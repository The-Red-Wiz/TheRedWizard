# -*- coding: utf-8 -*-
import os
import json
from windows.base_window import open_window
from apis.tmdb_api import tmdb_people_info, tmdb_people_full_info, tmdb_popular_people, tmdb_trending_people_day, tmdb_trending_people_week, tmdb_media_images
from apis.easynews_api import EasyNews
from modules.kodi_utils import make_listitem, list_dirs, delete_file, show_busy_dialog, hide_busy_dialog, get_icon, image_extensions, make_directories
# from modules.kodi_utils import logger

class Images():
	def run(self, params):
		show_busy_dialog()
		self.list_items = []
		self.params = params
		self.mode = self.params.pop('mode')
		self.direct_search_result = False
		self.tmdb_image_base = 'https://image.tmdb.org/t/p/%s%s'
		if self.mode == 'imageviewer': return self.imageviewer()
		if self.mode == 'delete_image': return self.delete_image()
		if self.mode == 'tmdb_people_list_image_results': self.tmdb_people_list_image_results()
		elif self.mode == 'tmdb_people_search_image_results': self.tmdb_people_search_image_results()
		elif self.mode == 'favorite_people_list_image_results': self.favorite_people_list_image_results()
		elif self.mode == 'tmdb_media_image_results': self.tmdb_media_image_results()
		elif self.mode == 'tmdb_people_image_results': self.tmdb_people_image_results()
		elif self.mode == 'tmdb_people_tagged_image_results': self.tmdb_people_tagged_image_results()
		elif self.mode == 'favorites_image_results': self.favorites_image_results()
		elif self.mode == 'easynews_image_results': self.easynews_image_results()
		elif self.mode == 'browser_image': self.browser_image()
		hide_busy_dialog()
		if self.direct_search_result: return
		if len(self.list_items) == 0 and self.mode == 'browser_image' and self.params.get('folder_path'):
			from modules import kodi_utils
			kodi_utils.container_update({'mode': 'downloader.viewer', 'folder_type': 'image', 'name': 'Images'})
			return
		if not 'in_progress' in params: self.open_window_xml()
		else: return self.list_items, self.next_page_params

	def tmdb_people_list_image_results(self):
		def builder():
			results = image_info['results']
			for item in results:
				try:
					name, actor_id = item['name'], item['id']
					p_path = item['profile_path']
					if p_path:
						actor_poster, actor_image = self.tmdb_image_base % ('w185', p_path), self.tmdb_image_base % ('h632', p_path)
						actor_url = self.tmdb_image_base % ('original', p_path)
					else:
						actor_poster, actor_image = get_icon('empty_person'), get_icon('empty_person')
						actor_url = ''
					url_params = {'mode': 'person_data_dialog', 'actor_name': name, 'actor_id': actor_id, 'actor_image': actor_image}
					listitem = make_listitem()
					listitem.setProperties({'thumb': actor_poster, 'path': actor_url, 'name': name, 'actor_name': name, 'actor_id': actor_id,
											'fav_enabled': 'true', 'action': json.dumps(url_params)})
					yield listitem
				except: pass
		action = self.params['action']
		page_no = self.params['page_no']
		function = tmdb_popular_people if action == 'popular' else tmdb_trending_people_day if action == 'day' else tmdb_trending_people_week
		image_info = function(page_no)
		self.list_items = list(builder())
		if image_info['total_pages'] > page_no: page_no += 1
		else: page_no = 'final_page'
		self.next_page_params = {'mode': 'tmdb_people_list_image_results', 'action': action, 'page_no': page_no}

	def tmdb_people_search_image_results(self):
		def builder():
			for item in results:
				try:
					name, actor_id = item['name'], item['id']
					p_path = item['profile_path']
					known = item['known_for']
					known_for_list = [i.get('title', 'NA') for i in known]
					known_for_list = [i for i in known_for_list if not i == 'NA']
					known_for = ' | [I]%s[/I]' % ', '.join(known_for_list) if known_for_list else ''
					if p_path: actor_poster, actor_image = self.tmdb_image_base % ('w185', p_path), self.tmdb_image_base % ('h632', p_path)
					else: actor_poster, actor_image = get_icon('empty_person'), get_icon('empty_person')
					url_params = {'mode': 'person_data_dialog', 'actor_name': name, 'actor_id': actor_id, 'actor_image': actor_image}
					listitem = make_listitem()
					listitem.setProperties({'thumb': actor_poster, 'name': name + known_for, 'actor_name': name, 'actor_id': actor_id,
											'fav_enabled': 'true', 'action': json.dumps(url_params)})
					yield listitem
				except: pass
		page_no = self.params['page_no']
		key_id = self.params.get('key_id') or self.params.get('query')
		try:
			data = tmdb_people_info(key_id, page_no)
			results = data['results']
			results = sorted(results, key=lambda k: k.get('popularity', 0.0), reverse=True)
		except: return
		if len(results) == 1:
			self.direct_search_result = True
			item = results[0]
			return open_window(('windows.people', 'People'), 'people.xml', key_id=None, actor_name=item['name'], actor_id=item['id'],
					actor_image=self.tmdb_image_base % ('h632', item['profile_path']) if item['profile_path'] else get_icon('empty_person'))
		self.list_items = list(builder())
		if data['total_pages'] > page_no: page_no += 1
		else: page_no = 'final_page'
		self.next_page_params = {'mode': 'tmdb_people_search_image_results', 'key_id': key_id, 'page_no': page_no}

	def favorite_people_list_image_results(self, return_items=False):
		from modules.favorites import get_favorites
		def builder():
			for item in image_info:
				try:
					title, actor_id = item['title'], item['media_id']
					name, actor_poster, actor_image = title.split('|')
					url_params = {'mode': 'person_data_dialog', 'actor_name': name, 'actor_id': actor_id, 'actor_image': actor_image}
					listitem = make_listitem()
					listitem.setProperties({'thumb': actor_poster, 'name': name, 'actor_name': name, 'actor_id': actor_id, 'action': json.dumps(url_params), 'in_favorites': 'true'})
					yield listitem
				except: pass
		image_info = get_favorites('people', 'dummy_arg')
		self.list_items = list(builder())
		self.next_page_params = {}
		if return_items: return self.list_items

	def tmdb_media_image_results(self):
		def builder():
			for item in all_images:
				try:
					listitem = make_listitem()
					listitem.setProperties({'thumb': item[2], 'path': item[0], 'name': item[1], 'action': image_action, 'image_subject': rootname})
					yield listitem
				except: pass
		rootname = self.params['rootname']
		all_images = []
		results = tmdb_media_images(self.params['media_type'], self.params['tmdb_id'])
		try:
			posters, clearlogos = [i for i in results['posters']], [dict(i, **{'file_path': '%s.png' % i['file_path'].split('.')[0]}) for i in results['logos']]
			fanarts, landscapes = [i for i in results['backdrops'] if i['iso_639_1'] in (None, 'xx')], [i for i in results['backdrops'] if i['iso_639_1'] == 'en']
			for item in ((posters, '%s _Poster_%03d'), (fanarts, '%s _Fanart_%03d'), (landscapes, '%s _Landscape_%03d'), (clearlogos, '%s _Clearlogo_%03d')):
				if item[0]: all_images.extend([(self.tmdb_image_base % ('original', i['file_path']), item[1] % (rootname, count), self.tmdb_image_base % ('w300', i['file_path'])) \
												for count, i in enumerate(item[0], 1)])
		except: pass
		image_action = json.dumps({'mode': 'imageviewer', 'all_images': all_images})
		self.list_items = list(builder())
		self.next_page_params = {}

	def tmdb_people_image_results(self):
		def builder():
			for item in all_images:
				try:
					listitem = make_listitem()
					listitem.setProperties({'thumb': item[2], 'path': item[0], 'name': item[1], 'action': image_action, 'image_subject': actor_name})
					yield listitem
				except: pass
		all_images = []
		actor_name, actor_id = self.params['actor_name'], self.params['actor_id']
		try:
			results = tmdb_people_full_info(actor_id).get('images', [])
			image_info = results['profiles']
			image_info.sort(key=lambda x: x['file_path'])
			all_images = [(self.tmdb_image_base % ('original', i['file_path']), '%s_%03d' % (actor_name, count),
						self.tmdb_image_base % ('w185', i['file_path'])) for count, i in enumerate(image_info, 1)]
		except: pass
		image_action = json.dumps({'mode': 'imageviewer', 'all_images': all_images})
		self.list_items = list(builder())
		self.next_page_params = {}

	def tmdb_people_tagged_image_results(self):
		def builder():
			for count, item in enumerate(image_info, 1):
				try:
					media = item['media']
					if 'title' in media: name_key = 'title'
					else: name_key = 'name'
					thumb_url = self.tmdb_image_base % ('w185', item['file_path'])
					image_url = self.tmdb_image_base % ('original', item['file_path'])
					name = '%s_%s_%03d' % (actor_name, media[name_key], count)
					listitem = make_listitem()
					listitem.setProperties({'thumb': thumb_url, 'path': image_url, 'name': name, 'action': image_action, 'image_subject': actor_name})
					yield listitem
				except: pass
		actor_name, actor_id = self.params['actor_name'], self.params['actor_id']
		try: results = tmdb_people_full_info(actor_id)['tagged_images']
		except: return
		image_info = results['results']
		image_info.sort(key=lambda x: x['file_path'])
		all_images = [(self.tmdb_image_base % ('original', i['file_path']), (i['media']['title']) if 'title' in i['media'] else i['media']['name']) for i in image_info]
		image_action = json.dumps({'mode': 'imageviewer', 'all_images': all_images})
		self.list_items = list(builder())
		self.next_page_params = {'mode': 'tmdb_people_tagged_image_results', 'actor_id': actor_id, 'actor_name': actor_name}

	def easynews_image_results(self):
		def builder():
			for item in image_info:
				try:
					listitem = make_listitem()
					thumb = EasyNews.auth_thumb(item.get('thumbnail') or '')
					listitem.setProperties({'thumb': thumb, 'path': item['down_url'], 'name': item['name'], 'action': image_action, 'image_subject': key_id})
					yield listitem
				except: pass
		key_id, page_no = self.params['key_id'], self.params['page_no']
		results = EasyNews.search_images(key_id, page_no)
		image_info, total_pages = results['results'], results['total_pages']
		all_images = [(i['url_dl'], i['name']) for i in image_info]
		image_action = json.dumps({'mode': 'imageviewer', 'all_images': all_images})
		self.list_items = list(builder())
		new_page = page_no + 1
		if new_page > total_pages: new_page = 'final_page'
		self.next_page_params = {'mode': 'easynews_image_results', 'key_id': key_id, 'page_no': new_page}

	def browser_image(self, folder_path=None, return_items=False):
		def builder():
			for item in image_info:
				try:
					listitem = make_listitem()
					image_url = os.path.join(folder_path, item)
					if item in thumbs_info:
						try: thumb_url = os.path.join(thumbs_path, item)
						except: thumb_url = image_url
					else: thumb_url = fallback_image
					listitem.setProperties({'thumb': thumb_url, 'path': image_url, 'name': item, 'action': image_action, 'delete': 'true'})
					yield listitem
				except: pass
		fallback_image = get_icon('empty_person')
		if not folder_path: folder_path = self.params.get('folder_path')
		if not folder_path:
			self.list_items = []
			return self.list_items if return_items else None
		make_directories(folder_path)
		thumbs_path = os.path.join(folder_path, '.thumbs')
		make_directories(thumbs_path)
		extensions = image_extensions()
		try: image_info = list_dirs(folder_path)[1]
		except: image_info = []
		image_info = [i for i in image_info if i.endswith(extensions)]
		image_info.sort()
		try: thumbs_info = list_dirs(thumbs_path)[1]
		except: thumbs_info = []
		thumbs_info = [i for i in thumbs_info if i.endswith(extensions)]
		thumbs_info.sort()
		all_images = [(os.path.join(folder_path, i), i) for i in image_info]
		image_action = json.dumps({'mode': 'imageviewer', 'all_images': all_images, 'page_no': 'final_page'})
		self.list_items = list(builder())
		self.next_page_params = {}
		if return_items: return self.list_items

	def open_window_xml(self):
		hide_busy_dialog()
		open_window(('windows.imageviewer', 'ThumbImageViewer'), 'thumbviewer.xml', list_items=self.list_items, next_page_params= self.next_page_params, ImagesInstance=self)

	def imageviewer(self):
		hide_busy_dialog()
		return open_window(('windows.imageviewer', 'ImageViewer'), 'imageviewer.xml', all_images=self.params['all_images'], index=int(self.params['current_index']))

	def delete_image(self, image_url=None, thumb_url=None):
		image_url, thumb_url = image_url or self.params['image_url'], thumb_url or self.params['thumb_url']
		delete_file(thumb_url)
		delete_file(image_url)
		hide_busy_dialog()
