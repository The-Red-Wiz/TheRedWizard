# -*- coding: utf-8 -*-

import re
import time

import requests
from requests.compat import json, str
#import simplejson as json
from six import ensure_str, ensure_text
from six.moves.urllib_parse import urljoin, quote_plus

from resources.lib.modules import cache
from resources.lib.modules import cleandate
from resources.lib.modules import client
from resources.lib.modules import client_utils
from resources.lib.modules import control
from resources.lib.modules import log_utils


# ---------------------------------------------------------------------------
# PAGINATION HELPER
# ---------------------------------------------------------------------------
# Why: several Trakt endpoints the add-on uses (``/users/me/favorites/*``,
# ``/users/me/collection/*``, some legacy callers) and the local SQLite
# favorites DB return the *entire* collection in a single payload.  With
# large accounts that means the directory freezes Kodi for several
# seconds while every row is rendered, even though the user only ever
# looks at the first page.  This helper produces the current page slice
# and a ``next_page`` integer (or None) that callers can turn into a
# "Next Page" directory entry - exact same UX the existing server-side
# paginated views already have.  Keeping it here (rather than copying
# the logic into every indexer) means it can be reused from movies.py,
# tvshows.py, episodes.py and modules.favorites consistently.
def paginate(items, page=1, page_size=None):
    """Slice ``items`` for directory pagination.

    Returns (page_items, next_page_number_or_None).  ``page`` is 1-based
    to match Trakt's own ``page=1`` convention.  ``page_size`` defaults to
    the add-on's "items.per.page" setting (falling back to 40 if unset /
    invalid) so the directory behaviour matches the rest of the add-on.
    """
    try:
        page = int(page) if page else 1
    except Exception:
        page = 1
    if page < 1:
        page = 1
    if not page_size:
        try:
            page_size = int(control.setting('items.per.page'))
        except Exception:
            page_size = 0
        if not page_size or page_size <= 0:
            page_size = 40
    items = items or []
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    next_page = page + 1 if end < len(items) else None
    return page_items, next_page

BASE_URL = 'https://api.trakt.tv'
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
V2_API_KEY = '33ea6bfa2b06c9cfa3e408fc6b4cc30484f31b90733df3508fd09ce512f47982'
CLIENT_SECRET = '4a294afdab95894be977dc79c9715224dc87a4a88d74944507945ca58bf719b2'
# Trakt API max per-page limit (reduced to 250; see trakt-api discussions #681 / #775)
TRAKT_PAGE_LIMIT = 250
# extended=progress on watched/shows is capped at 100 per page
TRAKT_WATCHED_PROGRESS_PAGE_LIMIT = 100
TRAKT_REFRESH_PROPERTY = 'gratisred.trakt_refreshing_token'


def _trakt_page_limit(query_params):
    ext = str((query_params or {}).get('extended') or '').lower()
    if 'progress' in ext:
        return TRAKT_WATCHED_PROGRESS_PAGE_LIMIT
    return TRAKT_PAGE_LIMIT


def _set_trakt_expires(expires_in):
    try:
        control.setSetting('trakt.expires', str(time.time() + int(expires_in)))
    except Exception:
        pass


def _refreshTraktToken():
    try:
        control.window.setProperty(TRAKT_REFRESH_PROPERTY, 'true')
        oauth = urljoin(BASE_URL, '/oauth/token')
        headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
        opost = {'client_id': V2_API_KEY, 'client_secret': CLIENT_SECRET, 'redirect_uri': REDIRECT_URI,
                 'grant_type': 'refresh_token', 'refresh_token': control.setting('trakt.refresh')}
        result = requests.post(oauth, data=json.dumps(opost), headers=headers, timeout=30).json()
        token, refresh = result['access_token'], result['refresh_token']
        control.setSetting('trakt.token', token)
        control.setSetting('trakt.refresh', refresh)
        _set_trakt_expires(result.get('expires_in', 7200))
        return token
    except Exception as e:
        log_utils.log('Trakt token refresh failed: %s' % e)
        return None
    finally:
        control.window.clearProperty(TRAKT_REFRESH_PROPERTY)


def _ensureTraktTokenFresh():
    if not getTraktCredentialsInfo():
        return
    while control.window.getProperty(TRAKT_REFRESH_PROPERTY) == 'true':
        time.sleep(0.25)
    try:
        expires_at = float(control.setting('trakt.expires') or '0')
    except Exception:
        expires_at = 0.0
    if expires_at > 0 and time.time() >= expires_at:
        _refreshTraktToken()


def valid_trakt_activities(data):
    return isinstance(data, dict) and 'all' in data and isinstance(data.get('movies'), dict) and isinstance(data.get('episodes'), dict)


def getTraktCredentialsInfo():
    user = control.setting('trakt.user').strip()
    token = control.setting('trakt.token')
    refresh = control.setting('trakt.refresh')
    if (user == '' or token == '' or refresh == ''):
        return False
    return True


def __getTraktALT(url, post=None):
    try:
        url = urljoin(BASE_URL, url) if not url.startswith(BASE_URL) else url
        post = json.dumps(post) if post else None
        headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
        if getTraktCredentialsInfo():
            headers.update({'Authorization': 'Bearer %s' % control.setting('trakt.token')})
        result = client.request(url, post=post, headers=headers, output='extended', error=True)
        result = client_utils.byteify(result)
        resp_code = result[1]
        resp_header = result[2]
        result = result[0]
        if resp_code in ['423', '500', '502', '503', '504', '520', '521', '522', '524']:
            log_utils.log('Trakt Error: %s' % str(resp_code))
            control.infoDialog('Trakt Error: ' + str(resp_code), sound=True)
            return
        elif resp_code in ['429']:
            log_utils.log('Trakt Rate Limit Reached: %s' % str(resp_code))
            control.infoDialog('Trakt Rate Limit Reached: ' + str(resp_code), sound=True)
            return
        elif resp_code in ['404']:
            log_utils.log('Trakt Object Not Found : %s' % str(resp_code))
            return
        if resp_code not in ['401', '405', '403']:
            return result, resp_header
        oauth = urljoin(BASE_URL, '/oauth/token')
        opost = {'client_id': V2_API_KEY, 'client_secret': CLIENT_SECRET, 'redirect_uri': REDIRECT_URI, 'grant_type': 'refresh_token', 'refresh_token': control.setting('trakt.refresh')}
        result = client.request(oauth, post=json.dumps(opost), headers=headers)
        result = client_utils.json_loads_as_str(result)
        token, refresh = result['access_token'], result['refresh_token']
        control.setSetting('trakt.token', token)
        control.setSetting('trakt.refresh', refresh)
        headers['Authorization'] = 'Bearer %s' % token
        result = client.request(url, post=post, headers=headers, output='extended', error=True)
        result = client_utils.byteify(result)
        return result[0], result[2]
    except:
        pass


