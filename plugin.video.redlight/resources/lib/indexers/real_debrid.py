# -*- coding: utf-8 -*-
import sys
from datetime import datetime
from modules.utils import datetime_workaround
from apis.real_debrid_api import RealDebrid
from modules import kodi_utils
from modules.source_utils import supported_video_extensions
from modules.utils import clean_file_name, normalize, jsondate_to_datetime
logger = kodi_utils.logger

def rd_cloud():
	def _builder():
		for count, item in enumerate(cloud_files, 1):
			try:
				cm = []
				cm_append = cm.append
				folder_name, folder_id = item['filename'], item['id']
				clean_folder_name = clean_file_name(normalize(folder_name)).upper()
				display = '%02d | [B]FOLDER[/B] | [I]%s [/I]' % (count, clean_folder_name)
				url_params = {'mode': 'real_debrid.browse_rd_cloud', 'id': folder_id}
				delete_params = {'mode': 'real_debrid.delete', 'id': folder_id, 'cache_type': 'torrent'}
				cm_append(('[B]Delete Folder[/B]','RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setPlot(' ')
				yield (url, listitem, True)
			except: pass
	try:
		cloud_files = RealDebrid.user_cloud()
		cloud_files = [i for i in cloud_files if i['progress'] == 100 and i['status'] == 'downloaded']
		logger('cloud_files', cloud_files)
	except: cloud_files = []
	icon, fanart = kodi_utils.get_icon('realdebrid'), kodi_utils.get_addon_fanart()
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)

def rd_downloads():
	def _builder():
		for count, item in enumerate(downloads, 1):
			try:
				cm = []
				cm_append = cm.append
				datetime_object = jsondate_to_datetime(item['generated'], '%Y-%m-%dT%H:%M:%S.%fZ', remove_time=True)
				filename, size = item['filename'], float(int(item['filesize']))/1073741824
				name = clean_file_name(filename).upper()
				display = '%02d | %.2f GB | %s  | [I]%s [/I]' % (count, size, datetime_object, name)
				url_link = item['download']
				url_params = {'mode': 'playback.video', 'url': url_link, 'obj': 'video'}
				down_file_params = {'mode': 'downloader.runner', 'name': name, 'url': url_link, 'action': 'cloud.realdebrid_direct', 'image': icon}
				delete_params = {'mode': 'real_debrid.delete', 'id': item['id'], 'cache_type': 'download'}
				cm_append(('[B]Download File[/B]','RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				cm_append(('[B]Delete File[/B]','RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setPlot(' ')
				yield (url, listitem, True)
			except: pass
	icon, fanart = kodi_utils.get_icon('realdebrid'), kodi_utils.get_addon_fanart()
	downloads = []
	try:
		kodi_utils.show_busy_dialog()
		downloads = RealDebrid.downloads(fresh=True)
		kodi_utils.hide_busy_dialog()
		if not isinstance(downloads, list):
			downloads = []
		downloads = [i for i in downloads if i['download'].lower().endswith(tuple(supported_video_extensions()))]
	except:
		kodi_utils.hide_busy_dialog()
		downloads = []
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)

def browse_rd_cloud(folder_id):
	def _builder():
		for count, item in enumerate(pack_info, 1):
			try:
				cm = []
				name, url_link, size = item['path'], item['url_link'], float(int(item['bytes']))/1073741824
				if name.startswith('/'): name = name.split('/')[-1]
				name = clean_file_name(name).upper()
				if url_link.startswith('/'): url_link = 'http' + url_link
				display = '%02d | [B]FILE[/B] | %.2f GB | [I]%s [/I]' % (count, size, name)
				url_params = {'mode': 'real_debrid.resolve_rd', 'url': url_link, 'play': 'true'}
				url = kodi_utils.build_url(url_params)
				down_file_params = {'mode': 'downloader.runner', 'name': name, 'url': url_link, 'action': 'cloud.realdebrid', 'image': icon}
				cm.append(('[B]Download File[/B]','RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setPlot(' ')
				yield (url, listitem, False)
			except: pass
	icon, fanart = kodi_utils.get_icon('realdebrid'), kodi_utils.get_addon_fanart()
	handle = int(sys.argv[1])
	cloud_files = RealDebrid.user_cloud_info(folder_id)
	c_files = cloud_files['files']
	files = [i for i in c_files if i['selected'] == 1 and i['path'].lower().endswith(tuple(supported_video_extensions()))]
	file_info = [dict(i, **{'url_link': cloud_files['links'][idx]}) for idx, i in enumerate(files)]
	pack_info = sorted(file_info, key=lambda k: k['path'])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)

def rd_delete(file_id, cache_type):
	if not kodi_utils.confirm_dialog(): return
	if cache_type == 'torrent': result = RealDebrid.delete_torrent(file_id)
	else: result = RealDebrid.delete_download(file_id) # cache_type: 'download'
	if result.status_code in (401, 403, 404): return kodi_utils.notification('Error')
	RealDebrid.clear_cache()
	kodi_utils.execute_builtin('Container.Refresh')

def resolve_rd(params):
	url = params['url']
	resolved_link = RealDebrid.unrestrict_link(url)
	if params.get('play', 'false') != 'true' : return resolved_link
	from modules.player import RedLightPlayer
	RedLightPlayer().run(resolved_link, 'video')

def rd_account_info():
	try:
		from modules.service_expiry import append_expiry_lines, fetch_expiry_summary
		kodi_utils.show_busy_dialog()
		account_info = RealDebrid.account_info()
		body = []
		append = body.append
		append('[B]Account:[/B] %s' % account_info['email'])
		append('[B]Username:[/B] %s' % account_info['username'])
		append('[B]Status:[/B] %s' % account_info['type'].capitalize())
		append_expiry_lines(body, fetch_expiry_summary('rd'))
		append('[B]Fidelity Points:[/B] %s' % account_info['points'])
		kodi_utils.hide_busy_dialog()
		return kodi_utils.show_text('REAL DEBRID', '\n\n'.join(body), font_size='large')
	except: kodi_utils.hide_busy_dialog()
