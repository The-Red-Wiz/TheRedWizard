# -*- coding: utf-8 -*-
"""
NZB Indexers browser (Newznab).

Search configured NZB indexers (Tools > Settings > Direct Sources > NZB Indexers)
and act on results: send to TorBox Pro usenet (streams from TorBox Cloud once
downloaded — TorBox Pro required) or save the .nzb file for an external client (SABnzbd, NZBGet).
"""
import os
import sys
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import unquote
from modules import kodi_utils
from modules.utils import clean_file_name
# logger = kodi_utils.logger

def _age_days(pub_date):
	try:
		published = parsedate_to_datetime(pub_date)
		if published.tzinfo: published = published.astimezone(timezone.utc).replace(tzinfo=None)
		return max((datetime.utcnow() - published).days, 0)
	except: return None

def search_nzb(params):
	from apis.nzb_api import search_all
	handle = int(sys.argv[1])
	key_id = params.get('key_id') or params.get('query') or ''
	search_name = clean_file_name(unquote(key_id))
	try:
		files = search_all(search_name)
		nzb_file_browser(files, handle)
	except: pass
	kodi_utils.set_content(handle, kodi_utils.PREMIUM_FILES_CONTENT)
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.premium', kodi_utils.PREMIUM_FILES_CONTENT)

def nzb_file_browser(files, handle):
	def _builder():
		for count, item in enumerate(files, 1):
			try:
				item_get = item.get
				name = clean_file_name(item_get('name', 'Unknown')).upper()
				link = item_get('link', '')
				size_gb = round(float(item_get('size', 0) or 0) / 1073741824.0, 2)
				indexer = item_get('indexer', 'NZB')
				display = '%02d | [B]NZB[/B] | [B]%.2fGB[/B] | [B]%s[/B] | [I]%s[/I]' % (count, size_gb, indexer, name)
				plot_lines = []
				age = _age_days(item_get('age', ''))
				if age is not None: plot_lines.append('[B]Age:[/B] %s day%s' % (age, '' if age == 1 else 's'))
				if item_get('group'): plot_lines.append('[B]Group:[/B] %s' % item_get('group'))
				if item_get('grabs'): plot_lines.append('[B]Grabs:[/B] %s' % item_get('grabs'))
				plot_lines.append('[B]Indexer:[/B] %s' % indexer)
				action_params = {'mode': 'nzb.nzb_action', 'name': name, 'url': link, 'isFolder': 'false'}
				url = kodi_utils.build_url(action_params)
				cm = [('[B]Send to TorBox Pro[/B]', 'RunPlugin(%s)' % kodi_utils.build_url({'mode': 'nzb.send_to_torbox', 'name': name, 'url': link})),
					('[B]Download NZB File[/B]', 'RunPlugin(%s)' % kodi_utils.build_url({'mode': 'nzb.download_nzb', 'name': name, 'url': link}))]
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				kodi_utils.set_list_item_art(listitem, icon, fanart=fanart)
				info_tag = listitem.getVideoInfoTag()
				info_tag.setPlot('\n'.join(plot_lines) or ' ')
				yield (url, listitem, False)
			except: pass
	icon = kodi_utils.get_icon('search')
	fanart = kodi_utils.get_addon_fanart()
	kodi_utils.add_items(handle, list(_builder()))

def nzb_action(params):
	"""Click handler for an NZB result - choose what to do with it."""
	from modules.settings import authorized_debrid_check
	choices = []
	if authorized_debrid_check('tb'): choices.append(('Send to TorBox Pro (stream from Cloud when ready)', 'torbox'))
	choices.append(('Download NZB File', 'download'))
	list_items = [{'line1': item[0]} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': 'NZB Result', 'narrow_window': 'true'}
	choice = kodi_utils.select_dialog([item[1] for item in choices], **kwargs)
	if choice == 'torbox': return send_to_torbox(params)
	if choice == 'download': return download_nzb(params)

def send_to_torbox(params):
	from apis.torbox_api import TorBoxAPI
	name, link = params.get('name', ''), params.get('url', '')
	if not link: return kodi_utils.notification('No NZB link found', 3500)
	kodi_utils.show_busy_dialog()
	try: result = TorBoxAPI().add_nzb(link, name)
	except: result = None
	kodi_utils.hide_busy_dialog()
	if result and result.get('success'):
		detail = (result.get('detail') or 'Sent to TorBox Pro usenet queue').rstrip('.')
		kodi_utils.notification('TorBox: %s' % detail, 5000, kodi_utils.get_icon('torbox'))
	else:
		error = (result or {}).get('detail') or (result or {}).get('error') or 'Send failed. A TorBox Pro account (usenet) is required'
		kodi_utils.ok_dialog(heading='TorBox', text='NZB could not be added:\n%s' % error)

def download_nzb(params):
	from modules.settings import download_directory
	from modules.kodi_utils import make_session
	name, link = params.get('name', ''), params.get('url', '')
	if not link: return kodi_utils.notification('No NZB link found', 3500)
	directory = download_directory('premium')
	if not directory:
		return kodi_utils.ok_dialog(heading='NZB Download', text='Please set a Premium Files download location in Tools > Settings > Downloads first')
	filename = ''.join(c for c in (name or 'download') if c.isalnum() or c in ' ._-').strip() or 'download'
	if not filename.lower().endswith('.nzb'): filename += '.nzb'
	kodi_utils.show_busy_dialog()
	try:
		response = make_session('https://').get(link, timeout=30, allow_redirects=True)
		content = response.content if response.status_code == 200 else None
	except: content = None
	if not content:
		kodi_utils.hide_busy_dialog()
		return kodi_utils.ok_dialog(heading='NZB Download', text='Could not fetch the NZB file from the indexer')
	try:
		import xbmcvfs
		final_path = os.path.join(directory, filename)
		with xbmcvfs.File(final_path, 'w') as f: f.write(bytearray(content))
		kodi_utils.hide_busy_dialog()
		kodi_utils.notification('NZB saved: %s' % filename, 5000)
	except:
		kodi_utils.hide_busy_dialog()
		kodi_utils.ok_dialog(heading='NZB Download', text='Could not write the NZB file to:\n%s' % directory)

def test_connection(params):
	from apis.nzb_api import NzbIndexerAPI
	slot = int(params.get('slot', 1))
	api = NzbIndexerAPI(slot)
	heading = api.label if api.label else 'NZB Indexer %d' % slot
	if not api.is_configured():
		return kodi_utils.ok_dialog(heading=heading, text='Please enter the URL and API key for this indexer in Tools > Settings > Direct Sources > NZB Indexers')
	kodi_utils.show_busy_dialog()
	result = api.capabilities()
	kodi_utils.hide_busy_dialog()
	if not result or 'error' in result:
		error = (result or {}).get('error', 'No response')
		return kodi_utils.ok_dialog(heading=heading, text='Connection failed:\n%s' % error)
	server = result.get('server') or {}
	if isinstance(server, dict): server = server.get('@attributes', server)
	title = server.get('title') or (result.get('channel') or {}).get('title') or 'Indexer'
	kodi_utils.ok_dialog(heading=heading, text='[B]%s[/B] connected successfully' % title)
