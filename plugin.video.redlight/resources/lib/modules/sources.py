# -*- coding: utf-8 -*-
import json
import os
import pickle
import time
from threading import Thread, current_thread
from windows.base_window import open_window, create_window
from caches.episode_groups_cache import episode_groups_cache
from caches.settings_cache import get_setting
from scrapers import external, folders
from modules import debrid, kodi_utils, settings, metadata, watched_status
from modules.player import RedLightPlayer
from modules.source_utils import get_cache_expiry, make_alias_dict, include_exclude_filters, get_file_info, release_info_format
from modules.utils import clean_file_name, string_to_float, safe_string, remove_accents, get_datetime, append_module_to_syspath, manual_function_import
# logger = kodi_utils.logger

PROP_SOURCES_BUSY = 'redlight.sources_busy'
PROP_SOURCES_OWNER = 'redlight.sources_busy_owner'
PROP_RESOLVE_BUSY = 'redlight.resolve_busy'
PROP_RESOLVE_OWNER = 'redlight.resolve_busy_owner'
PROP_RESOLVE_CANCEL = 'redlight.resolve_cancelled'
PROP_PLAY_OPENING = 'redlight.play_opening'
PROP_BROWSE_RETURN_SOURCES = 'redlight.browse_return_sources'
PROP_NEXTEP_SCRAPE_READY = 'redlight.nextep_scrape_ready'
PROP_NEXTEP_SCRAPE_KEY = 'redlight.nextep_scrape_key'
PROP_NEXTEP_AUTOPLAY_CANCELLED = 'redlight.nextep_autoplay_cancelled'
PROP_AUTOSCRAPE_NEXTEP_READY = 'redlight.autoscrape_nextep_ready'
PROP_RANDOM_CONTINUAL_SKIP_ATTEMPTS = 'redlight.random_continual_skip_attempts'
RANDOM_CONTINUAL_MAX_SKIPS = 25
_NEXTEP_AUTOPLAY_STASH = {}
_NEXTEP_PLAY_STASH_PATH = None

def _nextep_play_stash_path():
	global _NEXTEP_PLAY_STASH_PATH
	if not _NEXTEP_PLAY_STASH_PATH:
		_NEXTEP_PLAY_STASH_PATH = os.path.join(kodi_utils.addon_profile(), 'nextep_play_stash.pkl')
	return _NEXTEP_PLAY_STASH_PATH

def persist_nextep_play_stash(stash):
	try:
		with open(_nextep_play_stash_path(), 'wb') as handle:
			pickle.dump(stash, handle, protocol=2)
		return True
	except Exception as exc:
		kodi_utils.logger('Red Light', 'Autoplay next episode stash persist failed: %s' % exc)
		return False

def consume_persisted_nextep_play_stash():
	path = _nextep_play_stash_path()
	try:
		if not os.path.isfile(path):
			return None
		with open(path, 'rb') as handle:
			stash = pickle.load(handle)
		os.remove(path)
		return stash
	except Exception as exc:
		kodi_utils.logger('Red Light', 'Autoplay next episode stash load failed: %s' % exc)
		try: os.remove(path)
		except: pass
		return None

def schedule_nextep_stashed_play(stash, show_busy=None):
	if not stash or not persist_nextep_play_stash(stash):
		return False
	if show_busy is None:
		# DialogBusy is torn down when fullscreen closes; prefer the resolve modal while still playing.
		show_busy = not kodi_utils.get_visibility('Window.IsActive(fullscreenvideo)')
	if show_busy and not kodi_utils.get_visibility('Window.IsActive(busydialognocancel)'):
		kodi_utils.show_busy_dialog()
	try:
		meta = stash.get('meta') or {}
		kodi_utils.logger('Red Light', 'Autoplay next episode play: scheduled resolve for %s S%02dE%02d' % (
			meta.get('title', ''), meta.get('season', 0), meta.get('episode', 0)))
	except:
		pass
	play_key = settings.playback_key()
	kodi_utils.run_plugin({'mode': 'playback.%s' % play_key, play_key: play_key, 'nextep_stash_play': 'true'})
	return True

def _nextep_stash_key(meta):
	try:
		return '%s_%s_%s' % (meta.get('tmdb_id'), int(meta.get('season')), int(meta.get('episode')))
	except:
		return None

def peek_nextep_autoplay_stash():
	key = kodi_utils.get_property(PROP_NEXTEP_SCRAPE_KEY)
	if not key: return None
	return _NEXTEP_AUTOPLAY_STASH.get(key)

def nextep_autoplay_cancelled():
	return kodi_utils.get_property(PROP_NEXTEP_AUTOPLAY_CANCELLED) == 'true'

def mark_nextep_autoplay_cancelled():
	kodi_utils.set_property(PROP_NEXTEP_AUTOPLAY_CANCELLED, 'true')
	clear_nextep_autoplay_stash()
	clear_orphan_nextep_play_stash()

def clear_nextep_autoplay_cancelled():
	kodi_utils.clear_property(PROP_NEXTEP_AUTOPLAY_CANCELLED)

def stash_nextep_autoplay_results(results, meta, nextep_settings, params):
	if nextep_autoplay_cancelled():
		return False
	key = _nextep_stash_key(meta)
	if not key: return False
	_NEXTEP_AUTOPLAY_STASH[key] = {'results': list(results), 'meta': dict(meta), 'nextep_settings': dict(nextep_settings or {}), 'params': dict(params or {})}
	kodi_utils.set_property(PROP_NEXTEP_SCRAPE_KEY, key)
	kodi_utils.set_property(PROP_NEXTEP_SCRAPE_READY, 'true')
	return True

def take_nextep_autoplay_stash(clear_only=False):
	key = kodi_utils.get_property(PROP_NEXTEP_SCRAPE_KEY)
	kodi_utils.clear_property(PROP_NEXTEP_SCRAPE_READY)
	kodi_utils.clear_property(PROP_NEXTEP_SCRAPE_KEY)
	if not key: return None
	if clear_only:
		_NEXTEP_AUTOPLAY_STASH.pop(key, None)
		return None
	return _NEXTEP_AUTOPLAY_STASH.pop(key, None)

def clear_nextep_autoplay_stash():
	_NEXTEP_AUTOPLAY_STASH.clear()
	kodi_utils.clear_property(PROP_NEXTEP_SCRAPE_READY)
	kodi_utils.clear_property(PROP_NEXTEP_SCRAPE_KEY)

def clear_orphan_nextep_play_stash():
	try:
		path = _nextep_play_stash_path()
		if os.path.isfile(path):
			os.remove(path)
	except:
		pass

