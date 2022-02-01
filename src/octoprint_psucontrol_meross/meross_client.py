"""This module converts async meross-iot library to synchronous bindings flask handle can use."""
import asyncio
import hashlib
import os
import shelve
import threading
import time

from pathlib import Path
from typing import Callable

from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager

from .threaded_worker import ThreadedWorker


class MerossClientError(Exception):
    """A generic meross client exception."""


class MerossCache:
    """Wrapper around shelf's cache file."""

    _shelve: dict = None  # shelve cache

    def __init__(self, cache_file: Path, logger):
        self._logger = logger
        self.mutex = threading.Lock()
        try:
            self._shelve = shelve.open(os.fspath(cache_file))
        except Exception:
            self._logger.exception(f"Error while opening {cache_file!r} cache")
            if cache_file.exists():
                os.unlink(cache_file)
            # Attempt one more time
            self._shelve = shelve.open(cache_file)
        else:
            self._logger.debug(f"Sucessfully opened {cache_file!r} cache.")
        if self._shelve is None:
            raise MerossClientError("Unable to open shelve cache.")
        self._check_cache_version()

    def _check_cache_version(self):
        """Confirm version of the cache file."""
        with self.mutex:
            key = "__CACHE_VERSION__"
            self._shelve.setdefault(key, 1)
            if self._shelve[key] != 1:
                raise MerossClientError("Cache file version mismatch")

    @classmethod
    def hash_auth_pair(cls, user: str, password: str) -> str:
        return hashlib.sha256(f"{user}:{password}".encode("utf8")).hexdigest()

    @classmethod
    def get_session_name_key(cls, user: str, password: str):
        hashval = cls.hash_auth_pair(user, password)
        return f"_meross_token_{hashval}"

    def get_cloud_session_token(self, user: str, password: str):
        """Returns a cloud token for user/password combination (if exists) or `None`"""
        key = self.get_session_name_key(user, password)
        with self.mutex:
            return self._shelve.get(key, None)

    def set_cloud_session_token(self, user: str, password: str, value):
        """Returns a cloud token for user/password combination (if exists) or `None`"""
        key = self.get_session_name_key(user, password)
        with self.mutex:
            self._shelve[key] = value
        return key

    def delete_cloud_session_token(self, user: str, password: str):
        key = self.get_session_name_key(user, password)
        with self.mutex:
            self._shelve.pop(key, None)


class _OctoprintPsuMerossClientAsync:
    """Async client bits."""

    api_client: MerossHttpClient = None

    def __init__(self, cache_file: Path, logger):
        super().__init__()
        self._logger = logger
        self._cache = MerossCache(cache_file, logger=logger.getChild("cache"))

    _manager_cache = None  # tuple of (http_client_id, cached obj)

    async def get_manager(self) -> MerossManager:
        if (
            self.is_authenticated
            and self._manager_cache
            and self._manager_cache[0] == id(self._async_client)
        ):
            # Return cached value
            return self._manager_cache[1]
        # Try constructing new object
        if self.is_authenticated:
            manager = MerossManager(http_client=self.api_client)
            self._manager_cache = (id(self.api_client), manager)
            await manager.async_init()
            return manager
        raise MerossClientError("Not authenticated/HTTP connection not found.")

    _device_discovery_cache = None  # tuple of (manager_id, cache_creation_time, data)

    async def async_device_discovery(self):
        manager = await self.get_manager()
        if self._device_discovery_cache:
            max_cache_age = 10 * 60  # 10 minutes
            (cached_manager_id, cache_t, cached_data) = self._device_discovery_cache
            if (id(manager) == cached_manager_id) and (
                (cache_t + max_cache_age) > time.time()
            ):
                return cached_data
        # re-fetch the data
        out = await manager.async_device_discovery()
        out = tuple(el for el in out if el is not None)
        self._device_discovery_cache = (id(manager), time.time(), out)
        return out

    @property
    def is_authenticated(self):
        return self.api_client is not None

    async def logout(self):
        if self.api_client:
            await self.api_client.logout()
        self.api_client = None
        del self.manager

    _cache_session_token: Callable

    async def login(self, user: str, password: str):
        restore_success = await self._try_restore_session(user, password)
        if restore_success:
            self._logger.debug("Restored saved session.")
            return True
        await self.logout()
        try:
            self.api_client = await MerossHttpClient.async_from_user_password(
                email=user, password=password
            )
        except Exception:
            self._logger.exception("Error when trying to log in.")
            self.api_client = None
        else:
            # save the session (and store a bound function to do that periodically later)
            def _save_session_fn():
                if self.api_client and self.api_client.cloud_credentials:
                    self._cache.set_cloud_session_token(
                        user, password, self.api_client.cloud_credentials
                    )

            self._cache_session_token = _save_session_fn
            self._cache_session_token()

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

    async def list_devices(self):
        """Return a list of (uuid, name) tuples."""
        assert self.is_authenticated, "Must be authenticated"
        devices = await self.async_device_discovery()
        out = [(dev.uuid, dev.name) for dev in devices]
        out.sort(key=lambda el: el[1])  # sort by name
        return out

    async def set_device_state(self, uuid: str, state: bool):
        assert self.is_authenticated, "Must be authenticated"
        devices = await self.async_device_discovery()
        for device in devices:
            if device.uuid == uuid:
                await device.async_update()
                if state:
                    await device.async_turn_on(channel=0)
                else:
                    await device.async_turn_off(channel=0)


class OctoprintPsuMerossClient:
    def __init__(self, cache_file: Path, logger):
        super().__init__()
        self._logger = logger
        self.worker = ThreadedWorker()
        self._async_client = _OctoprintPsuMerossClientAsync(
            cache_file=cache_file, logger=self._logger.getChild("async_client")
        )

    def login(self, user: str, password: str, sync: bool = False):
        """Login to the meross cloud.

        Returns `None` in async mode, or True/False (success state) in sync mode.
        """
        future = asyncio.run_coroutine_threadsafe(
            self._async_client.login(user, password), self.worker.loop
        )
        if sync:
            return future.result()

    def list_devices(self):
        if not self.is_authenticated:
            raise MerossClientError("Not authenticated")
        future = asyncio.run_coroutine_threadsafe(
            self._async_client.list_devices(), self.worker.loop
        )
        return future.result()

    def set_device_state(self, uuid: str, state: bool):
        future = asyncio.run_coroutine_threadsafe(
            self._async_client.set_device_state(uuid, state), self.worker.loop
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

    def get_status(self) -> bool:
        """Return True/False for on/off respectively."""
        if not self.switch_operational:
            self._logger.info(
                "Unable to acquire switch status - Meross API is not operational (not authenticated?)"
            )
            return False
        return True

    def set_status(self, state: bool):
        """Set the desired switch state."""
        if not self.switch_operational:
            self._logger.info(
                "Unable to acquire switch status - Meross API is not operational (not authenticated?)"
            )
            return False
