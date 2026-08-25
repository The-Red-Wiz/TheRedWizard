# -*- coding: utf-8 -*-
import json
import sys
from random import shuffle
from threading import Thread
from apis.mdblist_api import (
	mdbl_get_lists, mdbl_get_liked_lists, mdbl_top_lists, get_mdbl_list_payload,
	mdbl_list_media_type, mdbl_unified_item_tmdb_id, mdbl_ordered_list_rows, mdbl_search_lists
)
from indexers.movies import Movies
from indexers.tvshows import TVShows
from indexers.episodes import build_single_episode
from modules import kodi_utils, settings
from modules.utils import paginate_list
from modules.settings import paginate, page_limit, widget_hide_next_page, jump_to_enabled

def _mdbl_parent_exit_path(params=None):
	folder_path = kodi_utils.folder_path()
	parent_tokens = (
		'navigator.mdblist_lists', 'navigator.my_lists', 'get_mdbl_lists',
		'get_mdbl_liked_lists', 'get_mdbl_top_lists', 'search_mdbl_my_lists', 'search_mdbl_lists'
	)
	if any(token in folder_path for token in parent_tokens): return kodi_utils.sanitize_folder_url(folder_path)
	params = params or {}
	list_type = params.get('list_type', 'my_lists')
	if list_type == 'liked_lists':
		return kodi_utils.build_folder_url({'mode': 'mdblist.get_mdbl_liked_lists', 'name': 'Liked Lists'})
	if list_type == 'user_lists':
		return kodi_utils.build_folder_url({'mode': 'mdblist.get_mdbl_top_lists', 'name': 'Popular MDBLists'})
	return kodi_utils.build_folder_url({'mode': 'mdblist.get_mdbl_lists', 'name': 'My Lists'})

def _set_mdbl_browse_exit_params():
	if kodi_utils.external(): return
	kodi_utils.set_property('redlight.exit_params', _mdbl_parent_exit_path())

def _set_mdbl_list_exit_params(params):
	if kodi_utils.external(): return
	try: page_no = int(params.get('new_page', '1'))
	except: page_no = 1
	if page_no != 1: return
	kodi_utils.set_property('redlight.exit_params', _mdbl_parent_exit_path(params))

def _mdbl_list_open_params(item, list_type, random_contents=False):
	name, list_id = item.get('name', ''), item.get('id')
	url_params = {
		'mode': 'random.build_mdblist_lists_contents' if random_contents else 'mdblist.build_mdbl_list',
		'list_id': list_id,
		'list_type': list_type,
		'list_name': name,
		'media_type': mdbl_list_media_type(item),
		'name': name
	}
	if random_contents: url_params['random'] = 'true'
	return url_params

def _mdbl_list_user(item):
	return (item or {}).get('user_name') or (item or {}).get('username') or ''

def _mdbl_folder_plot(item, user=''):
	return kodi_utils.list_folder_plot((item or {}).get('description'), user or _mdbl_list_user(item),
		(item or {}).get('items'), (item or {}).get('likes'))

def _mdbl_shuffle_catalogue(lists, order_prop):
	returning_to_list = 'build_mdblist_lists_contents' in kodi_utils.folder_path()
	if returning_to_list:
		try:
			stored = json.loads(kodi_utils.get_property(order_prop) or '')
			if isinstance(stored, list) and stored: return stored
		except: pass
	shuffle(lists)
	try: kodi_utils.set_property(order_prop, json.dumps(lists))
	except: pass
	return lists