def __getTrakt(url, post=None, timeout=30):
    # ---------------------------------------------------------------------
    # FIX (Trakt lists missing): the original implementation returned a bare
    # ``None`` on any server / rate-limit / transport error.  Every caller in
    # this module (e.g. ``getTraktAsJson``) immediately unpacks the result
    # with ``r, res_headers = __getTrakt(url)`` which raises a
    # ``TypeError: cannot unpack non-iterable NoneType object`` the moment
    # Trakt hiccups.  That exception is then swallowed by the caller's own
    # blanket ``try/except`` and the user just sees an *empty* directory –
    # i.e. the "block" symptom where lists silently fail to load.
    #
    # We now ALWAYS return a 2-tuple ``(body_or_None, headers_dict)`` so
    # tuple-unpacking never blows up.  Transient 5xx / 429 are logged only
    # (no more spammy "Trakt Error 502" pop-up that previously discouraged
    # the caller from retrying).  A single short retry with the server's
    # ``Retry-After`` value is attempted on 429 before giving up.
    # ---------------------------------------------------------------------
    try:
        url = urljoin(BASE_URL, url) if not url.startswith(BASE_URL) else url
        post = json.dumps(post) if post else None
        headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
        if getTraktCredentialsInfo():
            _ensureTraktTokenFresh()
            headers.update({'Authorization': 'Bearer %s' % control.setting('trakt.token')})
        if not post:
            r = requests.get(url, headers=headers, timeout=timeout)
        else:
            r = requests.post(url, data=post, headers=headers, timeout=timeout)
        r.encoding = 'utf-8'
        resp_code = str(r.status_code)
        resp_header = r.headers
        result = r.text
        if resp_code in ['423', '500', '502', '503', '504', '520', '521', '522', '524']:
            # Log only - popping a modal for every transient gateway error
            # was both noisy and, combined with the old ``return`` below,
            # caused list views to appear empty.
            log_utils.log('Trakt Error: %s on %s' % (str(resp_code), url))
            return None, resp_header
        elif resp_code in ['429']:
            # Rate-limited.  Trakt sends a ``Retry-After`` header (seconds).
            # Do one polite short wait + retry so large list enumerations
            # (which legitimately hit the API many times) don't terminate
            # prematurely and drop the remaining pages.
            wait = 2
            try:
                wait = max(1, min(10, int(resp_header.get('Retry-After', '2'))))
            except Exception:
                wait = 2
            log_utils.log('Trakt Rate Limit %s - sleeping %ss then retrying %s' % (resp_code, wait, url))
            time.sleep(wait)
            if not post:
                r = requests.get(url, headers=headers, timeout=timeout)
            else:
                r = requests.post(url, data=post, headers=headers, timeout=timeout)
            r.encoding = 'utf-8'
            if str(r.status_code) == '200':
                return r.text, r.headers
            return None, r.headers
        elif resp_code in ['404']:
            log_utils.log('Trakt Object Not Found : %s' % str(resp_code))
            return None, resp_header
        if resp_code not in ['401', '405', '403']:
            return result, resp_header
        # 401/403/405 => access token expired, try refreshing once and replay.
        token = _refreshTraktToken()
        if not token:
            return None, resp_header
        headers['Authorization'] = 'Bearer %s' % token
        if not post:
            r = requests.get(url, headers=headers, timeout=timeout)
        else:
            r = requests.post(url, data=post, headers=headers, timeout=timeout)
        r.encoding = 'utf-8'
        return r.text, r.headers
    except Exception as e:
        # Network / DNS / SSL failure: still return a well-formed tuple so
        # that downstream ``r, res_headers = __getTrakt(...)`` never explodes.
        log_utils.log('Trakt request failed for %s : %s' % (url, e))
        return None, {}


def _released_key(item):
    if 'released' in item:
        return item['released'] or '0'
    elif 'first_aired' in item:
        return item['first_aired'] or '0'
    else:
        return '0'


def sort_list(sort_key, sort_direction, list_data):
    reverse = False if sort_direction == 'asc' else True
    if not isinstance(list_data, list):
        return list_data
    try:
        if sort_key == 'rank':
            return sorted(list_data, key=lambda x: x.get('rank') or 0, reverse=reverse)
        elif sort_key == 'added':
            return sorted(list_data, key=lambda x: x.get('listed_at') or '', reverse=reverse)
        elif sort_key == 'title':
            def _title(x):
                try:
                    return (x.get(x.get('type')) or {}).get('title') or ''
                except Exception:
                    return ''
            return sorted(list_data, key=_title, reverse=reverse)
        elif sort_key == 'released':
            def _released(x):
                try:
                    return _released_key(x.get(x.get('type')) or {})
                except Exception:
                    return '0'
            return sorted(list_data, key=_released, reverse=reverse)
        elif sort_key == 'runtime':
            def _runtime(x):
                try:
                    return (x.get(x.get('type')) or {}).get('runtime') or 0
                except Exception:
                    return 0
            return sorted(list_data, key=_runtime, reverse=reverse)
        elif sort_key == 'popularity':
            def _votes(x):
                try:
                    return (x.get(x.get('type')) or {}).get('votes') or 0
                except Exception:
                    return 0
            return sorted(list_data, key=_votes, reverse=reverse)
        elif sort_key == 'percentage':
            def _rating(x):
                try:
                    return (x.get(x.get('type')) or {}).get('rating') or 0
                except Exception:
                    return 0
            return sorted(list_data, key=_rating, reverse=reverse)
        elif sort_key == 'votes':
            def _votes(x):
                try:
                    return (x.get(x.get('type')) or {}).get('votes') or 0
                except Exception:
                    return 0
            return sorted(list_data, key=_votes, reverse=reverse)
    except Exception:
        return list_data
    return list_data


def choose_list_sort(media, shelf, label=None):
    """Context-menu picker for My Trakt shelves and personal lists."""
    from resources.lib.modules import shelf_sort
    shelf_sort.choose_list_sort(
        'trakt', media, shelf, sortable=shelf_sort.TRAKT_SORTABLE, heading_label=label)


def apply_my_shelf_sort(items, url, media):
    """Apply user sort to My Trakt sync shelves or personal / liked lists."""
    from resources.lib.modules import shelf_sort
    shelf = shelf_sort.trakt_shelf_from_url(url)
    if not shelf:
        return items
    return shelf_sort.sort_items(items, 'trakt', media, shelf, sortable=shelf_sort.TRAKT_SORTABLE)


# Home-window property: shelf removals that must not reappear in directory
# listings even if Trakt's list endpoint lags behind sync/remove.
_SHELF_EXCLUDE_PROP = 'gratisred.trakt_shelf_exclude'


def _exclude_window():
    from kodi_six import xbmcgui
    return xbmcgui.Window(10000)


def _parse_shelf_exclusions():
    """Return {shelf: set([id, ...])} from the home window property."""
    out = {}
    try:
        raw = _exclude_window().getProperty(_SHELF_EXCLUDE_PROP) or ''
    except Exception:
        return out
    if not raw:
        return out
    for chunk in raw.split(';'):
        if ':' not in chunk:
            continue
        shelf, _, ids = chunk.partition(':')
        shelf = (shelf or '').strip()
        if not shelf:
            continue
        out[shelf] = set(x for x in ids.split(',') if x)
    return out


def _save_shelf_exclusions(data):
    parts = []
    for shelf in sorted(data.keys()):
        ids = sorted(x for x in (data.get(shelf) or set()) if x)
        if ids:
            parts.append('%s:%s' % (shelf, ','.join(ids[:80])))
    try:
        _exclude_window().setProperty(_SHELF_EXCLUDE_PROP, ';'.join(parts))
    except Exception:
        pass


def _shelf_exclusion_allowed(shelf):
    if shelf in ('watchlist', 'collection'):
        return True
    try:
        from resources.lib.modules import shelf_sort
        return shelf_sort.is_personal_shelf(shelf)
    except Exception:
        return False


