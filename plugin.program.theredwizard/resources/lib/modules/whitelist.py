import json
import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui
import re
import os
from itertools import count
from uservar import excludes
from .addonvar import addon_id, addon_name, addon_icon, textures_db

translatePath = xbmcvfs.translatePath
addon_id = xbmcaddon.Addon().getAddonInfo('id')
addon = xbmcaddon.Addon(addon_id)
addoninfo  = addon.getAddonInfo
addon_data  = translatePath(addon.getAddonInfo('profile'))
addons_path = translatePath(translatePath('special://home/addons'))
file_path = addon_data + 'whitelist.json'
dialog = xbmcgui.Dialog()

EXCLUDES_BASIC = excludes + [addon_id, textures_db, 'kodi.log', 'Addons33.db', 'packages', 'backups']
EXCLUDES_FRESH = [addon_id, textures_db, 'Addons33.db', 'kodi.log', 'plugin.program.theredwizard', 'repository.redwizard']

def strip_kodi_colors(text):
    if not text:
        return text
    return re.sub(r'\[\/?color[^\]]*\]', '', text, flags=re.IGNORECASE).strip()

def addon_xml_path(addon_folder):
    return os.path.join(addons_path, addon_folder, 'addon.xml')

def name_from_addon_xml(addon_folder):
    xml_path = addon_xml_path(addon_folder)
    if not xbmcvfs.exists(xml_path):
        return None
    try:
        with open(xml_path, 'r', encoding='utf-8', errors='ignore') as xml_file:
            text = xml_file.read(8192)
        match = re.search(r'<addon[^>]*\bname=["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            return strip_kodi_colors(match.group(1))
    except Exception:
        pass
    return None

def get_addon_name(addon_folder):
    try:
        return strip_kodi_colors(xbmcaddon.Addon(addon_folder).getAddonInfo('name'))
    except Exception:
        pass
    try:
        query = json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'Addons.GetAddonDetails',
            'params': {'addonid': addon_folder, 'properties': ['name']}
        })
        name = json.loads(xbmc.executeJSONRPC(query)).get('result', {}).get('addon', {}).get('name')
        if name:
            return strip_kodi_colors(name)
    except Exception:
        pass
    xml_name = name_from_addon_xml(addon_folder)
    if xml_name:
        return xml_name
    return addon_folder

def add_whitelist():
    dirs, files = xbmcvfs.listdir(addons_path)
    dirs.sort()
    for x in ['packages', 'temp']:
        if x in dirs:
            dirs.remove(x)
    current_whitelist = []
    if xbmcvfs.exists(file_path):
        with open(file_path, 'r') as wl:
            current_whitelist = json.load(wl)['whitelist']
    xbmc.log('dirs = ' + str(dirs), xbmc.LOGINFO)
    names = []
    available = []
    for x in list(current_whitelist):
        if x not in dirs:
            current_whitelist.remove(x)
        else:
            dirs.remove(x)
    for foldername in dirs:
        if not xbmcvfs.exists(addon_xml_path(foldername)):
            continue
        available.append(foldername)
        names.append(get_addon_name(foldername))
    dirs = available
    if not names:
        xbmcgui.Dialog().notification(addon_name, 'No items available to add!', addon_icon, 3000)
        quit()
    ret = xbmcgui.Dialog().multiselect('Select Items to Add to Your Whitelist', names, preselect=[])
    xbmc.log('ret = ' + str(ret), xbmc.LOGINFO)
    if ret is None:
        return None
    whitelist = []
    for x in range(len(dirs)):
        if x in ret:
            whitelist.append(dirs[x])
    xbmc.log('whitelist = ' + str(whitelist), xbmc.LOGINFO)
    if not xbmcvfs.exists(addon_data):
        xbmcvfs.mkdir(addon_data)
    new_list = current_whitelist + whitelist
    with open(file_path, 'w') as whitelist_file:
        json.dump({'whitelist': new_list}, whitelist_file, indent = 4)
        xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Whitelist Updated![/COLOR]', addon_icon, 3000)

def remove_whitelist():
    dirs, files = xbmcvfs.listdir(addons_path)
    dirs.sort()
    for y in ['packages', 'temp']:
        if y in dirs:
            dirs.remove(y)
    current_whitelist = []
    if xbmcvfs.exists(file_path):
        with open(file_path, 'r') as wl:
            current_whitelist = json.load(wl)['whitelist']
    names = []
    for y in list(current_whitelist):
        if y not in dirs:
            current_whitelist.remove(y)
        else:
            names.append(get_addon_name(y))
    if not names:
        xbmcgui.Dialog().notification(addon_name, '[COLOR gold]No items available to remove![/COLOR]', addon_icon, 3000)
        try:
            os.unlink(os.path.join(file_path))
        except Exception as e:
            xbmc.log('Failed to delete %s. Reason: %s' % (os.path.join(file_path), e), xbmc.LOGINFO)
        quit()
    ret = xbmcgui.Dialog().multiselect('Select Items to Remove From Your Whitelist', names, preselect=[])
    xbmc.log('ret = ' + str(ret), xbmc.LOGINFO)
    if ret is None:
        return None
    whitelist = []
    for x in range(len(current_whitelist)):
        if x in ret:
            whitelist.append(current_whitelist[x])
    xbmc.log('whitelist = ' + str(whitelist), xbmc.LOGINFO)
    for x in whitelist:
        current_whitelist.remove(x)
    if not current_whitelist:
        try:
            os.unlink(os.path.join(file_path))
        except Exception as e:
            xbmc.log('Failed to delete %s. Reason: %s' % (os.path.join(file_path), e), xbmc.LOGINFO)
        xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Whitelist Updated![/COLOR]', addon_icon, 3000)
    else:
        with open(file_path, 'w') as whitelist_file:
            json.dump({'whitelist': current_whitelist}, whitelist_file, indent = 4)
            xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Whitelist Updated![/COLOR]', addon_icon, 3000)
            
'''def view_whitelist():
    if xbmcvfs.exists(file_path):
        with open(file_path, 'r') as wl:
            current_whitelist = json.load(wl)['whitelist']
            whitelist = []
            key = None
            for key in current_whitelist:
                name = xbmcaddon.Addon(key).getAddonInfo('name')
                whitelist.append(name)
                a = str(whitelist)
                b = a.replace("[", "\n       >>>  ", 1)
                #button_number_count = 2;
                #counter = count(button_number_count)
                #c = re.sub(r',', lambda x: x.group(0) + str(next(counter)), b)
                c = "".join(re.split("\[|\]", b)[::2])
                replacements = {"]": "", "'": "", ",": "\n       >>> "}
                for old, new in replacements.items():
                    c = c.replace(old, new)
                    cleanlist = c
            return cleanlist
your_whitelist = view_whitelist()'''
        
def read_whitelist(_excludes):
    if xbmcvfs.exists(file_path):
        with open(file_path, 'r') as wl:
            whitelist  = json.loads(wl.read())['whitelist']
        for x in whitelist:
            if not x in _excludes:
                _excludes.append(x)
        return _excludes
    else:
        return _excludes
EXCLUDES_INSTALL = read_whitelist(EXCLUDES_BASIC)
