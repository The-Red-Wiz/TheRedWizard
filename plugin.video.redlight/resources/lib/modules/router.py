# -*- coding: utf-8 -*-
import json
from xbmc import getInfoLabel
from urllib.parse import parse_qsl
from modules import kodi_utils
from modules.kodi_utils import external, get_property
# from modules.kodi_utils import logger

def sys_exit_check(mode='navigator.main'):
	from caches.settings_cache import get_setting, is_directory_listing_mode
	if get_setting('redlight.reuse_language_invoker', 'true') == 'false': return False
	# First open still has external() true before Container.PluginName updates; never discard a built list.
	if is_directory_listing_mode(mode): return False
	if mode == 'open_settings': return False
	if not external(): return False
	return True

def prepare_directory_listing(mode):
	from caches.settings_cache import is_directory_listing_mode
	if not is_directory_listing_mode(mode): return
	try:
		from caches.base_cache import ensure_listing_databases_ready
		ensure_listing_databases_ready()
	except Exception as e:
		kodi_utils.logger('routing', 'prepare listing: %s' % e)

def routing(sys):
	params = dict(parse_qsl(sys.argv[2][1:], keep_blank_values=True))
	mode = params.get('mode', 'navigator.main')
	try:
		from caches.settings_cache import sync_kodi_profile_context
		sync_kodi_profile_context()
	except Exception as e:
		kodi_utils.logger('routing', 'profile context: %s' % e)
	prepare_directory_listing(mode)
	from caches.settings_cache import ensure_settings_properties_loaded, should_block_bootstrap_on_entry
	if should_block_bootstrap_on_entry(mode):
		try: ensure_settings_properties_loaded()
		except Exception as e: kodi_utils.logger('routing', 'bootstrap: %s' % e)
	if 'navigator.' in mode:
		from indexers.navigator import Navigator
		return exec('Navigator(params).%s()' % mode.split('.')[1])
	elif 'menu_editor.' in mode:
		from modules.menu_editor import MenuEditor
		return exec('MenuEditor(params).%s()' % mode.split('.')[1])
	elif 'personal_lists.' in mode:
		from indexers import personal_lists
		return exec('personal_lists.%s(params)' % mode.split('.')[1])
	elif 'tmdblist.' in mode:
		from indexers import tmdb_lists
		return exec('tmdb_lists.%s(params)' % mode.split('.')[1])
	elif 'easynews.' in mode:
		from indexers import easynews
		return exec('easynews.%s(params)' % mode.split('.')[1])
	elif mode.startswith('nzb.'):
		from indexers import nzb
		return exec('nzb.%s(params)' % mode.split('.')[1])
	elif 'playback.' in mode:
		from modules.kodi_utils import player_check
		return player_check(mode, params)
	elif 'choice' in mode:
		from indexers import dialogs
		return exec('dialogs.%s(params)' % mode)
	elif 'custom_key.' in mode:
		from modules import custom_keys
		return exec('custom_keys.%s()' % mode.split('custom_key.')[1])
	elif 'simkl.' in mode:
		if '.list.' in mode:
			from indexers import simkl_lists
			return exec('simkl_lists.%s(params)' % mode.split('.')[2])
		from apis import simkl_api
		return exec('simkl_api.%s(params)' % mode.split('.')[1])
	elif 'mdblist.' in mode:
		from apis import mdblist_api
		return exec('mdblist_api.%s(params)' % mode.split('.')[1])
	elif 'punchplay.' in mode:
		if '.list.' in mode:
			from indexers import punchplay_lists
			return exec('punchplay_lists.%s(params)' % mode.split('.')[2])
		from apis import punchplay_api
		return exec('punchplay_api.%s(params)' % mode.split('.')[1])
	elif 'wetrakr.' in mode:
		from apis import wetrakr_api
		return exec('wetrakr_api.%s(params)' % mode.split('.')[1])
	elif 'trakt.' in mode:
		if '.list' in mode:
			from indexers import trakt_lists
			return exec('trakt_lists.%s(params)' % mode.split('.')[2])
		from apis import trakt_api
		return exec('trakt_api.%s(params)' % mode.split('.')[1])
	elif 'build' in mode:
		if mode == 'build_movie_list':
			from indexers.movies import Movies
			return Movies(params).fetch_list()
		elif mode == 'build_tvshow_list':
			from indexers.tvshows import TVShows
			return TVShows(params).fetch_list()
		elif mode == 'build_season_list':
			from indexers.seasons import build_season_list
			return build_season_list(params)
		elif mode == 'build_episode_list':
			from indexers.episodes import build_episode_list
			return build_episode_list(params)
		elif mode == 'build_in_progress_episode':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.progress', params)
		elif mode == 'build_recently_watched_episode':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.recently_watched', params)
		elif mode == 'build_next_episode':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.next', params)
		elif mode == 'build_my_calendar':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.trakt', params)
		elif mode == 'build_mdbl_calendar':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.mdblist', params)
		elif mode == 'build_punchplay_calendar':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.punchplay', params)
		elif mode == 'build_simkl_calendar':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.simkl', params)
		elif mode == 'build_simkl_public_calendar':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.simkl_public', params)
		elif mode == 'build_mdbl_next_up':
			from indexers.episodes import build_single_episode
			return build_single_episode('episode.mdblist_next', params)
		elif mode == 'build_next_episode_manager':
			from modules.episode_tools import build_next_episode_manager
			return build_next_episode_manager()
		elif mode == 'build_tmdb_people':
			from indexers.people import tmdb_people
			return tmdb_people(params)
		elif 'random.' in mode:
			from indexers.random_lists import RandomLists
			return RandomLists(params).run_random()
	elif 'watched_status.' in mode:
		if mode == 'watched_status.mark_episode':
			from modules.watched_status import mark_episode
			return mark_episode(params)
		elif mode == 'watched_status.mark_season':
			from modules.watched_status import mark_season
			return mark_season(params)
		elif mode == 'watched_status.mark_tvshow':
			from modules.watched_status import mark_tvshow
			return mark_tvshow(params)
		elif mode == 'watched_status.mark_movie':
			from modules.watched_status import mark_movie
			return mark_movie(params)
		elif mode == 'watched_status.erase_bookmark':
			from modules.watched_status import erase_bookmark
			return erase_bookmark(params.get('media_type'), params.get('tmdb_id'), params.get('season', ''), params.get('episode', ''), params.get('refresh', 'false'))
		elif mode == 'watched_status.unmark_previous_episode':
			from modules.watched_status import unmark_previous_episode
			return unmark_previous_episode(params)
	elif 'search.' in mode:
		if mode == 'search.get_key_id':
			from modules.search import get_key_id
			return get_key_id(params)
		elif mode == 'search.clear_search':
			from modules.search import clear_search
			return clear_search()
		elif mode == 'search.remove':
			from modules.search import remove_from_search
			return remove_from_search(params)
		elif mode == 'search.clear_all':
			from modules.search import clear_all
			return clear_all(params.get('setting_id'), params.get('refresh', 'false'))
		elif mode == 'search.clear_easynews_search_history':
			from modules.search import clear_easynews_search_history
			return clear_easynews_search_history(params.get('refresh', 'false'))
	elif 'real_debrid' in mode:
		if mode == 'real_debrid.rd_cloud':
			from indexers.real_debrid import rd_cloud
			return rd_cloud()
		elif mode == 'real_debrid.rd_downloads':
			from indexers.real_debrid import rd_downloads
			return rd_downloads()
		elif mode == 'real_debrid.browse_rd_cloud':
			from indexers.real_debrid import browse_rd_cloud
			return browse_rd_cloud(params.get('id'))
		elif mode == 'real_debrid.resolve_rd':
			from indexers.real_debrid import resolve_rd
			return resolve_rd(params)
		elif mode == 'real_debrid.rd_account_info':
			from indexers.real_debrid import rd_account_info
			return rd_account_info()
		elif mode == 'real_debrid.authenticate':
			from apis.real_debrid_api import RealDebridAPI
			return RealDebridAPI().auth()
		elif mode == 'real_debrid.revoke_authentication':
			from apis.real_debrid_api import RealDebridAPI
			return RealDebridAPI().revoke()
		elif mode == 'real_debrid.delete':
			from indexers.real_debrid import rd_delete
			return rd_delete(params.get('id'), params.get('cache_type'))
	elif 'premiumize' in mode:
		if mode == 'premiumize.pm_cloud':
			from indexers.premiumize import pm_cloud
			return pm_cloud(params.get('id', None), params.get('folder_name', None))
		elif mode == 'premiumize.pm_transfers':
			from indexers.premiumize import pm_transfers
			return pm_transfers()
		elif mode == 'premiumize.pm_account_info':
			from indexers.premiumize import pm_account_info
			return pm_account_info()
		elif mode == 'premiumize.authenticate':
			from apis.premiumize_api import PremiumizeAPI
			return PremiumizeAPI().auth()
		elif mode == 'premiumize.revoke_authentication':
			from apis.premiumize_api import PremiumizeAPI
			return PremiumizeAPI().revoke()
		elif mode == 'premiumize.rename':
			from indexers.premiumize import pm_rename
			return pm_rename(params.get('file_type'), params.get('id'), params.get('name'))
		elif mode == 'premiumize.delete':
			from indexers.premiumize import pm_delete
			return pm_delete(params.get('file_type'), params.get('id'))
	elif 'alldebrid' in mode:
		if mode == 'alldebrid.ad_cloud':
			from indexers.alldebrid import ad_cloud
			return ad_cloud()
		elif mode == 'alldebrid.ad_downloads':
			from indexers.alldebrid import ad_downloads
			return ad_downloads()
		elif mode == 'alldebrid.ad_saved_links':
			from indexers.alldebrid import ad_saved_links
			return ad_saved_links()
		elif mode == 'alldebrid.browse_ad_cloud':
			from indexers.alldebrid import browse_ad_cloud
			return browse_ad_cloud(params.get('id'))
		elif mode == 'alldebrid.resolve_ad':
			from indexers.alldebrid import resolve_ad
			return resolve_ad(params)
		elif mode == 'alldebrid.ad_account_info':
			from indexers.alldebrid import ad_account_info
			return ad_account_info()
		elif mode == 'alldebrid.authenticate':
			from apis.alldebrid_api import AllDebridAPI
			return AllDebridAPI().auth()
		elif mode == 'alldebrid.revoke_authentication':
			from apis.alldebrid_api import AllDebridAPI
			return AllDebridAPI().revoke()
		elif mode == 'alldebrid.delete':
			from indexers.alldebrid import ad_delete
			return ad_delete(params.get('id'))
	elif 'offcloud' in mode:
		if mode == 'offcloud.oc_cloud':
			from indexers.offcloud import oc_cloud
			return oc_cloud()
		elif mode == 'offcloud.oc_history':
			from indexers.offcloud import oc_history
			return oc_history()
		elif mode == 'offcloud.browse_oc_cloud':
			from indexers.offcloud import browse_oc_cloud
			return browse_oc_cloud(params.get('folder_id'))
		elif mode == 'offcloud.resolve_oc':
			from indexers.offcloud import resolve_oc
			return resolve_oc(params)
		elif mode == 'offcloud.oc_account_info':
			from indexers.offcloud import oc_account_info
			return oc_account_info()
		elif mode == 'offcloud.authenticate':
			from apis.offcloud_api import OffcloudAPI
			return OffcloudAPI().auth()
		elif mode == 'offcloud.revoke_authentication':
			from apis.offcloud_api import OffcloudAPI
			return OffcloudAPI().revoke()
		elif mode == 'offcloud.delete':
			from indexers.offcloud import oc_delete
			return oc_delete(params.get('folder_id'))
	elif 'torbox' in mode:
		if mode == 'torbox.tb_cloud':
			from indexers.torbox import tb_cloud
			return tb_cloud()
		elif mode == 'torbox.tb_history':
			from indexers.torbox import tb_history
			return tb_history()
		elif mode == 'torbox.browse_tb_cloud':
			from indexers.torbox import browse_tb_cloud
			return browse_tb_cloud(params.get('folder_id'), params.get('media_type'))
		elif mode == 'torbox.resolve_tb':
			from indexers.torbox import resolve_tb
			return resolve_tb(params)
		elif mode == 'torbox.tb_account_info':
			from indexers.torbox import tb_account_info
			return tb_account_info()
		elif mode == 'torbox.authenticate':
			from apis.torbox_api import TorBoxAPI
			return TorBoxAPI().auth()
		elif mode == 'torbox.revoke_authentication':
			from apis.torbox_api import TorBoxAPI
			return TorBoxAPI().revoke()
		elif mode == 'torbox.delete':
			from indexers.torbox import tb_delete
			return tb_delete(params.get('folder_id'), params.get('media_type'))
		elif mode == 'torbox.airlock':
			from indexers.torbox import tb_airlock
			return tb_airlock(params.get('folder_id'), params.get('media_type'))
		elif mode == 'torbox.send_webdl':
			from indexers.torbox import tb_send_webdl
			tb_send_webdl()
	elif 'tmdblist_api' in mode:
		if mode == 'tmdblist_api.authenticate':
			from apis.tmdblist_api import TMDbListAPI
			return TMDbListAPI().auth()
		elif mode == 'tmdblist_api.revoke_authentication':
			from apis.tmdblist_api import TMDbListAPI
			return TMDbListAPI().revoke()
	elif '_cache' in mode:
		from caches import base_cache
		if mode == 'clear_cache':
			return base_cache.clear_cache(params.get('cache'))
		elif mode == 'clear_all_cache':
			return base_cache.clear_all_cache()
		elif mode == 'clean_databases_cache':
			return base_cache.clean_databases()
		elif mode == 'check_databases_integrity_cache':
			return base_cache.check_databases_integrity()
	elif '_image' in mode:
		from indexers.images import Images
		return Images().run(params)
	elif '_text' in mode:
		if mode == 'show_text':
			from modules.kodi_utils import show_text
			return show_text(params.get('heading'), params.get('text', None), params.get('file', None),
							params.get('font_size', 'small'), params.get('kodi_log', 'false') == 'true')
		elif mode == 'show_text_media':
			from modules.kodi_utils import show_text_media
			return show_text(params.get('heading'), params.get('text', None), params.get('file', None), params.get('meta'), {})
	elif 'settings_manager.' in mode:
		from caches import settings_cache
		return exec('settings_cache.%s(params)' % mode.split('.')[1])
	elif 'downloader.' in mode:
		from modules import downloader
		return exec('downloader.%s(params)' % mode.split('.')[1])
	elif 'local_backup.' in mode:
		from modules import local_backup
		return getattr(local_backup, mode.split('.', 1)[1])(params)
	elif 'settings_backup.' in mode:
		from modules import settings_backup
		return getattr(settings_backup, mode.split('.', 1)[1])(params)
	elif 'kodi_favorites.' in mode:
		from modules import kodi_favorites_backup
		return getattr(kodi_favorites_backup, mode.split('.', 1)[1])(params)
	elif mode == 'set_view':
		from indexers.navigator import Navigator
		return Navigator(params).set_view()
	elif mode == 'sync_settings':
		from caches.settings_cache import sync_settings
		return sync_settings(params)
	elif mode == 'person_direct.search':
		from indexers.people import person_direct_search
		return person_direct_search(params.get('key_id') or params.get('query'))
	elif mode == 'kodi_refresh':
		from modules.kodi_utils import kodi_refresh
		return kodi_refresh()
	elif mode == 'refresh_widgets':
		from modules.kodi_utils import refresh_widgets
		return refresh_widgets(
			params.get('silent', 'false') == 'true',
			params.get('reload_skin', 'false') == 'true',
			params.get('defer_browsing', 'false') == 'true')
	elif mode == 'person_data_dialog':
		from indexers.people import person_data_dialog
		return person_data_dialog(params)
	elif mode == 'favorite_people':
		from indexers.people import favorite_people
		return favorite_people()
	elif mode == 'manual_add_magnet_to_cloud':
		from modules.debrid import manual_add_magnet_to_cloud
		return manual_add_magnet_to_cloud(params)
	elif mode == 'upload_logfile':
		from modules.kodi_utils import upload_logfile
		return upload_logfile(params)
	elif mode == 'downloader':
		from modules.downloader import runner
		return runner(params)
	elif mode == 'debrid.browse_packs':
		from modules.sources import Sources
		source_item = params.get('source_item')
		if isinstance(source_item, str):
			try:
				source_item = json.loads(source_item)
			except:
				source_item = None
		return Sources().debridPacks(params.get('provider'), params.get('name'), params.get('magnet_url'), params.get('info_hash'), source_item=source_item)
	elif mode == 'open_settings':
		from modules.kodi_utils import open_settings
		return open_settings(params.get('section'))
	elif mode == 'opensubs_test_login':
		from apis.opensubs_api import check_account
		return check_account()
	elif mode == 'opensubs_check_account':
		from apis.opensubs_api import check_account
		return check_account()
	elif mode == 'opensubs_revoke':
		from apis.opensubs_api import revoke_access
		return revoke_access()
	elif mode == 'hide_unhide_progress_items':
		from modules.watched_status import hide_unhide_progress_items
		return hide_unhide_progress_items(params)
	elif mode in ('external_scraper_clear_slot', 'external_scraper_move_slot'):
		from indexers import dialogs
		return exec('dialogs.%s(params)' % mode)
	elif mode == 'open_external_scraper_settings':
		from modules.kodi_utils import external_scraper_settings
		return external_scraper_settings(params)
