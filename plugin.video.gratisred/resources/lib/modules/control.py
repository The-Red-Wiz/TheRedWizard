# -*- coding: utf-8 -*-

import os
import re
import sys
import traceback

import six
from six.moves import urllib_parse
from kodi_six import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs


def six_encode(txt, char='utf-8', errors='replace'):
    if six.PY2 and isinstance(txt, six.text_type):
        txt = txt.encode(char, errors=errors)
    return txt


def six_decode(txt, char='utf-8', errors='replace'):
    if six.PY3 and isinstance(txt, six.binary_type):
        txt = txt.decode(char, errors=errors)
    return txt


def getKodiVersion():
    return int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])


addon = xbmcaddon.Addon
addonInfo = xbmcaddon.Addon().getAddonInfo

lang = xbmcaddon.Addon().getLocalizedString
lang2 = xbmc.getLocalizedString

setting = xbmcaddon.Addon().getSetting
setSetting = xbmcaddon.Addon().setSetting

addItem = xbmcplugin.addDirectoryItem
addItems = xbmcplugin.addDirectoryItems

item = xbmcgui.ListItem
directory = xbmcplugin.endOfDirectory

content = xbmcplugin.setContent
property = xbmcplugin.setProperty

infoLabel = xbmc.getInfoLabel

condVisibility = xbmc.getCondVisibility

jsonrpc = xbmc.executeJSONRPC

dialog = xbmcgui.Dialog()
progressDialog = xbmcgui.DialogProgress()
progressDialogBG = xbmcgui.DialogProgressBG()
window = xbmcgui.Window(10000)
windowDialog = xbmcgui.WindowDialog()

button = xbmcgui.ControlButton

image = xbmcgui.ControlImage

getCurrentDialogId = xbmcgui.getCurrentWindowDialogId()
getCurrentWinId = xbmcgui.getCurrentWindowId()

keyboard = xbmc.Keyboard

monitor = xbmc.Monitor()

execute = xbmc.executebuiltin

skin = xbmc.getSkinDir()

player = xbmc.Player()
playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
resolve = xbmcplugin.setResolvedUrl
PROP_RESOLVE_DONE = 'plugin.video.gratisred.resolve_done'


def plugin_handle():
    try:
        return int(sys.argv[1])
    except Exception:
        return -1


def clear_resolve_state():
    try:
        window.clearProperty(PROP_RESOLVE_DONE)
    except Exception:
        pass


def mark_resolve_sent():
    try:
        window.setProperty(PROP_RESOLVE_DONE, 'true')
    except Exception:
        pass


def abort_plugin_resolve():
    # Kodi 22 widget / PlayMedia: exit without setResolvedUrl(True|False) leaves plugin://
    # "not playable" → "One or more items failed to play".
    try:
        if window.getProperty(PROP_RESOLVE_DONE) == 'true':
            return False
    except Exception:
        pass
    handle = plugin_handle()
    if handle <= 0:
        return False
    try:
        resolve(handle, False, item(offscreen=True))
        mark_resolve_sent()
        return True
    except Exception:
        try:
            resolve(handle, False, item())
            mark_resolve_sent()
            return True
        except Exception:
            return False


legalFilename = xbmc.makeLegalFilename if getKodiVersion() < 19 else xbmcvfs.makeLegalFilename

openFile = xbmcvfs.File
makeFile = xbmcvfs.mkdir
deleteFile = xbmcvfs.delete

deleteDir = xbmcvfs.rmdir
listDir = xbmcvfs.listdir

transPath = xbmc.translatePath if getKodiVersion() < 19 else xbmcvfs.translatePath
#transPath = xbmcvfs.translatePath if six.PY3 else xbmc.translatePath
addonPath = transPath(addonInfo('path'))
dataPath = transPath(addonInfo('profile'))
# Estuary WideList row icons use ListItem.Icon only for Container.Content() — not addons/files.
MENU_FOLDER_CONTENT = ''
skinPath = transPath('special://skin/')

cacheFile = os.path.join(dataPath, 'cache.db')
viewsFile = os.path.join(dataPath, 'views.db')
metacacheFile = os.path.join(dataPath, 'meta.db')
searchFile = os.path.join(dataPath, 'search.db')
libcacheFile = os.path.join(dataPath, 'library.db')
bookmarksFile = os.path.join(dataPath, 'bookmarks.db')
favoritesFile = os.path.join(dataPath, 'favorites.db')
progressFile = os.path.join(dataPath, 'progress.db')
providercacheFile = os.path.join(dataPath, 'providers.db')

