# -*- coding: utf-8 -*-
"""MDBList account, lists, watched sync, and manager for Gratis Red.

Simkl-shaped (Fen directories / settings.xml). Behaviour and API from Red Light
mdblist_api (device OAuth, sync/watched, watchlist, library, dropped, playback,
calendar, static lists). Indicators value 3.
"""
from __future__ import absolute_import

import json
import re
import time
from datetime import timedelta

import requests

from resources.lib.modules import cache
from resources.lib.modules import control
from resources.lib.modules import log_utils

BASE_URL = 'https://api.mdblist.com/%s'
_OAUTH_DEVICE_URL = 'https://api.mdblist.com/oauth/device-authorization/'
_OAUTH_TOKEN_URL = 'https://api.mdblist.com/oauth/token/'
# Gratis Red MDBList app (unique client ID — not shared with Red Light).
MDBLIST_CLIENT_ID = 'YhnyzeM1g05NEzuSvBEZx4N9KnActYThYCzWL7vy'
_ACTIVITIES_SETTING = 'mdblist.activities_json'
_LIST_CACHE_HOURS = 24
_WATCHED_CACHE_HOURS = 24
MAX_PAGES = 250

session = requests.Session()
session.mount('https://api.mdblist.com', requests.adapters.HTTPAdapter(pool_maxsize=20))


def _client_id():
    value = (control.setting('mdblist.client') or '').strip()
    return value or MDBLIST_CLIENT_ID


def _token():
    return (control.setting('mdblist.token') or '').strip()


def _refresh_token():
    return (control.setting('mdblist.refresh') or '').strip()


def _oauth_active():
    refresh = _refresh_token()
    return refresh not in ('', '0', 'empty_setting', 'None')


def getMdblistCredentialsInfo():
    return bool(_token() and _token() not in ('0', 'empty_setting') and (control.setting('mdblist.user') or '').strip())


def getMdblistIndicatorsInfo():
    from resources.lib.modules import simkl
    return simkl.getIndicatorsProvider() == 'mdblist'


def _normalize_imdb(imdb):
    if not imdb or imdb in ('0', 'None'):
        return '0'
    imdb = str(imdb)
    if not imdb.startswith('tt'):
        imdb = 'tt' + re.sub(r'[^0-9]', '', imdb)
    return imdb or '0'


def _first_int(*values):
    for value in values:
        if value in (None, '', 'None', 0, '0'):
            continue
        try:
            return int(value)
        except Exception:
            continue
    return None


def call_mdblist(path, params=None, json_data=None, method=None, _retried=False):
    params = dict(params or {})
    token = _token()
    if not token or token in ('0', 'empty_setting'):
        return None
    headers = {}
    if _oauth_active():
        headers['Authorization'] = 'Bearer %s' % token
    else:
        params['apikey'] = token
    try:
        response = session.request(
            method or 'get', BASE_URL % path.lstrip('/'),
            params=params, json=json_data, headers=headers, timeout=30)
        if response.status_code == 401 and _oauth_active() and not _retried:
            if _refresh_access_token():
                return call_mdblist(path, params=params, json_data=json_data, method=method, _retried=True)
        if not response.ok:
            log_utils.log('MDBList HTTP %s %s' % (response.status_code, path), 1)
            return None
        if 'json' in (response.headers.get('Content-Type') or ''):
            result = response.json() if response.text else {}
        else:
            result = response.text
        if isinstance(result, list):
            wrapped = {'items': result, 'pagination': {'has_more': response.headers.get('X-Has-More') == 'true'}}
            next_cursor = response.headers.get('X-Next-Cursor')
            if next_cursor:
                wrapped['pagination']['next_cursor'] = next_cursor
            return wrapped
        return result
    except Exception as e:
        log_utils.log('MDBList Error: %s' % e, 1)
        return None


def _refresh_access_token():
    refresh = _refresh_token()
    if not refresh or refresh in ('0', 'empty_setting'):
        return False
    try:
        response = session.post(_OAUTH_TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh,
            'client_id': _client_id(),
        }, timeout=20)
        if response.status_code != 200:
            return False
        data = response.json() or {}
        access = data.get('access_token')
        if not access:
            return False
        control.setSetting('mdblist.token', access)
        if data.get('refresh_token'):
            control.setSetting('mdblist.refresh', data.get('refresh_token'))
        return True
    except Exception:
        return False


def _get_mdbl_paginated_list(url):
    params = {'limit': 1000}
    items = {'movies': [], 'shows': [], 'seasons': [], 'episodes': [], 'items': []}
    try:
        for _ in range(MAX_PAGES):
            result = call_mdblist(url, params=params)
            if not isinstance(result, dict):
                return None
            for key in items:
                if isinstance(result.get(key), list):
                    items[key].extend(result[key])
            pagination = result.get('pagination') or {}
            if not pagination.get('has_more'):
                break
            next_cursor = pagination.get('next_cursor')
            if not next_cursor:
                break
            params['cursor'] = next_cursor
    except Exception:
        return None
    return items


def _tmdb_from_ids(ids, block=None):
    for source in (ids, block or {}):
        if not isinstance(source, dict):
            continue
        for key in ('tmdb', 'tmdb_id', 'tmdbid', 'id'):
            value = source.get(key)
            if value in (None, '', 'None', 0, '0'):
                continue
            try:
                return str(int(value))
            except Exception:
                continue
    return None


