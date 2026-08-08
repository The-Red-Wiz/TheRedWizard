# -*- coding: utf-8 -*-
"""Simkl account, status lists, watched sync, and manager for Gratis Red.

Adapted from Red Light's Simkl stack to the Exodus-style Gratis Red architecture.
"""
from __future__ import absolute_import

import calendar
import json
import os
import pickle
import re
import time
import zlib
from threading import Lock

import requests
from six.moves.urllib_parse import quote, urljoin

from resources.lib.modules import cache
from resources.lib.modules import control
from resources.lib.modules import log_utils

try:
    from sqlite3 import Binary
except ImportError:
    from pysqlite2 import Binary

BASE_URL = 'https://api.simkl.com'
OAUTH_PIN_URL = 'https://api.simkl.com/oauth/pin'
SIMKL_APP_NAME = 'plugin.video.gratisred'
# Gratis Red Simkl app (unique client ID — not shared with Red Light).
SIMKL_CLIENT_ID = '7508fd47a5237d06eb9b27863e744763c278bc8b35c6c24c336ebbb5d66318bd'

# Shared across plugin invokers + service timer (in-memory alone is not enough in Kodi).
_SIMKL_MIN_REQUEST_GAP = 1.5
_SIMKL_THROTTLE_PROP = 'gratisred.simkl_last_request_at'
_SIMKL_SYNC_BUSY_PROP = 'gratisred.simkl_sync_busy'
_SIMKL_SYNC_BUSY_AT_PROP = 'gratisred.simkl_sync_busy_at'
_SIMKL_ACTIVITIES_SETTING = 'simkl.activities_json'
_SIMKL_SHOW_WATCHED_ACTIVITY_KEYS = ('watching', 'plantowatch', 'completed', 'hold', 'dropped', 'removed_from_list', 'all')
_SIMKL_MOVIE_WATCHED_ACTIVITY_KEYS = ('plantowatch', 'completed', 'dropped', 'removed_from_list', 'all')
_SIMKL_MOVIE_FULL_SYNC_KEYS = ('completed', 'removed_from_list')
_SIMKL_SHOW_FULL_SYNC_KEYS = ('removed_from_list',)
_SIMKL_TV_SYNC_QUERY = 'extended=full&episode_watched_at=yes&include_all_episodes=yes'
_SIMKL_ANIME_SYNC_QUERY = 'extended=full_anime_seasons&episode_watched_at=yes&include_all_episodes=yes'
# Phase 2 multi-type: one /sync/all-items?date_from=… (shows + anime + movies).
_SIMKL_PHASE2_ALL_QUERY = 'extended=full_anime_seasons&episode_watched_at=yes&include_all_episodes=yes'

_STATUSES = ('plantowatch', 'watching', 'completed', 'hold', 'dropped')
_STATUS_LABELS = {
    'plantowatch': 'Plan to Watch',
    'watching': 'Watching',
    'completed': 'Completed',
    'hold': 'On Hold',
    'dropped': 'Dropped',
}

_request_lock = Lock()
_sync_lock = Lock()
_last_request_time = 0.0
_throttle_path = None


def _simkl_throttle_path():
    global _throttle_path
    if not _throttle_path:
        _throttle_path = os.path.join(control.dataPath, 'simkl_api_throttle')
    return _throttle_path


def _shared_last_request_at():
    last = _last_request_time
    try:
        last = max(last, float(control.window.getProperty(_SIMKL_THROTTLE_PROP) or 0))
    except Exception:
        pass
    try:
        last = max(last, os.path.getmtime(_simkl_throttle_path()))
    except Exception:
        pass
    return last


def _claim_request_slot(now):
    global _last_request_time
    _last_request_time = now
    try:
        control.window.setProperty(_SIMKL_THROTTLE_PROP, '%.3f' % now)
    except Exception:
        pass
    try:
        path = _simkl_throttle_path()
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            try:
                os.makedirs(folder)
            except Exception:
                pass
        with open(path, 'w') as handle:
            handle.write('%.3f\n' % now)
    except Exception:
        pass


def _throttle():
    """Space Simkl HTTP calls across threads and separate Kodi Python invokers."""
    with _request_lock:
        while True:
            now = time.time()
            wait = _SIMKL_MIN_REQUEST_GAP - (now - _shared_last_request_at())
            if wait <= 0:
                _claim_request_slot(now)
                return
            control.sleep(int(wait * 1000) + 25)


def _token():
    return (control.setting('simkl.token') or '').strip()


def getSimklCredentialsInfo():
    return bool(_token() and (control.setting('simkl.user') or '').strip())


def getIndicatorsProvider():
    """Return 'local', 'trakt', or 'simkl' based on Indicators setting + credentials."""
    from resources.lib.modules import trakt
    trakt_ok = trakt.getTraktCredentialsInfo()
    simkl_ok = getSimklCredentialsInfo()
    if not trakt_ok and not simkl_ok:
        return 'local'
    val = control.setting('indicators.alt')
    if val == '1' and trakt_ok:
        return 'trakt'
    if val == '2' and simkl_ok:
        return 'simkl'
    return 'local'


def getSimklIndicatorsInfo():
    return getIndicatorsProvider() == 'simkl'


_INDICATOR_LABELS = {'0': 'Local', '1': 'Trakt', '2': 'Simkl'}


def indicators_options():
    """Authorised Indicators choices only (stable values: 0 Local, 1 Trakt, 2 Simkl)."""
    from resources.lib.modules import trakt
    opts = [('Local', '0')]
    if getSimklCredentialsInfo():
        opts.append(('Simkl', '2'))
    if trakt.getTraktCredentialsInfo():
        opts.append(('Trakt', '1'))
    return opts


def indicators_display_name(value=None):
    if value is None:
        value = {'local': '0', 'trakt': '1', 'simkl': '2'}.get(getIndicatorsProvider(), '0')
    return _INDICATOR_LABELS.get(str(value), 'Local')


def sync_indicators_label(value=None):
    try:
        control.setSetting('indicators.alt.name', indicators_display_name(value))
    except Exception:
        pass


def sync_bookmarks_label(value=None):
    try:
        if value is None:
            value = control.setting('bookmarks.source') or '0'
        control.setSetting('bookmarks.source.name', _INDICATOR_LABELS.get(str(value), 'Local'))
    except Exception:
        pass