settingsPath = os.path.join(addonPath, 'resources', 'settings.xml')
settingsFile = os.path.join(dataPath, 'settings.xml')

key = "RgUkXp2s5v8x/A?D(G+KbPeShVmYq3t6"
iv = "p2s5v8y/B?E(H+Mb"
integer = 1000

notifcations_disabled = setting('addon.notifcations')


def sleep(time):
    while time > 0 and not monitor.abortRequested():
        xbmc.sleep(min(100, time))
        time = time - 100


def set_list_item_art(item, icon, fanart=None, thumb=None):
    icon_img = icon or thumb
    art = {'icon': icon_img, 'thumb': thumb or icon_img}
    if fanart:
        art['fanart'] = fanart
    item.setArt(art)
    try:
        item.setIconImage(icon_img)
    except:
        pass


def menu_image(image, fallback='DefaultFolder.png'):
    if not image:
        return fallback
    if isinstance(image, str) and image.startswith('http'):
        return image
    art = artPath()
    if art and image and not os.path.isabs(image):
        return os.path.join(art, image)
    return image if image else fallback


def set_menu_item_art(item, image, fanart=None):
    icon_img = menu_image(image)
    fanart_img = fanart or addonFanart()
    art = {'icon': icon_img, 'thumb': icon_img, 'poster': icon_img, 'fanart': fanart_img}
    item.setArt(art)
    try:
        item.setIconImage(icon_img)
    except:
        pass


def addonId():
    return addonInfo('id')


def addonName():
    return addonInfo('name')


def appearance():
    appearance = setting('theme.1').lower() if condVisibility('System.HasAddon(script.gratisred.artwork)') else setting('theme.alt').lower()
    return appearance


def artPath():
    theme = appearance()
    if theme in ['-', '']:
        return
    elif condVisibility('System.HasAddon(script.gratisred.artwork)'):
        return os.path.join(xbmcaddon.Addon('script.gratisred.artwork').getAddonInfo('path'), 'resources', 'media', theme)


def artwork():
    execute('RunPlugin(plugin://script.gratisred.artwork)')


def addonIcon():
    theme = appearance()
    art = artPath()
    if not (art == None and theme in ['-', '']):
        return os.path.join(art, 'icon.png')
    return addonInfo('icon')


def addonThumb():
    theme = appearance()
    art = artPath()
    if not (art == None and theme in ['-', '']):
        return os.path.join(art, 'poster.png')
    elif theme == '-':
        return 'DefaultFolder.png'
    return addonInfo('icon')


def addonPoster():
    theme = appearance()
    art = artPath()
    if not (art == None and theme in ['-', '']):
        return os.path.join(art, 'poster.png')
    return 'DefaultVideo.png'


def addonBanner():
    theme = appearance()
    art = artPath()
    if not (art == None and theme in ['-', '']):
        return os.path.join(art, 'banner.png')
    return 'DefaultVideo.png'


def addonFanart():
    theme = appearance()
    art = artPath()
    if not (art == None and theme in ['-', '']):
        return os.path.join(art, 'fanart.jpg')
    return addonInfo('fanart')


def addonNext():
    theme = appearance()
    art = artPath()
    if not (art == None and theme in ['-', '']):
        return os.path.join(art, 'next.png')
    return 'DefaultVideo.png'


def getCurrentViewId():
    # Some Kodi builds do not expose a numeric Container.Viewmode.id label.
    # Fall back to the focused view control ID used by skin views (50/55/500/...).
    view_id = infoLabel('Container.Viewmode.id') or ''
    if view_id and view_id.isdigit():
        return str(view_id)
    try:
        win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        focus = str(win.getFocusId())
        if focus.isdigit() and int(focus) >= 50:
            return focus
    except:
        pass
    return ''


