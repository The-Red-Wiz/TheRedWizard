# -*- coding: utf-8 -*-
import os
import sys
import json
from random import shuffle
from threading import Thread
from urllib.parse import unquote
from apis.tmdblist_api import tmdb_list_api
from caches.settings_cache import get_setting
from caches.tmdb_lists import tmdb_lists_cache
from indexers.movies import Movies
from indexers.tvshows import TVShows
from modules.utils import paginate_list, sort_for_article, gen_md5, jsondate_to_datetime as js2date
from modules.settings import paginate, page_limit, widget_hide_next_page, ignore_articles, jump_to_enabled
from modules import kodi_utils
# logger = kodi_utils.logger

def get_tmdb_lists(params):
	def get_custom_image(list_name, image_type, images):
		try:
			md5_image_name = gen_md5(list_name)
			custom_image = [i for i in images if i.rsplit('_', 1)[0] == md5_image_name][0]
			return os.path.join(profile_path, 'images', 'tmdb_lists_%s' % image_type, custom_image)
		except: return ''
	def _process():
		for item in data:
			try:
				list_name, list_id, item_count = item['name'], item['id'], item['number_of_items']
				sort_order = sort_orders.get(list_id, 'None')
				updated_at = item['updated_at']
				custom_poster = get_custom_image(list_name, 'poster', all_posters)
				if custom_poster: poster = custom_poster
				else: poster = icon
				custom_fanart = get_custom_image(list_name, 'fanart', all_fanart)
				if custom_fanart: fanart = custom_fanart
				else: fanart = background
				random_contents = random or shuffle_lists
				mode = 'random.build_tmdb_lists_contents' if random_contents else 'tmdblist.build_tmdb_list'
				url_params = {'mode': mode, 'list_id': list_id, 'list_name': list_name,
				'sort_order': 'shuffle' if random_contents else sort_order, 'updated_at': updated_at, 'iconImage': poster, 'name': list_name}
				if random_contents: url_params['random'] = 'true'
				url = kodi_utils.build_folder_url(url_params)
				display = '%s [I](x%02d)[/I]' % (list_name, item_count)
				cm = [('[B]Make New List[/B]', 'RunPlugin(%s)' % build_url({'mode': 'tmdblist.make_new_tmdb_list'})),
				('[B]Set Custom Sort[/B]', 'RunPlugin(%s)' % build_url({'mode': 'list_sort_override_choice', 'list_key': 'tmdb:%s' % list_id,
					'adapter': 'tmdb', 'fallback': 'default:asc'})),
				('[B]Edit Properties[/B]', 'RunPlugin(%s)' % build_url({'mode': 'tmdblist.adjust_tmdb_list_properties', 'list_id': list_id, 'updated_at': updated_at,
					'original_list_name': list_name, 'original_sort_order': sort_order, 'custom_poster': custom_poster, 'custom_fanart': custom_fanart})),
				('[B]Delete List[/B]', 'RunPlugin(%s)' % build_url({'mode': 'tmdblist.delete_tmdb_list', 'list_id': list_id})),
				('[B]Clear Contents Cache[/B]', 'RunPlugin(%s)' % build_url({'mode': 'tmdblist.cache_delete_list_tmdb', 'list_id': list_id})),
				('[B]Clear All Lists Cache[/B]', 'RunPlugin(%s)' % build_url({'mode': 'tmdblist.cache_delete_all_tmdb'})),
				('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url}))]
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': poster, 'poster': poster, 'thumb': poster, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(' ')
				listitem.addContextMenuItems(cm)
				yield (url, listitem, True)
			except: pass
	def _new_process():
		url = build_url({'mode': 'tmdblist.make_new_tmdb_list'})
		new_icon = kodi_utils.get_icon('new')
		listitem = kodi_utils.make_listitem()
		listitem.setLabel('[I]Make New TMDb List...[/I]')
		listitem.setArt({'icon': new_icon, 'poster': new_icon, 'thumb': new_icon, 'fanart': background, 'banner': background})
		info_tag = listitem.getVideoInfoTag(True)
		info_tag.setPlot(' ')
		yield (url, listitem, False)
	handle, icon, background = int(sys.argv[1]), kodi_utils.get_icon('tmdb'), kodi_utils.get_addon_fanart()
	tmdb_image_url = 'https://image.tmdb.org/t/p/%s%s'
	profile_path = kodi_utils.addon_profile()
	all_posters = kodi_utils.list_dirs(os.path.join(profile_path, 'images', 'tmdb_lists_poster'))[1]
	all_fanart = kodi_utils.list_dirs(os.path.join(profile_path, 'images', 'tmdb_lists_fanart'))[1]
	sort_orders = get_sort_orders()
	build_url = kodi_utils.build_url
	random, shuffle_lists = params.get('random', 'false') == 'true', params.get('shuffle', 'false') == 'true'
	returning_to_list = False
	try:
		data = get_all_tmdb_lists(get_setting('redlight.tmdblist.list_sort', '0'))
		if data:
			if shuffle_lists:
				returning_to_list = 'build_tmdb_lists_contents' in kodi_utils.folder_path()
				if returning_to_list:
					try: data = json.loads(kodi_utils.get_property('redlight.tmdb.lists.order'))
					except: pass
				else:
					shuffle(data)
					kodi_utils.set_property('redlight.tmdb.lists.order', json.dumps(data))
			else:
				kodi_utils.clear_property('redlight.tmdb.lists.order')
			result = list(_process())
		else: result = list(_new_process())
		kodi_utils.add_items(handle, result)
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, params.get('category_name', ''))
	if shuffle_lists and not returning_to_list: kodi_utils.focus_index(0)
	kodi_utils.end_directory(handle, cacheToDisc=not (random or shuffle_lists))
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def build_tmdb_list(params):
	def _process(function, _list, _type):
		if not _list['list']: return
		item_list_extend(function(_list).worker())
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
	try:
		threads, item_list = [], []
		item_list_extend = item_list.extend
		user, slug, list_type = '', '', ''
		paginate_enabled = paginate(is_external)
		use_result = 'result' in params
		list_name, list_id, media_type, sort_order = params.get('list_name'), params.get('list_id'), params.get('media_type'), params.get('sort_order')
		page_no, paginate_start = int(params.get('new_page', '1')), int(params.get('paginate_start', '0'))
		new_params = {'mode': 'tmdblist.build_tmdb_list', 'list_id': list_id, 'list_name': list_name, 'media_type': media_type,
						'paginate_start': paginate_start, 'sort_order': sort_order}
		if page_no == 1 and not is_external: kodi_utils.set_property('redlight.exit_params', kodi_utils.list_collection_exit_params(params))
		if use_result: result = params.get('result', [])
		else: result = get_tmdb_list(params)
		result, total_pages, paginate_start = _paginate_list(result, page_no, paginate_start)
		all_movies = [dict(i, **{'order': c}) for c, i in enumerate(result) if i['media_type'] == 'movie']
		all_tvshows = [dict(i, **{'order': c}) for c, i in enumerate(result) if i['media_type'] == 'tv']
		movie_list = {'list': [(i['order'], i['id']) for i in all_movies], 'custom_order': 'true'}
		tvshow_list = {'list': [(i['order'], i['id']) for i in all_tvshows], 'custom_order': 'true'}
		content = max([('movies', len(all_movies)), ('tvshows', len(all_tvshows))], key=lambda k: k[1])[0]
		for item in ((Movies, movie_list, 'movies'), (TVShows, tvshow_list, 'tvshows')):
			threaded_object = Thread(target=_process, args=item)
			threaded_object.start()
			threads.append(threaded_object)
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		if use_result: return content, [i[0] for i in item_list]
		kodi_utils.add_items(handle, [i[0] for i in item_list])
		if total_pages > 2 and jump_to_enabled() and not is_external:
				kodi_utils.add_dir(handle, {'mode': 'navigate_to_page_choice', 'current_page': page_no, 'total_pages': total_pages, 'url_params': json.dumps(new_params)},
											'Jump To...', 'item_jump', kodi_utils.get_icon('item_jump_landscape'), isFolder=False)
		if total_pages > page_no and not hide_next_page:
			new_page = str(page_no + 1)
			new_params['new_page'] = new_page
			kodi_utils.add_dir(handle, new_params, 'Next Page (%s) >>' % new_page, 'nextpage', kodi_utils.get_icon('nextpage_landscape'))
	except: pass
	kodi_utils.set_content(handle, content)
	kodi_utils.set_category(handle, list_name)
	kodi_utils.end_directory(handle, cacheToDisc=False if is_external else True)
	if not is_external:
		if params.get('refreshed') == 'true': kodi_utils.sleep(1000)
		kodi_utils.set_view_mode('view.%s' % content, content, is_external)

def adjust_tmdb_list_properties(params):
	from modules import list_sort
	list_id = params.get('list_id')
	original_list_name = params.get('original_list_name', '')
	custom_poster, custom_fanart = params.get('custom_poster', ''), params.get('custom_fanart', '')
	current_name = params.get('list_name', '') or original_list_name
	# The sort_order carried in the URL is the legacy column, which nothing reads any more. The label
	# and the picker both go through the override store so the row states what the list actually does.
	# 'default:asc' is get_tmdb_list's fallback: no override means the list is served in TMDb order.
	current_sort = list_sort.resolve('tmdb:%s' % list_id, None, 'default:asc')
	choices = [('Change Name', 'Currently [B]%s[/B]' % (current_name), 'list_name'),
				('Change Sort Order', 'Currently [B]%s[/B]' % list_sort.spec_label(current_sort), 'sort_order'),
				('Make Custom Poster', '', 'make_poster'),
				('Make Custom Fanart', '', 'make_fanart')]
	if custom_poster: choices.append(('Delete Custom Poster', '', 'delete_poster'))
	if custom_fanart: choices.append(('Delete Custom Fanart', '', 'delete_fanart'))
	choices.extend([('Empty List Contents', 'Delete All Contents of %s' % current_name, 'empty_contents'),
					('Import Trakt List', 'Import a Trakt List into %s' % current_name, 'import_trakt')])
	list_items = [{'line1': item[0], 'line2': item[1] or item[0]} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'TMDb List Properties', 'multi_line': 'true', 'narrow_window': 'true'}
	action = kodi_utils.select_dialog([i[2] for i in choices], **kwargs)
	if action == None:
		if params.get('refresh_cache', 'false') == 'true': cache_delete_all_tmdb()
		elif params.get('refresh', 'false') == 'true': return kodi_utils.kodi_refresh()
		return None
	if action in ('make_poster', 'make_fanart'):
		art_type = 'Posters' if action == 'make_poster' else 'Fanart'
		shuffle_sort_order = kodi_utils.confirm_dialog(heading='TMDb Lists', text='Use [B]4 Random[/B] %s from List?[CR]OR[CR]Use [B]First 4[/B] %s from List?' % (art_type, art_type),
												ok_label='4 Random', cancel_label='First 4')
		if shuffle_sort_order == None: return adjust_tmdb_list_properties(params)
	if action == 'list_name':
		list_name = rename_tmdb_list(current_name, list_id)
		if not list_name: return adjust_tmdb_list_properties(params)
		current_name = list_name
		params.update({'list_name': current_name, 'refresh_cache': 'true'})
	elif action == 'sort_order':
		from caches.list_sort_cache import set_override
		from indexers.dialogs import _pick_sort_spec
		# No "Use Default" entry: a TMDb list is mixed media, so it has no mediatype default to fall
		# back to. The equivalent choice is the adapter's own 'default' field (Provider Default),
		# which stores 'default:asc' and hands back TMDb's ordering untouched.
		spec = _pick_sort_spec('List Sort Order', 'tmdb', current=current_sort)
		if spec == None: return adjust_tmdb_list_properties(params)
		if set_override('tmdb:%s' % list_id, list_sort.format_spec(spec)): params.update({'refresh': 'true'})
		else: kodi_utils.notification('Error Setting Sort Order', 3000)
	elif action == 'make_poster':
		new_poster = tmdb_image_maker(current_name, list_id, 'poster', custom_poster, shuffle_sort_order)
		if new_poster is None: return adjust_tmdb_list_properties(params)
		params.update({'custom_poster': new_poster, 'refresh': 'true'})
	elif action == 'make_fanart':
		new_fanart = tmdb_image_maker(current_name, list_id, 'fanart', custom_fanart, shuffle_sort_order)
		if new_fanart is None: return adjust_tmdb_list_properties(params)
		params.update({'custom_fanart': new_fanart, 'refresh': 'true'})
	elif action == 'delete_poster':
		success = delete_current_image(custom_poster)
		if not success: return adjust_tmdb_list_properties(params)
		params.update({'custom_poster': None, 'refresh': 'true'})
	elif action == 'delete_fanart':
		success = delete_current_image(custom_fanart)
		if not success: return adjust_tmdb_list_properties(params)
		params.update({'custom_fanart': None, 'refresh': 'true'})
	elif action == 'empty_contents':
		if not clear_tmdb_list(current_name, list_id): return adjust_tmdb_list_properties(params)
		params.update({'refresh_cache': 'true'})
	elif action == 'import_trakt':
		import_trakt_list_tmdb({'list_name': current_name, 'list_id': list_id})
		params.update({'refresh_cache': 'true'})
	return adjust_tmdb_list_properties(params)

def delete_current_image(custom_image):
	os.remove(custom_image)
	kodi_utils.sleep(1000)
	if kodi_utils.path_exists(custom_image): return False
	return True

def tmdb_image_maker(list_name, list_id, image_type, custom_image, shuffle_sort_order):
	from modules.utils import make_image
	kodi_utils.show_busy_dialog()
	content = get_tmdb_list({'list_id': list_id})
	if shuffle_sort_order: shuffle(content)
	images = []
	if image_type == 'poster': image_dimension, image_key = 'w780', 'poster_path'
	else: image_dimension, image_key = 'w1280', 'backdrop_path'
	for item in content:
		if item[image_key]: images.append('https://image.tmdb.org/t/p/%s%s' % (image_dimension, item[image_key]))
		if len(images) == 4: break
	final_image = make_image('tmdb_lists', image_type, list_name, images, custom_image)
	kodi_utils.hide_busy_dialog()
	return final_image

def _tmdb_media_type(media_type):
	if media_type in ('movie', 'movies'): return 'movie'
	return 'tv'

def _tmdb_list_remove_succeeded(data):
	if not data: return False
	results = data.get('results')
	if isinstance(results, list):
		if not results: return False
		return any(isinstance(i, dict) and i.get('success') for i in results)
	return bool(data.get('success'))

def add_remove_watchfavs(media_type, media_id, list_type, status):
	media_type = _tmdb_media_type(media_type)
	data = tmdb_list_api.add_remove_from_watchfavs(media_type, media_id, list_type, status)
	if not data or not data.get('success'):
		if not status: kodi_utils.notify_not_in_list()
		else: kodi_utils.notify_error()
		return False
	return True

def add_to_tmdb_list(list_id, items, list_name=None, notify=True):
	data = tmdb_list_api.add_remove_from_list(list_id, items, 'post')
	if not data or not data.get('success'):
		if notify: kodi_utils.notify_error()
		return False
	if notify: kodi_utils.notify_added_to(list_name)
	return True

def remove_from_tmdb_list(list_id, items, list_name=None):
	try:
		payload = {'items': []}
		for item in items.get('items', []):
			if not isinstance(item, dict): continue
			payload['items'].append({'media_type': _tmdb_media_type(item.get('media_type', '')), 'media_id': int(item.get('media_id'))})
		if not payload['items']: raise ValueError('no_items')
		data = tmdb_list_api.add_remove_from_list(list_id, payload, 'delete')
		if not _tmdb_list_remove_succeeded(data):
			kodi_utils.notify_not_in_list(settle_ms=300)
			return False
		kodi_utils.notify_removed_from(list_name)
		return True
	except:
		kodi_utils.notify_not_in_list(settle_ms=300)
		return False

def rename_tmdb_list(current_name, list_id):
	list_name = kodi_utils.kodi_dialog().input('Please Choose a Name for the New List', defaultt=current_name)
	if list_name == None: return None
	tmdb_list_api.rename_list(list_id, list_name)
	return list_name

def check_item_status(list_id, media_type, media_id):
	media_type = _tmdb_media_type(media_type)
	try: media_id = int(media_id)
	except: return False
	cached = tmdb_lists_cache.get('get_list_details_%s' % list_id)
	if cached is not None:
		try:
			return any(i.get('media_type') == media_type and int(i.get('id')) == media_id for i in cached)
		except: return False
	try:
		item_status = tmdb_list_api.item_status(list_id, media_type, media_id)
		return item_status.get('success', False) if item_status else False
	except: return False

def check_item_status_watchfav(list_id, media_type, media_id):
	try:
		media_type = _tmdb_media_type(media_type)
		items = tmdb_list_api.get_watchfavrecs_list_details(list_id, media_type) or []
		return int(media_id) in [i['id'] for i in items]
	except: return False

def tmdb_lists_split_by_membership(media_type, media_id):
	from modules.utils import TaskPool
	from modules.settings import max_threads
	results = []
	results_append = results.append
	def _check(item):
		list_id = item.get('id')
		if not list_id: return
		entry = {
			'name': item.get('name') or '',
			'id': list_id,
			'number_of_items': int(item.get('number_of_items') or 0)
		}
		results_append((entry, check_item_status(list_id, media_type, media_id)))
	all_lists = get_all_tmdb_lists('0') or []
	if not all_lists: return [], []
	threads = TaskPool().tasks(_check, all_lists, min(len(all_lists), max_threads()) or 1)
	[i.join() for i in threads]
	in_lists, out_lists = [], []
	for entry, is_in in results:
		(in_lists if is_in else out_lists).append(entry)
	in_lists.sort(key=lambda k: k['name'])
	out_lists.sort(key=lambda k: k['name'])
	return in_lists, out_lists

def select_tmdb_lists(lists):
	if not lists: return None
	choices = [('%s [I](x%02d)[/I]' % (i['name'], i.get('number_of_items', 0)), i['id']) for i in lists]
	list_items = [{'line1': i[0]} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
	return kodi_utils.select_dialog([i[1] for i in choices], **kwargs)

def make_new_tmdb_list(params):
	suggested_list_name, chosen_list = '', None
	external_creation = params.get('external_creation', 'false') == 'true'
	if not external_creation and kodi_utils.confirm_dialog(heading='TMDb Lists', text='Import a Trakt List to populate this new list?',
																				ok_label='Yes', cancel_label='No'):
		from apis.trakt_api import get_trakt_list_selection
		chosen_list = get_trakt_list_selection(['default', 'personal'])
		if chosen_list == None:
			kodi_utils.notification(kodi_utils.LIST_CREATE_CANCELLED, 3000)
			return None
		suggested_list_name = chosen_list.get('name')
	list_name = kodi_utils.kodi_dialog().input('Please Choose a Name for the New TMDb List', defaultt=suggested_list_name)
	if not list_name:
		kodi_utils.notification(kodi_utils.LIST_CREATE_CANCELLED, 3000)
		return None
	list_name = unquote(list_name)
	data = tmdb_list_api.make_list(list_name)
	if not data or not data.get('success') or not data.get('id'):
		kodi_utils.notification(kodi_utils.LIST_CREATE_ERROR, 3000)
		return None
	if chosen_list:
		new_contents = process_trakt_list(chosen_list)
		success = process_add_to_list(data.get('id'), new_contents)
	tmdb_lists_cache.clear_all_lists()
	if not external_creation: kodi_utils.kodi_refresh()
	return data.get('id'), list_name

def delete_tmdb_list(params):
	if not kodi_utils.confirm_dialog(heading='TMDb Lists', text='Are You Sure?', ok_label='Yes', cancel_label='No'): return
	list_id = params['list_id']
	data = tmdb_list_api.delete_list(list_id)
	if not data.get('success'): return kodi_utils.notification('Error Deleting List')
	tmdb_lists_cache.clear_list(list_id)
	tmdb_lists_cache.clear_all_lists()
	kodi_utils.kodi_refresh()

def clear_tmdb_list(list_name, list_id):
	if not list_change_warning(list_name): return None
	data = tmdb_list_api.clear_list(list_id)
	if not data.get('success'):
		kodi_utils.notification('Error Clearing List Contents')
		return None
	tmdb_lists_cache.clear_list(list_id)
	tmdb_lists_cache.clear_all_lists()
	return True

def get_all_tmdb_lists(sort_order=None):
	contents = tmdb_list_api.get_user_lists() or []
	try:
		if sort_order:
			if sort_order in ('', '0', 'None'):
				contents = sort_for_article(contents, 'name', ignore_articles())
			elif sort_order in ('1', '2'):
				reverse = sort_order != '1'
				contents.sort(key=lambda k: (k['created_at'] is None, k['created_at']), reverse=reverse)
			elif sort_order in ('3', '4'):
				reverse = sort_order != '3'
				contents.sort(key=lambda k: (k['updated_at'] is None, k['updated_at']), reverse=reverse)
			elif sort_order in ('5', '6'):
				reverse = sort_order != '5'
				contents.sort(key=lambda k: (k['number_of_items'] is None, k['number_of_items']), reverse=reverse)
			elif sort_order in ('7', '8'):
				reverse = sort_order != '7'
				contents.sort(key=lambda k: (k['average_rating'] is None, k['average_rating']), reverse=reverse)
			elif sort_order in ('9', '10'):
				reverse = sort_order != '9'
				contents.sort(key=lambda k: (k['runtime'] is None, k['runtime']), reverse=reverse)
			elif sort_order in ('11', '12'):
				reverse = sort_order != '11'
				contents.sort(key=lambda k: (k['revenue'] is None, k['revenue']), reverse=reverse)
	except: pass
	return contents

def get_tmdb_list(params):
	list_id, media_type = params['list_id'], params.get('media_type')
	if list_id in ('watchlist', 'favorites', 'recommendations'):
		contents = [dict(i, **{'media_type': media_type}) for i in tmdb_list_api.get_watchfavrecs_list_details(list_id, media_type)]
	else:
		contents = tmdb_list_api.get_list_details(list_id)
	contents = [dict(i, **{'title': i.get('title') or i.get('name'), 'release_date': i.get('release_date') or i.get('first_air_date')}) for i in contents]
	from modules import list_sort
	# No override means the list was never sorted client-side: the old getters fell back to code 4
	# (original_order) for watchlist/favorites and to the stored 'None' for a user list. DEFAULT_SPEC
	# would reorder every one of them to title on upgrade, with no legacy row left to migrate.
	# Fixed shelves are media-split (tmdb.watchlist:movies / :shows) with media_type=None so
	# "Use Default" / no override keeps TMDb provider order via fallback — not Content → Movies/TV.
	# Custom My Lists stay mixed under tmdb:<id>.
	if list_id in ('watchlist', 'favorites', 'recommendations'):
		sort_media = 'movies' if media_type in ('movie', 'movies') else 'shows'
		return list_sort.sort_source(contents, 'tmdb.%s:%s' % (list_id, sort_media), None, 'tmdb', fallback='default:asc')
	return list_sort.sort_source(contents, 'tmdb:%s' % list_id, None, 'tmdb', fallback='default:asc')

def cache_delete_all_tmdb(params=None):
	tmdb_lists_cache.clear_all()
	kodi_utils.notification('Success')
	kodi_utils.kodi_refresh()

def cache_delete_list_tmdb(params):
	tmdb_lists_cache.clear_list(params['list_id'])
	tmdb_lists_cache.clear_all_lists()
	kodi_utils.notification('Success')
	kodi_utils.kodi_refresh()

def import_trakt_list_tmdb(params):
	if not list_change_warning(params['list_name']): return None
	from apis.trakt_api import get_trakt_list_selection
	list_id = params.get('list_id', '')
	chosen_list = get_trakt_list_selection(['default', 'personal'])
	if chosen_list == None: return None
	if kodi_utils.confirm_dialog(heading='TMDb Lists', text='Rename List to Match Trakt List Name?', ok_label='Yes', cancel_label='No'): rename_list = True
	else: rename_list = False
	trakt_list_name = chosen_list.get('name')
	new_contents = process_trakt_list(chosen_list)
	success = process_add_to_list(list_id, new_contents)
	if success and rename_list:
			tmdb_list_api.rename_list(list_id, trakt_list_name)
	kodi_utils.notify_success() if success else kodi_utils.notify_error()

def process_trakt_list(chosen_list):
	from apis.trakt_api import trakt_fetch_collection_watchlist, get_trakt_list_contents
	tmdb_media_converter = {'movie': 'movie', 'tvshow': 'tv', 'show': 'tv'}
	media_type_check = {'movie': 'movie', 'show': 'tvshow', 'tvshow': 'tvshow'}
	new_contents = []
	new_contents_append = new_contents.append
	trakt_list_type, trakt_list_name = chosen_list.get('list_type'), chosen_list.get('name')
	if trakt_list_type in ('collection', 'watchlist'):
		trakt_media_type = chosen_list.get('media_type')
		result = trakt_fetch_collection_watchlist(trakt_list_type, trakt_media_type)
		try:
			from modules import list_sort
			result = list_sort.sort_source(result, 'trakt.%s' % trakt_list_type, trakt_media_type, 'trakt_sync')
		except: pass
	else:
		result = get_trakt_list_contents(trakt_list_type, chosen_list.get('user'), chosen_list.get('slug'), trakt_list_type == 'my_lists')
		try: result.sort(key=lambda k: (k['order']))
		except: pass
	for item in result:
		try:
			media_type = item.get('type') or media_type_check[trakt_media_type]
			if trakt_list_type in ('my_lists', 'liked_lists') and item['type'] not in ('movie', 'show'): continue
			media_id = item['media_ids']['tmdb']
			if media_id in (None, 'None', ''): continue
			new_contents_append({'media_type': tmdb_media_converter[media_type], 'media_id': media_id})
		except: continue
	return new_contents

def process_add_to_list(list_id, new_contents):
	success = False
	kodi_utils.show_busy_dialog()
	try:
		if add_to_tmdb_list(list_id, {'items': new_contents}, notify=False):
			success = True
			tmdb_lists_cache.clear_list(list_id)
			tmdb_lists_cache.clear_all_lists()
		else: pass
	except: pass
	kodi_utils.hide_busy_dialog()
	return success

def get_sort_orders():
	return tmdb_lists_cache.get_sort_orders()

def list_change_warning(list_name, text='[B]CAUTION!!![/B][CR][CR]This will change the contents of [B]%s[/B]. Continue?'):
	return kodi_utils.confirm_dialog(heading='TMDb Lists', text=text % list_name, ok_label='Yes', cancel_label='No')