def set_bookmarks_source(value, notify=False):
    """Set Resume Point Source only (0 Local, 1 Trakt, 2 Simkl)."""
    value = str(value)
    if value not in _INDICATOR_LABELS:
        value = '0'
    control.setSetting('bookmarks.source', value)
    sync_bookmarks_label(value)
    if notify:
        control.infoDialog('Resume Point Source: %s' % _INDICATOR_LABELS.get(value, 'Local'), sound=True)


def set_watched_provider(value, notify=False):
    """Set Indicators + matching Resume Point Source (0 Local, 1 Trakt, 2 Simkl)."""
    value = str(value)
    if value not in _INDICATOR_LABELS:
        value = '0'
    control.setSetting('indicators.alt', value)
    set_bookmarks_source(value, notify=False)
    sync_indicators_label(value)
    if notify:
        name = _INDICATOR_LABELS.get(value, 'Local')
        control.infoDialog('Watched Indicators & Resume: %s' % name, sound=True)


def ensure_bookmarks_valid():
    """Keep Resume Point Source aligned with Watched Indicators (no separate picker)."""
    val = control.setting('indicators.alt') or '0'
    if (control.setting('bookmarks.source') or '0') != val:
        set_bookmarks_source(val)
    else:
        sync_bookmarks_label(val)


def ensure_indicators_valid():
    """If stored Indicators points at an unauthorised service, fall back and refresh label."""
    from resources.lib.modules import trakt
    val = control.setting('indicators.alt') or '0'
    if val == '1' and not trakt.getTraktCredentialsInfo():
        set_watched_provider('2' if getSimklCredentialsInfo() else '0')
    elif val == '2' and not getSimklCredentialsInfo():
        set_watched_provider('1' if trakt.getTraktCredentialsInfo() else '0')
    else:
        sync_indicators_label(val)
        ensure_bookmarks_valid()


def fallback_indicators_on_revoke(revoked):
    """revoked: 'trakt' or 'simkl'. Adjust Indicators if that provider was selected."""
    from resources.lib.modules import trakt
    val = control.setting('indicators.alt') or '0'
    if revoked == 'trakt' and val == '1':
        set_watched_provider('2' if getSimklCredentialsInfo() else '0')
    elif revoked == 'simkl' and val == '2':
        set_watched_provider('1' if trakt.getTraktCredentialsInfo() else '0')
    else:
        sync_indicators_label()
        ensure_bookmarks_valid()


def _provider_select(heading, current):
    opts = indicators_options()
    labels = [o[0] for o in opts]
    preselect = -1
    for i, (_label, value) in enumerate(opts):
        if value == current:
            preselect = i
            break
    try:
        select = control.dialog.select(heading, labels, preselect=preselect)
    except TypeError:
        select = control.selectDialog(labels, heading)
    if select < 0:
        return None
    return opts[select][1]


def choose_indicators(reopen_settings=False):
    ensure_indicators_valid()
    value = _provider_select('Watched Indicators', control.setting('indicators.alt') or '0')
    if value is None:
        if reopen_settings:
            control.reopen_settings_category(0, 0)
        return
    set_watched_provider(value, notify=True)
    control.sleep(350)
    if reopen_settings:
        control.reopen_settings_category(0, 0)


def _headers():
    h = {
        'Content-Type': 'application/json',
        'simkl-api-key': SIMKL_CLIENT_ID,
        'User-Agent': '%s/%s' % (SIMKL_APP_NAME, control.addonInfo('version')),
    }
    token = _token()
    if token:
        h['Authorization'] = 'Bearer %s' % token
    return h


def _url(path):
    base = path if path.startswith('http') else urljoin(BASE_URL, path.lstrip('/'))
    sep = '&' if '?' in base else '?'
    return '%s%sclient_id=%s&app-name=%s&app-version=%s' % (
        base, sep, SIMKL_CLIENT_ID, SIMKL_APP_NAME, control.addonInfo('version'))


def call_simkl(path, data=None, method=None):
    _throttle()
    url = _url(path)
    headers = _headers()
    try:
        if method == 'get' or (data is None and not method):
            resp = requests.get(url, headers=headers, timeout=20)
        else:
            payload = json.dumps(data) if isinstance(data, (dict, list)) else data
            resp = requests.post(url, data=payload, headers=headers, timeout=20)
        if resp.status_code in (200, 201):
            return resp.json() if resp.text else True
        if resp.status_code == 204:
            return True
        log_utils.log('Simkl HTTP %s %s' % (resp.status_code, url), 1)
    except Exception as e:
        log_utils.log('Simkl Error: %s' % e, 1)
    return None


def _fetch_user_settings(access_token):
    """POST /users/settings — Simkl's documented profile call (GET is not the contract)."""
    _throttle()
    url = _url('/users/settings')
    headers = _headers()
    headers['Authorization'] = 'Bearer %s' % access_token
    try:
        resp = requests.post(url, data=json.dumps({}), headers=headers, timeout=20)
        if resp.status_code in (200, 201) and resp.text:
            return resp.json()
        log_utils.log('Simkl HTTP %s %s' % (resp.status_code, url), 1)
    except Exception as e:
        log_utils.log('Simkl Error: %s' % e, 1)
    return None


def _pin_url(user_code=None):
    url = '%s/%s' % (OAUTH_PIN_URL, user_code) if user_code else OAUTH_PIN_URL
    sep = '&' if '?' in url else '?'
    return '%s%sclient_id=%s&app-name=%s&app-version=%s' % (
        url, sep, SIMKL_CLIENT_ID, SIMKL_APP_NAME, control.addonInfo('version'))