def moderator():
    try:
        white_list = [urllib_parse.urlparse(sys.argv[0]).netloc, '', 'plugin.video.metalliq', 'script.extendedinfo',
            'plugin.program.super.favourites', 'plugin.video.openmeta', 'plugin.video.themoviedb.helper'
        ]
        plugin_name = infoLabel('Container.PluginName')
        if not plugin_name in white_list:
            xbmc.log('Gratis Red Moderator Blockage: %s (Contact me with this line if you feel its a error.)' % plugin_name, xbmc.LOGWARNING)
            sys.exit()
    except Exception as error:
        xbmc.log('Gratis Red Moderator Failure: %s' % error, xbmc.LOGDEBUG)


def version():
    num = ''
    try:
        version = addon('xbmc.addon').getAddonInfo('version')
    except:
        version = '999'
    for i in version:
        if i.isdigit():
            num += i
        else:
            break
    return int(num)


def idle():
    if getKodiVersion() >= 18:
        return execute('Dialog.Close(busydialognocancel)')
    else:
        return execute('Dialog.Close(busydialog)')


def busy():
    if getKodiVersion() >= 18:
        return execute('ActivateWindow(busydialognocancel)')
    else:
        return execute('ActivateWindow(busydialog)')


def refresh():
    return execute('Container.Refresh')


def refresh_folder(folder=None):
    """Reload the open shelf after Manager remove — deferred, non-blocking.

    RunPlugin(-1) + Container.Refresh(wait=True) deadlocks (busy spinner).
    Container.Refresh(url) / Update(...,replace) collapse ParentPath so Back
    from page 2+ jumps to the addon root. Schedule a plain Container.Refresh
    after this plugin returns; exclusions drop the removed title on rebuild.
    """
    def _later():
        try:
            # Let RunPlugin(-1) finish before touching the container.
            xbmc.sleep(250)
            xbmc.executebuiltin('Container.Refresh')
        except Exception:
            pass
    try:
        from threading import Thread
        Thread(target=_later).start()
        return True
    except Exception:
        return execute('Container.Refresh')


def last_search_term(select):
    """Most recent term from search.db for this select table (movie/tvshow/...)."""
    try:
        from sqlite3 import dbapi2 as database
        dbcon = database.connect(searchFile)
        dbcur = dbcon.cursor()
        dbcur.execute("SELECT term FROM %s ORDER BY ID DESC LIMIT 1" % select)
        row = dbcur.fetchone()
        dbcur.close()
        return row[0] if row else None
    except Exception:
        return None


def folder_is_trakt_shelf(content, shelf):
    """True when Container.FolderPath is already the given My Trakt shelf."""
    try:
        from six.moves import urllib_parse
        folder_raw = urllib_parse.unquote(infoLabel('Container.FolderPath') or '')
        if addonInfo('id') not in folder_raw:
            return False
        url_key = {
            'watchlist': 'trakt_watchlist',
            'collection': 'trakt_collection',
            'favorites': 'trakt_favorites',
            'watchedlist': 'trakt_watchedlist',
            'history': 'trakt_history',
        }.get(shelf)
        if url_key and ('url=%s' % url_key) in folder_raw:
            return True
        media = 'movies' if content == 'movie' else 'shows'
        path_map = {
            'watchlist': '/users/me/watchlist/%s' % media,
            'collection': '/users/me/collection/%s' % media,
            'favorites': '/users/me/favorites/%s' % media,
            'watchedlist': '/users/me/watched/%s' % media,
            'history': '/users/me/history/%s' % media,
        }
        needle = path_map.get(shelf)
        return bool(needle and needle in folder_raw)
    except Exception:
        return False


def refresh_list():
    """Reload the current addon folder without rewriting history."""
    try:
        from six.moves import urllib_parse
        folder = infoLabel('Container.FolderPath') or ''
        if addonInfo('id') not in folder:
            return execute('Container.Refresh')
        if any(x in folder for x in (
            'action=add_item', 'action=play_item', 'action=play_', 'action=sources'
        )):
            return execute('Container.Refresh')
        # Typed Search without name=: reload results with the last term,
        # without replace so Search menu history stays intact.
        if 'searchterm' in folder and 'name=' not in folder:
            args = dict(urllib_parse.parse_qsl(folder.split('?', 1)[-1]))
            select = args.get('select') or ''
            action = args.get('action') or ''
            q = last_search_term(select) if select else None
            if not q or not action:
                return
            folder = '%s?action=%s&select=%s&name=%s' % (
                folder.split('?', 1)[0], action, select, urllib_parse.quote_plus(q)
            )
            execute('Container.Update(%s)' % folder)
            return
    except Exception:
        pass
    return execute('Container.Refresh')


