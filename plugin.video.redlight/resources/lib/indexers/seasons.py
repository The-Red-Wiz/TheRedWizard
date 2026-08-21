# -*- coding: utf-8 -*-
import sys
from modules import kodi_utils, settings
from modules.metadata import tvshow_meta
from modules.utils import get_datetime, adjust_premiered_date, TaskPool
from modules.watched_status import get_database, watched_info_season, get_watched_status_season, get_progress_status_season, count_aired_episodes
# logger = kodi_utils.logger

def build_season_list(params):
	def _process():
		total_aired_eps, episode_count = meta_get('total_aired_eps'), 0
		for item in season_data:
			try:
				cm = []
				cm_append = cm.append
				listitem = make_listitem()
				set_properties = listitem.setProperties
				item_get = item.get
				overview, poster_path, air_date = item_get('overview'), item_get('poster_path'), item_get('air_date')
				season_number, aired_eps = item_get('season_number'), item_get('episode_count')
				season_special = season_number == 0
				if use_name: title = item_get('name', None) or 'Season %s' % season_number
				else: title = 'Season %s' % season_number
				if custom_order is not None: title = '%s - %s' % (show_title, title)
				poster = 'https://image.tmdb.org/t/p/w780%s' % poster_path if poster_path is not None else show_poster
				thumb = poster or show_landscape or show_fanart
				try: year = air_date.split('-')[0]
				except: year = show_year or '2050'
				plot = overview or show_plot
				try: premiered = adjust_premiered_date(air_date, adjust_hours)[1]
				except: premiered = ''
				unaired = aired_eps == 0
				if unaired:
					# Must set watched/unwatched here — Specials sorts last and previously
					# leaked the prior season's counts via unset locals (e.g. S5 10 → Specials 10/37).
					progress, playcount, watched, unwatched = 0, 0, 0, aired_eps
					title = '[COLOR red][I]%s[/I][/COLOR]' % title
				elif season_special:
					title = 'Specials'
					playcount, watched, unwatched = get_watched_status_season(watched_info.get(season_number, None), aired_eps)
					progress = get_progress_status_season(watched, aired_eps)
				else:
					if season_number < total_seasons:
						episode_count += aired_eps
					else:
						# Current/latest season: count by premiered date (same as episode unaired colour).
						aired_eps = count_aired_episodes(meta, season=season_number, current_date=current_date, adjust_hours=adjust_hours)
					playcount, watched, unwatched = get_watched_status_season(watched_info.get(season_number, None), aired_eps)
					progress = get_progress_status_season(watched, aired_eps)
				visible_progress = 0 if progress == 100 else progress
				url_params = build_url({'mode': 'build_episode_list', 'tmdb_id': tmdb_id, 'season': season_number})
				extras_params = build_url({'mode': 'extras_menu_choice', 'tmdb_id': tmdb_id, 'media_type': 'tvshow', 'is_external': is_external})
				options_params = build_url({'mode': 'options_menu_choice', 'content': 'season', 'tmdb_id': tmdb_id, 'poster': show_poster, 'is_external': is_external})
				cm_append(['extras', ('[B]Extras[/B]', 'RunPlugin(%s)' % extras_params)])
				cm_append(['options', ('[B]Options[/B]', 'RunPlugin(%s)' % options_params)])
				settings.append_external_scraper_settings_cm(cm_append, build_url)
				if playcount:
					if hide_watched: continue
				elif not unaired and not season_special:
						cm_append(['mark_watched', ('[B]Mark Watched[/B]', 'RunPlugin(%s)' % build_url({'mode': 'watched_status.mark_season', 'action': 'mark_as_watched',
															'title': show_title, 'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season_number}))])
				if progress:
					cm_append(['mark_watched', ('[B]Mark Unwatched[/B]', 'RunPlugin(%s)' % build_url({'mode': 'watched_status.mark_season', 'action': 'mark_as_unwatched',
														'title': show_title, 'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season_number}))])
				set_properties({'watchedepisodes': str(watched), 'unwatchedepisodes': str(unwatched)})
				set_properties({'totalepisodes': str(aired_eps), 'watchedprogress': str(visible_progress),
								'redlight.extras_params': extras_params, 'redlight.options_params': options_params})
				if is_external:
					cm.extend([['refresh', ('[B]Refresh Widgets[/B]', 'RunPlugin(%s)' % build_url({'mode': 'refresh_widgets'}))],
							['reload', ('[B]Reload Widgets[/B]', 'RunPlugin(%s)' % build_url({'mode': 'kodi_refresh'}))]])
				if custom_cm_menu:
					try: cm = sorted([i for i in cm if i[0] in cm_sort_order], key=lambda k: cm_sort_order[k[0]])
					except: pass
				cm = [i[1] for i in cm]
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setMediaType('season'), info_tag.setTitle(title), info_tag.setOriginalTitle(orig_title), info_tag.setTvShowTitle(show_title), info_tag.setIMDBNumber(imdb_id)
				info_tag.setSeason(season_number), info_tag.setPlot(plot), info_tag.setDuration(episode_run_time), info_tag.setPlaycount(playcount), info_tag.setGenres(genre)
				info_tag.setUniqueIDs({'imdb': imdb_id, 'tmdb': str_tmdb_id, 'tvdb': str_tvdb_id})
				info_tag.setTvShowStatus(status), info_tag.setFirstAired(premiered), info_tag.setStudios(studio), info_tag.setYear(int(year))
				info_tag.setRating(rating), info_tag.setVotes(votes), info_tag.setMpaa(mpaa), info_tag.setCountries(country), info_tag.setTrailer(trailer)
				info_tag.setCast([kodi_actor(name=item['name'], role=item['role'], thumbnail=item['thumbnail']) for item in cast])
				listitem.setLabel(title)
				listitem.setArt({'poster': poster, 'season.poster': poster, 'fanart': show_fanart, 'clearlogo': show_clearlogo, 'landscape': show_landscape, 'thumb': thumb,
								'icon': show_landscape, 'tvshow.poster': poster, 'tvshow.clearlogo': show_clearlogo})
				listitem.addContextMenuItems(cm)
				yield (url_params, listitem, True)
			except: pass
	kodi_actor, make_listitem, build_url = kodi_utils.kodi_actor(), kodi_utils.make_listitem, kodi_utils.build_url
	poster_empty, fanart_empty = kodi_utils.get_icon('box_office'), kodi_utils.addon_fanart()
	handle, is_external = int(sys.argv[1]), kodi_utils.external()
	watched_indicators, adjust_hours, hide_watched = settings.watched_indicators(), settings.date_offset(), is_external and settings.widget_hide_watched()
	current_date = get_datetime()
	cm_sort_order = settings.cm_sort_order()
	custom_cm_menu = cm_sort_order != settings.cm_default_order()
	rpdb_info = settings.rpdb_info('tvshow')
	rpdb_api_key, rpdb_format = rpdb_info['rpdb_api_key'], rpdb_info['rpdb_format']
	use_name = settings.use_season_name()
	meta = tvshow_meta('tmdb_id', params['tmdb_id'], settings.tmdb_api_key(), settings.mpaa_region(), current_date)
	meta_get = meta.get
	tmdb_id, tvdb_id, imdb_id, show_title, show_year = meta_get('tmdb_id'), meta_get('tvdb_id'), meta_get('imdb_id'), meta_get('title'), meta_get('year') or '2050'
	orig_title, status, show_plot = meta_get('original_title', ''), meta_get('status'), meta_get('plot')
	str_tmdb_id, str_tvdb_id, rating, genre = str(tmdb_id), str(tvdb_id), meta_get('rating'), meta_get('genre')
	cast = meta_get('short_cast', []) or meta_get('cast', []) or []
	mpaa, votes, trailer, studio, country = meta_get('mpaa'), meta_get('votes'), str(meta_get('trailer')), meta_get('studio'), meta_get('country')
	episode_run_time, season_data, total_seasons = meta_get('duration'), meta_get('season_data'), meta_get('total_seasons')
	if rpdb_api_key:
		try: show_poster = meta_get('rpdb_poster') % rpdb_api_key + rpdb_format
		except: show_poster = meta_get('poster') or poster_empty
	else: show_poster = meta_get('poster') or poster_empty
	show_fanart = meta_get('fanart') or fanart_empty
	show_clearlogo, show_landscape = meta_get('clearlogo') or '', meta_get('landscape') or ''
	custom_order = params.get('custom_order', None)
	if settings.show_specials(): season_data.sort(key=lambda i: (i['season_number'] == 0, i['season_number']))
	elif custom_order is not None: season_data = [i for i in season_data if i['season_number'] == params['season']]
	else:
		season_data = [i for i in season_data if not i['season_number'] == 0]
		season_data.sort(key=lambda k: k['season_number'])
	watched_info = watched_info_season(tmdb_id, get_database(watched_indicators))
	if watched_indicators == 2 and settings.simkl_user_active():
		from apis.simkl_api import simkl_sync_activities
		simkl_sync_activities()
		watched_info = watched_info_season(tmdb_id, get_database(watched_indicators))
	if watched_indicators == 3 and settings.mdblist_user_active():
		from apis.mdblist_api import mdblist_sync_activities
		mdblist_sync_activities()
		watched_info = watched_info_season(tmdb_id, get_database(watched_indicators))
	list_items = list(list(_process()))
	if custom_order is not None: return (list_items[0], custom_order)
	kodi_utils.add_items(handle, list_items)
	kodi_utils.set_content(handle, 'seasons')
	kodi_utils.set_category(handle, show_title)
	kodi_utils.end_directory(handle, cacheToDisc=False if is_external else True)
	kodi_utils.set_view_mode('view.seasons', 'seasons', is_external)

def single_seasons(seasons_list):
	season_results = []
	threads = TaskPool().tasks(lambda x: season_results.append(build_season_list(x)), seasons_list, min(len(seasons_list), settings.max_threads()))
	[i.join() for i in threads]
	return [i for i in season_results if i]