def authSimkl(reopen_settings=False):
    from resources.lib.modules import auth_utils
    progress = None
    try:
        if getSimklCredentialsInfo():
            control.infoDialog('Simkl is already authorised. Use Revoke Simkl Account to sign out.', sound=True)
            return
        progress = auth_utils.auth_progress_dialog('Simkl Authorise', '')
        progress.update('Connecting to Simkl...')
        try:
            pin = requests.get(_pin_url(), headers={'User-Agent': SIMKL_APP_NAME}, timeout=20).json()
        except Exception:
            pin = None
        if not pin or not pin.get('user_code'):
            control.infoDialog('Simkl Authorisation Failed.', sound=True)
            return
        user_code = str(pin.get('user_code', ''))
        expires_in = int(pin.get('expires_in') or 900)
        interval = max(int(pin.get('interval') or 5), 1)
        verify = (pin.get('verification_uri') or pin.get('verification_url') or 'https://simkl.com/pin').rstrip('/')
        auth_url = '%s/%s' % (verify, user_code)
        progress.update('Preparing QR code...')
        qr_code = auth_utils.make_qrcode(auth_url) or ''
        short_url = auth_utils.make_tinyurl(auth_url)
        auth_utils.copy2clip(auth_url)
        insert = '[CR]OR visit [B]%s[/B]' % short_url if short_url else ''
        content = ('Enter [B]%s[/B] at [B]simkl.com/pin[/B][CR]OR scan the [B]QR Code[/B][CR]'
                   'Link copied to clipboard%s[CR][CR]Waiting for authorisation...' % (user_code, insert))
        progress.update(content, qr_path=qr_code)
        token = None
        start = time.time()
        while not progress.iscanceled() and (time.time() - start) < expires_in:
            if auth_utils.auth_progress_wait(progress, interval):
                break
            try:
                resp = requests.get(_pin_url(user_code), headers={'User-Agent': SIMKL_APP_NAME}, timeout=20).json()
                if isinstance(resp, dict) and resp.get('access_token'):
                    token = resp['access_token']
                    break
            except Exception:
                pass
        canceled = progress.iscanceled()
        auth_utils.close_auth_progress_dialog(progress)
        progress = None
        if canceled or not token:
            control.infoDialog('Simkl Authorisation Canceled.' if canceled else 'Simkl Authorisation Failed.', sound=True)
            return
        control.setSetting('simkl.token', token)
        # Profile is POST /users/settings (docs). Pass the new token explicitly so we do not
        # race Addon.setSetting before Bearer auth is readable for the follow-up call.
        info = _fetch_user_settings(token)
        user = 'Simkl User'
        if info and isinstance(info, dict) and info.get('user'):
            u = info['user']
            user = str(u.get('name') or u.get('login') or u.get('username') or user)
        control.setSetting('simkl.user', user)
        control.setSetting('simkl.authed', 'yes')
        if control.yesnoDialog('Set Simkl as your Watched Indicators provider?', heading='Watched Status Provider'):
            set_watched_provider('2', notify=True)
        try:
            cachesyncMovies(timeout=0)
            cachesyncTVShows(timeout=0)
        except Exception:
            pass
        control.infoDialog('Simkl Account Authorised.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('Simkl Authorisation Failed.', sound=True)
    finally:
        if progress is not None:
            auth_utils.close_auth_progress_dialog(progress)


def revokeSimkl(reopen_settings=False):
    if not getSimklCredentialsInfo():
        control.infoDialog('No Simkl account is authorised.', sound=True)
        return
    try:
        control.setSetting('simkl.user', '')
        control.setSetting('simkl.token', '')
        control.setSetting('simkl.authed', '')
        _store_cached_activities({})
        fallback_indicators_on_revoke('simkl')
        _bust_sync_cache()
        control.infoDialog('Simkl Account Revoked.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('Simkl Revoke Failed.', sound=True)


def _media_ids(item, media_kind):
    try:
        if media_kind == 'movies':
            obj = item.get('movie') or item
        else:
            obj = item.get('show') or item.get('anime') or item
        ids = obj.get('ids') or item.get('ids') or {}
        if not isinstance(ids, dict):
            ids = {}
        out = {}
        for key in ('tmdb', 'imdb', 'tvdb'):
            value = ids.get(key)
            if value in (None, '', 'None', 0, '0'):
                continue
            if key in ('tmdb', 'tvdb'):
                try:
                    value = int(value)
                except Exception:
                    pass
            out[key] = value
        return out, obj
    except Exception:
        return {}, {}


def _all_items(media_kind, status):
    # Default sync payload includes title/year (needed for shelf_sort). ids_only strips titles.
    path = '/sync/all-items/%s/%s' % (media_kind, status)
    response = call_simkl(path, method='get')
    if response is None:
        return None
    if response is True:
        return []
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return None
    items = response.get(media_kind)
    if items is None and media_kind in ('shows', 'anime'):
        items = response.get('shows') or response.get('anime')
    if items is None:
        items = response.get('items') or response.get('list') or []
    return items if isinstance(items, list) else []


def _fetch_status(media_kind, status):
    if not getSimklCredentialsInfo():
        return []
    items = _all_items(media_kind, status)
    if items is None:
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ids, block = _media_ids(item, media_kind)
        if not ids:
            continue
        result.append({
            'ids': ids,
            'title': block.get('title', '') or '',
            'year': block.get('year') or 0,
            'collected_at': item.get('added_to_watchlist_at') or '',
        })
    return result


def _fetch_tv_status(status):
    shows = _fetch_status('shows', status)
    anime = _fetch_status('anime', status)
    if not shows and not anime:
        return []
    seen = set()
    merged = []
    for item in shows + anime:
        key = item['ids'].get('tmdb') or item['ids'].get('imdb') or item.get('title')
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _normalize_imdb(imdb):
    if not imdb or imdb in ('0', 'None'):
        return '0'
    imdb = str(imdb)
    if not imdb.startswith('tt'):
        imdb = 'tt' + re.sub(r'[^0-9]', '', imdb)
    return imdb


# Per-shelf sort for My Simkl status lists — see shelf_sort.py.


def choose_list_sort(media, status):
    from resources.lib.modules import shelf_sort
    shelf_sort.choose_list_sort('simkl', media, status, sortable=shelf_sort.SIMKL_SORTABLE)


def directory_movies(status):
    """Build Gratis Red movie list items for a Simkl status shelf."""
    from resources.lib.modules import shelf_sort
    items = _fetch_status('movies', status)
    out = []
    for item in items:
        ids = item.get('ids') or {}
        title = item.get('title') or 'Unknown'
        year = item.get('year') or '0'
        try:
            year = re.sub(r'[^0-9]', '', str(year)) or '0'
        except Exception:
            year = '0'
        imdb = _normalize_imdb(ids.get('imdb'))
        tmdb = str(ids.get('tmdb') or '0')
        out.append({
            'title': title, 'originaltitle': title, 'year': year,
            'imdb': imdb, 'tmdb': tmdb, 'tvdb': '0', 'next': '', 'paused_at': '0',
            'collected_at': item.get('collected_at') or '',
        })
    return shelf_sort.sort_items(out, 'simkl', 'movies', status, sortable=shelf_sort.SIMKL_SORTABLE)


def directory_tvshows(status):
    """Build Gratis Red TV show list items for a Simkl status shelf."""
    from resources.lib.modules import shelf_sort
    items = _fetch_tv_status(status)
    out = []
    for item in items:
        ids = item.get('ids') or {}
        title = item.get('title') or 'Unknown'
        year = item.get('year') or '0'
        try:
            year = re.sub(r'[^0-9]', '', str(year)) or '0'
        except Exception:
            year = '0'
        imdb = _normalize_imdb(ids.get('imdb'))
        tmdb = str(ids.get('tmdb') or '0')
        tvdb = str(ids.get('tvdb') or '0')
        out.append({
            'title': title, 'originaltitle': title, 'year': year,
            'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'next': '',
            'collected_at': item.get('collected_at') or '',
        })
    return shelf_sort.sort_items(out, 'simkl', 'tvshows', status, sortable=shelf_sort.SIMKL_SORTABLE)


def _paused_key(paused_at):
    if not paused_at:
        return '0'
    try:
        return re.sub(r'[^0-9]+', '', str(paused_at)) or '0'
    except Exception:
        return '0'


def get_playback(media_filter=None):
    """Raw /sync/playback items. media_filter: None, 'movies', or 'episodes'."""
    if not getSimklCredentialsInfo():
        return []
    path = '/sync/playback'
    if media_filter == 'movies':
        path = '/sync/playback/movies'
    elif media_filter == 'episodes':
        path = '/sync/playback/episodes'
    data = call_simkl(path, method='get')
    if data is None:
        return []
    if data is True:
        return []
    return data if isinstance(data, list) else []


def directory_playback_movies():
    """In Progress movies from Simkl playback."""
    out = []
    for item in get_playback('movies'):
        try:
            if item.get('type') and item.get('type') != 'movie':
                continue
            movie = item.get('movie') or item
            ids = movie.get('ids') or {}
            title = movie.get('title') or 'Unknown'
            year = movie.get('year') or '0'
            try:
                year = re.sub(r'[^0-9]', '', str(year)) or '0'
            except Exception:
                year = '0'
            imdb = _normalize_imdb(ids.get('imdb'))
            tmdb = str(ids.get('tmdb') or '0')
            out.append({
                'title': title, 'originaltitle': title, 'year': year,
                'imdb': imdb, 'tmdb': tmdb, 'tvdb': '0', 'next': '',
                'paused_at': _paused_key(item.get('paused_at')),
            })
        except Exception:
            pass
    return out


def playback_episode_items():
    """Minimal episode rows for In Progress Episodes enrichment."""
    out = []
    for item in get_playback('episodes'):
        try:
            if item.get('type') and item.get('type') != 'episode':
                continue
            show = item.get('show') or {}
            ep = item.get('episode') or {}
            ids = show.get('ids') or {}
            title = show.get('title') or 'Unknown'
            year = show.get('year') or '0'
            try:
                year = re.sub(r'[^0-9]', '', str(year)) or '0'
            except Exception:
                year = '0'
            season = ep.get('season')
            episode = ep.get('number') or ep.get('episode')
            if season is None or episode is None:
                continue
            out.append({
                'title': ep.get('title') or title,
                'season': '%01d' % int(season),
                'episode': '%01d' % int(episode),
                'tvshowtitle': title,
                'year': year,
                'premiered': '0',
                'status': '0',
                'studio': [],
                'genre': [],
                'duration': '0',
                'rating': '0',
                'votes': '0',
                'mpaa': '0',
                'plot': '0',
                'imdb': _normalize_imdb(ids.get('imdb')),
                'tvdb': str(ids.get('tvdb') or '0'),
                'tmdb': str(ids.get('tmdb') or '0'),
                'poster': '0',
                'thumb': '0',
                'paused_at': _paused_key(item.get('paused_at')),
                'watched_at': '0',
            })
        except Exception:
            pass
    return out


def dropped_tmdb_ids():
    ids = set()
    for item in _fetch_tv_status('dropped'):
        tmdb = (item.get('ids') or {}).get('tmdb')
        if tmdb:
            ids.add(str(tmdb))
    return ids


def progress_seeds():
    """Continue Watching seeds: last watched ep per show (exclude Dropped).

    Shape matches the pre-enrichment items used by trakt_progress_list
    (snum/enum = last watched; enrichment resolves the *next* episode).
    """
    if not getSimklCredentialsInfo():
        return []
    dropped = dropped_tmdb_ids()
    indicators = cachesyncTVShows(timeout=720) or []
    by_tmdb = {}
    for row in indicators:
        try:
            tmdb, aired, watched = str(row[0]), int(row[1]), row[2] or []
        except Exception:
            continue
        if not tmdb or tmdb == '0' or tmdb in dropped:
            continue
        if not watched:
            continue
        if len(watched) >= aired > 0:
            continue
        last = sorted(watched, key=lambda se: (int(se[0]), int(se[1])))[-1]
        by_tmdb[tmdb] = {
            'tmdb': tmdb, 'imdb': '0', 'tvdb': '0',
            'tvshowtitle': '', 'year': '0', 'studio': [], 'duration': '0',
            'mpaa': '0', 'status': '0', 'genre': [],
            'snum': str(last[0]), 'enum': str(last[1]),
            '_last_watched': '0',
        }
    # Prefer titles/ids from Watching + plantowatch shelves when available.
    meta_by_tmdb = {}
    for status in ('watching', 'plantowatch', 'hold', 'completed'):
        for item in _fetch_tv_status(status):
            ids = item.get('ids') or {}
            tmdb = str(ids.get('tmdb') or '0')
            if tmdb == '0':
                continue
            meta_by_tmdb[tmdb] = item
    for tmdb, seed in list(by_tmdb.items()):
        meta = meta_by_tmdb.get(tmdb)
        if not meta:
            continue
        ids = meta.get('ids') or {}
        seed['tvshowtitle'] = meta.get('title') or seed['tvshowtitle']
        seed['year'] = str(meta.get('year') or seed['year'] or '0')
        seed['imdb'] = _normalize_imdb(ids.get('imdb'))
        seed['tvdb'] = str(ids.get('tvdb') or '0')
    # Watching shows with no watched episodes yet → start from S01E00 tip.
    for item in _fetch_tv_status('watching'):
        ids = item.get('ids') or {}
        tmdb = str(ids.get('tmdb') or '0')
        if tmdb == '0' or tmdb in dropped or tmdb in by_tmdb:
            continue
        by_tmdb[tmdb] = {
            'tmdb': tmdb,
            'imdb': _normalize_imdb(ids.get('imdb')),
            'tvdb': str(ids.get('tvdb') or '0'),
            'tvshowtitle': item.get('title') or '',
            'year': str(item.get('year') or '0'),
            'studio': [], 'duration': '0', 'mpaa': '0', 'status': '0', 'genre': [],
            'snum': '1', 'enum': '0', '_last_watched': '0',
        }
    seeds = [s for s in by_tmdb.values() if s.get('tvshowtitle')]
    limit = str(control.setting('trakt.item.limit') or '100')
    try:
        limit = int(limit)
    except Exception:
        limit = 100
    return seeds[:limit]


def _cdn_get(path):
    """Fetch a Simkl CDN JSON file (calendar / trending). Auth not required."""
    base = 'https://data.simkl.in/%s' % path.lstrip('/')
    url = _url(base)
    _throttle()
    try:
        resp = requests.get(url, headers={
            'User-Agent': '%s/%s' % (SIMKL_APP_NAME, control.addonInfo('version')),
        }, timeout=25)
        if resp.status_code != 200:
            log_utils.log('Simkl CDN HTTP %s %s' % (resp.status_code, path), 1)
            return None
        return resp.json()
    except Exception as e:
        log_utils.log('Simkl CDN Error: %s' % e, 1)
        return None


def my_show_tmdb_ids():
    """TMDb IDs for Upcoming filter: Watching / Plan to Watch / On Hold (minus Dropped)."""
    ids = set()
    for status in ('watching', 'plantowatch', 'hold'):
        for item in _fetch_tv_status(status):
            tmdb = (item.get('ids') or {}).get('tmdb')
            if tmdb:
                ids.add(str(tmdb))
    return ids - dropped_tmdb_ids()


def calendar_episode_items(mine_only=True):
    """Upcoming episodes from Simkl calendar v2 (TV + anime), optional user filter."""
    want = my_show_tmdb_ids() if mine_only else None
    if mine_only and not want:
        return []
    out = []
    seen = set()
    for catalog in ('tv', 'anime'):
        data = _cdn_get('calendar/v2/%s.json' % catalog)
        if not isinstance(data, dict):
            continue
        calendar = data.get('calendar') or []
        metadata = data.get('metadata') or {}
        for entry in calendar:
            try:
                meta = metadata.get(str(entry.get('simkl_id'))) or {}
                ids = meta.get('ids') or {}
                tmdb = str(ids.get('tmdb') or '0')
                if mine_only and tmdb not in want:
                    continue
                ep = entry.get('episode') or {}
                season = ep.get('season')
                episode = ep.get('episode')
                if episode is None:
                    continue
                if season is None:
                    season = 1
                premiered = (entry.get('date') or '')[:10] or '0'
                key = (tmdb, int(season), int(episode), premiered)
                if key in seen:
                    continue
                seen.add(key)
                title = meta.get('title') or 'Unknown'
                year = '0'
                try:
                    rd = meta.get('release_date') or ''
                    if rd:
                        year = re.sub(r'[^0-9]', '', rd)[:4] or '0'
                except Exception:
                    pass
                out.append({
                    'title': ep.get('title') or title,
                    'season': '%01d' % int(season),
                    'episode': '%01d' % int(episode),
                    'tvshowtitle': title,
                    'year': year,
                    'premiered': premiered,
                    'status': meta.get('status') or '0',
                    'studio': [meta['network']] if meta.get('network') else [],
                    'genre': meta.get('genres') or [],
                    'duration': '0',
                    'rating': '0',
                    'votes': '0',
                    'mpaa': '0',
                    'plot': '0',
                    'imdb': _normalize_imdb(ids.get('imdb')),
                    'tvdb': str(ids.get('tvdb') or '0'),
                    'tmdb': tmdb,
                    'poster': '0',
                    'thumb': '0',
                    'paused_at': '0',
                    'watched_at': '0',
                })
            except Exception:
                pass
    try:
        out = sorted(out, key=lambda k: k.get('premiered') or '', reverse=False)
    except Exception:
        pass
    limit = str(control.setting('trakt.item.limit') or '100')
    try:
        limit = int(limit)
    except Exception:
        limit = 100
    return out[: max(limit, 50)]


def _trending_file(media_kind, period):
    # media_kind: movies|tv|anime ; period: today|week|month
    return 'discover/trending/%s/%s_100.json' % (media_kind, period)


def directory_trending(media_kind, period='today'):
    """Simkl Most Watched / Trending CDN list as Gratis Red movie or TV items."""
    kinds = (media_kind,)
    if media_kind in ('tv', 'shows', 'tvshows'):
        kinds = ('tv', 'anime')
        media_kind = 'tv'
    out = []
    seen = set()
    for kind in kinds:
        data = _cdn_get(_trending_file(kind, period))
        if data is None:
            continue
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get(kind) or data.get('items') or data.get('movies') or data.get('tv') or data.get('anime') or []
        else:
            items = []
        for item in items:
            try:
                if not isinstance(item, dict):
                    continue
                # Trending payload may nest under movie/show or be flat with ids/title.
                block = item.get('movie') or item.get('show') or item.get('anime') or item
                ids = block.get('ids') or item.get('ids') or {}
                tmdb = str(ids.get('tmdb') or '0')
                if tmdb == '0' or tmdb in seen:
                    continue
                seen.add(tmdb)
                title = block.get('title') or item.get('title') or 'Unknown'
                year = block.get('year') or item.get('year') or '0'
                try:
                    year = re.sub(r'[^0-9]', '', str(year)) or '0'
                except Exception:
                    year = '0'
                row = {
                    'title': title, 'originaltitle': title, 'year': year,
                    'imdb': _normalize_imdb(ids.get('imdb')),
                    'tmdb': tmdb,
                    'tvdb': str(ids.get('tvdb') or '0'),
                    'next': '',
                }
                if media_kind == 'movies':
                    row['paused_at'] = '0'
                out.append(row)
            except Exception:
                pass
    return out


def syncMovies(user):
    try:
        if not getSimklCredentialsInfo():
            return []
        return _fetch_movie_indicators(date_from=None)
    except Exception:
        return []


def cachesyncMovies(timeout=0):
    return cache.get(syncMovies, timeout, control.setting('simkl.user').strip() or 'simkl')


def timeoutsyncMovies():
    try:
        return cache.timeout(syncMovies, control.setting('simkl.user').strip() or 'simkl') or 0
    except Exception:
        return 0


def syncTVShows(user):
    """Match Trakt cachesyncTVShows shape: [(tmdb, aired_eps, [(s,e),...]), ...]."""
    try:
        if not getSimklCredentialsInfo():
            return []
        indicators, _touched = _fetch_tv_indicators(date_from=None)
        return indicators
    except Exception:
        return []


def cachesyncTVShows(timeout=0):
    return cache.get(syncTVShows, timeout, control.setting('simkl.user').strip() or 'simkl')


def timeoutsyncTVShows():
    try:
        return cache.timeout(syncTVShows, control.setting('simkl.user').strip() or 'simkl') or 0
    except Exception:
        return 0


def _simkl_with_date_from(query, date_from=None):
    if not date_from:
        return query
    return '%s&date_from=%s' % (query, quote(date_from, safe=''))


def _activity_ts(ts_str):
    if not ts_str:
        return 0
    try:
        return int(calendar.timegm(time.strptime(ts_str.rstrip('Z').split('.')[0], '%Y-%m-%dT%H:%M:%S')))
    except Exception:
        return 0


def _activity_block_changed(latest_blk, cached_blk, keys):
    latest_blk = latest_blk or {}
    cached_blk = cached_blk or {}
    for key in keys:
        if _activity_ts(latest_blk.get(key, '')) > _activity_ts(cached_blk.get(key, '')):
            return True
    return False


def _simkl_date_from(cached_activities):
    ts = str((cached_activities or {}).get('all') or '').strip()
    if not ts:
        return None
    if ts.startswith('2020-01-01'):
        return None
    return ts


def _load_cached_activities():
    raw = (control.setting(_SIMKL_ACTIVITIES_SETTING) or '').strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _store_cached_activities(latest):
    try:
        control.setSetting(_SIMKL_ACTIVITIES_SETTING, json.dumps(latest or {}))
    except Exception:
        pass


def _read_sync_cache(function, *args):
    try:
        key = cache._hash_function(function, *args)
        row = cache.cache_get(key)
        if not row:
            return None
        return pickle.loads(zlib.decompress(row['value']))
    except Exception:
        return None


def _write_sync_cache(function, result, *args):
    try:
        key = cache._hash_function(function, *args)
        cache.cache_insert(key, Binary(zlib.compress(pickle.dumps(result))))
    except Exception as e:
        log_utils.log('Simkl cache write failed: %s' % e, 1)


def _fetch_movie_indicators(date_from=None):
    path = '/sync/all-items/movies/completed?%s' % _simkl_with_date_from('extended=full', date_from)
    data = call_simkl(path, method='get') or {}
    return _movie_indicators_from_data(data, filter_status=False)


def _movie_indicators_from_data(data, filter_status=False):
    rows = (data or {}).get('movies', data if isinstance(data, list) else [])
    indicators = []
    for item in rows:
        try:
            movie = item.get('movie', item)
            imdb = movie.get('ids', {}).get('imdb')
            if not imdb:
                continue
            status = str(item.get('status') or '').lower()
            watched_at = item.get('last_watched_at') or item.get('watched_at')
            # Unified Phase 2 returns all statuses — only store completed/watched movies.
            if filter_status and not watched_at and status != 'completed':
                continue
            indicators.append(_normalize_imdb(imdb))
        except Exception:
            pass
    return indicators


def _append_tv_indicator_rows(indicators, touched_ids, data, item_key):
    items = data.get(item_key, data if isinstance(data, list) else [])
    for item in items:
        try:
            if item_key == 'anime':
                show = item.get('anime') or item.get('show') or item
            else:
                show = item.get('show') or item
            tmdb = show.get('ids', {}).get('tmdb')
            if not tmdb:
                continue
            tmdb = str(tmdb)
            if touched_ids is not None:
                touched_ids.add(tmdb)
            aired = int(show.get('total_episodes_count') or show.get('aired_episodes') or 0)
            watched = []
            for season in item.get('seasons') or []:
                try:
                    snum = int(season.get('number', season.get('season')))
                except Exception:
                    continue
                for ep in season.get('episodes') or []:
                    if not (ep.get('watched_at') or ep.get('last_watched_at')):
                        continue
                    tvdb_map = ep.get('tvdb') if isinstance(ep.get('tvdb'), dict) else None
                    try:
                        if tvdb_map and tvdb_map.get('season') is not None and tvdb_map.get('episode') is not None:
                            ep_snum = int(tvdb_map['season'])
                            epnum = int(tvdb_map['episode'])
                        else:
                            ep_snum = snum
                            epnum = int(ep.get('number', ep.get('episode')))
                    except Exception:
                        continue
                    watched.append((ep_snum, epnum))
            if not aired:
                aired = len(watched)
            indicators.append((tmdb, int(aired), watched))
        except Exception:
            pass


def _tv_indicators_from_data(data, date_from=None):
    touched_ids = set() if date_from else None
    indicators = []
    _append_tv_indicator_rows(indicators, touched_ids, data or {}, 'shows')
    _append_tv_indicator_rows(indicators, touched_ids, data or {}, 'anime')
    return indicators, touched_ids


def _fetch_tv_indicators(date_from=None):
    if date_from:
        # Phase 2: one multi-type request (shows + anime; movies ignored here).
        data = call_simkl('/sync/all-items?%s' % _simkl_with_date_from(_SIMKL_PHASE2_ALL_QUERY, date_from), method='get') or {}
        return _tv_indicators_from_data(data, date_from)
    # Phase 1: sequential per-type full pulls (Simkl guidance for large libraries).
    indicators = []
    shows = call_simkl('/sync/all-items/shows?%s' % _SIMKL_TV_SYNC_QUERY, method='get') or {}
    _append_tv_indicator_rows(indicators, None, shows, 'shows')
    anime = call_simkl('/sync/all-items/anime?%s' % _SIMKL_ANIME_SYNC_QUERY, method='get') or {}
    _append_tv_indicator_rows(indicators, None, anime, 'anime')
    return indicators, None


def _fetch_phase2_indicators(date_from):
    """Phase 2 continuous sync: one /sync/all-items?date_from= for movies + shows + anime."""
    if not date_from:
        return [], [], None
    data = call_simkl('/sync/all-items?%s' % _simkl_with_date_from(_SIMKL_PHASE2_ALL_QUERY, date_from), method='get') or {}
    movies = _movie_indicators_from_data(data, filter_status=True)
    tv, touched = _tv_indicators_from_data(data, date_from)
    return movies, tv, touched


def _merge_movie_indicators(existing, delta):
    out = set(existing or [])
    out.update(delta or [])
    return list(out)


def _merge_tv_indicators(existing, delta, touched_ids):
    by_tmdb = {}
    for row in existing or []:
        try:
            by_tmdb[str(row[0])] = row
        except Exception:
            pass
    delta_ids = set()
    for row in delta or []:
        try:
            tid = str(row[0])
            by_tmdb[tid] = row
            delta_ids.add(tid)
        except Exception:
            pass
    for tid in (touched_ids or set()):
        if tid not in delta_ids and tid in by_tmdb:
            old = by_tmdb[tid]
            try:
                by_tmdb[tid] = (old[0], old[1], [])
            except Exception:
                pass
    return list(by_tmdb.values())


def getWatchedActivity():
    """Latest movies/tv/anime watched activity timestamp (UTC seconds), Trakt-shaped helper."""
    try:
        latest = call_simkl('/sync/activities', method='get') or {}
        stamps = []
        for block in (latest.get('movies') or {}, latest.get('tv_shows') or {}, latest.get('anime') or {}):
            for key in ('completed', 'watching', 'all'):
                ts = _activity_ts(block.get(key, ''))
                if ts:
                    stamps.append(ts)
        stamps.append(_activity_ts(latest.get('all', '')))
        return max(stamps) if stamps else 0
    except Exception:
        return 0


def syncSeason(imdb):
    """Season overlays rely on episode-level Simkl sync; return empty here."""
    return []


def _list_ids(tmdb=None, imdb=None, tvdb=None):
    ids = {}
    if tmdb and str(tmdb) not in ('0', '', 'None'):
        try:
            ids['tmdb'] = int(tmdb)
        except Exception:
            pass
    if imdb and str(imdb) not in ('0', '', 'None'):
        ids['imdb'] = _normalize_imdb(imdb)
    if tvdb and str(tvdb) not in ('0', '', 'None'):
        try:
            ids['tvdb'] = int(tvdb)
        except Exception:
            pass
    return ids


def _ids_match(item_ids, ids):
    if not isinstance(item_ids, dict) or not isinstance(ids, dict):
        return False
    for key in ('tmdb', 'imdb', 'tvdb'):
        item_value = item_ids.get(key)
        wanted_value = ids.get(key)
        if item_value in (None, '', 'None', 0, '0') or wanted_value in (None, '', 'None', 0, '0'):
            continue
        if str(item_value) == str(wanted_value):
            return True
    return False


def _item_in_status(media_kind, status, ids):
    try:
        if media_kind == 'movies':
            items = _fetch_status('movies', status)
        else:
            items = _fetch_tv_status(status)
        for item in items:
            if _ids_match(item.get('ids'), ids):
                return True
    except Exception:
        pass
    return False


def markMovieAsWatched(imdb, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    return call_simkl('/sync/history', data={'movies': [{'ids': ids}]})


def markMovieAsNotWatched(imdb, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    return call_simkl('/sync/history/remove', data={'movies': [{'ids': ids}]})


def markEpisodeAsWatched(imdb, season, episode, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    season, episode = int(season), int(episode)
    return call_simkl('/sync/history', data={
        'shows': [{'ids': ids, 'seasons': [{'number': season, 'episodes': [{'number': episode}]}]}]
    })


def markEpisodeAsNotWatched(imdb, season, episode, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    season, episode = int(season), int(episode)
    return call_simkl('/sync/history/remove', data={
        'shows': [{'ids': ids, 'seasons': [{'number': season, 'episodes': [{'number': episode}]}]}]
    })


def markTVShowAsWatched(imdb, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    return call_simkl('/sync/history', data={'shows': [{'ids': ids}]})


def markTVShowAsNotWatched(imdb, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    return call_simkl('/sync/history/remove', data={'shows': [{'ids': ids}]})


def getSimklAddonMovieInfo():
    """True when official script.simkl should own movie scrobble (defer Gratis Red mark)."""
    try:
        addon = control.addon('script.simkl')
    except Exception:
        return False
    try:
        token = (addon.getSetting('access_token') or addon.getSetting('token') or
                 addon.getSetting('authorization') or '').strip()
    except Exception:
        token = ''
    if not token:
        return False
    for key in ('auto_scrobble', 'autoscrobble', 'scrobble_enabled', 'auto_scrobble_enabled'):
        try:
            if addon.getSetting(key) in ('true', 'True', '1'):
                return True
        except Exception:
            pass
    return False


def getSimklAddonEpisodeInfo():
    return getSimklAddonMovieInfo()


def _scrobble_payload(media_type, percent, tmdb=None, imdb=None, season=None, episode=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    data = {'progress': float(percent or 0)}
    if media_type == 'movie':
        data['movie'] = {'ids': ids}
    else:
        data['show'] = {'ids': ids}
        data['episode'] = {'season': int(season), 'number': int(episode)}
    return data


def simkl_scrobble(action, media_type, percent=0, tmdb=None, imdb=None, season=None, episode=None):
    """Native Simkl scrobble. Skips when Indicators != Simkl or script.simkl auto-scrobble is on."""
    if getIndicatorsProvider() != 'simkl':
        return
    if media_type == 'movie' and getSimklAddonMovieInfo():
        return
    if media_type != 'movie' and getSimklAddonEpisodeInfo():
        return
    path = {'start': '/scrobble/start', 'pause': '/scrobble/pause', 'stop': '/scrobble/stop'}.get(action)
    if not path:
        return
    payload = _scrobble_payload(media_type, percent, tmdb=tmdb, imdb=imdb, season=season, episode=episode)
    if not payload:
        return
    call_simkl(path, data=payload)


def syncSimklWatched(silent=True, force_update=False):
    """Refresh Simkl watched indicator caches via /sync/activities + optional date_from deltas."""
    if not getSimklCredentialsInfo():
        return False
    if not force_update:
        try:
            if control.window.getProperty(_SIMKL_SYNC_BUSY_PROP) == 'true':
                started = float(control.window.getProperty(_SIMKL_SYNC_BUSY_AT_PROP) or 0)
                if started and (time.time() - started) < 180:
                    return False
        except Exception:
            pass
        if not _sync_lock.acquire(False):
            return False
    else:
        _sync_lock.acquire(True)
    try:
        try:
            control.window.setProperty(_SIMKL_SYNC_BUSY_PROP, 'true')
            control.window.setProperty(_SIMKL_SYNC_BUSY_AT_PROP, '%.3f' % time.time())
        except Exception:
            pass
        status = _sync_simkl_watched_body(force_update=force_update)
        if not silent and status:
            control.infoDialog('Simkl Cache Refreshed.', sound=True)
        return bool(status)
    except Exception as e:
        log_utils.log('Simkl Watched Sync Failed: %s' % e, 1)
        return False
    finally:
        try:
            control.window.setProperty(_SIMKL_SYNC_BUSY_PROP, 'false')
            control.window.clearProperty(_SIMKL_SYNC_BUSY_AT_PROP)
        except Exception:
            pass
        try:
            _sync_lock.release()
        except Exception:
            pass


def _sync_simkl_watched_body(force_update=False):
    user = control.setting('simkl.user').strip() or 'simkl'
    if force_update:
        _bust_sync_cache()
        _store_cached_activities({})
    try:
        latest = call_simkl('/sync/activities', method='get')
    except Exception:
        return False
    if not latest:
        return False
    cached = _load_cached_activities()
    if not force_update and _activity_ts(latest.get('all', '')) <= _activity_ts(cached.get('all', '')):
        return True
    date_from = None if force_update else _simkl_date_from(cached)
    movies, shows = latest.get('movies', {}), latest.get('tv_shows', {})
    anime = latest.get('anime', {})
    cached_movies, cached_shows = cached.get('movies', {}), cached.get('tv_shows', {})
    cached_anime = cached.get('anime', {})
    need_movies = force_update or _activity_block_changed(movies, cached_movies, _SIMKL_MOVIE_WATCHED_ACTIVITY_KEYS)
    need_tv = force_update or _activity_block_changed(shows, cached_shows, _SIMKL_SHOW_WATCHED_ACTIVITY_KEYS) \
        or _activity_block_changed(anime, cached_anime, _SIMKL_SHOW_WATCHED_ACTIVITY_KEYS)
    movie_from = None if (not date_from or _activity_block_changed(movies, cached_movies, _SIMKL_MOVIE_FULL_SYNC_KEYS)) else date_from
    tv_from = None if (not date_from
        or _activity_block_changed(shows, cached_shows, _SIMKL_SHOW_FULL_SYNC_KEYS)
        or _activity_block_changed(anime, cached_anime, _SIMKL_SHOW_FULL_SYNC_KEYS)) else date_from
    if need_movies and need_tv and movie_from and tv_from and movie_from == tv_from:
        # Simkl Phase 2 multi-type: one request for movies + shows + anime.
        movie_delta, tv_delta, touched = _fetch_phase2_indicators(movie_from)
        existing_m = _read_sync_cache(syncMovies, user) or []
        _write_sync_cache(syncMovies, _merge_movie_indicators(existing_m, movie_delta), user)
        existing_t = _read_sync_cache(syncTVShows, user) or []
        _write_sync_cache(syncTVShows, _merge_tv_indicators(existing_t, tv_delta, touched), user)
    else:
        if need_movies:
            delta = _fetch_movie_indicators(date_from=movie_from)
            if movie_from:
                existing = _read_sync_cache(syncMovies, user) or []
                _write_sync_cache(syncMovies, _merge_movie_indicators(existing, delta), user)
            else:
                _write_sync_cache(syncMovies, delta, user)
        if need_tv:
            delta, touched = _fetch_tv_indicators(date_from=tv_from)
            if tv_from:
                existing = _read_sync_cache(syncTVShows, user) or []
                _write_sync_cache(syncTVShows, _merge_tv_indicators(existing, delta, touched), user)
            else:
                _write_sync_cache(syncTVShows, delta, user)
    _store_cached_activities(latest)
    return True


def _bust_sync_cache():
    user = control.setting('simkl.user').strip() or 'simkl'
    try:
        cache.remove(syncMovies, user)
    except Exception:
        pass
    try:
        cache.remove(syncTVShows, user)
    except Exception:
        pass


def refreshSimklCache(silent=False):
    try:
        ok = syncSimklWatched(silent=True, force_update=True)
        if not silent:
            control.infoDialog('Simkl Cache Refreshed.' if ok else 'Simkl Cache Refresh Failed.', sound=True)
    except Exception:
        if not silent:
            control.infoDialog('Simkl Cache Refresh Failed.', sound=True)
    try:
        control.refresh_list()
    except Exception:
        pass


def manager(name, imdb, tmdb, content):
    try:
        if not getSimklCredentialsInfo():
            return control.infoDialog('Authorise Simkl first.', sound=True)
        is_movie = content == 'movie'
        media_kind = 'movies' if is_movie else 'shows'
        ids = _list_ids(tmdb=tmdb, imdb=imdb)
        if not ids:
            return control.infoDialog('Missing IDs for Simkl Lists Manager.', sound=True, icon='ERROR')
        choices = []
        for status in _STATUSES:
            if is_movie and status in ('watching', 'hold'):
                continue
            label = _STATUS_LABELS[status]
            if _item_in_status(media_kind, status, ids):
                choices.append(('Remove from [B]%s[/B]' % label, 'remove', status))
            else:
                choices.append(('Add to [B]%s[/B]' % label, 'add', status))
        select = control.selectDialog([c[0] for c in choices], 'Simkl Lists Manager')
        if select < 0:
            return
        _, action, status = choices[select]
        label = _STATUS_LABELS.get(status, status)
        if action == 'add':
            if is_movie:
                post = {'movies': [{'to': status, 'ids': ids}]}
            else:
                post = {'shows': [{'to': status, 'ids': ids}]}
            result = call_simkl('/sync/add-to-list', data=post)
        else:
            if not _item_in_status(media_kind, status, ids):
                return control.infoDialog('Item is not in %s.' % label, heading=str(name), sound=True, icon='ERROR')
            if is_movie:
                post = {'movies': [{'ids': ids}]}
            else:
                post = {'shows': [{'ids': ids}]}
            result = call_simkl('/sync/history/remove', data=post)
        ok = result not in (None, False)
        if not ok:
            verb = 'add to' if action == 'add' else 'remove from'
            return control.infoDialog('Could not %s %s.' % (verb, label), heading=str(name), sound=True, icon='ERROR')
        message = ('Added to %s.' if action == 'add' else 'Removed from %s.') % label
        control.infoDialog(message, heading=str(name), sound=True, icon=control.infoLabel('ListItem.Icon'))
        try:
            refreshSimklCache(silent=True)
        except Exception:
            pass
    except Exception:
        control.infoDialog('Simkl Lists Manager failed.', heading=str(name), sound=True, icon='ERROR')