def _ids_from_item(item, media_kind):
    nested = 'movie' if media_kind in ('movie', 'movies') else 'show'
    block = item.get(nested) if isinstance(item.get(nested), dict) else item
    if not isinstance(block, dict):
        block = {}
    ids = block.get('ids') if isinstance(block.get('ids'), dict) else {}
    merged = dict(ids)
    for src, dst in (
        ('tmdb', 'tmdb'), ('tmdb_id', 'tmdb'), ('tmdbid', 'tmdb'),
        ('imdb', 'imdb'), ('imdb_id', 'imdb'), ('imdbid', 'imdb'),
        ('tvdb', 'tvdb'), ('tvdb_id', 'tvdb'), ('tvdbid', 'tvdb'),
    ):
        if block.get(src) not in (None, '', 'None', 0, '0') and dst not in merged:
            merged[dst] = block.get(src)
    tmdb = _tmdb_from_ids(merged, block)
    return merged, block, tmdb


def _item_media_kind(item):
    if not isinstance(item, dict):
        return 'movie'
    mediatype = str(item.get('mediatype') or item.get('media_type') or item.get('type') or '').lower()
    if mediatype in ('episode', 'episodes'):
        return 'episode'
    if mediatype in ('show', 'shows', 'tvshow', 'tv', 'series'):
        return 'show'
    if mediatype in ('movie', 'movies'):
        return 'movie'
    if item.get('show') or item.get('season') or item.get('episode'):
        return 'show'
    return 'movie'


def _directory_row(item, media_kind):
    ids, block, tmdb = _ids_from_item(item, media_kind)
    if not tmdb:
        return None
    title = block.get('title') or item.get('title') or 'Unknown'
    year = block.get('year') or block.get('release_year') or item.get('year') or '0'
    try:
        year = re.sub(r'[^0-9]', '', str(year)) or '0'
    except Exception:
        year = '0'
    imdb = _normalize_imdb(ids.get('imdb') or block.get('imdb_id'))
    tvdb = str(ids.get('tvdb') or block.get('tvdb_id') or '0')
    collected = item.get('watchlist_at') or item.get('collected_at') or item.get('added') or ''
    return {
        'title': title, 'originaltitle': title, 'year': year,
        'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'next': '',
        'paused_at': '0', 'collected_at': collected,
    }


def _device_auth_url(device_data):
    verification_url = (device_data.get('verification_uri') or device_data.get('verification_url')
                        or 'https://mdblist.com/oauth/device/').rstrip('/')
    user_code = device_data.get('user_code', '')
    if user_code:
        return '%s?code=%s' % (verification_url, user_code)
    return verification_url


def _username_from_profile(info, allow_display_name=True):
    if not isinstance(info, dict):
        return ''
    nested = info.get('user') if isinstance(info.get('user'), dict) else {}
    keys = ('username', 'user_name', 'login')
    if allow_display_name:
        keys = keys + ('name',)
    for source in (info, nested):
        for key in keys:
            value = source.get(key)
            if value not in (None, '', 'None', 'MDBList User'):
                return str(value)
    return ''


def _parse_json_body(response):
    text = response.text if response is not None else ''
    if not text:
        return None
    ctype = (response.headers.get('Content-Type') or '').lower()
    if 'json' in ctype or text.lstrip()[:1] in '{[':
        try:
            return response.json()
        except Exception:
            return None
    return None


def _fetch_user_profile(access_token):
    """GET /user — pass the new token so we do not race Addon.setSetting."""
    headers = {
        'Authorization': 'Bearer %s' % access_token,
        'Accept': 'application/json',
    }
    try:
        response = session.get(BASE_URL % 'user', headers=headers, timeout=20)
        if response.status_code == 200:
            data = _parse_json_body(response)
            if isinstance(data, dict):
                return data
        log_utils.log('MDBList HTTP %s user' % response.status_code, 1)
    except Exception as e:
        log_utils.log('MDBList Error: %s' % e, 1)
    return None


def _username_from_lists(access_token):
    headers = {
        'Authorization': 'Bearer %s' % access_token,
        'Accept': 'application/json',
    }
    try:
        response = session.get(BASE_URL % 'lists/user', headers=headers, timeout=20)
        data = _parse_json_body(response) if response is not None and response.ok else None
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('items') or []
        for item in items:
            user = _username_from_profile(item, allow_display_name=False)
            if user:
                return user
    except Exception:
        pass
    return ''


