# -*- coding: utf-8 -*-
import re
from urllib.parse import quote_plus
from caches.main_cache import main_cache
from caches.settings_cache import get_setting
from modules.kodi_utils import make_session, logger
from modules.native_torrents import USER_AGENT, normalize_info_hash, parse_size_gb

NYAA_BASE = 'https://nyaa.si'
_ITEM = re.compile(r'<item>(.*?)</item>', re.I | re.S)
_TITLE = re.compile(r'<title>(.*?)</title>', re.I | re.S)
_HASH = re.compile(r'<nyaa:infoHash>(.*?)</nyaa:infoHash>', re.I | re.S)
_SIZE = re.compile(r'<nyaa:size>(.*?)</nyaa:size>', re.I | re.S)
_SEEDERS = re.compile(r'<nyaa:seeders>(.*?)</nyaa:seeders>', re.I | re.S)
_CDATA = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.S)
_session = None

NYAA_CATEGORIES = {
	'0': '0_0',
	'1': '1_2',
	'2': '1_0',
}


def _http():
	global _session
	if _session is None:
		_session = make_session('https://')
		_session.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/xml, text/xml, */*'})
	return _session


def nyaa_category():
	idx = str(get_setting('redlight.nyaa.category', '0'))
	return NYAA_CATEGORIES.get(idx, '0_0')


def _text(match):
	if not match:
		return ''
	value = match.group(1).strip()
	cdata = _CDATA.search(value)
	if cdata:
		return cdata.group(1).strip()
	return value.replace('&amp;', '&').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'")


def _parse_items(xml_text):
	results = []
	seen = set()
	for block in _ITEM.findall(xml_text or ''):
		info_hash = normalize_info_hash(_text(_HASH.search(block)))
		name = _text(_TITLE.search(block))
		if not info_hash or not name or info_hash in seen:
			continue
		seen.add(info_hash)
		try:
			seeders = int(_text(_SEEDERS.search(block)) or 0)
		except Exception:
			seeders = 0
		results.append({
			'hash': info_hash,
			'name': name,
			'size': parse_size_gb(_text(_SIZE.search(block))),
			'seeders': seeders,
		})
	return results


def _cache_key(url):
	return 'NYAA_%s' % url


def clear_nyaa_cache():
	try:
		main_cache.delete_like('NYAA_%')
		return True
	except Exception:
		return False


def search(query, timeout=10, expiration=24):
	query = (query or '').strip()
	if not query:
		return []
	url = '%s/?page=rss&c=%s&f=0&q=%s' % (NYAA_BASE, nyaa_category(), quote_plus(query))
	cache_key = _cache_key(url)
	cached = main_cache.get(cache_key)
	if cached is not None:
		return cached
	try:
		response = _http().get(url, timeout=max(5, int(timeout)))
		response.raise_for_status()
		results = _parse_items(response.text)
	except Exception as e:
		logger('nyaa api', '%s (%s)' % (type(e).__name__, query))
		return []
	main_cache.set(cache_key, results, expiration=expiration)
	return results
