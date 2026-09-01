# -*- coding: utf-8 -*-
from caches.main_cache import main_cache
from modules.native_torrents import instance_base_url, search_stremio_streams, stremio_stream_url

TORRENTIO_URLS = (
	'https://torrentio.strem.fun',
)


def torrentio_base_url():
	return instance_base_url('torrentio.url', TORRENTIO_URLS, 'torrentio.custom_url', 1)


def torrentio_stream_url(imdb_id, media_type, season=None, episode=None):
	return stremio_stream_url(torrentio_base_url(), imdb_id, media_type, season, episode)


def clear_torrentio_cache():
	try:
		main_cache.delete_like('TORRENTIO_%')
		return True
	except Exception:
		return False


def search_streams(imdb_id, media_type, season=None, episode=None, timeout=15, expiration=24):
	return search_stremio_streams(
		torrentio_stream_url(imdb_id, media_type, season, episode),
		'TORRENTIO', timeout=timeout, expiration=expiration, log_name='torrentio api')
