# -*- coding: utf-8 -*-
from modules.kodi_utils import make_session
# from modules.kodi_utils import logger

_BASE = 'https://webservice.fanart.tv/v3'
_EMPTY_IDS = (None, '', 'None', 'empty_setting', 0, '0', '0000000')
session = make_session('https://webservice.fanart.tv')

def _headers(api_key):
	return {'api-key': api_key, 'client-key': api_key, 'User-Agent': 'plugin.video.redlight'}

def _best(images):
	if not images: return ''
	preferred, fallback = [], []
	for item in images:
		url = item.get('url') or ''
		if not url: continue
		try: likes = int(item.get('likes') or 0)
		except: likes = 0
		lang = item.get('lang')
		if lang == 'en': preferred.append((-likes, url))
		elif lang in ('00', '', None): fallback.append((-likes, url))
	pool = preferred or fallback
	if not pool:
		for item in images:
			url = item.get('url') or ''
			if not url: continue
			try: likes = int(item.get('likes') or 0)
			except: likes = 0
			pool.append((-likes, url))
	if not pool: return ''
	pool.sort()
	return pool[0][1]

def _get(path, api_key):
	try:
		response = session.get('%s/%s' % (_BASE, path), headers=_headers(api_key), timeout=15)
		if response.status_code != 200: return None
		data = response.json()
		if not isinstance(data, dict) or data.get('status') == 'error': return None
		return data
	except: return None

def test_key(api_key):
	"""Return (ok, message) for Settings → Test API Key. Fight Club is always on Fanart.tv."""
	if api_key in _EMPTY_IDS: return False, 'Enter a Fanart.tv API key first.'
	try:
		response = session.get('%s/movies/550' % _BASE, headers=_headers(api_key), timeout=15)
		if response.status_code == 200:
			data = response.json()
			if isinstance(data, dict) and data.get('name'):
				return True, 'Fanart.tv API key is valid.'
			if isinstance(data, dict) and data.get('status') == 'error':
				return False, data.get('error message') or data.get('error') or 'Fanart.tv rejected the key.'
			return True, 'Fanart.tv API key is valid.'
		if response.status_code in (401, 403):
			return False, 'Fanart.tv API key is invalid.'
		return False, 'Fanart.tv returned HTTP %s.' % response.status_code
	except Exception as e:
		return False, 'Fanart.tv request failed.[CR]%s' % str(e)

def artwork_fallback(media_type, api_key, tmdb_id=None, imdb_id=None, tvdb_id=None):
	"""Art for empty TMDb slots. One request. Returns {} if unused, failed, or nothing to map."""
	if api_key in _EMPTY_IDS: return {}
	if media_type == 'movie':
		data = None
		if tmdb_id not in _EMPTY_IDS: data = _get('movies/%s' % tmdb_id, api_key)
		if not data and imdb_id not in _EMPTY_IDS: data = _get('movies/%s' % imdb_id, api_key)
		if not data: return {}
		return {
			'poster': _best(data.get('movieposter')),
			'fanart': _best(data.get('moviebackground')),
			'landscape': _best(data.get('moviethumb')) or _best(data.get('moviebackground')),
			'clearlogo': _best(data.get('hdmovielogo')) or _best(data.get('movielogo')),
		}
	if media_type == 'tvshow':
		if tvdb_id in _EMPTY_IDS: return {}
		data = _get('tv/%s' % tvdb_id, api_key)
		if not data: return {}
		return {
			'poster': _best(data.get('tvposter')),
			'fanart': _best(data.get('showbackground')),
			'landscape': _best(data.get('tvthumb')) or _best(data.get('showbackground')),
			'clearlogo': _best(data.get('hdtvlogo')) or _best(data.get('clearlogo')),
		}
	return {}
