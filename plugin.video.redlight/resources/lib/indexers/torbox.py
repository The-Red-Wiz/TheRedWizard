import sys
from apis.torbox_api import TorBox
from modules.source_utils import supported_video_extensions
from modules.utils import clean_file_name, normalize
from modules import kodi_utils
# from modules.kodi_utils import logger


def _api_error_text(result, fallback='Error'):
	if not isinstance(result, dict): return fallback
	# TorBox returns: { success, error, detail, data }
	err = result.get('error') or result.get('detail') or fallback
	if isinstance(err, (list, dict)): err = str(err)
	return str(err)


def tb_cloud():
	def _builder():
		for count, item in enumerate(folders, 1):
			try:
				cm = []
				cm_append = cm.append
				media_type = item['media_type']
				folder_id = item.get('id')
				if folder_id is None:
					continue
				label_type = {'torrent': 'TORRENT', 'usenet': 'USENET', 'webdl': 'WEB DL'}.get(media_type, 'FOLDER')
				airlocked = TorBox.item_is_airlocked(item)
				lock_tag = ' | [B]AIRLOCK[/B]' if airlocked else ''
				display = '%02d | [B]%s[/B]%s | [I]%s [/I]' % (count, label_type, lock_tag, clean_file_name(normalize(item.get('name') or '')).upper())
				url_params = {'mode': 'torbox.browse_tb_cloud', 'folder_id': folder_id, 'media_type': media_type}
				airlock_params = {'mode': 'torbox.airlock', 'folder_id': folder_id, 'media_type': media_type}
				delete_params = {'mode': 'torbox.delete', 'folder_id': folder_id, 'media_type': media_type}
				cm_append(('[B]Remove from Airlock[/B]' if airlocked else '[B]Add to Airlock[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(airlock_params)))
				cm_append(('[B]Delete Folder[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				listitem.getVideoInfoTag().setPlot(' ')
				yield (url, listitem, True)
			except Exception:
				pass
	icon, fanart = kodi_utils.get_icon('torbox'), kodi_utils.get_addon_fanart()
	handle = int(sys.argv[1])
	try:
		# Always refresh so Airlock labels / CM options match live TorBox status.
		kodi_utils.show_busy_dialog()
		data = TorBox.load_ui_cloud_folders(refresh=True)
		folders, errors = data['folders'], data['errors']
		if errors:
			msg = 'TorBox: %s' % errors[0]
			if folders:
				msg += ' (partial list)'
			kodi_utils.notification(msg, 4000)
		folders.sort(key=lambda k: str(k.get('updated_at') or ''), reverse=True)
		kodi_utils.add_items(handle, list(_builder()))
		kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
		kodi_utils.end_directory(handle, cacheToDisc=False)
		kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)
	except Exception as e:
		kodi_utils.notification('TorBox: %s' % str(e), 4000)
		kodi_utils.end_directory(handle)
	finally:
		kodi_utils.hide_busy_dialog()


def tb_history():
	def _progress(item):
		if item.get('download_finished'):
			return 100
		try:
			value = float(item.get('progress', 0))
			if 0 <= value <= 1:
				return int(value * 100)
			return min(int(value), 100)
		except:
			return 0

	def _builder():
		for count, item in enumerate(history_items, 1):
			try:
				cm = []
				cm_append = cm.append
				media_type = item['media_type']
				type_label = item['type_label']
				name = clean_file_name(normalize(item.get('name', 'Unknown'))).upper()
				progress = _progress(item)
				finished = bool(item.get('download_finished'))
				airlocked = TorBox.item_is_airlocked(item)
				lock_tag = ' | [B]AIRLOCK[/B]' if airlocked else ''
				display = '%02d | %d%% | [B]%s[/B]%s | [I]%s [/I]' % (count, progress, type_label, lock_tag, name)
				airlock_params = {'mode': 'torbox.airlock', 'folder_id': item['id'], 'media_type': media_type}
				delete_params = {'mode': 'torbox.delete', 'folder_id': item['id'], 'media_type': media_type}
				cm_append(('[B]Remove from Airlock[/B]' if airlocked else '[B]Add to Airlock[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(airlock_params)))
				cm_append(('[B]Delete[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(delete_params)))
				if finished:
					url_params = {'mode': 'torbox.browse_tb_cloud', 'folder_id': item['id'], 'media_type': media_type}
					is_folder = True
				else:
					url_params = {'mode': 'torbox.tb_history'}
					is_folder = False
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				plot = item.get('status') or ('Ready' if finished else 'In progress')
				if isinstance(plot, str) and plot.strip():
					listitem.getVideoInfoTag().setPlot(plot)
				yield (url, listitem, is_folder)
			except Exception:
				pass
	icon, fanart = kodi_utils.get_icon('torbox'), kodi_utils.get_addon_fanart()
	history_items, errors = [], []
	kodi_utils.show_busy_dialog()
	for media_type, type_label in (('torrent', 'TORRENT'), ('usenet', 'USENET'), ('webdl', 'WEB DL')):
		err, items = TorBox.mylist_items(media_type, fresh=True)
		if err:
			errors.append('%s: %s' % (type_label, err))
		else:
			for item in items:
				history_items.append({**item, 'media_type': media_type, 'type_label': type_label})
	kodi_utils.hide_busy_dialog()
	history_items.sort(key=lambda k: str(k.get('updated_at') or ''), reverse=True)
	if not history_items:
		if errors:
			kodi_utils.notification('TorBox: %s' % errors[0], 4000)
		else:
			kodi_utils.notification('TorBox: No transfers in history', 2500)
	handle = int(sys.argv[1])
	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)


def browse_tb_cloud(folder_id, media_type):
	'''Match Gears/Umbrella: user_cloud_info + short_name filter + item id.'''
	icon, fanart = kodi_utils.get_icon('torbox'), kodi_utils.get_addon_fanart()
	handle = int(sys.argv[1])
	if media_type == 'torrent':
		files = TorBox.user_cloud_info(folder_id)
	elif media_type == 'webdl':
		files = TorBox.user_cloud_info_webdl(folder_id)
	else:
		files = TorBox.user_cloud_info_usenet(folder_id)
	if not files or not files.get('success'):
		kodi_utils.notification('TorBox: %s' % _api_error_text(files, 'Failed to load folder'))
		kodi_utils.end_directory(handle)
		return
	data = files.get('data')
	if isinstance(data, list):
		data = data[0] if data else {}
	if not isinstance(data, dict):
		data = {}
	extensions = tuple(supported_video_extensions())
	video_files = [{**i, 'media_type': media_type} for i in (data.get('files') or []) if (i.get('short_name') or '').lower().endswith(extensions)]
	if not video_files:
		kodi_utils.notification('TorBox: No playable video files in this folder', 4000)

	def _builder():
		for count, item in enumerate(video_files, 1):
			try:
				short_name = item.get('short_name') or ''
				file_id = item.get('id')
				if not short_name or file_id is None:
					continue
				name = clean_file_name(short_name).upper()
				size_gb = float(int(item.get('size') or 0)) / 1073741824
				display = '%02d | [B]FILE[/B] | %.2f GB | [I]%s [/I]' % (count, size_gb, name)
				url_link = '%d,%d' % (int(folder_id), int(file_id))
				url_params = {
					'mode': 'torbox.resolve_tb', 'play': 'true', 'url': url_link,
					'media_type': media_type, 'filename': short_name,
				}
				down_file_params = {'mode': 'downloader.runner', 'name': name, 'url': url_link, 'media_type': media_type, 'action': 'cloud.torbox', 'image': icon}
				cm = [('[B]Download File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url(down_file_params))]
				url = kodi_utils.build_url(url_params)
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setMediaType('video')
				info_tag.setTitle(short_name)
				info_tag.setFilenameAndPath(short_name)
				info_tag.setPlot(' ')
				yield (url, listitem, False)
			except Exception:
				pass

	kodi_utils.add_items(handle, list(_builder()))
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)


def tb_delete(folder_id, media_type):
	if not kodi_utils.confirm_dialog(): return
	if media_type == 'torrent': result = TorBox.delete_torrent(folder_id)
	elif media_type == 'webdl': result = TorBox.delete_webdl(folder_id)
	else: result = TorBox.delete_usenet(folder_id)
	if not result or not result.get('success'):
		return kodi_utils.notification('TorBox: %s' % _api_error_text(result, 'Delete failed'), 4000)
	TorBox.clear_cache()
	kodi_utils.notification('TorBox: Deleted', 2500)
	kodi_utils.execute_builtin('Container.Refresh')


def tb_airlock(folder_id, media_type, airlocked=None):
	# Re-check TorBox live so Add/Remove matches current Airlock state, not a stale list row.
	kodi_utils.show_busy_dialog()
	lock, result = None, None
	try:
		current = TorBox.get_airlocked_status(media_type, folder_id)
		if current is None:
			return kodi_utils.notification('TorBox: Unable to check Airlock status', 4000)
		lock = not current
		result = TorBox.set_airlocked(media_type, folder_id, lock)
	finally:
		kodi_utils.hide_busy_dialog()
	if not result or not result.get('success'):
		return kodi_utils.notification('TorBox: %s' % _api_error_text(result, 'Add to Airlock failed' if lock else 'Remove from Airlock failed'), 4000)
	TorBox.clear_cache()
	kodi_utils.notification('TorBox: Added to Airlock' if lock else 'TorBox: Removed from Airlock', 2500)
	kodi_utils.execute_builtin('Container.Refresh')


def _tb_mime_type(filename):
	ext = ('.' + (filename or '').rsplit('.', 1)[-1].lower()) if '.' in (filename or '') else ''
	return {
		'.mp4': 'video/mp4', '.m4v': 'video/mp4', '.mkv': 'video/x-matroska',
		'.avi': 'video/x-msvideo', '.mov': 'video/quicktime', '.webm': 'video/webm',
		'.m2ts': 'video/mp2t', '.mts': 'video/mp2t', '.ts': 'video/mp2t',
		'.mpg': 'video/mpeg', '.mpeg': 'video/mpeg',
	}.get(ext, 'video/mp4')


def _tb_play_cloud(resolved_link, filename=''):
	'''Match Gears: raw CDN URL, no proxy, no pipe headers.'''
	kodi_utils.hide_busy_dialog()
	try:
		if filename:
			kodi_utils.set_property('redlight.tb.play_mime', _tb_mime_type(filename))
			kodi_utils.set_property('redlight.tb.play_filename', filename)
		from modules.player import RedLightPlayer
		RedLightPlayer().run(resolved_link, 'video')
	finally:
		kodi_utils.clear_property('redlight.tb.play_mime')
		kodi_utils.clear_property('redlight.tb.play_filename')
	return None


def resolve_tb(params):
	file_id, media_type = params.get('url'), params.get('media_type') or 'torrent'
	filename = params.get('filename') or ''
	if not file_id:
		kodi_utils.notification('TorBox: Missing file reference', 4000)
		return None
	kodi_utils.show_busy_dialog()
	try:
		if media_type == 'torrent':
			resolved_link = TorBox.unrestrict_link(file_id)
		elif media_type == 'webdl':
			resolved_link = TorBox.unrestrict_webdl(file_id)
		else:
			resolved_link = TorBox.unrestrict_usenet(file_id)
		resolved_link = TorBox.coerce_play_url(resolved_link) or resolved_link
	finally:
		kodi_utils.hide_busy_dialog()
	if not resolved_link:
		kodi_utils.ok_dialog(heading='TorBox', text='Unable to resolve this cloud link. It may be expired or no longer available.')
		return None
	if params.get('play', 'false') != 'true':
		return resolved_link
	return _tb_play_cloud(resolved_link, filename)


def tb_send_webdl():
	url = kodi_utils.kodi_dialog().input('Paste URL to send to TorBox WebDL:').strip()
	if not url: return
	if not (url.startswith('http://') or url.startswith('https://') or url.startswith('magnet:')):
		return kodi_utils.ok_dialog(text='Invalid URL. Must start with http://, https:// or magnet:')
	kodi_utils.show_busy_dialog()
	try:
		if url.startswith('magnet:'):
			result = TorBox.add_magnet(url)
			kind = 'Torrent'
		else:
			result = TorBox.add_webdl(url)
			kind = 'WebDL'
	except Exception:
		result, kind = None, '?'
	kodi_utils.hide_busy_dialog()
	if result and result.get('success'):
		TorBox.clear_cache()
		detail = result.get('detail') or 'Submitted'
		kodi_utils.notification('TorBox %s: %s' % (kind, detail), 4000)
		kodi_utils.execute_builtin('Container.Refresh')
	else:
		kodi_utils.ok_dialog(text='TorBox: %s' % _api_error_text(result, 'Failed to submit to TorBox'))


def tb_account_info():
	try:
		kodi_utils.show_busy_dialog()
		plans = {0: 'Free plan', 1: 'Essential plan', 2: 'Pro plan', 3: 'Standard plan'}
		account_info = TorBox.account_info()
		if not account_info or not account_info.get('success'):
			kodi_utils.hide_busy_dialog()
			return kodi_utils.ok_dialog(text='TorBox: %s' % _api_error_text(account_info, 'Unable to load account info'))
		account_info = account_info['data']
		body = []
		append = body.append
		append('[B]Email[/B]: %s' % account_info.get('email', ''))
		append('[B]Customer[/B]: %s' % account_info.get('customer', ''))
		from modules.service_expiry import append_expiry_lines, fetch_expiry_summary
		append('[B]Plan[/B]: %s' % plans.get(account_info.get('plan'), 'Unknown'))
		append_expiry_lines(body, fetch_expiry_summary('tb'))
		append('[B]Downloaded[/B]: {:,}'.format(account_info.get('total_downloaded', 0)))
		kodi_utils.hide_busy_dialog()
		return kodi_utils.show_text('TorBox'.upper(), '\n\n'.join(body), font_size='large')
	except Exception:
		kodi_utils.hide_busy_dialog()
