# -*- coding: utf-8 -*-
import json
import time
import calendar
import requests
from datetime import datetime
from threading import Lock
from urllib.parse import urljoin
from caches import simkl_cache
from caches.settings_cache import get_setting, set_setting
from modules import kodi_utils, settings
from modules.utils import copy2clip, make_qrcode

BASE_URL = 'https://api.simkl.com'
OAUTH_PIN_URL = 'https://api.simkl.com/oauth/pin'
SIMKL_APP_NAME = 'plugin.video.redlight'
SIMKL_CLIENT_ID = '6cacc8db22e67b2cd423ef73a9fd3a4f45146ba7fbf30fb2ae28f2fa9d0c2583'
_request_lock = Lock()
_last_request_time = 0.0

def _throttle():
	global _last_request_time
	with _request_lock:
		elapsed = time.time() - _last_request_time
		if elapsed < 1.0: kodi_utils.sleep(int((1.0 - elapsed) * 1000) + 50)
		_last_request_time = time.time()

def _client_id():
	return SIMKL_CLIENT_ID

def _simkl_token():
	from caches.settings_cache import settings_cache
	token = settings_cache.read_db_value('simkl.token')
	if token in (None, '0', '', 'empty_setting'):
		token = get_setting('redlight.simkl.token', '0')
	return token

def _headers():
	token = _simkl_token()
	h = {'Content-Type': 'application/json', 'simkl-api-key': _client_id(), 'User-Agent': '%s/%s' % (SIMKL_APP_NAME, kodi_utils.addon_version())}
	if token not in ('0', '', None, 'empty_setting'): h['Authorization'] = 'Bearer %s' % token
	return h

def _url(path, auth=True):
	cid = _client_id()
	if not cid: return None
	base = path if path.startswith('http') else urljoin(BASE_URL, path.lstrip('/'))
	sep = '&' if '?' in base else '?'
	return '%s%sclient_id=%s&app-name=%s&app-version=%s' % (base, sep, cid, SIMKL_APP_NAME, kodi_utils.addon_version())

def _pin_headers():
	return {'User-Agent': '%s/%s' % (SIMKL_APP_NAME, kodi_utils.addon_version())}

def _pin_url(user_code=None):
	url = '%s/%s' % (OAUTH_PIN_URL, user_code) if user_code else OAUTH_PIN_URL
	sep = '&' if '?' in url else '?'
	return '%s%sclient_id=%s&app-name=%s&app-version=%s' % (url, sep, _client_id(), SIMKL_APP_NAME, kodi_utils.addon_version())

def _simkl_pin_auth_url(pin):
	user_code = pin.get('user_code', '')
	verify = (pin.get('verification_uri') or pin.get('verification_url') or 'https://simkl.com/pin').rstrip('/')
	return '%s/%s' % (verify, user_code)

def call_simkl(path, data=None, method=None, is_delete=False):
	_throttle()
	url = _url(path)
	if not url: return None
	headers = _headers()
	try:
		if is_delete:
			resp = requests.delete(url, headers=headers, timeout=20)
		elif method == 'get' or (data is None and not method):
			resp = requests.get(url, headers=headers, timeout=20)
		else:
			payload = json.dumps(data) if isinstance(data, (dict, list)) else data
			resp = requests.post(url, data=payload, headers=headers, timeout=20)
		if resp.status_code in (200, 201): return resp.json() if resp.text else True
		if resp.status_code == 204: return True
		kodi_utils.logger('Simkl', 'HTTP %s %s' % (resp.status_code, url))
	except Exception as e: kodi_utils.logger('Simkl Error', str(e))
	return None

def simkl_get_pin():
	try: return requests.get(_pin_url(), headers=_pin_headers(), timeout=20).json()
	except: return None

def simkl_poll_pin(pin):
	user_code = pin.get('user_code')
	if not user_code: return None
	expires_in = int(pin.get('expires_in') or 900)
	interval = max(int(pin.get('interval') or 5), 1)
	auth_url = _simkl_pin_auth_url(pin)
	qr_code = make_qrcode(auth_url) or ''
	copy2clip(auth_url)
	content = 'Enter [B]%s[/B] at [B]simkl.com/pin[/B][CR]OR scan the [B]QR Code[/B][CR]Link copied to clipboard[CR][CR]Waiting for authorisation...' % user_code
	progress = kodi_utils.progress_dialog('Simkl Authorise', qr_code)
	progress.update(content, 0)
	expires = time.time() + expires_in
	while time.time() < expires:
		if progress.iscanceled():
			progress.close()
			return None
		_throttle()
		try:
			resp = requests.get(_pin_url(user_code), headers=_pin_headers(), timeout=20).json()
			if resp.get('access_token'):
				progress.close()
				return resp['access_token']
		except: pass
		progress.update(content, int(100 * (1 - (expires - time.time()) / float(expires_in))))
		kodi_utils.sleep(interval * 1000)
	progress.close()
	return None

