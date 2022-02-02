from pathlib import Path

import flask
import octoprint.plugin

from . import meross_client


class PSUControlMeross(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.AssetPlugin,
):
    def initialize(self):
        super().initialize()
        cache_file = Path(self.get_plugin_data_folder()) / "meross_cloud.cache"
        self.meross = meross_client.OctoprintPsuMerossClient(
            cache_file=cache_file,
            logger=self._logger.getChild("meross_client"),
        )

    def on_settings_initialized(self):
        self._logger.info(f"{self.__class__.__name__} loaded.")
        self._ensure_meross_login()
        

    def _ensure_meross_login(self, user=None, password=None):
        """Ensures that we are logged in as user/pass

        (either provided or values from the settings).
        """
        self._logger.debug(f"SETTINGS: {self._settings}, {type(self._settings)}")
        self._logger.debug(f"ALL DATA: {self._settings.get_all_data()}")
        if (not user) and (not password):
            user = self._settings.get(['user_email'])
            password = self._settings.get(['user_password'])
        return self.meross.login(user, password)

    def get_settings_defaults(self):
        return {
            "user_email": "",
            "user_password": "",
            "target_device_id": "",
        }

    def get_settings_restricted_paths(self):
        return {
            'admin': [
                ["user_email", ],
                ["user_password", ],
                ["target_device_id", ],
            ],
        }

    def on_settings_save(self, data):
        self._logger.debug(f"on_settings_save: {data!r}")
        return super().on_settings_save(data)

    def get_settings_version(self):
        return 1

    def on_startup(self, host, port):
        psucontrol_helpers = self._plugin_manager.get_helpers("psucontrol")
        if not psucontrol_helpers or "register_plugin" not in psucontrol_helpers.keys():
            self._logger.warning(
                "The version of PSUControl that is installed "
                "does not support plugin registration."
            )
            return

        self._logger.debug("Registering plugin with PSUControl")
        psucontrol_helpers["register_plugin"](self)

    def turn_psu_on(self):
        self._logger.debug("turn_psu_on")
        self._ensure_meross_login()
        self.meross.set_device_state(self._settings.get(['target_device_id']), True)

    def turn_psu_off(self):
        self._logger.debug("turn_psu_off")
        self._ensure_meross_login()
        self.meross.set_device_state(self._settings.get(['target_device_id']), False)

    def get_psu_state(self):
        self._logger.debug("get_psu_state")
        self._ensure_meross_login()
        return self.meross.is_on(self._settings.get(['target_device_id']))

    # Setting the location of the assets such as javascript
    def get_assets(self):
        return {
            "js": ["js/octoprint_psucontrol_settings.js"],
        }

    def get_api_commands(self):
        return {
            "try_login": ("user_email", "user_password"),
            "list_devices": ("user_email", "user_password"),
            "set_device_state": ("user_email", "user_password", "dev_id", "state"),
        }

    def on_api_command(self, event, payload):
        self._logger.info(f"ON_EVENT {event!r}")
        if event == "try_login":
            out = {
                "rv": self._ensure_meross_login(
                    payload["user_email"], payload["user_password"]
                ),
                "error": False,
            }
        elif event == "list_devices":
            # Ensure that we are logged in with the desired credentials
            login_ok = self._ensure_meross_login(payload["user_email"], payload["user_password"])
            if login_ok:
                rv = [
                    dev.asdict()
                    for dev in self.meross.list_devices()
                ]
            else:
                rv = []
            out = {
                "rv": rv,
                "error": "Unable to authenticate" if not login_ok else ""
            }
        elif event == "set_device_state":
            # Ensure that we are logged in with the desired credentials
            login_ok = self._ensure_meross_login(payload["user_email"], payload["user_password"])
            if login_ok:
                rv = self.meross.set_device_state(payload['dev_id'], bool(payload['state']))
            else:
                rv = None
            out = {
                "rv": rv,
                "error": "Unable to authenticate" if not login_ok else "",
            }
        else:
            raise NotImplementedError(event)
        return flask.jsonify(out)

    def on_api_get(self, request):
        return flask.jsonify(hello="world")
