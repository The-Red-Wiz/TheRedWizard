import base64
import xbmc
import xbmcvfs
import xbmcaddon
import xbmcgui
import json
import os
import platform
from datetime import datetime
from xml.etree import ElementTree as ET
from uservar import buildfile, BUILDS
from urllib.request import Request, urlopen
from .parser import XmlParser, TextParser

addon_id = xbmcaddon.Addon().getAddonInfo('id')
addon           = xbmcaddon.Addon(addon_id)
addon_info      = addon.getAddonInfo
addon_version   = addon_info('version')
addon_name      = addon_info('name')
addon_icon      = addon_info("icon")
addon_fanart    = addon_info("fanart")
translatePath   = xbmcvfs.translatePath
addon_profile   = translatePath(addon_info('profile'))
addon_path      = translatePath(addon_info('path'))    
def setting(key):
    return xbmcaddon.Addon(addon_id).getSetting(key)
setting_true    = lambda x: bool(True if setting(str(x)) == "true" else False)
def setting_set(key, value):
    xbmcaddon.Addon(addon_id).setSetting(key, value)
local_string    = addon.getLocalizedString
CURRENT_BUILD   = setting('buildname')
CURRENT_VERSION = setting('buildversion')
BUILD_VERSION   = setting('buildversion')
home = translatePath('special://home/')
dialog = xbmcgui.Dialog()
dp = xbmcgui.DialogProgress()
xbmcPath=os.path.abspath(home)
addons_path = os.path.join(home, 'addons/')
user_path = os.path.join(home, 'userdata/')
data_path = os.path.join(user_path, 'addon_data/')
db_path = translatePath('special://database/')
addons_db = os.path.join(db_path, 'Addons33.db')
packages = os.path.join(addons_path, 'packages/')
zippath = os.path.join(packages, 'tempzip.zip')
resources = os.path.join(addon_path, 'resources/')
thumbnails = os.path.join(user_path, 'Thumbnails')
user_agent = 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.101 Safari/537.36'
headers = {'User-Agent': user_agent}
kodi_ver_ = str(xbmc.getInfoLabel("System.BuildVersion")[:2])
kodi_ver = str(xbmc.getInfoLabel("System.BuildVersion")[:4])
kodi_versions = ['K20', 'K21', 'K22']
build_ver = xbmc.getInfoLabel('System.BuildVersion')
build_date = xbmc.getInfoLabel('System.BuildDate')
sys_arch = platform.architecture()[0]
sleep = xbmc.sleep
notify_file = os.path.join(addon_profile,'notify.txt')
texts_path = os.path.join(resources, 'texts/')
authorize = texts_path + 'authorize.json'
installed_date = str(datetime.now())[:-7]

#Backup Path for User GUI/Skin Settings
gui_save_path = translatePath(setting('backupfolder'))

#GUI Settings
gui_file = os.path.join(user_path, 'guisettings.xml')
gui_temp_dir = os.path.join(packages, 'gui_temp/')
gui_temp_file = os.path.join(gui_temp_dir, 'guisettings.xml')
gui_save_default = os.path.join(user_path, 'gui_settings/')
gui_save_user = os.path.join(gui_save_path, 'gui_settings_user/')

#Advanced Settings
advancedsettings_blank = os.path.join(resources, 'advancedsettings/advancedsettings.xml')
advancedsettings_xml =  os.path.join(user_path, 'advancedsettings.xml')
advancedsettings_backup =  os.path.join(packages, 'advancedsettings.xml')

#MDblist Variables
mdblist_key = setting('mdb.api.key')
translatePath = xbmcvfs.translatePath
addons = translatePath('special://home/addons/')
addon_data = translatePath('special://profile/addon_data/')
chk_fentastic = addons + translatePath('skin.fentastic/')
chk_nimbus = addons + translatePath('skin.nimbus/')
chk_altus = addons + translatePath('skin.altus/')
chkset_fentastic = addon_data + translatePath('skin.fentastic/settings.xml')
chkset_nimbus = addon_data + translatePath('skin.nimbus/settings.xml')
chkset_altus = addon_data + translatePath('skin.altus/settings.xml')

def isBase64(s):
    try:
        if base64.b64encode(base64.b64decode(s)).decode('utf8') == s:
            return True
        else:
            return False
    except:
        return False

def currSkin():
    return xbmc.getSkinDir()

def percentage(part, whole):
    return 100 * float(part)/float(whole)

def get_latest_db(db_type: str) -> str:
    highest_number = -1
    highest_file = None
    for file in os.listdir(db_path):
        if file.startswith(db_type) and file.endswith('.db'):
            try:
                number = int(file[len(db_type):file.index('.db')])
                if number > highest_number:
                    highest_number = number
                    highest_file = file
            except ValueError:
                pass
    if highest_file is not None:
        return os.path.join(db_path, highest_file)

textures_db = get_latest_db('Textures')
addons_db = get_latest_db('Addons')

def file_check(bfile):
    if isBase64(bfile):
        return base64.b64decode(bfile).decode('utf8')
    return bfile

def get_page(url):
       req = Request(file_check(url), headers = headers)
       return urlopen(req).read().decode('utf-8')
                
def skin_chk():
    json_query = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Settings.GetSettingValue", "params":{"setting":"lookandfeel.skin"}, "id":1}')
    json_query = json.loads(json_query)
    skin = ''
    if 'result' in json_query and 'value' in json_query['result']:
            skin = json_query['result']['value']
    return skin
skin_chk = skin_chk()

def mdb_api_chk():
    if xbmcvfs.exists(chk_fentastic) and xbmcvfs.exists(chkset_fentastic) and skin_chk == 'skin.fentastic':
        your_mdb_api = xbmcaddon.Addon("plugin.program.theredwizard").getSetting("mdb.api.key")
        with open(chkset_fentastic) as f:
                if your_mdb_api != '' and your_mdb_api in f.read():
                    return True
    elif xbmcvfs.exists(chk_nimbus) and xbmcvfs.exists(chkset_nimbus) and skin_chk == 'skin.nimbus':
        your_mdb_api = xbmcaddon.Addon("plugin.program.theredwizard").getSetting("mdb.api.key")
        with open(chkset_nimbus) as f:
                if your_mdb_api != '' and your_mdb_api in f.read():
                    return True
    elif xbmcvfs.exists(chk_altus) and xbmcvfs.exists(chkset_altus) and skin_chk == 'skin.altus':
        your_mdb_api = xbmcaddon.Addon("plugin.program.theredwizard").getSetting("mdb.api.key")
        with open(chkset_altus) as f:
                if your_mdb_api != '' and your_mdb_api in f.read():
                    return True

