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

    def get_settings_defaults(self):
        return {
            "user_email": "",
            "user_password": "",
        }

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
        self.meross.set_status(True)

    def turn_psu_off(self):
        self.meross.set_status(False)

    def get_psu_state(self):
        return self.meross.get_status()

    # Setting the location of the assets such as javascript
    def get_assets(self):
        return {
            "js": ["js/octoprint_psucontrol_settings.js"],
        }

    def get_api_commands(self):
        return {
            "try_meross_login": ("user_email", "user_password"),
        }

    def on_api_command(self, event, payload):
        self._logger.info("ON_EVENT {event!r}")
        if event == "try_meross_login":
            out = {
                "success": self.meross.login(
                    payload["user_email"], payload["user_password"], sync=True
                )
            }
        else:
            raise NotImplementedError(event)
        return flask.jsonify(out)

    def on_api_get(self, request):
        return flask.jsonify(foo="bar")
