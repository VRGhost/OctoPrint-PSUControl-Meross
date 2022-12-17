import logging
import unittest.mock

import asyncmock
import meross_iot.http_api
import pytest
import pytest_asyncio

from octoprint_psucontrol_meross import meross_client


@pytest.fixture
def logger():
    return logging.getLogger(f"{__name__}.test.logger")


@pytest.fixture
def cache_file(tmp_path):
    return tmp_path


@pytest.fixture
def mock_meross_cache_cls(mocker):
    return mocker.patch.object(meross_client, "MerossCache")


@pytest.fixture
def mock_meross_cache(mock_meross_cache_cls):
    return mock_meross_cache_cls.return_value


@pytest_asyncio.fixture
async def mock_meross_iot_http_client():
    mock_client = asyncmock.create_autospec(
        meross_iot.http_api.MerossHttpClient,
        name="mock_meross_iot.http_api.MerossHttpClient",
    )
    mock_client.async_from_user_password.return_value = mock_client
    with unittest.mock.patch.object(meross_client, "MerossHttpClient", new=mock_client):
        yield mock_client


@pytest_asyncio.fixture
async def test_client(
    tmp_path, logger, mock_meross_cache_cls, mock_meross_iot_http_client
):
    return meross_client._OctoprintPsuMerossClientAsync(tmp_path, logger)


@pytest.mark.asyncio
async def test_login(test_client, mock_meross_iot_http_client, mock_meross_cache):
    mock_meross_cache.get_cloud_session_token.return_value = None
    await test_client.login("testuser", "password", raise_exc=True)
    mock_meross_iot_http_client.async_from_user_password.assert_called_once_with(
        email="testuser", password="password"
    )


class TestLogout:
    @pytest_asyncio.fixture
    def test_client(self, test_client, mock_meross_iot_http_client):
        """Log-in the test client"""
        test_client.api_client = mock_meross_iot_http_client
        return test_client

    @pytest.mark.asyncio
    async def test_logout(self, test_client, mock_meross_iot_http_client):
        await test_client.logout()
        mock_meross_iot_http_client.async_logout.assert_called_once_with()
