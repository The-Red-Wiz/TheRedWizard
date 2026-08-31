import shutil
import sys
import os
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import time
from .params import Params
from .play_video import play_video
from uservar import notify_url, changelog_dir
from resources.lib.modules import addonvar
from .menus import main_menu, build_menu, submenu_maintenance, submenu_tools, submenu_whitelist, authorize_menu, backup_restore, restore_gui_skin, kodi_settings, kodi_specific, kodi_builtins, addon_specific, addonbrowser
from .authorize import authorize_menu as debrid_trakt_menu, authorize_submenu
from .build_install import build_install
from .maintenance import fresh_start, clear_packages, clear_thumbnails, advanced_settings, splash, skin_override, skin_override_disable
from .whitelist import add_whitelist, remove_whitelist
from .addons_enable import force_update
from .addonvar import setting, setting_set, addon, addon_name, addon_icon, gui_save_default, gui_save_user, skin_gui, mdb_api_chk, mdblist, skin_chk, chk_splash, chk_skin_override, advancedsettings_xml, advancedsettings_blank, UPDATE_VERSION, BUILD_URL, BUILD_NAME
from .save_data import restore_gui, restore_skin, backup_gui_skin
from .backup_restore import backup_build, restore_menu, restore_build, get_backup_folder, reset_backup_folder
from .focus_settings import tmdbh_mdblist_api, rurl_settings_rd, rurl_settings_pm, rurl_settings_ad, rurl_settings_oc, rurl_settings_tb, am_accounts, am_manage, am_backup_restore
           
try:
    HANDLE = int(sys.argv[1])
except IndexError:
    HANDLE = 0

def router(paramstring):
    p = Params(paramstring)
    xbmc.log(str(p.get_params()), xbmc.LOGDEBUG)
    
    name = p.get_name()
    name2 = p.get_name2()
    version = p.get_version()
    url = p.get_url()
    mode = p.get_mode()
    icon = p.get_icon()
    description = p.get_description()
    
    xbmcplugin.setContent(HANDLE, 'files')

    if mode is None:
        main_menu()
    
    elif mode == 1:
        build_menu()
    
    elif mode == 2:
        play_video(name, url, icon, description)
    
    elif mode == 3:
        build_install(name, name2, version, url)
    
    elif mode == 4:
        fresh_start(standalone=True)
    
    elif mode == 5:
        submenu_maintenance()
    
    elif mode == 6:
        clear_packages()
        xbmc.executebuiltin('Container.Refresh()')
    
    elif mode == 7:
        clear_thumbnails()
        xbmc.executebuiltin('Container.Refresh()')
    
    elif mode == 8:
        advanced_settings()
    
    elif mode == 9:
        addon.openSettings()
        xbmc.executebuiltin('Container.Refresh()')
    
    elif mode == 10:
        authorize_menu()
    
    elif mode == 11:
        add_whitelist()
    
    elif mode == 12:
        backup_restore()
    
    elif mode == 13:
        backup_build()
    
    elif mode == 14:
        restore_menu()
    
    elif mode == 15:
        restore_build(url)
    
    elif mode == 16:
        get_backup_folder()
    
    elif mode == 17:
        reset_backup_folder()
    
    elif mode == 18:
        os._exit(1)

    elif mode == 19:
        restore_gui_skin()

    elif mode == 20:
        restore_gui(gui_save_default)

    elif mode == 21:
        restore_skin(gui_save_default)

    elif mode == 22:
        backup_gui_skin(gui_save_user)
        xbmcgui.Dialog().notification(addon_name, 'Backup Complete!', addon_icon, 3000)

    elif mode == 23:
        restore_gui(gui_save_user)
        
    elif mode == 24:
        restore_skin(gui_save_user)
    
    elif mode == 25:
        xbmc.executebuiltin(url)
    
    elif mode == 26:
        from .quick_log import upload_logfile
        upload_logfile()
    
    elif mode == 27:
        authorize_submenu(name2, icon)
    
    elif mode == 28:
        from .speedtester.addon import run
        run()

    elif mode == 29:
        if chk_splash == None or chk_splash == 'true':
            ask = xbmcgui.Dialog().yesno(addon_name, 'Are you sure?', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
            if ask:
                splash('false') # Splash Disabled
                xbmc.executebuiltin('Container.Refresh()')
                xbmcgui.Dialog().notification(addon_name, 'Kodi Splash Screen Disabled!', addon_icon, 3000)
                xbmc.sleep(4000)
            else:
                quit()
        if chk_splash == 'false':
            ask = xbmcgui.Dialog().yesno(addon_name, 'Are you sure?', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
            if ask:
                splash('true') # Splash Enabled
                xbmc.executebuiltin('Container.Refresh()')
                xbmcgui.Dialog().notification(addon_name, 'Kodi Splash Screen Enabled!', addon_icon, 3000)
                xbmc.sleep(4000)
            else:
                quit()

    elif mode == 30:
        if chk_skin_override():
            if str(skin_gui) == 'skin.estuary':
                xbmcgui.Dialog().ok(addon_name, '[COLOR gold]You\'re already using the default Estuary skin![CR][CR]Skin protection cannot be enabled. Please install a build and then enable skin protection![/COLOR]')
                quit()
            elif setting('skin_protection') == 'true':
                xbmcgui.Dialog().ok(addon_name, 'Skin protection is already enabled!')
                quit()
            else:
                ask = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Are you sure?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                if ask:
                    if not xbmcvfs.exists(advancedsettings_xml):
                        #If advancedsettings.xml does not exist copy blank file
                        shutil.copyfile(advancedsettings_blank, advancedsettings_xml)
                    else:
                        skin_override(skin_gui, advancedsettings_xml)
                        setting_set('skin_protection', 'true')
                        setting_set('saveadvanced', 'true')
                        xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Skin Protection Enabled![/COLOR]', addon_icon, 1000)
                        xbmcgui.Dialog().ok(addon_name, '[COLOR gold]To save your changes you now need to force close Kodi. Click OK to force close Kodi![/COLOR]')
                        os._exit(1)
        else: 
            ask = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Are you sure?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
            if ask:
                skin_override_disable()
                setting_set('skin_protection', 'false')
                xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Skin Protection Disabled![/COLOR]', addon_icon, 1000)
                xbmcgui.Dialog().ok(addon_name, '[COLOR gold]To save your changes you now need to force close Kodi. Click OK to force close Kodi![/COLOR]')
                os._exit(1)

    elif mode == 31:
        clear_packages()
        xbmc.sleep(1000)
        clear_thumbnails()
        xbmc.executebuiltin('Container.Refresh()')

    elif mode == 32:
        force_update()
        xbmc.executebuiltin('Container.Refresh()')
        xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Checking for Add-on Updates![/COLOR]', addon_icon, 3000)

    elif mode == 33:
        remove_whitelist()

    elif mode == 34:
        if notify_url in ('http://CHANGEME', 'http://slamiousproject.com/wzrd/notify19.txt', ''):
            xbmcgui.Dialog().notification(addon_name, 'No Notifications to Display!!', addon_icon, 3000)
            sys.exit()
        from . import notify
        message = notify.get_notify()[1]
        notify.notification(message)

    elif mode == 35:
        if changelog_dir in ('http://CHANGEME', ''):
            xbmcgui.Dialog().notification(addon_name, 'No Changelog to Display!!', addon_icon, 3000)
            sys.exit()
        from . import notify
        message = notify.get_changelog()
        notify.notification_clog(message)

    elif mode == 36:
        if not xbmcaddon.Addon("plugin.program.theredwizard").getSetting("mdb.api.key"):
            ask = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to add your MDBList API Key to The Red Wizard?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
            if ask:
                dialog = xbmcgui.Dialog()
                data = dialog.input('[COLOR gold]Enter your MDBList API Key[/COLOR]', type=xbmcgui.INPUT_ALPHANUM)
                if data:
                    setting_set('mdb.api.key', data)
                    xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Applied to The Red Wizard!![/COLOR]', addon_icon, 3000)
                    xbmc.sleep(3000)
                    mdblist()
        else:
            mdblist()

    elif mode == 37:
        if xbmcvfs.exists(addonvar.chk_fentastic) and xbmcvfs.exists(addonvar.chkset_fentastic) and skin_chk == 'skin.fentastic':
            skin = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to remove your MDBList API Key from FENtastic?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
            if skin:
                xbmc.executebuiltin("Skin.Reset(mdblist_api_key)")
                xbmc.executebuiltin("Container.Refresh")
                xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Removed!![/COLOR]', addon_icon, 3000)
                wiz = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you also like to remove your MDBList API Key from The Red Wizard?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                if wiz:
                    setting_set('mdb.api.key', '')
                    xbmc.executebuiltin("Container.Refresh")
                    xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Removed!![/COLOR]', addon_icon, 3000)
            
        if xbmcvfs.exists(addonvar.chk_nimbus) and xbmcvfs.exists(addonvar.chkset_nimbus) and skin_chk == 'skin.nimbus':
            skin = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to remove your MDBList API Key from Nimbus?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
            if skin:
                xbmc.executebuiltin("Skin.Reset(mdblist_api_key)")
                xbmc.executebuiltin("Container.Refresh")
                xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Removed!![/COLOR]', addon_icon, 3000)
                wiz = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you also like to remove your MDBList API Key from The Red Wizard?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                if wiz:
                    setting_set('mdb.api.key', '')
                    xbmc.executebuiltin("Container.Refresh")
                    xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Removed!![/COLOR]', addon_icon, 3000)
            
        if xbmcvfs.exists(addonvar.chk_altus) and xbmcvfs.exists(addonvar.chkset_altus) and skin_chk == 'skin.altus':
            skin = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to remove your MDBList API Key from FENtastic?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
            if skin:
                xbmc.executebuiltin("Skin.Reset(mdblist_api_key)")
                xbmc.executebuiltin("Container.Refresh")
                xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Removed!![/COLOR]', addon_icon, 3000)
                wiz = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you also like to remove your MDBList API Key from The Red Wizard?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                if wiz:
                    setting_set('mdb.api.key', '')
                    xbmc.executebuiltin("Container.Refresh")
                    xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Removed!![/COLOR]', addon_icon, 3000)
                    
    elif mode == 38:
        if xbmc.getCondVisibility('System.HasAddon(script.module.acctmgr)'):
            xbmc.executebuiltin('RunScript(script.module.acctmgr)')
        else:
            xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Account Manager Lite is not installed.[/COLOR]', addon_icon, 3000)

    elif mode == 39:
        submenu_tools()

    elif mode == 40:
        from .play_video import video_menu
        video_menu()

    elif mode == 41:
        name = BUILD_NAME
        name2 = name
        if BUILD_URL.startswith('https://www.dropbox.com'):
           url = BUILD_URL.replace('dl=0', 'dl=1')
        else:
            url = BUILD_URL
        build_install(name, name2, UPDATE_VERSION, url)

    elif mode == 42:
        submenu_whitelist()

    elif mode == 43:
        debrid_trakt_menu()

    elif mode == 44:
        from .quick_log import log_viewer
        log_viewer()


#############################################################
#######################SHORTCUTS#############################
#############################################################


####Focus Add-on settings###
    elif mode == 50:
        tmdbh_mdblist_api()
    #ResolveURL
    elif mode == 51:
        rurl_settings_rd()
    elif mode == 52:
        rurl_settings_pm()
    elif mode == 53:
        rurl_settings_ad()
    elif mode == 54:
        rurl_settings_oc()
    elif mode == 55:
        rurl_settings_tb()
    # Account Manager
    elif mode == 62:
        am_accounts()
    elif mode == 63:
        am_manage()
    elif mode == 64:
        am_backup_restore()
    elif mode == 65:
        xbmc.executebuiltin('ActivateWindowAndFocus(skinsettings,9000,0,648,6480), True') #Logging

        
    #Video Cache Settings
    elif mode == 75:
        xbmc.executebuiltin('ActivateWindowAndFocus(servicesettings,9001,0,-194,0), True') #Video Caching

    #Player Settings
    elif mode == 76:
        xbmc.executebuiltin('ActivateWindowAndFocus(playersettings,9001,0,-196,-179), True') #Audio & Subtitle Language
    elif mode == 77:
        xbmc.executebuiltin('ActivateWindowAndFocus(playersettings,9001,0,-196,-175), True') #Subtitle Language
    elif mode == 78:
        xbmc.executebuiltin('ActivateWindowAndFocus(playersettings,9001,0,-195,-175), True') #Subtitles

    #PVR Settings
    elif mode == 80:
        xbmc.executebuiltin('ActivateWindowAndFocus(pvrsettings,9001,-200,-174,0), True') #PVR Clear Data
    elif mode == 81:
        xbmc.executebuiltin('ActivateWindowAndFocus(pvrsettings,9001,0,-199,-173), True') #PVR Group Manager

    #Look & Feel Settings
    elif mode == 83:
        xbmc.executebuiltin('ActivateWindowAndFocus(appearancesettings,9001,-200,-179,0), True') #Change Skin
    elif mode == 84:
        xbmc.executebuiltin('ActivateWindowAndFocus(appearancesettings,9001,-200,-178,0), True') #Configure Skin
    elif mode == 85:
        xbmc.executebuiltin('ActivateWindowAndFocus(appearancesettings,9001,-200,-176,0), True') #Colors
    elif mode == 86:
        xbmc.executebuiltin('ActivateWindowAndFocus(appearancesettings,9001,-200,-175,0), True') #Fonts
    elif mode == 87:
        xbmc.executebuiltin('ActivateWindowAndFocus(appearancesettings,9001,0,-199,0), True') #Regional Settings

    #System Settings
    elif mode == 90:
        xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings,9001,0,-195,-177), True') #Manage Dependencies
    elif mode == 91:
        xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings,9001,0,-195,-174), True') #Unknown Sources
    elif mode == 92:
        xbmc.executebuiltin('ActivateWindowAndFocus(systemsettings,9001,0,-194,0), True') #Logging

    #System Information
    elif mode == 95:
        xbmc.executebuiltin('ActivateWindowAndFocus(systeminfo,9000,0,95,0), True') #System Summary
    elif mode == 96:
        xbmc.executebuiltin('ActivateWindowAndFocus(systeminfo,9000,0,94,0), True') #Storage
    elif mode == 97:
        xbmc.executebuiltin('ActivateWindowAndFocus(systeminfo,9000,0,96,0), True') #Network
    elif mode == 98:
        xbmc.executebuiltin('ActivateWindowAndFocus(systeminfo,9000,0,97,0), True') #Video
    elif mode == 99:
        xbmc.executebuiltin('ActivateWindowAndFocus(systeminfo,9000,0,98,0), True') #Hardware

    #Kodi Settings
    elif mode == 105:
        xbmc.executebuiltin('ActivateWindow(filemanager)') #File Manager
    elif mode == 106:
        xbmc.executebuiltin('ActivateWindow(addonbrowser)') #Addon Browser
    elif mode == 107:
        xbmc.executebuiltin('ActivateWindow(systeminfo)') #System Info
    elif mode == 108:
        xbmc.executebuiltin('ActivateWindow(eventlog)') #Event Log
    elif mode == 109:
        xbmc.executebuiltin('ActivateWindow(playersettings)') #Player Settings
    elif mode == 110:
        xbmc.executebuiltin('ActivateWindow(mediasettings)') #Media Settings
    elif mode == 111:
        xbmc.executebuiltin('ActivateWindow(pvrsettings)') #PVR Settings
    elif mode == 112:
        xbmc.executebuiltin('ActivateWindow(servicesettings)') #Service Settings
    elif mode == 113:
        xbmc.executebuiltin('ActivateWindow(appearancesettings)') #Appearance Settings
    elif mode == 114:
        xbmc.executebuiltin('ActivateWindow(systemsettings)') #System Settings

    #Kodi Builtins
    elif mode == 120:
        xbmc.executebuiltin('ReloadSkin()') #Reload Skin
    elif mode == 121:
        xbmc.executebuiltin('ActivateScreensaver') #Activate Screen Saver
    elif mode == 122:
        xbmc.executebuiltin('CleanLibrary(video)') #Clean Library
    elif mode == 123:
        xbmc.executebuiltin('UpdateLibrary(video)') #Update Library
    elif mode == 124:
        xbmc.executebuiltin('Reboot') #Reboot
    elif mode == 125:
        xbmc.executebuiltin('Quit') #Quit Kodi
    elif mode == 126:
        xbmc.executebuiltin('Powerdown') #Power Down
    elif mode == 127:
        xbmc.executebuiltin('Reboot') #Reboot
    elif mode == 128:
        xbmc.executebuiltin('ShutDown') #Shutdown
    elif mode == 129:
        xbmc.executebuiltin('Hibernate') #Hibernate
    elif mode == 130:
        xbmc.executebuiltin('Suspend') #Suspend

    #Addon Browser
    elif mode == 135:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/all")') #All Add-ons
    elif mode == 136:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/xbmc.addon.repository")') #Add-on Repositories
    elif mode == 137:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/kodi.audioencoder")') #Audio Encoders
    elif mode == 138:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/category.gameaddons")') #Games Add-ons
    elif mode == 139:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/category.infoproviders")') #Information Providers
    elif mode == 140:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/category.lookandfeel")') #Look & Feel
    elif mode == 141:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/kodi.peripheral")') #Peripherals
    elif mode == 142:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/xbmc.service")') #Services
    elif mode == 143:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/xbmc.addon.video")') #Video Add-ons
    elif mode == 144:
        xbmc.executebuiltin('ActivateWindow(10040,"addons://user/xbmc.webinterface")') #Web Interface Add-ons

        
    #Kodi Settings Menu Shortcuts    
    elif mode == 150:
        kodi_settings()

    #Kodi Specific Shortcuts    
    elif mode == 151:
        kodi_specific()

    #Kodi Builtins Shortcuts    
    elif mode == 152:
        kodi_builtins()
        
    #Add-on Specific Shortcuts    
    elif mode == 153:
        addon_specific()

    #Add-on Browser Shortcuts    
    elif mode == 154:
        addonbrowser()


    xbmcplugin.endOfDirectory(HANDLE)
