# -*- coding: utf-8 -*-
# TRUMP - UNFIT FOR OFFICE
import xbmc, xbmcgui, xbmcplugin, xbmcvfs, xbmcaddon
import os
from urllib.parse import urlencode, unquote

def addon_themes():
	return [{'name': 'Light', 'value': ('FF434343', 'FF2E2E2E'), 'icon': 'light'}, {'name': 'Medium', 'value': ('FF373737', 'FF4a4347'), 'icon': 'medium'},
			{'name': 'Dark', 'value': ('FF1F2020', 'FF4F4F4F'), 'icon': 'dark'}]

def addon_themes_opacity():
	return [{'name': '100%', 'value': 'FF'}, {'name': '95%', 'value': 'F2'}, {'name': '90%', 'value': 'E6'}, {'name': '85%', 'value': 'D9'}, {'name': '80%', 'value': 'CC'},
			{'name': '75%', 'value': 'BF'}, {'name': '70%', 'value': 'B3'}, {'name': '65%', 'value': 'A6'}, {'name': '60%', 'value': '99'}, {'name': '55%', 'value': '8C'},
			{'name': '50%', 'value': '80'}]

def random_valid_type_check():
	return {'build_movie_list': 'movie', 'build_tvshow_list': 'tvshow', 'build_season_list': 'season', 'build_episode_list': 'episode',
	'build_in_progress_episode': 'single_episode', 'build_recently_watched_episode': 'single_episode', 'build_next_episode': 'single_episode',
	'build_my_calendar': 'single_episode', 'build_mdbl_calendar': 'single_episode', 'build_punchplay_calendar': 'single_episode',
	'build_simkl_calendar': 'single_episode', 'build_simkl_public_calendar': 'single_episode',
	'build_mdbl_next_up': 'single_episode', 'build_trakt_lists': 'trakt_list',
	'trakt.list.build_trakt_list': 'trakt_list', 'build_trakt_lists_contents': 'trakt_list', 'personal_lists.build_personal_list': 'personal_list',
	'build_personal_lists_contents': 'personal_list', 'tmdblist.build_tmdb_list': 'tmdb_list', 'build_tmdb_lists_contents': 'tmdb_list',
	'mdblist.build_mdbl_list': 'mdblist_list', 'build_mdblist_lists_contents': 'mdblist_list'}

def random_episodes_check():
	return {'build_in_progress_episode': 'episode.progress', 'build_recently_watched_episode': 'episode.recently_watched',
	'build_next_episode': 'episode.next', 'build_my_calendar': 'episode.trakt', 'build_mdbl_calendar': 'episode.mdblist',
	'build_mdbl_next_up': 'episode.mdblist_next', 'build_punchplay_calendar': 'episode.punchplay',
	'build_simkl_calendar': 'episode.simkl', 'build_simkl_public_calendar': 'episode.simkl_public'}

def extras_button_label_values():
	return {'movie':
				{'movies_play': 'Play', 'show_trailers': 'Trailer', 'show_images': 'Images',  'show_extrainfo': 'Extra Info', 'show_genres': 'Genres',
				'show_director': 'Director', 'show_options': 'Options', 'show_recommended': 'Recommended', 'show_related': 'Related', 'show_more_like_this': 'More Like This',
				'show_similar': 'Similar', 'show_reviews': 'Reviews', 'show_comments': 'Comments', 'show_trivia': 'Trivia', 'show_blunders': 'Blunders',
				'show_year': 'More Year', 'show_genre': 'More Genres', 'show_network': 'More Network',
				'show_mdblist_manager': 'MDBList', 'show_punchplay_manager': 'PunchPlay', 'show_simkl_manager': 'Simkl Lists', 'show_tmdb_manager': 'TMDb Lists', 'show_trakt_manager': 'Trakt Lists', 'show_personallists_manager': 'Personal Lists',
				'show_favorites_manager': 'Favorites Lists', 'playback_choice': 'Play Options', 'show_plot': 'Plot', 'show_keywords': 'Keywords',
				'show_in_trakt_lists': 'In Trakt Lists', 'close_all': 'Close'},
			'tvshow':
				{'tvshow_browse': 'Browse', 'show_trailers': 'Trailer', 'show_images': 'Images', 'show_extrainfo': 'Extra Info', 'show_genres': 'Genres',
				'play_nextep': 'Play Next', 'show_options': 'Options', 'show_recommended': 'Recommended', 'show_related': 'Related', 'show_more_like_this': 'More Like This',
				'show_similar': 'Similar', 'show_reviews': 'Reviews', 'show_comments': 'Comments', 'show_trivia': 'Trivia', 'show_blunders': 'Blunders',
				'show_year': 'More Year', 'show_genre': 'More Genres', 'show_network': 'More Network',
				'show_mdblist_manager': 'MDBList', 'show_punchplay_manager': 'PunchPlay', 'show_simkl_manager': 'Simkl Lists', 'show_tmdb_manager': 'TMDb Lists', 'show_trakt_manager': 'Trakt Lists', 'show_personallists_manager': 'Personal Lists',
				'show_favorites_manager': 'Favorites Lists', 'play_random_episode': 'Play Random', 'show_plot': 'Plot', 'show_keywords': 'Keywords',
				'show_in_trakt_lists': 'In Trakt Lists', 'close_all': 'Close'}}

def extras_items():
	return [{'name': 'Plot', 'value': 2050}, {'name': 'Cast', 'value': 2051}, {'name': 'Recommended', 'value': 2052}, {'name': 'Related', 'value': 2053},
	{'name': 'More Like This', 'value': 2054}, {'name': 'Similar', 'value': 2055}, {'name': 'Reviews', 'value': 2056}, {'name': 'Comments', 'value': 2057},
	{'name': 'Trivia', 'value': 2058}, {'name': 'Blunders', 'value': 2059}, {'name': 'Parental Guide', 'value': 2060}, {'name': 'In Trakt Lists', 'value': 2061},
	{'name': 'Videos', 'value': 2062}, {'name': 'More from Year', 'value': 2063}, {'name': 'More from Genres', 'value': 2064}, {'name': 'More from Networks', 'value': 2065},
	{'name': 'More from Collection', 'value': 2066}]

def context_menu_items():
	return [
	{'name': 'Extras', 'value': 'extras'}, {'name': 'Options', 'value': 'options'}, {'name': 'Play Options', 'value': 'playback_options'},
	{'name': 'Select Source', 'value': 'select_source'}, {'name': 'Rescrape & Select Source', 'value': 'rescrape_select_source'},
	{'name': 'External Scraper Settings', 'value': 'external_scraper_settings'},
	{'name': 'Browse Movie Set', 'value': 'browse_movie_set'}, {'name': 'Browse TV Seasons', 'value': 'browse_seasons'},
	{'name': 'Browse Season Episodes', 'value': 'browse_episodes'}, {'name': 'Browse Recommended', 'value': 'recommended'}, {'name': 'Browse Related', 'value': 'related'},
	{'name': 'Browse More Like This', 'value': 'more_like_this'}, {'name': 'Browse Similar', 'value': 'similar'}, {'name': 'In Trakt Lists', 'value': 'in_trakt_list'},
	{'name': 'MDBList Manager', 'value': 'mdblist_manager'}, {'name': 'MDBList Watchlist', 'value': 'mdblist_watchlist'}, {'name': 'MDBList Library', 'value': 'mdblist_library'},
	{'name': 'PunchPlay Manager', 'value': 'punchplay_manager'},
	{'name': 'Simkl Lists Manager', 'value': 'simkl_manager'}, {'name': 'Simkl Plan to Watch', 'value': 'simkl_plantowatch'},
	{'name': 'TMDb Lists Manager', 'value': 'tmdb_manager'}, {'name': 'TMDb Watchlist', 'value': 'tmdb_watchlist'}, {'name': 'TMDb Favorites', 'value': 'tmdb_favorites'},
	{'name': 'Trakt Lists Manager', 'value': 'trakt_manager'}, {'name': 'Trakt Watchlist', 'value': 'trakt_watchlist'}, {'name': 'Trakt Library', 'value': 'trakt_collection'},
	{'name': 'Personal Lists Manager', 'value': 'personal_manager'}, {'name': 'Favorites Manager', 'value': 'favorites_manager'}, {'name': 'Mark Watched/Unwatched', 'value': 'mark_watched'},
	{'name': 'Unmark Previous Watched Episode', 'value': 'unmark_previous_episode'}, {'name': 'Exit List', 'value': 'exit'}, {'name': 'Refresh Widgets', 'value': 'refresh'},
	{'name': 'Reload Widgets', 'value': 'reload'}]

def rescrape_items():
	return [
	{'name': 'Rescrape With No Cache Check', 'value': 'cache_ignored'},
	{'name': 'Rescrape With IMDb Year Data', 'value': 'imdb_year'},
	{'name': 'Rescrape With Disabled External Providers', 'value': 'with_all'},
	{'name': 'Rescrape With Episode Group', 'value': 'episode_group'},
	{'name': 'Rescrape with Filters Ignored', 'value': 'ignore_filters'},
	{'name': 'Offer Full Search After Early Results', 'value': 'full_scrape'}]

def video_extensions():
	return ('m4v', '3g2', '3gp', 'nsv', 'tp', 'ts', 'ty', 'pls', 'rm', 'rmvb', 'mpd', 'ifo', 'mov', 'qt', 'divx', 'xvid', 'bivx', 'vob', 'nrg', 'img', 'iso', 'udf', 'pva',
			'wmv', 'asf', 'asx', 'ogm', 'm2v', 'avi', 'bin', 'dat', 'mpg', 'mpeg', 'mp4', 'mkv', 'mk3d', 'avc', 'vp3', 'svq3', 'nuv', 'viv', 'dv', 'fli', 'flv', 'wpl',
			'xspf', 'vdr', 'dvr-ms', 'xsp', 'mts', 'm2t', 'm2ts', 'evo', 'ogv', 'sdp', 'avs', 'rec', 'url', 'pxml', 'vc1', 'h264', 'rcv', 'rss', 'mpls', 'mpl', 'webm',
			'bdmv', 'bdm', 'wtv', 'trp', 'f4v', 'pvr', 'disc')

def image_extensions():
	return ('jpg', 'jpeg', 'jpe', 'jif', 'jfif', 'jfi', 'bmp', 'dib', 'png', 'gif', 'webp', 'tiff', 'tif',
			'psd', 'raw', 'arw', 'cr2', 'nrw', 'k25', 'jp2', 'j2k', 'jpf', 'jpx', 'jpm', 'mj2')

def kodi_progress_background():
	return xbmcgui.DialogProgressBG()

def get_visibility(obj):
	return xbmc.getCondVisibility(obj)

def get_infolabel(label):
	return xbmc.getInfoLabel(label)

def kodi_actor():
	return xbmc.Actor

def translate_path(_path):
	return xbmcvfs.translatePath(_path)

def kodi_monitor():
	return xbmc.Monitor()

def kodi_player():
	return xbmc.Player()

def playback_is_paused():
	try:
		if get_visibility('Player.Paused'):
			return True
	except:
		pass
	try:
		player = kodi_player()
		if not (player.isPlayingVideo() or player.isPlaying()):
			return False
		props = get_jsonrpc({'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetProperties', 'params': {'playerid': 1, 'properties': ['speed']}})
		if props is not None and float(props.get('speed', 1)) == 0.0:
			return True
	except:
		pass
	return False

def kodi_dialog():
	return xbmcgui.Dialog()

def is_android():
	return get_visibility('System.Platform.Android')

def _folder_has_entries(path):
	try:
		tpath = translate_path(path)
		if not path_exists(tpath) or not os.path.isdir(tpath):
			return False
		with os.scandir(tpath) as scan:
			return any(True for _ in scan)
	except:
		return False

def safe_browse_defaultt(path):
	# Kodi on Android can block parent navigation when browse opens inside a non-empty folder.
	if not is_android() or not path or path in ('None', ''):
		return path
	if _folder_has_entries(path):
		return ''
	return path

_ADDON_DATA_SPECIAL = 'special://profile/addon_data/plugin.video.redlight/'

def portable_addon_data_path(path, as_folder=True):
	'''Prefer special:// when a path is under Red Light addon_data; keep OS-wide paths absolute.'''
	if not path or str(path).strip() in ('', 'None', 'empty_setting'):
		return path
	raw = str(path).strip()
	slash_form = raw.replace('\\', '/')
	special_prefix = 'special://profile/addon_data/plugin.video.redlight'
	if slash_form.lower().startswith(special_prefix):
		result = slash_form
		if as_folder and not result.endswith('/'):
			result += '/'
		return result
	try:
		if slash_form.lower().startswith('special://'):
			native = os.path.normpath(translate_path(slash_form))
		else:
			native = os.path.normpath(raw)
		profile = os.path.normpath(translate_path(_ADDON_DATA_SPECIAL))
		native_cmp = os.path.normcase(native)
		profile_cmp = os.path.normcase(profile)
		if native_cmp == profile_cmp:
			return _ADDON_DATA_SPECIAL
		if not native_cmp.startswith(profile_cmp + os.sep):
			return raw
		rel = os.path.relpath(native, profile).replace('\\', '/')
		if rel in ('.', ''):
			return _ADDON_DATA_SPECIAL
		result = _ADDON_DATA_SPECIAL + rel
		if as_folder and not result.endswith('/'):
			result += '/'
		return result
	except Exception:
		return raw

def browse_start_path(path, force_defaultt=False):
	'''Real filesystem path for Kodi browse defaultt.

	Never pass special:// into Dialog.browse — that opens a virtual tree where
	parent navigation cannot reach storage roots (so users cannot pick an
	OS-wide Import/Export or download folder). force_defaultt is kept for
	callers but no longer feeds special:// to the dialog.
	'''
	if not path or str(path).strip() in ('', 'None', 'empty_setting'):
		return None
	native = translate_path(path)
	if not native or not str(native).strip():
		return None
	# Android: opening inside a non-empty folder can block leaving via parent.
	start = safe_browse_defaultt(native)
	if start == '':
		return ''
	return start if start else None

def _browse_paths_equal(a, b):
	if not a or not b:
		return False
	try:
		return os.path.normpath(translate_path(a)) == os.path.normpath(translate_path(b))
	except:
		return a == b

def browse_directory(defaultt='', heading='Choose folder', use_defaultt=False, confirm_unchanged=False, force_defaultt=False):
	# Kodi returns defaultt unchanged when the user cancels (same as pressing OK without moving).
	start = browse_start_path(defaultt, force_defaultt=force_defaultt) if use_defaultt else None
	result = kodi_dialog().browse(0, heading, '', defaultt=start)
	if not result or not str(result).strip():
		return None
	if start is not None and _browse_paths_equal(result, start):
		if confirm_unchanged:
			display = result if len(result) <= 120 else '%s...' % result[:117]
			if not confirm_dialog(
				heading=heading,
				text='Use this folder?[CR][CR][B]%s[/B]' % display,
				ok_label='Continue',
				cancel_label='Cancel',
				default_control=10,
			):
				return None
		else:
			return None
	return result

def browse_file(mask='', defaultt='', heading='Choose file', force_defaultt=False):
	# File browse: cancel with a folder defaultt returns that path, not an empty string.
	start = browse_start_path(defaultt, force_defaultt=force_defaultt)
	result = kodi_dialog().browse(1, heading, '', mask, defaultt=start)
	if not result or not str(result).strip():
		return None
	if start is not None and _browse_paths_equal(result, start) and not os.path.isfile(translate_path(result)):
		return None
	return result

def addon_info(info):
	return xbmcaddon.Addon('plugin.video.redlight').getAddonInfo(info)

def addon_version():
	return get_property('redlight.addon_version') or addon_info('version')

def addon_path():
	return get_property('redlight.addon_path') or addon_info('path')

def addon_profile():
	try:
		return translate_path(addon_info('profile'))
	except:
		return get_property('redlight.addon_profile') or ''

def addon_icon():
	return get_property('redlight.addon_icon') or translate_path(addon_info('icon'))

def addon_icon_mini():
	return get_property('redlight.addon_icon_mini') or os.path.join(addon_info('path'), 'resources', 'media', 'addon_icons', 'minis',
														os.path.basename(translate_path(addon_info('icon'))))

def addon_fanart():
	return (
		get_property('redlight.addon_fanart')
		or 'special://home/addons/plugin.video.redlight/resources/media/fanart.jpg'
	)

MEDIA_GITHUB_USER = 'The-Red-Wizard'
MEDIA_GITHUB_REPO = 'TheRedWizard.github.io'
MEDIA_GITHUB_RAW = 'https://raw.githubusercontent.com/%s/%s/main/packages/media' % (MEDIA_GITHUB_USER, MEDIA_GITHUB_REPO)
LEGACY_MEDIA_GITHUB_RAW = 'https://raw.githubusercontent.com/TheRedWizard/TheRedWizard.github.io/main/packages/media'
# Estuary WideList row icons use ListItem.Icon only for Container.Content() — not files.
MENU_FOLDER_CONTENT = ''
# EasyNews search / debrid cloud: skins (FENtastic, Aeon Nox, Nimbus) show thumbs when content is files.
PREMIUM_FILES_CONTENT = 'files'

def media_github_credentials():
	return MEDIA_GITHUB_USER, MEDIA_GITHUB_REPO

def get_icon(image_name, image_folder='icons', image_type='png'):
	local_path = os.path.join(addon_info('path'), 'resources', 'media', image_folder, '%s.%s' % (image_name, image_type))
	if os.path.exists(local_path):
		return local_path
	return '%s/%s/%s.%s' % (MEDIA_GITHUB_RAW, image_folder, image_name, image_type)

