# -*- coding: utf-8 -*-
import sys
from datetime import datetime
from apis.alldebrid_api import AllDebrid
from modules import kodi_utils
from modules.source_utils import supported_video_extensions
from modules.utils import clean_file_name, normalize
# logger = kodi_utils.logger

extensions = supported_video_extensions()


def _magnet_progress(item):
	if item.get('statusCode') == 4:
		return 100
	try:
		proc = item.get('processingPerc')
		if proc is not None:
			value = float(proc)
			if 0 <= value <= 1:
				return int(value * 100)
			return min(int(value), 99)
	except:
		pass
	try:
		size = float(item.get('size') or 0)
		downloaded = float(item.get('downloaded') or 0)
		if size > 0 and downloaded > 0:
			return min(int(100 * downloaded / size), 99)
	except:
		pass
	return 0


def ad_cloud(folder_id=None):
	if folder_id:
		return browse_ad_cloud(folder_id)
	def _builder():
		for count, item in enumerate(cloud_dict, 1):
			try:
				cm = []
				folder_name, folder_id = item['filename'], item['id']
				clean_folder_name = clean_file_name(normalize(folder_name)).upper()
				display = '%02d | [B]FOLDER[/B] | [I]%s [/I]' % (count, clean_folder_name)
				url_params = {'mode': 'alldebrid.browse_ad_cloud', 'id': folder_id}
				delete_params = {'mode': 'alldebrid.delete', 'id': folder_id}
				cm.append(('[B]Delete Folder[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setPlot(' ')
				yield (url, listitem, True)
			except:
				pass
	icon, fanart = kodi_utils.get_icon('alldebrid'), kodi_utils.get_addon_fanart()
	cloud_dict = []
	try:
		kodi_utils.show_busy_dialog()
		cloud = AllDebrid.user_cloud(fresh=True)
		kodi_utils.hide_busy_dialog()
		cloud_dict = [i for i in (cloud.get('magnets') or []) if i.get('statusCode') == 4]
	except:
		kodi_utils.hide_busy_dialog()
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)


def ad_downloads():
	def _builder():
		for count, item in enumerate(history_items, 1):
			try:
				cm = []
				cm_append = cm.append
				history_type = item.get('history_type')
				progress = item.get('progress', 100)
				name = clean_file_name(normalize(item.get('display_name', 'Unknown'))).upper()
				if history_type == 'magnet':
					type_label = 'MAGNET'
					finished = item.get('statusCode') == 4
					display = '%02d | %d%% | [B]%s[/B] | [I]%s [/I]' % (count, progress, type_label, name)
					delete_params = {'mode': 'alldebrid.delete', 'id': item['id']}
					cm_append(('[B]Delete[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
					if finished:
						url_params = {'mode': 'alldebrid.browse_ad_cloud', 'id': item['id']}
						is_folder = True
					else:
						url_params = {'mode': 'alldebrid.ad_downloads'}
						is_folder = False
				else:
					type_label = 'LINK'
					size = float(int(item.get('size', 0))) / 1073741824
					date_str = datetime.fromtimestamp(item.get('date', 0)).strftime('%Y-%m-%d') if item.get('date') else ''
					display = '%02d | %d%% | %.2f GB | %s | [B]%s[/B] | [I]%s [/I]' % (count, progress, size, date_str, type_label, name)
					url_link = item.get('link_dl') or item.get('link')
					url_params = {'mode': 'playback.video', 'url': url_link, 'obj': 'video'}
					down_file_params = {'mode': 'downloader.runner', 'name': name, 'url': url_link, 'action': 'cloud.alldebrid_direct', 'image': icon}
					cm_append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
					is_folder = False
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				plot = item.get('status') if history_type == 'magnet' else ''
				if isinstance(plot, str) and plot.strip():
					listitem.getVideoInfoTag().setPlot(plot)
				yield (url, listitem, is_folder)
			except:
				pass
	icon, fanart = kodi_utils.get_icon('alldebrid'), kodi_utils.get_addon_fanart()
	history_items, errors = [], []
	kodi_utils.show_busy_dialog()
	AllDebrid.clear_mylist_cache()
	err, magnets = AllDebrid.magnets_list(fresh=True)
	if err:
		errors.append('MAGNET: %s' % err)
	else:
		for magnet in magnets:
			history_items.append({
				**magnet,
				'history_type': 'magnet',
				'display_name': magnet.get('filename', 'Unknown'),
				'progress': _magnet_progress(magnet),
				'sort_date': magnet.get('uploadDate') or magnet.get('completionDate') or 0,
			})
	try:
		result = AllDebrid.history(fresh=True)
		links = (result.get('links') or []) if isinstance(result, dict) else []
		for link in links:
			if link.get('error'):
				continue
			filename = link.get('filename', '')
			if not filename.lower().endswith(tuple(extensions)):
				continue
			history_items.append({
				**link,
				'history_type': 'link',
				'display_name': filename,
				'progress': 100,
				'sort_date': link.get('date') or 0,
			})
	except:
		errors.append('LINK: Unable to load history')
	kodi_utils.hide_busy_dialog()
	history_items.sort(key=lambda k: k.get('sort_date', 0), reverse=True)
	if not history_items:
		if errors:
			kodi_utils.notification('All Debrid: %s' % errors[0], 4000)
		else:
			kodi_utils.notification('All Debrid: No transfers in history', 2500)
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)


def ad_saved_links():
	def _builder():
		for count, item in enumerate(saved_links, 1):
			try:
				cm = []
				cm_append = cm.append
				filename, size = item['filename'], float(int(item['size']))/1073741824
				name = clean_file_name(filename).upper()
				display = '%02d | %.2f GB | [I]%s [/I]' % (count, size, name)
				url_link = item['link']
				url_params = {'mode': 'alldebrid.resolve_ad', 'url': url_link, 'play': 'true'}
				down_file_params = {'mode': 'downloader.runner', 'name': name, 'url': url_link, 'action': 'cloud.alldebrid', 'image': icon}
				cm_append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setPlot(' ')
				yield (url, listitem, False)
			except:
				pass
	icon, fanart = kodi_utils.get_icon('alldebrid'), kodi_utils.get_addon_fanart()
	saved_links = []
	try:
		kodi_utils.show_busy_dialog()
		result = AllDebrid.user_links(fresh=True)
		kodi_utils.hide_busy_dialog()
		saved_links = (result.get('links') or []) if isinstance(result, dict) else []
	except:
		kodi_utils.hide_busy_dialog()
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)


def browse_ad_cloud(folder_id):
	def _builder():
		for count, item in enumerate(links, 1):
			try:
				if not item.get('n', '').lower().endswith(tuple(extensions)):
					continue
				cm = []
				url_link = item['l']
				name = clean_file_name(item['n']).upper()
				size = item['s']
				display_size = float(int(size))/1073741824
				display = '%02d | [B]FILE[/B] | %.2f GB | [I]%s [/I]' % (count, display_size, name)
				url_params = {'mode': 'alldebrid.resolve_ad', 'url': url_link, 'play': 'true'}
				down_file_params = {'mode': 'downloader.runner', 'name': name, 'url': url_link, 'action': 'cloud.alldebrid', 'image': icon}
				url = kodi_utils.build_url(url_params)
				cm.append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setPlot(' ')
				yield (url, listitem, False)
			except:
				pass
	try:
		links = AllDebrid.parse_magnet(transfer_id=folder_id)[1]
	except:
		links = []
	handle = int(sys.argv[1])
	icon, fanart = kodi_utils.get_icon('alldebrid'), kodi_utils.get_addon_fanart()
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)


