import json
from os import path
import sys
import xbmcaddon
import xbmcplugin
from .addonvar import texts_path, addon_icon, addon_fanart
from .utils import add_dir
from .colors import colors

COLOR1 = colors.color_text1
COLOR2 = colors.color_text2

AUTH_FILE = path.join(texts_path, 'authorize.json')
HANDLE = int(sys.argv[1])

def open_file(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def _load_auth():
    try:
        data = json.loads(open_file(AUTH_FILE))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"supported_addons": []}

def _is_installed(addon_id):
    try:
        xbmcaddon.Addon(addon_id)
        return True
    except Exception:
        return False

def authorize_menu():
    xbmcplugin.setPluginCategory(HANDLE, COLOR1('Authorise Debrid and Meta Accounts'))
    data = _load_auth()
    addons = [addon for addon in data.get('supported_addons', []) if addon.get('id') and _is_installed(addon.get('id'))]
    addons.sort(key=lambda addon: addon.get('name', addon.get('id', '')).lower())

    add_dir(COLOR1('<><> [B]Authorise Debrid and Meta Accounts[/B] <><>'), '', '', addon_icon, addon_fanart, COLOR1('Authorise Debrid and Meta Accounts'), isFolder=False)
    for addon in addons:
        name = addon.get('name', addon.get('id'))
        add_dir(COLOR2(name), '', 27, addon_icon, addon_fanart, COLOR2(name), name2=addon.get('id'))

def authorize_submenu(name, icon):
    data = _load_auth()
    target = None
    for addon in data.get('supported_addons', []):
        if addon.get('id') == name:
            target = addon
            break
    if not target:
        return

    xbmcplugin.setPluginCategory(HANDLE, COLOR1(target.get('name', name)))
    META_SERVICES = {
        'mdblist', 'punchplay', 'simkl', 'tmdb', 'trakt', 'wetrakr',
    }
    DEBRID_SERVICES = {
        'alldebrid', 'debridlink', 'linksnappy', 'offcloud',
        'premiumize', 'realdebrid', 'torbox',
    }
    GROUP_HEADERS = (
        (0, 'Debrid Accounts'),
        (1, 'Meta Accounts'),
    )

    entries = []
    for service, actions in target.get('services', {}).items():
        if service in DEBRID_SERVICES:
            group = 0
        elif service in META_SERVICES:
            group = 1
        else:
            group = 2
        for action in actions:
            typ = action.get('type')
            value = action.get('value')
            label = action.get('label', 'Authorise')
            if not typ or not value:
                continue
            if typ == 'plugin':
                cmd = 'RunPlugin({})'.format(value)
            elif typ == 'builtin':
                cmd = value
            else:
                continue
            entries.append((group, label.lower(), label, cmd))
    entries.sort()

    show_headers = len({entry[0] for entry in entries}) > 1
    shown_groups = set()
    for group, _sort, label, cmd in entries:
        if show_headers and group not in shown_groups:
            shown_groups.add(group)
            for header_group, header in GROUP_HEADERS:
                if header_group == group:
                    add_dir(
                        COLOR1('<><> [B]{0}[/B] <><>'.format(header)),
                        '',
                        '',
                        addon_icon,
                        addon_fanart,
                        COLOR1(header),
                        isFolder=False
                    )
                    break
        add_dir(COLOR2(label), cmd, 25, icon or addon_icon, addon_fanart, COLOR2(label), isFolder=False)
