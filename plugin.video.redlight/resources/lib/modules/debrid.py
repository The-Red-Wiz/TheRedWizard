# -*- coding: utf-8 -*-
import re
from caches.debrid_cache import debrid_cache
from apis.real_debrid_api import RealDebridAPI
from apis.premiumize_api import PremiumizeAPI
from apis.alldebrid_api import AllDebridAPI
from apis.torbox_api import TorBoxAPI
from apis.offcloud_api import OffcloudAPI
from modules.native_torrents import NATIVE_TORRENT_SCRAPERS
from modules.source_utils import get_external_cache_status
from modules.utils import chunks
from modules.kodi_utils import show_busy_dialog, hide_busy_dialog, notification
from modules.settings import enabled_debrids_check
# from modules.kodi_utils import logger

def debrid_enabled():
	return [
	i[0] for i in [('Real-Debrid', 'rd'), ('Premiumize.me', 'pm'), ('AllDebrid', 'ad'), ('Offcloud', 'oc'), ('TorBox', 'tb')] if enabled_debrids_check(i[1])]

def debrid_cache_check_available(enabled_debrid=None):
	if not enabled_debrid: enabled_debrid = debrid_enabled()
	return any(p in enabled_debrid for p in ('Real-Debrid', 'TorBox', 'Premiumize.me', 'Offcloud'))

NO_DOWNLOAD_URL_MSG = 'No URL found for Download. Pick another Source'
NO_CLOUD_ADD_MSG = 'No URL found for Add to Cloud. Pick another Source'
BROWSE_NO_FILES_MSG = 'Could not list files for Browse — source may not be cached yet'

def debrid_for_ext_cache_check(enabled_debrid=None):
	return debrid_cache_check_available(enabled_debrid)

def normalize_debrid_provider(provider):
	if not provider:
		return provider
	if provider.startswith('Uncached '):
		provider = provider[9:]
	elif provider.startswith('Unchecked '):
		provider = provider[10:]
	aliases = {
		'offcloud': 'Offcloud',
		'oc_cloud': 'Offcloud',
		'torbox': 'TorBox',
		'torbox cloud': 'TorBox',
		'tb_cloud': 'TorBox',
		'real-debrid': 'Real-Debrid',
		'rd_cloud': 'Real-Debrid',
		'premiumize.me': 'Premiumize.me',
		'premiumize': 'Premiumize.me',
		'pm_cloud': 'Premiumize.me',
		'alldebrid': 'AllDebrid',
		'ad_cloud': 'AllDebrid',
	}
	return aliases.get(str(provider).lower(), provider)

def downloader_provider_slug(provider):
	provider = normalize_debrid_provider(provider)
	return {
		'Real-Debrid': 'real-debrid',
		'Premiumize.me': 'premiumize.me',
		'AllDebrid': 'alldebrid',
		'TorBox': 'torbox',
		'Offcloud': 'offcloud',
	}.get(provider, (provider or '').lower())

def import_pack_api(provider):
	provider = normalize_debrid_provider(provider)
	api_map = {
		'Real-Debrid': RealDebridAPI,
		'Premiumize.me': PremiumizeAPI,
		'AllDebrid': AllDebridAPI,
		'TorBox': TorBoxAPI,
		'Offcloud': OffcloudAPI,
	}
	return api_map.get(provider)()

