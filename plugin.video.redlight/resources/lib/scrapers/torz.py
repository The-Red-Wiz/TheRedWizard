# -*- coding: utf-8 -*-
from apis import torz_api
from modules import source_utils
from modules.native_torrents import filter_and_build_sources, scrape_expiry, scrape_timeout
from modules.settings import torz_scrape_active
from modules.kodi_utils import logger


class source:
	def __init__(self):
		self.scrape_provider = 'torz'
		self.sources = []

	def results(self, info):
		try:
			if not torz_scrape_active():
				return source_utils.internal_results(self.scrape_provider, self.sources)
			imdb_id = info.get('imdb_id')
			if not imdb_id:
				return source_utils.internal_results(self.scrape_provider, self.sources)
			streams = torz_api.search_streams(
				imdb_id, info.get('media_type'), info.get('season'), info.get('episode'),
				timeout=scrape_timeout(info), expiration=scrape_expiry(info))
			self.sources = filter_and_build_sources(self.scrape_provider, streams, info)
			logger('torz scraper', '%s : %s kept / %s raw' % (info.get('title', ''), len(self.sources), len(streams or [])))
		except Exception as e:
			logger('torz scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources
