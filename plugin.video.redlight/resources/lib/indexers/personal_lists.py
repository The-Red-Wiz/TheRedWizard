# -*- coding: utf-8 -*-
import os
import sys
import json
from random import shuffle
from threading import Thread
from urllib.parse import unquote
from caches.settings_cache import get_setting
from caches.personal_lists_cache import personal_lists_cache
from indexers.movies import Movies
from indexers.tvshows import TVShows
from modules import metadata
from modules import kodi_utils, settings
from modules.utils import TaskPool, paginate_list, sort_for_article, get_datetime, get_current_timestamp, make_image, download_image
# logger = kodi_utils.logger

def get_personal_lists(params):
	def _process():
		for item in data:
			try:
				list_name, sort_order, description, list_total = item['name'], item['sort_order'], item['description'], item['total']
				author, seen = item.get('author', 'Unknown'), item.get('seen', 'true')
				if show_author: name_insert = '%s | [I]%s[/I]' % (list_name, author)
				else: name_insert = list_name
				if new_list_check(seen) and unseen_highlight: display = '[COLOR %s]%s [I](x%02d)[/I][/COLOR]' % (unseen_highlight, name_insert, list_total)
				else: display = '%s [I](x%02d)[/I]' % (name_insert, list_total)
				custom_poster = item.get('poster', '')
				poster = custom_poster or icon
				custom_fanart = item.get('fanart', '')
				fanart = custom_fanart or background
				random_contents = random or shuffle_lists
				mode = 'random.build_personal_lists_contents' if random_contents else 'personal_lists.build_personal_list'
				url_params = {'mode': mode, 'list_name': list_name, 'category_name': list_name,
				'sort_order': 'shuffle' if random_contents else sort_order, 'seen': seen, 'author': author,
				'iconImage': poster, 'name': list_name}
				if random_contents: url_params['random'] = 'true'
				url = kodi_utils.build_folder_url(url_params)
				cm = [('[B]Make New List[/B]', 'RunPlugin(%s)' % build_url({'mode': 'personal_lists.make_new_personal_list'})),
				('[B]Edit Properties[/B]', 'RunPlugin(%s)' % build_url({'mode': 'personal_lists.adjust_personal_list_properties', 'description': description, 'author': author,
					'list_name': list_name, 'sort_order': sort_order, 'seen': seen, 'poster': custom_poster, 'fanart': custom_fanart})),
				('[B]Delete List[/B]', 'RunPlugin(%s)' % build_url({'mode': 'personal_lists.delete_personal_list', 'list_name': list_name, 'author': author,
					'poster': custom_poster, 'fanart': custom_fanart})),
				('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url}))]
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': poster, 'poster': poster, 'thumb': poster, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(description)
				listitem.addContextMenuItems(cm)
				yield (url, listitem, True)
			except: pass
	def _new_process():
		url = build_url({'mode': 'personal_lists.make_new_personal_list'})
		new_icon = kodi_utils.get_icon('new')
		listitem = kodi_utils.make_listitem()
		listitem.setLabel('[I]Make New Personal List...[/I]')
		listitem.setArt({'icon': new_icon, 'poster': new_icon, 'thumb': new_icon, 'fanart': background, 'banner': background})
		info_tag = listitem.getVideoInfoTag(True)
		info_tag.setPlot(' ')
		yield (url, listitem, False)
	icon, background = kodi_utils.get_icon('lists'), kodi_utils.get_addon_fanart()
	unseen_highlight = settings.personal_lists_unseen_highlight()
	show_author = settings.personal_lists_show_author()
	build_url = kodi_utils.build_url
	random, shuffle_lists = params.get('random', 'false') == 'true', params.get('shuffle', 'false') == 'true'
	returning_to_list = False
	handle = int(sys.argv[1])
	try:
		data = get_all_personal_lists(get_setting('redlight.personal_list.list_sort', '0'))
		if data:
			if shuffle_lists:
				returning_to_list = 'build_personal_lists_contents' in kodi_utils.folder_path()
				if returning_to_list:
					try: data = json.loads(kodi_utils.get_property('redlight.personal.lists.order'))
					except: pass
				else:
					shuffle(data)
					kodi_utils.set_property('redlight.personal.lists.order', json.dumps(data))
			else:
				kodi_utils.clear_property('redlight.personal.lists.order')
			result = list(_process())
		else: result = list(_new_process())
		kodi_utils.add_items(handle, result)
	except: pass
	kodi_utils.set_content(handle, kodi_utils.MENU_FOLDER_CONTENT)
	kodi_utils.set_category(handle, 'Personal Lists')
	if shuffle_lists and not returning_to_list: kodi_utils.focus_index(0)
	kodi_utils.end_directory(handle, cacheToDisc=not (random or shuffle_lists))
	kodi_utils.set_view_mode('view.main', kodi_utils.MENU_FOLDER_CONTENT)

def build_personal_list(params):
	def _process(function, _list):
		item_list_extend(function(_list).worker())
	def _paginate_list(data, page_no, paginate_start):
		if use_result: total_pages = 1
		elif paginate_enabled:
			limit = settings.page_limit(is_external)
			data, total_pages = paginate_list(data, page_no, limit, paginate_start)
			if is_external: paginate_start = limit
		else: total_pages = 1
		return data, total_pages, paginate_start
	handle, is_external = int(sys.argv[1]), kodi_utils.external()
	hide_next_page = is_external and settings.widget_hide_next_page()
	try:
		threads, item_list, content = [], [], 'movies'
		item_list_extend = item_list.extend
		paginate_enabled = settings.paginate(is_external)
		use_result = 'result' in params
		list_name, author, sort_order = params.get('list_name'), params.get('author'), params.get('sort_order')
		page_no, paginate_start = int(params.get('new_page', '1')), int(params.get('paginate_start', '0'))
		new_params = {'mode': 'personal_lists.build_personal_list', 'list_name': list_name, 'author': author, 'sort_order': sort_order, 'seen': 'true',
						'paginate_start': paginate_start}
		if page_no == 1 and not is_external: kodi_utils.set_property('redlight.exit_params', kodi_utils.list_collection_exit_params(params))
		if use_result: result = params.get('result', [])
		else: result = get_personal_list(params)
		process_list, total_pages, paginate_start = _paginate_list(result, page_no, paginate_start)
		movie_list = {'list': [(c, i['media_id']) for c, i in enumerate(process_list) if i['type'] == 'movie'], 'custom_order': 'true'}
		tvshow_list = {'list': [(c, i['media_id']) for c, i in enumerate(process_list) if i['type'] == 'tvshow'], 'custom_order': 'true'}
		content = 'movies' if len(movie_list['list']) > len(tvshow_list['list']) else 'tvshows'
		for item in ((Movies, movie_list), (TVShows, tvshow_list)):
			if not item[1]['list']: continue
			threaded_object = Thread(target=_process, args=item)
			threaded_object.start()
			threads.append(threaded_object)
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		if use_result: return content, [i[0] for i in item_list]
		kodi_utils.add_items(handle, [i[0] for i in item_list])
		if total_pages > 2 and settings.jump_to_enabled() and not is_external:
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

def get_all_personal_lists(sort_order=None):
	contents = personal_lists_cache.get_lists()
	try:
		if sort_order:
			contents.sort(key=lambda k: (k['total'] is None, k['total']), reverse=False)
			if sort_order in ('', '0', 'None'):
				contents = sort_for_article(contents, 'name', settings.ignore_articles())
			elif sort_order == '1':
				contents = sort_for_article(contents, 'author', settings.ignore_articles())
			elif sort_order in ('2', '3'):
				reverse = sort_order != '2'
				contents.sort(key=lambda k: (k['created_at'] is None, k['created_at']), reverse=reverse)
			elif sort_order in ('4', '5'):
				reverse = sort_order != '4'
				contents.sort(key=lambda k: k.get('updated', None) or '0', reverse=reverse)
			elif sort_order in ('6', '7'):
				reverse = sort_order != '6'
				contents.sort(key=lambda k: (k['total'] is None, k['total']), reverse=reverse)
	except: pass
	if settings.personal_lists_sort_unseen_to_top():
		unseen = [i for i in contents if new_list_check(i['seen'])]
		seen = [i for i in contents if not i in unseen]
		unseen.sort(key=lambda k: k['created_at'], reverse=True)
		contents = unseen + seen
	return contents

def personal_lists_split_by_membership(lists, tmdb_id):
	tmdb_id = str(tmdb_id)
	in_lists, out_lists = [], []
	for item in lists or []:
		contents = personal_lists_cache.get_list(item['name'], item.get('author', 'Unknown'), update_seen=False)
		if any(str(i.get('media_id')) == tmdb_id for i in contents):
			in_lists.append(item)
		else:
			out_lists.append(item)
	return in_lists, out_lists

def delete_personal_list(params):
	list_name, author, poster, fanart = params.get('list_name', ''), params.get('author', 'Unknown'), params.get('poster', ''), params.get('fanart', '')
	if not kodi_utils.confirm_dialog(heading='Personal Lists', text='Delete [B]%s[/B] Personal List?' % list_name): return
	if personal_lists_cache.delete_list(list_name, author):
		for image_type, custom_image in (('poster', poster), ('fanart', fanart)): delete_current_image(image_type, list_name, author, custom_image)
		_delete_sort_override(list_name, author)
		return kodi_utils.kodi_refresh()
	kodi_utils.notification('Error Deleting List', 3000)

def delete_personal_list_contents(params):
	list_name, author = params.get('list_name', ''), params.get('author', 'Unknown')
	if not list_change_warning(list_name): return
	if personal_lists_cache.delete_list_contents(list_name, author): return
	kodi_utils.notification('Error Deleting List Contents', 3000)

def get_personal_list(params):
	list_name, author, seen, update_seen = params['list_name'], params['author'], params.get('seen', True), params.get('update_seen', True)
	contents = personal_lists_cache.get_list(list_name, author, update_seen=update_seen, seen=seen)
	from modules import list_sort
	# No fallback, unlike the Trakt and TMDb call sites: those exist to preserve a provider's own
	# declared ordering for a list nobody has overridden yet. A personal list has no such ordering -
	# migrate_legacy_stores() already turned every list's old sort_order column into an override row,
	# so one with no override now is one nobody has ever chosen a sort for, and the engine's own
	# default (title:asc) is the right answer. A 'default:asc' fallback would read as "Provider
	# Default" for a provider that does not exist.
	return list_sort.sort_source(contents, 'personal:%s|%s' % (list_name, author), None, 'personal')

def make_new_personal_list(params):
	is_retry, external_creation = params.get('is_retry', False), params.get('external_creation', 'false') == 'true'
	chosen_list, suggested_list_name, suggested_author = params.get('chosen_list', []), params.get('suggested_list_name', ''), params.get('suggested_author', '')
	if not external_creation and not is_retry and kodi_utils.confirm_dialog(
		heading='Personal Lists',text='Import a Trakt List to populate this new list?', ok_label='Yes', cancel_label='No'):
		from apis.trakt_api import get_trakt_list_selection
		chosen_list = get_trakt_list_selection(['default', 'personal', 'liked'])
		if chosen_list == None:
			kodi_utils.notification(kodi_utils.LIST_CREATE_CANCELLED, 3000)
			return None, None
		params['chosen_list'] = chosen_list
		suggested_list_name = chosen_list.get('name')
		suggested_author = chosen_list.get('user')
		params.update({'suggested_list_name': suggested_list_name, 'suggested_author': suggested_author, 'chosen_list': chosen_list})
		if suggested_author in ('Collection', 'Watchlist'): suggested_author = get_setting('redlight.trakt.user')
	list_name = personal_list_name(suggested_list_name)
	if list_name == None:
		kodi_utils.notification(kodi_utils.LIST_CREATE_CANCELLED, 3000)
		return None, None
	author = personal_list_author(suggested_author)
	if not unique_list_check(list_name, author):
		params['is_retry'] = True
		return make_new_personal_list(params)
	description = personal_list_description()
	spec = personal_sort_order()
	if spec == None:
		kodi_utils.notification(kodi_utils.LIST_CREATE_CANCELLED, 3000)
		return None, None
	# The sort_order column is kept in step for anything that still displays it, but the list is
	# sorted from the override store - writing only the column, as this did before, meant every list
	# created after the upgrade ignored the sort order chosen right here and came back title first.
	success = personal_lists_cache.make_list(list_name, author, _legacy_sort_code(spec), description)
	if not success:
		kodi_utils.notification(kodi_utils.LIST_CREATE_ERROR, 3000)
		return None, None
	_set_sort_override(list_name, author, spec)
	if chosen_list:
		new_contents = process_trakt_list(chosen_list)
		result = personal_lists_cache.add_many_list_items(list_name, author, new_contents)
	if not external_creation and any([kodi_utils.path_check('get_personal_lists') or kodi_utils.external()]): kodi_utils.kodi_refresh()
	return list_name, author

def adjust_personal_list_properties(params):
	from modules import list_sort
	list_name, sort_order, author = params.get('list_name', ''), params.get('sort_order', ''), params.get('author', '')
	seen, description = params.get('seen', ''), params.get('description', '')
	poster, fanart = params.get('poster', ''), params.get('fanart', '')
	choices = [('Change Name', 'Currently [B]%s[/B]' % (list_name), 'list_name'),
				('Change Author', 'Currently [B]%s[/B]' % (author), 'author'),
				('Change Sort Order', 'Currently [B]%s[/B]' % list_sort.spec_label(_current_sort_spec(list_name, author)), 'sort_order'),
				('Change List Description', 'Currently [B]%s[/B]' % (description), 'description'),
				('Make Custom Poster', '', 'make_poster'),
				('Make Custom Fanart', '', 'make_fanart')]
	if poster: choices.append(('Delete Custom Poster', '', 'delete_poster'))
	if fanart: choices.append(('Delete Custom Fanart', '', 'delete_fanart'))
	choices.extend([('Empty List Contents', 'Delete All Contents of %s' % list_name, 'empty_contents'),
					('Import Trakt List', 'Import a Trakt List into %s' % list_name, 'import_trakt')])
	list_items = [{'line1': item[0], 'line2': item[1] or item[0]} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Personal List Properties', 'multi_line': 'true', 'narrow_window': 'true'}
	action = kodi_utils.select_dialog([i[2] for i in choices], **kwargs)
	if action == None: return kodi_utils.kodi_refresh() if params.get('refresh', 'false') == 'true' else None
	if action in ('make_poster', 'make_fanart'):
		art_type = 'Posters' if action == 'make_poster' else 'Fanart'
		shuffle_art = kodi_utils.confirm_dialog(
			heading='Personal Lists', text='Use [B]4 Random[/B] %s from List?[CR]OR[CR]Use [B]First 4[/B] %s from List?' % (art_type, art_type),
			ok_label='4 Random', cancel_label='First 4')
		if shuffle_art == None: return adjust_personal_list_properties(params)
	if action == 'list_name':
		new_name = personal_list_name(list_name)
		if new_name == None: return adjust_personal_list_properties(params)
		personal_lists_cache.update_single_detail('name', new_name, list_name, author)
		_move_sort_override(list_name, author, new_name, author)
		params.update({'list_name': new_name, 'refresh': 'true'})
	if action == 'author':
		new_author = personal_list_author(author)
		personal_lists_cache.update_single_detail('author', new_author, list_name, author)
		_move_sort_override(list_name, author, list_name, new_author)
		params.update({'author': new_author, 'refresh': 'true'})
	elif action == 'sort_order':
		spec = personal_sort_order(current=_current_sort_spec(list_name, author))
		if spec == None: return adjust_personal_list_properties(params)
		if _set_sort_override(list_name, author, spec):
			new_sort_order = _legacy_sort_code(spec)
			personal_lists_cache.update_single_detail('sort_order', new_sort_order, list_name, author)
			params.update({'sort_order': new_sort_order, 'refresh': 'true'})
	elif action == 'description':
		new_description = personal_list_description()
		personal_lists_cache.update_single_detail('description', new_description, list_name, author)
		params.update({'description': new_description, 'refresh': 'true'})
	elif action == 'make_poster':
		new_poster = personal_image_maker(list_name, author, 'poster', sort_order, seen, poster, shuffle_art)
		if new_poster is None: return adjust_personal_list_properties(params)
		personal_lists_cache.update_single_detail('poster', new_poster, list_name, author)
		params.update({'poster': new_poster, 'refresh': 'true'})
	elif action == 'make_fanart':
		new_fanart = personal_image_maker(list_name, author, 'fanart', sort_order, seen, fanart, shuffle_art)
		if new_fanart is None: return adjust_personal_list_properties(params)
		personal_lists_cache.update_single_detail('fanart', new_fanart, list_name, author)
		params.update({'fanart': new_fanart, 'refresh': 'true'})
	elif action == 'delete_poster':
		success = delete_current_image('poster', list_name, author, poster)
		if not success: return adjust_personal_list_properties(params)
		params.update({'poster': None, 'refresh': 'true'})
	elif action == 'delete_fanart':
		success = delete_current_image('fanart', list_name, author, fanart)
		if not success: return adjust_personal_list_properties(params)
		params.update({'fanart': None, 'refresh': 'true'})
	elif action == 'empty_contents':
		delete_personal_list_contents({'list_name': list_name, 'author': author})
		params.update({'refresh': 'true'})
	elif action == 'import_trakt':
		import_trakt_list({'list_name': list_name, 'author': author, 'description': description, 'sort_order': sort_order,
							'seen': seen, 'poster': poster, 'fanart': fanart})
		params.update({'refresh': 'true'})
	return adjust_personal_list_properties(params)

def delete_current_image(image_type, list_name, author, custom_image):
	try: os.remove(custom_image)
	except: pass
	kodi_utils.sleep(100)
	if kodi_utils.path_exists(custom_image): return False
	try: personal_lists_cache.update_single_detail(image_type, '', list_name, author)
	except: pass
	return True

def personal_image_maker(list_name, author, image_type, sort_order, seen, custom_image, shuffle_art, show_busy=True):
	if show_busy: kodi_utils.show_busy_dialog()
	content = get_personal_list({'list_name': list_name, 'author': author, 'sort_order': str(sort_order), 'update_seen': False, 'seen': seen})
	if shuffle_art: shuffle(content)
	images = []
	api_key, mpaa, current_time, current_timestamp = settings.tmdb_api_key(), settings.mpaa_region(), get_datetime(), get_current_timestamp()
	for item in content:
		if item['type'] == 'movie': function = metadata.movie_meta
		else: function = metadata.tvshow_meta
		meta = function('tmdb_id', item['media_id'], api_key, mpaa, current_time, current_timestamp)
		if meta.get(image_type): images.append(meta[image_type])
		if len(images) == 4: break
	final_image = make_image('personal_lists', image_type, list_name, images, custom_image)
	kodi_utils.hide_busy_dialog()
	if final_image: personal_lists_cache.update_single_detail(image_type, final_image, list_name, author)
	return final_image

def personal_image_downloader(list_name, author, image_type, url, sort_order, seen, custom_image, show_busy=True):
	if show_busy: kodi_utils.show_busy_dialog()
	content = get_personal_list({'list_name': list_name, 'author': author, 'sort_order': str(sort_order), 'update_seen': False, 'seen': seen})
	final_image = download_image('personal_lists', image_type, list_name, url, custom_image)
	kodi_utils.hide_busy_dialog()
	if final_image: personal_lists_cache.update_single_detail(image_type, final_image, list_name, author)
	return final_image

def personal_list_name(list_name=''):
	new_name = kodi_utils.kodi_dialog().input('Please Choose a Name for the New List', defaultt=list_name)
	if not new_name: return None
	new_name = unquote(new_name)
	return new_name

def personal_list_author(author=''):
	new_author = kodi_utils.kodi_dialog().input('Optional List Author', defaultt=author)
	if not new_author: return 'Unknown'
	new_author = unquote(new_author)
	return new_author

def personal_sort_order(current=None):
	"""The shared two stage sort picker. Returns a spec dict or None.

	No "Use Default" entry: a personal list is mixed media, so it has no mediatype default to fall
	back to. The adapter's own 'default' field (Provider Default) is the equivalent choice.
	"""
	from indexers.dialogs import _pick_sort_spec
	return _pick_sort_spec('List Sort Order', 'personal', current=current)

def _sort_scope(list_name, author):
	from caches.list_sort_cache import scope_key
	return scope_key('personal:%s|%s' % (list_name, author))

def _current_sort_spec(list_name, author):
	"""What get_personal_list will actually sort by. It passes no fallback, so an absent override
	means the engine's own default rather than the list's stored order."""
	from modules import list_sort
	return list_sort.resolve('personal:%s|%s' % (list_name, author))

def _legacy_sort_code(spec):
	"""The legacy sort_order column value for a spec, '0' (title) when the spec has no equivalent.

	Nothing reads the column for ordering any more; it is written only so exports and the row in
	personal_lists.db keep describing the same list the override store describes.
	"""
	from modules import list_sort
	spec_string = list_sort.format_spec(spec)
	for code, legacy_spec in list_sort.LEGACY_PERSONAL_CODES.items():
		if legacy_spec == spec_string and code != '': return code
	return '0'

def _set_sort_override(list_name, author, spec):
	from caches.list_sort_cache import set_override
	from modules import list_sort
	if set_override(_sort_scope(list_name, author), list_sort.format_spec(spec)): return True
	kodi_utils.notification('Error Setting Sort Order', 3000)
	return False

def _move_sort_override(old_name, old_author, new_name, new_author):
	"""A personal list's override scope is keyed by name and author, so a rename has to carry it."""
	from caches.list_sort_cache import get_override, set_override, delete_override
	old_scope, new_scope = _sort_scope(old_name, old_author), _sort_scope(new_name, new_author)
	if old_scope == new_scope: return
	spec_string = get_override(old_scope)
	if not spec_string: return
	if set_override(new_scope, spec_string): delete_override(old_scope)

def _delete_sort_override(list_name, author):
	"""Same defect class as the rename orphan above: the override scope is keyed by name and author,
	not by any id the deleted row still owns, so a deleted list's row would otherwise sit there ready
	to be silently inherited by a future list created with the same name and author. Best effort - a
	failed delete leaves a harmless orphaned row, since the list it described is already gone."""
	from caches.list_sort_cache import delete_override
	delete_override(_sort_scope(list_name, author))

def personal_list_description():
	description = kodi_utils.kodi_dialog().input('Optional Description for the New List') or ' '
	if not description: return None
	description = unquote(description)
	return description

def import_trakt_list(params):
	media_type_check = {'movie': 'movie', 'show': 'tvshow', 'tvshow': 'tvshow'}
	list_name, author, description, sort_order, seen = params['list_name'], params['author'], params['description'], params['sort_order'], params['seen']
	poster, fanart = params['poster'], params['fanart']
	if not list_change_warning(list_name): return
	from apis.trakt_api import get_trakt_list_selection, trakt_fetch_collection_watchlist, get_trakt_list_contents
	chosen_list = get_trakt_list_selection(['default', 'personal', 'liked'])
	if chosen_list == None: return
	trakt_list_name = chosen_list.get('name')
	new_contents = process_trakt_list(chosen_list)
	result = personal_lists_cache.add_many_list_items(list_name, author, new_contents)
	if result == 'Success':
		if kodi_utils.confirm_dialog(heading='Personal Lists', text='Rename List to Match Trakt List Name?', ok_label='Yes', cancel_label='No'):
			personal_lists_cache.update_single_detail('name', trakt_list_name, list_name, author)
			_move_sort_override(list_name, author, trakt_list_name, author)
	kodi_utils.notification(result, 3000)

def process_trakt_list(chosen_list):
	from apis.trakt_api import trakt_fetch_collection_watchlist, get_trakt_list_contents
	media_type_check = {'movie': 'movie', 'show': 'tvshow', 'tvshow': 'tvshow'}
	new_contents = []
	new_contents_append = new_contents.append
	current_timestamp = get_current_timestamp()
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
	for count, item in enumerate(result):
		try:
			media_type = item.get('type') or media_type_check[trakt_media_type]
			if trakt_list_type in ('my_lists', 'liked_lists') and item['type'] not in ('movie', 'show'): continue
			media_id = item['media_ids']['tmdb']
			if media_id in (None, 'None', ''): continue
			title = item['title']
			try: release_date = item['released'].split('T')[0]
			except: release_date = item['released']
			date_added = current_timestamp + count
			new_contents_append({'media_id': str(media_id), 'title': title, 'type': media_type_check[media_type],
								'release_date': release_date, 'date_added': str(date_added)})
		except: continue
	return new_contents

def external_process_view(params):
	def _process(function, _list, _type):
		if not _list.get('list', []): return
		data = function(_list).worker()
		results_extend(data)
	tmdb_movies, imdb_movies, tmdb_tvshows, imdb_tvshows = {}, {}, {}, {}
	item_list, list_name, list_type, media_type = json.loads(params['item_list']), params['list_name'], params['list_type'], params['media_type']
	movies = {'list': [(i['order'], i['id']) for i in item_list if i['mt'] == 'm'], 'id_type': '%s_id' % list_type, 'custom_order': 'true'}
	tvshows = {'list': [(i['order'], i['id']) for i in item_list if i['mt'] == 'tv'], 'id_type': '%s_id' % list_type, 'custom_order': 'true'}
	threads, results = [], []
	results_extend = results.extend
	handle, is_external = int(sys.argv[1]), kodi_utils.external()
	content = max([('movies', len(tmdb_movies.get('list', []) + imdb_movies.get('list', []))), ('tvshows', len(tmdb_tvshows.get('list', []) + imdb_tvshows.get('list', [])))],
					key=lambda k: k[1])[0]
	for item in ((Movies, movies, 'movies'), (TVShows, tvshows, 'tvshows')):
		threaded_object = Thread(target=_process, args=item)
		threaded_object.start()
		threads.append(threaded_object)
	[i.join() for i in threads]
	results.sort(key=lambda k: k[1])
	kodi_utils.add_items(handle, [i[0] for i in results])
	kodi_utils.set_content(handle, content)
	kodi_utils.set_category(handle, list_name)
	kodi_utils.end_directory(handle, cacheToDisc=False if is_external else True)
	if not is_external:
		if params.get('refreshed') == 'true': kodi_utils.sleep(1000)
		kodi_utils.set_view_mode('view.%s' % content, content, is_external)

class ExternalImport:
	def __init__(self, params, item_list):
		self.results = []
		self.progressDialog = None
		self.results_append = self.results.append
		self.item_list = item_list
		self.total_items = len(self.item_list)
		self.list_name, self.list_type, self.media_type = params.get('list_name'), params.get('list_type', None), params.get('media_type', None)
		self.action, self.author, self.description = params.get('action', None), params.get('author', 'Unknown') or 'Unknown', params.get('description', '')
		self.import_indicator, self.poster, self.fanart = params.get('busy_indicator', 'none'), params.get('poster', ''), params.get('fanart', '')
		self.api_key, self.mpaa, self.current_time, self.current_timestamp = settings.tmdb_api_key(), settings.mpaa_region(), get_datetime(), get_current_timestamp()
	
	def process(self, item):
		try:
			original_id, id_type, order = item['id'], '%s_id' % self.list_type, item['order']
			m_type = item.get('mt') or self.media_type
			m_type = 'movie' if m_type == 'm' else 'tvshow'
			function = metadata.movie_meta if m_type == 'movie' else metadata.tvshow_meta
			meta = function(id_type, original_id, self.api_key, self.mpaa, self.current_time, self.current_timestamp)
			title, media_id, release_date, date_added = meta['title'], meta['tmdb_id'], meta['premiered'], self.current_timestamp + order
			self.results_append({'media_id': str(media_id), 'title': title, 'type': m_type, 'release_date': release_date, 'date_added': str(date_added), 'order': order})
			if self.progressDialog: self.progressDialog.update(meta['title'], int(float(len(self.results)) / float(self.total_items) * 100), meta['poster'])
		except: pass
	
	def run(self):
		if self.import_indicator == 'busy': kodi_utils.show_busy_dialog()
		elif self.import_indicator == 'progress':
			self.progressDialog = kodi_utils.progress_dialog('Importing Media', kodi_utils.get_icon('lists'))
			kodi_utils.sleep(1000)
		threads = TaskPool().tasks(self.process, self.item_list, min(self.total_items, settings.max_threads()))
		[i.join() for i in threads]
		self.results.sort(key=lambda k: k['order'])
		success = personal_lists_cache.make_list(self.list_name, self.author, '1', self.description, seen='true' if self.action == 'import_view' else 'false')
		if not success: return kodi_utils.notification('Error Creating [B]%s[/B]' % self.list_name, 3000)
		# Legacy code '1' is date added ascending, which for an import is the order of the imported
		# file. The column no longer orders anything, so the same choice has to be stored as an
		# override or the imported list comes back alphabetised.
		_set_sort_override(self.list_name, self.author, {'field': 'date_added', 'direction': 'asc'})
		items_added = personal_lists_cache.add_many_list_items(self.list_name, self.author, self.results)
		if items_added == 'Success':
			if self.poster: self.poster = personal_image_maker(self.list_name, self.author, 'poster', '1', 'false', '', True if self.poster == 'random' else False, show_busy=False)
			if self.fanart:
				if self.fanart not in ('first_4', 'random'):
					personal_image_downloader(self.list_name, self.author, 'fanart', self.fanart, '1', 'false', '', show_busy=False)
				else:
					self.fanart = personal_image_maker(self.list_name, self.author, 'fanart', '1', 'false', '', True if self.fanart == 'random' else False, show_busy=False)
			self.close_indicator()
			kodi_utils.notification('Items Added to New List [B]%s[/B]' % self.list_name, 3000)
		else:
			self.close_indicator()
			kodi_utils.notification('Error Adding Items to [B]%s[/B]' % self.list_name, 3000)
	
	def close_indicator(self):
		if self.progressDialog:
			self.progressDialog.close()
			kodi_utils.sleep(100)
		elif self.import_indicator == 'busy': kodi_utils.hide_busy_dialog()

def external(params):
	kodi_utils.sleep(200)
	kodi_utils.close_all_dialog()
	kodi_utils.sleep(200)
	action = params.get('action', None)
	list_name, list_type, media_type = params.get('list_name'), params.get('list_type', None), params.get('media_type_default', None)
	params['media_type'] = media_type
	if not action:
		choices = [('View', 'view'), ('Import', 'import'), ('Import & View', 'import_view')]
		list_items = [{'line1': i[0]} for i in choices]
		kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true', 'heading': 'TESTING: Choose Import Action'}
		choice = kodi_utils.select_dialog(choices, **kwargs)
		if choice == None: return
		action = choice[1]
	item_list = params.get('list_items', '')
	if not item_list:
		base_64 = params.get('base64_items') or ''
		if base_64:
			import gzip
			import base64
			try:
				payload_bytes = base64.b64decode(base_64)
				try: json_bytes = gzip.decompress(payload_bytes)
				except: json_bytes = payload_bytes
				item_list = json.loads(json_bytes.decode('utf-8', 'ignore'))
			except: kodi_utils.notification('Invalid External Payload (base64_items)', 4000)
	else: item_list = json.loads(params.get('list_items', '[]'))
	if not item_list: return kodi_utils.notification('No Items in Import List. Try Again.', 3000)
	item_list = [dict(i, **{'order': c, 'mt': i.get('mt') or media_type}) for c, i in enumerate(item_list)]
	if list_name: list_name = unquote(list_name)
	else: list_name = personal_list_name()
	if not list_name: return
	if 'import' in action: ExternalImport(params, [(i,) for i in item_list]).run()
	if 'view' in action:
		kodi_utils.activate_window({'mode': 'personal_lists.external_process_view', 'item_list': json.dumps(item_list), 'media_type': media_type,
									'list_type': list_type, 'list_name': list_name}, True)
	if action == 'import' and (kodi_utils.path_check('get_personal_lists') or kodi_utils.external()): kodi_utils.kodi_refresh()

def unique_list_check(list_name, author='Unknown'):
	contents = personal_lists_cache.get_lists()
	list_names = [i['name'] for i in contents]
	list_authors = [i['author'] for i in contents]
	if list_name in list_names and author in list_authors:
		kodi_utils.notification('List Already Exists. Choose a different name or author')
		return False
	return True

def new_list_check(seen):
	return seen != 'true'

def list_change_warning(list_name, text='[B]CAUTION!!![/B][CR][CR]This will change the contents of [B]%s[/B]. Continue?'):
	return kodi_utils.confirm_dialog(heading='Personal Lists', text=text % list_name, ok_label='Yes', cancel_label='No')