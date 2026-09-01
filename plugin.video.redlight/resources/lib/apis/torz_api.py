# -*- coding: utf-8 -*-
from caches.main_cache import main_cache
from modules.kodi_utils import logger
from modules.native_torrents import bytes_to_gb, instance_base_url, json_http, normalize_info_hash

TORZ_URLS = (
	'https://stremthru.stremio.ru',
	'https://stremthru.13377001.xyz',
	'https://stremthrufortheweebs.midnightignite.me',
)


def torz_base_url():
	return instance_base_url('torz.url', TORZ_URLS, 'torz.custom_url', 3)


def torz_search_url(imdb_id, media_type, season=None, episode=None):
	base = torz_base_url()
	if not base or not imdb_id:
		return None
	imdb_id = str(imdb_id).strip()
	if '/v0/torrents' in base:
		return base
	if media_type == 'movie':
		return '%s/v0/torrents?sid=%s' % (base, imdb_id)
	return '%s/v0/torrents?sid=%s:%s:%s' % (base, imdb_id, int(season), int(episode))


def clear_torz_cache():
	try:
		main_cache.delete_like('TORZ_%')
		return True
	except Exception:
		return False


def _parse_item(raw):
	info_hash = normalize_info_hash(raw.get('hash') or '')
	name = raw.get('name') or ''
	if not info_hash or not name:
		return None
	try:
		seeders = int(raw.get('seeders') or 0)
	except Exception:
		seeders = 0
	return {
		'hash': info_hash,
		'name': name,
		'size': bytes_to_gb(raw.get('size')),
		'seeders': seeders,
	}


def search_streams(imdb_id, media_type, season=None, episode=None, timeout=15, expiration=24):
	url = torz_search_url(imdb_id, media_type, season, episode)
	if not url:
		return []
	cache_key = 'TORZ_%s' % url
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	items = []
	try:
		response = json_http().get(url, timeout=max(5, int(timeout)))
		response.raise_for_status()
		payload = response.json() or {}
		raw_items = ((payload.get('data') or {}).get('items')) or []
		for raw in raw_items:
			parsed = _parse_item(raw)
			if parsed:
				items.append(parsed)
	except Exception as e:
		logger('torz api', '%s (%s)' % (type(e).__name__, url))
		return []
	main_cache.set(cache_key, items, expiration=expiration)
	return items
