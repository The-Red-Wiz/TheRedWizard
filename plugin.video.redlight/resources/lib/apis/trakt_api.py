# -*- coding: utf-8 -*-
import json
import time
import requests
from urllib.parse import unquote, quote_plus
from caches import trakt_cache
from caches.settings_cache import get_setting, set_setting, settings_cache

def _trakt_setting(setting_id, fallback=''):
	val = settings_cache.read_db_value(setting_id)
	if val in (None, '', '0', 'empty_setting'): return fallback
	return val
from caches.main_cache import cache_object
from caches.lists_cache import lists_cache_object
from modules import kodi_utils, settings
from modules.metadata import movie_meta_external_id, tvshow_meta_external_id
from modules.utils import sort_list, sort_for_article, get_datetime, timedelta, replace_html_codes, copy2clip, make_qrcode, make_tinyurl, \
							TaskPool, jsondate_to_datetime as js2date
# logger = kodi_utils.logger

# Trakt API max per-page limit (reducing to 250; see https://github.com/trakt/trakt-api/discussions/681 / #775)
TRAKT_PAGE_LIMIT = 250
# extended=progress on watched/shows is capped at 100 per page (discussion #775)
TRAKT_WATCHED_PROGRESS_PAGE_LIMIT = 100

def _trakt_fetch_page_limit(base_params):
	ext = str((base_params or {}).get('extended') or '').lower()
	if 'progress' in ext: return TRAKT_WATCHED_PROGRESS_PAGE_LIMIT
	return TRAKT_PAGE_LIMIT

def no_client_key():
	kodi_utils.notification('Please set a valid Trakt Client ID Key')
	return None

def no_secret_key():
	kodi_utils.notification('Please set a valid Trakt Client Secret Key')
	return None

def get_trakt(params):
	if params.get('fetch_all'):
		return get_trakt_all(params)
	result = call_trakt(params['path'] % params.get('path_insert', ''), params=params.get('params', {}), data=params.get('data'), is_delete=params.get('is_delete', False),
						with_auth=params.get('with_auth', False), method=params.get('method'), pagination=params.get('pagination', True), page_no=params.get('page_no', 1))
	return result[0] if params.get('pagination', True) else result

def get_trakt_all(params):
	path = params['path'] % params.get('path_insert', '')
	base_params = dict(params.get('params') or {})
	method = params.get('method')
	page_limit = _trakt_fetch_page_limit(base_params)
	sort_by, sort_how = 'rank', 'asc'
	all_items = []
	page_no, page_count = 1, 1
	while page_no <= page_count:
		query = dict(base_params)
		query['limit'] = page_limit
		page_method = method if page_no == 1 else (None if method == 'sort_by_headers' else method)
		result, page_count = call_trakt(path, params=query, data=params.get('data'), is_delete=params.get('is_delete', False),
						with_auth=params.get('with_auth', False), method=page_method, pagination=True, page_no=page_no)
		try: page_count = max(int(page_count), page_no)
		except: page_count = page_no
		if result is None:
			if page_no == 1: return None
			break
		if isinstance(result, dict) and 'data' in result:
			sort_by, sort_how = result.get('sort_by', sort_by), result.get('sort_how', sort_how)
			chunk = result.get('data') or []
		elif isinstance(result, list): chunk = result
		else: break
		if not chunk: break
		all_items.extend(chunk)
		page_no += 1
		if page_no > 1: kodi_utils.sleep(100)
	if method == 'sort_by_headers':
		return {'sort_by': sort_by, 'sort_how': sort_how, 'data': all_items}
	return all_items

def call_trakt(path, params={}, data=None, is_delete=False, with_auth=True, method=None, pagination=False, page_no=1):
	def send_query():
		resp = None
		if with_auth:
			while kodi_utils.get_property('redlight.trakt_refreshing_token') == 'true':
				kodi_utils.logger('refreshing trakt token', '')
				kodi_utils.sleep(250)
			try: expires_at = float(_trakt_setting('trakt.expires', '0'))
			except: expires_at = 0.0
			if time.time() > expires_at: trakt_refresh_token()
			token = _trakt_setting('trakt.token')
			if token: headers['Authorization'] = 'Bearer ' + token
		try:
			if method:
				if method == 'post': resp = requests.post(API_ENDPOINT % path, headers=headers, timeout=10)
				elif method == 'delete': resp = requests.delete(API_ENDPOINT % path, headers=headers, timeout=10)
				else: resp = requests.get(API_ENDPOINT % path, params=params, headers=headers, timeout=10)
			elif data is not None:
				assert not params
				resp = requests.post(API_ENDPOINT % path, json=data, headers=headers, timeout=10)
			elif is_delete: resp = requests.delete(API_ENDPOINT % path, headers=headers, timeout=10)
			else: resp = requests.get(API_ENDPOINT % path, params=params, headers=headers, timeout=10)
			resp.raise_for_status()
		except Exception as e: kodi_utils.logger('Trakt Error', str(e))
		return resp
	API_ENDPOINT = 'https://api.trakt.tv/%s'
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, 'empty_setting', ''): return no_client_key()
	headers = {'Content-Type': 'application/json', 'trakt-api-version': '2', 'trakt-api-key': CLIENT_ID}
	if pagination: params['page'] = page_no
	response = send_query()
	try: status_code = response.status_code
	except: return None
	headers = response.headers
	if status_code == 401:
		if with_auth:
			if settings.trakt_user_active(): trakt_refresh_token()
			else: return None
		else: return None
	elif status_code == 429:
		if 'Retry-After' in headers:
			kodi_utils.sleep(1000 * headers['Retry-After'])
			response = send_query()
	response.encoding = 'utf-8'
	result = response.json() if 'json' in headers.get('Content-Type', '') else response.text
	if method == 'sort_by_headers':
		sort_by, sort_how = headers.get('X-Sort-By', 'title'), headers.get('X-Sort-How', 'asc')
		result = {'sort_by': sort_by, 'sort_how': sort_how, 'data': result}
	if pagination:
		try: page_count = int(headers.get('X-Pagination-Page-Count', page_no))
		except: page_count = page_no
		return (result, page_count)
	else: return result

def trakt_get_device_code():
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, 'empty_setting', ''): return no_client_key()
	data = {'client_id': CLIENT_ID}
	result = call_trakt('oauth/device/code', data=data, with_auth=False)
	if result: return result
	_, message = trakt_test_credentials()
	kodi_utils.ok_dialog(heading='Trakt Authorise', text=message)
	return None

def trakt_test_credentials():
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, 'empty_setting', ''):
		return False, 'Trakt Client ID Key is not set.'
	CLIENT_SECRET = settings.trakt_secret()
	if CLIENT_SECRET in (None, 'empty_setting', ''):
		return False, 'Trakt Client Secret Key is not set.'
	try:
		headers = {'Content-Type': 'application/json', 'trakt-api-version': '2', 'trakt-api-key': CLIENT_ID}
		response = requests.post('https://api.trakt.tv/oauth/device/code', json={'client_id': CLIENT_ID}, headers=headers, timeout=15)
		if response.status_code == 200:
			return True, 'Trakt client keys are valid.'
		try:
			payload = response.json()
			detail = payload.get('error_description') or payload.get('error') or ''
		except: detail = ''
		if not detail: detail = (response.text or '').strip() or 'No details returned.'
		return False, 'Trakt client keys failed.[CR]Trakt rejected the client ID (HTTP %s).[CR]%s' % (response.status_code, detail)
	except Exception as e:
		return False, 'Trakt client keys failed.[CR]Could not reach Trakt: %s' % str(e)

