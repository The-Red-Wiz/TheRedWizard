# -*- coding: utf-8 -*-
import json
from caches.settings_cache import get_setting, set_setting, set_default, default_setting_values
from modules import kodi_utils, settings
# logger = kodi_utils.logger

def window_theme_choice(params):
	if params['type'] == 'theme':
		choices = kodi_utils.addon_themes()
		list_items = [{'line1': i['name'], 'icon': kodi_utils.get_icon(i['icon'], 'themes')} for i in choices]
		kwargs = {'items': json.dumps(list_items), 'heading': 'Assign a Theme', 'narrow_window': 'true'}
		choice = kodi_utils.select_dialog(choices, **kwargs)
		if choice == None: return
		window_theme, window_theme_contrast, window_theme_name = choice['value'][0][2:], choice['value'][1], choice['name']
		window_theme_opacity = get_setting('redlight.window_theme_opacity', 'CC')
		set_setting('window_theme_name', window_theme_name)
	else:
		choices = kodi_utils.addon_themes_opacity()
		list_items = [{'line1': i['name']} for i in choices]
		kwargs = {'items': json.dumps(list_items), 'heading': 'Assign an Opacity Level', 'narrow_window': 'true'}
		choice = kodi_utils.select_dialog(choices, **kwargs)
		if choice == None: return
		window_theme_opacity, window_theme_opacity_name = choice['value'], choice['name']
		window_theme = get_setting('redlight.window_theme', 'FF1F2020')[2:]
		window_theme_contrast = get_setting('redlight.window_theme_contrast', 'FF4a4347')
		set_setting('window_theme_opacity', window_theme_opacity)
		set_setting('window_theme_opacity_name', window_theme_opacity_name)
	set_setting('window_theme', window_theme_opacity + window_theme)
	set_setting('window_theme_contrast', window_theme_contrast)

def rpdb_poster_format_choice(params):
	choices = [{'name': 'default', 'value': ''}, {'name': 'blocks', 'value': '&theme=blocks'}, {'name': 'rounded', 'value': '&theme=rounded-blocks'}]
	list_items = [{'line1': i['name'], 'icon': kodi_utils.get_icon('rpdb_%s' % i['name'], 'rpdb_posters', 'jpg')} for i in choices]
	kwargs = {'items': json.dumps(list_items)}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return
	set_setting('rpdb_format', choice['value'])
	set_setting('rpdb_format_name', choice['name'])

def navigate_to_page_choice(params):
	def _builder():
		for item in start_list:
			if item == current_page: line1 = '[COLOR blue][B]Page %s   |   Current Page[/B][/COLOR]' % item
			else: line1 = 'Page %s' % item
			yield {'line1': line1}
	try:
		current_page, total_pages = int(params.get('current_page')), int(params.get('total_pages'))
		start_list = [i for i in range(1, total_pages+1)]
		list_items = list(_builder())
		kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true', 'set_focus': current_page - 1}
		new_page = kodi_utils.select_dialog(start_list, **kwargs)
		if new_page == None or new_page == current_page: return
		url_params = json.loads(params['url_params'])
		url_params.update({'new_page': new_page, 'refreshed': 'true'})
		kodi_utils.container_update(url_params)
	except: return

