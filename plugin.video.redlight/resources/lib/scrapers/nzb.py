# -*- coding: utf-8 -*-
from apis.nzb_api import search_all, nzb_link_hash
from modules import source_utils
from modules.utils import clean_file_name, normalize
from modules.settings import filter_by_name, filter_by_episode_title, nzb_fallback_search, nzb_search_width, nzb_scrape_active
# from modules.kodi_utils import logger

class source:
	def __init__(self):
		self.scrape_provider = 'nzb'
		self.sources = []

	def results(self, info):
		try:
			if not nzb_scrape_active(): return source_utils.internal_results(self.scrape_provider, self.sources)
			filter_title = filter_by_name('nzb')
			allow_episode_title = filter_by_episode_title('nzb')
			self.media_type, title, self.year, self.season, self.episode = info.get('media_type'), info.get('title'), int(info.get('year')), info.get('season'), info.get('episode')
			self.search_title = clean_file_name(title).replace('&', 'and')
			self.aliases = source_utils.get_aliases_titles(info.get('aliases', []))
			self.absolute_episode = info.get('absolute_episode')
			self.ep_name = info.get('ep_name') or ''
			expiry = info.get('expiry_times')[0]
			primary = self._search_name()
			files = self._merge_searches(self._search_queries(), expiry)
			if not files and nzb_fallback_search(): files = self._merge_searches(self._fallback_search_queries(primary), expiry, files)
			if not files: return source_utils.internal_results(self.scrape_provider, self.sources)
			cached_hashes = self._torbox_cached_hashes([i.get('link', '') for i in files if i.get('link')])
			extras = source_utils.extras()
			def _process():
				for item in files:
					try:
						file_name = normalize(item.get('name', ''))
						if not file_name or any(x in file_name.lower() for x in extras): continue
						if filter_title and not source_utils.check_title_or_absolute(
								title, file_name, self.aliases, self.year, self.season, self.episode, self.absolute_episode, self.ep_name, allow_episode_title): continue
						nzb_link = item.get('link', '')
						if not nzb_link: continue
						nzb_hash = nzb_link_hash(nzb_link)
						display_name = clean_file_name(file_name).replace('html', ' ').replace('+', ' ').replace('-', ' ')
						size_bytes = int(item.get('size', 0) or 0)
						size = round(size_bytes / 1073741824.0, 2) if size_bytes else 0.0
						size_label = '%.2f GB' % size if size_bytes else 'N/A'
						video_quality, details = source_utils.get_file_info(name_info=source_utils.release_info_format(file_name))
						indexer = item.get('indexer', 'NZB')
						if indexer and indexer not in details: details = '%s | Site: %s' % (details, indexer)
						source_item = {'name': file_name, 'display_name': display_name, 'quality': video_quality, 'size': size,
									'size_label': size_label, 'debrid': self.scrape_provider, 'extraInfo': details,
									'url_dl': nzb_link, 'id': nzb_hash, 'nzb_link': nzb_link, 'nzb_hash': nzb_hash,
									'nzb_indexer': indexer, 'nzb_cached': nzb_hash in cached_hashes,
									'local': False, 'direct': False, 'source': self.scrape_provider, 'scrape_provider': self.scrape_provider}
						yield source_item
					except Exception as e:
						from modules.kodi_utils import logger
						logger('nzb scraper yield source error', str(e))
			self.sources = list(_process())
		except Exception as e:
			from modules.kodi_utils import logger
			logger('nzb scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources

	def _torbox_cached_hashes(self, links):
		try:
			from apis.torbox_api import TorBoxAPI
			hashes = [nzb_link_hash(link) for link in links if link]
			return TorBoxAPI().usenet_hashes_cached(hashes)
		except: return set()

	def _merge_searches(self, queries, expiry, files=None):
		if files is None: files = []
		seen = {i.get('link') for i in files if i.get('link')}
		for query in queries:
			for item in search_all(query, expiration=expiry) or []:
				link = item.get('link')
				if link and link not in seen:
					seen.add(link)
					files.append(item)
		return files

	def _add_query(self, queries, seen, query):
		if query and query not in seen:
			seen.add(query)
			queries.append(query)

	def _search_queries(self):
		primary = self._search_name()
		seen = {primary}
		queries = [primary]
		width = nzb_search_width()
		if width >= 1:
			if self.media_type == 'movie': self._add_query(queries, seen, self.search_title)
			else: self._add_query(queries, seen, '%s S%02d' % (self.search_title, self.season))
		if width >= 2:
			if self.media_type != 'movie': self._add_query(queries, seen, self.search_title)
			for alias in self.aliases:
				name = clean_file_name(alias).replace('&', 'and')
				if name == self.search_title: continue
				if self.media_type == 'movie':
					self._add_query(queries, seen, '%s %d' % (name, self.year))
					self._add_query(queries, seen, name)
				else:
					self._add_query(queries, seen, '%s S%02dE%02d' % (name, self.season, self.episode))
					self._add_query(queries, seen, '%s S%02d' % (name, self.season))
		return queries

	def _fallback_search_queries(self, primary):
		queries, seen = [], {primary}
		for query in self._search_queries():
			seen.add(query)
		for alias in self.aliases:
			name = clean_file_name(alias).replace('&', 'and')
			if name == self.search_title: continue
			if self.media_type == 'movie':
				self._add_query(queries, seen, '%s %d' % (name, self.year))
			else:
				self._add_query(queries, seen, '%s S%02dE%02d' % (name, self.season, self.episode))
				self._add_query(queries, seen, '%s S%02d' % (name, self.season))
		return queries

	def _search_name(self):
		if self.media_type == 'movie': return '%s %d' % (self.search_title, self.year)
		return '%s S%02dE%02d' % (self.search_title, self.season, self.episode)
