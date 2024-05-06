"""This module converts async meross-iot library to synchronous bindings flask handle can use."""
import asyncio
import dataclasses

from concurrent.futures import Future
from pathlib import Path
from typing import Sequence, Tuple

from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager
from meross_iot.model.enums import Namespace as MerossEvtNamespace, OnlineStatus
from meross_iot.model.exception import (
    CommandError,
    CommandTimeoutError,
    MqttError,
    UnconnectedError,
    UnknownDeviceType,
)

from .cache import AsyncCachedObject, MerossCache, NO_VALUE
from .exc import CacheGetError, MerossClientError
from .threaded_worker import ThreadedWorker


ANY_MEROSS_IOT_EXC = (
    UnconnectedError,
    CommandTimeoutError,
    MqttError,
    CommandError,
    UnknownDeviceType,
)


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
    is_on_cache: bool = None

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

        async def _async_device_discovery():
            self._logger.debug("Running async device discovery...")
            manager = await self.get_manager()
            out = await manager.async_device_discovery()
            return tuple(el for el in out if el is not None)

        self.async_device_discovery = AsyncCachedObject(
            enabled=(lambda: self.is_authenticated),
            get_key=self.get_manager.cache_key,
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
            MerossEvtNamespace.CONTROL_TOGGLEX,  # An unknown device is toggled
        ):
            # flush device list cache if a new device appeared online
            self.async_device_discovery.flush()
            self._logger.debug("Device list cache flushed")

    @property
    def is_authenticated(self):
        return self.api_client is not None

    async def logout(self):
        if self.api_client:
            await self.api_client.async_logout()
        self.api_client = None

    async def login(self, api_base_url: str, user: str, password: str, raise_exc: bool):
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
        if len(api_base_url) > 0 and "https://" not in api_base_url[0]:
            self._logger.info(f"Adding missing \"https://\" prefix to {api_base_url!r}.")
            api_base_url = "https://" + api_base_url[0].replace("'", "")
        else:
            api_base_url = api_base_url[0]
        self._logger.info(f"Performing full auth login for the user {user!r} against {api_base_url!r}.")
        try:
            self.api_client = await MerossHttpClient.async_from_user_password(
                api_base_url=api_base_url, email=user, password=password
            )
        except ANY_MEROSS_IOT_EXC:
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
            return (
                self.get_manager.cache_key(),
                self.async_device_discovery.cache_key(),
            )

        async def _find_device():
            for device in await self.async_device_discovery():
                if device.uuid == dev_uuid:
                    if device.online_status is not OnlineStatus.ONLINE:
                        self._logger.info(f"The device is {device.online_status}.")
                        return NO_VALUE

                    try:
                        await device.async_update()
                    except CommandTimeoutError:
                        self._logger.error(
                            f"Timeout getting device update for {dev_uuid!r}. Flushing device cache."
                        )
                        device.online_status = OnlineStatus.OFFLINE
                        self.async_device_discovery.flush()
                        return NO_VALUE
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

    async def get_device_handles(self, dev_ids: Sequence[str]):
        """Returns list of (dev_handle, channel)"""
        if not self.is_authenticated:
            self._logger.warning("get_device_handles:: not authenticated")
            return []

        uuid_channel_pairs = [self.parse_plugin_dev_id(dev_id) for dev_id in dev_ids]
        devices = await asyncio.gather(
            *[
                self.get_controlled_device(dev_uuid)
                for (dev_uuid, _) in uuid_channel_pairs
            ]
        )
        out = []
        for device_hanle, (dev_uuid, dev_channel) in zip(devices, uuid_channel_pairs):
            if not device_hanle:
                self._logger.error(f"Device {dev_uuid!r} not found.")
                continue
            out.append((device_hanle, dev_channel))
        return out

    async def set_devices_states(self, dev_ids: Sequence[str], state: bool):
        self._logger.debug(f"Attempting to change state of {dev_ids!r}.")
        assert self.is_authenticated, "Must be authenticated"
        dev_handles = await self.get_device_handles(dev_ids)
        futures = []
        for device, channel in dev_handles:
            if state:
                the_future = device.async_turn_on(channel=channel)
            else:
                the_future = device.async_turn_off(channel=channel)
            futures.append(the_future)
        await asyncio.gather(*futures)
        self._logger.debug(f"Sucessfully changed state of {dev_ids!r}.")
        return True

    async def is_on(self, dev_ids: Sequence[str]) -> bool:
        assert self.is_authenticated, "Must be authenticated"
        dev_handles = await self.get_device_handles(dev_ids)
        on_states = [device.is_on(channel=channel) for (device, channel) in dev_handles]
        if on_states:
            out = all(on_states)
        else:
            out = False
        # save a copy of result for async polling
        self.is_on_cache = out
        return out

    async def toggle_devices(self, dev_ids: Sequence[str]) -> bool:
        self._logger.debug(f"Attempting to toggle devices {dev_ids!r}.")
        assert self.is_authenticated, "Must be authenticated"
        dev_handles = await self.get_device_handles(dev_ids)
        await asyncio.gather(
            *[device.async_toggle(channel=channel) for (device, channel) in dev_handles]
        )
        self._logger.debug(f"Sucessfully toggled devices {dev_ids!r}.")
        return True


class OctoprintPsuMerossClient:
    def __init__(self, cache_file: Path, logger):
        super().__init__()
        self._logger = logger
        self.worker = ThreadedWorker()
        self._async_client = _OctoprintPsuMerossClientAsync(
            cache_file=cache_file, logger=self._logger.getChild("async_client")
        )

    def login(
        self, api_base_url: str, user: str, password: str, raise_exc: bool = False
    ) -> Future:
        """Login to the meross cloud.

        Returns `None` in async mode, or True/False (success state) in sync mode.
        """
        if (not user) or (not password):
            self._logger.info("No user/password configured, skipping login")
            return False
        return asyncio.run_coroutine_threadsafe(
            self._async_client.login(api_base_url, user, password, raise_exc),
            self.worker.loop,
        )

    def list_devices(self):
        if not self.is_authenticated:
            raise MerossClientError("Not authenticated")
        future = asyncio.run_coroutine_threadsafe(
            self._async_client.list_devices(), self.worker.loop
        )
        return future.result()

    def set_devices_states(self, dev_ids: Sequence[str], state: bool) -> Future:
        if (not dev_ids) or (not self.is_authenticated):
            self._logger.info(
                f"Unable change device state for {dev_ids!r} (auth state: {self.is_authenticated})"
            )
            return

        return asyncio.run_coroutine_threadsafe(
            self._async_client.set_devices_states(dev_ids, state), self.worker.loop
        )

    def toggle_device(self, dev_ids: Sequence[str]) -> Future:
        if (not dev_ids) or (not self.is_authenticated):
            self._logger.info(f"Unable change device state for {dev_ids!r}")
            return

        return asyncio.run_coroutine_threadsafe(
            self._async_client.toggle_devices(dev_ids), self.worker.loop
        )

    def is_on(self, dev_ids: Sequence[str], sync: bool = False):
        self._logger.debug(f"Attempting to check if devices is on {dev_ids!r}.")
        if (not dev_ids) or (not self.is_authenticated):
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._async_client.is_on(dev_ids), self.worker.loop
        )
        if sync:
            return future.result()
        else:
            return self._async_client.is_on_cache

    @property
    def is_authenticated(self) -> bool:
        return self._async_client.is_authenticated

    @property
    def switch_operational(self) -> bool:
        """Return True/False signifying if the API is ready to be invoked to turn stuff on or off."""
        if not self.is_authenticated:
            return False
        return False