def list_display_order_choice(params):
	from modules.meta_lists import list_display_choices
	list_type = params['list_type']
	info = list_display_choices(list_type)
	choices = info['choices']
	list_items = [{'line1': i[0]} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return
	set_setting('%s.list_sort_name' % info['setting'], choice[0])
	set_setting('%s.list_sort' % info['setting'], choice[1])

def language_invoker_choice(params):
	from xml.dom.minidom import parse as mdParse
	kodi_utils.close_all_dialog()
	addon_xml = kodi_utils.translate_path('special://home/addons/plugin.video.redlight/addon.xml')
	root = mdParse(addon_xml)
	invoker_instance = root.getElementsByTagName('reuselanguageinvoker')[0].firstChild
	current_invoker_setting = (invoker_instance.data or 'true').strip().lower()
	new_value = {'true': 'false', 'false': 'true'}[current_invoker_setting]
	if not kodi_utils.confirm_dialog(text='Turn [B]Reuse Language Invoker[/B] %s?' % ('On' if new_value == 'true' else 'Off')): return
	if new_value == 'true' and not kodi_utils.confirm_dialog(text='Enabling this setting may cause instability on some devices.[CR][CR]Continue?'): return
	invoker_instance.data = new_value
	new_xml = str(root.toxml()).replace('<?xml version="1.0" ?>', '')
	with open(addon_xml, 'w') as f: f.write(new_xml)
	set_setting('reuse_language_invoker', new_value)
	kodi_utils.finish_addon_xml_sync()
	kodi_utils.restart_addon_for_addon_xml_change(notify=False)

def addon_icon_choice(params):
	import os
	from xml.dom.minidom import parse as mdParse
	addon_xml = kodi_utils.translate_path('special://home/addons/plugin.video.redlight/addon.xml')
	root = mdParse(addon_xml)
	icon_instance = root.getElementsByTagName('icon')[0].firstChild
	icons_path = 'special://home/addons/plugin.video.redlight/resources/media/addon_icons'
	all_icons = kodi_utils.list_dirs(kodi_utils.translate_path(icons_path))[1]
	all_icons.sort()
	list_items = [{'line1': i, 'icon': kodi_utils.translate_path(os.path.join(icons_path, i))} for i in all_icons]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose New Icon Image'}
	new_icon = kodi_utils.select_dialog(all_icons, **kwargs)
	if new_icon == None: return
	new_icon_path = 'resources/media/addon_icons/%s' % new_icon
	if not kodi_utils.confirm_dialog(text='Set New Icon?'): return
	icon_instance.data = new_icon_path
	new_xml = str(root.toxml()).replace('<?xml version="1.0" ?>', '')
	with open(addon_xml, 'w') as f: f.write(new_xml)
	set_setting('addon_icon_choice', new_icon_path)
	set_setting('addon_icon_choice_name', new_icon)
	icon_path = kodi_utils.translate_path(os.path.join(kodi_utils.addon_info('path'), new_icon_path))
	kodi_utils.set_property('redlight.addon_icon', icon_path)
	kodi_utils.set_property('redlight.addon_icon_mini', os.path.join(kodi_utils.addon_info('path'), 'resources', 'media', 'addon_icons', 'minis', new_icon))
	kodi_utils.update_local_addons()

def rescrape_actions_choice(params):
	set_focus = params.get('set_focus', 0)
	action_values = {0: 'Off', 1: 'Auto', 2: 'Prompt'}
	order_values = {0: 'Highest', 1: 'High', 2: 'Middle', 3: 'Low', 4: 'Lower', 5: 'Lowest'}
	rescrape_settings = settings.rescrape_all_settings()
	choices = [dict(i, **{'line1': i['name'],
				'line2': 'Action: [B]%s[/B] | Order: [B]%s[/B]' % (action_values[k[1]], order_values[k[2]]), 'value': i['value'],
				'action': k[1], 'order': k[2]}) for i in kodi_utils.rescrape_items() for k in rescrape_settings if k[0] == i['value']]
	choices = [dict(i, **{'position': c}) for c, i in enumerate(sorted(choices, key=lambda k: k['order']))]
	kwargs = {'items': json.dumps(choices), 'heading': 'Rescrape Actions', 'multi_line': 'true', 'narrow_window': 'true', 'set_focus': set_focus}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return
	choice_value, choice_action, choice_order = choice['value'], choice['action'], choice['order']
	params['set_focus'] = choice['position']
	choices = [{'line1': 'Set Action', 'action': 'set_action'}, {'line1': 'Set Order', 'action': 'set_order'}]
	kwargs = {'items': json.dumps(choices), 'heading': 'Rescrape Actions', 'narrow_window': 'true', 'set_focus': set_focus}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return rescrape_actions_choice(params)
	action = choice['action']
	if action == 'set_action':
		choices = [{'line1': 'Off', 'value': '0'}, {'line1': 'Auto', 'value': '1'}, {'line1': 'Prompt', 'value': '2'}]
		heading, setting = 'Choose Action Value', 'rescrape.%s' % choice_value
		kwargs = {'items': json.dumps(choices), 'heading': heading, 'narrow_window': 'true'}
		choice = kodi_utils.select_dialog(choices, **kwargs)
		if choice == None: return rescrape_actions_choice(params)
		setting_value = choice['value']
		set_setting(setting, setting_value)
	else:
		choices = [{'line1': 'Highest', 'value': '0'}, {'line1': 'High', 'value': '1'}, {'line1': 'Middle', 'value': '2'},
					{'line1': 'Low', 'value': '3'}, {'line1': 'Lower', 'value': '4'}, {'line1': 'Lowest', 'value': '5'}]
		heading, setting = 'Choose Order', 'rescrape.%s.order'
		kwargs = {'items': json.dumps(choices), 'heading': heading, 'narrow_window': 'true'}
		choice = kodi_utils.select_dialog(choices, **kwargs)
		if choice == None: return rescrape_actions_choice(params)
		setting_value = choice['value']
		new_settings = list(rescrape_settings)
		new_settings.remove((choice_value, choice_action, choice_order))
		new_settings.insert(int(setting_value), (choice_value, choice_action, setting_value))
		for item in [(i[0], str(c)) for c, i in enumerate(new_settings)]: set_setting(setting % item[0], item[1])
		params['set_focus'] = int(setting_value)
	return rescrape_actions_choice(params)

def context_menu_choice(params):
	choices = kodi_utils.context_menu_items()
	current_settings = settings.cm_enabled()
	try: preselect = [choices.index(i) for i in choices if i['value'] in current_settings]
	except: preselect = []
	list_items = [{'line1': i['name']} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Enable Content for the Context Menu', 'multi_choice': 'true', 'preselect': preselect}
	selection = kodi_utils.select_dialog(choices, **kwargs)
	if selection  == []:
		kodi_utils.ok_dialog(text='You must select at least 1 item')
		return context_menu_choice(params)
	elif selection == None: return
	selection = [i['value'] for i in selection]
	set_setting('context_menu.enabled', ','.join(selection))

def context_menu_order_choice(params):
	set_focus = params.get('set_focus', 0)
	all_items = kodi_utils.context_menu_items()
	enabled_items = settings.cm_enabled()
	current_order = settings.cm_current_order()
	active_items = [i for i in all_items if i['value'] in enabled_items]
	sorted_active_items = sorted(active_items, key=lambda k: current_order.index(k['value']))
	choices = [{'line1': 'Position %02d' % (count + 1), 'line2': 'Currently [B]%s[/B]' % (item['name']),
			 'current_item': item, 'display_position': count + 1, 'position': count} for count, item in enumerate(sorted_active_items)]
	kwargs = {'items': json.dumps(choices), 'heading': 'Choose Order for Context Menu', 'multi_line': 'true', 'narrow_window': 'true', 'set_focus': set_focus}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return
	current_item = choice['current_item']
	position = choice['position']
	display_position = choice['display_position']
	choices = [{'line1': item['name'], 'value': item['value']} for item in active_items if item != current_item]
	kwargs = {'items': json.dumps(choices), 'narrow_window': 'true', 'heading': 'Choose Context Menu Item for Position %02d' % display_position}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice != None:
		value = choice['value']
		current_order.remove(value)
		current_order.insert(position, value)
		current_order = [str(i) for i in current_order]
		set_setting('context_menu.order', ','.join(current_order))
		params['set_focus'] = position
	return context_menu_order_choice(params)

def personallists_manager_choice(params):
	from indexers.personal_lists import get_all_personal_lists, make_new_personal_list, new_list_check
	icon = params.get('icon', None) or kodi_utils.get_icon('lists')
	list_type = params['list_type']
	all_lists = get_all_personal_lists(get_setting('redlight.personal_list.list_sort', '0'))
	choices = []
	if not all_lists: action = 'add_new'
	else:
		choices = [('Add To Personal List...', 'add'), ('Remove From Personal List...', 'remove'), ('Add To [B]NEW[/B] Personal List...', 'add_new')]
		list_items = [{'line1': item[0], 'icon': icon} for item in choices]
		kwargs = {'items': json.dumps(list_items), 'heading': 'Personal Lists Manager'}
		action = kodi_utils.select_dialog([i[1] for i in choices], **kwargs)
		if action == None: return
	if action == 'add_new':
		list_name, author = make_new_personal_list({'external_creation': 'true'})
		if not list_name: return kodi_utils.notification('Error Creating List', 3000)
		action = 'add'
	else:
		new_template, normal_template = '[COLOR FF008EB2]%s [I](x%02d)[/I][/COLOR]', '%s [I](x%02d)[/I]'
		choices = [((new_template if new_list_check(i['seen']) else normal_template) % (i['name'], i['total']), (i['name'], i['author'])) for i in all_lists]
		list_items = [{'line1': i[0]} for i in choices]
		kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
		try:list_name, author = kodi_utils.select_dialog([i[1] for i in choices], **kwargs)
		except: return
	if action == 'add': new_contents = {'media_id': params['tmdb_id'], 'title': params['title'], 'type': list_type,
										'release_date': params['premiered'], 'date_added': params['current_time']}
	else: new_contents = params['tmdb_id']
	from caches.personal_lists_cache import personal_lists_cache
	result = personal_lists_cache.add_remove_list_item(list_name, author, action, new_contents)
	kodi_utils.notification(result, 3000)
	if action == 'remove' and any([kodi_utils.path_check(list_name) or kodi_utils.external()]): kodi_utils.kodi_refresh()

def tmdblists_manager_choice(params):
	try:
		return _tmdblists_manager_choice(params)
	except Exception as e:
		from modules.kodi_utils import logger
		logger('tmdblists_manager_choice', str(e))
		return kodi_utils.notification(kodi_utils.LIST_ITEM_NOT_IN_LIST, 3000, settle_ms=300)

def _tmdblists_manager_choice(params):
	from caches.tmdb_lists import tmdb_lists_cache
	from indexers.tmdb_lists import (
		make_new_tmdb_list, add_to_tmdb_list, remove_from_tmdb_list, check_item_status_watchfav,
		add_remove_watchfavs, tmdb_lists_split_by_membership, select_tmdb_lists
	)
	icon = params.get('icon', None) or kodi_utils.get_icon('tmdb')
	media_type, tmdb_id = params['media_type'], params['tmdb_id']
	if media_type in ('movie', 'movies'): media_type = 'movie'
	else: media_type = 'tv'
	try: tmdb_id = int(tmdb_id)
	except: return kodi_utils.notification('Error', 3000)
	in_watchlist = check_item_status_watchfav('watchlist', media_type, tmdb_id)
	in_favorites = check_item_status_watchfav('favorites', media_type, tmdb_id)
	in_lists, out_lists = tmdb_lists_split_by_membership(media_type, tmdb_id)
	choices = []
	if in_watchlist:
		choices.append(('Remove From [B]Watchlist[/B]', 'watchlist_remove'))
	else:
		choices.append(('Add To [B]Watchlist[/B]', 'watchlist_add'))
	if in_favorites:
		choices.append(('Remove From [B]Favorites[/B]', 'favorites_remove'))
	else:
		choices.append(('Add To [B]Favorites[/B]', 'favorites_add'))
	if out_lists:
		choices.append(('Add To TMDb List...', 'list_add'))
	if in_lists:
		choices.append(('Remove From TMDb List...', 'list_remove'))
	choices.append(('Add To [B]NEW[/B] TMDb List...', 'list_add_new'))
	list_items = [{'line1': item[0], 'icon': icon} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'TMDb Lists Manager'}
	action = kodi_utils.select_dialog([i[1] for i in choices], **kwargs)
	if action == None: return
	if action.startswith(('watchlist', 'favorites')):
		list_id = action.split('_')[0]
		status = True if 'add' in action else False
		success = add_remove_watchfavs(media_type, tmdb_id, list_id, status)
		tmdb_lists_cache.clear_watchfavrecs(list_id, media_type)
		if not success: return
		kodi_utils.notification('Success', 3000)
		return
	item_in_list = False
	if action == 'list_add_new':
		list_id = make_new_tmdb_list({'external_creation': 'true'})
		if not list_id: return kodi_utils.notification('Error Creating List')
		action, item_in_list = 'list_add', False
	else:
		list_id = select_tmdb_lists(out_lists if action == 'list_add' else in_lists)
		if list_id == None: return
	new_contents = {'items': [{'media_type': media_type, 'media_id': tmdb_id}]}
	if action == 'list_add':
		if item_in_list: return kodi_utils.notification('Item already in List')
		success = add_to_tmdb_list(list_id, new_contents)
		tmdb_lists_cache.clear_list(list_id)
		tmdb_lists_cache.clear_all_lists()
		kodi_utils.notification('Success' if success else 'Failed', 3000)
	elif action == 'list_remove':
		remove_from_tmdb_list(list_id, new_contents)
		tmdb_lists_cache.clear_list(list_id)
		tmdb_lists_cache.clear_all_lists()
	if 'remove' in action and any([kodi_utils.path_check(str(list_id)) or kodi_utils.external()]):
		kodi_utils.sleep(500)
		kodi_utils.kodi_refresh()

def favorites_manager_choice(params):
	from caches.favorites_cache import favorites_cache
	media_type, tmdb_id, title = params.get('media_type'), params.get('tmdb_id'), params.get('title')
	current_favorites = favorites_cache.get_favorites(media_type)
	people_favorite = media_type == 'people'
	current_favorite = any(i['tmdb_id'] == tmdb_id for i in current_favorites)
	if current_favorite:
		function, text = favorites_cache.delete_favourite, 'Remove From Favorites?'
		param_refresh = params.get('refresh', None)
		if param_refresh == None: refresh = any(i in kodi_utils.folder_path() for i in ('action=favorites_movies', 'action=favorites_tvshows', 'action=favorites_anime'))
		else: refresh = param_refresh == 'true'
	else: function, text, refresh = favorites_cache.set_favourite, 'Add To Favorites?', False
	heading = title.split('|')[0] if people_favorite else title
	if not kodi_utils.confirm_dialog(heading=heading, text=text): return
	success = function(media_type, tmdb_id, title)
	if success:
		if refresh: kodi_utils.kodi_refresh()
		kodi_utils.notification('Success', 3500)
	else: kodi_utils.notification('Error', 3500)
	if people_favorite and success: return text

def ai_model_order_choice(params):
	model_descriptions = {
		'gemini-3.1-flash-lite': ('GEMINI FAST, 20 RPD', 'gemini'),
		'llama-3.3-70b-versatile': ('GROQ FAST, 140 RPD', 'groq'),
		'gemma-4-31b-it': ('GEMMA Fast, MANY RPD', 'gemma'),
		'llama-3.1-8b-instant': ('GROQ FAST, MANY RPD', 'groq'),
	}
	default_order = default_setting_values('ai_model.order')['setting_default'].split(',')
	current_order = settings.ai_model_order()
	choices = [{'line1': 'Position %02d' % (count + 1), 'line2': 'Currently [B]%s[/B] (%s)' % (item, model_descriptions.get(item, ('?', 'folder'))[0]),
				'icon': kodi_utils.get_icon(model_descriptions.get(item, ('?', 'folder'))[1]), 'current_item': item, 'display_position': count + 1, 'position': count}
				for count, item in enumerate(current_order)]
	kwargs = {'items': json.dumps(choices), 'multi_line': 'true', 'heading': 'Choose Sort Order Of AI Models'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return
	current_model_id = choice['current_item']
	position = choice['position']
	display_position = choice['display_position']
	choices = [{'line1': item, 'line2': model_descriptions.get(item, ('?', 'folder'))[0], 'icon': kodi_utils.get_icon(model_descriptions.get(item, ('?', 'folder'))[1]), 'model_id': item}
				for item in default_order if item != current_model_id]
	kwargs = {'items': json.dumps(choices), 'multi_line': 'true', 'heading': 'Choose Model for Position %02d' % display_position}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice != None:
		from caches.lists_cache import lists_cache
		lists_cache.delete_like("ai_similar_%")
		model_id = choice['model_id']
		current_order.remove(model_id)
		current_order.insert(position, model_id)
		set_setting('ai_model.order', ','.join(current_order))
	return ai_model_order_choice(params)

def extras_lists_choice(params={}):
	current_settings = settings.extras_enabled()
	choices = kodi_utils.extras_items()
	list_items = [{'line1': i['name']} for i in choices]
	try: preselect = [choices.index(i) for i in choices if i['value'] in current_settings]
	except: preselect = []
	kwargs = {'items': json.dumps(list_items), 'heading': 'Enable Content for Extras Lists', 'multi_choice': 'true', 'preselect': preselect}
	selection = kodi_utils.select_dialog(choices, **kwargs)
	if selection  == []:
		kodi_utils.ok_dialog(text='You must select at least 1 item')
		return extras_lists_choice(params)
	elif selection == None: return
	selection = [str(i['value']) for i in selection]
	set_setting('extras.enabled', ','.join(selection))

def extras_order_choice(params={}):
	all_items = kodi_utils.extras_items()
	enabled_items = settings.extras_enabled()
	current_order = settings.extras_order()
	active_items = [i for i in all_items if i['value'] in enabled_items]
	active_items = sorted(active_items, key=lambda k: current_order.index(k['value']))
	choices = [{'line1': 'Position %02d' % (count + 1), 'line2': 'Currently [B]%s[/B]' % (item['name']),
			 'current_item': item, 'display_position': count + 1, 'position': count} for count, item in enumerate(active_items)]
	kwargs = {'items': json.dumps(choices), 'heading': 'Choose Order Of Extras Lists', 'multi_line': 'true', 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None:
		if params.get('remake', False):
			from windows.base_window import ExtrasUtils
			ExtrasUtils().run()
		return
	current_item = choice['current_item']
	position = choice['position']
	display_position = choice['display_position']
	choices = [{'line1': item['name'], 'value': item['value']} for item in active_items if item != current_item]
	kwargs = {'items': json.dumps(choices), 'narrow_window': 'true', 'heading': 'Choose List Item for Position %02d' % display_position}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice != None:
		value = choice['value']
		current_order.remove(value)
		current_order.insert(position, value)
		current_order = [str(i) for i in current_order]
		set_setting('extras.order', ','.join(current_order))
		params['remake'] = True
	return extras_order_choice(params)

def preferred_filters_choice(params):
	from modules.source_utils import source_filters, include_exclude_filters
	def _default_choices():
		return [{'name': '1st Sort', 'value': 'Choose 1st Sort Param'}, {'name': '2nd Sort', 'value': 'Choose 2nd Sort Param'},
				{'name': '3rd Sort', 'value': 'Choose 3rd Sort Param'}, {'name': '4th Sort', 'value': 'Choose 4th Sort Param'},
				{'name': '5th Sort', 'value': 'Choose 5th Sort Param'}]
	def _beginning_choices():
		defaults = _default_choices()
		for count, item in enumerate(auto_settings): defaults[count]['value'] = item
		return defaults
	def _rechoose_checker(choice):
		if choice['value'].startswith('Choose'): return (choice, True)
		clear_choice = kodi_utils.confirm_dialog(heading='Current Param Active', text='This sort slot is already filled.[CR]Please choose what action to take.',
						ok_label='Remake Slot', cancel_label='Clear Slot')
		if clear_choice == None: new_default, ask_params = (choice, False)
		else:
			choice_index = choices.index(choice)
			new_default = _default_choices()[choice_index]
			choices[choice_index] = new_default
		return (new_default, clear_choice)
	def _param_choices(choice):
		filter_keys = include_exclude_filters()
		disabled_filters = [v for k, v in filter_keys.items() if settings.filter_status(k) == 1]
		s_filters = source_filters()
		filters_choice = [(i[0], i[1].replace('[B]', '').replace('[/B]', '')) for i in s_filters]
		filters_choice = [i for i in filters_choice if not i[1] in disabled_filters]
		unused_filters = [i for i in filters_choice if not i[1] in auto_settings]
		param_list_items = [{'line1': i[0], 'line2': i[1]} for i in unused_filters]
		param_kwargs = {'items': json.dumps(param_list_items), 'multi_line': 'true', 'heading': 'Choose Sort To Top Parameters', 'narrow_window': 'true'}
		param_choice = kodi_utils.select_dialog(unused_filters, **param_kwargs)
		if param_choice == None: return ''
		choice['value'] = param_choice[1]
		return choice
	def _make_settings():
		new_settings = [i['value'] for i in choices if not i['value'].startswith('Choose')]
		if not new_settings: set_setting('filter.preferred_filters', 'empty_setting')
		else: set_setting('filter.preferred_filters', ', '.join(new_settings))
	auto_settings = settings.preferred_filters()
	choices = params.get('choices') or _beginning_choices()
	list_items = [{'line1': i['name'], 'line2': i['value']} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'multi_line': 'true', 'heading': 'Choose Sort To Top Parameters', 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return _make_settings()
	choice, ask_params = _rechoose_checker(choice)
	if not ask_params: return preferred_filters_choice({'choices': choices})
	param_choice = _param_choices(choice)
	if not param_choice: return preferred_filters_choice({'choices': choices})
	choices[choices.index(choice)] = param_choice
	_make_settings()
	return preferred_filters_choice({'choices': choices})

def tmdb_api_check_choice(params):
	from apis.tmdb_api import movie_details
	from caches.settings_cache import looks_like_tmdb_v4_jwt
	api_key = settings.tmdb_api_key()
	if looks_like_tmdb_v4_jwt(api_key):
		return kodi_utils.ok_dialog(heading='Wrong key type', text='This is a TMDb v4 Read Access Token (JWT), not the v3 API Key.[CR]Use TMDb Lists → Read Access Token for v4 tokens.')
	data = movie_details('299534', api_key)
	if not data or not data.get('success', True):
		text = 'TMDb API Key failed.[CR]%s' % (data or {}).get('status_message', 'Unknown error')
		return kodi_utils.ok_dialog(heading='Failed', text=text)
	return kodi_utils.ok_dialog(heading='Success', text='TMDb API Key is valid.')

def trakt_credentials_check_choice(params):
	from apis.trakt_api import trakt_test_credentials
	ok, text = trakt_test_credentials()
	return kodi_utils.ok_dialog(heading='Success' if ok else 'Failed', text=text)

def punchplay_client_check_choice(params):
	from apis.punchplay_api import punchplay_test_client_id
	ok, text = punchplay_test_client_id()
	return kodi_utils.ok_dialog(heading='Success' if ok else 'Failed', text=text)

def simkl_client_check_choice(params):
	from apis.simkl_api import simkl_test_client_id
	ok, text = simkl_test_client_id()
	return kodi_utils.ok_dialog(heading='Success' if ok else 'Failed', text=text)

def tmdblist_read_token_check_choice(params):
	import requests
	from apis.tmdblist_api import TMDbListAPI
	api = TMDbListAPI()
	try:
		data = requests.post('%s/auth/request_token' % api.base_url, headers=api.read_access_headers(), timeout=20).json()
		if not data.get('success'):
			text = 'Lists read access token failed.[CR]%s' % data.get('status_message', 'Unknown error')
			return kodi_utils.ok_dialog(heading='Failed', text=text)
		return kodi_utils.ok_dialog(heading='Success', text='Lists read access token is valid.')
	except Exception as e:
		return kodi_utils.ok_dialog(heading='Failed', text='Lists read access token failed.[CR]%s' % str(e))

def clear_sources_folder_choice(params):
	setting_id = params['setting_id']
	set_default(['%s.display_name' % setting_id, '%s.movies_directory' % setting_id, '%s.tv_shows_directory' % setting_id])

def widget_refresh_timer_choice(params):
	choices = [{'name': 'OFF', 'value': '0'}]
	choices.extend([{'name': 'Every %s Minutes' % i, 'value': str(i)} for i in range(5,25,5)])
	choices.extend([{'name': 'Every %s Minutes' % i, 'value': str(i)} for i in range(30,65,10)])
	choices.extend([{'name': 'Every %s Hours' % (float(i)/60), 'value': str(i)} for i in range(90,720,30)])
	list_items = [{'line1': i['name']} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return
	set_setting('widget_refresh_timer', choice['value'])
	set_setting('widget_refresh_timer_name', choice['name'])

def limit_number_quality_choice(params):
	choices = [{'name': 'OFF', 'value': '0'}]
	choices.extend([{'name': '%sx Per Quality' % i, 'value': str(i)} for i in range(1,5)])
	choices.extend([{'name': '%sx Per Quality' % i, 'value': str(i)} for i in range(5,205,5)])
	list_items = [{'line1': i['name']} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return
	set_setting('results.limit_number_quality', choice['value'])
	set_setting('results.limit_number_quality_name', choice['name'])

def limit_number_total_choice(params):
	choices = [{'name': 'OFF', 'value': '0'}]
	choices.extend([{'name': '%sx Total Results' % i, 'value': str(i)} for i in range(1,10)])
	choices.extend([{'name': '%sx Total Results' % i, 'value': str(i)} for i in range(10,1000,5)])
	list_items = [{'line1': i['name']} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return
	set_setting('results.limit_number_total', choice['value'])
	set_setting('results.limit_number_total_name', choice['name'])

def external_scraper_choice(params):
	from modules.utils import append_module_to_syspath, manual_function_import
	try: slot = int(params.get('slot', '1'))
	except: slot = 1
	slot = max(1, min(slot, settings.EXTERNAL_SCRAPER_SLOT_COUNT))
	try:
		results = kodi_utils.jsonrpc_get_addons('xbmc.python.module')
		results = [i for i in results if kodi_utils.addon_enabled(i['addonid'])]
	except: return
	used = {}
	for other_slot in range(1, settings.EXTERNAL_SCRAPER_SLOT_COUNT + 1):
		if other_slot == slot: continue
		data = settings.external_scraper_slot_data(other_slot)
		if data['module']: used[data['module']] = other_slot
	results = [i for i in results if i['addonid'] not in used]
	if not results:
		kodi_utils.ok_dialog(text='Every installed scraper module is already assigned to another slot.[CR]Clear a slot or install another module.')
		return
	current_module = settings.external_scraper_slot_data(slot)['module']
	list_items = []
	preselect_index = None
	for idx, item in enumerate(results):
		entry = {'line1': item['name'], 'icon': item['thumbnail']}
		if current_module and item['addonid'] == current_module:
			entry['line2'] = 'Current selection for slot %d' % slot
			preselect_index = idx
		list_items.append(entry)
	kwargs = {'items': json.dumps(list_items), 'heading': 'External Scraper Slot %d' % slot}
	if preselect_index is not None:
		kwargs['multi_line'] = 'true'
		kwargs['preselect'] = [preselect_index]
		kwargs['set_focus'] = preselect_index
	choice = kodi_utils.select_dialog(results, **kwargs)
	if choice == None: return
	module_id, module_name = choice['addonid'], choice['name']
	success = False
	try:
		append_module_to_syspath('special://home/addons/%s/lib' % module_id)
		main_folder_name = module_id.split('.')[-1]
		sourceDict = manual_function_import(main_folder_name, 'sources')(specified_folders=['torrents'])
		success = True
	except: pass
	if success:
		try:
			if not settings.set_external_scraper_slot(slot, module_id, module_name, enable=True):
				other_slot = settings.external_scraper_module_in_use(module_id, exclude_slot=slot)
				kodi_utils.ok_dialog(text='[B]%s[/B] is already assigned to slot %d.[CR]Choose a different module or clear that slot first.' % (module_name, other_slot))
				return
			set_setting('provider.external', 'true')
			kodi_utils.ok_dialog(text='Success.[CR][B]%s[/B] set as External Scraper slot %d' % (module_name, slot))
			try:
				from caches.settings_cache import refresh_settings_manager_properties
				refresh_settings_manager_properties()
			except: pass
		except: kodi_utils.ok_dialog(text='Error')
	else:
		kodi_utils.ok_dialog(text='The [B]%s[/B] Module is not compatible.[CR]Please choose a different Module...' % module_name.upper())
		return external_scraper_choice(params)

def external_scraper_clear_slot(params):
	try: slot = int(params.get('slot', '1'))
	except: return
	slot = max(1, min(slot, settings.EXTERNAL_SCRAPER_SLOT_COUNT))
	settings.set_external_scraper_slot(slot, '', '', enable=False)
	try:
		from caches.settings_cache import refresh_settings_manager_properties
		refresh_settings_manager_properties()
	except: pass

def external_scraper_move_slot(params):
	try:
		slot = int(params.get('slot', '1'))
		direction = params.get('direction', 'up')
	except: return
	target = slot - 1 if direction == 'up' else slot + 1
	if target < 1 or target > settings.EXTERNAL_SCRAPER_SLOT_COUNT: return
	settings.swap_external_scraper_slots(slot, target)
	try:
		from caches.settings_cache import refresh_settings_manager_properties
		refresh_settings_manager_properties()
	except: pass

def audio_filters_choice(params={}):
	from modules.source_utils import audio_filter_choices
	icon = kodi_utils.get_icon('audio')
	audio_filters = audio_filter_choices()
	list_items = [{'line1': item[0], 'line2': item[1], 'icon': icon} for item in audio_filters]
	try: preselect = [audio_filters.index(item) for item in audio_filters if item[1] in settings.audio_filters()]
	except: preselect = []
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Audio Properties to Exclude', 'multi_choice': 'true', 'multi_line': 'true', 'preselect': preselect}
	selection = kodi_utils.select_dialog([i[1] for i in audio_filters], **kwargs)
	if selection == None: return
	if selection == []: set_setting('filter_audio', 'empty_setting')
	else: set_setting('filter_audio', ', '.join(selection))

def genres_choice(params):
	genres_list, genres, poster = params['genres_list'], params['genres'], params['poster']
	genre_list = [i for i in genres_list if i['name'] in genres]
	if not genre_list:
		kodi_utils.notification('No Results', 2500)
		return None
	list_items = [{'line1': i['name'], 'icon': poster} for i in genre_list]
	kwargs = {'items': json.dumps(list_items)}
	return kodi_utils.select_dialog([i['id'] for i in genre_list], **kwargs)

def keywords_choice(params):
	media_type, meta = params['media_type'], params['meta']
	keywords, tmdb_id, poster = meta.get('keywords', []), meta['tmdb_id'], meta['poster']
	if keywords: keywords = keywords.get('keywords') or keywords.get('results')
	else:
		kodi_utils.show_busy_dialog()
		from apis.tmdb_api import tmdb_movie_keywords, tmdb_tv_keywords
		if media_type == 'movie': function, key = tmdb_movie_keywords, 'keywords'
		else: function, key = tmdb_tv_keywords, 'results'
		try: keywords = function(tmdb_id)[key]
		except: keywords = []
		kodi_utils.hide_busy_dialog()
	if not keywords:
		kodi_utils.notification('No Results', 2500)
		return None
	list_items = [{'line1': i['name'], 'icon': poster} for i in keywords]
	kwargs = {'items': json.dumps(list_items)}
	return kodi_utils.select_dialog([i['id'] for i in keywords], **kwargs)

def random_choice(params):
	meta, poster, return_choice = params.get('meta'), params.get('poster'), params.get('return_choice', 'false')
	meta = params.get('meta', None)	
	list_items = [{'line1': 'Single Random Play', 'icon': poster}, {'line1': 'Continual Random Play', 'icon': poster}]
	choices = ['play_random', 'play_random_continual']
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Random Play Type...'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if return_choice == 'true': return choice
	if choice == None: return
	from modules.episode_tools import EpisodeTools
	exec('EpisodeTools(meta).%s()' % choice)

def _trakt_manager_mark(params, action):
	from modules import watched_status as ws
	mark_params = {'action': action, 'tmdb_id': params['tmdb_id'], 'tvdb_id': params.get('tvdb_id', '0'),
					'title': params.get('title', ''), 'refresh': 'true'}
	media_type = params.get('media_type')
	season, episode = params.get('season'), params.get('episode')
	if media_type == 'movie': return ws.mark_movie(mark_params)
	try:
		if media_type == 'episode' or (season not in ('', None) and episode not in ('', None) and int(season) > 0 and int(episode) > 0):
			mark_params.update({'season': season, 'episode': episode})
			return ws.mark_episode(mark_params)
	except: pass
	return ws.mark_tvshow(mark_params)

def _trakt_episode_context(params):
	season, episode = params.get('season'), params.get('episode')
	try:
		season, episode = int(season), int(episode)
	except: return None, None
	if season < 0 or episode < 0: return None, None
	return season, episode

def _trakt_resolve_episode_tmdb(show_tmdb, season, episode, episode_id=None):
	if episode_id not in (None, '', 'None', '0', 0):
		try: return int(episode_id)
		except: pass
	try:
		from modules import metadata
		from modules.utils import get_datetime
		meta = metadata.tvshow_meta('tmdb_id', show_tmdb, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
		for ep in metadata.episodes_meta(int(season), meta) or []:
			if int(ep.get('episode') or 0) != int(episode): continue
			eid = ep.get('episode_id')
			if eid not in (None, '', 'None', '0', 0): return int(eid)
	except: pass
	return None

def _trakt_manager_payload(params):
	tmdb_id, tvdb_id, imdb_id, media_type = params['tmdb_id'], params.get('tvdb_id'), params.get('imdb_id'), params['media_type']
	if media_type == 'movie': key, media_key, media_id = ('movies', 'tmdb', int(tmdb_id))
	else:
		key = 'shows'
		media_ids = [(tmdb_id, 'tmdb'), (imdb_id, 'imdb'), (tvdb_id, 'tvdb')]
		media_id, media_key = next(item for item in media_ids if item[0] not in ('None', None, ''))
		if media_id in (tmdb_id, tvdb_id): media_id = int(media_id)
	return {key: [{'ids': {media_key: media_id}}]}

def _trakt_manager_personal_list_payload(params, episode_tmdb=None):
	season, episode = _trakt_episode_context(params)
	if season is not None and episode is not None and episode_tmdb not in (None, '', 'None', '0', 0):
		return {'episodes': [{'ids': {'tmdb': int(episode_tmdb)}}]}
	return _trakt_manager_payload(params)

def trakt_manager_choice(params):
	if not settings.trakt_user_active(): return kodi_utils.notification('No Active Trakt Account', 3500)
	from apis import trakt_api
	icon = params.get('icon', None) or kodi_utils.get_icon('trakt')
	media_type = params.get('media_type') or 'movie'
	tmdb_id, imdb_id, tvdb_id = params.get('tmdb_id'), params.get('imdb_id'), params.get('tvdb_id')
	list_media = 'movie' if media_type == 'movie' else 'tvshow'
	season, episode = _trakt_episode_context(params)
	episode_mode = list_media != 'movie' and season is not None and episode is not None
	episode_tmdb = None
	if episode_mode:
		episode_tmdb = _trakt_resolve_episode_tmdb(tmdb_id, season, episode, params.get('episode_id'))
	# Show-scoped personal lists always (restore add-show from episode rows).
	show_in_lists, show_out_lists = trakt_api.trakt_personal_lists_split_by_membership(
		media_type, tmdb_id, imdb_id, tvdb_id
	)
	ep_in_lists, ep_out_lists = [], []
	if episode_mode and episode_tmdb:
		ep_in_lists, ep_out_lists = trakt_api.trakt_personal_lists_split_by_membership(
			'episode', tmdb_id, imdb_id, tvdb_id, season=season, episode=episode
		)
	choices = []
	if trakt_api.trakt_item_in_sync_list('watchlist', media_type, tmdb_id, imdb_id, tvdb_id):
		choices.append(('Remove from [B]Watchlist[/B]', 'remove_watchlist'))
	else:
		choices.append(('Add to [B]Watchlist[/B]', 'add_watchlist'))
	if trakt_api.trakt_item_in_sync_list('collection', media_type, tmdb_id, imdb_id, tvdb_id):
		choices.append(('Remove from [B]Library[/B]', 'remove_collection'))
	else:
		choices.append(('Add to [B]Library[/B]', 'add_collection'))
	if trakt_api.trakt_item_in_favorites(media_type, tmdb_id, imdb_id, tvdb_id):
		choices.append(('Remove from [B]Favorites[/B]', 'remove_favorites'))
	else:
		choices.append(('Add to [B]Favorites[/B]', 'add_favorites'))
	if media_type != 'movie':
		if trakt_api.trakt_item_is_dropped(tmdb_id):
			choices.append(('Undrop [B]TV Show[/B]', 'undrop'))
		else:
			choices.append(('Drop [B]TV Show[/B]', 'drop'))
	if episode_mode:
		if show_out_lists:
			choices.append(('Add TV Show To [B]Personal List[/B]...', 'add_show'))
		if show_in_lists:
			choices.append(('Remove TV Show from [B]Personal List[/B]...', 'remove_show'))
		if episode_tmdb:
			if ep_out_lists:
				choices.append(('Add Episode To [B]Personal List[/B]...', 'add_episode'))
			if ep_in_lists:
				choices.append(('Remove Episode from [B]Personal List[/B]...', 'remove_episode'))
	else:
		if show_out_lists:
			choices.append(('Add To [B]Personal List[/B]...', 'add_show'))
		if show_in_lists:
			choices.append(('Remove from [B]Personal List[/B]...', 'remove_show'))
	watchlist_label = 'Movies Watchlist' if list_media == 'movie' else 'TV Shows Watchlist'
	collection_label = 'Movies Library' if list_media == 'movie' else 'TV Shows Library'
	favorites_label = 'Favorite Movies' if list_media == 'movie' else 'Favorite TV Shows'
	list_mode = 'build_movie_list' if list_media == 'movie' else 'build_tvshow_list'
	choices.extend([
		('Mark as [B]Watched[/B]', 'mark_watched'),
		('Mark as [B]Unwatched[/B]', 'mark_unwatched'),
		('Reset [B]Scrobble[/B]', 'reset_scrobble'),
		('Open [B]Watchlist[/B]', 'open_watchlist'),
		('Open [B]Library[/B]', 'open_collection'),
		('Open [B]Favorites[/B]', 'open_favorites'),
		('Open [B]Liked Lists[/B]', 'open_liked_lists'),
		('Open [B]My Lists[/B]', 'open_my_lists'),
		('Refresh Widgets', 'refresh'),
	])
	if list_media != 'movie':
		choices.insert(-1, ('Open [B]Dropped TV Shows[/B]', 'open_dropped'))
	list_items = [{'line1': item[0], 'icon': icon} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Trakt Lists Manager'}
	choice = kodi_utils.select_dialog([i[1] for i in choices], **kwargs)
	if choice == None: return
	if choice == 'refresh':
		kodi_utils.kodi_refresh()
		return kodi_utils.notification('Widgets Refreshed', 2500)
	open_modes = {
		'open_watchlist': {'mode': list_mode, 'action': 'trakt_watchlist', 'category_name': watchlist_label},
		'open_collection': {'mode': list_mode, 'action': 'trakt_collection', 'category_name': collection_label},
		'open_favorites': {'mode': list_mode, 'action': 'trakt_favorites', 'category_name': favorites_label},
		'open_dropped': {'mode': 'build_tvshow_list', 'action': 'trakt_droplist', 'category_name': 'Dropped TV Shows'},
		'open_liked_lists': {'mode': 'trakt.list.get_trakt_lists', 'list_type': 'liked_lists', 'category_name': 'Liked Lists'},
		'open_my_lists': {'mode': 'trakt.list.get_trakt_lists', 'list_type': 'my_lists', 'category_name': 'My Lists'},
	}
	if choice in open_modes:
		return kodi_utils.container_update(open_modes[choice])
	if choice == 'mark_watched':
		return _trakt_manager_mark(params, 'mark_as_watched')
	if choice == 'mark_unwatched':
		return _trakt_manager_mark(params, 'mark_as_unwatched')
	if choice == 'reset_scrobble':
		return trakt_api.trakt_reset_scrobble(params)
	data = _trakt_manager_payload(params)
	if choice == 'add_watchlist': return trakt_api.add_to_watchlist(data)
	if choice == 'remove_watchlist': return trakt_api.remove_from_watchlist(data)
	if choice == 'add_collection': return trakt_api.add_to_collection(data)
	if choice == 'remove_collection': return trakt_api.remove_from_collection(data)
	if choice == 'add_favorites': return trakt_api.add_to_favorites(data)
	if choice == 'remove_favorites': return trakt_api.remove_from_favorites(data)
	if choice in ('drop', 'undrop'):
		return trakt_api.hide_unhide_progress_items({
			'action': choice, 'media_type': 'shows', 'media_id': int(tmdb_id), 'section': 'dropped'
		})
	if choice in ('add_show', 'remove_show'):
		selected = trakt_api.select_trakt_personal_lists(show_out_lists if choice == 'add_show' else show_in_lists)
		if selected == None: return
		if choice == 'add_show':
			return trakt_api.add_to_list(selected['user'], selected['slug'], data)
		return trakt_api.remove_from_list(selected['user'], selected['slug'], data)
	if choice in ('add_episode', 'remove_episode'):
		if not episode_tmdb:
			return kodi_utils.notification('Unable to resolve episode for Trakt', 3500)
		selected = trakt_api.select_trakt_personal_lists(ep_out_lists if choice == 'add_episode' else ep_in_lists)
		if selected == None: return
		list_data = _trakt_manager_personal_list_payload(params, episode_tmdb)
		if choice == 'add_episode':
			return trakt_api.add_to_list(selected['user'], selected['slug'], list_data)
		return trakt_api.remove_from_list(selected['user'], selected['slug'], list_data)

def _trakt_list_shortcut_choice(params, list_type):
	if not settings.trakt_user_active(): return kodi_utils.notification('No Active Trakt Account', 3500)
	from apis import trakt_api
	label = 'Watchlist' if list_type == 'watchlist' else 'Library'
	heading = params.get('title') or ('Trakt %s' % label)
	in_list = trakt_api.trakt_item_in_sync_list(list_type, params['media_type'], params.get('tmdb_id'), params.get('imdb_id'), params.get('tvdb_id'))
	text = 'Remove from %s?' % label if in_list else 'Add to %s?' % label
	if not kodi_utils.confirm_dialog(heading=heading, text=text): return
	data = _trakt_manager_payload(params)
	if list_type == 'watchlist':
		return trakt_api.remove_from_watchlist(data) if in_list else trakt_api.add_to_watchlist(data)
	return trakt_api.remove_from_collection(data) if in_list else trakt_api.add_to_collection(data)

def trakt_watchlist_shortcut_choice(params):
	return _trakt_list_shortcut_choice(params, 'watchlist')

def trakt_collection_shortcut_choice(params):
	return _trakt_list_shortcut_choice(params, 'collection')

def simkl_manager_choice(params):
	from apis import simkl_api
	return simkl_api.simkl_manager_choice(params)

def simkl_plantowatch_shortcut_choice(params):
	if not settings.simkl_user_active(): return kodi_utils.notification('No Active Simkl Account', 3500)
	from apis import simkl_api
	media_type = params.get('media_type') or 'movie'
	list_media = 'movie' if media_type == 'movie' else 'tvshow'
	tmdb_id, imdb_id, tvdb_id = params.get('tmdb_id'), params.get('imdb_id'), params.get('tvdb_id')
	simkl_id, media_kind = params.get('simkl_id'), params.get('simkl_media_kind')
	heading = params.get('title') or 'Simkl Plan to Watch'
	in_list = simkl_api._simkl_item_in_status(list_media, 'plantowatch', imdb_id, tvdb_id, tmdb_id, simkl_id)
	text = 'Remove from Plan to Watch?' if in_list else 'Add to Plan to Watch?'
	if not kodi_utils.confirm_dialog(heading=heading, text=text): return
	if in_list: return simkl_api.simkl_remove_from_list('plantowatch', tmdb_id, list_media, imdb_id, tvdb_id, simkl_id, media_kind)
	return simkl_api.simkl_add_to_list('plantowatch', tmdb_id, list_media, imdb_id, tvdb_id, simkl_id, media_kind)

def mdblist_manager_choice(params):
	from apis import mdblist_api
	return mdblist_api.mdblist_manager_choice(params)

def punchplay_manager_choice(params):
	from apis import punchplay_api
	if not settings.punchplay_user_active(): return kodi_utils.notification('No Active PunchPlay Account', 3500)
	return punchplay_api.punchplay_manager_choice(params)

def _mdblist_list_shortcut_choice(params, list_type):
	if not settings.mdblist_user_active(): return kodi_utils.notification('No Active MDBList Account', 3500)
	from apis import mdblist_api
	media_type = params.get('media_type') or 'movie'
	list_media = 'movie' if media_type == 'movie' else 'tvshow'
	tmdb_id, imdb_id = params.get('tmdb_id'), params.get('imdb_id')
	label = 'MDBList Watchlist' if list_type == 'watchlist' else 'MDBList Library'
	heading = params.get('title') or label
	in_list = mdblist_api._mdbl_item_in_watchlist(list_media, tmdb_id) if list_type == 'watchlist' else mdblist_api._mdbl_item_in_library(list_media, tmdb_id)
	text = 'Remove from %s?' % label if in_list else 'Add to %s?' % label
	if not kodi_utils.confirm_dialog(heading=heading, text=text): return
	if list_type == 'watchlist':
		return mdblist_api.mdblist_remove_from_watchlist(tmdb_id, list_media, imdb_id) if in_list else mdblist_api.mdblist_add_to_watchlist(tmdb_id, list_media, imdb_id)
	return mdblist_api.mdblist_remove_from_library(tmdb_id, list_media, imdb_id) if in_list else mdblist_api.mdblist_add_to_library(tmdb_id, list_media, imdb_id)

def mdblist_watchlist_shortcut_choice(params):
	return _mdblist_list_shortcut_choice(params, 'watchlist')

def mdblist_library_shortcut_choice(params):
	return _mdblist_list_shortcut_choice(params, 'library')

def _tmdb_watchfav_shortcut_choice(params, list_id):
	from caches.tmdb_lists import tmdb_lists_cache
	from indexers.tmdb_lists import check_item_status_watchfav, add_remove_watchfavs
	media_type, tmdb_id = params['media_type'], params['tmdb_id']
	if media_type in ('movie', 'movies'): media_type = 'movie'
	else: media_type = 'tv'
	try: tmdb_id = int(tmdb_id)
	except: return kodi_utils.notification('Error', 3000)
	label = 'TMDb Watchlist' if list_id == 'watchlist' else 'TMDb Favorites'
	heading = params.get('title') or label
	in_list = check_item_status_watchfav(list_id, media_type, tmdb_id)
	text = 'Remove from %s?' % label if in_list else 'Add to %s?' % label
	if not kodi_utils.confirm_dialog(heading=heading, text=text): return
	success = add_remove_watchfavs(media_type, tmdb_id, list_id, not in_list)
	tmdb_lists_cache.clear_watchfavrecs(list_id, media_type)
	if not success: return
	kodi_utils.notification('Success', 3000)

def tmdb_watchlist_shortcut_choice(params):
	return _tmdb_watchfav_shortcut_choice(params, 'watchlist')

def tmdb_favorites_shortcut_choice(params):
	return _tmdb_watchfav_shortcut_choice(params, 'favorites')

def select_source_choice(params):
	p = dict(params)
	p['playback_action'] = 'scrape'
	return playback_choice(p)

def rescrape_select_source_choice(params):
	p = dict(params)
	p['playback_action'] = 'clear_and_rescrape'
	return playback_choice(p)

def episode_groups_choice(params):
	from modules.metadata import episode_groups
	episode_group_types = {1: 'Original Air Date', 2: 'Absolute', 3: 'DVD', 4: 'Digital', 5: 'Story Arc', 6: 'Production', 7: 'TV'}
	meta = params.get('meta')
	poster = params.get('poster') or kodi_utils.get_icon('box_office')
	groups = episode_groups(meta['tmdb_id'])
	if not groups:
		kodi_utils.notification('No Episode Groups to choose from.')
		return None
	list_items = [{'line1': '%s | %s Order | %d Groups | %02d Episodes' % (item['name'], episode_group_types[item['type']], item['group_count'], item['episode_count']),
					'line2': item['description'], 'icon': poster} for item in groups]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Episode Groups', 'enable_context_menu': 'true', 'enumerate': 'true', 'multi_line': 'true'}
	choice = kodi_utils.select_dialog([i['id'] for i in groups], **kwargs)
	return choice

def assign_episode_group_choice(params):
	from caches.episode_groups_cache import episode_groups_cache
	from modules import metadata
	tmdb_id = params['meta']['tmdb_id']
	current_group = episode_groups_cache.get(tmdb_id)
	if current_group:
		action = kodi_utils.confirm_dialog(text='Set new Group or Clear Current Group?', ok_label='Set New', cancel_label='Clear', default_control=10)
		if action == None: return
		if not action:
			episode_groups_cache.delete(tmdb_id)
			return kodi_utils.notification('Success', 2000)
	choice = episode_groups_choice(params)
	if choice == None: return
	group_details = metadata.group_details(choice)
	group_data = {'name': group_details['name'], 'id': group_details['id']}
	episode_groups_cache.set(tmdb_id, group_data)
	kodi_utils.notification('Success', 2000)

def playback_choice(params):
	from modules.utils import get_datetime
	from modules.debrid import debrid_cache_check_available
	from modules.source_utils import get_aliases_titles, make_alias_dict
	from modules import metadata
	media_type, season, episode, episode_id = params.get('media_type'), params.get('season', ''), params.get('episode', ''), params.get('episode_id', None)
	playcount = params.get('playcount', '0')
	playback_key = settings.playback_key()
	play_mode = 'playback.%s' % playback_key
	meta = params.get('meta')
	try: meta = json.loads(meta)
	except: pass
	if not isinstance(meta, dict):
		function = metadata.movie_meta if media_type == 'movie' else metadata.tvshow_meta
		meta = function('tmdb_id', meta, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
	poster = meta.get('poster') or kodi_utils.get_icon('box_office')
	aliases = get_aliases_titles(make_alias_dict(meta, meta['title']))
	check_cache_status, check_cache_toggle = ('OFF', 'false') if settings.any_external_cache_check() else ('ON', 'true')
	items = []
	if media_type == 'episode': items.append({'line': 'Play # Episodes', 'function': 'play_number_eps'})
	items.extend([{'line': 'Select Source', 'function': 'scrape'},
			{'line': 'Rescrape & Select Source', 'function': 'clear_and_rescrape'}])
	if debrid_cache_check_available():
		items.append({'line': 'Rescrape with External Cache Check [B]%s[/B]' % check_cache_status, 'function': 'rescrape_external_cache_check'})
	items.extend([{'line': 'Clear Debrid Cache & Show Results', 'function': 'clear_debrid_cache_and_show'},
				{'line': 'Scrape with ALL External Scrapers', 'function': 'scrape_with_disabled'},
				{'line': 'Scrape With All Filters Ignored', 'function': 'scrape_with_filters_ignored'}])
	if media_type == 'episode': items.append({'line': 'Scrape with Custom Episode Groups Value', 'function': 'scrape_with_episode_group'})
	if aliases: items.append({'line': 'Scrape with an Alias', 'function': 'scrape_with_aliases'})
	items.append({'line': 'Scrape with Custom Values', 'function': 'scrape_with_custom_values'})
	choice = params.get('playback_action')
	if not choice:
		list_items = [{'line1': i['line'], 'icon': poster} for i in items]
		kwargs = {'items': json.dumps(list_items), 'heading': 'Playback Options'}
		choice = kodi_utils.select_dialog([i['function'] for i in items], **kwargs)
		if choice == None: return kodi_utils.notification('Cancelled', 2500)
	if choice in ('clear_and_rescrape', 'scrape_with_custom_values'):
		kodi_utils.show_busy_dialog()
		from caches.base_cache import clear_cache
		from caches.external_cache import ExternalCache
		clear_cache('internal_scrapers', silent=True)
		ExternalCache().delete_cache_single(media_type, str(meta['tmdb_id']))
		kodi_utils.hide_busy_dialog()
	if choice == 'play_number_eps':
		num_episodes = kodi_utils.kodi_dialog().input('Number of episodes', type=1)
		try: num_episodes = int(num_episodes)
		except: num_episodes = 0
		if num_episodes < 1: return kodi_utils.notification('Cancelled', 2500)
		play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'],
						'season': season, 'episode': episode, 'num_episodes': str(num_episodes)}
	elif choice == 'scrape':
		if media_type == 'movie': play_params = {'mode': play_mode, 'media_type': 'movie', 'tmdb_id': meta['tmdb_id'], 'autoplay': 'false', 'prescrape': 'false'}
		else: play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'],
							'season': season, 'episode': episode, 'autoplay': 'false', 'prescrape': 'false'}
	elif choice == 'clear_and_rescrape':
		if media_type == 'movie': play_params = {'mode': play_mode, 'media_type': 'movie', 'tmdb_id': meta['tmdb_id'], 'autoplay': 'false', 'prescrape': 'false'}
		else: play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'],
							'season': season, 'episode': episode, 'autoplay': 'false', 'prescrape': 'false'}
	elif choice == 'rescrape_external_cache_check':
		if media_type == 'movie': play_params = {'mode': play_mode, 'media_type': 'movie', 'tmdb_id': meta['tmdb_id'],
												'external_cache_check': check_cache_toggle, 'prescrape': 'false'}
		else:
			play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'], 'season': season, 'episode': episode,
							'external_cache_check': check_cache_toggle, 'prescrape': 'false'}
	elif choice == 'clear_debrid_cache_and_show':
		from caches.debrid_cache import debrid_cache
		debrid_cache.clear_cache()	
		if media_type == 'movie': play_params = {'mode': play_mode, 'media_type': 'movie', 'tmdb_id': meta['tmdb_id'], 'autoplay': 'false', 'prescrape': 'false'}
		else: play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'],
							'season': season, 'episode': episode, 'autoplay': 'false', 'prescrape': 'false'}
	elif choice == 'scrape_with_disabled':
		if media_type == 'movie': play_params = {'mode': play_mode, 'media_type': 'movie', 'tmdb_id': meta['tmdb_id'],
												'disabled_ext_ignored': 'true', 'prescrape': 'false', 'autoplay': 'false'}
		else: play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'], 'season': season,
							'episode': episode, 'disabled_ext_ignored': 'true', 'prescrape': 'false', 'autoplay': 'false'}
	elif choice == 'scrape_with_filters_ignored':
		if media_type == 'movie': play_params = {'mode': play_mode, 'media_type': 'movie', 'tmdb_id': meta['tmdb_id'],
												'ignore_scrape_filters': 'true', 'prescrape': 'false', 'autoplay': 'false'}
		else: play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'], 'season': season,
							'episode': episode, 'ignore_scrape_filters': 'true', 'prescrape': 'false', 'autoplay': 'false'}
		kodi_utils.set_property('fs_filterless_search', 'true')
	elif choice == 'scrape_with_episode_group':
		choice = episode_groups_choice({'meta': meta, 'poster': poster})
		if choice == None: return playback_choice(params)
		episode_details = metadata.group_episode_data(metadata.group_details(choice), episode_id, season, episode)
		if not episode_details:
			kodi_utils.notification('No matching episode')
			return playback_choice(params)
		play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'], 'season': season, 'episode': episode, 'prescrape': 'false',
		'custom_season': episode_details['season'], 'custom_episode': episode_details['episode']}
	elif choice == 'scrape_with_aliases':
		if len(aliases) == 1: custom_title = aliases[0]
		else:
			list_items = [{'line1': i, 'icon': poster} for i in aliases]
			kwargs = {'items': json.dumps(list_items)}
			custom_title = kodi_utils.select_dialog(aliases, **kwargs)
			if custom_title == None: return kodi_utils.notification('Cancelled', 2500)
		custom_title = kodi_utils.kodi_dialog().input('Title', defaultt=custom_title)
		if not custom_title: return kodi_utils.notification('Cancelled', 2500)
		if media_type in ('movie', 'movies'): play_params = {'mode': play_mode, 'media_type': 'movie', 'tmdb_id': meta['tmdb_id'],
						'custom_title': custom_title, 'prescrape': 'false'}
		else: play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'], 'season': season, 'episode': episode,
							'custom_title': custom_title, 'prescrape': 'false'}
	elif choice == 'scrape_with_custom_values':
		default_title, default_year = meta['title'], str(meta['year'])
		if media_type in ('movie', 'movies'): play_params = {'mode': play_mode, 'media_type': 'movie', 'tmdb_id': meta['tmdb_id'], 'prescrape': 'false'}
		else: play_params = {'mode': play_mode, 'media_type': 'episode', 'tmdb_id': meta['tmdb_id'], 'season': season, 'episode': episode, 'prescrape': 'false'}
		if aliases:
			if len(aliases) == 1: alias_title = aliases[0]
			list_items = [{'line1': i, 'icon': poster} for i in aliases]
			kwargs = {'items': json.dumps(list_items)}
			alias_title = kodi_utils.select_dialog(aliases, **kwargs)
			if alias_title: custom_title = kodi_utils.kodi_dialog().input('Title', defaultt=alias_title)
			else: custom_title = kodi_utils.kodi_dialog().input('Title', defaultt=default_title)
		else: custom_title = kodi_utils.kodi_dialog().input('Title', defaultt=default_title)
		if not custom_title: return kodi_utils.notification('Cancelled', 2500)
		def _process_params(default_value, custom_value, param_value):
			if custom_value and custom_value != default_value: play_params[param_value] = custom_value
		_process_params(default_title, custom_title, 'custom_title')
		custom_year = kodi_utils.kodi_dialog().input('Year', type=1, defaultt=default_year)
		_process_params(default_year, custom_year, 'custom_year')
		if media_type == 'episode':
			custom_season = kodi_utils.kodi_dialog().input('Season', type=1, defaultt=season)
			_process_params(season, custom_season, 'custom_season')
			custom_episode = kodi_utils.kodi_dialog().input('Episode', type=1, defaultt=episode)
			_process_params(episode, custom_episode, 'custom_episode')
			if any(i in play_params for i in ('custom_season', 'custom_episode')):
				if settings.autoplay_next_episode(): _process_params('', 'true', 'disable_autoplay_next_episode')
		all_choice = kodi_utils.confirm_dialog(heading=meta.get('rootname', ''), text='Scrape with ALL External Scrapers?', ok_label='Yes', cancel_label='No')
		if all_choice == None: return kodi_utils.notification('Cancelled', 2500)
		if all_choice: _process_params('', 'true', 'disabled_ext_ignored')
		disable_filters_choice = kodi_utils.confirm_dialog(heading=meta.get('rootname', ''), text='Disable All Filters for Search?', ok_label='Yes', cancel_label='No')
		if disable_filters_choice == None: return kodi_utils.notification('Cancelled', 2500)
		if disable_filters_choice:
			_process_params('', 'true', 'ignore_scrape_filters')
			kodi_utils.set_property('fs_filterless_search', 'true')
	else: episodes_data = metadata.episodes_meta(orig_season, meta)
	if media_type == 'episode': play_params['playcount'] = playcount
	play_params[playback_key] = playback_key
	from modules.sources import Sources
	Sources().playback_prep(play_params)

def set_quality_choice(params):
	quality_setting = params.get('setting_id')
	icon = params.get('icon', None) or ''
	dl = ['Include 4K', 'Include 1080p', 'Include 720p', 'Include SD']
	fl = ['4K', '1080p', '720p', 'SD']
	q_setting = get_setting('redlight.%s' % quality_setting).split(', ')
	try: preselect = [fl.index(i) for i in q_setting]
	except: preselect = []
	list_items = [{'line1': item, 'icon': icon} for item in dl]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose the Included Qualities', 'multi_choice': 'true', 'preselect': preselect}
	choice = kodi_utils.select_dialog(fl, **kwargs)
	if choice is None: return
	if choice == []:
		kodi_utils.ok_dialog(text='You must select at least 1 Quality')
		return set_quality_choice(params)
	set_setting(quality_setting, ', '.join(choice))

def extras_buttons_choice(params):
	extras_button_label_values = kodi_utils.extras_button_label_values()
	media_type, button_dict, orig_button_dict = params.get('media_type', None), params.get('button_dict', {}), params.get('orig_button_dict', {})
	if not orig_button_dict:
		for _type in ('movie', 'tvshow'):
			setting_id_base = 'extras.%s.button' % _type
			for item in range(10, 18):
				setting_id = 'extras.%s.button%s' % (_type, item)
				try:
					button_action = get_setting('redlight.%s' % setting_id)
					button_label = extras_button_label_values[_type][button_action]
				except:
					set_setting(setting_id.replace('redlight.', ''), default_setting_values(setting_id)['setting_default'])
					button_action = get_setting('redlight.%s' % setting_id)
					button_label = extras_button_label_values[_type][button_action]
				button_dict[setting_id] = {'button_action': button_action, 'button_label': button_label, 'button_name': 'Button %s' % str(item - 9)}
				orig_button_dict[setting_id] = {'button_action': button_action, 'button_label': button_label, 'button_name': 'Button %s' % str(item - 9)}
	if media_type == None:
		choices = [('Set [B]Movie[/B] Buttons', 'movie'),
					('Set [B]TV Show[/B] Buttons', 'tvshow'),
					('Restore [B]Movie[/B] Buttons to Default', 'restore.movie'),
					('Restore [B]TV Show[/B] Buttons to Default', 'restore.tvshow'),
					('Restore [B]Movie & TV Show[/B] Buttons to Default', 'restore.both')]
		list_items = [{'line1': i[0]} for i in choices]
		kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Media Type to Set Buttons', 'narrow_window': 'true'}
		choice = kodi_utils.select_dialog(choices, **kwargs)
		if choice == None:
			if button_dict != orig_button_dict:
				for k, v in button_dict.items(): set_setting(k, v['button_action'])
			return
		media_type = choice[1]
		if 'restore' in media_type:
			restore_type = media_type.split('.')[1]
			if restore_type in ('movie', 'both'):
				for item in [(i, default_setting_values(i)['setting_default']) for i in ('extras.movie.button%s' % i for i in range(10,18))]:
					set_setting(item[0], item[1])
			if restore_type in ('tvshow', 'both'):
				for item in [(i, default_setting_values(i)['setting_default']) for i in ('extras.tvshow.button%s' % i for i in range(10,18))]:
					set_setting(item[0], item[1])
			return extras_buttons_choice({})
	choices = [('[B]%s[/B]   |   %s' % (v['button_name'], v['button_label']), v['button_name'], v['button_label'], k) for k, v in button_dict.items() if media_type in k]
	list_items = [{'line1': i[0]} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Button to Set', 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return extras_buttons_choice({'button_dict': button_dict, 'orig_button_dict': orig_button_dict})
	button_name, button_label, button_setting = choice[1:]
	choices = [(v, k) for k, v in extras_button_label_values[media_type].items() if not v == button_label]
	choices = [i for i in choices if not i[0] == button_label]
	list_items = [{'line1': i[0]} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Action For %s' % button_name, 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice == None: return extras_buttons_choice({'button_dict': button_dict, 'orig_button_dict': orig_button_dict, 'media_type': media_type})
	button_label, button_action = choice
	button_dict[button_setting] = {'button_action': button_action, 'button_label': button_label, 'button_name': button_name}
	return extras_buttons_choice({'button_dict': button_dict, 'orig_button_dict': orig_button_dict, 'media_type': media_type})

def extras_ratings_choice(params={}):
	choices = [('Metacritic', 'Meta', 'metacritic.png'), ('Tomato Rating Critic', 'Tom/Critic', 'rtcertified.png'),
				('Tomato Rating User', 'Tom/User', 'popcorn.png'), ('IMDb', 'IMDb', 'imdb.png'), ('TMDb', 'TMDb', 'tmdb.png')]
	list_items = [{'line1': i[0], 'icon': 'redlight_flags/ratings/%s' % i[2]} for i in choices]
	current_settings = settings.extras_enabled_ratings()
	try: preselect = [choices.index(i) for i in choices if i[1] in current_settings]
	except: preselect = []
	kwargs = {'items': json.dumps(list_items), 'heading': 'Ratings to Display', 'multi_choice': 'true', 'preselect': preselect}
	selection = kodi_utils.select_dialog(choices, **kwargs)
	if selection == None: return
	if selection == []:
		kodi_utils.ok_dialog(text='You must select at least 1 Ratings Provider')
		return extras_ratings_choice()
	set_setting('extras.enabled_ratings', ', '.join([i[1] for i in selection]))

def set_language_filter_choice(params):
	from modules.meta_lists import language_choices
	filter_setting_id, multi_choice, include_none = params.get('filter_setting_id'), params.get('multi_choice', 'false'), params.get('include_none', 'false')
	lang_choices = language_choices()
	if include_none == 'false': lang_choices.pop('None')
	dl, fl = list(lang_choices.keys()), list(lang_choices.values())
	set_filter = get_setting('redlight.%s' % filter_setting_id).split(', ')
	try: preselect = [fl.index(i) for i in set_filter]
	except: preselect = []
	list_items = [{'line1': item} for item in dl]
	kwargs = {'items': json.dumps(list_items), 'multi_choice': multi_choice, 'preselect': preselect}
	choice = kodi_utils.select_dialog(fl, **kwargs)
	if choice == None: return
	if multi_choice == 'true':
		if choice == []: set_setting(filter_setting_id, 'eng')
		else: set_setting(filter_setting_id, ', '.join(choice))
	else: set_setting(filter_setting_id, choice)

def enable_scrapers_choice(params={}):
	icon = params.get('icon', None) or kodi_utils.get_icon('redlight')
	scrapers = ['external', 'easynews', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'tb_cloud', 'folders']
	cloud_scrapers = {'rd_cloud': 'rd.enabled', 'pm_cloud': 'pm.enabled', 'ad_cloud': 'ad.enabled', 'tb_cloud': 'tb.enabled'}
	scraper_names = ['EXTERNAL SCRAPERS', 'EASYNEWS', 'RD CLOUD', 'PM CLOUD', 'AD CLOUD', 'TB CLOUD', 'FOLDERS 1-5']
	set_scrapers = settings.active_internal_scrapers()
	preselect = [scrapers.index(i) for i in set_scrapers]
	list_items = [{'line1': item, 'icon': icon} for item in scraper_names]
	kwargs = {'items': json.dumps(list_items), 'multi_choice': 'true', 'preselect': preselect}
	choice = kodi_utils.select_dialog(scrapers, **kwargs)
	if choice is None: return
	for i in scrapers:
		set_setting('provider.%s' % i, ('true' if i in choice else 'false'))
		if i in cloud_scrapers and i in choice: set_setting(cloud_scrapers[i], 'true')

def sources_folders_choice(params):
	from windows.base_window import open_window
	return open_window(('windows.settings_manager', 'SettingsManagerFolders'), 'settings_manager_folders.xml')

def results_sorting_choice(params):
	choices = [('Quality, Provider, Size', '0'), ('Quality, Size, Provider', '1'),
				('Provider, Quality, Size', '2'), ('Provider, Size, Quality', '3'),
				('Size, Quality, Provider', '4'), ('Size, Provider, Quality', '5')]
	list_items = [{'line1': item[0]} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice is None: return
	set_setting('results.sort_order_display', choice[0])
	set_setting('results.sort_order', choice[1])

def quality_sort_order_choice(params):
	default_order = ['4K', '1080p', '720p', 'SD']
	current_order = settings.quality_sort_order()
	choices = [{'line1': 'Position %02d' % (count + 1), 'line2': 'Currently [B]%s[/B]' % item,
			'current_item': item, 'display_position': count + 1, 'position': count}
			for count, item in enumerate(current_order)]
	kwargs = {'items': json.dumps(choices), 'heading': 'Quality Sort Order', 'multi_line': 'true', 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice is None: return
	current_item = choice['current_item']
	position = choice['position']
	display_position = choice['display_position']
	choices = [{'line1': item, 'value': item} for item in default_order if item != current_item]
	kwargs = {'items': json.dumps(choices), 'narrow_window': 'true', 'heading': 'Choose Quality for Position %02d' % display_position}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice is not None:
		value = choice['value']
		current_order.remove(value)
		current_order.insert(position, value)
		set_setting('results.quality_sort_order', ', '.join(current_order))
	return quality_sort_order_choice(params)

def results_format_choice(params):
	choices = [('List', kodi_utils.get_icon('results_list', 'results')), ('Rows', kodi_utils.get_icon('results_row', 'results')),
				('WideList', kodi_utils.get_icon('results_widelist', 'results'))]
	list_items = [{'line1': item[0], 'icon': item[1]} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Results Format'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice is None: return
	set_setting('results.list_format', choice[0])

def clear_favorites_choice(params):
	fl = [('Clear Movies Favorites', 'movie'), ('Clear TV Show Favorites', 'tvshow'), ('Clear People Favorites', 'people')]
	list_items = [{'line1': item[0]} for item in fl]
	kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
	media_type = kodi_utils.select_dialog([item[1] for item in fl], **kwargs)
	if media_type == None: return
	if not kodi_utils.confirm_dialog(): return
	from caches.favorites_cache import favorites_cache
	favorites_cache.clear_favorites(media_type)
	kodi_utils.notification('Success', 3000)

def highlight_background_opacity_choice(params):
	choices = [('20%', '33'), ('30%', '4D'), ('40%', '66'), ('50%', '80'), ('60%', '99'), ('70%', 'B3'), ('80%', 'CC')]
	list_items = [{'line1': item[0]} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(choices, **kwargs)
	if choice is None: return
	set_setting('highlight.background_opacity_name', choice[0])
	set_setting('highlight.background_opacity', choice[1])

def scraper_color_choice(params):
	setting = params.get('setting_id')
	current_setting, original_highlight = get_setting('redlight.%s' % setting), default_setting_values(setting)['setting_default']
	if current_setting != original_highlight:
		action = kodi_utils.confirm_dialog(text='Set new Highlight or Restore Default Highlight?', ok_label='Set New', cancel_label='Restore Default', default_control=10)
		if action == None: return
		if not action: return set_setting(setting, original_highlight)
	chosen_color = color_choice({'current_setting': current_setting})
	if chosen_color: set_setting(setting, chosen_color)

def personal_list_unseen_color_choice(params):
	setting = 'personal_list.unseen_highlight'
	current_setting, original_highlight = get_setting('redlight.%s' % setting), default_setting_values(setting)['setting_default']
	if current_setting != original_highlight:
		action = kodi_utils.confirm_dialog(text='Set new Highlight or Restore Default Highlight?', ok_label='Set New', cancel_label='Restore Default', default_control=10)
		if action == None: return
		if not action: return set_setting(setting, original_highlight)
	chosen_color = color_choice({'current_setting': current_setting})
	if chosen_color: set_setting(setting, chosen_color)

def color_choice(params):
	from windows.base_window import open_window
	return open_window(('windows.color', 'SelectColor'), 'color.xml', current_setting=params.get('current_setting', None))

def mpaa_region_choice(params={}):
	from modules.meta_lists import regions as rg
	regions = rg()
	regions.sort(key=lambda x: x['name'])
	list_items = [{'line1': i['name']} for i in regions]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Set MPAA Region', 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(regions, **kwargs)
	if choice == None: return None
	from caches.meta_cache import delete_meta_cache
	set_setting('mpaa_region', choice['id'])
	set_setting('mpaa_region_display_name', choice['name'])
	delete_meta_cache(silent=True)

def lists_cache_duration_choice(params={}):
	durations = [{'name': '6 hours', 'duration': '6'}, {'name': '12 hours', 'duration': '12'}, {'name': '18 hours', 'duration': '18'}, {'name': '1 Day', 'duration': '24'},
				{'name': '2 Days', 'duration': '48'}, {'name': '3 Days', 'duration': '72'}, {'name': '4 Days', 'duration': '96'}, {'name': '5 Days', 'duration': '120'},
				{'name': '6 Days', 'duration': '144'}, {'name': '7 Days', 'duration': '168'}]
	list_items = [{'line1': i['name']} for i in durations]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Set Generic List Cache Duration', 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog(durations, **kwargs)
	if choice == None: return None
	set_setting('lists_cache_duraton', choice['duration'])
	set_setting('lists_cache_duraton_display_name', choice['name'])

def options_menu_choice(params, meta=None):
	from caches.episode_groups_cache import episode_groups_cache
	from modules.utils import get_datetime
	from modules import metadata
	params_get = params.get
	tmdb_id, content, poster = params_get('tmdb_id', None), params_get('content', None), params_get('poster', None)
	is_external, from_extras = params_get('is_external') in (True, 'True', 'true'), params_get('from_extras', 'false') == 'true'
	season, episode = params_get('season', ''), params_get('episode', '')
	single_ep_list = ('episode.progress', 'episode.recently_watched', 'episode.next_trakt', 'episode.next_redlight', 'episode.next_simkl', 'episode.next_mdblist',
					'episode.next_punchplay', 'episode.mdblist_next', 'episode.trakt_recently_aired', 'episode.trakt_calendar', 'episode.mdblist_calendar',
					'episode.punchplay_calendar', 'episode.simkl_calendar')
	if not content: content = kodi_utils.container_content()[:-1]
	menu_type = content
	if content.startswith('episode.'): content = 'episode'
	if not meta:
		function = metadata.movie_meta if content == 'movie' else metadata.tvshow_meta
		meta = function('tmdb_id', tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
	meta_get = meta.get
	rootname, title, imdb_id, tvdb_id = meta_get('rootname', None), meta_get('title'), meta_get('imdb_id', None), meta_get('tvdb_id', None)
	window_function = kodi_utils.activate_window if is_external else kodi_utils.container_update
	listing = []
	listing_append = listing.append
	# Episode / Next Episodes / calendars use the parent show for list managers (same as Progress).
	list_manager_media = 'movie' if content == 'movie' else 'tvshow'
	if from_extras:
		if menu_type in ('movie', 'episode'): listing_append(('Playback Options', 'Scrapers Options', 'playback_choice'))
	if menu_type in ('movie', 'tvshow') or content == 'episode' or menu_type in single_ep_list:
		if settings.mdblist_user_active(): listing_append(('MDBList Manager', '', 'mdblist_manager'))
		if settings.punchplay_user_active(): listing_append(('PunchPlay Manager', '', 'punchplay_manager'))
		if settings.simkl_user_active(): listing_append(('Simkl Lists Manager', '', 'simkl_manager'))
		if settings.tmdblist_user_active(): listing_append(('TMDb Lists Manager', '', 'tmdblists_manager_choice'))
		if settings.trakt_user_active(): listing_append(('Trakt Lists Manager', '', 'trakt_manager'))
		listing_append(('Personal Lists Manager', '', 'personallists_manager_choice'))
		listing_append(('Favorites Manager', '', 'favorites_manager_choice'))
	if menu_type == 'tvshow': listing_append(('Play Random', 'Based On %s' % rootname, 'random'))
	if menu_type in ('tvshow', 'season'):
		listing_append(('Assign an Episode Group to %s' % rootname, 'Currently %s' % episode_groups_cache.get(tmdb_id).get('name', 'None'), 'episode_group'))
	if menu_type in ('movie', 'episode') or menu_type in single_ep_list:
		base_str1, base_str2, on_str, off_str = '%s%s', 'Currently: [B]%s[/B]', 'On', 'Off'
		if settings.auto_play(content): autoplay_status, autoplay_toggle, quality_setting = on_str, 'false', 'autoplay_quality_%s' % content
		else: autoplay_status, autoplay_toggle, quality_setting = off_str, 'true', 'results_quality_%s' % content
		set_active = settings.active_internal_scrapers()
		active_int_scrapers = [i.replace('_', '') for i in set_active]
		current_scrapers_status = ', '.join([i for i in active_int_scrapers]) if len(active_int_scrapers) > 0 else 'N/A'
		current_quality_status =  ', '.join(settings.quality_filter(quality_setting))
		autoplay_next_status, autoplay_next_toggle = (on_str, 'false') if settings.autoplay_next_episode() else (off_str, 'true')
		listing_append((base_str1 % ('Auto Play', ' (%s)' % content), base_str2 % autoplay_status, 'toggle_autoplay'))
		if menu_type == 'episode' or menu_type in single_ep_list:
			if autoplay_status == on_str:
				autoplay_next_status, autoplay_next_toggle = (on_str, 'false') if settings.autoplay_next_episode() else (off_str, 'true')
				listing_append((base_str1 % ('Autoplay Next Episode', ''), base_str2 % autoplay_next_status, 'toggle_autoplay_next'))
			else:
				autoscrape_next_status, autoscrape_next_toggle = (on_str, 'false') if settings.autoscrape_next_episode() else (off_str, 'true')
				listing_append((base_str1 % ('Autoscrape Next Episode', ''), base_str2 % autoscrape_next_status, 'toggle_autoscrape_next'))
		listing_append((base_str1 % ('Quality Limit', ' (%s)' % content), base_str2 % current_quality_status, 'set_quality'))
		listing_append((base_str1 % ('', 'Enable Scrapers'), base_str2 % current_scrapers_status, 'enable_scrapers'))
		if menu_type == 'episode' or menu_type in single_ep_list:
			listing_append(('Assign an Episode Group to %s' % rootname, base_str2 % episode_groups_cache.get(tmdb_id).get('name', 'None'), 'episode_group'))
	if not from_extras:
		if menu_type in ('movie', 'tvshow'):
			listing_append(('Re-Cache %s Info' % ('Movies' if menu_type == 'movie' else 'TV Shows'), 'Clear %s Cache' % rootname, 'clear_media_cache'))
		if menu_type in ('movie', 'episode') or menu_type in single_ep_list: listing_append(('Clear Scrapers Cache', '', 'clear_scrapers_cache'))
		if menu_type in ('tvshow', 'season', 'episode') or menu_type in single_ep_list: listing_append(('TV Shows Progress Manager', '', 'nextep_manager'))
		listing_append(('Open Download Manager', '', 'open_download_manager'))
		listing_append(('Open Tools', '', 'open_tools'))
		if menu_type in ('movie', 'episode', 'tvshow', 'season') or menu_type in single_ep_list:
			configured_scrapers = settings.configured_external_scraper_slots()
			if configured_scrapers:
				listing_append((settings.external_scraper_settings_options_label(), '', 'open_external_scraper_settings'))
		listing_append(('Open Settings', '', 'open_settings'))
	list_items = [{'line1': item[0], 'line2': item[1] or item[0], 'icon': poster} for item in listing]
	heading = rootname or 'Options...'
	kwargs = {'items': json.dumps(list_items), 'heading': heading, 'multi_line': 'true'}
	choice = kodi_utils.select_dialog([i[2] for i in listing], **kwargs)
	if choice == None: return
	if choice == 'clear_media_cache':
		from caches.base_cache import refresh_cached_data
		kodi_utils.close_all_dialog()
		return refresh_cached_data(meta)
	if choice == 'clear_scrapers_cache':
		from modules.source_utils import clear_scrapers_cache
		return clear_scrapers_cache()
	if choice == 'open_download_manager':
		from modules.downloader import manager
		kodi_utils.close_all_dialog()
		return manager()
	if choice == 'open_tools':
		kodi_utils.close_all_dialog()
		return window_function({'mode': 'navigator.tools'})
	if choice == 'open_settings':
		kodi_utils.close_all_dialog()
		return kodi_utils.open_settings()
	if choice == 'open_external_scraper_settings':
		kodi_utils.close_all_dialog()
		return kodi_utils.external_scraper_settings()
	if choice == 'playback_choice':
		return playback_choice({'media_type': content, 'poster': poster, 'meta': meta, 'season': season, 'episode': episode})
	if choice == 'nextep_manager':
		return window_function({'mode': 'build_next_episode_manager'})
	if choice == 'random':
		kodi_utils.close_all_dialog()
		return random_choice({'meta': meta, 'poster': poster})
	if choice == 'trakt_manager':
		return trakt_manager_choice({'tmdb_id': tmdb_id, 'imdb_id': imdb_id, 'tvdb_id': tvdb_id or 'None', 'media_type': list_manager_media, 'icon': poster,
									'season': season, 'episode': episode, 'episode_id': params_get('episode_id')})
	if choice == 'simkl_manager':
		return simkl_manager_choice({'tmdb_id': tmdb_id, 'imdb_id': imdb_id, 'tvdb_id': tvdb_id or 'None', 'media_type': list_manager_media, 'icon': poster,
									'title': title, 'season': season, 'episode': episode})
	if choice == 'mdblist_manager':
		return mdblist_manager_choice({'tmdb_id': tmdb_id, 'imdb_id': imdb_id, 'tvdb_id': tvdb_id or 'None', 'media_type': list_manager_media, 'icon': poster,
									'title': title, 'season': season, 'episode': episode, 'episode_id': params_get('episode_id')})
	if choice == 'punchplay_manager':
		return punchplay_manager_choice({'tmdb_id': tmdb_id, 'imdb_id': imdb_id, 'tvdb_id': tvdb_id or 'None', 'media_type': list_manager_media, 'icon': poster,
									'title': title, 'season': season, 'episode': episode})
	if choice == 'personallists_manager_choice':
		from modules.utils import get_current_timestamp
		return personallists_manager_choice({'list_type': list_manager_media, 'tmdb_id': tmdb_id, 'title': title,
							'premiered': meta_get('premiered'), 'current_time': get_current_timestamp(), 'icon': poster})
	if choice == 'favorites_manager_choice':
		return favorites_manager_choice({'media_type': list_manager_media, 'tmdb_id': tmdb_id, 'title': title})
	if choice == 'tmdblists_manager_choice':
		return tmdblists_manager_choice({'media_type': 'movie' if list_manager_media == 'movie' else 'tv', 'tmdb_id': tmdb_id, 'icon': poster})
	if choice == 'toggle_autoplay':
		set_setting('auto_play_%s' % content, autoplay_toggle)
	elif choice == 'toggle_autoplay_next':
		set_setting('autoplay_next_episode', autoplay_next_toggle)
	elif choice == 'toggle_autoscrape_next':
		set_setting('autoscrape_next_episode', autoscrape_next_toggle)
	elif choice == 'set_quality':
		set_quality_choice({'setting_id': 'autoplay_quality_%s' % content if autoplay_status == on_str else 'results_quality_%s' % content, 'icon': poster})
	elif choice == 'enable_scrapers':
		enable_scrapers_choice({'icon': poster})
	elif choice == 'episode_group':
		assign_episode_group_choice({'meta': meta, 'poster': poster})
	options_menu_choice(params, meta=meta)

def extras_menu_choice(params):
	from windows.base_window import open_window
	from modules.utils import get_datetime
	from modules import metadata
	stacked = params.get('stacked', 'false') == 'true'
	if not stacked: kodi_utils.show_busy_dialog()
	media_type = params['media_type']
	function = metadata.movie_meta if media_type == 'movie' else metadata.tvshow_meta
	meta = function('tmdb_id', params['tmdb_id'], settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
	if not stacked: kodi_utils.hide_busy_dialog()
	open_window(('windows.extras', 'Extras'), 'extras.xml', meta=meta, is_external=params.get('is_external', 'true' if kodi_utils.external() else 'false'),
															options_media_type=media_type, starting_position=params.get('starting_position', None))

def open_movieset_choice(params):
	kodi_utils.hide_busy_dialog()
	window_function = kodi_utils.activate_window if params['is_external'] in (True, 'True', 'true') else kodi_utils.container_update
	return window_function({'mode': 'build_movie_list', 'action': 'tmdb_movies_sets', 'key_id': params['key_id'], 'name': params['name']})

def media_extra_info_choice(params):
	from modules.utils import adjust_premiered_date
	from modules.source_utils import get_aliases_titles, make_alias_dict
	media_type, meta = params.get('media_type'), params.get('meta')
	extra_info, listings = meta.get('extra_info', None), []
	append = listings.append
	try:
		if media_type == 'movie':
			if meta['tagline']: append('[B]Tagline:[/B] %s' % meta['tagline'])
			aliases = get_aliases_titles(make_alias_dict(meta, meta['title']))
			if aliases: append('[B]Aliases:[/B] %s' % ', '.join(aliases))
			append('[B]Status:[/B] %s' % extra_info['status'])
			append('[B]Premiered:[/B] %s' % meta['premiered'])
			append('[B]Rating:[/B] %s (%s Votes)' % (str(round(meta['rating'], 1)), meta['votes']))
			append('[B]Runtime:[/B] %s mins' % int(float(meta['duration'])/60))
			append('[B]Genre/s:[/B] %s' % ', '.join(meta['genre']))
			append('[B]Budget:[/B] %s' % extra_info['budget'])
			append('[B]Revenue:[/B] %s' % extra_info['revenue'])
			append('[B]Director:[/B] %s' % ', '.join(meta['director']))
			append('[B]Writer/s:[/B] %s' % ', '.join(meta['writer']) or 'N/A')
			append('[B]Studio:[/B] %s' % ', '.join(meta['studio']) or 'N/A')
			if extra_info['collection_name']: append('[B]Collection:[/B] %s' % extra_info['collection_name'])
			append('[B]Homepage:[/B] %s' % extra_info['homepage'])
		else:
			append('[B]Type:[/B] %s' % extra_info['type'])
			if meta['tagline']: append('[B]Tagline:[/B] %s' % meta['tagline'])
			aliases = get_aliases_titles(make_alias_dict(meta, meta['title']))
			if aliases: append('[B]Aliases:[/B] %s' % ', '.join(aliases))
			append('[B]Status:[/B] %s' % extra_info['status'])
			append('[B]Premiered:[/B] %s' % meta['premiered'])
			append('[B]Rating:[/B] %s (%s Votes)' % (str(round(meta['rating'], 1)), meta['votes']))
			append('[B]Runtime:[/B] %d mins' % int(float(meta['duration'])/60))
			append('[B]Classification:[/B] %s' % meta['mpaa'])
			append('[B]Genre/s:[/B] %s' % ', '.join(meta['genre']))
			append('[B]Networks:[/B] %s' % ', '.join(meta['studio']))
			append('[B]Created By:[/B] %s' % extra_info['created_by'])
			try:
				last_ep = extra_info['last_episode_to_air']
				append('[B]Last Aired:[/B] %s - [B]S%.2dE%.2d[/B] - %s' \
					% (adjust_premiered_date(last_ep['air_date'], settings.date_offset())[0].strftime('%d %B %Y'),
						last_ep['season_number'], last_ep['episode_number'], last_ep['name']))
			except: pass
			try:
				next_ep = extra_info['next_episode_to_air']
				append('[B]Next Aired:[/B] %s - [B]S%.2dE%.2d[/B] - %s' \
					% (adjust_premiered_date(next_ep['air_date'], settings.date_offset())[0].strftime('%d %B %Y'),
						next_ep['season_number'], next_ep['episode_number'], next_ep['name']))
			except: pass
			append('[B]Seasons:[/B] %s' % meta['total_seasons'])
			try:
				from modules.watched_status import progress_aired_eps
				append('[B]Episodes:[/B] %s' % progress_aired_eps(meta))
			except Exception:
				append('[B]Episodes:[/B] %s' % meta['total_aired_eps'])
			append('[B]Homepage:[/B] %s' % extra_info['homepage'])
	except: return kodi_utils.notification('Error', 2000)
	return '[CR][CR]'.join(listings)

def discover_choice(params):
	from windows.base_window import open_window
	open_window(('windows.discover', 'Discover'), 'discover.xml', media_type=params['media_type'])

def sort_default_choice(params):
	from modules import list_sort
	media_type = params['media_type']
	setting_id = 'sort.default.%s' % media_type
	current = list_sort.parse_spec(get_setting('redlight.%s' % setting_id, ''))
	heading = 'Default Sort For %s' % ('Movies' if media_type == 'movies' else 'TV Shows')
	# Not any single adapter's field list: this setting is read by every mediatype-split list at once,
	# and a field one of those adapters cannot extract would leave that list in raw cache order.
	spec = _pick_sort_spec(heading, None, current=current, fields=list_sort.default_field_choices())
	if spec == None: return
	set_setting(setting_id, list_sort.format_spec(spec))
	set_setting('%s_name' % setting_id, list_sort.spec_label(spec))
	kodi_utils.kodi_refresh()

def list_sort_override_choice(params):
	from modules import list_sort
	from caches.list_sort_cache import scope_key, set_override, delete_override
	list_key, media_type, adapter_name = params['list_key'], params.get('media_type'), params['adapter']
	scope = scope_key(list_key, media_type)
	# The fallback is the ordering the list has when nothing is stored for it - a Trakt user list's
	# own declared sort, say - so without it the "current" marker would point at title:asc for every
	# list the user has never overridden, which is not the order on screen.
	current = list_sort.resolve(list_key, media_type, params.get('fallback'))
	spec = _pick_sort_spec('Custom Sort', adapter_name, allow_default=True, current=current)
	if spec == None: return
	if spec == 'use_default': success = delete_override(scope)
	else: success = set_override(scope, list_sort.format_spec(spec))
	if success: kodi_utils.kodi_refresh()
	else: kodi_utils.ok_dialog('Custom Sort', 'An Error Occurred')

def _pick_sort_spec(heading, adapter_name, allow_default=False, current=None, fields=None):
	"""Two stage picker: field, then direction. Returns a spec dict, 'use_default', or None.

	'current' is the spec the list is sorted by right now; the matching entries are marked.
	'fields' overrides the adapter's own capabilities, for a setting read by several adapters at once.
	"""
	from modules import list_sort
	current = current or {}
	if fields is None: fields = list_sort.field_choices(adapter_name)
	choices = []
	if allow_default: choices.append(('use_default', 'Use Default'))
	choices.extend([(i, list_sort.FIELD_LABELS.get(i, i)) for i in fields])
	if not choices: return None
	field = _sort_select_dialog(choices, '%s: Field' % heading, current.get('field'))
	if field == None: return None
	if field == 'use_default': return 'use_default'
	if field in list_sort.DIRECTIONLESS_FIELDS: return {'field': field, 'direction': 'asc'}
	direction_choices = [('asc', 'Ascending'), ('desc', 'Descending')]
	current_direction = current.get('direction') if current.get('field') == field else None
	direction = _sort_select_dialog(direction_choices, '%s: Direction' % heading, current_direction)
	if direction == None: return None
	return {'field': field, 'direction': direction}

def _sort_select_dialog(choices, heading, current_value):
	current_mark = '   [B][COLOR green][CURRENT][/COLOR][/B]'
	list_items = [{'line1': '%s%s' % (i[1], current_mark if i[0] == current_value else ''), 'line2': ''} for i in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': heading, 'narrow_window': 'true'}
	return kodi_utils.select_dialog([i[0] for i in choices], **kwargs)
