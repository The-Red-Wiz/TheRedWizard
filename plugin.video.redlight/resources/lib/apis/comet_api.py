# -*- coding: utf-8 -*-
from caches.main_cache import main_cache
from modules.native_torrents import instance_base_url, search_stremio_streams, stremio_stream_url

COMET_URLS = (
	'https://comet.feels.legal',
	'https://comet.stremio.ru',
	'https://cometfortheweebs.midnightignite.me',
)


def comet_base_url():
	return instance_base_url('comet.url', COMET_URLS, 'comet.custom_url', 3)


def comet_stream_url(imdb_id, media_type, season=None, episode=None):
	return stremio_stream_url(comet_base_url(), imdb_id, media_type, season, episode)


def clear_comet_cache():
	try:
		main_cache.delete_like('COMET_%')
		return True
	except Exception:
		return False


def search_streams(imdb_id, media_type, season=None, episode=None, timeout=15, expiration=24):
	return search_stremio_streams(
		comet_stream_url(imdb_id, media_type, season, episode),
		'COMET', timeout=timeout, expiration=expiration, log_name='comet api')
