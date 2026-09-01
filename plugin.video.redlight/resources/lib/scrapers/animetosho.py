# -*- coding: utf-8 -*-
from apis import animetosho_api
from modules import source_utils
from modules.native_torrents import filter_and_build_sources, merge_name_searches, name_search_queries, scrape_expiry, scrape_timeout
from modules.settings import animetosho_scrape_active
from modules.kodi_utils import logger


class source:
	def __init__(self):
		self.scrape_provider = 'animetosho'
		self.sources = []

	def results(self, info):
		try:
			if not animetosho_scrape_active():
				return source_utils.internal_results(self.scrape_provider, self.sources)
			files = merge_name_searches(
				animetosho_api.search, name_search_queries(info), scrape_timeout(info), scrape_expiry(info))
			self.sources = filter_and_build_sources(self.scrape_provider, files, info)
			logger('animetosho scraper', '%s : %s kept / %s raw' % (info.get('title', ''), len(self.sources), len(files)))
		except Exception as e:
			logger('animetosho scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources
