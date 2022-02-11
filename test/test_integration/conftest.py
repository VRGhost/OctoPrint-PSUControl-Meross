import asyncio
import concurrent.futures


import asyncmock
import pytest

import octoprint_psucontrol_meross


@pytest.fixture(autouse=True)
def mocked_meross_http_client(mocker):
    out = mocker.patch(
        "octoprint_psucontrol_meross.meross_client.MerossHttpClient", spec=True
    )
    for async_fn in ("async_from_user_password",):
        setattr(out, async_fn, asyncmock.AsyncMock(name=f"async_mock::{async_fn}"))
    return out


@pytest.fixture
def mock_data_dir(fs):
    return fs.create_dir("/unittest")


@pytest.fixture
def mock_shelve_data():
    """Just a fixutre for the actual shelve data dict."""
    return {}


@pytest.fixture(autouse=True)
def mock_shelve_open(mocker, mock_shelve_data):
    shelve_mock = mocker.MagicMock(
        name="shelve_open_mock", spec=dict, wraps=mock_shelve_data
    )
    shelve_mock.__getitem__.side_effect = mock_shelve_data.__getitem__
    shelve_mock.__setitem__.side_effect = mock_shelve_data.__setitem__
    return mocker.patch("shelve.open", return_value=shelve_mock)


@pytest.fixture
def mock_plugin_settings(mocker):
    out = mocker.MagicMock(name="mock_plugin_settings")

    def _get_rv(path):
        return f"settings::{'::'.join(path)}::value"

    out.get.side_effect = _get_rv
    return out


@pytest.fixture
def octoprint_psu_meross_plugin_raw(mock_data_dir, logger_mock, mock_plugin_settings):
    out = octoprint_psucontrol_meross.plugin.PSUControlMeross()
    out._data_folder = mock_data_dir.path
    out._logger = logger_mock
    out._settings = mock_plugin_settings
    return out


@pytest.fixture
def octoprint_psu_meross_plugin(octoprint_psu_meross_plugin_raw):
    octoprint_psu_meross_plugin_raw.initialize()
    return octoprint_psu_meross_plugin_raw


@pytest.fixture
def run_coroutine_threadsafe(mocker):
    orig_fn = asyncio.run_coroutine_threadsafe
    out = mocker.patch.object(asyncio, "run_coroutine_threadsafe")
    out._all_futures = []

    def _my_side_effect(*args, **kwargs):
        future = orig_fn(*args, **kwargs)
        out._all_futures.append(future)
        return future

    out.side_effect = _my_side_effect
    return out


@pytest.fixture
def threaded_loop(octoprint_psu_meross_plugin, run_coroutine_threadsafe):
    """Returns the loop that is running all async code."""

    def _wait_all_futures():
        rv = concurrent.futures.wait(run_coroutine_threadsafe._all_futures)
        out = []
        for future in rv.done:
            out.append(future.result())
        return out

    out = octoprint_psu_meross_plugin.meross.worker.loop
    out.wait_all_futures = _wait_all_futures
    return out
