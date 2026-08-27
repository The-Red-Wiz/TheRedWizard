import xbmc

from resources.lib.common import settings
from resources.lib.common import utils

# Kodi's context-menu <visible> conditions can only check Window properties,
# not add-on settings directly, so this tiny always-idle monitor mirrors the
# "Show 'Add to Shortcut Manager Group' on Context Menu" setting into a
# Window property whenever it changes. It does no polling, caching, or
# background work of any kind.
_properties = ["context.shortcutmanager"]


class ContextMenuMonitor(xbmc.Monitor):
    def __init__(self):
        super(ContextMenuMonitor, self).__init__()
        self._update_properties()

    def onSettingsChanged(self):
        self._update_properties()

    def _update_properties(self):
        for property in _properties:
            setting = settings.get_setting(property)
            if setting is not None:
                utils.set_property(property, setting)
            else:
                utils.clear_property(property)


if __name__ == "__main__":
    _monitor = ContextMenuMonitor()
    _monitor.waitForAbort()
