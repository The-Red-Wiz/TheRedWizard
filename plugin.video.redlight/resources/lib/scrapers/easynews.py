# -*- coding: utf-8 -*-
from apis.easynews_api import EasyNews
from modules import source_utils
from modules.utils import clean_file_name, normalize
from modules.settings import filter_by_name, filter_by_episode_title, easynews_language_filter, easynews_lang_include_unknown, easynews_fallback_search, easynews_search_width
# from modules.kodi_utils import logger

class source:
	def __init__(self):
		self.scrape_provider = 'easynews'
		self.sources = []

	def results(self, info):
		try:
			filter_lang, lang_filters = easynews_language_filter()
			include_unknown = easynews_lang_include_unknown()
			filter_title = filter_by_name('easynews')
			allow_episode_title = filter_by_episode_title('easynews')
			self.media_type, title, self.year, self.season, self.episode = info.get('media_type'), info.get('title'), int(info.get('year')), info.get('season'), info.get('episode')
			self.search_title = clean_file_name(title).replace('&', 'and')
			self.aliases = source_utils.get_aliases_titles(info.get('aliases', []))
			self.absolute_episode = info.get('absolute_episode')
			self.ep_name = info.get('ep_name') or ''
			expiry = info.get('expiry_times')[0]
			primary = self._search_name()
			files = self._merge_searches(self._search_queries(), expiry)
			if not files and easynews_fallback_search(): files = self._merge_searches(self._fallback_search_queries(primary), expiry, files)
			if not files: return source_utils.internal_results(self.scrape_provider, self.sources)
			extras = source_utils.extras()
			def _process():
				for item in files:
					try:
						if item.get('short_vid', False): continue
						file_name = normalize(item['name'])
						if any(x in file_name.lower() for x in extras): continue
						if filter_title and not source_utils.check_title_or_absolute(
								title, file_name, self.aliases, self.year, self.season, self.episode, self.absolute_episode, self.ep_name, allow_episode_title): continue
						if filter_lang and not self._language_ok(item['language'], lang_filters, include_unknown): continue
						display_name = clean_file_name(file_name).replace('html', ' ').replace('+', ' ').replace('-', ' ')
						url_dl, size = item['url_dl'], round(float(int(item['rawSize']))/1073741824, 2)
						video_quality, details = source_utils.get_file_info(name_info=source_utils.release_info_format(file_name),
									default_quality=self._quality_estimate(int(item.get('width', 0))))
						source_item = {'name': file_name, 'display_name': display_name, 'quality': video_quality, 'size': size, 'size_label': '%.2f GB' % size, 'debrid': self.scrape_provider,
									'extraInfo': details, 'url_dl': url_dl, 'down_url': item['down_url'], 'id': url_dl, 'local': False, 'direct': True, 'source': self.scrape_provider,
									'scrape_provider': self.scrape_provider}
						yield source_item
					except Exception as e:
						from modules.kodi_utils import logger
						logger('easynews scraper yield source error', str(e))
			self.sources = list(_process())
		except Exception as e:
			from modules.kodi_utils import logger
			logger('easynews scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources

	def _language_ok(self, language, lang_filters, include_unknown):
		if not language: return include_unknown
		if isinstance(language, (list, tuple)): parts = [str(i).lower() for i in language]
		else: parts = [str(language).lower()]
		return any(p in lang_filters for p in parts)

	def _merge_searches(self, queries, expiry, files=None):
		if files is None: files = []
		seen = {i.get('url_dl') for i in files if i.get('url_dl')}
		for query in queries:
			for item in EasyNews.search(query, expiry) or []:
				if not isinstance(item, dict): continue
				url = item.get('url_dl')
				if url and url not in seen:
					seen.add(url)
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
		width = easynews_search_width()
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
		queries = []
		seen = {primary}
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

	def _quality_estimate(self, width):
		if width > 1920: return '4K'
		if 1280 < width <= 1920: return '1080p'
		if 720 < width <= 1280: return '720p'
		return 'SD'

	def _search_name(self):
		if self.media_type == 'movie': return '%s %d' % (self.search_title, self.year)
		else: return '%s S%02dE%02d' % (self.search_title,  self.season, self.episode)