def simkl_authenticate(dummy=''):
	pin = simkl_get_pin()
	if not pin or not pin.get('user_code'): return kodi_utils.notification('Simkl Authorisation Failed', 3000)
	token = simkl_poll_pin(pin)
	if not token: return kodi_utils.notification('Simkl Authorisation Canceled', 3000)
	set_setting('simkl.token', token)
	from caches.settings_cache import settings_cache
	settings_cache.clear_db_cache()
	info = call_simkl('/users/settings')
	if info and info.get('user'):
		set_setting('simkl.user', str(info['user'].get('name') or info['user'].get('login') or 'Simkl User'))
	else: set_setting('simkl.user', 'Simkl User')
	switched = settings.offer_watched_provider(2, 'Simkl')
	kodi_utils.notification('Simkl Account Authorised', 3000)
	import_ran = switched and settings.trakt_user_active() and settings.offer_trakt_import_to_simkl()
	if not import_ran: simkl_sync_activities(force_update=True)
	try: kodi_utils.container_refresh()
	except: pass
	return True

SIMKL_TRAKT_IMPORT_URL = 'https://simkl.com/apps/import/trakt/'

def simkl_import_trakt(params=None):
	from threading import Thread
	url = SIMKL_TRAKT_IMPORT_URL
	icon = kodi_utils.get_icon('simkl') or kodi_utils.addon_icon()
	try: copy2clip(url)
	except: pass
	try: qr_code = make_qrcode(url) or icon
	except: qr_code = icon
	content = ('Official Simkl Trakt import page:[CR][CR][B]%s[/B][CR][CR]'
		'Scan the QR code with your phone, or paste the copied link into a browser.[CR][CR]'
		'Complete the import on Simkl, then close this dialog to sync.' % url)
	try:
		progress = kodi_utils.progress_dialog('Import Trakt to Simkl', qr_code)
		progress.update(content, 0)
		while not progress.iscanceled(): kodi_utils.sleep(500)
		progress.close()
	except:
		kodi_utils.ok_dialog(heading='Import Trakt to Simkl',
			text='Open this official Simkl page in a browser:[CR][CR][B]%s[/B][CR][CR]The link has been copied where supported.[CR][CR]When finished, use Force Simkl Sync under My Data.' % url)
	Thread(target=simkl_sync_activities, kwargs={'force_update': True}, daemon=True).start()
	return True

def simkl_revoke_authentication(dummy=''):
	set_setting('simkl.user', 'empty_setting')
	set_setting('simkl.token', '0')
	settings.fallback_watched_provider_on_revoke(2)
	simkl_cache.clear_all_simkl_cache_data(silent=True, refresh=False)
	kodi_utils.notification('Simkl Authorisation Reset', 3000)

def _tmdb_id(ids):
	try:
		if ids.get('tmdb'): return str(int(ids['tmdb']))
	except: pass
	return None

def _simkl_media_ids(item, media_kind):
	try:
		if media_kind == 'movies': obj = item.get('movie')
		else: obj = item.get('show') or item.get('anime')
		if not isinstance(obj, dict): obj = item
		ids = obj.get('ids') or item.get('ids') or {}
		if not isinstance(ids, dict): ids = {}
		media_ids = {}
		for key in ('tmdb', 'imdb', 'tvdb'):
			value = ids.get(key)
			if value in (None, '', 'None', 'empty_setting', 0, '0'): continue
			if key in ('tmdb', 'tvdb'):
				try: value = int(value)
				except: pass
			media_ids[key] = value
		return media_ids
	except: return {}

def _simkl_all_items(media_kind, status):
	path = '/sync/all-items/%s/%s?extended=ids_only' % (media_kind, status)
	response = call_simkl(path, method='get')
	if response is None:
		kodi_utils.logger('Simkl', 'list fetch failed: %s' % path)
		return None
	if response is True:
		return []
	if isinstance(response, list):
		return response
	if not isinstance(response, dict):
		kodi_utils.logger('Simkl', 'list fetch unexpected response for %s: %s' % (path, type(response).__name__))
		return None
	items = response.get(media_kind)
	if items is None and media_kind in ('shows', 'anime'):
		items = response.get('shows') or response.get('anime')
	if items is None:
		items = response.get('items') or response.get('list')
	if items is None:
		return []
	return items if isinstance(items, list) else []

def _simkl_release_key(item, media_kind):
	block = _simkl_item_block(item, media_kind)
	if not isinstance(block, dict): block = {}
	for key in ('released', 'released_at', 'first_aired', 'aired'):
		val = block.get(key)
		if val not in (None, '', 'None'): return val
	year = block.get('year')
	if year not in (None, '', 'None', 0):
		try: return '%04d-01-01' % int(year)
		except: pass
	return '9999-12-31' if media_kind == 'movies' else '9999-12-31T00:00:00.000Z'