def mdblist():
    if xbmcvfs.exists(chk_fentastic) and xbmcvfs.exists(chkset_fentastic) and skin_chk == 'skin.fentastic':
            your_mdb_api = xbmcaddon.Addon("plugin.program.theredwizard").getSetting("mdb.api.key")
            if mdb_api_chk == True:
                xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Already Applied to Skin!![/COLOR]', addon_icon, 3000)
            else:
                ask = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to apply your MDBList API Key to FENtastic?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                if ask:
                    xbmc.executebuiltin("Skin.SetString(mdblist_api_key, %s)" % your_mdb_api)
                    xbmc.executebuiltin("Container.Refresh")
                    xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Applied to FENtastic!![/COLOR]', addon_icon, 3000)
                
    if xbmcvfs.exists(chk_nimbus) and xbmcvfs.exists(chkset_nimbus) and skin_chk == 'skin.nimbus':
            your_mdb_api = xbmcaddon.Addon("plugin.program.theredwizard").getSetting("mdb.api.key")
            if mdb_api_chk == True:
                xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Already Applied to Skin!![/COLOR]', addon_icon, 3000)
            else:
                ask = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to apply your MDBList API Key to Nimbus?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                if ask:
                    xbmc.executebuiltin("Skin.SetString(mdblist_api_key, %s)" % your_mdb_api)
                    xbmc.executebuiltin("Container.Refresh")
                    xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Applied to Nimbus!![/COLOR]', addon_icon, 3000)

    if xbmcvfs.exists(chk_altus) and xbmcvfs.exists(chkset_altus) and skin_chk == 'skin.altus':
            your_mdb_api = xbmcaddon.Addon("plugin.program.theredwizard").getSetting("mdb.api.key")
            if mdb_api_chk == True:
                xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Already Applied to Skin!![/COLOR]', addon_icon, 3000)
            else:
                ask = xbmcgui.Dialog().yesno(addon_name, '[COLOR gold]Would you like to apply your MDBList API Key to Altus?[/COLOR]', yeslabel='Yes', nolabel='No', defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
                if ask:
                    xbmc.executebuiltin("Skin.SetString(mdblist_api_key, %s)" % your_mdb_api)
                    xbmc.executebuiltin("Container.Refresh")
                    xbmcgui.Dialog().notification(addon_name, '[COLOR gold]MDBList Key Applied to Altus Skin!![/COLOR]', addon_icon, 3000)
                
def splash_chk():
    if xbmcvfs.exists(advancedsettings_xml):
        tree = ET.parse(advancedsettings_xml) #Parse Advancedsettings.xml
        root = tree.getroot()
        for splash in root.iter('splash'): #Check if splash is enabled/disabled
                value = splash.text
                return value
chk_splash = splash_chk()

def chk_skin_override():
    if xbmcvfs.exists(advancedsettings_xml):
        tree = ET.parse(advancedsettings_xml) #Parse Advancedsettings.xml
        root = tree.getroot()
        if len(root.findall('lookandfeel')) == 0: #Check if skin settings exist
            return True
    else:
        return True
            
def get_skin_gui():
    #Get current skin name
    cur_skin = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Settings.GetSettingValue", "params":{"setting":"lookandfeel.skin"}, "id":1}')
    cur_skin = json.loads(cur_skin)
    skin = ''
    if 'result' in cur_skin and 'value' in cur_skin['result']:
            skin = cur_skin['result']['value']
            return skin
skin_gui = get_skin_gui()

def get_dir_size(dir_path):
    
    # Get the uncompressed size of a directory
    size = 0
    size_mb = 0
    for path, dirs, files in os.walk(dir_path):
        for name in dirs:
            if name in ['cache', 'temp']:
                pass
        for f in files:
            fp = os.path.join(path, f)
            try:
                size += os.path.getsize(fp)
            except OSError as e:
                xbmc.log(f'Error reading file while getting directory size - {e}', xbmc.LOGINFO)
    size_mb = f"{int(size) / float(1 << 20):.2f}"
    return size_mb

def build_size():
    if setting('buildname') not in ['ExampleLargeBuild1', 'ExampleLargeBuild2']:
        buildsize = get_dir_size(home)
    else:
        buildsize = 0
    return buildsize

#Kodi Maintenance Stats
packagesize = get_dir_size(packages)
thumbnailsize = get_dir_size(thumbnails)
cleanup = round(float(packagesize) + float(thumbnailsize), 2)
buildsize = build_size()

def count_builds():
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
           if not build.get('version'):
               pass
           else:
               if kodi_ver_ in build.get('kodi'):
                    current_list.append(build.get('name'))
                    name = len(current_list)
       return name
NUM_BUILDS = count_builds()

def get_old_build():
       key = None
       for key in BUILDS:
           if key['Old Build'] == CURRENT_BUILD:
               builds = key
               break
           else:
               builds = {'Old Build': "Old Build_1"}
       for key, value in builds.items():
           if key == 'Old Build':
               old_build = value
               break
       return old_build
OLD_BUILD = get_old_build()

def get_new_build():
       if CURRENT_BUILD == OLD_BUILD:
           key = None
           for key in BUILDS:
               if key['Old Build'] == CURRENT_BUILD:
                   builds = key
                   break
           for key, value in builds.items():
               if key == 'New Build':
                   new_build = value
                   break
           return new_build
NEW_BUILD = get_new_build()

def get_update_details():
    response = ''
    try:
       response = get_page(buildfile)
    except:
       name = None
       version = None
       url = None
    name = ''
    version = ''
    url = ''
    builds = []

    if '"builds"' in response or "'builds'" in response:
       builds = json.loads(response)['builds']
       
    elif '<version>' in response:
       xml = XmlParser(response)
       builds = xml.parse_builds()
       
    elif 'name="' in response:
       text = TextParser(response)
       builds = text.parse_builds()

    for build in builds:
       if build.get('name') == NEW_BUILD:
           name = str(build.get('name'))
           version = str(build.get('version'))
           url = (build.get('url', ''))
           break
       elif build.get('name') == CURRENT_BUILD:
           name = str(build.get('name'))
           version = str(build.get('version'))
           url = (build.get('url', ''))
           break
    return name, version, url
BUILD_NAME, UPDATE_VERSION, BUILD_URL = get_update_details()

def get_os():
    platforms = {
        'System.Platform.Windows': 'Windows',
        'System.Platform.Android': 'Android',
        'System.Platform.Linux': 'Linux',
        'System.Platform.OSX': 'macOS',
        'System.Platform.IOS': 'iOS'
    }
    for condition, name in platforms.items():
        if xbmc.getCondVisibility(condition):
            return name
    return 'Unknown'

def get_kodi_codename():
    try:
        major = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
        return {20: 'Nexus', 21: 'Omega', 22: 'Piers'}.get(major, 'Unknown')
    except Exception:
        return 'Unknown'

os_name = get_os()
code_name = get_kodi_codename()