def resolve_list_icon(icon, default_name='folder'):
	if not icon:
		return get_icon(default_name)
	if icon.startswith('http'):
		if icon.startswith(LEGACY_MEDIA_GITHUB_RAW):
			return MEDIA_GITHUB_RAW + icon[len(LEGACY_MEDIA_GITHUB_RAW):]
		return icon
	icon_norm = icon.replace('\\', '/')
	if icon_norm.startswith('special://') or 'plugin.video.redlight/resources/media/' in icon_norm:
		for folder in ('icons', 'flags', 'network_icons', 'results', 'rpdb_posters', 'themes'):
			if '/%s/' % folder in icon_norm:
				name = os.path.splitext(os.path.basename(icon_norm))[0]
				ext = os.path.splitext(icon_norm)[1].lstrip('.') or 'png'
				return get_icon(name, folder, ext)
		return get_icon(os.path.splitext(os.path.basename(icon_norm))[0])
	return get_icon(icon)

def set_list_item_art(listitem, icon, fanart=None, banner=None, landscape=None):
	art = {'icon': icon, 'poster': icon, 'thumb': icon, 'banner': banner or icon, 'landscape': landscape or icon}
	if fanart: art['fanart'] = fanart
	listitem.setArt(art)
	try: listitem.setIconImage(icon) # Estuary WideList reads ListItem.Icon, not Art(thumb).
	except: pass

def finish_premium_listitem(listitem, icon, fanart=None, plot=' '):
	"""Art after InfoTag so getVideoInfoTag does not drop EasyNews/cloud thumbs."""
	try:
		listitem.getVideoInfoTag().setPlot(plot)
	except: pass
	set_list_item_art(listitem, icon, fanart=fanart)

def get_addon_fanart():
	return get_property('redlight.default_addon_fanart') or addon_fanart()

def build_url(url_params):
	return 'plugin://plugin.video.redlight/?%s' % urlencode(url_params)

# Keep `random` / `shuffle` on folder URLs — stripping `random` broke Random Trakt Public (All)
# and any other list-of-lists parent that only passed random=true (shuffle alone was the workaround).
_FOLDER_URL_SKIP = frozenset(('iconImage', 'random_support', 'name', 'isFolder'))
_FOLDER_URL_KEEP_NAME_MODES = frozenset(('navigator.build_shortcut_folder_contents',))

def _folder_url_keep_name(mode):
	if mode in _FOLDER_URL_KEEP_NAME_MODES: return True
	return mode.startswith('random.build_')

def build_folder_url(url_params):
	mode = url_params.get('mode', '')
	skip = _FOLDER_URL_SKIP
	if _folder_url_keep_name(mode):
		skip = skip - frozenset(('name',))
	routing = {k: v for k, v in url_params.items() if k not in skip and v not in (None, '')}
	if 'category_name' not in routing and url_params.get('name') and mode in ('build_movie_list', 'build_tvshow_list'):
		routing['category_name'] = url_params['name']
	return build_url(routing)

def sanitize_folder_url(url):
	if not url or 'plugin.video.redlight' not in url: return url
	try:
		from urllib.parse import parse_qsl, unquote
		query = unquote(url.split('?', 1)[-1])
		params = dict(parse_qsl(query, keep_blank_values=True))
		return build_folder_url(params)
	except: return url

def set_browse_exit_params(list_mode='tvshow', action=None):
	if external(): return
	set_property('redlight.exit_params', browse_list_exit_params(list_mode, action))

def browse_list_exit_params(list_mode='tvshow', action=None):
	folder_path = get_infolabel('Container.FolderPath')
	parent_tokens = (
		'navigator.', 'mdblist.', 'punchplay.', 'simkl.', 'trakt.list', 'tmdblist.', 'personal_lists.',
		'build_tmdb_lists_contents', 'build_mdblist_lists_contents')
	if any(token in folder_path for token in parent_tokens):
		return sanitize_folder_url(folder_path)
	if action:
		action_parent = _browse_action_exit_params.get(action)
		if action_parent: return build_folder_url(action_parent)
		subnav_parent = _browse_subnav_exit_params.get(action)
		if subnav_parent: return build_folder_url(subnav_parent)
	build_mode = 'build_movie_list' if list_mode == 'movie' else 'build_tvshow_list'
	if build_mode in folder_path:
		nav_actions = {'movie': 'MovieList', 'tvshow': 'TVShowList', 'anime': 'AnimeList'}
		return build_folder_url({'mode': 'navigator.main', 'action': nav_actions.get(list_mode, 'TVShowList')})
	return sanitize_folder_url(folder_path)

def list_collection_exit_params(params=None):
	folder_path = get_infolabel('Container.FolderPath')
	parent_tokens = (
		'trakt.list.get_trakt_lists', 'trakt.list.search_trakt', 'trakt.list.get_trakt_user_lists',
		'tmdblist.get_tmdb_lists', 'personal_lists.get_personal_lists', 'navigator.', 'mdblist.', 'punchplay.', 'simkl.')
	if any(token in folder_path for token in parent_tokens):
		return sanitize_folder_url(folder_path)
	params = params or {}
	mode = params.get('mode', '')
	if mode in ('trakt.list.build_trakt_list', 'random.build_trakt_lists_contents'):
		return build_folder_url({'mode': 'trakt.list.get_trakt_lists', 'list_type': params.get('list_type', 'my_lists')})
	if mode in ('tmdblist.build_tmdb_list', 'random.build_tmdb_lists_contents'):
		return build_folder_url({'mode': 'tmdblist.get_tmdb_lists'})
	if mode in ('personal_lists.build_personal_list', 'random.build_personal_lists_contents'):
		return build_folder_url({'mode': 'personal_lists.get_personal_lists'})
	if mode in ('mdblist.build_mdbl_list', 'random.build_mdblist_lists_contents'):
		list_type = params.get('list_type', 'my_lists')
		if list_type == 'liked_lists':
			return build_folder_url({'mode': 'mdblist.get_mdbl_liked_lists', 'name': 'Liked Lists'})
		if list_type == 'user_lists':
			return build_folder_url({'mode': 'mdblist.get_mdbl_top_lists', 'name': 'Popular MDBLists'})
		return build_folder_url({'mode': 'mdblist.get_mdbl_lists', 'name': 'My Lists'})
	return sanitize_folder_url(folder_path)

_browse_action_exit_params = {
	'mdblist_watchlist': {'mode': 'navigator.mdblist_watchlists'},
	'mdblist_collection': {'mode': 'navigator.mdblist_library'},
	'mdblist_droplist': {'mode': 'navigator.mdblist_lists'},
	'trakt_droplist': {'mode': 'navigator.trakt_lists_personal'},
	'trakt_collection': {'mode': 'navigator.trakt_collections'},
	'trakt_collection_lists': {'mode': 'navigator.trakt_collections'},
	'trakt_watchlist': {'mode': 'navigator.trakt_watchlists'},
	'trakt_watchlist_lists': {'mode': 'navigator.trakt_watchlists'},
	'trakt_favorites': {'mode': 'navigator.trakt_favorites', 'category_name': 'Favorites'},
	'trakt_recommendations': {'mode': 'navigator.trakt_recommendations', 'category_name': 'Recommended'},
	'simkl_plantowatch': {'mode': 'navigator.simkl_watchlists'},
	'simkl_completed': {'mode': 'navigator.simkl_completed'},
	'simkl_watching': {'mode': 'navigator.simkl_watching'},
	'simkl_hold': {'mode': 'navigator.simkl_hold'},
	'simkl_dropped': {'mode': 'navigator.simkl_dropped'},
	'punchplay_watchlist': {'mode': 'navigator.punchplay_watchlists'},
	'punchplay_collection': {'mode': 'navigator.punchplay_collections'},
	'punchplay_favorites': {'mode': 'navigator.punchplay_favourites'},
	'punchplay_plantowatch': {'mode': 'navigator.punchplay_planning'},
	'punchplay_watching': {'mode': 'navigator.punchplay_watching_menu'},
	'punchplay_hold': {'mode': 'navigator.punchplay_on_hold'},
	'punchplay_completed': {'mode': 'navigator.punchplay_watched'},
	'punchplay_dropped': {'mode': 'navigator.punchplay_dropped_menu'},
	'favorites_movies': {'mode': 'navigator.favorites'},
	'favorites_tvshows': {'mode': 'navigator.favorites'},
	'favorites_anime': {'mode': 'navigator.favorites'},
}

_browse_subnav_exit_params = {
	'tmdb_movies_genres': {'mode': 'navigator.genres', 'menu_type': 'movie'},
	'tmdb_tv_genres': {'mode': 'navigator.genres', 'menu_type': 'tvshow'},
	'tmdb_anime_genres': {'mode': 'navigator.genres', 'menu_type': 'anime'},
	'tmdb_movies_providers': {'mode': 'navigator.providers', 'menu_type': 'movie'},
	'tmdb_tv_providers': {'mode': 'navigator.providers', 'menu_type': 'tvshow'},
	'tmdb_anime_providers': {'mode': 'navigator.providers', 'menu_type': 'anime'},
	'tmdb_movies_languages': {'mode': 'navigator.languages', 'menu_type': 'movie'},
	'tmdb_tv_languages': {'mode': 'navigator.languages', 'menu_type': 'tvshow'},
	'tmdb_movies_year': {'mode': 'navigator.years', 'menu_type': 'movie'},
	'tmdb_tv_year': {'mode': 'navigator.years', 'menu_type': 'tvshow'},
	'tmdb_anime_year': {'mode': 'navigator.years', 'menu_type': 'anime'},
	'tmdb_movies_decade': {'mode': 'navigator.decades', 'menu_type': 'movie'},
	'tmdb_tv_decade': {'mode': 'navigator.decades', 'menu_type': 'tvshow'},
	'tmdb_anime_decade': {'mode': 'navigator.decades', 'menu_type': 'anime'},
	'tmdb_movies_certifications': {'mode': 'navigator.certifications', 'menu_type': 'movie'},
	'trakt_tv_certifications': {'mode': 'navigator.certifications', 'menu_type': 'tvshow'},
	'trakt_anime_certifications': {'mode': 'navigator.certifications', 'menu_type': 'anime'},
	'tmdb_tv_networks': {'mode': 'navigator.networks', 'menu_type': 'tvshow'},
	'tmdb_movies_discover': {'mode': 'navigator.discover_contents', 'media_type': 'movie'},
	'tmdb_tv_discover': {'mode': 'navigator.discover_contents', 'media_type': 'tvshow'},
}

def add_dir(handle, url_params, list_name, icon_image='folder', fanart_image=None, isFolder=True):
	fanart = fanart_image or get_addon_fanart()
	icon = get_icon(icon_image)
	url = build_url(url_params)
	listitem = make_listitem()
	listitem.setLabel(list_name)
	info_tag = listitem.getVideoInfoTag()
	info_tag.setPlot(' ')
	set_list_item_art(listitem, icon, fanart=fanart, banner=fanart)
	add_item(handle, url, listitem, isFolder)

def make_listitem(offscreen=True):
	return xbmcgui.ListItem(offscreen=offscreen)

def add_item(handle, url, listitem, isFolder):
	xbmcplugin.addDirectoryItem(handle, url, listitem, isFolder)

def add_items(handle, item_list):
	xbmcplugin.addDirectoryItems(handle, item_list)

def set_content(handle, content):
	xbmcplugin.setContent(handle, content)

def set_category(handle, label):
	xbmcplugin.setPluginCategory(handle, label)

def end_directory(handle, updateListing=False, cacheToDisc=True):
	xbmcplugin.endOfDirectory(handle, updateListing=updateListing, cacheToDisc=cacheToDisc)

# Estuary List (50) is for movies/tvshows content only — not plugin browse folders.
_ESTUARY_MENU_VIEW_MAP = {'50': '55'}

def _view_schema_default(view_type):
	try:
		from caches.settings_cache import default_setting_values
		schema = default_setting_values(view_type.replace('redlight.', ''))
		if schema: return str(schema.get('setting_default', '')).strip()
	except: pass
	return ''

def _resolve_view_id(view_type, fallback_view_types=()):
	view_id = None
	try:
		from caches.settings_cache import get_setting, ensure_settings_properties_loaded
		ensure_settings_properties_loaded()
		view_id = get_property('redlight.%s' % view_type) or get_setting('redlight.%s' % view_type) or get_setting(view_type)
	except: view_id = None
	if not view_id: return None
	view_id = str(view_id).strip()
	if view_type == 'view.main' and 'estuary' in (current_skin() or '').lower():
		view_id = _ESTUARY_MENU_VIEW_MAP.get(view_id, view_id)
	if fallback_view_types:
		primary_default = _view_schema_default(view_type)
		if primary_default and str(view_id) == primary_default:
			for fallback_type in fallback_view_types:
				fallback_id = _resolve_view_id(fallback_type)
				if not fallback_id: continue
				fallback_default = _view_schema_default(fallback_type)
				if str(fallback_id) != str(fallback_default):
					return fallback_id
	return view_id

def set_view_mode(view_type, content='files', is_external=None, fallback_view_types=()):
	if get_property('redlight.use_viewtypes') != 'true': return
	if is_external == None: is_external = external()
	if is_external: return
	view_id = _resolve_view_id(view_type, fallback_view_types)
	if not view_id: return
	if content is None: content = 'files'
	try:
		sleep(100)
		for _ in range(3000):
			if container_content() != content:
				sleep(1)
				continue
			current = get_infolabel('Container.Viewmode.id') or get_infolabel('Container.Viewmode')
			if current and str(current) == str(view_id): return
			execute_builtin('Container.SetViewMode(%s)' % view_id)
			return
	except: return

def random_integer(start=1, end=1000000):
	from random import randint
	return randint(start, end)

def remove_keys(dict_item, dict_removals):
	for k in dict_removals: dict_item.pop(k, None)
	return dict_item

def append_path(_path):
	import sys
	sys.path.append(translate_path(_path))

def logger(heading, function):
	xbmc.log('###%s###: %s' % (heading, function), 1)

def kodi_window():
	return xbmcgui.Window(10000)

def get_property(prop):
	return kodi_window().getProperty(prop)

def set_property(prop, value):
	return kodi_window().setProperty(prop, value)

def clear_property(prop):
	return kodi_window().clearProperty(prop)

def sync_scrape_progress_ui(percent=0, results_sd=0, results_720p=0, results_1080p=0, results_4k=0, results_total=0):
	from caches.settings_cache import get_setting
	set_property('redlight.scrape.percent', str(int(percent)))
	set_property('redlight.scrape.results_sd', str(results_sd))
	set_property('redlight.scrape.results_720p', str(results_720p))
	set_property('redlight.scrape.results_1080p', str(results_1080p))
	set_property('redlight.scrape.results_4k', str(results_4k))
	set_property('redlight.scrape.results_total', str(results_total))
	if get_setting('redlight.highlight.scrape_progress_colours', 'true') == 'true':
		set_property('redlight.scrape.progress_4k_color', get_setting('redlight.scraper_4k_highlight', 'FFFF00FE'))
		set_property('redlight.scrape.progress_1080p_color', get_setting('redlight.scraper_1080p_highlight', 'FFE6B800'))
		set_property('redlight.scrape.progress_720p_color', get_setting('redlight.scraper_720p_highlight', 'FF3C9900'))
		set_property('redlight.scrape.progress_sd_color', get_setting('redlight.scraper_SD_highlight', 'FF0166FF'))
		set_property('redlight.scrape.progress_total_color', get_setting('redlight.scraper_total_highlight', 'FFFFFFFF'))
	else:
		white = 'FFFFFFFF'
		set_property('redlight.scrape.progress_4k_color', white)
		set_property('redlight.scrape.progress_1080p_color', white)
		set_property('redlight.scrape.progress_720p_color', white)
		set_property('redlight.scrape.progress_sd_color', white)
		set_property('redlight.scrape.progress_total_color', white)

def clear_scrape_progress_ui():
	for prop in ('redlight.scrape.percent', 'redlight.scrape.results_sd', 'redlight.scrape.results_720p',
			'redlight.scrape.results_1080p', 'redlight.scrape.results_4k', 'redlight.scrape.results_total',
			'redlight.scrape.progress_4k_color', 'redlight.scrape.progress_1080p_color',
			'redlight.scrape.progress_720p_color', 'redlight.scrape.progress_sd_color',
			'redlight.scrape.progress_total_color',
			'redlight.scrape.ready'):
		clear_property(prop)

def clear_all_properties():
	return kodi_window().clearProperties()

def addon(addon_id='plugin.video.redlight'):
	return xbmcaddon.Addon(id=addon_id)

def addon_installed(addon_id):
	return get_visibility('System.HasAddon(%s)' % addon_id)

def addon_enabled(addon_id):
	return get_visibility('System.AddonIsEnabled(%s)' % addon_id)

def service_scrobbler_defer(addon_id, auth_keys=(), scrobble_enable_keys=()):
	"""Return True when an external service addon should own playback scrobbling."""
	if not addon_installed(addon_id) or not addon_enabled(addon_id): return False
	try: inst = addon(addon_id)
	except: return False
	if auth_keys:
		authed = False
		for key in auth_keys:
			try:
				val = str(inst.getSetting(key) or '').strip()
				if val and val not in ('empty_setting',): authed = True; break
			except: pass
		if not authed: return False
	for key in scrobble_enable_keys:
		try:
			val = str(inst.getSetting(key) or '').strip().lower()
			if val in ('false', '0', 'no', 'off'): return False
			if val in ('true', '1', 'yes', 'on'): return True
		except: pass
	return bool(auth_keys)

def container_content():
	return get_infolabel('Container.Content')

def set_sort_method(handle, method, labelMask=''):
	xbmcplugin.addSortMethod(handle, {'episodes': 24, 'files': 5, 'label': 2, 'none': 0}[method], labelMask=labelMask)

def make_session(url='https://'):
	import requests
	session = requests.Session()
	session.mount(url, requests.adapters.HTTPAdapter(pool_maxsize=100))
	return session	

def make_playlist(playlist_type='video'):
	return xbmc.PlayList({'music': 0, 'video': 1}[playlist_type])

def clear_video_playlist():
	'''Drop episode plugin URLs left on the video playlist when browse/direct play starts during a scrape.'''
	try:
		make_playlist('video').clear()
	except:
		try:
			execute_builtin('Playlist.Clear')
		except:
			pass

def supported_media():
	return xbmc.getSupportedMedia('video')

def path_exists(path):
	return xbmcvfs.exists(path)

def open_file(_file, mode='r'):
	return xbmcvfs.File(_file, mode)

def copy_file(source, destination):
	return xbmcvfs.copy(source, destination)

def delete_file(_file):
	xbmcvfs.delete(_file)

def delete_folder(_folder, force=False):
	xbmcvfs.rmdir(_folder, force)

def rename_file(old, new):
	xbmcvfs.rename(old, new)

def list_dirs(location):
	return xbmcvfs.listdir(location)

def make_directory(path):
	xbmcvfs.mkdir(path)

def make_directories(path):
	xbmcvfs.mkdirs(path)

def sleep(time):
	return xbmc.sleep(time)

def execute_builtin(command, block=False):
	return xbmc.executebuiltin(command, block)

def current_skin():
	return xbmc.getSkinDir()

def get_window_id():
	return xbmcgui.getCurrentWindowId()

def current_window_object():
	return xbmcgui.Window(get_window_id())

def kodi_version():
	return int(get_infolabel('System.BuildVersion')[0:2])

def get_video_database_path():
	"""Resolve the live MyVideos DB under the user profile.

	Prefer the newest non-empty MyVideos*.db on disk (matches Kodi's
	'Running database version MyVideosNNN' log line). Version-number fallbacks
	are only used if that scan fails — see kodi.wiki/view/Databases.
	"""
	import os
	db_dir = translate_path('special://profile/Database')
	try:
		candidates = []
		for name in os.listdir(db_dir):
			if not (name.startswith('MyVideos') and name.endswith('.db')): continue
			path = os.path.join(db_dir, name)
			try:
				if os.path.getsize(path) <= 0: continue
			except Exception:
				continue
			candidates.append(path)
		if candidates:
			return max(candidates, key=lambda p: (os.path.getmtime(p), os.path.getsize(p)))
	except Exception:
		pass
	# Fallback if the profile Database folder is empty/unreadable.
	# https://kodi.wiki/view/Databases — v21 Omega = 131, v22 Piers = 146 (subject to change).
	ver = {19: '119', 20: '121', 21: '131', 22: '146'}.get(kodi_version(), '146')
	return translate_path('special://profile/Database/MyVideos%s.db' % ver)

def show_busy_dialog():
	return execute_builtin('ActivateWindow(busydialognocancel)')

def hide_busy_dialog():
	execute_builtin('Dialog.Close(busydialognocancel)')
	execute_builtin('Dialog.Close(busydialog)')

def close_dialog(dialog, block=False):
	execute_builtin('Dialog.Close(%s,true)' % dialog, block)

def close_all_dialog():
	execute_builtin('Dialog.Close(all,true)')

def run_addon(addon='plugin.video.redlight', block=False):
	return execute_builtin('RunAddon(%s)' % addon, block)

def external():
	return 'redlight' not in get_infolabel('Container.PluginName')

def home():
	return xbmcgui.getCurrentWindowId() == 10000

def folder_path():
	return get_infolabel('Container.FolderPath')

def path_check(string):
	return string in unquote(folder_path())

def reload_skin():
	execute_builtin('ReloadSkin()')

def kodi_refresh():
	execute_builtin('UpdateLibrary(video,special://skin/foo)')

SHUTTING_DOWN_PROP = 'redlight.shutting_down'
PROP_AUTOSCRAPE_TOAST_SHOWN = 'redlight.autoscrape_nextep_toast_shown'
PLAYBACK_WIDGET_REFRESH_PROP = 'redlight.playback_widget_refresh_at'
PLAYBACK_WIDGET_REFRESH_COOLDOWN_SEC = 120
# Next Episodes / In Progress: skip blocking provider sync this long after Stop (local DB already written).
PLAYBACK_LIST_SYNC_SKIP_SEC = 30
BOOT_SYNC_STARTED_PROP = 'redlight.boot_sync_started_at'
BOOT_TRAKT_SYNC_READY_PROP = 'redlight.boot_trakt_sync_ready'
BOOT_SYNC_GATE_TIMEOUT_SEC = 180

def reset_boot_sync_gate():
	try:
		from time import time
		set_property(BOOT_SYNC_STARTED_PROP, str(time()))
	except:
		pass
	clear_property(BOOT_TRAKT_SYNC_READY_PROP)

def mark_boot_trakt_sync_ready():
	set_property(BOOT_TRAKT_SYNC_READY_PROP, 'true')

def boot_trakt_list_refresh_allowed():
	if get_property(BOOT_TRAKT_SYNC_READY_PROP) == 'true':
		return True
	try:
		from time import time
		started = float(get_property(BOOT_SYNC_STARTED_PROP) or 0)
		if started and (time() - started) >= BOOT_SYNC_GATE_TIMEOUT_SEC:
			return True
	except:
		pass
	return False

def service_shutting_down(monitor=None):
	if monitor and monitor.abortRequested(): return True
	return get_property(SHUTTING_DOWN_PROP) == 'true'

def cancel_widget_refresh_alarms():
	try: execute_builtin('CancelAlarm(redlight_widget_refresh,silent)')
	except: pass
	try: execute_builtin('CancelAlarm(redlight_widget_skin,silent)')
	except: pass

def prepare_service_shutdown():
	set_property(SHUTTING_DOWN_PROP, 'true')
	cancel_widget_refresh_alarms()

def schedule_widget_refresh(silent=True, reload_skin=False, defer_browsing=False, delay='00:00:02'):
	if service_shutting_down(): return
	url = 'plugin://plugin.video.redlight/?mode=refresh_widgets&silent=%s&reload_skin=%s&defer_browsing=%s' % (
		'true' if silent else 'false', 'true' if reload_skin else 'false', 'true' if defer_browsing else 'false')
	execute_builtin('AlarmClock(redlight_widget_refresh,RunPlugin(%s),%s,silent)' % (url, delay))

def mark_playback_widget_refresh():
	try:
		from time import time
		set_property(PLAYBACK_WIDGET_REFRESH_PROP, str(time()))
	except:
		pass

def playback_widget_refresh_recent():
	try:
		from time import time
		at = float(get_property(PLAYBACK_WIDGET_REFRESH_PROP) or 0)
		return at > 0 and (time() - at) < PLAYBACK_WIDGET_REFRESH_COOLDOWN_SEC
	except:
		return False

def playback_list_sync_skip_recent():
	"""True shortly after playback wrote local watched/progress — list UIs can paint without a blocking sync."""
	try:
		from time import time
		at = float(get_property(PLAYBACK_WIDGET_REFRESH_PROP) or 0)
		return at > 0 and (time() - at) < PLAYBACK_LIST_SYNC_SKIP_SEC
	except:
		return False

def schedule_playback_widget_refresh():
	"""Refresh home widgets after playback without reloading the in-addon Videos list.

	UpdateLibrary refreshes the active container too. After Stop from Next Episodes that
	re-enters build_next_episode; Back during that GetDirectory fails and Kodi dumps to Files.
	"""
	if service_shutting_down(): return
	mark_playback_widget_refresh()
	schedule_widget_refresh(silent=True, defer_browsing=True)

def refresh_widgets(silent=False, reload_skin=False, defer_browsing=False):
	if service_shutting_down(): return
	# Playback-scheduled refresh: wait until Home (or leave Red Light Videos) so we do not
	# interrupt Next Episodes / In Progress with a second GetDirectory.
	if defer_browsing:
		try:
			if not home() and path_check('plugin.video.redlight'):
				schedule_widget_refresh(silent=silent, reload_skin=reload_skin, defer_browsing=True, delay='00:00:05')
				return
		except: pass
	from caches.settings_cache import get_setting
	from caches.random_widgets_cache import RandomWidgets
	from caches.lists_cache import lists_cache
	RandomWidgets().delete_like('random_list.%')
	if reload_skin: lists_cache.delete_like('trakt_movies_trending_%')
	kodi_refresh()
	try:
		if home(): container_refresh()
	except: pass
	if reload_skin:
		try: execute_builtin('AlarmClock(redlight_widget_skin,ReloadSkin(),00:00:01,silent)')
		except: pass
	if not silent and get_setting('redlight.widget_refresh_notification', 'true') == 'true': notification('Widgets Refreshed', 2500)

def run_plugin(params, block=False):
	if isinstance(params, dict): params = build_url(params)
	return execute_builtin('RunPlugin(%s)' % params, block)

def container_update(params, block=False):
	if isinstance(params, dict): params = build_url(params)
	return execute_builtin('Container.Update(%s)' % params, block)

def activate_window(params, block=False):
	if isinstance(params, dict): params = build_url(params)
	return execute_builtin('ActivateWindow(Videos,%s,return)' % params, block)

def container_refresh():
	return execute_builtin('Container.Refresh')

def container_refresh_input(params, block=False):
	if isinstance(params, dict): params = build_url(params)
	return execute_builtin('Container.Refresh(%s)' % params, block)

def replace_window(params, block=False):
	if isinstance(params, dict): params = build_url(params)
	return execute_builtin('ReplaceWindow(Videos,%s)' % params, block)

def disable_enable_addon(addon_name='plugin.video.redlight'):
	import json
	try:
		xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.SetAddonEnabled', 'params': {'addonid': addon_name, 'enabled': False}}))
		xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.SetAddonEnabled', 'params': {'addonid': addon_name, 'enabled': True}}))
	except: pass

def update_local_addons():
	execute_builtin('UpdateLocalAddons', True)
	sleep(2500)

def addon_ui_busy():
	try:
		player = xbmc.Player()
		if player.isPlaying() or player.isPlayingVideo(): return True
	except: pass
	if get_property('redlight.window_loaded') == 'true': return True
	try:
		if xbmc.getCondVisibility('Window.IsActive(dialog)'): return True
	except: pass
	return False

def language_invoker_from_addon_xml(addon_name='plugin.video.redlight'):
	try:
		from xml.dom.minidom import parse as mdParse
		addon_xml = translate_path('special://home/addons/%s/addon.xml' % addon_name)
		if not path_exists(addon_xml): return 'true'
		root = mdParse(addon_xml)
		tags = root.getElementsByTagName('reuselanguageinvoker')
		if not tags: return 'true'
		node = tags[0].firstChild
		return (node.data or 'true').strip().lower()
	except:
		return 'true'

_ADDON_XML_SYNC_VERSION = 'redlight.addon_xml_sync_version'
_ADDON_XML_APPLIED = 'redlight.addon_xml_applied'

def addon_xml_sync_needed():
	return get_property(_ADDON_XML_SYNC_VERSION) != addon_info('version')

def mark_addon_xml_synced():
	set_property(_ADDON_XML_SYNC_VERSION, addon_info('version'))

def clear_addon_xml_sync_version():
	clear_property(_ADDON_XML_SYNC_VERSION)

def sync_addon_xml_from_settings(addon_name='plugin.video.redlight'):
	from xml.dom.minidom import parse as mdParse
	from caches.settings_cache import get_setting
	addon_xml = translate_path('special://home/addons/%s/addon.xml' % addon_name)
	if not path_exists(addon_xml): return False, False
	invoker_setting = get_setting('redlight.reuse_language_invoker', None)
	icon_setting = get_setting('redlight.addon_icon_choice', None)
	if invoker_setting is None and icon_setting is None: return False, False
	root = mdParse(addon_xml)
	changed = False
	invoker_changed = False
	if invoker_setting is not None:
		tags = root.getElementsByTagName('reuselanguageinvoker')
		if tags:
			node = tags[0].firstChild
			current = (node.data or '').strip().lower() if node else ''
			target = str(invoker_setting).strip().lower()
			if node and current != target:
				node.data = target
				changed = True
				invoker_changed = True
	if icon_setting is not None:
		tags = root.getElementsByTagName('icon')
		if tags:
			node = tags[0].firstChild
			current = (node.data or '').strip() if node else ''
			target = str(icon_setting).strip()
			if node and current != target:
				node.data = target
				changed = True
	if changed:
		new_xml = str(root.toxml()).replace('<?xml version="1.0" ?>', '')
		with open(addon_xml, 'w') as f: f.write(new_xml)
	return changed, invoker_changed

def addon_xml_settings_diff(addon_name='plugin.video.redlight'):
	from xml.dom.minidom import parse as mdParse
	from caches.settings_cache import get_setting
	addon_xml = translate_path('special://home/addons/%s/addon.xml' % addon_name)
	invoker_mismatch = icon_mismatch = False
	if not path_exists(addon_xml): return invoker_mismatch, icon_mismatch
	invoker_setting = get_setting('redlight.reuse_language_invoker', None)
	icon_setting = get_setting('redlight.addon_icon_choice', None)
	root = mdParse(addon_xml)
	if invoker_setting is not None:
		tags = root.getElementsByTagName('reuselanguageinvoker')
		if tags:
			node = tags[0].firstChild
			current = (node.data or '').strip().lower() if node else ''
			target = str(invoker_setting).strip().lower()
			invoker_mismatch = current != target
	if icon_setting is not None:
		tags = root.getElementsByTagName('icon')
		if tags:
			node = tags[0].firstChild
			current = (node.data or '').strip() if node else ''
			target = str(icon_setting).strip()
			icon_mismatch = current != target
	return invoker_mismatch, icon_mismatch

def finish_addon_xml_sync():
	mark_addon_xml_synced()
	set_property(_ADDON_XML_APPLIED, 'true')

def restart_addon_for_addon_xml_change(notify=True):
	if notify:
		notification('Refreshing addon.xml. Restarting Red Light.', 8000)
	execute_builtin('ActivateWindow(Home)', True)
	update_local_addons()
	disable_enable_addon()

def reuse_language_invoker_check(force=False):
	"""Fen-style: restore addon.xml from settings; disable/enable when invoker or icon differs."""
	try:
		if not force and get_property(_ADDON_XML_APPLIED) == 'true' and not addon_xml_sync_needed():
			return False
		invoker_mismatch, icon_mismatch = addon_xml_settings_diff()
		if not invoker_mismatch and not icon_mismatch:
			finish_addon_xml_sync()
			return False
		changed, _invoker_changed = sync_addon_xml_from_settings()
		if not changed:
			logger('Red Light', 'AddonXMLCheck - addon.xml sync failed')
			return False
		logger('Red Light', 'AddonXMLCheck - Change Detected. Restarting Red Light')
		finish_addon_xml_sync()
		restart_addon_for_addon_xml_change(notify=not force)
		return True
	except Exception as e:
		logger('reuse_language_invoker_check', str(e))
		return False

def ensure_addon_xml_from_settings(force=False):
	"""Settings import / forced restore only — not used from plugin routing."""
	return reuse_language_invoker_check(force=force)

def update_kodi_addons_db(addon_name='plugin.video.redlight'):
	import time
	import sqlite3 as database
	try:
		date = time.strftime('%Y-%m-%d %H:%M:%S')
		dbcon = database.connect(translate_path('special://database/Addons33.db'), timeout=40.0)
		dbcon.execute("INSERT OR REPLACE INTO installed (addonID, enabled, lastUpdated) VALUES (?, ?, ?)", (addon_name, 1, date))
		dbcon.close()
	except: pass

def get_jsonrpc(request):
	import json
	response = xbmc.executeJSONRPC(json.dumps(request))
	result = json.loads(response)
	return result.get('result', None)

def jsonrpc_get_directory(directory, properties=['title', 'file', 'thumbnail']):
	command = {'jsonrpc': '2.0', 'id': 1, 'method': 'Files.GetDirectory', 'params': {'directory': directory, 'media': 'files', 'properties': properties}}
	try:
		files = get_jsonrpc(command).get('files')
		results = [i for i in files if i['file'].startswith('plugin://') and i['filetype'] == 'directory']
	except: results = None
	return results

def jsonrpc_get_addons(_type, properties=['thumbnail', 'name']):
	command = {'jsonrpc': '2.0', 'method': 'Addons.GetAddons','params':{'type':_type, 'properties': properties}, 'id': '1'}
	results = get_jsonrpc(command).get('addons')
	return results

def addons_database_path():
	database_dir = translate_path('special://database')
	if database_dir and database_dir[-1] not in ('\\', '/'):
		database_dir = database_dir + '/'
	try:
		_dirs, files = list_dirs(database_dir)
	except:
		files = []
	candidates = [f for f in files if f.lower().startswith('addons') and f.lower().endswith('.db')]
	if not candidates:
		return translate_path('special://database/Addons33.db')
	candidates.sort()
	return database_dir + candidates[-1]

def addon_available_from_repos(addon_id):
	if not addon_id: return False
	if addon_installed(addon_id): return True
	try:
		import sqlite3 as database
		dbcon = database.connect(addons_database_path(), timeout=40.0)
		row = dbcon.execute(
			'SELECT 1 FROM addons AS a JOIN addonlinkrepo AS l ON l.idAddon = a.id WHERE a.addonID = ? LIMIT 1',
			(addon_id,)).fetchone()
		dbcon.close()
		return bool(row)
	except:
		return _addon_listed_in_repo_directories(addon_id)

def _addon_listed_in_repo_directories(addon_id):
	try: repos = jsonrpc_get_addons('xbmc.addon.repository') or []
	except: repos = []
	addon_id_l = addon_id.lower()
	for repo in repos:
		repo_id = repo.get('addonid') or ''
		if not repo_id: continue
		for directory in (
			'addons://%s/' % repo_id,
			'addons://%s/xbmc.python.module/' % repo_id,
			'addons://%s/xbmc.python.pluginsource/' % repo_id):
			command = {'jsonrpc': '2.0', 'id': 1, 'method': 'Files.GetDirectory',
				'params': {'directory': directory, 'media': 'files', 'properties': ['file']}}
			try: files = get_jsonrpc(command).get('files') or []
			except: files = []
			for item in files:
				path = (item.get('file') or '').rstrip('/').lower()
				if path.endswith('/' + addon_id_l) or path.split('/')[-1] == addon_id_l:
					return True
	return False

def jsonrpc_get_system_setting(setting_id, setting_value=''):
	command = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue', 'params': {'setting': setting_id}}
	try: result = get_jsonrpc(command)['value']
	except: result = setting_value
	return result