class ExternalPackSource:
	'''POV-style pack helper: uses source url/hash and debrid API parse_magnet_pack.'''
	def __init__(self, source_dict, meta=None):
		for key, value in source_dict.items():
			setattr(self, key, value)
		self.meta = meta or {}

	def browse_packs(self, download=False):
		provider = normalize_debrid_provider(getattr(self, 'debrid', None) or getattr(self, 'cache_provider', ''))
		api = import_pack_api(provider)
		if not api:
			hide_busy_dialog()
			notification('Unsupported provider for pack download: %s' % (provider or 'Unknown'))
			return None
		show_busy_dialog()
		magnet_fn = getattr(api, 'parse_magnet_pack', None) or api.display_magnet_pack
		pack_choices = magnet_fn(getattr(self, 'url', ''), getattr(self, 'hash', ''))
		hide_busy_dialog()
		if not pack_choices:
			if provider == 'TorBox':
				notification('TorBox: No video file(s) yet. Try again in a moment.', 4500)
			elif download:
				notification(NO_DOWNLOAD_URL_MSG, 2500)
			else:
				notification(BROWSE_NO_FILES_MSG, 4500)
			return None
		pack_choices.sort(key=lambda k: (k.get('filename') or '').lower())
		if download:
			return pack_choices, api
		return pack_choices

def manual_add_magnet_to_cloud(params):
	show_busy_dialog()
	provider = normalize_debrid_provider(params.get('provider') or params.get('debrid', ''))
	debrid_list_modules = [('Real-Debrid', RealDebridAPI), ('Premiumize.me', PremiumizeAPI), ('AllDebrid', AllDebridAPI), ('Offcloud', OffcloudAPI), ('TorBox', TorBoxAPI)]
	try:
		function = [i[1] for i in debrid_list_modules if i[0] == provider][0]
	except IndexError:
		hide_busy_dialog()
		return notification('Unsupported provider for Add to Cloud: %s' % (provider or 'Unknown'), 4500)
	api = function()
	magnet_url = (params.get('magnet_url') or '').strip()
	info_hash = (params.get('info_hash') or params.get('hash') or '').strip().lower()
	if magnet_url and not magnet_url.startswith('magnet:') and len(info_hash) == 40:
		magnet_url = 'magnet:?xt=urn:btih:%s' % info_hash
	if not magnet_url or magnet_url == 'None':
		hide_busy_dialog()
		return notification('No magnet/link to send to cloud', 4500)
	if provider == 'Offcloud':
		label = params.get('display_name') or params.get('name') or ''
		ok, detail = api.add_to_cloud(magnet_url, title=label)
		api.clear_cache()
		hide_busy_dialog()
		return notification(detail, 6000 if ok else 4500)
	result = api.create_transfer(magnet_url)
	api.clear_cache()
	hide_busy_dialog()
	if result == 'failed':
		return notification('Failed', 2500)
	if not result or result == 'no_url':
		return notification(NO_CLOUD_ADD_MSG, 2500)
	if provider == 'TorBox':
		from modules.settings import tb_notify_cloud_ready
		label = params.get('display_name') or params.get('name') or ''
		if tb_notify_cloud_ready():
			api.monitor_torrent_cloud_ready(result, label)
			return notification('TorBox: Added — you will be notified when it is ready in Cloud Storage', 4500)
		return notification('TorBox: Added — check TorBox History for progress', 4500)
	notification('Success')

def query_local_cache(hash_list):
	return debrid_cache.get_many(hash_list) or []

def add_to_local_cache(hash_list, debrid, expires=24):
	debrid_cache.set_many(hash_list, debrid, expires)

def _ad_instant_available(magnet):
	if not magnet or magnet.get('error'): return False
	for key in ('instant', 'ready', 'cached'):
		val = magnet.get(key)
		if val is True or val == 1: return True
		if str(val).lower() in ('true', '1', 'yes'): return True
	status = str(magnet.get('status', '')).lower()
	if status in ('cached', 'ready', 'completed', 'instant'): return True
	return False

def _ad_magnet_hash(magnet, fallback=''):
	magnet_hash = (magnet.get('hash') or '').lower()
	if len(magnet_hash) == 40: return magnet_hash
	magnet_uri = magnet.get('magnet') or magnet.get('uri') or ''
	match = re.search(r'btih:([a-fA-F0-9]{40})', magnet_uri, re.I)
	if match: return match.group(1).lower()
	match = re.search(r'\b([a-fA-F0-9]{40})\b', magnet_uri)
	if match: return match.group(1).lower()
	fallback = str(fallback).lower()
	return fallback if len(fallback) == 40 else ''

