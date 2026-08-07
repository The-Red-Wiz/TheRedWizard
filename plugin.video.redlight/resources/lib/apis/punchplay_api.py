# -*- coding: utf-8 -*-
"""PunchPlay Platform API v1 — watched provider, lists, and native scrobble."""
import json
import time
import uuid
import requests
from caches.settings_cache import get_setting, set_setting
from caches import punchplay_cache as pp_cache
from modules import kodi_utils, settings
from modules.http_defaults import META_API_TIMEOUT
from modules.utils import copy2clip, make_qrcode

BASE_URL = 'https://punchplay.tv'
API_PREFIX = '/api/platform/v1'
APP_UA = 'RedLight-PunchPlay/%s' % kodi_utils.addon_version()
DEFAULT_SCOPES = (
	'profile:read playback:read playback:write history:read history:write '
	'lists:read lists:write ratings:read ratings:write collection:read collection:write'
)
WATCHED_THRESHOLD = 0.9
STATUS_PLANNING = 'PLANNING'
STATUS_WATCHING = 'WATCHING'
STATUS_ON_HOLD = 'ON_HOLD'
STATUS_DROPPED = 'DROPPED'
STATUS_WATCHED = 'WATCHED'

def _icon():
	return kodi_utils.get_icon('punchplay') or kodi_utils.addon_icon()

def punchplay_client_id():
	return (get_setting('redlight.punchplay.client', '') or '').strip()

def _device_id():
	from caches.settings_cache import settings_cache
	device_id = settings_cache.read_db_value('punchplay.device_id')
	if device_id in (None, '', 'empty_setting', '0'):
		device_id = str(uuid.uuid4())
		set_setting('punchplay.device_id', device_id)
	return str(device_id)

def _token():
	from caches.settings_cache import settings_cache
	token = settings_cache.read_db_value('punchplay.token')
	if token in (None, '0', '', 'empty_setting'):
		token = get_setting('redlight.punchplay.token', '0')
	return token

def _refresh_token():
	from caches.settings_cache import settings_cache
	token = settings_cache.read_db_value('punchplay.refresh')
	if token in (None, '0', '', 'empty_setting'):
		token = get_setting('redlight.punchplay.refresh', '0')
	return token

def punchplay_user_active():
	return settings.punchplay_user_active()

def punchplay_official_status(media_type=None):
	if kodi_utils.service_scrobbler_defer(
		'script.punchplay',
		auth_keys=('access_token', 'token', 'authorization', 'Authorization'),
		scrobble_enable_keys=('auto_scrobble', 'autoscrobble', 'scrobble_enabled', 'enabled')):
		return False
	return True

def _url(path, query=None):
	url = '%s%s%s' % (BASE_URL.rstrip('/'), API_PREFIX, path if path.startswith('/') else '/%s' % path)
	if query:
		parts = []
		for key, value in query.items():
			if value in (None, ''): continue
			parts.append('%s=%s' % (key, requests.utils.quote(str(value), safe='')))
		if parts: url = '%s?%s' % (url, '&'.join(parts))
	return url

def _headers(with_auth=True):
	headers = {'Content-Type': 'application/json', 'User-Agent': APP_UA, 'Accept': 'application/json'}
	if with_auth:
		token = _token()
		if token not in (None, '0', '', 'empty_setting'):
			headers['Authorization'] = 'Bearer %s' % token
	return headers

def _save_tokens(payload):
	access = payload.get('access_token')
	refresh = payload.get('refresh_token')
	if not access: return False
	set_setting('punchplay.token', access)
	if refresh: set_setting('punchplay.refresh', refresh)
	expires_in = int(payload.get('expires_in') or 3600)
	set_setting('punchplay.expires', str(int(time.time()) + max(60, expires_in) - 60))
	from caches.settings_cache import settings_cache
	settings_cache.clear_db_cache()
	return True

def _refresh_access_token():
	client_id = punchplay_client_id()
	refresh = _refresh_token()
	if not client_id or refresh in (None, '0', '', 'empty_setting'): return False
	try:
		resp = requests.post(
			_url('/auth/refresh'),
			data=json.dumps({'client_id': client_id, 'refresh_token': refresh}),
			headers=_headers(with_auth=False), timeout=META_API_TIMEOUT)
		if resp.status_code != 200: return False
		return _save_tokens(resp.json() or {})
	except Exception as e:
		kodi_utils.logger('PunchPlay', 'refresh failed: %s' % e)
		return False

def call_punchplay(path, method='get', data=None, query=None, retry=True):
	if not punchplay_user_active() and method != 'get':
		pass
	url = _url(path, query)
	try:
		if method == 'get':
			resp = requests.get(url, headers=_headers(), timeout=META_API_TIMEOUT)
		elif method == 'delete':
			resp = requests.delete(url, headers=_headers(), timeout=META_API_TIMEOUT)
		elif method == 'patch':
			resp = requests.patch(url, data=json.dumps(data or {}), headers=_headers(), timeout=META_API_TIMEOUT)
		else:
			resp = requests.post(url, data=json.dumps(data or {}), headers=_headers(), timeout=META_API_TIMEOUT)
		if resp.status_code == 401 and retry and _refresh_access_token():
			return call_punchplay(path, method=method, data=data, query=query, retry=False)
		if resp.status_code == 204: return True
		if 200 <= resp.status_code < 300:
			if not resp.content: return True
			try: return resp.json()
			except: return True
		try: body = resp.json() or {}
		except Exception: body = {}
		detail = ''
		if isinstance(body, dict):
			detail = body.get('message') or body.get('error') or ''
			if body.get('required_scope'):
				detail = '%s (requires %s)' % (detail, body.get('required_scope'))
		kodi_utils.logger('PunchPlay', '%s %s HTTP %s%s' % (
			method.upper(), path, resp.status_code, (': %s' % detail) if detail else ''))
		return body if isinstance(body, dict) else None
	except Exception as e:
		kodi_utils.logger('PunchPlay Error', str(e))
		return None

def _title_kind(media_type):
	return 'movie' if media_type in ('movie', 'movies') else 'show'

def _media_ids(tmdb_id):
	try: tid = int(tmdb_id)
	except: return None
	if tid <= 0: return None
	return {'tmdb': tid, 'imdb': '', 'tvdb': ''}

def _library_items(payload):
	if payload is None: return []
	if isinstance(payload, list): return payload
	if isinstance(payload, dict):
		if payload.get('error') and not payload.get('items'): return []
		items = payload.get('items')
		if isinstance(items, list): return items
	return []

def _api_ok(payload):
	return isinstance(payload, dict) and not payload.get('error')