def jsonrpc_set_system_setting(setting_id, value):
	command = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.SetSettingValue', 'params': {'setting': setting_id, 'value': value}}
	try: return get_jsonrpc(command)
	except: return None

def open_settings(section=None, panel=None):
	try:
		from caches.settings_cache import refresh_settings_manager_properties
		refresh_settings_manager_properties()
	except Exception as e:
		logger('open_settings', 'bootstrap: %s' % e)
	try:
		from apis.aiostreams_api import refresh_settings_properties
		refresh_settings_properties()
	except: pass
	section_indexes = {'torrent': 5, 'direct': 6, '61': 5, '62': 6, 'torrent_sources': 5, 'direct_sources': 6}
	focus_key = str(section or '').strip().lower()
	if focus_key in section_indexes:
		set_property('redlight.settings_manager.focus_index', str(section_indexes[focus_key]))
	else:
		clear_property('redlight.settings_manager.focus_index')
	if panel:
		set_property('redlight.settings_manager.focus_panel', str(panel))
	else:
		clear_property('redlight.settings_manager.focus_panel')
	from windows.base_window import open_window
	try:
		open_window(('windows.settings_manager', 'SettingsManager'), 'settings_manager.xml')
	finally:
		clear_property('redlight.settings_manager.focus_index')
		clear_property('redlight.settings_manager.focus_panel')

def _open_addon_settings(addon_id):
	if not addon_id or addon_id in ('empty_setting', ''): return False
	try:
		addon(addon_id).openSettings()
		return True
	except:
		try:
			execute_builtin('Addon.OpenSettings(%s)' % addon_id, True)
			return True
		except:
			return False

def external_scraper_settings(params=None):
	try:
		import json
		from modules import settings
		params = params or {}
		return_to_settings = str(params.get('return_to', '')).lower() in ('settings', 'torrent', '1', 'true')
		slot = None
		if params.get('slot') not in (None, ''):
			try: slot = int(params.get('slot'))
			except: slot = None
		if return_to_settings:
			close_all_dialog()
			sleep(150)
		slots = settings.configured_external_scraper_slots()
		opened = False
		if not slots:
			external = get_property('redlight.external_scraper.module')
			opened = _open_addon_settings(external)
		elif slot is None and len(slots) != 1:
			list_items = []
			for entry in slots:
				line2 = 'Slot %d' % entry['slot']
				if not entry['enabled']: line2 = '%s (disabled)' % line2
				list_items.append({'line1': entry['display_name'], 'line2': line2})
			kwargs = {'items': json.dumps(list_items), 'heading': 'External Scraper Settings', 'multi_line': 'true'}
			choice = select_dialog(slots, **kwargs)
			if choice is None:
				if return_to_settings: open_settings('torrent', panel=2100)
				return
			opened = _open_addon_settings(choice['module_id'])
		else:
			if slot is None: slot = slots[0]['slot']
			data = settings.external_scraper_slot_data(slot)
			opened = _open_addon_settings(data['module'])
		if return_to_settings and opened:
			open_settings('torrent', panel=2100)
	except: pass

def progress_dialog(heading='', icon=None):
	from threading import Thread
	from windows.base_window import create_window
	progress_dialog = create_window(('windows.progress', 'Progress'), 'progress.xml', heading=heading, icon=icon or addon_icon_mini())
	Thread(target=progress_dialog.run).start()
	for _ in range(40):
		try:
			if progress_dialog.getProperty('redlight.progress_ready') == 'true':
				break
		except: pass
		sleep(50)
	return progress_dialog

def close_progress_dialog(progress):
	if not progress: return
	try:
		progress.is_canceled = True
		progress.close()
	except: pass

def select_dialog(function_list, **kwargs):
	from windows.base_window import open_window
	alt_function_list = kwargs.pop('alt_function_list', None)
	selection = open_window(('windows.default_dialogs', 'Select'), 'select.xml', **kwargs)
	if selection in (None, []): return selection
	if isinstance(selection, dict) and selection.get('alt'):
		if not alt_function_list: return None
		try: return alt_function_list[selection['index']]
		except: return None
	if kwargs.get('multi_choice', 'false') == 'true': return [function_list[i] for i in selection]
	return function_list[selection]

_DIALOG_CONFIRM_CHARS_PER_LINE = 42
_DIALOG_CONFIRM_VISIBLE_LINES = 5