def _normalize_hash_list(hash_list):
	return list({str(h).lower() for h in hash_list if h and len(str(h)) == 40})

def cached_check(hash_list, cached_hashes, debrid):
	hash_list = _normalize_hash_list(hash_list)
	cached_list = [i[0].lower() for i in cached_hashes if i[1] == debrid and i[2] == 'True']
	unchecked_list = [i for i in hash_list if not any(h[0].lower() == i and h[1] == debrid and h[2] == 'True' for h in cached_hashes)]
	return cached_list, unchecked_list

def RD_check(hash_list, cached_hashes, data, active_debrid):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'rd')
	if unchecked_hashes:
		results = get_external_cache_status('Real-Debrid', unchecked_hashes, data, active_debrid)
		if results:
			cached_append = cached_hashes.append
			process_list = []
			process_append = process_list.append
			try:
				for h in unchecked_hashes:
					cached = 'False'
					if h in results:
						cached_append(h)
						cached = 'True'
					process_append((h, cached))
			except:
				for i in unchecked_hashes: process_append((i, 'False'))
		else: process_list, expires  = [(h, 'False') for h in unchecked_hashes], 2
		add_to_local_cache(process_list, 'rd', expires)
	return cached_hashes

def AD_check(hash_list, cached_hashes, data, active_debrid):
	expires = 24
	hash_list = _normalize_hash_list(hash_list)
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'ad')
	if unchecked_hashes:
		cached_results = set()
		api = AllDebridAPI()
		api_responded = False
		api_errors = []
		try:
			_, err = api._probe_magnets_get('&magnet=%s' % unchecked_hashes[0])
			if err in ('NO_SERVER', 'MAGNET_NO_SERVER'):
				from modules.kodi_utils import set_property, logger
				set_property('redlight.debrid_cache_api_error', str(err))
				logger('DebridCacheCheck', 'provider=AllDebrid preflight=%s unchecked=%d' % (err, len(unchecked_hashes)))
				return cached_hashes
		except: pass
		for hash_chunk in chunks(unchecked_hashes, 50):
			try:
				response = api.check_cache(hash_chunk)
				if not response: continue
				if response.get('error'):
					err_code = str(response.get('error'))
					api_errors.append(err_code)
					if err_code in ('NO_SERVER', 'MAGNET_NO_SERVER'):
						try:
							from modules.kodi_utils import set_property
							set_property('redlight.debrid_cache_api_error', err_code)
						except: pass
						break
					continue
				magnets = response.get('magnets')
				if not magnets: continue
				api_responded = True
				chunk_hashes = [h.lower() for h in hash_chunk]
				for idx, magnet in enumerate(magnets):
					if not _ad_instant_available(magnet): continue
					fallback = chunk_hashes[idx] if idx < len(chunk_hashes) else ''
					magnet_hash = _ad_magnet_hash(magnet, fallback)
					if magnet_hash: cached_results.add(magnet_hash)
			except: pass
		if not api_responded:
			from modules.kodi_utils import get_property
			if 'AllDebrid' in active_debrid and not get_property('redlight.debrid_cache_api_error'):
				try:
					fallback = get_external_cache_status('AllDebrid', unchecked_hashes, data, active_debrid) or []
					cached_results.update(str(i).lower() for i in fallback if i)
				except: pass
			if not cached_results:
				if not get_property('redlight.debrid_cache_api_error'):
					add_to_local_cache([(h, 'False') for h in unchecked_hashes], 'ad', 2)
				try:
					from modules.kodi_utils import logger, set_property, clear_property
					logger('DebridCacheCheck', 'provider=AllDebrid unchecked=%d cached=0 api=%s errors=%s' % (
						len(unchecked_hashes), api_responded, ','.join(api_errors[:3]) or 'none'))
					if api_errors and all(e in ('NO_SERVER', 'MAGNET_NO_SERVER') for e in api_errors):
						set_property('redlight.debrid_cache_api_error', 'NO_SERVER')
					elif not get_property('redlight.debrid_cache_api_error'):
						clear_property('redlight.debrid_cache_api_error')
				except: pass
				return cached_hashes
			try:
				from modules.kodi_utils import clear_property
				clear_property('redlight.debrid_cache_api_error')
			except: pass
		else:
			remaining = [h for h in unchecked_hashes if h not in cached_results]
			if remaining and 'AllDebrid' in active_debrid:
				try:
					fallback = get_external_cache_status('AllDebrid', remaining, data, active_debrid) or []
					cached_results.update(str(i).lower() for i in fallback if i)
				except: pass
		cached_append = cached_hashes.append
		process_list = []
		process_append = process_list.append
		for h in unchecked_hashes:
			cached = 'False'
			if h in cached_results:
				cached_append(h)
				cached = 'True'
			process_append((h, cached))
		if not cached_results: expires = 2
		add_to_local_cache(process_list, 'ad', expires)
		try:
			from modules.kodi_utils import logger, clear_property
			clear_property('redlight.debrid_cache_api_error')
			logger('DebridCacheCheck', 'provider=AllDebrid unchecked=%d cached=%d api=%s errors=%s' % (
				len(unchecked_hashes), len(cached_results), api_responded, ','.join(api_errors[:3]) or 'none'))
		except: pass
	return cached_hashes

