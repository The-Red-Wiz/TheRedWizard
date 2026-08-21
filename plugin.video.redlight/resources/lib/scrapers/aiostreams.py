# -*- coding: utf-8 -*-
from apis import aiostreams_api
from modules import source_utils
from modules.utils import clean_file_name, normalize
from modules.settings import filter_by_name
from caches.settings_cache import get_setting
from modules.kodi_utils import logger

class source:
	def __init__(self):
		self.scrape_provider = 'aiostreams'
		self.sources = []
		self.errors = []

	def results(self, info):
		try:
			if not aiostreams_api.ENABLED: return source_utils.internal_results(self.scrape_provider, self.sources)
			if not aiostreams_api.auth(): return source_utils.internal_results(self.scrape_provider, self.sources)
			filter_title = filter_by_name(self.scrape_provider)
			self.media_type = info.get('media_type')
			title = info.get('title', '')
			self.year = int(info.get('year') or 0)
			self.season, self.episode = info.get('season'), info.get('episode')
			imdb_id = info.get('imdb_id')
			tmdb_id = info.get('tmdb_id')
			self.aliases = source_utils.get_aliases_titles(info.get('aliases', []))
			timeout = int(get_setting('redlight.results.timeout', '60'))
			if 'timeout' in info: timeout = max(1, int(info['timeout']) - 1)
			scrape_results, self.errors = aiostreams_api.search(
				self.media_type, imdb_id, self.season, self.episode, timeout=timeout, tmdb_id=tmdb_id)
			if self.errors and not scrape_results:
				logger('aiostreams scraper', 'API errors: %s' % '; '.join(self.errors))
			if not scrape_results: return source_utils.internal_results(self.scrape_provider, self.sources)
			extras = source_utils.extras()
			raw_count = len(scrape_results)
			skipped = {'p2p': 0, 'no_name': 0, 'extras': 0, 'title_filter': 0, 'no_url': 0, 'exception': 0}
			def _process():
				for aio_order, raw in enumerate(scrape_results):
					try:
						merged = aiostreams_api.flatten_result(raw)
						if 'p2p' in (merged.get('type') or '').lower():
							skipped['p2p'] += 1
							continue
						file_name = merged.get('filename') or merged.get('name') or ''
						if not file_name:
							skipped['no_name'] += 1
							continue
						file_name = normalize(file_name)
						if any(x in file_name.lower() for x in extras):
							skipped['extras'] += 1
							continue
						if filter_title and not source_utils.check_title(title, file_name, self.aliases, self.year, self.season, self.episode):
							skipped['title_filter'] += 1
							continue
						url = merged.get('url')
						if not url:
							skipped['no_url'] += 1
							continue
						display_name = clean_file_name(file_name).replace('html', ' ').replace('+', ' ').replace('-', ' ')
						size_bytes = merged.get('size') or 0
						try: size = round(float(size_bytes) / 1073741824, 2)
						except: size = 0.0
						video_quality, details = source_utils.get_file_info(name_info=source_utils.release_info_format(file_name))
						resolution = merged.get('resolution') or merged.get('quality')
						if resolution:
							res_key = str(resolution).upper()
							if res_key in ('4K', '2160P'): video_quality = '4K'
							elif res_key in ('1080P', '1080'): video_quality = '1080p'
							elif res_key in ('720P', '720'): video_quality = '720p'
							elif res_key == 'SD': video_quality = 'SD'
						request_headers = aiostreams_api.playback_headers(merged)
						panel_label, aio_short, aio_name, aio_icon = aiostreams_api.inner_source_display(merged)
						site_name = aiostreams_api.origin_site_label(merged)
						hoster = aiostreams_api.hoster_label(merged)
						release_group = aiostreams_api.release_group_label(merged, file_name)
						extra_tags = []
						for key in ('encode', 'quality'):
							val = merged.get(key)
							if val and str(val) not in extra_tags: extra_tags.append(str(val))
						for tag in merged.get('visualTags') or ():
							if tag and str(tag) not in extra_tags: extra_tags.append(str(tag))
						if extra_tags:
							tag_line = ' | '.join(extra_tags)
							details = '%s | %s' % (details, tag_line) if details else tag_line
						source_item = {'name': file_name, 'display_name': display_name, 'quality': video_quality, 'size': size,
									'size_label': '%.2f GB' % size if size else 'N/A', 'debrid': self.scrape_provider, 'source': self.scrape_provider,
									'aio_order': aio_order, 'aio_source_label': panel_label, 'aio_source': aio_short, 'aio_source_name': aio_name, 'aio_source_icon': aio_icon,
									'aio_site_name': site_name, 'aio_hoster': hoster, 'aio_release_group': release_group,
									'extraInfo': details, 'url_dl': url, 'url': url, 'id': url, 'direct': True, 'local': False,
									'scrape_provider': self.scrape_provider, 'request_headers': request_headers}
						yield source_item
					except Exception as e:
						skipped['exception'] += 1
						logger('aiostreams scraper yield source error', str(e))
			self.sources = list(_process())
			logger('aiostreams scraper', '%s : %s kept / %s raw' % (title, len(self.sources), raw_count))
			if raw_count and not self.sources:
				dropped = ', '.join('%s=%s' % (k, v) for k, v in skipped.items() if v)
				logger('aiostreams scraper', 'all raw results dropped (%s)' % dropped)
			elif any(skipped.values()):
				dropped = ', '.join('%s=%s' % (k, v) for k, v in skipped.items() if v)
				logger('aiostreams scraper', 'dropped (%s)' % dropped)
		except Exception as e:
			logger('aiostreams scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources
