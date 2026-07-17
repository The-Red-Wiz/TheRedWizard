# -*- coding: utf-8 -*-
from caches.settings_cache import get_setting, set_setting, default_setting_values, _EXTRAS_LIST_DEFAULT
from modules.kodi_utils import translate_path, get_property, addon_profile, make_directory
from modules.kodi_utils import logger

def tmdb_api_key():
	return get_setting('redlight.tmdb_api', '')

def tmdb_lists_read_token():
	return get_setting('redlight.tmdb.lists_read_token', '')

def trakt_client():
	return get_setting('redlight.trakt.client', '')

def mdblist_client():
	return get_setting('redlight.mdblist.client', '')

def trakt_secret():
	return get_setting('redlight.trakt.secret', '')

def trakt_user_active():
	from caches.settings_cache import settings_cache
	val = settings_cache.read_db_value('trakt.user')
	return val not in (None, 'empty_setting', '')

def simkl_user_active():
	from caches.settings_cache import settings_cache
	user = settings_cache.read_db_value('simkl.user')
	token = settings_cache.read_db_value('simkl.token')
	return user not in (None, 'empty_setting', '') and token not in (None, '0', '', 'empty_setting')

def mdblist_user_active():
	from caches.settings_cache import settings_cache
	user = settings_cache.read_db_value('mdblist.user')
	token = settings_cache.read_db_value('mdblist.token')
	return user not in (None, 'empty_setting', '') and token not in (None, '0', '', 'empty_setting')

def mdblist_sync_interval():
	setting = get_setting('redlight.mdblist.sync_interval', '60')
	try: interval = max(5, int(setting))
	except: interval = 60
	return interval, interval * 60

def simkl_sync_interval():
	setting = get_setting('redlight.simkl.sync_interval', '60')
	try: interval = max(5, int(setting))
	except: interval = 60
	return interval, interval * 60

def tmdblist_user_active():
	return get_setting('redlight.tmdb.account_id', 'empty_setting') not in (None, 'empty_setting', '')

def results_format():
	results_window_numbers_dict = {'List': 2000, 'Rows': 2001, 'WideList': 2002}
	window_format = str(get_setting('redlight.results.list_format', 'List'))
	if not window_format in results_window_numbers_dict:
		window_format = 'List'
		set_setting('results.list_format', window_format)
	window_number = results_window_numbers_dict[window_format]
	return window_format.lower(), window_number

def store_resolved_to_cloud(debrid_service, pack):
	setting_value = int(get_setting('redlight.store_resolved_to_cloud.%s' % debrid_service.lower(), '0'))
	return setting_value in (1, 2) if pack else setting_value == 1

def enabled_debrids_check(debrid_service):
	if not get_setting('redlight.%s.enabled' % debrid_service) == 'true': return False
	return authorized_debrid_check(debrid_service)

def authorized_debrid_check(debrid_service):
	if get_setting('redlight.%s.token' % debrid_service) in (None, '', 'empty_setting'): return False
	return True

def playback_key():
	return 'media'

def playback_settings():
	return (int(get_setting('redlight.playback.watched_percent', '90')), int(get_setting('redlight.playback.resume_percent', '5')))

def limit_resolve():
	return get_setting('redlight.playback.limit_resolve', 'false') == 'true'

def movies_directory():
	return translate_path(get_setting('redlight.movies_directory'))
	
def tv_show_directory():
	return translate_path(get_setting('redlight.tv_shows_directory'))

def download_directory(media_type):
	download_directories_dict = {'movie': 'redlight.movie_download_directory', 'episode': 'redlight.tvshow_download_directory', 'thumb_url': 'redlight.image_download_directory',
								'image_url': 'redlight.image_download_directory','image': 'redlight.image_download_directory', 'premium': 'redlight.premium_download_directory',
								None: 'redlight.premium_download_directory', 'None': False}
	return translate_path(get_setting(download_directories_dict[media_type]))

_IMPORT_EXPORT_DIR_DEFAULT = 'special://profile/addon_data/plugin.video.redlight/Import Export/'

def import_export_directory_setting():
	# Virtual path for Kodi browse dialogs (works on all platforms).
	path = get_setting('redlight.import_export_directory', '')
	if path in ('', 'None', None, 'empty_setting'):
		return _IMPORT_EXPORT_DIR_DEFAULT
	return path

def import_export_directory():
	# Filesystem path for os.path / file I/O.
	return translate_path(import_export_directory_setting())

def ensure_import_export_directory():
	path = import_export_directory()
	make_directory(path)
	return path

def ai_model_active():
	if get_setting('redlight.google_api', 'empty_setting') not in (None, 'None', '', 'empty_setting'): return True
	if get_setting('redlight.groq_api', 'empty_setting') not in (None, 'None', '', 'empty_setting'): return True
	return False

def ai_model_order():
	return get_setting('redlight.ai_model.order', 'gemini-2.5-flash-lite,llama-3.3-70b-versatile,gemma-3-27b-it,llama-3.1-8b-instant').split(',')

def ai_model_limit():
	return max(1, int(get_setting('redlight.ai_model.limit', '10')))

def show_unaired_watchlist():
	return get_setting('redlight.show_unaired_watchlist', 'true') == 'true'

def lists_cache_duraton():
	return int(get_setting('redlight.lists_cache_duraton', '48'))

def auto_start_redlight():
	return get_setting('redlight.auto_start_redlight', 'false') == 'true'

def source_folders_directory(media_type, source):
	setting = 'redlight.%s.movies_directory' % source if media_type == 'movie' else 'redlight.%s.tv_shows_directory' % source
	if get_setting(setting) not in ('', 'None', None): return translate_path( get_setting(setting))
	else: return False

def avoid_episode_spoilers():
	return get_setting('redlight.avoid_episode_spoilers', 'false') == 'true'

def paginate(is_home):
	paginate_lists = int(get_setting('redlight.paginate.lists', '0'))
	if is_home: return paginate_lists in (2, 3)
	else: return paginate_lists in (1, 3)

def page_limit(is_home):	
	return int(get_setting({True: 'redlight.paginate.limit_widgets', False: 'redlight.paginate.limit_addon'}[is_home], '20'))

def quality_filter(setting):
	return get_setting('redlight.%s' % setting).split(', ')

def sort_to_top_filter(autoplay):
	return {0: False, 1: False if autoplay else True, 2: True if autoplay else False, 3: True}[int(get_setting('redlight.filter.sort_to_top', '0'))]

def audio_filters():
	setting = get_setting('redlight.filter_audio')
	if setting in ('empty_setting', ''): return []
	return setting.split(', ')

def preferred_filters():
	setting = get_setting('redlight.filter.preferred_filters')
	if setting in ('empty_setting', ''): return []
	return setting.split(', ')

