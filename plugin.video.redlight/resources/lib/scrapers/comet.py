# -*- coding: utf-8 -*-
from apis import comet_api
from modules import source_utils
from modules.native_torrents import build_source, pack_type_from_name, apply_pack_size
from modules.settings import filter_by_name, filter_by_episode_title, comet_scrape_active
from caches.settings_cache import get_setting
from modules.kodi_utils import logger


class source:
	def __init__(self):
		self.scrape_provider = 'comet'
		self.sources = []

	def results(self, info):
		try:
			if not comet_scrape_active():
				return source_utils.internal_results(self.scrape_provider, self.sources)
			imdb_id = info.get('imdb_id')
			if not imdb_id:
				return source_utils.internal_results(self.scrape_provider, self.sources)
			filter_title = filter_by_name(self.scrape_provider)
			allow_episode_title = filter_by_episode_title(self.scrape_provider)
			media_type = info.get('media_type')
			title = info.get('title', '')
			year = int(info.get('year') or 0)
			season, episode = info.get('season'), info.get('episode')
			aliases = source_utils.get_aliases_titles(info.get('aliases', []))
			absolute_episode = info.get('absolute_episode')
			ep_name = info.get('ep_name') or ''
			expiry = int((info.get('expiry_times') or [24])[0] or 24)
			timeout = int(get_setting('redlight.results.timeout', '20'))
			if 'timeout' in info:
				timeout = max(5, int(info['timeout']) - 1)
			streams = comet_api.search_streams(imdb_id, media_type, season, episode, timeout=min(timeout, 20), expiration=expiry)
			if not streams:
				return source_utils.internal_results(self.scrape_provider, self.sources)
			extras = source_utils.extras()
			season_divider = int(info.get('season_episode_count') or 1) or 1
			show_divider = int(info.get('total_aired_eps') or 1) or 1
			raw_count = len(streams)
			seen = set()

			def _keep(file_name):
				if any(x in file_name.lower() for x in extras):
					return False, None
				if not filter_title:
					return True, pack_type_from_name(file_name, season)
				if source_utils.check_title_or_absolute(
						title, file_name, aliases, year, season, episode, absolute_episode, ep_name, allow_episode_title):
					return True, None
				package = pack_type_from_name(file_name, season)
				if package and source_utils.check_title(title, file_name, aliases, year, 'pack', episode):
					return True, package
				return False, None

			for raw in streams:
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
					logger('comet scraper yield source error', str(e))
			logger('comet scraper', '%s : %s kept / %s raw' % (title, len(self.sources), raw_count))
		except Exception as e:
			logger('comet scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources
