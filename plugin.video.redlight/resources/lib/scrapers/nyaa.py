# -*- coding: utf-8 -*-
from apis import nyaa_api
from modules import source_utils
from modules.utils import clean_file_name
from modules.native_torrents import build_source, pack_type_from_name, apply_pack_size
from modules.settings import filter_by_name, filter_by_episode_title, nyaa_scrape_active
from caches.settings_cache import get_setting
from modules.kodi_utils import logger


class source:
	def __init__(self):
		self.scrape_provider = 'nyaa'
		self.sources = []

	def results(self, info):
		try:
			if not nyaa_scrape_active():
				return source_utils.internal_results(self.scrape_provider, self.sources)
			filter_title = filter_by_name(self.scrape_provider)
			allow_episode_title = filter_by_episode_title(self.scrape_provider)
			media_type = info.get('media_type')
			title = info.get('title', '')
			self.year = int(info.get('year') or 0)
			season, episode = info.get('season'), info.get('episode')
			self.search_title = clean_file_name(title).replace('&', 'and')
			aliases = source_utils.get_aliases_titles(info.get('aliases', []))
			absolute_episode = info.get('absolute_episode')
			ep_name = info.get('ep_name') or ''
			expiry = int((info.get('expiry_times') or [24])[0] or 24)
			timeout = int(get_setting('redlight.results.timeout', '20'))
			files = self._merge_searches(self._search_queries(media_type, season, episode, absolute_episode, aliases), timeout, expiry)
			if not files:
				return source_utils.internal_results(self.scrape_provider, self.sources)
			extras = source_utils.extras()
			season_divider = int(info.get('season_episode_count') or 1) or 1
			show_divider = int(info.get('total_aired_eps') or 1) or 1
			raw_count = len(files)
			seen = set()

			def _keep(file_name):
				if any(x in file_name.lower() for x in extras):
					return False, None
				if not filter_title:
					return True, pack_type_from_name(file_name, season)
				if source_utils.check_title_or_absolute(
						title, file_name, aliases, self.year, season, episode, absolute_episode, ep_name, allow_episode_title):
					return True, None
				package = pack_type_from_name(file_name, season)
				if package and source_utils.check_title(title, file_name, aliases, self.year, 'pack', episode):
					return True, package
				return False, None

			for raw in files:
				try:
					info_hash = raw.get('hash')
					if not info_hash or info_hash in seen:
						continue
					file_name = raw.get('name') or ''
					keep, package = _keep(file_name)
					if not keep:
						continue
					seen.add(info_hash)
					size = apply_pack_size(raw.get('size') or 0, package, season_divider, show_divider)
					self.sources.append(build_source(
						self.scrape_provider, file_name, info_hash, size, raw.get('seeders') or 0, package))
				except Exception as e:
					logger('nyaa scraper yield source error', str(e))
			logger('nyaa scraper', '%s : %s kept / %s raw' % (title, len(self.sources), raw_count))
		except Exception as e:
			logger('nyaa scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources

	def _add_query(self, queries, seen, query):
		query = (query or '').strip()
		if not query or query in seen:
			return
		seen.add(query)
		queries.append(query)

	def _search_queries(self, media_type, season, episode, absolute_episode, aliases):
		queries, seen = [], set()
		if media_type == 'movie':
			self._add_query(queries, seen, '%s %d' % (self.search_title, self.year))
			for alias in aliases:
				name = clean_file_name(alias).replace('&', 'and')
				if name and name != self.search_title:
					self._add_query(queries, seen, '%s %d' % (name, self.year))
			return queries
		hdlr = 'S%02dE%02d' % (int(season), int(episode))
		hdlr_alt = 'S%dE%d' % (int(season), int(episode))
		self._add_query(queries, seen, '%s %s' % (self.search_title, hdlr))
		if hdlr_alt != hdlr:
			self._add_query(queries, seen, '%s %s' % (self.search_title, hdlr_alt))
		if absolute_episode not in (None, '', 0, '0'):
			try:
				abs_i = int(absolute_episode)
			except Exception:
				abs_i = None
			if abs_i:
				self._add_query(queries, seen, '%s - %s' % (self.search_title, abs_i))
				self._add_query(queries, seen, '%s %s' % (self.search_title, abs_i))
				if abs_i >= 100:
					self._add_query(queries, seen, '%s - %03d' % (self.search_title, abs_i))
		for alias in aliases[:2]:
			name = clean_file_name(alias).replace('&', 'and')
			if not name or name == self.search_title:
				continue
			self._add_query(queries, seen, '%s %s' % (name, hdlr))
		return queries

	def _merge_searches(self, queries, timeout, expiry):
		files, seen = [], set()
		per_query = max(5, min(10, int(timeout) // max(1, len(queries) or 1)))
		for query in queries:
			for item in nyaa_api.search(query, timeout=per_query, expiration=expiry) or []:
				info_hash = item.get('hash')
				if info_hash and info_hash not in seen:
					seen.add(info_hash)
					files.append(item)
		return files