def include_prerelease_results():
	return int(get_setting('redlight.filter.include_prerelease', '0')) == 0

def auto_enable_subs():
	return get_setting('redlight.playback.auto_enable_subs', 'false') == 'true'

def subtitles_source():
	return get_setting('redlight.playback.subs_source', '0')

def subtitles_source_options():
	options = {'0': 'Local Subtitles'}
	if submaker_manifest_configured(): options['1'] = 'SubMaker'
	if opensubs_configured(): options['2'] = 'OpenSubtitles'
	return options

def refresh_playback_subs_source():
	from caches.settings_cache import get_setting, set_setting
	opts = subtitles_source_options()
	current = str(get_setting('redlight.playback.subs_source', '0'))
	if current not in opts:
		if current == '2':
			current = '1' if '1' in opts else '0'
		elif current == '1':
			current = '2' if '2' in opts else '0'
		else:
			current = '0'
		set_setting('playback.subs_source', current)

def submaker_enabled():
	return subtitles_source() == '1'

def opensubs_enabled():
	return subtitles_source() == '2'

def submaker_manifest():
	manifest = get_setting('redlight.playback.submaker_manifest', 'empty_setting')
	if manifest == 'empty_setting': return ''
	return manifest.strip()

def submaker_manifest_configured():
	manifest = submaker_manifest()
	return bool(manifest) and 'manifest' in manifest

def opensubs_api_key():
	try:
		from apis.opensubs_api import effective_api_key
		return effective_api_key()
	except: return ''

def opensubs_username():
	value = get_setting('redlight.playback.opensubs_username', 'empty_setting')
	return '' if value in (None, '', '0', 'empty_setting') else str(value).strip()

def opensubs_password():
	value = get_setting('redlight.playback.opensubs_password', 'empty_setting')
	return '' if value in (None, '', '0', 'empty_setting') else str(value).strip()

def opensubs_configured():
	return bool(opensubs_username()) and bool(opensubs_password())

def subs_alert_fetch_configured():
	return submaker_manifest_configured() or opensubs_configured()

def alert_timing_options(next_episode=False):
	options = {'0': 'Playback Percentage', '1': 'Chapter Info', '2': 'Subtitles Info'}
	if next_episode:
		options['3'] = 'IntroDB Info'
	if not subs_alert_fetch_configured():
		options.pop('2', None)
	return options

def refresh_alert_timing_settings():
	from caches.settings_cache import get_setting, set_setting, settings_cache
	settings_cache.clear_db_cache()
	changed = False
	for setting_id in ('stinger_alert.alert_timing', 'autoplay_alert_timing', 'autoscrape_alert_timing'):
		opts = alert_timing_options(next_episode=(setting_id != 'stinger_alert.alert_timing'))
		current = str(get_setting('redlight.%s' % setting_id, '1'))
		if current not in opts:
			fallback = '1' if '1' in opts else '0'
			set_setting(setting_id, fallback)
			current = fallback
			changed = True
		try:
			settings_cache.set_memory_cache('%s_name' % setting_id, opts.get(current, ''))
		except: pass
	return changed

def submaker_language():
	return get_setting('redlight.playback.submaker_language_name', 'English')

def subs_language():
	return submaker_language()

FORCED_LOCAL_SUBS_LANGUAGE_INDEX = '42'

def subs_language_is_forced_local():
	return str(get_setting('redlight.playback.submaker_language', '0')) == FORCED_LOCAL_SUBS_LANGUAGE_INDEX

def subs_language_for_download():
	if subs_language_is_forced_local(): return 'English'
	return subs_language()

_KODI_SUBTITLE_LANG_SKIP = frozenset(('original', 'original only', 'mediadefault', 'default', 'forced only', 'forced'))

def kodi_subtitle_language():
	try:
		import xbmc
		value = xbmc.getSetting('locale.subtitlelanguage')
	except: return ''
	if not value: return ''
	value = str(value).strip()
	if value.lower() in _KODI_SUBTITLE_LANG_SKIP: return ''
	try:
		name = xbmc.convertLanguage(value, xbmc.ENGLISH_NAME)
		if name and name.lower() not in ('unknown', ''): return name
	except: pass
	return value

def subs_language_preferences():
	if subs_language_is_forced_local(): return []
	prefs = []
	red_light = subs_language()
	if red_light: prefs.append(red_light)
	kodi_lang = kodi_subtitle_language()
	if kodi_lang and (not red_light or kodi_lang.lower() != red_light.lower()):
		prefs.append(kodi_lang)
	return prefs

def submaker_prefer_local():
	return get_setting('redlight.playback.submaker_prefer_local', 'true') == 'true'

def subs_show_notifications():
	return get_setting('redlight.playback.subs_show_notifications', 'true') == 'true'

def stingers_show():
	return get_setting('redlight.stinger_alert.show', 'false') == 'true'

def _alert_timing_mode(setting_id, default='1'):
	value = get_setting('redlight.%s' % setting_id, default)
	return {'0': 'off', '1': 'chapters', '2': 'subtitles', '3': 'introdb'}.get(str(value), 'chapters')

def stingers_alert_timing():
	return _alert_timing_mode('stinger_alert.alert_timing', '1')

def stingers_use_chapters():
	return stingers_alert_timing() == 'chapters'

def stingers_percentage():
	return int(get_setting('redlight.stinger_alert.window_percentage', '90'))

def include_anime_tvshow():
	return get_setting('redlight.include_anime_tvshow', 'false') == 'true'

def auto_play(media_type):
	return get_setting('redlight.auto_play_%s' % media_type, 'false') == 'true'

def autoplay_next_episode():
	if auto_play('episode') and get_setting('redlight.autoplay_next_episode', 'false') == 'true': return True
	else: return False

def skip_intro_mode():
	return int(get_setting('redlight.autoplay_skip_intro', '0'))

def skip_intro_all_episodes():
	return get_setting('redlight.skip_intro_all_episodes', 'true') == 'true'

def _skip_intro_chain_play_type(play_type):
	return play_type in ('autoplay_nextep', 'autoscrape_nextep', 'random_continual')

def skip_intro_enabled(play_type):
	if skip_intro_mode() == 0:
		return False
	if _skip_intro_chain_play_type(play_type):
		return True
	return skip_intro_all_episodes()

def skip_intro_auto_approved(play_type):
	return skip_intro_mode() == 2 and _skip_intro_chain_play_type(play_type)

def skip_intro_needs_prompt(play_type):
	mode = skip_intro_mode()
	if mode == 1:
		return True
	if mode == 2 and not _skip_intro_chain_play_type(play_type):
		return True
	return False

def autoplay_skip_intro_mode():
	return skip_intro_mode()

def autoplay_skip_intro_enabled(play_type):
	return skip_intro_enabled(play_type)

