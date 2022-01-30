import flask
import octoprint.plugin

from meross_iot.http_api import MerossHttpClient


class PSUControlMeross(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.AssetPlugin,
):
    def __init__(self):
        super().__init__()
        self.config = {}
        self.status = False

    def get_settings_defaults(self):
        return {
            "user_email": "",
            "user_password": "",
        }

    def get_meross_http_client(self):
        return MerossHttpClient

    def get_template_vars(self):
        out = super().get_template_vars()
        out.update(
            {
                "meross_status": {
                    "client_obj": self.get_meross_http_client(),
                    "connection_ok": "HELLO WORLD!",
                }
            }
        )
        return out

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
        self._logger.info("ON")
        self.status = True

    def turn_psu_off(self):
        self._logger.info("OFF")
        self.status = False

    def get_psu_state(self):
        return self.status

    # Setting the location of the assets such as javascript
    def get_assets(self):
        return {
            "js": ["js/octoprint_psucontrol_settings.js"],
        }

    def get_api_commands(self):
        return {
            "try_meross_login": (),
        }

    def on_event(self, event, payload):
        if event == "try_meross_login":
            out = {"success": bool(self.get_meross_http_client())}
        else:
            raise NotImplementedError(event)
        return flask.jsonify(res=out)
