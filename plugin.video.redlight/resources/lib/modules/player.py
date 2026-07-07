# -*- coding: utf-8 -*-
import os
import xbmc
import json
import time
from threading import Thread
from apis.trakt_api import make_trakt_slug
from caches.settings_cache import get_setting
from modules import kodi_utils as ku, settings as st, watched_status as ws
# logger = ku.logger

PROP_RESOLVE_CANCEL = 'redlight.resolve_cancelled'
PROP_PLAY_OPENING = 'redlight.play_opening'
PROP_NEXTEP_PENDING = 'redlight.nextep_pending'
PROP_NEXTEP_PREP_SCHEDULED = 'redlight.nextep_prep_scheduled'
PROP_NEXTEP_PREP_DECLINED = 'redlight.nextep_prep_declined'
PROP_AUTOSCRAPE_NEXTEP_READY = 'redlight.autoscrape_nextep_ready'
PROP_NEXTEP_AUTOPLAY_CANCELLED = 'redlight.nextep_autoplay_cancelled'
PROP_RANDOM_CONTINUAL_SKIP_ATTEMPTS = 'redlight.random_continual_skip_attempts'
# Movies-only: fire stingers alert ~3 min before other alert sources would (typical 90% vs 95% gap on ~1 hr).
_STINGER_EARLY_OFFSET_SEC = 180
_NEXTEP_SUB_FETCH_DEFER_SEC = 45
_NEXTEP_CLOSE_EARLY_PLAY_SEC = 4
_NEXTEP_CLOSE_POLL_MS = 250
_INTRO_SKIP_PROMPT_EARLY_SEC = 15
_INTRO_SKIP_PROMPT_COUNTDOWN_SEC = 15
_INTRO_SKIP_EARLY_START_SEC = 120
_INTRO_SKIP_SETTLE_SEC = 4
_INTRO_SKIP_SETTLE_MAX_WAIT_SEC = 12
_INTRO_SKIP_SETTLE_JUMP_SEC = 20
_INTRO_CHAPTER_MIN_START_SEC = 5
_INTRO_CHAPTER_MIN_SEGMENT_SEC = 10
_INTRO_CHAPTER_MIN_END_SEC = 15
_INTRO_SKIP_POST_END_GRACE_SEC = 20

