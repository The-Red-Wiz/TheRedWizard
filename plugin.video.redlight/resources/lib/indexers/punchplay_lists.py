# -*- coding: utf-8 -*-
import sys
from apis.punchplay_api import punchplay_search_my_lists, punchplay_search_lists
from modules import settings
from modules.kodi_utils import (add_items, set_content, set_category, end_directory, build_url, make_listitem,
	get_icon, get_addon_fanart, set_view_mode, MENU_FOLDER_CONTENT, list_folder_plot, external, folder_path,
	sanitize_folder_url, set_property, build_folder_url)

def _set_punchplay_public_search_exit():
	if external(): return
	current = folder_path()
	if current and 'search_punchplay_public_lists' in current:
		set_property('redlight.exit_params', sanitize_folder_url(current))
	else:
		set_property('redlight.exit_params', build_folder_url({'mode': 'navigator.punchplay_lists'}))

def search_punchplay_public_lists(params):
	"""Open a PunchPlay list by numeric ID or punchplay.tv/lists/{id} URL."""
	def _builder():
		for item in results:
			try:
				list_id, name = item.get('id'), item.get('name') or 'List'
				if list_id in (None, '', 0, '0'): continue
				is_owner = bool(item.get('isOwner') or item.get('isCollaborator'))
				if item.get('isPublic') is False and not is_owner: continue
				user = item.get('ownerUsername') or ''
				count = item.get('itemCount', '?')
				display = '[B]%s[/B] | [I](x%s) - %s[/I]' % (name, count, user)
				if item.get('isDynamicList'):
					display = '[COLOR magenta][I]%s[/I][/COLOR] | [I](x%s) - %s[/I]' % (name, count, user)
				url_params = {
					'mode': 'navigator.punchplay_user_list', 'list_id': list_id, 'list_name': name, 'name': name,
					'iconImage': 'punchplay', 'from_search': 'true', 'key_id': search_title, 'query': search_title
				}
				url = build_url(url_params)
				cm = [('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url}))]
				listitem = make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(list_folder_plot(item.get('description'), user, count, item.get('likeCount')))
				listitem.addContextMenuItems(cm)
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	_set_punchplay_public_search_exit()
	icon, fanart = get_icon('punchplay'), get_addon_fanart()
	search_title = params.get('key_id') or params.get('query') or ''
	try:
		if not settings.punchplay_user_active(): results = []
		else: results = punchplay_search_lists(search_title)
		add_items(handle, list(_builder()))
	except: pass
	set_content(handle, MENU_FOLDER_CONTENT)
	set_category(handle, search_title.capitalize() if search_title else 'Search PunchPlay Lists')
	end_directory(handle)
	set_view_mode('view.main', MENU_FOLDER_CONTENT)

def search_punchplay_lists(params):
	def _builder():
		for item in results:
			try:
				media_ids = item.get('media_ids') or {}
				tmdb_id = media_ids.get('tmdb')
				if not tmdb_id: continue
				title = item.get('title') or 'Unknown'
				status_label = item.get('status_label', '')
				media_kind = item.get('media_kind', 'movies')
				if media_kind == 'anime': display = '%s | [I]%s · Anime[/I]' % (title, status_label)
				else: display = '%s | [I]%s[/I]' % (title, status_label)
				if media_kind == 'movies':
					url = build_url({'mode': 'extras_menu_choice', 'media_type': 'movie', 'tmdb_id': tmdb_id})
				else:
					url = build_url({'mode': 'build_season_list', 'tmdb_id': tmdb_id})
				listitem = make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot('PunchPlay %s' % status_label)
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	icon, fanart = get_icon('punchplay'), get_addon_fanart()
	search_title = params.get('key_id') or params.get('query') or ''
	try:
		if not settings.punchplay_user_active(): results = []
		else: results = punchplay_search_my_lists(search_title)
		add_items(handle, list(_builder()))
	except: pass
	set_content(handle, MENU_FOLDER_CONTENT)
	set_category(handle, search_title.capitalize())
	end_directory(handle)
	set_view_mode('view.main', MENU_FOLDER_CONTENT)