def autoplay_skip_intro_auto(play_type):
	return skip_intro_auto_approved(play_type)

def autoscrape_next_episode():
	if not auto_play('episode') and get_setting('redlight.autoscrape_next_episode', 'false') == 'true': return True
	else: return False

def any_alert_uses_subtitle_timing(media_type='episode'):
	if media_type == 'episode':
		if autoplay_next_episode() and _alert_timing_mode('autoplay_alert_timing') == 'subtitles': return True
		if autoscrape_next_episode() and _alert_timing_mode('autoscrape_alert_timing') == 'subtitles': return True
	elif media_type == 'movie' and stingers_show() and stingers_alert_timing() == 'subtitles':
		return True
	return False

def subs_alert_fetch_enabled(media_type='episode'):
	return any_alert_uses_subtitle_timing(media_type) and subs_alert_fetch_configured()

def autoscrape_confirm():
	return get_setting('redlight.autoscrape_confirm', 'false') == 'true'

def autoplay_prescrape(scrape_provider):
	return get_setting('redlight.autoplay.%s' % scrape_provider, 'false') == 'true'

NEXTEP_SCRAPE_MARGIN_SEC = 30
NEXTEP_COMMAND_HEADROOM_SEC = 15
NEXTEP_AUTOSCRAPE_MIN_HEADROOM_SEC = 90
NEXTEP_ALERT_MAX_REMAINING_SEC = 20
NEXTEP_ALERT_MIN_REMAINING_SEC = 20
NEXTEP_CREDITS_ENTRY_GAP_SEC = 15
NEXTEP_INTRODB_BUFFER_SEC = 5
NEXTEP_STOP_NOTIFY_REMAINING_SEC = 90

def nextep_pipeline_headroom(play_type, scraper_time, still_watching_due=False):
	# Scrape budget (results.timeout + NEXTEP_SCRAPE_MARGIN_SEC) plus time for still-watching / autoscrape confirm dialogs.
	headroom = int(scraper_time)
	if 'autoplay' in play_type and still_watching_due:
		headroom += NEXTEP_COMMAND_HEADROOM_SEC
	if 'autoscrape' in play_type and autoscrape_confirm():
		headroom += NEXTEP_COMMAND_HEADROOM_SEC
	if 'autoscrape' in play_type:
		headroom = max(headroom, NEXTEP_AUTOSCRAPE_MIN_HEADROOM_SEC)
	return headroom

def random_continual_still_watching_enabled():
	if not autoplay_next_episode(): return False
	if int(get_setting('redlight.autoplay_watching_check', '3')) == 0: return False
	return get_setting('redlight.autoplay_random_continual_watching_check', 'true') == 'true'

def auto_nextep_settings(play_type):
	play_type = 'autoplay' if play_type == 'autoplay_nextep' else 'autoscrape'
	window_percentage = 100 - int(get_setting('redlight.%s_next_window_percentage' % play_type, '95'))
	alert_timing = _alert_timing_mode('%s_alert_timing' % play_type, '1')
	watching_check = int(get_setting('redlight.autoplay_watching_check', '3'))
	scraper_time = int(get_setting('redlight.results.timeout', '60')) + NEXTEP_SCRAPE_MARGIN_SEC
	if play_type == 'autoplay':
		alert_method = int(get_setting('redlight.autoplay_alert_method', '0'))
		default_action = {'0': 'play', '1': 'cancel', '2': 'pause'}[get_setting('redlight.autoplay_default_action', '1')]
	else: alert_method, default_action = '', ''
	return {'scraper_time': scraper_time, 'window_percentage': window_percentage, 'alert_method': alert_method,
			'default_action': default_action, 'alert_timing': alert_timing, 'watching_check': watching_check}

def filter_status(filter_type):
	return int(get_setting('redlight.filter.%s' % filter_type, '0'))

def limit_number_quality():
	return int(get_setting('redlight.results.limit_number_quality', '0'))

def limit_number_total():
	return int(get_setting('redlight.results.limit_number_total', '0'))

def trakt_sync_interval():
	setting = get_setting('redlight.trakt.sync_interval', '60')
	interval = int(setting) * 60
	return setting, interval

def lists_sort_order(setting):
	return int(get_setting('redlight.sort.%s' % setting, '0'))

def sort_trakt_sync_list(data, setting_key):
	"""Sort Trakt collection/watchlist rows. 0=title, 1/3=date added desc/asc, 2/4=release desc/asc."""
	sort_order = lists_sort_order(setting_key)
	if sort_order == 0:
		from modules.utils import sort_for_article
		return sort_for_article(data, 'title', ignore_articles())
	if sort_order in (1, 3):
		data.sort(key=lambda k: k.get('collected_at') or '', reverse=(sort_order == 1))
	elif sort_order in (2, 4):
		data.sort(key=lambda k: k.get('released') or '', reverse=(sort_order == 2))
	return data

def sort_simkl_personal_list(data):
	"""Sort Simkl Plan to Watch / Watching / etc. Same order codes as sort_trakt_sync_list."""
	try: sort_order = lists_sort_order('simkl')
	except: sort_order = 0
	if sort_order == 0:
		from modules.utils import sort_for_article
		return sort_for_article(data, 'title', ignore_articles())
	if sort_order in (1, 3):
		data.sort(key=lambda k: k.get('collected_at') or '', reverse=(sort_order == 1))
	elif sort_order in (2, 4):
		data.sort(key=lambda k: k.get('released') or '', reverse=(sort_order == 2))
	return data

def tmdblists_sort_order(setting):
	if setting == 'recommendations': return None
	return str(get_setting('redlight.tmdbsort.%s' % setting, '4'))

def personal_lists_sort_unseen_to_top():
	return get_setting('redlight.personal_list.sort_unseen_to_top') == 'true'

def personal_lists_unseen_highlight():
	if get_setting('redlight.personal_list.highlight_unseen', 'false') == 'false': return None
	return get_setting('redlight.personal_list.unseen_highlight', 'FF4DDBFF')

def personal_lists_show_author():
	return get_setting('redlight.personal_list.show_author', 'true') == 'true'

def show_specials():
	return get_setting('redlight.show_specials', 'false') == 'true'

def single_ep_unwatched_episodes():
	return get_setting('redlight.single_ep_unwatched_episodes', 'false') == 'true'

def single_ep_display_format(is_external):
	if is_external: setting, default = 'redlight.single_ep_display_widget', '1'
	else: setting, default = 'redlight.single_ep_display', ''
	return int(get_setting(setting, default))

def calendar_display_format(is_external):
	if is_external:
		setting, default = 'redlight.trakt.calendar_display_widget', '1'
	else:
		setting, default = 'redlight.trakt.calendar_display', '0'
	return int(get_setting(setting, default))