def PM_check(hash_list, cached_hashes):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'pm')
	if not unchecked_hashes:
		return cached_hashes
	api = PremiumizeAPI()
	cached_append = cached_hashes.append
	process_list = []
	try:
		for offset in range(0, len(unchecked_hashes), 50):
			chunk = unchecked_hashes[offset:offset + 50]
			results = api.check_cache(chunk)
			if not results:
				raise RuntimeError('empty Premiumize cache check response')
			responses = results['response']
			for c, h in enumerate(chunk):
				cached = 'False'
				try:
					if responses[c] is True:
						cached_append(h)
						cached = 'True'
				except Exception:
					pass
				process_list.append((h, cached))
	except Exception as e:
		try:
			from modules.kodi_utils import logger
			logger('DebridCacheCheck', 'provider=Premiumize.me incomplete=%s hashes=%d done=%d' % (
				type(e).__name__, len(unchecked_hashes), len(process_list)))
		except Exception:
			pass
		return None
	add_to_local_cache(process_list, 'pm', expires)
	return cached_hashes

def _tb_cached_hash_set(api_response):
	if not api_response or not api_response.get('success'):
		return set()
	data = api_response.get('data')
	cached = set()
	if isinstance(data, dict):
		for key, value in data.items():
			if value in (True, 1, '1', 'true'):
				cached.add(str(key).lower())
			elif isinstance(value, dict) and value.get('hash'):
				cached.add(str(value['hash']).lower())
	elif isinstance(data, list):
		for item in data:
			if isinstance(item, dict) and item.get('hash'):
				cached.add(str(item['hash']).lower())
			elif isinstance(item, str):
				cached.add(item.lower())
	return cached

def OC_check(hash_list, cached_hashes):
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'oc')
	if not unchecked_hashes:
		return cached_hashes
	try:
		results = OffcloudAPI().check_cache(unchecked_hashes)
		if not results:
			raise RuntimeError('empty Offcloud cache check response')
		cached_items = results['cachedItems']
		cached_append = cached_hashes.append
		process_list = []
		for h in unchecked_hashes:
			cached = 'False'
			if h in cached_items:
				cached_append(h)
				cached = 'True'
			process_list.append((h, cached))
	except Exception as e:
		try:
			from modules.kodi_utils import logger
			logger('DebridCacheCheck', 'provider=Offcloud incomplete=%s hashes=%d' % (type(e).__name__, len(unchecked_hashes)))
		except Exception:
			pass
		return None
	add_to_local_cache(process_list, 'oc')
	return cached_hashes