def resolve_ad(params):
	url = params['url']
	resolved_link = AllDebrid.unrestrict_link(url)
	if params.get('play', 'false') != 'true':
		return resolved_link
	from modules.player import RedLightPlayer
	RedLightPlayer().run(resolved_link, 'video')


def ad_delete(file_id):
	if not kodi_utils.confirm_dialog():
		return
	result = AllDebrid.delete_transfer(file_id)
	if not result:
		return kodi_utils.notification('Error')
	AllDebrid.clear_cache()
	kodi_utils.execute_builtin('Container.Refresh')


def ad_account_info():
	try:
		from modules.service_expiry import append_expiry_lines, fetch_expiry_summary
		kodi_utils.show_busy_dialog()
		account_info = AllDebrid.account_info()['user']
		username = account_info['username']
		email = account_info['email']
		status = 'Premium' if account_info['isPremium'] else 'Not Active'
		body = []
		append = body.append
		append('[B]Username:[/B] %s' % username)
		append('[B]Email:[/B] %s' % email)
		append('[B]Status:[/B] %s' % status)
		append_expiry_lines(body, fetch_expiry_summary('ad'))
		kodi_utils.hide_busy_dialog()
		return kodi_utils.show_text('ALL DEBRID', '\n\n'.join(body), font_size='large')
	except:
		kodi_utils.hide_busy_dialog()
