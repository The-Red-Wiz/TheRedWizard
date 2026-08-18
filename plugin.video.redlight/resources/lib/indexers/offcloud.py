# -*- coding: utf-8 -*-
# Thanks to kodifitzwell for allowing me to borrow his code
import sys
from apis.offcloud_api import Offcloud
from modules import kodi_utils
from modules.source_utils import supported_video_extensions
from modules.utils import clean_file_name, normalize
# logger = kodi_utils.logger

def _oc_status_label(status):
	status = str(status or '').lower()
	if status == 'downloaded':
		return 'DOWNLOADED'
	if status in ('error', 'failed'):
		return 'ERROR'
	if status == 'created':
		return 'QUEUED'
	return (status or 'processing').upper()

def _oc_item_play_link(item):
	url = item.get('url')
	if url: return Offcloud.requote_uri(url)
	server, request_id, file_name = item.get('server'), item.get('requestId', ''), item.get('fileName', '')
	if server and request_id and file_name:
		return Offcloud.requote_uri(Offcloud.build_url(server, request_id, file_name))
	if request_id and not item.get('isDirectory'):
		explore = Offcloud.user_cloud_info(request_id)
		if isinstance(explore, list) and explore:
			return Offcloud.requote_uri(explore[0])
	return ''

def oc_cloud():
	def _builder():
		for count, item in enumerate(folders, 1):
			try:
				cm = []
				cm_append = cm.append
				is_folder = item.get('isDirectory', False)
				request_id, folder_name = item.get('requestId', ''), item.get('fileName', '')
				if not request_id or not folder_name: continue
				delete_params = {'mode': 'offcloud.delete', 'folder_id': request_id}
				if is_folder:
					display = '%02d | [B]FOLDER[/B] | [I]%s [/I]' % (count, clean_file_name(normalize(folder_name)).upper())
					url_params = {'mode': 'offcloud.browse_oc_cloud', 'folder_id': request_id}
					cm_append(('[B]Delete Folder[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				else:
					link = _oc_item_play_link(item)
					if not link: continue
					display = '%02d | [B]File[/B] | [I]%s [/I]' % (count, clean_file_name(normalize(folder_name)).upper())
					url_params = {'mode': 'offcloud.resolve_oc', 'url': link, 'play': 'true'}
					down_file_params = {'mode': 'downloader', 'action': 'cloud.offcloud_direct', 'name': folder_name, 'url': link, 'image': icon}
					cm_append(('[B]Delete File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
					cm.append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				yield (url, listitem, is_folder)
			except Exception:
				pass
	icon, fanart = kodi_utils.get_icon('offcloud'), kodi_utils.get_addon_fanart()
	all_items = []
	try:
		kodi_utils.show_busy_dialog()
		all_items = _oc_cloud_history_items()
	except Exception:
		all_items = []
	finally:
		kodi_utils.hide_busy_dialog()
	folders = [i for i in all_items if str(i.get('status', '')).lower() == 'downloaded']
	handle = int(sys.argv[1])
	built = list(_builder())
	kodi_utils.add_items(handle, built)
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)
	if not built and all_items:
		kodi_utils.notification('Offcloud: Nothing ready in Cloud Storage yet. Open History for queued or processing items.', 5500)
	elif not built and not all_items:
		kodi_utils.notification('Offcloud: Cloud Storage is empty', 4500)

def _oc_cloud_history_items():
	try:
		return Offcloud.user_cloud_check() or []
	except Exception:
		return []

def oc_history():
	def _builder():
		for count, item in enumerate(history_items, 1):
			try:
				cm = []
				cm_append = cm.append
				status = str(item.get('status', '')).lower()
				status_label = _oc_status_label(status)
				folder_name = clean_file_name(normalize(item.get('fileName', ''))).upper()
				display = '%02d | [B]%s[/B] | [I]%s [/I]' % (count, status_label, folder_name)
				request_id = item.get('requestId', '')
				delete_params = {'mode': 'offcloud.delete', 'folder_id': request_id}
				cm_append(('[B]Delete[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				if status == 'downloaded':
					is_folder = item.get('isDirectory', False)
					if is_folder:
						url_params = {'mode': 'offcloud.browse_oc_cloud', 'folder_id': request_id}
					else:
						link = _oc_item_play_link(item)
						url_params = {'mode': 'offcloud.resolve_oc', 'url': link, 'play': 'true'} if link else {'mode': 'offcloud.oc_history'}
						is_folder = False
				else:
					url_params = {'mode': 'offcloud.oc_history'}
					is_folder = False
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				plot = item.get('message') or item.get('detail') or status_label
				if isinstance(plot, str) and plot.strip():
					listitem.getVideoInfoTag().setPlot(plot)
				yield (url, listitem, is_folder)
			except Exception:
				pass
	icon, fanart = kodi_utils.get_icon('offcloud'), kodi_utils.get_addon_fanart()
	history_items = []
	try:
		kodi_utils.show_busy_dialog()
		history_items = _oc_cloud_history_items()
	except Exception:
		history_items = []
	finally:
		kodi_utils.hide_busy_dialog()
	handle = int(sys.argv[1])
	built = list(_builder())
	kodi_utils.add_items(handle, built)
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)
	if not built and not history_items:
		kodi_utils.notification('Offcloud: No history items (or authorisation expired — re-link in Torrent Sources)', 5500)

def browse_oc_cloud(folder_id):
	def _builder():
		for count, item in enumerate(video_files, 1):
			try:
				cm = []
				name = item.split('/')[-1]
				name = clean_file_name(name).upper()
				link = Offcloud.requote_uri(item)
				display = '%02d | [B]FILE[/B] | [I]%s [/I]' % (count, name)
				url_params = {'mode': 'offcloud.resolve_oc', 'url': link, 'play': 'true'}
				url = kodi_utils.build_url(url_params)
				down_file_params = {'mode': 'downloader', 'action': 'cloud.offcloud_direct', 'name': name, 'url': link, 'image': icon}
				cm.append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				listitem.getVideoInfoTag().setPlot(' ')
				yield (url, listitem, False)
			except Exception:
				pass
	icon, fanart = kodi_utils.get_icon('offcloud'), kodi_utils.get_addon_fanart()
	torrent_files = Offcloud.user_cloud_info(folder_id)
	video_files = [i for i in (torrent_files or []) if i.lower().endswith(tuple(supported_video_extensions()))]
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)

def oc_delete(folder_id):
	if not kodi_utils.confirm_dialog(): return
	result = Offcloud.delete_torrent(folder_id)
	if not result or 'success' not in result: return kodi_utils.notification('Error')
	Offcloud.clear_cache()
	kodi_utils.execute_builtin('Container.Refresh')

def resolve_oc(params):
	url = params['url']
	if params.get('play', 'false') != 'true': return url
	from modules.player import RedLightPlayer
	RedLightPlayer().run(url, 'video')

def oc_account_info():
	try:
		kodi_utils.show_busy_dialog()
		account_info = Offcloud.account_info() or {}
		kodi_utils.hide_busy_dialog()
		if not account_info or account_info.get('error'):
			err = account_info.get('error') if isinstance(account_info.get('error'), str) else 'Unable to load Offcloud account info'
			return kodi_utils.ok_dialog(text='Offcloud: %s' % err)
		body = []
		append = body.append
		append('[B]Email[/B]: %s' % account_info.get('email', ''))
		append('[B]User ID[/B]: %s' % account_info.get('user_id') or account_info.get('userId', ''))
		from modules.service_expiry import append_expiry_lines, fetch_expiry_summary
		is_premium = account_info.get('is_premium') if 'is_premium' in account_info else account_info.get('isPremium', '')
		append('[B]Premium[/B]: %s' % is_premium)
		append_expiry_lines(body, fetch_expiry_summary('oc'))
		if 'can_download' in account_info:
			append('[B]Can Download[/B]: %s' % account_info.get('can_download'))
		cloud_limit = (account_info.get('limits') or {}).get('cloud', 0) or 0
		try: cloud_limit = '{:,}'.format(int(cloud_limit))
		except Exception: cloud_limit = str(cloud_limit)
		append('[B]Cloud Limit[/B]: %s' % cloud_limit)
		append('[I]Can Download and Cloud Limit are set by your Offcloud plan (offcloud.com), not in Red Light.[/I]')
		return kodi_utils.show_text('OFFCLOUD', '\n\n'.join(body), font_size='large')
	except Exception:
		kodi_utils.hide_busy_dialog()
		return kodi_utils.ok_dialog(text='Offcloud: Unable to load account info')
