# -*- coding: utf-8 -*-
import re
import base64
from urllib.parse import quote_plus
from modules.utils import clean_file_name, normalize
from modules import source_utils

_HASH_HEX = re.compile(r'^[a-f0-9]{40}$')
_BTIH = re.compile(r'btih:([a-zA-Z0-9]+)', re.I)
_SIZE = re.compile(r'((?:\d+,\d+\.\d+|\d+\.\d+|\d+,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', re.I)
_SEEDERS = re.compile(r'(?:👤|seeders?)\s*[:\s]*(\d+)', re.I)
_SXXEXX = re.compile(r's\d{1,2}e\d{1,2}', re.I)
_SEASON_TAG = re.compile(r'(?:s|season)[.\s_-]*(\d{1,2})(?:[^\de]|$)', re.I)

NATIVE_TORRENT_SCRAPERS = ('comet', 'nyaa')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'


def normalize_info_hash(value):
	if not value:
		return None
	text = str(value).strip()
	match = _BTIH.search(text)
	if match:
		text = match.group(1)
	text = text.lower()
	if _HASH_HEX.match(text):
		return text
	if len(text) == 32:
		try:
			padded = text.upper() + ('=' * ((8 - (len(text) % 8)) % 8))
			decoded = base64.b32decode(padded)
			if len(decoded) == 20:
				return decoded.hex()
		except Exception:
			return None
	return None


def parse_size_gb(text):
	if not text:
		return 0.0
	match = _SIZE.search(str(text).replace('\xa0', ' '))
	if not match:
		return 0.0
	raw, unit = match.group(1).rsplit(None, 1)
	try:
		value = float(raw.replace(',', ''))
	except Exception:
		return 0.0
	if unit.lower().startswith('m'):
		return round(value / 1024.0, 2)
	return round(value, 2)


def parse_seeders(text):
	if not text:
		return 0
	match = _SEEDERS.search(str(text))
	if not match:
		return 0
	try:
		return int(match.group(1))
	except Exception:
		return 0


def magnet_url(info_hash, name):
	display = quote_plus((name or info_hash).replace(' ', '.'))
	return 'magnet:?xt=urn:btih:%s&dn=%s' % (info_hash, display)


def pack_type_from_name(name, season=None):
	if not name:
		return None
	release = normalize(name)
	if _SXXEXX.search(release.replace(' ', '.')):
		return None
	dotted = release.lower().replace(' ', '.')
	if any(token in dotted for token in ('.complete.', 'collection', 'all.seasons', 'all.season')):
		return 'show'
	if season in (None, '', 'pack'):
		if re.search(r'season', dotted):
			return 'season'
		return None
	try:
		season_i = int(season)
	except Exception:
		return None
	season_fill = '%02d' % season_i
	match = _SEASON_TAG.search(dotted)
	if match and int(match.group(1)) == season_i:
		return 'season'
	if '.s%s.' % season_fill in '.%s.' % dotted.replace('-', '.'):
		return 'season'
	if 'season.%s' % season_i in dotted or 'season.%s' % season_fill in dotted:
		return 'season'
	return None


def apply_pack_size(size, package, season_divider, show_divider):
	try:
		size = float(size or 0)
	except Exception:
		return 0.0
	if package == 'season' and season_divider:
		size = size / float(season_divider)
	elif package == 'show' and show_divider:
		size = size / float(show_divider)
	return round(size, 2)


def build_source(scrape_provider, name, info_hash, size=0.0, seeders=0, package=None, extra_name_info=''):
	file_name = normalize(name or info_hash)
	display_name = clean_file_name(file_name).replace('html', ' ').replace('+', ' ').replace('-', ' ')
	name_info = source_utils.release_info_format(file_name)
	if extra_name_info:
		name_info = '%s.%s' % (name_info, extra_name_info)
	quality, extra_info = source_utils.get_file_info(name_info=name_info)
	item = {
		'name': file_name,
		'display_name': display_name,
		'quality': quality,
		'size': round(float(size or 0), 2),
		'size_label': '%.2f GB' % float(size or 0),
		'hash': info_hash,
		'url': magnet_url(info_hash, file_name),
		'id': info_hash,
		'seeders': int(seeders or 0),
		'source': 'torrent',
		'provider': scrape_provider,
		'scrape_provider': scrape_provider,
		'extraInfo': extra_info,
		'direct': False,
		'debridonly': True,
		'external': False,
		'local': False,
	}
	if package:
		item['package'] = package
	return item