def TB_check(hash_list, cached_hashes):
	expires = 24
	cached_hashes, unchecked_hashes = cached_check(hash_list, cached_hashes, 'tb')
	if not unchecked_hashes:
		return cached_hashes
	cached_append = cached_hashes.append
	process_list = []
	cached_set = set()
	api = TorBoxAPI()
	try:
		for offset in range(0, len(unchecked_hashes), 100):
			chunk = unchecked_hashes[offset:offset + 100]
			results = api.check_cache(chunk)
			if results:
				cached_set.update(_tb_cached_hash_set(results))
			elif results is None:
				raise RuntimeError('empty TorBox cache check response')
		for h in unchecked_hashes:
			h_lower = str(h).lower()
			if h_lower in cached_set:
				cached_append(h)
				process_list.append((h, 'True'))
			else:
				process_list.append((h, 'False'))
	except Exception as e:
		try:
			from modules.kodi_utils import logger
			logger('DebridCacheCheck', 'provider=TorBox incomplete=%s hashes=%d' % (type(e).__name__, len(unchecked_hashes)))
		except Exception:
			pass
		return None
	add_to_local_cache(process_list, 'tb', expires)
	return cached_hashes

_DEBRID_RUNNERS = {
	'Real-Debrid': ('Real-Debrid', RD_check),
	'Premiumize.me': ('Premiumize.me', PM_check),
	'AllDebrid': ('AllDebrid', AD_check),
	'Offcloud': ('Offcloud', OC_check),
	'TorBox': ('TorBox', TB_check),
}


