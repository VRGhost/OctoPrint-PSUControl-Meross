__VERSION__ = "0.13.3"
__author__ = "Ilja Orlovs <vrghost@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = (
    "Copyright (C) 2021 Ilja Orlovs - Released under terms of the AGPLv3 License"
)
__plugin_name__ = "PSU Control - Meross"
__plugin_pythoncompat__ = ">=3.7,<4"

from . import exc
from .plugin import PSUControlMeross


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PSUControlMeross()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    }
