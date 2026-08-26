# -*- coding: utf-8 -*-
"""Open a service's official Trakt import web page (QR / URL).

Red Light does not run the import — users finish it on the service website.
"""
from modules import kodi_utils
from modules.utils import copy2clip, make_qrcode


def open_official_trakt_import_page(service_name, url, icon=None, close_hint='to sync',
		extra_line=None, after_close=None, fallback_hint=None):
	icon = icon or kodi_utils.addon_icon()
	try: copy2clip(url)
	except: pass
	try: qr_code = make_qrcode(url) or icon
	except: qr_code = icon
	heading = 'Import Trakt to %s' % service_name
	hint = (' %s' % close_hint) if close_hint else ''
	content = (
		'Official %s Trakt import page:[CR][CR][B]%s[/B][CR][CR]'
		'Scan the QR code with your phone, or open the URL in a browser.'
		% (service_name, url))
	if extra_line:
		content = '%s[CR][CR]%s' % (content, extra_line)
	content = '%s[CR][CR]Complete the import on %s, then close this dialog%s.' % (
		content, service_name, hint)
	if not fallback_hint:
		fallback_hint = (
			'When finished, use Force Sync under Meta Accounts > %s if available.' % service_name)
	fallback = (
		'Open this official %s page in a browser:[CR][CR][B]%s[/B][CR][CR]%s'
		% (service_name, url, fallback_hint))
	try:
		progress = kodi_utils.progress_dialog(heading, qr_code)
		progress.update(content, 0)
		while not progress.iscanceled():
			kodi_utils.sleep(500)
		progress.close()
	except:
		kodi_utils.ok_dialog(heading=heading, text=fallback)
	if after_close:
		try: after_close()
		except: pass
	return True