_SIMKL_STATUS_CACHE_PREFIX = 'simkl_all_items'
_SIMKL_LIST_ACTIVITY_KEYS = ('plantowatch', 'watching', 'completed', 'hold', 'dropped', 'removed_from_list', 'all')
_SIMKL_STATUS_LABELS = {'plantowatch': 'Plan to Watch', 'watching': 'Watching', 'completed': 'Completed', 'hold': 'On Hold', 'dropped': 'Dropped'}
_SIMKL_ID_EMPTY = ('None', None, '', 'empty_setting', 0, '0')

def _simkl_list_cache_key(media_kind, status):
	return '%s_%s_%s' % (_SIMKL_STATUS_CACHE_PREFIX, media_kind, status)

def clear_simkl_list_status_cache(media_kind=None, status=None):
	try:
		from caches.lists_cache import lists_cache
		if media_kind and status:
			lists_cache.delete(_simkl_list_cache_key(media_kind, status))
		elif media_kind:
			if media_kind == 'movies': kinds = ('movies',)
			elif media_kind == 'anime': kinds = ('anime',)
			else: kinds = ('shows', 'anime')
			for kind in kinds:
				for st in ('plantowatch', 'completed', 'watching', 'hold', 'dropped'):
					lists_cache.delete(_simkl_list_cache_key(kind, st))
		else:
			lists_cache.delete_like('%s_%%' % _SIMKL_STATUS_CACHE_PREFIX)
	except: pass

def _simkl_item_block(item, media_kind):
	if media_kind == 'movies': return item.get('movie', {}) or {}
	return item.get('show') or item.get('anime') or {}

def _simkl_fetch_status_live(media_kind, status):
	items = _simkl_all_items(media_kind, status)
	if items is None: return None
	result = []
	skipped = 0
	for count, item in enumerate(items, 1):
		if not isinstance(item, dict): continue
		media_ids = _simkl_media_ids(item, media_kind)
		if not media_ids:
			skipped += 1
			continue
		block = _simkl_item_block(item, media_kind)
		result.append({'order': count, 'media_ids': media_ids, 'type': 'movie' if media_kind == 'movies' else 'show',
			'title': block.get('title', ''), 'collected_at': item.get('added_to_watchlist_at') or '',
			'released': _simkl_release_key(item, media_kind)})
	if skipped and not result:
		kodi_utils.logger('Simkl', 'list %s/%s: %s items had no tmdb/imdb/tvdb ids' % (media_kind, status, skipped))
	try: return settings.sort_simkl_personal_list(result)
	except Exception as e:
		kodi_utils.logger('Simkl', 'sort %s/%s failed: %s' % (media_kind, status, e))
		return result

def _simkl_fetch_status(media_kind, status):
	if not settings.simkl_user_active(): return []
	result = _simkl_fetch_status_live(media_kind, status)
	return [] if result is None else result

def _simkl_fetch_tv_status(status):
	shows = _simkl_fetch_status('shows', status)
	anime = _simkl_fetch_status('anime', status)
	if not shows and not anime: return []
	combined = shows + anime
	try: return settings.sort_simkl_personal_list(combined)
	except: return combined

def simkl_plantowatch(media_kind, page_no=None):
	if media_kind == 'shows': return _simkl_fetch_tv_status('plantowatch')
	return _simkl_fetch_status(media_kind, 'plantowatch')

def simkl_completed(media_kind, page_no=None):
	if media_kind == 'shows': return _simkl_fetch_tv_status('completed')
	return _simkl_fetch_status(media_kind, 'completed')

def simkl_watching(media_kind, page_no=None):
	if media_kind == 'shows': return _simkl_fetch_tv_status('watching')
	return _simkl_fetch_status(media_kind, 'watching')

def simkl_hold(media_kind, page_no=None):
	if media_kind == 'shows': return _simkl_fetch_tv_status('hold')
	return _simkl_fetch_status(media_kind, 'hold')

def simkl_dropped(media_kind, page_no=None):
	if media_kind == 'shows': return _simkl_fetch_tv_status('dropped')
	return _simkl_fetch_status(media_kind, 'dropped')

_SIMKL_DROPPED_CACHE_KEY = 'simkl_hidden_items_dropped'

def clear_simkl_dropped_cache():
	simkl_cache.simkl_cache.delete(_SIMKL_DROPPED_CACHE_KEY)

def simkl_get_dropped_items():
	cached = simkl_cache.simkl_cache.get(_SIMKL_DROPPED_CACHE_KEY)
	if cached is not None: return cached
	items = []
	for item in simkl_dropped('shows'):
		try:
			tmdb_id = item.get('media_ids', {}).get('tmdb')
			if tmdb_id: items.append(int(tmdb_id))
		except: pass
	simkl_cache.simkl_cache.set(_SIMKL_DROPPED_CACHE_KEY, items)
	return items

def _simkl_list_ids(tmdb_id, imdb_id=None, tvdb_id=None):
	ids = {'tmdb': int(tmdb_id)}
	if imdb_id and imdb_id not in ('None', None, ''): ids['imdb'] = imdb_id
	if tvdb_id and str(tvdb_id) not in ('None', '0', ''):
		try: ids['tvdb'] = int(tvdb_id)
		except: ids['tvdb'] = tvdb_id
	return ids

def _simkl_list_add_ok(result, media_type):
	if not isinstance(result, dict): return False
	key = 'movies' if media_type == 'movie' else 'shows'
	if (result.get('added') or {}).get(key): return True
	not_found = (result.get('not_found') or {}).get(key)
	if not_found: kodi_utils.logger('Simkl', 'add-to-list not_found: %s' % not_found)
	return False

def _simkl_list_remove_ok(result, media_type):
	if result is True: return True
	if not isinstance(result, dict): return False
	key = 'movies' if media_type == 'movie' else 'shows'
	deleted = result.get('deleted') or {}
	if isinstance(deleted, dict) and deleted.get(key): return True
	if deleted is True: return True
	return False

def _simkl_refresh_after_list_change(listname=None, media_type='movie'):
	clear_simkl_dropped_cache()
	media_kind = 'movies' if media_type == 'movie' else 'shows'
	clear_simkl_list_status_cache(media_kind)
	if settings.watched_indicators() == 2:
		simkl_sync_activities()
	if kodi_utils.path_check('simkl') or kodi_utils.external():
		kodi_utils.kodi_refresh()

def _simkl_id_match(item_ids, imdb_id=None, tvdb_id=None, tmdb_id=None):
	if not isinstance(item_ids, dict): return False
	if imdb_id and imdb_id not in _SIMKL_ID_EMPTY and str(item_ids.get('imdb')) == str(imdb_id): return True
	if tvdb_id and tvdb_id not in _SIMKL_ID_EMPTY and str(item_ids.get('tvdb')) == str(tvdb_id): return True
	if tmdb_id and tmdb_id not in _SIMKL_ID_EMPTY and str(item_ids.get('tmdb')) == str(tmdb_id): return True
	return False

def _simkl_item_in_status(media_type, status, imdb_id=None, tvdb_id=None, tmdb_id=None):
	try:
		if media_type == 'movie':
			items = _simkl_fetch_status('movies', status)
		else:
			items = _simkl_fetch_tv_status(status)
		for item in items:
			if _simkl_id_match(item.get('media_ids'), imdb_id, tvdb_id, tmdb_id): return True
	except: pass
	return False

def simkl_search_my_lists(query):
	query = (query or '').strip().lower()
	if not query or not settings.simkl_user_active(): return []
	results = []
	statuses = ('plantowatch', 'completed', 'watching', 'hold', 'dropped')
	for status in statuses:
		for item in _simkl_fetch_status('movies', status):
			if status in ('watching', 'hold'): continue
			title = (item.get('title') or '').strip()
			if query not in title.lower(): continue
			entry = dict(item)
			entry['status'] = status
			entry['status_label'] = _SIMKL_STATUS_LABELS.get(status, status)
			entry['media_kind'] = 'movies'
			results.append(entry)
	for status in statuses:
		for item in _simkl_fetch_tv_status(status):
			title = (item.get('title') or '').strip()
			if query not in title.lower(): continue
			entry = dict(item)
			entry['status'] = status
			entry['status_label'] = _SIMKL_STATUS_LABELS.get(status, status)
			entry['media_kind'] = 'shows'
			results.append(entry)
	return results