def queueItem():
    return execute('Action(Queue)')


def yesnoDialog(message, heading=addonInfo('name'), nolabel='', yeslabel=''):
    if getKodiVersion() < 19:
        return dialog.yesno(heading, message, '', '', nolabel, yeslabel)
    else:
        return dialog.yesno(heading, message, nolabel, yeslabel)


def okDialog(message, heading=addonInfo('name')):
    return dialog.ok(heading, message)


def selectDialog(list, heading=addonInfo('name'), useDetails=False):
    if getKodiVersion() >= 17:
        return dialog.select(heading, list, useDetails=useDetails)
    else:
        return dialog.select(heading, list)


def multiselectDialog(list, heading=addonInfo('name'), useDetails=False):
    if getKodiVersion() >= 17:
        return dialog.multiselect(heading, list, useDetails=useDetails)
    else:
        return dialog.multiselect(heading, list)


def contextmenuDialog(list):
    return dialog.contextmenu(list)


def infoDialog(message, heading=addonInfo('name'), icon='', time=3000, sound=False):
    if notifcations_disabled == 'true':
        return
    if icon == '':
        icon = addonIcon()
    elif icon == 'INFO':
        icon = xbmcgui.NOTIFICATION_INFO
    elif icon == 'WARNING':
        icon = xbmcgui.NOTIFICATION_WARNING
    elif icon == 'ERROR':
        icon = xbmcgui.NOTIFICATION_ERROR
    dialog.notification(heading, message, icon, time, sound=sound)


def textViewer(file, heading=addonInfo('name'), monofont=True):
    sleep(200)
    if not os.path.exists(file):
        w = open(file, 'w')
        w.close()
    with open(file, 'rb') as r:
        text = r.read()
    if not text:
        text = ' '
    head = '[COLOR red][B]%s[/B][/COLOR]' % six.ensure_str(heading, errors='replace')
    if getKodiVersion() >= 18:
        return dialog.textviewer(head, text, monofont)
    else:
        return dialog.textviewer(head, text)


def textViewer2(text, heading=addonInfo('name'), monofont=True):
    sleep(200)
    if not text:
        text = 'Error, Something Went Wrong.'
    head = '[COLOR red][B]%s[/B][/COLOR]' % six.ensure_str(heading, errors='replace')
    if getKodiVersion() >= 18:
        return dialog.textviewer(head, text, monofont)
    else:
        return dialog.textviewer(head, text)


def metadataClean(metadata):
    if metadata == None:
        return metadata
    allowed = ['aired', 'album', 'artist', 'cast',
        'castandrole', 'code', 'country', 'credits', 'dateadded', 'dbid', 'director',
        'duration', 'episode', 'episodeguide', 'genre', 'imdbnumber', 'lastplayed',
        'mediatype', 'mpaa', 'originaltitle', 'overlay', 'path', 'playcount', 'plot',
        'plotoutline', 'premiered', 'rating', 'season', 'set', 'setid', 'setoverview',
        'showlink', 'sortepisode', 'sortseason', 'sorttitle', 'status', 'studio', 'tag',
        'tagline', 'title', 'top250', 'totalepisodes', 'totalteasons', 'tracknumber',
        'trailer', 'tvshowtitle', 'userrating', 'votes', 'watched', 'writer', 'year'
    ]
    return {k: v for k, v in six.iteritems(metadata) if k in allowed}