def stamp_torrent_cache(results, active_debrid, cache_check_override=None, data=None, background=True, progress_dialog=None):
	'''Stamp internal torrent hash rows with per-debrid cache_provider. Other rows pass through.'''
	from threading import Thread, Lock
	from time import time as _time
	from modules.settings import debrid_cache_check
	from modules.kodi_utils import logger, get_property, clear_property, sleep, kodi_monitor

	if not results:
		return results
	native, rest = [], []
	for item in results:
		if item.get('scrape_provider') in NATIVE_TORRENT_SCRAPERS and item.get('hash') and not item.get('cache_provider'):
			native.append(item)
		else:
			rest.append(item)
	if not native:
		return results
	active_debrid = list(active_debrid or [])
	if not active_debrid:
		return rest

	def _cache_check_enabled(provider):
		if cache_check_override is not None:
			return cache_check_override
		return debrid_cache_check(provider)

	def _is_unchecked_row(item):
		return str(item.get('cache_provider', '')).startswith('Unchecked ')

	hash_list, unique_hashes, unique_urls = [], set(), set()
	deduped = []
	for item in native:
		try:
			url = (item.get('url') or '').lower()
			info_hash = str(item.get('hash') or '').lower()
			item['hash'] = info_hash
			if url in unique_urls:
				continue
			unique_urls.add(url)
			if len(info_hash) != 40 or info_hash in unique_hashes:
				continue
			unique_hashes.add(info_hash)
			hash_list.append(info_hash)
			deduped.append(item)
		except Exception:
			deduped.append(item)
	if not deduped:
		return rest
	native = deduped
	cached_hashes = query_local_cache(hash_list)
	providers_needing_api = [p for p in active_debrid if _cache_check_enabled(p)]
	final_results, frozen_providers, final_lock = [], set(), Lock()
	monitor = kodi_monitor() if progress_dialog and not background else None

	def _unchecked_batch(provider, reason):
		try:
			logger('DebridCacheCheck', 'native fallback=unchecked provider=%s reason=%s total=%d' % (provider, reason, len(native)))
		except Exception:
			pass
		return [dict(i, **{'cache_provider': 'Unchecked %s' % provider, 'debrid': provider}) for i in native]

	def _commit(provider, batch):
		with final_lock:
			if provider in frozen_providers:
				return
			existing = [i for i in final_results if i.get('debrid') == provider]
			if existing:
				existing_unverified = all(_is_unchecked_row(i) for i in existing)
				new_verified = batch and not all(_is_unchecked_row(i) for i in batch)
				if existing_unverified and new_verified:
					final_results[:] = [i for i in final_results if i.get('debrid') != provider]
					final_results.extend(batch)
				return
			final_results.extend(batch)

	def _process_cache_check(provider, function):
		incomplete, cached = False, []
		try:
			if _cache_check_enabled(provider):
				if provider in ('Real-Debrid', 'AllDebrid'):
					cached = function(hash_list, cached_hashes, data or {}, active_debrid)
				else:
					cached = function(hash_list, cached_hashes)
				if cached is None:
					incomplete, cached = True, []
			else:
				cached = hash_list
		except Exception as e:
			incomplete, cached = True, []
			try:
				logger('DebridCacheCheck', 'native provider=%s thread=%s' % (provider, type(e).__name__))
			except Exception:
				pass
		api_blocked = get_property('redlight.debrid_cache_api_error') if provider == 'AllDebrid' else ''
		if api_blocked:
			clear_property('redlight.debrid_cache_api_error')
			batch = _unchecked_batch(provider, api_blocked)
		elif incomplete:
			batch = _unchecked_batch(provider, 'incomplete_check')
		else:
			cached_set = set(str(i).lower() for i in cached)
			batch = [dict(i, **{'cache_provider': provider if i.get('hash', '').lower() in cached_set else 'Uncached %s' % provider, 'debrid': provider}) for i in native]
		_commit(provider, batch)

	if not providers_needing_api:
		for provider in active_debrid:
			final_results.extend([dict(i, **{'cache_provider': provider, 'debrid': provider}) for i in native])
		return rest + final_results

	debrid_check_threads = [Thread(target=_process_cache_check, args=_DEBRID_RUNNERS[item], name=item) for item in providers_needing_api]
	hash_budget = max(0, len(hash_list))
	debrid_timeout = max(45, min(240, 30 + (hash_budget // 25) * 8))
	debrid_deadline = _time() + debrid_timeout
	for provider in active_debrid:
		if provider in providers_needing_api:
			continue
		final_results.extend([dict(i, **{'cache_provider': provider, 'debrid': provider}) for i in native])
	[i.start() for i in debrid_check_threads]
	if progress_dialog and not background:
		start_time = _time()
		try:
			progress_dialog.reset_is_cancelled()
		except Exception:
			pass
		while not progress_dialog.iscanceled() and not (monitor and monitor.abortRequested()):
			remaining = [x.getName() for x in debrid_check_threads if x.is_alive()]
			percent = min(100, int((max((_time() - start_time), 0) / float(debrid_timeout)) * 100))
			try:
				progress_dialog.update_scraper(0, 0, 0, 0, len(final_results) or len(native), ', '.join(remaining).upper(), percent)
			except Exception:
				pass
			if not remaining or _time() >= debrid_deadline:
				break
			sleep(100)
	for thread in debrid_check_threads:
		thread.join(timeout=max(0.0, debrid_deadline - _time()))
	grace = _time() + 2.0
	for thread in debrid_check_threads:
		if thread.is_alive():
			thread.join(timeout=max(0.0, grace - _time()))
	with final_lock:
		present = set(i.get('debrid') for i in final_results if i.get('debrid'))
		for provider in providers_needing_api:
			if provider not in present:
				final_results.extend(_unchecked_batch(provider, 'incomplete_check'))
		frozen_providers.update(providers_needing_api)
	try:
		uncached = sum(1 for i in final_results if str(i.get('cache_provider', '')).startswith('Uncached '))
		unchecked = sum(1 for i in final_results if str(i.get('cache_provider', '')).startswith('Unchecked '))
		cached = len(final_results) - uncached - unchecked
		logger('DebridCacheCheck', 'native enabled=%s providers=%s total=%d cached=%d uncached=%d unchecked=%d' % (
			bool(providers_needing_api), ','.join(providers_needing_api) or 'none', len(final_results), cached, uncached, unchecked))
	except Exception:
		pass
	return rest + final_results

