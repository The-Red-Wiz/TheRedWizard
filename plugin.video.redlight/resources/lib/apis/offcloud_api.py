# -*- coding: utf-8 -*-
from threading import Thread
from caches.main_cache import cache_object
from caches.settings_cache import get_setting, set_setting
from modules.source_utils import supported_video_extensions, seas_ep_filter, extras
from modules.utils import copy2clip, make_qrcode
from modules.kodi_utils import make_session, ok_dialog, notification, progress_dialog, sleep
# from modules.kodi_utils import logger

api_session = make_session('https://offcloud.com/api/')
oauth_session = make_session('https://offcloud.com/oauth/')

class OffcloudAPI:
	base_url = 'https://offcloud.com/api/'
	oauth_url = 'https://offcloud.com/oauth/'

	def __init__(self):
		self._sync_token()

	def _sync_token(self):
		self.token = get_setting('redlight.oc.token', 'empty_setting')

	def _authorized(self):
		return self.token not in ('empty_setting', '', None)

	def _headers(self):
		if not self._authorized(): return {}
		return {'Authorization': 'Bearer %s' % self.token}

	def _request(self, method, path, params=None, json_data=None, data=None, timeout=20):
		self._sync_token()
		if not self._authorized(): return None
		url = path if path.startswith('http') else '%s%s' % (self.base_url, path.lstrip('/'))
		try:
			response = api_session.request(method, url, params=params, json=json_data, data=data, headers=self._headers(), timeout=timeout)
			try: return response.json()
			except Exception: return {}
		except Exception:
			return {}

	def _get(self, path, **kwargs):
		return self._request('get', path, **kwargs)

	def _post(self, path, json_data=None, data=None, **kwargs):
		return self._request('post', path, json_data=json_data, data=data, **kwargs)

	def _cloud_post(self, path, payload):
		'''Offcloud docs describe POST request variables; prefer form body (Gears/node-offcloud).'''
		return self._post(path, data=payload)

	def cloud_status(self, request_id):
		if not request_id: return {}
		return self._cloud_post('cloud/status', {'requestId': request_id}) or {}

	def _parse_cloud_response(self, result):
		if not result or not isinstance(result, dict):
			return False, 'Offcloud: No response from API (check authorisation)'
		not_available = result.get('not_available')
		if not_available:
			reasons = {
				'premium': 'Premium addon required',
				'links': 'Link limit addon required',
				'proxy': 'Proxy addon required',
				'cloud': 'Cloud storage addon required',
				'video': 'Video site addon required',
			}
			return False, 'Offcloud: %s' % reasons.get(str(not_available).lower(), not_available)
		if result.get('error'):
			err = result.get('error')
			if isinstance(err, dict):
				err = err.get('message') or str(err)
			return False, 'Offcloud: %s' % err
		status = str(result.get('status', '')).lower()
		if status in ('error', 'failed'):
			detail = result.get('message') or result.get('detail') or 'Request rejected'
			return False, 'Offcloud: %s' % detail
		if status not in ('created', 'downloaded'):
			return False, 'Offcloud: Unexpected status "%s"' % (result.get('status') or 'unknown')
		return True, result

	def auth(self):
		self.token = ''
		try:
			response = oauth_session.post('%sdevice/code' % self.oauth_url, json={}, timeout=20)
			payload = response.json()
		except Exception:
			return ok_dialog(text='Unable to start Offcloud authorisation')
		device_code = payload.get('device_code')
		user_code = payload.get('user_code')
		verify_url = payload.get('verification_uri_complete') or payload.get('verification_uri') or 'https://offcloud.com/activate'
		if not device_code or not user_code:
			return ok_dialog(text='Invalid Offcloud authorisation response')
		qr_code = make_qrcode(verify_url) or ''
		copy2clip(verify_url)
		p_dialog_insert = '[CR]OR visit [B]offcloud.com/activate[/B][CR]AND Enter this Code: [B]%s[/B]' % user_code
		content = 'Scan the [B]QR Code[/B]%s' % p_dialog_insert
		progress = progress_dialog('Offcloud Authorise', qr_code)
		progress.update(content, 0)
		expires_in = int(payload.get('expires_in') or 600)
		poll_interval = int(payload.get('interval') or 5)
		token_ttl = expires_in
		while not self.token:
			if progress.iscanceled():
				try: progress.close()
				except Exception: pass
				return
			if token_ttl <= 0:
				try: progress.close()
				except Exception: pass
				return ok_dialog(text='Offcloud: Authorisation timed out')
			sleep(poll_interval * 1000)
			token_ttl -= poll_interval
			progress.update(content, int(100 * (expires_in - token_ttl) / float(expires_in)))
			try:
				poll = oauth_session.post('%stoken' % self.oauth_url, json={
					'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
					'device_code': device_code,
				}, timeout=20).json()
			except Exception:
				continue
			error = poll.get('error')
			if error == 'authorization_pending':
				continue
			if error == 'slow_down':
				poll_interval += 5
				continue
			if error in ('expired_token', 'access_denied'):
				try: progress.close()
				except Exception: pass
				return ok_dialog(text='Offcloud: %s' % error)
			access_token = poll.get('access_token')
			if access_token:
				self.token = access_token
				break
		try: progress.close()
		except Exception: pass
		if not self.token:
			return
		set_setting('oc.token', self.token)
		set_setting('oc.enabled', 'true')
		info = self.account_info() or {}
		username = info.get('user_id') or info.get('userId') or info.get('email') or ''
		if username:
			set_setting('oc.account_id', username)
		self.clear_cache()
		ok_dialog(heading='Offcloud', text='Account authorised.')

	def item_play_link(self, item):
		url = item.get('url')
		if url: return self.requote_uri(url)
		server, request_id, file_name = item.get('server'), item.get('requestId', ''), item.get('fileName', '')
		if server and request_id and file_name:
			return self.requote_uri(self.build_url(server, request_id, file_name))
		if request_id and not item.get('isDirectory'):
			explore = self.torrent_info(request_id)
			if isinstance(explore, list):
				for link in explore:
					if isinstance(link, str) and link:
						return self.requote_uri(link)
		return ''

	def revoke(self):
		set_setting('oc.token', 'empty_setting')
		set_setting('oc.enabled', 'false')
		set_setting('oc.account_id', 'empty_setting')
		notification('Offcloud Authorisation Reset', 3000)

	def user_cloud(self):
		return cache_object(self._get, 'oc_user_cloud', 'cloud/history', False, 0.03)

	def user_cloud_check(self):
		result = self._get('cloud/history')
		return result if isinstance(result, list) else []

	def user_cloud_info(self, request_id=''):
		return cache_object(self._get, 'oc_user_cloud_%s' % request_id, 'cloud/explore/%s' % request_id, False, 0.03)

	def account_info(self):
		return self._get('account/info') or self._get('account/stats')

	def check_cache(self, hashlist):
		return self._post('cache', json_data={'hashes': hashlist})

	def cache_download(self, magnet_url):
		return self._post('cache/download', json_data={'url': magnet_url})

	def _hash_is_cached(self, info_hash):
		info_hash = str(info_hash or '').lower()
		if len(info_hash) != 40: return False
		response = self.check_cache([info_hash]) or {}
		cached_items = response.get('cachedItems') or []
		return info_hash in {str(h).lower() for h in cached_items}

	def _filter_cache_files(self, files, season, episode):
		if not isinstance(files, list) or not files: return []
		extensions = supported_video_extensions()
		extras_filter = extras()
		selected = [f for f in files if (f.get('filename') or '').lower().endswith(tuple(extensions))]
		if not selected: return []
		if season:
			selected = [f for f in selected if seas_ep_filter(season, episode, f.get('filename', ''))]
			return selected
		if self._m2ts_check([{'filename': f.get('filename', '')} for f in selected]):
			return []
		return [f for f in selected if not any(x in f.get('filename', '') for x in extras_filter)]

	def _resolve_cached_download(self, magnet_url, season, episode):
		files = self.cache_download(magnet_url)
		selected = self._filter_cache_files(files, season, episode)
		if not selected: return None
		return self.requote_uri(selected[0].get('url', ''))

	def create_transfer(self, magnet_url):
		ok, result = self._parse_cloud_response(self.add_magnet(magnet_url))
		if not ok:
			return ''
		return result.get('requestId', '') or ''

	def monitor_cloud_ready(self, request_id, title=''):
		if not request_id:
			return
		Thread(target=self._monitor_cloud_ready, args=(str(request_id), title or ''), daemon=True).start()

	def _monitor_cloud_ready(self, request_id, title):
		from modules.settings import oc_notify_cloud_ready
		if not oc_notify_cloud_ready():
			return
		interval_ms, max_attempts = 15000, 240
		for attempt in range(max_attempts):
			if attempt:
				sleep(interval_ms)
			poll = self.cloud_status(request_id) or {}
			status = str(poll.get('status', '')).lower()
			if status == 'downloaded':
				from modules.utils import clean_file_name, normalize
				label = title or poll.get('fileName') or 'Download'
				label = clean_file_name(normalize(label))[:80]
				self.clear_cache()
				notification('Offcloud: Ready in Cloud Storage — %s' % label, 6000)
				return
			if status in ('error', 'failed'):
				detail = poll.get('message') or poll.get('detail') or status
				notification('Offcloud: Transfer failed — %s' % (title or detail), 5000)
				return
		notification('Offcloud: Still downloading — check Offcloud History', 4500)

	def add_to_cloud(self, url, title=''):
		ok, result = self._parse_cloud_response(self.add_magnet(url))
		if not ok:
			return False, result if isinstance(result, str) else 'Offcloud: Request failed'
		request_id = result.get('requestId', '')
		status = str(result.get('status', '')).lower()
		label = title or result.get('fileName') or ''
		if status == 'downloaded':
			return True, 'Offcloud: Ready in Cloud Storage now.'
		# Poll once — stuck on created usually means still processing or account/cloud limit
		if request_id:
			poll = self.cloud_status(request_id)
			poll_status = str((poll or {}).get('status', '')).lower()
			if poll_status == 'downloaded':
				return True, 'Offcloud: Ready in Cloud Storage now.'
			if poll_status == 'error':
				return False, 'Offcloud: Download failed on Offcloud servers (check Offcloud History)'
		from modules.settings import oc_notify_cloud_ready
		if request_id and oc_notify_cloud_ready():
			self.monitor_cloud_ready(request_id, label)
			return True, 'Offcloud: Added — you will be notified when it is ready in Cloud Storage'
		return True, 'Offcloud: Added — check Offcloud History for progress'

	def add_magnet(self, magnet):
		return self._cloud_post('cloud', {'url': magnet})

	def torrent_info(self, request_id=''):
		return self._get('cloud/explore/%s' % request_id)

	def delete_torrent(self, request_id=''):
		return self._get('cloud/remove/%s' % request_id)

	def resolve_magnet(self, magnet_url, info_hash, store_to_cloud, title, season, episode):
		url, _cleanup_request_id = self.resolve_magnet_with_cleanup(magnet_url, info_hash, store_to_cloud, title, season, episode)
		return url

	def resolve_magnet_with_cleanup(self, magnet_url, info_hash, store_to_cloud, title, season, episode):
		try:
			if self._hash_is_cached(info_hash):
				url = self._resolve_cached_download(magnet_url, season, episode)
				if url: return url, None
			return self._resolve_via_cloud_result(magnet_url, season, episode, store_to_cloud)
		except Exception:
			return None, None

	def _resolve_via_cloud(self, magnet_url, season, episode, store_to_cloud=True):
		url, _cleanup_request_id = self._resolve_via_cloud_result(magnet_url, season, episode, store_to_cloud)
		return url

	def _resolve_via_cloud_result(self, magnet_url, season, episode, store_to_cloud=True):
		torrent_id = None
		try:
			extensions = supported_video_extensions()
			torrent = self.add_magnet(magnet_url)
			if not torrent or torrent.get('status') != 'downloaded': return None, None
			single_file_torrent = '%s/%s' % (torrent['url'], torrent['fileName'])
			torrent_id = torrent['requestId']
			torrent_files = self.torrent_info(torrent_id)
			if not isinstance(torrent_files, list): torrent_files = [single_file_torrent]
			torrent_files = [{'url': item, 'filename': item.split('/')[-1], 'size': 0} for item in torrent_files if item.lower().endswith(tuple(extensions))]
			if not torrent_files: return None, None
			if season:
				torrent_files = [i for i in torrent_files if seas_ep_filter(season, episode, i['filename'])]
				if not torrent_files: return None, None
			else:
				if self._m2ts_check(torrent_files):
					self.delete_torrent(torrent_id)
					return None, None
				extras_filter = extras()
				torrent_files = [i for i in torrent_files if not any(x in i['filename'] for x in extras_filter)]
			# Download URLs include this requestId — deleting here invalidates the link
			# before Kodi opens it. Caller removes the request after playback when
			# Store Resolved to Cloud is off (see Sources._cleanup_offcloud_resolved_url).
			# Only mark for cleanup when we created this cloud request during resolve —
			# cached playback URLs can share the same /cloud/download/{id}/ shape but
			# must not delete a user-owned Offcloud item after play (#167).
			file_url = self.requote_uri(torrent_files[0]['url'])
			cleanup_request_id = torrent_id if file_url and not store_to_cloud else None
			return file_url, cleanup_request_id
		except Exception:
			if torrent_id: self.delete_torrent(torrent_id)
			return None, None

	def display_magnet_pack(self, magnet_url, info_hash):
		try:
			files = self.cache_download(magnet_url)
			selected = self._filter_cache_files(files, None, None) if isinstance(files, list) else []
			if selected:
				return [{'link': self.requote_uri(f.get('url', '')), 'filename': f.get('filename', ''), 'size': f.get('size', 0)} for f in selected]
			return self._display_magnet_pack_via_cloud(magnet_url)
		except Exception:
			return None

	def _display_magnet_pack_via_cloud(self, magnet_url):
		torrent_id = None
		try:
			extensions = supported_video_extensions()
			torrent = self.add_magnet(magnet_url)
			if not torrent or torrent.get('status') != 'downloaded': return None
			torrent_id = torrent['requestId']
			torrent_files = self.torrent_info(torrent_id)
			torrent_files = [{'link': self.requote_uri(item), 'filename': item.split('/')[-1], 'size': 0, 'request_id': torrent_id}
				for item in torrent_files if item.lower().endswith(tuple(extensions))]
			return torrent_files or None
		except Exception:
			if torrent_id: self.delete_torrent(torrent_id)
			return None

	def requote_uri(self, url):
		import requests
		return requests.utils.requote_uri(url)

	def build_url(self, server, request_id, file_name):
		return 'https://%s.offcloud.com/cloud/download/%s/%s' % (server, request_id, file_name)

	@staticmethod
	def request_id_from_download_url(url):
		'''Extract cloud requestId from an Offcloud /cloud/download/{id}/... play URL.'''
		if not url:
			return None
		try:
			marker = '/cloud/download/'
			text = str(url)
			if marker not in text:
				return None
			request_id = text.split(marker, 1)[1].split('/', 1)[0].strip()
			return request_id or None
		except Exception:
			return None

	def cleanup_resolved_request(self, request_id):
		'''Remove a temporary cloud request created for resolve (Store to Cloud = None).'''
		if not request_id:
			return
		try: self.delete_torrent(request_id)
		except Exception: pass
		try: self.clear_cache(clear_hashes=False)
		except Exception: pass

	def _m2ts_check(self, folder_items):
		for item in folder_items:
			if item['filename'].endswith('.m2ts'): return True
		return False

	def clear_played_torrent(self, played_item):
		played_url = played_item.get('url')
		if not played_url: return
		request_id = self.request_id_from_download_url(played_url)
		if request_id:
			self.cleanup_resolved_request(request_id)
			return
		user_cloud = self.user_cloud_check()
		if not user_cloud: return
		correct_torrent = next((i for i in user_cloud if i.get('originalLink') == played_url), None)
		if correct_torrent: self.delete_torrent(correct_torrent['requestId'])

	def clear_cache(self, clear_hashes=True):
		try:
			from caches.debrid_cache import debrid_cache
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			try:
				dbcon.execute("""DELETE FROM maincache WHERE id=?""", ('oc_user_cloud',))
				dbcon.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('oc_user_cloud%',))
				user_cloud_success = True
			except Exception:
				user_cloud_success = False
			if clear_hashes:
				try:
					debrid_cache.clear_debrid_results('oc')
					hash_cache_status_success = True
				except Exception:
					hash_cache_status_success = False
			else:
				hash_cache_status_success = True
		except Exception:
			return False
		if False in (user_cloud_success, hash_cache_status_success): return False
		return True

Offcloud = OffcloudAPI()