def _dialog_needs_scroll(text):
	if not text: return False
	plain = text
	for tag in ('[B]', '[/B]', '[I]', '[/I]', '[COLOR yellow]', '[/COLOR]'):
		plain = plain.replace(tag, '')
	lines = [i.strip() for i in plain.split('[CR]') if i.strip()]
	wrapped = sum(max(1, (len(line) + _DIALOG_CONFIRM_CHARS_PER_LINE - 1) // _DIALOG_CONFIRM_CHARS_PER_LINE) for line in lines)
	return wrapped > _DIALOG_CONFIRM_VISIBLE_LINES

def confirm_dialog(heading='', text='Are you sure?', ok_label='OK', cancel_label='Cancel', default_control=11, scroll=False, third_label=None):
	from windows.base_window import open_window
	needs_scroll = scroll and _dialog_needs_scroll(text)
	kwargs = {'heading': heading, 'text': text, 'ok_label': ok_label, 'cancel_label': cancel_label, 'default_control': default_control,
				'third_label': third_label or '', 'scroll': 'true' if needs_scroll else 'false',
				'scroll_focus': 'true' if needs_scroll else 'false'}
	raw = open_window(('windows.default_dialogs', 'Confirm'), 'confirm.xml', **kwargs)
	if third_label:
		return raw
	if raw is True or raw is False:
		return raw
	return None

def ok_dialog(heading='', text='No Results', ok_label='OK', scroll=False):
	from windows.base_window import open_window
	needs_scroll = scroll and _dialog_needs_scroll(text)
	# Keep OK focused so Enter dismisses; Up reaches the scrollbar when text is long.
	kwargs = {'heading': heading, 'text': text, 'ok_label': ok_label,
				'scroll': 'true' if needs_scroll else 'false', 'scroll_focus': 'false'}
	return open_window(('windows.default_dialogs', 'OK'), 'ok.xml', **kwargs)

def show_text(heading, text=None, file=None, font_size='small', kodi_log=False):
	import re
	from windows.base_window import open_window
	heading = heading.replace('[B]', '').replace('[/B]', '')
	if file:
		with open(file, encoding='utf-8') as r: text = r.readlines()
	if kodi_log:
		confirm = confirm_dialog(text='Show Log Errors Only?', ok_label='Yes', cancel_label='No')
		if confirm == None: return
		if confirm: text = [i for i in text if any(x in i.lower() for x in ('exception', 'error', '[test]'))]
	if isinstance(text, str):
		# Callers often use Kodi [CR] as a line break (e.g. Clean Databases). Treat like \n
		# before wrap — otherwise one giant line hard-splits mid-[COLOR]/[B] and shows orphan tags.
		text = text.replace('[CR]', '\n').splitlines()
	# List labels do not wrap; overflow becomes "...". Wrap by estimated pixel width for
	# Estuary NotoSans (font14/33 large, font12/25 small). Label is 1214px; keep a small
	# margin so dense/proportional lines are not truncated mid-word.
	bbcode_re = re.compile(r'\[/?[^\[\]]+\]')
	# Keep spaces inside [B]/[I]/[COLOR] spans so wrap cannot split e.g. [I]Original Air Date[/I].
	# COLOR tags may be "[COLOR green]" or "[COLOR=green]" / "[COLOR ff00ff00]".
	bbcode_span_re = re.compile(
		r'\[(B|I|LIGHT|UPPERCASE|LOWERCASE|CAPITALIZE)\](?:(?!\[/\1\]).)*\[/\1\]'
		r'|\[COLOR(?:\s|=)[^\]]+\].*?\[/COLOR\]',
		re.I | re.DOTALL
	)
	bbcode_tag_re = re.compile(r'\[(/?)([^\]]+)\]')
	nbsp = '\u00a0'
	# ASCII 32-126 advance widths (rounded) for NotoSans-Regular at the active size.
	if str(font_size).lower() == 'large':
		char_widths = (9, 9, 13, 21, 19, 27, 24, 7, 10, 10, 18, 19, 9, 11, 9, 12, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 9, 9, 19, 19, 19, 14, 30, 21, 21, 21, 24, 18, 17, 24, 24, 11, 9, 20, 17, 30, 25, 26, 20, 26, 21, 18, 18, 24, 20, 31, 19, 19, 19, 11, 12, 11, 19, 15, 9, 19, 20, 16, 20, 19, 11, 20, 20, 9, 9, 18, 9, 31, 20, 20, 20, 20, 14, 16, 12, 20, 17, 26, 17, 17, 16, 13, 18, 13, 19)
		extra_widths = {'\u2014': 33, '\u2013': 17, '\u2026': 26, '\u2019': 6, '\u2018': 6, '\u201c': 12, '\u201d': 12, '\u00b7': 9, nbsp: 9}
		default_width, max_px = 19, 1190
	else:
		char_widths = (7, 7, 10, 16, 14, 21, 18, 6, 8, 8, 14, 14, 7, 8, 7, 9, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 7, 7, 14, 14, 14, 11, 22, 16, 16, 16, 18, 14, 13, 18, 19, 8, 7, 15, 13, 23, 19, 20, 15, 20, 16, 14, 14, 18, 15, 23, 15, 14, 14, 8, 9, 8, 14, 11, 7, 14, 15, 12, 15, 14, 9, 15, 15, 6, 6, 13, 6, 23, 15, 15, 15, 15, 10, 12, 9, 15, 13, 20, 13, 13, 12, 10, 14, 10, 14)
		extra_widths = {'\u2014': 25, '\u2013': 13, '\u2026': 20, '\u2019': 4, '\u2018': 4, '\u201c': 9, '\u201d': 9, '\u00b7': 7, nbsp: 7}
		default_width, max_px = 14, 1190

	def _text_width(value):
		total = 0
		for char in bbcode_re.sub('', value).replace(nbsp, ' '):
			code = ord(char)
			if 32 <= code <= 126:
				total += char_widths[code - 32]
			else:
				total += extra_widths.get(char, default_width)
		return total

	def _protect_bbcode_spaces(value):
		return bbcode_span_re.sub(lambda m: m.group(0).replace(' ', nbsp), value)

	def _tag_stack_delta(stack, value):
		for match in bbcode_tag_re.finditer(value):
			closing, name = match.group(1), match.group(2)
			base = name.split(' ', 1)[0].split('=', 1)[0].upper()
			if closing:
				for idx in range(len(stack) - 1, -1, -1):
					open_base = stack[idx].split(' ', 1)[0].split('=', 1)[0].upper()
					if open_base == base:
						del stack[idx]
						break
			else:
				stack.append(name)

	def _open_tags(stack):
		return ''.join('[%s]' % name for name in stack)

	def _close_tags(stack):
		return ''.join('[/%s]' % name.split(' ', 1)[0].split('=', 1)[0] for name in reversed(stack))

	def _balance_bbcode(parts):
		# Close open markup at each line end and reopen on the next so a wrap cannot leave
		# orphan tags like [I]Original / Air Date[/I] (which Kodi then fails to italicise).
		stack, balanced = [], []
		for part in parts:
			prefix = _open_tags(stack)
			_tag_stack_delta(stack, part)
			balanced.append((prefix + part + _close_tags(stack)).replace(nbsp, ' '))
		return balanced

	def _wrap_line(value, width):
		value = _protect_bbcode_spaces(value)
		if _text_width(value) <= width:
			return [value.replace(nbsp, ' ')]
		parts, current = [], ''
		for word in value.split(' '):
			candidate = word if not current else '%s %s' % (current, word)
			if current and _text_width(candidate) > width:
				parts.append(current)
				current = word
				while _text_width(current) > width:
					# Hard-split oversized tokens (URLs, long unbroken strings).
					# Never cut inside a [...] BBCode tag — that yields orphan "[COLOR green]" lines.
					cut, idx = current, 1
					while idx < len(cut) and _text_width(cut[:idx]) <= width:
						idx += 1
					idx = max(1, idx - 1)
					open_bracket = cut.rfind('[', 0, idx)
					close_bracket = cut.rfind(']', 0, idx)
					if open_bracket > close_bracket:
						# Mid-tag: finish the tag if present, else back up before '['.
						tag_end = cut.find(']', open_bracket)
						if tag_end != -1 and _text_width(cut[:tag_end + 1]) <= width:
							idx = tag_end + 1
						elif open_bracket > 0:
							idx = open_bracket
					parts.append(cut[:idx])
					current = cut[idx:]
			else:
				current = candidate
		if current:
			parts.append(current)
		return _balance_bbcode(parts or [value])

	processed_lines = []
	for line in text:
		clean_line = line.rstrip('\r\n')
		processed_lines.extend(_wrap_line(clean_line, max_px))
	return open_window(('windows.textviewer', 'TextViewer'), 'textviewer.xml', heading=heading, text=processed_lines, font_size=font_size)

LIST_ITEM_NOT_IN_LIST = 'Item not in list'

def notification(line1, time=5000, icon=None, settle_ms=0):
	# Brief delay helps Kodi show the toast after select/confirm dialogs close (rapid calls can drop it otherwise).
	# sound=False: silent toast — especially during playback (Next Episode Ready, Next Up).
	if settle_ms: sleep(settle_ms)
	kodi_dialog().notification('Red Light', line1, icon or addon_icon_mini(), time, False)

def player_check(mode, params):
	from modules.settings import playback_key
	if mode == 'playback.%s' % playback_key():
		from modules.sources import Sources
		Sources().playback_prep(params)
	elif mode == 'playback.video':
		from modules.player import RedLightPlayer
		RedLightPlayer().run(params.get('url', None), params.get('obj', None))
	else: ok_dialog('External Playback Detected', 'Playback through external addons is not supported')

def external_playback_check(params):
	return True

def timeIt(func):
	# Thanks to 123Venom
	import time
	fnc_name = func.__name__
	def wrap(*args, **kwargs):
		started_at = time.time()
		result = func(*args, **kwargs)
		logger('%s.%s' % (__name__ , fnc_name), (time.time() - started_at))
		return result
	return wrap

def volume_checker():
	# 0% == -60db, 100% == 0db
	try:
		if get_property('redlight.playback.volumecheck_enabled') == 'false' or get_visibility('Player.Muted'): return
		from modules.utils import string_alphanum_to_num
		max_volume = min(int(get_property('redlight.playback.volumecheck_percent') or '50'), 100)
		if int(100 - (float(string_alphanum_to_num(get_infolabel('Player.Volume').split('.')[0]))/60)*100) > max_volume: execute_builtin('SetVolume(%d)' % max_volume)
	except: pass

def focus_index(index):
	current_window = current_window_object()
	focus_id = current_window.getFocusId()
	try: current_window.getControl(focus_id).selectItem(index)
	except: pass

def get_all_icons():
	import requests
	from caches.main_cache import cache_object
	username, location = media_github_credentials()
	def _process(dummy):
		try:
			results = requests.get('https://api.github.com/repos/%s/%s/contents/packages/media/icons' % (username, location))
			results = [i['name'].replace('.png', '') for i in results.json()]
			return results
		except: return ['folder']
	return cache_object(_process, 'all_icons', 'foo', False, 168)

def get_all_addon_icons():
	import requests
	from caches.main_cache import cache_object
	username, location = media_github_credentials()
	def _process(dummy):
		try:
			results = requests.get('https://api.github.com/repos/%s/%s/contents/packages/addon_icons' % (username, location))
			return results.json()
		except: return []
	return cache_object(_process, 'all_addon_icons', 'foo', True, 168)

def upload_logfile(params):
	import json
	import requests
	from modules.utils import copy2clip, make_qrcode
	log_files = [('Current Kodi Log', 'kodi.log'), ('Previous Kodi Log', 'kodi.old.log')]
	list_items = [{'line1': i[0]} for i in log_files]
	kwargs = {'items': json.dumps(list_items), 'heading': 'Choose Which Log File to Upload', 'narrow_window': 'true'}
	log_file = select_dialog(log_files, **kwargs)
	if log_file == None: return
	log_name, log_file = log_file
	if not confirm_dialog(heading=log_name): return
	progressDialog = None
	url = 'https://paste.kodi.tv/'
	log_file = translate_path('special://logpath/%s' % log_file)
	if not path_exists(log_file): return ok_dialog(text='Error. Log Upload Failed')
	try:
		show_busy_dialog()
		try:
			with open_file(log_file) as f: text = f.read()
			UserAgent = 'script.kodi.loguploader: 1.0'
			response = requests.post('%s%s' % (url, 'documents'), data=text.encode('utf-8', errors='ignore'), headers={'User-Agent': UserAgent}).json()
		finally:
			hide_busy_dialog()
		if 'key' not in response:
			return ok_dialog(text='Error. Log Upload Failed')
		user_code = response['key']
		url = '%s%s' % (url, user_code)
		copy2clip(url)
		qr_code = make_qrcode(url) or ''
		progressDialog = progress_dialog(heading='Kodi Log Uploader', icon=qr_code)
		countdown_secs = 120
		remaining = countdown_secs
		while not progressDialog.iscanceled() and remaining > 0:
			progressDialog.update(
				'Share or Access with this url: [B]%s[/B][CR]Or scan the QR code on another device.[CR][CR]Auto-closes in [B]%d[/B] seconds (Back to dismiss now).' % (url, remaining),
				int(100 * remaining / countdown_secs))
			for _ in range(10):
				if progressDialog.iscanceled(): break
				sleep(100)
			remaining -= 1
	except:
		ok_dialog(text='Error. Log Upload Failed')
	finally:
		hide_busy_dialog()
		if progressDialog:
			try: progressDialog.close()
			except: pass

def fetch_kodi_imagecache(image):
	import sqlite3 as database
	result = None
	try:
		dbcon = database.connect(translate_path('special://database/Textures13.db'), timeout=40.0)
		dbcur = dbcon.cursor()
		dbcur.execute("SELECT cachedurl FROM texture WHERE url = ?", (image,))
		result = dbcur.fetchone()[0]
	except: pass
	return result
