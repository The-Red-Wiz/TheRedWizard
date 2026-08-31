# -*- coding: utf-8 -*-
import requests
from caches.main_cache import main_cache

THEINTRODB_URL = 'https://api.theintrodb.org/v3/media'
INTRODB_URL = 'https://api.introdb.app/segments'
_CACHE_HOURS = 168
_API_TIMEOUT = 6
_MIN_SEGMENT_SEC = 10
_MIN_END_SEC = 15
_MAX_SEGMENT_SEC = 600
_MAX_INTRO_START_FRAC = 0.5
_CREDITS_INTRO_OVERLAP_MS = 5000


def _intro_cache_key(tmdb_id, imdb_id, season, episode):
	return 'intro_skip_%s_%s_%s_%s' % (tmdb_id, imdb_id or '', season, episode)


def _outro_cache_key(tmdb_id, imdb_id, season, episode):
	return 'outro_credits_%s_%s_%s_%s' % (tmdb_id, imdb_id or '', season, episode)


def peek_intro_segment_cache(tmdb_id, imdb_id, season, episode, duration_sec=None):
	try:
		season, episode = int(season), int(episode)
	except:
		return '__miss__'
	cached = main_cache.get(_intro_cache_key(tmdb_id, imdb_id, season, episode))
	if cached is None:
		return '__miss__'
	if not cached:
		return None
	segment = _valid_segment(cached.get('start_sec'), cached.get('end_sec'), duration_sec)
	if segment:
		segment['source'] = cached.get('source', 'introdb')
		return segment
	return '__miss__'


def prefetch_intro_segment(tmdb_id, imdb_id, season, episode, duration_sec=None):
	try:
		resolve_intro_segment(tmdb_id, imdb_id, season, episode, duration_sec)
	except:
		pass


def prefetch_credits_start(tmdb_id, imdb_id, season, episode, duration_sec=None):
	try:
		resolve_credits_start_sec(tmdb_id, imdb_id, season, episode, duration_sec)
	except:
		pass


def resolve_intro_segment(tmdb_id, imdb_id, season, episode, duration_sec=None):
	try:
		season, episode = int(season), int(episode)
	except:
		return None
	cache_key = _intro_cache_key(tmdb_id, imdb_id, season, episode)
	cached = main_cache.get(cache_key)
	if cached is not None:
		if not cached:
			return None
		segment = _valid_segment(cached.get('start_sec'), cached.get('end_sec'), duration_sec)
		if segment:
			segment['source'] = cached.get('source', 'introdb')
			return segment
		main_cache.set(cache_key, '', expiration=_CACHE_HOURS)
	segment = None
	if tmdb_id not in (None, '', 'None', '0000000'):
		segment = _fetch_theintrodb_intro(tmdb_id, season, episode, duration_sec)
	if not segment and imdb_id not in (None, '', 'None', 'tt0000000'):
		segment = _fetch_introdb_intro(imdb_id, season, episode)
	main_cache.set(cache_key, segment or '', expiration=_CACHE_HOURS)
	return segment


def resolve_credits_start_sec(tmdb_id, imdb_id, season, episode, duration_sec=None):
	try:
		season, episode = int(season), int(episode)
	except:
		return None
	cache_key = _outro_cache_key(tmdb_id, imdb_id, season, episode)
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached or None
	start_sec = None
	if tmdb_id not in (None, '', 'None', '0000000'):
		start_sec = _fetch_theintrodb_credits(tmdb_id, season, episode, duration_sec)
	if start_sec is None and imdb_id not in (None, '', 'None', 'tt0000000'):
		start_sec = _fetch_introdb_outro(imdb_id, season, episode, duration_sec)
	main_cache.set(cache_key, start_sec if start_sec is not None else '', expiration=_CACHE_HOURS)
	return start_sec


def _valid_start_sec(start_sec, duration_sec=None):
	try:
		start_sec = float(start_sec)
	except:
		return None
	if start_sec < 0:
		return None
	if duration_sec:
		try:
			total = float(duration_sec)
			if total > 60 and start_sec > total:
				return None
		except:
			pass
	return start_sec


def _valid_segment(start_sec, end_sec, duration_sec=None):
	try:
		start_sec, end_sec = float(start_sec), float(end_sec)
	except:
		return None
	if end_sec <= start_sec:
		return None
	length = end_sec - start_sec
	if length < _MIN_SEGMENT_SEC or length > _MAX_SEGMENT_SEC:
		return None
	if end_sec < _MIN_END_SEC:
		return None
	if duration_sec:
		try:
			total = float(duration_sec)
			if total > 60:
				if end_sec > total:
					return None
				if start_sec > total * _MAX_INTRO_START_FRAC:
					return None
		except:
			pass
	return {'start_sec': start_sec, 'end_sec': end_sec}


def _ms_segment(start_ms, end_ms, duration_sec=None):
	if start_ms is None:
		start_ms = 0
	try:
		start_ms, end_ms = int(start_ms), int(end_ms)
	except:
		return None
	if end_ms <= start_ms:
		return None
	return _valid_segment(start_ms / 1000.0, end_ms / 1000.0, duration_sec)


def _credits_start_ms_list(credits_list):
	starts = []
	for entry in credits_list or []:
		ms = entry.get('start_ms') if isinstance(entry, dict) else None
		if ms is None:
			continue
		try:
			starts.append(int(ms))
		except:
			pass
	return starts


def _intro_is_credits_duplicate(start_ms, credits_starts):
	if not credits_starts:
		return False
	try:
		start_ms = 0 if start_ms is None else int(start_ms)
	except:
		return False
	for credit_ms in credits_starts:
		if abs(start_ms - credit_ms) <= _CREDITS_INTRO_OVERLAP_MS:
			return True
		if start_ms >= credit_ms:
			return True
	return False


def _parse_start_value(start_val, end_val=None):
	if start_val is None:
		return None
	try:
		start_sec = float(start_val)
		if start_sec > 10000:
			start_sec = start_sec / 1000.0
		return start_sec
	except:
		return None


def _fetch_theintrodb_intro(tmdb_id, season, episode, duration_sec=None):
	try:
		params = {'tmdb_id': str(tmdb_id), 'season': season, 'episode': episode}
		if duration_sec:
			try:
				params['durationMs'] = int(float(duration_sec) * 1000)
			except:
				pass
		response = requests.get(THEINTRODB_URL, params=params, timeout=_API_TIMEOUT)
		if response.status_code != 200:
			return None
		data = response.json()
		intro_list = data.get('intro') or []
		if not intro_list:
			return None
		credits_starts = _credits_start_ms_list(data.get('credits') or [])
		for entry in intro_list:
			if not isinstance(entry, dict):
				continue
			start_ms = entry.get('start_ms')
			if _intro_is_credits_duplicate(start_ms, credits_starts):
				continue
			segment = _ms_segment(start_ms, entry.get('end_ms'), duration_sec)
			if segment:
				segment['source'] = 'theintrodb'
				return segment
		return None
	except:
		return None


def _fetch_introdb_intro(imdb_id, season, episode):
	try:
		params = {'imdb_id': str(imdb_id), 'season': season, 'episode': episode, 'segment_type': 'intro'}
		response = requests.get(INTRODB_URL, params=params, timeout=_API_TIMEOUT)
		if response.status_code != 200:
			return None
		data = response.json()
		intro = data.get('intro')
		if not intro or not isinstance(intro, dict):
			return None
		start_sec = _parse_start_value(intro.get('start_sec', intro.get('start_ms')))
		end_sec = _parse_start_value(intro.get('end_sec', intro.get('end_ms')))
		if start_sec is None:
			start_sec = 0.0
		segment = _valid_segment(start_sec, end_sec)
		if segment:
			segment['source'] = 'introdb'
		return segment
	except:
		return None


def _fetch_introdb_outro(imdb_id, season, episode, duration_sec=None):
	try:
		params = {'imdb_id': str(imdb_id), 'season': season, 'episode': episode}
		response = requests.get(INTRODB_URL, params=params, timeout=_API_TIMEOUT)
		if response.status_code != 200:
			return None
		outro = response.json().get('outro') or {}
		start_sec = _parse_start_value(outro.get('start_sec', outro.get('start_ms')))
		return _valid_start_sec(start_sec, duration_sec)
	except:
		return None


def _fetch_theintrodb_credits(tmdb_id, season, episode, duration_sec=None):
	try:
		params = {'tmdb_id': str(tmdb_id), 'season': season, 'episode': episode}
		if duration_sec:
			try:
				params['durationMs'] = int(float(duration_sec) * 1000)
			except:
				pass
		response = requests.get(THEINTRODB_URL, params=params, timeout=_API_TIMEOUT)
		if response.status_code != 200:
			return None
		credits_list = response.json().get('credits') or []
		if not credits_list:
			return None
		entry = credits_list[0]
		if entry.get('start_ms') is None:
			return None
		return _valid_start_sec(int(entry['start_ms']) / 1000.0, duration_sec)
	except:
		return None