def _paginate_history(limit=100, max_pages=50):
	items, cursor, pages = [], None, 0
	while pages < max_pages:
		pages += 1
		query = {'limit': limit}
		if cursor: query['cursor'] = cursor
		data = call_punchplay('/me/history', method='get', query=query) or {}
		batch = _library_items(data)
		if not batch: break
		items.extend(batch)
		cursor = data.get('nextCursor') if isinstance(data, dict) else None
		if not cursor: break
	return items

def _paginate_interaction_library(path, max_pages=50):
	"""Favourites / watch-status return items + hasMore (page params when needed)."""
	data = call_punchplay(path, method='get') or {}
	items = list(_library_items(data))
	page = 2
	while page <= max_pages and isinstance(data, dict) and data.get('hasMore'):
		page_size = data.get('pageSize') or 100
		data = call_punchplay(path, method='get', query={'page': page, 'pageSize': page_size}) or {}
		batch = _library_items(data)
		if not batch: break
		items.extend(batch)
		page += 1
	return items

# ---------- Auth ----------

def punchplay_test_client_id():
	"""Probe /auth/device/code — same acceptance check Trakt uses for client keys."""
	client_id = punchplay_client_id()
	if not client_id:
		return False, 'PunchPlay Client ID Key is not set.'
	try:
		resp = requests.post(
			_url('/auth/device/code'),
			data=json.dumps({'client_id': client_id, 'scope': DEFAULT_SCOPES}),
			headers=_headers(with_auth=False), timeout=META_API_TIMEOUT)
		if resp.status_code == 200:
			body = {}
			try: body = resp.json() or {}
			except: body = {}
			if body.get('device_code'):
				return True, 'PunchPlay Client ID Key is valid.'
			return False, 'PunchPlay Client ID Key failed.[CR]PunchPlay returned an empty device code.'
		detail = ''
		try:
			payload = resp.json() or {}
			if isinstance(payload, dict):
				detail = payload.get('error_description') or payload.get('message') or payload.get('error') or ''
		except: detail = ''
		if not detail: detail = (resp.text or '').strip() or 'No details returned.'
		return False, 'PunchPlay Client ID Key failed.[CR]PunchPlay rejected the Client ID (HTTP %s).[CR]%s' % (resp.status_code, detail)
	except Exception as e:
		return False, 'PunchPlay Client ID Key failed.[CR]Could not reach PunchPlay: %s' % str(e)

def punchplay_authenticate(dummy=''):
	icon = _icon()
	client_id = punchplay_client_id()
	if not client_id:
		return kodi_utils.ok_dialog(
			heading='PunchPlay',
			text='PunchPlay [B]Client ID Key[/B] is missing.[CR][CR]'
			'Red Light ships a default — if you cleared it, enter the Client ID from your app at '
			'punchplay.tv/developers (Meta Accounts > PunchPlay > Client ID Key).')
	if kodi_utils.addon_installed('script.punchplay') and kodi_utils.addon_enabled('script.punchplay'):
		try:
			inst = kodi_utils.addon('script.punchplay')
			ext = ''
			for key in ('access_token', 'token'):
				try:
					ext = str(inst.getSetting(key) or '').strip()
					if ext: break
				except: pass
		except: ext = ''
		if ext:
			kodi_utils.ok_dialog(
				heading='PunchPlay',
				text='The official [B]PunchPlay[/B] Kodi add-on appears authorised.[CR][CR]'
				'Red Light will defer native scrobble to [B]script.punchplay[/B] when it is active '
				'so events are not sent twice. You can still authorise here for lists and watched sync.')
	try:
		resp = requests.post(
			_url('/auth/device/code'),
			data=json.dumps({'client_id': client_id, 'scope': DEFAULT_SCOPES}),
			headers=_headers(with_auth=False), timeout=META_API_TIMEOUT)
		code_data = resp.json() if resp.status_code == 200 else None
	except Exception as e:
		kodi_utils.logger('PunchPlay', 'device/code: %s' % e)
		code_data = None
	if not code_data or not code_data.get('device_code'):
		return kodi_utils.notification('PunchPlay Authorisation Failed', 3000, icon)
	user_code = str(code_data.get('user_code') or '')
	device_code = code_data.get('device_code')
	verification_url = (code_data.get('verification_uri') or 'https://punchplay.tv/link').rstrip('/')
	auth_url = code_data.get('verification_uri_complete') or (
		'%s?code=%s' % (verification_url, user_code) if user_code else verification_url)
	expires_in = int(code_data.get('expires_in') or 600)
	interval = 5
	qr_code = make_qrcode(auth_url) or icon
	try: copy2clip(auth_url)
	except: pass
	content = (
		'Enter [B]%s[/B] at [B]%s[/B][CR]OR scan the [B]QR Code[/B][CR]'
		'Link copied to clipboard[CR][CR]Waiting for authorisation...'
		% (user_code, verification_url.replace('https://', '').replace('http://', '')))
	progress = kodi_utils.progress_dialog('PunchPlay Authorise', qr_code)
	progress.update(content, 0)
	expires = time.time() + expires_in
	token_payload = None
	while time.time() < expires:
		if progress.iscanceled():
			progress.close()
			return kodi_utils.notification('PunchPlay Authorisation Canceled', 3000, icon)
		try:
			poll = requests.post(
				_url('/auth/device/token'),
				data=json.dumps({
					'client_id': client_id,
					'device_code': device_code,
					'device_id': _device_id(),
					'device_name': kodi_utils.get_infolabel('System.FriendlyName') or 'Kodi'
				}),
				headers=_headers(with_auth=False), timeout=META_API_TIMEOUT)
			body = {}
			try: body = poll.json() or {}
			except: body = {}
			if poll.status_code == 200 and body.get('access_token'):
				token_payload = body
				break
			error = body.get('error') or ''
			if error in ('expired', 'access_denied', 'expired_token'): break
			if poll.status_code == 429:
				kodi_utils.sleep(30000)
				continue
		except Exception as e:
			kodi_utils.logger('PunchPlay', 'poll: %s' % e)
		progress.update(content, int(100 * (1 - (expires - time.time()) / float(expires_in))))
		kodi_utils.sleep(interval * 1000)
	try: progress.close()
	except: pass
	if not token_payload or not _save_tokens(token_payload):
		return kodi_utils.notification('PunchPlay Authorisation Failed', 3000, icon)
	username = 'PunchPlay User'
	try:
		me = call_punchplay('/me', method='get') or {}
		username = (me.get('username') or me.get('name') or
			(me.get('user') or {}).get('username') or username)
	except: pass
	set_setting('punchplay.user', str(username))
	from caches.settings_cache import settings_cache
	settings_cache.clear_db_cache()
	kodi_utils.notification('PunchPlay Account Authorised', 3000, icon)
	try: settings.offer_watched_provider(4, 'PunchPlay')
	except: pass
	try:
		from threading import Thread
		Thread(target=punchplay_sync_activities, kwargs={'force_update': True}).start()
	except: pass
	try: kodi_utils.container_refresh()
	except: pass
	return True

