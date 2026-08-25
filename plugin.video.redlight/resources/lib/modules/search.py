# -*- coding: utf-8 -*-
import json
from urllib.parse import unquote
from caches.main_cache import main_cache
from indexers.people import person_search
from indexers.easynews import search_easynews_image
from modules.kodi_utils import close_all_dialog, external, build_url, kodi_dialog, execute_builtin, select_dialog, notification, kodi_refresh, folder_path, sanitize_folder_url, container_update
# from modules.kodi_utils import logger

def _refresh_search_history_if_visible():
	try:
		folder = folder_path()
		if folder and 'navigator.search_history' in folder:
			container_update(sanitize_folder_url(folder))
	except: pass

def get_key_id(params):
	close_all_dialog()
	params_key_id = params.get('key_id', None)
	key_id = params_key_id or kodi_dialog().input('')
	if not key_id: return
	key_id = unquote(key_id)
	media_type = params.get('media_type', '')
	search_type = params.get('search_type', 'media_title')
	string = None
	if search_type == 'media_title':
		if media_type == 'movie': url_params, string = {'mode': 'build_movie_list', 'action': 'tmdb_movies_search'}, 'movie_queries'
		elif media_type == 'tv_show': url_params, string = {'mode': 'build_tvshow_list', 'action': 'tmdb_tv_search', 'is_anime_list': 'false'}, 'tvshow_queries'
		elif media_type == 'anime': url_params, string = {'mode': 'build_tvshow_list', 'action': 'tmdb_tv_search', 'is_anime_list': 'true'}, 'anime_queries'
		else: url_params, string = {'mode': 'build_tvshow_list', 'action': 'tmdb_tv_search'}, 'tvshow_anime_queries'#media_type=tvshow_anime
	elif search_type == 'people': string = 'people_queries'
	elif search_type == 'tmdb_keyword':
		url_params, string = {'mode': 'navigator.keyword_results', 'media_type': media_type}, 'keyword_tmdb_%s_queries' % media_type
	elif search_type == 'tmdb_collection':
		url_params, string = {'mode': 'navigator.collection_results'}, 'collection_tmdb_queries'
	elif search_type == 'easynews_video':
		url_params, string = {'mode': 'easynews.search_easynews'}, 'easynews_video_queries'
	elif search_type == 'easynews_image':
		url_params, string = {'mode': 'easynews.search_easynews_image'}, 'easynews_image_queries'
	elif search_type == 'nzb_search':
		url_params, string = {'mode': 'nzb.search_nzb'}, 'nzb_queries'
	elif search_type == 'trakt_lists':
		url_params, string = {'mode': 'trakt.list.search_trakt_lists'}, 'trakt_list_queries'
	elif search_type == 'trakt_my_lists':
		url_params, string = {'mode': 'trakt.list.search_trakt_my_lists'}, 'trakt_my_list_queries'
	elif search_type == 'mdblist_my_lists':
		url_params, string = {'mode': 'mdblist.search_mdbl_my_lists'}, 'mdblist_my_list_queries'
	elif search_type == 'mdblist_lists':
		url_params, string = {'mode': 'mdblist.search_mdbl_lists'}, 'mdblist_list_queries'
	elif search_type == 'simkl_lists':
		url_params, string = {'mode': 'simkl.list.search_simkl_lists'}, 'simkl_list_queries'
	elif search_type == 'punchplay_lists':
		url_params, string = {'mode': 'punchplay.list.search_punchplay_lists'}, 'punchplay_list_queries'
	elif search_type == 'punchplay_public_lists':
		url_params, string = {'mode': 'punchplay.list.search_punchplay_public_lists'}, 'punchplay_public_list_queries'
	if string: history_changed = add_to_search(key_id, string)
	else: history_changed = False
	if search_type == 'people':
		person_search(key_id)
		if history_changed: _refresh_search_history_if_visible()
		return
	if search_type == 'easynews_image':
		search_easynews_image(key_id)
		if history_changed: _refresh_search_history_if_visible()
		return
	url_params.update({'query': key_id, 'key_id': key_id, 'name': 'Search Results for %s' % key_id})
	return execute_builtin('ActivateWindow(Videos,%s,return)' if external() else 'Container.Update(%s)' % build_url(url_params))

def add_to_search(search_name, search_list):
	try:
		result = list(main_cache.get(search_list) or [])
		if result and result[0] == search_name:
			return False
		if search_name in result:
			result.remove(search_name)
		result.insert(0, search_name)
		result = result[:50]
		main_cache.set(search_list, result, expiration=8760)
		return True
	except: return False

def remove_from_search(params):
	try:
		result = main_cache.get(params['setting_id'])
		result.remove(params.get('key_id'))
		main_cache.set(params['setting_id'], result, expiration=8760)
		notification('Success', 2500)
		kodi_refresh()
	except: return

def clear_search():
	clear_history_list = [('Clear Movie Search History', 'movie_queries'),
	('Clear TV Show Search History', 'tvshow_queries'),
	('Clear Anime Search History', 'anime_queries'),
	('Clear TV Show & Anime Search History', 'tvshow_anime_queries'),
	('Clear People Search History', 'people_queries'),
	('Clear Collections Search History', 'collection_tmdb_queries'),
	('Clear Keywords Movie Search History', 'keyword_tmdb_movie_queries'),
	('Clear Keywords TV Show Search History', 'keyword_tmdb_tvshow_queries'),
	('Clear EasyNews Search History', 'easynews_video_queries'),
	('Clear EasyNews Search History', 'easynews_image_queries'),
	('Clear NZB Indexer Search History', 'nzb_queries'),
	('Clear Trakt User Lists Search History', 'trakt_list_queries'),
	('Clear Trakt My Lists Search History', 'trakt_my_list_queries'),
	('Clear MDBList My Lists Search History', 'mdblist_my_list_queries'),
	('Clear MDBList Search History', 'mdblist_list_queries'),
	('Clear Simkl List Search History', 'simkl_list_queries'),
	('Clear PunchPlay List Search History', 'punchplay_list_queries'),
	('Clear PunchPlay Lists Search History', 'punchplay_public_list_queries')]
	try:
		list_items = [{'line1': item[0]} for item in clear_history_list]
		kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
		setting_id = select_dialog([item[1] for item in clear_history_list], **kwargs)
		if setting_id == None: return
		clear_all(setting_id)
	except: return

def clear_all(setting_id, refresh='false'):
	main_cache.set(setting_id, '', expiration=365)
	notification('Success', 2500)
	if refresh == 'true': kodi_refresh()

def clear_easynews_search_history(refresh='false', silent=False):
	main_cache.set('easynews_video_queries', '', expiration=365)
	main_cache.set('easynews_image_queries', '', expiration=365)
	if not silent: notification('Success', 2500)
	if refresh == 'true': kodi_refresh()

	