def simkl_manager_choice(params):
	if not settings.simkl_user_active(): return kodi_utils.notification('No Active Simkl Account', 3500)
	media_type = params.get('media_type') or params.get('content') or 'movie'
	list_media = 'movie' if media_type == 'movie' else 'tvshow'
	icon = params.get('icon') or kodi_utils.get_icon('simkl')
	imdb_id, tvdb_id, tmdb_id = params.get('imdb_id'), params.get('tvdb_id'), params.get('tmdb_id')
	status_map = [
		('plantowatch', 'Add to [B]Plan to Watch[/B]', 'Remove from [B]Plan to Watch[/B]'),
		('completed', 'Add to [B]Completed[/B]', 'Remove from [B]Completed[/B]'),
		('dropped', 'Add to [B]Dropped[/B]', 'Remove from [B]Dropped[/B]')
	]
	if media_type != 'movie':
		status_map.insert(1, ('watching', 'Add to [B]Watching[/B]', 'Remove from [B]Watching[/B]'))
		status_map.insert(3, ('hold', 'Add to [B]On Hold[/B]', 'Remove from [B]On Hold[/B]'))
	choices = []
	for status, add_label, remove_label in status_map:
		if _simkl_item_in_status(list_media, status, imdb_id, tvdb_id, tmdb_id):
			choices.append((remove_label, 'remove_%s' % status))
		else:
			choices.append((add_label, status))
	choices.extend([
		('Mark as [B]Watched[/B]', 'mark_watched'),
		('Mark as [B]Unwatched[/B]', 'mark_unwatched'),
		('Reset [B]Scrobble[/B]', 'reset_scrobble'),
		('Open [B]Plan to Watch[/B]', 'open_plantowatch'),
		('Open [B]Completed[/B]', 'open_completed'),
	])
	if media_type != 'movie':
		choices.append(('Open [B]Watching[/B]', 'open_watching'))
		choices.append(('Open [B]On Hold[/B]', 'open_hold'))
	choices.extend([
		('Open [B]Dropped[/B]', 'open_dropped'),
		('Open [B]Simkl Lists[/B]', 'open_lists'),
		('Refresh Widgets', 'refresh'),
	])
	list_items = [{'line1': item[0], 'icon': icon} for item in choices]
	choice = kodi_utils.select_dialog([i[1] for i in choices], **{'items': json.dumps(list_items), 'heading': 'Simkl Lists Manager'})
	if choice == None: return
	if choice == 'refresh':
		kodi_utils.kodi_refresh()
		return kodi_utils.notification('Widgets Refreshed', 2500)
	open_modes = {
		'open_plantowatch': 'navigator.simkl_watchlists',
		'open_completed': 'navigator.simkl_completed',
		'open_watching': 'navigator.simkl_watching',
		'open_hold': 'navigator.simkl_hold',
		'open_dropped': 'navigator.simkl_dropped',
		'open_lists': 'navigator.simkl_lists',
	}
	if choice in open_modes:
		return kodi_utils.container_update({'mode': open_modes[choice]})
	if choice == 'mark_watched':
		from indexers.dialogs import _trakt_manager_mark
		return _trakt_manager_mark(params, 'mark_as_watched')
	if choice == 'mark_unwatched':
		from indexers.dialogs import _trakt_manager_mark
		return _trakt_manager_mark(params, 'mark_as_unwatched')
	if choice == 'reset_scrobble':
		return simkl_reset_scrobble(params)
	if choice in ('plantowatch', 'watching', 'completed', 'hold', 'dropped'):
		return simkl_add_to_list(choice, tmdb_id, list_media, imdb_id, tvdb_id)
	if choice.startswith('remove_'):
		return simkl_remove_from_list(choice.replace('remove_', ''), tmdb_id, list_media, imdb_id, tvdb_id)

def simkl_hide_unhide_progress_items(params):
	action, media_id = params['action'], params.get('media_id')
	imdb_id, tvdb_id = params.get('imdb_id'), params.get('tvdb_id', 'None')
	if action == 'drop': return simkl_add_to_list('dropped', media_id, 'tvshow', imdb_id, tvdb_id)
	return simkl_remove_from_list('dropped', media_id, 'tvshow', imdb_id, tvdb_id)

def _simkl_history_ok(result, action, media_type):
	if not isinstance(result, dict): return False
	result_key = 'added' if action == 'mark_as_watched' else 'deleted'
	item_key = 'movies' if media_type == 'movie' else 'shows'
	bucket = result.get(result_key) or {}
	if bucket.get('episodes', 0) > 0: return True
	if bucket.get(item_key, 0) > 0: return True
	if isinstance(bucket.get(item_key), list) and bucket[item_key]: return True
	if action == 'mark_as_unwatched':
		not_found = result.get('not_found') or {}
		if not not_found.get(item_key) and not not_found.get('episodes'): return True
	return False

def simkl_watched_status_mark(action, media_type, tmdb_id, tvdb_id=0, season=None, episode=None):
	if action == 'mark_as_watched':
		url, key = '/sync/history', 'added'
		watched_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
	else:
		url, key = '/sync/history/remove', 'deleted'
		watched_at = None
	if media_type == 'movie':
		item = {'ids': {'tmdb': int(tmdb_id)}}
		if watched_at: item['watched_at'] = watched_at
		data = {'movies': [item]}
		item_type = 'movie'
	elif media_type in ('episode',):
		ep = {'number': int(episode)}
		if watched_at: ep['watched_at'] = watched_at
		data = {'shows': [{'ids': _simkl_list_ids(tmdb_id, tvdb_id=tvdb_id), 'seasons': [{'number': int(season), 'episodes': [ep]}]}]}
		item_type = 'episode'
	elif media_type == 'season':
		data = {'shows': [{'ids': _simkl_list_ids(tmdb_id, tvdb_id=tvdb_id), 'seasons': [{'number': int(season)}]}]}
		item_type = 'season'
	else:
		data = {'shows': [{'ids': _simkl_list_ids(tmdb_id, tvdb_id=tvdb_id)}]}
		item_type = 'tvshow'
	result = call_simkl(url, data=data)
	if _simkl_history_ok(result, action, 'movie' if media_type == 'movie' else 'shows'):
		if action == 'mark_as_unwatched': simkl_sync_activities()
		return True
	if action == 'mark_as_unwatched' and item_type == 'tvshow' and tvdb_id and int(tvdb_id) > 0:
		fallback = call_simkl(url, data={'shows': [{'ids': {'tvdb': int(tvdb_id)}}]})
		if _simkl_history_ok(fallback, action, 'shows'):
			simkl_sync_activities()
			return True
	kodi_utils.logger('Simkl', 'history %s failed for %s tmdb=%s tvdb=%s: %s' % (action, item_type, tmdb_id, tvdb_id, result))
	return False

