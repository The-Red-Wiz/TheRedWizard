# -*- coding: utf-8 -*-
import sys
from modules import kodi_utils, settings, watched_status as ws
from modules.metadata import tvshow_meta, episodes_meta, all_episodes_meta
from modules.utils import jsondate_to_datetime, adjust_premiered_date, make_day, get_datetime, get_current_timestamp, title_key, date_difference, TaskPool
# logger = kodi_utils.logger

def build_episode_list(params):
	def _process():
		for item in episodes_data:
			try:
				cm = []
				cm_append = cm.append
				listitem = make_listitem()
				set_properties = listitem.setProperties
				item_get = item.get
				season, episode, ep_name = item_get('season'), item_get('episode'), item_get('title')
				season_special = season == 0
				episode_date, premiered = adjust_premiered_date(item_get('premiered'), adjust_hours)
				episode_type = item_get('episode_type') or ''
				episode_id = item_get('episode_id') or None
				if season_special: playcount, progress = 0, None
				else:
					playcount = ws.get_watched_status_episode(watched_info, (season, episode))
					if playcount and hide_watched: continue
					if total_seasons: progress = ws.get_progress_status_all_episode(bookmarks, season, episode)
					else: progress = ws.get_progress_status_episode(bookmarks, episode)
				if no_spoilers and not playcount: thumb, plot = show_landscape or show_fanart, tvshow_plot or '* Hidden to Prevent Spoilers *'
				else: thumb, plot = item_get('thumb', None) or show_landscape or show_fanart, item_get('plot') or tvshow_plot
				try: year = premiered.split('-')[0]
				except: year = show_year or '2050'
				duration = item_get('duration')
				if not duration:
					duration = show_duration
					item['duration'] = duration
				if not episode_date or current_date < episode_date:
					display, unaired = '[COLOR red][I]%s[/I][/COLOR]' % ep_name, True
					item['title'] = display
				else: display, unaired = ep_name, False
				extras_params = build_url({'mode': 'extras_menu_choice', 'tmdb_id': tmdb_id, 'media_type': 'episode', 'is_external': is_external})
				options_params = build_url({'mode': 'options_menu_choice', 'content': 'episode', 'tmdb_id': tmdb_id, 'poster': show_poster, 'is_external': is_external})
				playback_options_params = build_url({'mode': 'playback_choice', 'media_type': 'episode', 'meta': tmdb_id, 'season': season, 'playcount': playcount,
												'episode': episode, 'episode_id': episode_id})
				play_params = build_url({'mode': play_mode, 'media_type': 'episode', 'tmdb_id': tmdb_id, 'season': season, 'episode': episode, 'playcount': playcount,
										'episode_id': episode_id, playback_key: playback_key})
				cm_append(['extras', ('[B]Extras[/B]', 'RunPlugin(%s)' % extras_params)])
				cm_append(['options', ('[B]Options[/B]', 'RunPlugin(%s)' % options_params)])
				cm_append(['playback_options', ('[B]Play Options[/B]', 'RunPlugin(%s)' % playback_options_params)])
				settings.append_external_scraper_settings_cm(cm_append, build_url)
				if not unaired and not season_special:
					if playcount:
						cm_append(['mark_watched', ('[B]Mark Unwatched[/B]', 'RunPlugin(%s)' % build_url({'mode': 'watched_status.mark_episode', 'action': 'mark_as_unwatched',
													'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season, 'episode': episode,  'title': title}))])
					else: cm_append(['mark_watched', ('[B]Mark Watched[/B]', 'RunPlugin(%s)' % build_url({'mode': 'watched_status.mark_episode', 'action': 'mark_as_watched',
													'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season, 'episode': episode,  'title': title}))])
					if progress: cm_append(['mark_watched', ('[B]Clear Progress[/B]', 'RunPlugin(%s)' % \
								build_url({'mode': 'watched_status.erase_bookmark', 'media_type': 'episode', 'tmdb_id': tmdb_id,
								'season': season, 'episode': episode, 'refresh': 'true'}))])
				if is_external:
					cm.extend([['refresh', ('[B]Refresh Widgets[/B]', 'RunPlugin(%s)' % build_url({'mode': 'refresh_widgets'}))],
							['reload', ('[B]Reload Widgets[/B]', 'RunPlugin(%s)' % build_url({'mode': 'kodi_refresh'}))]])
				if custom_cm_menu:
					try: cm = sorted([i for i in cm if i[0] in cm_sort_order], key=lambda k: cm_sort_order[k[0]])
					except: pass
				cm = [i[1] for i in cm]
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setMediaType('episode'), info_tag.setTitle(display), info_tag.setOriginalTitle(orig_title), info_tag.setTvShowTitle(title), info_tag.setGenres(genre)
				info_tag.setPlaycount(playcount), info_tag.setSeason(season), info_tag.setEpisode(episode), info_tag.setPlot(plot)
				info_tag.setDuration(duration), info_tag.setIMDBNumber(imdb_id), info_tag.setUniqueIDs({'imdb': imdb_id, 'tmdb': str(tmdb_id), 'tvdb': str(tvdb_id)})
				info_tag.setFirstAired(premiered), info_tag.setTvShowStatus(show_status)
				info_tag.setCountries(country), info_tag.setTrailer(trailer), info_tag.setDirectors(item_get('director'))
				info_tag.setYear(int(year)), info_tag.setRating(item_get('rating')), info_tag.setVotes(item_get('votes')), info_tag.setMpaa(mpaa)
				info_tag.setStudios(studio), info_tag.setWriters(item_get('writer'))
				full_cast = cast + item_get('guest_stars', [])
				info_tag.setCast([kodi_actor(name=item['name'], role=item['role'], thumbnail=item['thumbnail']) for item in full_cast])
				if progress and not unaired:
					info_tag.setResumePoint(ws.get_resume_seconds(progress, duration))
					set_properties({'WatchedProgress': progress})
				listitem.setLabel(display)
				listitem.addContextMenuItems(cm)
				listitem.setArt({'poster': show_poster, 'fanart': show_fanart, 'thumb': thumb, 'icon':thumb, 'clearlogo': show_clearlogo, 'landscape': show_landscape,
								'season.poster': season_poster, 'tvshow.poster': show_poster, 'tvshow.clearlogo': show_clearlogo})
				set_properties({
					'episode_type': episode_type, 'redlight.extras_params': extras_params, 'redlight.options_params': options_params,
					'redlight.playback_options_params': playback_options_params
					})
				yield (play_params, listitem, False)
			except: pass
	kodi_actor, make_listitem, build_url = kodi_utils.kodi_actor(), kodi_utils.make_listitem, kodi_utils.build_url
	poster_empty, fanart_empty = kodi_utils.get_icon('box_office'), kodi_utils.addon_fanart()
	handle, is_external = int(sys.argv[1]), kodi_utils.external()
	no_spoilers = settings.avoid_episode_spoilers()
	item_list = []
	append = item_list.append
	watched_indicators, adjust_hours = settings.watched_indicators(), settings.date_offset()
	current_date, hide_watched = get_datetime(), is_external and settings.widget_hide_watched()
	cm_sort_order = settings.cm_sort_order()
	custom_cm_menu = cm_sort_order != settings.cm_default_order()
	rpdb_info = settings.rpdb_info('tvshow')
	rpdb_api_key, rpdb_format = rpdb_info['rpdb_api_key'], rpdb_info['rpdb_format']
	playback_key = settings.playback_key()
	play_mode = 'playback.%s' % playback_key
	meta = tvshow_meta('tmdb_id', params.get('tmdb_id'), settings.tmdb_api_key(), settings.mpaa_region(), current_date)
	meta_get = meta.get
	tmdb_id, tvdb_id, imdb_id, tvshow_plot, orig_title = meta_get('tmdb_id'), meta_get('tvdb_id'), meta_get('imdb_id'), meta_get('plot'), meta_get('original_title')
	title, show_year, rootname, show_duration, show_status = meta_get('title'), meta_get('year') or '2050', meta_get('rootname'), meta_get('duration'), meta_get('status')
	mpaa, trailer, genre, studio, country = meta_get('mpaa'), str(meta_get('trailer')), meta_get('genre'), meta_get('studio'), meta_get('country')
	cast = meta_get('short_cast', []) or meta_get('cast', []) or []
	season = params['season']
	if rpdb_api_key:
		try: show_poster = meta_get('rpdb_poster') % rpdb_api_key + rpdb_format
		except: show_poster = meta_get('poster') or poster_empty
	else: show_poster = meta_get('poster') or poster_empty
	show_fanart = meta_get('fanart') or fanart_empty
	show_clearlogo = meta_get('clearlogo') or ''
	show_landscape = meta_get('landscape') or ''
	watched_db = ws.get_database(watched_indicators)
	watched_info = ws.watched_info_episode(tmdb_id, watched_db)
	if season == 'all':
		total_seasons = meta_get('total_seasons')
		episodes_data = sorted(all_episodes_meta(meta, settings.show_specials()), key=lambda x: (x['season'], x['episode']))
		bookmarks = ws.get_bookmarks_all_episode(tmdb_id, total_seasons, watched_db)
		season_poster = show_poster
		category_name = 'Season %s' % season if total_seasons == 1 else 'Seasons 1-%s' % total_seasons
	else:
		total_seasons = None
		episodes_data = episodes_meta(season, meta)
		bookmarks = ws.get_bookmarks_episode(tmdb_id, season, watched_db)
		try:
			season_data = meta_get('season_data')
			poster_path = next((i['poster_path'] for i in season_data if i['season_number'] == int(season)), None)
			season_poster = 'https://image.tmdb.org/t/p/w780%s' % poster_path if poster_path is not None else show_poster
		except: season_poster = show_poster
		category_name = 'Season %s' % season
	kodi_utils.add_items(handle, list(_process()))
	kodi_utils.set_sort_method(handle, 'episodes')
	kodi_utils.set_content(handle, 'episodes')
	kodi_utils.set_category(handle, category_name)
	kodi_utils.end_directory(handle, cacheToDisc=False if is_external else True)
	kodi_utils.set_view_mode('view.episodes', 'episodes', is_external)

def build_single_episode(list_type, params={}):
	def _get_category_name():
		try:
			cat_name = {'episode.progress': 'In Progress Episodes',
						'episode.recently_watched': 'Recently Watched Episodes',
						'episode.next_trakt': 'Next Episodes', 'episode.next_redlight': 'Next Episodes', 'episode.next_simkl': 'Next Episodes',
						'episode.trakt': {'true': 'Recently Aired Episodes', None: 'Trakt Calendar'}}[list_type]
			if isinstance(cat_name, dict): cat_name = cat_name[params.get('recently_aired')]
		except: cat_name = 'Episodes'
		return cat_name
	def _process(_position, ep_data):
		try:
			ep_data_get = ep_data.get
			meta = tvshow_meta('trakt_dict', ep_data_get('media_ids'), api_key, mpaa_region_value, current_date, current_time, is_anime_list=is_anime_list)
			if not meta: return
			meta_get = meta.get
			cm = []
			cm_append = cm.append
			listitem = make_listitem()
			set_properties = listitem.setProperties
			orig_season, orig_episode = ep_data_get('season'), ep_data_get('episode')
			unwatched = ep_data_get('unwatched', False)
			_position = ep_data_get('custom_order', _position)
			tmdb_id, tvdb_id, imdb_id, title, show_year = meta_get('tmdb_id'), meta_get('tvdb_id'), meta_get('imdb_id'), meta_get('title'), meta_get('year') or '2050'
			season_data = meta_get('season_data')
			watched_info = ws.watched_info_episode(meta_get('tmdb_id'), watched_db)
			if list_type_starts_with('next'):
				orig_season, orig_episode = ws.get_next(orig_season, orig_episode, watched_info, season_data, nextep_content)
				if not orig_season or not orig_episode: return
				if ws.get_watched_status_episode(watched_info, (orig_season, orig_episode)): return
			episodes_data = episodes_meta(orig_season, meta)
			if not episodes_data: return
			item = next((i for i in episodes_data if i['episode'] == orig_episode), None)
			if not item: return
			item_get = item.get
			season, episode, ep_name = item_get('season'), item_get('episode'), item_get('title')
			episode_date, premiered = adjust_premiered_date(item_get('premiered'), adjust_hours)
			episode_type = item_get('episode_type') or ''
			episode_id = item_get('episode_id') or None
			if not episode_date or current_date < episode_date:
				if list_type_starts_with('next_'):
					if not episode_date: return
					if not include_unaired: return
					if not date_difference(current_date, episode_date, 7): return
				unaired = True
			else: unaired = False
			orig_title, rootname, trailer, genre = meta_get('original_title'), meta_get('rootname'), str(meta_get('trailer')), meta_get('genre')
			mpaa, tvshow_plot, studio, show_status = meta_get('mpaa'), meta_get('plot'), meta_get('studio'), meta_get('status')
			cast = meta_get('short_cast', []) or meta_get('cast', []) or []
			if rpdb_api_key:
				try: show_poster = meta_get('rpdb_poster') % rpdb_api_key + rpdb_format
				except: show_poster = meta_get('poster') or poster_empty
			else: show_poster = meta_get('poster') or poster_empty
			show_fanart = meta_get('fanart') or fanart_empty
			show_clearlogo = meta_get('clearlogo') or ''
			show_landscape = meta_get('landscape') or ''
			try: year = premiered.split('-')[0]
			except: year = show_year or '2050'
			try:
				poster_path = next((i['poster_path'] for i in season_data if i['season_number'] == int(season)), None)
				season_poster = 'https://image.tmdb.org/t/p/w780%s' % poster_path if poster_path is not None else show_poster
			except: season_poster = show_poster
			str_season_zfill2, str_episode_zfill2 = str(season).zfill(2), str(episode).zfill(2)
			if display_format == 0: title_str = '%s: ' % title
			else: title_str = ''
			if display_format in (0, 1): seas_ep = '%sx%s - ' % (str_season_zfill2, str_episode_zfill2)
			else: seas_ep = ''
			if not list_type_starts_with('next_'):
				playcount = ws.get_watched_status_episode(watched_info, (season, episode))
				if playcount and hide_watched: return
			if list_type_starts_with('next_'):
				playcount = 0
				if include_airdate:
					if episode_date: display_premiered = '[%s] ' % make_day(current_date, episode_date)
					else: display_premiered = '[UNKNOWN] '
				else: display_premiered = ''
				if unwatched: highlight_start, highlight_end = '[COLOR darkgoldenrod]', '[/COLOR]'
				elif unaired: highlight_start, highlight_end = '[COLOR red]', '[/COLOR]'
				else: highlight_start, highlight_end = '', ''
				display = '%s%s%s%s%s%s' % (display_premiered, title_str, highlight_start, seas_ep, ep_name, highlight_end)
			elif list_type_compare == 'trakt_calendar':
				if episode_date: display_premiered = make_day(current_date, episode_date)
				else: display_premiered = 'UNKNOWN'
				display = '[%s] %s%s%s' % (display_premiered, title_str, seas_ep, ep_name)
			else: display = '%s%s%s' % (title_str, seas_ep, ep_name)
			if no_spoilers and not playcount: thumb, plot = show_landscape or show_fanart, tvshow_plot or '* Hidden to Prevent Spoilers *'
			else: thumb, plot = item_get('thumb', None) or show_landscape or show_fanart, item_get('plot') or tvshow_plot
			duration = item_get('duration')
			if not duration:
				duration = meta_get('duration')
				item['duration'] = duration
			bookmarks = ws.get_bookmarks_episode(tmdb_id, season, watched_db)
			progress = ws.get_progress_status_episode(bookmarks, episode)
			play_params = build_url({'mode': play_mode, 'media_type': 'episode', 'tmdb_id': tmdb_id, 'season': season, 'episode': episode, 'playcount': playcount,
									'episode_id': episode_id, playback_key: playback_key})
			extras_params = build_url({'mode': 'extras_menu_choice', 'tmdb_id': tmdb_id, 'media_type': 'episode', 'is_external': is_external})
			options_params = build_url({'mode': 'options_menu_choice', 'content': list_type, 'tmdb_id': tmdb_id, 'poster': show_poster, 'is_external': is_external})
			playback_options_params = build_url({'mode': 'playback_choice', 'media_type': 'episode', 'meta': tmdb_id, 'season': season, 'playcount': playcount,
											'episode': episode, 'episode_id': episode_id})
			cm_append(['extras', ('[B]Extras[/B]', 'RunPlugin(%s)' % extras_params)])
			cm_append(['options', ('[B]Options[/B]', 'RunPlugin(%s)' % options_params)])
			cm_append(['playback_options', ('[B]Play Options[/B]', 'RunPlugin(%s)' % \
						build_url({'mode': 'playback_choice', 'media_type': 'episode', 'meta': tmdb_id, 'season': season, 'episode': episode, 'episode_id': episode_id}))])
			settings.append_external_scraper_settings_cm(cm_append, build_url)
			cm_append(['browse_seasons', ('[B]Browse Seasons[/B]', window_command % build_url({'mode': 'build_season_list', 'tmdb_id': tmdb_id}))])
			cm_append(['browse_episodes', ('[B]Browse Episodes[/B]', window_command % build_url({'mode': 'build_episode_list', 'tmdb_id': tmdb_id, 'season': season}))])
			if not unaired:
				if playcount:
					cm_append(['mark_watched', ('[B]Mark Unwatched[/B]', 'RunPlugin(%s)' % build_url({'mode': 'watched_status.mark_episode', 'action': 'mark_as_unwatched',
												'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season, 'episode': episode,  'title': title}))])
				else: cm_append(['mark_watched', ('[B]Mark Watched[/B]', 'RunPlugin(%s)' % build_url({'mode': 'watched_status.mark_episode', 'action': 'mark_as_watched',
											'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id, 'season': season, 'episode': episode,  'title': title}))])
				if progress:
					cm_append(['mark_watched', ('[B]Clear Progress[/B]', 'RunPlugin(%s)' % \
								build_url({'mode': 'watched_status.erase_bookmark', 'media_type': 'episode', 'tmdb_id': tmdb_id,
											'season': season, 'episode': episode, 'refresh': 'true'}))])
				if unwatched_info:
					total_aired_eps = meta_get('total_aired_eps')
					total_unwatched = ws.get_watched_status_tvshow(ws.watched_info_tvshow(watched_db).get(str(tmdb_id), None), total_aired_eps)[2]
					if total_aired_eps != total_unwatched: set_properties({'watchedepisodes': '1', 'unwatchedepisodes': str(total_unwatched)})
			if list_type_starts_with('next_') and (season, episode) != (1, 1):
				cm_append(['unmark_previous_episode', ('[B]Unmark Previous Watched[/B]', 'RunPlugin(%s)' % \
								build_url({'mode': 'watched_status.unmark_previous_episode', 'action': 'mark_as_unwatched', 'tmdb_id': tmdb_id, 'tvdb_id': tvdb_id,
											'season': season, 'episode': episode, 'title': title, 'refresh': 'true'}))])
			if is_external:
				cm.extend([['refresh', ('[B]Refresh Widgets[/B]', 'RunPlugin(%s)' % build_url({'mode': 'refresh_widgets'}))],
						['reload', ('[B]Reload Widgets[/B]', 'RunPlugin(%s)' % build_url({'mode': 'kodi_refresh'}))]])
			if custom_cm_menu:
				try: cm = sorted([i for i in cm if i[0] in cm_sort_order], key=lambda k: cm_sort_order[k[0]])
				except: pass
			cm = [i[1] for i in cm]
			info_tag = listitem.getVideoInfoTag(True)
			info_tag.setMediaType('episode'), info_tag.setOriginalTitle(orig_title), info_tag.setTvShowTitle(title), info_tag.setTitle(display), info_tag.setGenres(genre)
			info_tag.setPlaycount(playcount), info_tag.setSeason(season), info_tag.setEpisode(episode), info_tag.setPlot(plot), info_tag.setFirstAired(premiered)
			info_tag.setDuration(duration), info_tag.setIMDBNumber(imdb_id), info_tag.setUniqueIDs({'imdb': imdb_id, 'tmdb': str(tmdb_id), 'tvdb': str(tvdb_id)})
			info_tag.setCountries(meta_get('country', [])), info_tag.setTrailer(trailer), info_tag.setTvShowStatus(show_status)
			info_tag.setStudios(studio), info_tag.setWriters(item_get('writer')), info_tag.setDirectors(item_get('director'))
			info_tag.setYear(int(year)), info_tag.setRating(item_get('rating')), info_tag.setVotes(item_get('votes')), info_tag.setMpaa(mpaa)
			full_cast = cast + item_get('guest_stars', [])
			info_tag.setCast([kodi_actor(name=item['name'], role=item['role'], thumbnail=item['thumbnail']) for item in full_cast])
			if progress and not unaired:
				info_tag.setResumePoint(ws.get_resume_seconds(progress, duration))
				set_properties({'WatchedProgress': progress})
			listitem.setLabel(display)
			listitem.addContextMenuItems(cm)
			listitem.setArt({'poster': show_poster, 'fanart': show_fanart, 'thumb': thumb, 'icon':thumb, 'clearlogo': show_clearlogo, 'landscape': show_landscape,
							'season.poster': season_poster, 'tvshow.poster': show_poster, 'tvshow.clearlogo': show_clearlogo})
			set_properties({
				'episode_type': episode_type, 'redlight.extras_params': extras_params, 'redlight.options_params': options_params,
				'redlight.playback_options_params': playback_options_params
				})
			item_list_append({'list_items': (play_params, listitem, False), 'first_aired': premiered, 'name': '%s - %sx%s' % (title, str_season_zfill2, str_episode_zfill2),
							'unaired': unaired, 'last_played': ep_data_get('last_played', resinsert), 'sort_order': _position, 'unwatched': ep_data_get('unwatched')})
		except: pass
	kodi_actor, make_listitem, build_url = kodi_utils.kodi_actor(), kodi_utils.make_listitem, kodi_utils.build_url
	poster_empty, fanart_empty = kodi_utils.get_icon('box_office'), kodi_utils.addon_fanart()
	handle, is_external = int(sys.argv[1]), kodi_utils.external()
	is_anime_list = 'is_anime_list' in params
	if not is_anime_list and settings.include_anime_tvshow(): is_anime_list = None
	item_list, airing_today, unwatched, return_results = [], [], [], False
	resinsert = ''
	item_list_append = item_list.append
	window_command = 'ActivateWindow(Videos,%s,return)' if is_external else 'Container.Update(%s)'
	no_spoilers = settings.avoid_episode_spoilers()
	watched_indicators = settings.watched_indicators()
	if list_type == 'episode.trakt': display_format = settings.calendar_display_format(is_external)
	else: display_format = settings.single_ep_display_format(is_external)
	current_date, current_time, adjust_hours = get_datetime(), get_current_timestamp(), settings.date_offset()
	unwatched_info = settings.single_ep_unwatched_episodes()
	hide_watched = is_external and settings.widget_hide_watched() and list_type != 'episode.recently_watched'
	api_key, mpaa_region_value = settings.tmdb_api_key(), settings.mpaa_region()
	cm_sort_order, ignore_articles = settings.cm_sort_order(), settings.ignore_articles()
	custom_cm_menu = cm_sort_order != settings.cm_default_order()
	rpdb_info = settings.rpdb_info('tvshow')
	rpdb_api_key, rpdb_format = rpdb_info['rpdb_api_key'], rpdb_info['rpdb_format']
	playback_key = settings.playback_key()
	play_mode = 'playback.%s' % playback_key
	watched_db = ws.get_database(watched_indicators)
	if list_type == 'episode.next':
		include_unwatched, include_unaired, nextep_content = settings.nextep_include_unwatched(), settings.nextep_include_unaired(), settings.nextep_method()
		sort_key, sort_direction = settings.nextep_sort_key(), settings.nextep_sort_direction()
		include_airdate = settings.nextep_include_airdate()
		data = ws.get_next_episodes(nextep_content)
		if settings.nextep_limit_history(): data = data[:settings.nextep_limit()]
		hidden_list = ws.get_hidden_progress_items(watched_indicators)
		if hidden_list: data = [i for i in data if not i['media_ids']['tmdb'] in hidden_list]
		if watched_indicators in (1, 2, 3):
			resformat, resinsert = '%Y-%m-%dT%H:%M:%S.%fZ', '2000-01-01T00:00:00.000Z'
			list_type = {1: 'episode.next_trakt', 2: 'episode.next_simkl', 3: 'episode.next_mdblist'}[watched_indicators]
		else: resformat, resinsert, list_type = '%Y-%m-%d %H:%M:%S', '2000-01-01 00:00:00', 'episode.next_redlight'
		if include_unwatched != 0:
			if include_unwatched in (1, 3):
				from apis.trakt_api import trakt_watchlist
				try:
					watchlist = trakt_watchlist('tvshow', '')
					unwatched.extend([{'media_ids': i['media_ids'], 'season': 1, 'episode': 0, 'unwatched': True, 'title': i['title']} for i in watchlist])
				except: pass
			if include_unwatched in (2, 3):
				from caches.favorites_cache import favorites_cache
				try:
					favorites = favorites_cache.get_favorites('tvshow')
					unwatched.extend([{'media_ids': {'tmdb': int(i['tmdb_id'])}, 'season': 1, 'episode': 0, 'unwatched': True, 'title': i['title']} \
									for i in favorites if not int(i['tmdb_id']) in [x['media_ids']['tmdb'] for x in data]])
				except: pass
			data += unwatched
	elif list_type == 'episode.progress': data = ws.get_in_progress_episodes()
	elif list_type == 'episode.recently_watched': data = ws.get_recently_watched('episode', short_list=True)
	elif list_type == 'episode.trakt':
		from apis.trakt_api import trakt_get_my_calendar
		recently_aired = params.get('recently_aired', None)
		data = trakt_get_my_calendar(recently_aired, get_datetime())
		hidden_list = ws.get_hidden_progress_items(watched_indicators)
		if hidden_list: data = [i for i in data if not i['media_ids']['tmdb'] in hidden_list]
		list_type = 'episode.trakt_recently_aired' if recently_aired else 'episode.trakt_calendar'
		if settings.flatten_episodes():
			try:
				duplicates = set()
				data.sort(key=lambda i: i['sort_title'])
				data = [i for i in data if not ((i['media_ids']['tmdb'], i['first_aired'].split('T')[0]) in duplicates
						or duplicates.add((i['media_ids']['tmdb'], i['first_aired'].split('T')[0])))]
			except: pass
		else:
			try: data = sorted(data, key=lambda i: (i['sort_title'], i.get('first_aired', '2100-12-31')), reverse=True)
			except: data = sorted(data, key=lambda i: i['sort_title'], reverse=True)
	else: data, return_results = sorted(params, key=lambda i: i['custom_order']), True
	list_type_compare = list_type.split('episode.')[1]
	list_type_starts_with = list_type_compare.startswith
	threads = TaskPool().tasks_enumerate(_process, data, min(len(data), settings.max_threads()))
	[i.join() for i in threads]
	if return_results: return [(i['list_items'], i['sort_order']) for i in item_list]
	if list_type_starts_with('next_'):
		def func(function):
			if sort_key == 'name': return title_key(function, ignore_articles)
			elif sort_key == 'last_played': return jsondate_to_datetime(function, resformat)
			else: return function
		if settings.nextep_airing_today():
			airing_today = sorted([i for i in item_list if date_difference(current_date, jsondate_to_datetime(i.get('first_aired', '2100-12-31'), '%Y-%m-%d').date(), 0)],
									key=lambda i: func(i[sort_key]), reverse=sort_direction)
			item_list = [i for i in item_list if not i in airing_today]
		else: airing_today = []
		if sort_key == 'last_played':
			unwatched = sorted([i for i in item_list if i['unwatched']], key=lambda i: title_key(i['name'], ignore_articles))
			item_list = sorted([i for i in item_list if not i['unwatched']], key=lambda i: func(i[sort_key]), reverse=sort_direction) + unwatched
		else: item_list = sorted(item_list, key=lambda i: func(i[sort_key]), reverse=sort_direction)
		item_list = airing_today + item_list
	else:
		item_list.sort(key=lambda i: i['sort_order'])
		if list_type_compare in ('trakt_calendar', 'trakt_recently_aired'):
			if list_type_compare == 'trakt_calendar': reverse = settings.calendar_sort_order() == 0
			else: reverse = True
			try: item_list = sorted(item_list, key=lambda i: i.get('first_aired', '2100-12-31'), reverse=reverse)
			except:
				item_list = [i for i in item_list if i.get('first_aired') not in (None, 'None', '')]
				item_list = sorted(item_list, key=lambda i: i.get('first_aired'), reverse=reverse)
			if list_type_compare == 'trakt_calendar':
				airing_today = sorted([i for i in item_list if date_difference(current_date, jsondate_to_datetime(i.get('first_aired', '2100-12-31'), '%Y-%m-%d').date(), 0)],
										key=lambda i: i['first_aired'])
				item_list = [i for i in item_list if not i in airing_today]
				item_list = airing_today + item_list
	kodi_utils.add_items(handle, [i['list_items'] for i in item_list])
	kodi_utils.set_content(handle, 'episodes')
	kodi_utils.set_category(handle, _get_category_name())
	kodi_utils.end_directory(handle, cacheToDisc=False)
	kodi_utils.set_view_mode('view.episodes_single', 'episodes', is_external, fallback_view_types=('view.episodes',))
