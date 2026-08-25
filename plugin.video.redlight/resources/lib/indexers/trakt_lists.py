# -*- coding: utf-8 -*-
import os
import sys
import json
from random import shuffle
from threading import Thread
from apis.trakt_api import trakt_get_lists, trakt_search_lists, get_trakt_list_contents, trakt_lists_with_media
from indexers.movies import Movies
from indexers.tvshows import TVShows
from indexers.seasons import single_seasons
from indexers.episodes import build_single_episode
from modules import kodi_utils
from modules.utils import paginate_list, gen_md5, get_datetime, get_current_timestamp
from modules.settings import paginate, page_limit, widget_hide_next_page, tmdb_api_key, mpaa_region, jump_to_enabled, trakt_user_active
# logger = kodi_utils.logger

def _trakt_list_id(value):
	if value in (None, '', 0, '0', 'None'): return None
	return value

def _trakt_can_like(user, list_id):
	# Official lists have no real username; like/unlike must use /lists/{id}/like.
	return _trakt_list_id(list_id) is not None or (user and user != 'Trakt Official')

def _trakt_like_params(user, slug, list_id, mode):
	params = {'mode': mode, 'user': user, 'list_slug': slug}
	list_id = _trakt_list_id(list_id)
	if list_id is not None: params['list_id'] = list_id
	return params

def _trakt_liked_lookup():
	liked_ids, liked_pairs = set(), set()
	try:
		if not trakt_user_active(): return liked_ids, liked_pairs
		for i in trakt_get_lists('liked_lists') or []:
			lst = (i.get('list') if isinstance(i, dict) else None) or {}
			if not lst: continue
			ids = lst.get('ids') or {}
			tid = ids.get('trakt')
			if tid not in (None, '', 0, '0'): liked_ids.add(str(tid))
			user_s = ((lst.get('user') or {}).get('ids') or {}).get('slug') or ''
			if lst.get('type') == 'official': user_s = 'Trakt Official'
			liked_pairs.add((ids.get('slug'), user_s))
	except: pass
	return liked_ids, liked_pairs

def _trakt_list_is_liked(list_id, slug, user, liked_ids, liked_pairs):
	tid = _trakt_list_id(list_id)
	if tid is not None and str(tid) in liked_ids: return True
	return (slug, user) in liked_pairs

def _append_like_unlike_cm(cm, build_url, user, slug, list_id, liked_ids, liked_pairs):
	if not trakt_user_active() or not _trakt_can_like(user, list_id): return
	liked = _trakt_list_is_liked(list_id, slug, user, liked_ids, liked_pairs)
	mode = 'trakt.trakt_unlike_a_list' if liked else 'trakt.trakt_like_a_list'
	label = '[B]Unlike List[/B]' if liked else '[B]Like List[/B]'
	cm.append((label, 'RunPlugin(%s)' % build_url(_trakt_like_params(user, slug, list_id, mode))))

