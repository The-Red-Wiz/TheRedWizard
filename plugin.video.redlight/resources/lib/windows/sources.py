# -*- coding: utf-8 -*-
import json
from threading import Thread
from windows.base_window import BaseDialog
from caches.settings_cache import get_setting, set_setting
from modules.debrid import debrid_cache_check_available
from modules.settings import debrid_cache_check, external_module_display_name
from modules.utils import TaskPool
from modules.source_utils import source_filters
from modules.settings import provider_sort_ranks, avoid_episode_spoilers, show_loading_plot, max_threads
from modules.native_torrents import NATIVE_INDEXER_SCRAPERS, NATIVE_TORRENT_SCRAPERS
from modules.kodi_utils import get_icon, kodi_dialog, hide_busy_dialog, show_busy_dialog, close_dialog, addon_fanart, select_dialog, ok_dialog, notification, clear_property

def _highlight_with_alpha(color, alpha):
	if not color: return color or 'FFCCCCCC'
	color = color.strip().replace('#', '')
	if len(color) == 8: return alpha + color[2:]
	if len(color) == 6: return alpha + color
	return color

class SourcesResults(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.window_format = kwargs.get('window_format', 'list')
		self.window_id = kwargs.get('window_id', 2000)
		self.filter_window_id = 2100
		self.results = kwargs.get('results')
		self.uncached_results = kwargs.get('uncached_results', [])
		self.info_highlights_dict = kwargs.get('scraper_settings')
		self.episode_group_label = kwargs.get('episode_group_label', '')
		self.prescrape = kwargs.get('prescrape')
		self.meta = kwargs.get('meta')
		self.sources_ref = kwargs.get('sources_ref')
		self.filters_ignored = kwargs.get('filters_ignored', False)
		self.selected = (None, '')
		self.meta_get = self.meta.get
		self.make_poster = self.window_format in ('list', 'medialist')
		self.empty_poster = get_icon('box_office')
		self.addon_fanart = addon_fanart()
		self.poster = self.meta_get('poster') or self.empty_poster
		self.cache_check_override = kwargs.get('cache_check_override')
		self.prerelease_values, self.prerelease_key = ('CAM', 'SCR', 'TELE'), 'CAM/SCR/TELE'
		self.item_list, self.filter_list, self.total_results = [], [], '0'
		self.info_icons_dict = {'easynews': get_icon('easynews'), 'aiostreams': get_icon('premiumize'), 'nzb': get_icon('torbox'), 'alldebrid': get_icon('alldebrid'), 'real-debrid': get_icon('realdebrid'),
		'premiumize': get_icon('premiumize'), 'offcloud': get_icon('offcloud'), 'torbox': get_icon('torbox'), 'ad_cloud': get_icon('alldebrid'), 'rd_cloud': get_icon('realdebrid'),
		'pm_cloud': get_icon('premiumize'), 'oc_cloud': get_icon('offcloud'), 'tb_cloud': get_icon('torbox')}
		self.info_quality_dict = {'4k': get_icon('flag_4k', 'flags'), '1080p': get_icon('flag_1080p', 'flags'), '720p': get_icon('flag_720p', 'flags'),
		'sd': get_icon('flag_sd', 'flags'), 'cam': get_icon('flag_sd', 'flags'), 'tele': get_icon('flag_sd', 'flags'), 'scr': get_icon('flag_sd', 'flags')}
		self.tint_focused_background = get_setting('redlight.highlight.tint_focused_background') == 'true'
		self.highlight_alpha = get_setting('redlight.highlight.background_opacity', '66')
		self.make_items()
		self.make_filter_items()
		self.set_properties()

	def _any_cache_check_active(self):
		if self.cache_check_override is not None:
			return self.cache_check_override
		from modules.settings import any_external_cache_check
		return any_external_cache_check()

	def _provider_cache_verified(self, provider):
		if self.cache_check_override is not None:
			return self.cache_check_override
		return debrid_cache_check(provider)

	def onInit(self):
		self.filter_applied = False
		hide_busy_dialog()
		# Ready / Next Up toasts (6.5s) sit on top of the first result row after Autoscrape Stop.
		close_dialog('notification')
		self.set_properties()
		if self.make_poster: self.set_poster()
		self.add_items(self.window_id, self.item_list)
		self.add_items(self.filter_window_id, self.filter_list)
		self._focus_results_list()

	def _focus_results_list(self):
		try: self.select_item(self.window_id, 0)
		except: pass
		try: self.setFocusId(self.window_id)
		except: pass
		try:
			if self.get_visibility('Control.HasFocus(%s)' % self.window_id): return
		except: pass
		Thread(target=self._retry_results_focus, daemon=True).start()

	def _retry_results_focus(self):
		# List is often not focusable on the first onInit tick (empty → "Control 2000 ... can't").
		# Without focus, the selected row uses the dimmed focused layout (dark-on-tint).
		for _ in range(20):
			self.sleep(50)
			try:
				self.setFocusId(self.window_id)
				if self.get_visibility('Control.HasFocus(%s)' % self.window_id): return
			except: return

	def run(self):
		self.doModal()
		self.clearProperties()
		self.clear_home_property('window_theme.sources')
		action = self.selected[0] if self.selected else None
		if action != 'play':
			hide_busy_dialog()
		return self.selected

	def get_provider_and_path(self, provider):
		try: return provider, self.info_icons_dict[provider]
		except: return 'folders', get_icon('folder')

	def get_quality_and_path(self, quality):
		try: return quality, self.info_quality_dict[quality]
		except: return 'sd', get_icon('flag_sd')

	def filter_action(self, action):
		if action == self.right_action or action in self.closing_actions:
			self.select_item(self.filter_window_id, 0)
			self.setFocusId(self.window_id)
		if action in self.selection_actions:
			chosen_listitem = self.get_listitem(self.filter_window_id)
			filter_type, filter_value = chosen_listitem.getProperty('filter_type'), chosen_listitem.getProperty('filter_value')
			if filter_type in ('quality', 'provider'):
				if filter_value == self.prerelease_key: filtered_list = [i for i in self.item_list if i.getProperty(filter_type) in self.prerelease_values]
				else: filtered_list = [i for i in self.item_list if i.getProperty(filter_type) == filter_value]
			elif filter_type == 'special':
				if filter_value == 'title':
					keywords = kodi_dialog().input('Enter Keyword (Comma Separated for Multiple)')
					if not keywords: return
					keywords.replace(' ', '')
					keywords = keywords.split(',')
					choice = [i.upper() for i in keywords]
					filtered_list = [i for i in self.item_list if all(x in i.getProperty('name') for x in choice)]
				elif filter_value == 'extraInfo':
					from modules.source_utils import matches_english_or_untagged
					filters = source_filters()
					list_items = [{'line1': item[0], 'icon': self.poster} for item in filters]
					kwargs = {'items': json.dumps(list_items), 'heading': 'Filter Results', 'multi_choice': 'true'}
					choice = select_dialog(filters, **kwargs)
					if choice == None: return
					choice = [i[1] for i in choice]
					def _extra_info_tags(listitem):
						extra = listitem.getProperty('extraInfo') or ''
						return [p.replace('[B]', '').replace('[/B]', '').strip() for p in extra.split(' | ') if p.strip()]
					def _matches_filters(listitem):
						extra = listitem.getProperty('extraInfo') or ''
						tags = _extra_info_tags(listitem)
						for filt in choice:
							if filt == 'ENG-OR-UNTAGGED':
								if not matches_english_or_untagged(tags): return False
							elif filt not in extra:
								return False
						return True
					filtered_list = [i for i in self.item_list if _matches_filters(i)]
				elif filter_value == 'showuncached': filtered_list = self.make_items(self.uncached_results)
				else: #cache_check_rescrape
					self.selected = ('cache_change_rescrape', 'false' if self._any_cache_check_active() else 'true')
					return self.close()
			if not filtered_list: return ok_dialog(text='No Results')
			self.set_filter(filtered_list)

	def _offer_full_scrape(self):
		if not self.prescrape: return False
		ref = self.sources_ref
		if not ref: return True
		if getattr(ref, 'check_prescrape_ran', False): return True
		if getattr(ref, 'active_external', False): return True
		return False

	def onAction(self, action):
		if self.get_visibility('Control.HasFocus(%s)' % self.filter_window_id): return self.filter_action(action)
		chosen_listitem = self.get_listitem(self.window_id)
		if action in self.closing_actions:
			if self.filter_applied: return self.clear_filter()
			self.selected = (None, '')
			return self.close()
		if action == self.info_action:
			self.open_window(('windows.sources', 'SourcesInfo'), 'sources_info.xml', item=chosen_listitem)
		elif action in self.selection_actions:
			if self._offer_full_scrape() and chosen_listitem.getProperty('perform_full_search') == 'true':
				self.selected = ('perform_full_search', '')
				return self.close()
			chosen_source = json.loads(chosen_listitem.getProperty('source'))
			if 'Uncached' in chosen_source.get('cache_provider', ''):
				from modules.debrid import manual_add_magnet_to_cloud
				return manual_add_magnet_to_cloud({
					'mode': 'manual_add_magnet_to_cloud',
					'provider': chosen_source['debrid'],
					'magnet_url': chosen_source['url'],
					'display_name': chosen_source.get('display_name', ''),
				})
			try:
				if self.sources_ref:
					self.sources_ref._prepare_resolve_ui()
			except:
				pass
			show_busy_dialog()
			self.selected = ('play', chosen_source)
			return self.close()
		elif action in self.context_actions:
			source = json.loads(chosen_listitem.getProperty('source'))
			choice = self.context_menu(source)
			if choice:
				if isinstance(choice, dict):
					if choice.get('mode') == 'debrid.browse_packs':
						if self.sources_ref:
							try:
								self.sources_ref._close_progress_before_modal()
							except:
								pass
							self.sources_ref._sources_results_window = self
							self.sources_ref.debridPacks(choice.get('provider'), choice.get('name'), choice.get('magnet_url'),
								choice.get('info_hash'), source_item=choice.get('source_item'))
							self.sources_ref._sources_results_window = None
							if self.sources_ref._playback_already_active():
								try:
									if self.get_visibility('Window.IsActive(sources_results.xml)'):
										self.selected = (None, '')
										return self.close()
								except:
									self.selected = (None, '')
									return self.close()
						return
					return self.execute_code('RunPlugin(%s)' % self.build_url(choice))
				if choice == 'results_info': return self.open_window(('windows.sources', 'SourcesInfo'), 'sources_info.xml', item=chosen_listitem)
				if choice == 'rd_cloud_delete':
					from apis.real_debrid_api import RealDebridAPI
					rd_api = RealDebridAPI()
					function = rd_api.delete_torrent if source['cache_type'] == 'torrent' else rd_api.delete_download
					result = function(source['folder_id'])
					if result.status_code in (401, 403, 404): return notification('Error', 1200)
					rd_api.clear_cache()
					self.delete_single_source(source)
				if choice == 'tb_cloud_delete':
					from apis.torbox_api import TorBox
					folder_id = source.get('folder_id')
					if folder_id is None:
						raw = source.get('id') or source.get('url_dl') or ''
						if isinstance(raw, str) and ',' in raw:
							folder_id = raw.split(',', 1)[0]
					if folder_id is None:
						return notification('Error', 1200)
					media_type = source.get('cloud_media_type') or 'torrent'
					if media_type == 'webdl':
						result = TorBox.delete_webdl(folder_id)
					elif media_type == 'usenet':
						result = TorBox.delete_usenet(folder_id)
					else:
						result = TorBox.delete_torrent(folder_id)
					if not result or not result.get('success'):
						return notification('Error', 1200)
					TorBox.clear_cache()
					self.delete_single_source(source)

	def delete_single_source(self, single_source):
		self.results.remove(single_source)
		self.make_items()
		self.total_results = str(len(self.item_list))
		self.reset_window(self.window_id)
		self.add_items(self.window_id, self.item_list)
		self.setFocusId(self.window_id)
		self.set_properties()

	def make_items(self, filtered_list=None):
		def builder(count, item):
			try:
				get = item.get
				listitem = self.make_listitem()
				set_properties = listitem.setProperties
				scrape_provider, source, quality, name = get('scrape_provider'), get('source'), get('quality', 'SD'), get('display_name')
				source_site_label = 'Indexer' if scrape_provider in NATIVE_INDEXER_SCRAPERS else 'Site'
				basic_quality, quality_icon = self.get_quality_and_path(quality.lower())
				pack = get('package', 'false') in ('true', 'show', 'season')
				extraInfo = get('extraInfo', '')
				extraInfo = extraInfo.rstrip('| ')
				if pack: extraInfo = '[B]%s PACK[/B] | %s' % (get('package'), extraInfo)
				if self.episode_group_label: extraInfo = '%s | %s' % (self.episode_group_label, extraInfo)
				if not extraInfo: extraInfo = 'N/A'
				if scrape_provider == 'external' or scrape_provider in NATIVE_TORRENT_SCRAPERS:
					source_site = get('provider').upper()
					provider = get('debrid', source_site).replace('.me', '').upper()
					provider_lower = provider.lower()
					provider_icon = self.get_provider_and_path(provider_lower)[1]
					cache_provider = item.get('cache_provider') or ''
					if cache_provider.startswith('Uncached '):
						if 'seeders' in item: set_properties({'source_type': 'UNCACHED (%d SEEDERS)' % get('seeders', 0)})
						else: set_properties({'source_type': 'UNCACHED'})
						item_highlight = 'FF7C7C7C'
					elif cache_provider.startswith('Unchecked '):
						cache_flag = 'UNCHECKED'
						if highlight_type == 0: key = provider_lower
						else: key = basic_quality
						item_highlight = self.info_highlights_dict[key]
						if pack: set_properties({'source_type': '%s [B]PACK[/B]' % cache_flag})
						else: set_properties({'source_type': '%s' % cache_flag})
					else:
						provider_check_names = {'REAL-DEBRID': 'Real-Debrid', 'ALLDEBRID': 'AllDebrid', 'TORBOX': 'TorBox', 'PREMIUMIZE': 'Premiumize.me', 'OFFCLOUD': 'Offcloud'}
						check_provider = provider_check_names.get(provider)
						if check_provider and self._provider_cache_verified(check_provider): cache_flag = '[B]CACHED[/B]'
						elif check_provider: cache_flag = 'UNCHECKED'
						else: cache_flag = '[B]CACHED[/B]'
						if highlight_type == 0: key = provider_lower
						else: key = basic_quality
						item_highlight = self.info_highlights_dict[key]
						if pack: set_properties({'source_type': '%s [B]PACK[/B]' % cache_flag})
						else: set_properties({'source_type': '%s' % cache_flag})
					set_properties({'provider': provider})
				else:
					if scrape_provider == 'aiostreams':
						aio_label = get('aio_source_label') or 'AIO'
						source_site = (get('aio_site_name') or get('aio_source_name') or aio_label.replace('AIO / ', '')).upper()
						provider = aio_label
						provider_icon = self.get_provider_and_path(get('aio_source_icon', 'aiostreams'))[1]
						hoster_label = get('aio_hoster') or 'DIRECT'
					elif scrape_provider == 'nzb':
						source_site = (get('nzb_indexer') or 'NZB').upper()
						provider = 'NZB'
						provider_icon = self.get_provider_and_path('nzb')[1]
						hoster_label = '[B]CACHED[/B]' if get('nzb_cached') else 'TORBOX'
					else:
						source_site = source.upper()
						provider, provider_icon = self.get_provider_and_path(source.lower())
						hoster_label = 'DIRECT'
					if highlight_type == 0: key = source.lower() if scrape_provider in ('aiostreams', 'nzb') else provider
					else: key = basic_quality
					item_highlight = self.info_highlights_dict[key]
					set_properties({'source_type': hoster_label, 'provider': provider.upper()})
				highlight_bg = _highlight_with_alpha(item_highlight, self.highlight_alpha) if self.tint_focused_background else 'FFCCCCCC'
				scraper_module = ''
				scraper_suffix = ''
				scraper_suffix_tint = ''
				scraper_module_label = ''
				if scrape_provider == 'external':
					scraper_module = external_module_display_name(get('external_module', ''))
					if scraper_module:
						scraper_module_label = 'Scraper'
						scraper_suffix = '     [COLOR %s][B]Scraper: [/B][/COLOR]%s' % (item_highlight, scraper_module.upper())
						scraper_suffix_tint = '     [COLOR FFA8A8A8][B]Scraper: [/B][/COLOR][COLOR FFFFFFFF]%s[/COLOR]' % scraper_module.upper()
				elif scrape_provider in NATIVE_TORRENT_SCRAPERS:
					scraper_module = 'Internal'
					scraper_module_label = 'Scraper'
					scraper_suffix = '     [COLOR %s][B]Scraper: [/B][/COLOR]%s' % (item_highlight, scraper_module.upper())
					scraper_suffix_tint = '     [COLOR FFA8A8A8][B]Scraper: [/B][/COLOR][COLOR FFFFFFFF]%s[/COLOR]' % scraper_module.upper()
				elif scrape_provider == 'aiostreams':
					scraper_module = get('aio_release_group') or ''
					if scraper_module:
						scraper_module_label = 'Group'
						scraper_suffix = '     [COLOR %s][B]Group: [/B][/COLOR]%s' % (item_highlight, scraper_module.upper())
						scraper_suffix_tint = '     [COLOR FFA8A8A8][B]Group: [/B][/COLOR][COLOR FFFFFFFF]%s[/COLOR]' % scraper_module.upper()
				elif scrape_provider == 'nzb':
					scraper_module = get('nzb_indexer') or ''
					if scraper_module:
						scraper_module_label = 'Site'
						scraper_suffix = '     [COLOR %s][B]Site: [/B][/COLOR]%s' % (item_highlight, scraper_module.upper())
						scraper_suffix_tint = '     [COLOR FFA8A8A8][B]Site: [/B][/COLOR][COLOR FFFFFFFF]%s[/COLOR]' % scraper_module.upper()
				set_properties({'name': name.upper(), 'source_site': source_site, 'source_site_label': source_site_label, 'provider_icon': provider_icon, 'quality_icon': quality_icon, 'count': '%02d.' % count,
						'size_label': get('size_label', 'N/A'), 'extraInfo': extraInfo, 'quality': quality.upper(), 'hash': get('hash', 'N/A'), 'source': json.dumps(item),
						'highlight': item_highlight, 'highlight_bg': highlight_bg, 'highlight_tint_focused_background': 'true' if self.tint_focused_background else 'false',
						'scraper_module': scraper_module.upper() if scraper_module else '', 'scraper_module_label': scraper_module_label,
						'scraper_suffix': scraper_suffix, 'scraper_suffix_tint': scraper_suffix_tint})
				item_list.append((listitem, count))
			except: pass
		try:
			item_list = []
			highlight_type = self.info_highlights_dict['highlight_type']
			if filtered_list:
				threads = TaskPool().tasks_enumerate(builder, filtered_list, min(len(filtered_list), max_threads()))
				[i.join() for i in threads]
				item_list.sort(key=lambda k: k[1])
				item_list = [i[0] for i in item_list]
				return item_list
			threads = TaskPool().tasks_enumerate(builder, self.results, min(len(self.results), max_threads()))
			[i.join() for i in threads]
			item_list.sort(key=lambda k: k[1])
			self.item_list = [i[0] for i in item_list]
			self.total_results = str(len(self.item_list))
			if self.prescrape and self._offer_full_scrape():
				prescrape_listitem = self.make_listitem()
				prescrape_listitem.setProperty('perform_full_search', 'true')
				self.item_list.append(prescrape_listitem)
		except:
			self.item_list = []
			self.total_results = '0'

	def make_filter_items(self):
		def builder(count, item):
			listitem = self.make_listitem()
			listitem.setProperties({'label': item[0], 'filter_type': item[1], 'filter_value': item[2]})
			self.filter_list.append((listitem, count))
		duplicates = set()
		qualities = [i.getProperty('quality') for i in self.item_list \
							if not (i.getProperty('quality') in duplicates or duplicates.add(i.getProperty('quality'))) \
							and not i.getProperty('quality') == '']
		if any(i in self.prerelease_values for i in qualities): qualities = [i for i in qualities if not i in self.prerelease_values] + [self.prerelease_key]
		qualities.sort(key=('4K', '1080P', '720P', 'SD', 'CAM/SCR/TELE').index)
		quality_totals = {i: len([x for x in self.item_list if x.getProperty('quality') == i]) for i in qualities}
		if 'CAM/SCR/TELE' in qualities: quality_totals['CAM/SCR/TELE'] = len([i for i in self.item_list if i.getProperty('quality') in self.prerelease_values])
		duplicates = set()
		providers = [i.getProperty('provider') for i in self.item_list \
							if not (i.getProperty('provider') in duplicates or duplicates.add(i.getProperty('provider'))) \
							and not i.getProperty('provider') == '']
		provider_totals = {i: len([x for x in self.item_list if x.getProperty('provider') == i]) for i in providers}
		sort_ranks = provider_sort_ranks()
		cache_functions_debrid = debrid_cache_check_available()
		sort_ranks['premiumize'] = sort_ranks.pop('premiumize.me')
		provider_choices = sorted(sort_ranks.keys(), key=sort_ranks.get)
		provider_choices = [i.upper() for i in provider_choices]
		_aio_inner_to_choice = {'TB': 'TORBOX', 'PM': 'PREMIUMIZE', 'RD': 'REAL-DEBRID', 'AD': 'ALLDEBRID', 'OC': 'OFFCLOUD', 'EN': 'EASYNEWS'}
		def _provider_filter_sort_key(label):
			key = label.upper().replace('.ME', '')
			try: return (0, provider_choices.index(key))
			except ValueError: pass
			if key.startswith('AIO /'):
				inner = key.replace('AIO /', '').strip().rstrip('+')
				mapped = _aio_inner_to_choice.get(inner)
				if mapped in provider_choices:
					return (0, provider_choices.index(mapped))
				return (1, key)
			return (2, key)
		providers.sort(key=_provider_filter_sort_key)
		qualities = [('Show [B]%s[/B] Only | [B]%d[/B] Results' % (i, quality_totals[i]), 'quality', i) for i in qualities]
		providers = [('Show [B]%s[/B] Only | [B]%d[/B] Results' % (i, provider_totals[i]), 'provider', i) for i in providers]
		data = []
		if cache_functions_debrid: data.append(('Rescrape with External Cache Check [B]%s[/B]' % ('OFF' if self._any_cache_check_active() else 'ON'), 'special', 'cache_check_rescrape'))
		if self.uncached_results: data.append(('Show [B]Uncached[/B] Only | [B]%d[/B] Results' % len(self.uncached_results), 'special', 'showuncached'))
		data.extend(qualities)
		data.extend(providers)
		data.extend([('Filter by [B]Title[/B]...', 'special', 'title'), ('Filter by [B]Info[/B]...', 'special', 'extraInfo')])
		self.filter_list = []
		threads = TaskPool().tasks_enumerate(builder, data, min(len(data), max_threads()))
		[i.join() for i in threads]
		self.filter_list.sort(key=lambda k: k[1])
		self.filter_list = [i[0] for i in self.filter_list]

	def set_properties(self):
		self.set_home_property('window_theme.sources', self.get_home_property('window_theme'))
		self.setProperty('highlight_tint_focused_background', 'true' if self.tint_focused_background else 'false')
		self.setProperty('window_format', self.window_format)
		self.setProperty('fanart', self.meta_get('fanart') or self.addon_fanart)
		self.setProperty('clearlogo', self.meta_get('clearlogo') or '')
		self.setProperty('title', self.meta_get('title'))
		self.setProperty('episode_label', self._episode_results_label())
		self.setProperty('total_results', self.total_results)
		self.setProperty('filters_ignored', '| Filters Ignored' if self.filters_ignored else '')

	def _episode_results_label(self):
		"""SxxExx - episode title beside results count (List format + setting only)."""
		if self.window_format != 'list':
			return ''
		if get_setting('redlight.results.show_episode_title', 'true') != 'true':
			return ''
		season, episode = self.meta_get('season'), self.meta_get('episode')
		try:
			season, episode = int(season), int(episode)
		except Exception:
			return ''
		if season < 0 or episode < 0:
			return ''
		label = 'S%02dE%02d' % (season, episode)
		ep_name = (self.meta_get('ep_name') or '').strip()
		if ep_name:
			label = '%s - %s' % (label, ep_name)
		group = (self.episode_group_label or '').replace('[B]', '').replace('[/B]', '').strip()
		if group:
			label = '%s | %s' % (label, group)
		return label

	def set_poster(self):
		if self.window_id == 2000: self.set_image(200, self.poster)

	def context_menu(self, item):
		# Pre-regression handoff: full source + meta in RunPlugin; downloader resolves.
		down_file_params, down_pack_params, browse_pack_params, add_magnet_to_cloud_params, uncached_download = None, None, None, None, None
		item_get = item.get
		item_id, name, magnet_url, info_hash = item_get('id', None), item_get('name'), item_get('url', 'None'), item_get('hash', 'None')
		provider_source, scrape_provider, cache_provider = item_get('source'), item_get('scrape_provider'), item_get('cache_provider', 'None')
		uncached = 'Uncached' in cache_provider
		source, meta_json = json.dumps(item), json.dumps(self.meta)
		choices = []
		choices_append = choices.append
		if not uncached and scrape_provider != 'folders':
			release_name = item_get('name') or item_get('display_name') or self.meta.get('rootname', '')
			down_file_params = {'mode': 'downloader.runner', 'action': 'meta.single', 'name': release_name, 'source': source,
								'url': None, 'provider': scrape_provider, 'meta': meta_json}
		if 'package' in item and not uncached:
			pack_provider = item_get('debrid') or cache_provider
			down_pack_params = {'mode': 'downloader.runner', 'action': 'meta.pack', 'name': self.meta.get('rootname', ''), 'source': source, 'url': None,
								'provider': pack_provider, 'meta': meta_json, 'magnet_url': magnet_url, 'info_hash': info_hash}
		if provider_source == 'torrent' and not uncached:
			browse_pack_params = {'mode': 'debrid.browse_packs', 'provider': item_get('debrid') or cache_provider, 'name': name,
								'magnet_url': magnet_url, 'info_hash': info_hash, 'source_item': item}
		if provider_source == 'torrent':
			add_magnet_to_cloud_params = {
				'mode': 'manual_add_magnet_to_cloud',
				'provider': cache_provider,
				'magnet_url': magnet_url,
				'display_name': item_get('display_name', ''),
			}
		choices_append(('Info', 'results_info'))
		if add_magnet_to_cloud_params: choices_append(('Add to Cloud', add_magnet_to_cloud_params))
		if browse_pack_params: choices_append(('Browse', browse_pack_params))
		if down_pack_params: choices_append(('Download Pack', down_pack_params))
		if down_file_params: choices_append(('Download File', down_file_params))
		if provider_source == 'rd_cloud': choices_append(('Delete from RD Cloud', 'rd_cloud_delete'))
		if provider_source == 'tb_cloud': choices_append(('Delete from TorBox Cloud', 'tb_cloud_delete'))
		list_items = [{'line1': i[0], 'icon': self.poster} for i in choices]
		kwargs = {'items': json.dumps(list_items)}
		choice = select_dialog([i[1] for i in choices], **kwargs)
		return choice

	def set_filter(self, filtered_list):
		self.filter_applied = True
		self.reset_window(self.window_id)
		self.add_items(self.window_id, filtered_list)
		self.setFocusId(self.window_id)
		self.setProperty('total_results', str(len(filtered_list)))
		self.setProperty('filter_applied', 'true')
		self.setProperty('filter_info', '| Press [B]BACK[/B] to Cancel')

	def clear_filter(self):
		self.filter_applied = False
		self.reset_window(self.window_id)
		self.add_items(self.window_id, self.item_list)
		self.setFocusId(self.window_id)
		self.select_item(self.filter_window_id, 0)
		self.setProperty('total_results', self.total_results)
		self.setProperty('filter_applied', 'false')
		self.setProperty('filter_info', '')

_RESUME_CHOICE_TIMEOUT_MS = 15000

class SourcesPlayback(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.meta = kwargs.get('meta')
		self.sources_ref = kwargs.get('sources_ref')
		self.is_canceled, self.skip_resolve, self.resume_choice = False, False, None
		self.meta_get = self.meta.get
		self.addon_fanart = addon_fanart()
		self.enable_scraper()

	def onInit(self):
		from modules.kodi_utils import hide_busy_dialog, set_property, sync_scrape_progress_ui
		hide_busy_dialog()
		sync_scrape_progress_ui(0, 0, 0, 0, 0, 0)
		set_property('redlight.scrape.ready', 'true')
		self.setProperty('redlight.scrape.ready', 'true')

	def run(self):
		self.doModal()
		from modules.kodi_utils import clear_scrape_progress_ui
		clear_scrape_progress_ui()
		self.clearProperties()
		self.clear_modals()

	def onClick(self, controlID):
		if self.window_mode == 'resume' and self.getProperty('resume_ready') != 'true':
			return
		self.resume_choice = {3010: 'resume', 3011: 'start_over', 3012: 'cancel'}.get(controlID)

	def onAction(self, action):
		if action in self.closing_actions:
			self.is_canceled = True
			defer_close = False
			try:
				if self.sources_ref:
					if self.window_mode == 'resume':
						self.resume_choice = 'cancel'
						self.sources_ref._on_resolve_dialog_cancel()
						defer_close = True
					elif self.window_mode == 'resolver':
						self.sources_ref._on_resolve_dialog_cancel()
						defer_close = True
					elif self.window_mode == 'scraper':
						self.sources_ref._on_scrape_dialog_cancel()
			except:
				pass
			if not defer_close:
				self.close()
		elif action == self.right_action and self.window_mode == 'resolver': self.skip_resolve = True

	def iscanceled(self):
		return self.is_canceled

	def skip_resolved(self):
		status = self.skip_resolve
		self.skip_resolve = False
		return status

	def reset_is_cancelled(self):
		self.is_canceled = False

	def enable_scraper(self):
		self.window_mode = 'scraper'
		self.set_scraper_properties()

	def enable_resolver(self):
		from modules.kodi_utils import set_property
		self.window_mode = 'resolver'
		set_property('redlight.scrape.percent', '0')
		self.setProperty('percent', '0')
		self.set_resolver_properties()

	def enable_resume(self, percent):
		self.is_canceled = False
		self.skip_resolve = False
		self.resume_choice = None
		self.busy_spinner('false')
		self.window_mode = 'resume'
		self.set_resume_properties(percent)
		Thread(target=self._resume_countdown, daemon=True).start()

	def busy_spinner(self, toggle='true'):
		self.setProperty('enable_busy_spinner', toggle)
		if toggle == 'false':
			from modules.kodi_utils import set_property
			set_property('redlight.scrape.percent', '0')
			self.setProperty('percent', '0')

	def set_scraper_properties(self):
		from modules.kodi_utils import sync_scrape_progress_ui
		sync_scrape_progress_ui(0, 0, 0, 0, 0, 0)
		title, genre = self.meta_get('title'), self.meta_get('genre', '')
		fanart, clearlogo = self.meta_get('fanart') or self.addon_fanart, self.meta_get('clearlogo') or ''
		self.setProperty('window_mode', self.window_mode)
		self.setProperty('fanart', fanart)
		self.setProperty('clearlogo', clearlogo)
		self.setProperty('title', title)
		self.setProperty('genre', ', '.join(genre))

	def set_resolver_properties(self):
		if not show_loading_plot():
			if self.meta_get('media_type') == 'movie':
				self.text = ''
			else:
				self.text = '[B]%02dx%02d - %s[/B]' % (
					self.meta_get('season'), self.meta_get('episode'), self.meta_get('ep_name', 'N/A').upper())
		elif self.meta_get('media_type') == 'movie':
			self.text = self.meta_get('plot')
		else:
			if avoid_episode_spoilers() and int(self.meta_get('playcount') or 0) == 0: plot = self.meta_get('tvshow_plot') or '* Hidden to Prevent Spoilers *'
			else: plot = self.meta_get('plot', '') or self.meta_get('tvshow_plot', '')
			self.text = '[B]%02dx%02d - %s[/B][CR][CR]%s' % (self.meta_get('season'), self.meta_get('episode'), self.meta_get('ep_name', 'N/A').upper(), plot)
		self.setProperty('window_mode', self.window_mode)
		self.setProperty('text', self.text)

	def set_resume_properties(self, percent):
		percent_str = str(percent)
		self.setProperty('resume_ready', 'false')
		self.setProperty('window_mode', self.window_mode)
		self.setProperty('resume_percent', percent_str)
		self.setProperty('resume_btn_label', 'Resume %s%%' % percent_str)
		self.setProperty('startover_btn_label', 'Start Over')
		self.setProperty('cancel_btn_label', 'Cancel')
		self.setProperty('resume_timeout_percent', '0')
		self.setProperty('text', '')
		for _ in range(4):
			hide_busy_dialog()
			self.sleep(80)
		self.setProperty('resume_ready', 'true')
		self.setFocusId(3010)

	def _resume_countdown(self):
		count = 0
		while self.resume_choice is None:
			timeout_percent = int((float(count) / _RESUME_CHOICE_TIMEOUT_MS) * 100)
			if timeout_percent >= 100:
				self.resume_choice = 'resume'
				break
			self.setProperty('resume_timeout_percent', str(timeout_percent))
			count += 100
			self.sleep(100)

	def update_scraper(self, results_sd, results_720p, results_1080p, results_4k, results_total, content='', percent=0):
		from modules.kodi_utils import sync_scrape_progress_ui
		pct = int(percent)
		sync_scrape_progress_ui(pct, results_sd, results_720p, results_1080p, results_4k, results_total)
		self.setProperty('results_4k', str(results_4k))
		self.setProperty('results_1080p', str(results_1080p))
		self.setProperty('results_720p', str(results_720p))
		self.setProperty('results_sd', str(results_sd))
		self.setProperty('results_total', str(results_total))
		self.setProperty('percent', str(pct))
		self.set_text(2001, content)

	def update_resolver(self, text='', percent=0):
		from modules.kodi_utils import set_property
		pct = int(percent)
		try:
			set_property('redlight.scrape.percent', str(pct))
			self.setProperty('percent', str(pct))
		except: pass
		if text: self.set_text(2002, text)

class SourcesInfo(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.item = kwargs['item']
		self.item_get_property = self.item.getProperty
		self.set_properties()

	def run(self):
		self.doModal()

	def onAction(self, action):
		self.close()

	def set_properties(self):
		self.setProperty('name', self.item_get_property('name'))
		self.setProperty('source_type', self.item_get_property('source_type'))
		self.setProperty('source_site', self.item_get_property('source_site'))
		self.setProperty('source_site_label', self.item_get_property('source_site_label') or 'Site')
		self.setProperty('scraper_module', self.item_get_property('scraper_module'))
		self.setProperty('scraper_module_label', self.item_get_property('scraper_module_label') or 'Scraper')
		self.setProperty('size_label', self.item_get_property('size_label'))
		self.setProperty('extraInfo', self.item_get_property('extraInfo'))
		self.setProperty('highlight', self.item_get_property('highlight'))
		self.setProperty('hash', self.item_get_property('hash'))
		self.setProperty('provider', self.item_get_property('provider').lower())
		self.setProperty('quality', self.item_get_property('quality').lower())
		self.setProperty('provider_icon', self.item_get_property('provider_icon'))
		self.setProperty('quality_icon', self.item_get_property('quality_icon'))
