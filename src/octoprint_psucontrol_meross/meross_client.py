"""This module converts async meross-iot library to synchronous bindings flask handle can use."""
import asyncio
import dataclasses
import hashlib
import os
import shelve
import threading
import time

from pathlib import Path
from typing import Callable, Iterable, Tuple

from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager
from meross_iot.model.enums import Namespace as MerossEvtNamespace

from .cache import AsyncCachedObject, MerossCache
from .exc import CacheGetError, MerossClientError
from .threaded_worker import ThreadedWorker


@dataclasses.dataclass
class MerossDeviceHandle:
    """A simplified thread-safe meross device ID."""

    name: str
    dev_id: str

    def asdict(self) -> dict:
        return dataclasses.asdict(self)


class _OctoprintPsuMerossClientAsync:
    """Async client bi ts."""

    # a Key that identifies currently active session
    #  (used to deduplicate login())
    _current_session_key: str = None
    api_client: MerossHttpClient = None

    def __init__(self, cache_file: Path, logger):
        super().__init__()
        self._logger = logger
        self._cache = MerossCache(cache_file, logger=logger.getChild("cache"))

        # Configure awaitable caches
        async def _get_manager_fn():
            manager = MerossManager(http_client=self.api_client)
            await manager.async_init()
            manager.register_push_notification_handler_coroutine(self._on_manager_event)
            return manager

        self.get_manager = AsyncCachedObject(
            enabled=(lambda: self.is_authenticated),
            get_key=(lambda: id(self.api_client)),
            get_object=_get_manager_fn,
        )

        async def _get_manager_id():
            manager = await self.get_manager()
            return id(manager)

        async def _async_device_discovery():
            self._logger.debug("Running async device discovery...")
            manager = await self.get_manager()
            out = await manager.async_device_discovery()
            return tuple(el for el in out if el is not None)

        self.async_device_discovery = AsyncCachedObject(
            enabled=(lambda: self.is_authenticated),
            get_key=_get_manager_id,
            get_object=_async_device_discovery,
            timeout=10 * 60,  # 10 minutes
        )

        self._controlled_device_cache = {}

    async def _on_manager_event(
        self, evt, data: dict, device_internal_id: str, *args, **kwargs
    ):
        if evt.namespace in (
            MerossEvtNamespace.SYSTEM_ONLINE,
            MerossEvtNamespace.SYSTEM_ALL,
        ):
            # flush device list cache if a new device appeared online
            self.async_device_discovery.flush()
            self._logger.debug("Device list cache flushed")

    @property
    def is_authenticated(self):
        return self.api_client is not None

    async def logout(self):
        if self.api_client:
            await self.api_client.logout()
        self.api_client = None

    async def login(self, user: str, password: str, raise_exc: bool):
        expected_session_key = self._cache.get_session_name_key(user, password)
        self._logger.debug(
            f"login called with user {user!r} "
            f", expected session key = {expected_session_key!r} "
            f"and current state is_authenticated = {self.is_authenticated}, "
            f"current session key = {self._current_session_key!r}"
        )
        if self.is_authenticated:
            if expected_session_key == self._current_session_key:
                self._logger.debug("Already logged in.")
                return True
            else:
                await self.logout()

        restore_success = await self._try_restore_session(user, password)
        if restore_success:
            self._logger.debug("Restored saved session.")
            return True
        self._logger.info(f"Performing full auth login for the user {user!r}.")
        try:
            self.api_client = await MerossHttpClient.async_from_user_password(
                email=user, password=password
            )
        except Exception:
            self._logger.exception("Error when trying to log in.")
            self.api_client = None
            if raise_exc:
                raise
        else:
            # save the session (and store a bound function to do that periodically later)
            self._current_session_key = self._cache.set_cloud_session_token(
                user, password, self.api_client.cloud_credentials
            )

        return bool(self.api_client)  # Return 'True' on success

    async def _try_restore_session(self, user: str, password: str) -> bool:
        old_session = self._cache.get_cloud_session_token(user, password)
        if not old_session:
            # Nothing to restore
            return False

        success = False
        try:
            self.api_client = await MerossHttpClient.async_from_cloud_creds(old_session)
            success = True
        except Exception:
            self._logger.exception("Error while trying to restore the session.")
            self._cache.delete_cloud_session_token(user, password)
        return success

    async def list_devices(self) -> Tuple[MerossDeviceHandle]:
        """Return a list of (uuid, name) tuples."""
        assert self.is_authenticated, "Must be authenticated"
        out = []
        for device in await self.async_device_discovery():
            for channel in device.channels:
                if channel.is_master_channel:
                    # Use plain device name for master channel
                    merged_name = device.name
                else:
                    merged_name = f"{device.name}: {channel.name}"

                out.append(
                    MerossDeviceHandle(
                        name=merged_name,
                        dev_id=f"{device.uuid}::{channel.index}",
                    )
                )
        out.sort(key=lambda el: el.name)
        return tuple(out)

    async def get_controlled_device(self, dev_uuid: str):
        try:
            cache_obj = self._controlled_device_cache[dev_uuid]
        except KeyError:
            # Not cached yet
            pass
        else:
            return await cache_obj(default=None)

        async def _get_device_cache_key():
            manager = await self.get_manager()
            # dev_list is a cached tuple
            dev_list = await self.async_device_discovery()
            return (id(manager), id(dev_list))

        async def _find_device():
            for device in await self.async_device_discovery():
                if device.uuid == dev_uuid:
                    await device.async_update()
                    return device
            raise CacheGetError(dev_uuid)

        self._controlled_device_cache[dev_uuid] = AsyncCachedObject(
            enabled=(lambda: self.is_authenticated),
            get_key=_get_device_cache_key,
            get_object=_find_device,
        )
        return await self._controlled_device_cache[dev_uuid](default=None)

    def parse_plugin_dev_id(self, dev_id: str):
        """Convert this plugins' device IDs (<meross uuid>::<channel idx>) to a tuple."""
        (uuid, channel_id) = dev_id.split("::")
        return (uuid, int(channel_id))

    async def set_device_state(self, dev_id: str, state: bool):
        assert self.is_authenticated, "Must be authenticated"
        (dev_uuid, channel) = self.parse_plugin_dev_id(dev_id)
        device = await self.get_controlled_device(dev_uuid)
        if not device:
            self._logger.error(f"Device {dev_id} not found.")
            return
        if state:
            await device.async_turn_on(channel=channel)
        else:
            await device.async_turn_off(channel=channel)
        self._logger.debug(
            f"Sucessfully changed state of {dev_uuid!r} (channel {channel!r})."
        )

    async def is_on(self, dev_id: str) -> bool:
        (dev_uuid, channel) = self.parse_plugin_dev_id(dev_id)
        device = await self.get_controlled_device(dev_uuid)
        if not device:
            self._logger.error(f"Device {dev_id} not found.")
            return False
        return device.is_on(channel=channel)