def easynews_active():
	if get_setting('redlight.provider.easynews', 'false') == 'true': easynews_status = easynews_authorized()
	else: easynews_status = False
	return easynews_status

def easynews_playback_method(query):
	method = int(get_setting('redlight.easynews.playback_method', '0'))
	queries = {'retry': lambda: method in (1, 3), 'non_seek': lambda: method in (2, 3),
				'direct_play': lambda: method in (2, 3) and get_setting('redlight.easynews.playback_method_limited', 'false') != 'true'}
	setting = queries[query]()
	return setting

def easynews_playback_method_retries():
	return int(get_setting('redlight.easynews.playback_method_retries', '1')) + 1

def easynews_authorized():
	easynews_user = get_setting('redlight.easynews_user', 'empty_setting')
	easynews_password = get_setting('redlight.easynews_password', 'empty_setting')
	if easynews_user in ('empty_setting', '') or easynews_password in ('empty_setting', ''): easynews_status = False
	else: easynews_status = True
	return easynews_status

def nzb_indexer_active():
	"""True when NZB Indexers are enabled and at least one slot is configured."""
	if get_setting('redlight.provider.nzb', 'false') != 'true': return False
	for slot in (1, 2, 3):
		if get_setting('redlight.nzb%d.enabled' % slot, 'false') != 'true': continue
		url = get_setting('redlight.nzb%d.url' % slot, '')
		key = get_setting('redlight.nzb%d.key' % slot, '')
		if url not in ('', 'empty_setting') and key not in ('', 'empty_setting'): return True
	return False

def nzb_scrape_active():
	"""NZB title scrape — indexers plus TorBox Pro usenet for resolve."""
	return nzb_indexer_active() and authorized_debrid_check('tb')

def nzb_search_width():
	return int(get_setting('redlight.nzb.search_width', '0'))

def nzb_fallback_search():
	return get_setting('redlight.nzb.fallback_search', 'true') == 'true'

def aiostreams_authorized():
	username = get_setting('redlight.aiostreams.username', 'empty_setting')
	password = get_setting('redlight.aiostreams.password', 'empty_setting')
	if username in ('empty_setting', '') or password in ('empty_setting', ''): return False
	return True

def aiostreams_active():
	from apis.aiostreams_api import ENABLED
	if not ENABLED: return False
	if get_setting('redlight.provider.aiostreams', 'false') == 'true': return aiostreams_authorized()
	return False

def aiostreams_preserve_order():
	return get_setting('redlight.aiostreams.preserve_order', 'true') == 'true'

def extras_enable_extra_ratings():
	return get_setting('redlight.extras.enable_extra_ratings', 'true') == 'true'

def extras_enabled_ratings():
	return get_setting('redlight.extras.enabled_ratings', 'Meta, Tom/Critic, Tom/User, IMDb, TMDb').split(', ')

def extras_enable_item_ratings():
	return get_setting('redlight.extras.enable_item_ratings', 'false') =='true'

def extras_enable_scrollbars():
	return get_setting('redlight.extras.enable_scrollbars', 'false')

def extras_enabled():
	setting = get_setting('redlight.extras.enabled', '2000,2050,2051,2052,2053,2054,2055,2056,2057,2058,2059,2060,2061,2062')
	if setting in ('', None, 'noop', []): return []
	split_setting = setting.split(',')
	return [int(i) for i in split_setting]

def extras_order():
	setting = get_setting('redlight.extras.order', _EXTRAS_LIST_DEFAULT)
	if setting in ('', None, 'noop', []): return []
	split_setting = setting.split(',')
	return [int(i) for i in split_setting if i.strip()]

def recommend_service():
	return int(get_setting('redlight.recommend_service', '0'))

def recommend_seed():
	return int(get_setting('redlight.recommend_seed', '5'))

def tv_progress_location():
	return int(get_setting('redlight.tv_progress_location', '0'))

def check_prescrape_sources(scraper, media_type):
	"""Prescrape only when Check Before Full Search is enabled for that provider."""
	if scraper in ('easynews', 'aiostreams', 'nzb', 'rd_cloud', 'pm_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud'):
		return get_setting('redlight.check.%s' % scraper) == 'true'
	if scraper == 'folders':
		return get_setting('redlight.check.folders') == 'true'
	if get_setting('redlight.check.%s' % scraper) == 'true' and auto_play(media_type):
		return True
	return False

def prescrape_enabled(media_type, active_scrapers=None):
	if active_scrapers is None:
		active_scrapers = active_internal_scrapers()
	return any(check_prescrape_sources(scraper, media_type) for scraper in active_scrapers)

def cloud_scrape_before_external(scraper):
	"""Run debrid cloud scrapers before external torrent scrapers when the provider is enabled."""
	cloud_scrapers = {
		'rd_cloud': 'provider.rd_cloud',
		'pm_cloud': 'provider.pm_cloud',
		'ad_cloud': 'provider.ad_cloud',
		'oc_cloud': 'provider.oc_cloud',
		'tb_cloud': 'provider.tb_cloud',
	}
	if scraper in cloud_scrapers:
		return get_setting('redlight.%s' % cloud_scrapers[scraper]) == 'true'
	return False

EXTERNAL_SCRAPER_SLOT_COUNT = 3

def _external_slot_setting(slot, field):
	return 'external_scraper.slot%d.%s' % (int(slot), field)

def external_scraper_slot_data(slot):
	module = get_setting('redlight.%s' % _external_slot_setting(slot, 'module'), 'empty_setting')
	name = get_setting('redlight.%s' % _external_slot_setting(slot, 'name'), 'empty_setting')
	enabled = get_setting('redlight.%s' % _external_slot_setting(slot, 'enabled'), 'false') == 'true'
	if module in ('empty_setting', ''):
		return {'slot': int(slot), 'module': '', 'name': '', 'enabled': False, 'folder_name': ''}
	return {'slot': int(slot), 'module': module, 'name': name, 'enabled': enabled, 'folder_name': module.split('.')[-1]}

def external_scraper_cache_key(module_id, provider):
	return '%s::%s' % (module_id, provider)

def active_external_modules():
	modules = []
	for slot in range(1, EXTERNAL_SCRAPER_SLOT_COUNT + 1):
		data = external_scraper_slot_data(slot)
		if not data['module'] or not data['enabled']: continue
		display = data['name'] if data['name'] not in ('empty_setting', '') else data['folder_name']
		modules.append({'slot': slot, 'module_id': data['module'], 'folder_name': data['folder_name'], 'display_name': display})
	return modules

def external_module_display_name(module_id):
	if not module_id or module_id in ('empty_setting', ''): return ''
	for slot in range(1, EXTERNAL_SCRAPER_SLOT_COUNT + 1):
		data = external_scraper_slot_data(slot)
		if data['module'] == module_id:
			if data['name'] not in ('empty_setting', '', None): return data['name']
			return data['folder_name']
	module_id = str(module_id)
	if '.' in module_id: return module_id.split('.')[-1]
	return module_id

def any_external_scraper_configured():
	for slot in range(1, EXTERNAL_SCRAPER_SLOT_COUNT + 1):
		if external_scraper_slot_data(slot)['module']: return True
	module = get_setting('redlight.external_scraper.module', 'empty_setting')
	return module not in ('empty_setting', '')

def _sync_legacy_external_scraper_from_slot(slot=1):
	data = external_scraper_slot_data(slot)
	if data['module']:
		set_setting('external_scraper.module', data['module'])
		set_setting('external_scraper.name', data['name'] or data['folder_name'])
	else:
		set_setting('external_scraper.module', 'empty_setting')
		set_setting('external_scraper.name', 'empty_setting')

def external_scraper_module_in_use(module_id, exclude_slot=None):
	if not module_id or module_id in ('empty_setting', ''): return 0
	for slot in range(1, EXTERNAL_SCRAPER_SLOT_COUNT + 1):
		if exclude_slot and int(slot) == int(exclude_slot): continue
		if external_scraper_slot_data(slot)['module'] == module_id: return slot
	return 0

def set_external_scraper_slot(slot, module_id, module_name, enable=True):
	slot = int(slot)
	if module_id and module_id not in ('empty_setting', ''):
		if external_scraper_module_in_use(module_id, exclude_slot=slot): return False
	set_setting(_external_slot_setting(slot, 'module'), module_id or 'empty_setting')
	set_setting(_external_slot_setting(slot, 'name'), module_name or 'empty_setting')
	set_setting(_external_slot_setting(slot, 'enabled'), 'true' if enable and module_id else 'false')
	if slot == 1: _sync_legacy_external_scraper_from_slot(1)
	return True

def swap_external_scraper_slots(slot_a, slot_b):
	slot_a, slot_b = int(slot_a), int(slot_b)
	if slot_a == slot_b: return
	fields = ('module', 'name', 'enabled')
	values = {}
	for slot in (slot_a, slot_b):
		values[slot] = {field: get_setting('redlight.%s' % _external_slot_setting(slot, field)) for field in fields}
	for field in fields:
		set_setting(_external_slot_setting(slot_a, field), values[slot_b][field] or ('false' if field == 'enabled' else 'empty_setting'))
		set_setting(_external_slot_setting(slot_b, field), values[slot_a][field] or ('false' if field == 'enabled' else 'empty_setting'))
	_sync_legacy_external_scraper_from_slot(1)

def migrate_external_scraper_slots_for_upgrade(had_existing_settings):
	if not had_existing_settings: return False
	migrated = False
	slot1 = external_scraper_slot_data(1)
	if not slot1['module']:
		legacy_module = get_setting('redlight.external_scraper.module', 'empty_setting')
		legacy_name = get_setting('redlight.external_scraper.name', 'empty_setting')
		if legacy_module not in ('empty_setting', ''):
			set_external_scraper_slot(1, legacy_module, legacy_name, enable=get_setting('redlight.provider.external', 'false') == 'true')
			migrated = True
	if get_setting('redlight.migration.external_scraper_slots_v160', 'false') != 'true':
		set_setting('migration.external_scraper_slots_v160', 'true')
	return migrated

def external_scraper_info():
	modules = active_external_modules()
	if modules:
		entry = modules[0]
		return entry['module_id'], entry['folder_name']
	module = get_setting('redlight.external_scraper.module')
	if module in ('empty_setting', ''): return None, ''
	return module, module.split('.')[-1]

def external_scraper_enabled_module_count():
	count = 0
	for slot in range(1, EXTERNAL_SCRAPER_SLOT_COUNT + 1):
		data = external_scraper_slot_data(slot)
		if data['module'] and data['enabled']:
			count += 1
	return count

def configured_external_scraper_slots():
	slots = []
	for slot in range(1, EXTERNAL_SCRAPER_SLOT_COUNT + 1):
		data = external_scraper_slot_data(slot)
		if not data['module']: continue
		display = data['name'] if data['name'] not in ('empty_setting', '', None) else data['folder_name']
		slots.append({'slot': slot, 'module_id': data['module'], 'display_name': display, 'enabled': data['enabled']})
	return slots

def external_scraper_settings_tools_label():
	if len(configured_external_scraper_slots()) != 1:
		return 'External Scrapers Settings'
	return 'External Scraper Settings'

def external_scraper_settings_options_label():
	if len(configured_external_scraper_slots()) != 1:
		return 'Open External Scrapers Settings'
	return 'Open External Scraper Settings'

def append_external_scraper_settings_cm(cm_append, build_url_fn):
	if not configured_external_scraper_slots(): return
	cm_append(['external_scraper_settings', ('[B]%s[/B]' % external_scraper_settings_tools_label(),
		'RunPlugin(%s)' % build_url_fn({'mode': 'open_external_scraper_settings'}))])

def external_scraper_run_mode():
	return str(get_setting('redlight.external_scraper.run_mode', '1'))

def external_scraper_run_mode_series():
	return external_scraper_run_mode() == '1'

def external_scraper_run_mode_parallel():
	return external_scraper_run_mode() == '0'

def external_scraper_run_mode_orchestrated():
	return external_scraper_run_mode() in ('1', '2', '3')

def refresh_external_scraper_properties():
	from modules.kodi_utils import set_property
	count = external_scraper_enabled_module_count()
	set_property('redlight.external_scraper.enabled_count', str(count))
	set_property('redlight.external_scraper.multi_search', 'true' if count >= 2 else 'false')

def migrate_external_scraper_run_mode_for_upgrade(had_existing_settings):
	if not had_existing_settings:
		return False
	if get_setting('redlight.external_scraper.run_mode', 'empty_setting') not in ('empty_setting', ''):
		return False
	legacy = get_setting('redlight.external_scraper.max_modules_parallel', '3')
	set_setting('external_scraper.run_mode', '1' if legacy == '1' else '0')
	return True

def filter_by_name(scraper):
	if get_property('fs_filterless_search') == 'true': return False
	return get_setting('redlight.%s.title_filter' % scraper, 'false') == 'true'

def uncached_min_seeders():
	return int(get_setting('redlight.results.uncached_min_seeders', '0'))

_DEBRID_CACHE_CHECK_SETTINGS = {
	'Real-Debrid': 'rd.cache_check',
	'TorBox': 'tb.cache_check',
	'Premiumize.me': 'pm.cache_check',
	'Offcloud': 'oc.cache_check',
}

def debrid_cache_check(provider):
	if provider == 'AllDebrid':
		return False
	setting_id = _DEBRID_CACHE_CHECK_SETTINGS.get(provider)
	if not setting_id: return False
	return get_setting('redlight.%s' % setting_id, 'false') == 'true'

def any_external_cache_check():
	for slug, provider in (('rd', 'Real-Debrid'), ('tb', 'TorBox'), ('pm', 'Premiumize.me'), ('oc', 'Offcloud')):
		if enabled_debrids_check(slug) and debrid_cache_check(provider):
			return True
	return False

def include_uncached_torbox():
	return get_setting('redlight.tb.include_uncached', 'false') == 'true' and debrid_cache_check('TorBox')

def include_uncached_offcloud():
	return get_setting('redlight.oc.include_uncached', 'false') == 'true' and debrid_cache_check('Offcloud')

def include_uncached_premiumize():
	return get_setting('redlight.pm.include_uncached', 'false') == 'true' and debrid_cache_check('Premiumize.me')

def tb_notify_cloud_ready():
	return get_setting('redlight.tb.notify_cloud_ready', 'true') == 'true'

def oc_notify_cloud_ready():
	return get_setting('redlight.oc.notify_cloud_ready', 'true') == 'true'

def easynews_language_filter():
	enabled = get_setting('redlight.easynews.filter_lang') == 'true'
	if enabled: filters = get_setting('redlight.easynews.lang_filters').split(', ')
	else: filters = []
	return enabled, filters

def easynews_exclude_adult():
	return get_setting('redlight.easynews.exclude_adult', 'false') == 'true'

def easynews_refresh_credentials():
	return get_setting('redlight.easynews.refresh_credentials', 'true') == 'true'

def easynews_lang_include_unknown():
	return get_setting('redlight.easynews.lang_include_unknown', 'true') == 'true'

def easynews_fallback_search():
	return get_setting('redlight.easynews.fallback_search', 'true') == 'true'

def easynews_search_width():
	return int(get_setting('redlight.easynews.search_width', '0'))

def size_sort_weighted():
	return get_setting('redlight.results.size_sort_weighted', 'false') == 'true'

def results_sort_order():
	sort_direction = -1 if get_setting('redlight.results.size_sort_direction') == '0' else 1
	return (
			lambda k: (k['quality_rank'], k['provider_rank'], sort_direction*k['size_rank']), #Quality, Provider, Size
			lambda k: (k['quality_rank'], sort_direction*k['size_rank'], k['provider_rank']), #Quality, Size, Provider
			lambda k: (k['provider_rank'], k['quality_rank'], sort_direction*k['size_rank']), #Provider, Quality, Size
			lambda k: (k['provider_rank'], sort_direction*k['size_rank'], k['quality_rank']), #Provider, Size, Quality
			lambda k: (sort_direction*k['size_rank'], k['quality_rank'], k['provider_rank']), #Size, Quality, Provider
			lambda k: (sort_direction*k['size_rank'], k['provider_rank'], k['quality_rank'])  #Size, Provider, Quality
			)[int(get_setting('redlight.results.sort_order', '1'))]

def active_internal_scrapers():
	settings = ['provider.external', 'provider.easynews', 'provider.folders']
	settings_append = settings.append
	for item in [('rd', 'provider.rd_cloud'), ('pm', 'provider.pm_cloud'), ('ad', 'provider.ad_cloud'), ('oc', 'provider.oc_cloud'), ('tb', 'provider.tb_cloud')]:
		if enabled_debrids_check(item[0]): settings_append(item[1])
	active = [i.split('.')[1] for i in settings if get_setting('redlight.%s' % i) == 'true']
	if aiostreams_active(): active.append('aiostreams')
	if nzb_scrape_active(): active.append('nzb')
	return active

def provider_sort_ranks():
	fo_priority = int(get_setting('redlight.folders.priority', '6'))
	aio_priority = int(get_setting('redlight.aio.priority', '7'))
	en_priority = int(get_setting('redlight.en.priority', '7'))
	nzb_priority = int(get_setting('redlight.nzb.priority', '7'))
	rd_priority = int(get_setting('redlight.rd.priority', '8'))
	ad_priority = int(get_setting('redlight.ad.priority', '9'))
	pm_priority = int(get_setting('redlight.pm.priority', '10'))
	oc_priority = int(get_setting('redlight.oc.priority', '10'))
	tb_priority = int(get_setting('redlight.tb.priority', '10'))
	return {'easynews': en_priority, 'aiostreams': aio_priority, 'nzb': nzb_priority, 'real-debrid': rd_priority, 'premiumize.me': pm_priority, 'alldebrid': ad_priority,
	'offcloud': oc_priority, 'torbox': tb_priority, 'rd_cloud': rd_priority, 'pm_cloud': pm_priority, 'ad_cloud': ad_priority, 'oc_cloud': oc_priority,
	'tb_cloud': tb_priority, 'folders': fo_priority}

def sort_to_top(provider):
	sort_to_top_dict = {'folders': 'redlight.results.sort_folders_first', 'rd_cloud': 'redlight.results.sort_rdcloud_first', 'pm_cloud': 'redlight.results.sort_pmcloud_first',
						'ad_cloud': 'redlight.results.sort_adcloud_first', 'oc_cloud': 'redlight.results.sort_occloud_first', 'tb_cloud': 'redlight.results.sort_tbcloud_first'}
	return get_setting(sort_to_top_dict[provider]) == 'true'

def auto_resume(media_type, autoplay_status):
	return {0: False, 1: True, 2: autoplay_status}[int(get_setting('redlight.auto_resume_%s' % media_type))]

