# -*- coding: utf-8 -*-
import json
import re
import time
import requests
from caches import mdblist_cache
from caches.settings_cache import get_setting, set_setting
from modules import kodi_utils, settings, list_sort
from modules.http_defaults import META_API_TIMEOUT, meta_status_retry
from modules.utils import paginate_list, get_datetime, TaskPool, make_thread_list, copy2clip, make_qrcode, make_tinyurl

_EPISODE_SE_RE = re.compile(
	r'(?:^|[\s·|\-–—/])S(\d{1,2})\s*[:.]?\s*E(\d{1,3})(?:\b|:)|(?:^|[\s·|\-–—/])(\d{1,2})x(\d{1,3})\b',
	re.I
)

BASE_URL = 'https://api.mdblist.com/%s'
_OAUTH_DEVICE_URL = 'https://api.mdblist.com/oauth/device-authorization/'
_OAUTH_TOKEN_URL = 'https://api.mdblist.com/oauth/token/'
MAX_LIST_ITEMS = 250_000
session = requests.Session()
session.mount('https://api.mdblist.com', requests.adapters.HTTPAdapter(pool_maxsize=100, max_retries=meta_status_retry()))

def _mdblist_token():
	from caches.settings_cache import settings_cache
	token = settings_cache.read_db_value('mdblist.token')
	if token in (None, '0', '', 'empty_setting'):
		token = get_setting('redlight.mdblist.token', '0')
	return token

def _mdblist_oauth_active():
	refresh = get_setting('redlight.mdblist.refresh', '0')
	return refresh not in (None, '0', '', 'empty_setting')

def call_mdblist(path, params=None, json_data=None, method=None):
	params = params or {}
	token = _mdblist_token()
	if not token or token in ('0', 'empty_setting'): return None
	headers = {'Authorization': 'Bearer %s' % token} if _mdblist_oauth_active() else {}
	if not headers: params['apikey'] = token
	try:
		response = session.request(method or 'get', BASE_URL % path.lstrip('/'), params=params, json=json_data, headers=headers, timeout=META_API_TIMEOUT)
		if 'json' in response.headers.get('Content-Type', ''):
			result = response.json()
		else:
			result = response.text
		if not response.ok:
			kodi_utils.logger('MDBList', 'HTTP %s %s' % (response.status_code, path))
			return None
		if isinstance(result, list):
			result = {'items': result, 'pagination': {'has_more': response.headers.get('X-Has-More') == 'true'}}
			if next_cursor := response.headers.get('X-Next-Cursor'):
				result['pagination']['next_cursor'] = next_cursor
		return result
	except Exception as e:
		kodi_utils.logger('MDBList Error', str(e))
		return None

def _get_mdbl_paginated_list(url):
	params = {'limit': 1000}
	items = {'movies': [], 'shows': [], 'seasons': [], 'episodes': [], 'items': []}
	try:
		for _ in range(MAX_LIST_ITEMS // params['limit']):
			result = call_mdblist(url, params=params)
			# None = hard failure (do not treat as empty success — bulk watched replace would wipe).
			if not isinstance(result, dict): return None
			for key in items:
				if key in result and isinstance(result[key], list):
					items[key].extend(result[key])
			pagination = result.get('pagination') or {}
			if not pagination.get('has_more'): break
			next_cursor = pagination.get('next_cursor')
			if not next_cursor: break
			params['cursor'] = next_cursor
	except: return None
	return items

def _get_mdbl_playback_items():
	result = _get_mdbl_paginated_list('sync/playback')
	if result is None: return None
	return result.get('items', [])

def _tmdb_id_from_ids(ids):
	for key in ('tmdb', 'tmdbid'):
		try:
			if ids.get(key): return str(int(ids[key]))
		except: pass
	return None

def _imdb_from_ids(ids, block=None):
	for source in (ids, block or {}):
		for key in ('imdb', 'imdb_id', 'imdbid'):
			if value := source.get(key):
				return value
	return ''

def _tvdb_from_ids(ids, block=None):
	for source in (ids, block or {}):
		for key in ('tvdb', 'tvdb_id', 'tvdbid'):
			if value := source.get(key):
				return value
	return ''

def _resolve_movie_id(ids):
	if tmdb_id := _tmdb_id_from_ids(ids): return tmdb_id
	from modules import metadata
	for key, id_type in (('imdb', 'imdb_id'), ('imdbid', 'imdb_id')):
		try:
			value = ids.get(key)
			if value: return str(metadata.movie_meta(id_type, value, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())['tmdb_id'])
		except: pass
	return None

def _resolve_tvshow_id(ids):
	if tmdb_id := _tmdb_id_from_ids(ids): return tmdb_id
	from modules import metadata
	for key, id_type in (('imdb', 'imdb_id'), ('imdbid', 'imdb_id'), ('tvdb', 'tvdb_id'), ('tvdbid', 'tvdb_id')):
		try:
			value = ids.get(key)
			if value: return str(metadata.tvshow_meta(id_type, value, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())['tmdb_id'])
		except: pass
	return None

def _normalize_mdbl_personal_item(item, media_kind):
	is_movie = media_kind in ('movie', 'movies')
	nested_key = 'movie' if is_movie else 'show'
	block = item.get(nested_key)
	if isinstance(block, dict):
		ids = block.get('ids') or {}
		tmdb_id = _resolve_movie_id(ids) if is_movie else _resolve_tvshow_id(ids)
		title = block.get('title', '')
		year = block.get('year') or block.get('release_year', '')
		imdb_id = ids.get('imdb', '')
		tvdb_id = ids.get('tvdb', '')
	else:
		block = item if isinstance(item, dict) else {}
		ids = block.get('ids') or {}
		tmdb_id = None
		if block.get('tmdb') is not None:
			try: tmdb_id = str(int(block['tmdb']))
			except: pass
		if not tmdb_id:
			merged_ids = dict(ids)
			if block.get('imdb_id'): merged_ids['imdb'] = block['imdb_id']
			if block.get('tvdb_id'): merged_ids['tvdb'] = block['tvdb_id']
			tmdb_id = _resolve_movie_id(merged_ids) if is_movie else _resolve_tvshow_id(merged_ids)
		title = block.get('title', '')
		year = block.get('year') or block.get('release_year', '')
		imdb_id = block.get('imdb_id') or ids.get('imdb', '')
		tvdb_id = block.get('tvdb_id') or ids.get('tvdb', '')
	if not tmdb_id: return None
	return {'id': tmdb_id, 'title': title, 'year': year, 'imdb_id': imdb_id or '', 'tvdb_id': tvdb_id or '',
		'watchlist_at': item.get('watchlist_at', ''), 'collected_at': item.get('collected_at', ''), 'release_date': item.get('release_date', '')}

def _mdbl_first_int(*values):
	for value in values:
		if value in (None, '', 'None'): continue
		try: return int(value)
		except: pass
	return None

def _mdbl_parse_se_from_text(text):
	if not text: return None, None
	match = _EPISODE_SE_RE.search(str(text))
	if not match: return None, None
	if match.group(1) is not None:
		return int(match.group(1)), int(match.group(2))
	return int(match.group(3)), int(match.group(4))

def _mdbl_show_title_from_episode_title(title):
	if not title: return ''
	text = str(title)
	for sep in (' · ', ' • ', ' - ', ' – ', ' — '):
		if sep in text:
			head = text.split(sep, 1)[0].strip()
			if head: return re.sub(r'\s*\(\d{4}\)\s*$', '', head).strip() or head
	match = _EPISODE_SE_RE.search(text)
	if match:
		head = text[:match.start()].strip(' -–—·|/')
		if head: return re.sub(r'\s*\(\d{4}\)\s*$', '', head).strip() or head
	return text

def _mdbl_item_media_kind(item):
	if not isinstance(item, dict): return 'movie'
	mediatype = (item.get('mediatype') or item.get('type') or item.get('media_type') or '').lower()
	if mediatype in ('episode', 'episodes'): return 'episode'
	if mediatype in ('movie', 'movies'): return 'movie'
	if mediatype in ('show', 'shows', 'tvshow', 'tv', 'series'): return 'show'
	if isinstance(item.get('episode'), dict) and (
		isinstance(item.get('show'), dict)
		or item.get('season') is not None
		or item.get('season_number') is not None
		or item['episode'].get('season') is not None
		or item['episode'].get('season_number') is not None
	):
		return 'episode'
	if item.get('season_number') is not None and item.get('episode_number') is not None:
		return 'episode'
	if item.get('show_tmdb') is not None and (
		item.get('season') is not None or item.get('season_number') is not None
	) and (
		item.get('episode') is not None or item.get('episode_number') is not None or item.get('number') is not None
	):
		return 'episode'
	if item.get('tvdb_id'): return 'show'
	return 'movie'

def mdbl_episode_list_entry(item, order=0):
	"""Normalize an MDBList episode list row for build_single_episode (Trakt-shaped)."""
	if not isinstance(item, dict): return None
	show = item.get('show') if isinstance(item.get('show'), dict) else {}
	ep = item.get('episode') if isinstance(item.get('episode'), dict) else {}
	show_ids = show.get('ids') if isinstance(show.get('ids'), dict) else {}
	item_ids = item.get('ids') if isinstance(item.get('ids'), dict) else {}

	season = _mdbl_first_int(
		item.get('season'), item.get('season_number'),
		ep.get('season'), ep.get('season_number')
	)
	episode = None
	if not isinstance(item.get('episode'), dict):
		episode = _mdbl_first_int(item.get('episode_number'), item.get('episode'), item.get('number'))
	if episode is None:
		episode = _mdbl_first_int(ep.get('episode'), ep.get('episode_number'), ep.get('number'), item.get('episode_number'))
	if season is None or episode is None:
		parsed_season, parsed_episode = _mdbl_parse_se_from_text(item.get('title') or ep.get('title') or '')
		if season is None: season = parsed_season
		if episode is None: episode = parsed_episode
	if season is None or episode is None or season < 1 or episode < 0:
		return None

	# Prefer show-level ids. Flat item id/tmdb/ids.tmdb on episode rows is the episode TMDb id.
	# Unified episode items expose the parent show as show_id (TMDb).
	media_ids = {}
	show_tmdb = _mdbl_first_int(
		item.get('show_tmdb'), item.get('show_id'),
		show.get('tmdb'), show_ids.get('tmdb')
	)
	if show_tmdb: media_ids['tmdb'] = show_tmdb
	imdb = (
		item.get('show_imdb') or show.get('imdb_id') or show_ids.get('imdb')
		or item.get('imdb_id') or item_ids.get('imdb') or ''
	)
	if imdb and imdb not in ('None', '0', None): media_ids['imdb'] = imdb
	tvdb = (
		item.get('show_tvdb') or show.get('tvdb_id') or show_ids.get('tvdb')
		or item.get('tvdb_id') or item_ids.get('tvdb') or ''
	)
	if tvdb and tvdb not in ('None', '0', None): media_ids['tvdb'] = tvdb
	if not media_ids: return None

	title = (
		show.get('title') or item.get('parent_title') or item.get('show_title')
		or item.get('show_name') or _mdbl_show_title_from_episode_title(item.get('title') or '')
	)
	return {
		'media_ids': media_ids,
		'title': title or '',
		'type': 'episode',
		'season': int(season),
		'episode': int(episode),
		'custom_order': order
	}

def mdbl_collect_list_media(payload):
	"""Split list contents into movie/show/episode raw items (unified + typed buckets)."""
	movies, shows, episodes = [], [], []
	if not isinstance(payload, dict): return movies, shows, episodes
	movies.extend(i for i in (payload.get('movies') or []) if isinstance(i, dict))
	shows.extend(i for i in (payload.get('shows') or []) if isinstance(i, dict))
	episodes.extend(i for i in (payload.get('episodes') or []) if isinstance(i, dict))
	for item in payload.get('items') or []:
		if not isinstance(item, dict): continue
		kind = _mdbl_item_media_kind(item)
		if kind == 'episode': episodes.append(item)
		elif kind == 'show': shows.append(item)
		else: movies.append(item)
	return movies, shows, episodes

def _mdbl_movie_show_row(item, media_type, order):
	tmdb_id = mdbl_unified_item_tmdb_id(item)
	if not tmdb_id: return None
	return {'type': media_type, 'media_ids': {'tmdb': tmdb_id}, 'order': order, 'custom_order': order}

def mdbl_ordered_list_rows(payload):
	"""Ordered typed rows for mixed list open (movie | show | episode), preserving unified order."""
	rows = []
	if not isinstance(payload, dict): return rows
	items = [i for i in (payload.get('items') or []) if isinstance(i, dict)]
	if items:
		for order, item in enumerate(items):
			kind = _mdbl_item_media_kind(item)
			if kind == 'episode':
				row = mdbl_episode_list_entry(item, order)
				if row:
					row['order'] = order
					rows.append(row)
			else:
				row = _mdbl_movie_show_row(item, 'movie' if kind == 'movie' else 'show', order)
				if row: rows.append(row)
		return rows
	order = 0
	for item in payload.get('movies') or []:
		if not isinstance(item, dict): continue
		row = _mdbl_movie_show_row(item, 'movie', order)
		if row:
			rows.append(row)
			order += 1
	for item in payload.get('shows') or []:
		if not isinstance(item, dict): continue
		row = _mdbl_movie_show_row(item, 'show', order)
		if row:
			rows.append(row)
			order += 1
	for item in payload.get('episodes') or []:
		if not isinstance(item, dict): continue
		row = mdbl_episode_list_entry(item, order)
		if row:
			row['order'] = order
			rows.append(row)
			order += 1
	return rows

def _mdbl_item_to_list_entry(item, media_kind):
	if not isinstance(item, dict): return None
	ids = item.get('ids') or {}
	tmdb_id = _tmdb_id_from_ids(ids)
	if not tmdb_id and item.get('tmdb') is not None:
		try: tmdb_id = str(int(item['tmdb']))
		except: pass
	if not tmdb_id and item.get('mediatype') and item.get('id') is not None:
		try: tmdb_id = str(int(item['id']))
		except: pass
	if tmdb_id:
		return {'id': tmdb_id, 'title': item.get('title', ''), 'year': item.get('year') or item.get('release_year', ''),
			'imdb_id': _imdb_from_ids(ids, item), 'tvdb_id': _tvdb_from_ids(ids, item),
			'watchlist_at': item.get('watchlist_at', ''), 'collected_at': item.get('collected_at', ''), 'release_date': item.get('release_date', '')}
	entry = _normalize_mdbl_personal_item(item, media_kind)
	if entry: return entry
	if item.get('id') is not None:
		try:
			tmdb_id = str(int(item['id']))
			return {'id': tmdb_id, 'title': item.get('title', ''), 'year': item.get('year') or item.get('release_year', ''),
				'imdb_id': _imdb_from_ids(ids, item), 'tvdb_id': _tvdb_from_ids(ids, item),
				'watchlist_at': item.get('watchlist_at', ''), 'collected_at': item.get('collected_at', ''), 'release_date': item.get('release_date', '')}
		except: pass
	return None

def mdbl_list_media_type(list_item, fallback='movie'):
	"""Route param for build_mdbl_list: movie | tvshow | episode from MDBList list metadata."""
	if not isinstance(list_item, dict):
		if fallback in ('episode', 'episodes'): return 'episode'
		return 'tvshow' if fallback in ('tv', 'tvshow', 'show', 'shows', 'series') else 'movie'
	mediatype = (list_item.get('mediatype') or list_item.get('media_type') or '').lower()
	if mediatype in ('episode', 'episodes'):
		return 'episode'
	if mediatype in ('show', 'shows', 'tvshow', 'tv', 'series'):
		return 'tvshow'
	if mediatype in ('movie', 'movies'):
		return 'movie'
	if fallback in ('episode', 'episodes'):
		return 'episode'
	if fallback in ('tv', 'tvshow', 'show', 'shows', 'series'):
		return 'tvshow'
	return 'movie'

def mdbl_unified_item_tmdb_id(item):
	"""Resolve TMDb id from unified list item payloads (nested show/movie blocks)."""
	if _mdbl_item_media_kind(item) == 'episode':
		return None
	entry = _mdbl_item_to_list_entry(item, _mdbl_item_media_kind(item))
	if not entry or not entry.get('id'):
		return None
	try:
		return int(entry['id'])
	except:
		return None

def _mdbl_personal_list(original_list, media_kind):
	is_movie = media_kind in ('movie', 'movies')
	key = 'movies' if is_movie else 'shows'
	raw_items = list(original_list.get(key, []) or [])
	for item in original_list.get('items', []) or []:
		kind = _mdbl_item_media_kind(item)
		if is_movie and kind == 'movie': raw_items.append(item)
		elif not is_movie and kind == 'show': raw_items.append(item)
	normalized = []
	for item in raw_items:
		entry = _mdbl_item_to_list_entry(item, media_kind)
		if entry: normalized.append(entry)
	return normalized

def _mdblist_device_auth_url(device_data):
	verification_url = (device_data.get('verification_uri') or device_data.get('verification_url') or 'https://mdblist.com/oauth/device/').rstrip('/')
	user_code = device_data.get('user_code', '')
	if user_code: return '%s?code=%s' % (verification_url, user_code)
	return verification_url

def mdblist_get_device_code():
	client_id = settings.mdblist_client()
	if not client_id or client_id in ('empty_setting', ''): return None
	try:
		response = session.post(_OAUTH_DEVICE_URL, data={'client_id': client_id, 'scope': 'write'}, timeout=META_API_TIMEOUT)
		if not response.ok: return None
		return response.json()
	except: return None

def mdblist_poll_device(device_data):
	device_code, user_code = device_data.get('device_code'), device_data.get('user_code')
	if not device_code or not user_code: return None
	expires_in = int(device_data.get('expires_in') or 300)
	interval = max(int(device_data.get('interval') or 5), 1)
	auth_url = _mdblist_device_auth_url(device_data)
	qr_code = make_qrcode(auth_url) or ''
	copy2clip(auth_url)
	short_url = make_tinyurl(auth_url)
	p_dialog_insert = '[CR]OR visit [B]%s[/B]' % short_url if short_url else ''
	verify_display = (device_data.get('verification_uri') or device_data.get('verification_url') or 'mdblist.com/oauth/device').replace('https://', '')
	content = ('Enter [B]%s[/B] at [B]%s[/B][CR]OR scan the [B]QR Code[/B][CR]Link copied to clipboard%s[CR][CR]'
		'Waiting for authorisation...' % (user_code, verify_display, p_dialog_insert))
	progress = kodi_utils.progress_dialog('MDBList Authorise', qr_code)
	progress.update(content, 0)
	start = time.time()
	while time.time() - start < expires_in:
		if progress.iscanceled():
			progress.close()
			return None
		kodi_utils.sleep(interval * 1000)
		try:
			client_id = settings.mdblist_client()
			response = session.post(_OAUTH_TOKEN_URL, data={
				'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
				'device_code': device_code,
				'client_id': client_id}, timeout=META_API_TIMEOUT)
			if response.status_code == 200:
				result = response.json()
				progress.close()
				return result
		except: pass
		progress.update(content, int(100 * (time.time() - start) / float(expires_in)))
	progress.close()
	return None

def mdblist_authenticate(dummy=''):
	device_data = mdblist_get_device_code()
	if not device_data or not device_data.get('user_code'): return kodi_utils.notification('MDBList Authorisation Failed', 3000)
	token_result = mdblist_poll_device(device_data)
	if not token_result: return kodi_utils.notification('MDBList Authorisation Canceled', 3000)
	access_token = token_result.get('access_token')
	if not access_token: return kodi_utils.notification('MDBList Authorisation Failed', 3000)
	set_setting('mdblist.token', access_token)
	set_setting('mdblist.refresh', token_result.get('refresh_token') or '0')
	from caches.settings_cache import settings_cache
	settings_cache.clear_db_cache()
	user_info = call_mdblist('user') or {}
	set_setting('mdblist.user', str(user_info.get('username') or user_info.get('user_id') or 'MDBList User'))
	settings_cache.clear_db_cache()
	mdblist_cache.clear_mdblist_collection_watchlist_data('watchlist')
	try: _mdbl_watchlist_raw()
	except: pass
	switched = settings.offer_watched_provider(3, 'MDBList')
	kodi_utils.notification('MDBList Account Authorised', 3000)
	if switched:
		try: mdblist_sync_activities(force_update=True)
		except Exception as e: kodi_utils.logger('MDBList', 'Post-auth sync failed: %s' % e)
	try: kodi_utils.container_refresh()
	except: pass
	return True

def mdblist_revoke_authentication(dummy=''):
	set_setting('mdblist.user', 'empty_setting')
	set_setting('mdblist.token', '0')
	set_setting('mdblist.refresh', '0')
	settings.fallback_watched_provider_on_revoke(3)
	mdblist_cache.clear_all_mdblist_cache_data(silent=True, refresh=False)
	kodi_utils.notification('MDBList Authorisation Reset', 3000)

MDBLIST_TRAKT_IMPORT_URL = 'https://mdblist.com/preferences/'

def mdblist_import_trakt(params=None):
	from threading import Thread
	from modules.trakt_import_help import open_official_trakt_import_page
	def _after():
		Thread(target=mdblist_sync_activities, kwargs={'force_update': True}, daemon=True).start()
	return open_official_trakt_import_page(
		'MDBList', MDBLIST_TRAKT_IMPORT_URL,
		icon=kodi_utils.get_icon('mdblist') or kodi_utils.addon_icon(),
		extra_line='On Preferences, use [B]Import from Trakt[/B].',
		after_close=_after)

def mdblist_force_sync(params=None):
	if not settings.mdblist_user_active(): return kodi_utils.notification('MDBList account not authorised', 3000)
	progress = kodi_utils.progress_dialog('MDBList Sync')
	progress.update('Syncing with MDBList...', 0)
	status = 'failed'
	try:
		status = mdblist_sync_activities(force_update=True, progress=progress)
	except Exception as e:
		kodi_utils.logger('MDBList', 'Force sync failed: %s' % e)
		status = 'failed'
	finally:
		kodi_utils.close_progress_dialog(progress)
	if status == 'canceled': return status
	if status == 'failed': kodi_utils.notification('MDBList Sync Failed', 3000)
	elif status != 'no account':
		kodi_utils.notification('MDBList Sync Complete', 3000)
		kodi_utils.kodi_refresh()
	return status

def _mdbl_watched_unwatched(action, media, media_id, tvdb_id=0, season=None, episode=None, key='tmdb'):
	if action == 'mark_as_watched': url, result_key = 'sync/watched', 'updated'
	else: url, result_key = 'sync/watched/remove', 'removed'
	try: media_id = int(media_id)
	except: pass
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
	if not isinstance(result, dict): return False
	success = result.get(result_key, {}).get(success_key, 0) > 0
	if not success and media != 'movies' and tvdb_id:
		return _mdbl_watched_unwatched(action, media, tvdb_id, 0, season, episode, 'tvdb')
	# Remove with 0 removed = already unwatched on MDBList — not a failure.
	if not success and action != 'mark_as_watched': return True
	return success

def mdblist_watched_status_mark(action, media_type, tmdb_id, tvdb_id=0, season=None, episode=None):
	if media_type == 'movie': media = 'movies'
	elif media_type == 'episode': media = 'episode'
	elif media_type == 'season': media = 'season'
	else: media = 'shows'
	success = _mdbl_watched_unwatched(action, media, tmdb_id, tvdb_id, season, episode)
	if success and action == 'mark_as_unwatched': mdblist_sync_activities()
	return success

def mdblist_official_status(media_type):
	if kodi_utils.service_scrobbler_defer('service.mdblist-scrobbler',
		auth_keys=('api_key', 'apikey', 'token', 'mdblist_api_key', 'mdblist.token', 'refresh_token'),
		scrobble_enable_keys=('scrobble', 'scrobble_enabled', 'enable_scrobble', 'scrobble_movies', 'scrobble_episodes')): return False
	return True

def mdblist_progress(action, media_type, tmdb_id, percent, season=None, episode=None, resume_id=None, refresh_mdblist=False):
	if action == 'clear_progress':
		call_mdblist('scrobble/clear', json_data={'id': resume_id}, method='post')
	else:
		try: tmdb_id = int(tmdb_id)
		except: pass
		if media_type == 'movie':
			payload = {'movie': {'ids': {'tmdb': tmdb_id}}, 'progress': float(percent)}
		else:
			payload = {'show': {'ids': {'tmdb': tmdb_id}, 'season': {'number': int(season), 'episode': {'number': int(episode)}}}, 'progress': float(percent)}
		call_mdblist('scrobble/pause', json_data=payload, method='post')
	if refresh_mdblist: mdblist_sync_activities(force_update=True)

def mdblist_reset_scrobble(params):
	if not settings.mdblist_user_active(): return
	tmdb_id = params.get('tmdb_id')
	tvdb_id = params.get('tvdb_id', 'None')
	season, episode = params.get('season'), params.get('episode')
	media_type = params.get('media_type') or params.get('content') or 'movie'
	from modules.watched_status import get_database, get_bookmarks_movie, get_bookmarks_episode
	watched_db = get_database(3)
	try:
		if media_type == 'movie':
			resume_id = get_bookmarks_movie(watched_db).get(str(tmdb_id), {}).get('resume_id')
			if resume_id: mdblist_progress('clear_progress', 'movie', tmdb_id, 0, resume_id=resume_id)
		else:
			bookmarks = get_bookmarks_episode(str(tmdb_id), season, watched_db)
			if episode and bookmarks:
				resume_id = bookmarks.get(int(episode), {}).get('resume_id')
				if resume_id: mdblist_progress('clear_progress', 'episode', tmdb_id, 0, season, episode, resume_id)
	except: pass
	mdblist_sync_activities(force_update=True)
	kodi_utils.notification('MDBList Scrobble Reset', 3000)
	kodi_utils.kodi_refresh()

_MDBL_DROPPED_CACHE_KEY = 'mdblist_hidden_items_dropped'

def _mdbl_dropped_show_tmdb(item):
	"""Resolve show TMDb from nested Trakt-shaped or flat MDBList dropped rows."""
	if not isinstance(item, dict): return None
	show = item.get('show') if isinstance(item.get('show'), dict) else item
	ids = show.get('ids') if isinstance(show.get('ids'), dict) else {}
	merged = dict(ids)
	for src_key, dst_key in (
		('tmdb', 'tmdb'), ('tmdb_id', 'tmdb'), ('tmdbid', 'tmdb'),
		('imdb', 'imdb'), ('imdb_id', 'imdb'), ('imdbid', 'imdb'),
		('tvdb', 'tvdb'), ('tvdb_id', 'tvdb'), ('tvdbid', 'tvdb'),
	):
		if show.get(src_key) not in (None, '', 'None', 0, '0') and dst_key not in merged:
			merged[dst_key] = show.get(src_key)
	# Some flat payloads use bare id as TMDb when mediatype is explicitly show.
	if 'tmdb' not in merged and (show.get('mediatype') or '').lower() in ('show', 'shows', 'tvshow') and show.get('id') not in (None, '', 'None'):
		try: merged['tmdb'] = int(show['id'])
		except: pass
	tmdb_id = _resolve_tvshow_id(merged)
	if not tmdb_id: return None
	try: return int(tmdb_id)
	except: return None

def mdblist_get_dropped_items():
	cached = mdblist_cache.mdblist_cache.get(_MDBL_DROPPED_CACHE_KEY)
	if cached is not None: return cached
	# Same cursor pagination as watched/watchlist — a single GET misses large Dropped sets
	# and list-shaped responses land under items (not shows).
	result = _get_mdbl_paginated_list('sync/dropped')
	# Failed fetch must not cache [] — that would clear Next Up's drop filter until expiry.
	if not isinstance(result, dict): return []
	rows = list(result.get('shows') or [])
	rows.extend(result.get('items') or [])
	items, seen = [], set()
	for item in rows:
		try:
			tmdb_id = _mdbl_dropped_show_tmdb(item)
			if tmdb_id and tmdb_id not in seen:
				seen.add(tmdb_id)
				items.append(tmdb_id)
		except: pass
	mdblist_cache.mdblist_cache.set(_MDBL_DROPPED_CACHE_KEY, items)
	return items

def _mdblist_dropped_payload(tmdb_id, imdb_id=None):
	payload = {'shows': [{'ids': {'tmdb': int(tmdb_id)}}]}
	if imdb_id and imdb_id not in ('None', '', '0'): payload['shows'][0]['ids']['imdb'] = imdb_id
	return payload

def _mdblist_resolve_show_imdb(tmdb_id, imdb_id=None):
	if imdb_id and imdb_id not in ('None', '', '0'): return imdb_id
	try:
		from modules.metadata import tvshow_meta
		from modules.settings import tmdb_api_key, mpaa_region
		from modules.utils import get_datetime
		meta = tvshow_meta('tmdb_id', tmdb_id, tmdb_api_key(), mpaa_region(), get_datetime())
		imdb_id = meta.get('imdb_id')
		if imdb_id and imdb_id not in ('None', '', '0'): return imdb_id
	except: pass
	return None

def _mdbl_dropped_count(block, bucket):
	if not isinstance(block, dict): return 0
	try: return int(block.get(bucket) or 0)
	except: return 0

def _mdbl_dropped_post_ok(result, action, mediatype):
	"""True/False from counts; None = unknown shape, check membership."""
	if not isinstance(result, dict) or result.get('error'): return False
	bucket = 'movies' if mediatype == 'movies' else 'shows'
	# MDBList Drop uses updated/existing (not Trakt-style added).
	has_counts = any(k in result for k in ('added', 'updated', 'existing', 'deleted', 'removed'))
	if not has_counts: return None
	if action == 'hide':
		# Newly dropped (updated/added), or already on Dropped (existing).
		return (
			_mdbl_dropped_count(result.get('updated'), bucket) > 0
			or _mdbl_dropped_count(result.get('added'), bucket) > 0
			or _mdbl_dropped_count(result.get('existing'), bucket) > 0
		)
	removed = _mdbl_dropped_count(result.get('deleted'), bucket) + _mdbl_dropped_count(result.get('removed'), bucket)
	# Some remove responses mirror Drop and use updated for the change count.
	if removed == 0:
		removed = _mdbl_dropped_count(result.get('updated'), bucket)
	return removed > 0

def mdblist_hide_unhide_progress_items(params):
	action, media_id = params['action'], params.get('media_id')
	imdb_id = params.get('imdb_id')
	mediatype = 'movies' if params.get('media_type') in ('movie', 'movies') else 'shows'
	if action in ('drop', 'hide'): action = 'hide'
	elif action in ('undrop', 'unhide'): action = 'unhide'
	elif action not in ('hide', 'unhide'):
		hidden = mdblist_get_dropped_items()
		action = 'unhide' if int(media_id) in hidden else 'hide'
	url = 'sync/dropped' if action == 'hide' else 'sync/dropped/remove'
	if mediatype == 'movies':
		json_data = {'movies': [{'ids': {'tmdb': int(media_id)}}]}
	else:
		json_data = _mdblist_dropped_payload(media_id, _mdblist_resolve_show_imdb(media_id, imdb_id))
	result = call_mdblist(url, json_data=json_data, method='post')
	mdblist_cache.mdblist_cache.delete(_MDBL_DROPPED_CACHE_KEY)
	if result is None:
		return kodi_utils.notification('Error', 3000)
	ok = _mdbl_dropped_post_ok(result, action, mediatype)
	# Membership fallback only for Drop — Undrop must see a real removed/updated count.
	# (A partial Dropped fetch missing the show would otherwise false-succeed Undrop.)
	if ok is None and action == 'hide':
		try: mid = int(media_id)
		except: mid = None
		dropped = mdblist_get_dropped_items()
		ok = mid in dropped if mid is not None else False
	if not ok:
		return kodi_utils.notification('Error', 3000)
	mdblist_sync_activities()
	kodi_utils.kodi_refresh()
	if action == 'hide': kodi_utils.notification('Dropped from MDBList Progress', 3000)
	else: kodi_utils.notification('Removed from MDBList Dropped', 3000)

def mdblist_indicators_movies(watched_info):
	if watched_info is None: return False
	insert_list = []
	def _process(item):
		tmdb_id = _resolve_movie_id(item.get('movie', {}).get('ids', {}))
		if tmdb_id: insert_list.append(('movie', tmdb_id, '', '', item.get('last_watched_at', ''), item.get('movie', {}).get('title', '')))
	movies = watched_info.get('movies', [])
	for i in TaskPool().tasks(_process, movies, min(len(movies), settings.max_threads())): i.join()
	mdblist_cache.mdblist_watched_cache.set_bulk_movie_watched(insert_list)
	return True

def mdblist_indicators_tv(watched_info):
	if watched_info is None: return False
	insert_list = []
	def _process(item):
		show_ids = item.get('episode', {}).get('show', {}).get('ids', {})
		tmdb_id = _resolve_tvshow_id(show_ids)
		if not tmdb_id: return
		ep = item.get('episode', {})
		insert_list.append(('episode', tmdb_id, ep.get('season'), ep.get('number'), item.get('last_watched_at', ''), ep.get('show', {}).get('title', '')))
	episodes = watched_info.get('episodes', [])
	for i in TaskPool().tasks(_process, episodes, min(len(episodes), settings.max_threads())): i.join()
	mdblist_cache.mdblist_watched_cache.set_bulk_tvshow_watched(insert_list)
	return True

def mdblist_progress_movies(progress_info):
	if progress_info is None: return False
	insert_list = []
	def _process(item):
		tmdb_id = _resolve_movie_id(item.get('movie', {}).get('ids', {}))
		if tmdb_id:
			insert_list.append(('movie', tmdb_id, '', '', str(round(float(item['progress']), 1)), 0, item.get('paused_at', ''), item['id'], item.get('movie', {}).get('title', '')))
	threads = list(make_thread_list(_process, [i for i in progress_info if i.get('type') == 'movie' and float(i.get('progress', 0)) > 1]))
	[i.join() for i in threads]
	mdblist_cache.mdblist_watched_cache.set_bulk_movie_progress(insert_list)
	return True

def mdblist_progress_tv(progress_info):
	if progress_info is None: return False
	insert_list = []
	def _process(item):
		tmdb_id = _resolve_tvshow_id(item.get('show', {}).get('ids', {}))
		if not tmdb_id: return
		season, episode = item.get('episode', {}).get('season'), item.get('episode', {}).get('number')
		if season and int(season) > 0:
			insert_list.append(('episode', tmdb_id, season, episode, str(round(float(item['progress']), 1)), 0, item.get('paused_at', ''), item['id'], item.get('show', {}).get('title', '')))
	threads = list(make_thread_list(_process, [i for i in progress_info if i.get('type') == 'episode' and float(i.get('progress', 0)) > 1]))
	[i.join() for i in threads]
	mdblist_cache.mdblist_watched_cache.set_bulk_tvshow_progress(insert_list)
	return True

def mdblist_sync_activities(params=None, force_update=False, progress=None):
	if isinstance(params, dict): force_update = params.get('force_update', 'false') in ('true', 'True', True) or force_update
	if not settings.mdblist_user_active(): return 'no account'
	def _sync_canceled():
		return progress and progress.iscanceled()
	if force_update:
		mdblist_cache.clear_all_mdblist_cache_data(silent=True, refresh=False)
	if _sync_canceled(): return 'canceled'
	latest = call_mdblist('sync/last_activities')
	if not latest: return 'failed'
	if _sync_canceled(): return 'canceled'
	cached = mdblist_cache.reset_activity(latest)
	def _changed(key):
		try: return (latest.get(key) or '') > (cached.get(key) or '')
		except: return True
	success = 'not needed'
	if force_update or _changed('collected_at'):
		success = 'success'
		mdblist_cache.clear_mdblist_collection_watchlist_data('collection')
	if _sync_canceled(): return 'canceled'
	if force_update or _changed('watchlisted_at'):
		success = 'success'
		mdblist_cache.clear_mdblist_collection_watchlist_data('watchlist')
		mdblist_cache.clear_mdblist_calendar_data()
	if _sync_canceled(): return 'canceled'
	if force_update or _changed('dropped_at'):
		success = 'success'
		mdblist_cache.mdblist_cache.delete(_MDBL_DROPPED_CACHE_KEY)
	if _sync_canceled(): return 'canceled'
	if force_update or _changed('list_updated_at'):
		success = 'success'
		for list_type in ('external', 'my_lists'):
			mdblist_cache.clear_mdblist_list_data(list_type)
			mdblist_cache.clear_mdblist_list_contents_data(list_type)
		mdblist_cache.mdblist_cache.delete('mdblist_liked_lists')
	refresh_movies = force_update or _changed('watched_at')
	refresh_episodes = force_update or _changed('episode_watched_at')
	refresh_movie_pause = force_update or _changed('paused_at')
	refresh_episode_pause = force_update or _changed('episode_paused_at')
	if refresh_episodes:
		mdblist_cache.clear_mdblist_calendar_data()
	if refresh_movies or refresh_episodes:
		if _sync_canceled(): return 'canceled'
		success = 'success'
		watched_info = _get_mdbl_paginated_list('sync/watched')
		if watched_info is None: return 'failed'
		if _sync_canceled(): return 'canceled'
		if refresh_movies: mdblist_indicators_movies(watched_info)
		if _sync_canceled(): return 'canceled'
		if refresh_episodes: mdblist_indicators_tv(watched_info)
	if refresh_movie_pause or refresh_episode_pause:
		if _sync_canceled(): return 'canceled'
		success = 'success'
		items = _get_mdbl_playback_items()
		if items is None: return 'failed'
		if _sync_canceled(): return 'canceled'
		if refresh_movie_pause: mdblist_progress_movies(items)
		if _sync_canceled(): return 'canceled'
		if refresh_episode_pause: mdblist_progress_tv(items)
	return success

def _mdbl_collection_watchlist_items(string, url):
	return mdblist_cache.cache_mdblist_object(_get_mdbl_paginated_list, string, url) or {'movies': [], 'shows': []}

def _mdbl_watchlist_raw():
	string, url = 'mdblist_watchlist_live', 'watchlist/items'
	return mdblist_cache.cache_mdblist_object(_get_mdbl_paginated_list, string, url) or {'movies': [], 'shows': [], 'items': []}

def _mdblist_watchlist_normalized(media_kind):
	# Umbrella/POV: plain GET watchlist/items → flat movies[]/shows[] (id = TMDb, imdb_id on item).
	raw = _mdbl_watchlist_raw()
	key = 'movies' if media_kind in ('movie', 'movies') else 'shows'
	original_list = list(raw.get(key) or [])
	if not original_list:
		for item in raw.get('items') or []:
			kind = _mdbl_item_media_kind(item)
			if key == 'movies' and kind == 'movie': original_list.append(item)
			elif key == 'shows' and kind == 'show': original_list.append(item)
	if not original_list:
		kodi_utils.logger('MDBList Watchlist', 'No %s items (movies=%s shows=%s)' % (
			media_kind, len(raw.get('movies') or []), len(raw.get('shows') or [])))
	else:
		kodi_utils.logger('MDBList Watchlist', '%s: %s items' % (media_kind, len(original_list)))
	normalized = []
	for item in original_list:
		entry = _mdbl_item_to_list_entry(item, media_kind)
		if entry: normalized.append(entry)
	if original_list and not normalized:
		kodi_utils.logger('MDBList Watchlist', 'Could not resolve TMDb ids from %s raw items' % len(original_list))
	return list_sort.sort_source(normalized, 'mdblist.watchlist', media_kind, 'mdblist_watchlist')

def mdblist_watchlist(media_kind, page_no):
	original_list = _mdblist_watchlist_normalized(media_kind)
	is_home = kodi_utils.external()
	if settings.paginate(is_home): return paginate_list(original_list, page_no, settings.page_limit(is_home))
	return original_list, 1

def mdblist_watchlist_media_ids(media_kind):
	"""Full watchlist as media_ids dicts (no pagination) for Next Episodes include-unwatched."""
	result = []
	for entry in _mdblist_watchlist_normalized(media_kind):
		try: tmdb_id = int(entry['id'])
		except: continue
		result.append({'media_ids': {'tmdb': tmdb_id, 'imdb': entry.get('imdb_id') or '', 'tvdb': entry.get('tvdb_id') or ''},
			'title': entry.get('title', '')})
	return result

def mdblist_collection(media_kind, page_no):
	string, url = 'mdblist_collection', 'sync/collection'
	original_list = _mdbl_personal_list(_mdbl_collection_watchlist_items(string, url), media_kind)
	original_list = list_sort.sort_source(original_list, 'mdblist.collection', media_kind, 'mdblist_collection')
	is_home = kodi_utils.external()
	if settings.paginate(is_home): return paginate_list(original_list, page_no, settings.page_limit(is_home))
	return original_list, 1

def mdblist_droplist(media_kind, page_no):
	return [{'id': i, 'imdb_id': ''} for i in mdblist_get_dropped_items()], 1

def _mdbl_normalize_list_response(result):
	if isinstance(result, list): return result
	if isinstance(result, dict):
		for key in ('items', 'lists', 'liked', 'data', 'results'):
			if isinstance(result.get(key), list): return result[key]
	return []

def _mdbl_expand_list_entries(lists):
	"""Normalize list rows; expand unified twin lists that return `ids` instead of `id`."""
	expanded = []
	for item in lists or []:
		if not isinstance(item, dict): continue
		list_id = item.get('id')
		if list_id not in (None, '', 0, '0'):
			expanded.append(item)
			continue
		ids = item.get('ids') or []
		if not isinstance(ids, (list, tuple)): continue
		for lid in ids:
			if lid in (None, '', 0, '0'): continue
			row = dict(item)
			row['id'] = lid
			expanded.append(row)
	return expanded

def _mdbl_list_is_dynamic(item):
	if not isinstance(item, dict): return False
	if item.get('dynamic') is True: return True
	list_type = (item.get('type') or '').lower()
	return list_type in ('dynamic', 'ai', 'ailist', 'ai_list')

def _mdbl_list_is_static(item):
	if not isinstance(item, dict): return False
	if item.get('source'): return False
	return not _mdbl_list_is_dynamic(item)

def _mdbl_list_matches_media_type(item, media_type):
	if not media_type: return True
	mediatype = (item.get('mediatype') or item.get('media_type') or '').lower()
	if not mediatype: return True
	if media_type in ('movie', 'movies'): return mediatype in ('movie', 'movies')
	if media_type in ('episode', 'episodes'): return mediatype in ('episode', 'episodes')
	return mediatype in ('show', 'shows', 'tvshow', 'tv', 'series')

def mdbl_get_lists(list_type, refresh=False):
	if list_type == 'external': string, url = 'mdblist_external', 'external/lists/user'
	else: string, url = 'mdblist_my_lists', 'lists/user'
	if refresh:
		mdblist_cache.mdblist_cache.delete(string)
	result = mdblist_cache.cache_mdblist_object(call_mdblist, string, url)
	lists = _mdbl_normalize_list_response(result)
	if not lists and isinstance(result, dict):
		lists = result.get('items') or []
	return _mdbl_expand_list_entries(lists)

def mdbl_get_liked_lists(media_type=None):
	result = mdblist_cache.cache_mdblist_object(call_mdblist, 'mdblist_liked_lists', 'lists/liked')
	lists = _mdbl_expand_list_entries(_mdbl_normalize_list_response(result))
	if not media_type: return lists
	return [i for i in lists if _mdbl_list_matches_media_type(i, media_type)]

def mdbl_top_lists():
	result = mdblist_cache.cache_mdblist_object(call_mdblist, 'mdblist_top_lists', 'lists/top')
	lists = _mdbl_normalize_list_response(result)
	if not lists and isinstance(result, dict):
		lists = result.get('items') or []
	return _mdbl_expand_list_entries(lists)

def get_mdbl_list_payload(list_type, list_id):
	string = 'mdblist_list_contents_%s_%s' % (list_type, list_id)
	if list_type == 'external': url = 'external/lists/%s/items?unified=true' % list_id
	else: url = 'lists/%s/items?unified=true' % list_id
	result = mdblist_cache.cache_mdblist_object(_get_mdbl_paginated_list, string, url)
	return result if isinstance(result, dict) else {}

def get_mdbl_list_contents(list_type, list_id):
	result = get_mdbl_list_payload(list_type, list_id)
	items = result.get('items') or []
	if items: return items
	# Non-unified responses: membership/browse for movies/shows only (episodes use payload).
	return list(result.get('movies') or []) + list(result.get('shows') or [])

def get_mdbl_list_episode_rows(list_type, list_id):
	_, _, episode_items = mdbl_collect_list_media(get_mdbl_list_payload(list_type, list_id))
	rows = []
	for order, item in enumerate(episode_items):
		row = mdbl_episode_list_entry(item, order)
		if row: rows.append(row)
	return rows

def mdbl_get_static_lists(media_type=None, refresh=False):
	"""User-owned static lists (editable). Dynamic/AI/external lists are excluded."""
	lists = [i for i in mdbl_get_lists('my_lists', refresh=refresh) if _mdbl_list_is_static(i)]
	if media_type:
		lists = [i for i in lists if _mdbl_list_matches_media_type(i, media_type)]
	lists.sort(key=lambda k: (k.get('name') or '').lower())
	return lists

def _mdblist_list_payload(media_type, tmdb_id, imdb_id=None):
	if media_type == 'movie':
		payload = {'movies': [{'ids': {'tmdb': int(tmdb_id)}}]}
	else:
		payload = {'shows': [{'ids': {'tmdb': int(tmdb_id)}}]}
		if imdb_id and imdb_id not in ('None', '', '0'): payload['shows'][0]['ids']['imdb'] = imdb_id
	return payload

def _mdbl_episode_context(params):
	"""Return (season, episode) ints when manager was opened from an episode row."""
	season, episode = params.get('season'), params.get('episode')
	try:
		season, episode = int(season), int(episode)
	except: return None, None
	if season < 0 or episode < 0: return None, None
	return season, episode

def _mdbl_resolve_episode_tmdb(show_tmdb, season, episode, episode_id=None):
	if episode_id not in (None, '', 'None', '0', 0):
		try: return int(episode_id)
		except: pass
	try:
		from modules import metadata
		from modules.utils import get_datetime
		meta = metadata.tvshow_meta('tmdb_id', show_tmdb, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
		for ep in metadata.episodes_meta(int(season), meta) or []:
			if int(ep.get('episode') or 0) != int(episode): continue
			eid = ep.get('episode_id')
			if eid not in (None, '', 'None', '0', 0): return int(eid)
	except: pass
	return None

def _mdblist_static_list_payload(media_type, tmdb_id, imdb_id=None, season=None, episode=None, episode_tmdb=None):
	# Static list modify uses flat tmdb/imdb keys (not the watchlist ids wrapper).
	# Episodes need the episode TMDb id (not the show); season/episode help MDBList match.
	if media_type in ('episode', 'episodes') and season is not None and episode is not None:
		entry = {'season': int(season), 'episode': int(episode)}
		if episode_tmdb not in (None, '', 'None', '0', 0):
			entry['tmdb'] = int(episode_tmdb)
		elif tmdb_id not in (None, '', 'None', '0', 0):
			# Fallback: some callers already pass episode TMDb as tmdb_id.
			entry['tmdb'] = int(tmdb_id)
		return {'episodes': [entry]}
	entry = {'tmdb': int(tmdb_id)}
	if imdb_id and imdb_id not in ('None', '', '0'): entry['imdb'] = imdb_id
	if media_type == 'movie':
		return {'movies': [entry]}
	return {'shows': [entry]}

def _mdbl_static_result_count(result, key):
	block = (result or {}).get(key) or {}
	if not isinstance(block, dict): return 0
	return int(block.get('movies') or 0) + int(block.get('shows') or 0) + int(block.get('seasons') or 0) + int(block.get('episodes') or 0)

def _mdbl_clear_static_list_cache(list_id):
	mdblist_cache.mdblist_cache.delete('mdblist_list_contents_my_lists_%s' % list_id)
	mdblist_cache.mdblist_cache.delete('mdblist_my_lists')

def mdblist_item_in_static_list(list_id, tmdb_id):
	try: tmdb_id = int(tmdb_id)
	except: return False
	for item in get_mdbl_list_contents('my_lists', list_id) or []:
		try:
			if int(mdbl_unified_item_tmdb_id(item) or 0) == tmdb_id: return True
		except: pass
	return False

def mdblist_episode_in_static_list(list_id, show_tmdb, season, episode, episode_tmdb=None):
	try:
		show_tmdb, season, episode = int(show_tmdb), int(season), int(episode)
	except: return False
	try: episode_tmdb = int(episode_tmdb) if episode_tmdb not in (None, '', 'None', '0', 0) else None
	except: episode_tmdb = None
	for item in get_mdbl_list_contents('my_lists', list_id) or []:
		if _mdbl_item_media_kind(item) != 'episode': continue
		item_season = _mdbl_first_int(item.get('season'), item.get('season_number'))
		item_episode = _mdbl_first_int(item.get('episode_number'), item.get('episode'), item.get('number'))
		if item_season is None or item_episode is None: continue
		if int(item_season) != season or int(item_episode) != episode: continue
		show_block = item.get('show') if isinstance(item.get('show'), dict) else {}
		ids_block = item.get('ids') if isinstance(item.get('ids'), dict) else {}
		item_show = _mdbl_first_int(item.get('show_tmdb'), item.get('show_id'), show_block.get('tmdb'))
		if item_show is not None and int(item_show) == show_tmdb: return True
		# Unified episode rows expose episode TMDb as flat id.
		item_ep_tmdb = _mdbl_first_int(item.get('tmdb'), item.get('id'), ids_block.get('tmdb'))
		if episode_tmdb is not None and item_ep_tmdb is not None and int(item_ep_tmdb) == episode_tmdb: return True
	return False

def mdblist_static_lists_split_by_membership(media_type, tmdb_id, refresh=True, season=None, episode=None, episode_tmdb=None):
	results = []
	results_append = results.append
	episode_mode = media_type in ('episode', 'episodes') and season is not None and episode is not None
	def _check(item):
		list_id = item.get('id')
		if list_id in (None, '', 0, '0'): return
		entry = {
			'name': item.get('name') or 'MDBList',
			'display': '[B]STATIC:[/B] [I]%s[/I]' % (item.get('name') or 'MDBList').upper(),
			'list_id': list_id,
			'list_type': 'my_lists',
			'item_count': item.get('items') or 0,
			'dynamic': False,
		}
		if episode_mode:
			is_in = mdblist_episode_in_static_list(list_id, tmdb_id, season, episode, episode_tmdb)
		else:
			is_in = mdblist_item_in_static_list(list_id, tmdb_id)
		results_append((entry, is_in))
	static_lists = mdbl_get_static_lists(media_type, refresh=refresh)
	if not static_lists: return [], []
	threads = TaskPool().tasks(_check, static_lists, min(len(static_lists), settings.max_threads()) or 1)
	[i.join() for i in threads]
	in_lists, out_lists = [], []
	for entry, is_in in results:
		(in_lists if is_in else out_lists).append(entry)
	in_lists.sort(key=lambda k: k['name'].lower())
	out_lists.sort(key=lambda k: k['name'].lower())
	return in_lists, out_lists

def select_mdblist_static_lists(lists):
	if not lists: return None
	list_items = [{'line1': '%s [I](x%02d)[/I]' % (item['display'], item.get('item_count', 0))} for item in lists]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Select MDBList', 'narrow_window': 'true'}
	return kodi_utils.select_dialog(lists, **kwargs)

def mdblist_add_to_static_list(list_id, tmdb_id, media_type, imdb_id=None, list_name=None, season=None, episode=None, episode_tmdb=None):
	payload = _mdblist_static_list_payload(media_type, tmdb_id, imdb_id, season=season, episode=episode, episode_tmdb=episode_tmdb)
	result = call_mdblist('lists/%s/items/add' % list_id, json_data=payload, method='post')
	_mdbl_clear_static_list_cache(list_id)
	label = list_name or 'MDBList'
	if isinstance(result, dict):
		added = _mdbl_static_result_count(result, 'added')
		existing = _mdbl_static_result_count(result, 'existing')
		if added > 0:
			kodi_utils.notification('Added to %s' % label, 3000)
			return result
		if existing > 0:
			return kodi_utils.notification('Already In List', 3000)
	return kodi_utils.notification('Error', 3000)

def mdblist_remove_from_static_list(list_id, tmdb_id, media_type, imdb_id=None, list_name=None, season=None, episode=None, episode_tmdb=None):
	payload = _mdblist_static_list_payload(media_type, tmdb_id, imdb_id, season=season, episode=episode, episode_tmdb=episode_tmdb)
	result = call_mdblist('lists/%s/items/remove' % list_id, json_data=payload, method='post')
	_mdbl_clear_static_list_cache(list_id)
	label = list_name or 'MDBList'
	removed = _mdbl_static_result_count(result, 'removed') if isinstance(result, dict) else 0
	# Some MDBList responses omit removed counts; confirm via fresh membership check.
	if media_type in ('episode', 'episodes') and season is not None and episode is not None:
		still_in = mdblist_episode_in_static_list(list_id, tmdb_id, season, episode, episode_tmdb)
	else:
		still_in = mdblist_item_in_static_list(list_id, tmdb_id)
	if removed > 0 or (result is not None and 'error' not in (result or {}) and not still_in):
		kodi_utils.notification('Removed from %s' % label, 3000)
		if kodi_utils.path_check('build_mdbl_list') or kodi_utils.external(): kodi_utils.kodi_refresh()
		return result
	return kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000)

def mdblist_add_to_watchlist(tmdb_id, media_type, imdb_id=None):
	result = call_mdblist('watchlist/items/add', json_data=_mdblist_list_payload(media_type, tmdb_id, imdb_id), method='post')
	if isinstance(result, dict) and result.get('added', {}).get('movies', 0) + result.get('added', {}).get('shows', 0) > 0:
		mdblist_sync_activities()
		return kodi_utils.notification('Added to MDBList Watchlist', 3000)
	if isinstance(result, dict) and result.get('existing', {}).get('movies', 0) + result.get('existing', {}).get('shows', 0) > 0:
		return kodi_utils.notification('Already In List', 3000)
	return kodi_utils.notification('Error', 3000)

def mdblist_remove_from_watchlist(tmdb_id, media_type, imdb_id=None):
	result = call_mdblist('watchlist/items/remove', json_data=_mdblist_list_payload(media_type, tmdb_id, imdb_id), method='post')
	if isinstance(result, dict) and result.get('removed', {}).get('movies', 0) + result.get('removed', {}).get('shows', 0) > 0:
		mdblist_sync_activities()
		kodi_utils.kodi_refresh()
		return kodi_utils.notification('Removed from MDBList Watchlist', 3000)
	return kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000)

