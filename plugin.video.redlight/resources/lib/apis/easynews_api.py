# -*- coding: utf-8 -*-
import re
import json
import base64
from urllib.parse import quote, urlencode
from caches.base_cache import connect_database
from caches.main_cache import cache_object
from caches.settings_cache import get_setting
from modules.settings import easynews_refresh_credentials, easynews_exclude_adult
from modules.dom_parser import parseDOM
from modules.utils import chunks, remove_accents
from modules.kodi_utils import make_session
# from modules.kodi_utils import logger

session = make_session()

class EasyNewsAPI:
	def __init__(self):
		self.base_url = 'https://members.easynews.com'
		self.search_link = '/2.0/search/solr-search/advanced'
		self.account_link = 'https://account.easynews.com/editinfo.php'
		self.usage_link = 'https://account.easynews.com/usageview.php'
		self.username = get_setting('redlight.easynews_user', 'empty_setting')
		self.password = get_setting('redlight.easynews_password', 'empty_setting')
		self.auth = self._get_auth()
		self.auth_quoted = quote(self.auth)
		self.base_process = self._process_files

	def _get_auth(self):
		user_info = '%s:%s' % (self.username, self.password)
		user_info = user_info.encode('utf-8')
		auth = 'Basic ' + base64.b64encode(user_info).decode('utf-8')
		return auth

	def _reload_credentials(self):
		self.username = get_setting('redlight.easynews_user', 'empty_setting')
		self.password = get_setting('redlight.easynews_password', 'empty_setting')
		self.auth = self._get_auth()
		self.auth_quoted = quote(self.auth)

	def _maybe_reload_credentials(self):
		if easynews_refresh_credentials(): self._reload_credentials()

	def thumb_url(self, post_hash, kind='pr'):
		# Fen classic: drop last 4 hash chars. Full id 403s on th.easynews.com (pr and sm).
		# Do not use nested API thumbURL or |Authorization= — both blank Kodi textures.
		if not post_hash: return ''
		name = post_hash[:-4] if len(post_hash) > 4 else post_hash
		return 'https://th.easynews.com/thumbnails-%s/%s-%s.jpg' % (post_hash[0:3], kind, name)

	def auth_thumb(self, url):
		"""Rewrite leftover full-hash / nested EasyNews thumb URLs to the Fen filename that 200s."""
		if not url: return url
		url = str(url)
		if '|' in url: url = url.split('|', 1)[0]
		if '@th.easynews.com/' in url:
			url = 'https://th.easynews.com/' + url.split('@th.easynews.com/', 1)[-1]
		if 'th.easynews.com/thumbnails-' not in url: return url
		try:
			prefix, rest = url.split('th.easynews.com/thumbnails-', 1)
			folder, fname = rest.split('/', 1)
			if '/th-' in fname:
				fname = fname.split('/th-', 1)[0]
			kind, name = fname.rsplit('.', 1)[0].split('-', 1)
			if kind in ('pr', 'sm') and name and len(name) > 41:
				name = name[:-4]
			return '%sth.easynews.com/thumbnails-%s/%s-%s.jpg' % (prefix, folder, kind, name)
		except: return url

	def search(self, query, expiration=48):
		self._maybe_reload_credentials()
		self.query = query
		self.base_process = self._process_files
		url, self.params = self._translate_search()
		string = 'EASYNEWS_SEARCH_' + urlencode(self.params)
		results = cache_object(self._process_search, string, url, json=False, expiration=expiration)
		return results if isinstance(results, list) else []

	def search_images(self, query, page_no=1, expiration=48):
		self._maybe_reload_credentials()
		self.query = remove_accents(query)
		self.base_process = self.process_image_files
		url, self.params = self._translate_search(search_type='IMAGE')
		string = 'EASYNEWS_IMAGE_SEARCH_v4_%s' % urlencode(self.params)
		results = cache_object(self._process_search, string, url, json=False, expiration=expiration)
		try: results['results'] = results['results'][page_no -1]
		except: pass
		return results

	def account(self):
		account_info, usage_info = self.account_info(), self.usage_info()
		return account_info, usage_info

	def account_info(self):
		account_info = None
		try:
			account_html = self._get(self.account_link)
			account_info = parseDOM(account_html, 'form', attrs={'id': 'accountForm'})
			account_info = parseDOM(account_info, 'td')[0:11][1::3]
		except: pass
		return account_info

	def usage_info(self):
		usage_info = None
		try:
			usage_html = self._get(self.usage_link)
			usage_info = parseDOM(usage_html, 'div', attrs={'class': 'table-responsive'})
			usage_info = parseDOM(usage_info, 'td')[0:11][1::3]
			usage_info[1] = re.sub(r'[</].+?>', '', usage_info[1])
		except: pass
		return usage_info

	def process_image_files(self, files):
		def _process():
			count = 1
			for item in files:
				try:
					post_hash, size, group, post_title, ext = item['0'], item['4'], item['9'], item['10'], item['11']
					if ext == '.gif': continue
					if 'type' in item and item['type'].upper() != 'IMAGE': continue
					elif 'virus' in item and item['virus']: continue
					if any(i in group for i in ['comic', 'fake', 'erotica']): continue
					url_add = quote('/%s/%s/%s%s/%s%s' % (dl_farm, dl_port, post_hash, ext, post_title, ext))
					url_dl = download_url + url_add
					file_dl = down_url + url_add + '|Authorization=%s' % self.auth_quoted
					thumbnail = self.thumb_url(post_hash, 'sm')
					result = {'name': '%s_%s_%02d' % (self.query, post_title, count),
							  'fullsize': size,
							  'fullres': item['fullres'],
							  'url_dl': url_dl,
							  'down_url': file_dl,
							  'version': 'version2',
							  'thumbnail': thumbnail,
							  'group': group}
					count += 1
					yield result
				except Exception as e:
					from modules.kodi_utils import logger
					logger('easynews API Exception', str(e))
		if not isinstance(files, dict):
			return {'total_results': 0, 'total_pages': 0, 'results': []}
		down_url = files.get('downURL')
		download_url = 'https://%s:%s@members.easynews.com/dl' % (quote(self.username), quote(self.password))
		dl_farm, dl_port = files.get('dlFarm'), files.get('dlPort')
		total_results, total_pages = files.get('results'), files.get('numPages')
		files = files.get('data', []) or []
		results = list(chunks(list(list(_process())), 50))
		return {'total_results': total_results, 'total_pages': len(results), 'results': results}

	def _process_files(self, files):
		def _process():
			for item in files:
				try:
					if not isinstance(item, dict): continue
					post_hash, size, post_title, ext, duration = item['0'], item['4'], item['10'], item['11'], item['14']
					if 'alangs' in item and item['alangs']: language = item['alangs']
					else: language = ''
					if 'type' in item and item['type'].upper() != 'VIDEO': continue
					elif 'virus' in item and item['virus']: continue
					if re.match(r'^\d+s', duration) or re.match(r'^[0-5]m', duration): short_vid = True
					else: short_vid = False
					url_add = quote('/%s/%s/%s%s/%s%s' % (dl_farm, dl_port, post_hash, ext, post_title, ext))
					stream_url = streaming_url + url_add
					file_dl = down_url + url_add + '|Authorization=%s' % self.auth_quoted
					thumbnail = self.thumb_url(post_hash, 'pr')
					result = {'name': post_title,
							  'size': size,
							  'rawSize': item['rawSize'],
							  'width': int(item['width']),
							  'runtime': int(item['runtime']/60.0),
							  'url_dl': stream_url,
							  'down_url': file_dl,
							  'version': 'version2',
							  'short_vid': short_vid,
							  'language': language,
							  'thumbnail': thumbnail}
					yield result
				except Exception as e:
					from modules.kodi_utils import logger
					logger('easynews API Exception', str(e))
		# Empty/failed HTTP (_get → None) or non-JSON body must not raise on .get (scraper log noise).
		if not isinstance(files, dict):
			return []
		down_url = files.get('downURL')
		streaming_url = 'https://%s:%s@members.easynews.com/dl' % (quote(self.username), quote(self.password))
		dl_farm, dl_port = files.get('dlFarm'), files.get('dlPort')
		files = files.get('data', []) or []
		results = list(_process())
		return results

	def _translate_search(self, search_type='VIDEO'):
		video_extensions = 'm4v, 3g2, 3gp, nsv, tp, ts, ty, pls, rm, rmvb, mpd, ifo, mov, qt, divx, xvid, bivx, vob, nrg, img, iso, udf, pva, wmv, asf, asx, ogm, m2v, avi, bin, dat,' \
		'mpg, mpeg, mp4, mkv, mk3d, avc, vp3, svq3, nuv, viv, dv, fli, flv, wpl, xspf, vdr, dvr-ms, xsp, mts, m2t, m2ts, evo, ogv, sdp, avs, rec, url, pxml, vc1, h264, rcv, rss, mpls,' \
		'mpl, webm, bdmv, bdm, wtv, trp, f4v, pvr, disc'
		SEARCH_PARAMS = {'st': 'adv', 'sb': 1, 'fex': video_extensions, 'fty[]': 'VIDEO', 'spamf': 1, 'u': 1, 'gx': 1, 'pno': 1, 'sS': 3, 's1': 'relevance', 's1d': '-', 'pby': 1000}
		IMAGE_SEARCH_PARAMS = {'st': 'adv', 'safeO': 0, 'sb': 1, 's1': 'relevance', 's1d': '+', 's2': 'nsubject', 's2d': '+', 's3': 'nrfile', 's3d': '+', 'pno': 1, 'sS':1,
		'fty[]': 'IMAGE', 'pby': 10000}
		search_types_params = {'VIDEO': SEARCH_PARAMS, 'IMAGE': IMAGE_SEARCH_PARAMS}
		params = search_types_params[search_type]
		params['safeO'] = 1 if easynews_exclude_adult() else 0
		params['gps'] = self.query
		url = self.base_url + self.search_link
		return url, params

	def _process_search(self, url):
		results = self._get(url, self.params)
		if results is None:
			return [] if self.base_process is self._process_files else {'total_results': 0, 'total_pages': 0, 'results': []}
		return self.base_process(results)

	def _get(self, url, params={}):
		headers = {'Authorization': self.auth}
		try: response = session.get(url, params=params, headers=headers, timeout=20).text
		except: return None
		try: return json.loads(response)
		except: return response

	def resolve_easynews(self, url_dl, use_non_seekable=False):
		self._maybe_reload_credentials()
		headers = {'Authorization': self.auth}
		response = session.get(url_dl, headers=headers, stream=True, timeout=20)
		if not response.ok: return None
		if use_non_seekable: resolved_link = response.url + '|seekable=0'
		else: resolved_link = response.url
		return resolved_link

EasyNews = EasyNewsAPI()

def clear_media_results_database():
	dbcon = connect_database('maincache_db')
	try:
		dbcon.execute("DELETE FROM maincache WHERE id LIKE 'EASYNEWS_SEARCH_%'")
		process_result = True
	except: process_result = False
	try:
		dbcon.execute("DELETE FROM maincache WHERE id LIKE 'EASYNEWS_IMAGE_SEARCH_%'")
		process_image_result = True
	except: process_image_result = False
	return (process_result, process_image_result) == (True, True)