def punchplay_revoke_authentication(dummy=''):
	settings.fallback_watched_provider_on_revoke(4)
	set_setting('punchplay.user', 'empty_setting')
	set_setting('punchplay.token', '0')
	set_setting('punchplay.refresh', '0')
	set_setting('punchplay.expires', '0')
	kodi_utils.notification('PunchPlay Authorisation Reset', 3000, _icon())
	try: kodi_utils.container_refresh()
	except: pass
	return True

# ---------- Lists / shelves ----------

def _tmdb_is_anime(tmdb_id):
	"""PunchPlay watch-status/favourites often omit isAnime — use TMDb anime keyword."""
	try:
		from modules.metadata import is_anime_check, tvshow_meta
		from modules.settings import tmdb_api_key, mpaa_region
		from modules.utils import get_datetime, get_current_timestamp
		if is_anime_check(tmdb_id=tmdb_id): return True
		meta = tvshow_meta('tmdb_id', str(tmdb_id), tmdb_api_key(), mpaa_region(), get_datetime(), get_current_timestamp())
		return bool(meta) and is_anime_check(meta=meta)
	except: return False

def _entry_to_list_item(entry, order):
	tmdb_id = entry.get('tmdbId') or entry.get('tmdb_id') or entry.get('sourceId')
	ids = _media_ids(tmdb_id)
	if not ids: return None
	kind = (entry.get('kind') or entry.get('type') or 'movie').lower()
	is_anime = bool(entry.get('isAnime')) or kind == 'anime'
	if not is_anime and kind not in ('movie', 'movies') and tmdb_id:
		is_anime = _tmdb_is_anime(tmdb_id)
	if kind in ('movie', 'movies'): media_type = 'movie'
	elif is_anime: media_type = 'anime'
	else: media_type = 'show'
	return {
		'order': order,
		'media_ids': ids,
		'type': media_type,
		'title': entry.get('title') or '',
		'collected_at': entry.get('addedAt') or entry.get('updatedAt') or entry.get('favouritedAt') or '',
		'released': str(entry.get('year') or '')
	}

def _filter_status_items(status):
	items = []
	for count, entry in enumerate(_paginate_interaction_library('/me/watch-status'), 1):
		if (entry.get('showStatus') or '') != status: continue
		row = _entry_to_list_item(entry, count)
		if row: items.append(row)
	return items

def _normalize_media_kind(media_kind):
	if media_kind in ('movies', 'movie'): return 'movie'
	if media_kind == 'anime': return 'anime'
	return 'show'

def _filter_kind(items, media_kind):
	want = _normalize_media_kind(media_kind)
	return [item for item in items if item.get('type') == want]

def punchplay_plantowatch(media_kind, page_no=None):
	return _filter_kind(_filter_status_items(STATUS_PLANNING), media_kind)

def punchplay_watching(media_kind, page_no=None):
	return _filter_kind(_filter_status_items(STATUS_WATCHING), media_kind)

def punchplay_hold(media_kind, page_no=None):
	return _filter_kind(_filter_status_items(STATUS_ON_HOLD), media_kind)

def punchplay_completed(media_kind, page_no=None):
	return _filter_kind(_filter_status_items(STATUS_WATCHED), media_kind)

def punchplay_dropped(media_kind, page_no=None):
	return _filter_kind(_filter_status_items(STATUS_DROPPED), media_kind)

def punchplay_favorites(media_kind, page_no=None):
	items = []
	for count, entry in enumerate(_paginate_interaction_library('/me/favourites'), 1):
		row = _entry_to_list_item(entry, count)
		if row: items.append(row)
	return _filter_kind(items, media_kind)

def punchplay_collection(media_kind, page_no=None):
	want = _normalize_media_kind(media_kind)
	# OpenAPI: type is optional. Add-to-collection kind is only movie|show (no anime),
	# so anime often lands as type=show. Fetch all, then classify client-side.
	raw = list(_library_items(call_punchplay('/me/collection', method='get')))
	if not raw:
		qtypes = ('movie',) if want == 'movie' else (('anime', 'show') if want == 'anime' else ('show',))
		seen_raw = set()
		for qtype in qtypes:
			for entry in _library_items(call_punchplay('/me/collection', method='get', query={'type': qtype})):
				eid = entry.get('id') if entry.get('id') is not None else entry.get('tmdbId')
				if eid in seen_raw: continue
				if eid is not None: seen_raw.add(eid)
				raw.append(entry)
	items, seen = [], set()
	for entry in raw:
		row = _entry_to_list_item(entry, len(items) + 1)
		if not row or row.get('type') != want: continue
		tid = (row.get('media_ids') or {}).get('tmdb')
		if tid in seen: continue
		if tid is not None: seen.add(tid)
		items.append(row)
	try:
		kodi_utils.logger('PunchPlay', 'collection %s: raw=%s kept=%s' % (want, len(raw), len(items)))
	except: pass
	return items

def _watchlist_list_id():
	cached = pp_cache.punchplay_cache.get('watchlist_list_id')
	if cached: return cached
	for entry in _library_items(call_punchplay('/me/lists', method='get')):
		if entry.get('isWatchlist'):
			list_id = entry.get('id')
			if list_id:
				pp_cache.punchplay_cache.set('watchlist_list_id', list_id)
				return list_id
	return None

def punchplay_watchlist(media_kind, page_no=None):
	list_id = _watchlist_list_id()
	if not list_id:
		# Fallback: PLANNING status doubles as plan/watchlist when no dedicated list.
		return punchplay_plantowatch(media_kind, page_no)
	return punchplay_list_items(list_id, media_kind)

def punchplay_get_lists():
	return _library_items(call_punchplay('/me/lists', method='get'))

def _punchplay_list_items_paginated(list_id):
	"""Paginated GET /lists/{id}/items — documented for dynamic lists."""
	items, offset = [], 0
	while True:
		data = call_punchplay('/lists/%s/items' % list_id, method='get', query={'offset': offset, 'limit': 100}) or {}
		if isinstance(data, dict) and data.get('error') and not data.get('items'):
			break
		batch = _library_items(data)
		if not batch: break
		items.extend(batch)
		next_offset = data.get('nextOffset') if isinstance(data, dict) else None
		if next_offset in (None, offset): break
		offset = next_offset
	return items

def punchplay_list_items(list_id, media_kind='movies'):
	"""Ordinary lists: items live on GET /lists/{id}. Dynamic lists: paginated /items."""
	items = []
	detail = call_punchplay('/lists/%s' % list_id, method='get') or {}
	if _api_ok(detail):
		raw = detail.get('items') if isinstance(detail.get('items'), list) else []
		is_dynamic = bool(detail.get('isDynamicList'))
		item_count = int(detail.get('itemCount') or 0)
		# Dynamic lists may truncate the detail payload — page /items when needed.
		if is_dynamic and (item_count > len(raw) or not raw):
			raw = _punchplay_list_items_paginated(list_id) or raw
		for entry in raw:
			row = _entry_to_list_item(entry, len(items) + 1)
			if row: items.append(row)
		return _filter_kind(items, media_kind)
	# Fallback for older shapes / detail miss
	for entry in _punchplay_list_items_paginated(list_id):
		row = _entry_to_list_item(entry, len(items) + 1)
		if row: items.append(row)
	return _filter_kind(items, media_kind)

def punchplay_search_my_lists(query):
	query = (query or '').strip().lower()
	if not query: return []
	results = []
	shelves = (
		(STATUS_PLANNING, 'Planning'),
		(STATUS_WATCHING, 'Watching'),
		(STATUS_ON_HOLD, 'On Hold'),
		(STATUS_WATCHED, 'Watched'),
		(STATUS_DROPPED, 'Dropped'),
	)
	for status, label in shelves:
		for item in _filter_status_items(status):
			title = (item.get('title') or '').lower()
			if query not in title: continue
			item_type = item.get('type')
			if item_type == 'movie': media_kind = 'movies'
			elif item_type == 'anime': media_kind = 'anime'
			else: media_kind = 'shows'
			results.append({
				'title': item.get('title') or 'Unknown',
				'status_label': label,
				'media_kind': media_kind,
				'media_ids': item.get('media_ids') or {}
			})
	return results

# ---------- Interact / mark ----------

def punchplay_interact(media_type, tmdb_id, payload):
	kind = _title_kind(media_type)
	try: tid = int(tmdb_id)
	except: return False
	result = call_punchplay('/title/%s/%s/interact' % (kind, tid), method='patch', data=payload)
	return bool(result) and not (isinstance(result, dict) and result.get('error'))

def _punchplay_episode_history_ids(tmdb_id, season, episode):
	"""Watch-history row ids for one episode (Mark Unwatched deletes these).

	History is newest-first and has no show/episode filter. Stop after the first
	page with no hits once we already found matches — avoids crawling the full
	library for Unmark Previous right after a recent watch (~5s → ~1 API page).
	"""
	try:
		tid, season_num, episode_num = int(tmdb_id), int(season), int(episode)
	except: return []
	history_ids, cursor, pages = [], None, 0
	while pages < 50:
		pages += 1
		query = {'limit': 100}
		if cursor: query['cursor'] = cursor
		data = call_punchplay('/me/history', method='get', query=query) or {}
		batch = _library_items(data)
		if not batch: break
		page_hits = 0
		for item in batch:
			try:
				if item.get('type') != 'episode': continue
				show_id = item.get('showTmdbId') or item.get('show_tmdb_id') or item.get('tmdbId')
				if int(show_id) != tid: continue
				if int(item.get('season')) != season_num or int(item.get('episode')) != episode_num: continue
				history_id = item.get('id') or item.get('historyId') or item.get('watchHistoryId')
				if history_id not in (None, ''):
					history_ids.append(str(history_id))
					page_hits += 1
			except Exception:
				continue
		if history_ids and page_hits == 0:
			break
		cursor = data.get('nextCursor') if isinstance(data, dict) else None
		if not cursor: break
	return history_ids

def _punchplay_delete_episode_history(tmdb_id, season, episode):
	"""Delete only that episode's history rows — season DELETE would clear the whole season."""
	history_ids = _punchplay_episode_history_ids(tmdb_id, season, episode)
	if not history_ids: return True  # already unwatched
	ok = True
	for history_id in history_ids:
		result = call_punchplay('/watch-history/%s' % history_id, method='delete')
		if result is None or (isinstance(result, dict) and result.get('error')):
			ok = False
	return ok

def _title_year_for_mark(media_type, tmdb_id, title=None, year=None):
	"""PunchPlay LogWatch / LogSeason require title + year in the JSON body."""
	title = (title or '').strip()
	year_int = None
	try:
		if year not in (None, '', 'None'): year_int = int(year)
	except Exception:
		year_int = None
	if year_int in (0, 2050): year_int = None
	if title and year_int:
		return title, year_int
	try:
		from modules import metadata, settings
		from modules.utils import get_datetime
		api_key, region, now = settings.tmdb_api_key(), settings.mpaa_region(), get_datetime()
		if media_type == 'movie':
			meta = metadata.movie_meta('tmdb_id', tmdb_id, api_key, region, now)
		else:
			meta = metadata.tvshow_meta('tmdb_id', tmdb_id, api_key, region, now)
		if meta:
			if not title:
				title = (meta.get('title') or meta.get('tvshowtitle') or '').strip()
			if not year_int:
				try: year_int = int(meta.get('year') or 0) or None
				except Exception: year_int = None
				if not year_int:
					try: year_int = int(str(meta.get('premiered') or '')[:4]) or None
					except Exception: year_int = None
	except Exception:
		pass
	return title or 'Unknown', year_int or 0

def _watched_at_now():
	"""ISO-8601 UTC timestamp for LogWatch / LogSeason (API requires watchedAt)."""
	return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())

