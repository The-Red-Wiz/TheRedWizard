import xbmc, xbmcaddon


# addonId is the Addon ID
# id1 is the Category (Tab) offset (0=first, 1=second, 2...etc)
# id2 is the Setting (Control) offset (0=first, 1=second, 2...etc)
# Example: OpenAddonSettings('plugin.video.name', 2, 3)
# This will open settings dialog focusing on fourth setting (control) inside the third category (tab)

def openAddonSettings(addonId, id1=None, id2=None):
    xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
    if id1 != None and id2 != None:
        xbmc.executebuiltin('SetFocus(%i)' % (id1))
    if id2 != None:
        xbmc.executebuiltin('SetFocus(%i)' % (id2)) 

def tmdbh_mdblist_api():
        openAddonSettings('plugin.video.themoviedb.helper', -196, -175)
        
def rurl_settings_rd():
        openAddonSettings('script.module.resolveurl', -198, -162)

def rurl_settings_pm():
        openAddonSettings('script.module.resolveurl', -198, -173)

def rurl_settings_ad():
        openAddonSettings('script.module.resolveurl', -199, -174)

def rurl_settings_oc():
        openAddonSettings('script.module.resolveurl', -198, -184)

def rurl_settings_tb():
        openAddonSettings('script.module.resolveurl', -197, -174)

def am_accounts():
        openAddonSettings('script.module.acctmgr', -200, 0)

def am_manage():
        openAddonSettings('script.module.acctmgr', -199, 0)

def am_backup_restore():
        openAddonSettings('script.module.acctmgr', -198, 0)