class RedLightPlayer(xbmc.Player):
	def __init__ (self):
		xbmc.Player.__init__(self)

	def _resolve_cancelled(self):
		if not self.is_generic and (self.sources_object._resolve_user_cancelled or self.sources_object.cancel_all_playback):
			return True
		return ku.get_property(PROP_RESOLVE_CANCEL) == 'true'

	def run(self, url=None, obj=None):
		ku.hide_busy_dialog()
		self.clear_playback_properties(clear_navigation=False)
		if not url:
			self.is_generic = obj == 'video'
			return self.run_error('No playable link was returned.')
		try: return self.play_video(url, obj)
		except:
			self.is_generic = obj == 'video'
			return self.run_error()

	def play_video(self, url, obj):
		self.set_constants(url, obj)
		if self.is_generic:
			ku.clear_video_playlist()
		if not self.is_generic and self._resolve_cancelled():
			self.playback_successful = False
			self.cancel_all_playback = True
			self.sources_object.cancel_all_playback = True
			self.sources_object._resolve_user_cancelled = True
			return
		ku.volume_checker()
		ku.set_property(PROP_PLAY_OPENING, 'true')
		self.play(self.url, self.make_listing())
		if self.is_generic:
			self.check_playback_start_generic()
			if self.playback_successful:
				ku.clear_property(PROP_PLAY_OPENING)
			else:
				self.safe_stop()
				return self.run_error()
		else:
			self.check_playback_start()
			if self.playback_successful:
				ku.clear_property(PROP_PLAY_OPENING)
				try:
					if self.sources_object:
						self.sources_object._release_resolve_busy()
				except:
					pass
				self.monitor()
			else:
				self.sources_object.playback_successful = self.playback_successful
				cancelled = self.cancel_all_playback or self.sources_object._resolve_user_cancelled
				if cancelled:
					self.sources_object.cancel_all_playback = True
					self.sources_object._resolve_user_cancelled = True
				else:
					self.sources_object.cancel_all_playback = self.cancel_all_playback
				if cancelled:
					if not self.sources_object._resolve_user_cancelled:
						self.kill_dialog()
				else:
					# Keep the resolver progress UI so play_file can try the next queued source.
					self.run_error()
				self.safe_stop()
		try: del self.kodi_monitor
		except: pass

	def check_playback_start_generic(self):
		resolve_percent = 0
		while self.playback_successful is None:
			ku.hide_busy_dialog()
			if self.kodi_monitor.abortRequested():
				self.playback_successful = False
				break
			elif resolve_percent >= 100:
				self.playback_successful = False
				break
			elif ku.get_visibility('Window.IsTopMost(okdialog)'):
				ku.execute_builtin('SendClick(okdialog, 11)')
				self.playback_successful = False
			elif self.isPlayingVideo():
				try:
					if ku.get_property('redlight.browse_playback') == 'true':
						browse_window = getattr(self, '_browse_results_window', None)
						if browse_window:
							try:
								browse_window.selected = (None, '')
								browse_window.close()
								self._browse_results_window = None
							except:
								pass
					if not ku.get_visibility('Window.IsActive(fullscreenvideo)'):
						ku.execute_builtin('ActivateWindow(fullscreenvideo)', block=False)
					if self.getTotalTime() not in ('0.0', '', 0.0, None):
						self.playback_successful = True
				except:
					pass
			resolve_percent = round(resolve_percent + 0.26, 1)
			ku.sleep(50)

	def check_playback_start(self):
		resolve_percent = 0
		while self.playback_successful is None:
			ku.hide_busy_dialog()
			if self._resolve_cancelled():
				self.sources_object.cancel_all_playback = True
				self.sources_object._resolve_user_cancelled = True
				self.playback_successful = False
				self.safe_stop()
				break
			elif not self.sources_object.progress_dialog:
				if self._resolve_cancelled():
					self.sources_object.cancel_all_playback = True
					self.sources_object._resolve_user_cancelled = True
					self.playback_successful = False
					self.safe_stop()
					break
				elif self.isPlayingVideo():
					try:
						if self.getTotalTime() not in ('0.0', '', 0.0, None) and ku.get_visibility('Window.IsActive(fullscreenvideo)'):
							self.playback_successful = True
					except: pass
			elif self.sources_object.progress_dialog.skip_resolved(): self.playback_successful = False
			elif self.sources_object.progress_dialog.iscanceled() or self.kodi_monitor.abortRequested():
				self.sources_object.cancel_all_playback = True
				self.sources_object._resolve_user_cancelled = True
				self.playback_successful = False
				self.safe_stop()
				break
			elif resolve_percent >= 100:
				self.playback_successful = False
				break
			elif ku.get_visibility('Window.IsTopMost(okdialog)'):
				ku.execute_builtin('SendClick(okdialog, 11)')
				self.playback_successful = False
			elif self.isPlayingVideo():
				if self._resolve_cancelled():
					self.sources_object.cancel_all_playback = True
					self.sources_object._resolve_user_cancelled = True
					self.playback_successful = False
					self.safe_stop()
					break
				try:
					if self.getTotalTime() not in ('0.0', '', 0.0, None) and ku.get_visibility('Window.IsActive(fullscreenvideo)'): self.playback_successful = True
				except: pass
			resolve_percent = round(resolve_percent + 0.26, 1)
			try:
				if self.sources_object.progress_dialog:
					self.sources_object.progress_dialog.update_resolver(percent=resolve_percent)
			except: pass
			ku.sleep(50)

	def playback_close_dialogs(self):
		self.sources_object.playback_successful = True
		self.kill_dialog()
		ku.sleep(200)
		ku.close_all_dialog()

	def monitor(self):
		try:
			ensure_dialog_dead, total_check_time = False, 0
			if self.media_type == 'episode':
				play_random_continual = self.sources_object.random_continual
				play_random = self.sources_object.random
				disable_autoplay_next_episode = self.sources_object.disable_autoplay_next_episode
				if disable_autoplay_next_episode: ku.notification('Scrape with Custom Values - Autoplay Next Episode Cancelled', 4500)
				if any((play_random_continual, play_random, disable_autoplay_next_episode)): self.autoplay_nextep, self.autoscrape_nextep = False, False
				else: self.autoplay_nextep, self.autoscrape_nextep = self.sources_object.autoplay_nextep, self.sources_object.autoscrape_nextep
				if self.autoplay_nextep or self.autoscrape_nextep:
					self._log_nextep('Next episode monitor active: autoplay=%s autoscrape=%s' % (self.autoplay_nextep, self.autoscrape_nextep))
				elif st.autoscrape_next_episode() or st.autoplay_next_episode():
					self._log_nextep('Next episode disabled this play (random=%s random_continual=%s custom_values=%s)' % (play_random, play_random_continual, disable_autoplay_next_episode))
			else:
				show_stinger, stinger_alert_timing, stingers_percentage_fallback = st.stingers_show(), st.stingers_alert_timing(), st.stingers_percentage()
				play_random_continual, self.autoplay_nextep, self.autoscrape_nextep = False, False, False
			while total_check_time <= 30 and not ku.get_visibility('Window.IsActive(fullscreenvideo)'):
				ku.sleep(100)
				total_check_time += 0.10
			ku.hide_busy_dialog()
			ku.sleep(1000)
			self._simkl_scrobble_start()
			self._maybe_start_subtitle_alert_fetch()
			self._maybe_start_introdb_alert_fetch()
			self._intro_skip_fetch_started = False
			if st.auto_enable_subs() and st.subtitles_source() == '0':
				try:
					from indexers.subtitles import enable_local_subtitles, subtitle_notify_poster
					poster = subtitle_notify_poster(self.meta, self.media_type) if getattr(self, 'meta', None) else ku.get_icon('box_office')
					enable_local_subtitles(self, poster=poster, is_episode=self.media_type == 'episode')
				except:
					self.showSubtitles(True)
			while self.isPlayingVideo():
				try:
					if not ensure_dialog_dead:
						ensure_dialog_dead = True
						self.playback_close_dialogs()
					_monitor_sleep_ms = 1000
					if self.media_type == 'episode' and getattr(self, '_nextep_close_wait', False) and not getattr(self, '_nextep_stash_play_scheduled', False):
						try:
							_rem = round(float(self.getTotalTime()) - float(self.getTime()))
							if 0 < _rem <= 10:
								_monitor_sleep_ms = _NEXTEP_CLOSE_POLL_MS
						except:
							pass
					ku.sleep(_monitor_sleep_ms)
					try: self.total_time, self.curr_time = self.getTotalTime(), self.getTime()
					except: ku.sleep(250); continue
					if not self._valid_playback_duration(self.total_time, self.curr_time):
						ku.sleep(250)
						continue
					if not getattr(self, '_intro_skip_fetch_started', False):
						self._intro_skip_fetch_started = True
						self._start_intro_skip_fetch()
					self._maybe_apply_intro_skip()
					self.current_point = round(float(self.curr_time/self.total_time * 100), 1)
					if play_random_continual:
						if self._should_prep_random_continual():
							self.random_continual_triggered = True
							self.run_random_continual()
							break
					elif self.current_point >= 90:
						if not self.media_marked: self.media_watched_marker()
					if self.media_type == 'episode':
						if self.autoplay_nextep or self.autoscrape_nextep:
							if not self.nextep_info_gathered:
								if not self._defer_nextep_info(): self.info_next_ep()
							else:
								self._maybe_refresh_nextep_subtitle_timing()
								self._maybe_refresh_nextep_chapter_timing()
								self._maybe_refresh_nextep_introdb_timing()
							try:
								_nextep_remaining = round(float(self.total_time) - float(self.curr_time))
								if _nextep_remaining > 0: ku.set_property('redlight.nextep_remaining', str(_nextep_remaining))
							except: pass
							if self._should_prep_next_ep(): self._schedule_next_ep()
							self._try_autoplay_nextep_alert()
							self._try_autoplay_early_stash_play()
							self._try_autoscrape_nextep_ready_notify()
							self._maybe_log_nextep_alert_pending()
					elif show_stinger and not self.movie_stingers_run: 
						final_chapter = self._stinger_trigger_point(stinger_alert_timing, stingers_percentage_fallback)
						if self.current_point >= final_chapter: self.run_movie_stingers()
				except: pass
				if not self.subs_searched: self.run_subtitles()
			autoplay_stash_scheduled = False
			if self.autoplay_nextep:
				try:
					from modules.sources import clear_nextep_autoplay_stash, clear_orphan_nextep_play_stash, nextep_autoplay_cancelled, peek_nextep_autoplay_stash, schedule_nextep_stashed_play, take_nextep_autoplay_stash
					if nextep_autoplay_cancelled():
						clear_nextep_autoplay_stash()
						clear_orphan_nextep_play_stash()
						self._log_nextep('Autoplay next episode: skipped at episode end (user cancelled)')
					elif getattr(self, '_nextep_stash_play_scheduled', False):
						autoplay_stash_scheduled = True
					elif getattr(self, '_nextep_alert_shown', False):
						if peek_nextep_autoplay_stash():
							stash = take_nextep_autoplay_stash()
							if stash:
								self._log_nextep('Autoplay next episode: playing stashed resolve at episode end')
								autoplay_stash_scheduled = schedule_nextep_stashed_play(stash)
					else:
						clear_nextep_autoplay_stash()
				except: pass
			if not autoplay_stash_scheduled:
				ku.hide_busy_dialog()
			if not self.media_marked: self.media_watched_marker()
			self.clear_playback_properties(clear_navigation=False)
		except:
			ku.hide_busy_dialog()
			self.sources_object.playback_successful = False
			self.sources_object.cancel_all_playback = True
			return self.kill_dialog()

	def make_listing(self):
		listitem = ku.make_listitem()
		listitem.setPath(self.url)
		listitem.setContentLookup(False)
		if self.is_generic:
			info_tag = listitem.getVideoInfoTag(True)
			info_tag.setMediaType('video')
			play_name = ku.get_property('redlight.tb.play_filename') or self.url
			info_tag.setFilenameAndPath(play_name)
			info_tag.setTitle(os.path.basename(play_name) if play_name else '')
			mime = ku.get_property('redlight.tb.play_mime')
			if not mime:
				path_lower = (play_name or self.url or '').lower().split('|')[0].split('?')[0]
				for ext, mt in (
					('.m2ts', 'video/mp2t'), ('.mts', 'video/mp2t'), ('.ts', 'video/mp2t'),
					('.mkv', 'video/x-matroska'), ('.mp4', 'video/mp4'), ('.avi', 'video/x-msvideo'),
					('.mov', 'video/quicktime'), ('.webm', 'video/webm'),
				):
					if path_lower.endswith(ext):
						mime = mt
						break
			if mime:
				try:
					listitem.setMimeType(mime)
				except Exception:
					pass
			self._disable_kodi_url_resume(listitem)
		else:
			self.tmdb_id, self.imdb_id, self.tvdb_id = self.meta_get('tmdb_id', ''), self.meta_get('imdb_id', ''), self.meta_get('tvdb_id', '')
			self.media_type, self.title, self.year = self.meta_get('media_type'), self.meta_get('title'), self.meta_get('year')
			self.season, self.episode = self.meta_get('season', ''), self.meta_get('episode', '')
			poster = self.meta_get('poster') or ku.get_icon('box_office')
			fanart = self.meta_get('fanart') or ku.get_addon_fanart()
			clearlogo = self.meta_get('clearlogo') or ''
			duration, genre, trailer, mpaa = self.meta_get('duration'), self.meta_get('genre', ''), self.meta_get('trailer'), self.meta_get('mpaa')
			rating, votes = self.meta_get('rating'), self.meta_get('votes')
			premiered, studio, tagline = self.meta_get('premiered'), self.meta_get('studio', ''), self.meta_get('tagline')
			director, writer, country = self.meta_get('director', ''), self.meta_get('writer', ''), self.meta_get('country', '')
			cast = self.meta_get('short_cast', []) or self.meta_get('cast', []) or []
			listitem.setLabel(self.title)
			if self.media_type == 'movie':
				plot = self.meta_get('plot')
				listitem.setArt({'poster': poster, 'fanart': fanart, 'icon': poster, 'clearlogo': clearlogo})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setMediaType('movie'), info_tag.setTitle(self.title), info_tag.setOriginalTitle(self.meta_get('original_title')), info_tag.setPlot(plot)
				info_tag.setYear(int(self.year)), info_tag.setRating(rating), info_tag.setVotes(votes), info_tag.setMpaa(mpaa)
				info_tag.setDuration(duration), info_tag.setCountries(country), info_tag.setTrailer(trailer), info_tag.setPremiered(premiered)
				info_tag.setTagLine(tagline), info_tag.setStudios(studio), info_tag.setIMDBNumber(self.imdb_id), info_tag.setGenres(genre)
				info_tag.setWriters(writer), info_tag.setDirectors(director), info_tag.setUniqueIDs({'imdb': self.imdb_id, 'tmdb': str(self.tmdb_id)})
				info_tag.setCast([ku.kodi_actor()(name=item['name'], role=item['role'], thumbnail=item['thumbnail']) for item in cast])
			else:
				if st.avoid_episode_spoilers() and int(self.meta_get('playcount', '0')) == 0: plot = self.meta_get('tvshow_plot') or '* Hidden to Prevent Spoilers *'
				else: plot = self.meta_get('plot') or self.meta_get('tvshow_plot')
				listitem.setArt({'poster': poster, 'fanart': fanart, 'icon': poster, 'clearlogo': clearlogo, 'tvshow.poster': poster, 'tvshow.clearlogo': clearlogo})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setMediaType('episode'), info_tag.setTitle(self.meta_get('ep_name')), info_tag.setOriginalTitle(self.meta_get('original_title'))
				info_tag.setTvShowTitle(self.title), info_tag.setTvShowStatus(self.meta_get('status')), info_tag.setSeason(self.season), info_tag.setEpisode(self.episode)
				info_tag.setPlot(plot), info_tag.setYear(int(self.year)), info_tag.setRating(rating), info_tag.setVotes(votes)
				info_tag.setMpaa(mpaa), info_tag.setDuration(duration), info_tag.setTrailer(trailer), info_tag.setFirstAired(premiered)
				info_tag.setStudios(studio), info_tag.setIMDBNumber(self.imdb_id), info_tag.setGenres(genre), info_tag.setWriters(writer)
				info_tag.setDirectors(director), info_tag.setUniqueIDs({'imdb': self.imdb_id, 'tmdb': str(self.tmdb_id), 'tvdb': str(self.tvdb_id)})
				info_tag.setCast([ku.kodi_actor()(name=item['name'], role=item['role'], thumbnail=item['thumbnail']) for item in cast])
				info_tag.setFilenameAndPath(self.url)
			self.set_resume_point(listitem)
			if self.url and str(self.url).startswith('http'):
				self._disable_kodi_url_resume(listitem, keep_start_percent=True)
			self.set_playback_properties()
		return listitem

	def _simkl_scrobble_start(self):
		if self.is_generic or st.watched_indicators() != 2 or not st.simkl_user_active(): return
		from apis.simkl_api import simkl_scrobble, simkl_official_status
		if not simkl_official_status(self.media_type): return
		percent = self.playback_percent if self.playback_percent else 0
		Thread(target=simkl_scrobble, args=('start', self.media_type, self.tmdb_id, percent, self.season, self.episode)).start()

	def _simkl_scrobble_stop(self, percent):
		if self.is_generic or st.watched_indicators() != 2 or not st.simkl_user_active(): return
		from apis.simkl_api import simkl_scrobble, simkl_official_status
		if not simkl_official_status(self.media_type): return
		Thread(target=simkl_scrobble, args=('stop', self.media_type, self.tmdb_id, percent, self.season, self.episode)).start()

	def media_watched_marker(self, force_watched=False):
		self.media_marked = True
		try:
			if self.current_point >= 90 or force_watched:
				self._simkl_scrobble_stop(100)
				watched_function = ws.mark_movie if self.media_type == 'movie' else ws.mark_episode
				watched_params = {'action': 'mark_as_watched', 'tmdb_id': self.tmdb_id, 'title': self.title, 'year': self.year, 'season': self.season, 'episode': self.episode,
									'tvdb_id': self.tvdb_id, 'from_playback': 'true'}
				Thread(target=self.run_media_progress, args=(watched_function, watched_params)).start()
			else:
				ku.clear_property('redlight.random_episode_history')
				if self.current_point >= 5:
					progress_params = {'media_type': self.media_type, 'tmdb_id': self.tmdb_id, 'curr_time': self.curr_time, 'total_time': self.total_time,
									'title': self.title, 'season': self.season, 'episode': self.episode, 'from_playback': 'true'}
					Thread(target=self.run_media_progress, args=(ws.set_bookmark, progress_params)).start()
		except: pass

	def run_media_progress(self, function, params):
		try: function(params)
		except: pass

	def _valid_playback_duration(self, total_time=None, curr_time=None):
		try:
			total = total_time if total_time is not None else self.getTotalTime()
			curr = curr_time if curr_time is not None else self.getTime()
			if total in (0, 0.0, '0.0', '', None): return False
			if curr in (0, 0.0, '0.0', '', None): return False
			if float(total) < 60: return False
			return float(curr) > 0
		except:
			return False

	def _player_is_active(self):
		try:
			return self.isPlayingVideo() or self.isPlaying()
		except:
			return False

	def seek(self, seconds, pause_after=False):
		try:
			if not self._player_is_active():
				return False
			seconds = float(seconds)
			total = float(self.getTotalTime())
			if total > 1:
				seconds = max(0.0, min(seconds, total - 1.0))
			self.seekTime(seconds)
			if pause_after:
				self.pause()
			return True
		except:
			return False

	def _log_nextep(self, message):
		try: ku.logger('Red Light', message)
		except: pass

	def _intro_skip_play_type_label(self):
		try:
			play_type = getattr(self.sources_object, 'play_type', '') if getattr(self, 'sources_object', None) else ''
			if play_type in ('autoplay_nextep', 'autoscrape_nextep', 'random_continual'):
				return play_type
		except: pass
		return 'manual'

	def _log_intro_skip(self, message):
		try: ku.logger('Red Light', '%s (play_type=%s)' % (message, self._intro_skip_play_type_label()))
		except: pass

	def _defer_nextep_info(self):
		if getattr(self, 'nextep_info_gathered', False): return False
		nextep_settings = st.auto_nextep_settings(self._nextep_play_type())
		alert_timing = nextep_settings.get('alert_timing')
		if alert_timing == 'introdb':
			if self._outro_credits_pop_at(fetch=False) is not None: return False
			if self._outro_credits_pop_at(fetch=True) is not None: return False
			started = getattr(self, '_playback_started_at', None)
			if started and (time.time() - started) > _NEXTEP_SUB_FETCH_DEFER_SEC: return False
			return True
		if alert_timing != 'subtitles': return False
		if self._subtitle_end_remaining(fetch=False, for_alert=True) is not None: return False
		if not st.subs_alert_fetch_enabled(self.media_type): return False
		if getattr(self, '_subtitle_alert_fetch_done', False): return False
		started = getattr(self, '_playback_started_at', None)
		if started and (time.time() - started) > _NEXTEP_SUB_FETCH_DEFER_SEC: return False
		return True

	def decline_nextep_prep(self, reason=''):
		ku.set_property(PROP_NEXTEP_PREP_DECLINED, 'true')
		if reason:
			self._log_nextep('Next episode prep declined: %s' % reason)

	def _should_prep_next_ep(self):
		if ku.get_property(PROP_NEXTEP_PREP_DECLINED) == 'true':
			return False
		if ku.get_property(PROP_NEXTEP_AUTOPLAY_CANCELLED) == 'true':
			return False
		if ku.get_property(PROP_NEXTEP_PENDING) == 'true':
			return False
		if ku.get_property(PROP_NEXTEP_PREP_SCHEDULED) == 'true':
			return False
		if self.autoplay_nextep and ku.get_property('redlight.nextep_scrape_ready') == 'true':
			try:
				from modules.sources import peek_nextep_autoplay_stash
				if peek_nextep_autoplay_stash():
					return False
			except:
				pass
		if not self._valid_playback_duration(self.total_time, self.curr_time):
			return False
		try:
			remaining = round(float(self.total_time) - float(self.curr_time))
		except:
			return False
		return remaining > 0 and remaining <= self.start_prep

	def _nextep_play_type(self):
		return 'autoplay_nextep' if self.autoplay_nextep else 'autoscrape_nextep'

	def _still_watching_due(self, nextep_settings):
		watching_check = nextep_settings.get('watching_check', 0)
		return watching_check and self.meta_get('watch_count') == watching_check

	def _pop_window_seconds(self, nextep_settings, total_time):
		return self._alert_window_time(nextep_settings, 90, total_time, still_watching_check=0)

	def _start_prep_seconds(self, nextep_settings, pop_at, play_type):
		pipeline = st.nextep_pipeline_headroom(play_type, nextep_settings['scraper_time'], self._still_watching_due(nextep_settings))
		return int(pop_at) + pipeline

	def _resolve_subtitle_pop_at(self, sub_tail, credits_entry):
		# subtitles.py returns the target remaining seconds; do not clamp to NEXTEP_ALERT_MAX (that cap is for % fallback only).
		vals = [int(v) for v in (sub_tail, credits_entry) if v is not None]
		if not vals: return None
		return max(max(vals), st.NEXTEP_ALERT_MIN_REMAINING_SEC)

	def _subtitle_credits_entry_remaining(self, fetch=False, quiet=False):
		if getattr(self, 'is_generic', False) or not getattr(self, 'imdb_id', None): return None
		if quiet:
			cached = getattr(self, '_subtitle_credits_entry_cached', '__unset__')
			if cached != '__unset__': return cached
		try:
			from indexers.subtitles import subtitle_seconds_remaining_before_end
			season = self.season if self.media_type == 'episode' else None
			episode = self.episode if self.media_type == 'episode' else None
			remaining = subtitle_seconds_remaining_before_end(float(self.total_time), self.imdb_id, season, episode, fetch=fetch,
				player=self, playing_filename=getattr(self, 'playing_filename', None), playing_item=getattr(self, 'playing_item', None),
				playback_started_at=getattr(self, '_playback_started_at', None),
				year=getattr(self, 'year', None), credits_entry=True, quiet=quiet)
		except:
			remaining = None
		if quiet: self._subtitle_credits_entry_cached = remaining
		return remaining

	def _ensure_random_continual_prep(self):
		if getattr(self, 'random_continual_start_prep', None) is not None: return
		if st.autoscrape_next_episode(): play_type = 'autoscrape_nextep'
		elif st.autoplay_next_episode(): play_type = 'autoplay_nextep'
		else: play_type = 'autoscrape_nextep'
		nextep_settings = st.auto_nextep_settings(play_type)
		pop_at, _timing_source = self._pop_window_seconds(nextep_settings, self.total_time)
		self.random_continual_start_prep = self._start_prep_seconds(nextep_settings, pop_at, play_type)

	def _should_prep_random_continual(self):
		if getattr(self, 'random_continual_triggered', False): return False
		if not self._valid_playback_duration(self.total_time, self.curr_time): return False
		self._ensure_random_continual_prep()
		try: remaining = round(float(self.total_time) - float(self.curr_time))
		except: return False
		return remaining > 0 and remaining <= self.random_continual_start_prep

	def _schedule_next_ep(self):
		if ku.get_property(PROP_NEXTEP_PENDING) == 'true':
			return
		if ku.get_property(PROP_NEXTEP_PREP_SCHEDULED) == 'true':
			return
		try: remaining = round(float(self.total_time) - float(self.curr_time))
		except: remaining = -1
		self._log_nextep('Next episode prep scheduled: %s S%02dE%02d play_type=%s remaining=%ss start_prep=%ss' % (
			self.meta_get('title', ''), self.meta_get('season', 0), self.meta_get('episode', 0),
			self.nextep_settings.get('play_type', ''), remaining, getattr(self, 'start_prep', '')))
		ku.set_property(PROP_NEXTEP_PREP_SCHEDULED, 'true')
		ku.set_property(PROP_NEXTEP_PENDING, 'true')
		meta = dict(self.meta) if getattr(self, 'meta', None) else {}
		nextep_settings = dict(self.nextep_settings) if getattr(self, 'nextep_settings', None) else None
		def _work():
			try:
				from modules.episode_tools import EpisodeTools
				if not self.media_marked:
					try: self.media_watched_marker(force_watched=True)
					except: pass
				EpisodeTools(meta, nextep_settings).auto_nextep()
			except Exception as exc:
				ku.logger('Red Light', 'Next episode prep failed: %s' % exc)
			finally:
				ku.clear_property(PROP_NEXTEP_PENDING)
				ku.clear_property(PROP_NEXTEP_PREP_SCHEDULED)
		Thread(target=_work, daemon=True).start()

	def _maybe_log_nextep_alert_pending(self):
		if not self.autoplay_nextep or getattr(self, '_nextep_alert_shown', False): return
		if getattr(self, '_nextep_alert_pending_logged', False): return
		if ku.get_property('redlight.nextep_scrape_ready') != 'true': return
		try:
			from modules.sources import peek_nextep_autoplay_stash
			if not peek_nextep_autoplay_stash(): return
		except:
			return
		try:
			remaining = round(float(self.total_time) - float(self.curr_time))
		except:
			return
		window = int(getattr(self, 'nextep_settings', {}).get('window_time', 0) or 0)
		if remaining <= 0 or remaining <= window: return
		self._nextep_alert_pending_logged = True
		self._log_nextep('Autoplay next episode alert pending: remaining=%ss window=%ss (scrape ready)' % (remaining, window))

	def _should_show_autoplay_nextep_alert(self):
		if not self.autoplay_nextep or not getattr(self, 'nextep_settings', None): return False
		if getattr(self, '_nextep_alert_shown', False): return False
		try:
			from modules.sources import nextep_autoplay_cancelled
			if nextep_autoplay_cancelled(): return False
		except:
			pass
		if ku.get_property('redlight.nextep_scrape_ready') != 'true': return False
		try:
			from modules.sources import peek_nextep_autoplay_stash
			if not peek_nextep_autoplay_stash(): return False
		except:
			return False
		try:
			remaining = round(float(self.total_time) - float(self.curr_time))
		except:
			return False
		window = int(self.nextep_settings.get('window_time', 0) or 0)
		return remaining > 0 and remaining <= window

	def _try_autoscrape_nextep_ready_notify(self):
		if not self.autoscrape_nextep or getattr(self, '_autoscrape_ready_notified', False): return
		if not ku.get_property(PROP_AUTOSCRAPE_NEXTEP_READY): return
		if not getattr(self, 'nextep_settings', None): return
		try:
			remaining = round(float(self.total_time) - float(self.curr_time))
		except:
			return
		window = int(self.nextep_settings.get('window_time', 0) or 0)
		if remaining <= 0 or remaining > window: return
		self._autoscrape_ready_notified = True
		meta = {}
		try:
			raw = ku.get_property(PROP_AUTOSCRAPE_NEXTEP_READY)
			if raw and raw != 'true':
				meta = json.loads(raw)
		except:
			pass
		ku.clear_property(PROP_AUTOSCRAPE_NEXTEP_READY)
		title = meta.get('title') or self.meta_get('title', '')
		season = meta.get('season', self.season)
		episode = meta.get('episode', self.episode)
		poster = meta.get('poster') or self.meta_get('poster')
		ku.notification('[B]Next Episode Ready:[/B] %s S%02dE%02d' % (title, season, episode), 6500, poster)
		self._log_nextep('Autoscrape next episode ready notify: remaining=%ss window=%ss' % (remaining, window))

	def _try_autoplay_early_stash_play(self):
		if not self.autoplay_nextep or not getattr(self, '_nextep_close_wait', False):
			return
		if getattr(self, '_nextep_stash_play_scheduled', False) or not getattr(self, '_nextep_alert_shown', False):
			return
		try:
			from modules.sources import nextep_autoplay_cancelled, peek_nextep_autoplay_stash, schedule_nextep_stashed_play, take_nextep_autoplay_stash
			if nextep_autoplay_cancelled() or not peek_nextep_autoplay_stash():
				return
		except:
			return
		try:
			remaining = round(float(self.total_time) - float(self.curr_time))
		except:
			return
		if remaining > _NEXTEP_CLOSE_EARLY_PLAY_SEC or remaining <= 0:
			return
		stash = take_nextep_autoplay_stash()
		if not stash:
			return
		if schedule_nextep_stashed_play(stash, show_busy=False):
			self._nextep_stash_play_scheduled = True
			self._log_nextep('Autoplay next episode: early stash resolve at remaining=%ss' % remaining)

	def _try_autoplay_nextep_alert(self):
		if not self._should_show_autoplay_nextep_alert(): return
		self._nextep_alert_shown = True
		try:
			from modules.sources import peek_nextep_autoplay_stash, take_nextep_autoplay_stash
		except:
			return
		stash = peek_nextep_autoplay_stash()
		if not stash: return
		settings = self.nextep_settings
		use_window = settings.get('use_window')
		default_action = settings.get('default_action')
		dialog_meta = stash['meta']
		try:
			remaining = round(float(self.total_time) - float(self.curr_time))
		except:
			remaining = settings.get('window_time')
		self._log_nextep('Autoplay next episode alert: remaining=%ss window=%ss method=%s' % (
			remaining, settings.get('window_time'), 'window' if use_window else 'notification'))
		action = None
		if use_window:
			from windows.base_window import open_window
			try:
				action = open_window(('windows.playback_notifications', 'NextEpisode'), 'playback_notifications.xml', meta=dialog_meta, default_action=default_action)
			except:
				action = 'cancel'
		else:
			ku.notification('[B]Next Up:[/B] %s S%02dE%02d' % (dialog_meta.get('title'), dialog_meta.get('season'), dialog_meta.get('episode')), 6500, dialog_meta.get('poster'))
		if not action:
			action = default_action if use_window else 'close'
		if not action:
			action = 'close'
		if action == 'cancel':
			try:
				from modules.sources import mark_nextep_autoplay_cancelled
				mark_nextep_autoplay_cancelled()
			except:
				pass
			ku.clear_property(PROP_NEXTEP_PREP_SCHEDULED)
			self._log_nextep('Autoplay next episode alert action: cancel')
			return
		if action == 'pause':
			self._nextep_close_wait = True
			self._log_nextep('Autoplay next episode alert action: pause (waiting for user)')
			return
		if action == 'close':
			self._nextep_close_wait = True
			self._log_nextep('Autoplay next episode alert action: close (waiting for episode end)')
			return
		if action != 'play':
			return
		self._log_nextep('Autoplay next episode alert action: play')
		stash = take_nextep_autoplay_stash()
		if not stash: return
		try:
			from modules.sources import schedule_nextep_stashed_play
			if not schedule_nextep_stashed_play(stash):
				ku.logger('Red Light', 'Autoplay next episode play failed: could not schedule resolve')
		except Exception as exc:
			ku.logger('Red Light', 'Autoplay next episode play failed: %s' % exc)
		return

	def run_next_ep(self):
		from modules.episode_tools import EpisodeTools
		if not self.media_marked: self.media_watched_marker(force_watched=True)
		EpisodeTools(self.meta, self.nextep_settings).auto_nextep()

	def run_random_continual(self):
		from modules.episode_tools import EpisodeTools
		if not self.media_marked: self.media_watched_marker(force_watched=True)
		EpisodeTools(self.meta).play_random_continual(False)

	def run_movie_stingers(self):
		self.movie_stingers_run = True
		stinger_keys = self.meta.get('stinger_keys', None)
		if not stinger_keys:
			try:
				keywords = self.meta.get('keywords', [])
				stinger_keys = [i['name'] for i in keywords['keywords'] if i['name'] in ('duringcreditsstinger', 'aftercreditsstinger')]
				self.meta['stinger_keys'] = stinger_keys
			except: pass
		if stinger_keys:
			from windows.base_window import open_window
			Thread(target=lambda: open_window(('windows.playback_notifications', 'StingersNotification'), 'playback_notifications.xml', meta=self.meta)).start()

	def set_resume_point(self, listitem):
		if self.playback_percent > 0.0: listitem.setProperty('StartPercent', str(self.playback_percent))

	def _disable_kodi_url_resume(self, listitem, keep_start_percent=False):
		# Kodi stores resume by stream URL/filename; debrid links reuse the same name and can reopen near EOF.
		if not keep_start_percent or float(listitem.getProperty('StartPercent') or 0) <= 0:
			listitem.setProperty('StartPercent', '0')
		listitem.setProperty('StartOffset', '0')
		try:
			listitem.getVideoInfoTag(True).setResumePoint(0.0)
		except:
			pass

	def info_next_ep(self):
		self.nextep_info_gathered = True
		play_type = self._nextep_play_type()
		nextep_settings = st.auto_nextep_settings(play_type)
		pop_at, timing_source = self._pop_window_seconds(nextep_settings, self.total_time)
		credits_entry = self._subtitle_credits_entry_remaining(fetch=False) if nextep_settings.get('alert_timing') == 'subtitles' else None
		use_window = nextep_settings['alert_method'] == 0
		default_action = nextep_settings['default_action']
		self.start_prep = self._start_prep_seconds(nextep_settings, pop_at, play_type)
		pipeline = st.nextep_pipeline_headroom(play_type, nextep_settings['scraper_time'], self._still_watching_due(nextep_settings))
		self.nextep_settings = {'use_window': use_window, 'window_time': pop_at, 'default_action': default_action, 'play_type': play_type,
			'alert_timing': nextep_settings.get('alert_timing'), 'watching_check': nextep_settings['watching_check'], 'pipeline_headroom': pipeline, 'credits_entry': credits_entry}
		if nextep_settings.get('alert_timing') == 'introdb':
			outro_start = self._outro_credits_start(fetch=True)
			if outro_start is not None:
				self.nextep_settings['outro_start'] = outro_start
		credits_log = ' credits_entry=%ss' % credits_entry if credits_entry is not None else ''
		outro_start = self.nextep_settings.get('outro_start')
		outro_log = ' outro_start=%.1fs' % outro_start if outro_start is not None else ''
		self._log_nextep('Next episode timing: play_type=%s alert=%s source=%s pop_at=%ss pipeline=%ss start_prep=%ss total=%ss%s%s' % (
			play_type, nextep_settings.get('alert_timing'), timing_source, pop_at, pipeline, self.start_prep, round(float(self.total_time)), credits_log, outro_log))

	def final_chapter(self, threshhold):
		try:
			final_chapter = float(ku.get_infolabel('Player.Chapters').split(',')[-1])
			if final_chapter >= threshhold: return final_chapter
		except: pass
		return None

	def _clear_subtitle_end_cache(self):
		self._subtitle_end_remaining_cached = '__unset__'
		self._subtitle_credits_entry_cached = '__unset__'

	def _subtitle_alert_fetch_pending(self):
		return getattr(self, '_subtitle_alert_fetch_started', False) and not getattr(self, '_subtitle_alert_fetch_done', False)

	def _maybe_start_introdb_alert_fetch(self):
		if getattr(self, '_introdb_alert_fetch_started', False): return
		if self.is_generic or self.media_type != 'episode': return
		if not (self.autoplay_nextep or self.autoscrape_nextep): return
		nextep_settings = st.auto_nextep_settings(self._nextep_play_type())
		if nextep_settings.get('alert_timing') != 'introdb': return
		self._introdb_alert_fetch_started = True
		season = self.season
		episode = self.episode
		tmdb_id, imdb_id = self.tmdb_id, self.imdb_id
		def _work():
			try:
				from apis.intro_skip_api import prefetch_credits_start
				duration = None
				try: duration = float(self.total_time) if self.total_time else None
				except: pass
				prefetch_credits_start(tmdb_id, imdb_id, season, episode, duration)
			except: pass
			finally:
				self._outro_credits_start_cached = '__unset__'
		Thread(target=_work, daemon=True).start()

	def _maybe_start_subtitle_alert_fetch(self):
		if getattr(self, '_subtitle_alert_fetch_started', False): return
		if self.is_generic or not self.imdb_id: return
		if not st.subs_alert_fetch_enabled(self.media_type): return
		self._subtitle_alert_fetch_started = True
		season = self.season if self.media_type == 'episode' else None
		episode = self.episode if self.media_type == 'episode' else None
		year = getattr(self, 'year', None)
		playing_filename = getattr(self, 'playing_filename', None)
		playing_item = getattr(self, 'playing_item', None)
		def _work():
			try:
				from indexers.subtitles import fetch_subtitle_for_alert_timing
				fetch_subtitle_for_alert_timing(self.imdb_id, season, episode, year, playing_filename, playing_item)
			except: pass
			finally:
				self._subtitle_alert_fetch_done = True
				self._clear_subtitle_end_cache()
		Thread(target=_work, daemon=True).start()

	def _subtitle_end_remaining(self, fetch=False, for_alert=False):
		cached = getattr(self, '_subtitle_end_remaining_cached', '__unset__')
		cache_key = 'alert' if for_alert else 'scrape'
		cached_by_mode = cached if isinstance(cached, dict) else {}
		if cache_key in cached_by_mode and (cached_by_mode[cache_key] is not None or getattr(self, 'subs_searched', False)) and not self._subtitle_alert_fetch_pending():
			return cached_by_mode[cache_key]
		try:
			from indexers.subtitles import subtitle_seconds_remaining_before_end
			season = self.season if self.media_type == 'episode' else None
			episode = self.episode if self.media_type == 'episode' else None
			remaining = subtitle_seconds_remaining_before_end(float(self.total_time), self.imdb_id, season, episode, fetch=fetch,
				player=self, playing_filename=getattr(self, 'playing_filename', None), playing_item=getattr(self, 'playing_item', None),
				playback_started_at=getattr(self, '_playback_started_at', None),
				year=getattr(self, 'year', None), for_alert=for_alert)
		except:
			remaining = None
		if remaining is not None:
			cached_by_mode[cache_key] = remaining
			self._subtitle_end_remaining_cached = cached_by_mode
		elif getattr(self, 'subs_searched', False):
			cached_by_mode[cache_key] = None
			self._subtitle_end_remaining_cached = cached_by_mode
		return remaining

	def _alert_window_time(self, nextep_settings, chapter_threshold, total_time, still_watching_check=0):
		alert_timing = nextep_settings.get('alert_timing', 'off')
		window_percentage = nextep_settings['window_percentage']
		try: total_time = float(total_time)
		except:
			return window_percentage + still_watching_check, 'percentage'
		if alert_timing == 'chapters':
			final_chapter = self.final_chapter(chapter_threshold)
			if final_chapter:
				percentage = 100 - final_chapter
				return round((percentage / 100) * total_time) + still_watching_check, 'chapters'
		if alert_timing == 'subtitles':
			sub_remaining = self._subtitle_end_remaining(fetch=True, for_alert=True)
			credits_entry = self._subtitle_credits_entry_remaining(fetch=False, quiet=True)
			pop_at = self._resolve_subtitle_pop_at(sub_remaining, credits_entry)
			if pop_at is not None:
				return pop_at + still_watching_check, 'subtitles'
		if alert_timing == 'introdb':
			pop_at = self._outro_credits_pop_at(fetch=True)
			if pop_at is not None:
				return pop_at + still_watching_check, 'introdb'
		fallback = 'percentage_fallback' if alert_timing in ('chapters', 'subtitles', 'introdb') else 'percentage'
		pop_at = round((window_percentage / 100) * total_time) + still_watching_check
		if alert_timing == 'subtitles':
			pop_at = min(int(pop_at), st.NEXTEP_ALERT_MAX_REMAINING_SEC)
		return pop_at, fallback

	def _maybe_refresh_nextep_subtitle_timing(self):
		if not getattr(self, 'nextep_info_gathered', False) or not getattr(self, 'nextep_settings', None): return
		play_type = self._nextep_play_type()
		nextep_settings = st.auto_nextep_settings(play_type)
		if nextep_settings.get('alert_timing') != 'subtitles': return
		sub_alert = self._subtitle_end_remaining(fetch=False, for_alert=True)
		if sub_alert is None: return
		credits_entry = self._subtitle_credits_entry_remaining(fetch=False, quiet=True)
		pop_at = self._resolve_subtitle_pop_at(sub_alert, credits_entry)
		if pop_at is None: return
		start_prep = self._start_prep_seconds(nextep_settings, pop_at, play_type)
		pipeline = st.nextep_pipeline_headroom(play_type, nextep_settings['scraper_time'], self._still_watching_due(nextep_settings))
		if pop_at == self.nextep_settings.get('window_time') and start_prep == self.start_prep and credits_entry == self.nextep_settings.get('credits_entry'): return
		self.start_prep = start_prep
		self.nextep_settings['window_time'] = pop_at
		self.nextep_settings['pipeline_headroom'] = pipeline
		self.nextep_settings['credits_entry'] = credits_entry
		credits_log = ' credits_entry=%ss' % credits_entry if credits_entry is not None else ''
		self._log_nextep('Next episode timing refreshed (subtitles): pop_at=%ss start_prep=%ss%s' % (pop_at, start_prep, credits_log))

	def _maybe_refresh_nextep_chapter_timing(self):
		if not getattr(self, 'nextep_info_gathered', False) or not getattr(self, 'nextep_settings', None): return
		play_type = self._nextep_play_type()
		nextep_settings = st.auto_nextep_settings(play_type)
		if nextep_settings.get('alert_timing') != 'chapters': return
		if not self.final_chapter(90): return
		pop_at, _timing_source = self._alert_window_time(nextep_settings, 90, self.total_time, still_watching_check=0)
		start_prep = self._start_prep_seconds(nextep_settings, pop_at, play_type)
		pipeline = st.nextep_pipeline_headroom(play_type, nextep_settings['scraper_time'], self._still_watching_due(nextep_settings))
		if pop_at == self.nextep_settings.get('window_time') and start_prep == self.start_prep: return
		self.start_prep = start_prep
		self.nextep_settings['window_time'] = pop_at
		self.nextep_settings['pipeline_headroom'] = pipeline
		self._log_nextep('Next episode timing refreshed (chapters): pop_at=%ss start_prep=%ss' % (pop_at, start_prep))

	def _outro_credits_start(self, fetch=False):
		if getattr(self, 'is_generic', False) or self.media_type != 'episode':
			return None
		cache_attr = '_outro_credits_start_cached'
		if not fetch:
			cached = getattr(self, cache_attr, '__unset__')
			if cached != '__unset__':
				return cached
		try:
			from apis.intro_skip_api import resolve_credits_start_sec
			duration = float(self.total_time) if self.total_time else None
			start_sec = resolve_credits_start_sec(self.tmdb_id, self.imdb_id, self.season, self.episode, duration)
		except:
			start_sec = None
		setattr(self, cache_attr, start_sec)
		return start_sec

	def _outro_credits_pop_at(self, fetch=False):
		try:
			total_time = float(self.total_time)
		except:
			return None
		start_sec = self._outro_credits_start(fetch=fetch)
		if start_sec is None:
			return None
		pop_at = int(round(total_time - float(start_sec) + st.NEXTEP_INTRODB_BUFFER_SEC))
		return max(pop_at, st.NEXTEP_ALERT_MIN_REMAINING_SEC)

	def _maybe_refresh_nextep_introdb_timing(self):
		if not getattr(self, 'nextep_info_gathered', False) or not getattr(self, 'nextep_settings', None): return
		play_type = self._nextep_play_type()
		nextep_settings = st.auto_nextep_settings(play_type)
		if nextep_settings.get('alert_timing') != 'introdb': return
		pop_at = self._outro_credits_pop_at(fetch=False)
		if pop_at is None: return
		start_prep = self._start_prep_seconds(nextep_settings, pop_at, play_type)
		pipeline = st.nextep_pipeline_headroom(play_type, nextep_settings['scraper_time'], self._still_watching_due(nextep_settings))
		outro_start = getattr(self, '_outro_credits_start_cached', None)
		if pop_at == self.nextep_settings.get('window_time') and start_prep == self.start_prep and outro_start == self.nextep_settings.get('outro_start'): return
		self.start_prep = start_prep
		self.nextep_settings['window_time'] = pop_at
		self.nextep_settings['pipeline_headroom'] = pipeline
		self.nextep_settings['outro_start'] = outro_start
		outro_log = ' outro_start=%.1fs' % outro_start if outro_start is not None else ''
		self._log_nextep('Next episode timing refreshed (introdb): pop_at=%ss start_prep=%ss%s' % (pop_at, start_prep, outro_log))

	def _stinger_early_percentage(self, trigger_pct):
		try:
			total = float(self.total_time)
			if total > 0:
				trigger_pct = round(trigger_pct - (_STINGER_EARLY_OFFSET_SEC / total * 100), 1)
				return max(1.0, trigger_pct)
		except: pass
		return trigger_pct

	def _stinger_trigger_point(self, alert_timing, fallback_percentage):
		if alert_timing == 'chapters':
			trigger_pct = self.final_chapter(75) or fallback_percentage
		elif alert_timing == 'subtitles':
			trigger_pct = fallback_percentage
			try:
				sub_remaining = self._subtitle_end_remaining(fetch=True, for_alert=True)
				if sub_remaining is not None and self.total_time:
					trigger_pct = round(100 - (float(sub_remaining) / float(self.total_time) * 100), 1)
			except: pass
		else:
			trigger_pct = fallback_percentage
		return self._stinger_early_percentage(trigger_pct)

	def kill_dialog(self):
		try:
			self.sources_object._kill_progress_dialog()
		except:
			if not getattr(self.sources_object, '_resolve_user_cancelled', False):
				ku.close_all_dialog()

	def set_constants(self, url, obj):
		self.url = url
		self.sources_object = obj
		self.is_generic = self.sources_object == 'video'
		self.kodi_monitor = ku.kodi_monitor()
		self.playback_successful = None
		self.cancel_all_playback = False
		if not self.is_generic:
			self.meta = self.sources_object.meta
			self.meta_get, self.playback_percent = self.meta.get, self.sources_object.playback_percent or 0.0
			self.playing_filename = self.sources_object.playing_filename
			self.media_marked, self.nextep_info_gathered, self.movie_stingers_run = False, False, False
			self.subs_searched = False
			self._subtitle_end_remaining_cached = '__unset__'
			self._subtitle_alert_fetch_started = False
			self._subtitle_alert_fetch_done = False
			self._playback_started_at = time.time()
			ku.clear_property(PROP_NEXTEP_PENDING)
			ku.clear_property(PROP_NEXTEP_PREP_SCHEDULED)
			ku.clear_property(PROP_NEXTEP_PREP_DECLINED)
			ku.clear_property(PROP_AUTOSCRAPE_NEXTEP_READY)
			ku.clear_property(PROP_RANDOM_CONTINUAL_SKIP_ATTEMPTS)
			ku.clear_property(PROP_NEXTEP_AUTOPLAY_CANCELLED)
			self._autoscrape_ready_notified = False
			self._nextep_alert_pending_logged = False
			self._nextep_close_wait = False
			self._nextep_stash_play_scheduled = False
			self.playing_item = self.sources_object.playing_item
			self._intro_skip_active = False
			self._intro_skip_done = False
			self._intro_skip_segment = None
			self._intro_skip_no_timing_logged = False
			self._intro_skip_last_curr = None
			self._intro_skip_settle_ready = False
			self._outro_credits_start_cached = '__unset__'

	def _start_intro_skip_fetch(self):
		play_type = getattr(self.sources_object, 'play_type', '')
		if not st.autoplay_skip_intro_enabled(play_type) or self.media_type != 'episode':
			return
		self._intro_skip_active = True
		self._intro_skip_done = False
		self._intro_skip_prompt_answered = False
		self._intro_skip_approved = st.autoplay_skip_intro_auto(play_type)
		self._intro_skip_fetch_done = False
		self._intro_skip_no_timing_logged = False
		try:
			from apis.intro_skip_api import peek_intro_segment_cache
			cached = peek_intro_segment_cache(self.tmdb_id, self.imdb_id, self.season, self.episode)
			if cached != '__miss__':
				self._intro_skip_fetch_done = True
				if cached:
					self._intro_skip_segment = cached
				return
		except: pass
		def _work():
			try:
				from apis.intro_skip_api import resolve_intro_segment
				total = getattr(self, 'total_time', None)
				duration = None
				try:
					if total not in (None, '', 0, 0.0): duration = float(total)
				except: pass
				segment = resolve_intro_segment(self.tmdb_id, self.imdb_id, self.season, self.episode, duration)
				if segment and not getattr(self, '_intro_skip_segment', None):
					self._intro_skip_segment = segment
			except: pass
			finally:
				self._intro_skip_fetch_done = True
		Thread(target=_work, daemon=True).start()

	def _try_intro_skip_chapters(self):
		if getattr(self, '_intro_skip_segment', None):
			return
		if not getattr(self, '_intro_skip_fetch_done', False):
			return
		try:
			total = float(self.total_time)
			if total < 60:
				return
			raw = ku.get_infolabel('Player.Chapters')
			if not raw:
				return
			marks = [float(x) for x in raw.split(',') if x.strip()]
			if len(marks) < 2:
				return
			start_pct, end_pct = marks[0], marks[1]
			if start_pct > 5 or end_pct > 30 or end_pct <= start_pct:
				return
			start_sec = total * start_pct / 100.0
			end_sec = total * end_pct / 100.0
			if start_sec < _INTRO_CHAPTER_MIN_START_SEC:
				return
			if end_sec - start_sec < _INTRO_CHAPTER_MIN_SEGMENT_SEC or end_sec < _INTRO_CHAPTER_MIN_END_SEC:
				return
			self._intro_skip_segment = {'start_sec': start_sec, 'end_sec': end_sec, 'source': 'chapters'}
		except: pass

	def _maybe_log_intro_skip_no_timing(self):
		if getattr(self, '_intro_skip_no_timing_logged', False):
			return
		if not getattr(self, '_intro_skip_fetch_done', False):
			return
		if getattr(self, '_intro_skip_segment', None):
			return
		self._try_intro_skip_chapters()
		if getattr(self, '_intro_skip_segment', None):
			return
		self._intro_skip_no_timing_logged = True
		self._intro_skip_done = True
		self._log_intro_skip('Intro skip: no timing (api miss, chapters rejected)')

	def _intro_resume_sec(self):
		if self.playback_percent and float(self.playback_percent) > 0:
			try: return float(self.total_time) * float(self.playback_percent) / 100.0
			except: pass
		return None

	def _intro_effective_playhead(self):
		try: curr = float(self.curr_time)
		except: curr = 0.0
		resume_sec = self._intro_resume_sec()
		if resume_sec is not None: return max(curr, resume_sec)
		return curr

	def _intro_skip_position_settled(self):
		if getattr(self, '_intro_skip_settle_ready', False): return True
		started = getattr(self, '_playback_started_at', None)
		if not started: return True
		elapsed = time.time() - started
		try: curr = float(self.curr_time)
		except: return False
		last = getattr(self, '_intro_skip_last_curr', None)
		if last is not None and abs(curr - last) >= _INTRO_SKIP_SETTLE_JUMP_SEC:
			self._intro_skip_last_curr = curr
			return False
		resume_sec = self._intro_resume_sec()
		if resume_sec is not None and resume_sec > _INTRO_SKIP_PROMPT_EARLY_SEC:
			self._intro_skip_settle_ready = True
			return True
		if elapsed < _INTRO_SKIP_SETTLE_SEC:
			self._intro_skip_last_curr = curr
			return False
		if last is not None and abs(curr - last) <= 3:
			self._intro_skip_settle_ready = True
			return True
		if elapsed >= _INTRO_SKIP_SETTLE_MAX_WAIT_SEC:
			self._intro_skip_settle_ready = True
			return True
		self._intro_skip_last_curr = curr
		return False

	def _intro_skip_past_segment(self, segment):
		try:
			end_sec = float(segment['end_sec'])
			curr = self._intro_effective_playhead()
			if getattr(self, '_intro_skip_approved', False) and curr < end_sec + _INTRO_SKIP_POST_END_GRACE_SEC:
				return False
			if curr >= end_sec:
				return True
		except: pass
		return False

	def _execute_intro_skip_seek(self, start_sec, end_sec, source):
		if not self._player_is_active():
			self._log_intro_skip('Intro skip failed: player inactive')
			return False
		if not self.seek(end_sec, False):
			self._log_intro_skip('Intro skip failed: seek rejected')
			return False
		try:
			ku.sleep(400)
			actual = float(self.getTime())
			if abs(actual - end_sec) > 8:
				if not self.seek(end_sec, False):
					self._log_intro_skip('Intro skip failed: seek did not stick (at %.1fs, wanted %.1fs)' % (actual, end_sec))
					return False
				ku.sleep(400)
				actual = float(self.getTime())
				if abs(actual - end_sec) > 8:
					self._log_intro_skip('Intro skip failed: seek did not stick (at %.1fs, wanted %.1fs)' % (actual, end_sec))
					return False
		except Exception as exc:
			self._log_intro_skip('Intro skip failed: seek verify (%s)' % exc)
			return False
		self._log_intro_skip('Intro skip (%s): %.1fs -> %.1fs' % (source, start_sec, end_sec))
		return True

	def _prompt_intro_skip(self):
		if not self._player_is_active():
			return False
		try:
			from windows.base_window import open_window
			return open_window(('windows.playback_notifications', 'IntroSkipPrompt'), 'playback_notifications.xml',
				meta=self.meta, countdown_sec=_INTRO_SKIP_PROMPT_COUNTDOWN_SEC)
		except:
			return False

	def _maybe_apply_intro_skip(self):
		if not getattr(self, '_intro_skip_active', False) or getattr(self, '_intro_skip_done', False):
			return
		if not self._player_is_active():
			return
		self._try_intro_skip_chapters()
		segment = getattr(self, '_intro_skip_segment', None)
		if not segment:
			self._maybe_log_intro_skip_no_timing()
			return
		if self._intro_skip_past_segment(segment):
			if getattr(self, '_intro_skip_approved', False):
				self._log_intro_skip('Intro skip missed: past grace window')
			self._intro_skip_done = True
			return
		try:
			start_sec = float(segment['start_sec'])
			end_sec = float(segment['end_sec'])
			curr = float(self.curr_time)
		except:
			return
		if not getattr(self, '_intro_skip_prompt_answered', False) and st.skip_intro_needs_prompt(getattr(self.sources_object, 'play_type', '')):
			if not self._intro_skip_position_settled():
				return
			effective_curr = self._intro_effective_playhead()
			should_prompt = (start_sec <= _INTRO_SKIP_EARLY_START_SEC and effective_curr <= _INTRO_SKIP_PROMPT_EARLY_SEC) or (effective_curr >= start_sec and effective_curr < end_sec)
			if should_prompt:
				choice = self._prompt_intro_skip()
				self._intro_skip_prompt_answered = True
				if choice is None:
					self._intro_skip_done = True
					self._log_intro_skip('Intro skip: timed out')
					return
				if not choice:
					self._intro_skip_done = True
					self._log_intro_skip('Intro skip: declined')
					return
				self._intro_skip_approved = True
				try:
					curr = float(self.curr_time)
				except:
					return
		if not getattr(self, '_intro_skip_approved', False):
			return
		if self._intro_skip_past_segment(segment):
			self._log_intro_skip('Intro skip missed: past grace window')
			self._intro_skip_done = True
			return
		if curr < start_sec:
			return
		if curr >= end_sec:
			self._intro_skip_done = True
			self._log_intro_skip('Intro skip: already past intro (%.1fs >= %.1fs)' % (curr, end_sec))
			return
		try:
			if self._execute_intro_skip_seek(start_sec, end_sec, segment.get('source', '?')):
				self._intro_skip_done = True
		except Exception as exc:
			self._log_intro_skip('Intro skip failed: %s' % exc)
			self._intro_skip_done = True

	def run_subtitles(self):
		self.subs_searched = True
		self._clear_subtitle_end_cache()
		if not st.auto_enable_subs(): return
		if not self.imdb_id: return
		try:
			from indexers.subtitles import subtitle_notify_poster
			poster = subtitle_notify_poster(self.meta, self.media_type)
			season = self.season if self.media_type == 'episode' else None
			episode = self.episode if self.media_type == 'episode' else None
			year = getattr(self, 'year', None)
			playing_filename = getattr(self, 'playing_filename', None)
			playing_item = getattr(self, 'playing_item', None)
			if st.submaker_enabled():
				from indexers.subtitles import Subtitles
				Thread(target=Subtitles().run, args=(self.imdb_id, season, episode, poster, playing_filename, playing_item, self)).start()
			elif st.opensubs_enabled():
				from indexers.subtitles import OpenSubtitlesSubs
				Thread(target=OpenSubtitlesSubs().run, args=(self.imdb_id, season, episode, poster, year, playing_filename, playing_item, self)).start()
		except: pass

	def set_playback_properties(self):
		try:
			trakt_ids = {'tmdb': self.tmdb_id, 'imdb': self.imdb_id, 'slug': make_trakt_slug(self.title)}
			if self.media_type == 'episode': trakt_ids['tvdb'] = self.tvdb_id
			ku.set_property('script.trakt.ids', json.dumps(trakt_ids))
			if self.playing_filename or getattr(self, 'playing_item', None):
				try:
					from indexers.subtitles import _best_play_filename
					season = self.season if self.media_type == 'episode' else None
					episode = self.episode if self.media_type == 'episode' else None
					best = _best_play_filename(self.playing_filename, getattr(self, 'playing_item', None), season, episode)
					ku.set_property('subs.player_filename', best or self.playing_filename)
				except:
					if self.playing_filename: ku.set_property('subs.player_filename', self.playing_filename)
			elif self.playing_filename:
				ku.set_property('subs.player_filename', self.playing_filename)
		except: pass

	def safe_stop(self):
		try:
			opening = ku.get_property(PROP_PLAY_OPENING) == 'true'
			if opening and not self.isPlayingVideo() and not ku.get_visibility('Window.IsActive(fullscreenvideo)'):
				ku.execute_builtin('PlayerControl(Stop)', block=False)
				return
			if self.isPlayingVideo() or ku.get_visibility('Window.IsActive(fullscreenvideo)'):
				if self.isPlaying():
					self.stop()
				ku.sleep(150)
			elif self.isPlaying():
				ku.execute_builtin('PlayerControl(Stop)', block=False)
				ku.sleep(100)
		except:
			pass
		finally:
			ku.clear_property(PROP_PLAY_OPENING)

	def clear_playback_properties(self, clear_navigation=True):
		if clear_navigation:
			ku.clear_property('redlight.window_stack')
		ku.clear_property('script.trakt.ids')
		ku.clear_property('subs.player_filename')
		try:
			from indexers.subtitles import clear_active_subtitle_path
			clear_active_subtitle_path()
		except: pass

	def run_error(self, message=None):
		ku.clear_property(PROP_PLAY_OPENING)
		try:
			if not self.is_generic:
				self.sources_object.playback_successful = False
		except:
			pass
		self.clear_playback_properties(clear_navigation=not self.is_generic)
		if self.is_generic and ku.get_property('redlight.browse_playback') == 'true':
			return ku.notification('Playback Failed', 4000, settle_ms=400)
		# play_file walks the resolve queue and calls playback_failed_action after the last attempt.
		if not self.is_generic and getattr(self, 'sources_object', None):
			return
		text = message or 'This link could not be played. It may be expired, removed, or unsupported on this device.'
		ku.hide_busy_dialog()
		ku.sleep(400)
		try:
			return ku.kodi_dialog().ok('Playback failed', text)
		except Exception:
			try:
				return ku.ok_dialog(heading='Playback failed', text=text)
			except Exception:
				return ku.notification('Playback Failed', 4000, settle_ms=400)
