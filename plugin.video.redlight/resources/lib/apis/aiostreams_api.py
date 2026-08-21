# -*- coding: utf-8 -*-
ENABLED = True

import json
import time
import requests
from urllib.parse import urlencode
from caches.settings_cache import get_setting
from modules import kodi_utils
from modules.kodi_utils import logger

# id, short label, base URL (None = Custom; Custom is last in the picker).
# Preset ids are stable — never renumber existing entries (saved settings + per-instance profiles).
PRESETS = (
	('0', 'Kuu', 'https://aiostreams.stremio.ru'),
	('1', 'Viren', 'https://aiostreams.viren070.me'),
	('2', 'Yeb', 'https://aiostreams.fortheweak.cloud'),
	('3', 'Midnight', 'https://aiostreamsfortheweebsstable.midnightignite.me'),
	('4', 'Custom', None),
	# Public host returns 403 Search API is disabled — hidden from picker until re-enabled.
	('5', 'ElfHosted', 'https://aiostreams.elfhosted.com'),
)

INSTANCE_LABELS = {preset_id: label for preset_id, label, url in PRESETS}
INSTANCE_IDS = tuple(preset_id for preset_id, _, _ in PRESETS)
CUSTOM_INSTANCE_ID = '4'
# Keep preset id + credentials; omit from dropdown only.
PICKER_HIDDEN_IDS = frozenset({'5'})
PROFILE_SETTING = 'aiostreams.profiles'

_public_presets = [(preset_id, url) for preset_id, _, url in PRESETS if url]
PUBLIC_INSTANCES = tuple(url for _, url in _public_presets)
_PUBLIC_INDEX = {preset_id: index for index, (preset_id, _) in enumerate(_public_presets)}

def _empty_profile():
	return {'username': 'empty_setting', 'password': 'empty_setting', 'custom_url': ''}

def _load_profiles_raw():
	try:
		raw = get_setting('redlight.%s' % PROFILE_SETTING, '{}') or '{}'
		data = json.loads(raw)
		return data if isinstance(data, dict) else {}
	except: return {}

def _save_profiles(profiles):
	from caches.settings_cache import set_setting
	set_setting(PROFILE_SETTING, json.dumps(profiles))

def _ensure_profiles(profiles):
	for iid in INSTANCE_IDS:
		entry = profiles.get(iid)
		if not isinstance(entry, dict):
			profiles[iid] = _empty_profile()
			continue
		profiles[iid] = {
			'username': entry.get('username') or 'empty_setting',
			'password': entry.get('password') or 'empty_setting',
			'custom_url': (entry.get('custom_url') or '').strip(),
		}
	return profiles

def read_active_credentials():
	username = get_setting('redlight.aiostreams.username', 'empty_setting')
	password = get_setting('redlight.aiostreams.password', 'empty_setting')
	custom_url = (get_setting('redlight.aiostreams.custom_url', '') or '').strip()
	return {'username': username, 'password': password, 'custom_url': custom_url}

def _credentials_configured(credentials):
	return credentials['username'] not in ('empty_setting', '') or credentials['password'] not in ('empty_setting', '')

def _profiles_all_empty(profiles):
	for iid in INSTANCE_IDS:
		entry = profiles.get(iid, _empty_profile())
		if _credentials_configured(entry) or entry.get('custom_url'):
			return False
	return True

def ensure_profiles_initialized():
	profiles = _ensure_profiles(_load_profiles_raw())
	active = read_active_credentials()
	if _profiles_all_empty(profiles) and _credentials_configured(active):
		profiles[str(instance_id())] = dict(active)
		_save_profiles(profiles)
	return profiles

def persist_active_profile(instance_id_value=None):
	iid = str(instance_id_value if instance_id_value is not None else instance_id())
	profiles = _ensure_profiles(_load_profiles_raw())
	profiles[iid] = read_active_credentials()
	_save_profiles(profiles)

def apply_profile(instance_id_value):
	from caches.settings_cache import default_setting_values, property_safe_string, settings_cache
	profiles = _ensure_profiles(_load_profiles_raw())
	profile = profiles.get(str(instance_id_value), _empty_profile())
	for setting_id, value in (
		('aiostreams.username', profile['username']),
		('aiostreams.password', profile['password']),
		('aiostreams.custom_url', profile['custom_url']),
	):
		info = default_setting_values(setting_id)
		settings_cache.write_db(setting_id, value, info)
		try:
			settings_cache.set_memory_cache(setting_id, property_safe_string(value))
		except: pass

def instance_id():
	return str(get_setting('redlight.aiostreams.instance', '0'))

def base_url():
	current = instance_id()
	if current == CUSTOM_INSTANCE_ID:
		url = get_setting('redlight.aiostreams.custom_url', '').strip()
	else:
		index = _PUBLIC_INDEX.get(current, 0)
		url = PUBLIC_INSTANCES[index]
	return url.rstrip('/') if url else ''

def refresh_base_url_property():
	url = base_url()
	kodi_utils.set_property('redlight.aiostreams.base_url', url or '(not set — choose instance or enter Custom URL)')

def sync_instance_display_name():
	label = INSTANCE_LABELS.get(instance_id(), INSTANCE_LABELS['0'])
	kodi_utils.set_property('redlight.aiostreams.instance_name', label)

def active_instance_label():
	"""Short preset label for the instance used at scrape time (ElfHosted, Kuu, Midnight, etc.)."""
	return INSTANCE_LABELS.get(instance_id(), INSTANCE_LABELS['0'])

def instance_picker_list():
	"""Instance dropdown rows: alphabetical by preset name, Custom always last."""
	items = []
	for preset_id, label, url in PRESETS:
		if preset_id == CUSTOM_INSTANCE_ID or preset_id in PICKER_HIDDEN_IDS:
			continue
		items.append((label.lower(), '%s — %s' % (label, url), preset_id))
	items.sort(key=lambda entry: entry[0])
	picker = [(display, preset_id) for _, display, preset_id in items]
	picker.append(('Custom — set URL below', CUSTOM_INSTANCE_ID))
	return picker

def refresh_settings_properties():
	kodi_utils.set_property('redlight.aiostreams.available', 'true' if ENABLED else 'false')
	ensure_profiles_initialized()
	sync_instance_display_name()
	refresh_base_url_property()

def auth():
	username = get_setting('redlight.aiostreams.username', 'empty_setting')
	password = get_setting('redlight.aiostreams.password', 'empty_setting')
	if username in ('empty_setting', '') or password in ('empty_setting', ''): return None
	return (username, password)

def flatten_result(raw):
	"""Merge streamData, parsedFile, and top-level fields (Magneto player pattern)."""
	item = dict(raw)
	item.pop('sources', None)
	stream_data = item.pop('streamData', None) or {}
	if not isinstance(stream_data, dict): stream_data = {}
	parsed = item.pop('parsedFile', None) or {}
	if not isinstance(parsed, dict): parsed = {}
	info = item.pop('info', None) or {}
	if not isinstance(info, dict): info = {}
	merged = {**parsed, **stream_data, **info, **item}
	service = merged.get('service')
	if isinstance(service, dict) and merged.get('cached') is None and 'cached' in service:
		merged['cached'] = service.get('cached')
	return merged

def _norm_source_key(value):
	return str(value or '').strip().lower().replace(' ', '').replace('_', '').replace('.', '').replace('-', '')

def _service_id(merged):
	def _valid_service(val):
		return val and not _is_generic_addon_name(val)
	service = merged.get('service')
	if isinstance(service, dict):
		val = service.get('id') or service.get('name')
		if _valid_service(val): return val
	elif _valid_service(service):
		return service
	for key in ('serviceId', 'service_id', 'debridService', 'debrid_service'):
		val = merged.get(key)
		if _valid_service(val): return val
	info = merged.get('info')
	if isinstance(info, dict):
		for key in ('debridService', 'debrid_service', 'service', 'serviceId', 'service_id'):
			val = info.get(key)
			if _valid_service(val): return val
	return None

_GENERIC_ADDON_KEYS = frozenset(_norm_source_key(x) for x in (
	'aiostreams', 'aiostream', 'aio streams', 'aio-streams', 'aio',
))

def _is_generic_addon_name(value):
	key = _norm_source_key(value)
	if not key: return True
	if key in _GENERIC_ADDON_KEYS: return True
	return key.startswith('aiostream')

def _addon_id(merged):
	for key in ('addon', 'addonName', 'addon_name'):
		val = merged.get(key)
		if isinstance(val, dict):
			val = val.get('name') or val.get('id')
		if val and not _is_generic_addon_name(val):
			return val
	return None

def _panel_label(short):
	return 'AIO / %s' % short