def search_trakt_lists(params):
	def _builder():
		for item in lists:
			try:
				list_info = item.get('list')
				if not list_info:
					list_key = item.get('type')
					if list_key: list_info = item.get(list_key)
				if not list_info: continue
				id_lookup = bool(item.get('id_lookup'))
				if list_info.get('type') == 'official' and not id_lookup: continue
				item_count = list_info.get('item_count', 0)
				if list_info.get('privacy') == 'private': continue
				if item_count == 0 and not id_lookup: continue
				list_name = list_info['name']
				list_ids = list_info.get('ids') or {}
				list_id, slug = list_ids.get('trakt'), list_ids.get('slug')
				user_info = list_info.get('user') or {}
				user = (user_info.get('ids') or {}).get('slug') or user_info.get('username') or list_info.get('username')
				if list_info.get('type') == 'official': user = 'Trakt Official'
				if not list_id or not user: continue
				display = '%s | [I]%s (x%s)[/I]' % (list_name, user, str(item_count))
				url = build_url({'mode': 'trakt.list.build_trakt_list', 'list_id': list_id, 'list_type': 'user_lists', 'list_name': list_name,
								'user': user, 'slug': slug, 'iconImage': 'trakt', 'name': list_name})
				cm = []
				_append_like_unlike_cm(cm, build_url, user, slug, list_id, liked_ids, liked_pairs)
				cm.append(('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url})))
				listitem = make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': trakt_icon, 'poster': trakt_icon, 'thumb': trakt_icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(kodi_utils.list_folder_plot(list_info.get('description'), user, item_count, list_info.get('likes')))
				listitem.addContextMenuItems(cm)
				yield (url, listitem, True)
			except: pass
	handle, search_title, trakt_icon, fanart = int(sys.argv[1]), '', kodi_utils.get_icon('trakt'), kodi_utils.get_addon_fanart()
	build_url, make_listitem = kodi_utils.build_url, kodi_utils.make_listitem
	try:
		mode = params.get('mode')
		page = params.get('new_page', '1')
		try: page_no = int(page)
		except: page_no = 1
		search_title = params.get('key_id') or params.get('query') or ''
		lists, pages = trakt_search_lists(search_title, page_no)
		liked_ids, liked_pairs = _trakt_liked_lookup()
		kodi_utils.add_items(handle, list(_builder()))
		if pages > page_no:
			new_page = str(page_no + 1)
			kodi_utils.add_dir(handle, {'mode': mode, 'key_id': search_title, 'new_page': new_page}, 'Next Page (%s) >>' % new_page,
								'nextpage', kodi_utils.get_icon('nextpage_landscape'))
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, search_title.capitalize() if search_title else 'Search User Lists')
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def search_trakt_my_lists(params):
	"""Search the authenticated user's Trakt lists by name (not global Trakt list search)."""
	def get_custom_image(list_name, list_type, user, image_type, images):
		try:
			md5_image_name = gen_md5('%s_%s' % (list_name, user))
			custom_image = [i for i in images if i.rsplit('_', 1)[0] == md5_image_name][0]
			return os.path.join(profile_path, 'images', 'trakt_%s_%s' % (list_type, image_type), custom_image)
		except: return ''
	def _builder():
		for item in data:
			try:
				cm = []
				cm_append = cm.append
				list_name, list_id, user, slug, item_count = item['name'], item['ids']['trakt'], item['user']['ids']['slug'], item['ids']['slug'], item['item_count']
				if user in (None, 'None'): continue
				# Trakt's own declared ordering for the list. The legacy per-list sort store is
				# write-never now, and reading it here made "Use Default" in the new picker fall back
				# to the user's pre-upgrade legacy choice instead of to Trakt's declared order.
				sort_by, sort_how = item['sort_by'], item['sort_how']
				custom_poster = get_custom_image(list_name, list_type, user, 'poster', all_posters)
				poster = custom_poster or trakt_icon
				custom_fanart = get_custom_image(list_name, list_type, user, 'fanart', all_fanart)
				background = custom_fanart or fanart
				url_params = {'mode': 'trakt.list.build_trakt_list', 'user': user, 'slug': slug, 'list_type': list_type, 'list_id': list_id,
					'list_name': list_name, 'iconImage': 'trakt', 'name': list_name}
				url = kodi_utils.build_folder_url(url_params)
				display = '%s [I](x%s)[/I]' % (list_name, str(item_count))
				cm_append(('[B]Make New List[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.make_new_trakt_list'})))
				cm_append(('[B]Delete List[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.delete_trakt_list', 'user': user, 'list_slug': slug})))
				cm_append(('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url})))
				cm_append(('[B]Set Custom Sort[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.list.set_list_custom_sort', 'list_id': list_id,
					'sort_by': sort_by, 'sort_how': sort_how})))
				listitem = make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': poster, 'poster': poster, 'thumb': poster, 'fanart': background, 'banner': background})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(kodi_utils.list_folder_plot(item.get('description'), user, item_count, item.get('likes')))
				listitem.addContextMenuItems(cm)
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	list_type = 'my_lists'
	trakt_icon, fanart = kodi_utils.get_icon('trakt'), kodi_utils.get_addon_fanart()
	build_url, make_listitem = kodi_utils.build_url, kodi_utils.make_listitem
	profile_path = kodi_utils.addon_profile()
	all_posters = kodi_utils.list_dirs(os.path.join(profile_path, 'images', 'trakt_%s_poster' % list_type))[1]
	all_fanart = kodi_utils.list_dirs(os.path.join(profile_path, 'images', 'trakt_%s_fanart' % list_type))[1]
	search_title = params.get('key_id') or params.get('query') or ''
	query = search_title.strip().lower()
	try:
		from modules import settings
		if not settings.trakt_user_active(): data = []
		else:
			data = trakt_get_lists(list_type) or []
			if query: data = [i for i in data if query in (i.get('name') or '').lower()]
			data.sort(key=lambda k: (k.get('name') or '').lower())
		kodi_utils.add_items(handle, list(_builder()))
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, search_title.capitalize() if search_title else 'Search My Trakt Lists')
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def get_trakt_lists(params):
	def get_custom_image(list_name, list_type, user, image_type, images):
		try:
			md5_image_name = gen_md5('%s_%s' % (list_name, user))
			custom_image = [i for i in images if i.rsplit('_', 1)[0] == md5_image_name][0]
			return os.path.join(profile_path, 'images', 'trakt_%s_%s' % (list_type, image_type), custom_image)
		except: return ''
	def _process():
		for item in data:
			try:
				cm = []
				cm_append = cm.append
				list_name, list_id, slug, item_count = item['name'], item['ids']['trakt'], item['ids']['slug'], item['item_count']
				user = ((item.get('user') or {}).get('ids') or {}).get('slug')
				if item.get('type') == 'official': user = 'Trakt Official'
				if user in (None, 'None'): continue
				# See search_trakt_my_lists: Trakt's declared order, not the legacy store.
				sort_by, sort_how = item['sort_by'], item['sort_how']
				custom_poster = get_custom_image(list_name, list_type, user, 'poster', all_posters)
				if custom_poster: poster = custom_poster
				else: poster = trakt_icon
				custom_fanart = get_custom_image(list_name, list_type, user, 'fanart', all_fanart)
				if custom_fanart: background = custom_fanart
				else: background = fanart
				# Parent shuffle (list-of-lists order) is separate from content randomisation.
				# When the contents are to be randomised the URL must name the random builder itself -
				# random.build_trakt_lists_contents with random=true - and not trakt.list.build_trakt_list,
				# which has no shuffle of its own. The URL carries no sort_by/sort_how: folder URLs no
				# longer encode an ordering (build_trakt_list resolves it from the stored override and the
				# payload headers), and the random builder shuffles regardless.
				random_contents = random or shuffle_lists
				mode = 'random.build_trakt_lists_contents' if random_contents else 'trakt.list.build_trakt_list'
				url_params = {'mode': mode, 'user': user, 'slug': slug, 'list_type': list_type, 'list_id': list_id, 'list_name': list_name, 'iconImage': 'trakt',
				'name': list_name}
				if random_contents: url_params['random'] = 'true'
				url = kodi_utils.build_folder_url(url_params)
				if list_type == 'liked_lists':
					display = '%s | [I]%s (x%s)[/I]' % (list_name, user, str(item_count))
					if trakt_user_active() and _trakt_can_like(user, list_id):
						cm_append(('[B]Unlike List[/B]', 'RunPlugin(%s)' % build_url(_trakt_like_params(user, slug, list_id, 'trakt.trakt_unlike_a_list'))))
				else:
					display = '%s [I](x%s)[/I]' % (list_name, str(item_count))
					cm_append(('[B]Make New List[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.make_new_trakt_list'})))
					cm_append(('[B]Delete List[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.delete_trakt_list', 'user': user, 'list_slug': slug})))
				cm_append(('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url})))
				cm_append(('[B]Set Custom Sort[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.list.set_list_custom_sort', 'list_id': list_id,
					'sort_by': sort_by, 'sort_how': sort_how})))
				cm_append(('[B]Make Custom Poster[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.list.make_custom_artwork', 'action': 'make_poster',
					'custom_image': custom_poster, 'list_name': list_name, 'list_type': list_type, 'list_id': list_id, 'user': user, 'list_slug': slug})))
				cm_append(('[B]Make Custom Fanart[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.list.make_custom_artwork', 'action': 'make_fanart',
					'custom_image': custom_fanart, 'list_name': list_name, 'list_type': list_type, 'list_id': list_id, 'user': user, 'list_slug': slug})))
				if custom_poster: cm_append(('[B]Delete Custom Poster[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.list.delete_current_image', 'custom_image': custom_poster})))
				if custom_fanart: cm_append(('[B]Delete Custom Fanart[/B]', 'RunPlugin(%s)' % build_url({'mode': 'trakt.list.delete_current_image', 'custom_image': custom_fanart})))
				listitem = make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': poster, 'poster': poster, 'thumb': poster, 'fanart': background, 'banner': background})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(kodi_utils.list_folder_plot(item.get('description'), user, item_count, item.get('likes')))
				listitem.addContextMenuItems(cm)
				yield (url, listitem, True)
			except: pass
	def _new_process():
		if list_type != 'my_lists':
			return
		url = build_url({'mode': 'trakt.make_new_trakt_list'})
		new_icon = kodi_utils.get_icon('new')
		listitem = make_listitem()
		listitem.setLabel('[I]Make New Trakt List...[/I]')
		listitem.setArt({'icon': new_icon, 'poster': new_icon, 'thumb': new_icon, 'fanart': fanart, 'banner': fanart})
		info_tag = listitem.getVideoInfoTag(True)
		info_tag.setPlot(' ')
		yield (url, listitem, False)
	handle, trakt_icon, fanart = int(sys.argv[1]), kodi_utils.get_icon('trakt'), kodi_utils.get_addon_fanart()
	list_type = params.get('list_type')
	random, shuffle_lists = params.get('random', 'false') == 'true', params.get('shuffle', 'false') == 'true'
	returning_to_list = False
	build_url, make_listitem = kodi_utils.build_url, kodi_utils.make_listitem
	try:
		profile_path = kodi_utils.addon_profile()
		all_posters = kodi_utils.list_dirs(os.path.join(profile_path, 'images', 'trakt_%s_poster' % list_type))[1]
		all_fanart = kodi_utils.list_dirs(os.path.join(profile_path, 'images', 'trakt_%s_fanart' % list_type))[1]
		order_prop = 'redlight.trakt.%s.lists.order' % list_type
		data = trakt_get_lists(list_type) or []
		if list_type == 'liked_lists': data = [i['list'] for i in data if isinstance(i, dict) and 'list' in i]
		if data:
			if shuffle_lists:
				returning_to_list = 'build_trakt_lists_contents' in kodi_utils.folder_path()
				if returning_to_list:
					try: data = json.loads(kodi_utils.get_property(order_prop))
					except: pass
				else:
					shuffle(data)
					kodi_utils.set_property(order_prop, json.dumps(data))
			else:
				kodi_utils.clear_property(order_prop)
				data.sort(key=lambda k: (k.get('name') or '').lower())
			result = list(_process())
		else:
			if list_type == 'liked_lists':
				kodi_utils.notification('No Trakt Liked Lists', 3000)
			result = list(_new_process())
		kodi_utils.add_items(handle, result)
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, params.get('category_name', ''))
	if shuffle_lists and not returning_to_list: kodi_utils.focus_index(0)
	kodi_utils.end_directory(handle, cacheToDisc=not (random or shuffle_lists))
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def get_trakt_user_lists(params):
	def _process():
		for _list in lists:
			try:
				cm = []
				cm_append = cm.append
				item = _list['list']
				item_count = item.get('item_count', 0)
				if item_count == 0: continue
				list_name, list_id = item['name'], item['ids']['trakt']
				slug = (item.get('ids') or {}).get('slug')
				user = ((item.get('user') or {}).get('ids') or {}).get('slug')
				if item.get('type') == 'official':
					user = 'Trakt Official'
					if not slug: slug = str(list_id or '')
				if not slug: continue
				if not user: continue
				display = '%s | [I]%s (x%s)[/I]' % (list_name, user, str(item_count))
				# Parent folder URLs drop random= (build_folder_url skip); shuffle= survives — same pattern as My Lists.
				mode = 'random.build_trakt_lists_contents' if random_contents else 'trakt.list.build_trakt_list'
				url_params = {'mode': mode, 'user': user, 'slug': slug, 'list_id': list_id, 'list_type': 'user_lists', 'list_name': list_name, 'iconImage': 'trakt',
								'name': list_name}
				if random_contents: url_params['random'] = 'true'
				url = kodi_utils.build_folder_url(url_params)
				listitem = make_listitem()
				_append_like_unlike_cm(cm, build_url, user, slug, list_id, liked_ids, liked_pairs)
				cm_append(('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url})))
				listitem.addContextMenuItems(cm)
				listitem.setLabel(display)
				listitem.setArt({'icon': trakt_icon, 'poster': trakt_icon, 'thumb': trakt_icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(kodi_utils.list_folder_plot(item.get('description'), user, item_count, item.get('likes')))
				yield (url, listitem, True)
			except: pass
	handle, trakt_icon, fanart = int(sys.argv[1]), kodi_utils.get_icon('trakt'), kodi_utils.get_addon_fanart()
	build_url, make_listitem = kodi_utils.build_url, kodi_utils.make_listitem
	list_type = params.get('list_type')
	random, shuffle_lists = params.get('random', 'false') == 'true', params.get('shuffle', 'false') == 'true'
	random_contents = random or shuffle_lists
	returning_to_list = False
	try:
		page = params.get('new_page', '1')
		new_page = str(int(page) + 1)
		order_prop = 'redlight.trakt.%s.user_lists.order' % list_type
		lists = list(trakt_get_lists(list_type, page) or [])
		liked_ids, liked_pairs = _trakt_liked_lookup()
		if shuffle_lists and lists:
			returning_to_list = 'build_trakt_lists_contents' in kodi_utils.folder_path()
			if returning_to_list:
				try: lists = json.loads(kodi_utils.get_property(order_prop))
				except: pass
			else:
				shuffle(lists)
				kodi_utils.set_property(order_prop, json.dumps(lists))
		elif not shuffle_lists:
			kodi_utils.clear_property(order_prop)
		kodi_utils.add_items(handle, list(_process()))
		next_params = {'mode': 'trakt.list.get_trakt_user_lists', 'list_type': list_type, 'new_page': new_page,
			'category_name': params.get('category_name', 'Trakt Lists')}
		if random: next_params['random'] = 'true'
		if shuffle_lists: next_params['shuffle'] = 'true'
		kodi_utils.add_dir(handle, next_params, 'Next Page (%s) >>' % new_page, 'nextpage', kodi_utils.get_icon('nextpage_landscape'))
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, params.get('category_name', 'Trakt Lists'))
	if shuffle_lists and not returning_to_list: kodi_utils.focus_index(0)
	kodi_utils.end_directory(handle, cacheToDisc=not random_contents)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def in_trakt_lists(params):
	def _process():
		for item in lists:
			try:
				cm = []
				cm_append = cm.append
				item_count = item.get('item_count', 0)
				ids = item.get('ids') or {}
				list_name = item['name']
				slug = ids.get('slug')
				list_id = ids.get('trakt')
				user = ((item.get('user') or {}).get('ids') or {}).get('slug') or item.get('username')
				is_official = item.get('type') == 'official' or user == 'Trakt Official'
				if is_official:
					user = 'Trakt Official'
					if not slug: slug = str(list_id or '')
				if not user: continue
				if not slug and list_id in (None, '', 0, '0'): continue
				display = '%s | [I]%s (x%s)[/I]' % (list_name, user, str(item_count))
				url_params = {'mode': 'trakt.list.build_trakt_list', 'user': user, 'slug': slug, 'list_type': 'user_lists',
					'list_name': list_name, 'name': list_name}
				if list_id not in (None, '', 0, '0'): url_params['list_id'] = list_id
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				_append_like_unlike_cm(cm, kodi_utils.build_url, user, slug, list_id, liked_ids, liked_pairs)
				cm_append(('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % kodi_utils.build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url})))
				listitem.addContextMenuItems(cm)
				listitem.setLabel(display)
				listitem.setArt({'icon': trakt_icon, 'poster': trakt_icon, 'thumb': trakt_icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(kodi_utils.list_folder_plot(item.get('description'), user, item_count, item.get('likes')))
				yield (url, listitem, True)
			except: pass
	handle, trakt_icon, fanart = int(sys.argv[1]), kodi_utils.get_icon('trakt'), kodi_utils.get_addon_fanart()
	try:
		lists = trakt_lists_with_media(params['media_type'], params['imdb_id'])
		liked_ids, liked_pairs = _trakt_liked_lookup()
		kodi_utils.add_items(handle, list(_process()))
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, params.get('category_name', 'Trakt Lists'))
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def build_trakt_list(params):
	def _process(function, _list, _type):
		if not _list['list']: return
		if _type in ('movies', 'tvshows'): item_list_extend(function(_list).worker())
		elif _type == 'seasons': item_list_extend(function(_list['list']))
		else: item_list_extend(function('episode.trakt_list', _list['list']))
	def _paginate_list(data, page_no, paginate_start):
		if use_result: total_pages = 1
		elif paginate_enabled:
			limit = page_limit(is_external)
			data, total_pages = paginate_list(data, page_no, limit, paginate_start)
			if is_external: paginate_start = limit
		else: total_pages = 1
		return data, total_pages, paginate_start
	handle, is_external, list_name, content = int(sys.argv[1]), kodi_utils.external(), params.get('list_name'), 'movies'
	hide_next_page = is_external and widget_hide_next_page()
	try:
		threads, item_list = [], []
		item_list_extend = item_list.extend
		paginate_enabled = paginate(is_external)
		use_result = 'result' in params
		page_no, paginate_start = int(params.get('new_page', '1')), int(params.get('paginate_start', '0'))
		if page_no == 1 and not is_external: kodi_utils.set_property('redlight.exit_params', kodi_utils.list_collection_exit_params(params))
		if use_result: result = params.get('result', [])
		else:
			user, slug, list_id, list_type = params.get('user'), params.get('slug'), params.get('list_id'), params.get('list_type')
			with_auth = list_type == 'my_lists'
			# No sort_by/sort_how: the list resolves its own override and falls back to the ordering
			# Trakt declares in the payload headers. Passing one here would take the custom-sort branch,
			# and trakt_image_maker - which cannot pass one - would read a differently shaped cache row
			# back out of the very same key.
			result = get_trakt_list_contents(list_type, user, slug, with_auth, list_id)
			if params.get('shuffle', 'false') == 'true':
				shuffle(result)
				for c, i in enumerate(result):
					i['order'] = c
					if i.get('type') == 'season': i['custom_order'] = c
					elif i.get('type') == 'episode': i['custom_order'] = c
		process_list, total_pages, paginate_start = _paginate_list(result, page_no, paginate_start)
		all_movies = [i for i in process_list if i['type'] == 'movie']
		all_tvshows = [i for i in process_list if i['type'] == 'show']
		all_seasons = [i for i in process_list if i['type'] == 'season']
		all_episodes = [i for i in process_list if i['type'] == 'episode']
		movie_list = {'list': [(i['order'], i['media_ids']) for i in all_movies], 'id_type': 'trakt_dict', 'custom_order': 'true'}
		tvshow_list = {'list': [(i['order'], i['media_ids']) for i in all_tvshows], 'id_type': 'trakt_dict', 'custom_order': 'true'}
		season_list = {'list': all_seasons}
		episode_list = {'list': all_episodes}
		content = max([('movies', len(all_movies)), ('tvshows', len(all_tvshows)), ('seasons', len(all_seasons)), ('episodes', len(all_episodes))], key=lambda k: k[1])[0]
		for item in ((Movies, movie_list, 'movies'), (TVShows, tvshow_list, 'tvshows'),
					(single_seasons, season_list, 'seasons'), (build_single_episode, episode_list, 'episodes')):
			threaded_object = Thread(target=_process, args=item)
			threaded_object.start()
			threads.append(threaded_object)
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		if use_result: return content, [i[0] for i in item_list]
		new_params = {'mode': 'trakt.list.build_trakt_list', 'list_type': list_type, 'list_name': list_name, 'user': user, 'slug': slug,
						'paginate_start': paginate_start}
		kodi_utils.add_items(handle, [i[0] for i in item_list])
		if total_pages > 2 and jump_to_enabled() and not is_external:
				kodi_utils.add_dir(handle, {'mode': 'navigate_to_page_choice', 'current_page': page_no, 'total_pages': total_pages, 'url_params': json.dumps(new_params)},
											'Jump To...', 'item_jump', kodi_utils.get_icon('item_jump_landscape'), isFolder=False)
		if total_pages > page_no and not hide_next_page:
			new_page = str(page_no + 1)
			new_params['new_page'] = new_page
			kodi_utils.add_dir(handle, new_params,  'Next Page (%s) >>' % new_page, 'nextpage', kodi_utils.get_icon('nextpage_landscape'))
	except: pass
	kodi_utils.set_content(handle, content)
	kodi_utils.set_category(handle, list_name)
	no_disc_cache = is_external or params.get('shuffle', 'false') == 'true' or params.get('random', 'false') == 'true'
	kodi_utils.end_directory(handle, cacheToDisc=not no_disc_cache)
	if not is_external:
		if params.get('refreshed') == 'true': kodi_utils.sleep(1000)
		kodi_utils.set_view_mode('view.%s' % content, content, is_external)

def make_custom_artwork(params):
	action, list_name, list_type, list_id = params['action'], params['list_name'], params['list_type'], params['list_id'],
	user, slug, custom_image = params['user'], params['list_slug'], params['custom_image']
	art_type, image_type = ('Posters', 'poster') if action == 'make_poster' else ('Fanart', 'fanart')
	shuffle_art = kodi_utils.confirm_dialog(
		heading='Trakt My Lists', text='Use [B]4 Random[/B] %s from List?[CR]OR[CR]Use [B]First 4[/B] %s from List?' % (art_type, art_type),
		ok_label='4 Random', cancel_label='First 4')
	if shuffle_art == None: return
	new_image = trakt_image_maker(list_name, list_type, list_id, image_type, user, slug, custom_image, shuffle_art)
	kodi_utils.kodi_refresh()

def trakt_image_maker(list_name, list_type, list_id, image_type, user, slug, custom_image, shuffle_sort_order):
	from modules import metadata
	from modules.utils import make_image
	kodi_utils.show_busy_dialog()
	# The artwork must be built from the first four items the user sees. get_trakt_list_contents
	# resolves the list's sort override itself and falls back to the ordering Trakt declares for the
	# list, so the legacy per-list sort store - which nothing reads any more, and which raised a
	# KeyError here for any list that had no row - is no longer consulted.
	content = get_trakt_list_contents(list_type, user, slug, True, list_id)
	if shuffle_sort_order: shuffle(content)
	images = []
	api_key, mpaa, current_time, current_timestamp = tmdb_api_key(), mpaa_region(), get_datetime(), get_current_timestamp()
	for item in content:
		try:
			tmdb_id = item.get('tmdb_id') or item['media_ids']['tmdb']
			if not tmdb_id: continue
			media_type = item.get('type') or media_type_check[trakt_media_type]
			if media_type == 'movie': function = metadata.movie_meta
			else: function = metadata.tvshow_meta
			meta = function('tmdb_id', tmdb_id, api_key, mpaa, current_time, current_timestamp)
			if meta.get(image_type): images.append(meta[image_type])
			if len(images) == 4: break
		except: pass
	final_image = make_image('trakt_%s' % list_type, image_type, '%s_%s' % (list_name, user), images, custom_image)
	kodi_utils.hide_busy_dialog()
	return final_image

def delete_current_image(params):
	custom_image = params['custom_image']
	os.remove(custom_image)
	kodi_utils.sleep(1000)
	success = not kodi_utils.path_exists(custom_image)
	if success: kodi_utils.kodi_refresh()
	else: kodi_utils.notification('Error Deleting Image')

def set_list_custom_sort(params):
	"""Context menu entry for a Trakt user list. The dialog and the store both live elsewhere now.

	sort_by/sort_how still ride in on the context menu URL. They are the ordering Trakt itself
	declares for the list, which is what the list falls back to when no override is stored, so they
	are passed on as the fallback for the "current" marker rather than being written anywhere.
	"""
	from indexers.dialogs import list_sort_override_choice
	from modules import list_sort
	fallback = list_sort.trakt_list_fallback(params.get('sort_by'), params.get('sort_how'))
	list_sort_override_choice({'list_key': 'trakt.list:%s' % params['list_id'], 'adapter': 'trakt_list', 'fallback': fallback})