def mdblist_add_to_library(tmdb_id, media_type, imdb_id=None):
	result = call_mdblist('sync/collection', json_data=_mdblist_list_payload(media_type, tmdb_id, imdb_id), method='post')
	if isinstance(result, dict) and result.get('updated', {}).get('movies', 0) + result.get('updated', {}).get('shows', 0) > 0:
		mdblist_sync_activities()
		return kodi_utils.notification('Added to MDBList Library', 3000)
	if isinstance(result, dict) and result.get('existing', {}).get('movies', 0) + result.get('existing', {}).get('shows', 0) > 0:
		return kodi_utils.notification('Already In List', 3000)
	return kodi_utils.notification('Error', 3000)

def mdblist_remove_from_library(tmdb_id, media_type, imdb_id=None):
	result = call_mdblist('sync/collection/remove', json_data=_mdblist_list_payload(media_type, tmdb_id, imdb_id), method='post')
	if isinstance(result, dict) and result.get('removed', {}).get('movies', 0) + result.get('removed', {}).get('shows', 0) > 0:
		mdblist_sync_activities()
		kodi_utils.kodi_refresh()
		return kodi_utils.notification('Removed from MDBList Library', 3000)
	return kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000)

def _mdbl_personal_tmdb_ids(media_kind, fetch_func):
	try:
		data, _ = fetch_func(media_kind, 1)
	except: return set()
	ids = set()
	for item in data or []:
		if not isinstance(item, dict): continue
		tmdb_id = item.get('id') or item.get('tmdb') or (item.get('ids') or {}).get('tmdb')
		if tmdb_id:
			try: ids.add(int(tmdb_id))
			except: pass
	return ids

def _mdbl_item_in_watchlist(list_media, tmdb_id):
	try: tmdb_id = int(tmdb_id)
	except: return False
	media_kind = 'movies' if list_media == 'movie' else 'shows'
	return tmdb_id in _mdbl_personal_tmdb_ids(media_kind, mdblist_watchlist)

def _mdbl_item_in_library(list_media, tmdb_id):
	try: tmdb_id = int(tmdb_id)
	except: return False
	media_kind = 'movies' if list_media == 'movie' else 'shows'
	return tmdb_id in _mdbl_personal_tmdb_ids(media_kind, mdblist_collection)

def _mdbl_item_in_dropped(tmdb_id):
	try: tmdb_id = int(tmdb_id)
	except: return False
	return tmdb_id in mdblist_get_dropped_items()

def mdblist_manager_choice(params):
	if not settings.mdblist_user_active(): return kodi_utils.notification('No Active MDBList Account', 3500)
	media_type = params.get('media_type') or params.get('content') or 'movie'
	list_media = 'movie' if media_type == 'movie' else 'tvshow'
	icon = params.get('icon') or kodi_utils.get_icon('mdblist')
	tmdb_id, imdb_id, tvdb_id = params.get('tmdb_id'), params.get('imdb_id'), params.get('tvdb_id')
	season, episode = _mdbl_episode_context(params)
	episode_mode = list_media != 'movie' and season is not None and episode is not None
	episode_tmdb = None
	if episode_mode:
		episode_tmdb = _mdbl_resolve_episode_tmdb(tmdb_id, season, episode, params.get('episode_id'))
	# Show-scoped static lists always (restore add-show from episode rows).
	show_in_lists, show_out_lists = mdblist_static_lists_split_by_membership(list_media, tmdb_id, refresh=True)
	ep_in_lists, ep_out_lists = [], []
	if episode_mode and episode_tmdb:
		ep_in_lists, ep_out_lists = mdblist_static_lists_split_by_membership(
			'episode', tmdb_id, refresh=False, season=season, episode=episode, episode_tmdb=episode_tmdb
		)
	choices = []
	if _mdbl_item_in_watchlist(list_media, tmdb_id):
		choices.append(('Remove from [B]MDBList Watchlist[/B]', 'remove_watchlist'))
	else:
		choices.append(('Add to [B]MDBList Watchlist[/B]', 'add_watchlist'))
	if _mdbl_item_in_library(list_media, tmdb_id):
		choices.append(('Remove from [B]MDBList Library[/B]', 'remove_library'))
	else:
		choices.append(('Add to [B]MDBList Library[/B]', 'add_library'))
	if episode_mode:
		if show_out_lists:
			choices.append(('Add TV Show To [B]Static List[/B]...', 'add_static_show'))
		if show_in_lists:
			choices.append(('Remove TV Show from [B]Static List[/B]...', 'remove_static_show'))
		if episode_tmdb:
			if ep_out_lists:
				choices.append(('Add Episode To [B]Static List[/B]...', 'add_static_episode'))
			if ep_in_lists:
				choices.append(('Remove Episode from [B]Static List[/B]...', 'remove_static_episode'))
	else:
		if show_out_lists:
			choices.append(('Add To [B]Static List[/B]...', 'add_static_show'))
		if show_in_lists:
			choices.append(('Remove from [B]Static List[/B]...', 'remove_static_show'))
	if list_media != 'movie':
		if _mdbl_item_in_dropped(tmdb_id):
			choices.append(('Undrop [B]TV Show[/B]', 'undrop'))
		else:
			choices.append(('Drop [B]TV Show[/B]', 'drop'))
	choices.extend([
		('Mark as [B]Watched[/B]', 'mark_watched'),
		('Mark as [B]Unwatched[/B]', 'mark_unwatched'),
		('Reset [B]Scrobble[/B]', 'reset_scrobble'),
		('Open [B]MDBList Watchlist[/B]', 'open_watchlist'),
		('Open [B]MDBList Library[/B]', 'open_library'),
	])
	if list_media != 'movie':
		choices.append(('Open [B]Dropped TV Shows[/B]', 'open_dropped'))
	choices.extend([
		('Open [B]Liked Lists[/B]', 'open_liked_lists'),
		('Open [B]My MDBLists[/B]', 'open_my_lists'),
		('Refresh Widgets', 'refresh'),
	])
	list_items = [{'line1': item[0], 'icon': icon} for item in choices]
	choice = kodi_utils.select_dialog([i[1] for i in choices], **{'items': json.dumps(list_items), 'heading': 'MDBList Manager'})
	if choice is None: return
	if choice == 'refresh':
		kodi_utils.kodi_refresh()
		return kodi_utils.notification('Widgets Refreshed', 2500)
	watchlist_label = 'Movies Watchlist' if list_media == 'movie' else 'TV Shows Watchlist'
	library_label = 'Movies Library' if list_media == 'movie' else 'TV Shows Library'
	watchlist_mode = 'build_movie_list' if list_media == 'movie' else 'build_tvshow_list'
	library_mode = 'build_movie_list' if list_media == 'movie' else 'build_tvshow_list'
	open_modes = {
		'open_watchlist': {'mode': watchlist_mode, 'action': 'mdblist_watchlist', 'category_name': watchlist_label},
		'open_library': {'mode': library_mode, 'action': 'mdblist_collection', 'category_name': library_label},
		'open_dropped': {'mode': 'build_tvshow_list', 'action': 'mdblist_droplist', 'category_name': 'Dropped TV Shows'},
		'open_liked_lists': {'mode': 'mdblist.get_mdbl_liked_lists', 'name': 'Liked Lists'},
		'open_my_lists': {'mode': 'mdblist.get_mdbl_lists', 'name': 'My Lists'},
	}
	if choice in open_modes:
		return kodi_utils.container_update(open_modes[choice])
	if choice == 'mark_watched':
		from indexers.dialogs import _trakt_manager_mark
		return _trakt_manager_mark(params, 'mark_as_watched')
	if choice == 'mark_unwatched':
		from indexers.dialogs import _trakt_manager_mark
		return _trakt_manager_mark(params, 'mark_as_unwatched')
	if choice == 'reset_scrobble':
		return mdblist_reset_scrobble(params)
	if choice == 'add_watchlist':
		return mdblist_add_to_watchlist(tmdb_id, list_media, imdb_id)
	if choice == 'remove_watchlist':
		return mdblist_remove_from_watchlist(tmdb_id, list_media, imdb_id)
	if choice == 'add_library':
		return mdblist_add_to_library(tmdb_id, list_media, imdb_id)
	if choice == 'remove_library':
		return mdblist_remove_from_library(tmdb_id, list_media, imdb_id)
	if choice == 'drop':
		return mdblist_hide_unhide_progress_items({'action': 'drop', 'media_type': 'shows', 'media_id': tmdb_id, 'imdb_id': imdb_id})
	if choice == 'undrop':
		return mdblist_hide_unhide_progress_items({'action': 'undrop', 'media_type': 'shows', 'media_id': tmdb_id, 'imdb_id': imdb_id})
	if choice in ('add_static_show', 'remove_static_show'):
		selected = select_mdblist_static_lists(show_out_lists if choice == 'add_static_show' else show_in_lists)
		if selected is None: return
		if choice == 'add_static_show':
			return mdblist_add_to_static_list(selected['list_id'], tmdb_id, list_media, imdb_id, selected.get('name'))
		return mdblist_remove_from_static_list(selected['list_id'], tmdb_id, list_media, imdb_id, selected.get('name'))
	if choice in ('add_static_episode', 'remove_static_episode'):
		if not episode_tmdb:
			return kodi_utils.notification('Unable to resolve episode for MDBList', 3500)
		selected = select_mdblist_static_lists(ep_out_lists if choice == 'add_static_episode' else ep_in_lists)
		if selected is None: return
		if choice == 'add_static_episode':
			return mdblist_add_to_static_list(
				selected['list_id'], tmdb_id, 'episode', imdb_id, selected.get('name'),
				season=season, episode=episode, episode_tmdb=episode_tmdb
			)
		return mdblist_remove_from_static_list(
			selected['list_id'], tmdb_id, 'episode', imdb_id, selected.get('name'),
			season=season, episode=episode, episode_tmdb=episode_tmdb
		)

def mdblist_get_my_calendar(dummy=None):
	"""Episode airings for the authenticated user (undocumented /calendar/events).

	MDBList only returns past airings when start/end are on the request (same as POV).
	Fetch the max Calendars day span (14 previous + 14 future); Show Previous/Future
	Days still filters on read so settings apply without waiting for cache expiry.
	"""
	from datetime import timedelta
	from modules.utils import get_datetime
	def _process(_url, params=None):
		result = call_mdblist(_url, params=params)
		if not result: return []
		# call_mdblist wraps bare JSON arrays as {'items': [...]}. Calendar may also
		# return {'events': [...]} — accept either (MDBList has flipped shapes before).
		if isinstance(result, dict):
			events = result.get('events')
			if not isinstance(events, list):
				events = result.get('items')
		else:
			events = result
		if not isinstance(events, list): return []
		data = []
		for item in events:
			try:
				if not isinstance(item, dict): continue
				# Episodes only — skip movie premieres. Do not filter release_type=watched:
				# MDBList tags upcoming airings of in-progress shows that way too.
				item_type = item.get('type')
				if item_type and item_type != 'episode': continue
				show_tmdb = item.get('show_tmdb') or item.get('show_id')
				season, episode = item.get('season_number'), item.get('episode_number')
				start = item.get('start')
				if not show_tmdb or season is None or episode is None or not start: continue
				if int(season) < 1: continue
				title = item.get('title') or ''
				data.append({
					'sort_title': '%s s%s e%s' % (title, str(season).zfill(2), str(episode).zfill(2)),
					'media_ids': {'tmdb': int(show_tmdb)},
					'season': int(season),
					'episode': int(episode),
					# Keep full ISO when present so Calendars UTC (+/-) can apply.
					'first_aired': str(start)
				})
			except Exception:
				continue
		# Prefer latest occurrence when the API repeats the same show/day.
		data = [i for n, i in enumerate(data) if i not in data[n + 1:]]
		return data
	# v5: keep full start timestamps (UTC adjust); start/end so past airings are included.
	# Empty list is not a valid cache hit — refetch (failed API used to poison the cache).
	current = get_datetime()
	api_start = (current - timedelta(days=14)).strftime('%Y-%m-%d')
	api_end = (current + timedelta(days=14)).strftime('%Y-%m-%d')
	cache_key = 'mdblist_calendar_airings_v5_%s_%s' % (api_start, api_end)
	cached = mdblist_cache.mdblist_cache.get(cache_key)
	if cached:
		data = cached
	else:
		data = _process('calendar/events', {
			'limit': 1000, 'start': api_start, 'end': api_end
		}) or []
		if data: mdblist_cache.mdblist_cache.set(cache_key, data)
		elif cached is not None:
			mdblist_cache.mdblist_cache.delete(cache_key)
	filtered = _filter_mdblist_calendar_day_window(data)
	try:
		start_date, end_date = settings.calendar_day_window()
		kodi_utils.logger('Red Light', 'MDBList calendar: %s cached/fetched, %s in day window (%s → %s)' % (
			len(data), len(filtered), start_date, end_date))
	except Exception:
		pass
	return filtered