class Sources():
	def __init__(self):
		self.params = {}
		self.prescrape_scrapers, self.prescrape_threads, self.prescrape_sources, self.prescrape_ran_scrapers, self.uncached_results, self.orig_results = [], [], [], set(), [], []
		self.threads, self.providers, self.sources, self.internal_scraper_names, self.remove_scrapers = [], [], [], [], ['external']
		self.clear_properties, self.filters_ignored, self.active_folders, self.resolve_dialog_made, self.episode_group_used = True, False, False, False, False
		self.sources_total = self.sources_4k = self.sources_1080p = self.sources_720p = self.sources_sd = 0
		self.prescrape, self.disabled_ext_ignored = False, False
		self.ext_name, self.ext_folder = '', ''
		self.external_modules = []
		self.progress_dialog, self.progress_thread = None, None
		self.playing_filename = ''
		self._resolve_user_cancelled, self.cancel_all_playback = False, False
		self.count_tuple = (('sources_4k', '4K', self._quality_length), ('sources_1080p', '1080p', self._quality_length), ('sources_720p', '720p', self._quality_length),
							('sources_sd', '', self._quality_length_sd), ('sources_total', '', self._quality_length_final))
		self.filter_keys = include_exclude_filters()
		self.filter_keys.pop('hybrid')
		self.default_internal_scrapers = ('easynews', 'aiostreams', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud', 'folders')
		self.debrids = {'Real-Debrid': ('apis.real_debrid_api', 'RealDebridAPI'), 'rd_cloud': ('apis.real_debrid_api', 'RealDebridAPI'),
		'rd_browse': ('apis.real_debrid_api', 'RealDebridAPI'), 'Premiumize.me': ('apis.premiumize_api', 'PremiumizeAPI'), 'pm_cloud': ('apis.premiumize_api', 'PremiumizeAPI'),
		'pm_browse': ('apis.premiumize_api', 'PremiumizeAPI'), 'AllDebrid': ('apis.alldebrid_api', 'AllDebridAPI'), 'ad_cloud': ('apis.alldebrid_api', 'AllDebridAPI'),
		'ad_browse': ('apis.alldebrid_api', 'AllDebridAPI'), 'Offcloud': ('apis.offcloud_api', 'OffcloudAPI'), 'oc_cloud': ('apis.offcloud_api', 'OffcloudAPI'),
		'oc_browse': ('apis.offcloud_api', 'OffcloudAPI'), 'TorBox': ('apis.torbox_api', 'TorBoxAPI'), 'tb_cloud': ('apis.torbox_api', 'TorBoxAPI'),
		'tb_browse': ('apis.torbox_api', 'TorBoxAPI')}
		self.retry_actions = settings.rescrape_settings()

	def _playback_already_active(self):
		try:
			player = kodi_utils.kodi_player()
			if player.isPlayingVideo() or player.isPlaying():
				return True
		except:
			pass
		try:
			if kodi_utils.get_visibility('Window.IsActive(fullscreenvideo)'):
				return True
		except:
			pass
		return False

	def _close_sources_results_window(self):
		try:
			kodi_utils.close_dialog('sources_results.xml')
			kodi_utils.sleep(200)
		except:
			pass

	def _random_playback(self):
		return any((self.random, self.random_continual, self.play_type == 'random_continual'))

	def _explicit_autoplay_request(self):
		return 'autoplay' in self.params and self.params.get('autoplay', 'false') == 'true'

	def _effective_autoplay(self):
		if not self.autoplay:
			return False
		if self._explicit_autoplay_request() or self.cloud_prescrape_autoplay or self._random_playback():
			return True
		return settings.auto_play(self.media_type)

	def playback_prep(self, params=None):
		if params: self.params = params
		params_get = self.params.get
		# Background next-episode prep runs while the current episode is still playing;
		# do not dismiss the end-of-episode busy cover (or other playback busy state).
		if params_get('nextep_stash_play') != 'true' and not (
			params_get('background', 'false') == 'true'
			and params_get('play_type', '') in ('autoplay_nextep', 'autoscrape_nextep', 'random_continual')
		):
			kodi_utils.hide_busy_dialog()
		if params_get('nextep_stash_play') == 'true':
			stash = consume_persisted_nextep_play_stash()
			if not stash:
				kodi_utils.logger('Red Light', 'Autoplay next episode play: no persisted stash')
				return
			self.params = dict(stash.get('params') or {})
			self.params['background'] = 'false'
			self.params['nextep_stash_play'] = 'true'
			self.params['play_type'] = 'autoplay_nextep'
			self._nextep_stash_results = list(stash.get('results') or [])
			self._nextep_stash_settings = dict(stash.get('nextep_settings') or {})
			self._nextep_alert_handled = True
			params_get = self.params.get
		self.background = params_get('background', 'false') == 'true'
		if not self.background and params_get('nextep_stash_play') != 'true' and self._playback_already_active():
			return
		self.play_type = params_get('play_type', '')
		if 'prescrape' in self.params:
			self.prescrape = params_get('prescrape') == 'true'
		else:
			self.prescrape = False
		self.random, self.random_continual = params_get('random', 'false') == 'true', params_get('random_continual', 'false') == 'true'
		if 'external_cache_check' in self.params: self.cache_check_override = params_get('external_cache_check') == 'true'
		else: self.cache_check_override = None
		if self.play_type:
			if self.play_type == 'autoplay_nextep': self.autoplay_nextep, self.autoscrape_nextep = True, False
			elif self.play_type == 'random_continual': self.autoplay_nextep, self.autoscrape_nextep = False, False
			else: self.autoplay_nextep, self.autoscrape_nextep = False, True
		else: self.autoplay_nextep, self.autoscrape_nextep = settings.autoplay_next_episode(), settings.autoscrape_next_episode()
		self.autoscrape = self.autoscrape_nextep and self.background		
		self.ignore_scrape_filters = params_get('ignore_scrape_filters', 'false') == 'true'
		self.nextep_settings, self.disable_autoplay_next_episode = params_get('nextep_settings', {}), params_get('disable_autoplay_next_episode', 'false') == 'true'
		if getattr(self, '_nextep_stash_settings', None):
			self.nextep_settings = self._nextep_stash_settings
		self.disabled_ext_ignored = params_get('disabled_ext_ignored', self.disabled_ext_ignored) == 'true'
		self.folders_ignore_filters = get_setting('redlight.results.folders_ignore_filters', 'false') == 'true'
		self.filter_size_method = int(get_setting('redlight.results.filter_size_method', '0'))
		self.media_type, self.tmdb_id = params_get('media_type'), params_get('tmdb_id')		
		self.custom_title, self.custom_year = params_get('custom_title', None), params_get('custom_year', None)
		self.episode_group_label, self.episode_id = params_get('episode_group_label', ''), params_get('episode_id', None)
		self.playcount, self.watch_count = params_get('playcount', None), params_get('watch_count', 1)
		if self.media_type == 'episode':
			self.season, self.episode = int(params_get('season')), int(params_get('episode'))
			self.custom_season, self.custom_episode = params_get('custom_season', None), params_get('custom_episode', None)
			self.check_episode_group()
		else: self.season, self.episode, self.custom_season, self.custom_episode = '', '', '', ''
		if 'autoplay' in self.params: self.autoplay = params_get('autoplay', 'false') == 'true'
		else: self.autoplay = settings.auto_play(self.media_type)
		if self._random_playback(): self.autoplay = True
		self.cloud_prescrape_autoplay = False
		self._playback_failed_notified = False
		self.get_meta()
		self.determine_scrapers_status()
		if not self.prescrape and not self._playback_skips_prescrape_override() and settings.prescrape_enabled(self.media_type, self.active_internal_scrapers):
			self.prescrape = True
		self.sleep_time, self.provider_sort_ranks, self.scraper_settings = 100, settings.provider_sort_ranks(), settings.scraping_settings()
		self.include_prerelease_results = settings.include_prerelease_results()
		self.limit_resolve = settings.limit_resolve()
		self.weight_size = settings.size_sort_weighted()
		self.sort_function, self.quality_filter = settings.results_sort_order(), self._quality_filter()
		self.include_unknown_size = get_setting('redlight.results.size_unknown', 'false') == 'true'
		self.make_search_info()
		if self.background and self.play_type in ('autoplay_nextep', 'autoscrape_nextep', 'random_continual'):
			self._log_nextep_scrape_started()
			self._prefetch_nextep_segment_data()
		if self.background and self.play_type == 'random_continual' and not self.nextep_settings:
			self.nextep_settings = {'watching_check': settings.auto_nextep_settings('autoplay_nextep')['watching_check']}
		if self.background and (self.autoplay_nextep or self.play_type == 'random_continual') and self.nextep_settings and not getattr(self, '_nextep_alert_handled', False):
			if not self.still_watching_check():
				self._decline_nextep_prep('still watching')
				kodi_utils.notification('Cancel Autoplay', icon=self.meta.get('poster'))
				return
		if getattr(self, '_nextep_stash_results', None):
			try:
				kodi_utils.logger('Red Light', 'Autoplay next episode play: starting resolve for %s S%02dE%02d' % (
					self.meta.get('title', ''), self.season, self.episode))
			except:
				pass
			return self.play_file(self._nextep_stash_results)
		if self.autoscrape: self.autoscrape_nextep_handler()
		else: return self.get_sources()

	def check_episode_group(self):
		try:
			if any([self.custom_season, self.custom_episode]) or 'skip_episode_group_check' in self.params: return
			group_info = episode_groups_cache.get(self.tmdb_id)
			if not group_info: return
			group_details = metadata.group_episode_data(metadata.group_details(group_info['id']), self.episode_id, self.season, self.episode)
			if group_details:
				self.custom_season, self.custom_episode, self.episode_group_used = group_details['season'], group_details['episode'], True
				self.episode_group_label = '[B]CUSTOM GROUP: S%02dE%02d[/B]' % (self.custom_season, self.custom_episode)
		except: self.custom_season, self.custom_episode = None, None

	def determine_scrapers_status(self):
		self.active_internal_scrapers = settings.active_internal_scrapers()
		if not 'external' in self.active_internal_scrapers and self.disabled_ext_ignored: self.active_internal_scrapers.append('external')
		self.active_external = 'external' in self.active_internal_scrapers
		if self.active_external:
			self.debrid_enabled = debrid.debrid_enabled()
			if not self.debrid_enabled:
				return self.disable_external('No Debrid Services Enabled' if all(scraper == 'external' for scraper in self.active_internal_scrapers) else 'EN used only')
			self.external_modules = settings.active_external_modules()
			if not self.external_modules: return self.disable_external('Error Importing External Module')
			self.ext_folder = self.external_modules[0]['module_id']
			self.ext_name = self.external_modules[0]['folder_name']

	def _any_cache_check_active(self):
		if self.cache_check_override is not None:
			return self.cache_check_override
		return settings.any_external_cache_check()

	def _playback_skips_prescrape_override(self):
		if self.play_type == 'autoscrape_nextep': return True
		if self.disabled_ext_ignored or self.ignore_scrape_filters: return True
		if 'disabled_ext_ignored' in self.params or 'ignore_scrape_filters' in self.params: return True
		return False

	def _background_nextep_scrape(self):
		return self.background and self.play_type in ('autoplay_nextep', 'autoscrape_nextep')

	def _allow_concurrent_scrape(self):
		if self.autoscrape and self.background:
			return True
		if self.background and self.play_type == 'random_continual':
			return True
		return self._background_nextep_scrape()

	def get_sources(self):
		depth = getattr(self, '_get_sources_depth', 0)
		if depth == 0:
			allow_concurrent = self._allow_concurrent_scrape()
			self._clear_stale_resolve_busy()
			if kodi_utils.get_property(PROP_RESOLVE_BUSY) == 'true' and not allow_concurrent:
				if not self.background:
					kodi_utils.notification('Resolve or playback in progress.', 2500)
				return
			if kodi_utils.get_property(PROP_SOURCES_BUSY) == 'true' and not allow_concurrent:
				if not self.background:
					kodi_utils.notification('Source search already running.', 2500)
				return
			self._scrape_user_cancelled = False
			self._sources_busy_owner = str(id(self))
			kodi_utils.set_property(PROP_SOURCES_BUSY, 'true')
			kodi_utils.set_property(PROP_SOURCES_OWNER, self._sources_busy_owner)
		self._get_sources_depth = depth + 1
		try:
			if depth == 0:
				self._log_prescrape_settings()
			if not self.progress_dialog and not self.background: self._make_progress_dialog()
			results = []
			self.check_prescrape_ran = False
			if self.prescrape and any(x in self.active_internal_scrapers for x in self.default_internal_scrapers):
				if self.prepare_internal_scrapers():
					results = self.collect_prescrape_results()
					self.check_prescrape_ran = bool(self.prescrape_scrapers)
					if results:
						results = self.process_results(results)
						if not self._can_continue_full_scrape(): self.prescrape = False
			if self._user_cancelled_scrape():
				return self._finish_scrape_cancel()
			if not results:
				if self.check_prescrape_ran and self._can_continue_full_scrape():
					self._reset_scrape_progress_counts()
					if self.progress_dialog:
						try:
							self.progress_dialog.update_scraper(0, 0, 0, 0, 0, '', 0)
						except:
							pass
					elif not self.background:
						self._make_progress_dialog()
					self._refresh_results_settings()
				if not settings.auto_play(self.media_type) and not self.cloud_prescrape_autoplay and not self._random_playback() and not self._explicit_autoplay_request():
					self.autoplay = False
				self.prescrape = False
				self._release_empty_prescrape_cloud_scrapers()
				self.prepare_internal_scrapers()
				if self.active_external: self.activate_external_providers()
				elif not self.active_internal_scrapers: self._kill_progress_dialog()
				self.orig_results = self.collect_results()
				if self._user_cancelled_scrape():
					return self._finish_scrape_cancel()
				if not self.orig_results: self._kill_progress_dialog()
				results = self.process_results(self.orig_results)
			if self._user_cancelled_scrape():
				return self._finish_scrape_cancel()
			if not results:
				return self._process_post_results()
			if self.autoscrape: return results
			else: return self.play_source(results)
		finally:
			self._get_sources_depth = max(0, getattr(self, '_get_sources_depth', 1) - 1)
			if self._get_sources_depth == 0:
				self._release_sources_busy()

	def collect_results(self):
		if self.prescrape_sources:
			self.sources.extend(self.prescrape_sources)
		self._quality_poll_scrapers = set()
		self.cloud_scraper_names = []
		threads_append = self.threads.append
		if self.active_external:
			prescrape_ran = getattr(self, 'prescrape_ran_scrapers', set()) or set()
			early_cloud = [i for i in self.internal_sources(cloud_early=True) if i[2] not in prescrape_ran]
			if early_cloud:
				self.cloud_scraper_names = [i[2] for i in early_cloud]
				for i in early_cloud:
					threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], False), name=i[2]))
				self.remove_scrapers.extend(i[2] for i in early_cloud)
		if self.active_folders: self.append_folder_scrapers(self.providers)
		self.providers.extend(self.internal_sources())
		if self.providers:
			for i in self.providers: threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], False), name=i[2]))
		if self.threads:
			[i.start() for i in self.threads]
		if self._user_cancelled_scrape():
			return []
		if self.active_external or self.background:
			if self.active_external:
				# Cloud scrapers in remove_scrapers run in parallel threads; do not poll their
				# window properties on the external progress bar (was showing TB_CLOUD etc. for the full timeout).
				external_progress_scrapers = [i for i in self.internal_scraper_names if i not in self.remove_scrapers]
				self.external_args = (self.meta, self.external_providers, self.debrid_enabled, self.cache_check_override, external_progress_scrapers,
										self.prescrape_sources, self.progress_dialog, self.disabled_ext_ignored, self.cloud_scraper_names, self.external_orchestration())
				self.activate_providers('external', external, False)
			if self._user_cancelled_scrape():
				return []
			if self.threads:
				self._wait_for_cloud_threads()
				self._absorb_internal_properties()
		elif self.active_internal_scrapers: self.scrapers_dialog()
		if self._user_cancelled_scrape():
			return []
		if self.threads:
			self._join_internal_threads(6)
			self._absorb_internal_properties()
		return self.sources

	def collect_prescrape_results(self):
		threads_append = self.prescrape_threads.append
		folder_prescrape = False
		if self.active_folders:
			if settings.check_prescrape_sources('folders', self.media_type):
				self.append_folder_scrapers(self.prescrape_scrapers)
				folder_prescrape = True
		self.prescrape_scrapers.extend(self.internal_sources(True))
		if not self.prescrape_scrapers and not folder_prescrape: return []
		for i in self.prescrape_scrapers: threads_append(Thread(target=self.activate_providers, args=(i[0], i[1], True), name=i[2]))
		[i.start() for i in self.prescrape_threads]
		if self.background: [i.join() for i in self.prescrape_threads]
		else: self.scrapers_dialog()
		for i in self.prescrape_scrapers:
			scraper_name = i[2]
			if scraper_name not in self.remove_scrapers:
				self.remove_scrapers.append(scraper_name)
		if folder_prescrape and 'folders' not in self.remove_scrapers:
			self.remove_scrapers.append('folders')
		self.prescrape_ran_scrapers = {i[2] for i in self.prescrape_scrapers}
		return self.prescrape_sources

	def process_results(self, results):
		if not results: return results
		results = self.sort_results(results)
		min_seeders = settings.uncached_min_seeders()
		all_uncached_results = [i for i in results if 'Uncached' in i.get('cache_provider', '')]
		self.uncached_results = [i for i in all_uncached_results if int(i.get('seeders', '0')) >= min_seeders]
		uncached_in_main = []
		if settings.include_uncached_torbox():
			uncached_in_main.extend([i for i in self.uncached_results if 'TorBox' in i.get('cache_provider', '')])
		if settings.include_uncached_offcloud():
			uncached_in_main.extend([i for i in self.uncached_results if 'Offcloud' in i.get('cache_provider', '')])
		if settings.include_uncached_premiumize():
			uncached_in_main.extend([i for i in self.uncached_results if 'Premiumize' in i.get('cache_provider', '')])
		if uncached_in_main:
			strip_uncached = [i for i in all_uncached_results if i not in uncached_in_main]
			self.uncached_results = [i for i in self.uncached_results if i not in uncached_in_main]
		else:
			strip_uncached = all_uncached_results
		results = [i for i in results if i not in strip_uncached]
		cloud_scrapers = ('rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud')
		cloud_results = [i for i in results if i.get('scrape_provider') in cloud_scrapers]
		if self.ignore_scrape_filters: self.filters_ignored = True
		else:
			scrape_results = [i for i in results if i not in cloud_results]
			scrape_results = self.filter_results(scrape_results)
			scrape_results = self.filter_audio(scrape_results)
			for file_type in self.filter_keys: scrape_results = self.special_filter(scrape_results, file_type)
			results = scrape_results + cloud_results
		if self.prescrape:
			self.all_scrapers = self.active_internal_scrapers
			if self.autoplay:
				autoplay_results = self._prescrape_autoplay_candidates(results)
				if autoplay_results:
					self.cloud_prescrape_autoplay = True
					results = autoplay_results
		else:
			self.all_scrapers = list(set(self.active_internal_scrapers + self.remove_scrapers))
			kodi_utils.clear_property('fs_filterless_search')
		results = self.sort_preferred_filters(results)
		results = self.sort_first(results)
		pref_sort_ran = False
		if self._pref_sort_should_run() or any(i.get('pref_includes') for i in results):
			results = self._sort_with_pref_boost(results)
			pref_sort_ran = True
		if self.ignore_scrape_filters: return results
		combined = self._apply_result_limits(results, cloud_scrapers)
		if self._pin_scrapers_to_top_enabled():
			combined = self.sort_first(combined)
		elif not pref_sort_ran:
			combined = self.sort_results(combined)
		self._log_custom_sort_summary(combined, pref_sort_ran)
		return combined

	def _log_prescrape_settings(self):
		try:
			active = self.active_internal_scrapers or []
			check_scrapers = ('easynews', 'aiostreams', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud', 'folders', 'external')
			check = {s: settings.check_prescrape_sources(s, self.media_type) for s in active if s in check_scrapers}
			label = '%s tmdb=%s' % (self.media_type, self.tmdb_id)
			if self.media_type == 'episode':
				label += ' S%02dE%02d' % (self.season, self.episode)
			kodi_utils.logger('ScrapePrescrape', '%s prescrape=%s enabled=%s skip_override=%s autoplay=%s background=%s check=%s active=%s' % (
				label, self.prescrape, settings.prescrape_enabled(self.media_type, active),
				self._playback_skips_prescrape_override(), self.autoplay, self.background, check, active))
		except: pass

	def _log_custom_sort_summary(self, results, pref_sort_ran):
		try:
			if not results or not self._pref_sort_should_run(): return
			prefs = settings.preferred_filters()
			scored = sum(1 for i in results if i.get('pref_includes', 0) > 0)
			top = [(i.get('quality'), i.get('pref_includes', 0), i.get('scrape_provider'), (i.get('display_name') or i.get('name') or '')[:80]) for i in results[:15]]
			kodi_utils.logger('CustomSort', '%s tmdb=%s ran=%s prefs=%s scored=%s/%s top=%s' % (
				self.media_type, self.tmdb_id, pref_sort_ran, prefs, scored, len(results), top))
		except: pass

	def sort_results(self, results):
		results = [dict(i, **{
			'provider_rank': self._get_provider_rank(i['debrid'].lower()), 'quality_rank': self._get_quality_rank(i.get('quality', 'SD')),
			'size_rank': self._get_size_rank(i)}) for i in results]
		results.sort(key=self.sort_function)
		results = self._sort_uncached_results(results)
		return results

	def filter_results(self, results):
		if self.folders_ignore_filters:
			folder_results = [i for i in results if i['scrape_provider'] == 'folders']
			results = [i for i in results if not i in folder_results]
		else: folder_results = []
		results = [i for i in results if i['quality'] in self.quality_filter]
		if self.filter_size_method:
			min_size = string_to_float(get_setting('redlight.results.%s_size_min' % self.media_type, '0'), '0') / 1000
			if min_size == 0.0 and not self.include_unknown_size: min_size = 0.02
			if self.filter_size_method == 1:
				duration = self.meta['duration'] or (5400 if self.media_type == 'movie' else 2400)
				max_size = ((0.125 * (0.90 * string_to_float(get_setting('results.line_speed', '25'), '25'))) * duration)/1000
			elif self.filter_size_method == 2:
				max_size = string_to_float(get_setting('redlight.results.%s_size_max' % self.media_type, '10000'), '10000') / 1000
			results = [i for i in results if i['scrape_provider'] == 'folders' or i['scrape_provider'] in ('rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud') or min_size <= i['size'] <= max_size]
		results += folder_results
		return results

	def filter_audio(self, results):
		a_filters = settings.audio_filters()
		return [i for i in results if not any(x in i['extraInfo'] for x in a_filters)]

	def special_filter(self, results, file_type):
		enable_setting, key = settings.filter_status(file_type), self.filter_keys[file_type]
		if key == 'HEVC' and enable_setting == 0:
			hevc_max_quality = self._get_quality_rank(get_setting('redlight.filter.hevc.%s' % ('max_autoplay_quality' if self.autoplay else 'max_quality'), '4K'))
			results = [i for i in results if not self._extra_info_has_tag(i['extraInfo'], key) or i['quality_rank'] >= hevc_max_quality]
		if enable_setting == 1:
			if key in ('D/VISION', 'HDR'):
				if not settings.filter_status({'D/VISION': 'hdr', 'HDR': 'dv'}[key]) == 0: results = [i for i in results if not self._extra_info_has_tag(i['extraInfo'], key)]
				else: results = [i for i in results if not (self._extra_info_has_tag(i['extraInfo'], key) and not self._extra_info_has_tag(i['extraInfo'], 'HYBRID'))]
			else: results = [i for i in results if not self._extra_info_has_tag(i['extraInfo'], key)]
		return results

	def _normalize_pref_tag(self, tag):
		key = (tag or '').lower().replace('[b]', '').replace('[/b]', '').strip()
		if key in self.filter_keys: return self.filter_keys[key]
		aliases = {'d/vision': 'D/VISION', 'dolby vision': 'D/VISION', 'hdr': 'HDR', 'high dynamic range (hdr)': 'HDR', 'dolby atmos': 'ATMOS', 'atmos': 'ATMOS', 'hevc (x265)': 'HEVC', 'hevc': 'HEVC'}
		return aliases.get(key, tag)

	def _parse_extra_info_tags(self, extra_info):
		tags = []
		if not extra_info: return tags
		items = extra_info if isinstance(extra_info, list) else [extra_info]
		for item in items:
			if not item: continue
			for part in str(item).split(' | '):
				part = part.replace('[B]', '').replace('[/B]', '').strip()
				if part: tags.append(part)
		return tags

	def _pref_tag_in_extra_info(self, tag, extra_info):
		if not tag or not extra_info: return False
		normalized = self._normalize_pref_tag(tag)
		for part in self._parse_extra_info_tags(extra_info):
			part_norm = self._normalize_pref_tag(part)
			if part_norm == normalized or part == tag or part == normalized: return True
		return False

	def _extra_info_has_tag(self, extra_info, tag):
		return self._pref_tag_in_extra_info(tag, extra_info)

	def _normalized_title_blob(self, item):
		parts = [item.get('name'), item.get('display_name')]
		extra = item.get('extraInfo', '')
		if extra: parts.append(' | '.join(extra) if isinstance(extra, list) else extra)
		return ' '.join(' '.join([i for i in parts if i]).lower().split())

	def _all_extra_info_tags(self, item):
		tags = []
		existing = item.get('extraInfo', '')
		if isinstance(existing, list): tags.extend(existing)
		elif existing: tags.append(existing)
		for field in ('name', 'display_name'):
			raw = item.get(field)
			if not raw: continue
			try:
				_, info = get_file_info(name_info=release_info_format(raw))
				if isinstance(info, list): tags.extend(info)
			except: pass
		return tags

	def _explicit_sdr_release(self, item):
		blob = self._normalized_title_blob(item)
		if ' sdr ' in f' {blob} ' or blob.startswith('sdr '): return True
		return 'SDR' in self._all_extra_info_tags(item)

	def _pref_tag_in_result(self, tag, item):
		if self._pref_tag_in_extra_info(tag, item.get('extraInfo', '')): return True
		if self._pref_tag_in_extra_info(tag, self._all_extra_info_tags(item)): return True
		if self._explicit_sdr_release(item): return False
		normalized = self._normalize_pref_tag(tag)
		blob = self._normalized_title_blob(item)
		if normalized == 'D/VISION' and any(x in blob for x in ('dolby vision', 'dolbyvision', ' dovi ', ' dv ', 'dovi', 'profile 8', 'profile8')): return True
		if normalized == 'ATMOS' and ('atmos' in blob or ('ddp' in blob and 'atmos' in blob)): return True
		if normalized == 'HDR':
			if any(x in blob.split() for x in ('hdrip', 'hd.rip')): return False
			if any(x in blob for x in ('hdr10', 'hdr10+', 'hdr10p')): return True
			return ' hdr ' in f' {blob} '
		return False

	def sort_preferred_filters(self, results):
		if self._pref_sort_should_run():
			try:
				preferences = settings.preferred_filters()
				if not preferences: return results
				preferences = [self._normalize_pref_tag(i) for i in preferences]
				pref_weights = {0: 100, 1: 50, 2: 20, 3: 10, 4: 5, 5: 2}
				return [dict(i, **{'pref_includes': sum(pref_weights.get(preferences.index(x), 0) for x in preferences if self._pref_tag_in_result(x, i))}) for i in results]
			except: pass
		return results

	def _sort_with_pref_boost(self, results):
		results = [dict(i, **{
			'provider_rank': self._get_provider_rank(i['debrid'].lower()),
			'quality_rank': self._get_quality_rank(i.get('quality', 'SD')),
			'size_rank': self._get_size_rank(i)}) for i in results]
		groups = {}
		for item in results:
			groups.setdefault(item['quality_rank'], []).append(item)
		with_pref_all = []
		for quality_rank in sorted(groups.keys()):
			with_pref_all.extend([i for i in groups[quality_rank] if i.get('pref_includes', 0) > 0])
		with_pref_all.sort(key=lambda k: (-k.get('pref_includes', 0), k['quality_rank']) + self.sort_function(k)[1:])
		without_sorted = []
		for quality_rank in sorted(groups.keys()):
			without_pref = [i for i in groups[quality_rank] if i.get('pref_includes', 0) == 0]
			non_sdr = [i for i in without_pref if not self._explicit_sdr_release(i)]
			sdr = [i for i in without_pref if self._explicit_sdr_release(i)]
			non_sdr.sort(key=self.sort_function)
			sdr.sort(key=self.sort_function)
			without_sorted.extend(non_sdr + sdr)
		return self._sort_uncached_results(with_pref_all + without_sorted)

	def _custom_pref_sort_active(self):
		return self._pref_sort_should_run()

	def _pref_sort_should_run(self):
		if not settings.preferred_filters(): return False
		if int(get_setting('redlight.filter.sort_to_top', '0')) == 0: return False
		return settings.sort_to_top_filter(self.autoplay)

	def _pin_scrapers_to_top_enabled(self):
		if 'folders' in self.all_scrapers and settings.sort_to_top('folders'): return True
		return any(settings.sort_to_top(p) for p in ('rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud') if p in self.all_scrapers)

	def sort_first(self, results):
		try:
			sort_first_scrapers = []
			if 'folders' in self.all_scrapers and settings.sort_to_top('folders'): sort_first_scrapers.append('folders')
			sort_first_scrapers.extend([i for i in self.all_scrapers if i in ('rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud') and settings.sort_to_top(i)])
			if not sort_first_scrapers: return results
			sort_first = [i for i in results if i['scrape_provider'] in sort_first_scrapers]
			sort_first.sort(key=lambda k: (self._sort_folder_to_top(k['scrape_provider']), k['quality_rank']))
			sort_last = [i for i in results if not i in sort_first]
			results = sort_first + sort_last
		except: pass
		return results

	def _apply_result_limits(self, results, cloud_scrapers):
		if self.autoplay or self.ignore_scrape_filters: return results
		quality_limit = settings.limit_number_quality()
		total_limit = settings.limit_number_total()
		if not quality_limit and not total_limit: return results
		quality_counter_dict = {'4K': 0, '1080p': 0, '720p': 0, 'SD': 0, 'SCR': 0, 'CAM': 0, 'TELE': 0}
		limit_list, non_cloud_count = [], 0
		for i in results:
			if i.get('scrape_provider') in cloud_scrapers:
				limit_list.append(i)
				continue
			if quality_limit and quality_counter_dict[i['quality']] >= quality_limit: continue
			if total_limit and non_cloud_count >= total_limit: continue
			quality_counter_dict[i['quality']] += 1
			non_cloud_count += 1
			limit_list.append(i)
		return limit_list

	def limit_quality_numbers(self, results):
		if self.autoplay or self.ignore_scrape_filters: return results
		quality_limit = settings.limit_number_quality()
		if not quality_limit: return results
		quality_counter_dict, limit_list = {'4K': 0, '1080p': 0, '720p': 0, 'SD': 0, 'SCR': 0, 'CAM': 0, 'TELE': 0}, []
		for i in results:
			if quality_counter_dict[i['quality']] < quality_limit:
				quality_counter_dict[i['quality']] += 1
				limit_list.append(i)
		return limit_list

	def limit_quality_total(self, results):
		if self.autoplay or self.ignore_scrape_filters: return results
		total_limit = settings.limit_number_total()
		if not total_limit: return results
		return results[:total_limit]

	def prepare_internal_scrapers(self):
		if self.active_external and len(self.active_internal_scrapers) == 1:
			self.internal_scraper_names = [i for i in self.active_internal_scrapers if i != 'external']
			if self.clear_properties: self._clear_properties()
			return True
		active_internal_scrapers = [i for i in self.active_internal_scrapers if not i in self.remove_scrapers]
		if self.prescrape and not self.active_external and all([settings.check_prescrape_sources(i, self.media_type) for i in active_internal_scrapers]): return False
		if 'folders' in active_internal_scrapers:
			folder_info = self.get_folderscraper_info()
			self.folder_info = [i for i in folder_info if settings.source_folders_directory(self.media_type, i[1])]
			if self.folder_info:
				self.active_folders = True
				self.internal_scraper_names = [i for i in active_internal_scrapers if i not in ('folders', 'external')] + [i[0] for i in self.folder_info]
			else: self.internal_scraper_names = [i for i in active_internal_scrapers if i not in ('folders', 'external')]
		else:
			self.folder_info = []
			self.internal_scraper_names = [i for i in active_internal_scrapers if i != 'external']
		self.active_internal_scrapers = active_internal_scrapers
		if self.clear_properties: self._clear_properties()
		return True

	def activate_providers(self, module_type, function, prescrape):
		sources = self._get_module(module_type, function).results(self.search_info)
		if prescrape:
			if sources: self.prescrape_sources.extend(sources)
			return
		# Early cloud scrapers publish via window property only during external scrape.
		if current_thread().name in self.remove_scrapers:
			return
		if sources: self.sources.extend(sources)

	def activate_external_providers(self):
		self.external_providers = self.external_sources()
		if not self.external_providers: self.disable_external('No External Providers Enabled')

	def disable_external(self, line1=''):
		if line1: kodi_utils.notification(line1, 2000)
		try: self.active_internal_scrapers.remove('external')
		except: pass
		self.active_external, self.external_providers = False, []

	def internal_sources(self, prescrape=False, cloud_early=False):
		active_sources = [i for i in self.active_internal_scrapers if i in ['easynews', 'aiostreams', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud'] and i not in self.remove_scrapers]
		if not prescrape:
			prescrape_ran = getattr(self, 'prescrape_ran_scrapers', set()) or set()
			if prescrape_ran:
				active_sources = [i for i in active_sources if i not in prescrape_ran]
		if cloud_early:
			active_sources = [i for i in active_sources if settings.cloud_scrape_before_external(i)]
		else:
			active_sources = [i for i in active_sources if not (prescrape and not settings.check_prescrape_sources(i, self.media_type))]
		try: sourceDict = [('internal', manual_function_import('scrapers.%s' % i, 'source'), i) for i in active_sources]
		except: sourceDict = []
		return sourceDict

	def _can_continue_full_scrape(self):
		if self.active_external: return True
		remaining = [i for i in self.active_internal_scrapers if i not in self.remove_scrapers]
		return bool(remaining)

	def external_module_groups(self):
		groups = []
		for mod in getattr(self, 'external_modules', None) or settings.active_external_modules():
			append_module_to_syspath('special://home/addons/%s/lib' % mod['module_id'])
			try:
				sourceDict = manual_function_import(mod['folder_name'], 'sources')(specified_folders=['torrents'], ret_all=self.disabled_ext_ignored)
			except:
				sourceDict = []
			module_label = mod.get('display_name') or mod['folder_name']
			entries = []
			for item in sourceDict or []:
				try:
					provider, module_class = item[0], item[1]
					pack = item[2] if len(item) > 2 else ''
					cache_key = settings.external_scraper_cache_key(mod['module_id'], provider)
					thread_name = '%s [%s]' % (provider, module_label)
					entries.append((thread_name, module_class, pack, cache_key, provider, mod['module_id']))
				except: pass
			if entries:
				groups.append({'module_id': mod['module_id'], 'display_name': module_label, 'entries': entries})
		return groups

	def external_orchestration(self):
		groups = self.external_module_groups()
		if len(groups) <= 1: return None
		mode = settings.external_scraper_run_mode()
		if mode == '0': return None
		if mode == '1':
			return {'groups': groups, 'max_parallel': 1, 'skip_threshold': 0, 'early_stop': True, 'primary_dedicated': False, 'mode': 'series_fallback'}
		if mode == '2':
			return {'groups': groups, 'max_parallel': 1, 'skip_threshold': 0, 'early_stop': False, 'primary_dedicated': False, 'mode': 'series_full'}
		if mode == '3':
			return {'groups': groups, 'max_parallel': max(1, len(groups) - 1), 'skip_threshold': 0, 'early_stop': False, 'primary_dedicated': True, 'mode': 'primary_parallel'}
		return None

	def external_sources(self):
		merged = []
		for group in self.external_module_groups():
			merged.extend(group['entries'])
		return merged

	def folder_sources(self):
		def import_info():
			for item in self.folder_info:
				scraper_name = item[0]
				module = manual_function_import('scrapers.folders', 'source')
				yield ('folders', (module, (item[1], scraper_name, item[2])), scraper_name)
		sourceDict = list(import_info())
		try: sourceDict = list(import_info())
		except: sourceDict = []
		return sourceDict

	def _cloud_scrapers(self):
		return ('rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud')

	def _prescrape_autoplay_candidates(self, results):
		autoplay_scrapers = self._cloud_scrapers() + ('easynews',)
		return [i for i in results if i.get('scrape_provider') in autoplay_scrapers and settings.autoplay_prescrape(i['scrape_provider'])]

	def _is_cloud_result(self, item):
		return item.get('scrape_provider') in self._cloud_scrapers()

	def _external_autoplay_candidates(self, results):
		"""Global Autoplay Movie/Episode — external scrapers only, not debrid cloud library rows."""
		return [i for i in results if not self._is_cloud_result(i)]

	def _release_empty_prescrape_cloud_scrapers(self):
		"""Let cloud scrapers run again during full scrape when prescrape found nothing."""
		if not self.check_prescrape_ran: return
		prescrape_ran = getattr(self, 'prescrape_ran_scrapers', set()) or set()
		for scraper in self._cloud_scrapers():
			if scraper in prescrape_ran:
				continue
			if scraper in self.remove_scrapers and not any(r.get('scrape_provider') == scraper for r in self.prescrape_sources):
				self.remove_scrapers.remove(scraper)

	def _prepare_cloud_autoplay_resolve(self):
		"""Leave prescrape progress UI and open a clean resolver dialog for cloud autoplay."""
		self._kill_progress_dialog(join_timeout=1.0)
		if not self.background:
			self._make_progress_dialog()
		self.resolve_dialog_made = False

	def play_source(self, results):
		if self._user_cancelled_scrape():
			return self._finish_scrape_cancel()
		self._clear_stale_resolve_busy()
		if kodi_utils.get_property(PROP_RESOLVE_BUSY) == 'true':
			return
		if self.background:
			autoplay_queue = results
			if self._effective_autoplay():
				external = self._external_autoplay_candidates(results)
				if external: autoplay_queue = external
			if self.autoplay_nextep and not self.autoscrape_nextep:
				return self._stash_nextep_autoplay_play(autoplay_queue)
			return self.play_file(autoplay_queue)
		prescrape_autoplay = self._prescrape_autoplay_candidates(results) if self.autoplay else []
		if prescrape_autoplay:
			self.cloud_prescrape_autoplay = True
			self._last_cloud_autoplay_results = list(prescrape_autoplay)
			kodi_utils.logger('Red Light', 'Autoplay prescrape: %s hit(s) from %s' % (len(prescrape_autoplay), prescrape_autoplay[0].get('scrape_provider', '')))
			self._prepare_cloud_autoplay_resolve()
			return self.play_file(prescrape_autoplay)
		self.cloud_prescrape_autoplay = False
		if self.prescrape and any(self._is_cloud_result(i) for i in results):
			return self.display_results(results)
		if self._effective_autoplay():
			external = self._external_autoplay_candidates(results)
			if external:
				return self.play_file(external)
			if any(self._is_cloud_result(i) for i in results):
				return self.display_results(results)
		return self.display_results(results)

	def append_folder_scrapers(self, current_list):
		current_list.extend(self.folder_sources())

	def get_folderscraper_info(self):
		folder_info = [(get_setting('redlight.%s.display_name' % i), i, settings.source_folders_directory(self.media_type, i))
						for i in ('folder1', 'folder2', 'folder3', 'folder4', 'folder5')]
		return [i for i in folder_info if not i[0] in (None, 'None', '') and i[2]]

	def _get_active_scraper_names(self, scraper_list):
		return [i[2] for i in scraper_list]

	def scrapers_dialog(self):
		def _scraperDialog():
			monitor = kodi_utils.kodi_monitor()
			start_time = time.time()
			while not self.progress_dialog.iscanceled() and not monitor.abortRequested():
				try:
					remaining_providers = [x.getName() for x in _threads if x.is_alive() is True]
					self._process_internal_results()
					current_progress = max((time.time() - start_time), 0)
					line1 = ', '.join(remaining_providers).upper()
					percent = int((current_progress/float(25))*100)
					self.progress_dialog.update_scraper(self.sources_sd, self.sources_720p, self.sources_1080p, self.sources_4k, self.sources_total, line1, percent)
					kodi_utils.sleep(self.sleep_time)
					if len(remaining_providers) == 0: break
					if percent >= 100:
						grace_deadline = time.time() + 8
						while time.time() < grace_deadline and any(x.is_alive() for x in _threads):
							self._process_internal_results()
							kodi_utils.sleep(100)
						for thread in _threads:
							thread.join(timeout=max(0.0, grace_deadline - time.time()))
						self._absorb_internal_properties()
						break
				except:	return self._kill_progress_dialog()
		if self.prescrape: scraper_list, _threads = self.prescrape_scrapers, self.prescrape_threads
		else: scraper_list, _threads = self.providers, self.threads
		self.internal_scrapers = self._get_active_scraper_names(scraper_list)
		if not self.internal_scrapers: return
		_scraperDialog()
		try: del monitor
		except: pass

	def _wait_active_playback_end(self):
		player = kodi_utils.kodi_player()
		monitor = kodi_utils.kodi_monitor()
		while player.isPlayingVideo() or player.isPlaying():
			if monitor.abortRequested():
				return
			kodi_utils.sleep(100)

	def display_results(self, results):
		while True:
			if self.autoscrape_nextep:
				kodi_utils.show_busy_dialog()
			window_format, window_number = settings.results_format()
			window_result = open_window(('windows.sources', 'SourcesResults'), 'sources_results.xml',
					window_format=window_format, window_id=window_number, results=results, meta=self.meta, sources_ref=self, episode_group_label=self.episode_group_label,
					scraper_settings=self.scraper_settings, prescrape=self.prescrape, filters_ignored=self.filters_ignored,
					uncached_results=self.uncached_results, cache_check_override=self.cache_check_override)
			if not window_result:
				self._kill_progress_dialog()
				return
			action, chosen_item = window_result
			if not action:
				if kodi_utils.get_property(PROP_BROWSE_RETURN_SOURCES) == 'true':
					kodi_utils.clear_property(PROP_BROWSE_RETURN_SOURCES)
					self._wait_active_playback_end()
					continue
				if self._playback_already_active():
					self._kill_progress_dialog(join_timeout=1.0)
					self.resolve_dialog_made = False
					return
				self._kill_progress_dialog(join_timeout=3.0)
				self.resolve_dialog_made = False
				return
			elif action == 'play':
				kodi_utils.clear_property(PROP_RESOLVE_CANCEL)
				self.play_file(results, chosen_item)
				return
			elif self.prescrape and action == 'perform_full_search':
				self._reset_scrape_progress_counts()
				if self.progress_dialog:
					try:
						self.progress_dialog.update_scraper(0, 0, 0, 0, 0, '', 0)
					except:
						pass
				elif not self.background:
					self._make_progress_dialog()
				# Mirror empty-prescrape → full scrape: keep remove_scrapers and prescrape_sources
				# so cloud scrapers stay finished and progress shows external/cache only.
				self.prescrape = False
				self.clear_properties = True
				self.filters_ignored = self.ignore_scrape_filters
				self.sources, self.orig_results = [], []
				self.threads, self.providers, self.prescrape_scrapers, self.prescrape_threads = [], [], [], []
				self.uncached_results, self.cloud_scraper_names = [], []
				self.active_folders, self.folder_info = False, []
				self.internal_scraper_names, self.resolve_dialog_made = [], False
				if not self.ignore_scrape_filters: kodi_utils.clear_property('fs_filterless_search')
				self._prepare_external_only_followup()
				return self.get_sources()
			elif action == 'cache_change_rescrape':
				self.cache_check_override = chosen_item == 'true'
				self._reset_scrape_state(keep_disabled_ext_ignored=True)
				return self.get_sources()

	def _get_active_scraper_names(self, scraper_list):
		return [i[2] for i in scraper_list]

	def _prepare_external_only_followup(self):
		"""External torrent follow-up: skip re-scraping internals, use current filter/sort/priority settings."""
		self.autoplay = False
		self._refresh_results_settings()
		self._exclude_internal_scrapers_for_external_only_followup()

	def _refresh_results_settings(self):
		self.provider_sort_ranks = settings.provider_sort_ranks()
		self.sort_function = settings.results_sort_order()
		self.weight_size = settings.size_sort_weighted()
		self.quality_filter = self._quality_filter()

	def _exclude_internal_scrapers_for_external_only_followup(self):
		"""Run External Scraper Search: skip all non-external scrapers; keep prescrape results in memory."""
		self.determine_scrapers_status()
		for scraper in self.active_internal_scrapers:
			if scraper != 'external' and scraper not in self.remove_scrapers:
				self.remove_scrapers.append(scraper)

	def _reset_scrape_state(self, keep_disabled_ext_ignored=False):
		self.prescrape = False
		self.clear_properties = True
		self.filters_ignored = self.ignore_scrape_filters
		self.sources, self.prescrape_sources, self.orig_results = [], [], []
		self.threads, self.providers, self.prescrape_scrapers, self.prescrape_threads = [], [], [], []
		self.prescrape_ran_scrapers = set()
		self.remove_scrapers, self.uncached_results = ['external'], []
		self.active_folders, self.folder_info = False, []
		self.internal_scraper_names, self.resolve_dialog_made = [], False
		if 'autoplay' in self.params: self.autoplay = self.params.get('autoplay') == 'true'
		else: self.autoplay = settings.auto_play(self.media_type)
		self.cloud_prescrape_autoplay = False
		if not keep_disabled_ext_ignored:
			self.disabled_ext_ignored = self.params.get('disabled_ext_ignored', 'false') == 'true'
		if not self.ignore_scrape_filters: kodi_utils.clear_property('fs_filterless_search')
		self.determine_scrapers_status()

	def _process_post_results(self):
		self._kill_progress_dialog(join_timeout=2.0)
		if not self.retry_actions: return self._no_results()
		next_action, next_setting, order = self.retry_actions.pop(0)
		if next_action == 'cache_ignored':
			api_err = kodi_utils.get_property('redlight.debrid_cache_api_error')
			if api_err:
				kodi_utils.clear_property('redlight.debrid_cache_api_error')
				try:
					kodi_utils.logger('DebridCacheRetry', 'skipped=cache_ignored reason=api_%s' % api_err)
				except: pass
				if not self.background:
					kodi_utils.notification('AllDebrid cache check unavailable (%s). Showing unchecked sources.' % api_err, 6000)
				if self.orig_results:
					for item in self.orig_results:
						raw = item.get('cache_provider', '')
						if 'Uncached' in raw:
							provider = debrid.normalize_debrid_provider(item.get('debrid') or raw.replace('Uncached ', ''))
							item['cache_provider'] = provider
							item['debrid'] = provider
					results = self.process_results(self.orig_results)
					if results:
						if self.autoscrape: return results
						return self.play_source(results)
				return self._process_post_results()
			if next_setting in (1, 2) and self.active_external and self.orig_results and self._any_cache_check_active() \
																				and debrid.debrid_cache_check_available(self.debrid_enabled):
				try:
					kodi_utils.logger('DebridCacheRetry', 'action=cache_ignored auto=%s orig=%d playable=0' % (next_setting == 1, len(self.orig_results)))
				except: pass
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry with external cache check disabled?'):
					self.threads, self.prescrape, self.cache_check_override = [], False, False
					return self.get_sources()
			return self._process_post_results()
		if next_action == 'imdb_year':
			if next_setting in (1, 2) and self.active_external and not self.orig_results and not self.meta.get('custom_year'):
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry With IMDb Year Data?'):
					from apis.imdb_api import imdb_year_check
					imdb_year = str(imdb_year_check(self.meta.get('imdb_id')))
					if imdb_year != self.get_search_year():
						self.meta['custom_year'] = imdb_year
						self.make_search_info()
						self.threads, self.prescrape = [], False
						return self.get_sources()
			return self._process_post_results()
		if next_action == 'with_all':
			if next_setting in (1, 2) and self.active_external:
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry including disabled external torrent providers?'):
					self.threads, self.disabled_ext_ignored, self.prescrape = [], True, False
					return self.get_sources()
			return self._process_post_results()
		if next_action == 'episode_group':
			if next_setting in (1, 2) and self.media_type == 'episode':
				if next_setting == 1 \
											or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results.[CR]Retry With Custom Episode Group if Possible?'):
					if self.episode_group_used:
						return self._process_post_results()
					if next_setting == 2:
						from indexers.dialogs import episode_groups_choice
						try: group_id = episode_groups_choice({'meta': self.meta, 'poster': self.meta['poster']})
						except: group_id = None
					else:
						try: group_id = metadata.episode_groups(self.tmdb_id)[0]['id']
						except: group_id = None
					if group_id:
						try: group_details = metadata.group_episode_data(metadata.group_details(group_id), None, self.season, self.episode)
						except: group_details = None
						if group_details:
							season, episode = group_details['season'], group_details['episode']
							self.params.update({'custom_season': season, 'custom_episode': episode, 'episode_group_label': '[B]CUSTOM GROUP: S%02dE%02d[/B]' % (season, episode)})
							self.threads, self.prescrape = [], False
							return self.playback_prep()
			return self._process_post_results()
		if next_action == 'ignore_filters':
			if next_setting in (1, 2) and self.orig_results and not self.background:
				if next_setting == 1 or kodi_utils.confirm_dialog(heading=self.meta.get('rootname', ''), text='No results. Access Filtered Results?'):
					if self.autoplay: kodi_utils.notification('Filters Ignored & Autoplay Disabled')
					self.threads, self.ignore_scrape_filters, self.disabled_ext_ignored, self.autoplay = [], True, True, False
					return self.get_sources()
			return self._process_post_results()
		return self._process_post_results()

	def _close_progress_before_modal(self):
		self._kill_progress_dialog(join_timeout=3.0)
		kodi_utils.hide_busy_dialog()
		if self.progress_thread and self.progress_thread.is_alive():
			try:
				kodi_utils.close_dialog('sources_playback.xml')
				self.progress_thread.join(timeout=2.0)
			except:
				pass
		kodi_utils.sleep(400)

	def _show_modal_message(self, heading, text, background_notification=None):
		if self.background:
			return kodi_utils.notification(background_notification or text, 5000)
		try:
			return kodi_utils.kodi_dialog().ok(heading, text)
		except Exception:
			try:
				return kodi_utils.ok_dialog(heading=heading, text=text, ok_label='OK')
			except Exception:
				return kodi_utils.notification(text, 4000, settle_ms=400)

	def _external_cache_check_active(self, provider):
		provider = debrid.normalize_debrid_provider(provider)
		if not provider:
			return True
		if self.cache_check_override is not None:
			return self.cache_check_override
		return settings.debrid_cache_check(provider)

	def _playback_failed_default_message(self):
		reasons = ['expired', 'removed']
		item = getattr(self, 'playing_item', None) or {}
		if item.get('scrape_provider') == 'external':
			provider = debrid.normalize_debrid_provider(item.get('debrid') or item.get('cache_provider'))
			if provider and not self._external_cache_check_active(provider):
				reasons.append('not cached on your debrid (cache check was off)')
		reasons.append('unsupported on this device')
		return 'This link could not be played. It may be %s, or %s.' % (', '.join(reasons[:-1]), reasons[-1])

	def _show_playback_failed_dialog(self, text=None):
		if self._playback_failed_notified:
			return
		self._playback_failed_notified = True
		self._close_progress_before_modal()
		message = text or self._playback_failed_default_message()
		if self.autoplay or self.background:
			return kodi_utils.notification('Playback Failed', 4000, settle_ms=400)
		return self._show_modal_message('Playback failed', message)

	def _no_results(self):
		if self.random_continual and self.media_type == 'episode' and self.tmdb_id:
			return self._random_continual_skip()
		self._close_progress_before_modal()
		return self._show_no_results()

	def _show_no_results(self):
		heading = self.meta.get('rootname', '') or self.meta.get('title', '') or 'Red Light'
		return self._show_modal_message(heading, 'No results found.', '[B]Next Up:[/B] No Results')

	def _random_continual_skip(self):
		"""Continual random play: an episode with no links should not stop the chain, so retry with another random episode."""
		from modules.episode_tools import EpisodeTools
		attempts = int(kodi_utils.get_property(PROP_RANDOM_CONTINUAL_SKIP_ATTEMPTS) or 0)
		self._close_progress_before_modal()
		if attempts >= RANDOM_CONTINUAL_MAX_SKIPS:
			kodi_utils.clear_property(PROP_RANDOM_CONTINUAL_SKIP_ATTEMPTS)
			return self._show_no_results()
		kodi_utils.set_property(PROP_RANDOM_CONTINUAL_SKIP_ATTEMPTS, str(attempts + 1))
		kodi_utils.logger('Red Light', 'Continual random play: no results for %s S%02dE%02d, skipping to another episode' % (
			self.meta.get('title', ''), self.meta.get('season', 0), self.meta.get('episode', 0)))
		meta = metadata.tvshow_meta('tmdb_id', self.tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
		meta['watch_count'] = self.meta.get('watch_count', 1)
		return EpisodeTools(meta).play_random_continual(first_run=False)

	def get_search_title(self):
		search_title = self.meta.get('custom_title', None) or self.meta.get('english_title') or self.meta.get('title')
		return search_title

	def get_search_year(self):
		year = self.meta.get('custom_year', None) or self.meta.get('year')
		return year

	def get_season(self):
		season = self.meta.get('custom_season', None) or self.meta.get('season')
		try: season = int(season)
		except: season = None
		return season

	def get_episode(self):
		episode = self.meta.get('custom_episode', None) or self.meta.get('episode')
		try: episode = int(episode)
		except: episode = None
		return episode

	def get_ep_name(self):
		ep_name = None
		if self.meta['media_type'] == 'episode':
			ep_name = self.meta.get('ep_name')
			try: ep_name = safe_string(remove_accents(ep_name))
			except: ep_name = safe_string(ep_name)
		return ep_name

	def _wait_for_cloud_threads(self, timeout=None):
		"""Keep the scraper progress bar alive while parallel cloud threads finish after external."""
		if not self.threads:
			return
		if timeout is None:
			timeout = min(35, max(15, int(get_setting('redlight.results.timeout', '20')) + 10))
		start_time, deadline = time.time(), time.time() + timeout
		while time.time() < deadline:
			if self._user_cancelled_scrape():
				break
			alive = [t.getName() for t in self.threads if t.is_alive()]
			self._poll_scraper_quality_counts()
			if self.progress_dialog and alive:
				try:
					elapsed = max(time.time() - start_time, 0)
					percent = min(99, int((elapsed / 25.0) * 100))
					line1 = ', '.join(alive).upper()
					self.progress_dialog.update_scraper(self.sources_sd, self.sources_720p, self.sources_1080p, self.sources_4k, self.sources_total, line1, percent)
				except:
					pass
			if not alive:
				break
			self._absorb_internal_properties()
			kodi_utils.sleep(100)
		self._join_internal_threads(max(0, deadline - time.time()))
		self._absorb_internal_properties()
		self._finalize_cloud_scraper_properties()

	def _cloud_scraper_names(self):
		names = set(self.cloud_scraper_names or [])
		names.update(i for i in self.remove_scrapers if i not in ('external',))
		for thread in self.threads:
			name = thread.getName()
			if name in ('rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud'):
				names.add(name)
		return names

	def _finalize_cloud_scraper_properties(self):
		"""Mark cloud scrapers done when the thread exited without publishing a property."""
		for scraper in self._cloud_scraper_names():
			thread = next((t for t in self.threads if t.getName() == scraper), None)
			if thread and thread.is_alive():
				continue
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % scraper)
			if win_property in ('checked', '', None):
				kodi_utils.set_property('redlight.internal_results.%s' % scraper, 'checked')

	def _poll_scraper_quality_counts(self):
		names = list(self.cloud_scraper_names or [])
		for thread in self.threads:
			name = thread.getName()
			if name and name not in names:
				names.append(name)
		for scraper in names:
			if scraper in self._quality_poll_scrapers:
				continue
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % scraper)
			if win_property in ('checked', '', None):
				continue
			try:
				sources = json.loads(win_property)
			except:
				continue
			self._quality_poll_scrapers.add(scraper)
			self._sources_quality_count(sources)

	def _join_internal_threads(self, timeout=30):
		"""Wait for cloud/internal threads; cap wait so a stuck scraper cannot block results forever."""
		deadline = time.time() + timeout
		for thread in self.threads:
			if self._user_cancelled_scrape():
				break
			remaining = deadline - time.time()
			if remaining <= 0:
				break
			try:
				thread.join(timeout=remaining)
			except:
				pass

	def _absorb_internal_properties(self):
		"""Merge internal scraper window properties into sources (cloud may finish after external dialog)."""
		scraper_names = set(self.internal_scraper_names)
		scraper_names.update(self._cloud_scraper_names())
		existing = {i.get('id') for i in self.sources if i.get('id')}
		for scraper in scraper_names:
			if scraper in ('external',): continue
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % scraper)
			if win_property in ('checked', '', None): continue
			try: internal_sources = json.loads(win_property)
			except: continue
			kodi_utils.set_property('redlight.internal_results.%s' % scraper, 'checked')
			for item in internal_sources:
				item_id = item.get('id')
				if item_id and item_id in existing: continue
				if item_id: existing.add(item_id)
				self.sources.append(item)

	def _process_internal_results(self):
		for i in self.internal_scrapers:
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % i)
			if win_property in ('checked', '', None): continue
			try: sources = json.loads(win_property)
			except: continue
			kodi_utils.set_property('redlight.internal_results.%s' % i, 'checked')
			self._sources_quality_count(sources)
	
	def _sources_quality_count(self, sources):
		for item in self.count_tuple: setattr(self, item[0], getattr(self, item[0]) + item[2](sources, item[1]))

	def _quality_filter(self):
		setting = 'results_quality_%s' % self.media_type if not self.autoplay else 'autoplay_quality_%s' % self.media_type
		filter_list = settings.quality_filter(setting)
		if self.include_prerelease_results and 'SD' in filter_list: filter_list += ['SCR', 'CAM', 'TELE']
		return filter_list

	def _get_size_rank(self, item):
		if self.weight_size: return item['size'] * 2 if 'HEVC' in item['extraInfo'] else item['size']
		else: return item['size']

	def _get_quality_rank(self, quality):
		return {'4K': 1, '1080p': 2, '720p': 3, 'SD': 4, 'SCR': 5, 'CAM': 5, 'TELE': 5}[quality]

	def _get_provider_rank(self, account_type):
		rank = self.provider_sort_ranks.get(account_type)
		return 11 if rank is None else rank

	def _sort_folder_to_top(self, provider):
		if provider == 'folders': return 0
		else: return 1

	def _sort_uncached_results(self, results):
		keep_in_sort = []
		if settings.include_uncached_torbox():
			keep_in_sort.append('TorBox')
		if settings.include_uncached_offcloud():
			keep_in_sort.append('Offcloud')
		if settings.include_uncached_premiumize():
			keep_in_sort.append('Premiumize')
		if keep_in_sort:
			defer_uncached = [i for i in results if 'Uncached' in i.get('cache_provider', '') and not any(p in i.get('cache_provider', '') for p in keep_in_sort)]
			return [i for i in results if i not in defer_uncached] + defer_uncached
		uncached = [i for i in results if 'Uncached' in i.get('cache_provider', '')]
		cached = [i for i in results if i not in uncached]
		return cached + uncached

	def get_meta(self):
		if self.media_type == 'movie': self.meta = metadata.movie_meta('tmdb_id', self.tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
		else:
			try:
				self.meta = metadata.tvshow_meta('tmdb_id', self.tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
				episodes_data = metadata.episodes_meta(self.season, self.meta)
				episode_data = [i for i in episodes_data if i['episode'] == self.episode][0]
				ep_thumb = episode_data.get('thumb', None) or self.meta.get('fanart') or ''
				episode_type = episode_data.get('episode_type', '')
				self.meta.update({'season': episode_data['season'], 'episode': episode_data['episode'], 'premiered': episode_data['premiered'], 'episode_type': episode_type,
								'ep_name': episode_data['title'], 'ep_thumb': ep_thumb, 'plot': episode_data['plot'], 'tvshow_plot': self.meta['plot'],
								'playcount': self.playcount, 'watch_count': self.watch_count, 'custom_season': self.custom_season, 'custom_episode': self.custom_episode})
			except: pass
		self.meta.update({'media_type': self.media_type, 'background': self.background, 'custom_title': self.custom_title, 'custom_year': self.custom_year})

	def make_search_info(self):
		title, year, ep_name = self.get_search_title(), self.get_search_year(), self.get_ep_name()
		aliases = make_alias_dict(self.meta, title)
		expiry_times = get_cache_expiry(self.media_type, self.meta, self.season)
		self.search_info = {'media_type': self.media_type, 'title': title, 'year': year, 'tmdb_id': self.tmdb_id, 'imdb_id': self.meta.get('imdb_id'), 'aliases': aliases,
							'season': self.get_season(), 'episode': self.get_episode(), 'tvdb_id': self.meta.get('tvdb_id'), 'ep_name': ep_name, 'expiry_times': expiry_times,
							'total_seasons': self.meta.get('total_seasons', 1)}

	def _get_module(self, module_type, function):
		if module_type == 'external': module = function.source(*self.external_args)
		elif module_type == 'folders': module = function[0](*function[1])
		else: module = function()
		return module

	def _clear_properties(self):
		def_internal = self.default_internal_scrapers
		for item in def_internal: kodi_utils.clear_property('redlight.internal_results.%s' % item)
		if self.active_folders:
			for item in self.folder_info: kodi_utils.clear_property('redlight.internal_results.%s' % item[0])

	def _release_sources_busy(self):
		if kodi_utils.get_property(PROP_SOURCES_OWNER) == getattr(self, '_sources_busy_owner', ''):
			kodi_utils.clear_property(PROP_SOURCES_BUSY)
			kodi_utils.clear_property(PROP_SOURCES_OWNER)

	def _release_resolve_busy(self):
		if kodi_utils.get_property(PROP_RESOLVE_OWNER) == getattr(self, '_resolve_busy_owner', ''):
			kodi_utils.clear_property(PROP_RESOLVE_BUSY)
			kodi_utils.clear_property(PROP_RESOLVE_OWNER)

	def _clear_stale_resolve_busy(self):
		if kodi_utils.get_property(PROP_RESOLVE_BUSY) != 'true':
			return False
		try:
			if kodi_utils.kodi_player().isPlayingVideo():
				return False
		except:
			pass
		if kodi_utils.get_property(PROP_PLAY_OPENING) == 'true':
			return False
		kodi_utils.clear_property(PROP_RESOLVE_BUSY)
		kodi_utils.clear_property(PROP_RESOLVE_OWNER)
		kodi_utils.clear_property(PROP_RESOLVE_CANCEL)
		return True

	def _claim_resolve_busy(self):
		self._resolve_busy_owner = str(id(self))
		kodi_utils.set_property(PROP_RESOLVE_BUSY, 'true')
		kodi_utils.set_property(PROP_RESOLVE_OWNER, self._resolve_busy_owner)

	def _on_scrape_dialog_cancel(self):
		self._scrape_user_cancelled = True
		self._release_sources_busy()

	def _on_resolve_dialog_cancel(self):
		self._resolve_user_cancelled = True
		self.cancel_all_playback = True
		kodi_utils.set_property(PROP_RESOLVE_CANCEL, 'true')

	def _user_cancelled_scrape(self):
		if getattr(self, '_scrape_user_cancelled', False):
			return True
		try:
			if self.progress_dialog and self.progress_dialog.iscanceled():
				return getattr(self.progress_dialog, 'window_mode', 'scraper') == 'scraper'
		except:
			pass
		return False

	def _finish_scrape_cancel(self):
		self._kill_progress_dialog(join_timeout=2.0)
		self._release_sources_busy()
		kodi_utils.hide_busy_dialog()

	def _ensure_progress_dialog_dead(self, join_timeout=2.0):
		thread = self.progress_thread
		if thread and thread.is_alive():
			try:
				if self.progress_dialog:
					self.progress_dialog.is_canceled = True
					self.progress_dialog.close()
			except:
				pass
			try:
				thread.join(timeout=join_timeout)
			except:
				pass
		self.progress_dialog, self.progress_thread = None, None

	def _reset_scrape_progress_counts(self):
		self.sources_total = self.sources_4k = self.sources_1080p = self.sources_720p = self.sources_sd = 0

	def _make_progress_dialog(self):
		self._ensure_progress_dialog_dead()
		self._reset_scrape_progress_counts()
		self.progress_dialog = create_window(('windows.sources', 'SourcesPlayback'), 'sources_playback.xml', meta=self.meta, sources_ref=self)
		self.progress_thread = Thread(target=self.progress_dialog.run)
		self.progress_thread.start()

	def _prepare_resolve_ui(self):
		try:
			if self.progress_dialog:
				self.progress_dialog.reset_is_cancelled()
				self.progress_dialog.enable_resolver()
				self.resolve_dialog_made = True
		except:
			pass

	def _make_resolve_dialog(self):
		self.resolve_dialog_made = True
		if not self.progress_dialog: self._make_progress_dialog()
		self.progress_dialog.enable_resolver()

	def _make_resume_dialog(self, percent):
		if not self.progress_dialog: self._make_progress_dialog()
		self.progress_dialog.enable_resume(percent)
		return self.progress_dialog.resume_choice

	def _make_still_watching_dialog(self, check_text, heading='Still Watching?', right_align=False):
		try: action = open_window(('windows.playback_notifications', 'StillWatching'), 'playback_notifications.xml', meta=self.meta, check_text=check_text,
			heading=heading, right_align='true' if right_align else 'false')
		except: action = False
		return action

	def _user_cancelled_resolve(self):
		if kodi_utils.get_property(PROP_RESOLVE_CANCEL) == 'true':
			return True
		if getattr(self, '_resolve_user_cancelled', False) or getattr(self, 'cancel_all_playback', False):
			return True
		try:
			if self.progress_dialog and self.progress_dialog.iscanceled():
				return self.progress_dialog.window_mode in ('resolver', 'resume')
		except:
			pass
		return False

	def _wait_for_player_open(self, max_ms=8000):
		try:
			player = kodi_utils.kodi_player()
			if kodi_utils.get_property(PROP_PLAY_OPENING) != 'true':
				try:
					if not player.isPlaying():
						return
					if player.isPlayingVideo():
						kodi_utils.sleep(300)
						return
				except:
					return
			for _ in range(max(1, max_ms // 100)):
				try:
					if player.isPlayingVideo():
						kodi_utils.sleep(300)
						return
				except:
					pass
				kodi_utils.sleep(100)
			kodi_utils.sleep(400)
		except:
			pass

	def _request_player_stop(self, light=False):
		try:
			player = kodi_utils.kodi_player()
			opening = kodi_utils.get_property(PROP_PLAY_OPENING) == 'true'
			if light or opening or (player.isPlaying() and not player.isPlayingVideo()):
				kodi_utils.execute_builtin('PlayerControl(Stop)', block=False)
				return
			if player.isPlayingVideo() or kodi_utils.get_visibility('Window.IsActive(fullscreenvideo)'):
				if player.isPlaying():
					player.stop()
				kodi_utils.sleep(150)
			elif player.isPlaying():
				kodi_utils.execute_builtin('PlayerControl(Stop)', block=False)
				kodi_utils.sleep(100)
		except:
			pass

	def _wait_player_idle(self, max_ms=8000, light=False):
		try:
			player = kodi_utils.kodi_player()
			stable_idle = 0
			for _ in range(max(1, max_ms // 100)):
				playing = False
				try:
					playing = player.isPlaying() or player.isPlayingVideo()
				except:
					pass
				if not playing:
					stable_idle += 1
					if stable_idle >= 3:
						kodi_utils.sleep(200)
						return
				else:
					stable_idle = 0
					self._request_player_stop(light=True if light else (kodi_utils.get_property(PROP_PLAY_OPENING) == 'true' or not player.isPlayingVideo()))
				kodi_utils.sleep(100)
		except:
			pass

	def _stop_active_playback(self, wait_for_open=False, light=False):
		if wait_for_open:
			self._wait_for_player_open()
		self._wait_player_idle(light=light)

	def _ensure_play_headers(self, url, item):
		if not url or not isinstance(url, str) or '|' in url:
			return url
		try:
			debrid = (item.get('debrid') or item.get('cache_provider') or '').replace('.me', '')
			if debrid in ('Premiumize', 'pm_cloud'):
				return self.debrid_importer('Premiumize.me')().add_headers_to_url(url)
			if debrid in ('TorBox', 'tb_cloud'):
				return self.debrid_importer('TorBox')().add_headers_to_url(url)
		except:
			pass
		return url

	def _finish_resolve_cancel(self):
		kodi_utils.clear_property(PROP_PLAY_OPENING)
		self._release_resolve_busy()
		kodi_utils.clear_property(PROP_RESOLVE_CANCEL)
		self._request_player_stop(light=True)
		self._kill_progress_dialog(join_timeout=0.5, resolve_cancel=True)
		kodi_utils.hide_busy_dialog()

	def _kill_progress_dialog(self, join_timeout=3.0, resolve_cancel=False):
		try:
			if self.progress_dialog:
				self.progress_dialog.is_canceled = True
				self.progress_dialog.close()
		except:
			pass
		thread = self.progress_thread
		if thread and thread.is_alive():
			try:
				thread.join(timeout=join_timeout)
			except:
				pass
			if thread.is_alive() and not resolve_cancel and kodi_utils.get_property(PROP_RESOLVE_BUSY) != 'true':
				try:
					kodi_utils.close_all_dialog()
				except:
					pass
		self.progress_dialog, self.progress_thread = None, None
		kodi_utils.hide_busy_dialog()

	def _resolve_sources_wait(self, item, meta=None, poll_ms=50):
		if self._user_cancelled_resolve():
			return None
		result = [None]
		def _worker():
			try:
				result[0] = self.resolve_sources(item, meta)
			except:
				result[0] = None
		worker = Thread(target=_worker, daemon=True)
		worker.start()
		while worker.is_alive():
			if self._user_cancelled_resolve():
				return None
			kodi_utils.sleep(poll_ms)
		try:
			worker.join(timeout=0.5)
		except:
			pass
		if self._user_cancelled_resolve():
			return None
		return result[0]

	def _browse_transfer_id(self, debrid_provider, debrid_files):
		if not debrid_files:
			return None
		item = debrid_files[0]
		if item.get('torrent_id') not in (None, ''):
			return item.get('torrent_id')
		if item.get('request_id') not in (None, ''):
			return item.get('request_id')
		if debrid_provider == 'TorBox':
			link = str(item.get('link', ''))
			if ',' in link:
				return link.split(',')[0]
		return None

	def _cleanup_browse_transfer(self, debrid_provider, debrid_files, is_pack):
		'''Remove temporary browse transfers when Store Resolved to Cloud does not apply.'''
		if debrid_provider not in ('TorBox', 'Offcloud'):
			return
		if settings.store_resolved_to_cloud(debrid_provider, is_pack):
			return
		transfer_id = self._browse_transfer_id(debrid_provider, debrid_files)
		if not transfer_id:
			return
		api = self.debrid_importer(debrid_provider)()
		Thread(target=api.delete_torrent, args=(transfer_id,), daemon=True).start()

	def _resolve_browse_pick_link(self, debrid_info, debrid_provider, chosen_result):
		file_link = (chosen_result.get('link') or '').strip()
		if not file_link:
			return None
		if debrid_info == 'tb_browse':
			return self.resolve_internal(debrid_info, file_link, '')
		if file_link.startswith(('http://', 'https://')):
			api = self.debrid_importer(debrid_provider)()
			if debrid_info in ('pm_browse', 'oc_browse'):
				try:
					return api.add_headers_to_url(file_link)
				except:
					return file_link
			if debrid_info == 'rd_browse':
				try:
					url = api.unrestrict_link(file_link)
					if url:
						return url
				except:
					pass
				if 'real-debrid.com' in file_link or 'download.real-debrid.com' in file_link:
					return file_link
		return self.resolve_internal(debrid_info, file_link, '')

	def _resolve_browse_pack_fallback(self, source_item, debrid_provider):
		if not source_item:
			return None
		try:
			if self.meta.get('media_type') == 'episode':
				if hasattr(self, 'search_info'):
					title, season, episode = self.search_info['title'], self.search_info['season'], self.search_info['episode']
				else:
					title, season, episode = self.get_ep_name(), self.get_season(), self.get_episode()
				pack = 'package' in source_item
			else:
				title, season, episode, pack = self.get_search_title(), None, None, 'package' in source_item
			return self.resolve_cached(debrid_provider, source_item.get('url'), source_item.get('hash'), title, season, episode, pack)
		except:
			return None

	def debridPacks(self, debrid_provider, name, magnet_url, info_hash, download=False, source_item=None):
		from modules.debrid import ExternalPackSource, normalize_debrid_provider
		debrid_provider = normalize_debrid_provider(debrid_provider)
		is_pack = bool(source_item and 'package' in source_item)
		source = {'url': magnet_url, 'hash': info_hash, 'debrid': debrid_provider, 'cache_provider': debrid_provider, 'name': name}
		pack_result = ExternalPackSource(source).browse_packs(download=download)
		if not pack_result:
			if download:
				return None
			# browse_packs() already notified; do not fall back to full magnet resolve/play.
			return None
		debrid_info = {'Real-Debrid': 'rd_browse', 'Premiumize.me': 'pm_browse', 'AllDebrid': 'ad_browse', 'Offcloud': 'oc_browse', 'TorBox': 'tb_browse'}.get(debrid_provider)
		if download:
			debrid_files, _pack_api = pack_result
			return debrid_files, self.debrid_importer(debrid_info)
		debrid_files = pack_result
		self._close_progress_before_modal()
		if is_pack and len(debrid_files) == 1:
			chosen_result = debrid_files[0]
		else:
			list_items = [{'line1': '%.2f GB | %s' % (float(item['size'])/1073741824, clean_file_name(item['filename']).upper())} for item in debrid_files]
			picker_heading = 'Browse: %s' % name
			kwargs = {'items': json.dumps(list_items), 'heading': picker_heading, 'enumerate': 'true', 'narrow_window': 'true'}
			chosen_result = kodi_utils.select_dialog(debrid_files, **kwargs)
		if chosen_result is None:
			self._cleanup_browse_transfer(debrid_provider, debrid_files, is_pack=is_pack)
			return None
		link = self._resolve_browse_pick_link(debrid_info, debrid_provider, chosen_result)
		if not link and is_pack:
			link = self._resolve_browse_pack_fallback(source_item, debrid_provider)
		if not link:
			kodi_utils.notification('Could not resolve selected file on %s' % debrid_provider, 4500)
			self._cleanup_browse_transfer(debrid_provider, debrid_files, is_pack=is_pack)
			return None
		link = self._ensure_play_headers(link, {'debrid': debrid_provider, 'cache_provider': debrid_provider})
		self._close_progress_before_modal()
		kodi_utils.set_property('redlight.browse_playback', 'true')
		kodi_utils.set_property(PROP_BROWSE_RETURN_SOURCES, 'true')
		player = RedLightPlayer()
		player._browse_results_window = getattr(self, '_sources_results_window', None)
		player.run(link, 'video')
		kodi_utils.clear_property('redlight.browse_playback')
		if not getattr(player, 'playback_successful', False):
			kodi_utils.clear_property(PROP_BROWSE_RETURN_SOURCES)
		self._cleanup_browse_transfer(debrid_provider, debrid_files, is_pack=is_pack)
		return player

	def play_file(self, results, source={}):
		playable_results = [i for i in results if 'Uncached' not in i.get('cache_provider', '')]
		if not playable_results and not source:
			return self._no_results()
		if not self.background:
			self._prefetch_intro_segment_async()
		self._playback_failed_notified = False
		kodi_utils.clear_property(PROP_RESOLVE_CANCEL)
		self._claim_resolve_busy()
		url = None
		monitor = None
		try:
			self.playback_successful, self.cancel_all_playback = None, False
			self._resolve_user_cancelled = False
			self._prepare_resolve_ui()
			defer_stop_for_nextep = getattr(self, '_nextep_alert_handled', False) or (self.background and (self.autoplay_nextep or self.autoscrape_nextep or self.play_type == 'random_continual' or self.random_continual))
			if not defer_stop_for_nextep:
				self._stop_active_playback()
			retry_easynews = settings.easynews_playback_method('retry')
			retry_easynews_limit = settings.easynews_playback_method_retries()
			if not source: source = playable_results[0]
			items = [source]
			if not self.limit_resolve:
				source_index = playable_results.index(source)
				queue_tail = playable_results[source_index + 1:]
				queue_head = playable_results[:source_index]
				queue_head.reverse()
				items = [source] + queue_tail + queue_head
			processed_items = []
			processed_items_append = processed_items.append
			for count, item in enumerate(items, 1):
				resolve_item = dict(item)
				provider = item['scrape_provider']
				if provider == 'external': provider = item['debrid'].replace('.me', '')
				elif provider == 'folders': provider = item['source']
				provider_text = provider.upper()
				extra_info = '[B]%s[/B] | [B]%s[/B] | %s' %  (item['quality'], item['size_label'], item['extraInfo'])
				display_name = item['display_name'].upper()
				resolve_item['resolve_display'] = '%02d. [B]%s[/B][CR]%s[CR]%s' % (count, provider_text, extra_info, display_name)
				processed_items_append(resolve_item)
				if provider == 'easynews' and retry_easynews:
					for retry in range(1, retry_easynews_limit):
						resolve_item = dict(item)
						resolve_item['resolve_display'] = '%02d. [B]%s (RETRYx%s)[/B][CR]%s[CR]%s' % (count, provider_text, retry, extra_info, display_name)
						processed_items_append(resolve_item)
			items = list(processed_items)
			if not self.continue_resolve_check():
				self._kill_progress_dialog()
				return
			if defer_stop_for_nextep:
				if getattr(self, '_nextep_alert_handled', False) and not self.resolve_dialog_made:
					self._make_resolve_dialog()
				self._stop_active_playback(light=True)
			if not self.progress_dialog and not self.background:
				self._make_progress_dialog()
			self.playback_percent = self.get_playback_percent()
			if self.playback_percent == None:
				self._finish_resolve_cancel()
				return
			if not self.resolve_dialog_made: self._make_resolve_dialog()
			if self.background: kodi_utils.sleep(1000)
			monitor = kodi_utils.kodi_monitor()
			for count, item in enumerate(items, 1):
				try:
					if self._resolve_user_cancelled or self.cancel_all_playback:
						break
					if not self.progress_dialog:
						if self._user_cancelled_resolve():
							self._resolve_user_cancelled = True
							self.cancel_all_playback = True
							break
						if not self.background:
							self._make_progress_dialog()
						if not self.progress_dialog:
							break
					if not self._user_cancelled_resolve():
						if count > 1:
							prev = items[count - 2]
							if prev.get('scrape_provider') != item.get('scrape_provider'):
								self.progress_dialog.reset_is_cancelled()
						else:
							self.progress_dialog.reset_is_cancelled()
					self.progress_dialog.update_resolver(text=item['resolve_display'])
					self.progress_dialog.busy_spinner()
					if count > 1:
						kodi_utils.sleep(200)
						try:
							del player
						except Exception:
							pass
					url, self.playback_successful = None, None
					self.playing_filename = item['name']
					self.playing_item = item
					player = RedLightPlayer()
					try:
						if self._user_cancelled_resolve() or monitor.abortRequested():
							self._resolve_user_cancelled = True
							self.cancel_all_playback = True
							break
						url = self._resolve_sources_wait(item)
						if self._user_cancelled_resolve():
							self._resolve_user_cancelled = True
							self.cancel_all_playback = True
							break
						if self._resolve_user_cancelled or self.cancel_all_playback:
							break
						if url:
							if self._user_cancelled_resolve():
								self._resolve_user_cancelled = True
								self.cancel_all_playback = True
								break
							resolve_percent = 0
							self.progress_dialog.busy_spinner('false')
							self.progress_dialog.update_resolver(percent=resolve_percent)
							kodi_utils.sleep(200)
							if self._user_cancelled_resolve():
								self._resolve_user_cancelled = True
								self.cancel_all_playback = True
								break
							kodi_utils.sleep(50)
							if self._user_cancelled_resolve():
								self._resolve_user_cancelled = True
								self.cancel_all_playback = True
								break
							url = self._ensure_play_headers(url, item)
							if self._user_cancelled_resolve():
								self._resolve_user_cancelled = True
								self.cancel_all_playback = True
								break
							if self.background:
								self._wait_player_idle(max_ms=2000, light=True)
							player.run(url, self)
						else: continue
						if self.cancel_all_playback or self._resolve_user_cancelled:
							break
						if self.playback_successful: break
					except: pass
				except: pass
		except:
			self._kill_progress_dialog()
		else:
			if self.cancel_all_playback or self._resolve_user_cancelled:
				self._finish_resolve_cancel()
			elif not self.playback_successful or not url:
				kodi_utils.logger('Red Light', 'Resolve queue failed: success=%s url=%s dialog=%s' % (
					self.playback_successful, bool(url), bool(self.progress_dialog)))
				self.playback_failed_action()
		finally:
			self._release_resolve_busy()
			try: del monitor
			except: pass

	def get_playback_percent(self):
		if self.media_type == 'movie': percent = watched_status.get_progress_status_movie(watched_status.get_bookmarks_movie(), str(self.tmdb_id))
		elif any((self.random, self.random_continual)): return 0.0
		else: percent = watched_status.get_progress_status_episode(watched_status.get_bookmarks_episode(self.tmdb_id, self.season), self.episode)
		if not percent: return 0.0
		if self.cloud_prescrape_autoplay:
			if settings.auto_resume(self.media_type, True):
				return float(percent)
			return 0.0
		action = self.get_resume_status(percent)
		if action == 'cancel': return None
		if action == 'start_over':
			watched_status.erase_bookmark(self.media_type, self.tmdb_id, self.season, self.episode)
			return 0.0
		return float(percent)

	def get_resume_status(self, percent):
		if settings.auto_resume(self.media_type, self.autoplay): return float(percent)
		choice = self._make_resume_dialog(percent)
		if self._user_cancelled_resolve() or choice in (None, 'cancel'):
			return 'cancel'
		if choice == 'start_over':
			return 'start_over'
		return float(percent)

	def playback_failed_action(self):
		if self._user_cancelled_resolve():
			return self._finish_resolve_cancel()
		if self.cloud_prescrape_autoplay:
			self._kill_progress_dialog(join_timeout=1.0)
			self.resolve_dialog_made = False
			fallback_sources = list(self.prescrape_sources) if self.prescrape_sources else list(getattr(self, '_last_cloud_autoplay_results', []) or [])
			if fallback_sources:
				self.prescrape = bool(self.prescrape_sources)
				results = self.process_results(fallback_sources)
				if results:
					self.cloud_prescrape_autoplay = False
					if self.autoplay and not self._effective_autoplay():
						self.autoplay = False
					return self.display_results(results)
			self.cloud_prescrape_autoplay = False
			if self.autoplay and not self._effective_autoplay():
				self.autoplay = False
			return self._show_playback_failed_dialog()
		if self.prescrape and self._effective_autoplay() and not self.prescrape_sources:
			# Prescrape found nothing — continue to the full scrape (e.g. external autoplay).
			self._kill_progress_dialog(join_timeout=1.0)
			self.resolve_dialog_made, self.prescrape, self.prescrape_sources = False, False, []
			return self.get_sources()
		if self.prescrape_sources:
			self._kill_progress_dialog(join_timeout=1.0)
			self.resolve_dialog_made = False
			results = self.process_results(list(self.prescrape_sources))
			if results:
				return self.display_results(results)
		if self.autoplay or self.background:
			return self._no_results()
		return self._show_playback_failed_dialog()

	def _log_nextep_scrape_started(self):
		try:
			kodi_utils.logger('Red Light', 'Next episode background scrape started: %s S%02dE%02d (%s)' % (
				self.meta.get('title'), self.meta.get('season'), self.meta.get('episode'), self.play_type))
		except: pass

	def _prefetch_intro_segment_async(self):
		if self.media_type != 'episode':
			return
		if not settings.skip_intro_enabled(self.play_type):
			return
		try:
			from threading import Thread
			from apis.intro_skip_api import prefetch_intro_segment
			imdb_id = self.meta.get('imdb_id')
			Thread(target=prefetch_intro_segment, args=(self.tmdb_id, imdb_id, self.season, self.episode), daemon=True).start()
		except: pass

	def _prefetch_nextep_segment_data(self):
		if self.media_type != 'episode':
			return
		try:
			from threading import Thread
			imdb_id = self.meta.get('imdb_id')
			tmdb_id = self.tmdb_id
			season, episode = self.season, self.episode
			self._prefetch_intro_segment_async()
			alert_key = 'autoplay_alert_timing' if self.play_type == 'autoplay_nextep' else 'autoscrape_alert_timing'
			if settings._alert_timing_mode(alert_key) == 'introdb':
				from apis.intro_skip_api import prefetch_credits_start
				Thread(target=prefetch_credits_start, args=(tmdb_id, imdb_id, season, episode), daemon=True).start()
		except: pass

	def _playback_remaining_seconds(self, player, allow_stopped=False):
		try:
			if not allow_stopped and not player.isPlayingVideo(): return None
			return round(float(player.getTotalTime()) - float(player.getTime()))
		except:
			if not allow_stopped: return None
			try:
				prop = kodi_utils.get_property('redlight.nextep_remaining')
				if prop: return int(prop)
			except: pass
			return None

	def _autoscrape_stop_notify_remaining(self, window_time):
		return max(int(window_time), settings.NEXTEP_STOP_NOTIFY_REMAINING_SEC)

	def _mark_autoscrape_nextep_ready(self):
		if getattr(self, '_autoscrape_ready_marked', False): return
		self._autoscrape_ready_marked = True
		try:
			kodi_utils.set_property(PROP_AUTOSCRAPE_NEXTEP_READY, json.dumps({
				'title': self.meta.get('title', ''),
				'season': self.meta.get('season', 0),
				'episode': self.meta.get('episode', 0),
				'poster': self.meta.get('poster', '') or '',
			}))
		except:
			kodi_utils.set_property(PROP_AUTOSCRAPE_NEXTEP_READY, 'true')

	def _show_autoscrape_ready_notification(self):
		meta = {}
		try:
			raw = kodi_utils.get_property(PROP_AUTOSCRAPE_NEXTEP_READY)
			if raw and raw != 'true':
				meta = json.loads(raw)
		except:
			pass
		if not meta:
			meta = {'title': self.meta.get('title', ''), 'season': self.meta.get('season', 0),
				'episode': self.meta.get('episode', 0), 'poster': self.meta.get('poster', '') or ''}
		kodi_utils.clear_property(PROP_AUTOSCRAPE_NEXTEP_READY)
		kodi_utils.notification('[B]Next Episode Ready:[/B] %s S%02dE%02d' \
				% (meta.get('title'), meta.get('season'), meta.get('episode')), 6500, meta.get('poster') or None)

	def _notify_autoscrape_ready(self, remaining, window_time):
		kodi_utils.logger('Red Light', 'Autoscrape next episode ready: %s S%02dE%02d remaining=%ss alert_window=%ss' % (
			self.meta.get('title'), self.meta.get('season'), self.meta.get('episode'), remaining, window_time))
		player = kodi_utils.kodi_player()
		if self._player_episode_active(player):
			self._mark_autoscrape_nextep_ready()
			return
		if getattr(self, '_autoscrape_ready_notified', False): return
		self._autoscrape_ready_notified = True
		self._mark_autoscrape_nextep_ready()
		self._show_autoscrape_ready_notification()

	def _wait_autoscrape_pop_window(self, player, window_time):
		tight = int(window_time)
		last_remaining = self._playback_remaining_seconds(player)
		while self._player_episode_active(player):
			last_remaining = self._playback_remaining_seconds(player)
			if last_remaining is None: break
			if last_remaining <= tight:
				return last_remaining, True
			kodi_utils.sleep(500)
		return last_remaining, False

	def _player_episode_active(self, player):
		try:
			return player.isPlayingVideo() or player.isPlaying()
		except:
			return False

	def _should_autoscrape_stop_notify(self, remaining, window_time):
		if remaining is None: return False
		return remaining <= self._autoscrape_stop_notify_remaining(window_time)

	def still_watching_check(self):
		watching_check = self.nextep_settings.get('watching_check', 0)
		if watching_check == 0: return True
		player = kodi_utils.kodi_player()
		if not player.isPlayingVideo():
			return bool(self.background)
		watch_count = self.meta.get('watch_count')
		if watch_count == watching_check: still_watching, watch_count = self._make_still_watching_dialog('Are you still watching [B]%s[/B]?'), 0
		else: still_watching = True
		watch_count += 1
		self.meta['watch_count'] = watch_count
		return still_watching

	def _stash_nextep_autoplay_play(self, results):
		if not results:
			kodi_utils.logger('Red Light', 'Autoplay next episode scrape ready: no results for %s S%02dE%02d' % (
				self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')))
			return
		if stash_nextep_autoplay_results(results, self.meta, self.nextep_settings, self.params):
			kodi_utils.logger('Red Light', 'Autoplay next episode scrape ready: %s S%02dE%02d (%s results)' % (
				self.meta.get('title'), self.meta.get('season'), self.meta.get('episode'), len(results)))
		else:
			kodi_utils.logger('Red Light', 'Autoplay next episode stash failed: %s S%02dE%02d' % (
				self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')))

	def continue_resolve_check(self):
		try:
			if not self.background or self.autoscrape_nextep:
				return True
			if getattr(self, '_nextep_alert_handled', False):
				return True
			if self.play_type == 'random_continual':
				return self.random_continual_handler()
			return True
		except:
			return False

	def random_continual_handler(self):
		kodi_utils.notification('[B]Next Up:[/B] %s S%02dE%02d' % (self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')), 6500, self.meta.get('poster'))
		player = kodi_utils.kodi_player()
		while self._player_episode_active(player): kodi_utils.sleep(100)
		self._make_resolve_dialog()
		return True

	def _decline_nextep_prep(self, reason):
		try:
			player = kodi_utils.kodi_player()
			if isinstance(player, RedLightPlayer):
				player.decline_nextep_prep(reason)
				return
		except: pass
		kodi_utils.set_property('redlight.nextep_prep_declined', 'true')
		kodi_utils.logger('Red Light', 'Next episode prep declined: %s' % reason)

	def autoscrape_nextep_handler(self):
		if settings.autoscrape_confirm():
			if not self._make_still_watching_dialog('Autoscrape Next Episode of [B]%s[/B]?', heading='Autoscrape Next Episode?', right_align=True):
				self._decline_nextep_prep('autoscrape confirm')
				return
		player = kodi_utils.kodi_player()
		if not self._player_episode_active(player):
			return
		results = self.get_sources()
		if not results:
			kodi_utils.logger('Red Light', 'Autoscrape next episode: no results for %s S%02dE%02d' % (
				self.meta.get('title'), self.meta.get('season'), self.meta.get('episode')))
			return
		window_time = self.nextep_settings.get('window_time', 0) if self.nextep_settings else 0
		self._autoscrape_ready_notified = False
		self._autoscrape_ready_marked = False
		self._mark_autoscrape_nextep_ready()
		remaining = self._playback_remaining_seconds(player, allow_stopped=True)
		if not self._player_episode_active(player):
			if self._should_autoscrape_stop_notify(remaining, window_time):
				self._notify_autoscrape_ready(remaining, window_time)
			else:
				kodi_utils.logger('Red Light', 'Autoscrape next episode ready (stopped during scrape): %s S%02dE%02d remaining=%ss alert_window=%ss' % (
					self.meta.get('title'), self.meta.get('season'), self.meta.get('episode'), remaining, window_time))
			kodi_utils.show_busy_dialog()
			return self.display_results(results)
		if remaining is not None and remaining <= int(window_time):
			self._notify_autoscrape_ready(remaining, window_time)
		else:
			remaining, should_notify = self._wait_autoscrape_pop_window(player, window_time)
			if should_notify:
				self._notify_autoscrape_ready(remaining, window_time)
		while self._player_episode_active(player): kodi_utils.sleep(100)
		kodi_utils.show_busy_dialog()
		if kodi_utils.get_property(PROP_AUTOSCRAPE_NEXTEP_READY):
			self._show_autoscrape_ready_notification()
		self.display_results(results)

	def debrid_importer(self, debrid_provider):
		return manual_function_import(*self.debrids[debrid_provider])

	def resolve_sources(self, item, meta=None):
		if self._user_cancelled_resolve():
			return None
		if meta: self.meta = meta
		url = None
		scrape_provider = item.get('scrape_provider')
		try:
			# Cloud scrapers set debrid=tb_cloud/pm_cloud/etc.; resolve those here, not via resolve_cached.
			if scrape_provider in self.default_internal_scrapers:
				if scrape_provider == 'aiostreams':
					from apis.aiostreams_api import resolve_playback_url
					url = resolve_playback_url(item)
				else:
					url = self.resolve_internal(scrape_provider, item['id'], item['url_dl'], item.get('direct_debrid_link', False), item.get('cloud_media_type'))
			elif 'cache_provider' in item or item.get('debrid'):
				raw_cache = item.get('cache_provider', '')
				if 'Uncached' in raw_cache:
					return None
				cache_provider = debrid.normalize_debrid_provider(raw_cache or item.get('debrid'))
				if self.meta['media_type'] == 'episode':
					if hasattr(self, 'search_info'):
						title, season, episode, pack = self.search_info['title'], self.search_info['season'], self.search_info['episode'], 'package' in item
					else: title, season, episode, pack = self.get_ep_name(), self.get_season(), self.get_episode(), 'package' in item
				else: title, season, episode, pack = self.get_search_title(), None, None, False
				if cache_provider in ('Real-Debrid', 'Premiumize.me', 'AllDebrid', 'Offcloud', 'TorBox'):
					url = self.resolve_cached(cache_provider, item['url'], item['hash'], title, season, episode, pack)
			else: url = item['url']
		except: pass
		if self._user_cancelled_resolve():
			return None
		return url

	def resolve_cached(self, debrid_provider, item_url, _hash, title, season, episode, pack):
		debrid_function = self.debrid_importer(debrid_provider)
		store_to_cloud = settings.store_resolved_to_cloud(debrid_provider, pack)
		try: url = debrid_function().resolve_magnet(item_url, _hash, store_to_cloud, title, season, episode)
		except: url = None
		return url

	def resolve_internal(self, scrape_provider, item_id, url_dl, direct_debrid_link=False, cloud_media_type=None):
		url = None
		try:
			if direct_debrid_link or scrape_provider == 'folders': url = url_dl
			elif scrape_provider == 'easynews':
				from indexers.easynews import resolve_easynews
				url = resolve_easynews({'url_dl': url_dl, 'play': 'false'})
			else:
				debrid_function = self.debrid_importer(scrape_provider)
				if scrape_provider == 'tb_cloud':
					tb = debrid_function()
					media_type = cloud_media_type or 'torrent'
					if media_type == 'webdl':
						url = tb.unrestrict_webdl(item_id)
					elif media_type == 'usenet':
						url = tb.unrestrict_usenet(item_id)
					else:
						url = tb.unrestrict_link(item_id)
					url = tb.coerce_play_url(url) or url
				elif any(i in scrape_provider for i in ('rd_', 'ad_', 'tb_')):
					url = debrid_function().unrestrict_link(item_id)
				else:
					if '_cloud' in scrape_provider: item_id = debrid_function().get_item_details(item_id)['link']
					url = debrid_function().add_headers_to_url(item_id)
		except: pass
		return url

	def _quality_length(self, items, quality):
		return len([i for i in items if i['quality'] == quality])

	def _quality_length_sd(self, items, dummy):
		return len([i for i in items if i['quality'] in ('SD', 'CAM', 'TELE', 'SYNC')])

	def _quality_length_final(self, items, dummy):
		return len(items)