def _scrobble_payload(media_type, tmdb_id, percent, season=None, episode=None):
	data = {'progress': float(percent)}
	if media_type == 'movie':
		data['movie'] = {'ids': {'tmdb': int(tmdb_id)}}
	else:
		data['show'] = {'ids': {'tmdb': int(tmdb_id)}}
		data['episode'] = {'season': int(season), 'number': int(episode)}
	return data

def simkl_official_status(media_type):
	if kodi_utils.service_scrobbler_defer('script.simkl',
		auth_keys=('access_token', 'token', 'authorization', 'Authorization', 'simkl_token'),
		scrobble_enable_keys=('auto_scrobble', 'autoscrobble', 'scrobble_enabled', 'auto_scrobble_enabled')): return False
	return True

def simkl_scrobble(action, media_type, tmdb_id, percent=0, season=None, episode=None):
	if not settings.simkl_user_active(): return
	path = {'start': '/scrobble/start', 'pause': '/scrobble/pause', 'stop': '/scrobble/stop'}.get(action)
	if not path: return
	call_simkl(path, data=_scrobble_payload(media_type, tmdb_id, percent, season, episode))

def simkl_progress(action, media_type, tmdb_id, percent, season=None, episode=None, resume_id=None, refresh_simkl=False):
	if action == 'clear_progress' and resume_id:
		_throttle()
		url = _url('/sync/playback/%s' % resume_id)
		if not url: return
		try: requests.delete(url, headers=_headers(), timeout=20)
		except: pass
	else:
		simkl_scrobble('pause', media_type, tmdb_id, percent, season, episode)
	if refresh_simkl: simkl_sync_activities(force_update=True)

def simkl_reset_scrobble(params):
	from modules.watched_status import erase_bookmark
	media_type, tmdb_id = params.get('media_type'), params.get('tmdb_id')
	season, episode = params.get('season', ''), params.get('episode', '')
	watched_db = __import__('modules.watched_status', fromlist=['get_database']).get_database(2)
	try:
		if media_type == 'movie':
			simkl_scrobble('stop', 'movie', tmdb_id, 0)
			resume_id = watched_db.execute('SELECT resume_id FROM progress WHERE db_type=? AND media_id=?', ('movie', str(tmdb_id))).fetchone()[0]
			simkl_progress('clear_progress', 'movie', tmdb_id, 0, resume_id=resume_id)
			erase_bookmark('movie', tmdb_id, '', '', 'true', 2)
		elif media_type == 'episode' and season and episode:
			simkl_scrobble('stop', 'episode', tmdb_id, 0, season, episode)
			row = watched_db.execute('SELECT resume_id FROM progress WHERE db_type=? AND media_id=? AND season=? AND episode=?',
				('episode', str(tmdb_id), int(season), int(episode))).fetchone()
			if row:
				simkl_progress('clear_progress', 'episode', tmdb_id, 0, season, episode, resume_id=row[0])
			erase_bookmark('episode', tmdb_id, season, episode, 'true', 2)
		else: return kodi_utils.notification('Reset Scrobble is only available for movies and episodes', 3500)
		kodi_utils.notification('Success', 3000)
	except: kodi_utils.notification('Error', 3000)

def simkl_add_to_list(listname, tmdb_id, media_type, imdb_id=None, tvdb_id=None):
	if media_type == 'movie':
		post = {'movies': [{'to': listname, 'ids': {'tmdb': int(tmdb_id)}}]}
	else:
		post = {'shows': [{'to': listname, 'ids': _simkl_list_ids(tmdb_id, imdb_id, tvdb_id)}]}
	result = call_simkl('/sync/add-to-list', data=post)
	success = _simkl_list_add_ok(result, media_type)
	if success:
		_simkl_refresh_after_list_change(listname, media_type)
		kodi_utils.notification('Success', 3000)
	else: kodi_utils.notification('Error', 3000)
	return success

def simkl_remove_from_list(listname, tmdb_id, media_type, imdb_id=None, tvdb_id=None):
	if media_type == 'movie':
		post = {'movies': [{'ids': {'tmdb': int(tmdb_id)}}]}
	else:
		post = {'shows': [{'ids': _simkl_list_ids(tmdb_id, imdb_id, tvdb_id)}]}
	result = call_simkl('/sync/history/remove', data=post)
	success = _simkl_list_remove_ok(result, media_type)
	if success:
		_simkl_refresh_after_list_change(listname, media_type)
		kodi_utils.notification('Success', 3000)
	else: kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000)
	return success

_SIMKL_SHOW_WATCHED_ACTIVITY_KEYS = ('watching', 'plantowatch', 'completed', 'hold', 'dropped', 'removed_from_list', 'all')
_SIMKL_MOVIE_WATCHED_ACTIVITY_KEYS = ('plantowatch', 'completed', 'dropped', 'removed_from_list', 'all')
_SIMKL_TV_SYNC_QUERY = 'extended=full&episode_watched_at=yes&include_all_episodes=yes'

def simkl_indicators_movies():
	insert_list = []
	insert_append = insert_list.append
	data = call_simkl('/sync/all-items/movies/completed?extended=full', method='get') or {}
	for item in data.get('movies', data if isinstance(data, list) else []):
		try:
			movie = item.get('movie', item)
			tmdb_id = _tmdb_id(movie.get('ids', {}))
			if not tmdb_id: continue
			watched_at = item.get('last_watched_at') or item.get('watched_at') or datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
			insert_append(('movie', tmdb_id, '', '', watched_at, movie.get('title', '')))
		except: pass
	simkl_cache.simkl_watched_cache.set_bulk_movie_watched(insert_list)

def simkl_indicators_tv():
	insert_list = []
	insert_append = insert_list.append
	data = call_simkl('/sync/all-items/shows?%s' % _SIMKL_TV_SYNC_QUERY, method='get') or {}
	for item in data.get('shows', data if isinstance(data, list) else []):
		try:
			show = item.get('show', item)
			tmdb_id = _tmdb_id(show.get('ids', {}))
			if not tmdb_id: continue
			title = show.get('title', '')
			for season in item.get('seasons', []):
				try: snum = int(season.get('number', season.get('season')))
				except: continue
				for ep in season.get('episodes', []):
					watched_at = ep.get('watched_at') or ep.get('last_watched_at')
					if not watched_at: continue
					try: epnum = int(ep.get('number', ep.get('episode')))
					except: continue
					insert_append(('episode', tmdb_id, snum, epnum, watched_at, title))
		except: pass
	simkl_cache.simkl_watched_cache.set_bulk_tvshow_watched(insert_list)

def simkl_sync_playback():
	items = call_simkl('/sync/playback', method='get') or []
	movie_ins, ep_ins = [], []
	for item in items:
		try:
			if item.get('type') == 'movie':
				tmdb_id = _tmdb_id(item.get('movie', {}).get('ids', {}))
				if not tmdb_id: continue
				movie_ins.append(('movie', tmdb_id, '', '', str(round(item['progress'], 1)), 0, item.get('paused_at', ''), item['id'], item['movie'].get('title', '')))
			elif item.get('type') == 'episode':
				show = item.get('show', {})
				tmdb_id = _tmdb_id(show.get('ids', {}))
				if not tmdb_id: continue
				ep = item.get('episode', {})
				ep_ins.append(('episode', tmdb_id, ep.get('season'), ep.get('number'), str(round(item['progress'], 1)), 0,
					item.get('paused_at', ''), item['id'], show.get('title', '')))
		except: pass
	simkl_cache.simkl_watched_cache.set_bulk_movie_progress(movie_ins)
	simkl_cache.simkl_watched_cache.set_bulk_tvshow_progress(ep_ins)

def _activity_ts(ts_str):
	if not ts_str: return 0
	try: return int(calendar.timegm(time.strptime(ts_str.rstrip('Z').split('.')[0], '%Y-%m-%dT%H:%M:%S')))
	except: return 0

def _activity_block_changed(latest_blk, cached_blk, keys):
	for key in keys:
		if _activity_ts(latest_blk.get(key, '')) > _activity_ts(cached_blk.get(key, '')): return True
	return False

def simkl_sync_activities(params=None, force_update=False):
	if isinstance(params, dict): force_update = params.get('force_update', 'false') in ('true', 'True', True) or force_update
	if not settings.simkl_user_active(): return 'no account'
	if force_update:
		simkl_cache.clear_all_simkl_cache_data(silent=True, refresh=False)
		clear_simkl_list_status_cache()
	try: latest = call_simkl('/sync/activities', method='get')
	except: return 'failed'
	if not latest: return 'failed'
	cached = simkl_cache.reset_activity(latest)
	if not force_update and _activity_ts(latest.get('all', '')) <= _activity_ts(cached.get('all', '')): return 'not needed'
	movies, shows = latest.get('movies', {}), latest.get('tv_shows', {})
	anime = latest.get('anime', {})
	cached_movies, cached_shows = cached.get('movies', {}), cached.get('tv_shows', {})
	cached_anime = cached.get('anime', {})
	watched_keys_movies = _SIMKL_MOVIE_WATCHED_ACTIVITY_KEYS
	watched_keys_shows = _SIMKL_SHOW_WATCHED_ACTIVITY_KEYS
	playback_keys = ('playback', 'all')
	if force_update or _activity_block_changed(movies, cached_movies, _SIMKL_LIST_ACTIVITY_KEYS):
		clear_simkl_list_status_cache('movies')
	if force_update or _activity_block_changed(shows, cached_shows, _SIMKL_LIST_ACTIVITY_KEYS):
		clear_simkl_list_status_cache('shows')
	if force_update or _activity_block_changed(anime, cached_anime, _SIMKL_LIST_ACTIVITY_KEYS):
		clear_simkl_list_status_cache('anime')
	if force_update or _activity_block_changed(movies, cached_movies, watched_keys_movies):
		simkl_indicators_movies()
	if force_update or _activity_block_changed(shows, cached_shows, watched_keys_shows):
		simkl_indicators_tv()
		clear_simkl_dropped_cache()
	if force_update or _activity_block_changed(movies, cached_movies, playback_keys) or _activity_block_changed(shows, cached_shows, playback_keys):
		simkl_sync_playback()
	return 'success'

def simkl_force_sync(params=None):
	if not settings.simkl_user_active(): return kodi_utils.notification('Simkl account not authorised', 3000)
	progress = kodi_utils.progress_dialog('Simkl Sync')
	status = 'failed'
	try:
		progress.update('Syncing with Simkl...', 0)
		status = simkl_sync_activities(force_update=True)
	except Exception as e:
		kodi_utils.logger('Simkl', 'Force sync failed: %s' % e)
	finally:
		kodi_utils.close_progress_dialog(progress)
	if status == 'failed': kodi_utils.notification('Simkl Sync Failed', 3000)
	else:
		kodi_utils.notification('Simkl Sync Complete', 3000)
		kodi_utils.kodi_refresh()
	return status

SIMKL_TRENDING_BASE = 'https://data.simkl.in/discover/trending'
_SIMKL_TRENDING_TRAKT_KEYS = {'movies': 'movie', 'tv': 'show', 'anime': 'show'}

def _simkl_trending_url(media_kind):
	return '%s/%s/today_100.json' % (SIMKL_TRENDING_BASE, media_kind)

def _simkl_trending_query_url(url):
	sep = '&' if '?' in url else '?'
	return '%s%sclient_id=%s&app-name=%s&app-version=%s' % (url, sep, _client_id(), SIMKL_APP_NAME, kodi_utils.addon_version())

def _simkl_trending_ids(item):
	ids = item.get('ids') or {}
	result = {}
	for key in ('tmdb', 'imdb', 'tvdb', 'slug'):
		value = ids.get(key)
		if value in (None, ''): continue
		if key == 'tmdb':
			try: result[key] = int(value)
			except: result[key] = value
		else: result[key] = value
	return result

def _simkl_trending_to_trakt(item, media_kind):
	ids = _simkl_trending_ids(item)
	if not ids.get('tmdb'): return None
	return {_SIMKL_TRENDING_TRAKT_KEYS[media_kind]: {'ids': ids}}

def _simkl_fetch_trending_today(media_kind):
	from caches.lists_cache import lists_cache_object
	def _fetch(dummy):
		_throttle()
		try:
			resp = requests.get(_simkl_trending_query_url(_simkl_trending_url(media_kind)), headers=_pin_headers(), timeout=20)
			if resp.status_code != 200:
				kodi_utils.logger('Simkl Trending', 'HTTP %s for %s' % (resp.status_code, media_kind))
				return None
			data = resp.json()
			if isinstance(data, list): items = data
			else: items = data.get(media_kind) or data.get('items') or []
			results = []
			for item in items:
				converted = _simkl_trending_to_trakt(item, media_kind)
				if converted: results.append(converted)
			if not results:
				kodi_utils.logger('Simkl Trending', 'No usable items for %s' % media_kind)
				return None
			return results
		except Exception as e:
			kodi_utils.logger('Simkl Trending Error', str(e))
			return None
	result = lists_cache_object(_fetch, 'simkl_trending_%s_today_100' % media_kind, 'dummy_arg', expiration=1)
	return result or []

def clear_simkl_trending_cache(media_kind=None):
	try:
		from caches.lists_cache import lists_cache
		dbcon = lists_cache.manual_connect('lists_db')
		if media_kind: dbcon.execute('DELETE FROM lists WHERE id = ?', ('simkl_trending_%s_today_100' % media_kind,))
		else: dbcon.execute('DELETE FROM lists WHERE id LIKE ?', ('simkl_trending_%',))
		dbcon.execute('VACUUM')
	except: pass

def simkl_trending_today_count(media_kind):
	return len(_simkl_fetch_trending_today(media_kind))

def simkl_trending_today_page(media_kind, page_no, page_size=20):
	full_list = _simkl_fetch_trending_today(media_kind)
	start = (int(page_no) - 1) * page_size
	return full_list[start:start + page_size]