def _is_cached(merged):
	cached = merged.get('cached')
	if cached is None:
		service = merged.get('service')
		if isinstance(service, dict):
			cached = service.get('cached')
	return cached is True

def _is_usenet_stream(merged):
	stream_type = str(merged.get('type') or '').lower()
	return 'usenet' in stream_type or bool(merged.get('nzbUrl'))

_DEBRID_CACHE_HOSTER_TOKENS = frozenset(_norm_source_key(x) for x in (
	'realdebrid', 'alldebrid', 'premiumize', 'torbox', 'offcloud',
	'easydebrid', 'debrider', 'debridlink',
))

def _hoster_uses_debrid_cache(merged):
	service = _service_id(merged)
	if not service: return False
	return _norm_source_key(service) in _DEBRID_CACHE_HOSTER_TOKENS

def _debrid_short(short, merged):
	if _is_cached(merged):
		return '%s+' % short
	return short

def _aio_debrid_badge(short, name, icon, merged):
	short = _debrid_short(short, merged)
	return _panel_label(short), short, name, icon

def _short_label(value, limit=8):
	short = str(value or '').strip().upper()
	if len(short) > limit: short = short[:limit]
	return short

_SERVICE_LABELS = (
	('realdebrid', 'RD', 'Real-Debrid', 'real-debrid'),
	('alldebrid', 'AD', 'AllDebrid', 'alldebrid'),
	('premiumize', 'PM', 'Premiumize', 'premiumize'),
	('torbox', 'TB', 'TorBox', 'torbox'),
	('offcloud', 'OC', 'Offcloud', 'offcloud'),
	('easynews', 'EN', 'EasyNews', 'easynews'),
	('easydebrid', 'ED', 'EasyDebrid', 'easydebrid'),
	('debrider', 'DR', 'Debrider', 'debrider'),
	('debridlink', 'DL', 'Debrid-Link', 'debridlink'),
	('putio', 'Putio', 'Putio', 'putio'),
	('pikpak', 'PK', 'PikPak', 'pikpak'),
	('seedr', 'Seedr', 'Seedr', 'seedr'),
	('nzbdav', 'NZB', 'NZBDav', 'nzbdav'),
	('altmount', 'Alt', 'AltMount', 'altmount'),
	('stremthru_newz', 'SNZ', 'StremThru', 'stremthru_newz'),
)

_ADDON_LABELS = (
	('torrentio', 'Torrentio', 'torrentio'),
	('comet', 'Comet', 'comet'),
	('mediafusion', 'MF', 'mediafusion'),
	('jackett', 'Jackett', 'jackett'),
	('prowlarr', 'Prowlarr', 'prowlarr'),
)

def _lookup_label(value, labels):
	key = _norm_source_key(value)
	for entry in labels:
		if key in (_norm_source_key(entry[0]), _norm_source_key(entry[3])):
			return entry[1], entry[2], entry[3]
	return None

def _label_from_url(url):
	try:
		from urllib.parse import urlparse
		host = (urlparse(url).netloc or '').lower()
	except: return None
	if not host: return None
	for token, short, name, icon in _SERVICE_LABELS + _ADDON_LABELS:
		if token in host.replace('-', '').replace('.', ''):
			return short, name, icon
	return None

def inner_source_display(merged):
	"""Return (panel_label, short, name, icon_key) for an AIOStreams result row."""
	service = _service_id(merged)
	if service:
		match = _lookup_label(service, _SERVICE_LABELS)
		if match:
			short, name, icon = match
			return _aio_debrid_badge(short, name, icon, merged)
		short = _debrid_short(_short_label(service, 10), merged)
		return _panel_label(short), short, str(service), 'aiostreams'
	if _is_usenet_stream(merged):
		return 'AIO+', 'AIO+', 'Usenet', 'aiostreams'
	addon = _addon_id(merged)
	if addon:
		match = _lookup_label(addon, _ADDON_LABELS)
		if match:
			short, name, icon = match
			return _panel_label(short), short, name, icon
		name = str(addon).strip()
		short = name if len(name) <= 10 else name[:10]
		return _panel_label(short), short, name, 'aiostreams'
	url_match = _label_from_url(merged.get('url') or merged.get('url_dl') or merged.get('nzbUrl') or '')
	if url_match:
		short, name, icon = url_match
		return _panel_label(short), short, name, icon
	indexer = merged.get('indexer')
	if indexer:
		name = str(indexer).strip()
		short = name if len(name) <= 10 else name[:10]
		return _panel_label(short), short, name, 'aiostreams'
	return 'AIO', 'AIO', 'AIO', 'aiostreams'

