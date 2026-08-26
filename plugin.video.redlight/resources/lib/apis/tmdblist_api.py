# -*- coding: utf-8 -*-
from modules.kodi_utils import progress_dialog, notification, sleep, make_session
from caches.tmdb_lists import tmdb_lists_cache_object, tmdb_lists_cache
from caches.settings_cache import get_setting, set_setting
from modules.settings import max_threads, tmdb_lists_read_token
from modules.utils import copy2clip, make_qrcode, make_tinyurl, TaskPool
# from modules.kodi_utils import logger

session = make_session('https://api.themoviedb.org')

class TMDbListAPI:
	def __init__(self):
		self.base_url = 'https://api.themoviedb.org/4'
		self.base_url_v3 = 'https://api.themoviedb.org/3'

	def read_access_token(self):
		return tmdb_lists_read_token()

	def read_access_headers(self):
		return {'accept': 'application/json', 'content-type': 'application/json', 'Authorization': 'Bearer %s' % self.read_access_token()}
	
	def auth(self):
		import requests
		headers = self.read_access_headers()
		data = requests.post('%s/auth/request_token' % self.base_url, headers=headers, timeout=20).json()
		if not 'success' in data: return notification('Failed to Auth Account')
		request_token = data['request_token']
		token_url = 'https://www.themoviedb.org/auth/access?request_token=%s' % request_token
		qr_code = make_qrcode(token_url) or ''
		short_url = make_tinyurl(token_url)
		copy2clip(token_url)
		if short_url: p_dialog_insert = '[CR]OR visit [B]%s[/B]' % short_url
		else: p_dialog_insert = ''
		progressDialog = progress_dialog(heading='TMDb Authorise', icon=qr_code)
		count, success = 72, None
		while not progressDialog.iscanceled() and count >= 0 and success == None:
			try:
				count -= 1
				response = requests.post('%s/auth/access_token' % self.base_url, json={'request_token': request_token}, headers=headers, timeout=20).json()
				if response.get('success') and response.get('access_token'): success = True
				progressDialog.update('Scan the [B]QR Code[/B]%s[CR]Confirm Access to your TMDb Account' % p_dialog_insert, count)
				sleep(2500)
			except: success = False
		canceled = progressDialog.iscanceled()
		progressDialog.close()
		if canceled:
			tmdb_lists_cache.clear_all()
			return
		if success is True:
			success = self.add_tmdb3_to_session(response['access_token'], response['account_id'])
		tmdb_lists_cache.clear_all()
		if success is True:
			notification('Success')
		else:
			notification('Failed')

	def add_tmdb3_to_session(self, access_token, account_id):
		import requests
		headers = self.read_access_headers()
		response = requests.post('https://api.themoviedb.org/3/authentication/session/convert/4', json={'access_token': access_token}, headers=headers, timeout=20).json()
		session_id = response.get('session_id')
		if response.get('success') and session_id: success = True
		else: success = False
		if success:
			response = requests.get(('https://api.themoviedb.org/3/account'), params={'session_id': session_id}, headers=headers, timeout=20).json()
			username, account_session_id = response.get('username'), response.get('id')
			if not account_session_id: success == False
		if success:
			set_setting('tmdb.token', access_token)
			set_setting('tmdb.account_id', account_id)
			set_setting('tmdb.username', username)
			set_setting('tmdb.session_id', session_id)
			set_setting('tmdb.account_session_id', str(account_session_id))
			return True
		return False

	def revoke(self):
		import requests
		headers = self.read_access_headers()
		data = requests.delete('https://api.themoviedb.org/3/auth/access_token', json={'access_token': self.read_access_token()}, headers=headers, timeout=20).json()
		if not 'success' in data: notice = 'Failed to Revoke Account Auth'
		else:
			notice = 'Success! Auth Revoked'
			set_setting('tmdb.token', 'empty_setting')
			set_setting('tmdb.account_id', 'empty_setting')
			set_setting('tmdb.username', 'empty_setting')
			set_setting('tmdb.session_id', 'empty_setting')
			set_setting('tmdb.account_session_id', 'empty_setting')
			tmdb_lists_cache.clear_all()
		return notification(notice)

	def get_user_lists(self):
		def _process_multi(page_no):
			try: results_extend(self.request_data(url % (self.base_url, account_id, page_no))['results'])
			except: pass
		def _process(dummy):
			result = self.request_data(url % (self.base_url, account_id, 1))
			if not result: return results
			results_extend(result.get('results') or [])
			total_pages = result.get('total_pages') or 1
			if total_pages > 1:
				threads = TaskPool().tasks(_process_multi, range(2, total_pages + 1), max_threads())
				[i.join() for i in threads]
			return results
		account_id = get_setting('redlight.tmdb.account_id')
		string = 'get_user_lists'
		url = '%s/account/%s/lists?page=%s'
		results = []
		results_extend = results.extend
		return tmdb_lists_cache_object(_process, string, 'dummy')

	def get_watchfavrecs_list_details(self, list_id, media_type):
		def _process_multi(page_no):
			try:
				results_extend([dict(i, **{'original_order': c}) for c, i in enumerate(self.request_data(url % (self.base_url, account_id, media_type, list_id, page_no))['results'],
																													(page_no * 20) - 20)])
			except: pass
		def _process(dummy):
			result = self.request_data(url % (self.base_url, account_id, media_type, list_id, 1))
			results_extend([dict(i, **{'original_order': c}) for c, i in enumerate(result['results'])])
			total_pages = result['total_pages']
			if list_id == 'recommendations': total_pages = 2
			if total_pages > 1:
				threads = TaskPool().tasks(_process_multi, range(2, total_pages + 1), max_threads())
				[i.join() for i in threads]
			return results
		account_id = get_setting('redlight.tmdb.account_id')
		string = 'get_watchfavrecs_list_details_%s_%s' % (list_id, media_type)
		url = '%s/account/%s/%s/%s?page=%s'
		if list_id == 'recommendations': url += '&language=en-US&region=US'
		results = []
		results_extend = results.extend
		return tmdb_lists_cache_object(_process, string, 'dummy')

	def get_list_details(self, list_id):
		def _process_multi(page_no):
			try: results_extend([dict(i, **{'original_order': c}) for c, i in enumerate(self.request_data(url % (self.base_url, list_id, page_no))['results'], (page_no * 20) - 20)])
			except: pass
		def _process(dummy):
			result = self.request_data(url % (self.base_url, list_id, 1))
			results_extend([dict(i, **{'original_order': c}) for c, i in enumerate(result['results'])])
			total_pages = result['total_pages']
			if total_pages > 1:
				threads = TaskPool().tasks(_process_multi, range(2, total_pages + 1), max_threads())
				[i.join() for i in threads]
			return results
		string = 'get_list_details_%s' % (list_id)
		url = '%s/list/%s?page=%s'
		results = []
		results_extend = results.extend
		return tmdb_lists_cache_object(_process, string, 'dummy')

	def add_remove_from_list(self, list_id, items, action):
		url = '%s/list/%s/items' % (self.base_url, list_id)
		return self.request_data(url, data=items, method=action)

	def add_remove_from_watchfavs(self, media_type, media_id, list_type, status):
		if list_type == 'favorites': list_type = 'favorite'
		account_session_id = get_setting('tmdb.account_session_id')
		session_id = get_setting('tmdb.session_id')
		if 'empty_setting' in [account_session_id, session_id]:
			notification('Please Re-Authenticate you TMDB account')
			return {'success': False}
		url = '%s/account/%s/%s' % (self.base_url_v3, account_session_id, list_type)
		return self.request_data(url, params={'session_id': session_id}, data={'media_type': media_type, 'media_id': str(media_id), list_type: status}, method='post')

	def make_list(self, list_name):
		url = '%s/list' % self.base_url
		return self.request_data(url, data={'description': '', 'name': list_name, 'iso_3166_1': 'US', 'iso_639_1': 'en', 'public': True}, method='post')

	def delete_list(self, list_id):
		url = '%s/list/%s' % (self.base_url, list_id)
		return self.request_data(url, method='delete')

	def rename_list(self, list_id, new_name):
		data = {'description': '', 'name': new_name, 'iso_3166_1': 'US', 'iso_639_1': 'en', 'public': True}
		url = '%s/list/%s' % (self.base_url, list_id)
		return self.request_data(url, data=data, method='put')

	def clear_list(self, list_id):
		url = '%s/list/%s/clear' % (self.base_url, list_id)
		return self.request_data(url)

	def item_status(self, list_id, media_type, media_id):
		url = '%s/list/%s/item_status' % (self.base_url, list_id)
		return self.request_data(url, params={'media_type': media_type, 'media_id': int(media_id)})

	def request_data(self, url, params=None, data=None, method='get'):
		headers = {'accept': 'application/json', 'content-type': 'application/json', 'Authorization': 'Bearer %s' % get_setting('redlight.tmdb.token')}
		try: result = session.request(method, url, params=params, json=data, headers=headers, timeout=90).json()
		except: result = None
		return result

tmdb_list_api = TMDbListAPI()