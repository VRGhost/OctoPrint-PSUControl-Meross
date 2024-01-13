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

    def _ensure_meross_login(
        self, api_base_url=None, user=None, password=None, raise_exc=False
    ):
        """Ensures that we are logged in as user/pass

        (either provided or values from the settings).
        """
        if not api_base_url:
            api_base_url = self._settings.get(["api_base_url"])
        if not user:
            user = self._settings.get(["user_email"])
        if not password:
            password = self._settings.get(["user_password"])
        return self.meross.login(api_base_url, user, password, raise_exc=raise_exc)

    def get_settings_defaults(self):
        return {
            "api_urls": [
                {"name": "Asia-Pacific", "url": "iotx-ap.meross.com"},
                {"name": "Europe", "url": "iotx-eu.meross.com"},
                {"name": "US", "url": "iotx-us.meross.com"},
            ],
            "api_base_url": "iotx-eu.meross.com",
            "user_email": "",
            "user_password": "",
            "target_device_ids": [],
        }

    def get_settings_restricted_paths(self):
        return {
            "admin": [
                [
                    "api_base_url",
                ],
                [
                    "user_email",
                ],
                [
                    "user_password",
                ],
                [
                    "target_device_ids",
                ],
            ],
        }

    @property
    def target_device_ids(self):
        return self._settings.get(["target_device_ids"])

    def on_settings_save(self, data):
        self._logger.debug(f"on_settings_save: {data!r}")
        return super().on_settings_save(data)

    def on_settings_migrate(self, target, current):
        for migrate_from, migrate_to in zip(
            range(current, target), range(current + 1, target + 1)
        ):
            if (migrate_from, migrate_to) == (1, 2):
                # Migrate from settings v1 to v2
                old_dev_id = self._settings.get(["target_device_id"])
                if old_dev_id is not None:
                    self._settings.set(["target_device_ids"], [old_dev_id])
                    self._settings.remove(["target_device_id"])
            else:
                raise NotImplementedError([migrate_from, migrate_to])

    def get_settings_version(self):
        return 2

    def get_template_configs(self):
        return [
            {"type": "settings", "custom_bindings": True},
        ]

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
        self.meross.set_devices_states(self.target_device_ids, True)

    def turn_psu_off(self):
        self._logger.debug("turn_psu_off")
        self._ensure_meross_login()
        self.meross.set_devices_states(self.target_device_ids, False)

    def get_psu_state(self):
        self._logger.debug("get_psu_state")
        self._ensure_meross_login()
        return self.meross.is_on(self.target_device_ids)

    # Setting the location of the assets such as javascript
    def get_assets(self):
        return {
            "js": ["js/octoprint_psucontrol_settings.js"],
        }

    def get_api_commands(self):
        return {
            "try_login": ("api_base_url", "user_email", "user_password"),
            "list_devices": ("api_base_url", "user_email", "user_password"),
            "toggle_devices": (
                "api_base_url",
                "user_email",
                "user_password",
                "dev_ids",
            ),
        }

    def on_api_command(self, event, payload):
        self._logger.debug(f"ON_EVENT {event!r}")
        if event == "try_login":
            try:
                success = self._ensure_meross_login(
                    payload["api_base_url"],
                    payload["user_email"],
                    payload["user_password"],
                    raise_exc=True,
                ).result()
            except Exception as err:
                success = False
                message = str(err)
            else:
                message = "Login successful."

            out = {
                "rv": message,
                "error": (not success),
            }
        elif event == "toggle_device":
            # Ensure that we are logged in with the desired credentials
            err = False
            try:
                self._ensure_meross_login(
                    payload["api_base_url"],
                    payload["user_email"],
                    payload["user_password"],
                    raise_exc=True,
                ).result()
                rv = self.meross.toggle_device(payload["dev_id"]).result()
            except Exception as exc:
                err = message = str(exc)
            else:
                message = "success!" if rv else "Unexpected failure"
            out = {
                "rv": message,
                "error": err,
            }
        else:
            raise NotImplementedError(event)
        return flask.jsonify(out)

    def get_update_information(self):
        from . import __VERSION__, __plugin_name__

        return {
            "psucontrol_meross": {
                "displayName": __plugin_name__,
                "displayVersion": __VERSION__,
                "current": __VERSION__,
                # version check: github repository
                "type": "github_release",
                "user": "VRGhost",
                "repo": "OctoPrint-PSUControl-Meross",
                "stable_branch": {
                    "name": "Stable",
                    "branch": "main",
                },
                "prerelease_branches": [
                    {
                        "name": "Prerelease",
                        "branch": "main",
                    }
                ],
                "prerelease": False,
                "prerelease_channel": "main",
                # update method: pip w/ dependency links
                "pip": "https://github.com/VRGhost/OctoPrint-PSUControl-Meross/releases/download/"
                "{target_version}/OctoPrint_PSUControl_Meross-{target_version}-py3-none-any.whl",
            }
        }

    def on_api_get(self, request):
        device_list = ()
        if self.meross.is_authenticated:
            device_list = [dev.asdict() for dev in self.meross.list_devices()]
        return flask.jsonify(
            {
                "is_authenticated": self.meross.is_authenticated,
                "target_devices": [
                    {
                        "id": device_id,
                        "state": "on" if self.meross.is_on([device_id]) else "off",
                    }
                    for device_id in self.target_device_ids
                ],
                "device_list": device_list,
            }
        )