def _season_episode_inputs(tmdb_id, season, episode_numbers=None, watched_at=None):
	"""Build LogSeason SeasonEpisodeInput rows (episodeNumber + name + watchedAt)."""
	watched_at = watched_at or _watched_at_now()
	try:
		from modules import metadata, settings
		from modules.utils import get_datetime, adjust_premiered_date
		meta = metadata.tvshow_meta('tmdb_id', tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
		ep_data = metadata.episodes_meta(int(season), meta) or []
		current_date = get_datetime()
		wanted = None
		if episode_numbers is not None:
			wanted = {int(n) for n in episode_numbers}
		rows = []
		for item in ep_data:
			try:
				ep_num = int(item['episode'])
				if wanted is not None and ep_num not in wanted:
					continue
				episode_date, _premiered = adjust_premiered_date(item.get('premiered'), settings.date_offset())
				if wanted is None and episode_date and current_date < episode_date:
					continue
				name = (item.get('title') or item.get('name') or 'Episode %s' % ep_num).strip()
				row = {
					'episodeNumber': ep_num,
					'name': name or ('Episode %s' % ep_num),
					'watchedAt': watched_at,
				}
				air = str(item.get('premiered') or '').strip()
				if air:
					row['airDate'] = air[:10]
				rows.append(row)
			except Exception:
				continue
		return rows
	except Exception:
		return []

def punchplay_watched_status_mark(action, media_type, tmdb_id, tvdb_id=0, season=None, episode=None, title=None, year=None):
	if not punchplay_user_active(): return False
	kind = _title_kind(media_type)
	try: tid = int(tmdb_id)
	except: return False
	if action == 'mark_as_watched':
		# Platform API (beta): title+year; LogSeason also needs episodes[{episodeNumber,name,watchedAt}].
		show_title, show_year = _title_year_for_mark(media_type, tid, title, year)
		watched_at = _watched_at_now()
		if media_type == 'movie':
			result = call_punchplay(
				'/title/%s/%s/history' % (kind, tid), method='post',
				data={'title': show_title, 'year': show_year, 'watchedAt': watched_at})
		elif media_type in ('episode',) and season is not None and episode is not None:
			# Single episode: skip season meta fetch — API only needs episodeNumber + name.
			ep_rows = [{
				'episodeNumber': int(episode),
				'name': 'Episode %s' % int(episode),
				'watchedAt': watched_at,
			}]
			result = call_punchplay(
				'/title/%s/%s/season/%s/watch' % (kind, tid, int(season)),
				method='post',
				data={
					'episodes': ep_rows,
					'title': show_title,
					'year': show_year,
					'watchedAt': watched_at,
				})
		elif media_type == 'season' and season is not None:
			ep_rows = _season_episode_inputs(tid, season, watched_at=watched_at)
			if not ep_rows: return False
			result = call_punchplay(
				'/title/%s/%s/season/%s/watch' % (kind, tid, int(season)),
				method='post',
				data={
					'episodes': ep_rows,
					'title': show_title,
					'year': show_year,
					'watchedAt': watched_at,
				})
		else:
			result = punchplay_interact(media_type, tid, {'showStatus': STATUS_WATCHED})
		ok = bool(result) and not (isinstance(result, dict) and result.get('error'))
	else:
		result = None
		if media_type == 'movie':
			result = call_punchplay('/title/%s/%s/history' % (kind, tid), method='delete')
			ok = result is not None and not (isinstance(result, dict) and result.get('error'))
		elif media_type == 'episode' and season is not None and episode is not None:
			# Do not use season DELETE — that clears every episode in the season.
			ok = _punchplay_delete_episode_history(tid, season, episode)
		elif media_type == 'season' and season is not None:
			result = call_punchplay(
				'/title/%s/%s/season/%s/watch' % (kind, tid, int(season)), method='delete')
			ok = result is not None and not (isinstance(result, dict) and result.get('error'))
		else:
			result = call_punchplay('/title/%s/%s/history' % (kind, tid), method='delete')
			ok = result is not None and not (isinstance(result, dict) and result.get('error'))
		# Movie/season/show DELETE when already clear often returns an error body — not a real failure.
		if not ok and media_type != 'episode' and result is not None:
			ok = True
	if ok:
		# Local punchplay_db is already updated by watched_status_mark. Skip the next
		# Next Episodes / list activity refresh (change feed would otherwise full-rebuild
		# history under DialogBusy), and tip the feed when the mark is already visible.
		try: kodi_utils.set_property('redlight.punchplay_skip_list_sync', 'true')
		except Exception: pass
		_punchplay_ack_local_watched_change()
	return ok

def punchplay_progress(action, media_type, tmdb_id, percent, season=None, episode=None, resume_id=None, refresh_punchplay=False):
	if action == 'clear_progress' and resume_id:
		call_punchplay('/playback/in-progress/%s' % resume_id, method='delete')
	else:
		punchplay_scrobble('progress', media_type, tmdb_id, percent, season, episode)
	if refresh_punchplay: punchplay_sync_activities(force_update=True)

def punchplay_hide_unhide_progress_items(params):
	action, media_id = params.get('action'), params.get('media_id')
	if action == 'drop':
		return punchplay_interact('tvshow', media_id, {'showStatus': STATUS_DROPPED})
	return punchplay_interact('tvshow', media_id, {'showStatus': None})

def punchplay_get_dropped_items():
	cached = pp_cache.punchplay_cache.get('dropped_items')
	if cached is not None: return cached
	ids = []
	for item in punchplay_dropped('shows'):
		tmdb = (item.get('media_ids') or {}).get('tmdb')
		if tmdb: ids.append(str(tmdb))
	for item in punchplay_dropped('movies'):
		tmdb = (item.get('media_ids') or {}).get('tmdb')
		if tmdb: ids.append(str(tmdb))
	pp_cache.punchplay_cache.set('dropped_items', ids)
	return ids

# ---------- Scrobble ----------

def _scrobble_payload(media_type, tmdb_id, percent, season=None, episode=None, title='', year=None, session_id=None):
	payload = {
		'media_type': 'movie' if media_type == 'movie' else 'episode',
		'title': title or ('Movie' if media_type == 'movie' else 'Episode'),
		'tmdb_id': int(tmdb_id),
		'progress': float(percent or 0),
		'device_id': _device_id(),
		'event_id': str(uuid.uuid4()),
		'event_created_at': int(time.time() * 1000),
		'client_version': kodi_utils.addon_version(),
		'watched_threshold': WATCHED_THRESHOLD,
	}
	if session_id: payload['playback_session_id'] = session_id
	year_int = None
	try:
		if year not in (None, '', 'None'): year_int = int(year)
	except: year_int = None
	if year_int: payload['year'] = year_int
	if media_type != 'movie':
		payload['season'] = int(season or 0)
		payload['episode'] = int(episode or 0)
	if float(percent or 0) >= (WATCHED_THRESHOLD * 100):
		payload['watched'] = True
	return payload

def punchplay_scrobble(action, media_type, tmdb_id, percent=0, season=None, episode=None, title='', year=None, session_id=None):
	if not punchplay_user_active(): return False
	if not punchplay_official_status(media_type): return False
	path_action = {'start': 'start', 'pause': 'pause', 'resume': 'resume', 'progress': 'progress', 'stop': 'stop'}.get(action)
	if not path_action: return False
	try: tid = int(tmdb_id)
	except: return False
	payload = _scrobble_payload(media_type, tid, percent, season, episode, title, year, session_id)
	result = call_punchplay('/playback/%s' % path_action, method='post', data=payload)
	return bool(result) and not (isinstance(result, dict) and result.get('error'))

def punchplay_reset_scrobble(params):
	from modules.watched_status import erase_bookmark
	media_type, tmdb_id = params.get('media_type'), params.get('tmdb_id')
	season, episode = params.get('season', ''), params.get('episode', '')
	watched_db = __import__('modules.watched_status', fromlist=['get_database']).get_database(4)
	try:
		if media_type == 'movie':
			punchplay_scrobble('stop', 'movie', tmdb_id, 0)
			row = watched_db.execute('SELECT resume_id FROM progress WHERE db_type=? AND media_id=?', ('movie', str(tmdb_id))).fetchone()
			if row: punchplay_progress('clear_progress', 'movie', tmdb_id, 0, resume_id=row[0])
			erase_bookmark('movie', tmdb_id, '', '', 'true', 4)
		elif media_type == 'episode' and season and episode:
			punchplay_scrobble('stop', 'episode', tmdb_id, 0, season, episode)
			row = watched_db.execute(
				'SELECT resume_id FROM progress WHERE db_type=? AND media_id=? AND season=? AND episode=?',
				('episode', str(tmdb_id), int(season), int(episode))).fetchone()
			if row: punchplay_progress('clear_progress', 'episode', tmdb_id, 0, season, episode, resume_id=row[0])
			erase_bookmark('episode', tmdb_id, season, episode, 'true', 4)
		else:
			return kodi_utils.notification('Reset Scrobble is only available for movies and episodes', 3500)
		kodi_utils.notification('Success', 3000)
	except: kodi_utils.notification('Error', 3000)

# ---------- Manager ----------

def _item_has_status(media_type, status, tmdb_id):
	kind = 'movie' if media_type == 'movie' else 'show'
	for entry in _paginate_interaction_library('/me/watch-status'):
		if str(entry.get('tmdbId') or '') != str(tmdb_id): continue
		entry_kind = (entry.get('kind') or entry.get('type') or '').lower()
		if kind == 'movie' and entry_kind not in ('movie', 'movies', ''): continue
		if kind == 'show' and entry_kind in ('movie', 'movies'): continue
		if (entry.get('showStatus') or '') == status: return True
	return False

def _item_is_favourite(media_type, tmdb_id):
	kind = 'movie' if media_type == 'movie' else 'show'
	for entry in _paginate_interaction_library('/me/favourites'):
		if str(entry.get('tmdbId') or '') != str(tmdb_id): continue
		entry_kind = (entry.get('kind') or entry.get('type') or '').lower()
		if kind == 'movie' and entry_kind not in ('movie', 'movies', ''): continue
		if kind == 'show' and entry_kind in ('movie', 'movies'): continue
		return True
	return False

def punchplay_manager_choice(params):
	if not punchplay_user_active(): return kodi_utils.notification('No Active PunchPlay Account', 3500)
	media_type = params.get('media_type') or params.get('content') or 'movie'
	list_media = 'movie' if media_type == 'movie' else 'tvshow'
	icon = params.get('icon') or _icon()
	tmdb_id = params.get('tmdb_id')
	title = params.get('title') or ''
	status_map = [
		(STATUS_PLANNING, 'Add to [B]Planning[/B]', 'Remove from [B]Planning[/B]'),
		(STATUS_WATCHED, 'Add to [B]Watched[/B]', 'Remove from [B]Watched[/B]'),
		(STATUS_DROPPED, 'Add to [B]Dropped[/B]', 'Remove from [B]Dropped[/B]'),
	]
	if media_type != 'movie':
		status_map.insert(1, (STATUS_WATCHING, 'Add to [B]Watching[/B]', 'Remove from [B]Watching[/B]'))
		status_map.insert(3, (STATUS_ON_HOLD, 'Add to [B]On Hold[/B]', 'Remove from [B]On Hold[/B]'))
	choices = []
	for status, add_label, remove_label in status_map:
		if _item_has_status(list_media, status, tmdb_id):
			choices.append((remove_label, 'remove_%s' % status))
		else:
			choices.append((add_label, status))
	if _item_is_favourite(list_media, tmdb_id):
		choices.append(('Remove from [B]Favourites[/B]', 'remove_favourite'))
	else:
		choices.append(('Add to [B]Favourites[/B]', 'add_favourite'))
	choices.extend([
		('Add to [B]Collection[/B]', 'add_library'),
		('Mark as [B]Watched[/B]', 'mark_watched'),
		('Mark as [B]Unwatched[/B]', 'mark_unwatched'),
		('Reset [B]Scrobble[/B]', 'reset_scrobble'),
		('Open [B]PunchPlay Lists[/B]', 'open_lists'),
		('Refresh Widgets', 'refresh'),
	])
	if list_media == 'movie':
		choices.insert(-1, ('Open [B]Dropped Movies[/B]', 'open_dropped'))
	else:
		choices.insert(-1, ('Open [B]Dropped TV Shows[/B]', 'open_dropped'))
	list_items = [{'line1': item[0], 'icon': icon} for item in choices]
	choice = kodi_utils.select_dialog([i[1] for i in choices], **{'items': json.dumps(list_items), 'heading': 'PunchPlay Manager'})
	if choice is None: return
	if choice == 'refresh':
		kodi_utils.kodi_refresh()
		return kodi_utils.notification('Widgets Refreshed', 2500)
	if choice == 'open_lists':
		return kodi_utils.container_update({'mode': 'navigator.punchplay_lists'})
	if choice == 'open_dropped':
		if list_media == 'movie':
			return kodi_utils.container_update({
				'mode': 'build_movie_list', 'action': 'punchplay_dropped', 'category_name': 'Movies Dropped'
			})
		return kodi_utils.container_update({
			'mode': 'build_tvshow_list', 'action': 'punchplay_dropped', 'category_name': 'TV Shows Dropped'
		})
	if choice == 'mark_watched':
		from indexers.dialogs import _trakt_manager_mark
		return _trakt_manager_mark(params, 'mark_as_watched')
	if choice == 'mark_unwatched':
		from indexers.dialogs import _trakt_manager_mark
		return _trakt_manager_mark(params, 'mark_as_unwatched')
	if choice == 'reset_scrobble':
		return punchplay_reset_scrobble(params)
	if choice == 'add_favourite':
		ok = punchplay_interact(list_media, tmdb_id, {'isFavourite': True})
		return kodi_utils.notification('Success' if ok else 'Error', 3000)
	if choice == 'remove_favourite':
		ok = punchplay_interact(list_media, tmdb_id, {'isFavourite': False})
		return kodi_utils.notification('Success' if ok else 'Error', 3000)
	if choice == 'add_library':
		kind = _title_kind(list_media)
		ok = call_punchplay('/collection', method='post', data={
			'kind': kind, 'sourceId': int(tmdb_id), 'title': title or str(tmdb_id), 'format': 'digital'
		})
		return kodi_utils.notification('Success' if ok and not (isinstance(ok, dict) and ok.get('error')) else 'Error', 3000)
	if choice.startswith('remove_'):
		status = choice.replace('remove_', '')
		ok = punchplay_interact(list_media, tmdb_id, {'showStatus': None, 'wantToWatch': False} if status == STATUS_PLANNING else {'showStatus': None})
		return kodi_utils.notification('Success' if ok else 'Error', 3000)
	if choice in (STATUS_PLANNING, STATUS_WATCHING, STATUS_ON_HOLD, STATUS_DROPPED, STATUS_WATCHED):
		payload = {'showStatus': choice}
		if choice == STATUS_PLANNING: payload['wantToWatch'] = True
		ok = punchplay_interact(list_media, tmdb_id, payload)
		return kodi_utils.notification('Success' if ok else 'Error', 3000)

# ---------- Sync ----------

def punchplay_indicators_movies():
	insert_list, seen = [], set()
	for item in _paginate_history():
		if item.get('type') != 'movie': continue
		tmdb_id = item.get('tmdbId') or item.get('tmdb_id')
		if not tmdb_id or tmdb_id in seen: continue
		seen.add(tmdb_id)
		watched_at = item.get('watchedAt') or time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
		insert_list.append(('movie', str(tmdb_id), '', '', watched_at, item.get('title') or ''))
	# Also treat WATCHED status movies as watched
	for item in punchplay_completed('movies'):
		tmdb_id = (item.get('media_ids') or {}).get('tmdb')
		if not tmdb_id or tmdb_id in seen: continue
		seen.add(tmdb_id)
		insert_list.append(('movie', str(tmdb_id), '', '', item.get('collected_at') or '', item.get('title') or ''))
	pp_cache.punchplay_watched_cache.set_bulk_movie_watched(insert_list)

def punchplay_indicators_tv():
	insert_list, seen = [], set()
	for item in _paginate_history():
		if item.get('type') != 'episode': continue
		show_id = item.get('showTmdbId') or item.get('tmdbId')
		season, episode = item.get('season'), item.get('episode')
		if not show_id or season is None or episode is None: continue
		key = (int(show_id), int(season), int(episode))
		if key in seen: continue
		seen.add(key)
		watched_at = item.get('watchedAt') or time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
		insert_list.append(('episode', str(show_id), int(season), int(episode), watched_at, item.get('title') or ''))
	pp_cache.punchplay_watched_cache.set_bulk_tvshow_watched(insert_list)

def punchplay_sync_playback():
	data = call_punchplay('/playback/in-progress', method='get') or {}
	items = _library_items(data) if not isinstance(data, list) else data
	movie_ins, ep_ins = [], []
	for item in items:
		try:
			percent = float(item.get('progressPercent') or 0)
			updated = item.get('updatedAt') or ''
			resume_id = item.get('id') or 0
			if item.get('type') == 'movie':
				tmdb_id = item.get('tmdbId')
				if not tmdb_id: continue
				movie_ins.append(('movie', str(tmdb_id), '', '', str(round(percent, 1)), 0, updated, resume_id, item.get('title') or ''))
			elif item.get('type') == 'episode':
				show_id = item.get('showTmdbId') or item.get('tmdbId')
				if not show_id: continue
				ep_ins.append(('episode', str(show_id), item.get('season'), item.get('episode'),
					str(round(percent, 1)), 0, updated, resume_id, item.get('showTitle') or item.get('title') or ''))
		except: pass
	pp_cache.punchplay_watched_cache.set_bulk_movie_progress(movie_ins)
	pp_cache.punchplay_watched_cache.set_bulk_tvshow_progress(ep_ins)

# Partner sync change feed — PunchPlay's stand-in for Simkl/MDBList last_activities.
_PUNCHPLAY_WATCHED_SYNC_RESOURCES = frozenset(('history', 'playback', 'interaction'))

def _punchplay_sync_stale():
	"""TTL fallback when /me/sync/changes is unavailable — honour Resync Interval."""
	import calendar
	last = pp_cache.punchplay_cache.get('last_sync')
	if not last: return True
	try:
		ts = calendar.timegm(time.strptime(str(last).rstrip('Z').split('.')[0], '%Y-%m-%dT%H:%M:%S'))
	except Exception:
		return True
	try:
		_interval_min, wait_sec = settings.punchplay_sync_interval()
	except Exception:
		wait_sec = 3600
	return (time.time() - ts) >= max(300, int(wait_sec))

def _punchplay_probe_sync_changes():
	"""Return (needs_refresh, tip_response). tip_response used to advance cursor after a full pull."""
	cursor = pp_cache.punchplay_cache.get('sync_changes_cursor')
	query = {'limit': 100}
	if cursor: query['cursor'] = cursor
	data = call_punchplay('/me/sync/changes', method='get', query=query)
	if not isinstance(data, dict) or data.get('error'):
		# 429 / missing scope / network — do not pile on with a full history crawl.
		if isinstance(data, dict):
			err = ('%s %s' % (data.get('error') or '', data.get('message') or '')).lower()
			if '429' in err or 'rate' in err or 'too many' in err:
				return False, None
		return _punchplay_sync_stale(), None
	if data.get('resetRequired'):
		pp_cache.punchplay_cache.delete('sync_changes_cursor')
		return True, data
	changes = data.get('changes') or []
	if not changes:
		next_cursor = data.get('nextCursor')
		if next_cursor: pp_cache.punchplay_cache.set('sync_changes_cursor', next_cursor)
		return False, data
	if any((c.get('resource') or '') in _PUNCHPLAY_WATCHED_SYNC_RESOURCES for c in changes):
		return True, data
	# Lists/collection-only — keep cursor moving, skip history rebuild.
	_punchplay_advance_sync_cursor(data)
	return False, data

def _punchplay_advance_sync_cursor(start_data=None):
	"""After a full watched rebuild (or skipping non-watched changes), fast-forward the feed cursor."""
	data = start_data if isinstance(start_data, dict) else None
	cursor = (data or {}).get('nextCursor') or pp_cache.punchplay_cache.get('sync_changes_cursor')
	has_more = bool((data or {}).get('hasMore')) if data else bool(cursor)
	pages = 0
	while cursor and pages < 40:
		pp_cache.punchplay_cache.set('sync_changes_cursor', cursor)
		if data is not None and not has_more: break
		pages += 1
		data = call_punchplay('/me/sync/changes', method='get', query={'cursor': cursor, 'limit': 500}) or {}
		if not isinstance(data, dict) or data.get('error'): break
		if data.get('resetRequired'):
			pp_cache.punchplay_cache.delete('sync_changes_cursor')
			break
		cursor = data.get('nextCursor')
		has_more = bool(data.get('hasMore'))
		if cursor: pp_cache.punchplay_cache.set('sync_changes_cursor', cursor)
		if not has_more: break

def _punchplay_ack_local_watched_change():
	"""After Red Light mark/unmark (API + local DB), tip the change feed without a history rebuild."""
	try:
		needs_refresh, probe = _punchplay_probe_sync_changes()
		if not needs_refresh:
			return
		if isinstance(probe, dict):
			_punchplay_advance_sync_cursor(probe)
		pp_cache.punchplay_cache.set('last_sync', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
	except Exception as e:
		kodi_utils.logger('PunchPlay', 'ack local watched change failed: %s' % e)

def punchplay_sync_activities(params=None, force_update=False):
	"""Activity-gated sync. Uses PunchPlay /me/sync/changes (not Simkl-style last_activities)."""
	if isinstance(params, dict):
		force_update = params.get('force_update', 'false') in ('true', 'True', True) or force_update
	if not punchplay_user_active(): return 'no account'
	if force_update:
		pp_cache.clear_all_punchplay_cache_data(silent=True, refresh=False)
		pp_cache.punchplay_cache.delete('sync_changes_cursor')
	probe = None
	if not force_update:
		needs_refresh, probe = _punchplay_probe_sync_changes()
		if not needs_refresh: return 'not needed'
	try:
		punchplay_indicators_movies()
		punchplay_indicators_tv()
		punchplay_sync_playback()
		pp_cache.punchplay_cache.delete('dropped_items')
		pp_cache.punchplay_cache.delete('watchlist_list_id')
		pp_cache.punchplay_cache.set('last_sync', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
		# Full history rebuild is current as of now — advance change-feed cursor to the tip.
		if probe is None:
			probe = call_punchplay('/me/sync/changes', method='get', query={'limit': 100})
		_punchplay_advance_sync_cursor(probe if isinstance(probe, dict) else None)
		return 'success'
	except Exception as e:
		kodi_utils.logger('PunchPlay', 'sync failed: %s' % e)
		return 'failed'

PUNCHPLAY_TRAKT_IMPORT_URL = 'https://punchplay.tv/import/trakt'

def punchplay_import_trakt(params=None):
	from threading import Thread
	from modules.trakt_import_help import open_official_trakt_import_page
	def _after():
		Thread(target=punchplay_sync_activities, kwargs={'force_update': True}, daemon=True).start()
	return open_official_trakt_import_page(
		'PunchPlay', PUNCHPLAY_TRAKT_IMPORT_URL,
		icon=_icon(),
		after_close=_after)

def punchplay_force_sync(params=None):
	if not punchplay_user_active(): return kodi_utils.notification('PunchPlay account not authorised', 3000)
	progress = kodi_utils.progress_dialog('PunchPlay Sync')
	status = 'failed'
	try:
		progress.update('Syncing with PunchPlay...', 0)
		status = punchplay_sync_activities(force_update=True)
	except Exception as e:
		kodi_utils.logger('PunchPlay', 'Force sync failed: %s' % e)
	finally:
		kodi_utils.close_progress_dialog(progress)
	if status == 'failed': kodi_utils.notification('PunchPlay Sync Failed', 3000)
	else:
		kodi_utils.notification('PunchPlay Sync Complete', 3000)
		kodi_utils.kodi_refresh()
	return status

# ---------- Calendar / Next Up ----------

def punchplay_calendar(month=None):
	"""Raw GET /calendar for one month (YYYY-MM). Returns the API dict or {}."""
	query = {'month': month or time.strftime('%Y-%m')}
	data = call_punchplay('/calendar', method='get', query=query) or {}
	return data if isinstance(data, dict) else {}

def _months_covering_dates(start_date, end_date):
	months, y, m = [], start_date.year, start_date.month
	end_ym = (end_date.year, end_date.month)
	while (y, m) <= end_ym:
		months.append('%04d-%02d' % (y, m))
		if m == 12: y, m = y + 1, 1
		else: m += 1
	return months

def _normalize_punchplay_calendar_month(data):
	"""Platform CalendarResponse → shared episode calendar rows (episodes only)."""
	if not isinstance(data, dict): return []
	days = data.get('days')
	if not isinstance(days, list): return []
	out = []
	for day in days:
		try:
			if not isinstance(day, dict): continue
			day_date = day.get('date') or ''
			items = day.get('items')
			if not isinstance(items, list): continue
			for item in items:
				if not isinstance(item, dict): continue
				kind = (item.get('kind') or '').lower()
				if kind != 'episode': continue
				tmdb_id = item.get('tmdbId') or item.get('tmdb_id')
				next_ep = item.get('nextEpisode') or {}
				if not isinstance(next_ep, dict): continue
				season, episode = next_ep.get('season'), next_ep.get('episode')
				air = next_ep.get('airDate') or day_date
				if not tmdb_id or season is None or episode is None or not air: continue
				if int(season) < 1: continue
				title = item.get('title') or ''
				out.append({
					'sort_title': '%s s%s e%s' % (title, str(season).zfill(2), str(episode).zfill(2)),
					'media_ids': {'tmdb': int(tmdb_id)},
					'season': int(season),
					'episode': int(episode),
					# Keep full ISO when present so Calendars UTC (+/-) can apply.
					'first_aired': str(air)
				})
		except Exception:
			continue
	return [i for n, i in enumerate(out) if i not in out[n + 1:]]

def _filter_punchplay_calendar_day_window(data):
	from modules.utils import calendar_service_local_date
	start_date, end_date = settings.calendar_day_window()
	filtered = []
	for item in data:
		aired, _ = calendar_service_local_date(item.get('first_aired', ''))
		if aired is None: continue
		if start_date <= aired <= end_date:
			filtered.append(item)
	return filtered

def _punchplay_calendar_month_cached(month):
	cache_key = 'punchplay_calendar_v2_%s' % month
	cached = pp_cache.punchplay_cache.get(cache_key)
	if cached:
		return cached
	data = _normalize_punchplay_calendar_month(punchplay_calendar(month)) or []
	if data:
		pp_cache.punchplay_cache.set(cache_key, data)
	elif cached is not None:
		pp_cache.punchplay_cache.delete(cache_key)
	return data

def punchplay_get_my_calendar(dummy=None):
	"""Episode airings for the authenticated user (GET /calendar).

	Cached per month; Show Previous/Future Days is applied on read so calendar
	settings match Trakt/MDBList without waiting for cache expiry.
	"""
	start_date, end_date = settings.calendar_day_window()
	data = []
	for month in _months_covering_dates(start_date, end_date):
		data.extend(_punchplay_calendar_month_cached(month))
	data = [i for n, i in enumerate(data) if i not in data[n + 1:]]
	filtered = _filter_punchplay_calendar_day_window(data)
	try:
		kodi_utils.logger('Red Light', 'PunchPlay calendar: %s cached/fetched, %s in day window (%s → %s)' % (
			len(data), len(filtered), start_date, end_date))
	except Exception:
		pass
	return filtered

def punchplay_continue_watching():
	return _library_items(call_punchplay('/me/continue-watching', method='get'))