def scraping_settings():
	highlight_type = int(get_setting('redlight.highlight.type', '0'))
	if highlight_type == 2:
		highlight = get_setting('redlight.scraper_single_highlight', 'FF008EB2')
		return {'highlight_type': 1, '4k': highlight, '1080p': highlight, '720p': highlight, 'sd': highlight}
	easynews_highlight, aiostreams_highlight, nzb_highlight, debrid_cloud_highlight, folders_highlight = '', '', '', '', ''
	rd_highlight, pm_highlight, ad_highlight, oc_highlight, tb_highlight = '', '', '', '', ''
	highlight_4K, highlight_1080P, highlight_720P, highlight_SD = '', '', '', ''
	if highlight_type == 0:
		easynews_highlight = get_setting('redlight.provider.easynews_highlight', 'FF00B3B2')
		aiostreams_highlight = get_setting('redlight.provider.aiostreams_highlight', 'FF00D4FF')
		nzb_highlight = get_setting('redlight.provider.nzb_highlight', 'FFD4A017')
		debrid_cloud_highlight = get_setting('redlight.provider.debrid_cloud_highlight', 'FF7A01CC')
		folders_highlight = get_setting('redlight.provider.folders_highlight', 'FFB36B00')
		rd_highlight = get_setting('redlight.provider.rd_highlight', 'FF3C9900')
		pm_highlight = get_setting('redlight.provider.pm_highlight', 'FFFF3300')
		ad_highlight = get_setting('redlight.provider.ad_highlight', 'FFE6B800')
		oc_highlight = get_setting('redlight.provider.oc_highlight', 'FF5C6BC0')
		tb_highlight = get_setting('redlight.provider.tb_highlight', 'FF01662A')
	else:
		highlight_4K = get_setting('redlight.scraper_4k_highlight', 'FFFF00FE')
		highlight_1080P = get_setting('redlight.scraper_1080p_highlight', 'FFE6B800')
		highlight_720P = get_setting('redlight.scraper_720p_highlight', 'FF3C9900')
		highlight_SD = get_setting('redlight.scraper_SD_highlight', 'FF0166FF')
	return {'highlight_type': highlight_type, 'real-debrid': rd_highlight, 'premiumize': pm_highlight, 'alldebrid': ad_highlight,
			'offcloud': oc_highlight, 'torbox': tb_highlight, 'rd_cloud': debrid_cloud_highlight, 'pm_cloud': debrid_cloud_highlight, 'ad_cloud': debrid_cloud_highlight,
			'oc_cloud': debrid_cloud_highlight, 'tb_cloud': debrid_cloud_highlight, 'easynews': easynews_highlight, 'aiostreams': aiostreams_highlight, 'nzb': nzb_highlight, 'folders': folders_highlight,
			'4k': highlight_4K, '1080p': highlight_1080P, '720p': highlight_720P, 'sd': highlight_SD}

def external_cache_check():
	return any_external_cache_check()

def omdb_api_key():
	return get_setting('redlight.omdb_api', 'empty_setting')

def default_all_episodes():
	return int(get_setting('redlight.default_all_episodes', '0'))

def max_threads():
	if not get_setting('redlight.limit_concurrent_threads', 'false') == 'true': return 60
	return int(get_setting('redlight.max_threads', '60'))

def get_meta_filter():
	return get_setting('redlight.meta_filter', 'true')

def mpaa_region():
	return get_setting('redlight.mpaa_region', 'US')

def widget_hide_next_page():
	return get_setting('redlight.widget_hide_next_page', 'false') == 'true'

def widget_hide_watched():
	return get_setting('redlight.widget_hide_watched', 'false') == 'true'

def calendar_sort_order():
	return int(get_setting('redlight.trakt.calendar_sort_order', '0'))

def ignore_articles():
	return get_setting('redlight.ignore_articles', 'false') == 'true'

def jump_to_enabled():
	return get_setting('redlight.paginate.jump_to', 'true') == 'true'

def date_offset():
	return int(get_setting('redlight.datetime.offset', '0')) + 5

def media_open_action(media_type):
	return int(get_setting('redlight.media_open_action_%s' % media_type, '0'))

def _resolve_watched_provider():
	ind = int(get_setting('redlight.watched_indicators', '0'))
	if ind == 1 and not trakt_user_active(): return 0
	if ind == 2 and not simkl_user_active(): return 0
	if ind == 3 and not mdblist_user_active(): return 0
	return ind

def watched_provider_options():
	options = {}
	if mdblist_user_active(): options['3'] = 'MDBList'
	options['0'] = 'Red Light'
	if simkl_user_active(): options['2'] = 'Simkl'
	if trakt_user_active(): options['1'] = 'Trakt'
	return options

def offer_watched_provider(provider_index, name):
	from modules.kodi_utils import confirm_dialog
	if confirm_dialog(heading='Watched Status Provider', text='Do you want to set %s as your Watched Status Provider?' % name,
						ok_label='Yes', cancel_label='No', default_control=10):
		set_setting('watched_indicators', str(provider_index))
		return True
	return False

def offer_trakt_import_to_simkl():
	if not trakt_user_active() or not simkl_user_active(): return False
	from modules.kodi_utils import confirm_dialog
	if not confirm_dialog(heading='Import Trakt to Simkl',
		text='Import your Trakt watch history into Simkl?',
		ok_label='Yes', cancel_label='No', default_control=10): return False
	from apis.simkl_api import simkl_import_trakt
	simkl_import_trakt()
	return True

def fallback_watched_provider_on_revoke(revoked_index):
	current = int(get_setting('redlight.watched_indicators', '0'))
	if current != revoked_index: return
	if revoked_index == 1:
		set_setting('watched_indicators', '2' if simkl_user_active() else ('3' if mdblist_user_active() else '0'))
	elif revoked_index == 2:
		set_setting('watched_indicators', '1' if trakt_user_active() else ('3' if mdblist_user_active() else '0'))
	elif revoked_index == 3:
		set_setting('watched_indicators', '2' if simkl_user_active() else ('1' if trakt_user_active() else '0'))

def watched_indicators():
	return _resolve_watched_provider()

def provider_sync_refresh_widgets(provider_index):
	"""Refresh home widgets after a provider sync only when that provider owns watched/progress indicators."""
	if watched_indicators() != provider_index:
		return False
	keys = {1: 'trakt.refresh_widgets', 2: 'simkl.refresh_widgets', 3: 'mdblist.refresh_widgets'}
	key = keys.get(provider_index)
	if not key:
		return False
	return get_setting('redlight.%s' % key, 'false') == 'true'

def most_watched_provider():
	return 'simkl' if watched_indicators() == 2 else 'trakt'

def flatten_episodes():
	return get_setting('redlight.trakt.flatten_episodes', 'false') == 'true'

def nextep_method():
	return int(get_setting('redlight.nextep.method', '0'))

def nextep_limit_history():
	return get_setting('redlight.nextep.limit_history', 'false') == 'true'

def nextep_limit():
	return int(get_setting('redlight.nextep.limit', '20'))

def nextep_include_unwatched():
	return int(get_setting('redlight.nextep.include_unwatched', '0'))

def nextep_include_airdate():
	return get_setting('redlight.nextep.include_airdate', 'false') == 'true'

def nextep_airing_today():
	return get_setting('redlight.nextep.airing_today', 'false') == 'true'

def nextep_include_unaired():
	return get_setting('redlight.nextep.include_unaired', 'false') == 'true'

def nextep_sort_key():
	return {0: 'last_played', 1: 'first_aired', 2: 'name'}[int(get_setting('redlight.nextep.sort_type', '0'))]

def nextep_sort_direction():
	return int(get_setting('redlight.nextep.sort_order', '0')) == 0

def _rescrape_defaults():
	return [('cache_ignored', '1', '0'), ('imdb_year', '0', '1'), ('with_all', '0', '2'), ('episode_group', '0', '3'), ('ignore_filters', '0', '4'), ('full_scrape', '2', '5')]

