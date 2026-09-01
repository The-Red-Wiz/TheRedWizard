# -*- coding: utf-8 -*-
import re
from caches.main_cache import main_cache
from caches.settings_cache import get_setting
from modules.kodi_utils import make_session, logger
from modules.native_torrents import USER_AGENT, normalize_info_hash, parse_size_gb, parse_seeders

COMET_URLS = (
	'https://comet.feels.legal',
	'https://comet.stremio.ru',
	'https://cometfortheweebs.midnightignite.me',
)
_INFO_LINE = re.compile(r'(💾|👤|⚙️)')
_session = None


def _http():
	global _session
	if _session is None:
		_session = make_session('https://')
		_session.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/json'})
	return _session


def comet_base_url():
	try:
		idx = int(get_setting('redlight.comet.url', '0'))
	except (TypeError, ValueError):
		idx = 0
	if idx == 3:
		custom = (get_setting('redlight.comet.custom_url', '') or '').strip().rstrip('/')
		return custom
	if idx < 0 or idx >= len(COMET_URLS):
		idx = 0
	return COMET_URLS[idx]


def comet_stream_url(imdb_id, media_type, season=None, episode=None):
	base = comet_base_url()
	if not base or not imdb_id:
		return None
	imdb_id = str(imdb_id).strip()
	if media_type == 'movie':
		path = '/stream/movie/%s.json' % imdb_id
	else:
		path = '/stream/series/%s:%s:%s.json' % (imdb_id, int(season), int(episode))
	if '/stream/' in base:
		return base
	return '%s%s' % (base, path)


def _cache_key(url):
	return 'COMET_%s' % url


def clear_comet_cache():
	try:
		main_cache.delete_like('COMET_%')
		return True
	except Exception:
		return False


def _parse_stream(raw):
	info_hash = normalize_info_hash(raw.get('infoHash') or '')
	if not info_hash:
		info_hash = normalize_info_hash(raw.get('url') or '')
	if not info_hash:
		return None
	description = raw.get('description') or raw.get('title') or ''
	description = str(description).replace('┈➤', '\n')
	lines = [i.strip() for i in description.split('\n') if i.strip()]
	hints = raw.get('behaviorHints') or {}
	name = hints.get('filename') or raw.get('behaviorHints', {}).get('filename')
	if not name and lines:
		name = lines[0]
	if not name:
		name = raw.get('name') or info_hash
	info_line = ''
	for line in lines:
		if _INFO_LINE.search(line):
			info_line = line
			break
	if not info_line:
		info_line = description
	size = parse_size_gb(info_line)
	if not size:
		try:
			video_size = float(hints.get('videoSize') or 0)
			if video_size > 1048576:
				size = round(video_size / 1073741824.0, 2)
		except Exception:
			size = 0.0
	return {
		'hash': info_hash,
		'name': name,
		'size': size,
		'seeders': parse_seeders(info_line),
		'description': description,
	}


def search_streams(imdb_id, media_type, season=None, episode=None, timeout=15, expiration=24):
	url = comet_stream_url(imdb_id, media_type, season, episode)
	if not url:
		return []
	cache_key = _cache_key(url)
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	streams = []
	try:
		response = _http().get(url, timeout=max(5, int(timeout)))
		response.raise_for_status()
		payload = response.json() or {}
		for raw in payload.get('streams') or []:
			parsed = _parse_stream(raw)
			if parsed:
				streams.append(parsed)
	except Exception as e:
		logger('comet api', '%s (%s)' % (type(e).__name__, url))
		return []
	main_cache.set(cache_key, streams, expiration=expiration)
	return streams
