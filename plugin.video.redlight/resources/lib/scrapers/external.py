# -*- coding: utf-8 -*-
import time
import json
import random
from threading import Thread, Lock
from caches.external_cache import external_cache
from caches.settings_cache import get_setting
from modules import kodi_utils, source_utils
from modules.debrid import RD_check, AD_check, OC_check, TB_check, PM_check, query_local_cache
from modules.settings import debrid_cache_check, max_threads
from modules.utils import clean_file_name
# logger = kodi_utils.logger

_INTERNAL_PROGRESS_LABELS = {
	'aiostreams': 'AIOStreams',
	'easynews': 'EasyNews',
	'nzb': 'NZB',
	'rd_cloud': 'RD Cloud',
	'pm_cloud': 'PM Cloud',
	'ad_cloud': 'AD Cloud',
	'oc_cloud': 'OC Cloud',
	'tb_cloud': 'TB Cloud',
	'folders': 'Folders',
	'comet': 'Comet',
	'torrentio': 'Torrentio',
	'torz': 'StremThru Torz',
	'nyaa': 'Nyaa (Anime)',
	'animetosho': 'AnimeTosho (Anime)',
}

class source:
	def __init__(self, meta, source_dict, active_debrid, cache_check_override, internal_scrapers, prescrape_sources, progress_dialog, disabled_ext_ignored=False, cloud_scrapers=None, external_orchestration=None):
		self.monitor = kodi_utils.kodi_monitor()
		self.scrape_provider = 'external'
		self.progress_dialog = progress_dialog
		self.cache_check_override = cache_check_override
		self.meta = meta
		self.background = self.meta.get('background', False)
		self.active_debrid = active_debrid
		self.source_dict, self.host_dict = source_dict, []
		self.external_orchestration = external_orchestration
		self.sources, self.all_internal_sources, self.processed_internal_scrapers = [], [], []
		self.processed_internal_scrapers_append = self.processed_internal_scrapers.append
		self.internal_scrapers, self.prescrape_sources = [i for i in (internal_scrapers or []) if i != 'external'], prescrape_sources
		self.internal_activated, self.internal_prescraped = len(self.internal_scrapers) > 0, len(self.prescrape_sources) > 0
		self.processed_prescrape, self.threads_completed = False, False
		self.timeout = 60 if disabled_ext_ignored else int(get_setting('redlight.results.timeout', '20'))
		self.sources_total = self.sources_4k = self.sources_1080p = self.sources_720p = self.sources_sd = 0
		self.final_total = self.final_4k = self.final_1080p = self.final_720p = self.final_sd = 0
		self.count_tuple = (('sources_4k', '4K', self._quality_length), ('sources_1080p', '1080p', self._quality_length), ('sources_720p', '720p', self._quality_length),
							('sources_sd', '', self._quality_length_sd), ('sources_total', '', self.quality_length_final))
		self.count_tuple_final = (('final_4k', '4K', self._quality_length), ('final_1080p', '1080p', self._quality_length), ('final_720p', '720p', self._quality_length),
									('final_sd', '', self._quality_length_sd), ('final_total', '', self.quality_length_final))
		self.debrid_runners = {'Real-Debrid': ('Real-Debrid', RD_check), 'Premiumize.me': ('Premiumize.me', PM_check),
								'AllDebrid': ('AllDebrid', AD_check), 'Offcloud': ('Offcloud', OC_check), 'TorBox': ('TorBox', TB_check)}
		self.cloud_scrapers = [i for i in (cloud_scrapers or []) if i != 'external']
		self.processed_cloud_scrapers = set()

	def _internal_progress_label(self, scraper_id):
		return _INTERNAL_PROGRESS_LABELS.get(scraper_id, scraper_id.replace('_', ' ').title())

	def _progress_poll_state(self):
		external_threads = [x.getName() for x in self.threads if x.is_alive()]
		internal_pending = []
		if self.internal_activated or self.internal_prescraped:
			internal_pending = self.process_internal_results()
		self.poll_cloud_scrapers()
		return external_threads, internal_pending

	def _format_progress_line1(self, external_threads, internal_pending, wave_prefix=None):
		external_part = ', '.join(external_threads).upper() if external_threads else ''
		internal_part = ', '.join([self._internal_progress_label(i) for i in internal_pending]).upper() if internal_pending else ''
		segments = []
		if wave_prefix:
			if external_part:
				segments.append('%s: %s' % (wave_prefix, external_part))
			elif not internal_part:
				segments.append(wave_prefix)
		elif external_part:
			segments.append(external_part)
		if internal_part:
			segments.append(internal_part)
		if not segments and wave_prefix:
			segments.append(wave_prefix)
		return ' | '.join(segments)

	def results(self, info):
		if not self.source_dict: return
		try:
			self.media_type, self.tmdb_id, self.orig_title = info['media_type'], str(info['tmdb_id']), info['title']
			self.season, self.episode, self.total_seasons = info['season'], info['episode'], info['total_seasons']
			self.title, self.year = source_utils.normalize(info['title']), info['year']
			ep_name, aliases = source_utils.normalize(info['ep_name']), info['aliases']
			self.single_expiry, self.season_expiry, self.show_expiry = info['expiry_times']
			if self.media_type == 'movie':
				self.season_divider, self.show_divider = 0, 0
				self.data = {'imdb': info['imdb_id'], 'title': self.title, 'aliases': aliases, 'year': self.year}
			else:
				try: self.season_divider = [int(x['episode_count']) for x in self.meta['season_data'] if int(x['season_number']) == int(self.meta['season'])][0]
				except: self.season_divider = 1
				self.show_divider = int(self.meta['total_aired_eps'])
				self.data = {'imdb': info['imdb_id'], 'tvdb': info['tvdb_id'], 'tvshowtitle': self.title, 'aliases': aliases,'year': self.year,
							'title': ep_name, 'season': str(self.season), 'episode': str(self.episode)}
		except: return []
		if self.external_orchestration and len(self.external_orchestration.get('groups', [])) > 1:
			return self._get_sources_orchestrated()
		return self._get_sources_flat()

	def _get_sources_flat(self):
		def _scraperDialog():
			kodi_utils.hide_busy_dialog()
			kodi_utils.sleep(200)
			start_time = time.time()
			while not self.progress_dialog.iscanceled() and not self.monitor.abortRequested():
				try:
					external_threads, internal_pending = self._progress_poll_state()
					line1 = self._format_progress_line1(external_threads, internal_pending)
					percent = min(100, int((max((time.time() - start_time), 0) / float(self.timeout)) * 100))
					self.progress_dialog.update_scraper(self.sources_sd, self.sources_720p, self.sources_1080p, self.sources_4k, self.sources_total, line1, percent)
					if self.threads_completed:
						if not external_threads and not internal_pending: break
					if percent >= 100:
						self._join_scraper_threads_grace(8)
						break
					kodi_utils.sleep(100)
				except: pass
			return
		def _background():
			kodi_utils.sleep(1500)
			end_time = time.time() + self.timeout
			while time.time() < end_time:
				alive_threads = [x for x in self.threads if x.is_alive()]
				len_alive_threads = len(alive_threads)
				kodi_utils.sleep(1000)
				if len_alive_threads <= 5: return
				if len(self.sources) >= 100 * len_alive_threads: return
		self.threads = []
		self.threads_append = self.threads.append
		if self.media_type == 'movie': Thread(target=self.process_movie_threads).start()
		else:
			self._prepare_episode_source_dict()
			Thread(target=self.process_episode_threads).start()
		if self.background: _background()
		else: _scraperDialog()
		if self._scrape_was_cancelled():
			return []
		current_results = list(self.sources)
		if current_results: return self.process_results(current_results)
		return []

	def _scrape_was_cancelled(self):
		try:
			return bool(self.progress_dialog and self.progress_dialog.iscanceled())
		except:
			return False

	def _prepare_episode_source_dict(self):
		self.source_dict = [i for i in self.source_dict if i[1].hasEpisodes]
		self.season_packs, self.show_packs = source_utils.pack_enable_check(self.meta, self.season, self.episode)
		if self.season_packs:
			base_entries = [self._source_entry(i) for i in self.source_dict]
			self.source_dict = [(e[0], e[1], '', e[3], e[4], e[5]) for e in base_entries]
			pack_capable = [e for e in base_entries if e[1].pack_capable]
			if pack_capable:
				self.source_dict.extend([(e[0], e[1], 'Season', e[3], e[4], e[5]) for e in pack_capable])
				if self.show_packs: self.source_dict.extend([(e[0], e[1], 'Show', e[3], e[4], e[5]) for e in pack_capable])
				random.shuffle(self.source_dict)
				self.source_dict.sort(key=lambda k: k[2])

	def _log_scrape_external_wave(self, wave_idx, wave_labels, wave_new, wave_total, skip_threshold, mode, stop_reason):
		try:
			kodi_utils.logger('ScrapeExternalWave', 'wave=%d modules=%s wave_new=%d total=%d threshold=%d mode=%s stop=%s' % (
				wave_idx, ','.join(wave_labels), wave_new, wave_total, skip_threshold, mode, stop_reason))
		except: pass

	def _finish_orchestrated_scrape(self, stop_reason):
		try:
			kodi_utils.logger('ScrapeExternalWave', 'finished total=%d reason=%s' % (len(self.sources), stop_reason))
		except: pass
		if self._scrape_was_cancelled():
			return []
		current_results = list(self.sources)
		if current_results: return self.process_results(current_results)
		return []

	def _get_sources_primary_dedicated(self, orch):
		groups = orch['groups']
		skip_threshold = int(orch.get('skip_threshold', 0))
		mode = orch.get('mode', 'primary_parallel')
		stop_reason = 'exhausted'
		wave_idx = 0
		primary = groups[0]
		wave_idx += 1
		baseline = len(self.sources)
		self._run_provider_batch(list(primary['entries']), float(self.timeout), [primary['display_name']])
		if self._scrape_was_cancelled():
			return self._finish_orchestrated_scrape('cancelled')
		wave_total = len(self.sources)
		wave_new = wave_total - baseline
		self._log_scrape_external_wave(wave_idx, [primary['display_name']], wave_new, wave_total, skip_threshold, mode, 'primary_done')
		fallback_groups = groups[1:]
		if fallback_groups:
			wave_idx += 1
			baseline = len(self.sources)
			batch_entries, wave_labels = [], []
			for group in fallback_groups:
				wave_labels.append(group['display_name'])
				batch_entries.extend(group['entries'])
			self._run_provider_batch(batch_entries, float(self.timeout), wave_labels)
			wave_total = len(self.sources)
			wave_new = wave_total - baseline
			self._log_scrape_external_wave(wave_idx, wave_labels, wave_new, wave_total, skip_threshold, '%s_fallback' % mode, 'exhausted')
		return self._finish_orchestrated_scrape(stop_reason)

	def _get_sources_orchestrated(self):
		orch = self.external_orchestration
		if orch.get('primary_dedicated'):
			return self._get_sources_primary_dedicated(orch)
		groups = orch['groups']
		max_parallel = max(1, int(orch.get('max_parallel', 1)))
		skip_threshold = int(orch.get('skip_threshold', 0))
		early_stop = bool(orch.get('early_stop', False))
		mode = orch.get('mode', 'series')
		series_mode = max_parallel <= 1
		wave_step = 1 if series_mode else max_parallel
		phase_deadline = time.time() + self.timeout
		wave_idx = 0
		stop_reason = 'exhausted'
		for wave_start in range(0, len(groups), wave_step):
			remaining = phase_deadline - time.time()
			if remaining <= 0:
				stop_reason = 'timeout'
				break
			wave = groups[wave_start:wave_start + wave_step]
			wave_idx += 1
			baseline = len(self.sources)
			wave_labels = [g['display_name'] for g in wave]
			batch_entries = []
			for group in wave:
				batch_entries.extend(group['entries'])
			self._run_provider_batch(batch_entries, remaining, wave_labels)
			if self._scrape_was_cancelled():
				stop_reason = 'cancelled'
				break
			wave_total = len(self.sources)
			wave_new = wave_total - baseline
			if series_mode and early_stop and wave_new > 0:
				stop_reason = 'series_hit'
			elif skip_threshold > 0 and wave_total > skip_threshold:
				stop_reason = 'threshold'
			self._log_scrape_external_wave(wave_idx, wave_labels, wave_new, wave_total, skip_threshold, mode, stop_reason)
			if stop_reason in ('series_hit', 'threshold'):
				break
		return self._finish_orchestrated_scrape(stop_reason)

	def _run_provider_batch(self, batch_entries, batch_timeout, wave_labels):
		def _scraperDialog():
			kodi_utils.hide_busy_dialog()
			kodi_utils.sleep(200)
			batch_start = time.time()
			line1_prefix = ' | '.join(wave_labels).upper()
			while not self.progress_dialog.iscanceled() and not self.monitor.abortRequested():
				try:
					external_threads, internal_pending = self._progress_poll_state()
					line1 = self._format_progress_line1(external_threads, internal_pending, wave_prefix=line1_prefix)
					elapsed = max((time.time() - batch_start), 0)
					percent = min(100, (elapsed / float(batch_timeout)) * 100)
					self.progress_dialog.update_scraper(self.sources_sd, self.sources_720p, self.sources_1080p, self.sources_4k, self.sources_total, line1, percent)
					if self.threads_completed:
						if not external_threads and not internal_pending: break
					if time.time() >= batch_start + batch_timeout:
						self._join_scraper_threads_grace(8)
						break
					kodi_utils.sleep(100)
				except: pass
		def _background():
			kodi_utils.sleep(1500)
			end_time = time.time() + batch_timeout
			while time.time() < end_time:
				alive_threads = [x for x in self.threads if x.is_alive()]
				len_alive_threads = len(alive_threads)
				kodi_utils.sleep(1000)
				if len_alive_threads <= 5: return
				if len(self.sources) >= 100 * len_alive_threads: return
		self.source_dict = list(batch_entries)
		self.threads = []
		self.threads_append = self.threads.append
		self.threads_completed = False
		if self.media_type == 'movie': Thread(target=self.process_movie_threads).start()
		else:
			self._prepare_episode_source_dict()
			Thread(target=self.process_episode_threads).start()
		if self.background: _background()
		else: _scraperDialog()

	def _source_entry(self, item):
		provider_label = item[0]
		module = item[1]
		pack = ''
		if len(item) > 2:
			pack = item[2] if item[2] in ('Season', 'Show') else ''
		cache_key = item[3] if len(item) > 3 and item[3] else provider_label
		source_provider = item[4] if len(item) > 4 and item[4] else provider_label
		external_module = item[5] if len(item) > 5 else ''
		return provider_label, module, pack, cache_key, source_provider, external_module

	def _wait_for_thread_capacity(self):
		limit = max_threads()
		while sum(1 for x in self.threads if x.is_alive()) >= limit:
			if self.monitor.abortRequested(): return
			kodi_utils.sleep(100)

	def process_movie_threads(self):
		try:
			for i in self.source_dict:
				provider_label, module, pack, cache_key, source_provider, external_module = self._source_entry(i)
				self._wait_for_thread_capacity()
				threaded_object = Thread(target=self.get_movie_source, args=(provider_label, module, cache_key, source_provider, external_module), name=provider_label)
				try:
					threaded_object.start()
					self.threads_append(threaded_object)
				except RuntimeError:
					self.get_movie_source(provider_label, module, cache_key, source_provider, external_module)
		finally:
			self.threads_completed = True

	def process_episode_threads(self):
		try:
			for i in self.source_dict:
				provider_label, module, pack, cache_key, source_provider, external_module = self._source_entry(i)
				if pack: provider_display = '%s (%s)' % (provider_label, pack)
				else: provider_display = provider_label
				self._wait_for_thread_capacity()
				threaded_object = Thread(target=self.get_episode_source, args=(provider_label, module, pack, cache_key, source_provider, external_module), name=provider_display)
				try:
					threaded_object.start()
					self.threads_append(threaded_object)
				except RuntimeError:
					self.get_episode_source(provider_label, module, pack, cache_key, source_provider, external_module)
		finally:
			self.threads_completed = True

	def get_movie_source(self, provider_label, module, cache_key, source_provider, external_module):
		sources = external_cache.get(cache_key, self.media_type, self.tmdb_id, self.title, self.year, '', '')
		if sources == None:
			sources = module().sources(self.data, self.host_dict)			
			sources = self.process_sources(source_provider, sources, external_module)
			if not sources: expiry_hours = 1
			else: expiry_hours = self.single_expiry
			external_cache.set(cache_key, self.media_type, self.tmdb_id, self.title, self.year, '', '', sources, expiry_hours)
		if sources:
			if not self.background: self.process_quality_count(sources)
			self.sources.extend(sources)
		del module

	def get_episode_source(self, provider_label, module, pack, cache_key, source_provider, external_module):
		if pack in ('Season', 'Show'):
			if pack == 'Show': s_check = ''
			else: s_check = self.season
			e_check = ''
		else: s_check, e_check = self.season, self.episode
		sources = external_cache.get(cache_key, self.media_type, self.tmdb_id, self.title, self.year, s_check, e_check)
		if sources == None:
			if pack == 'Show':
				expiry_hours = self.show_expiry
				sources = module().sources_packs(self.data, self.host_dict, search_series=True, total_seasons=self.total_seasons)
			elif pack == 'Season':
				expiry_hours = self.season_expiry
				sources = module().sources_packs(self.data, self.host_dict)
			else:
				expiry_hours = self.single_expiry
				sources = module().sources(self.data, self.host_dict)
			sources = self.process_sources(source_provider, sources, external_module)
			if not sources: expiry_hours = 1
			external_cache.set(cache_key, self.media_type, self.tmdb_id, self.title, self.year, s_check, e_check, sources, expiry_hours)
		if sources:
			if pack == 'Season': sources = [i for i in sources if not 'episode_start' in i or i['episode_start'] <= self.episode <= i['episode_end']]
			elif pack == 'Show': sources = [i for i in sources if i['last_season'] >= self.season]
			if not self.background: self.process_quality_count(sources)
			self.sources.extend(sources)
		del module

	def process_results(self, results):
		if self._scrape_was_cancelled():
			return []
		def _process_duplicates(all_results):
			unique_urls, unique_hashes = set(), set()
			unique_urls_add, unique_hashes_add = unique_urls.add, unique_hashes.add
			for provider in all_results:
				try:
					url = provider['url'].lower()
					if url not in unique_urls:
						unique_urls_add(url)
						if 'hash' in provider:
							_hash = provider['hash']
							if len(_hash) == 40 and _hash not in unique_hashes:
								unique_hashes_add(provider['hash'])
								yield provider
						else: yield provider
				except: yield provider
		final_lock = Lock()
		frozen_providers = set()
		def _debrid_api_check_enabled(provider):
			if self.cache_check_override is not None:
				return self.cache_check_override
			return debrid_cache_check(provider)
		def _is_unchecked_row(item):
			return str(item.get('cache_provider', '')).startswith('Unchecked ')
		def _providers_with_rows():
			return set(i.get('debrid') for i in final_results if i.get('debrid'))
		def _unchecked_batch(provider, reason):
			if not self.background:
				self.process_quality_count_final(results)
			batch = [dict(i, **{'cache_provider': 'Unchecked %s' % provider, 'debrid': provider}) for i in results]
			try:
				kodi_utils.logger('DebridCacheCheck', 'fallback=unchecked provider=%s reason=%s total=%d' % (provider, reason, len(batch)))
			except: pass
			return batch
		def _commit_cache_batch(provider, batch):
			with final_lock:
				if provider in frozen_providers:
					return
				existing = [i for i in final_results if i.get('debrid') == provider]
				if existing:
					existing_unverified = all(_is_unchecked_row(i) for i in existing)
					new_verified = batch and not all(_is_unchecked_row(i) for i in batch)
					if existing_unverified and new_verified:
						final_results[:] = [i for i in final_results if i.get('debrid') != provider]
						final_results.extend(batch)
					return
				final_results.extend(batch)
		def _process_cache_check(provider, function):
			incomplete, cached = False, []
			try:
				if _debrid_api_check_enabled(provider):
					if provider in ('Real-Debrid', 'AllDebrid'):
						cached = function(hash_list, cached_hashes, self.data, self.active_debrid)
					else:
						cached = function(hash_list, cached_hashes)
					if cached is None:
						incomplete = True
						cached = []
				else:
					cached = hash_list
			except Exception as e:
				incomplete = True
				cached = []
				try:
					kodi_utils.logger('DebridCacheCheck', 'provider=%s thread=%s' % (provider, type(e).__name__))
				except: pass
			api_blocked = kodi_utils.get_property('redlight.debrid_cache_api_error') if provider == 'AllDebrid' else ''
			if api_blocked:
				if not self.background:
					kodi_utils.notification('AllDebrid cache check unavailable (%s). Showing unchecked sources.' % api_blocked, 6000)
					kodi_utils.clear_property('redlight.debrid_cache_api_error')
				batch = _unchecked_batch(provider, api_blocked)
			elif incomplete:
				batch = _unchecked_batch(provider, 'incomplete_check')
			else:
				cached_set = set(str(i).lower() for i in cached)
				if not self.background: self.process_quality_count_final([i for i in results if i.get('hash', '').lower() in cached_set])
				batch = [dict(i, **{'cache_provider': provider if i.get('hash', '').lower() in cached_set else 'Uncached %s' % provider, 'debrid': provider}) for i in results]
			_commit_cache_batch(provider, batch)
		def _apply_missing_provider_fallback(providers_needing_api):
			with final_lock:
				missing_providers = [p for p in providers_needing_api if p not in _providers_with_rows()]
			if not missing_providers:
				with final_lock:
					frozen_providers.update(providers_needing_api)
				return
			unchecked_batches = [(provider, _unchecked_batch(provider, 'incomplete_check')) for provider in missing_providers]
			with final_lock:
				for provider, batch in unchecked_batches:
					if provider in _providers_with_rows():
						continue
					final_results.extend(batch)
				verified = set(i.get('debrid') for i in final_results if i.get('debrid') and not _is_unchecked_row(i))
				if verified:
					final_results[:] = [i for i in final_results if not (
						i.get('debrid') in verified and _is_unchecked_row(i))]
			with final_lock:
				frozen_providers.update(providers_needing_api)
				still_unchecked = [p for p in providers_needing_api if p in set(
					i.get('debrid') for i in final_results if _is_unchecked_row(i))]
			try:
				if still_unchecked:
					kodi_utils.logger('DebridCacheCheck', 'warning=incomplete_check fallback=unchecked providers=%s hashes=%d' % (
						','.join(still_unchecked), len(hash_list)))
			except: pass
		def _debrid_check_dialog(debrid_deadline):
			# Do not clear a user Back/cancel from the scrape phase — that made cancel
			# look ignored while cache-check continued and could reopen progress UI.
			if self.progress_dialog.iscanceled():
				return
			self.progress_dialog.reset_is_cancelled()
			start_time = time.time()
			debrid_timeout = max(1.0, debrid_deadline - start_time)
			while not self.progress_dialog.iscanceled() and not self.monitor.abortRequested():
				try:
					remaining_debrids = [x.getName() for x in debrid_check_threads if x.is_alive() is True]
					current_progress = max((time.time() - start_time), 0)
					line1 = ', '.join(remaining_debrids).upper()
					percent = min(100, int((current_progress / float(debrid_timeout)) * 100))
					self.progress_dialog.update_scraper(self.final_sd, self.final_720p, self.final_1080p, self.final_4k, self.final_total, line1, percent)
					kodi_utils.sleep(100)
					if len(remaining_debrids) == 0: break
					if time.time() >= debrid_deadline: break
				except: pass
		def _log_debrid_cache_summary(final_results, providers_needing_api):
			try:
				uncached = sum(1 for i in final_results if str(i.get('cache_provider', '')).startswith('Uncached '))
				unchecked = sum(1 for i in final_results if str(i.get('cache_provider', '')).startswith('Unchecked '))
				cached = len(final_results) - uncached - unchecked
				kodi_utils.logger('DebridCacheCheck', 'enabled=%s providers=%s total=%d cached=%d uncached=%d unchecked=%d' % (
					bool(providers_needing_api), ','.join(providers_needing_api) or 'none', len(final_results), cached, uncached, unchecked))
			except: pass
		try:
			if not self.background and self.all_internal_sources: self.process_quality_count_final(self.all_internal_sources)
			final_results = []
			results = list(_process_duplicates(results))
			hash_list = list(set([i['hash'].lower() for i in results if i.get('hash') and len(i['hash']) == 40]))
			cached_hashes = query_local_cache(hash_list)
			providers_needing_api = [p for p in self.active_debrid if _debrid_api_check_enabled(p)]
			if not providers_needing_api:
				for provider in self.active_debrid:
					if not self.background:
						self.process_quality_count_final(results)
					batch = [dict(i, **{'cache_provider': provider, 'debrid': provider}) for i in results]
					final_results.extend(batch)
				_log_debrid_cache_summary(final_results, providers_needing_api)
				return final_results
			debrid_check_threads = [Thread(target=_process_cache_check, args=self.debrid_runners[item], name=item) for item in providers_needing_api]
			hash_budget = max(0, len(hash_list))
			debrid_timeout = max(45, min(240, 30 + (hash_budget // 25) * 8))
			debrid_deadline = time.time() + debrid_timeout
			for provider in self.active_debrid:
				if provider in providers_needing_api:
					continue
				if not self.background:
					self.process_quality_count_final(results)
				final_results.extend([dict(i, **{'cache_provider': provider, 'debrid': provider}) for i in results])
			if len(providers_needing_api) == 1 and not self.background:
				debrid_check_threads[0].start()
				_debrid_check_dialog(debrid_deadline)
				debrid_check_threads[0].join(timeout=max(0.0, debrid_deadline - time.time()))
			else:
				[i.start() for i in debrid_check_threads]
				if self.background:
					for thread in debrid_check_threads:
						thread.join(timeout=max(0.0, debrid_deadline - time.time()))
				else:
					_debrid_check_dialog(debrid_deadline)
					for thread in debrid_check_threads:
						thread.join(timeout=max(0.0, debrid_deadline - time.time()))
			grace_deadline = time.time() + 2.0
			for thread in debrid_check_threads:
				if thread.is_alive():
					thread.join(timeout=max(0.0, grace_deadline - time.time()))
			_apply_missing_provider_fallback(providers_needing_api)
			_log_debrid_cache_summary(final_results, providers_needing_api)
			return final_results
		except: return []

	def process_sources(self, provider, sources, external_module=''):
		try:
			for i in sources:
				try:
					i_get = i.get
					size, size_label, divider = 0, None, None
					if 'hash' in i:
						_hash = i_get('hash').lower()
						i['hash'] = str(_hash)
					display_name = clean_file_name(source_utils.normalize(i['name'].replace('html', ' ').replace('+', ' ').replace('-', ' ')))
					if 'name_info' in i: quality, extraInfo = source_utils.get_file_info(name_info=i_get('name_info'))
					else: quality, extraInfo = source_utils.get_file_info(url=i_get('url'))
					try:
						size = i_get('size')
						if 'package' in i and provider not in ('torrentio', 'knightcrawler', 'selfhosted'):
							if i_get('package') == 'season': divider = self.season_divider
							else: divider = self.show_divider
							size = float(size) / divider
						size_label = '%.2f GB' % size
					except: pass
					extra = {'provider': provider, 'display_name': display_name, 'external': True, 'scrape_provider': self.scrape_provider, 'extraInfo': extraInfo,
							'quality': quality, 'size_label': size_label, 'size': round(size, 2)}
					if external_module: extra['external_module'] = external_module
					i.update(extra)
				except: pass
		except: pass
		return sources

	def process_quality_count(self, sources):
		for item in self.count_tuple: setattr(self, item[0], getattr(self, item[0]) + item[2](sources, item[1]))
	
	def process_quality_count_final(self, sources):
		for item in self.count_tuple_final: setattr(self, item[0], getattr(self, item[0]) + item[2](sources, item[1]))

	def _join_scraper_threads_grace(self, grace_seconds=8):
		"""After the scrape timeout, allow slow host threads a short window to finish."""
		deadline = time.time() + grace_seconds
		while time.time() < deadline:
			if not any(x.is_alive() for x in self.threads):
				return
			try:
				if self.internal_activated or self.internal_prescraped:
					self.process_internal_results()
				self.poll_cloud_scrapers()
			except: pass
			kodi_utils.sleep(100)

	def poll_cloud_scrapers(self):
		for scraper in self.cloud_scrapers:
			if scraper in self.processed_cloud_scrapers:
				continue
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % scraper)
			if win_property in ('checked', '', None):
				continue
			try: internal_sources = json.loads(win_property)
			except: continue
			self.processed_cloud_scrapers.add(scraper)
			self.process_quality_count(internal_sources)

	def process_internal_results(self):
		if self.internal_prescraped and not self.processed_prescrape:
			self.all_internal_sources += self.prescrape_sources
			self.process_quality_count(self.prescrape_sources)
			self.processed_prescrape = True
		for i in self.internal_scrapers:
			if i == 'external': continue
			win_property = kodi_utils.get_property('redlight.internal_results.%s' % i)
			if win_property in ('checked', '', None): continue
			try: internal_sources = json.loads(win_property)
			except: continue
			kodi_utils.set_property('redlight.internal_results.%s' % i, 'checked')
			self.all_internal_sources += internal_sources
			self.processed_internal_scrapers_append(i)
			self.process_quality_count(internal_sources)
		return [i for i in self.internal_scrapers if i != 'external' and i not in self.processed_internal_scrapers]

	def _quality_length(self, items, quality):
		return len([i for i in items if i['quality'] == quality])

	def _quality_length_sd(self, items, dummy):
		return len([i for i in items if i['quality'] in ('SD', 'CAM', 'TELE', 'SYNC')])

	def quality_length_final(self, items, dummy):
		return len(items)