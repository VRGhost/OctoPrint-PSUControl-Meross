import pytest

import octoprint_psucontrol_meross


@pytest.fixture
def psucontrol_plugin(mocker):
    return {
        "register_plugin": mocker.MagicMock(name="mock_register_plugin"),
    }


@pytest.fixture
def plugin_manager(mocker, psucontrol_plugin):
    def _get_helpers(key):
        return {"psucontrol": psucontrol_plugin}.get(key)

    out = mocker.MagicMock(name="mock_plugin_manager")
    out.get_helpers.side_effect = _get_helpers
    return out


@pytest.fixture
def psucontrol_meross(logger_mock, plugin_manager, tmpdir):
    out = octoprint_psucontrol_meross.plugin.PSUControlMeross()
    out._logger = logger_mock
    out._plugin_manager = plugin_manager
    out._data_folder = tmpdir
    # Called by the plugin core after performing all injections.
    # Override this to initialize your implementation.
    out.initialize()
    return out


def test_get_assets(psucontrol_meross):
    assert psucontrol_meross.get_assets()


@pytest.mark.parametrize("psucontrol_state", [None, "no_key", "ok"])
def test_on_startup(
    psucontrol_meross, plugin_manager, psucontrol_plugin, psucontrol_state
):
    if psucontrol_state is None:
        plugin_manager.get_helpers.side_effect = lambda key: None
    elif psucontrol_state == "no_key":
        psucontrol_plugin.pop("register_plugin")
    elif psucontrol_state == "ok":
        pass
    else:
        raise NotImplementedError(psucontrol_state)

    psucontrol_meross.on_startup("myhost", 4242)

    if psucontrol_state in (None, "no_key"):
        assert psucontrol_meross._logger.warning.called
    else:
        psucontrol_plugin["register_plugin"].assert_called_once_with(psucontrol_meross)