def note_shelf_exclusion(shelf, imdb=None, tmdb=None):
    """Hide this title on Watchlist/Library/personal lists until added again."""
    if not _shelf_exclusion_allowed(shelf):
        return
    data = _parse_shelf_exclusions()
    bucket = data.setdefault(shelf, set())
    if tmdb and str(tmdb) not in ('0', '', 'None'):
        bucket.add(str(tmdb))
    if imdb and str(imdb) not in ('0', '', 'None'):
        bucket.add(str(imdb))
    _save_shelf_exclusions(data)


def clear_shelf_exclusion(shelf, imdb=None, tmdb=None):
    """Clear a prior remove-exclusion after a successful add."""
    if not _shelf_exclusion_allowed(shelf):
        return
    data = _parse_shelf_exclusions()
    bucket = data.get(shelf) or set()
    if not bucket:
        return
    if tmdb and str(tmdb) in bucket:
        bucket.discard(str(tmdb))
    if imdb and str(imdb) in bucket:
        bucket.discard(str(imdb))
    if bucket:
        data[shelf] = bucket
    else:
        data.pop(shelf, None)
    _save_shelf_exclusions(data)


def filter_shelf_exclusions(items, url):
    """Drop locally excluded titles from a My Trakt shelf / personal list page."""
    try:
        from resources.lib.modules import shelf_sort
        shelf = shelf_sort.trakt_shelf_from_url(url)
        if not _shelf_exclusion_allowed(shelf) or not items:
            return items
        excluded = _parse_shelf_exclusions().get(shelf) or set()
        if not excluded:
            return items
        kept = []
        for item in items:
            tmdb = str((item or {}).get('tmdb') or '')
            imdb = str((item or {}).get('imdb') or '')
            if tmdb in excluded or imdb in excluded:
                continue
            kept.append(item)
        return kept
    except Exception:
        return items


def _manager_shelf_from_path(path):
    """Return (shelf_key, list_slug_or_None) for Manager add/remove paths."""
    path = path or ''
    if '/sync/watchlist' in path:
        return 'watchlist', None
    if '/sync/collection' in path:
        return 'collection', None
    if path.startswith('/users/') and '/lists/' in path:
        parts = path.split('/')
        # /users/{user}/lists/{slug}/items[/remove]
        if len(parts) >= 6 and parts[3] == 'lists':
            try:
                from resources.lib.modules import shelf_sort
                return shelf_sort.personal_shelf_key(parts[2], parts[4]), parts[4]
            except Exception:
                return None, parts[4]
    return None, None


def _folder_matches_manager_shelf(folder_raw, shelf, list_slug=None):
    """True when the open container is the shelf/list just changed."""
    folder_raw = folder_raw or ''
    if not folder_raw:
        return False
    if list_slug:
        return (
            ('/lists/%s/' % list_slug) in folder_raw
            or ('/lists/%s/items' % list_slug) in folder_raw
        )
    if shelf in ('watchlist', 'collection'):
        return (
            ('url=trakt_%s' % shelf) in folder_raw
            or ('/%s/' % shelf) in folder_raw
            or '/users/me/%s/' % shelf in folder_raw
        )
    return False


def _trakt_id_from_sync(kind, content, ids):
    """Return Trakt's numeric id for a watchlist/collection member, if found."""
    try:
        media = 'movies' if content == 'movie' else 'shows'
        media_key = 'movie' if content == 'movie' else 'show'
        items = _trakt_paged_cached('/users/me/%s/%s' % (kind, media))
        if not items:
            return None
        for item in items:
            block = (item or {}).get(media_key) or {}
            if not _ids_match(block.get('ids'), ids):
                continue
            trakt_id = (block.get('ids') or {}).get('trakt')
            if trakt_id not in (None, '', 'None', 0, '0'):
                return int(trakt_id)
    except Exception:
        pass
    return None


def getTraktAsJson(url, post=None):
    try:
        r, res_headers = __getTrakt(url, post)
        # ``__getTrakt`` may now legitimately return ``(None, headers)`` on
        # 404/5xx; guard the JSON decode so callers get ``None`` rather than
        # a silently-swallowed exception (which previously looked to users
        # like "Trakt isn't returning all my lists").
        if not r:
            return None
        r = client_utils.json_loads_as_str(r)
        # Never let header re-sort wipe a page (KeyError on missing rank/listed_at
        # used to make getTraktAsJson return None → empty Watchlist page).
        if isinstance(r, list) and res_headers and 'X-Sort-By' in res_headers and 'X-Sort-How' in res_headers:
            try:
                r = sort_list(res_headers['X-Sort-By'], res_headers['X-Sort-How'], r)
            except Exception:
                pass
        return r
    except:
        pass


def getTraktAsJsonPaged(url, page_size=None):
    """
    Fetch a Trakt endpoint that supports pagination and return *all* results
    concatenated, following every page reported by the ``X-Pagination-Page-Count``
    response header.

    WHY THIS FUNCTION EXISTS
    ------------------------
    Trakt paginates almost every "list" endpoint (``/users/me/lists``,
    ``/users/likes/lists``, ``/users/me/watchlist/*``, ``/users/me/history/*``
    etc.).  The maximum allowed ``limit`` per page is now **250** (100 when
    ``extended=progress``).  Without walking the pages you only ever see the
    first chunk, which is exactly the user-visible bug ("Trakt doesn't get
    all its lists – some kind of block").

    The helper:
      * forces a sane ``limit`` (250 default, 100 for progress endpoints),
      * starts at ``page=1`` and increments until
        ``X-Pagination-Page-Count`` is reached (or the server stops
        returning items),
      * merges every page's JSON array into one flat list,
      * preserves Trakt's server-side sort when only a single page is
        returned (so behaviour is unchanged for small accounts),
      * hard-caps at 50 pages as a safety belt in case a buggy server
        sends absurd header values.
    """
    try:
        # Build the URL with explicit limit/page.  We respect any query
        # string the caller already provided so things like
        # ``?extended=full`` or ``?type=list`` survive untouched.
        split = url.split('?', 1)
        base = split[0]
        existing = dict()
        if len(split) == 2 and split[1]:
            for kv in split[1].split('&'):
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    existing[k] = v
        # Remove legacy out-of-range limits (e.g. limit=1000000) and use
        # Trakt's current per-page maximum for this endpoint.
        page_limit = _trakt_page_limit(existing)
        if page_size is None:
            page_size = page_limit
        try:
            limit = int(existing.get('limit', str(page_size)))
            if limit <= 0 or limit > page_limit:
                limit = page_size
        except Exception:
            limit = page_size
        existing['limit'] = str(min(int(limit), page_limit))

        merged = []
        current_page = 1
        max_pages = 50  # safety belt, see docstring
        while current_page <= max_pages:
            existing['page'] = str(current_page)
            qs = '&'.join('%s=%s' % (k, v) for k, v in existing.items())
            page_url = '%s?%s' % (base, qs)

            r, res_headers = __getTrakt(page_url, None)
            if not r:
                # Incomplete page walks must not look like "not a member".
                return None
            try:
                data = client_utils.json_loads_as_str(r)
            except Exception:
                return None
            if not isinstance(data, list):
                # Unexpected payload (e.g. an error dict); bail.
                return None
            merged.extend(data)

            # Determine total pages from Trakt's response headers.  If the
            # endpoint doesn't paginate (``/users/me/lists`` for example,
            # which is non-paginated on most accounts) the header will be
            # missing and we stop after the first page – exactly the old
            # behaviour.
            try:
                total_pages = int(res_headers.get('X-Pagination-Page-Count', '1'))
            except Exception:
                total_pages = 1
            if current_page >= total_pages:
                break
            if len(data) < limit:
                # Server returned fewer items than we asked for => we've
                # hit the end regardless of what the header claims.
                break
            current_page += 1

        # Honour Trakt's sort hints only when the server returned a single
        # page; for multi-page merges the per-page order is already
        # consistent and re-sorting would discard the natural order of
        # "most recently liked first" etc.
        if current_page == 1 and res_headers and 'X-Sort-By' in res_headers and 'X-Sort-How' in res_headers:
            merged = sort_list(res_headers['X-Sort-By'], res_headers['X-Sort-How'], merged)
        return merged
    except Exception as e:
        log_utils.log('getTraktAsJsonPaged failed for %s : %s' % (url, e))
        return None