def authMdblist(reopen_settings=False):
    from resources.lib.modules import auth_utils
    progress = None
    try:
        if getMdblistCredentialsInfo():
            control.infoDialog('MDBList is already authorised. Use Revoke MDBList Account to sign out.', sound=True)
            return
        progress = auth_utils.auth_progress_dialog('MDBList Authorise', '')
        progress.update('Connecting to MDBList...')
        try:
            pin = session.post(_OAUTH_DEVICE_URL, data={'client_id': _client_id(), 'scope': 'write'}, timeout=20).json()
        except Exception:
            pin = None
        if not pin or not pin.get('user_code'):
            control.infoDialog('MDBList Authorisation Failed.', sound=True)
            return
        user_code = str(pin.get('user_code', ''))
        device_code = pin.get('device_code')
        expires_in = int(pin.get('expires_in') or 300)
        interval = max(int(pin.get('interval') or 5), 1)
        auth_url = _device_auth_url(pin)
        progress.update('Preparing QR code...')
        qr_code = auth_utils.make_qrcode(auth_url) or ''
        short_url = auth_utils.make_tinyurl(auth_url)
        auth_utils.copy2clip(auth_url)
        insert = '[CR]OR visit [B]%s[/B]' % short_url if short_url else ''
        verify_display = (pin.get('verification_uri') or pin.get('verification_url')
                          or 'mdblist.com/oauth/device').replace('https://', '')
        content = ('Enter [B]%s[/B] at [B]%s[/B][CR]OR scan the [B]QR Code[/B][CR]'
                   'Link copied to clipboard%s[CR][CR]Waiting for authorisation...'
                   % (user_code, verify_display, insert))
        progress.update(content, qr_path=qr_code)
        token_result = None
        start = time.time()
        while not progress.iscanceled() and (time.time() - start) < expires_in:
            if auth_utils.auth_progress_wait(progress, interval):
                break
            try:
                resp = session.post(_OAUTH_TOKEN_URL, data={
                    'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                    'device_code': device_code,
                    'client_id': _client_id(),
                }, timeout=20)
                if resp.status_code == 200:
                    token_result = resp.json()
                    break
            except Exception:
                pass
        canceled = progress.iscanceled()
        auth_utils.close_auth_progress_dialog(progress)
        progress = None
        access = (token_result or {}).get('access_token')
        if canceled or not access:
            control.infoDialog('MDBList Authorisation Canceled.' if canceled else 'MDBList Authorisation Failed.', sound=True)
            return
        control.setSetting('mdblist.token', access)
        control.setSetting('mdblist.refresh', (token_result or {}).get('refresh_token') or '0')
        # Profile is GET /user (docs). Pass the new token explicitly so we do not
        # race Addon.setSetting before Bearer auth is readable for the follow-up call.
        info = _fetch_user_profile(access) or {}
        user = _username_from_profile(info) or _username_from_lists(access) or 'MDBList User'
        control.setSetting('mdblist.user', user)
        if control.yesnoDialog('Set MDBList as your Watched Indicators provider?', heading='Watched Status Provider'):
            from resources.lib.modules import simkl
            simkl.set_watched_provider('3', notify=True)
        try:
            cachesyncMovies(timeout=0)
            cachesyncTVShows(timeout=0)
        except Exception:
            pass
        control.infoDialog('MDBList Account Authorised.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('MDBList Authorisation Failed.', sound=True)
    finally:
        if progress is not None:
            auth_utils.close_auth_progress_dialog(progress)


def revokeMdblist(reopen_settings=False):
    if not getMdblistCredentialsInfo():
        control.infoDialog('No MDBList account is authorised.', sound=True)
        return
    try:
        control.setSetting('mdblist.user', '')
        control.setSetting('mdblist.token', '')
        control.setSetting('mdblist.refresh', '')
        _store_cached_activities({})
        from resources.lib.modules import simkl
        simkl.fallback_indicators_on_revoke('mdblist')
        _bust_caches()
        control.infoDialog('MDBList Account Revoked.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('MDBList Revoke Failed.', sound=True)


def _load_cached_activities():
    raw = (control.setting(_ACTIVITIES_SETTING) or '').strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _store_cached_activities(latest):
    try:
        control.setSetting(_ACTIVITIES_SETTING, json.dumps(latest or {}))
    except Exception:
        pass


def _bust_caches():
    try:
        cur = cache._get_connection_cursor()
        for prefix in (
            'syncMovies', 'syncTVShows', '_personal_items', '_dropped_tmdb_ids_raw',
            '_playback_items', '_fetch_lists', '_list_payload', '_calendar_fetch',
        ):
            cur.execute('DELETE FROM %s WHERE key LIKE ?' % cache.cache_table, [prefix + '%'])
        cur.connection.commit()
    except Exception:
        pass


def _personal_items(url, media_kind):
    result = _get_mdbl_paginated_list(url)
    if not isinstance(result, dict):
        return []
    key = 'movies' if media_kind in ('movie', 'movies') else 'shows'
    rows = list(result.get(key) or [])
    if not rows:
        want = 'movie' if key == 'movies' else 'show'
        for item in result.get('items') or []:
            if _item_media_kind(item) == want:
                rows.append(item)
    out = []
    for item in rows:
        row = _directory_row(item, media_kind)
        if row:
            out.append(row)
    return out


def directory_from_url(url, media):
    """Map movies&url=mdblist_* / tvshows&url=mdblist_* to directory rows."""
    key = str(url or '')
    media_kind = 'movies' if media in ('movie', 'movies') else 'tvshows'
    if key == 'mdblist_watchlist':
        return directory_watchlist(media_kind)
    if key == 'mdblist_collection':
        return directory_collection(media_kind)
    if key == 'mdblist_dropped':
        return directory_dropped(media_kind)
    if key == 'mdblist_watched':
        return directory_watched(media_kind)
    if key == 'mdblist_ondeck':
        return directory_playback_movies() if media_kind == 'movies' else []
    if key.startswith('mdblist_list_'):
        rest = key[len('mdblist_list_'):]
        list_type, _sep, list_id = rest.partition('_')
        if list_type not in ('user', 'external') or not list_id:
            list_type, list_id = 'user', rest
        return directory_list(list_id, media_kind, list_type)
    return []


def directory_watchlist(media):
    from resources.lib.modules import shelf_sort
    items = cache.get(_personal_items, _LIST_CACHE_HOURS, 'watchlist/items', media) or []
    return shelf_sort.sort_items(items, 'mdblist', media, 'watchlist', sortable=shelf_sort.MDBLIST_SORTABLE)


def directory_collection(media):
    from resources.lib.modules import shelf_sort
    items = cache.get(_personal_items, _LIST_CACHE_HOURS, 'sync/collection', media) or []
    return shelf_sort.sort_items(items, 'mdblist', media, 'collection', sortable=shelf_sort.MDBLIST_SORTABLE)


def _dropped_tmdb_ids_raw():
    result = _get_mdbl_paginated_list('sync/dropped')
    if not isinstance(result, dict):
        return []
    rows = list(result.get('shows') or []) + list(result.get('items') or [])
    ids, seen = [], set()
    for item in rows:
        _ids, _block, tmdb = _ids_from_item(item, 'shows')
        if not tmdb:
            continue
        try:
            tmdb_i = int(tmdb)
        except Exception:
            continue
        if tmdb_i in seen:
            continue
        seen.add(tmdb_i)
        ids.append(tmdb_i)
    return ids


def dropped_tmdb_ids():
    return set(str(i) for i in (cache.get(_dropped_tmdb_ids_raw, _LIST_CACHE_HOURS) or []))


def directory_dropped(media):
    from resources.lib.modules import shelf_sort
    if media in ('movie', 'movies'):
        return []
    out = []
    for tmdb in cache.get(_dropped_tmdb_ids_raw, _LIST_CACHE_HOURS) or []:
        out.append({
            'title': 'Unknown', 'originaltitle': 'Unknown', 'year': '0',
            'imdb': '0', 'tmdb': str(tmdb), 'tvdb': '0', 'next': '',
            'paused_at': '0', 'collected_at': '',
        })
    return shelf_sort.sort_items(out, 'mdblist', 'tvshows', 'dropped', sortable=shelf_sort.MDBLIST_SORTABLE)


def directory_watched(media):
    from resources.lib.modules import shelf_sort
    watched = _get_mdbl_paginated_list('sync/watched')
    if not isinstance(watched, dict):
        return []
    out = []
    if media in ('movie', 'movies'):
        for item in watched.get('movies') or []:
            row = _directory_row(item, 'movies')
            if row:
                out.append(row)
        return shelf_sort.sort_items(out, 'mdblist', 'movies', 'watched', sortable=shelf_sort.MDBLIST_SORTABLE)
    seen = set()
    for item in watched.get('episodes') or []:
        show = (item.get('episode') or {}).get('show') or item.get('show') or item
        fake = {'show': show} if 'ids' in (show or {}) or show.get('tmdb') else item
        row = _directory_row(fake, 'shows')
        if not row or row['tmdb'] in seen:
            continue
        seen.add(row['tmdb'])
        out.append(row)
    return shelf_sort.sort_items(out, 'mdblist', 'tvshows', 'watched', sortable=shelf_sort.MDBLIST_SORTABLE)


def _playback_items():
    result = _get_mdbl_paginated_list('sync/playback')
    if result is None:
        return None
    return result.get('items') or []


def get_playback(media_filter=None):
    items = cache.get(_playback_items, 1) or []
    if media_filter == 'movies':
        return [i for i in items if isinstance(i, dict) and (i.get('type') or 'movie') == 'movie']
    if media_filter == 'episodes':
        return [i for i in items if isinstance(i, dict) and i.get('type') == 'episode']
    return items if isinstance(items, list) else []


def directory_playback_movies():
    out = []
    for item in get_playback('movies'):
        try:
            if control.playback_progress_stale(item):
                continue
            movie = item.get('movie') or item
            ids = movie.get('ids') or {}
            title = movie.get('title') or 'Unknown'
            year = movie.get('year') or '0'
            try:
                year = re.sub(r'[^0-9]', '', str(year)) or '0'
            except Exception:
                year = '0'
            progress = item.get('progress')
            out.append({
                'title': title, 'originaltitle': title, 'year': year,
                'imdb': _normalize_imdb(ids.get('imdb')),
                'tmdb': str(ids.get('tmdb') or movie.get('tmdb') or '0'),
                'tvdb': '0', 'next': '',
                'paused_at': str(item.get('paused_at') or '0'),
                'progress': progress,
            })
        except Exception:
            pass
    return out


def playback_episode_items():
    out = []
    for item in get_playback('episodes'):
        try:
            if control.playback_progress_stale(item):
                continue
            show = item.get('show') or {}
            ep = item.get('episode') or {}
            ids = show.get('ids') or {}
            season = ep.get('season')
            episode = ep.get('number') or ep.get('episode')
            if season is None or episode is None:
                continue
            out.append({
                'title': ep.get('title') or show.get('title') or 'Unknown',
                'season': '%01d' % int(season),
                'episode': '%01d' % int(episode),
                'tvshowtitle': show.get('title') or 'Unknown',
                'year': str(show.get('year') or '0'),
                'premiered': '0', 'status': '0', 'studio': [], 'genre': [],
                'duration': '0', 'rating': '0', 'votes': '0', 'mpaa': '0', 'plot': '0',
                'imdb': _normalize_imdb(ids.get('imdb')),
                'tvdb': str(ids.get('tvdb') or '0'),
                'tmdb': str(ids.get('tmdb') or show.get('tmdb') or '0'),
                'poster': '0', 'thumb': '0',
                'paused_at': str(item.get('paused_at') or '0'),
                'watched_at': '0',
                'progress': item.get('progress'),
            })
        except Exception:
            pass
    return out


def progress_seeds():
    if not getMdblistCredentialsInfo():
        return []
    dropped = dropped_tmdb_ids()
    indicators = cachesyncTVShows(timeout=720) or []
    out = []
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
        out.append({
            'tmdb': tmdb, 'imdb': '0', 'tvdb': '0',
            'tvshowtitle': '', 'year': '0', 'studio': [], 'duration': '0',
            'mpaa': '0', 'status': '0', 'genre': [],
            'snum': str(last[0]), 'enum': str(last[1]),
            '_last_watched': '0',
        })
    return out


def _calendar_fetch(api_start, api_end):
    result = call_mdblist('calendar/events', params={'limit': 1000, 'start': api_start, 'end': api_end})
    if not result:
        return []
    if isinstance(result, dict):
        events = result.get('events')
        if not isinstance(events, list):
            events = result.get('items')
    else:
        events = result
    if not isinstance(events, list):
        return []
    data = []
    seen = set()
    for item in events:
        try:
            if not isinstance(item, dict):
                continue
            item_type = item.get('type')
            if item_type and item_type != 'episode':
                continue
            show_tmdb = item.get('show_tmdb') or item.get('show_id')
            season, episode = item.get('season_number'), item.get('episode_number')
            start = item.get('start')
            if not show_tmdb or season is None or episode is None or not start:
                continue
            if int(season) < 1:
                continue
            tmdb = str(int(show_tmdb))
            premiered = str(start)[:10]
            key = (tmdb, int(season), int(episode), premiered)
            if key in seen:
                continue
            seen.add(key)
            title = item.get('title') or 'Unknown'
            data.append({
                'title': title,
                'season': '%01d' % int(season),
                'episode': '%01d' % int(episode),
                'tvshowtitle': title,
                'year': premiered[:4] if premiered else '0',
                'premiered': premiered,
                'status': '0', 'studio': [], 'genre': [], 'duration': '0',
                'rating': '0', 'votes': '0', 'mpaa': '0', 'plot': '0',
                'imdb': '0', 'tvdb': '0', 'tmdb': tmdb,
                'poster': '0', 'thumb': '0', 'paused_at': '0', 'watched_at': '0',
            })
        except Exception:
            continue
    return data


def calendar_episode_items():
    """User calendar events (MDBList /calendar/events)."""
    from datetime import datetime
    try:
        current = datetime.utcnow().date()
    except Exception:
        current = datetime.now().date()
    api_start = (current - timedelta(days=14)).strftime('%Y-%m-%d')
    api_end = (current + timedelta(days=14)).strftime('%Y-%m-%d')
    items = cache.get(_calendar_fetch, 6, api_start, api_end) or []
    try:
        items = sorted(items, key=lambda k: k.get('premiered') or '', reverse=False)
    except Exception:
        pass
    limit = str(control.setting('trakt.item.limit') or '100')
    try:
        items = items[:int(limit)]
    except Exception:
        pass
    return items


def _normalize_list_response(result):
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ('items', 'lists', 'liked', 'data', 'results'):
            if isinstance(result.get(key), list):
                return result[key]
    return []


def _expand_list_entries(lists):
    expanded = []
    for item in lists or []:
        if not isinstance(item, dict):
            continue
        list_id = item.get('id')
        if list_id not in (None, '', 0, '0'):
            expanded.append(item)
            continue
        ids = item.get('ids') or []
        if not isinstance(ids, (list, tuple)):
            continue
        for lid in ids:
            if lid in (None, '', 0, '0'):
                continue
            row = dict(item)
            row['id'] = lid
            expanded.append(row)
    return expanded


def _list_is_dynamic(item):
    if not isinstance(item, dict):
        return False
    if item.get('dynamic') in (True, 1, '1', 'true', 'True'):
        return True
    kind = str(item.get('type') or item.get('list_type') or '').lower()
    return kind in ('dynamic', 'ai', 'smart')


def _list_is_static(item):
    if not isinstance(item, dict):
        return False
    if item.get('source'):
        return False
    return not _list_is_dynamic(item)


def _fetch_lists(path):
    result = call_mdblist(path)
    return _expand_list_entries(_normalize_list_response(result))


def my_lists():
    return cache.get(_fetch_lists, _LIST_CACHE_HOURS, 'lists/user') or []


def liked_lists():
    return cache.get(_fetch_lists, _LIST_CACHE_HOURS, 'lists/liked') or []


def top_lists():
    return cache.get(_fetch_lists, _LIST_CACHE_HOURS, 'lists/top') or []


def static_lists():
    lists = [i for i in my_lists() if _list_is_static(i)]
    lists.sort(key=lambda k: (k.get('name') or '').lower())
    return lists


def _list_payload(list_type, list_id):
    if list_type == 'external':
        url = 'external/lists/%s/items?unified=true' % list_id
    else:
        url = 'lists/%s/items?unified=true' % list_id
    result = _get_mdbl_paginated_list(url)
    return result if isinstance(result, dict) else {}


def directory_list(list_id, media, list_type='user'):
    from resources.lib.modules import shelf_sort
    payload = cache.get(_list_payload, _LIST_CACHE_HOURS, list_type, list_id) or {}
    key = 'movies' if media in ('movie', 'movies') else 'shows'
    rows = list(payload.get(key) or [])
    want = 'movie' if key == 'movies' else 'show'
    for item in payload.get('items') or []:
        if _item_media_kind(item) == want:
            rows.append(item)
    out = []
    for item in rows:
        row = _directory_row(item, media)
        if row:
            out.append(row)
    shelf = shelf_sort.personal_shelf_key(list_id)
    return shelf_sort.sort_items(out, 'mdblist', 'movies' if key == 'movies' else 'tvshows', shelf)


def user_list_directory(kind, media_action):
    """Folder rows for My / Liked / Popular MDBLists."""
    if kind == 'liked':
        lists = liked_lists()
    elif kind == 'top':
        lists = top_lists()
    else:
        lists = my_lists()
    out = []
    for item in lists:
        try:
            list_id = item.get('id')
            name = item.get('name') or item.get('title') or 'MDBList'
            if list_id in (None, '', 0, '0'):
                continue
            list_type = 'external' if kind in ('liked', 'top') else 'user'
            url = 'mdblist_list_%s_%s' % (list_type, list_id)
            out.append({
                'name': name,
                'url': url,
                'image': 'mdblist.png',
                'action': media_action,
                'sort_provider': 'mdblist',
                'sort_key': 'ulist_%s' % list_id,
            })
        except Exception:
            continue
    return out


def choose_list_sort(media, status, label=None):
    from resources.lib.modules import shelf_sort
    shelf_sort.choose_list_sort('mdblist', media, status, sortable=shelf_sort.MDBLIST_SORTABLE, heading_label=label)


def syncMovies(user):
    try:
        if not getMdblistCredentialsInfo():
            return []
        watched = _get_mdbl_paginated_list('sync/watched')
        if not isinstance(watched, dict):
            return []
        indicators = []
        for item in watched.get('movies') or []:
            ids, block, _tmdb = _ids_from_item(item, 'movies')
            imdb = _normalize_imdb(ids.get('imdb') or block.get('imdb_id'))
            if imdb and imdb != '0':
                indicators.append(imdb)
        return indicators
    except Exception:
        return []


def cachesyncMovies(timeout=0):
    return cache.get(syncMovies, timeout, control.setting('mdblist.user').strip() or 'mdblist')


def timeoutsyncMovies():
    try:
        return cache.timeout(syncMovies, control.setting('mdblist.user').strip() or 'mdblist') or 0
    except Exception:
        return 0


def syncTVShows(user):
    try:
        if not getMdblistCredentialsInfo():
            return []
        watched = _get_mdbl_paginated_list('sync/watched')
        if not isinstance(watched, dict):
            return []
        by_show = {}
        for item in watched.get('episodes') or []:
            try:
                ep = item.get('episode') or {}
                show = ep.get('show') or item.get('show') or {}
                ids = show.get('ids') if isinstance(show.get('ids'), dict) else {}
                tmdb = str(ids.get('tmdb') or show.get('tmdb') or '0')
                if tmdb in ('0', '', 'None'):
                    continue
                season = ep.get('season')
                number = ep.get('number') or ep.get('episode')
                if season is None or number is None:
                    continue
                if int(season) < 1:
                    continue
                bucket = by_show.setdefault(tmdb, set())
                bucket.add((int(season), int(number)))
            except Exception:
                continue
        indicators = []
        for tmdb, pairs in by_show.items():
            watched_pairs = sorted(pairs)
            # MDBList has no aired-total; keep show overlays from looking fully watched
            # and still allow Continue Watching (progress_seeds skips len >= aired).
            aired = len(watched_pairs) + 1
            indicators.append((tmdb, aired, watched_pairs))
        return indicators
    except Exception:
        return []


def cachesyncTVShows(timeout=0):
    return cache.get(syncTVShows, timeout, control.setting('mdblist.user').strip() or 'mdblist')


def timeoutsyncTVShows():
    try:
        return cache.timeout(syncTVShows, control.setting('mdblist.user').strip() or 'mdblist') or 0
    except Exception:
        return 0


def syncSeason(imdb, tmdb=None):
    try:
        rows = cachesyncTVShows(timeout=720) or []
        tmdb_s = str(tmdb or '0')
        row = None
        if tmdb_s not in ('0', '', 'None'):
            for item in rows:
                try:
                    if str(item[0]) == tmdb_s:
                        row = item
                        break
                except Exception:
                    continue
        if row is None:
            return []
        watched = row[2] or []
        by_season = {}
        for pair in watched:
            try:
                season_n, episode_n = int(pair[0]), int(pair[1])
            except Exception:
                continue
            by_season.setdefault(season_n, set()).add(episode_n)
        fully = []
        for season_n, episodes in by_season.items():
            if not episodes:
                continue
            if min(episodes) == 1 and len(episodes) >= max(episodes):
                fully.append('%01d' % season_n)
        return fully
    except Exception:
        return []


def syncMdblistWatched(silent=True, force_update=False):
    if not getMdblistCredentialsInfo():
        return False
    try:
        latest = call_mdblist('sync/last_activities')
        if not isinstance(latest, dict):
            return False
        cached = _load_cached_activities()
        def _changed(key):
            try:
                return (latest.get(key) or '') > (cached.get(key) or '')
            except Exception:
                return True
        if force_update:
            _bust_caches()
        else:
            if not any(_changed(k) for k in (
                'watched_at', 'episode_watched_at', 'paused_at', 'episode_paused_at',
                'watchlisted_at', 'collected_at', 'dropped_at', 'list_updated_at',
            )):
                return True
            if _changed('watched_at'):
                cachesyncMovies(timeout=0)
            if _changed('episode_watched_at'):
                cachesyncTVShows(timeout=0)
        if force_update:
            cachesyncMovies(timeout=0)
            cachesyncTVShows(timeout=0)
        _store_cached_activities(latest)
        if not silent:
            control.infoDialog('MDBList Cache Refreshed.', sound=True)
        return True
    except Exception as e:
        log_utils.log('MDBList Watched Sync Failed: %s' % e, 1)
        return False


def refreshMdblistCache():
    if not getMdblistCredentialsInfo():
        control.infoDialog('Authorise MDBList first.', sound=True)
        return
    control.busy()
    try:
        ok = syncMdblistWatched(silent=True, force_update=True)
        control.idle()
        if ok:
            control.infoDialog('MDBList Cache Refreshed.', sound=True)
            try:
                control.refresh_list()
            except Exception:
                pass
        else:
            control.infoDialog('MDBList Sync Failed.', sound=True, icon='ERROR')
    except Exception:
        control.idle()
        control.infoDialog('MDBList Sync Failed.', sound=True, icon='ERROR')


def _watched_unwatched(action, media, media_id, tvdb_id=0, season=None, episode=None, key='tmdb'):
    if action == 'mark_as_watched':
        url, result_key = 'sync/watched', 'updated'
    else:
        url, result_key = 'sync/watched/remove', 'removed'
    try:
        media_id = int(media_id)
    except Exception:
        pass
    if media == 'movies':
        success_key, data = 'movies', {'movies': [{'ids': {key: media_id}}]}
    elif media == 'episode':
        success_key = 'episodes'
        data = {'shows': [{'ids': {key: media_id}, 'seasons': [{'number': int(season), 'episodes': [{'number': int(episode)}]}]}]}
    elif media == 'shows':
        success_key, data = 'episodes', {'shows': [{'ids': {key: media_id}}]}
    else:
        success_key = 'episodes'
        data = {'shows': [{'ids': {key: media_id}, 'seasons': [{'number': int(season)}]}]}
    result = call_mdblist(url, json_data=data, method='post')
    if not isinstance(result, dict):
        return False
    success = result.get(result_key, {}).get(success_key, 0) > 0
    if not success and media != 'movies' and tvdb_id:
        return _watched_unwatched(action, media, tvdb_id, 0, season, episode, 'tvdb')
    if not success and action != 'mark_as_watched':
        return True
    return success


def _resolve_tmdb(tmdb, imdb=None, media='movie'):
    if tmdb and str(tmdb) not in ('0', '', 'None'):
        try:
            return int(tmdb)
        except Exception:
            pass
    return None


def markMovieAsWatched(imdb, tmdb=None):
    media_id = _resolve_tmdb(tmdb, imdb, 'movie')
    if not media_id:
        return False
    return _watched_unwatched('mark_as_watched', 'movies', media_id)


def markMovieAsNotWatched(imdb, tmdb=None):
    media_id = _resolve_tmdb(tmdb, imdb, 'movie')
    if not media_id:
        return False
    return _watched_unwatched('mark_as_unwatched', 'movies', media_id)


def markEpisodeAsWatched(imdb, season, episode, tmdb=None, tvdb=None):
    media_id = _resolve_tmdb(tmdb, imdb, 'show')
    if not media_id:
        return False
    return _watched_unwatched('mark_as_watched', 'episode', media_id, tvdb or 0, season, episode)


def markEpisodeAsNotWatched(imdb, season, episode, tmdb=None, tvdb=None):
    media_id = _resolve_tmdb(tmdb, imdb, 'show')
    if not media_id:
        return False
    return _watched_unwatched('mark_as_unwatched', 'episode', media_id, tvdb or 0, season, episode)


def markTVShowAsWatched(imdb, tmdb=None):
    media_id = _resolve_tmdb(tmdb, imdb, 'show')
    if not media_id:
        return False
    return _watched_unwatched('mark_as_watched', 'shows', media_id)


def markTVShowAsNotWatched(imdb, tmdb=None):
    media_id = _resolve_tmdb(tmdb, imdb, 'show')
    if not media_id:
        return False
    return _watched_unwatched('mark_as_unwatched', 'shows', media_id)


def markSeasonAsWatched(imdb, season, tmdb=None):
    media_id = _resolve_tmdb(tmdb, imdb, 'show')
    if not media_id:
        return False
    return _watched_unwatched('mark_as_watched', 'season', media_id, 0, season)


def markSeasonAsNotWatched(imdb, season, tmdb=None):
    media_id = _resolve_tmdb(tmdb, imdb, 'show')
    if not media_id:
        return False
    return _watched_unwatched('mark_as_unwatched', 'season', media_id, 0, season)


def mdblist_official_status():
    """True when official MDBList scrobbler should own progress writes."""
    try:
        addon = control.addon('service.mdblist-scrobbler')
    except Exception:
        return False
    token = ''
    for key in ('api_key', 'apikey', 'token', 'mdblist_api_key', 'mdblist.token', 'refresh_token'):
        try:
            token = (addon.getSetting(key) or '').strip()
        except Exception:
            token = ''
        if token:
            break
    if not token:
        return False
    for key in ('scrobble', 'scrobble_enabled', 'enable_scrobble', 'scrobble_movies', 'scrobble_episodes'):
        try:
            if addon.getSetting(key) in ('true', 'True', '1'):
                return True
        except Exception:
            pass
    return False


def mdblist_scrobble(action, media_type, percent=0, tmdb=None, imdb=None, season=None, episode=None):
    from resources.lib.modules import simkl
    if simkl.getIndicatorsProvider() != 'mdblist':
        return
    if mdblist_official_status():
        return
    try:
        tmdb_id = _resolve_tmdb(tmdb, imdb, media_type)
        if not tmdb_id:
            return
        if action == 'clear':
            call_mdblist('scrobble/clear', json_data={'id': percent}, method='post')
            return
        if media_type == 'movie':
            payload = {'movie': {'ids': {'tmdb': tmdb_id}}, 'progress': float(percent)}
        else:
            payload = {
                'show': {'ids': {'tmdb': tmdb_id}, 'season': {'number': int(season), 'episode': {'number': int(episode)}}},
                'progress': float(percent),
            }
        # MDBList uses pause for in-progress writes; start is treated the same.
        path = 'scrobble/pause' if action in ('start', 'pause', 'stop') else 'scrobble/pause'
        call_mdblist(path, json_data=payload, method='post')
    except Exception as e:
        log_utils.log('MDBList scrobble failed: %s' % e, 1)


def _list_payload_ids(media_type, tmdb_id, imdb_id=None):
    if media_type == 'movie':
        payload = {'movies': [{'ids': {'tmdb': int(tmdb_id)}}]}
    else:
        payload = {'shows': [{'ids': {'tmdb': int(tmdb_id)}}]}
        if imdb_id and imdb_id not in ('None', '', '0'):
            payload['shows'][0]['ids']['imdb'] = imdb_id
    return payload


def _tmdb_in_rows(rows, tmdb_id):
    try:
        tmdb_id = int(tmdb_id)
    except Exception:
        return False
    for item in rows or []:
        _ids, _block, tmdb = _ids_from_item(item, 'movies' if 'movie' in str(item) else 'shows')
        try:
            if int(tmdb or 0) == tmdb_id:
                return True
        except Exception:
            continue
        try:
            if int(item.get('id') or 0) == tmdb_id:
                return True
        except Exception:
            continue
    return False


def _item_in_watchlist(is_movie, tmdb_id):
    media = 'movies' if is_movie else 'shows'
    items = cache.get(_personal_items, _LIST_CACHE_HOURS, 'watchlist/items', media) or []
    try:
        tmdb_s = str(int(tmdb_id))
    except Exception:
        return False
    return any(str(i.get('tmdb')) == tmdb_s for i in items)


def _item_in_library(is_movie, tmdb_id):
    media = 'movies' if is_movie else 'shows'
    items = cache.get(_personal_items, _LIST_CACHE_HOURS, 'sync/collection', media) or []
    try:
        tmdb_s = str(int(tmdb_id))
    except Exception:
        return False
    return any(str(i.get('tmdb')) == tmdb_s for i in items)


def _item_in_dropped(tmdb_id):
    try:
        return str(int(tmdb_id)) in dropped_tmdb_ids()
    except Exception:
        return False


def _post_ok(result, action_add=True, bucket='movies'):
    if not isinstance(result, dict) or result.get('error'):
        return False
    block = result.get('updated') or result.get('added') or result.get('existing') or {}
    removed = result.get('deleted') or result.get('removed') or {}
    try:
        if action_add:
            return int(block.get(bucket) or result.get(bucket) or 0) > 0 or True
        return int(removed.get(bucket) or 0) >= 0
    except Exception:
        return result is not None


def manager(name, imdb, tmdb, content):
    try:
        if not getMdblistCredentialsInfo():
            return control.infoDialog('Authorise MDBList first.', sound=True)
        is_movie = content == 'movie'
        media_type = 'movie' if is_movie else 'tvshow'
        if not tmdb or str(tmdb) in ('0', '', 'None'):
            return control.infoDialog('Missing TMDb ID for MDBList Lists Manager.', sound=True, icon='ERROR')
        try:
            tmdb_id = int(tmdb)
        except Exception:
            return control.infoDialog('Missing TMDb ID for MDBList Lists Manager.', sound=True, icon='ERROR')
        choices = []
        if _item_in_watchlist(is_movie, tmdb_id):
            choices.append(('Remove from [B]MDBList Watchlist[/B]', 'remove_watchlist'))
        else:
            choices.append(('Add to [B]MDBList Watchlist[/B]', 'add_watchlist'))
        if _item_in_library(is_movie, tmdb_id):
            choices.append(('Remove from [B]MDBList Library[/B]', 'remove_library'))
        else:
            choices.append(('Add to [B]MDBList Library[/B]', 'add_library'))
        if not is_movie:
            if _item_in_dropped(tmdb_id):
                choices.append(('Undrop [B]TV Show[/B]', 'undrop'))
            else:
                choices.append(('Drop [B]TV Show[/B]', 'drop'))
        static = static_lists()
        if static:
            choices.append(('Add To [B]Static List[/B]...', 'add_static'))
            choices.append(('Remove from [B]Static List[/B]...', 'remove_static'))
        select = control.selectDialog([c[0] for c in choices], 'MDBList Lists Manager')
        if select < 0:
            return
        _, action = choices[select]
        payload = _list_payload_ids('movie' if is_movie else 'show', tmdb_id, imdb)
        bucket = 'movies' if is_movie else 'shows'
        ok = False
        message = ''
        if action == 'add_watchlist':
            ok = call_mdblist('watchlist/items', json_data=payload, method='post') is not None
            message = 'Added to Watchlist.'
        elif action == 'remove_watchlist':
            ok = call_mdblist('watchlist/items/remove', json_data=payload, method='post') is not None
            message = 'Removed from Watchlist.'
        elif action == 'add_library':
            ok = call_mdblist('sync/collection', json_data=payload, method='post') is not None
            message = 'Added to Library.'
        elif action == 'remove_library':
            ok = call_mdblist('sync/collection/remove', json_data=payload, method='post') is not None
            message = 'Removed from Library.'
        elif action == 'drop':
            ok = call_mdblist('sync/dropped', json_data=payload, method='post') is not None
            message = 'Dropped from MDBList Progress.'
        elif action == 'undrop':
            ok = call_mdblist('sync/dropped/remove', json_data=payload, method='post') is not None
            message = 'Removed from MDBList Dropped.'
        elif action in ('add_static', 'remove_static'):
            labels = [i.get('name') or str(i.get('id')) for i in static]
            pick = control.selectDialog(labels, 'MDBList Static Lists')
            if pick < 0:
                return
            list_id = static[pick].get('id')
            list_name = static[pick].get('name') or 'List'
            path = 'lists/%s/items' % list_id if action == 'add_static' else 'lists/%s/items/remove' % list_id
            ok = call_mdblist(path, json_data=payload, method='post') is not None
            message = ('Added to %s.' if action == 'add_static' else 'Removed from %s.') % list_name
        if not ok:
            return control.infoDialog('MDBList Lists Manager failed.', heading=str(name), sound=True, icon='ERROR')
        try:
            _bust_caches()
        except Exception:
            pass
        control.infoDialog(message, heading=str(name), sound=True, icon=control.infoLabel('ListItem.Icon'))
        try:
            control.refresh_list()
        except Exception:
            pass
    except Exception:
        control.infoDialog('MDBList Lists Manager failed.', heading=str(name), sound=True, icon='ERROR')
