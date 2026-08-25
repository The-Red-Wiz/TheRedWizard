# -*- coding: utf-8 -*-
import json
from urllib.parse import parse_qsl, unquote
from caches.navigator_cache import navigator_cache
from modules import kodi_utils
# logger = kodi_utils.logger

class MenuEditor:
	def __init__(self, params):
		self.main_list_name_dict = {'RootList': 'Root', 'MovieList': 'Movies', 'TVShowList': 'TV Shows', 'AnimeList': 'Animes'}
		self.active_list = params.get('active_list')
		self.position = int(params.get('position', '0'))
		self.action = params.get('action')
		self.url = params.get('url', None)
		try: self.list_name = self.main_list_name_dict[self.active_list]
		except: self.list_name = params.get('name')
		self.name = params.get('name', '') or self._item_name_at_position()

	def _active_list_items(self):
		if self.active_list in navigator_cache.main_menus:
			return navigator_cache.currently_used_list(self.active_list)
		return navigator_cache.get_shortcut_folder_contents(self.active_list)

	def _item_name_at_position(self):
		try:
			list_items = self._active_list_items()
			if list_items and 0 <= self.position < len(list_items):
				return list_items[self.position].get('name', '')
		except: pass
		try: return self._get_menu_item(kodi_utils.get_infolabel('ListItem.FileNameAndPath')).get('name', '')
		except: return ''

	def move(self):
		list_items = navigator_cache.currently_used_list(self.active_list)
		list_items = self._materialize_injected_public_calendar(list_items)
		if len(list_items) <= 1: return
		if self.position < 0 or self.position >= len(list_items): return kodi_utils.notification('Cancelled', 1500)
		if not self.name: self.name = list_items[self.position].get('name', '')
		choice_items = [i for i in list_items if str(i['name']) != str(self.name)]
		new_position = self._menu_select(choice_items, self.name, multi_line='true', position_list=True)
		if new_position == None or new_position == self.position: return
		list_items.insert(new_position, list_items.pop(self.position))
		self._db_execute('set', self.active_list, list_items)

	def remove(self):
		if self._is_settings_public_calendar():
			return kodi_utils.notification('Turn off Show Public Calendar in Settings > Single Episode Lists > Calendars.', 4000)
		if not kodi_utils.confirm_dialog(): return kodi_utils.notification('Cancelled', 1500)
		list_items = navigator_cache.currently_used_list(self.active_list)
		if len(list_items) == 1: return kodi_utils.notification('Cancelled', 1500)
		if self.position < 0 or self.position >= len(list_items): return kodi_utils.notification('Cancelled', 1500)
		list_items.pop(self.position)
		self._db_execute('set', self.active_list, list_items)

	def _public_calendar_item(self):
		optional = navigator_cache.optional_menus.get(self.active_list) or []
		item = next((dict(i) for i in optional if i.get('mode') == 'build_simkl_public_calendar'), None)
		if not item:
			item = {'name': 'Public Calendar', 'mode': 'build_simkl_public_calendar', 'iconImage': 'calender'}
		if self.active_list == 'TVShowList' and not item.get('feeds'):
			from modules import settings as s
			item['feeds'] = 'all' if s.public_calendar_include_anime() else 'tv'
		elif self.active_list == 'AnimeList':
			item['feeds'] = 'anime'
		return item

	def _focused_is_public_calendar(self):
		if self.name == 'Public Calendar': return True
		stored = navigator_cache.currently_used_list(self.active_list) or []
		if stored and 0 <= self.position < len(stored) and stored[self.position].get('mode') == 'build_simkl_public_calendar':
			return True
		try:
			item = self._get_menu_item(kodi_utils.get_infolabel('ListItem.FileNameAndPath'))
			return item.get('mode') == 'build_simkl_public_calendar' or item.get('name') == 'Public Calendar'
		except: return False

	def _is_settings_public_calendar(self):
		if self.active_list not in ('TVShowList', 'AnimeList'): return False
		from modules import settings as s
		if not s.show_public_calendars(): return False
		return self._focused_is_public_calendar()

	def _materialize_injected_public_calendar(self, list_items):
		list_items = list(list_items or [])
		item = self._public_calendar_item()
		if self._menu_has_item(list_items, item):
			if self.position < 0 or self.position >= len(list_items):
				for idx, row in enumerate(list_items):
					if row.get('mode') == 'build_simkl_public_calendar':
						self.position = idx
						break
			return list_items
		if not self._focused_is_public_calendar(): return list_items
		list_items.append(item)
		self.position = len(list_items) - 1
		return list_items

	def restore(self):
		if not kodi_utils.confirm_dialog(): return kodi_utils.notification('Cancelled', 1500)
		if self.active_list not in navigator_cache.main_menus: return kodi_utils.notification('Cancelled', 1500)
		contents = navigator_cache.stock_menu_contents(self.active_list)
		for list_type in ('edited', 'opted_optional', 'default'):
			navigator_cache.delete_memory_cache(self.active_list, list_type)
		navigator_cache.delete_list(self.active_list, 'edited')
		navigator_cache.delete_list(self.active_list, 'opted_optional')
		navigator_cache.set_list(self.active_list, 'default', contents)
		kodi_utils.notification('Success', 1500)
		kodi_utils.sleep(500)
		kodi_utils.container_update(kodi_utils.build_folder_url({'mode': 'navigator.main', 'action': self.active_list}))

	def reload(self):
		default, edited = navigator_cache.get_main_lists(self.active_list)
		list_type = 'edited' if edited else 'default'
		current_list = edited or default
		try: new_item = [i for i in default if str(i['name']) == str(self.name)][0]
		except: return kodi_utils.notification('No Results', 1500)
		list_items = [i for i in current_list if str(i['name']) != str(self.name)]
		list_items.insert(self.position, new_item)
		self._db_execute('set', self.active_list, list_items, list_type)

	def update(self):
		stock = navigator_cache.main_menus.get(self.active_list) or []
		optional = navigator_cache.optional_menus.get(self.active_list) or []
		default, edited = navigator_cache.get_main_lists(self.active_list)
		list_type = 'edited' if edited else'default'
		current_list = edited or navigator_cache.without_optional_extras(self.active_list, default)
		new_from_catalog = [i for i in stock if not self._menu_has_item(default, i)]
		# Optional extras already opted-in belong in Browse Removed until Restore.
		opted = navigator_cache.get_opted_optional(self.active_list)
		new_optional = [i for i in optional if not self._menu_has_item(current_list, i) and not self._menu_has_item(opted, i)]
		new_entries = new_from_catalog + new_optional
		if not new_entries: return kodi_utils.notification('No New Items', 1500)
		added = False
		added_optional = False
		optional_names = {i.get('name') for i in optional}
		for new_entry in new_entries:
			new_entry_translated_name = new_entry.get('name')
			if not kodi_utils.confirm_dialog(text='New item [B]%s[/B] Exists[CR]Would you like to add this to the Menu?' % new_entry_translated_name):
				continue
			item_position = self._menu_select(current_list, new_entry_translated_name, position_list=True)
			if item_position == None: continue
			current_list.insert(item_position, new_entry)
			added = True
			if new_entry.get('name') in optional_names: added_optional = True
		if not added: return kodi_utils.notification('Cancelled', 1500)
		# Default stays stock so Restore cannot put extras back. Opted extras are a separate list.
		stock_contents = navigator_cache.stock_menu_contents(self.active_list)
		if added_optional or list_type == 'edited':
			self._db_execute('set', self.active_list, current_list, 'edited', refresh=False)
			self._db_execute('set', self.active_list, stock_contents, 'default', refresh=False)
			if added_optional:
				for entry in current_list:
					if entry.get('name') in optional_names and not self._menu_has_item(opted, entry):
						opted.append(dict(entry))
				navigator_cache.set_list(self.active_list, 'opted_optional', opted)
			self._refresh_menu()
		else:
			self._db_execute('set', self.active_list, current_list, 'default')

	def browse(self):
		list_name =  self.main_list_name_dict[self.active_list]
		try: choice_items = self._get_removed_items()
		except: return kodi_utils.notification('No Results', 1500)
		if not choice_items: return kodi_utils.notification('No Results', 1500)
		browse_item = self._menu_select(choice_items, list_name)
		if browse_item == None: return
		browse_item = choice_items[browse_item]
		item_name = browse_item.get('name', '')
		# Let the item picker close first — a second Select on top of it never appears.
		kodi_utils.sleep(400)
		add_back = kodi_utils.confirm_dialog(heading=item_name,
			text='Add [B]%s[/B] back to this menu, or browse?' % item_name,
			ok_label='Add to Menu', cancel_label='Browse', default_control=10)
		if add_back == None: return
		if add_back:
			default, edited = navigator_cache.get_main_lists(self.active_list)
			optional_names = {i.get('name') for i in (navigator_cache.optional_menus.get(self.active_list) or [])}
			is_optional = browse_item.get('name') in optional_names or browse_item.get('nextep_sort')
			current_list = edited or navigator_cache.without_optional_extras(self.active_list, default)
			position = self._menu_select(current_list, item_name, multi_line='true', position_list=True)
			if position == None: return kodi_utils.notification('Cancelled', 1500)
			current_list.insert(position, browse_item)
			if is_optional or edited:
				self._db_execute('set', self.active_list, current_list, 'edited')
			else:
				self._db_execute('set', self.active_list, current_list, 'default')
			return
		if browse_item.get('mode') == 'build_popular_people': command = 'RunPlugin(%s)'
		else: command = 'Container.Update(%s)'
		kodi_utils.execute_builtin(command % kodi_utils.build_url(browse_item))

	def add(self):
		list_name =  self.main_list_name_dict[self.active_list]
		list_items = navigator_cache.currently_used_list(self.active_list)
		browsed_result = self._path_browser()
		if browsed_result == None: return
		menu_item = self._get_menu_item(browsed_result['file'])
		name, icon = browsed_result['label'], self._get_icon_var(browsed_result['thumbnail'])
		menu_name = self._prompt_add_name(name)
		if not menu_name: return
		icon_choice = self._icon_select(default_icon=icon)
		if icon_choice is None: return kodi_utils.notification('Cancelled', 1500)
		menu_item.update({'name': menu_name, 'iconImage': icon_choice})
		position = self._menu_select(list_items, list_name, multi_line='true', position_list=True)
		if position == None: return kodi_utils.notification('Cancelled', 1500)
		list_items.insert(position, menu_item)
		self._db_execute('set', self.active_list, list_items)

	def shortcut_folder_edit(self):
		if self.action == 'clear':
			if not kodi_utils.confirm_dialog(): return kodi_utils.notification('Cancelled', 1500)
			list_items = []
		elif self.action == 'add': return self.shortcut_folder_add()
		else:
			list_items = navigator_cache.get_shortcut_folder_contents(self.active_list)
			if self.action == 'rename':
				current_item = list_items[self.position]
				item_name = current_item['name']
				new_item_name = self._get_external_name_input(item_name)
				if not new_item_name or new_item_name == item_name: return
				current_item['name'] = new_item_name
				list_items[self.position] == current_item
			elif self.action == 'remove':
				if not kodi_utils.confirm_dialog(): return kodi_utils.notification('Cancelled', 1500)
				if self.position < 0 or self.position >= len(list_items): return
				list_items.pop(self.position)
			elif self.action == 'move':
				if len(list_items) <= 1: return
				choice_items = [i for i in list_items if str(i['name']) != str(self.name)]
				new_position = self._menu_select(choice_items, self.name, multi_line='true', position_list=True)
				if new_position == None or new_position == self.position: return
				list_items.insert(new_position, list_items.pop(self.position))
			elif self.action == 'add':
				return self.shortcut_folder_add()
		self._db_execute('set', self.active_list, list_items, 'shortcut_folder')

	def shortcut_folder_make(self):
		list_name = kodi_utils.kodi_dialog().input('')
		if not list_name: return
		self._db_execute('make_new_shortcut_folder', list_name, list_type='shortcut_folder')

	def shortcut_folder_delete(self):
		if not kodi_utils.confirm_dialog(): return kodi_utils.notification('Cancelled', 1500)
		main_menus = navigator_cache.main_menus
		main_menu_items_list = [(i, navigator_cache.currently_used_list(i)) for i in main_menus]
		self._db_execute('delete', self.name, list_type='shortcut_folder')
		self._remove_active_shortcut_folder(main_menu_items_list, self.name)

	def shortcut_folder_rename(self):
		new_folder_name = self._get_external_name_input(self.name)
		if not new_folder_name: return
		if new_folder_name == self.name: return
		list_items = navigator_cache.get_shortcut_folder_contents(self.name)
		self._db_execute('delete', self.name, list_type='shortcut_folder', refresh=False)
		self._db_execute('make_new_shortcut_folder', new_folder_name, list_items)

	def shortcut_folder_convert(self):
		list_items = navigator_cache.get_shortcut_folder_contents(self.name)
		valid_random_items = [i for i in list_items if i.get('mode').replace('random.', '') in kodi_utils.random_valid_type_check()]
		make_random = '[COLOR red][RANDOM][/COLOR]' not in self.name
		if make_random:
			if not valid_random_items: return kodi_utils.notification('No random supported items in this list', 5000)
			new_folder_name = self.name + ' [COLOR red][RANDOM][/COLOR]'
		else: new_folder_name = self.name.replace(' [COLOR red][RANDOM][/COLOR]', '')
		self._db_execute('delete', self.name, list_type='shortcut_folder', refresh=False)
		self._db_execute('make_new_shortcut_folder', new_folder_name, list_items)

	def shortcut_folder_add(self):
		choice_name, list_items = self.list_name, navigator_cache.get_shortcut_folder_contents(self.list_name)
		browsed_result = self._path_browser()
		if browsed_result == None: return
		menu_item = self._get_menu_item(browsed_result['file'])
		if menu_item.get('mode', '').startswith('random.'): menu_item['random'] = 'true'
		name, icon = browsed_result['label'], self._get_icon_var(browsed_result['thumbnail'])
		menu_name = self._prompt_add_name(name)
		if not menu_name: return
		icon_choice = self._icon_select(default_icon=icon)
		if icon_choice is None: return kodi_utils.notification('Cancelled', 1500)
		menu_item.update({'name': menu_name, 'iconImage': icon_choice, 'full_list': 'false'})
		if list_items:
			position = self._menu_select(list_items, menu_name, multi_line='true', position_list=True)
			if position == None: return kodi_utils.notification('Cancelled', 1500)
		else: position = 0
		list_items.insert(position, menu_item)
		self._db_execute('set', choice_name, list_items, 'shortcut_folder')

	def shortcut_folder_add_known(self):
		file = self.url
		menu_item = self._get_menu_item(file)
		name = menu_item.get('name') or menu_item.get('list_name') or menu_item.get('category_name') or 'List'
		icon = menu_item.get('iconImage') or 'folder'
		menu_name = self._prompt_add_name(name)
		if not menu_name: return
		icon_choice = self._icon_select(default_icon=icon)
		if icon_choice is None: return kodi_utils.notification('Cancelled', 1500)
		menu_item.update({'name': menu_name, 'iconImage': icon_choice, 'full_list': 'false'})
		folders = navigator_cache.get_shortcut_folders()
		if folders:
			items = [{'line1': i[0]} for i in folders]
			kwargs = {'heading': 'Select Shortcut Folder', 'items': json.dumps(items), 'narrow_window': 'true'}
			choice = kodi_utils.select_dialog(folders, **kwargs)
			if choice == None: return kodi_utils.notification('Cancelled', 1500)
			choice_name, list_items = choice
		else:
			kodi_utils.ok_dialog(heading='Shortcut Folders', text='Please make a Shortcut Folder first')
			choice_name = kodi_utils.kodi_dialog().input('')
			if not choice_name: return kodi_utils.notification('Cancelled', 1500)
			self._db_execute('make_new_shortcut_folder', choice_name, list_type='shortcut_folder')
			list_items = []
		if list_items:
			position = self._menu_select(list_items, menu_name, multi_line='true', position_list=True)
			if position == None: return kodi_utils.notification('Cancelled', 1500)
		else: position = 0
		list_items.insert(position, menu_item)
		self._db_execute('set', choice_name, list_items, 'shortcut_folder', refresh=False)

	def _menu_select(self, choice_items, menu_name, heading='', multi_line='false', position_list=False):
		def _builder():
			for item in choice_items:
				item_get = item.get
				line2 = 'Place [B]%s[/B] below [B]%s[/B]' % (menu_name, item_get('name', None) or item_get('list_name') if position_list else '')
				iconImage = item_get('iconImage', None)
				if iconImage: icon = iconImage if iconImage.startswith('http') else kodi_utils.get_icon(item_get('iconImage'))
				else: icon = kodi_utils.get_icon('folder')
				yield {'line1': item_get('name'), 'line2': line2, 'icon':icon}
		list_items = list(_builder())
		if position_list: list_items.insert(0, {'line1': 'Top Position', 'line2': 'Place [B]%s[/B] at Top of List' % menu_name, 'icon': kodi_utils.get_icon('top')})
		index_list = [list_items.index(i) for i in list_items]
		kwargs = {'items': json.dumps(list_items), 'heading': heading, 'multi_line': multi_line}
		return kodi_utils.select_dialog(index_list, **kwargs)

	def _icon_select(self, default_icon=''):
		if default_icon.startswith('http') or 'plugin.video.redlight' in default_icon: return default_icon
		all_icons = kodi_utils.get_all_icons()
		if not all_icons: return default_icon or 'folder'
		if default_icon:
			try:
				all_icons.remove(default_icon)
				all_icons.insert(0, default_icon)
			except: pass
			list_items = [{'line1': i if i != default_icon else '%s (default)' % default_icon, 'icon': kodi_utils.get_icon(i)} for i in all_icons]
		else: list_items = [{'line1': i, 'icon': kodi_utils.get_icon(i)} for i in all_icons]
		kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Icon'}
		return kodi_utils.select_dialog(all_icons, **kwargs)

	def _prompt_add_name(self, current_name):
		"""Name step when adding a menu/shortcut item. Empty/cancel aborts the add."""
		new_name = kodi_utils.kodi_dialog().input('', defaultt=current_name or '')
		if not new_name:
			kodi_utils.notification('Cancelled', 1500)
			return None
		return new_name

	def _get_removed_items(self):
		default_list_items, edited = navigator_cache.get_main_lists(self.active_list)
		current = edited if edited else navigator_cache.without_optional_extras(self.active_list, default_list_items)
		stock_removed = [i for i in (default_list_items or []) if not self._menu_has_item(current, i)
			and i.get('mode') != 'build_simkl_public_calendar' and not i.get('nextep_sort')]
		removed = [i for i in stock_removed if i.get('name') not in {x.get('name') for x in (navigator_cache.optional_menus.get(self.active_list) or [])}]
		for item in navigator_cache.get_opted_optional(self.active_list):
			if not self._menu_has_item(current, item) and not self._menu_has_item(removed, item):
				removed.append(item)
		return removed

	def _same_menu_item(self, a, b):
		return (str(a.get('name')) == str(b.get('name')) and a.get('mode') == b.get('mode')
			and a.get('nextep_sort') == b.get('nextep_sort'))

	def _menu_has_item(self, menu, item):
		return any(self._same_menu_item(item, i) for i in (menu or []))

	def _get_external_name_input(self, current_name):
		new_name = kodi_utils.kodi_dialog().input('', defaultt=current_name)
		if new_name == current_name: return None
		return new_name

	def _remove_active_shortcut_folder(self, main_menu_items_list, folder_name):
		for x in main_menu_items_list:
			try:
				match = [i for i in x[1] if str(i['name']) == str(folder_name)][0]
				new_list = [i for i in x[1] if i != match]
				self._db_execute('set', x[0], new_list, refresh=False)
			except: pass

	def _refresh_menu(self):
		folder = kodi_utils.folder_path()
		if folder and 'plugin.video.redlight' in folder:
			return kodi_utils.container_refresh()
		if self.active_list in navigator_cache.main_menus:
			return kodi_utils.container_update(kodi_utils.build_folder_url({'mode': 'navigator.main', 'action': self.active_list}))
		if self.active_list:
			return kodi_utils.container_update(kodi_utils.build_folder_url({'mode': 'navigator.build_shortcut_folder_contents', 'name': self.active_list}))

	def _db_execute(self, db_action, list_name, list_contents=[], list_type='edited', refresh=True):
		if db_action == 'set': navigator_cache.set_list(list_name, list_type, list_contents)
		elif db_action == 'delete': navigator_cache.delete_list(list_name, list_type)
		elif db_action == 'make_new_shortcut_folder': navigator_cache.set_list(list_name, 'shortcut_folder', list_contents)
		else: return kodi_utils.notification('Failed', 1500)
		kodi_utils.notification('Success', 1500)
		kodi_utils.sleep(500)
		if refresh: self._refresh_menu()

	def _path_browser(self, label='', file='plugin://plugin.video.redlight?mode=navigator.main&full_list=true', thumbnail=''):
		kodi_utils.show_busy_dialog()
		results = kodi_utils.jsonrpc_get_directory(file)
		kodi_utils.hide_busy_dialog()
		list_items, function_items = [], []
		if file != 'plugin://plugin.video.redlight?mode=navigator.main&full_list=true':
			list_items.append({'line1': 'Use [B]%s[/B] As Path' % label, 'icon': thumbnail})
			function_items.append(json.dumps({'label': label, 'file': file, 'thumbnail': thumbnail}))
		list_items.extend([{'line1': '%s >>' % i['label'], 'icon': i['thumbnail']} for i in results])
		function_items.extend([json.dumps({'label': i['label'], 'file': '%s%s' % (i['file'], '&full_list=true') if 'navigator.main' in i['file'] else i['file'],
								'thumbnail': i['thumbnail']}) for i in results])
		kwargs = {'items': json.dumps(list_items)}
		choice = kodi_utils.select_dialog(function_items, **kwargs)
		if choice == None: return None
		choice = json.loads(choice)
		if choice['file'] == file: return choice
		else: return self._path_browser(**choice)

	def _get_menu_item(self, path):
		return dict(parse_qsl(path.replace('plugin://plugin.video.redlight/?','')))

	def _get_icon_var(self, icon_path):
		import os
		try:
			all_icons = kodi_utils.get_all_icons()
			icon_value = unquote(icon_path)
			icon_value = path = os.path.basename(os.path.normpath(icon_value))
			icon_value = icon_value.replace('.png/', '').replace('.png', '')
			icon_var = [i for i in all_icons if i == icon_value][0]
		except: icon_var = 'folder'
		return icon_var