def revokeTrakt(reopen_settings=False):
    """Revoke tokens at Trakt and clear local credentials."""
    if not getTraktCredentialsInfo():
        control.infoDialog('No Trakt account is authorised.', sound=True)
        return
    try:
        token = (control.setting('trakt.token') or '').strip()
        refresh = (control.setting('trakt.refresh') or '').strip()
        revoke_token = token or refresh
        if revoke_token:
            try:
                client.request(
                    urljoin(BASE_URL, '/oauth/revoke'),
                    post=json.dumps({
                        'token': revoke_token,
                        'client_id': V2_API_KEY,
                        'client_secret': CLIENT_SECRET,
                    }),
                    headers={'Content-Type': 'application/json'},
                    timeout='15',
                )
            except Exception as e:
                log_utils.log('Trakt revoke API call failed: %s' % e, 1)
        control.setSetting('trakt.user', '')
        control.setSetting('trakt.authed', '')
        control.setSetting('trakt.token', '')
        control.setSetting('trakt.refresh', '')
        control.setSetting('trakt.expires', '')
        try:
            from resources.lib.modules import simkl
            simkl.fallback_indicators_on_revoke('trakt')
        except Exception:
            pass
        control.infoDialog('Trakt Account Revoked.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('Trakt Revoke Failed.', sound=True)


def authTrakt(reopen_settings=False):
    from resources.lib.modules import auth_utils
    progress = None
    try:
        if getTraktCredentialsInfo():
            control.infoDialog('Trakt is already authorised. Use Revoke Trakt Account to sign out.', sound=True)
            return
        progress = auth_utils.auth_progress_dialog('Trakt Authorise', '')
        progress.update('Connecting to Trakt...')
        result = getTraktAsJson('/oauth/device/code', {'client_id': V2_API_KEY})
        if not result or not result.get('device_code'):
            control.infoDialog('Trakt Authorisation Failed.', sound=True)
            return
        user_code = str(result.get('user_code', ''))
        device_code = result['device_code']
        expires_in = int(result.get('expires_in', 600))
        interval = max(int(result.get('interval', 5)), 1)
        auth_url = 'https://trakt.tv/activate?code=%s' % user_code
        progress.update('Preparing QR code...')
        qr_code = auth_utils.make_qrcode(auth_url) or ''
        short_url = auth_utils.make_tinyurl(auth_url)
        auth_utils.copy2clip(auth_url)
        insert = '[CR]OR visit [B]%s[/B]' % short_url if short_url else ''
        verify_display = (result.get('verification_url') or 'trakt.tv/activate').replace('https://', '')
        content = ('Enter [B]%s[/B] at [B]%s[/B][CR]OR scan the [B]QR Code[/B][CR]Link copied to clipboard%s[CR][CR]'
                   'Waiting for authorisation...' % (user_code, verify_display, insert))
        progress.update(content, qr_path=qr_code)
        token_result = None
        start = time.time()
        while not progress.iscanceled() and (time.time() - start) < expires_in:
            if auth_utils.auth_progress_wait(progress, interval):
                break
            try:
                r = getTraktAsJson('/oauth/device/token', {
                    'client_id': V2_API_KEY,
                    'client_secret': CLIENT_SECRET,
                    'code': device_code,
                })
                if isinstance(r, dict) and r.get('access_token'):
                    token_result = r
                    break
            except Exception:
                pass
        canceled = progress.iscanceled()
        auth_utils.close_auth_progress_dialog(progress)
        progress = None
        if canceled or not token_result:
            control.infoDialog('Trakt Authorisation Canceled.' if canceled else 'Trakt Authorisation Failed.', sound=True)
            return
        token, refresh = token_result['access_token'], token_result['refresh_token']
        headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2', 'Authorization': 'Bearer %s' % token}
        result = client.request(urljoin(BASE_URL, '/users/me'), headers=headers)
        result = client_utils.json_loads_as_str(result)
        user = result.get('username', '')
        authed = '' if user == '' else str('yes')
        control.setSetting('trakt.user', user)
        control.setSetting('trakt.authed', authed)
        control.setSetting('trakt.token', token)
        control.setSetting('trakt.refresh', refresh)
        _set_trakt_expires(token_result.get('expires_in', 7200))
        if control.yesnoDialog('Set Trakt as your Watched Indicators provider?', heading='Watched Status Provider'):
            try:
                from resources.lib.modules import simkl
                simkl.set_watched_provider('1', notify=True)
            except Exception:
                control.setSetting('indicators.alt', '1')
                control.setSetting('bookmarks.source', '1')
        control.infoDialog('Trakt Account Authorised.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('Trakt Authorisation Failed.', sound=True)
    finally:
        if progress is not None:
            auth_utils.close_auth_progress_dialog(progress)


def getTraktIndicatorsInfo():
    # True only when Indicators is Trakt (not Gratis Red / Simkl).
    try:
        from resources.lib.modules import simkl
        return simkl.getIndicatorsProvider() == 'trakt'
    except Exception:
        indicators = control.setting('indicators') if getTraktCredentialsInfo() == False else control.setting('indicators.alt')
        return True if indicators == '1' else False


def getTraktAddonMovieInfo():
    """True when official script.trakt should own movie scrobble (we defer)."""
    try:
        if not control.condVisibility('System.HasAddon(script.trakt)'):
            return False
    except Exception:
        return False
    try:
        authorization = control.addon('script.trakt').getSetting('authorization')
    except Exception:
        authorization = ''
    # Match Red Light: unauthorised / empty token → we scrobble ourselves.
    if not authorization:
        return False
    try:
        scrobble = control.addon('script.trakt').getSetting('scrobble_movie')
    except Exception:
        scrobble = ''
    try:
        ExcludeHTTP = control.addon('script.trakt').getSetting('ExcludeHTTP')
    except Exception:
        ExcludeHTTP = ''
    # ExcludeHTTP true/empty → plugin HTTP playback is excluded; we scrobble.
    if ExcludeHTTP in ('true', ''):
        return False
    return scrobble == 'true'


def getTraktAddonEpisodeInfo():
    """True when official script.trakt should own episode scrobble (we defer)."""
    try:
        if not control.condVisibility('System.HasAddon(script.trakt)'):
            return False
    except Exception:
        return False
    try:
        authorization = control.addon('script.trakt').getSetting('authorization')
    except Exception:
        authorization = ''
    if not authorization:
        return False
    try:
        scrobble = control.addon('script.trakt').getSetting('scrobble_episode')
    except Exception:
        scrobble = ''
    try:
        ExcludeHTTP = control.addon('script.trakt').getSetting('ExcludeHTTP')
    except Exception:
        ExcludeHTTP = ''
    if ExcludeHTTP in ('true', ''):
        return False
    return scrobble == 'true'


def _trakt_scrobble_payload(media_type, percent, tmdb=None, imdb=None, tvdb=None, season=None, episode=None):
    """Build /scrobble/* body. Prefer TMDb, then IMDb, then TVDb."""
    ids = {}
    try:
        if tmdb not in (None, '', '0', 0):
            ids['tmdb'] = int(tmdb)
    except Exception:
        pass
    if imdb not in (None, '', '0'):
        ids['imdb'] = str(imdb)
    try:
        if tvdb not in (None, '', '0', 0):
            ids['tvdb'] = int(tvdb)
    except Exception:
        pass
    if not ids:
        return None
    progress = float(percent or 0)
    if media_type == 'movie':
        return {'movie': {'ids': ids}, 'progress': progress}
    try:
        return {
            'show': {'ids': ids},
            'episode': {'season': int(season), 'number': int(episode)},
            'progress': progress
        }
    except Exception:
        return None


def trakt_scrobble(action, media_type, percent=0, tmdb=None, imdb=None, tvdb=None, season=None, episode=None):
    """Native Trakt live scrobble (Playing now). Standalone when Indicators = Trakt.

    Defers when official script.trakt is authorised and set to scrobble that media type
    with ExcludeHTTP off (same idea as Simkl / Red Light).
    Short request timeout — never block Kodi player teardown on a hung Trakt call.
    """
    if not getTraktIndicatorsInfo():
        return False
    if not getTraktCredentialsInfo():
        return False
    if media_type == 'movie' and getTraktAddonMovieInfo():
        return False
    if media_type != 'movie' and getTraktAddonEpisodeInfo():
        return False
    path = {'start': '/scrobble/start', 'pause': '/scrobble/pause', 'stop': '/scrobble/stop'}.get(action)
    if not path:
        return False
    payload = _trakt_scrobble_payload(media_type, percent, tmdb=tmdb, imdb=imdb, tvdb=tvdb, season=season, episode=episode)
    if not payload:
        return False
    try:
        body, _headers = __getTrakt(path, post=payload, timeout=8)
        ok = body is not None
        log_utils.log('Trakt scrobble %s %s percent=%s ok=%s' % (action, media_type, percent, ok))
        return ok
    except Exception as e:
        log_utils.log('Trakt scrobble %s failed: %s' % (action, e))
        return False


def slug(name):
    name = name.strip()
    name = name.lower()
    name = re.sub(r'[^a-z0-9_]', '-', name)
    name = re.sub(r'--+', '-', name)
    if name.endswith('-'):
        name = name.rstrip('-')
    return name


def _trakt_probe_list_types(username, list_slug, limit=8):
    types = set()
    try:
        probe_url = '/users/%s/lists/%s/items?limit=%s' % (username, list_slug, int(limit))
        items = getTraktAsJson(probe_url) or []
        for item in items:
            if item.get('movie'):
                types.add('movie')
            if item.get('show'):
                types.add('show')
            if item.get('episode'):
                types.add('episode')
            if item.get('season'):
                types.add('season')
    except:
        pass
    return types


def _trakt_userlist_action(menu_type, item_types, item_count=0):
    if not menu_type:
        return 'movies'
    if item_count == 0:
        if menu_type == 'movie':
            return 'movies'
        if menu_type == 'tvshow':
            return 'tvshows'
        return 'calendar'
    if menu_type == 'movie':
        return 'movies' if 'movie' in item_types else None
    if menu_type == 'tvshow':
        return 'tvshows' if item_types & {'show', 'season'} else None
    if menu_type == 'episode':
        if 'episode' in item_types:
            return 'calendar'
        if item_types & {'show', 'season'}:
            return 'tvshows'
        return None
    return 'movies'


def build_user_list_directory(url, trakt_list_link, menu_type=None, image='trakt.png'):
    entries = []
    items = getTraktAsJsonPaged(url) or []
    for item in items:
        try:
            try:
                name = item['list']['name']
                username = slug(item['list']['user']['username'])
                list_slug = item['list']['ids']['slug']
                item_count = int(item['list'].get('item_count') or item.get('item_count') or 0)
            except:
                name = item['name']
                username = 'me'
                list_slug = item['ids']['slug']
                item_count = int(item.get('item_count') or 0)
            name = client_utils.replaceHTMLCodes(name)
            list_url = trakt_list_link % (username, list_slug)
            item_types = _trakt_probe_list_types(username, list_slug) if menu_type and item_count else set()
            action = _trakt_userlist_action(menu_type, item_types, item_count)
            if menu_type and action is None:
                continue
            from resources.lib.modules import shelf_sort
            entries.append({
                'name': name,
                'url': list_url,
                'context': list_url,
                'image': image,
                'action': action or 'movies',
                'sort_provider': 'trakt',
                'sort_key': shelf_sort.personal_shelf_key(username, list_slug),
            })
        except:
            pass
    return entries


def user_list_directory_movie(url, trakt_list_link, user=None):
    return build_user_list_directory(url, trakt_list_link, menu_type='movie')


def user_list_directory_tvshow(url, trakt_list_link, user=None):
    return build_user_list_directory(url, trakt_list_link, menu_type='tvshow')


def user_list_directory_episode(url, trakt_list_link, user=None):
    return build_user_list_directory(url, trakt_list_link, menu_type='episode')


def _manager_ids(imdb=None, tmdb=None):
    """Build a Trakt ids object; omit empty / placeholder values."""
    ids = {}
    if tmdb and str(tmdb) not in ('0', '', 'None'):
        try:
            ids['tmdb'] = int(tmdb)
        except Exception:
            pass
    if imdb and str(imdb) not in ('0', '', 'None'):
        imdb = str(imdb)
        if not imdb.startswith('tt'):
            imdb = 'tt' + re.sub(r'[^0-9]', '', imdb)
        if imdb not in ('tt', 'tt0'):
            ids['imdb'] = imdb
    return ids


def _manager_post(content, imdb=None, tmdb=None):
    ids = _manager_ids(imdb=imdb, tmdb=tmdb)
    if not ids:
        return None
    if content == 'movie':
        return {'movies': [{'ids': ids}]}
    return {'shows': [{'ids': ids}]}


def _ids_match(item_ids, wanted):
    if not isinstance(item_ids, dict) or not isinstance(wanted, dict):
        return False
    for key in ('tmdb', 'imdb'):
        item_value = item_ids.get(key)
        wanted_value = wanted.get(key)
        if item_value in (None, '', 'None', 0, '0') or wanted_value in (None, '', 'None', 0, '0'):
            continue
        if str(item_value) == str(wanted_value):
            return True
    return False


def _entry_media_ids(item, content):
    if not isinstance(item, dict):
        return None
    media_key = 'movie' if content == 'movie' else 'show'
    block = item.get(media_key)
    if isinstance(block, dict) and block.get('ids'):
        return block.get('ids')
    if content != 'movie':
        show = item.get('show')
        if isinstance(show, dict) and show.get('ids'):
            return show.get('ids')
    return None


def _trakt_paged_cache_payload(url):
    """Wrap paged results so empty lists still store in trakt_cache (falsy-safe)."""
    items = getTraktAsJsonPaged(url)
    if items is None:
        return None
    return {'items': items}


def _trakt_paged_cached(url):
    """Short-TTL paged Trakt fetch for manager membership (same table as shelves)."""
    from resources.lib.modules import trakt_cache
    data = trakt_cache.get(_trakt_paged_cache_payload, trakt_cache.TTL_LISTS_SEC, url)
    if data is None:
        return None
    if isinstance(data, dict) and 'items' in data:
        return data['items']
    return data if isinstance(data, list) else None


def _item_in_sync(kind, content, ids):
    """Return True/False if membership is known, or None if the check failed."""
    try:
        media = 'movies' if content == 'movie' else 'shows'
        items = _trakt_paged_cached('/users/me/%s/%s' % (kind, media))
        if items is None:
            return None
        for item in items:
            if _ids_match(_entry_media_ids(item, content), ids):
                return True
        return False
    except Exception:
        return None


def _item_in_personal_list(slug, content, ids):
    """Return True/False if membership is known, or None if the check failed."""
    try:
        items = _trakt_paged_cached('/users/me/lists/%s/items' % slug)
        if items is None:
            return None
        for item in items:
            if _ids_match(_entry_media_ids(item, content), ids):
                return True
        return False
    except Exception:
        return None


def _manager_still_member(path, content, ids):
    """Return True/False/None (None = membership check failed)."""
    path = path or ''
    if path == '/sync/collection/remove':
        return _item_in_sync('collection', content, ids)
    if path == '/sync/watchlist/remove':
        return _item_in_sync('watchlist', content, ids)
    if path.startswith('/users/me/lists/') and path.endswith('/items/remove'):
        # /users/me/lists/{slug}/items/remove
        parts = path.split('/')
        if len(parts) >= 6:
            return _item_in_personal_list(parts[4], content, ids)
    return True


def _manager_remove_label(path):
    path = path or ''
    if path == '/sync/collection/remove':
        return 'Library'
    if path == '/sync/watchlist/remove':
        return 'Watchlist'
    if path.startswith('/users/me/lists/') and path.endswith('/items/remove'):
        return 'list'
    return 'list'


def _sync_counts(bucket, keys):
    bucket = bucket or {}
    total = 0
    for key in keys:
        try:
            total += int(bucket.get(key, 0) or 0)
        except Exception:
            pass
    return total


def _not_found_count(data):
    not_found = (data or {}).get('not_found') or {}
    if not isinstance(not_found, dict):
        return 0
    total = 0
    for key in ('movies', 'shows', 'seasons', 'episodes', 'people'):
        try:
            total += len(not_found.get(key) or [])
        except Exception:
            pass
    return total


def _manager_sync_outcome(path, data):
    """Interpret Trakt sync JSON; never treat not_found / zero-adds as success."""
    if not isinstance(data, dict):
        return 'error'
    path = path or ''
    is_remove = path.endswith('/remove') or '/remove' in path
    if '/sync/collection' in path:
        # Shows are stored as collected episodes; some payloads also count shows.
        keys = ('movies', 'episodes', 'shows')
        if is_remove:
            # Non-zero deleted counts are definitive. Zero counts are common for
            # show-level Library removes — caller must confirm via membership.
            if _sync_counts(data.get('deleted'), keys):
                return 'deleted'
            return 'error'
        if _sync_counts(data.get('added'), keys):
            return 'added'
        if _sync_counts(data.get('existing'), keys):
            return 'existing'
        return 'error'
    if '/sync/watchlist' in path or '/users/me/lists/' in path:
        keys = ('movies', 'shows', 'seasons', 'episodes', 'people')
        if is_remove:
            # Do not treat deleted:0 as success — that left Watchlist items
            # (e.g. One Piece) still on Trakt while the UI toasted Removed.
            if _sync_counts(data.get('deleted'), keys):
                return 'deleted'
            return 'error'
        if _sync_counts(data.get('added'), keys):
            return 'added'
        if _sync_counts(data.get('existing'), keys):
            return 'existing'
        return 'error'
    return 'ok' if data else 'error'


def manager(name, imdb, tmdb, content):
    try:
        if not getTraktCredentialsInfo():
            return control.infoDialog('Authorise Trakt first.', sound=True, icon='ERROR')
        # Capture before selectDialog — after RunPlugin(-1) + dialogs,
        # Container.FolderPath is often wrong/empty so Refresh misses the shelf.
        folder_at_open = ''
        try:
            folder_at_open = control.infoLabel('Container.FolderPath') or ''
        except Exception:
            folder_at_open = ''
        ids = _manager_ids(imdb=imdb, tmdb=tmdb)
        post = _manager_post(content, imdb=imdb, tmdb=tmdb)
        if not post:
            return control.infoDialog('Missing IDs for Trakt Lists Manager.', heading=str(name), sound=True, icon='ERROR')
        items = []
        # State-aware Library, Watchlist, and personal lists (Add OR Remove).
        # If a personal-list membership check fails (rate-limit), show both for
        # that list only so Manager stays usable.
        if _item_in_sync('collection', content, ids):
            items.append(('Remove from [B]Library[/B]', '/sync/collection/remove'))
        else:
            items.append(('Add to [B]Library[/B]', '/sync/collection'))
        if _item_in_sync('watchlist', content, ids):
            items.append(('Remove from [B]Watchlist[/B]', '/sync/watchlist/remove'))
        else:
            items.append(('Add to [B]Watchlist[/B]', '/sync/watchlist'))
        items.append(('Add to [B]new List[/B]', '/users/me/lists/%s/items'))
        result = getTraktAsJsonPaged('/users/me/lists') or []
        for entry in result:
            try:
                list_name = entry['name']
                slug = entry['ids']['slug']
            except Exception:
                continue
            in_list = _item_in_personal_list(slug, content, ids)
            if in_list is True:
                items.append((
                    ensure_str('Remove from [B]%s[/B]' % list_name),
                    '/users/me/lists/%s/items/remove' % slug
                ))
            elif in_list is False:
                items.append((
                    ensure_str('Add to [B]%s[/B]' % list_name),
                    '/users/me/lists/%s/items' % slug
                ))
            else:
                items.append((
                    ensure_str('Add to [B]%s[/B]' % list_name),
                    '/users/me/lists/%s/items' % slug
                ))
                items.append((
                    ensure_str('Remove from [B]%s[/B]' % list_name),
                    '/users/me/lists/%s/items/remove' % slug
                ))
        select = control.selectDialog([i[0] for i in items], 'Trakt Lists Manager')
        if select == -1:
            return
        path = items[select][1]
        if '%s' in path:
            t = 'Add to [B]new List[/B]'
            k = control.keyboard('', t)
            k.doModal()
            new = k.getText() if k.isConfirmed() else None
            if (new == None or new == ''):
                return
            result = __getTrakt('/users/me/lists', post={"name": new, "privacy": "private"})[0]
            try:
                slug = client_utils.json_loads_as_str(result)['ids']['slug']
            except:
                return control.infoDialog('Could not create list.', heading=str(name), sound=True, icon='ERROR')
            path = path % slug
        result = __getTrakt(path, post=post)[0]
        if result is None:
            return control.infoDialog('Trakt request failed.', heading=str(name), sound=True, icon='ERROR')
        try:
            data = client_utils.json_loads_as_str(result) if not isinstance(result, dict) else result
        except Exception:
            data = None
        outcome = _manager_sync_outcome(path, data)
        is_remove = path.endswith('/remove') or '/remove' in path
        # Watchlist / personal lists: trust Trakt deleted counts only (same as
        # Red Light). Re-paging membership after remove was slow and, when
        # rate-limited mid-walk, toasted Removed while the title stayed on Trakt.
        # Library show-level removes often return deleted:0 even when they worked
        # — confirm with one membership check only in that case.
        if is_remove and '/sync/collection' in path and outcome != 'deleted':
            still = _item_in_sync('collection', content, ids)
            if still is False:
                outcome = 'deleted'
            elif still is True:
                outcome = 'error'
        try:
            from kodi_six import xbmc as _xbmc
            _xbmc.log(
                '[Gratis Red] Trakt Manager path=%s post=%s response=%s outcome=%s' % (
                    path, post, data, outcome),
                _xbmc.LOGINFO)
        except Exception:
            pass
        label = _manager_remove_label(path)
        try:
            chosen = items[select][0]
            if '[B]' in chosen and '[/B]' in chosen:
                label = chosen.split('[B]', 1)[1].split('[/B]', 1)[0]
        except Exception:
            pass
        if outcome == 'error':
            return control.infoDialog('Trakt did not update this item.', heading=str(name), sound=True, icon='ERROR')
        if outcome == 'existing':
            return control.infoDialog('Already on %s.' % label, heading=str(name), sound=True)
        if outcome == 'deleted':
            message = 'Removed from %s.' % label
        else:
            message = 'Added to %s.' % label
        try:
            from resources.lib.modules import trakt_cache
            trakt_cache.clear_shelf_caches()
        except Exception:
            pass
        shelf, list_slug = _manager_shelf_from_path(path)
        try:
            if shelf and is_remove and outcome == 'deleted':
                note_shelf_exclusion(shelf, imdb=imdb, tmdb=tmdb)
                still = _manager_still_member(path, content, ids)
                try:
                    from kodi_six import xbmc as _xbmc
                    _xbmc.log(
                        '[Gratis Red] Trakt Manager after-remove still_member=%s shelf=%s ids=%s folder=%s' % (
                            still, shelf, ids, folder_at_open),
                        _xbmc.LOGINFO)
                except Exception:
                    pass
                if still is True and shelf in ('watchlist', 'collection'):
                    trakt_id = _trakt_id_from_sync(shelf, content, ids)
                    if trakt_id:
                        retry_post = (
                            {'movies': [{'ids': {'trakt': trakt_id}}]}
                            if content == 'movie' else
                            {'shows': [{'ids': {'trakt': trakt_id}}]}
                        )
                        try:
                            __getTrakt(path, post=retry_post)
                        except Exception:
                            pass
            elif shelf and not is_remove and outcome in ('added', 'existing', 'ok'):
                clear_shelf_exclusion(shelf, imdb=imdb, tmdb=tmdb)
        except Exception:
            pass
        try:
            # Refresh the open shelf/list — exclusion drops the row on rebuild.
            if shelf and is_remove and outcome == 'deleted' and folder_at_open:
                from six.moves import urllib_parse
                folder_raw = urllib_parse.unquote(folder_at_open)
                if _folder_matches_manager_shelf(folder_raw, shelf, list_slug):
                    control.refresh_folder(folder_at_open)
        except Exception:
            pass
        control.infoDialog(message, heading=str(name), sound=True, icon=control.infoLabel('ListItem.Icon'))
    except Exception as e:
        try:
            log_utils.log('Trakt Manager failed: %s' % e)
        except Exception:
            pass
        control.infoDialog('Trakt Lists Manager failed.', heading=str(name), sound=True, icon='ERROR')


def getPlaybackEpisodes():
    return getTraktAsJsonPaged('/sync/playback/episodes?extended=full') or []


def getPlaybackMovies():
    return getTraktAsJsonPaged('/sync/playback/movies?extended=full') or []


def getActivity():
    try:
        i = getTraktAsJson('/sync/last_activities')
        if not valid_trakt_activities(i):
            return
        activity = []
        activity.append(i['movies']['collected_at'])
        activity.append(i['episodes']['collected_at'])
        activity.append(i['movies']['watchlisted_at'])
        activity.append(i['shows']['watchlisted_at'])
        activity.append(i['seasons']['watchlisted_at'])
        activity.append(i['episodes']['watchlisted_at'])
        activity.append(i['lists']['updated_at'])
        activity.append(i['lists']['liked_at'])
        activity = [int(cleandate.iso_2_utc(i)) for i in activity]
        activity = sorted(activity, key=int)[-1]
        return activity
    except:
        pass


def getWatchedActivity():
    try:
        i = getTraktAsJson('/sync/last_activities')
        if not valid_trakt_activities(i):
            return
        activity = []
        activity.append(i['movies']['watched_at'])
        activity.append(i['episodes']['watched_at'])
        activity = [int(cleandate.iso_2_utc(i)) for i in activity]
        activity = sorted(activity, key=int)[-1]
        return activity
    except:
        pass


def syncMovies(user):
    try:
        if getTraktCredentialsInfo() == False:
            return
        indicators = getTraktAsJsonPaged('/users/me/watched/movies') or []
        indicators = [i['movie']['ids'] for i in indicators]
        indicators = [str(i['imdb']) for i in indicators if 'imdb' in i]
        return indicators
    except:
        pass


def cachesyncMovies(timeout=0):
    indicators = cache.get(syncMovies, timeout, control.setting('trakt.user').strip())
    return indicators


def timeoutsyncMovies():
    timeout = cache.timeout(syncMovies, control.setting('trakt.user').strip())
    return timeout


def syncTVShows(user, sync_version='progress_v1'):
    """Watched TV indicators for overlays.

    Trakt no longer returns season/episode breakdown with extended=full (#775).
    Use /sync/watched/shows?extended=progress (same pattern as Red Light).
    sync_version busts the local cache key after the progress migration.
    """
    try:
        if getTraktCredentialsInfo() == False:
            return
        indicators = getTraktAsJsonPaged('/sync/watched/shows?extended=progress') or []
        rows = []
        for item in indicators:
            try:
                show = item.get('show') or {}
                tmdb = (show.get('ids') or {}).get('tmdb')
                if not tmdb:
                    continue
                aired = show.get('aired_episodes') or 0
                watched = []
                for season in item.get('seasons') or []:
                    try:
                        snum = int(season.get('number'))
                    except Exception:
                        continue
                    for ep in season.get('episodes') or []:
                        try:
                            watched.append((snum, int(ep.get('number'))))
                        except Exception:
                            continue
                rows.append((str(tmdb), int(aired), watched))
            except Exception:
                continue
        return rows
    except:
        pass


def cachesyncTVShows(timeout=0):
    indicators = cache.get(syncTVShows, timeout, control.setting('trakt.user').strip(), 'progress_v1')
    return indicators


def timeoutsyncTVShows():
    timeout = cache.timeout(syncTVShows, control.setting('trakt.user').strip(), 'progress_v1')
    if not timeout:
        timeout = 0
    return timeout


def syncSeason(imdb):
    try:
        if getTraktCredentialsInfo() == False:
            return
        indicators = getTraktAsJson('/shows/%s/progress/watched?specials=false&hidden=false' % imdb)
        indicators = indicators['seasons']
        indicators = [(i['number'], [x['completed'] for x in i['episodes']]) for i in indicators]
        indicators = ['%01d' % int(i[0]) for i in indicators if not False in i[1]]
        return indicators
    except:
        pass


def _history_id_candidates(imdb=None, tmdb=None, tvdb=None):
    """Ordered (key, value) attempts for sync/history — TMDb, then TVDb, then IMDb."""
    candidates = []
    if tmdb and str(tmdb) not in ('0', '', 'None'):
        try:
            candidates.append(('tmdb', int(tmdb)))
        except Exception:
            pass
    if tvdb and str(tvdb) not in ('0', '', 'None'):
        try:
            candidates.append(('tvdb', int(tvdb)))
        except Exception:
            pass
    if imdb and str(imdb) not in ('0', '', 'None'):
        imdb = str(imdb).strip()
        if not imdb.startswith('tt'):
            imdb = 'tt' + re.sub(r'[^0-9]', '', imdb)
        if imdb not in ('tt', 'tt0'):
            candidates.append(('imdb', imdb))
    return candidates


def _history_sync_success(body, path, success_key):
    if not body:
        return False
    try:
        data = client_utils.json_loads_as_str(body) if not isinstance(body, dict) else body
    except Exception:
        try:
            data = json.loads(body)
        except Exception:
            return False
    if not isinstance(data, dict):
        return False
    result_key = 'deleted' if ('/remove' in (path or '')) else 'added'
    try:
        return int((data.get(result_key) or {}).get(success_key, 0) or 0) > 0
    except Exception:
        return False


def _history_mark(path, media, imdb=None, tmdb=None, tvdb=None, season=None, episode=None):
    """Post sync/history with Red Light-style ID fallback (tmdb → tvdb → imdb)."""
    candidates = _history_id_candidates(imdb=imdb, tmdb=tmdb, tvdb=tvdb)
    if not candidates:
        return None
    # Trakt history responses count TV under "episodes" (even for whole-show marks).
    success_key = 'movies' if media == 'movies' else 'episodes'
    if season is not None:
        season = int('%01d' % int(season))
    if episode is not None:
        episode = int('%01d' % int(episode))
    last_body = None
    for key, value in candidates:
        if media == 'movies':
            payload = {'movies': [{'ids': {key: value}}]}
        elif season is not None and episode is not None:
            payload = {'shows': [{'ids': {key: value}, 'seasons': [{'number': season, 'episodes': [{'number': episode}]}]}]}
        elif season is not None:
            payload = {'shows': [{'ids': {key: value}, 'seasons': [{'number': season}]}]}
        else:
            payload = {'shows': [{'ids': {key: value}}]}
        body, _headers = __getTrakt(path, post=payload)
        last_body = body
        if _history_sync_success(body, path, success_key):
            return body
    return last_body


def markMovieAsWatched(imdb, tmdb=None, tvdb=None):
    return _history_mark('/sync/history', 'movies', imdb=imdb, tmdb=tmdb, tvdb=tvdb)


def markMovieAsNotWatched(imdb, tmdb=None, tvdb=None):
    return _history_mark('/sync/history/remove', 'movies', imdb=imdb, tmdb=tmdb, tvdb=tvdb)


def markTVShowAsWatched(imdb, tmdb=None, tvdb=None):
    return _history_mark('/sync/history', 'shows', imdb=imdb, tmdb=tmdb, tvdb=tvdb)


def markTVShowAsNotWatched(imdb, tmdb=None, tvdb=None):
    return _history_mark('/sync/history/remove', 'shows', imdb=imdb, tmdb=tmdb, tvdb=tvdb)


def markSeasonAsWatched(imdb, season, tmdb=None, tvdb=None):
    return _history_mark('/sync/history', 'shows', imdb=imdb, tmdb=tmdb, tvdb=tvdb, season=season)


def markSeasonAsNotWatched(imdb, season, tmdb=None, tvdb=None):
    return _history_mark('/sync/history/remove', 'shows', imdb=imdb, tmdb=tmdb, tvdb=tvdb, season=season)


def markEpisodeAsWatched(imdb, season, episode, tmdb=None, tvdb=None):
    return _history_mark('/sync/history', 'shows', imdb=imdb, tmdb=tmdb, tvdb=tvdb, season=season, episode=episode)


def markEpisodeAsNotWatched(imdb, season, episode, tmdb=None, tvdb=None):
    return _history_mark('/sync/history/remove', 'shows', imdb=imdb, tmdb=tmdb, tvdb=tvdb, season=season, episode=episode)


def getMovieTranslation(id, lang, full=False):
    url = '/movies/%s/translations/%s' % (id, lang)
    try:
        item = getTraktAsJson(url)[0]
        return item if full else item.get('title')
    except:
        pass


def getTVShowTranslation(id, lang, season='', episode='', full=False):
    if season and episode:
        url = '/shows/%s/seasons/%s/episodes/%s/translations/%s' % (id, season, episode, lang)
    else:
        url = '/shows/%s/translations/%s' % (id, lang)
    try:
        item = getTraktAsJson(url)[0]
        return item if full else item.get('title')
    except:
        pass


def getMovieAliases(id):
    try:
        return getTraktAsJson('/movies/%s/aliases' % id)
    except:
        return []


def getTVShowAliases(id):
    try:
        return getTraktAsJson('/shows/%s/aliases' % id)
    except:
        return []


def getMovieSummary(id, full=False):
    try:
        url = '/movies/%s' % id
        if full:
            url += '?extended=full'
        return getTraktAsJson(url)
    except:
        return


def getTVShowSummary(id, full=False):
    try:
        url = '/shows/%s' % id
        if full:
            url += '?extended=full'
        return getTraktAsJson(url)
    except:
        return


def getSeasonsSummary(id, full=False, episodes=False):  #Uses imdb_id, full or episodes but not both.
    try:
        url = '/shows/%s/seasons' % id
        if full:
            url += '?extended=full'
        if episodes:
            url += '?extended=episodes'
        return getTraktAsJson(url)
    except:
        return


def getEpisodeSummary(id, season, episode='', full=False):
    try:
        if not episode:
            url = '/shows/%s/seasons/%s' % (id, season)
            #url += '?translations=en'
        else:
            url = '/shows/%s/seasons/%s/episodes/%s' % (id, season, episode)
        if full:
            url += '?extended=full'
        return getTraktAsJson(url)
    except:
        return


#/shows/game-of-thrones/seasons/1/people
#/shows/game-of-thrones/seasons/1/people?extended=guest_stars

#/shows/game-of-thrones/seasons/1/episodes/1/people
#/shows/game-of-thrones/seasons/1/episodes/1/people?extended=guest_stars


def getPeople(id, content_type, full=False): #Uses imdb_id
    try:
        url = '/%s/%s/people' % (content_type, id)
        if full:
            url += '?extended=full'
        return getTraktAsJson(url)
    except:
        return


def getStudio(id, content_type): #Uses imdb_id
    try:
        url = '/%s/%s/studios' % (content_type, id)
        return getTraktAsJson(url)
    except:
        return


def getGenre(content, type, type_id):
    try:
        r = getTraktAsJson('/search/%s/%s?type=%s&extended=full' % (type, type_id, content))
        return r[0].get(content, {}).get('genres', [])
    except:
        return []


def SearchMovie(title, year='', full=False):
    try:
        url = '/search/movie?query=%s' % quote_plus(title)
        if year:
            url += '&year=%s' % year
        if full:
            url += '&extended=full'
        return getTraktAsJson(url)
    except:
        return


def SearchTVShow(title, year='', full=False):
    try:
        url = '/search/show?query=%s' % quote_plus(title)
        if year:
            url += '&year=%s' % year
        if full:
            url += '&extended=full'
        return getTraktAsJson(url)
    except:
        return


def SearchEpisode(title, season, episode, full=False):
    try:
        url = '/search/%s/seasons/%s/episodes/%s' % (title, season, episode)
        if full:
            url += '&extended=full'
        return getTraktAsJson(url)
    except:
        return


def SearchAll(title, year='', full=False):
    try:
        return SearchMovie(title, year, full) + SearchTVShow(title, year, full)
    except:
        return