class OctoprintPsuMerossClient:
    def __init__(self, cache_file: Path, logger):
        super().__init__()
        self._logger = logger
        self.worker = ThreadedWorker()
        self._async_client = _OctoprintPsuMerossClientAsync(
            cache_file=cache_file, logger=self._logger.getChild("async_client")
        )

    def login(self, user: str, password: str, raise_exc: bool = False):
        """Login to the meross cloud.

        Returns `None` in async mode, or True/False (success state) in sync mode.
        """
        if (not user) or (not password):
            self._logger.info("No user/password configured, skipping login")
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._async_client.login(user, password, raise_exc), self.worker.loop
        )
        return future.result()

    def list_devices(self):
        if not self.is_authenticated:
            raise MerossClientError("Not authenticated")
        future = asyncio.run_coroutine_threadsafe(
            self._async_client.list_devices(), self.worker.loop
        )
        return future.result()

    def set_device_state(self, dev_id: str, state: bool):
        if (not dev_id) or (not self.is_authenticated):
            self._logger.info(
                f"Unable change device state for {dev_id!r} (auth state: {self.is_authenticated})"
            )
            return

        future = asyncio.run_coroutine_threadsafe(
            self._async_client.set_device_state(dev_id, state), self.worker.loop
        )
        return future.result()

    def is_on(self, dev_id: str):
        if (not dev_id) or (not self.is_authenticated):
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._async_client.is_on(dev_id), self.worker.loop
        )
        return future.result()

    @property
    def is_authenticated(self) -> bool:
        return self._async_client.is_authenticated

    @property
    def switch_operational(self) -> bool:
        """Return True/False signifying if the API is ready to be invoked to turn stuff on or off."""
        if not self.is_authenticated:
            return False
        return False
