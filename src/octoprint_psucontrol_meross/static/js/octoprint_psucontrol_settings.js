$(function() {
    function OctoprintPsuControlMerossViewModel(parameters) {
        var self = this;

        self._g_settings = parameters[0];
        self.settings = null;

        self._ui_message = {
            level: "info",
            text: ""
        }
        self.devices =  ko.observableArray([]);
        self.selected_devices = ko.observableArray([]);

        self.devices.extend({ rateLimit: 200 });

        self.message = new function() {
            this.state = {
                level: ko.observable(),
                text: ko.observable(),
            }

            this._idx_gen = 0;

            this.set = function(level, text) {
                this._idx_gen ++;
                this.state.level(level);
                this.state.text(text);

                var thisCallId = this._idx_gen;
                var _msgObj = this;
                return function(){ _msgObj.hideIf(thisCallId); }
            }

            this.info = function (text) {
                return this.set('info', text);
            }

            this.error = function (text) {
                return this.set('error', text);
            }

            this.success = function (text) {
                return this.set('success', text);
            }

            this.hide = function() {
                return this.set(null, null);
            }

            this.hideIf = function(idx) {
                // Hide the box only if the message ID didn't change since
                if(this._idx_gen == idx) {
                    this.hide();
                }
            }

            this.ajaxWait = function() {
                // Just a shorthand for 'running in the backend'
                return this.info('... Talking to the backend ...');
            }
        };

        function ensure_devices_are_listed(device_ids) {
            // Ensure that an element with dev_id == device_id always exists
            //   in self.devices
            var missing_devices = [];
            var known_device_ids = self.devices().map(el => el.dev_id);
            for(test_dev_id of device_ids){
                if(!known_device_ids.includes(test_dev_id)) {
                    missing_devices.push(test_dev_id)
                }
            }
            console.log("missing_devices", missing_devices)
            
            for(missing_device_id of missing_devices) {
                self.devices.push({dev_id: missing_device_id, name: 'Unknown (' + missing_device_id +')' });
            }
        }

        self.onBeforeBinding = function () {
            self.settings = self._g_settings.settings.plugins.psucontrol_meross;
            self.message.hide();

            var orig_selection = self.settings.target_device_ids();
            // Add a dummy element to the dropdown if there had been a device selected
            if(!!orig_selection)
            {
                ensure_devices_are_listed(orig_selection);
            }
        }

        self.onSettingsShown = function() {
            self.fetch_plugin_status();
        }

        self.fetch_plugin_status = function() {
            // Fetch BE state
            var ajaxDone = this.message.ajaxWait();
            OctoPrint.simpleApiGet(
                "psucontrol_meross",
            ).done(function(response){
                var orig_selection = self.settings.target_device_ids(); // Store the current selection (while the list is being re-populated)
                console.log("ORIG", orig_selection);
                self.devices.removeAll()
                for (device of response.device_list) {
                    self.devices.push(device);
                }
                ensure_devices_are_listed(orig_selection)
                self.settings.target_device_ids(orig_selection);
            }).always(ajaxDone);
        }

        self.toggle_device = function() {
            var username = self.settings.user_email();
            var password = self.settings.user_password();
            var device_ids = self.settings.target_device_ids();

            if (!username || !password || !device_id) {
                self.message.error("Missing login/password or no device selected.");
                return;
            }
            
            var ajaxDone = this.message.ajaxWait();
            OctoPrint.simpleApiCommand(
                "psucontrol_meross",
                "toggle_device",
                {
                    "user_email": username,
                    "user_password": password,
                    "dev_ids": device_ids,
                }
            ).done(function(response){
                // psucontrol_meross_show_error(response.error);
                if(response.error) {
                    self.message.error(response.rv);
                }
                else
                {
                    self.message.success(response.rv);
                    self.fetch_plugin_status();
                }
            }).always(ajaxDone);
        }

        self.test_meross_cloud_login = function() {
            var username = self.settings.user_email();
            var password = self.settings.user_password();

            if (!username || !password) {
                self.message.error("Please provide both Meross cloud username and password.");
                return;
            }
            
            var ajaxDone = this.message.ajaxWait();
            OctoPrint.simpleApiCommand(
                "psucontrol_meross",
                "try_login",
                {
                    "user_email": username,
                    "user_password": password,
                }
            ).done(function(response){
                // psucontrol_meross_show_error(response.error);
                if(response.error) {
                    self.message.error(response.rv);
                }
                else
                {
                    self.message.success(response.rv);
                    self.fetch_plugin_status();
                }
            }).always(ajaxDone);
        }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: OctoprintPsuControlMerossViewModel,
        additionalNames: [],
        dependencies: ["settingsViewModel"],
        elements: ["#psucontrol_meross_settings_form"]
    });
});