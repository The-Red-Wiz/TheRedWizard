# -*- coding: utf-8 -*-
from urllib.parse import urlencode
from caches.main_cache import main_cache
from modules.kodi_utils import logger
from modules.native_torrents import bytes_to_gb, json_http, normalize_info_hash

ANIMETOSHO_JSON = 'https://feed.animetosho.org/json'


def clear_animetosho_cache():
	try:
		main_cache.delete_like('ANIMETOSHO_%')
		return True
	except Exception:
		return False


def _parse_item(raw):
	info_hash = normalize_info_hash(raw.get('info_hash') or '')
	name = raw.get('torrent_name') or raw.get('title') or ''
	if not info_hash or not name:
		return None
	try:
		seeders = int(raw.get('seeders') or 0)
	except Exception:
		seeders = 0
	return {
		'hash': info_hash,
		'name': name,
		'size': bytes_to_gb(raw.get('total_size')),
		'seeders': seeders,
	}


def search(query, timeout=10, expiration=24):
	query = (query or '').strip()
	if not query:
		return []
	url = '%s?%s' % (ANIMETOSHO_JSON, urlencode({'q': query}))
	cache_key = 'ANIMETOSHO_%s' % url
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	results = []
	try:
		response = json_http().get(url, timeout=max(5, int(timeout)))
		response.raise_for_status()
		payload = response.json()
		if not isinstance(payload, list):
			payload = []
		seen = set()
		for raw in payload:
			parsed = _parse_item(raw)
			if not parsed or parsed['hash'] in seen:
				continue
			seen.add(parsed['hash'])
			results.append(parsed)
	except Exception as e:
		logger('animetosho api', '%s (%s)' % (type(e).__name__, query))
		return []
	main_cache.set(cache_key, results, expiration=expiration)
	return results