def trakt_get_device_token(device_codes):
	API_ENDPOINT = 'https://api.trakt.tv/%s'
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, 'empty_setting', ''): return no_client_key()
	CLIENT_SECRET = settings.trakt_secret()
	if CLIENT_SECRET in (None, 'empty_setting', ''): return no_secret_key()
	result = None
	canceled = False
	try:
		headers = {'Content-Type': 'application/json', 'trakt-api-version': '2', 'trakt-api-key': CLIENT_ID}
		data = {'code': device_codes['device_code'], 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
		start = time.time()
		expires_in = device_codes['expires_in']
		sleep_interval = device_codes['interval']
		user_code = str(device_codes['user_code'])
		auth_url = 'https://trakt.tv/activate?code=%s' % str(user_code)
		qr_code = make_qrcode(auth_url) or ''
		short_url = make_tinyurl(auth_url)
		copy2clip(auth_url)
		if short_url: p_dialog_insert = '[CR]OR....[CR]visit [B]%s[/B]' % short_url
		else: p_dialog_insert = ''
		content = 'Enter [B]%s[/B] at [B]%s[/B][CR]OR....[CR]Scan the [B]QR Code[/B]%s' % (user_code, device_codes['verification_url'], p_dialog_insert)
		progressDialog = kodi_utils.progress_dialog('Trakt Authorise', qr_code)
		progressDialog.update(content, 0)
		try:
			time_passed = 0
			while not progressDialog.iscanceled() and time_passed < expires_in:
				kodi_utils.sleep(max(sleep_interval, 1)*1000)
				response = requests.post(API_ENDPOINT % 'oauth/device/token', data=json.dumps(data), headers=headers, timeout=20)
				status_code = response.status_code
				if status_code == 200:
					result = response.json()
					break
				elif status_code == 400:
					time_passed = time.time() - start
					progress = int(100 * time_passed/expires_in)
					progressDialog.update(content, progress)
				else: break
			canceled = progressDialog.iscanceled()
		except: pass
		try: progressDialog.close()
		except: pass
	except: pass
	if canceled:
		return 'canceled'
	return result

def trakt_refresh_token():
	try:
		CLIENT_ID = settings.trakt_client()
		if CLIENT_ID in (None, 'empty_setting', ''): return no_client_key()
		CLIENT_SECRET = settings.trakt_secret()
		if CLIENT_SECRET in (None, 'empty_setting', ''): return no_secret_key()
		kodi_utils.set_property('redlight.trakt_refreshing_token', 'true')
		data = {        
			'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
			'grant_type': 'refresh_token', 'refresh_token': _trakt_setting('trakt.refresh')}
		response = call_trakt("oauth/token", data=data, with_auth=False)
		if response:
			set_setting('trakt.token', response['access_token'])
			set_setting('trakt.refresh', response['refresh_token'])
			set_setting('trakt.expires', str(time.time() + response['expires_in']))
	except: pass
	kodi_utils.clear_property('redlight.trakt_refreshing_token')

def trakt_authenticate(dummy=''):
	code = trakt_get_device_code()
	if not code:
		return False
	token = trakt_get_device_token(code)
	if token == 'canceled':
		return False
	if token:
		set_setting('trakt.token', token['access_token'])
		set_setting('trakt.refresh', token['refresh_token'])
		set_setting('trakt.expires', str(time.time() + token['expires_in']))
		try:
			user = call_trakt('/users/me')
			set_setting('trakt.user', str(user['username']))
		except: set_setting('trakt.user', 'Trakt User')
		try:
			from caches.settings_cache import sync_kodi_profile_context
			sync_kodi_profile_context()
		except: pass
		settings.offer_watched_provider(1, 'Trakt')
		kodi_utils.sleep(1000)
		kodi_utils.notification('Trakt Account Authorised', 3000)
		trakt_sync_activities(force_update=True)
		return True
	kodi_utils.notification('Trakt Error Authorising', 3000)
	return False

def trakt_revoke_authentication(dummy=''):
	set_setting('trakt.user', 'empty_setting')
	set_setting('trakt.expires', '0')
	set_setting('trakt.token', '0')
	set_setting('trakt.refresh', '0')
	set_setting('trakt.next_daily_clear', '0')
	settings.fallback_watched_provider_on_revoke(1)
	trakt_cache.clear_all_trakt_cache_data(silent=True, refresh=False)
	kodi_utils.notification('Trakt Account Authorisation Reset', 3000)
	CLIENT_ID = settings.trakt_client()
	if CLIENT_ID in (None, 'empty_setting', ''): return no_client_key()
	CLIENT_SECRET = settings.trakt_secret()
	if CLIENT_SECRET in (None, 'empty_setting', ''): return no_secret_key()
	data = {'token': _trakt_setting('trakt.token'), 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
	response = call_trakt("oauth/revoke", data=data, with_auth=False)

def trakt_movies_related(imdb_id):
	string = 'trakt_movies_related_%s' % imdb_id
	params = {'path': 'movies/%s/related?extended=full', 'path_insert': imdb_id, 'params': {'limit': 20}}
	return lists_cache_object(get_trakt, string, params)

def trakt_movies_trending(page_no):
	string = 'trakt_movies_trending_%s' % page_no
	params = {'path': 'movies/trending/%s', 'params': {'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_movies_trending_recent(page_no):
	current_year = get_datetime().year
	years = '%s-%s' % (str(current_year-1), str(current_year))
	string = 'trakt_movies_trending_recent_%s' % page_no
	params = {'path': 'movies/trending/%s', 'params': {'limit': 20, 'years': years}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_movies_top10_boxoffice(page_no):
	string = 'trakt_movies_top10_boxoffice'
	params = {'path': 'movies/boxoffice/%s', 'pagination': False}
	return lists_cache_object(get_trakt, string, params)

def trakt_movies_most_watched(page_no):
	string = 'trakt_movies_most_watched_%s' % page_no
	params = {'path': 'movies/watched/daily/%s', 'params': {'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_movies_most_favorited(page_no):
	string = 'trakt_movies_most_favorited%s' % page_no
	params = {'path': 'movies/favorited/daily/%s', 'params': {'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_recommendations(media_type):
	string = 'trakt_recommendations_%s' % (media_type)
	params = {'path': '/recommendations/%s', 'path_insert': media_type, 'with_auth': True,
				'params': {'limit': 50, 'ignore_collected': 'true', 'ignore_watchlisted': 'true'}, 'pagination': False}
	return trakt_cache.cache_trakt_object(get_trakt, string, params)

def trakt_tv_related(imdb_id):
	string = 'trakt_tv_related_%s' % imdb_id
	params = {'path': 'shows/%s/related?extended=full', 'path_insert': imdb_id, 'params': {'limit': 20}}
	return lists_cache_object(get_trakt, string, params)

def trakt_tv_trending(page_no):
	string = 'trakt_tv_trending_%s' % page_no
	# params = {'path': 'shows/trending/%s', 'params': {'genres': '-anime', 'limit': 20}, 'page_no': page_no}
	params = {'path': 'shows/trending/%s', 'params': {'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_tv_trending_recent(page_no):
	current_year = get_datetime().year
	years = '%s-%s' % (str(current_year-1), str(current_year))
	string = 'trakt_tv_trending_recent_%s' % page_no
	# params = {'path': 'shows/trending/%s', 'params': {'genres': '-anime', 'years': years, 'limit': 20}, 'page_no': page_no}
	params = {'path': 'shows/trending/%s', 'params': {'years': years, 'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_tv_most_watched(page_no):
	string = 'trakt_tv_most_watched_%s' % page_no
	params = {'path': 'shows/watched/daily/%s', 'params': {'genres': '-anime', 'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_tv_most_favorited(page_no):
	string = 'trakt_tv_most_favorited_%s' % page_no
	params = {'path': 'shows/favorited/daily/%s', 'params': {'genres': '-anime', 'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_tv_certifications(certification, page_no):
	string = 'trakt_tv_certifications_%s_%s' % (certification, page_no)
	params = {'path': 'shows/collected/all%s', 'params': {'genres': '-anime', 'certifications': certification, 'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_tv_search(query, page_no):
	def _process(dummy_arg):
		return call_trakt('search/show', params={'genres': '-anime', 'query': query, 'limit': 20}, with_auth=False, pagination=True, page_no=page_no)
	string = 'trakt_tv_search_%s_%s' % (query, page_no)
	return cache_object(_process, string, 'dummy_arg', False, 24)

def trakt_anime_trending(page_no):
	string = 'trakt_anime_trending_%s' % page_no
	params = {'path': 'shows/trending/%s', 'params': {'genres': 'anime', 'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_anime_trending_recent(page_no):
	current_year = get_datetime().year
	years = '%s-%s' % (str(current_year-1), str(current_year))
	string = 'trakt_anime_trending_recent_%s' % page_no
	params = {'path': 'shows/trending/%s', 'params': {'genres': 'anime', 'limit': 20, 'years': years}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_anime_most_watched(page_no):
	string = 'trakt_anime_most_watched_%s' % page_no
	params = {'path': 'shows/watched/daily/%s', 'params': {'genres': 'anime', 'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_anime_most_favorited(page_no):
	string = 'trakt_anime_most_favorited_%s' % page_no
	params = {'path': 'shows/favorited/daily/%s', 'params': {'genres': 'anime', 'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_anime_certifications(certification, page_no):
	string = 'trakt_anime_certifications_%s_%s' % (certification, page_no)
	params = {'path': 'shows/collected/all%s', 'params': {'certifications': certification, 'genres': 'anime', 'limit': 20}, 'page_no': page_no}
	return lists_cache_object(get_trakt, string, params)

def trakt_anime_search(query, page_no):
	def _process(dummy_arg):
		return call_trakt('search/show', params={'genres': 'anime', 'query': query, 'limit': 20}, with_auth=False, pagination=True, page_no=page_no)
	string = 'trakt_anime_search_%s_%s' % (query, page_no)
	return cache_object(_process, string, 'dummy_arg', False, 24)

def trakt_get_hidden_items(list_type):
	def _get_trakt_ids(item):
		results_append(get_trakt_tvshow_id(item['show']['ids']))
	def _process(params):
		data = get_trakt(params)
		threads = TaskPool().tasks(_get_trakt_ids, data, min(len(data), settings.max_threads()))
		[i.join() for i in threads]
		return results
	results = []
	results_append = results.append
	string = 'trakt_hidden_items_%s' % list_type
	params = {'path': 'users/hidden/%s', 'path_insert': list_type, 'params': {'type': 'show'}, 'with_auth': True, 'fetch_all': True}
	return trakt_cache.cache_trakt_object(_process, string, params)

def trakt_watched_status_mark(action, media, media_id, tvdb_id=0, season=None, episode=None, key='tmdb'):
	if action == 'mark_as_watched': url, result_key = 'sync/history', 'added'
	else: url, result_key = 'sync/history/remove', 'deleted'
	if media == 'movies':
		success_key = 'movies'
		data = {'movies': [{'ids': {key: media_id}}]}
	else:
		success_key = 'episodes'
		if media == 'episode': data = {'shows': [{'seasons': [{'episodes': [{'number': int(episode)}], 'number': int(season)}], 'ids': {key: media_id}}]}
		elif media =='shows': data = {'shows': [{'ids': {key: media_id}}]}
		else: data = {'shows': [{'ids': {key: media_id}, 'seasons': [{'number': int(season)}]}]}#season
	result = call_trakt(url, data=data)
	success = result[result_key][success_key] > 0
	if not success:
		if media != 'movies' and tvdb_id != 0 and key != 'tvdb': return trakt_watched_status_mark(action, media, tvdb_id, 0, season, episode, 'tvdb')
	return success

def trakt_progress(action, media, media_id, percent, season=None, episode=None, resume_id=None, refresh_trakt=False):
	if action == 'clear_progress':
		url = 'sync/playback/%s' % resume_id
		result = call_trakt(url, is_delete=True)
	else:
		url = 'scrobble/pause'
		if media in ('movie', 'movies'): data = {'movie': {'ids': {'tmdb': media_id}}, 'progress': float(percent)}
		else: data = {'show': {'ids': {'tmdb': media_id}}, 'episode': {'season': int(season), 'number': int(episode)}, 'progress': float(percent)}
		call_trakt(url, data=data)
	if refresh_trakt: trakt_sync_activities()

def trakt_reset_scrobble(params):
	from modules.watched_status import get_database, get_bookmarks_movie, get_bookmarks_episode, erase_bookmark
	media_type = params.get('media_type') or params.get('content') or 'movie'
	tmdb_id = params.get('tmdb_id')
	season, episode = params.get('season'), params.get('episode')
	try:
		watched_db = get_database(1)
		if media_type == 'movie':
			resume_id = get_bookmarks_movie(watched_db).get(str(tmdb_id), {}).get('resume_id')
			if resume_id: trakt_progress('clear_progress', 'movie', tmdb_id, 0, resume_id=resume_id)
			erase_bookmark('movie', tmdb_id, '', '', 'true', 1)
		elif season not in (None, '', 'None') and episode not in (None, '', 'None'):
			bookmarks = get_bookmarks_episode(str(tmdb_id), season, watched_db) or {}
			resume_id = bookmarks.get(int(episode), {}).get('resume_id')
			if resume_id: trakt_progress('clear_progress', 'episode', tmdb_id, 0, season, episode, resume_id)
			erase_bookmark('episode', tmdb_id, season, episode, 'true', 1)
		else:
			return kodi_utils.notification('Reset Scrobble is only available for movies and episodes', 3500)
		trakt_sync_activities()
		kodi_utils.notification('Success', 3000)
	except:
		kodi_utils.notification('Error', 3000)

def trakt_collection_lists(media_type, list_type=None):
	data = trakt_fetch_collection_watchlist('collection', media_type)
	if list_type == 'recent':
		data.sort(key=lambda k: k['collected_at'], reverse=True)
		data = data[:20]
	return data

def trakt_watchlist_lists(media_type, list_type=None):
	data = trakt_fetch_collection_watchlist('watchlist', media_type)
	if list_type == 'recent':
		data.sort(key=lambda k: k['collected_at'], reverse=True)
		data = data[:20]
	return data

def trakt_collection(media_type, dummy_arg):
	data = trakt_fetch_collection_watchlist('collection', media_type)
	return settings.sort_trakt_sync_list(data, 'collection')

def trakt_watchlist(media_type, dummy_arg):
	data = trakt_fetch_collection_watchlist('watchlist', media_type)
	if not settings.show_unaired_watchlist():
		current_date = get_datetime()
		str_format = '%Y-%m-%d' if media_type in ('movie', 'movies') else '%Y-%m-%dT%H:%M:%S.%fZ'
		data = [i for i in data if i.get('released', None) and js2date(i.get('released'), str_format, remove_time=True) <= current_date]
	data = settings.sort_trakt_sync_list(data, 'watchlist')
	return data

def trakt_fetch_collection_watchlist(list_type, media_type):
	def _process(params):
		data = get_trakt(params) or []
		if list_type == 'watchlist': data = [i for i in data if i['type'] == key]
		return [{'media_ids': {'tmdb': i[key]['ids'].get('tmdb', ''), 'imdb': i[key]['ids'].get('imdb', ''), 'tvdb': i[key]['ids'].get('tvdb', '')},
		'title': i[key]['title'], 'collected_at': i.get(collected_at), 'released': i[key].get(r_key) if i[key].get(r_key) else
		('2050-01-01' if media_type == 'movie' else '2050-01-01T01:00:00.000Z')} for i in data]
	if media_type in ('movie', 'movies'): media_type, url_type = ('movie', 'movies')
	if media_type in ('show', 'shows', 'tvshow'): media_type, url_type = ('show', 'shows')
	key, r_key, string_insert = ('movie', 'released', 'movie') if media_type == 'movie' else ('show', 'first_aired', 'tvshow')
	collected_at = 'listed_at' if list_type == 'watchlist' else 'collected_at' if media_type == 'movie' else 'last_collected_at'
	string = 'trakt_%s_%s' % (list_type, string_insert)
	path = 'sync/%s/%s?extended=full'
	params = {'path': path, 'path_insert': (list_type, url_type), 'params': {'extended': 'full'}, 'with_auth': True, 'fetch_all': True}
	return trakt_cache.cache_trakt_object(_process, string, params)

def add_to_list(user, slug, data):
	result = call_trakt('/users/%s/lists/%s/items' % (user, slug), data=data)
	if result['existing']['movies'] + result['existing']['shows'] > 0: return kodi_utils.notification('Already In List', 3000)
	if result['added']['movies'] + result['added']['shows'] == 0: return kodi_utils.notification('Error', 3000)
	kodi_utils.notification('Success', 3000)
	trakt_sync_activities()
	return result

def remove_from_list(user, slug, data):
	result = call_trakt('/users/%s/lists/%s/items/remove' % (user, slug), data=data)
	if not result or result.get('deleted', {}).get('movies', 0) + result.get('deleted', {}).get('shows', 0) == 0:
		return kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000)
	kodi_utils.notification('Success', 3000)
	trakt_sync_activities()
	if kodi_utils.path_check('my_lists') or kodi_utils.external(): kodi_utils.kodi_refresh()
	return result

def _trakt_media_ids_match(ids, tmdb_id=None, imdb_id=None, tvdb_id=None):
	ids = ids or {}
	try:
		if tmdb_id not in (None, '', 'None') and ids.get('tmdb') not in (None, '', 'None') and int(ids['tmdb']) == int(tmdb_id):
			return True
	except: pass
	if imdb_id not in (None, '', 'None') and ids.get('imdb') and str(ids['imdb']) == str(imdb_id):
		return True
	try:
		if tvdb_id not in (None, '', 'None') and ids.get('tvdb') not in (None, '', 'None') and int(ids['tvdb']) == int(tvdb_id):
			return True
	except: pass
	return False

def trakt_item_in_sync_list(list_type, media_type, tmdb_id=None, imdb_id=None, tvdb_id=None):
	media = 'movie' if media_type in ('movie', 'movies') else 'show'
	try:
		data = trakt_fetch_collection_watchlist(list_type, media) or []
	except:
		return False
	return any(_trakt_media_ids_match(item.get('media_ids'), tmdb_id, imdb_id, tvdb_id) for item in data)

def trakt_item_in_favorites(media_type, tmdb_id=None, imdb_id=None, tvdb_id=None):
	media = 'movie' if media_type in ('movie', 'movies') else 'show'
	try:
		data = trakt_favorites(media, None) or []
	except:
		return False
	return any(_trakt_media_ids_match(item.get('media_ids'), tmdb_id, imdb_id, tvdb_id) for item in data)

def trakt_item_is_dropped(tmdb_id):
	try:
		return int(tmdb_id) in (trakt_get_hidden_items('dropped') or [])
	except:
		return False

def trakt_item_in_personal_list(user, slug, list_id, media_type, tmdb_id=None, imdb_id=None, tvdb_id=None):
	try:
		contents = get_trakt_list_contents('my_lists', user, slug, True, list_id=list_id) or []
	except:
		return False
	want_movie = media_type in ('movie', 'movies')
	for item in contents:
		item_type = item.get('type') or item.get('media_type')
		if want_movie:
			if item_type != 'movie': continue
			if _trakt_media_ids_match(item.get('media_ids'), tmdb_id, imdb_id, tvdb_id):
				return True
			continue
		if item_type == 'movie': continue
		if item_type in ('show', 'episode'):
			if _trakt_media_ids_match(item.get('media_ids'), tmdb_id, imdb_id, tvdb_id):
				return True
		elif item_type == 'season':
			try:
				if tmdb_id not in (None, '', 'None') and int(item.get('tmdb_id')) == int(tmdb_id):
					return True
			except: pass
	return False

def trakt_personal_lists_split_by_membership(media_type, tmdb_id=None, imdb_id=None, tvdb_id=None):
	results = []
	results_append = results.append
	def _check(item):
		user = item['user']['ids']['slug']
		slug = item['ids']['slug']
		list_id = item['ids']['trakt']
		entry = {
			'name': item['name'],
			'display': '[B]PERSONAL:[/B] [I]%s[/I]' % item['name'].upper(),
			'user': user,
			'slug': slug,
			'list_type': 'my_lists',
			'list_id': list_id,
			'item_count': item.get('item_count', 0)
		}
		is_in = trakt_item_in_personal_list(user, slug, list_id, media_type, tmdb_id, imdb_id, tvdb_id)
		results_append((entry, is_in))
	try:
		trakt_my_lists = trakt_get_lists('my_lists') or []
	except:
		return [], []
	if not trakt_my_lists: return [], []
	threads = TaskPool().tasks(_check, trakt_my_lists, min(len(trakt_my_lists), settings.max_threads()) or 1)
	[i.join() for i in threads]
	in_lists, out_lists = [], []
	for entry, is_in in results:
		(in_lists if is_in else out_lists).append(entry)
	in_lists.sort(key=lambda k: k['name'])
	out_lists.sort(key=lambda k: k['name'])
	return in_lists, out_lists

def select_trakt_personal_lists(lists):
	if not lists: return None
	list_items = [{'line1': '%s [I](x%02d)[/I]' % (item['display'], item.get('item_count', 0))} for item in lists]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Select', 'narrow_window': 'true'}
	return kodi_utils.select_dialog(lists, **kwargs)

def add_to_watchlist(data):
	result = call_trakt('/sync/watchlist', data=data)
	if result['existing']['movies'] + result['existing']['shows'] > 0: return kodi_utils.notification('Already In List', 3000)
	if result['added']['movies'] + result['added']['shows'] == 0: return kodi_utils.notification('Error', 3000)
	kodi_utils.notification('Success', 3000)
	trakt_sync_activities()
	return result

def remove_from_watchlist(data):
	result = call_trakt('/sync/watchlist/remove', data=data)
	if not result or result.get('deleted', {}).get('movies', 0) + result.get('deleted', {}).get('shows', 0) == 0:
		return kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000)
	kodi_utils.notification('Success', 3000)
	trakt_sync_activities()
	if kodi_utils.path_check('trakt_watchlist') or kodi_utils.external(): kodi_utils.kodi_refresh()
	return result

def add_to_collection(data):
	result = call_trakt('/sync/collection', data=data)
	if result['existing']['movies'] + result['existing']['episodes'] > 0: return kodi_utils.notification('Already In List', 3000)
	if result['added']['movies'] + result['added']['episodes'] == 0: return kodi_utils.notification('Error', 3000)
	kodi_utils.notification('Success', 3000)
	trakt_sync_activities()
	return result

def remove_from_collection(data):
	result = call_trakt('/sync/collection/remove', data=data)
	if not result or result.get('deleted', {}).get('movies', 0) + result.get('deleted', {}).get('episodes', 0) == 0:
		return kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000)
	kodi_utils.notification('Success', 3000)
	trakt_sync_activities()
	if kodi_utils.path_check('trakt_collection') or kodi_utils.external(): kodi_utils.kodi_refresh()
	return result

def add_to_favorites(data):
	result = call_trakt('/sync/favorites', data=data)
	if not result: return kodi_utils.notification('Error', 3000)
	if result.get('existing', {}).get('movies', 0) + result.get('existing', {}).get('shows', 0) > 0:
		return kodi_utils.notification('Already In List', 3000)
	if result.get('added', {}).get('movies', 0) + result.get('added', {}).get('shows', 0) == 0:
		return kodi_utils.notification('Error', 3000)
	kodi_utils.notification('Success', 3000)
	trakt_sync_activities()
	return result

def remove_from_favorites(data):
	result = call_trakt('/sync/favorites/remove', data=data)
	if not result or result.get('deleted', {}).get('movies', 0) + result.get('deleted', {}).get('shows', 0) == 0:
		return kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000)
	kodi_utils.notification('Success', 3000)
	trakt_sync_activities()
	if kodi_utils.path_check('trakt_favorites') or kodi_utils.external(): kodi_utils.kodi_refresh()
	return result

def hide_unhide_progress_items(params):
	action, media_type, media_id, list_type = params['action'], params['media_type'], params['media_id'], params['section']
	media_type = 'movies' if media_type in ('movie', 'movies') else 'shows'
	url = 'users/hidden/%s' % list_type if action == 'drop' else 'users/hidden/%s/remove' % list_type
	data = {media_type: [{'ids': {'tmdb': media_id}}]}
	call_trakt(url, data=data)
	trakt_sync_activities()
	kodi_utils.kodi_refresh()

def trakt_search_lists(search_title, page_no):
	def _process(dummy_arg):
		return call_trakt('search', params={'type': 'list', 'fields': 'name,description', 'query': search_title, 'limit': 50}, with_auth=False, pagination=True, page_no=page_no)
	string = 'trakt_search_lists_%s_%s' % (search_title, page_no)
	return cache_object(_process, string, 'dummy_arg', False, 4)

def trakt_favorites(media_type, dummy_arg):
	def _process(params):
		data = get_trakt(params)
		return [{'media_ids': {'tmdb': i[i['type']]['ids'].get('tmdb', ''), 'imdb': i[i['type']]['ids'].get('imdb', ''), 'tvdb': i[i['type']]['ids'].get('tvdb', '')}} \
					for i in data]
	media_type = 'movies' if media_type in ('movie', 'movies') else 'shows'
	string = 'trakt_favorites_%s' % media_type
	params = {'path': 'users/me/favorites/%s/%s', 'path_insert': (media_type, 'title'), 'with_auth': True, 'fetch_all': True}
	return trakt_cache.cache_trakt_object(_process, string, params)

def trakt_lists_with_media(media_type, imdb_id):
	def _process(foo):
		data = get_trakt(params)
		result = [i for i in data if i['item_count'] > 0 and i['ids']['slug'] not in ('', 'None', None) and i['privacy'] == 'public']
		return [kodi_utils.remove_keys(i, media_removals) for i in result]
	media_removals = ('description', 'privacy', 'type', 'share_link', 'display_numbers', 'allow_comments', 'sort_by', 'sort_how', 'created_at', 'updated_at', 'comment_count')
	results = []
	results_append = results.append
	template = '[B]%02d. [I]%s - %s likes[/I]'
	media_type = 'movies' if media_type in ('movie', 'movies') else 'shows'
	string = 'trakt_lists_with_media_%s' % imdb_id
	params = {'path': '%s/%s/lists/personal', 'path_insert': (media_type, imdb_id), 'params': {'limit': 100}, 'pagination': False}
	return cache_object(_process, string, 'foo', False, 168)

def get_trakt_list_contents(list_type, user, slug, with_auth, list_id=None, sort_by='default', sort_how='default'):
	if sort_by == 'skip': skip_sort, custom_sort, method = True, False, None
	else:
		skip_sort = False
		custom_sort = sort_by != 'default'
		method = None if custom_sort else 'sort_by_headers'
	if list_type == 'my_lists':
		string = 'trakt_list_contents_%s_%s_%s' % (list_type, user, slug)
		params = {'path': 'users/%s/lists/%s/items', 'path_insert': (user, slug), 'params': {'extended': 'full'}, 'method': method, 'with_auth': with_auth, 'fetch_all': True}
	elif list_id is not None:
		string = 'trakt_list_contents_%s_%s' % (list_type, list_id)
		params = {'path': 'users/%s/lists/%s/items', 'path_insert': (user, list_id), 'params': {'extended': 'full'}, 'method': method, 'fetch_all': True}
	else:
		string = 'trakt_list_contents_%s_%s_%s' % (list_type, user, slug)
		if user == 'Trakt Official': params = {'path': 'lists/%s/items', 'path_insert': slug, 'params': {'extended': 'full'}, 'method': method, 'fetch_all': True}
		else: params = {'path': 'users/%s/lists/%s/items', 'path_insert': (user, slug), 'params': {'extended': 'full'}, 'method': method, 'with_auth': with_auth, 'fetch_all': True}
	data = trakt_cache.cache_trakt_object(get_trakt, string, params) or []
	if not skip_sort:
		if not custom_sort:
			if isinstance(data, dict) and 'data' in data:
				sort_by, sort_how = data['sort_by'], data['sort_how']
				data = data['data'] or []
			elif not isinstance(data, list): data = []
		for i in data:
			if i['type'] == 'season': i['season']['title'] = '%s - %s' % (i['show']['title'], i['season']['title'])
			elif i['type'] == 'episode': i['episode']['title'] = '%s - %s' % (i['show']['title'], i['episode']['title'])
			else: pass
		data = sort_list(sort_by, sort_how, data, settings.ignore_articles())
	results = []
	results_append = results.append
	for c, i in enumerate(data):
		try:
			_type = i['type']
			if _type in ('movie', 'show'):
				r_key = 'released' if _type == 'movie' else 'first_aired'
				data = {'media_ids': i[_type]['ids'], 'title': i[_type]['title'], 'type': _type, 'order': c, 'released': i[_type][r_key], 'media_type': _type}
			elif _type == 'season':
				data = {'tmdb_id': i['show']['ids']['tmdb'], 'season': i[_type]['number'], 'type': _type, 'custom_order': c}
			elif _type == 'episode':
				data = {'media_ids': i['show']['ids'], 'title': i['show']['title'], 'type': _type,
						'season': i[_type]['season'], 'episode': i[_type]['number'], 'custom_order': c}
			results_append(data)
		except: pass
	return results

def trakt_get_lists(list_type, page_no='1'):
	if list_type in ('trending', 'popular'):
		string = 'trakt_%s_user_lists_%s' % (list_type, page_no)
		params = {'path': 'lists/%s', 'path_insert': list_type, 'params': {'limit': 50}, 'page_no': page_no}
		return cache_object(get_trakt, string, params, False)
	else:
		if list_type == 'my_lists': string, path = 'trakt_my_lists', 'users/me/lists%s'
		elif list_type == 'liked_lists': string, path = 'trakt_liked_lists', 'users/likes/lists%s'
		params = {'path': path, 'with_auth': True, 'fetch_all': True}
		return trakt_cache.cache_trakt_object(get_trakt, string, params)

def get_trakt_list_selection(included_lists):
	def default_lists():
		return [
		{'name': 'Movies Collection', 'display': '[B][I]MOVIES COLLECTION [/I][/B]', 'user': 'Collection', 'slug': 'Collection', 'list_type': 'collection', 'media_type': 'movie'},
		{'name': 'TV Show Collection', 'display': '[B][I]TV SHOW COLLECTION [/I][/B]', 'user': 'Collection', 'slug': 'Collection', 'list_type': 'collection', 'media_type': 'show'},
		{'name': 'Movies Watchlist', 'display': '[B][I]MOVIES WATCHLIST [/I][/B]',  'user': 'Watchlist', 'slug': 'Watchlist', 'list_type': 'watchlist', 'media_type': 'movie'},
		{'name': 'TV Show Watchlist', 'display': '[B][I]TV SHOW WATCHLIST [/I][/B]',  'user': 'Watchlist', 'slug': 'Watchlist', 'list_type': 'watchlist', 'media_type': 'show'}
		]
	def personal_lists():
		trakt_my_lists = trakt_get_lists('my_lists')
		_lists = [{'name': item['name'], 'display': '[B]PERSONAL:[/B] [I]%s[/I]' % item['name'].upper(), 'user': item['user']['ids']['slug'],
			'slug': item['ids']['slug'], 'list_type': 'my_lists', 'list_id': item['ids']['trakt'], 'item_count': item['item_count']} for item in trakt_my_lists]
		_lists.sort(key=lambda k: k['name'])
		return _lists
	def liked_lists():
		trakt_liked_lists = trakt_get_lists('liked_lists')
		_lists = [{'name': item['list']['name'], 'display': '[B]LIKED:[/B] [I]%s[/I]' % item['list']['name'].upper(), 'user': item['list']['user']['ids']['slug'],
			'slug': item['list']['ids']['slug'], 'list_type': 'liked_lists', 'list_id': item['list']['ids']['trakt'], 'item_count': item['list']['item_count']} \
			for item in trakt_liked_lists]
		_lists.sort(key=lambda k: (k['display']))
		return _lists
	list_dict = {'default': default_lists, 'personal': personal_lists, 'liked': liked_lists}
	used_lists = []
	for list_type in included_lists: used_lists.extend(list_dict[list_type]())
	list_items = [{'line1': '%s%s' % (item['display'],  ' [I](x%02d)[/I]' % item['item_count'] if 'item_count' in item else '')} for item in used_lists]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Select', 'narrow_window': 'true'}
	selection = kodi_utils.select_dialog(used_lists, **kwargs)
	if selection == None: return None
	return selection

def make_new_trakt_list(params):
	list_title = kodi_utils.kodi_dialog().input('')
	if not list_title: return
	list_name = unquote(list_title)
	data = {'name': list_name, 'privacy': 'private', 'allow_comments': False}
	call_trakt('users/me/lists', data=data)
	trakt_sync_activities()
	kodi_utils.notification('Success', 3000)
	kodi_utils.kodi_refresh()

def delete_trakt_list(params):
	user = params['user']
	list_slug = params['list_slug']
	if not kodi_utils.confirm_dialog(): return
	url = 'users/%s/lists/%s' % (user, list_slug)
	call_trakt(url, is_delete=True)
	trakt_sync_activities()
	kodi_utils.notification('Success', 3000)
	kodi_utils.kodi_refresh()

def trakt_like_a_list(params):
	user, list_slug, list_id = params.get('user'), params.get('list_slug'), params.get('list_id')
	refresh = params.get('refresh', 'true') == 'true'
	try:
		if list_id is not None: call_trakt('/lists/%s/like' % list_id, method='post')
		else: call_trakt('/users/%s/lists/%s/like' % (user, list_slug), method='post')
		kodi_utils.notification('Success - Trakt List Liked', 3000)
		trakt_sync_activities()
		if refresh: kodi_utils.kodi_refresh()
		return True
	except:
		kodi_utils.notification('Error', 3000)
		return False

def trakt_unlike_a_list(params):
	user, list_slug, list_id = params.get('user'), params.get('list_slug'), params.get('list_id')
	refresh = params.get('refresh', 'true') == 'true'
	try:
		if list_id is not None: call_trakt('/lists/%s/like' % list_id, method='delete')
		else: call_trakt('/users/%s/lists/%s/like' % (user, list_slug), method='delete')
		kodi_utils.notification('Success - Trakt List Unliked', 3000)
		trakt_sync_activities()
		if refresh: kodi_utils.kodi_refresh()
		return True
	except:
		kodi_utils.notification('Error', 3000)
		return False

def get_trakt_movie_id(item):
	if item['tmdb']: return item['tmdb']
	tmdb_id = None
	api_key = settings.tmdb_api_key()
	if item['imdb']:
		try:
			meta = movie_meta_external_id('imdb_id', item['imdb'], api_key)
			tmdb_id = meta['id']
		except: pass
	return tmdb_id

def get_trakt_tvshow_id(item):
	if item['tmdb']: return item['tmdb']
	tmdb_id = None
	api_key = settings.tmdb_api_key()
	if item['imdb']:
		try: 
			meta = tvshow_meta_external_id('imdb_id', item['imdb'], api_key)
			tmdb_id = meta['id']
		except: tmdb_id = None
	if not tmdb_id:
		if item['tvdb']:
			try: 
				meta = tvshow_meta_external_id('tvdb_id', item['tvdb'], api_key)
				tmdb_id = meta['id']
			except: tmdb_id = None
	return tmdb_id

def trakt_indicators_movies():
	def _process(item):
		try:
			movie = item['movie']
			tmdb_id = get_trakt_movie_id(movie['ids'])
			if not tmdb_id: return
			insert_append(('movie', tmdb_id, '', '', item['last_watched_at'], movie['title']))
		except: pass
	try:
		insert_list = []
		insert_append = insert_list.append
		params = {'path': 'sync/watched/movies%s', 'with_auth': True, 'fetch_all': True}
		result = get_trakt(params)
		if result is None: return
		threads = TaskPool().tasks(_process, result, min(len(result), settings.max_threads()))
		[i.join() for i in threads]
		trakt_cache.trakt_watched_cache.set_bulk_movie_watched(insert_list)
	except: pass

def trakt_indicators_tv():
	def _process(item):
		try:
			reset_at = item.get('reset_at', None)
			if reset_at: reset_at = js2date(reset_at, '%Y-%m-%dT%H:%M:%S.%fZ')
			show = item['show']
			seasons = item['seasons']
			title = show['title']
			tmdb_id = get_trakt_tvshow_id(show['ids'])
			if not tmdb_id: return
			for s in seasons:
				season_no, episodes = s['number'], s['episodes']
				for e in episodes:
					last_watched_at = e['last_watched_at']
					if reset_at and reset_at > js2date(last_watched_at, '%Y-%m-%dT%H:%M:%S.%fZ'): continue
					insert_append(('episode', tmdb_id, season_no, e['number'], last_watched_at, title))
		except: pass
	try:
		insert_list = []
		insert_append = insert_list.append
		params = {'path': 'sync/watched/shows%s', 'params': {'extended': 'progress'}, 'with_auth': True, 'fetch_all': True}
		result = get_trakt(params)
		if result is None: return
		threads = TaskPool().tasks(_process, result, min(len(result), settings.max_threads()))
		[i.join() for i in threads]
		trakt_cache.trakt_watched_cache.set_bulk_tvshow_watched(insert_list)
	except: pass

def trakt_playback_progress():
	params = {'path': 'sync/playback%s', 'with_auth': True, 'fetch_all': True}
	return get_trakt(params) or []

def trakt_comments(media_type, imdb_id):
	def _process(foo):
		data = get_trakt(params)
		for count, item in enumerate(data, 1):
			try:
				rating = '%s/10 - ' % item['user_rating'] if item['user_rating'] else ''
				comment = template % \
				(count, rating, item['user']['username'].upper(), js2date(item['created_at'], date_format, True).strftime('%d %B %Y'), replace_html_codes(item['comment']))
				if item['spoiler']: comment = spoiler_template + comment
				all_comments_append(comment)
			except: pass
		return all_comments
	all_comments = []
	all_comments_append = all_comments.append
	template, spoiler_template, date_format = '[B]%02d. [I]%s%s - %s[/I][/B][CR][CR]%s', '[B][COLOR red][CONTAINS SPOILERS][/COLOR][CR][/B]', '%Y-%m-%dT%H:%M:%S.000Z'
	media_type = 'movies' if media_type in ('movie', 'movies') else 'shows'
	string = 'trakt_comments_%s %s' % (media_type, imdb_id)
	params = {'path': '%s/%s/comments', 'path_insert': (media_type, imdb_id), 'params': {'sort': 'likes'}, 'fetch_all': True}
	return cache_object(_process, string, 'foo', False, 168)

def trakt_progress_movies(progress_info):
	def _process(item):
		tmdb_id = get_trakt_movie_id(item['movie']['ids'])
		if not tmdb_id: return
		obj = ('movie', str(tmdb_id), '', '', str(round(item['progress'], 1)), 0, item['paused_at'], item['id'], item['movie']['title'])
		insert_append(obj)
	insert_list = []
	insert_append = insert_list.append
	progress_items = [i for i in progress_info  if i['type'] == 'movie' and i['progress'] > 1]
	if not progress_items: return
	threads = TaskPool().tasks(_process, progress_items, min(len(progress_items), settings.max_threads()))
	[i.join() for i in threads]
	trakt_cache.trakt_watched_cache.set_bulk_movie_progress(insert_list)

def trakt_progress_tv(progress_info):
	def _process_tmdb_ids(item):
		tmdb_id = get_trakt_tvshow_id(item['ids'])
		tmdb_list_append((tmdb_id, item['title']))
	def _process():
		for item in tmdb_list:
			try:
				tmdb_id = item[0]
				if not tmdb_id: continue
				title = item[1]
				for p_item in progress_items:
					if p_item['show']['title'] == title:
						season = p_item['episode']['season']
						if season > 0: yield ('episode', str(tmdb_id), season, p_item['episode']['number'], str(round(p_item['progress'], 1)),
												0, p_item['paused_at'], p_item['id'], p_item['show']['title'])
			except: pass
	tmdb_list = []
	tmdb_list_append = tmdb_list.append
	progress_items = [i for i in progress_info if i['type'] == 'episode' and i['progress'] > 1]
	if not progress_items: return
	all_shows = [i['show'] for i in progress_items]
	all_shows = [i for n, i in enumerate(all_shows) if not i in all_shows[n + 1:]] # remove duplicates
	threads = TaskPool().tasks(_process_tmdb_ids, all_shows, min(len(all_shows), settings.max_threads()))
	[i.join() for i in threads]
	insert_list = list(_process())
	trakt_cache.trakt_watched_cache.set_bulk_tvshow_progress(insert_list)

def trakt_official_status(media_type):
	if not kodi_utils.addon_installed('script.trakt'): return True
	if not kodi_utils.addon_enabled('script.trakt'): return True
	trakt_addon = kodi_utils.addon('script.trakt')
	try: authorization = trakt_addon.getSetting('authorization')
	except: authorization = ''
	if authorization == '': return True
	try: exclude_http = trakt_addon.getSetting('ExcludeHTTP')
	except: exclude_http = ''
	if exclude_http in ('true', ''): return True
	media_setting = 'scrobble_movie' if media_type in ('movie', 'movies') else 'scrobble_episode'
	try: scrobble = trakt_addon.getSetting(media_setting)
	except: scrobble = ''
	if scrobble in ('false', ''): return True
	return False

def trakt_get_my_calendar(recently_aired, current_date):
	def _process(dummy):
		data = get_trakt(params)
		data = [{'sort_title': '%s s%s e%s' % (i['show']['title'], str(i['episode']['season']).zfill(2), str(i['episode']['number']).zfill(2)),
				'media_ids': i['show']['ids'], 'season': i['episode']['season'], 'episode': i['episode']['number'], 'first_aired': i['first_aired']} \
									for i in data if i['episode']['season'] > 0]
		data = [i for n, i in enumerate(data) if i not in data[n + 1:]] # remove duplicates
		return data
	start, finish = trakt_calendar_days(recently_aired, current_date)
	string = 'trakt_get_my_calendar_%s_%s' % (start, finish)
	params = {'path': 'calendars/my/shows/%s/%s', 'path_insert': (start, finish), 'with_auth': True, 'fetch_all': True}
	return trakt_cache.cache_trakt_object(_process, string, params)

def trakt_calendar_days(recently_aired, current_date):
	if recently_aired: start, finish = (current_date - timedelta(days=14)).strftime('%Y-%m-%d'), '14'
	else:
		previous_days = int(get_setting('redlight.trakt.calendar_previous_days', '0'))
		future_days = int(get_setting('redlight.trakt.calendar_future_days', '7'))
		start = (current_date - timedelta(days=previous_days)).strftime('%Y-%m-%d')
		finish = str(previous_days + future_days)
	return start, finish

def make_trakt_slug(name):
	import re
	name = name.strip()
	name = name.lower()
	name = re.sub('[^a-z0-9_]', '-', name)
	name = re.sub('--+', '-', name)
	return name

def trakt_get_activity():
	params = {'path': 'sync/last_activities%s', 'with_auth': True, 'pagination': False}
	return get_trakt(params)

def trakt_sync_activities(params=None, force_update=False):
	if isinstance(params, dict): force_update = params.get('force_update', 'false') in ('true', 'True', True) or force_update
	# def clear_watched_tvshow_cache():
	# 	from modules.watched_status import clear_cache_watched_tvshow_status
	# 	clear_cache_watched_tvshow_status(watched_indicators=1)
	def refresh_token_check():
		current_time = time.time()
		sync_interval = int(get_setting('redlight.trakt.sync_interval', '60')) * 60
		try: expires_at = float(get_setting('redlight.trakt.expires'))
		except: expires_at = 0.0
		if current_time + sync_interval >= expires_at: return True
	def clear_properties(media_type):
		for item in ((True, True), (True, False), (False, True), (False, False)): kodi_utils.clear_property('1_%s_%s_%s_watched' % (media_type, item[0], item[1]))
	def _get_timestamp(date_time):
		return int(time.mktime(date_time.timetuple()))
	def _compare(latest, cached):
		try: result = _get_timestamp(js2date(latest, '%Y-%m-%dT%H:%M:%S.%fZ')) > _get_timestamp(js2date(cached, '%Y-%m-%dT%H:%M:%S.%fZ'))
		except: result = True
		return result
	def _check_daily_expiry():
		return int(time.time()) >= int(get_setting('redlight.trakt.next_daily_clear', '0'))
	if refresh_token_check(): trakt_refresh_token()
	if force_update: trakt_cache.clear_all_trakt_cache_data(silent=True, refresh=False)
	elif _check_daily_expiry():
		trakt_cache.clear_daily_cache()
		set_setting('trakt.next_daily_clear', str(int(time.time()) + (24*3600)))
	if not settings.trakt_user_active() and not force_update: return 'no account'
	try: latest = trakt_get_activity()
	except: return 'failed'
	if not trakt_cache.valid_trakt_activities(latest): return 'failed'
	cached = trakt_cache.reset_activity(latest)
	fallback_date = '2020-01-01T00:00:01.000Z'
	if not force_update and not _compare(latest['all'], cached['all']): return 'not needed'
	lists_actions, refresh_movies_progress, refresh_shows_progress, clear_tvshow_watched_cache = [], False, False, False
	cached_movies, latest_movies = cached['movies'], latest['movies']
	cached_shows, latest_shows = cached['shows'], latest['shows']
	cached_episodes, latest_episodes = cached['episodes'], latest['episodes']
	cached_lists, latest_lists = cached['lists'], latest['lists']
	if _compare(latest['recommendations'], cached.get('recommendations', fallback_date)): trakt_cache.clear_trakt_recommendations()
	if _compare(latest['favorites'], cached.get('favorites', fallback_date)): trakt_cache.clear_trakt_favorites()
	if _compare(latest_movies['collected_at'], cached_movies.get('collected_at', fallback_date)): trakt_cache.clear_trakt_collection_watchlist_data('collection', 'movie')
	if _compare(latest_episodes['collected_at'], cached_episodes.get('collected_at', fallback_date)): trakt_cache.clear_trakt_collection_watchlist_data('collection', 'tvshow')
	if _compare(latest_movies['watchlisted_at'], cached_movies.get('watchlisted_at', fallback_date)): trakt_cache.clear_trakt_collection_watchlist_data('watchlist', 'movie')
	if _compare(latest_shows['watchlisted_at'], cached_shows.get('watchlisted_at', fallback_date)): trakt_cache.clear_trakt_collection_watchlist_data('watchlist', 'tvshow')
	if _compare(latest_shows['dropped_at'], cached_shows.get('dropped_at', fallback_date)):
		clear_properties('episode')
		trakt_cache.clear_trakt_hidden_data('dropped')
	if force_update or _compare(latest_movies['watched_at'], cached_movies.get('watched_at', fallback_date)):
		clear_properties('movie')
		trakt_indicators_movies()
	if force_update or _compare(latest_episodes['watched_at'], cached_episodes.get('watched_at', fallback_date)):
		clear_properties('episode')
		trakt_indicators_tv()
		# clear_tvshow_watched_cache = True
	if force_update or _compare(latest_movies['paused_at'], cached_movies.get('paused_at', fallback_date)): refresh_movies_progress = True
	if force_update or _compare(latest_episodes['paused_at'], cached_episodes.get('paused_at', fallback_date)): refresh_shows_progress = True
	if _compare(latest_lists['updated_at'], cached_lists.get('updated_at', fallback_date)): lists_actions.append('my_lists')
	if _compare(latest_lists['liked_at'], cached_lists.get('liked_at', fallback_date)): lists_actions.append('liked_lists')
	if refresh_movies_progress or refresh_shows_progress:
		progress_info = trakt_playback_progress()
		if refresh_movies_progress:
			clear_properties('movie')
			trakt_progress_movies(progress_info)
		if refresh_shows_progress:
			clear_properties('episode')
			trakt_progress_tv(progress_info)
	if lists_actions:
		for item in lists_actions:
			trakt_cache.clear_trakt_list_data(item)
			trakt_cache.clear_trakt_list_contents_data(item)
	# if clear_tvshow_watched_cache: clear_watched_tvshow_cache()
	return 'success'

def trakt_force_sync(params=None):
	if not settings.trakt_user_active(): return kodi_utils.notification('Trakt account not authorised', 3000)
	progress = kodi_utils.progress_dialog('Trakt Sync')
	status = 'failed'
	try:
		progress.update('Syncing with Trakt...', 0)
		status = trakt_sync_activities(force_update=True)
	except Exception as e:
		kodi_utils.logger('Trakt', 'Force sync failed: %s' % e)
	finally:
		kodi_utils.close_progress_dialog(progress)
	if status == 'failed': kodi_utils.notification('Trakt Sync Failed', 3000)
	else:
		kodi_utils.mark_boot_trakt_sync_ready()
		kodi_utils.notification('Trakt Sync Complete', 3000)
		kodi_utils.kodi_refresh()
	return status
