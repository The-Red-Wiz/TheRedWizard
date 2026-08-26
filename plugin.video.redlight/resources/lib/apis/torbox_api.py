# -*- coding: utf-8 -*-
import time
import requests
from datetime import datetime, timezone
from threading import Thread
from urllib.parse import urlencode
from caches.settings_cache import get_setting, set_setting
from caches.main_cache import cache_object
from modules.source_utils import supported_video_extensions, seas_ep_filter, extras
from modules.utils import copy2clip, make_qrcode
from modules.kodi_utils import make_session, ok_dialog, notification, confirm_dialog, progress_dialog, sleep
# from modules.kodi_utils import logger

base_url = 'https://api.torbox.app/v1/api/'
session = make_session(base_url)


def _to_int(value, default=0):
	try: return int(str(value).strip())
	except Exception: return default


def _device_auth_url(app_name, user_code):
	return 'https://torbox.app/oauth/device?%s' % urlencode({'app': app_name, 'code': user_code})


def _extract_device_token(response):
	if not response or not response.get('success'):
		return None
	data = response.get('data')
	if isinstance(data, str) and data.strip():
		return data.strip()
	if isinstance(data, dict):
		for key in ('token', 'api_token', 'api_key', 'access_token'):
			value = data.get(key)
			if value:
				return str(value).strip()
	return None


def _device_auth_poll_pending(response):
	if not response:
		return True
	if response.get('success'):
		return not _extract_device_token(response)
	error = (response.get('error') or '').upper()
	if error in ('ITEM_NOT_FOUND', 'DEVICE_CODE_EXPIRED', 'DEVICE_CODE_INVALID', 'INVALID_DEVICE_CODE'):
		return False
	return True


