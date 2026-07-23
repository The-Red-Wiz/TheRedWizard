# -*- coding: utf-8 -*-
"""Simkl account, status lists, watched sync, and manager for Gratis Red.

Adapted from Red Light's Simkl stack to the Exodus-style Gratis Red architecture.
"""
from __future__ import absolute_import

import json
import re
import time
from threading import Lock

import requests
from six.moves.urllib_parse import urljoin

from resources.lib.modules import cache
from resources.lib.modules import control
from resources.lib.modules import log_utils

BASE_URL = 'https://api.simkl.com'
OAUTH_PIN_URL = 'https://api.simkl.com/oauth/pin'
SIMKL_APP_NAME = 'plugin.video.gratisred'
# Gratis Red Simkl app (unique client ID — not shared with Red Light).
SIMKL_CLIENT_ID = '7508fd47a5237d06eb9b27863e744763c278bc8b35c6c24c336ebbb5d66318bd'
SIMKL_TRAKT_IMPORT_URL = 'https://simkl.com/apps/import/trakt/'

_STATUSES = ('plantowatch', 'watching', 'completed', 'hold', 'dropped')
_STATUS_LABELS = {
    'plantowatch': 'Plan to Watch',
    'watching': 'Watching',
    'completed': 'Completed',
    'hold': 'On Hold',
    'dropped': 'Dropped',
}

_request_lock = Lock()
_last_request_time = 0.0


def _throttle():
    global _last_request_time
    with _request_lock:
        elapsed = time.time() - _last_request_time
        if elapsed < 1.0:
            control.sleep(int((1.0 - elapsed) * 1000) + 50)
        _last_request_time = time.time()


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
    """If Resume Point Source points at an unauthorised service, fall back."""
    from resources.lib.modules import trakt
    val = control.setting('bookmarks.source') or '0'
    if val == '1' and not trakt.getTraktCredentialsInfo():
        set_bookmarks_source('2' if getSimklCredentialsInfo() else '0')
    elif val == '2' and not getSimklCredentialsInfo():
        set_bookmarks_source('1' if trakt.getTraktCredentialsInfo() else '0')
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


def choose_bookmarks_source(reopen_settings=False):
    ensure_bookmarks_valid()
    value = _provider_select('Resume Point Source', control.setting('bookmarks.source') or '0')
    if value is None:
        if reopen_settings:
            control.reopen_settings_category(1, 0)
        return
    set_bookmarks_source(value, notify=True)
    control.sleep(350)
    if reopen_settings:
        control.reopen_settings_category(1, 0)


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
        info = call_simkl('/users/settings', method='get')
        user = 'Simkl User'
        if info and isinstance(info, dict) and info.get('user'):
            user = str(info['user'].get('name') or info['user'].get('login') or user)
        control.setSetting('simkl.user', user)
        control.setSetting('simkl.authed', 'yes')
        if control.yesnoDialog('Set Simkl as your Watched Indicators provider?', heading='Watched Status Provider'):
            set_watched_provider('2', notify=True)
        from resources.lib.modules import trakt
        if trakt.getTraktCredentialsInfo() and control.yesnoDialog(
                'Open Simkl\'s official Trakt import page? (import completes in a browser)',
                heading='Import Trakt to Simkl'):
            try:
                control.openBrowser(SIMKL_TRAKT_IMPORT_URL)
            except Exception:
                auth_utils.copy2clip(SIMKL_TRAKT_IMPORT_URL)
                control.infoDialog('Import link copied to clipboard.', sound=True)
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
    path = '/sync/all-items/%s/%s?extended=ids_only' % (media_kind, status)
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


def directory_movies(status):
    """Build Gratis Red movie list items for a Simkl status shelf."""
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
        })
    return out


def directory_tvshows(status):
    """Build Gratis Red TV show list items for a Simkl status shelf."""
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
        })
    return out


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
        data = call_simkl('/sync/all-items/movies/completed?extended=full', method='get') or {}
        rows = data.get('movies', data if isinstance(data, list) else [])
        indicators = []
        for item in rows:
            try:
                movie = item.get('movie', item)
                imdb = movie.get('ids', {}).get('imdb')
                if not imdb:
                    continue
                indicators.append(_normalize_imdb(imdb))
            except Exception:
                pass
        return indicators
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
        path = '/sync/all-items/shows?extended=full&episode_watched_at=yes&include_all_episodes=yes'
        data = call_simkl(path, method='get') or {}
        rows = data.get('shows', data if isinstance(data, list) else [])
        anime = call_simkl('/sync/all-items/anime?extended=full&episode_watched_at=yes&include_all_episodes=yes', method='get') or {}
        anime_rows = anime.get('anime', anime.get('shows', anime if isinstance(anime, list) else []))
        indicators = []
        for item in list(rows) + list(anime_rows):
            try:
                show = item.get('show') or item.get('anime') or item
                tmdb = show.get('ids', {}).get('tmdb')
                if not tmdb:
                    continue
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
                        try:
                            epnum = int(ep.get('number', ep.get('episode')))
                        except Exception:
                            continue
                        watched.append((snum, epnum))
                if not aired:
                    aired = len(watched)
                indicators.append((str(tmdb), int(aired), watched))
            except Exception:
                pass
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


def syncSimklWatched(silent=True):
    """Refresh Simkl watched indicator caches (movies + TV)."""
    if not getSimklCredentialsInfo():
        return False
    try:
        cachesyncMovies(timeout=0)
        cachesyncTVShows(timeout=0)
        if not silent:
            control.infoDialog('Simkl Cache Refreshed.', sound=True)
        return True
    except Exception as e:
        log_utils.log('Simkl Watched Sync Failed: %s' % e, 1)
        return False


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


def refreshSimklCache():
    _bust_sync_cache()
    try:
        cachesyncMovies(timeout=0)
        cachesyncTVShows(timeout=0)
        control.infoDialog('Simkl Cache Refreshed.', sound=True)
    except Exception:
        control.infoDialog('Simkl Cache Refresh Failed.', sound=True)
    try:
        control.refresh()
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
            return control.infoDialog('Missing IDs for Simkl Manager.', sound=True, icon='ERROR')
        choices = []
        for status in _STATUSES:
            if is_movie and status in ('watching', 'hold'):
                continue
            label = _STATUS_LABELS[status]
            if _item_in_status(media_kind, status, ids):
                choices.append(('Remove from [B]%s[/B]' % label, 'remove', status))
            else:
                choices.append(('Add to [B]%s[/B]' % label, 'add', status))
        select = control.selectDialog([c[0] for c in choices], 'Simkl Manager')
        if select < 0:
            return
        _, action, status = choices[select]
        if action == 'add':
            if is_movie:
                post = {'movies': [{'to': status, 'ids': ids}]}
            else:
                post = {'shows': [{'to': status, 'ids': ids}]}
            result = call_simkl('/sync/add-to-list', data=post)
        else:
            if not _item_in_status(media_kind, status, ids):
                label = _STATUS_LABELS.get(status, status)
                return control.infoDialog('Item is not in %s.' % label, heading=str(name), sound=True, icon='ERROR')
            if is_movie:
                post = {'movies': [{'ids': ids}]}
            else:
                post = {'shows': [{'ids': ids}]}
            result = call_simkl('/sync/history/remove', data=post)
        ok = result not in (None, False)
        icon = control.infoLabel('ListItem.Icon') if ok else 'ERROR'
        control.infoDialog('Simkl Manager', heading=str(name), sound=True, icon=icon)
        if ok:
            try:
                refreshSimklCache()
            except Exception:
                pass
    except Exception:
        control.infoDialog('Simkl Manager', heading=str(name), sound=True, icon='ERROR')