def apiLanguage(ret_name=None):
    langDict = {'Bulgarian': 'bg', 'Chinese': 'zh', 'Croatian': 'hr', 'Czech': 'cs',
        'Danish': 'da', 'Dutch': 'nl', 'English': 'en', 'Finnish': 'fi', 'French': 'fr',
        'German': 'de', 'Greek': 'el', 'Hebrew': 'he', 'Hungarian': 'hu', 'Italian': 'it',
        'Japanese': 'ja', 'Korean': 'ko', 'Norwegian': 'no', 'Polish': 'pl', 'Portuguese': 'pt',
        'Romanian': 'ro', 'Russian': 'ru', 'Serbian': 'sr', 'Slovak': 'sk', 'Slovenian': 'sl',
        'Spanish': 'es', 'Swedish': 'sv', 'Thai': 'th', 'Turkish': 'tr', 'Ukrainian': 'uk'
    }
    trakt = ['bg', 'cs', 'da', 'de', 'el', 'en', 'es', 'fi', 'fr', 'he', 'hr', 'hu', 'it', 'ja',
        'ko', 'nl', 'no', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl', 'sr', 'sv', 'th', 'tr', 'uk', 'zh'
    ]
    tvdb = ['cs', 'da', 'de', 'el', 'en', 'es', 'fi', 'fr', 'he', 'hr', 'hu', 'it', 'ja',
        'ko', 'nl', 'no', 'pl', 'pt', 'ru', 'sl', 'sv', 'tr', 'zh'
    ]
    youtube = ['aa', 'ab', 'ae', 'af', 'ak', 'am', 'an', 'ar', 'as', 'av', 'ay', 'az', 'ba',
        'be', 'bg', 'bh', 'bi', 'bm', 'bn', 'bo', 'br', 'bs', 'ca', 'ce', 'ch', 'co', 'cr',
        'cs', 'cu', 'cv', 'cy', 'da', 'de', 'dv', 'dz', 'ee', 'el', 'en', 'eo', 'es', 'et',
        'eu', 'fa', 'ff', 'fi', 'fj', 'fo', 'fr', 'fy', 'ga', 'gd', 'gl', 'gn', 'gu', 'gv',
        'ha', 'he', 'hi', 'ho', 'hr', 'ht', 'hu', 'hy', 'hz', 'ia', 'id', 'ie', 'ig', 'ii',
        'ik', 'io', 'is', 'it', 'iu', 'ja', 'jv', 'ka', 'kg', 'ki', 'kj', 'kk', 'kl', 'km',
        'kn', 'ko', 'kr', 'ks', 'ku', 'kv', 'kw', 'ky', 'la', 'lb', 'lg', 'li', 'ln', 'lo',
        'lt', 'lu', 'lv', 'mg', 'mh', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'my', 'na',
        'nb', 'nd', 'ne', 'ng', 'nl', 'nn', 'no', 'nr', 'nv', 'ny', 'oc', 'oj', 'om', 'or',
        'os', 'pa', 'pi', 'pl', 'ps', 'pt', 'qu', 'rm', 'rn', 'ro', 'ru', 'rw', 'sa', 'sc',
        'sd', 'se', 'sg', 'si', 'sk', 'sl', 'sm', 'sn', 'so', 'sq', 'sr', 'ss', 'st', 'su',
        'sv', 'sw', 'ta', 'te', 'tg', 'th', 'ti', 'tk', 'tl', 'tn', 'to', 'tr', 'ts', 'tt',
        'tw', 'ty', 'ug', 'uk', 'ur', 'uz', 've', 'vi', 'vo', 'wa', 'wo', 'xh', 'yi', 'yo',
        'za', 'zh', 'zu'
    ]
    tmdb = ['ar', 'be', 'bg', 'bn', 'ca', 'ch', 'cs', 'da', 'de', 'el', 'en', 'eo', 'es', 'et',
        'eu', 'fa', 'fi', 'fr', 'gl', 'he', 'hi', 'hu', 'id', 'it', 'ja', 'ka', 'kk', 'kn',
        'ko', 'lt', 'lv', 'ml', 'ms', 'nb', 'nl', 'no', 'pl', 'pt', 'ro', 'ru', 'si', 'sk',
        'sl', 'sr', 'sv', 'ta', 'te', 'th', 'tl', 'tr', 'uk', 'vi', 'zh', 'zu-ZA'
    ]
    name = None
    name = setting('api.language')
    if not name:
        name = 'AUTO'
    if name[-1].isupper():
        try:
            name = xbmc.getLanguage(xbmc.ENGLISH_NAME).split(' ')[0]
        except:
            pass
    try:
        name = langDict[name]
    except:
        name = 'en'
    lang = {'trakt': name} if name in trakt else {'trakt': 'en'}
    lang['tvdb'] = name if name in tvdb else 'en'
    lang['youtube'] = name if name in youtube else 'en'
    lang['tmdb'] = name if name in tmdb else 'en'
    if ret_name:
        lang['trakt'] = [i[0] for i in six.iteritems(langDict)if i[1] == lang['trakt']][0]
        lang['tvdb'] = [i[0] for i in six.iteritems(langDict) if i[1] == lang['tvdb']][0]
        lang['youtube'] = [i[0] for i in six.iteritems(langDict) if i[1] == lang['youtube']][0]
        lang['tmdb'] = [i[0] for i in six.iteritems(langDict) if i[1] == lang['tmdb']][0]
    return lang


def platform():
    if xbmc.getCondVisibility('system.platform.android'):
        return 'android'
    elif xbmc.getCondVisibility('system.platform.linux'):
        return 'linux'
    elif xbmc.getCondVisibility('system.platform.windows'):
        return 'windows'
    elif xbmc.getCondVisibility('system.platform.osx'):
        return 'osx'
    elif xbmc.getCondVisibility('system.platform.atv2'):
        return 'atv2'
    elif xbmc.getCondVisibility('system.platform.ios'):
        return 'ios'


def openBrowser(link):
    myplatform = platform()
    if myplatform == 'android':
        mycommand = 'StartAndroidActivity(,android.intent.action.VIEW,,%s)'
        return xbmc.executebuiltin(mycommand % link)
    else:
        import webbrowser
        return webbrowser.open(link)


def copy2clip(txt):
    platform = sys.platform
    if platform == 'win32':
        try:
            import subprocess
            cmd = 'echo %s|clip' % txt.strip()
            return subprocess.check_call(cmd, shell=True)
        except:
            pass
    elif platform == 'linux2':
        try:
            from subprocess import PIPE, Popen
            p = Popen(['xsel', '-pi'], stdin=PIPE)
            p.communicate(input=txt)
        except:
            pass


def _addon_settings_visible():
    return condVisibility('Window.IsVisible(addonsettings)')


def _wait_addon_settings_window(timeout_ms=6000):
    elapsed = 0
    while elapsed < timeout_ms and not monitor.abortRequested():
        if _addon_settings_visible():
            try:
                return xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
            except Exception:
                pass
        sleep(100)
        elapsed += 100
    return None


def _control_item_count(ctrl):
    for attr in ('size', 'getNumItems', 'getItemCount'):
        fn = getattr(ctrl, attr, None)
        if callable(fn):
            try:
                return int(fn())
            except Exception:
                pass
    return 0


def _is_list_control(ctrl):
    cls = (ctrl.getControlClassName() or '').lower()
    return 'list' in cls or 'panel' in cls


def _find_category_list_control(window, category_index):
    sidebar = []
    tabbar = []
    for cid in range(1, 501):
        try:
            ctrl = window.getControl(cid)
        except Exception:
            continue
        if not _is_list_control(ctrl):
            continue
        try:
            x, y = ctrl.getPosition()
            w = ctrl.getWidth()
            h = ctrl.getHeight()
        except Exception:
            continue
        count = _control_item_count(ctrl)
        if count <= category_index:
            continue
        if x < 500 and w < 600 and h >= 120:
            sidebar.append((x, y, cid, ctrl))
        elif y < 220 and w >= 350:
            tabbar.append((y, x, cid, ctrl))
    if sidebar:
        sidebar.sort(key=lambda item: (item[0], item[1]))
        return sidebar[0][3], sidebar[0][2]
    if tabbar:
        tabbar.sort(key=lambda item: (item[0], item[1]))
        return tabbar[0][3], tabbar[0][2]
    return None, None


def _focus_addon_settings_category(category, setting=0):
    try:
        window = _wait_addon_settings_window()
        if window is None:
            return False
        ctrl, cid = _find_category_list_control(window, category)
        if ctrl is None:
            for fallback_id in (3, 9, 30, 6000, 7000):
                try:
                    ctrl = window.getControl(fallback_id)
                    if _is_list_control(ctrl) and _control_item_count(ctrl) > category:
                        cid = fallback_id
                        break
                except Exception:
                    ctrl = None
            else:
                ctrl, cid = None, None
        if ctrl is not None and cid is not None:
            try:
                window.setFocusId(cid)
            except Exception:
                pass
            try:
                ctrl.selectItem(max(int(category), 0))
            except Exception:
                execute('SetFocus(%d,%d,absolute)' % (cid, int(category)))
            sleep(250)
        elif getKodiVersion() < 18:
            execute('SetFocus(%i)' % (int(category) + 200))
        if setting:
            sleep(150)
            execute('SetFocus(%d)' % (100 + int(setting)))
        return True
    except Exception:
        return False


