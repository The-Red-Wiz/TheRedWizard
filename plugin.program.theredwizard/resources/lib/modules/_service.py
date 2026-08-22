import json
import base64
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
from uservar import buildfile, notify_url, changelog_dir
from .maintenance import clear_packages_startup, skin_override
from .addonvar import setting, setting_set, addon_name, addon_icon, addon_id, addon_profile, isBase64, headers, dialog, local_string, addon_id, gui_save_default, kodi_ver_, get_page, UPDATE_VERSION, CURRENT_BUILD, CURRENT_VERSION, BUILD_URL, BUILD_NAME, OLD_BUILD
from .build_install import build_install #, restore_binary, binaries_path
from .addons_enable import enable_addons
from .save_data import backup_gui_skin
from .parser import XmlParser
from . import  addonvar
from . import utils
from . import  notify

translatePath = xbmcvfs.translatePath
file_path = translatePath(addon_profile + 'build_list.json')

class Startup:
    def check_updates(self):
           if CURRENT_BUILD == 'No Build Installed':
               nobuild = dialog.yesnocustom(
                   addon_name,
                   '[COLOR gold]There is currently no[/COLOR] [COLOR red]Red Wizard[/COLOR] [COLOR gold]build installed!\n\nWould you like to install one now?[/COLOR]',
                   'Remind Later'
               )
               if nobuild == 1:
                   xbmc.executebuiltin(
                       f'ActivateWindow(10001, "plugin://{addon_id}/?mode=1",return)'
                   )
               elif nobuild == 0:
                   setting_set('buildname', 'No Build')
               return
           name_changed = (
               CURRENT_BUILD == OLD_BUILD
               and BUILD_NAME
               and BUILD_NAME != CURRENT_BUILD
               and BUILD_URL not in ('', 'http://')
               and setting('update_passed') != 'true'
           )
           if UPDATE_VERSION is None:
               pass
           elif name_changed:
               update_available = xbmcgui.Dialog().yesnocustom(
                   addon_name,
                   f'[COLOR gold]Update available! Your build has a name change!\nCurrent Name:[/COLOR] [COLOR red][B]{CURRENT_BUILD}[/B][/COLOR]    [COLOR gold]New Name:[/COLOR] [COLOR red][B]{BUILD_NAME}[/B][/COLOR]\n{local_string(30049)} [COLOR red][B]{CURRENT_VERSION}[/B][/COLOR]    {local_string(30050)} [COLOR red][B]{UPDATE_VERSION}[/B][/COLOR]\n{local_string(30051)}',
                   yeslabel='Update Now', nolabel='Not Now', customlabel='Changelog', defaultbutton=xbmcgui.DLG_YESNO_CUSTOM_BTN
               )
               if update_available == 1:
                   name = BUILD_NAME
                   name2 = name
                   if BUILD_URL.startswith('https://www.dropbox.com'):
                       url = BUILD_URL.replace('dl=0', 'dl=1')
                   else:
                       url = BUILD_URL
                   build_install(name, name2, UPDATE_VERSION, url)
                       
               elif update_available == 0:
                   remind_later = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to be reminded later?[/COLOR]', yeslabel='Remind Later', nolabel='Ignore', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                   if remind_later:
                       setting_set('update_passed', 'false')
                   else:
                       setting_set('update_passed', 'true')
                   
               elif update_available == 2:
                   if changelog_dir in ('', 'http://', 'http://CHANGEME/'):
                       xbmcgui.Dialog().notification(addon_name, 'No Changelog to Display!!', addon_icon, 3000)
                       Startup().check_updates()
                   else:
                       message = notify.get_changelog()
                       notify.notification_clog(message)
           elif UPDATE_VERSION == CURRENT_VERSION and setting('notifybuild') == 'false':
               self.new_builds_notify()
           else:
               if UPDATE_VERSION > CURRENT_VERSION and setting('update_passed') != 'true':
                   update_available = xbmcgui.Dialog().yesnocustom(
                       addon_name,
                       f'[COLOR red]{local_string(30047)} {CURRENT_BUILD} {local_string(30048)}\n{local_string(30049)} {CURRENT_VERSION}\n{local_string(30050)} {UPDATE_VERSION}\n{local_string(30051)}[/COLOR]',
                       yeslabel='Update Now', nolabel='Not Now', customlabel='Changelog', defaultbutton=xbmcgui.DLG_YESNO_CUSTOM_BTN
                   )
                   
                   if update_available == 1:
                       name = CURRENT_BUILD
                       name2 = name
                       if BUILD_URL.startswith('https://www.dropbox.com'):
                          url = BUILD_URL.replace('dl=0', 'dl=1')
                       else:
                           url = BUILD_URL
                       build_install(name, name2, UPDATE_VERSION, url) 
                           
                   elif update_available == 0:
                       remind_later = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to be reminded later?[/COLOR]', yeslabel='Remind Later', nolabel='Ignore', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                       if remind_later:
                           setting_set('update_passed', 'false')
                       else:
                           setting_set('update_passed', 'true')
                       
                   elif update_available == 2:
                       if changelog_dir in ('', 'http://', 'http://CHANGEME/'):
                           xbmcgui.Dialog().notification(addon_name, 'No Changelog to Display!!', addon_icon, 3000)
                           Startup().check_updates()
                       else:
                           message = notify.get_changelog()
                           notify.notification_clog(message)
                       
               elif UPDATE_VERSION == CURRENT_VERSION and setting('update_passed') == 'true':
                   setting_set('update_passed', 'false')

    def new_builds_notify(self):
        response = ''
        try:
           response = get_page(buildfile)
        except:
           name = None
        name = ''
        current_list = []
        xml = XmlParser(response)
        builds = xml.parse_builds()
        for build in builds:
            if not build.get('version'):    #Skip separators
                pass
            elif kodi_ver_ in build.get('kodi'):  #Skip unsupported builds
                build_name = (build.get('name') or '').strip()
                if build_name:
                    current_list.append(build_name)
        if not xbmcvfs.exists(file_path) and current_list:  #Check if build_list.json exists and current list is not empty
            with open(file_path, 'w') as buildlist:
                json.dump({'builds': current_list}, buildlist, indent = 4)   #Write initial list of build names
        elif xbmcvfs.exists(file_path):
            with open(file_path, 'r') as archivedlist:
                archived_list = json.load(archivedlist)['builds']    #Read archived list
            if current_list == archived_list:  #Check if lists are identical
                return
            archived_names = set(archived_list)
            new_names = [n for n in dict.fromkeys(current_list) if n not in archived_names]
            if not new_names:  # Reorder or removals only — update quietly
                with open(file_path, 'w') as buildlist:
                    json.dump({'builds': current_list}, buildlist, indent = 4)
                return
            new_builds = '\n'.join(new_names)

            #Dialog to notify user
            notify = xbmcgui.Dialog().yesnocustom(addon_name, f'[COLOR gold]New build(s) available! Would you like to check them out?[/COLOR]\n\n[COLOR red][B]{new_builds}[/B][/COLOR]', yeslabel='Yes', nolabel='No', customlabel='Remind Later', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
            if notify == 1:     #Yes
                with open(file_path, 'w') as buildlist:
                    json.dump({'builds': current_list}, buildlist, indent = 4)   #Update archived list
                xbmc.executebuiltin("ActivateWindow(10001,plugin://%s/?mode=1,return)" % addon_id)  #Open build menu to view new builds
            elif notify == 0:   #No
                with open(file_path, 'w') as buildlist:
                    json.dump({'builds': current_list}, buildlist, indent = 4)   #Update archived list
            elif notify == 2:   #Remind Me Later
                return
                        
    def save_menu(self):
        choices = []
        preselect = []
        if setting('savedata') == 'true':
            choices.append('[I]Debrid and Meta Account Data[/I][TABS]5[/TABS][Preselected]')
            preselect.append(0)
        else:
            choices.append('Debrid and Meta Account Data')
        if setting('saveyoutube') == 'true':
            choices.append('[I]YouTube API Keys[/I][TABS]5[/TABS][Preselected]')
            preselect.append(1)
        else:
            choices.append('YouTube API Keys')
        if setting('saveadvanced') == 'true':
            choices.append('[I]Advanced Settings[/I][TABS]5[/TABS][Preselected]')
            preselect.append(2)
        else:
            choices.append('Advanced Settings')
        if setting('savegui') == 'true':
            choices.append('[I]GUI Settings[/I][TABS]6[/TABS][Preselected]')
            preselect.append(3)
        else:
            choices.append('GUI Settings')
        if setting('savefavs') == 'true':
            choices.append('[I]Favourites[/I][TABS]7[/TABS][Preselected]')
            preselect.append(4)
        else:
            choices.append('Favourites')
        if setting('savesources') == 'true':
            choices.append('[I]Sources[/I][TABS]7[/TABS][Preselected]')
            preselect.append(5)
        else:
            choices.append('Sources')
        save_select = dialog.multiselect(
            f'{addon_name} - {local_string(30052)}',
            choices,
            preselect=preselect
        )
        # Select Save Items
        if save_select is None:
            return
        save_items = [choices[index] for index in save_select]

        setting_set('savedata', 'true' if any('Debrid and Meta Account Data' in i for i in save_items) else 'false')
        setting_set('saveyoutube', 'true' if any('YouTube API Keys' in i for i in save_items) else 'false')
        setting_set('saveadvanced', 'true' if any('Advanced Settings' in i for i in save_items) else 'false')
        setting_set('savegui', 'true' if any('GUI Settings' in i for i in save_items) else 'false')
        setting_set('savefavs', 'true' if any('Favourites' in i for i in save_items) else 'false')
        setting_set('savesources', 'true' if any('Sources' in i for i in save_items) else 'false')

        setting_set('firstrunSave', 'true')
                        
    def notify_check(self):
        if notify_url in ('http://CHANGEME', 'http://slamiousproject.com/wzrd/notify19.txt', '', 'http://'):
            return
        info = notify.get_notify()
        current_notify = int(setting('notifyversion'))
        notify_version = info[0]
        message = info[1]
        if setting('firstrunNotify') != 'true' or notify_version > current_notify:
            notify.notification(message)
            setting_set('firstrunNotify', 'true')
            setting_set('notifyversion', str(notify_version))
    
    def run_startup(self):
        #if setting('firstrunSave') != 'true':
            #self.save_menu()
            #xbmc.sleep(2000)
        if setting('firstrun') == 'true':
            enable_addons()
            backup_gui_skin(gui_save_default)
            setting_set('firstrun', 'false')
        else:
            if setting('autoclearpackages') != '0':
                clear_packages_startup()
            xbmc.sleep(1000)
            self.notify_check()
            xbmc.sleep(3000)  # Delay Build Update Notification
            self.check_updates()
        #if binaries_path.exists():
            #restore_binary()
