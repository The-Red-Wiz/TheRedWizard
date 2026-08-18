# -*- coding: utf-8 -*-
from modules.kodi_utils import addon_fanart, get_icon, get_visibility, set_property, clear_property
from windows.base_window import BaseDialog

PROP_HANDOFF_VISIBLE = 'redlight.nextep_handoff.visible'

class NextepHandoffCover(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.meta = kwargs.get('meta') or {}
		self._set_cover_properties()

	def _set_cover_properties(self):
		meta_get = self.meta.get
		empty_poster = get_icon('box_office')
		fanart = meta_get('fanart') or addon_fanart()
		poster = meta_get('poster') or empty_poster
		title = meta_get('title') or ''
		clearlogo = meta_get('clearlogo') or ''
		try:
			season, episode = int(meta_get('season') or 0), int(meta_get('episode') or 0)
		except Exception:
			season, episode = 0, 0
		ep_name = (meta_get('ep_name') or '').strip()
		if season and episode and ep_name:
			episode_line = 'S%02dE%02d - %s' % (season, episode, ep_name)
		elif season and episode:
			episode_line = 'S%02dE%02d' % (season, episode)
		else:
			episode_line = ''
		self.setProperty('fanart', fanart)
		self.setProperty('poster', poster)
		self.setProperty('title', title)
		self.setProperty('clearlogo', clearlogo)
		self.setProperty('episode_line', episode_line)

	def onInit(self):
		set_property(PROP_HANDOFF_VISIBLE, 'true')

	def run(self):
		# Non-modal: results / resolve doModal on top without closing this cover.
		self.show()
		set_property(PROP_HANDOFF_VISIBLE, 'true')

	def onAction(self, action):
		if action not in self.closing_actions:
			return
		# Results owns Back once it is up. Cover-only Back cancels the handoff.
		if get_visibility('Window.IsVisible(sources_results.xml)') or get_visibility('Window.IsVisible(sources_playback.xml)'):
			return
		# Still playing: this overlay should not be up. Dismiss it; do not cancel.
		if get_visibility('Window.IsActive(fullscreenvideo)'):
			try:
				from modules.sources import dismiss_nextep_handoff_cover_keep_armed
				dismiss_nextep_handoff_cover_keep_armed()
			except Exception:
				self.close()
			return
		try:
			from modules.sources import mark_nextep_autoplay_cancelled
			mark_nextep_autoplay_cancelled()
		except Exception:
			self.close()
