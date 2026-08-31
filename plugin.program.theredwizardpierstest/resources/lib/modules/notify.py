import xbmc
import xbmcgui
import xbmcaddon
import re
from ..modules.parser import get_page
from ..modules import _service
from uservar import notify_url, changelog_dir
from .addonvar import setting, BUILD_NAME, CURRENT_BUILD

def get_notify() -> list:
    response = get_page(notify_url)
    try:
        split_response = response.split('|||')
        notify_version = int(split_response[0])
        message = split_response[1]
    except:
        notify_version = 0
        message = 'Improper Notifications format. Please check the Notifications text.'
    return [notify_version, message]

def get_changelog():
    #build = setting('buildname')
    if not BUILD_NAME:
        rm_colors = "".join(re.split("\[|\]", CURRENT_BUILD)[::2])
        filename = rm_colors.replace(' ', '%20')
        changelog = '%s%s.txt' %(changelog_dir, filename)
        message = get_page(changelog)
        return message
    else:
        rm_colors = "".join(re.split("\[|\]", BUILD_NAME)[::2])
        filename = rm_colors.replace(' ', '%20')
        changelog = '%s%s.txt' %(changelog_dir, filename)
        message = get_page(changelog)
        return message

def notification(message: str) -> None:  
    class Notify(xbmcgui.WindowXMLDialog):
        KEY_NAV_BACK = 92
        TEXTBOX = 300
        CLOSEBUTTON = 302
        
        def onInit(self):
            self.getControl(self.TEXTBOX).setText(message)
            
        def onAction(self, action):
            if action.getId() == self.KEY_NAV_BACK:
                self.Close()
    
        def onClick(self, controlId):
            if controlId == self.CLOSEBUTTON:
                self.Close()

        def Close(self):
            self.close()
            
    d = Notify('notify.xml', xbmcaddon.Addon().getAddonInfo('path'), 'Default', '720p')
    d.doModal()
    del d

def notification_clog(message: str) -> None:  
    class Notify(xbmcgui.WindowXMLDialog):
        KEY_NAV_BACK = 92
        TEXTBOX = 300
        CLOSEBUTTON = 302
        
        def onInit(self):
            self.getControl(self.TEXTBOX).setText(message)
            
        def onAction(self, action):
            if action.getId() == self.KEY_NAV_BACK:
                self.close()
                _service.Startup().check_updates()
    
        def onClick(self, controlId):
            if controlId == self.CLOSEBUTTON:
                self.close()
                _service.Startup().check_updates()

        def Close(self):
            self.close()
            _service.Startup().check_updates()
    
    d = Notify('changelog.xml', xbmcaddon.Addon().getAddonInfo('path'), 'Default', '720p')
    d.doModal()
    del d
