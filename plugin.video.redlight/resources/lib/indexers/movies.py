# -*- coding: utf-8 -*-
import sys
import json
from modules.metadata import movie_meta, movieset_meta
from modules.utils import get_datetime, get_current_timestamp, paginate_list, jsondate_to_datetime, TaskPool, manual_function_import
from modules import kodi_utils, settings, watched_status

class Movies:
	main = ('tmdb_movies_popular', 'tmdb_movies_popular_today','tmdb_movies_blockbusters','tmdb_movies_in_theaters', 'tmdb_movies_upcoming',
	'tmdb_movies_latest_releases', 'tmdb_movies_premieres', 'tmdb_movies_oscar_winners')
	special = ('tmdb_movies_languages', 'tmdb_movies_providers', 'tmdb_movies_year', 'tmdb_movies_decade', 'tmdb_movies_certifications', 'tmdb_movies_recommendations',
	'tmdb_movies_genres', 'tmdb_movies_companies', 'tmdb_movies_search', 'tmdb_movie_keyword_results', 'tmdb_movie_keyword_results_direct', 'ai_similar')
	personal = {'in_progress_movies': ('modules.watched_status', 'get_in_progress_movies'), 'favorites_movies': ('modules.favorites', 'get_favorites'),
	'watched_movies': ('modules.watched_status', 'get_watched_items'), 'recent_watched_movies': ('modules.watched_status', 'get_recently_watched')}
	most_watched = ('movies_most_watched', 'trakt_movies_most_watched')
	trakt_main = ('trakt_movies_trending', 'trakt_movies_trending_recent', 'trakt_movies_most_favorited', 'trakt_movies_top10_boxoffice')
	trakt_personal = ('trakt_collection', 'trakt_watchlist', 'trakt_collection_lists', 'trakt_watchlist_lists', 'trakt_favorites')
	simkl_personal = ('simkl_plantowatch', 'simkl_completed', 'simkl_watching', 'simkl_hold', 'simkl_dropped')
	punchplay_personal = ('punchplay_watchlist', 'punchplay_collection', 'punchplay_favorites', 'punchplay_plantowatch',
		'punchplay_watching', 'punchplay_hold', 'punchplay_completed', 'punchplay_dropped')
	mdblist_personal = ('mdblist_watchlist', 'mdblist_collection')

	def __init__(self, params):
		self.params = params
		self.params_get = self.params.get
		self.category_name = self.params_get('category_name', None) or self.params_get('name', None) or 'Movies'
		self.id_type, self.list, self.action = self.params_get('id_type', 'tmdb_id'), self.params_get('list', []), self.params_get('action', None)
		self.tmdb_api_key = settings.tmdb_api_key()
		self.items, self.new_page, self.total_pages, self.is_external = [], {}, None, kodi_utils.external()
		if self.is_external:
			self.widget_hide_next_page = settings.widget_hide_next_page()
			self.widget_hide_watched = self.action not in ('watched_movies', 'recent_watched_movies', 'in_progress_movies') and settings.widget_hide_watched()
		else: self.widget_hide_next_page, self.widget_hide_watched = False, False
		self.playback_key = settings.playback_key()
		self.play_mode = 'playback.%s' % settings.playback_key()
		self.custom_order = self.params_get('custom_order', 'false') == 'true'
		self.paginate_start = int(self.params_get('paginate_start', '0'))
		self.append = self.items.append
		self.movieset_list_active = False

	def fetch_list(self):
		handle = int(sys.argv[1])
		try:
			try: page_no = int(self.params_get('new_page', '1'))
			except: page_no = self.params_get('new_page')
			if self.action in self.personal: var_module, import_function = self.personal[self.action]
			elif self.action in self.most_watched:
				from modules.most_watched import normalize_most_watched_action
				var_module, import_function = 'modules.most_watched', normalize_most_watched_action(self.action)
			else: var_module, import_function = 'apis.%s_api' % self.action.split('_')[0], self.action
			try: function = manual_function_import(var_module, import_function)
			except: pass
			if page_no == 1 and not self.is_external and self.action != 'mdblist_user_list':
				kodi_utils.set_browse_exit_params('movie', self.action)
			if self.action in self.main:
				data = function(page_no)
				results = data['results']
				self.list = [i['id'] for i in results]
				if data['total_pages'] > page_no: self.new_page = {'new_page': str(data['page'] + 1)}
			elif self.action in self.special:
				key_id = self.params_get('key_id') or self.params_get('query')
				if not key_id:
					kodi_utils.end_directory(handle)
					return
				data = function(key_id, page_no)
				results = data['results']
				self.list = [i['id'] for i in results]
				if data['total_pages'] > page_no: self.new_page = {'new_page': str(data['page'] + 1), 'key_id': key_id}
			elif self.action in self.personal:
				data = function('movie', page_no)
				data, total_pages = self.paginate_list(data, page_no)
				self.list = [i['media_id'] for i in data]
				if total_pages > 2: self.total_pages = total_pages
				if total_pages > page_no: self.new_page = {'new_page': str(page_no + 1), 'paginate_start': self.paginate_start}
			elif self.action in self.most_watched:
				from modules.most_watched import most_watched_category_name, simkl_most_watched_has_next, most_watched_provider, normalize_most_watched_action
				category_name = most_watched_category_name(self.action)
				if category_name: self.category_name = category_name
				self.id_type = 'trakt_dict'
				data = function(page_no) or []
				try: self.list = [i['movie']['ids'] for i in data]
				except: self.list = [i['ids'] for i in data]
				if most_watched_provider() == 'simkl' and data and simkl_most_watched_has_next(normalize_most_watched_action(self.action), page_no):
					self.new_page = {'new_page': str(page_no + 1)}
				elif data: self.new_page = {'new_page': str(page_no + 1)}
			elif self.action in self.trakt_main:
				self.id_type = 'trakt_dict'
				data = function(page_no)
				try: self.list = [i['movie']['ids'] for i in data]
				except: self.list = [i['ids'] for i in data]
				if self.action not in ('trakt_movies_top10_boxoffice', 'trakt_recommendations'): self.new_page = {'new_page': str(page_no + 1)}
			elif self.action in self.trakt_personal:
				self.id_type = 'trakt_dict'
				data = function('movies', page_no)
				if self.action in ('trakt_collection_lists', 'trakt_watchlist_lists', 'trakt_favorites'): total_pages = 1
				else: data, total_pages = self.paginate_list(data, page_no)
				self.list = [i['media_ids'] for i in data]
				if total_pages > 2: self.total_pages = total_pages
				try:
					if total_pages > page_no: self.new_page = {'new_page': str(page_no + 1), 'paginate_start': self.paginate_start}
				except: pass
			elif self.action in self.simkl_personal:
				self.id_type = 'trakt_dict'
				data = function('movies', page_no)
				data, total_pages = self.paginate_list(data, page_no)
				self.list = [i['media_ids'] for i in data]
				if total_pages > 2: self.total_pages = total_pages
				try:
					if total_pages > page_no: self.new_page = {'new_page': str(page_no + 1), 'paginate_start': self.paginate_start}
				except: pass
			elif self.action in self.punchplay_personal:
				self.id_type = 'trakt_dict'
				data = function('movies', page_no)
				data, total_pages = self.paginate_list(data, page_no)
				self.list = [i['media_ids'] for i in data]
				if total_pages > 2: self.total_pages = total_pages
				try:
					if total_pages > page_no: self.new_page = {'new_page': str(page_no + 1), 'paginate_start': self.paginate_start}
				except: pass
			elif self.action == 'punchplay_user_list':
				self.id_type = 'trakt_dict'
				from apis.punchplay_api import punchplay_list_items
				data = punchplay_list_items(self.params_get('list_id'), 'movies')
				data, total_pages = self.paginate_list(data, page_no)
				self.list = [i['media_ids'] for i in data]
				try:
					if total_pages > page_no: self.new_page = {'new_page': str(page_no + 1), 'paginate_start': self.paginate_start}
				except: pass
			elif self.action in self.mdblist_personal:
				data = function('movies', page_no)
				if isinstance(data, tuple): data, total_pages = data
				else: data, total_pages = data, 1
				if self.action == 'mdblist_watchlist':
					self.id_type = 'tmdb_id'
					self.list = []
					for i in data:
						if not isinstance(i, dict): continue
						tmdb_id = i.get('id') or i.get('tmdb') or (i.get('ids') or {}).get('tmdb')
						if tmdb_id:
							try: self.list.append(int(tmdb_id))
							except: pass
				else:
					self.id_type = 'trakt_dict'
					self.list = [{'tmdb': i['id'], 'imdb': i.get('imdb_id') or i.get('imdb') or '', 'tvdb': i.get('tvdb_id') or ''} for i in data if i.get('id')]
				if total_pages > page_no: self.new_page = {'new_page': str(page_no + 1), 'paginate_start': self.paginate_start}
			elif self.action == 'mdblist_user_list':
				self.list = self.params_get('list', [])
			elif self.action == 'trakt_recommendations':
				self.id_type = 'trakt_dict'
				data = function('movies')
				data, total_pages = self.paginate_list(data, page_no)
				self.list = [i['ids'] for i in data]
				if total_pages > 2: self.total_pages = total_pages
				try:
					if total_pages > page_no: self.new_page = {'new_page': str(page_no + 1), 'paginate_start': self.paginate_start}
				except: pass
			elif self.action == 'tmdb_movies_discover':
				url = self.params_get('url')
				data = function(url, page_no)
				results = data['results']
				self.list = [i['id'] for i in results]
				if data['total_pages'] > page_no: self.new_page = {'url': url, 'new_page': str(data['page'] + 1)}
			elif self.action  == 'tmdb_movies_sets':
				self.movieset_list_active = True
				data = sorted(movieset_meta(self.params_get('key_id'), self.tmdb_api_key)['parts'], key=lambda k: k['release_date'] or '2050')
				self.list = [i['id'] for i in data]
			elif self.action == 'trakt_movies_related':
				self.id_type = 'trakt_dict'
				key_id = self.params_get('key_id')
				if not key_id.startswith('tt'): key_id = movie_meta('tmdb_id', key_id, self.tmdb_api_key, settings.mpaa_region(), get_datetime())['imdb_id']
				data = function(key_id)
				self.list = [i['ids'] for i in data]
			elif self.action == 'imdb_more_like_this':
				from apis.imdb_api import imdb_more_like_this
				self.id_type = 'imdb_id'
				key_id = self.params_get('key_id')
				if self.params_get('get_imdb'):
					key_id = movie_meta('tmdb_id', key_id, self.tmdb_api_key, settings.mpaa_region(), get_datetime(), get_current_timestamp())['imdb_id']
				self.list = imdb_more_like_this(key_id)
			items = self.worker()
			if self.action == 'mdblist_watchlist' and self.list and not items:
				kodi_utils.logger('MDBList Watchlist', 'Failed to build list items from %s ids' % len(self.list))
			kodi_utils.add_items(handle, items)
			if self.total_pages and self.total_pages > 2 and settings.jump_to_enabled() and not self.is_external:
				url_params = json.dumps({**self.new_page, **{'mode': 'build_movie_list', 'action': self.action, 'category_name': self.category_name}})
				kodi_utils.add_dir(handle, {'mode': 'navigate_to_page_choice', 'current_page': page_no, 'total_pages': self.total_pages, 'url_params': url_params},
											'Jump To...', 'item_jump', kodi_utils.get_icon('item_jump_landscape'), isFolder=False)
			if self.new_page and not self.widget_hide_next_page:
				self.new_page.update({'mode': 'build_movie_list', 'action': self.action, 'category_name': self.category_name})
				kodi_utils.add_dir(handle, self.new_page, 'Next Page (%s) >>' % self.new_page['new_page'], 'nextpage', kodi_utils.get_icon('nextpage_landscape'))
		except Exception as e:
			if self.action in self.mdblist_personal or self.action == 'mdblist_user_list':
				kodi_utils.logger('MDBList List Error', '%s: %s' % (self.action, e))
		kodi_utils.set_content(handle, 'movies')
		kodi_utils.set_category(handle, self.category_name)
		kodi_utils.end_directory(handle, cacheToDisc=False if self.is_external or self.action in self.mdblist_personal else True)
		if not self.is_external:
			if self.params_get('refreshed') == 'true': kodi_utils.sleep(1000)
			kodi_utils.set_view_mode('view.movies', 'movies', self.is_external)
		
	def build_movie_content(self, _position, _id, dbcon=None):
		try:
			meta = movie_meta(self.id_type, _id, self.tmdb_api_key, self.mpaa_region, self.current_date, self.current_time, dbcon=dbcon)
			if not meta or 'blank_entry' in meta: return
			listitem = self.make_listitem()
			cm = []
			cm_append = cm.append
			set_properties = listitem.setProperties
			clearprog_params, watched_status_params = '', ''
			meta_get = meta.get
			premiered = meta_get('premiered')
			title, year = meta_get('title'), meta_get('year') or '2050'
			tmdb_id, imdb_id = meta_get('tmdb_id'), meta_get('imdb_id')
			str_tmdb_id = str(tmdb_id)
			if self.rpdb_api_key:
				try: poster = meta_get('rpdb_poster') % self.rpdb_api_key + self.rpdb_format
				except: poster = meta_get('poster') or self.poster_empty
			else: poster = meta_get('poster') or self.poster_empty
			fanart = meta_get('fanart') or self.fanart_empty
			clearlogo, landscape = meta_get('clearlogo') or '', meta_get('landscape') or ''
			thumb = poster or landscape or fanart
			movieset_id, movieset_name = meta_get('extra_info').get('collection_id', None), meta_get('extra_info').get('collection_name', None)
			first_airdate = jsondate_to_datetime(premiered, '%Y-%m-%d', True)
			duration = meta_get('duration')
			if not first_airdate or self.current_date < first_airdate: unaired = True
			else: unaired = False
			if settings.hide_unaired_watchlist_item(self.action, unaired): return
			progress = watched_status.get_progress_status_movie(self.bookmarks, str_tmdb_id)
			playcount = watched_status.get_watched_status_movie(self.watched_info, str_tmdb_id)
			play_params = self.build_url({'mode': self.play_mode, 'media_type': 'movie', 'tmdb_id': tmdb_id, self.playback_key: self.playback_key})
			extras_params = self.build_url({'mode': 'extras_menu_choice', 'media_type': 'movie', 'tmdb_id': tmdb_id, 'is_external': self.is_external})
			options_params = self.build_url({'mode': 'options_menu_choice', 'content': 'movie', 'tmdb_id': tmdb_id, 'poster': poster, 'is_external': self.is_external})
			playback_options_params = self.build_url({'mode': 'playback_choice', 'media_type': 'movie', 'meta': tmdb_id})
			browse_recommended_params = self.build_url({'mode': 'build_movie_list', 'action': 'tmdb_movies_recommendations', 'is_external': self.is_external,
										'key_id': tmdb_id, 'name': 'Recommended based on %s' % title})
			browse_related_params = self.build_url({'mode': 'build_movie_list', 'action': 'trakt_movies_related', 'key_id': imdb_id, 'is_external': self.is_external,
										'name': 'Related to %s' % title})
			browse_more_like_this_params = self.build_url({'mode': 'build_movie_list', 'action': 'imdb_more_like_this', 'key_id': imdb_id, 'is_external': self.is_external,
										'name': 'More Like This based on %s' % title})
			browse_similar_params = self.build_url({'mode': 'build_movie_list', 'action': 'ai_similar', 'is_external': self.is_external,
										'key_id': 'movie|%s' % tmdb_id, 'name': 'Similar based on %s' % title})
			browse_in_trakt_list_params, trakt_manager_params = '', ''
			if settings.trakt_user_active():
				browse_in_trakt_list_params = self.build_url({'mode': 'trakt.list.in_trakt_lists', 'media_type': 'movie', 'imdb_id': imdb_id, 'is_external': self.is_external,
										'category_name': '%s In Trakt Lists' % title})
				trakt_manager_params = self.build_url({'mode': 'trakt_manager_choice', 'tmdb_id': tmdb_id, 'imdb_id': imdb_id, 'tvdb_id': 'None', 'media_type': 'movie',
													'title': title, 'icon': poster})
			simkl_manager_params = ''
			if settings.simkl_user_active():
				simkl_manager_params = self.build_url({'mode': 'simkl_manager_choice', 'tmdb_id': tmdb_id, 'imdb_id': imdb_id, 'tvdb_id': 'None', 'media_type': 'movie',
														'title': title, 'icon': poster})
			punchplay_manager_params = ''
			if settings.punchplay_user_active():
				punchplay_manager_params = self.build_url({'mode': 'punchplay_manager_choice', 'tmdb_id': tmdb_id, 'imdb_id': imdb_id, 'tvdb_id': 'None', 'media_type': 'movie',
														'title': title, 'icon': poster})
			mdblist_manager_params = ''
			if settings.mdblist_user_active():
				mdblist_manager_params = self.build_url({'mode': 'mdblist_manager_choice', 'tmdb_id': tmdb_id, 'imdb_id': imdb_id, 'tvdb_id': 'None', 'media_type': 'movie',
														'title': title, 'icon': poster})
			personal_manager_params = self.build_url({'mode': 'personallists_manager_choice', 'list_type': 'movie', 'tmdb_id': tmdb_id, 'title': title,
										'premiered': premiered, 'current_time': self.current_time, 'icon': poster})
			tmdb_manager_params = ''
			if settings.tmdblist_user_active():
				tmdb_manager_params = self.build_url({'mode': 'tmdblists_manager_choice', 'media_type': 'movie', 'tmdb_id': tmdb_id, 'icon': poster})
			favorites_manager_params = self.build_url({'mode': 'favorites_manager_choice', 'media_type': 'movie', 'tmdb_id': tmdb_id, 'title': title})
			belongs_to_movieset = 'true' if all([movieset_id, movieset_name]) else 'false'
			skip_special = self.skip_inprogress and progress
			item_open_extras = self.open_extras and not skip_special
			item_open_movieset = self.open_movieset and not skip_special
			movieset_active = item_open_movieset and belongs_to_movieset == 'true'
			if item_open_extras or movieset_active:
				cm_append(['extras', ('[B]Play[/B]', 'RunPlugin(%s)' % play_params)])
			if not item_open_extras or movieset_active:
				cm_append(['extras', ('[B]Extras[/B]', 'RunPlugin(%s)' % extras_params)])
			if movieset_active:
				url_params = self.build_url({'mode': 'open_movieset_choice', 'key_id': movieset_id, 'name': movieset_name, 'is_external': self.is_external})
			elif item_open_extras:
				url_params = extras_params
			else:
				url_params = play_params
			cm_append(['options', ('[B]Options[/B]', 'RunPlugin(%s)' % options_params)])
			cm_append(['playback_options', ('[B]Play Options[/B]', 'RunPlugin(%s)' % playback_options_params)])
			settings.append_source_shortcut_context_menus(cm_append, self.build_url, self.cm_sort_order, 'movie', tmdb_id)
			settings.append_external_scraper_settings_cm(cm_append, self.build_url)
			if belongs_to_movieset == 'true' and not self.movieset_list_active and not item_open_movieset:
				browse_movie_set_params = self.build_url({'mode': 'build_movie_list', 'action': 'tmdb_movies_sets', 'key_id': movieset_id,
										'name': movieset_name, 'is_external': self.is_external})
				cm_append(['browse_movie_set', ('[B]Browse Movie Set[/B]', self.window_command % browse_movie_set_params)])
			else: browse_movie_set_params = ''
			cm_append(['recommended', ('[B]Browse Recommended[/B]', self.window_command % browse_recommended_params)])
			cm_append(['related', ('[B]Browse Related[/B]', self.window_command % browse_related_params)])
			cm_append(['more_like_this', ('[B]Browse More Like This[/B]', self.window_command % browse_more_like_this_params)])
			if self.ai_model_active: cm_append(['similar', ('[B]Browse Similar[/B]', self.window_command % browse_similar_params)])
			if browse_in_trakt_list_params: cm_append(['in_trakt_list', ('[B]In Trakt Lists[/B]', self.window_command % browse_in_trakt_list_params)])
			if mdblist_manager_params: cm_append(['mdblist_manager', ('[B]MDBList Manager[/B]', 'RunPlugin(%s)' % mdblist_manager_params)])
			if punchplay_manager_params: cm_append(['punchplay_manager', ('[B]PunchPlay Manager[/B]', 'RunPlugin(%s)' % punchplay_manager_params)])
			if simkl_manager_params: cm_append(['simkl_manager', ('[B]Simkl Lists Manager[/B]', 'RunPlugin(%s)' % simkl_manager_params)])
			if tmdb_manager_params: cm_append(['tmdb_manager', ('[B]TMDb Lists Manager[/B]', 'RunPlugin(%s)' % tmdb_manager_params)])
			if trakt_manager_params: cm_append(['trakt_manager', ('[B]Trakt Lists Manager[/B]', 'RunPlugin(%s)' % trakt_manager_params)])
			settings.append_list_shortcut_context_menus(cm_append, self.build_url, self.cm_sort_order, 'movie', tmdb_id, imdb_id, 'None', title, poster)
			cm_append(['personal_manager', ('[B]Personal Lists Manager[/B]', 'RunPlugin(%s)' % personal_manager_params)])
			cm_append(['favorites_manager', ('[B]Favorites Manager[/B]', 'RunPlugin(%s)' % favorites_manager_params)])
			if playcount:
				if self.widget_hide_watched: return
				cm_append(['mark_watched', ('[B]Mark Unwatched[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'watched_status.mark_movie', 'action': 'mark_as_unwatched',
											'tmdb_id': tmdb_id, 'title': title}))])
			elif not unaired:
				cm_append(['mark_watched', ('[B]Mark Watched[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'watched_status.mark_movie', 'action': 'mark_as_watched',
											'tmdb_id': tmdb_id, 'title': title}))])
			if progress:
				cm_append(['mark_watched', ('[B]Clear Progress[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'watched_status.erase_bookmark', 'media_type': 'movie',
											'tmdb_id': tmdb_id, 'refresh': 'true'}))])
			if not self.is_external: cm_append(['exit', ('[B]Exit Movie List[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'navigator.exit_media_menu'}))])
			if self.is_external:
				cm.extend([['refresh', ('[B]Refresh Widgets[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'refresh_widgets'}))],
						['reload', ('[B]Reload Widgets[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'kodi_refresh'}))]])
			cm = self.context_menu(cm)
			info_tag = listitem.getVideoInfoTag(True)
			info_tag.setMediaType('movie'), info_tag.setTitle(title), info_tag.setOriginalTitle(meta_get('original_title')), info_tag.setGenres(meta_get('genre'))
			info_tag.setDuration(duration), info_tag.setPlaycount(playcount), info_tag.setPlot(meta_get('plot'))
			info_tag.setUniqueIDs({'imdb': imdb_id, 'tmdb': str_tmdb_id}), info_tag.setIMDBNumber(imdb_id), info_tag.setPremiered(premiered)
			info_tag.setYear(int(year)), info_tag.setRating(meta_get('rating')), info_tag.setVotes(meta_get('votes')), info_tag.setMpaa(meta_get('mpaa'))
			info_tag.setCountries(meta_get('country')), info_tag.setTrailer(meta_get('trailer'))
			info_tag.setTagLine(meta_get('tagline')), info_tag.setStudios(meta_get('studio'))
			info_tag.setWriters(meta_get('writer')), info_tag.setDirectors(meta_get('director'))
			cast = meta_get('short_cast', []) or meta_get('cast', []) or []
			info_tag.setCast([self.kodi_actor(name=item['name'], role=item['role'], thumbnail=item['thumbnail']) for item in cast])
			watched_status.clear_listitem_kodi_resume(info_tag)
			try: listitem.setContentLookup(False)
			except: pass
			if progress:
				watched_status.apply_listitem_progress(info_tag, set_properties, progress, duration, self.is_external)
			listitem.setLabel(title)
			listitem.addContextMenuItems(cm)
			listitem.setArt({'poster': poster, 'fanart': fanart, 'icon': poster, 'clearlogo': clearlogo, 'landscape': landscape, 'thumb': thumb})
			set_properties({
				'belongs_to_collection': belongs_to_movieset,
				'redlight.extras_params': extras_params,
				'redlight.options_params': options_params,
				'redlight.playback_options_params': playback_options_params,
				'redlight.browse_movie_set_params': browse_movie_set_params,
				'redlight.browse_recommended_params': browse_recommended_params,
				'redlight.browse_related_params': browse_related_params,
				'redlight.browse_more_like_this_params': browse_more_like_this_params,
				'redlight.browse_similar_params': browse_similar_params,
				'redlight.browse_in_trakt_list_params': browse_in_trakt_list_params,
				'redlight.trakt_manager_params': trakt_manager_params,
				'redlight.simkl_manager_params': simkl_manager_params,
				'redlight.punchplay_manager_params': punchplay_manager_params,
				'redlight.mdblist_manager_params': mdblist_manager_params,
				'redlight.personal_manager_params': personal_manager_params,
				'redlight.tmdb_manager_params': tmdb_manager_params,
				'redlight.favorites_manager_params': favorites_manager_params
				})
			self.append(((url_params, listitem, False), _position))
		except: pass

	def worker(self):
		self.kodi_actor, self.make_listitem, self.build_url = kodi_utils.kodi_actor(), kodi_utils.make_listitem, kodi_utils.build_url
		self.poster_empty, self.fanart_empty = kodi_utils.get_icon('box_office'), kodi_utils.addon_fanart()
		self.current_date, self.current_time, self.watched_indicators = get_datetime(), get_current_timestamp(), settings.watched_indicators()
		self.cm_sort_order = settings.cm_sort_order()
		self.custom_cm_menu = self.cm_sort_order != settings.cm_default_order()
		self.mpaa_region = settings.mpaa_region()
		self.ai_model_active = settings.ai_model_active()
		rpdb_info = settings.rpdb_info('movie')
		self.rpdb_api_key, self.rpdb_format = rpdb_info['rpdb_api_key'], rpdb_info['rpdb_format']
		watched_db = watched_status.get_database(self.watched_indicators)
		self.watched_info, self.bookmarks = watched_status.watched_info_movie(watched_db), watched_status.get_bookmarks_movie(watched_db)
		self.window_command = 'ActivateWindow(Videos,%s,return)' if self.is_external else 'Container.Update(%s)'
		open_action = settings.media_open_action('movie')
		self.open_movieset = open_action in (2, 3) and not self.movieset_list_active
		self.open_extras = open_action in (1, 3)
		self.skip_inprogress = settings.media_open_action_skip_inprogress_movie()
		if self.custom_order:
			threads = TaskPool().tasks(self.build_movie_content, self.list, min(len(self.list), settings.max_threads()), 'metacache_db')
			[i.join() for i in threads]
		else:
			threads = TaskPool().tasks_enumerate(self.build_movie_content, self.list, min(len(self.list), settings.max_threads()), 'metacache_db')
			[i.join() for i in threads]
			self.items.sort(key=lambda k: k[1])
			self.items = [i[0] for i in self.items]
		return self.items

	def context_menu(self, context_menu_items):
		if self.custom_cm_menu:
			try: context_menu_items = sorted([i for i in context_menu_items if i[0] in self.cm_sort_order], key=lambda k: self.cm_sort_order[k[0]])
			except: pass
		return [i[1] for i in context_menu_items]

	def paginate_list(self, data, page_no):
		if settings.paginate(self.is_external):
			limit = settings.page_limit(self.is_external)
			data, total_pages = paginate_list(data, page_no, limit, self.paginate_start)
			if self.is_external: self.paginate_start = limit
		else: total_pages = 1
		return data, total_pages