def get_mdbl_lists(params):
	def _process():
		for item in lists:
			try:
				name, list_id = item.get('name', ''), item.get('id')
				if list_id in (None, '', 0, '0'): continue
				item_list_type = 'external' if item.get('source') else 'my_lists'
				count = item.get('items', '?')
				display = '%s (x%s)' % (name, count)
				if item_list_type == 'external': display = '[COLOR cyan][I]%s[/I][/COLOR]' % display
				elif item.get('dynamic') or (item.get('type') or '').lower() in ('dynamic', 'ai', 'ailist', 'ai_list'):
					display = '[COLOR magenta][I]%s[/I][/COLOR]' % display
				else:
					display = '[B]%s[/B]' % display
				url = build_url(_mdbl_list_open_params(item, item_list_type, random_contents))
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(_mdbl_folder_plot(item))
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	_set_mdbl_browse_exit_params()
	icon, fanart, build_url = kodi_utils.get_icon('mdblist'), kodi_utils.get_addon_fanart(), kodi_utils.build_url
	random_contents = params.get('random', 'false') == 'true' or params.get('shuffle', 'false') == 'true'
	from apis.mdblist_api import _mdbl_list_is_static, _mdbl_list_is_dynamic
	my_lists = mdbl_get_lists('my_lists', refresh=True)
	external = mdbl_get_lists('external', refresh=True)
	static = [i for i in my_lists if _mdbl_list_is_static(i)]
	dynamic = [i for i in my_lists if _mdbl_list_is_dynamic(i)]
	lists = static + dynamic + external
	if params.get('shuffle', 'false') == 'true':
		lists = _mdbl_shuffle_catalogue(lists, 'redlight.mdblist.my_lists.lists.order')
	else:
		static.sort(key=lambda k: (k.get('name') or '').lower())
		dynamic.sort(key=lambda k: (k.get('name') or '').lower())
		external.sort(key=lambda k: (k.get('name') or '').lower())
		lists = static + dynamic + external
	kodi_utils.add_items(handle, list(_process()))
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, params.get('name', 'MDBList Lists'))
	kodi_utils.end_directory(handle, cacheToDisc=not random_contents)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def get_mdbl_liked_lists(params):
	def _process():
		for item in lists:
			try:
				name, list_id = item.get('name', ''), item.get('id')
				if list_id in (None, '', 0, '0'): continue
				user = item.get('user_name', '')
				count = item.get('items', '?')
				if user: display = '[B]%s[/B] | [I](x%s) - %s[/I]' % (name, count, user)
				else: display = '%s (x%s)' % (name, count)
				url = build_url(_mdbl_list_open_params(item, 'liked_lists', random_contents))
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(_mdbl_folder_plot(item, user))
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	_set_mdbl_browse_exit_params()
	icon, fanart, build_url = kodi_utils.get_icon('mdblist'), kodi_utils.get_addon_fanart(), kodi_utils.build_url
	random_contents = params.get('random', 'false') == 'true' or params.get('shuffle', 'false') == 'true'
	# Flat liked catalogue (Trakt-style). Omit media_type to include all list types.
	media_type = params.get('media_type')
	if media_type in ('', 'None', None): media_type = None
	lists = mdbl_get_liked_lists(media_type)
	if params.get('shuffle', 'false') == 'true':
		lists = _mdbl_shuffle_catalogue(lists, 'redlight.mdblist.liked_lists.lists.order')
	else:
		lists.sort(key=lambda k: (k.get('name') or '').lower())
	kodi_utils.add_items(handle, list(_process()))
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, params.get('name', 'Liked Lists'))
	kodi_utils.end_directory(handle, cacheToDisc=not random_contents)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def get_mdbl_top_lists(params):
	def _process():
		for item in lists:
			try:
				name, list_id = item.get('name', ''), item.get('id')
				if list_id in (None, '', 0, '0'): continue
				user = item.get('user_name', '')
				count = item.get('items', '?')
				display = '[B]%s[/B] | [I](x%s) - %s[/I]' % (name, count, user)
				url = build_url(_mdbl_list_open_params(item, 'user_lists', random_contents))
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(_mdbl_folder_plot(item, user))
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	_set_mdbl_browse_exit_params()
	icon, fanart, build_url = kodi_utils.get_icon('mdblist'), kodi_utils.get_addon_fanart(), kodi_utils.build_url
	random_contents = params.get('random', 'false') == 'true' or params.get('shuffle', 'false') == 'true'
	lists = mdbl_top_lists()
	if params.get('shuffle', 'false') == 'true':
		lists = _mdbl_shuffle_catalogue(lists, 'redlight.mdblist.user_lists.lists.order')
	kodi_utils.add_items(handle, list(_process()))
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, params.get('name', 'Popular MDBLists'))
	kodi_utils.end_directory(handle, cacheToDisc=not random_contents)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def search_mdbl_my_lists(params):
	"""Search the authenticated user's MDBLists by name (local filter, not public search)."""
	def _process():
		for item in data:
			try:
				name, list_id = item.get('name', ''), item.get('id')
				if list_id in (None, '', 0, '0'): continue
				item_list_type = 'external' if item.get('source') else 'my_lists'
				count = item.get('items', '?')
				display = '%s [I](x%s)[/I]' % (name, count)
				if item_list_type == 'external': display = '[COLOR cyan][I]%s[/I][/COLOR]' % display
				url = build_url(_mdbl_list_open_params(item, item_list_type))
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(_mdbl_folder_plot(item))
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	icon, fanart, build_url = kodi_utils.get_icon('mdblist'), kodi_utils.get_addon_fanart(), kodi_utils.build_url
	search_title = params.get('key_id') or params.get('query') or ''
	query = search_title.strip().lower()
	try:
		if not settings.mdblist_user_active():
			data = []
		else:
			from apis.mdblist_api import _mdbl_list_is_static, _mdbl_list_is_dynamic
			my_lists = mdbl_get_lists('my_lists', refresh=True)
			external = mdbl_get_lists('external', refresh=True)
			static = [i for i in my_lists if _mdbl_list_is_static(i)]
			dynamic = [i for i in my_lists if _mdbl_list_is_dynamic(i)]
			data = static + dynamic + external
			if query: data = [i for i in data if query in (i.get('name') or '').lower()]
			data.sort(key=lambda k: (k.get('name') or '').lower())
		kodi_utils.add_items(handle, list(_process()))
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, search_title.capitalize() if search_title else 'Search My MDBLists')
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def search_mdbl_lists(params):
	"""Public MDBList search by title, username, list ID, or mdblist.com URL. Opens via build_mdbl_list (static + dynamic)."""
	def _process():
		for item in data:
			try:
				name, list_id = item.get('name', ''), item.get('id')
				if list_id in (None, '', 0, '0'): continue
				if item.get('private') and not item.get('_id_lookup'): continue
				user = _mdbl_list_user(item)
				count = item.get('items', '?')
				display = '[B]%s[/B] | [I](x%s) - %s[/I]' % (name, count, user)
				if item.get('dynamic') or (item.get('type') or '').lower() in ('dynamic', 'ai', 'ailist', 'ai_list'):
					display = '[COLOR magenta][I]%s[/I][/COLOR] | [I](x%s) - %s[/I]' % (name, count, user)
				url = build_url(_mdbl_list_open_params(item, 'user_lists'))
				cm = [('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url}))]
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(_mdbl_folder_plot(item, user))
				listitem.addContextMenuItems(cm)
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	_set_mdbl_browse_exit_params()
	icon, fanart, build_url = kodi_utils.get_icon('mdblist'), kodi_utils.get_addon_fanart(), kodi_utils.build_url
	search_title = params.get('key_id') or params.get('query') or ''
	try:
		if not settings.mdblist_user_active(): data = []
		else: data = mdbl_search_lists(search_title) or []
		if data and all(item.get('_id_lookup') for item in data):
			data.sort(key=lambda k: ((k.get('name') or '').lower(), (k.get('mediatype') or '').lower()))
		kodi_utils.add_items(handle, list(_process()))
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, search_title.capitalize() if search_title else 'Search MDBLists')
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def _mdbl_item_tmdb_id(item):
	return mdbl_unified_item_tmdb_id(item)

def build_mdbl_watchlist(params):
	_set_mdbl_list_exit_params(params)
	media_type = params.get('media_type', 'movie')
	media_kind = 'movies' if media_type in ('movie', 'movies') else 'shows'
	from apis.mdblist_api import mdblist_watchlist
	data, _ = mdblist_watchlist(media_kind, 1)
	id_list = [_mdbl_item_tmdb_id(i) for i in (data or [])]
	id_list = [i for i in id_list if i]
	category = params.get('category_name') or params.get('name') or ('Movies Watchlist' if media_kind == 'movies' else 'TV Shows Watchlist')
	params.update({'list': id_list, 'action': 'mdblist_user_list', 'category_name': category})
	if media_type in ('movie', 'movies'):
		return Movies(params).fetch_list()
	return TVShows(params).fetch_list()

def build_mdbl_library(params):
	_set_mdbl_list_exit_params(params)
	media_type = params.get('media_type', 'movie')
	media_kind = 'movies' if media_type in ('movie', 'movies') else 'shows'
	from apis.mdblist_api import mdblist_collection
	data, _ = mdblist_collection(media_kind, 1)
	id_list = [_mdbl_item_tmdb_id(i) for i in (data or [])]
	id_list = [i for i in id_list if i]
	category = params.get('category_name') or params.get('name') or ('Movies Library' if media_kind == 'movies' else 'TV Shows Library')
	params.update({'list': id_list, 'action': 'mdblist_user_list', 'category_name': category})
	if media_type in ('movie', 'movies'):
		return Movies(params).fetch_list()
	return TVShows(params).fetch_list()

def build_mdbl_list(params):
	def _process(function, _list, _type):
		if not _list['list']: return
		if _type in ('movies', 'tvshows'): item_list_extend(function(_list).worker())
		else: item_list_extend(function('episode.mdblist_list', _list['list']))

	def _paginate_list(data, page_no, paginate_start):
		if use_result: total_pages = 1
		elif paginate_enabled:
			limit = page_limit(is_external)
			data, total_pages = paginate_list(data, page_no, limit, paginate_start)
			if is_external: paginate_start = limit
		else: total_pages = 1
		return data, total_pages, paginate_start

	handle, is_external, content = int(sys.argv[1]), kodi_utils.external(), 'movies'
	hide_next_page = is_external and widget_hide_next_page()
	list_name = params.get('list_name') or params.get('category_name') or 'MDBList'
	try:
		threads, item_list = [], []
		item_list_extend = item_list.extend
		paginate_enabled = paginate(is_external)
		use_result = 'result' in params
		page_no, paginate_start = int(params.get('new_page', '1')), int(params.get('paginate_start', '0'))
		list_id, list_type = params.get('list_id'), params.get('list_type', 'my_lists')
		if page_no == 1 and not is_external and not use_result:
			_set_mdbl_list_exit_params(params)
		if use_result:
			result = params.get('result', [])
		else:
			result = mdbl_ordered_list_rows(get_mdbl_list_payload(list_type, list_id))
			if params.get('shuffle', 'false') == 'true':
				shuffle(result)
				for c, i in enumerate(result):
					i['order'] = c
					i['custom_order'] = c
		process_list, total_pages, paginate_start = _paginate_list(result, page_no, paginate_start)
		all_movies = [i for i in process_list if i.get('type') == 'movie']
		all_tvshows = [i for i in process_list if i.get('type') == 'show']
		all_episodes = [i for i in process_list if i.get('type') == 'episode']
		def _id_rows(rows):
			out = []
			for c, i in enumerate(rows):
				media_ids = i.get('media_ids') or {}
				if media_ids.get('tmdb') or media_ids.get('imdb') or media_ids.get('tvdb'):
					out.append((i.get('order', c), media_ids))
			return out
		movie_list = {'list': _id_rows(all_movies), 'id_type': 'trakt_dict', 'custom_order': 'true'}
		tvshow_list = {'list': _id_rows(all_tvshows), 'id_type': 'trakt_dict', 'custom_order': 'true'}
		episode_list = {'list': all_episodes}
		content = max(
			[('movies', len(all_movies)), ('tvshows', len(all_tvshows)), ('episodes', len(all_episodes))],
			key=lambda k: k[1]
		)[0]
		for item in (
			(Movies, movie_list, 'movies'),
			(TVShows, tvshow_list, 'tvshows'),
			(build_single_episode, episode_list, 'episodes')
		):
			threaded_object = Thread(target=_process, args=item)
			threaded_object.start()
			threads.append(threaded_object)
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		if use_result: return content, [i[0] for i in item_list]
		new_params = {
			'mode': 'mdblist.build_mdbl_list',
			'list_id': list_id,
			'list_type': list_type,
			'list_name': list_name,
			'media_type': params.get('media_type', 'movie'),
			'paginate_start': paginate_start
		}
		if params.get('shuffle', 'false') == 'true': new_params['shuffle'] = 'true'
		kodi_utils.add_items(handle, [i[0] for i in item_list])
		if total_pages > 2 and jump_to_enabled() and not is_external:
			kodi_utils.add_dir(
				handle,
				{'mode': 'navigate_to_page_choice', 'current_page': page_no, 'total_pages': total_pages, 'url_params': json.dumps(new_params)},
				'Jump To...', 'item_jump', kodi_utils.get_icon('item_jump_landscape'), isFolder=False
			)
		if total_pages > page_no and not hide_next_page:
			new_page = str(page_no + 1)
			new_params['new_page'] = new_page
			kodi_utils.add_dir(handle, new_params, 'Next Page (%s) >>' % new_page, 'nextpage', kodi_utils.get_icon('nextpage_landscape'))
	except Exception as e:
		try: kodi_utils.logger('MDBList List Error', 'build_mdbl_list: %s' % e)
		except: pass
	kodi_utils.set_content(handle, content)
	kodi_utils.set_category(handle, list_name)
	no_disc_cache = is_external or params.get('shuffle', 'false') == 'true' or params.get('random', 'false') == 'true'
	kodi_utils.end_directory(handle, cacheToDisc=not no_disc_cache)
	if not is_external:
		if content == 'episodes':
			kodi_utils.set_view_mode('view.episodes_single', 'episodes', is_external, fallback_view_types=('view.episodes',))
		else:
			kodi_utils.set_view_mode('view.%s' % content, content, is_external)