class TorBoxAPI:
	def __init__(self):
		self.token = get_setting('redlight.tb.token')

	def _safe_json(self, response):
		try: return response.json()
		except Exception: return None

	def _get(self, url, data=None, timeout=20):
		if self.token in ('empty_setting', '', None): return None
		try:
			headers = {'Authorization': 'Bearer %s' % self.token}
			response = session.get(base_url + url, params=data or {}, headers=headers, timeout=timeout)
			parsed = self._safe_json(response)
			if parsed is not None:
				return parsed
			text = (response.text or '').strip()
			return text if text else None
		except Exception: return None

	def _post(self, url, params=None, json=None, data=None, files=None, timeout=30):
		if self.token in ('empty_setting', '', None) and 'token' not in url: return None
		try:
			headers = {'Authorization': 'Bearer %s' % self.token}
			response = session.post(base_url + url, params=params, json=json, data=data, files=files, headers=headers, timeout=timeout)
			return self._safe_json(response)
		except Exception: return None

	def _put(self, url, params=None, json=None, data=None, timeout=30):
		if self.token in ('empty_setting', '', None): return None
		try:
			headers = {'Authorization': 'Bearer %s' % self.token}
			response = session.put(base_url + url, params=params, json=json, data=data, headers=headers, timeout=timeout)
			return self._safe_json(response)
		except Exception: return None

	def add_headers_to_url(self, url):
		return url + '|' + urlencode({
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
			'Referer': 'https://torbox.app/',
		})

	def add_headers_to_url_play(self, url):
		'''Gears-style play headers (downloads keep full Referer).'''
		return url + '|' + urlencode({'User-Agent': 'Mozilla/5.0'})

	def account_info(self):
		return self._get('user/me')

	# ----------- USER CLOUD LISTS -----------
	def user_cloud(self):
		string = 'tb_user_cloud'
		url = 'torrents/mylist'
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_usenet(self):
		string = 'tb_user_cloud_usenet'
		url = 'usenet/mylist'
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_webdl(self):
		string = 'tb_user_cloud_webdl'
		url = 'webdl/mylist'
		return cache_object(self._get, string, url, False, 0.03)

	TB_UI_CACHE_HOURS = 0.05  # ~3 minutes — Cloud Storage browse/back navigation

	def clear_ui_cache(self):
		try:
			from caches.main_cache import main_cache
			from caches.base_cache import connect_database
			main_cache.delete('tb_ui_cloud_folders')
			dbcon = connect_database('maincache_db')
			dbcon.execute("DELETE FROM maincache WHERE id LIKE ?", ('tb_ui_folder_%',))
		except:
			pass

	def peek_ui_cloud_folders(self):
		try:
			from caches.main_cache import main_cache
			cached = main_cache.get('tb_ui_cloud_folders')
			return isinstance(cached, dict) and cached.get('complete') is True
		except:
			return False

	def load_ui_cloud_folders(self, refresh=False, finished_only=True):
		from caches.main_cache import main_cache
		cache_key = 'tb_ui_cloud_folders'
		if not refresh:
			cached = main_cache.get(cache_key)
			if isinstance(cached, dict) and cached.get('complete') is True:
				return {'folders': cached.get('folders', []), 'errors': cached.get('errors', []), 'from_cache': True}
		folders, errors = [], []
		type_labels = {'torrent': 'TORRENT', 'usenet': 'USENET', 'webdl': 'WEB DL'}
		mylist_results = self.mylist_items_all(fresh=True)
		for media_type, type_label in type_labels.items():
			err, items = mylist_results.get(media_type, ('Unknown type', []))
			if err:
				errors.append('%s: %s' % (type_label, err))
				continue
			for item in items:
				if finished_only and not self._torrent_item_finished(item):
					continue
				folders.append({**item, 'media_type': media_type})
		complete = not errors
		payload = {'folders': folders, 'errors': errors, 'complete': complete}
		if complete:
			main_cache.set(cache_key, payload, expiration=self.TB_UI_CACHE_HOURS)
		else:
			main_cache.delete(cache_key)
		return {'folders': folders, 'errors': errors, 'from_cache': False, 'complete': complete}

	def clear_mylist_cache(self):
		self.clear_ui_cache()
		try:
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			for string in ('tb_user_cloud', 'tb_user_cloud_usenet', 'tb_user_cloud_webdl'):
				dbcon.execute("""DELETE FROM maincache WHERE id=?""", (string,))
		except:
			pass

	def mylist_items(self, media_type, fresh=True, timeout=20):
		paths = {'torrent': 'torrents/mylist', 'usenet': 'usenet/mylist', 'webdl': 'webdl/mylist'}
		path = paths.get(media_type)
		if not path:
			return 'Unknown type', []
		params = {'bypass_cache': True} if fresh else {}
		response = self._get(path, data=params, timeout=timeout)
		if not response or not isinstance(response, dict):
			return 'Invalid response', []
		if not response.get('success'):
			err = response.get('detail') or response.get('error') or 'Request failed'
			return str(err) if not isinstance(err, (list, dict)) else str(err), []
		data = response.get('data') or []
		if isinstance(data, dict):
			data = [data]
		return None, data

	def mylist_items_all(self, fresh=True, timeout=25):
		"""Fetch torrent, usenet and webdl mylist in parallel (TorBox has three endpoints vs one for other debrids)."""
		from threading import Thread
		media_types = ('torrent', 'usenet', 'webdl')
		results = {}
		per_request_timeout = min(20, max(8, int(timeout) - 2))

		def _fetch(media_type):
			results[media_type] = self.mylist_items(media_type, fresh=fresh, timeout=per_request_timeout)

		threads = [Thread(target=_fetch, args=(media_type,)) for media_type in media_types]
		deadline = time.time() + timeout
		for thread in threads:
			thread.start()
		for thread in threads:
			thread.join(timeout=max(0.0, deadline - time.time()))
		return results

	def mylist_folder(self, folder_id, media_type='torrent', fresh=True, timeout=20):
		paths = {'torrent': 'torrents/mylist', 'usenet': 'usenet/mylist', 'webdl': 'webdl/mylist'}
		path = paths.get(media_type)
		if not path:
			return None
		params = {'id': folder_id}
		if fresh:
			params['bypass_cache'] = True
			return self._get(path, data=params, timeout=timeout)
		string = 'tb_ui_folder_%s_%s' % (media_type, folder_id)
		return cache_object(self._get, string, [path, params], False, self.TB_UI_CACHE_HOURS)

	def mylist_item_files(self, folder_id, media_type='torrent', fresh=False, allow_live_fallback=True, request_timeout=12):
		response = self.mylist_folder(folder_id, media_type, fresh=fresh, timeout=request_timeout)
		if not response or not response.get('success'):
			return []
		data = response.get('data')
		if isinstance(data, list):
			data = data[0] if data else {}
		if not isinstance(data, dict):
			return []
		files = data.get('files') or []
		if files or fresh or not allow_live_fallback:
			return files
		response = self.mylist_folder(folder_id, media_type, fresh=True, timeout=request_timeout)
		if not response or not response.get('success'):
			return []
		data = response.get('data')
		if isinstance(data, list):
			data = data[0] if data else {}
		if not isinstance(data, dict):
			return []
		return data.get('files') or []

	def user_cloud_info(self, request_id='', fresh=False):
		if fresh:
			return self._get('torrents/mylist', data={'id': request_id, 'bypass_cache': True})
		string = 'tb_user_cloud_%s' % request_id
		url = 'torrents/mylist?id=%s' % request_id
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_info_usenet(self, request_id='', fresh=False):
		if fresh:
			return self._get('usenet/mylist', data={'id': request_id, 'bypass_cache': True})
		string = 'tb_user_cloud_usenet_%s' % request_id
		url = 'usenet/mylist?id=%s' % request_id
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_info_webdl(self, request_id='', fresh=False):
		if fresh:
			return self._get('webdl/mylist', data={'id': request_id, 'bypass_cache': True})
		string = 'tb_user_cloud_webdl_%s' % request_id
		url = 'webdl/mylist?id=%s' % request_id
		return cache_object(self._get, string, url, False, 0.03)

	def user_cloud_clear(self):
		if not confirm_dialog(): return
		data = {'all': True, 'operation': 'delete'}
		self._post('torrents/controltorrent', json=data)
		self._post('usenet/controlusenetdownload', json=data)
		self._post('webdl/controlwebdownload', json=data)
		self.clear_cache()

	# ----------- INFO -----------
	def torrent_info(self, request_id=''):
		return self._get('torrents/mylist', data={'id': request_id})

	def torrent_info_fresh(self, request_id=''):
		return self._get('torrents/mylist', data={'id': request_id, 'bypass_cache': True})

	@staticmethod
	def _torrent_item_from_info(response):
		if not response or not isinstance(response, dict) or not response.get('success'):
			return None
		data = response.get('data')
		if isinstance(data, list):
			return data[0] if data else None
		return data if isinstance(data, dict) else None

	@staticmethod
	def _torrent_item_finished(item):
		if not item:
			return False
		if item.get('download_finished') in (True, 1, '1', 'true'):
			return True
		if item.get('cached') in (True, 1, '1', 'true'):
			return True
		try:
			progress = float(item.get('progress', 0))
			if 0 < progress <= 1 and progress >= 0.99:
				return True
			if progress >= 100:
				return True
		except Exception:
			pass
		status = str(item.get('status', '')).lower()
		if status in ('completed', 'cached', 'ready', 'finished', 'complete', 'seeding', 'seeded'):
			return True
		# Dashboard can list cloud items with files before download_finished is set.
		files = item.get('files') or []
		return bool(files) and any(TorBoxAPI._torrent_file_id(f) is not None for f in files)

	@staticmethod
	def _torrent_file_label(item):
		label = item.get('short_name') or item.get('name') or ''
		if label and ('/' in label or '\\' in label):
			label = label.replace('\\', '/').rsplit('/', 1)[-1]
		return label or 'unknown'

	@staticmethod
	def _torrent_file_id(item):
		for key in ('id', 'file_id'):
			value = item.get(key)
			if value is not None and str(value).strip() not in ('', 'None'):
				return value
		return None

	def _torrent_id_from_create(self, response):
		if not response or not response.get('success'):
			return None
		data = response.get('data')
		if isinstance(data, dict):
			for key in ('torrent_id', 'id'):
				value = data.get(key)
				if value is not None and str(value).strip() not in ('', 'None'):
					return value
		return None

	def monitor_torrent_cloud_ready(self, torrent_id, title=''):
		if not torrent_id:
			return
		Thread(target=self._monitor_torrent_cloud_ready, args=(torrent_id, title or ''), daemon=True).start()

	def _monitor_torrent_cloud_ready(self, torrent_id, title):
		from modules.kodi_utils import notification, sleep
		from modules.settings import tb_notify_cloud_ready
		if not tb_notify_cloud_ready():
			return
		try:
			torrent_id = int(torrent_id)
		except Exception:
			return
		interval_ms, max_attempts = 15000, 240
		for attempt in range(max_attempts):
			if attempt:
				sleep(interval_ms)
			item = self._torrent_item_from_info(self.torrent_info_fresh(torrent_id))
			if not item:
				continue
			if self._torrent_item_finished(item):
				from modules.utils import clean_file_name, normalize
				label = title or item.get('name') or item.get('filename') or 'Torrent'
				label = clean_file_name(normalize(label))[:80]
				self.clear_cache()
				notification('TorBox: Ready in Cloud — %s' % label, 6000)
				return
			status = str(item.get('status', '')).lower()
			if status in ('error', 'failed') or 'stalled' in status:
				notification('TorBox: Transfer failed — %s' % (title or item.get('status') or 'Error'), 5000)
				return
		notification('TorBox: Still downloading — check TorBox History', 4500)

	def usenet_info(self, request_id=''):
		return self._get('usenet/mylist', data={'id': request_id})

	def webdl_info(self, request_id=''):
		return self._get('webdl/mylist', data={'id': request_id})

	# ----------- DELETE -----------
	# TorBox requires the *_id field to be a JSON integer. Cast defensively.
	def delete_torrent(self, request_id=''):
		data = {'torrent_id': _to_int(request_id), 'operation': 'delete'}
		return self._post('torrents/controltorrent', json=data)

	def delete_usenet(self, request_id=''):
		data = {'usenet_id': _to_int(request_id), 'operation': 'delete'}
		return self._post('usenet/controlusenetdownload', json=data)

	def delete_webdl(self, request_id=''):
		data = {'webdl_id': _to_int(request_id), 'operation': 'delete'}
		return self._post('webdl/controlwebdownload', json=data)

	# ----------- AIRLOCK (edit) -----------
	# Minimal body only — edit endpoints can overwrite name/tags if sent.
	@staticmethod
	def item_is_airlocked(item):
		value = (item or {}).get('airlocked')
		return value in (True, 1, '1', 'true', 'True')

	def get_airlocked_status(self, media_type, request_id, timeout=15):
		"""Live mylist lookup (bypass_cache) for current Airlock state."""
		response = self.mylist_folder(request_id, media_type, fresh=True, timeout=timeout)
		item = self._torrent_item_from_info(response)
		if item is None:
			return None
		return self.item_is_airlocked(item)

	def set_airlocked(self, media_type, request_id, airlocked):
		request_id = _to_int(request_id)
		airlocked = bool(airlocked)
		if media_type == 'torrent':
			return self._put('torrents/edittorrent', json={'torrent_id': request_id, 'airlocked': airlocked})
		if media_type == 'webdl':
			return self._put('webdl/editwebdownload', json={'webdl_id': request_id, 'airlocked': airlocked})
		return self._put('usenet/editusenetdownload', json={'usenet_id': request_id, 'airlocked': airlocked})

	# ----------- UNRESTRICT (request download URL) -----------
	@staticmethod
	def _extract_download_url(payload):
		if not payload:
			return None
		if isinstance(payload, str) and payload.strip():
			return payload.strip()
		if isinstance(payload, dict):
			for key in ('download', 'download_url', 'url', 'link'):
				value = payload.get(key)
				if value:
					return str(value).strip()
		return None

	@staticmethod
	def coerce_play_url(payload):
		url = TorBoxAPI._extract_download_url(payload)
		if not url and isinstance(payload, str):
			url = payload.strip()
		if not isinstance(url, str) or not url.lower().startswith('http'):
			return None
		return url

	@staticmethod
	def is_scrapeable_cloud_file(file_item, extensions, min_confirmed_bytes=1048576):
		'''Filter cloud search results: skip stream segments and confirmed tiny junk; allow unknown size.'''
		label = TorBoxAPI._torrent_file_label(file_item)
		if not label:
			return False
		lower = label.lower()
		if lower.endswith(('.m2ts', '.mts', '.mpls', '.clpi', '.cpi', '.bdmv', '.bdm')):
			return False
		if lower.endswith(('.srt', '.sub', '.ssa', '.ass', '.sup', '.idx', '.nfo', '.txt', '.jpg', '.jpeg', '.png', '.gif')):
			return False
		if not lower.endswith(tuple(extensions)):
			return False
		if any(x in lower for x in extras()):
			return False
		try:
			size_bytes = int(file_item.get('size') or 0)
		except Exception:
			size_bytes = 0
		if size_bytes > 0 and size_bytes < min_confirmed_bytes:
			return False
		return True

	@staticmethod
	def filter_browse_cloud_files(file_items, extensions):
		'''Cloud browse: Kodi-supported video (incl. .m2ts), same idea as Umbrella browse_user_torrents.'''
		extensions = tuple(extensions or supported_video_extensions())
		junk_ext = ('.srt', '.sub', '.ssa', '.ass', '.sup', '.idx', '.nfo', '.txt', '.jpg', '.jpeg', '.png', '.gif',
			'.mpls', '.clpi', '.cpi', '.bdmv', '.bdm')
		results = []
		for file_item in file_items or []:
			label = TorBoxAPI._torrent_file_label(file_item)
			if not label or TorBoxAPI._torrent_file_id(file_item) is None:
				continue
			lower = label.lower()
			if lower.endswith(junk_ext):
				continue
			if any(x in lower for x in extras()):
				continue
			if not lower.endswith(extensions):
				continue
			results.append(file_item)
		return results

	@staticmethod
	def folder_has_playable_videos(file_items, extensions):
		return bool(TorBoxAPI.filter_browse_cloud_files(file_items, extensions))

	@staticmethod
	def select_browse_cloud_files(file_items, extensions):
		return TorBoxAPI.filter_browse_cloud_files(file_items, extensions)

	def _requestdl_url(self, response):
		if isinstance(response, str) and response.strip():
			return response.strip()
		if isinstance(response, dict) and response.get('success'):
			data = response.get('data')
			if isinstance(data, str) and data.strip():
				return data.strip()
			return self._extract_download_url(data) or self._extract_download_url(response)
		return None

	def _mylist_torrent_ids(self, fresh=False):
		_, items = self.mylist_items('torrent', fresh=fresh, timeout=15)
		ids = set()
		for item in items or []:
			tid = item.get('id')
			if tid is not None and str(tid).strip() not in ('', 'None'):
				ids.add(str(tid))
		return ids

	def hash_is_cached(self, info_hash):
		ih = str(info_hash or '').lower()
		if len(ih) != 40:
			return False
		check = self.check_cache_single(ih)
		if not check or not check.get('success'):
			return False
		data = check.get('data')
		if isinstance(data, dict):
			for key, value in data.items():
				if str(key).lower() == ih and value in (True, 1, '1', 'true'):
					return True
				if isinstance(value, dict) and str(value.get('hash', '')).lower() == ih:
					return True
		if isinstance(data, list):
			for entry in data:
				if isinstance(entry, dict) and str(entry.get('hash', '')).lower() == ih:
					return True
				if isinstance(entry, str) and entry.lower() == ih:
					return True
		return False

	def requestdl_redirect_url(self, file_id):
		'''TorBox permalink: Kodi follows redirect to a fresh CDN link (recommended for play).'''
		try:
			user_ip = ''
			try:
				user_ip = requests.get('https://api.ipify.org', timeout=2).text.strip()
			except Exception:
				pass
			torrent_id, file_id = str(file_id).split(',', 1)
			params = {
				'token': self.token,
				'torrent_id': _to_int(torrent_id),
				'file_id': _to_int(file_id),
				'redirect': 'true',
			}
			if user_ip:
				params['user_ip'] = user_ip
			return '%storrents/requestdl?%s' % (base_url, urlencode(params))
		except Exception:
			return None

	def unrestrict_link_quick(self, file_id):
		'''One requestdl call (Umbrella) — no ipify, no retry loop.'''
		try:
			torrent_id, file_id = str(file_id).split(',', 1)
			params = {'token': self.token, 'torrent_id': _to_int(torrent_id), 'file_id': _to_int(file_id)}
			r = self._get('torrents/requestdl', data=params, timeout=28)
			if isinstance(r, dict) and r.get('success'):
				return self.coerce_play_url(r.get('data'))
			return self._requestdl_url(r)
		except Exception:
			return None

	def unrestrict_link_cloud(self, file_id):
		'''My Services cloud play — same as Gears requestdl.'''
		return self.unrestrict_link(file_id)

	def unrestrict_link(self, file_id, max_attempts=12):
		'''Retries with user_ip for search/magnet resolve.'''
		try:
			user_ip = ''
			try:
				user_ip = requests.get('https://api.ipify.org', timeout=2).text.strip()
			except Exception:
				pass
			torrent_id, file_id = str(file_id).split(',', 1)
			params = {'token': self.token, 'torrent_id': _to_int(torrent_id), 'file_id': _to_int(file_id)}
			if user_ip:
				params['user_ip'] = user_ip
			for attempt in range(max_attempts):
				if attempt:
					sleep(1500)
				r = self._get('torrents/requestdl', data=params)
				url = self._requestdl_url(r)
				if url:
					return url
				if isinstance(r, str) and r.strip():
					return r.strip()
				if not r or not isinstance(r, dict) or not r.get('success'):
					continue
				data = r.get('data')
				if isinstance(data, dict):
					for key in ('download', 'download_url', 'url', 'link'):
						if data.get(key):
							return str(data[key])
					continue
				if isinstance(data, str) and data.strip():
					return data.strip()
			return None
		except Exception:
			return None

	def unrestrict_usenet(self, file_id):
		try:
			usenet_id, file_id = str(file_id).split(',', 1)
			params = {'token': self.token, 'usenet_id': _to_int(usenet_id), 'file_id': _to_int(file_id)}
			r = self._get('usenet/requestdl', data=params, timeout=20)
			if isinstance(r, str) and r.strip():
				return r.strip()
			if r and r.get('success'):
				return self._extract_download_url(r.get('data')) or r.get('data')
			return None
		except Exception:
			return None

	def unrestrict_webdl(self, file_id):
		try:
			web_id, file_id = str(file_id).split(',', 1)
			params = {'token': self.token, 'web_id': _to_int(web_id), 'file_id': _to_int(file_id)}
			r = self._get('webdl/requestdl', data=params, timeout=20)
			if isinstance(r, str) and r.strip():
				return r.strip()
			if r and r.get('success'):
				return self._extract_download_url(r.get('data')) or r.get('data')
			return None
		except Exception:
			return None

	# ----------- CREATE TRANSFERS -----------
	def add_magnet(self, magnet):
		data = {'magnet': magnet, 'seed': 3, 'allow_zip': 'false'}
		return self._post('torrents/createtorrent', data=data)

	def add_webdl(self, link):
		data = {'link': link}
		return self._post('webdl/createwebdownload', data=data)

	def add_nzb(self, link, name='', add_only_if_cached=False):
		"""Send an NZB download link to TorBox Pro usenet (TorBox Pro required)."""
		data = {'link': link}
		if name: data['name'] = name
		if add_only_if_cached: data['add_only_if_cached'] = 'true'
		return self._post('usenet/createusenetdownload', data=data)

	def _usenet_id_from_create(self, response):
		if not response or not response.get('success'):
			return None
		data = response.get('data')
		if isinstance(data, dict):
			for key in ('usenetdownload_id', 'usenet_id', 'id'):
				value = data.get(key)
				if value is not None and str(value).strip() not in ('', 'None'):
					return value
		return None

	def usenet_hashes_cached(self, hashlist):
		"""Return lowercase MD5 hashes present in TorBox usenet cache."""
		cached = set()
		if not hashlist: return cached
		unique = []
		seen = set()
		for raw in hashlist:
			h = str(raw or '').strip().lower()
			if len(h) != 32 or h in seen: continue
			seen.add(h)
			unique.append(h)
		for offset in range(0, len(unique), 100):
			chunk = unique[offset:offset + 100]
			try:
				check = self.check_cache_usenet(chunk)
			except Exception:
				check = None
			if not check or not check.get('success'): continue
			data = check.get('data')
			if isinstance(data, dict):
				for key, value in data.items():
					key_l = str(key).lower()
					if len(key_l) == 32: cached.add(key_l)
					if isinstance(value, dict):
						item_hash = str(value.get('hash', '')).lower()
						if len(item_hash) == 32: cached.add(item_hash)
			elif isinstance(data, list):
				for entry in data:
					if isinstance(entry, str) and len(entry) == 32:
						cached.add(entry.lower())
					elif isinstance(entry, dict):
						item_hash = str(entry.get('hash', '')).lower()
						if len(item_hash) == 32: cached.add(item_hash)
		return cached

	def nzb_hash_is_cached(self, nzb_link):
		from apis.nzb_api import nzb_link_hash
		return nzb_link_hash(nzb_link) in self.usenet_hashes_cached([nzb_link_hash(nzb_link)])

	def _wait_for_usenet_files(self, usenet_id, max_attempts=45):
		for attempt in range(max_attempts):
			if attempt:
				sleep(1000)
			item = self._torrent_item_from_info(self.usenet_info(usenet_id))
			if not item:
				continue
			files = item.get('files') or []
			if self._torrent_item_finished(item) and files:
				return item, files
		return None, []

	def resolve_nzb(self, nzb_link, store_to_cloud, title, season, episode, max_attempts=None):
		"""Submit NZB to TorBox, wait for files, return a playable URL (cached or uncached)."""
		from modules.source_utils import supported_video_extensions, seas_ep_filter
		if not nzb_link: return None
		if max_attempts is None:
			try: max_attempts = min(120, max(20, int(get_setting('redlight.results.timeout', '20')) * 3))
			except: max_attempts = 45
		usenet_id, cleanup_usenet = None, False
		try:
			result = self.add_nzb(nzb_link, name=title or '')
			usenet_id = self._usenet_id_from_create(result)
			if not usenet_id:
				return None
			cleanup_usenet = not store_to_cloud
			extensions = supported_video_extensions()
			extras_filter = extras()
			extras_filtering_list = tuple(i for i in extras_filter if i not in (title or '').lower())
			_item, files = self._wait_for_usenet_files(usenet_id, max_attempts=max_attempts)
			if not files:
				return None
			selected_files = []
			for item in files:
				file_id = self._torrent_file_id(item)
				filename = self._torrent_file_label(item)
				if file_id is None or not filename.lower().endswith(tuple(extensions)):
					continue
				try: size = int(item.get('size') or 0)
				except: size = 0
				selected_files.append({'file_id': file_id, 'filename': filename, 'size': size})
			if not selected_files:
				return None
			if season:
				selected_files = [i for i in selected_files if seas_ep_filter(season, episode, i['filename'])]
			else:
				if self._m2ts_check(selected_files):
					return None
				selected_files = [i for i in selected_files if not any(x in i['filename'] for x in extras_filtering_list)]
				selected_files.sort(key=lambda k: k['size'], reverse=True)
			if not selected_files:
				return None
			file_key = '%s,%s' % (int(usenet_id), int(selected_files[0]['file_id']))
			file_url = self.unrestrict_usenet(file_key)
			file_url = self.coerce_play_url(file_url) or file_url
			if file_url and store_to_cloud:
				self.clear_cache()
			return file_url
		except Exception:
			return None
		finally:
			if cleanup_usenet and usenet_id:
				try: self.delete_usenet(usenet_id)
				except Exception: pass
				try: self.clear_cache(clear_hashes=False)
				except Exception: pass

	# ----------- CACHED CHECK -----------
	def check_cache_single(self, _hash):
		return self._get('torrents/checkcached', data={'hash': _hash, 'format': 'list'})

	def check_cache(self, hashlist):
		return self._post('torrents/checkcached', params={'format': 'list'}, json={'hashes': hashlist}, timeout=15)

	def check_cache_webdl(self, hashlist):
		return self._post('webdl/checkcached', params={'format': 'list'}, json={'hashes': hashlist})

	def check_cache_usenet(self, hashlist):
		return self._post('usenet/checkcached', params={'format': 'list'}, json={'hashes': hashlist})

	def create_transfer(self, magnet_url):
		torrent_id = self._torrent_id_from_create(self.add_magnet(magnet_url))
		return str(torrent_id) if torrent_id is not None else ''

	def create_webdl_transfer(self, link):
		result = self.add_webdl(link)
		if not result or not result.get('success'): return ''
		return (result.get('data') or {}).get('webdownload_id', '')

	# ----------- RESOLVE -----------
	def resolve_magnet(self, magnet_url, info_hash, store_to_cloud, title, season, episode):
		torrent_id, cleanup_torrent = None, False
		prior_mylist_ids = self._mylist_torrent_ids(fresh=False)
		try:
			# Do not hard-bail on hash_is_cached: scrape cache checks can disagree with a
			# live single-hash probe (Download File / play then fail with "No URL found").
			# Always attempt add_magnet; TorBox rejects truly uncached magnets itself.
			extensions = supported_video_extensions()
			extras_filter = extras()
			extras_filtering_list = tuple(i for i in extras_filter if i not in (title or '').lower())
			torrent = self.add_magnet(magnet_url)
			torrent_id = self._torrent_id_from_create(torrent)
			if not torrent_id:
				return None
			cleanup_torrent = (not store_to_cloud and str(torrent_id) not in prior_mylist_ids)
			_item = self._torrent_item_from_info(self.torrent_info_fresh(torrent_id))
			files = (_item or {}).get('files') or []
			if not files:
				_item, files = self._wait_for_torrent_files(torrent_id, max_attempts=12)
			if not files:
				return None
			selected_files = []
			for item in files:
				file_id = self._torrent_file_id(item)
				filename = self._torrent_file_label(item)
				if file_id is None or not filename.lower().endswith(tuple(extensions)):
					continue
				try:
					size = int(item.get('size') or 0)
				except Exception:
					size = 0
				selected_files.append({'url': '%d,%d' % (int(torrent_id), int(file_id)), 'filename': filename, 'size': size})
			if not selected_files:
				return None
			if season:
				selected_files = [i for i in selected_files if seas_ep_filter(season, episode, i['filename'])]
			else:
				if self._m2ts_check(selected_files):
					return None
				selected_files = [i for i in selected_files if not any(x in i['filename'] for x in extras_filtering_list)]
				selected_files.sort(key=lambda k: k['size'], reverse=True)
			if not selected_files:
				return None
			file_key = selected_files[0]['url']
			file_url = self.unrestrict_link(file_key)
			if store_to_cloud:
				self.monitor_torrent_cloud_ready(torrent_id, title)
			return file_url
		except Exception:
			return None
		finally:
			if cleanup_torrent and torrent_id:
				# Sync delete so Android/Python invoker exit cannot drop the cleanup thread.
				try: self.delete_torrent(torrent_id)
				except Exception: pass
				try: self.clear_cache(clear_hashes=False)
				except Exception: pass

	def _wait_for_torrent_files(self, torrent_id, max_attempts=45):
		for attempt in range(max_attempts):
			if attempt:
				sleep(1000)
			item = self._torrent_item_from_info(self.torrent_info_fresh(torrent_id))
			if not item:
				continue
			files = item.get('files') or []
			if files:
				return item, files
		return None, []

	def parse_magnet_pack(self, magnet_url, info_hash):
		'''List pack files via create_transfer; caller removes transfer when Store Resolved to Cloud is off.'''
		torrent_id, keep_transfer = None, False
		try:
			extensions = supported_video_extensions()
			torrent_id = self.create_transfer(magnet_url)
			if not torrent_id:
				return None
			item = self._torrent_item_from_info(self.torrent_info_fresh(torrent_id))
			files = (item or {}).get('files') or []
			if not files:
				_item, files = self._wait_for_torrent_files(torrent_id, max_attempts=12)
			if not files:
				return None
			pack_files = []
			for file_item in files:
				file_id = self._torrent_file_id(file_item)
				filename = self._torrent_file_label(file_item)
				if file_id is None or not filename.lower().endswith(tuple(extensions)):
					continue
				pack_files.append({
					'link': '%d,%d' % (int(torrent_id), int(file_id)),
					'filename': filename,
					'size': file_item.get('size', 0),
					'torrent_id': torrent_id,
				})
			keep_transfer = bool(pack_files)
			return pack_files or None
		except Exception:
			return None
		finally:
			if torrent_id and not keep_transfer:
				try: self.delete_torrent(torrent_id)
				except: pass

	def display_magnet_pack(self, magnet_url, info_hash):
		return self.parse_magnet_pack(magnet_url, info_hash)

	def _m2ts_check(self, folder_items):
		for item in folder_items:
			if item['filename'].endswith('.m2ts'):
				return True
		return False

	# ----------- AUTH -----------
	def auth(self):
		self.token = ''
		app_name = 'Red Light'
		try:
			response = requests.get(base_url + 'user/auth/device/start', params={'app': app_name}, timeout=20).json()
		except Exception:
			return ok_dialog(text='Unable to start TorBox authorisation')
		if not response.get('success'):
			return ok_dialog(text=response.get('detail') or 'Unable to start TorBox authorisation')
		data = response.get('data') or {}
		device_code = data.get('device_code')
		user_code = data.get('code')
		if not device_code or not user_code:
			return ok_dialog(text='Invalid TorBox authorisation response')
		auth_url = _device_auth_url(app_name, user_code)
		qr_code = make_qrcode(auth_url) or ''
		copy2clip(auth_url)
		p_dialog_insert = '[CR]OR visit [B]torbox.app/oauth/device[/B][CR]AND Enter this Code: [B]%s[/B]' % user_code
		content = 'Scan the [B]QR Code[/B]%s' % p_dialog_insert
		progressDialog = progress_dialog('TorBox Authorise', qr_code)
		progressDialog.update(content, 0)
		sleep_interval = int(data.get('interval') or 5)
		try:
			expires_at = data.get('expires_at', '').replace('Z', '+00:00')
			exp = datetime.fromisoformat(expires_at)
			if exp.tzinfo is None:
				exp = exp.replace(tzinfo=timezone.utc)
			expires_in = max(120, int((exp - datetime.now(timezone.utc)).total_seconds()) + 30)
		except Exception:
			expires_in = 900
		poll_url = base_url + 'user/auth/device/token'
		poll_body = {'device_code': device_code, 'code': user_code}
		start, time_passed = time.time(), 0
		sleep(2000)
		while not progressDialog.iscanceled() and time_passed < expires_in and not self.token:
			sleep(1000 * sleep_interval)
			time_passed = time.time() - start
			try:
				poll = requests.post(poll_url, json=poll_body, timeout=20).json()
			except Exception:
				progressDialog.update(content, int(100 * time_passed / float(expires_in)))
				continue
			api_token = _extract_device_token(poll)
			if api_token:
				self.token = api_token
				break
			if not _device_auth_poll_pending(poll):
				break
			progressDialog.update(content, int(100 * time_passed / float(expires_in)))
		try: progressDialog.close()
		except: pass
		if not self.token:
			return
		try:
			set_setting('tb.token', self.token)
			r = self.account_info()
			if not r or not r.get('success'): raise Exception('invalid account')
			set_setting('tb.enabled', 'true')
			ok_dialog(heading='TorBox', text='Account authorised.')
		except Exception:
			set_setting('tb.token', 'empty_setting')
			set_setting('tb.enabled', 'false')
			ok_dialog(heading='TorBox', text='Authorisation failed.')

	def revoke(self):
		if not confirm_dialog(): return
		set_setting('tb.token', 'empty_setting')
		set_setting('tb.enabled', 'false')
		notification('TorBox Authorisation Reset', 3000)

	def clear_cache(self, clear_hashes=True):
		try:
			from caches.debrid_cache import debrid_cache
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			# USER CLOUD
			try:
				dbcon.execute("""DELETE FROM maincache WHERE id=?""", ('tb_user_cloud',))
				dbcon.execute("""DELETE FROM maincache WHERE id=?""", ('tb_user_cloud_usenet',))
				dbcon.execute("""DELETE FROM maincache WHERE id=?""", ('tb_user_cloud_webdl',))
				dbcon.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('tb_user_cloud%',))
				dbcon.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('tb_ui_%',))
				user_cloud_success = True
			except Exception:
				user_cloud_success = False
			# HASH CACHED STATUS
			if clear_hashes:
				try:
					debrid_cache.clear_debrid_results('tb')
					hash_cache_status_success = True
				except Exception:
					hash_cache_status_success = False
			else:
				hash_cache_status_success = True
		except Exception:
			return False
		if False in (user_cloud_success, hash_cache_status_success): return False
		return True


TorBox = TorBoxAPI()
