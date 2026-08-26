# -*- coding: utf-8 -*-
import re
import time
import requests
from threading import Thread
from urllib.parse import quote
from caches.main_cache import cache_object
from caches.settings_cache import get_setting, set_setting
from modules.utils import copy2clip, make_qrcode, make_tinyurl
from modules.source_utils import supported_video_extensions, seas_ep_filter, extras
from modules.kodi_utils import progress_dialog, notification, hide_busy_dialog, show_busy_dialog, sleep, ok_dialog, progress_dialog, \
								notification, hide_busy_dialog
# from modules.kodi_utils import logger

class AllDebridAPI:
	def __init__(self):
		self.token = get_setting('redlight.ad.token', 'empty_setting')
		self.break_auth_loop = False
		self.base_url = 'https://api.alldebrid.com/v4/'
		self.user_agent = 'Red Light'

	def auth(self):
		self.token = ''
		url = self.base_url + 'pin/get?agent=%s' % self.user_agent
		response = requests.get(url, timeout=20).json()
		response = response['data']
		expires_in = int(response['expires_in'])
		poll_url = response['check_url']
		user_code = response['pin']
		auth_url = 'https://alldebrid.com/pin?pin=%s' % user_code
		qr_code = make_qrcode(auth_url) or ''
		short_url = make_tinyurl(auth_url)
		copy2clip(auth_url)
		if short_url: p_dialog_insert = '[CR]OR visit [B]%s[/B][CR]OR Enter this Code: [B]%s[/B]' % (short_url, user_code)
		else: p_dialog_insert = '[CR]OR Enter this Code: [B]%s[/B]' % user_code
		sleep_interval = 5
		content = 'Scan the [B]QR Code[/B]%s' % p_dialog_insert
		progressDialog = progress_dialog('All Debrid Authorise', qr_code)
		progressDialog.update(content, 0)
		start, time_passed = time.time(), 0
		sleep(2000)
		while not progressDialog.iscanceled() and time_passed < expires_in and not self.token:
			sleep(1000 * sleep_interval)
			response = requests.get(poll_url, timeout=20).json()
			response = response['data']
			activated = response['activated']
			if not activated:
				time_passed = time.time() - start
				progress = int(100 * time_passed/float(expires_in))
				progressDialog.update(content, progress)
				continue
			try:
				progressDialog.close()
				self.token = str(response['apikey'])
				set_setting('ad.token', self.token)
			except:
				ok_dialog(heading='All Debrid', text='Authorisation failed.')
				break
		try: progressDialog.close()
		except: pass
		if self.token:
			sleep(2000)
			account_info = self._get('user')
			set_setting('ad.account_id', str(account_info['user']['username']))
			set_setting('ad.enabled', 'true')
			ok_dialog(heading='All Debrid', text='Account authorised.')

	def revoke(self):
		set_setting('ad.token', 'empty_setting')
		set_setting('ad.account_id', 'empty_setting')
		set_setting('ad.enabled', 'false')
		notification('All Debrid Authorisation Reset', 3000)

	def account_info(self):
		response = self._get('user')
		return response

	def _probe_magnets_get(self, url_append):
		try:
			if self.token in ('empty_setting', ''): return None, 'no_token'
			url = self.base_url + 'magnet/upload?agent=%s&apikey=%s' % (self.user_agent, self.token) + url_append
			result = requests.get(url, timeout=12).json()
			if result.get('status') != 'success':
				return None, (result.get('error') or {}).get('code') or 'request_failed'
			data = result.get('data') or {}
			return data.get('magnets') or [], None
		except:
			return None, 'request_failed'

	def check_cache(self, hashes):
		if isinstance(hashes, str): hashes = [hashes]
		if not hashes or self.token in ('empty_setting', ''): return None
		valid_hashes = [str(h).lower() for h in hashes if h and len(str(h)) == 40]
		if not valid_hashes: return None
		from modules.utils import chunks
		all_magnets = []
		errors = []
		probe_ids = []
		for hash_chunk in chunks(valid_hashes, 50):
			url_append = ''.join('&magnets[]=%s' % h for h in hash_chunk)
			magnets, err = self._probe_magnets_get(url_append)
			if err in ('NO_SERVER', 'MAGNET_NO_SERVER'):
				return {'magnets': [], 'error': err}
			if err:
				errors.append(str(err))
				continue
			if not magnets:
				errors.append('empty_response')
				continue
			all_magnets.extend(magnets)
			probe_ids.extend([m.get('id') for m in magnets if isinstance(m, dict) and m.get('id')])
		if probe_ids:
			Thread(target=self._delete_cache_probe_magnets, args=(probe_ids,)).start()
		if not all_magnets:
			return {'magnets': [], 'error': errors[0] if errors else 'request_failed'}
		return {'magnets': all_magnets}

	def _delete_cache_probe_magnets(self, magnet_ids):
		for magnet_id in magnet_ids:
			try: self.delete_transfer(magnet_id)
			except: pass

	def check_single_magnet(self, hash_string):
		response = self.check_cache([hash_string])
		if not response or 'magnets' not in response or not response['magnets']: return False
		cache_info = response['magnets'][0]
		if cache_info.get('error'): return False
		instant = cache_info.get('instant')
		if instant is True or instant == 1: return True
		if str(instant).lower() in ('true', '1', 'yes'): return True
		ready = cache_info.get('ready')
		if ready is True or ready == 1: return True
		return str(ready).lower() in ('true', '1', 'yes')

	def _delete_cache_key(self, string):
		try:
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			dbcon.execute("""DELETE FROM maincache WHERE id=?""", (string,))
		except:
			pass

	def clear_mylist_cache(self):
		for string in ('ad_user_cloud', 'ad_user_history', 'ad_user_links'):
			self._delete_cache_key(string)

	def user_cloud(self, fresh=False):
		url = 'magnet/status'
		if fresh:
			self._delete_cache_key('ad_user_cloud')
			return self._get(url) or {'magnets': []}
		string = 'ad_user_cloud'
		return cache_object(self._get, string, url, False, 0.03)

	def magnets_list(self, fresh=True):
		if fresh:
			self._delete_cache_key('ad_user_cloud')
		result = self._get('magnet/status')
		if not result or not isinstance(result, dict):
			return 'Invalid response', []
		return None, result.get('magnets') or []

	def history(self, fresh=False):
		url = 'user/history'
		if fresh:
			self._delete_cache_key('ad_user_history')
			return self._get(url) or {}
		string = 'ad_user_history'
		return cache_object(self._get, string, url, False, 0.03)

	def user_links(self, fresh=False):
		url = 'user/links'
		if fresh:
			self._delete_cache_key('ad_user_links')
			return self._get(url) or {}
		string = 'ad_user_links'
		return cache_object(self._get, string, url, False, 0.03)

	def unrestrict_link(self, link):
		url = 'link/unlock'
		url_append = '&link=%s' % quote(link)
		response = self._get(url, url_append)
		try: return response['link']
		except: return None

	def create_transfer(self, magnet):
		url = 'magnet/upload'
		url_append = '&magnet=%s' % magnet
		result = self._get(url, url_append)
		if not result or 'error' in result:
			return 'no_url'
		try:
			transfer_id = result['magnets'][0].get('id', None)
		except (IndexError, KeyError, TypeError):
			return 'no_url'
		if not transfer_id:
			return 'no_url'
		return transfer_id

	def list_transfer(self, transfer_id):
		url = 'magnet/status'
		url_append = '&id=%s' % transfer_id
		result = self._get(url, url_append)
		return result['magnets']

	def delete_transfer(self, transfer_id):
		url = 'magnet/delete'
		url_append = '&id=%s' % transfer_id
		result = self._get(url, url_append)
		return result.get('message', '') == 'Magnet was successfully deleted'

	def correct_files_list(self, files_list):
		results = []
		while files_list:
			info = files_list.pop()
			if not isinstance(info, dict): continue
			if 'e' in info: files_list.extend(info['e'])
			elif info.get('l'): results.append(info)
		return results

	def resolve_magnet(self, magnet_url, info_hash, store_to_cloud, title, season, episode):
		file_url, media_id, transfer_id = None, None, None
		try:
			extensions = supported_video_extensions()
			correct_files = []
			transfer_id, links = self.parse_magnet(magnet_url=magnet_url)
			if not transfer_id: return None
			valid_results = [i for i in links if any(i.get('n').lower().endswith(x) for x in extensions) and not i.get('l', '') == '']
			if valid_results:
				if season:
					correct_files = [i for i in valid_results if seas_ep_filter(season, episode, i['n'])]
					if correct_files:
						_extras = [i for i in extras() if not i == title.lower()]
						episode_title = re.sub(r'[^A-Za-z0-9-]+', '.', title.replace('\'', '').replace('&', 'and').replace('%', '.percent')).lower()
						try: media_id = [i['l'] for i in correct_files if not any(x in re.sub(episode_title, '', seas_ep_filter(season, episode, i['n'], split=True)) \
											for x in _extras)][0]
						except: media_id = None
				else: media_id = max(valid_results, key=lambda x: x.get('s')).get('l', None)
			if media_id:
				file_url = self.unrestrict_link(media_id)
				if file_url and not any(file_url.lower().endswith(x) for x in extensions): file_url = None
			# Delete after unlock so the magnet link is still valid for unrestrict.
			# Recent unlock history has no per-item delete API (only full purge) — magnet cloud is cleared here.
			if not store_to_cloud and transfer_id:
				try: self.delete_transfer(transfer_id)
				except: pass
				try: self.clear_cache(clear_hashes=False)
				except: pass
			return file_url
		except:
			if transfer_id:
				try:self.delete_transfer(transfer_id)
				except: pass
			return None
	
	def display_magnet_pack(self, magnet_url, info_hash):
		from modules.source_utils import supported_video_extensions
		transfer_id = None
		try:
			extensions = supported_video_extensions()
			transfer_id, links = self.parse_magnet(magnet_url=magnet_url)
			if not transfer_id: return None
			end_results = [{'link': i['l'], 'filename': i['n'], 'size': i['s']} for i in links
							if any(i.get('n').lower().endswith(x) for x in extensions) and not i.get('l', '') == '']
			self.delete_transfer(transfer_id)
			return end_results
		except:
			try:
				if transfer_id: self.delete_transfer(transfer_id)
			except: pass
			return None

	def list_magnet_files(self, transfer_id):
		try:
			response = self._post('magnet/files', {'id[]': [str(transfer_id)]})
			if not response: return []
			for magnet in response.get('magnets', []):
				if str(magnet.get('id')) == str(transfer_id):
					return self.correct_files_list(magnet.get('files', []))
			magnets = response.get('magnets') or []
			if magnets: return self.correct_files_list(magnets[0].get('files', []))
		except: pass
		return []

	def cloud_file_links(self, transfer_id):
		_, links = self.parse_magnet(transfer_id=transfer_id)
		if links: return links
		return self.list_magnet_files(transfer_id)

	def parse_magnet(self, magnet_url=None, transfer_id=None):
		if magnet_url:
			transfer_id = self.create_transfer(magnet_url)
			if not transfer_id: return None, []
			sleep(1000)
		transfer_info = self.list_transfer(transfer_id)
		if transfer_info['statusCode'] != 4: return transfer_id, []
		links = self.correct_files_list(transfer_info.get('files', []))
		return transfer_id, links

	def _get(self, url, url_append=''):
		result = None
		try:
			if self.token in ('empty_setting', ''): return None
			url = self.base_url + url + '?agent=%s&apikey=%s' % (self.user_agent, self.token) + url_append
			if 'magnet/status' in url: url = url.replace('v4', 'v4.1')
			result = requests.get(url, timeout=20).json()
			if result.get('status') == 'success' and 'data' in result: result = result['data']
		except: pass
		return result

	def _post(self, url, data=None):
		result = None
		try:
			if self.token in ('empty_setting', ''): return None
			if data is None: data = {}
			url = self.base_url + url + '?agent=%s&apikey=%s' % (self.user_agent, self.token)
			result = requests.post(url, data=data, timeout=20).json()
			if result.get('status') == 'success' and 'data' in result: result = result['data']
		except: pass
		return result

	def clear_cache(self, clear_hashes=True):
		try:
			from caches.debrid_cache import debrid_cache
			from caches.base_cache import connect_database
			dbcon = connect_database('maincache_db')
			# USER CLOUD
			try:
				dbcon.execute("DELETE FROM maincache WHERE id LIKE 'ad_user_%'")
				dbcon.execute("DELETE FROM maincache WHERE id LIKE 'ad_list_transfer_%'")
				user_cloud_success = True
			except: user_cloud_success = False
			# HASH CACHED STATUS
			if clear_hashes:
				try:
					debrid_cache.clear_debrid_results('ad')
					hash_cache_status_success = True
				except: hash_cache_status_success = False
			else: hash_cache_status_success = True
		except: return False
		if False in (user_cloud_success, hash_cache_status_success): return False
		return True


AllDebrid = AllDebridAPI()