def _filter_mdblist_calendar_day_window(data):
	# Use the same local-day logic as list labels (ISO + UTC offset, or date-only).
	from modules.utils import calendar_service_local_date
	start_date, end_date = settings.calendar_day_window()
	filtered = []
	for item in data:
		aired, _ = calendar_service_local_date(item.get('first_aired', ''))
		if aired is None: continue
		if start_date <= aired <= end_date:
			filtered.append(item)
	return filtered

def get_mdbl_lists(params):
	from indexers import mdblist_lists
	return mdblist_lists.get_mdbl_lists(params)

def get_mdbl_liked_lists(params):
	from indexers import mdblist_lists
	return mdblist_lists.get_mdbl_liked_lists(params)

def get_mdbl_top_lists(params):
	from indexers import mdblist_lists
	return mdblist_lists.get_mdbl_top_lists(params)

def build_mdbl_list(params):
	from indexers import mdblist_lists
	return mdblist_lists.build_mdbl_list(params)

def search_mdbl_my_lists(params):
	from indexers import mdblist_lists
	return mdblist_lists.search_mdbl_my_lists(params)

def build_mdbl_watchlist(params):
	from indexers import mdblist_lists
	return mdblist_lists.build_mdbl_watchlist(params)

def build_mdbl_library(params):
	from indexers import mdblist_lists
	return mdblist_lists.build_mdbl_library(params)
