# -*- coding: utf-8 -*-
import re
import sys
import math
from datetime import datetime
from apis.premiumize_api import Premiumize
from modules.source_utils import supported_video_extensions
from modules.utils import clean_file_name, normalize
from modules import kodi_utils
# logger = kodi_utils.logger

def pm_cloud(folder_id=None, folder_name=None):
	def _builder():
		for count, item in enumerate(cloud_files, 1):
			try:
				cm = []
				cm_append = cm.append
				file_type = item['type']
				name = clean_file_name(item['name']).upper()
				rename_params = {'mode': 'premiumize.rename', 'file_type': file_type, 'id': item['id'], 'name': item['name']}
				delete_params = {'mode': 'premiumize.delete', 'id': item['id']}
				listitem = kodi_utils.make_listitem()
				if file_type == 'folder':
					is_folder = True
					display = '%02d | [B]FOLDER[/B] | [I]%s [/I]' % (count, name)
					url_params = {'mode': 'premiumize.pm_cloud', 'id': item['id'], 'folder_name': normalize(item['name']), 'name': item['name']}
					delete_params['file_type'] = 'folder'
				else:
					is_folder = False
					url_link, size = item['link'], item['size']
					if url_link.startswith('/'): url_link = 'https' + url_link
					display_size = float(int(size))/1073741824
					display = '%02d | [B]FILE[/B] | %.2f GB | [I]%s [/I]' % (count, display_size, name)
					url_params = {'mode': 'playback.video', 'url': url_link, 'obj': 'video'}
					down_file_params = {'mode': 'downloader.runner', 'name': item['name'], 'url': url_link, 'action': 'cloud.premiumize', 'image': icon}
					delete_params['file_type'] = 'item'
					cm_append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
				cm_append(('[B]Rename %s[/B]' % file_type.capitalize(),'RunPlugin(%s)' % kodi_utils.build_url(rename_params)))
				cm_append(('[B]Delete %s[/B]' % file_type.capitalize(),'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				url = kodi_utils.build_url(url_params)
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setPlot(' ')
				yield (url, listitem, is_folder)
			except: pass
	icon, fanart = kodi_utils.get_icon('premiumize'), kodi_utils.get_addon_fanart()
	try:
		cloud_files = Premiumize.user_cloud(folder_id)['content']
		cloud_files = [i for i in cloud_files if ('link' in i and i['link'].lower().endswith(tuple(supported_video_extensions()))) or i['type'] == 'folder']
		cloud_files.sort(key=lambda k: k['name'])
		cloud_files.sort(key=lambda k: k['type'], reverse=True)
	except: cloud_files = []
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)

def pm_transfers():
	def _transfer_progress(status, progress):
		status = str(status or '').lower()
		if status in ('finished', 'seeding'):
			return 100
		try:
			value = float(progress)
			if 0 <= value <= 1:
				return int(value * 100)
			return min(int(value), 99)
		except:
			try:
				return int(re.findall(r'(\d+)', str(progress or ''))[0][:3])
			except:
				return 0

	def _is_folder_transfer(item):
		file_id = item.get('file_id')
		return file_id is None or file_id in ('', 'None')

	def _builder():
		for count, item in enumerate(transfer_files, 1):
			try:
				cm = []
				cm_append = cm.append
				status = str(item.get('status', '')).lower()
				progress = _transfer_progress(status, item.get('progress'))
				name = clean_file_name(item.get('name', 'Unknown')).upper()
				folder_id = item.get('folder_id')
				file_id = item.get('file_id')
				ready = status in ('finished', 'seeding')
				if _is_folder_transfer(item):
					is_folder = bool(ready and folder_id)
					display = '%02d | %d%% | [B]FOLDER[/B] | [I]%s [/I]' % (count, progress, name)
					if is_folder:
						url_params = {'mode': 'premiumize.pm_cloud', 'id': folder_id, 'folder_name': normalize(item.get('name', ''))}
					else:
						url_params = {'mode': 'premiumize.pm_transfers'}
				else:
					is_folder = False
					url_params = {'mode': 'premiumize.pm_transfers'}
					if ready and file_id:
						details = Premiumize.get_item_details(file_id, fresh=True)
						if isinstance(details, dict) and details.get('link'):
							url_link = details['link']
							if url_link.startswith('/'):
								url_link = 'https' + url_link
							size = details.get('size', 0)
							display_size = float(int(size)) / 1073741824
							display = '%02d | %d%% | [B]FILE[/B] | %.2f GB | [I]%s [/I]' % (count, progress, display_size, name)
							url_params = {'mode': 'playback.video', 'url': url_link, 'obj': 'video'}
							down_file_params = {'mode': 'downloader.runner', 'name': item.get('name', ''), 'url': url_link, 'action': 'cloud.premiumize', 'image': icon}
							cm_append(('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params)))
						else:
							display = '%02d | %d%% | [B]FILE[/B] | [I]%s [/I]' % (count, progress, name)
					else:
						display = '%02d | %d%% | [B]FILE[/B] | [I]%s [/I]' % (count, progress, name)
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				if cm:
					listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				plot = item.get('message') or status
				if isinstance(plot, str) and plot.strip():
					listitem.getVideoInfoTag().setPlot(plot)
				yield (url, listitem, is_folder)
			except:
				pass
	icon, fanart = kodi_utils.get_icon('premiumize'), kodi_utils.get_addon_fanart()
	transfer_files = []
	api_error = None
	try:
		kodi_utils.show_busy_dialog()
		result = Premiumize.transfers_list(fresh=True)
		kodi_utils.hide_busy_dialog()
		if not result:
			api_error = 'Unable to load history'
		elif str(result.get('status', '')).lower() != 'success':
			api_error = result.get('message') or 'Unable to load history'
		else:
			transfer_files = result.get('transfers') or []
	except:
		kodi_utils.hide_busy_dialog()
		api_error = 'Unable to load history'
	if api_error:
		return kodi_utils.notification('Premiumize: %s' % api_error, 4000)
	items = list(_builder())
	if not transfer_files:
		kodi_utils.notification('Premiumize: No transfers in history', 2500)
	elif not items:
		kodi_utils.notification('Premiumize: Transfers found but could not be listed', 3500)
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, items)
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)

def pm_rename(file_type, file_id, current_name):
	new_name = kodi_utils.kodi_dialog().input('RedLight', defaultt=current_name)
	if not new_name: return
	result = Premiumize.rename_cache_item(file_type, file_id, new_name)
	if result == 'success':
		Premiumize.clear_cache()
		execute_builtin('Container.Refresh')
	else:
		return kodi_utils.ok_dialog(text='Error')

def pm_delete(file_type, file_id):
	if not kodi_utils.confirm_dialog(): return
	result = Premiumize.delete_object(file_type, file_id)
	if result == 'success':
		Premiumize.clear_cache()
		execute_builtin('Container.Refresh')
	else:
		return kodi_utils.ok_dialog(text='Error')

def pm_account_info():
	try:
		from modules.service_expiry import append_expiry_lines, fetch_expiry_summary
		kodi_utils.show_busy_dialog()
		account_info = Premiumize.account_info()
		customer_id = account_info['customer_id']
		points_used = int(math.floor(float(account_info['space_used']) / 1073741824.0))
		space_used = float(int(account_info['space_used']))/1073741824
		percentage_used = str(round(float(account_info['limit_used']) * 100.0, 1))
		body = []
		append = body.append
		append('[B]Customer ID:[/B] %s' % customer_id)
		append_expiry_lines(body, fetch_expiry_summary('pm'))
		append('[B]Points Used:[/B] %.f' % points_used)
		append('[B]Space Used:[/B] %.2f' % space_used)
		append('[B]Fair Use (Percentage Used):[/B] %s%%' % percentage_used)
		kodi_utils.hide_busy_dialog()
		return kodi_utils.show_text('PREMIUMIZE', '\n\n'.join(body), font_size='large')
	except: kodi_utils.hide_busy_dialog()