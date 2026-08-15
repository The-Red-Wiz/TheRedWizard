# -*- coding: utf-8 -*-
import os
import re
import struct
import xbmc
import xbmcvfs
import requests
from caches.settings_cache import get_setting, set_setting
from modules import kodi_utils as ku, settings as st

BASE_URL = 'https://api.opensubtitles.com/api/v1'
TIMEOUT = 20.0
_DEFAULT_API_KEY = 'GpubxF50wjXZXtRlq83Heh9serfjCFyI'
_OSUB_HASH_CHUNK = 65536
_OSUB_LONGLONG = struct.calcsize('q')


def effective_api_key():
	key = get_setting('redlight.playback.opensubs_api_key', 'empty_setting')
	if key not in (None, '', '0', 'empty_setting'):
		return str(key).strip()
	return _DEFAULT_API_KEY


def _api_key():
	return effective_api_key()


def _username():
	value = get_setting('redlight.playback.opensubs_username', 'empty_setting')
	return '' if value in (None, '', '0', 'empty_setting') else str(value).strip()


def _password():
	value = get_setting('redlight.playback.opensubs_password', 'empty_setting')
	return '' if value in (None, '', '0', 'empty_setting') else str(value).strip()


def _token():
	value = get_setting('redlight.playback.opensubs_token', '0')
	return '' if value in (None, '', '0', 'empty_setting') else str(value).strip()


def _headers(token=None):
	headers = {
		'Content-Type': 'application/json',
		'Api-Key': _api_key(),
		'User-Agent': 'RedLight/%s' % ku.addon_version(),
	}
	if token: headers['Authorization'] = token
	return headers


def _normalize_imdb(imdb_id):
	if not imdb_id: return ''
	imdb_id = str(imdb_id).strip()
	return imdb_id if imdb_id.startswith('tt') else 'tt%s' % imdb_id

def _imdb_as_int(imdb_id):
	if not imdb_id: return None
	text = str(imdb_id).strip().lower()
	if text.startswith('tt'): text = text[2:]
	try: return int(text)
	except: return None

def _parse_feature_imdb(feature_imdb):
	if feature_imdb in (None, ''): return None
	try:
		text = str(feature_imdb).strip().lower()
		if text.startswith('tt'): text = text[2:]
		return int(text)
	except: return None


def _subtitle_language_code():
	try: return xbmc.convertLanguage(st.subs_language_for_download(), xbmc.ISO_639_1)
	except: return 'en'


def _save_token(token):
	if token: set_setting('playback.opensubs_token', token)


def authorized():
	if not st.opensubs_configured(): return False
	token = _token()
	if token:
		try:
			response = requests.get('%s/infos/user' % BASE_URL, headers=_headers(token), timeout=TIMEOUT)
			if response.status_code == 200: return True
		except: pass
	try:
		response = requests.post('%s/login' % BASE_URL, headers=_headers(), json={'username': _username(), 'password': _password()}, timeout=TIMEOUT)
		if response.status_code != 200: return False
		token = response.json().get('token')
		if not token: return False
		_save_token(token)
		return True
	except: return False


def _title_query_from_playback(playing_filename=None, playing_item=None):
	if isinstance(playing_item, dict):
		for key in ('tvshowtitle', 'title', 'name', 'originaltitle'):
			val = playing_item.get(key)
			if val and not str(val).startswith('http'):
				return str(val).strip()
	if playing_filename:
		stem = os.path.splitext(os.path.basename(str(playing_filename).split('|')[0].split('?')[0]))[0]
		match = re.match(r'^(.+?)[.\s_-]*s\d{1,2}[ex]', stem, re.I)
		if match: return match.group(1).replace('.', ' ').replace('_', ' ').strip()
		parts = [part for part in re.split(r'[._\s-]+', stem) if part and not re.match(r'^s?\d', part, re.I)]
		if parts: return parts[0]
	return ''

def _search_query_from_playback(year, season, episode, playing_filename=None, playing_item=None):
	title = _title_query_from_playback(playing_filename, playing_item)
	if season not in (None, '') and episode not in (None, '') and title:
		return '%s S%02dE%02d' % (title, int(season), int(episode))
	if title and year not in (None, ''):
		return '%s %s' % (title, int(year))
	return title or ''

def _local_playback_path(playing_filename=None):
	if playing_filename:
		path = str(playing_filename).split('|')[0].split('?')[0].strip()
		lower = path.lower()
		if path and not lower.startswith(('http://', 'https://', 'plugin://')):
			return path
	try:
		path = xbmc.Player().getPlayingFile()
		if path and not str(path).lower().startswith(('http://', 'https://', 'plugin://')):
			return path
	except: pass
	return ''

def _sum_64k_bytes(file_handle, state):
	range_value = round(_OSUB_HASH_CHUNK / _OSUB_LONGLONG)
	for _ in range(range_value):
		chunk = file_handle.read(_OSUB_LONGLONG)
		if not chunk or len(chunk) < _OSUB_LONGLONG: return False
		(value,) = struct.unpack('q', chunk)
		state['hash'] = (state['hash'] + value) & 0xFFFFFFFFFFFFFFFF
	return True

def _opensubs_moviehash(playing_filename=None):
	path = _local_playback_path(playing_filename)
	if not path: return ''
	try:
		if path.startswith('special://'): path = ku.translate_path(path)
		if not ku.path_exists(path): return ''
		file_handle = xbmcvfs.File(path)
		try:
			filesize = file_handle.size()
			if filesize < _OSUB_HASH_CHUNK * 2: return ''
			state = {'hash': filesize}
			if not _sum_64k_bytes(file_handle, state): return ''
			file_handle.seek(filesize - _OSUB_HASH_CHUNK, 0)
			if not _sum_64k_bytes(file_handle, state): return ''
			return '%016x' % state['hash']
		finally:
			del file_handle
	except: return ''

def _base_search_params(imdb_id, year, season, episode, language):
	params = {'languages': language or 'en'}
	if imdb_id: params['imdb_id'] = _normalize_imdb(imdb_id)
	if season not in (None, ''):
		params['season_number'] = int(season)
		params['episode_number'] = int(episode)
	elif year not in (None, ''):
		params['year'] = int(year)
	return params

def _parse_search_result(item, expected_imdb_int=None):
	attrs = item.get('attributes') or {}
	parsed_imdb = _parse_feature_imdb((attrs.get('feature_details') or {}).get('imdb_id'))
	if parsed_imdb is not None and expected_imdb_int is not None and parsed_imdb != expected_imdb_int:
		return None
	files = attrs.get('files') or []
	if not files: return None
	file_info = files[0]
	file_id, file_name = file_info.get('file_id'), file_info.get('file_name')
	if not file_id or not file_name: return None
	return {
		'file_id': file_id,
		'file_name': file_name,
		'moviehash_match': bool(attrs.get('moviehash_match')),
	}

def _search_subtitles_request(params, expected_imdb_int=None, filter_imdb=True):
	token = _token()
	if not token and not authorized(): return []
	try:
		response = requests.get('%s/subtitles' % BASE_URL, headers=_headers(token or _token()), params=params, timeout=TIMEOUT)
		if response.status_code == 401 and authorized():
			response = requests.get('%s/subtitles' % BASE_URL, headers=_headers(_token()), params=params, timeout=TIMEOUT)
		if response.status_code != 200: return []
		imdb_filter = expected_imdb_int if filter_imdb else None
		results = []
		for item in response.json().get('data') or []:
			try:
				parsed = _parse_search_result(item, imdb_filter)
				if parsed: results.append(parsed)
			except: continue
		return results
	except: return []

def _search_subtitles(imdb_id, year, season, episode, language, playing_filename=None, playing_item=None):
	expected_imdb_int = _imdb_as_int(imdb_id)
	lang = language or 'en'
	imdb_params = _base_search_params(imdb_id, year, season, episode, lang)
	results = _search_subtitles_request(imdb_params, expected_imdb_int, filter_imdb=True)
	if results: return results
	query = _search_query_from_playback(year, season, episode, playing_filename, playing_item)
	moviehash = _opensubs_moviehash(playing_filename)
	if query or moviehash:
		enriched = dict(imdb_params)
		if query: enriched['query'] = query
		if moviehash: enriched['moviehash'] = moviehash
		results = _search_subtitles_request(enriched, expected_imdb_int, filter_imdb=True)
		if results: return results
	if not query: return []
	title_params = {'languages': lang, 'query': query}
	if season not in (None, ''):
		title_params['season_number'] = int(season)
		title_params['episode_number'] = int(episode)
	elif year not in (None, ''):
		title_params['year'] = int(year)
	if moviehash: title_params['moviehash'] = moviehash
	return _search_subtitles_request(title_params, expected_imdb_int, filter_imdb=False)


def _episode_in_filename(season, episode, filename):
	if not filename: return False
	lower = filename.lower()
	patterns = (
		r's%02de%02d' % (int(season), int(episode)),
		r's%d[eexx]%d' % (int(season), int(episode)),
		r'%dx%d' % (int(season), int(episode)),
		r'season[\.\s_-]*%d[\.\s_-]*episode[\.\s_-]*%d' % (int(season), int(episode)),
	)
	return any(re.search(pattern, lower) for pattern in patterns)


def _pick_best_subtitle(results, playing_filename=None, playing_item=None, season=None, episode=None):
	if not results: return None
	from indexers.subtitles import playback_release_context, _score_subtitle_release_match
	release_context = playback_release_context(playing_filename, playing_item, season, episode)
	filtered = []
	for item in results:
		file_name = item.get('file_name') or ''
		if season not in (None, '') and episode not in (None, '') and not _episode_in_filename(season, episode, file_name):
			continue
		filtered.append(item)
	pool = filtered or list(results)
	pool.sort(key=lambda item: (1 if item.get('moviehash_match') else 0, _score_subtitle_release_match(item, release_context)), reverse=True)
	return pool[0]


def _download_subtitle_content(file_id):
	token = _token()
	if not token and not authorized(): return None
	try:
		response = requests.post('%s/download' % BASE_URL, headers=_headers(token or _token()), json={'file_id': file_id}, timeout=TIMEOUT)
		if response.status_code == 401 and authorized():
			response = requests.post('%s/download' % BASE_URL, headers=_headers(_token()), json={'file_id': file_id}, timeout=TIMEOUT)
		if response.status_code != 200: return None
		link = response.json().get('link')
		if not link: return None
		file_response = requests.get(link, timeout=TIMEOUT)
		if file_response.status_code != 200: return None
		try: content = file_response.text
		except: content = file_response.content
		if isinstance(content, bytes):
			try: content = content.decode('utf-8', 'ignore')
			except: return None
		return content
	except: return None


def fetch_alert_subtitle(imdb_id, season=None, episode=None, year=None, playing_filename=None, playing_item=None, log_pick=False, skip_cache=False):
	if not st.opensubs_configured(): return None
	from indexers.subtitles import (
		_existing_opensubs_subtitle_cache, _opensubs_alert_path, _prepare_subtitle_file_content,
		_subtitle_cache_release_tag, playback_release_context, remember_active_subtitle_path,
	)
	if not skip_cache:
		cached = _existing_opensubs_subtitle_cache(imdb_id, season, episode, playing_filename, playing_item)
		if cached:
			remember_active_subtitle_path(cached)
			return cached
	release_context = playback_release_context(playing_filename, playing_item, season, episode)
	results = _search_subtitles(imdb_id, year, season, episode, _subtitle_language_code(), playing_filename, playing_item)
	match = _pick_best_subtitle(results, playing_filename, playing_item, season, episode)
	if not match: return None
	if log_pick:
		try:
			label = match.get('file_name') or match.get('file_id') or 'unknown'
			if len(str(label)) > 120: label = str(label)[:117] + '...'
			play_tag = _subtitle_cache_release_tag(release_context) or 'unknown'
			sync_tag = ' sync' if match.get('moviehash_match') else ''
			ku.logger('Red Light', 'OpenSubtitles pick (%s%s): %s' % (play_tag, sync_tag, label))
		except: pass
	content = _download_subtitle_content(match.get('file_id'))
	prepared = _prepare_subtitle_file_content(content, log_reject=log_pick, reject_label='OpenSubtitles')
	if not prepared: return None
	final_path = _opensubs_alert_path(imdb_id, season, episode, release_context)
	try:
		with ku.open_file(final_path, 'w') as file: file.write(prepared)
		ku.set_property('redlight.active_subtitle_path', final_path)
	except: return None
	return final_path


def _fetch_user_quota(token=None):
	token = token or _token()
	if not token:
		return None, None
	try:
		response = requests.get('%s/infos/user' % BASE_URL, headers=_headers(token), timeout=TIMEOUT)
		if response.status_code == 401 and authorized():
			response = requests.get('%s/infos/user' % BASE_URL, headers=_headers(_token()), timeout=TIMEOUT)
		if response.status_code != 200:
			return None, None
		info = response.json().get('data') or {}
		return info.get('remaining_downloads'), info.get('allowed_downloads')
	except:
		return None, None


def check_account():
	if not st.opensubs_configured():
		return ku.ok_dialog(heading='OpenSubtitles', text='Enter your OpenSubtitles username and password first.')
	try:
		response = requests.post('%s/login' % BASE_URL, headers=_headers(), json={'username': _username(), 'password': _password()}, timeout=TIMEOUT)
		if response.status_code != 200:
			return ku.ok_dialog(heading='OpenSubtitles', text='Login failed. Check your OpenSubtitles username and password.')
		data = response.json()
		token = data.get('token')
		if token: _save_token(token)
		user = data.get('user') or {}
		remaining = user.get('remaining_downloads')
		allowed = user.get('allowed_downloads')
		info_remaining, info_allowed = _fetch_user_quota(token)
		if info_remaining is not None: remaining = info_remaining
		if info_allowed is not None: allowed = info_allowed
		if remaining is not None and allowed is not None:
			text = 'Account: %s[CR][CR]Downloads remaining (24h): %s of %s' % (_username(), remaining, allowed)
		elif allowed is not None:
			text = 'Account: %s[CR][CR]Daily download limit (24h): %s' % (_username(), allowed)
		else:
			text = 'Account: %s[CR][CR]Download quota: unknown' % _username()
		return ku.ok_dialog(heading='OpenSubtitles', text=text)
	except:
		return ku.ok_dialog(heading='OpenSubtitles', text='Error checking OpenSubtitles account. Check your username and password.')


def revoke_access():
	for setting_id, value in (
		('playback.opensubs_username', 'empty_setting'),
		('playback.opensubs_password', 'empty_setting'),
		('playback.opensubs_token', '0'),
	):
		set_setting(setting_id, value)
	try:
		from caches.settings_cache import refresh_settings_manager_properties
		refresh_settings_manager_properties()
	except: pass
	try:
		from modules.settings import refresh_playback_subs_source, refresh_alert_timing_settings
		refresh_playback_subs_source()
		refresh_alert_timing_settings()
	except: pass
	return ku.ok_dialog(heading='OpenSubtitles', text='OpenSubtitles username, password, and saved login cleared.')


def test_login():
	return check_account()