def openSettings(query=None, id=None):
    try:
        id = addonInfo('id') if id == None else id
        idle()
        execute('Addon.OpenSettings(%s)' % id)
        if query == None:
            return
        category, setting = query.split('.')
        _focus_addon_settings_category(int(category), int(setting))
    except:
        return


def refresh_addon_container():
    """Rebuild the visible addon menu after auth changes."""
    try:
        execute('Dialog.Close(settings)')
        sleep(300)
    except Exception:
        pass
    try:
        folder = infoLabel('Container.FolderPath') or ''
        if addonInfo('id') in folder:
            execute('Container.Update(%s,replace)' % folder)
            sleep(200)
    except Exception:
        pass
    try:
        refresh()
    except Exception:
        pass


def reopen_account_settings():
    """Close and reopen Account Settings so auth changes apply without pressing OK."""
    reopen_settings_category(2, 0)


def reopen_settings_category(category, setting=0):
    """Close and reopen addon settings on the requested category."""
    try:
        idle()
        execute('Dialog.Close(settings)')
        sleep(250)
        execute('Addon.OpenSettings(%s)' % addonInfo('id'))
        sleep(350)
        _focus_addon_settings_category(int(category), int(setting))
    except Exception:
        pass


def finish_auth_ui(reopen_settings=False):
    """Refresh addon menus after auth changes; optionally return to Account Settings."""
    refresh_addon_container()
    if reopen_settings:
        try:
            reopen_account_settings()
        except Exception:
            pass


def installAddon(id, refresh_menu=False):
    try:
        addon_path = os.path.join(transPath('special://home/addons'), id)
        if not os.path.exists(addon_path) == True:
            execute('InstallAddon(%s)' % id)
            if refresh_menu and _wait_for_addon(id):
                refresh()
        else:
            infoDialog('{0} is already installed'.format(id), sound=True)
            if refresh_menu:
                refresh()
    except:
        return


def _wait_for_addon(addon_id, timeout_sec=120):
    try:
        check = 'System.HasAddon(%s)' % addon_id
        for _ in range(int(timeout_sec * 2)):
            if condVisibility(check):
                return True
            sleep(500)
    except:
        pass
    return False


def show_unaired_watchlist():
    """Include Unaired Media in Watchlists — default on (Red Light 2.3.2)."""
    return setting('show.unaired.watchlist') != 'false'


def is_watchlist_shelf(url_key):
    key = str(url_key or '').lower()
    if key in ('trakt_watchlist', 'simkl_plantowatch', 'mdblist_watchlist'):
        return True
    if '/users/me/watchlist/' in key:
        return True
    return False


def item_is_unaired(item, today_date, media='movie'):
    if not item:
        return False
    today = re.sub(r'[^0-9]', '', str(today_date or ''))
    premiered = item.get('premiered') or '0'
    try:
        if premiered and premiered != '0':
            return int(re.sub(r'[^0-9]', '', str(premiered))) > int(today)
    except Exception:
        pass
    if media != 'movie':
        status = item.get('status') or ''
        if (not premiered or premiered == '0') and status in ('Upcoming', 'In Production', 'Planned'):
            return True
    try:
        year = re.sub(r'[^0-9]', '', str(item.get('year') or ''))
        if year and int(year) > int(str(today_date or '')[:4] or '0'):
            return True
    except Exception:
        pass
    return False


def filter_watchlist_unaired(items, url_key, today_date, media='movie'):
    if not items or show_unaired_watchlist() or not is_watchlist_shelf(url_key):
        return items
    return [i for i in items if not item_is_unaired(i, today_date, media=media)]


def playback_progress_stale(item):
    """True when a playback row is leftover ≤1% (Red Light 2.2.4)."""
    if not item:
        return False
    if 'progress' not in item or item.get('progress') in (None, ''):
        return False
    try:
        return float(item.get('progress')) <= 1
    except Exception:
        return False


def checkArtwork():
    try:
        theme = appearance()
        art = artPath()
        if (art == None and theme in ['-', '']):
            if setting('show.artwork') == 'true':
                yes = yesnoDialog('Install Theme Artwork?')
                if not yes:
                    return
                installAddon('script.gratisred.artwork')
        return
    except:
        return