_TRACKER_SITE_HINTS = (
	('torrentgalaxy', 'TorrentGalaxy'),
	('thepiratebay', 'The Pirate Bay'),
	('piratebay', 'The Pirate Bay'),
	('1337x', '1337x'),
	('rarbg', 'RARBG'),
	('yts', 'YTS'),
	('eztv', 'EZTV'),
	('kickasstorrents', 'KickassTorrents'),
	('limetorrents', 'LimeTorrents'),
	('nyaa', 'Nyaa'),
	('knaben', 'Knaben'),
	('torrentleech', 'TorrentLeech'),
	('iptorrents', 'IPTorrents'),
)

def _format_site_name(value):
	text = str(value or '').strip()
	if not text: return ''
	key = _norm_source_key(text)
	for token, display in _TRACKER_SITE_HINTS:
		if key == _norm_source_key(token) or _norm_source_key(token) in key:
			return display
	if text.islower() or '_' in text or '-' in text:
		return text.replace('_', ' ').replace('-', ' ').title()
	return text

def _site_from_tracker_entry(entry):
	if not entry: return ''
	text = str(entry).strip()
	if text.startswith(('udp:', 'wss:', 'ws:')): return ''
	try:
		from urllib.parse import urlparse
		if '://' in text:
			host = (urlparse(text).netloc or '').lower()
			if host.startswith('www.'): host = host[4:]
			host_key = host.replace('-', '').replace('.', '')
			for token, display in _TRACKER_SITE_HINTS:
				if token in host_key:
					return display
			parts = [p for p in host.split('.') if p and p not in ('com', 'org', 'net', 'to', 'me', 'io', 'cc', 'app')]
			if parts:
				return parts[0].title()
	except: pass
	if len(text) < 48 and '://' not in text:
		return _format_site_name(text)
	return ''

def origin_site_label(raw):
	"""Indexer / tracker site name for the Site row (TorrentGalaxy, etc.)."""
	item = flatten_result(raw) if isinstance(raw, dict) and 'streamData' in raw else raw
	indexer = item.get('indexer')
	if indexer:
		site = _format_site_name(indexer)
		if site: return site
	sources = item.get('sources')
	if isinstance(sources, list):
		for entry in sources:
			site = _site_from_tracker_entry(entry)
			if site: return site
	addon = _addon_id(item)
	if addon and not _service_id(item):
		return _format_site_name(addon) or str(addon).strip()
	return ''

def hoster_label(raw):
	"""Hoster row label for AIOStreams results."""
	item = flatten_result(raw) if isinstance(raw, dict) and 'streamData' in raw else raw
	if _service_id(item) and not _hoster_uses_debrid_cache(item):
		return 'DIRECT'
	if _is_usenet_stream(item) and not _hoster_uses_debrid_cache(item):
		return 'USENET'
	cached = item.get('cached')
	if cached is None:
		service = item.get('service')
		if isinstance(service, dict):
			cached = service.get('cached')
	if cached is True:
		return '[B]CACHED[/B]'
	if cached is False:
		return 'UNCACHED'
	stream_type = str(item.get('type') or '').lower()
	if stream_type == 'p2p' or item.get('infoHash'):
		return 'TORRENT'
	torrent = item.get('torrent')
	if isinstance(torrent, dict) and torrent.get('infoHash'):
		return 'TORRENT'
	return 'DIRECT'

def _release_group_from_filename(filename):
	import re
	base = str(filename or '').strip()
	if not base: return ''
	base = re.sub(r'\.(mkv|mp4|avi|m4v|ts|m2ts|wmv|webm)$', '', base, flags=re.I)
	match = re.search(r'[-\.]([A-Za-z0-9]{2,12})$', base)
	if not match: return ''
	candidate = match.group(1)
	noise = {
		'1080p', '720p', '2160p', '1440p', '480p', '576p', '4k', 'uhd', 'hd', 'sd', 'web', 'webdl', 'webrip', 'webdlrip',
		'bluray', 'blu', 'ray', 'remux', 'h264', 'h265', 'x264', 'x265', 'hevc', 'avc', 'aac', 'ddp', 'dts', 'atmos',
		'proper', 'repack', 'internal', 'subs', 'subbed', 'dubbed',
	}
	if candidate.lower() in noise: return ''
	return candidate

