def test_init(mock_shelve_data, octoprint_psu_meross_plugin_raw, mock_shelve_open):
    assert mock_shelve_data.get("__CACHE_VERSION__") is None
    octoprint_psu_meross_plugin_raw.initialize()
    assert mock_shelve_data.get("__CACHE_VERSION__") == 1
    mock_shelve_open.assert_called_once_with("/unittest/meross_cloud.cache")


def test_on_settings_initialized(
    octoprint_psu_meross_plugin,
    mocked_meross_http_client,
    threaded_loop,
    mock_plugin_settings,
    mock_shelve_data,
):
    octoprint_psu_meross_plugin.on_settings_initialized()
    threaded_loop.wait_all_futures()
    assert mocked_meross_http_client.async_from_user_password.called
    mocked_meross_http_client.async_from_user_password.assert_called_with(
        api_base_url="settings::api_base_url::value", email="settings::user_email::value", password="settings::user_password::value"
    )
    assert (
        mock_shelve_data[
            "_meross_token_925c4eff75c595b75f84a1ec4733616b557aeea72cf643c4b3d354b15ca41b9e"
        ]
        == mocked_meross_http_client.async_from_user_password.return_value.cloud_credentials
    )
