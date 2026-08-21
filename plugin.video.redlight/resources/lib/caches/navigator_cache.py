# -*- coding: utf-8 -*-
from caches.base_cache import connect_database
from modules.kodi_utils import get_property, set_property, clear_property
# from modules.kodi_utils import logger

class NavigatorCache:
	root_list = [
	{'name': 'Movies', 'mode': 'navigator.main', 'action': 'MovieList', 'iconImage': 'movies'},
	{'name': 'TV Shows', 'mode': 'navigator.main', 'action': 'TVShowList', 'iconImage': 'tv'},
	{'name': 'Anime', 'mode': 'navigator.main', 'action': 'AnimeList', 'iconImage': 'anime'},
	{'name': 'People', 'mode': 'navigator.people', 'iconImage': 'empty_person'},
	{'name': 'Search', 'mode': 'navigator.search', 'iconImage': 'search'},
	{'name': 'Discover', 'mode': 'navigator.discover', 'iconImage': 'discover'},
	{'name': 'Random Lists', 'mode': 'navigator.random_lists', 'iconImage': 'random'},
	{'name': 'My Lists', 'mode': 'navigator.my_lists', 'iconImage': 'lists'},
	{'name': 'My Services', 'mode': 'navigator.premium', 'iconImage': 'premium'},
	{'name': 'Favorites', 'mode': 'navigator.favorites', 'iconImage': 'favorites'},
	{'name': 'Downloads', 'mode': 'navigator.downloads', 'iconImage': 'downloads'},
	{'name': 'Tools', 'mode': 'navigator.tools', 'iconImage': 'settings2'}
				]
	movie_list = [
	{'name': 'Trending', 'mode': 'build_movie_list', 'action': 'trakt_movies_trending', 'random_support': 'true', 'iconImage': 'trending'},
	{'name': 'Trending Recent', 'mode': 'build_movie_list', 'action': 'trakt_movies_trending_recent', 'random_support': 'true', 'iconImage': 'trending_recent'},
	{'name': 'Popular', 'mode': 'build_movie_list', 'action': 'tmdb_movies_popular', 'random_support': 'true', 'iconImage': 'popular'},
	{'name': 'Popular Today', 'mode': 'build_movie_list', 'action': 'tmdb_movies_popular_today', 'random_support': 'true', 'iconImage': 'popular_today'},
	{'name': 'Premieres', 'mode': 'build_movie_list', 'action': 'tmdb_movies_premieres', 'random_support': 'true', 'iconImage': 'fresh'},
	{'name': 'Latest Releases', 'mode': 'build_movie_list', 'action': 'tmdb_movies_latest_releases', 'random_support': 'true', 'iconImage': 'dvd'},
	{'name': 'Most Watched', 'mode': 'build_movie_list', 'action': 'movies_most_watched', 'random_support': 'true', 'iconImage': 'most_watched'},
	{'name': 'Most Favorited', 'mode': 'build_movie_list', 'action': 'trakt_movies_most_favorited', 'random_support': 'true', 'iconImage': 'favorites'},
	{'name': 'Top 10 Box Office', 'mode': 'build_movie_list', 'action': 'trakt_movies_top10_boxoffice', 'iconImage': 'box_office'},
	{'name': 'Blockbusters', 'mode': 'build_movie_list', 'action': 'tmdb_movies_blockbusters', 'random_support': 'true', 'iconImage': 'most_voted'},
	{'name': 'In Theaters', 'mode': 'build_movie_list', 'action': 'tmdb_movies_in_theaters', 'random_support': 'true', 'iconImage': 'intheatres'},
	{'name': 'Up Coming', 'mode': 'build_movie_list', 'action': 'tmdb_movies_upcoming', 'random_support': 'true', 'iconImage': 'lists'},
	{'name': 'Oscar Winners', 'mode': 'build_movie_list', 'action': 'tmdb_movies_oscar_winners', 'random_support': 'true', 'iconImage': 'oscar_winners'},
	{'name': 'Genres', 'mode': 'navigator.genres', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'genres'},
	{'name': 'Providers', 'mode': 'navigator.providers', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'providers'},
	{'name': 'Languages', 'mode': 'navigator.languages', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'languages'},
	{'name': 'Years', 'mode': 'navigator.years', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'calender'},
	{'name': 'Decades', 'mode': 'navigator.decades', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'calendar_decades'},
	{'name': 'Certifications', 'mode': 'navigator.certifications', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'certifications'},
	{'name': 'Because You Watched...', 'iconImage': 'because_you_watched', 'mode': 'navigator.because_you_watched', 'menu_type': 'movie'},
	{'name': 'Watched', 'mode': 'build_movie_list', 'action': 'watched_movies', 'iconImage': 'watched_1'},
	{'name': 'Recently Watched', 'mode': 'build_movie_list', 'action': 'recent_watched_movies', 'iconImage': 'watched_recent'},
	{'name': 'In Progress', 'mode': 'build_movie_list', 'action': 'in_progress_movies', 'iconImage': 'player'}
				]
	tvshow_list = [
	{'name': 'Trending', 'mode': 'build_tvshow_list', 'action': 'trakt_tv_trending', 'random_support': 'true', 'iconImage': 'trending'},
	{'name': 'Trending Recent', 'mode': 'build_tvshow_list', 'action': 'trakt_tv_trending_recent', 'random_support': 'true', 'iconImage': 'trending_recent'},
	{'name': 'Popular', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_popular', 'random_support': 'true', 'iconImage': 'popular'},
	{'name': 'Popular Today', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_popular_today', 'random_support': 'true', 'iconImage': 'popular_today'},
	{'name': 'Premieres', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_premieres', 'random_support': 'true', 'iconImage': 'fresh'},
	{'name': 'Most Watched', 'mode': 'build_tvshow_list', 'action': 'tv_most_watched', 'random_support': 'true', 'iconImage': 'most_watched'},
	{'name': 'Most Favorited', 'mode': 'build_tvshow_list', 'action': 'trakt_tv_most_favorited', 'random_support': 'true', 'iconImage': 'favorites'},
	{'name': 'Airing Today', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_airing_today', 'random_support': 'true', 'iconImage': 'live'},
	{'name': 'On the Air', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_on_the_air', 'random_support': 'true', 'iconImage': 'ontheair'},
	{'name': 'Up Coming', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_upcoming', 'random_support': 'true', 'iconImage': 'lists'},
	{'name': 'Genres', 'mode': 'navigator.genres', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'genres'},
	{'name': 'Providers', 'mode': 'navigator.providers', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'providers'},
	{'name': 'Networks', 'mode': 'navigator.networks', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'networks'},
	{'name': 'Languages', 'mode': 'navigator.languages', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'languages'},
	{'name': 'Years', 'mode': 'navigator.years', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'calender'},
	{'name': 'Decades', 'mode': 'navigator.decades', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'calendar_decades'},
	{'name': 'Certifications', 'mode': 'navigator.certifications', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'certifications'},
	{'name': 'Because You Watched...', 'mode': 'navigator.because_you_watched', 'menu_type': 'tvshow', 'iconImage': 'because_you_watched'},
	{'name': 'Watched', 'mode': 'build_tvshow_list', 'action': 'watched_tvshows', 'iconImage': 'watched_1'},
	{'name': 'Recently Watched', 'mode': 'build_tvshow_list', 'action': 'recent_watched_tvshows', 'iconImage': 'watched_recent'},
	{'name': 'In Progress', 'mode': 'build_tvshow_list', 'action': 'in_progress_tvshows', 'iconImage': 'in_progress_tvshow'},
	{'name': 'Recently Watched Episodes', 'mode': 'build_recently_watched_episode', 'iconImage': 'watched_recent'},
	{'name': 'In Progress Episodes', 'mode': 'build_in_progress_episode', 'iconImage': 'player'},
	{'name': 'Next Episodes', 'mode': 'build_next_episode', 'iconImage': 'next_episodes'}
				]
	tvshow_optional = [
	{'name': 'Next Episodes (Recently Watched)', 'mode': 'build_next_episode', 'nextep_sort': 'last_played', 'iconImage': 'next_episodes'},
	{'name': 'Next Episodes (Airdate)', 'mode': 'build_next_episode', 'nextep_sort': 'first_aired', 'iconImage': 'next_episodes'}
				]
	anime_list = [
	{'name': 'Anime Trending', 'mode': 'build_tvshow_list', 'action': 'trakt_anime_trending', 'random_support': 'true', 'iconImage': 'trending'},
	{'name': 'Anime Trending Recent', 'mode': 'build_tvshow_list', 'action': 'trakt_anime_trending_recent', 'random_support': 'true', 'iconImage': 'trending_recent'},
	{'name': 'Anime Popular', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_popular', 'random_support': 'true', 'iconImage': 'popular'},
	{'name': 'Anime Popular Recent', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_popular_recent', 'random_support': 'true', 'iconImage': 'popular_today'},
	{'name': 'Anime Premieres', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_premieres', 'random_support': 'true', 'iconImage': 'fresh'},
	{'name': 'Anime Most Watched', 'mode': 'build_tvshow_list', 'action': 'anime_most_watched', 'random_support': 'true', 'iconImage': 'most_watched'},
	{'name': 'Anime Most Favorited', 'mode': 'build_tvshow_list', 'action': 'trakt_anime_most_favorited', 'random_support': 'true', 'iconImage': 'favorites'},
	{'name': 'Anime On the Air', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_on_the_air', 'random_support': 'true', 'iconImage': 'ontheair'},
	{'name': 'Anime Upcoming', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_upcoming', 'random_support': 'true', 'iconImage': 'lists'},
	{'name': 'Anime Genres', 'mode': 'navigator.genres', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'genres'},
	{'name': 'Anime Providers', 'mode': 'navigator.providers', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'providers'},
	{'name': 'Anime Years', 'mode': 'navigator.years', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'calender'},
	{'name': 'Anime Decades', 'mode': 'navigator.decades', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'calendar_decades'},
	{'name': 'Anime Certifications', 'mode': 'navigator.certifications', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'certifications'},
	{'name': 'Anime Watched', 'mode': 'build_tvshow_list', 'action': 'watched_tvshows', 'is_anime_list': 'true', 'iconImage': 'watched_1'},
	{'name': 'Anime Recently Watched', 'mode': 'build_tvshow_list', 'action': 'recent_watched_tvshows', 'is_anime_list': 'true', 'iconImage': 'watched_recent'},
	{'name': 'Anime In Progress', 'mode': 'build_tvshow_list', 'action': 'in_progress_tvshows', 'is_anime_list': 'true', 'iconImage': 'in_progress_tvshow'},
	{'name': 'Anime Recently Watched Episodes', 'mode': 'build_recently_watched_episode', 'is_anime_list': 'true', 'iconImage': 'watched_recent'},
	{'name': 'Anime In Progress Episodes', 'mode': 'build_in_progress_episode', 'is_anime_list': 'true', 'iconImage': 'player'},
	{'name': 'Anime Next Episodes', 'mode': 'build_next_episode', 'iconImage': 'next_episodes', 'is_anime_list': 'true'}
					]
	anime_optional = [
	{'name': 'Anime Next Episodes (Recently Watched)', 'mode': 'build_next_episode', 'nextep_sort': 'last_played', 'iconImage': 'next_episodes', 'is_anime_list': 'true'},
	{'name': 'Anime Next Episodes (Airdate)', 'mode': 'build_next_episode', 'nextep_sort': 'first_aired', 'iconImage': 'next_episodes', 'is_anime_list': 'true'}
					]

	main_menus = {'RootList': root_list, 'MovieList': movie_list, 'TVShowList': tvshow_list, 'AnimeList': anime_list}
	optional_menus = {'TVShowList': tvshow_optional, 'AnimeList': anime_optional}
	
	def without_optional_extras(self, list_name, rows):
		optional = (getattr(self, 'optional_menus', None) or {}).get(list_name) or []
		skip_names = {i.get('name') for i in optional}
		return [i for i in (rows or []) if not i.get('nextep_sort') and i.get('name') not in skip_names]

	def stock_menu_contents(self, list_name):
		"""Catalog menu without optional extras (Next Episodes sort variants, etc.)."""
		return self.without_optional_extras(list_name, [dict(i) for i in (self.main_menus.get(list_name) or [])])

	def get_opted_optional(self, list_name):
		"""Extras the user added via Check for New, until Restore. Not stored on default."""
		contents = self.get_memory_cache(list_name, 'opted_optional')
		if contents is None:
			contents = self.get_list(list_name, 'opted_optional')
		if contents:
			return contents
		default = self.get_memory_cache(list_name, 'default') or self.get_list(list_name, 'default') or []
		optional = (getattr(self, 'optional_menus', None) or {}).get(list_name) or []
		canonical = {i.get('name'): dict(i) for i in optional}
		seen, extras = set(), []
		for item in default:
			name = item.get('name')
			if name in canonical and name not in seen:
				seen.add(name)
				extras.append(canonical[name])
		if extras:
			self.set_list(list_name, 'opted_optional', extras)
		return extras

	def get_main_lists(self, list_name):
		default_contents = self.get_memory_cache(list_name, 'default') or self.get_list(list_name, 'default')
		if default_contents == None:
			self.rebuild_database()
			return self.get_main_lists(list_name)
		edited_contents = self.get_memory_cache(list_name, 'edited')
		if edited_contents is None:
			edited_contents = self.get_list(list_name, 'edited')
		return default_contents, edited_contents

	def get_list(self, list_name, list_type):
		contents = None
		try:
			dbcon = connect_database('navigator_db')
			contents = eval(dbcon.execute('SELECT list_contents FROM navigator WHERE list_name = ? AND list_type = ?', (list_name, list_type)).fetchone()[0])
			self.set_memory_cache(list_name, list_type, contents)
		except: pass
		return contents

	def set_list(self, list_name, list_type, list_contents):
		dbcon = connect_database('navigator_db')
		dbcon.execute('INSERT OR REPLACE INTO navigator VALUES (?, ?, ?)', (list_name, list_type, repr(list_contents)))
		self.set_memory_cache(list_name, list_type, list_contents)

	def delete_list(self, list_name, list_type):
		dbcon = connect_database('navigator_db')
		dbcon.execute('DELETE FROM navigator WHERE list_name=? and list_type=?', (list_name, list_type))
		self.delete_memory_cache(list_name, list_type)
		dbcon.execute('VACUUM')
	
	def get_memory_cache(self, list_name, list_type):
		try: return eval(get_property(self._get_list_prop(list_type) % list_name))
		except: return None
	
	def set_memory_cache(self, list_name, list_type, list_contents):
		set_property(self._get_list_prop(list_type) % list_name, repr(list_contents))

	def delete_memory_cache(self, list_name, list_type):
		clear_property(self._get_list_prop(list_type) % list_name)

	def get_shortcut_folders(self):
		try:
			dbcon = connect_database('navigator_db')
			folders = dbcon.execute('SELECT list_name, list_contents FROM navigator WHERE list_type = ?', ('shortcut_folder',)).fetchall()
			folders = sorted([(str(i[0]), eval(i[1])) for i in folders], key=lambda s: s[0].lower())
		except: folders = []
		return folders

	def get_shortcut_folder_contents(self, list_name):
		try:
			dbcon = connect_database('navigator_db')
			contents = eval(dbcon.execute('SELECT list_contents FROM navigator WHERE list_name = ? AND list_type = ?', (list_name, 'shortcut_folder')).fetchone()[0])
		except: contents = []
		return contents

	def currently_used_list(self, list_name):
		used_list = None
		try:
			edited = self.get_memory_cache(list_name, 'edited')
			if edited is None:
				edited = self.get_list(list_name, 'edited')
			if edited:
				return edited
			used_list = self.get_memory_cache(list_name, 'default') or self.get_list(list_name, 'default')
			if used_list:
				return self.without_optional_extras(list_name, used_list)
		except: pass
		if not used_list:
			try: self.rebuild_database()
			except: pass
			used_list = self.stock_menu_contents(list_name)
		return used_list

	def rebuild_database(self):
		for list_name in NavigatorCache.main_menus:
			self.set_list(list_name, 'default', self.stock_menu_contents(list_name))

	def _get_list_prop(self, list_type):
		return {'default': 'redlight_%s_default', 'edited': 'redlight_%s_edited', 'shortcut_folder': 'redlight_%s_shortcut_folder',
			'opted_optional': 'redlight_%s_opted_optional'}[list_type]
	
	def random_movie_lists(self):
		m_list = NavigatorCache.movie_list
		movie_random_converts = {'navigator.genres': 'tmdb_movies_genres', 'navigator.providers': 'tmdb_movies_providers',  'navigator.languages': 'tmdb_movies_languages',
								'navigator.years': 'tmdb_movies_year', 'navigator.decades': 'tmdb_movies_decade', 'navigator.certifications': 'tmdb_movies_certifications'}
		return [dict(i, **{'mode': 'random.build_movie_list', 'action': i.get('action') or movie_random_converts[i['mode']],
							'random': 'true', 'name': 'Movies Random %s' % i['name'], 'menu_type': 'movie'}) for i in m_list if 'random_support' in i]
	
	def random_tvshow_lists(self):
		t_list = NavigatorCache.tvshow_list
		tvshow_random_converts = {'navigator.genres': 'tmdb_tv_genres', 'navigator.providers': 'tmdb_tv_providers', 'navigator.networks': 'tmdb_tv_networks',
								'navigator.languages': 'tmdb_tv_languages', 'navigator.years': 'tmdb_tv_year', 'navigator.decades': 'tmdb_tv_decade',
								'navigator.certifications': 'trakt_tv_certifications'}
		return [dict(i, **{'mode': 'random.build_tvshow_list', 'action': i.get('action') or tvshow_random_converts[i['mode']],
							'random': 'true', 'name': 'TV Shows Random %s' % i['name'], 'menu_type': 'tvshow'}) for i in t_list if 'random_support' in i]
	
	def random_anime_lists(self):
		a_list = NavigatorCache.anime_list
		anime_random_converts = {'navigator.genres': 'tmdb_anime_genres', 'navigator.providers': 'tmdb_anime_providers', 'navigator.years': 'tmdb_anime_year',
								'navigator.decades': 'tmdb_anime_decade', 'navigator.certifications': 'trakt_anime_certifications'}
		return [dict(i, **{'mode': 'random.build_tvshow_list', 'action': i.get('action') or anime_random_converts[i['mode']],
							'random': 'true', 'name': i['name'].replace('Anime', 'Anime Random'), 'menu_type': 'tvshow'}) for i in a_list if 'random_support' in i]

	def random_because_you_watched_lists(self):
		return [
			{'mode': 'random.build_movie_list', 'action': 'because_you_watched', 'name': 'Random Because You Watched Movies', 'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'because_you_watched', 'name': 'Random Because You Watched TV Shows', 'iconImage': 'tv', 'random': 'true'},
				]
	
	def random_tmdb_lists(self):
		return [
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'watchlist', 'media_type': 'movie', 'name': 'Random TMDb Movie Watchlist', 'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'watchlist', 'media_type': 'tv', 'name': 'Random TMDb TV Show Watchlist', 'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'favorites', 'media_type': 'movie', 'name': 'Random TMDb Movie Favorites', 'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'favorites', 'media_type': 'tv', 'name': 'Random TMDb TV Show Favorites', 'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'recommendations', 'media_type': 'movie', 'name': 'Random TMDb Movie Recommendations',
			'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'recommendations', 'media_type': 'tv', 'name': 'Random TMDb TV Show Recommendations',
			'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'tmdblist.get_tmdb_lists', 'name': 'Random Shuffled TMDb My Lists (All)', 'iconImage': 'tmdb', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_tmdb_lists', 'name': 'Random TMDb My Lists (Single)', 'iconImage': 'tmdb', 'random': 'true'}
				]
	
	def random_personal_lists(self):
		return [
			{'mode': 'personal_lists.get_personal_lists', 'name': 'Random Shuffled Personal Lists (All)', 'iconImage': 'lists', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_personal_lists', 'name': 'Random Personal Lists (Single)', 'iconImage': 'lists', 'random': 'true'}
				]

	def random_mdblist_lists(self):
		return [
			{'mode': 'random.build_movie_list', 'action': 'mdblist_watchlist', 'name': 'Random MDBList Movie Watchlist', 'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'mdblist_watchlist', 'name': 'Random MDBList TV Show Watchlist', 'iconImage': 'tv', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'mdblist_collection', 'name': 'Random MDBList Movie Library', 'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'mdblist_collection', 'name': 'Random MDBList TV Show Library', 'iconImage': 'tv', 'random': 'true'},
			{'mode': 'mdblist.get_mdbl_lists', 'name': 'Random Shuffled MDBList My Lists (All)', 'iconImage': 'mdblist', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_mdblist_lists', 'list_type': 'my_lists', 'name': 'Random MDBList My Lists (Single)', 'iconImage': 'mdblist', 'random': 'true'},
			{'mode': 'mdblist.get_mdbl_liked_lists', 'name': 'Random Shuffled MDBList Liked Lists (All)', 'iconImage': 'mdblist', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_mdblist_lists', 'list_type': 'liked_lists', 'name': 'Random MDBList Liked Lists (Single)', 'iconImage': 'mdblist', 'random': 'true'},
			{'mode': 'mdblist.get_mdbl_top_lists', 'name': 'Random Shuffled Popular MDBLists (All)', 'iconImage': 'mdblist', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_mdblist_lists', 'list_type': 'user_lists', 'name': 'Random Popular MDBLists (Single)', 'iconImage': 'mdblist', 'random': 'true'},
				]

	def random_trakt_lists_personal(self):
		return [
			{'mode': 'random.build_movie_list', 'action': 'trakt_collection_lists', 'name': 'Random Trakt Movie Library', 'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'trakt_collection_lists', 'name': 'Random Trakt TV Show Library', 'iconImage': 'tv', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'trakt_watchlist_lists', 'name': 'Random Trakt Movie Watchlist', 'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'trakt_watchlist_lists', 'name': 'Random Trakt TV Show Watchlist', 'iconImage': 'tv', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'trakt_recommendations', 'new_page': 'movies', 'name': 'Random Trakt Recommended Movies',
			'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'trakt_recommendations', 'new_page': 'shows', 'name': 'Random Trakt Recommended TV Shows',
			'iconImage': 'tv', 'random': 'true'},
			{'mode': 'trakt.list.get_trakt_lists', 'list_type': 'my_lists', 'name': 'Random Shuffled Trakt My Lists (All)',
			'iconImage': 'trakt', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_trakt_lists', 'list_type': 'my_lists', 'name': 'Random Trakt My Lists (Single)', 'iconImage': 'trakt', 'random': 'true'},
			{'mode': 'trakt.list.get_trakt_lists', 'list_type': 'liked_lists', 'name': 'Random Shuffled Trakt Liked Lists (All)',
			'iconImage': 'trakt', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_trakt_lists', 'list_type': 'liked_lists', 'name': 'Random Trakt Liked Lists (Single)', 'iconImage': 'trakt', 'random': 'true'},
				]

	def random_trakt_lists_public(self):
		return [
			{'mode': 'trakt.list.get_trakt_user_lists', 'list_type': 'trending', 'category_name': 'Random Trending User Lists', 'name': 'Random Trending User Lists (All)',
			'iconImage': 'trakt', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_trakt_lists', 'list_type': 'trending', 'category_name': 'Random Trending User Lists', 'name': 'Random Trending User Lists (Single)',
			'iconImage': 'trakt', 'random': 'true'},
			{'mode': 'trakt.list.get_trakt_user_lists', 'list_type': 'popular', 'category_name': 'Random Popular User Lists', 'name': 'Random Popular User Lists (All)',
			'iconImage': 'trakt', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_trakt_lists', 'list_type': 'popular', 'category_name': 'Random Popular User Lists', 'name': 'Random Popular User Lists (Single)',
			'iconImage': 'trakt', 'random': 'true'}
				]

	def random_simkl_lists(self):
		return [
			{'mode': 'random.build_movie_list', 'action': 'simkl_plantowatch', 'name': 'Random Simkl Movie Plan to Watch', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_plantowatch', 'name': 'Random Simkl TV Plan to Watch', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_plantowatch', 'is_anime_list': 'true', 'name': 'Random Simkl Anime Plan to Watch', 'iconImage': 'anime', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_watching', 'name': 'Random Simkl TV Watching', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_watching', 'is_anime_list': 'true', 'name': 'Random Simkl Anime Watching', 'iconImage': 'anime', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'simkl_completed', 'name': 'Random Simkl Movie Completed', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_completed', 'name': 'Random Simkl TV Completed', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_completed', 'is_anime_list': 'true', 'name': 'Random Simkl Anime Completed', 'iconImage': 'anime', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_hold', 'name': 'Random Simkl TV On Hold', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_hold', 'is_anime_list': 'true', 'name': 'Random Simkl Anime On Hold', 'iconImage': 'anime', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'simkl_dropped', 'name': 'Random Simkl Movie Dropped', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_dropped', 'name': 'Random Simkl TV Dropped', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_dropped', 'is_anime_list': 'true', 'name': 'Random Simkl Anime Dropped', 'iconImage': 'anime', 'random': 'true'},
				]

	def random_punchplay_lists(self):
		return [
			{'mode': 'random.build_movie_list', 'action': 'punchplay_watchlist', 'name': 'Random PunchPlay Movie Watchlist', 'iconImage': 'punchplay', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'punchplay_watchlist', 'name': 'Random PunchPlay TV Watchlist', 'iconImage': 'punchplay', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'punchplay_watchlist', 'is_anime_list': 'true', 'name': 'Random PunchPlay Anime Watchlist', 'iconImage': 'anime', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'punchplay_collection', 'name': 'Random PunchPlay Movie Collection', 'iconImage': 'punchplay', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'punchplay_collection', 'name': 'Random PunchPlay TV Collection', 'iconImage': 'punchplay', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'punchplay_collection', 'is_anime_list': 'true', 'name': 'Random PunchPlay Anime Collection', 'iconImage': 'anime', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'punchplay_watching', 'name': 'Random PunchPlay TV Watching', 'iconImage': 'punchplay', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'punchplay_watching', 'is_anime_list': 'true', 'name': 'Random PunchPlay Anime Watching', 'iconImage': 'anime', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'punchplay_completed', 'name': 'Random PunchPlay Movie Watched', 'iconImage': 'punchplay', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'punchplay_completed', 'name': 'Random PunchPlay TV Watched', 'iconImage': 'punchplay', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'punchplay_completed', 'is_anime_list': 'true', 'name': 'Random PunchPlay Anime Watched', 'iconImage': 'anime', 'random': 'true'},
				]

def migrate_my_content_nav_mode():
	"""Rewrite stored menus that still use navigator.my_content to navigator.my_lists."""
	nc = NavigatorCache()
	changed = False
	def _patch(items):
		nonlocal changed
		if not items: return items
		out = []
		for item in items:
			row = dict(item)
			if row.get('mode') == 'navigator.my_content':
				row['mode'] = 'navigator.my_lists'
				changed = True
			out.append(row)
		return out
	try:
		dbcon = connect_database('navigator_db')
		for list_name, list_type, raw in dbcon.execute('SELECT list_name, list_type, list_contents FROM navigator').fetchall():
			try: contents = eval(raw)
			except: continue
			patched = _patch(contents)
			if patched != contents:
				nc.set_list(list_name, list_type, patched)
				changed = True
	except: pass
	if changed:
		for list_name in NavigatorCache.main_menus:
			nc.delete_memory_cache(list_name, 'default')
			nc.delete_memory_cache(list_name, 'edited')
	return changed

navigator_cache = NavigatorCache()