def release_group_label(merged, filename=''):
	"""Scene/release group from AIO parsedFile (Hone, NTb, Flux, etc.)."""
	for key in ('releaseGroup', 'releasegroup', 'group'):
		val = merged.get(key)
		if val and str(val).strip(): return str(val).strip()
	parsed = merged.get('parsedFile')
	if isinstance(parsed, dict):
		for key in ('releaseGroup', 'releasegroup', 'group'):
			val = parsed.get(key)
			if val and str(val).strip(): return str(val).strip()
	return _release_group_from_filename(filename or merged.get('filename') or merged.get('name') or '')

def playback_headers(item):
	headers = item.get('request_headers') or item.get('requestHeaders')
	return headers if isinstance(headers, dict) and headers else None

def _format_payload_entries(items):
	lines = []
	for item in items or ():
		if not isinstance(item, dict):
			lines.append(str(item))
			continue
		title = item.get('title') or item.get('name') or 'entry'
		desc = item.get('description') or item.get('message') or ''
		lines.append('%s: %s' % (title, desc) if desc else str(title))
	return lines

_AIO_RETRY_PAUSE_SEC = 2.0

def _aio_connect_timeout(read_timeout):
	"""Seconds to wait for TCP/TLS; keep modest so read budget stays on the instance."""
	return min(15, max(5, int(read_timeout) // 4))

def _aio_read_timeout(read_timeout):
	return max(1, int(read_timeout))

def _aio_request_timeouts(read_timeout):
	read_timeout = max(1, int(read_timeout))
	return (_aio_connect_timeout(read_timeout), read_timeout)

def _timeout_message(exc):
	try:
		parts = []
		seen = set()
		current = exc
		while current is not None and id(current) not in seen:
			seen.add(id(current))
			parts.append(str(current))
			for arg in getattr(current, 'args', ()) or ():
				parts.append(str(arg))
			current = getattr(current, '__cause__', None) or getattr(current, '__context__', None)
		return ' '.join(parts).lower()
	except:
		return str(exc).lower()

def _timeout_kind(exc):
	if isinstance(exc, requests.exceptions.ConnectTimeout):
		return 'connect'
	if isinstance(exc, requests.exceptions.ReadTimeout):
		return 'read'
	if isinstance(exc, requests.exceptions.Timeout):
		return 'timeout'
	text = _timeout_message(exc)
	if 'read operation timed out' in text or 'read timed out' in text:
		return 'read'
	if 'connect' in text and 'timed out' in text:
		return 'connect'
	if isinstance(exc, requests.exceptions.ConnectionError) and 'timed out' in text:
		return 'read'
	return None

def _retryable_aio_timeout(exc):
	return _timeout_kind(exc) is not None

def _request_url(exc, fallback):
	try:
		req = getattr(exc, 'request', None)
		if req is not None and getattr(req, 'url', None):
			return req.url
	except:
		pass
	return fallback

def _log_aio_request_error(instance, elapsed_ms, kind, exc, search_link):
	url = _request_url(exc, search_link)
	if kind:
		logger('aiostreams API', '%s timeout | instance=%s | elapsed=%sms | %s | %s' % (
			kind, instance, elapsed_ms, url, exc))
	else:
		logger('aiostreams API', 'request failed | instance=%s | elapsed=%sms | %s | %s' % (
			instance, elapsed_ms, url, exc))

def _aio_get(search_link, params, credentials, read_timeout, fresh_connection=False):
	kwargs = {'params': params, 'auth': credentials, 'timeout': _aio_request_timeouts(read_timeout)}
	if fresh_connection:
		session = requests.Session()
		try:
			session.headers['Connection'] = 'close'
			return session.get(search_link, **kwargs)
		finally:
			try:
				session.close()
			except:
				pass
	return requests.get(search_link, **kwargs)

def _log_http_error(response, search_link, instance=None):
	prefix = 'instance=%s | ' % instance if instance else ''
	try:
		body = response.json()
		err = body.get('error')
		if isinstance(err, dict):
			logger('aiostreams API', '%sHTTP %s | %s: %s | %s' % (
				prefix, response.status_code, err.get('code', ''), err.get('message', ''), response.url))
			return
		if isinstance(err, str) and err.strip():
			logger('aiostreams API', '%sHTTP %s | %s | %s' % (prefix, response.status_code, err.strip(), response.url))
			return
		detail = body.get('detail')
		if detail:
			logger('aiostreams API', '%sHTTP %s | %s | %s' % (prefix, response.status_code, detail, response.url))
			return
		if body.get('success') is False:
			logger('aiostreams API', '%sHTTP %s | success=false | %s' % (prefix, response.status_code, response.url))
			return
	except: pass
	logger('aiostreams API', '%sHTTP %s | %s' % (prefix, response.status_code, getattr(response, 'url', search_link)))

def _log_search_response(response, payload, results, instance=None):
	elapsed_ms = int(response.elapsed.total_seconds() * 1000)
	filtered = payload.get('filtered', 0) or 0
	errors = payload.get('errors') or []
	statistics = payload.get('statistics') or []
	logger('aiostreams API', 'instance=%s | %sms | %s results | filtered=%s | %s' % (
		instance or active_instance_label(), elapsed_ms, len(results), filtered, response.url))
	for line in _format_payload_entries(errors):
		logger('aiostreams API', 'source error: %s' % line)
	for line in _format_payload_entries(statistics):
		logger('aiostreams API', 'statistic: %s' % line)
	if not results and filtered:
		logger('aiostreams API', 'all streams removed by instance filters (filtered=%s)' % filtered)
	if not results and not errors and not statistics:
		logger('aiostreams API', 'empty payload — instance returned no results, errors, or statistics')

def _parse_api_errors(payload):
	return [': '.join(str(v) for v in i.values()) for i in payload.get('errors', []) if isinstance(i, dict)]

def _search_id(imdb_id=None, tmdb_id=None):
	"""Prefer IMDb (tt…); fall back to tmdb:XXXX when IMDb is missing."""
	imdb = str(imdb_id or '').strip()
	if imdb and imdb not in ('None', '0', 'empty_setting') and imdb.lower().startswith('tt'):
		return imdb
	tmdb = str(tmdb_id or '').strip()
	if tmdb and tmdb not in ('None', '0', 'empty_setting'):
		try:
			return 'tmdb:%s' % int(tmdb)
		except Exception:
			pass
	return None

def search(media_type, imdb_id=None, season=None, episode=None, timeout=30, tmdb_id=None):
	credentials = auth()
	if not credentials:
		logger('aiostreams API', 'search skipped — username/password not configured')
		return [], ['AIOStreams username/password not configured']
	media_id = _search_id(imdb_id, tmdb_id)
	if not media_id:
		logger('aiostreams API', 'search skipped — missing IMDb and TMDb id')
		return [], ['Missing IMDb/TMDb id for AIOStreams search']
	base = base_url()
	if not base:
		logger('aiostreams API', 'search skipped — no instance URL configured')
		return [], ['No AIOStreams instance URL configured']
	if media_type == 'movie':
		params = {'type': 'movie', 'id': media_id}
	else:
		params = {'type': 'series', 'id': '%s:%s:%s' % (media_id, season, episode)}
	search_link = '%s/api/v1/search' % base
	instance = active_instance_label()
	read_s = _aio_read_timeout(timeout)
	last_exc = None
	for attempt in range(2):
		attempt_connect_s = _aio_connect_timeout(read_s)
		started = time.perf_counter()
		try:
			response = _aio_get(search_link, params, credentials, read_s, fresh_connection=True)
			if not response.ok:
				_log_http_error(response, search_link, instance)
				response.raise_for_status()
			body = response.json()
			if body.get('success') is False:
				err = body.get('error') or {}
				if isinstance(err, dict):
					logger('aiostreams API', 'instance=%s | success=false | %s: %s | %s' % (
						instance, err.get('code', ''), err.get('message', ''), response.url))
				elif isinstance(err, str) and err.strip():
					logger('aiostreams API', 'instance=%s | success=false | %s | %s' % (instance, err.strip(), response.url))
			payload = body.get('data', {}) or {}
			results = payload.get('results', []) or []
			errors = _parse_api_errors(payload)
			if attempt:
				logger('aiostreams API', 'instance=%s | retry succeeded | fresh_connection | connect=%ss read=%ss | %s' % (
					instance, attempt_connect_s, read_s, response.url))
			_log_search_response(response, payload, results, instance)
			return results, errors
		except requests.exceptions.RequestException as e:
			last_exc = e
			elapsed_ms = int((time.perf_counter() - started) * 1000)
			kind = _timeout_kind(e)
			if attempt == 0 and _retryable_aio_timeout(e):
				logger('aiostreams API', '%s timeout | instance=%s | elapsed=%sms | connect=%ss read=%ss | %s | retrying once (fresh connection, read=%ss, pause=%ss)' % (
					kind, instance, elapsed_ms, attempt_connect_s, read_s, _request_url(e, search_link), read_s, _AIO_RETRY_PAUSE_SEC))
				time.sleep(_AIO_RETRY_PAUSE_SEC)
				continue
			_log_aio_request_error(instance, elapsed_ms, kind, e, search_link)
			return [], []
	if last_exc is not None:
		_log_aio_request_error(instance, 0, _timeout_kind(last_exc), last_exc, search_link)
	return [], []

def is_direct_easynews_item(item):
	"""True for AIOStreams EasyNews rows (AIO / EN or EN+ badge)."""
	if not item or not isinstance(item, dict):
		return False
	if item.get('scrape_provider') != 'aiostreams':
		return False
	# Cached EN badges use EN+ via _debrid_short — strip the cache marker.
	short = str(item.get('aio_source') or '').strip().upper().rstrip('+')
	if short == 'EN':
		return True
	name = str(item.get('aio_source_name') or '').strip().lower()
	if 'easynews' in name:
		return True
	icon = str(item.get('aio_source_icon') or '').strip().lower()
	if icon == 'easynews':
		return True
	url = str(item.get('url_dl') or item.get('url') or '').lower()
	return 'easynews' in url

_PLACEHOLDER_STREAM_MARKERS = (
	'/static/downloading.mp4',
	'/static/downloading.',
	'downloading.mp4',
)

def _is_placeholder_stream_url(url):
	lower = (url or '').lower().split('|', 1)[0]
	return any(marker in lower for marker in _PLACEHOLDER_STREAM_MARKERS)

def _probe_final_url(url, headers=None, timeout=12):
	try:
		resp = requests.get(url, headers=headers or {}, allow_redirects=True, stream=True, timeout=timeout)
		try:
			# 404/5xx on the AIO wrapper must not be handed to Kodi as a playable URL —
			# RETRYx / failover need a failed resolve (None), not one dead OpenFile.
			if resp.status_code >= 400:
				return None
			return (resp.url or url).strip()
		finally:
			resp.close()
	except Exception as exc:
		logger('aiostreams playback probe', str(exc))
		return None

def _append_play_options(url, headers=None, seekable=None):
	"""Build a Kodi play URL with optional request headers and seekable=0."""
	parts = []
	if headers:
		parts.append(urlencode(headers))
	if seekable is not None:
		parts.append('seekable=%s' % seekable)
	if not parts:
		return url
	return '%s|%s' % (url, '&'.join(parts))

def _resolve_easynews_playback(url, headers=None):
	"""Materialize AIO EN → EasyNews CDN; apply No Seek when enabled.

	Each call follows redirects again so RETRYx attempts can land a different farm.
	Cannot use Red Light's native EasyNews auth resolve — AIO's link is already
	signed/wrapped by the instance's EN credentials.
	"""
	from modules.settings import easynews_playback_method
	final = _probe_final_url(url, headers)
	if not final:
		return None
	if _is_placeholder_stream_url(final):
		logger('aiostreams playback', 'rejected EN placeholder stream: %s' % final)
		return None
	play_url = final
	out_headers = None
	# Direct EasyNews CDN URLs are signed; keep AIO headers only if still on the AIO host.
	if 'easynews.com' not in play_url.lower() and headers:
		out_headers = headers
	use_non_seek = easynews_playback_method('non_seek')
	if use_non_seek:
		logger('aiostreams playback', 'EN No Seek applied | %s' % play_url[:120])
		return _append_play_options(play_url, out_headers, seekable=0)
	return _append_play_options(play_url, out_headers)

def resolve_playback_url(item):
	url = item.get('url_dl') or item.get('url')
	if not url: return None
	headers = playback_headers(item)
	bare = url.split('|', 1)[0]
	if is_direct_easynews_item(item):
		return _resolve_easynews_playback(bare, headers)
	# Uncached debrid playback with AIOStreams Failover often 302s to a short placeholder mp4
	# (static/downloading.mp4). Kodi treats that as successful playback and nextep/autoscrape runs.
	needs_probe = '/debrid/playback/' in bare.lower() or item.get('cached') is False
	if needs_probe:
		final = _probe_final_url(bare, headers)
		if not final:
			return None
		if _is_placeholder_stream_url(final):
			logger('aiostreams playback', 'rejected uncached placeholder stream: %s' % final)
			return None
		# Some EN rows are mis-labelled by the instance; still apply No Seek when the
		# wrapper lands on EasyNews CDN.
		if 'easynews.com' in final.lower():
			use_non_seek = None
			try:
				from modules.settings import easynews_playback_method
				use_non_seek = easynews_playback_method('non_seek')
			except Exception:
				use_non_seek = False
			if use_non_seek:
				logger('aiostreams playback', 'EN No Seek applied (probe) | %s' % final[:120])
				return _append_play_options(final, None, seekable=0)
			return _append_play_options(final, None)
	if headers: return '%s|%s' % (url, urlencode(headers))
	return url

_DOWNLOAD_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

_RESOLVER_HOST_TOKENS = (
	'strem.fun', 'stremio.ru', 'torrentsdb.com', 'comet.strem', 'elfhosted.com',
	'/resolve/', '/redirect/', '/debrid/',
)

def _download_request_headers(item, pipe_headers=None):
	headers = dict(pipe_headers or {})
	playback = playback_headers(item)
	if playback:
		headers.update(playback)
	headers.setdefault('User-Agent', _DOWNLOAD_UA)
	return headers

def _needs_download_materialize(url):
	lower = (url or '').lower()
	if not lower.startswith('http'):
		return False
	return any(token in lower for token in _RESOLVER_HOST_TOKENS)

def _debrid_service_key(item, url=''):
	for val in (item.get('aio_source_name'), item.get('aio_source'), item.get('aio_hoster')):
		norm = _norm_source_key(str(val or '').rstrip('+'))
		if norm in _DEBRID_CACHE_HOSTER_TOKENS:
			return norm
	label = _label_from_url(url)
	if label:
		norm = _norm_source_key(label[1])
		if norm in _DEBRID_CACHE_HOSTER_TOKENS:
			return norm
	lower = _norm_source_key(url)
	for token in _DEBRID_CACHE_HOSTER_TOKENS:
		if token in lower:
			return token
	return None

def _materialize_download_url(url, headers):
	try:
		resp = requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=30)
		try:
			final = (resp.url or url).strip()
			if not final.startswith('http'):
				return None
			if final != url:
				return final
			content_type = (resp.headers.get('content-type') or '').lower()
			if 'json' in content_type and resp.ok:
				data = resp.json()
				if isinstance(data, dict):
					for key in ('url', 'link', 'download', 'download_url', 'stream_url'):
						val = data.get(key)
						if isinstance(val, str) and val.startswith('http'):
							return val
			if resp.ok and not _needs_download_materialize(final):
				return final
		finally:
			resp.close()
	except Exception as exc:
		logger('aiostreams download resolve', str(exc))
	return None

def _apply_debrid_download_headers(service_key, url):
	if not url or not service_key:
		return url
	try:
		if service_key == 'premiumize':
			from apis.premiumize_api import PremiumizeAPI
			return PremiumizeAPI().add_headers_to_url(url)
		if service_key == 'torbox':
			from apis.torbox_api import TorBoxAPI
			return TorBoxAPI().add_headers_to_url(url)
	except Exception as exc:
		logger('aiostreams download headers', str(exc))
	return url

def resolve_download_url(item, url=None):
	"""Turn an AIO play/redirect URL into a downloader-ready direct link (+ headers)."""
	if not item or not isinstance(item, dict):
		return url
	if is_direct_easynews_item(item):
		from indexers.easynews import resolve_easynews
		return resolve_easynews({'url_dl': item.get('url_dl') or item.get('url'), 'play': 'false'}) or url
	if not url:
		url = resolve_playback_url(item)
	if not url:
		return None
	pipe_headers = None
	base = url
	if '|' in url:
		try:
			from urllib.parse import parse_qsl
			base, header_part = url.rsplit('|', 1)
			pipe_headers = dict(parse_qsl(header_part))
		except Exception:
			base = url.split('|')[0]
	req_headers = _download_request_headers(item, pipe_headers)
	final_url = base
	if _needs_download_materialize(base):
		materialized = _materialize_download_url(base, req_headers)
		if not materialized:
			return None
		final_url = materialized
	service = _debrid_service_key(item, final_url)
	return _apply_debrid_download_headers(service, final_url) or final_url