def rescrape_all_settings():
	return sorted([(i[0], int(get_setting('redlight.rescrape.%s' % i[0], i[1])), int(get_setting('redlight.rescrape.%s.order' % i[0], i[2]))) \
					for i in _rescrape_defaults()], key=lambda x: x[2])

def rescrape_settings():
	return [i for i in rescrape_all_settings() if i[1] in (1, 2)]

def rescrape_action_value(action, default='0'):
	return int(get_setting('redlight.rescrape.%s' % action, default))

def cm_enabled():
	default = 'extras,options,playback_options,external_scraper_settings,browse_movie_set,browse_seasons,browse_episodes,recommended,related,more_like_this,similar,in_trakt_list,' \
				'mdblist_manager,simkl_manager,trakt_manager,tmdb_manager,personal_manager,favorites_manager,mark_watched,unmark_previous_episode,exit,refresh,reload'
	setting = get_setting('redlight.context_menu.enabled', default)
	if setting in ('', None, 'noop', '[]'): return default.split(',')
	return setting.split(',')

def _merge_cm_order_with_enabled(order, enabled):
	order = [i for i in order if i]
	manager_insert = {
		'mdblist_manager': ('simkl_manager', 'trakt_manager'),
		'simkl_manager': ('trakt_manager',),
	}
	for item in enabled:
		if item in order: continue
		inserted = False
		for anchor in manager_insert.get(item, ()):
			if anchor in order:
				order.insert(order.index(anchor), item)
				inserted = True
				break
		if not inserted: order.append(item)
	return order

def _normalize_cm_list_order(order):
	order = list(order)
	managers = ('mdblist_manager', 'simkl_manager', 'trakt_manager')
	present = [m for m in managers if m in order]
	if present:
		insert_at = min(order.index(m) for m in present)
		order = [i for i in order if i not in managers]
		for offset, manager in enumerate([m for m in managers if m in present]):
			order.insert(insert_at + offset, manager)
	if 'tmdb_manager' in order and 'personal_manager' in order:
		ti, pi = order.index('tmdb_manager'), order.index('personal_manager')
		if pi < ti: order[ti], order[pi] = order[pi], order[ti]
	return order

def migrate_external_scraper_context_menu_for_upgrade(had_existing_settings):
	if get_setting('redlight.external_scraper.cm_menu_migrated', 'false') == 'true': return False
	set_setting('external_scraper.cm_menu_migrated', 'true')
	if not had_existing_settings: return False
	item, changed = 'external_scraper_settings', False
	for setting_key in ('context_menu.enabled', 'context_menu.order'):
		raw = get_setting('redlight.%s' % setting_key, '')
		if raw in ('', None, 'noop', '[]'): continue
		parts = [p for p in raw.split(',') if p]
		if item in parts: continue
		if 'playback_options' in parts: parts.insert(parts.index('playback_options') + 1, item)
		else: parts.append(item)
		set_setting(setting_key, ','.join(parts))
		changed = True
	return changed

def migrate_simkl_context_menu_for_upgrade(had_existing_settings):
	if get_setting('redlight.simkl.cm_menu_migrated', 'false') == 'true': return False
	set_setting('simkl.cm_menu_migrated', 'true')
	if not had_existing_settings: return False
	item, changed = 'simkl_manager', False
	raw = get_setting('redlight.context_menu.enabled', '')
	if raw and raw not in ('noop', '[]'):
		parts = [p for p in raw.split(',') if p]
		if item not in parts:
			set_setting('context_menu.enabled', ','.join(parts + [item]))
			changed = True
	raw = get_setting('redlight.context_menu.order', '')
	if raw and raw not in ('noop', '[]'):
		parts = _merge_cm_order_with_enabled([p for p in raw.split(',') if p], cm_enabled())
		if item not in raw.split(','):
			set_setting('context_menu.order', ','.join(parts))
			changed = True
	return changed

def migrate_mdblist_context_menu_for_upgrade(had_existing_settings):
	if get_setting('redlight.mdblist.cm_menu_migrated', 'false') == 'true': return False
	set_setting('mdblist.cm_menu_migrated', 'true')
	if not had_existing_settings: return False
	item, changed = 'mdblist_manager', False
	raw = get_setting('redlight.context_menu.enabled', '')
	if raw and raw not in ('noop', '[]'):
		parts = [p for p in raw.split(',') if p]
		if item not in parts:
			set_setting('context_menu.enabled', ','.join([item] + parts))
			changed = True
	raw = get_setting('redlight.context_menu.order', '')
	if raw and raw not in ('noop', '[]'):
		parts = _merge_cm_order_with_enabled([p for p in raw.split(',') if p], cm_enabled())
		if item not in raw.split(','):
			set_setting('context_menu.order', ','.join(parts))
			changed = True
	return changed

def migrate_cm_manager_order_for_upgrade():
	if get_setting('redlight.cm_manager_order_migrated_v2', 'false') == 'true': return False
	set_setting('cm_manager_order_migrated_v2', 'true')
	set_setting('cm_manager_order_migrated', 'true')
	before = get_setting('redlight.context_menu.order', '')
	cm_current_order()
	return get_setting('redlight.context_menu.order', '') != before

def cm_current_order():
	default = 'extras,options,playback_options,external_scraper_settings,browse_movie_set,browse_seasons,browse_episodes,recommended,related,more_like_this,similar,in_trakt_list,' \
				'mdblist_manager,simkl_manager,trakt_manager,tmdb_manager,personal_manager,favorites_manager,mark_watched,unmark_previous_episode,exit,refresh,reload'
	setting = get_setting('redlight.context_menu.order', default)
	if setting in ('', None, 'noop', '[]'): order = default.split(',')
	else: order = setting.split(',')
	enabled = cm_enabled()
	merged = _normalize_cm_list_order(_merge_cm_order_with_enabled(order, enabled))
	if merged != order: set_setting('context_menu.order', ','.join(merged))
	return merged

def cm_sort_order():
	try: setting = {i: c for c, i in enumerate([i for i in cm_current_order() if i in cm_enabled()])}
	except: setting = cm_default_order()
	return setting

def cm_default_order():
	return {i: c for c, i in enumerate(default_setting_values('context_menu.order')['setting_default'].split(','))}

def rpdb_info(media_type):
	if media_type == 'extras': active = extras_enable_item_ratings()
	else: active = int(get_setting('redlight.rpdb_enabled', '0')) in {'movie': (1, 3), 'tvshow': (2, 3)}[media_type]
	if active: return {'rpdb_api_key': get_setting('redlight.rpdb_api'), 'rpdb_format': get_setting('redlight.rpdb_format')}
	else: return {'rpdb_api_key': None, 'rpdb_format': None}

def use_season_name():
	return get_setting('redlight.use_season_name', 'false') == 'true'


