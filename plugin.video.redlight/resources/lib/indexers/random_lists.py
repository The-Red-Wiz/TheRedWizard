# -*- coding: utf-8 -*-
import sys
import json
import random
from caches.random_widgets_cache import RandomWidgets
from indexers.movies import Movies
from indexers.tvshows import TVShows
from modules import meta_lists
from modules.settings import paginate, page_limit, max_threads, widget_hide_watched_fill
from modules import kodi_utils
from modules.utils import manual_function_import, TaskPool
# logger = kodi_utils.logger

def get_persistent_content(database, key, is_external):
	results, refresh_cache, key = None, True, 'random_list.%s' % key
	if not is_external: refresh_cache = False
	else:
		try:
			results = database.get(key)
			if results: refresh_cache = False
		except: pass
	return results, refresh_cache

def set_persistent_content(database, key, data):
	database.set('random_list.%s' % key, data, 24)

_RANDOM_LIST_NAME_LOOKUP = None
_RANDOM_LIST_LOOKUP_KEYS = ('action', 'menu_type', 'list_type', 'list_id', 'media_type', 'new_page')

def _random_list_lookup_key(params, mode=None):
	mode = (mode or params.get('mode') or '').replace('random.', '')
	parts = [mode or '']
	for key in _RANDOM_LIST_LOOKUP_KEYS:
		value = params.get(key)
		if value not in (None, ''): parts.append('%s=%s' % (key, value))
	return '|'.join(parts)

def _build_random_list_name_lookup():
	from caches.navigator_cache import navigator_cache
	lookup = {}
	sources = (
		navigator_cache.random_movie_lists(), navigator_cache.random_tvshow_lists(), navigator_cache.random_anime_lists(),
		navigator_cache.random_because_you_watched_lists(), navigator_cache.random_tmdb_lists(), navigator_cache.random_personal_lists(),
		navigator_cache.random_mdblist_lists(), navigator_cache.random_trakt_lists_personal(), navigator_cache.random_trakt_lists_public(),
		navigator_cache.random_simkl_lists(),
		)
	for items in sources:
		for item in items:
			name = item.get('name')
			if not name: continue
			lookup[_random_list_lookup_key(item)] = name
	return lookup

def random_list_property_key(params):
	global _RANDOM_LIST_NAME_LOOKUP
	name = params.get('name') or params.get('base_list_name')
	if name: return name
	if _RANDOM_LIST_NAME_LOOKUP is None: _RANDOM_LIST_NAME_LOOKUP = _build_random_list_name_lookup()
	return _RANDOM_LIST_NAME_LOOKUP.get(_random_list_lookup_key(params))

class RandomLists():
	movie_main = ('tmdb_movies_popular', 'tmdb_movies_popular_today','tmdb_movies_blockbusters','tmdb_movies_in_theaters', 'tmdb_movies_upcoming', 'tmdb_movies_latest_releases',
	'tmdb_movies_premieres', 'tmdb_movies_oscar_winners')
	movie_trakt_main = ('trakt_movies_trending', 'trakt_movies_trending_recent', 'trakt_movies_most_favorited',
	'trakt_movies_top10_boxoffice', 'trakt_recommendations')
	movie_most_watched = ('movies_most_watched', 'trakt_movies_most_watched')
	movie_special_main = {'tmdb_movies_languages': meta_lists.languages, 'tmdb_movies_providers': meta_lists.watch_providers_movies, 'tmdb_movies_year': meta_lists.years_movies,
	'tmdb_movies_decade': meta_lists.decades_movies, 'tmdb_movies_certifications': meta_lists.movie_certifications, 'tmdb_movies_genres': meta_lists.movie_genres}
	tvshow_main = ('tmdb_tv_popular', 'tmdb_tv_popular_today', 'tmdb_tv_premieres', 'tmdb_tv_airing_today','tmdb_tv_on_the_air','tmdb_tv_upcoming',
	'tmdb_anime_popular', 'tmdb_anime_popular_recent', 'tmdb_anime_premieres', 'tmdb_anime_upcoming', 'tmdb_anime_on_the_air')
	tvshow_trakt_main = ('trakt_tv_trending', 'trakt_tv_trending_recent', 'trakt_recommendations', 'trakt_tv_most_favorited',
	'trakt_anime_trending', 'trakt_anime_trending_recent', 'trakt_anime_most_favorited')
	tvshow_most_watched = ('tv_most_watched', 'anime_most_watched', 'trakt_tv_most_watched', 'trakt_anime_most_watched')
	tvshow_special_main = {'tmdb_tv_languages': meta_lists.languages, 'tmdb_tv_networks': meta_lists.networks, 'tmdb_tv_providers': meta_lists.watch_providers_tvshows,
	'tmdb_tv_year': meta_lists.years_tvshows, 'tmdb_tv_decade': meta_lists.decades_tvshows, 'tmdb_tv_genres': meta_lists.tvshow_genres,
	'trakt_tv_certifications': meta_lists.tvshow_certifications, 'tmdb_anime_year': meta_lists.years_tvshows, 'tmdb_anime_decade': meta_lists.decades_tvshows,
	'tmdb_anime_genres': meta_lists.anime_genres, 'tmdb_anime_providers': meta_lists.watch_providers_tvshows, 'trakt_anime_certifications': meta_lists.tvshow_certifications}
	tvshow_trakt_special = ('trakt_tv_certifications', 'trakt_anime_certifications')
	simkl_personal = ('simkl_plantowatch', 'simkl_completed', 'simkl_watching', 'simkl_hold', 'simkl_dropped')
	punchplay_personal = ('punchplay_watchlist', 'punchplay_collection', 'punchplay_favorites', 'punchplay_plantowatch',
		'punchplay_watching', 'punchplay_hold', 'punchplay_completed', 'punchplay_dropped')
	mdblist_personal = ('mdblist_watchlist', 'mdblist_collection')

	def __init__(self, params):
		self.database = RandomWidgets()
		self.handle = int(sys.argv[1])
		self.params = params
		self.params_get = self.params.get
		self.mode = self.params_get('mode').replace('random.', '')
		self.action = self.params_get('action')
		self.menu_type = self.params_get('menu_type', None) or ('movie' if 'movie' in self.mode else 'tvshow' if 'tvshow' in self.mode else '')
		self.base_list_name = self.params_get('name') or random_list_property_key(self.params)
		self.params.update({'mode': self.mode, 'action': self.action, 'menu_type': self.menu_type, 'base_list_name': self.base_list_name})
		self.is_external = kodi_utils.external()
		self.folder_name = self.params_get('folder_name', None)
		if self.menu_type == 'movie': self.function, self.view_mode, self.content_type = Movies, 'view.movies', 'movies'
		else: self.function, self.view_mode, self.content_type = TVShows, 'view.tvshows', 'tvshows'
		self.category_name, self.list_items, self.random_results = '', [], []
		if self.action and 'anime' in self.action: self.max_range, self.sample_size = 4, 3
		else: self.max_range, self.sample_size = 10, 3

	def run_random(self):
		if self.action in self.movie_main: return self.random_main()
		if self.action in self.tvshow_main: return self.random_main()
		if self.action in self.movie_trakt_main: return self.random_trakt_main()
		if self.action in self.tvshow_trakt_main: return self.random_trakt_main()
		if self.action in self.movie_most_watched + self.tvshow_most_watched: return self.random_most_watched()
		if self.action in self.movie_special_main: return self.random_special_main()
		if self.action in self.tvshow_special_main: return self.random_special_main()
		if self.action in ('trakt_collection_lists', 'trakt_watchlist_lists'): return self.random_trakt_collection_watchlist()
		if self.action in self.simkl_personal: return self.random_simkl_personal()
		if self.action in self.punchplay_personal: return self.random_punchplay_personal()
		if self.action in self.mdblist_personal: return self.random_mdblist_personal()
		if self.action == 'because_you_watched': return self.random_because_you_watched()
		if self.mode == 'build_trakt_lists': return self.random_trakt_lists()
		if self.mode == 'build_personal_lists': return self.random_personal_lists()
		if self.mode == 'build_tmdb_lists': return self.random_tmdb_lists()
		if self.mode == 'build_mdblist_lists': return self.random_mdblist_lists()
		if self.mode == 'build_trakt_lists_contents': return self.trakt_lists_contents()
		if self.mode == 'build_personal_lists_contents': return self.personal_lists_contents()
		if self.mode == 'build_tmdb_lists_contents': return self.tmdb_lists_contents()
		if self.mode == 'build_mdblist_lists_contents': return self.mdblist_lists_contents()
		if self.action in ('tmdb_movies_discover', 'tmdb_tv_discover'): return self.random_discover()

	def _random_cache_key(self, key):
		if self.is_external and widget_hide_watched_fill(): return '%s.fill' % key
		return key

	def _random_sample_count(self):
		count = 20
		if self.is_external and widget_hide_watched_fill():
			try: count = max(count, page_limit(True) * 2)
			except: pass
		return count

	def _trim_filled_random_items(self):
		if not (self.is_external and widget_hide_watched_fill() and self.list_items): return
		try:
			limit = page_limit(True)
			if len(self.list_items) > limit: self.list_items = self.list_items[:limit]
		except: pass

	def random_main(self):
		cache_key = self._random_cache_key(self.action)
		random_list, cache_to_memory = get_persistent_content(self.database, cache_key, self.is_external)
		if not random_list:
			list_function = self.get_function()
			threads = TaskPool().tasks(lambda x: self.random_results.extend(list_function(x)['results']), self.get_sample(), max_threads())
			[i.join() for i in threads]
			random_list = random.sample(self.random_results, min(len(self.random_results), self._random_sample_count()))
			if cache_to_memory: set_persistent_content(self.database, cache_key, random_list)
		self.params['list'] = [i['id'] for i in random_list]
		self.list_items = self.function(self.params).worker()
		self._trim_filled_random_items()
		self.category_name = self.params_get('category_name', None) or self.base_list_name or ''
		self.make_directory()

	def random_trakt_main(self):
		cache_key = self._random_cache_key(self.action)
		random_list, cache_to_memory = get_persistent_content(self.database, cache_key, self.is_external)
		function_key, list_key = ('movies', 'movie') if self.menu_type == 'movie' else ('shows', 'show')
		if not random_list:
			list_function = self.get_function()
			threads = TaskPool().tasks(lambda x: self.random_results.extend(list_function(x)),
										[function_key,] if self.action == 'trakt_recommendations' else self.get_sample(), max_threads())
			[i.join() for i in threads]
			random_list = random.sample(self.random_results, min(len(self.random_results), self._random_sample_count()))
			if cache_to_memory: set_persistent_content(self.database, cache_key, random_list)
		try: self.params['list'] = [i[list_key]['ids'] for i in random_list]
		except: self.params['list'] = [i['ids'] for i in random_list]
		self.params['id_type'] = 'trakt_dict'
		self.list_items = self.function(self.params).worker()
		self._trim_filled_random_items()
		self.category_name = self.params_get('category_name', None) or self.base_list_name or ''
		self.make_directory()

	def random_most_watched(self):
		cache_key = self._random_cache_key(self.action)
		random_list, cache_to_memory = get_persistent_content(self.database, cache_key, self.is_external)
		list_key = 'movie' if self.menu_type == 'movie' else 'show'
		if not random_list:
			list_function = self.get_function()
			threads = TaskPool().tasks(lambda x: self.random_results.extend(list_function(x)), self.get_sample(), max_threads())
			[i.join() for i in threads]
			random_list = random.sample(self.random_results, min(len(self.random_results), self._random_sample_count()))
			if cache_to_memory: set_persistent_content(self.database, cache_key, random_list)
		try: self.params['list'] = [i[list_key]['ids'] for i in random_list]
		except: self.params['list'] = [i['ids'] for i in random_list]
		self.params['id_type'] = 'trakt_dict'
		self.list_items = self.function(self.params).worker()
		self._trim_filled_random_items()
		self.category_name = self.params_get('category_name', None) or self.base_list_name or ''
		self.make_directory()

	def random_special_main(self):
		cache_key = self._random_cache_key(self.action)
		random_list, cache_to_memory = get_persistent_content(self.database, cache_key, self.is_external)
		if not random_list:
			list_function = self.get_function()
			choice_list = self.movie_special_main if self.menu_type == 'movie' else self.tvshow_special_main
			info = random.choice(choice_list[self.action]())
			list_name = info['name']
			if self.action in self.tvshow_trakt_special:
				threads = TaskPool().tasks(lambda x: self.random_results.extend(list_function(info['id'], x)), self.get_sample(), max_threads())
			else:
				threads = TaskPool().tasks(lambda x: self.random_results.extend(list_function(info['id'], x)['results']), self.get_sample(), max_threads())
			[i.join() for i in threads]
			result = random.sample(self.random_results, min(len(self.random_results), self._random_sample_count()))
			if cache_to_memory: set_persistent_content(self.database, cache_key, {'name': list_name, 'result': result})
		else: list_name, result = random_list['name'], random_list['result']
		if self.action in self.tvshow_trakt_special: self.params.update({'id_type': 'trakt_dict', 'list': [i['show']['ids'] for i in result]})
		else: self.params['list'] = [i['id'] for i in result]
		self.list_items = self.function(self.params).worker()
		self._trim_filled_random_items()
		self.category_name = list_name
		self.make_directory()

	def random_trakt_collection_watchlist(self):
		from apis.trakt_api import trakt_collection_lists, trakt_watchlist_lists
		random_list, cache_to_memory = get_persistent_content(self.database, '%s_%s' % (self.menu_type, self.action), self.is_external)
		if not random_list:
			function = trakt_collection_lists if self.action == 'trakt_collection_lists' else trakt_watchlist_lists
			self.random_results = function('movies' if self.menu_type in ('movie', 'movies') else 'shows', None)
			if paginate(self.is_external): random_list = random.sample(self.random_results, min(len(self.random_results), page_limit(self.is_external)))
			else: random_list = random.sample(self.random_results, len(self.random_results))
			if cache_to_memory: set_persistent_content(self.database, '%s_%s' % (self.menu_type, self.action), random_list)
		self.params['list'] = [i['media_ids'] for i in random_list]
		self.params['id_type'] = 'trakt_dict'
		self.list_items = self.function(self.params).worker()
		self.category_name = self.base_list_name or ''
		self.make_directory()

	def random_simkl_personal(self):
		is_anime = self.params_get('is_anime_list') == 'true'
		if self.menu_type in ('movie', 'movies'): media_kind = 'movies'
		elif is_anime: media_kind = 'anime'
		else: media_kind = 'shows'
		cache_key = '%s_%s' % (media_kind, self.action)
		random_list, cache_to_memory = get_persistent_content(self.database, cache_key, self.is_external)
		if not random_list:
			list_function = self.get_function()
			self.random_results = list_function(media_kind, None) or []
			if paginate(self.is_external): random_list = random.sample(self.random_results, min(len(self.random_results), page_limit(self.is_external))) if self.random_results else []
			else: random_list = random.sample(self.random_results, len(self.random_results)) if self.random_results else []
			if cache_to_memory: set_persistent_content(self.database, cache_key, random_list)
		self.params['list'] = [i['media_ids'] for i in random_list]
		self.params['id_type'] = 'trakt_dict'
		if is_anime: self.params['is_anime_list'] = 'true'
		self.list_items = self.function(self.params).worker()
		self.category_name = self.base_list_name or ''
		self.make_directory()

	def random_punchplay_personal(self):
		return self.random_simkl_personal()

	def random_because_you_watched(self):
		from apis.tmdb_api import tmdb_movies_recommendations, tmdb_tv_recommendations
		from apis.imdb_api import imdb_more_like_this
		from apis.trakt_api import trakt_movies_related, trakt_tv_related
		from apis.ai_api import ai_similar
		from modules.episode_tools import single_last_watched_episodes
		from modules.settings import tmdb_api_key, mpaa_region, recommend_service, recommend_seed
		from modules.metadata import movie_meta, tvshow_meta
		from modules.watched_status import get_recently_watched
		from modules.utils import get_current_timestamp, get_datetime
		random_list, cache_to_memory = get_persistent_content(self.database, '%s_%s' % (self.menu_type, self.action), self.is_external)
		recommend_type = recommend_service()
		try:
			if not random_list:
				recently_watched = get_recently_watched('movie' if self.menu_type == 'movie' else 'episode')
				if self.menu_type == 'tvshow': recently_watched = single_last_watched_episodes(recently_watched)
				recent_seed = random.choice(recently_watched[:recommend_seed()])
				seed_tmdb_id = recent_seed['media_id'] if self.menu_type == 'movie' else recent_seed['media_ids']['tmdb']
				list_name = 'Because You Watched... %s' % recent_seed['title']
				if recommend_type == 0:
					list_function = tmdb_movies_recommendations if self.menu_type == 'movie' else tmdb_tv_recommendations
					result = list_function(seed_tmdb_id, 1)['results']
				elif recommend_type == 1:
					meta_function = movie_meta if self.menu_type == 'movie' else tvshow_meta
					result = imdb_more_like_this(meta_function('tmdb_id', seed_tmdb_id, tmdb_api_key(), mpaa_region(), get_datetime(), get_current_timestamp())['imdb_id'])
				elif recommend_type == 2:
					key_id = 'movie|%s' % seed_tmdb_id if self.menu_type == 'movie' else 'tvshow|%s' % seed_tmdb_id
					result = ai_similar(key_id)['results']
				else:
					meta_function = movie_meta if self.menu_type == 'movie' else tvshow_meta
					list_function = trakt_movies_related if self.menu_type == 'movie' else trakt_tv_related
					result = list_function(meta_function('tmdb_id', seed_tmdb_id, tmdb_api_key(), mpaa_region(), get_datetime(), get_current_timestamp())['imdb_id'])
				random.shuffle(result)
				if cache_to_memory: set_persistent_content(self.database, '%s_%s' % (self.menu_type, self.action), {'name': list_name, 'result': result})
			else: list_name, result = random_list['name'], random_list['result']
			if recommend_type in (0, 2): self.params['list'] = [i['id'] for i in result]
			elif recommend_type == 1: self.params.update({'list': result, 'id_type': 'imdb_id'})
			else: self.params.update({'list': [i['ids'] for i in result], 'id_type': 'trakt_dict'})
			self.list_items = self.function(self.params).worker()
			self.category_name =  list_name
		except: kodi_utils.clear_property('redlight.random_because_you_watched')
		self.make_directory()

	def _empty_random_lists(self, toast):
		# Toast only — no placeholder row (clicking one just looked broken).
		kodi_utils.notification(toast, 3000)
		self.list_items = []
		self.category_name = toast
		self.view_mode, self.content_type = 'view.main', kodi_utils.MENU_FOLDER_CONTENT
		self.make_directory()

	def random_trakt_lists(self):
		from apis.trakt_api import trakt_get_lists, get_trakt_list_contents
		from indexers.trakt_lists import build_trakt_list
		list_type = self.params.get('list_type')
		list_type_name = 'Trakt My Lists' if list_type == 'my_lists' else 'Trakt Liked Lists' if list_type == 'liked_lists' else 'Trakt User Lists'
		random_list, cache_to_memory = get_persistent_content(self.database, '%s_%s' % (self.mode, list_type), self.is_external)
		if not random_list:
			if list_type == 'my_lists': self.random_results = [i for i in (trakt_get_lists(list_type) or []) if i.get('item_count')]
			else: self.random_results = [i['list'] for i in (trakt_get_lists(list_type) or []) if i.get('list') and i['list'].get('item_count')]
			if not self.random_results:
				if list_type == 'liked_lists':
					return self._empty_random_lists('No Trakt Liked Lists')
				if list_type == 'my_lists':
					return self._empty_random_lists('No Trakt My Lists')
				return self._empty_random_lists('No Lists Found')
			random_list = random.choice(self.random_results)
			slug = random_list['ids']['slug']
			user_ids = random_list.get('user', {}).get('ids') or {}
			user = user_ids.get('slug') or random_list.get('user', {}).get('username')
			list_id = random_list['ids']['trakt']
			list_name = random_list['name']
			with_auth = list_type == 'my_lists'
			result = get_trakt_list_contents(list_type, user, slug, with_auth, list_id, skip_sort=True)
			random.shuffle(result)
			if paginate(self.is_external): data = random.sample(result, min(len(result), page_limit(self.is_external)))
			else: data = random.sample(result, len(result))
			result = [dict(i, **{'order': c}) for c, i in enumerate(data)]
			url_params = {'base_list_name':list_type_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_trakt_list(url_params)
			if cache_to_memory: set_persistent_content(self.database, '%s_%s' % (self.mode, list_type), {'name': list_name, 'result': result})
		else:
			list_name, result = random_list['name'], random_list['result']
			url_params = {'base_list_name':list_type_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_trakt_list(url_params)
		self.view_mode, self.content_type = 'view.%s' % content_type, content_type
		self.category_name = list_name
		self.make_directory()

	def random_personal_lists(self):
		from indexers.personal_lists import get_personal_list, build_personal_list, get_all_personal_lists
		random_list, cache_to_memory = get_persistent_content(self.database, self.mode, self.is_external)
		if not random_list:
			self.random_results = [i for i in get_all_personal_lists() if i['total']]
			if not self.random_results:
				return self._empty_random_lists('No Personal Lists')
			random_list = random.choice(self.random_results)
			list_name = random_list['name']
			random_list['list_name'] = list_name
			result = get_personal_list(random_list)
			random.shuffle(result)
			if paginate(self.is_external): data = random.sample(result, min(len(result), page_limit(self.is_external)))
			else: data = random.sample(result, len(result))
			result = [dict(i, **{'order': c}) for c, i in enumerate(data)]
			url_params = {'base_list_name':list_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_personal_list(url_params)
			if cache_to_memory: set_persistent_content(self.database, self.mode, {'name': list_name, 'result': result})
		else:
			list_name, result = random_list['name'], random_list['result']
			url_params = {'base_list_name':list_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_personal_list(url_params)
		self.category_name = list_name or ''
		self.view_mode, self.content_type = 'view.%s' % content_type, content_type
		self.make_directory()

	def random_tmdb_lists(self):
		from indexers.tmdb_lists import get_tmdb_list, build_tmdb_list, get_all_tmdb_lists
		random_list, cache_to_memory = get_persistent_content(self.database, self.mode, self.is_external)
		if not random_list:
			self.random_results = [i for i in get_all_tmdb_lists() if i['number_of_items']]
			if not self.random_results:
				return self._empty_random_lists('No TMDb Lists')
			random_list = random.choice(self.random_results)
			list_id, list_name = random_list['id'], random_list['name']
			result = get_tmdb_list({'list_id': list_id})
			random.shuffle(result)
			if paginate(self.is_external): data = random.sample(result, min(len(result), page_limit(self.is_external)))
			else: data = random.sample(result, len(result))
			result = [dict(i, **{'order': c}) for c, i in enumerate(data)]
			url_params = {'base_list_name':list_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_tmdb_list(url_params)
			if cache_to_memory: set_persistent_content(self.database, self.mode, {'name': list_name, 'result': result})
		else:
			list_name, result = random_list['name'], random_list['result']
			url_params = {'base_list_name':list_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_tmdb_list(url_params)
		self.category_name = list_name or ''
		self.view_mode, self.content_type = 'view.%s' % content_type, content_type
		self.make_directory()

	def random_mdblist_lists(self):
		from apis.mdblist_api import mdbl_get_lists, mdbl_get_liked_lists, mdbl_top_lists, get_mdbl_list_payload, mdbl_ordered_list_rows
		from indexers.mdblist_lists import build_mdbl_list
		list_type = self.params.get('list_type', 'my_lists')
		list_type_name = {
			'my_lists': 'MDBList My Lists',
			'liked_lists': 'MDBList Liked Lists',
			'user_lists': 'Popular MDBLists'
		}.get(list_type, 'MDBList Lists')
		cache_key = '%s_%s' % (self.mode, list_type)
		random_list, cache_to_memory = get_persistent_content(self.database, cache_key, self.is_external)
		if not random_list:
			if list_type == 'liked_lists':
				self.random_results = [i for i in (mdbl_get_liked_lists() or []) if i.get('id') and i.get('items')]
			elif list_type == 'user_lists':
				self.random_results = [i for i in (mdbl_top_lists() or []) if i.get('id') and i.get('items')]
			else:
				self.random_results = [i for i in (mdbl_get_lists('my_lists') or []) if i.get('id') and i.get('items')]
			if not self.random_results:
				return self._empty_random_lists('No %s' % list_type_name)
			chosen = random.choice(self.random_results)
			list_id, list_name = chosen.get('id'), chosen.get('name') or 'MDBList'
			# Contents URL is lists/{id} for my/liked/top; only external differs.
			fetch_type = 'external' if list_type == 'external' else 'my_lists'
			result = mdbl_ordered_list_rows(get_mdbl_list_payload(fetch_type, list_id))
			random.shuffle(result)
			if paginate(self.is_external): data = random.sample(result, min(len(result), page_limit(self.is_external))) if result else []
			else: data = random.sample(result, len(result)) if result else []
			result = []
			for c, i in enumerate(data):
				row = dict(i)
				row['order'] = c
				row['custom_order'] = c
				result.append(row)
			url_params = {'base_list_name': list_type_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_mdbl_list(url_params)
			if cache_to_memory: set_persistent_content(self.database, cache_key, {'name': list_name, 'result': result})
		else:
			list_name, result = random_list['name'], random_list['result']
			url_params = {'base_list_name': list_type_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_mdbl_list(url_params)
		self.category_name = list_name or ''
		self.view_mode, self.content_type = 'view.%s' % content_type, content_type
		self.make_directory()

	def mdblist_lists_contents(self):
		from apis.mdblist_api import get_mdbl_list_payload, mdbl_ordered_list_rows
		from indexers.mdblist_lists import build_mdbl_list
		list_name, list_type = self.params.get('list_name'), self.params.get('list_type', 'my_lists')
		list_type_name = {
			'my_lists': 'MDBList My Lists',
			'liked_lists': 'MDBList Liked Lists',
			'user_lists': 'Popular MDBLists',
			'external': 'MDBList Lists'
		}.get(list_type, 'MDBList Lists')
		cache_key = '%s_%s' % (list_type, list_name)
		random_list, cache_to_memory = get_persistent_content(self.database, cache_key, self.is_external)
		if not random_list:
			list_id = self.params_get('list_id')
			fetch_type = list_type if list_type == 'external' else 'my_lists'
			result = mdbl_ordered_list_rows(get_mdbl_list_payload(fetch_type, list_id))
			random.shuffle(result)
			if paginate(self.is_external): result = random.sample(result, min(len(result), page_limit(self.is_external))) if result else []
			else: result = random.sample(result, len(result)) if result else []
			ordered = []
			for c, i in enumerate(result):
				row = dict(i)
				row['order'] = c
				row['custom_order'] = c
				ordered.append(row)
			result = ordered
			url_params = {'base_list_name': list_type_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_mdbl_list(url_params)
			if cache_to_memory: set_persistent_content(self.database, cache_key, {'name': list_name, 'result': result})
		else:
			list_name, result = random_list['name'], random_list['result']
			url_params = {'base_list_name': list_type_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_mdbl_list(url_params)
		self.category_name = self.base_list_name or list_name or ''
		self.view_mode, self.content_type = 'view.%s' % content_type, content_type
		self.make_directory()

	def trakt_lists_contents(self):
		from apis.trakt_api import get_trakt_list_contents
		from indexers.trakt_lists import build_trakt_list
		list_name, list_type = self.params.get('list_name'), self.params.get('list_type')
		list_type_name = 'Trakt My Lists' if list_type == 'my_lists' else 'Trakt Liked Lists' if list_type == 'liked_lists' else 'Trakt User Lists'
		random_list, cache_to_memory = get_persistent_content(self.database, '%s_%s' % (list_type, list_name), self.is_external)
		if not random_list:
			user, slug, list_id = self.params_get('user'), self.params_get('slug'), self.params_get('list_id')
			with_auth = list_type == 'my_lists'
			result = get_trakt_list_contents(list_type, user, slug, with_auth, list_id, skip_sort=True)
			random.shuffle(result)
			if paginate(self.is_external): result = random.sample(result, min(len(result), page_limit(self.is_external)))
			result = [dict(i, **{'order': c}) for c, i in enumerate(result)]
			url_params = {'base_list_name':list_type_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_trakt_list(url_params)
			if cache_to_memory: set_persistent_content(self.database, '%s_%s' % (list_type, list_name), {'name': list_name, 'result': result})
		else:
			list_name, result = random_list['name'], random_list['result']
			url_params = {'base_list_name':list_type_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_trakt_list(url_params)
		self.category_name = self.base_list_name or list_name or ''
		self.view_mode, self.content_type = 'view.%s' % content_type, content_type
		self.make_directory()

	def personal_lists_contents(self):
		from indexers.personal_lists import get_personal_list, build_personal_list
		list_name = self.params.get('list_name')
		random_list, cache_to_memory = get_persistent_content(self.database, '%s-%s' % (self.mode, list_name), self.is_external)
		if not random_list:
			result = get_personal_list(self.params)
			random.shuffle(result)
			if paginate(self.is_external): result = random.sample(result, min(len(result), page_limit(self.is_external)))
			result = [dict(i, **{'order': c}) for c, i in enumerate(result)]
			url_params = {'base_list_name':list_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_personal_list(url_params)
			if cache_to_memory: set_persistent_content(self.database, '%s-%s' % (self.mode, list_name), {'name': list_name, 'result': result})
		else:
			list_name, result = random_list['name'], random_list['result']
			url_params = {'base_list_name':list_name, 'list_name': list_name, 'result': result}
			content_type, self.list_items = build_personal_list(url_params)
		self.category_name = self.base_list_name or list_name or ''
		self.view_mode, self.content_type = 'view.%s' % content_type, content_type
		self.make_directory()

	def tmdb_lists_contents(self):
		from indexers.tmdb_lists import get_tmdb_list, build_tmdb_list
		list_id, list_name, media_type = self.params.get('list_id'), self.params.get('list_name')or self.params.get('name'), self.params.get('media_type')
		random_list, cache_to_memory = get_persistent_content(self.database, '%s_%s' % (self.mode, list_id), self.is_external)
		if not random_list:
			result = get_tmdb_list({'list_id': list_id, 'media_type': media_type})
			random.shuffle(result)
			if paginate(self.is_external): data = random.sample(result, min(len(result), page_limit(self.is_external)))
			else: data = random.sample(result, len(result))
			result = [dict(i, **{'order': c}) for c, i in enumerate(result)]
			url_params = {'base_list_name':list_name, 'list_id': list_id, 'result': result}
			content_type, self.list_items = build_tmdb_list(url_params)
			if cache_to_memory: set_persistent_content(self.database, '%s_%s' % (self.mode, list_id), {'name': list_name, 'result': result})
		else:
			list_name, result = random_list['name'], random_list['result']
			url_params = {'base_list_name':list_name, 'list_id': list_id, 'result': result}
			content_type, self.list_items = build_tmdb_list(url_params)
		self.category_name = self.base_list_name or list_name or ''
		self.view_mode, self.content_type = 'view.%s' % content_type, content_type
		self.make_directory()

	def random_discover(self):
		url = self.params_get('url', None)
		if not url: return
		random_list, cache_to_memory = get_persistent_content(self.database, url, self.is_external)
		if not random_list:
			list_function = self.get_function()
			threads = TaskPool().tasks(lambda x: self.random_results.extend(list_function(url, x)['results']), self.get_sample(), max_threads())
			[i.join() for i in threads]
			if paginate(self.is_external): random_list = random.sample(self.random_results, min(len(self.random_results), page_limit(self.is_external)))
			else: random_list = random.sample(self.random_results, len(self.random_results))
			if cache_to_memory: set_persistent_content(self.database, url, random_list)
		self.params['list'] = [i['id'] for i in random_list]
		self.list_items = self.function(self.params).worker()
		self.category_name = self.params_get('category_name', None) or self.base_list_name or ''
		self.make_directory()

	def make_directory(self, next_page_params={}):
		kodi_utils.add_items(self.handle, self.list_items)
		if next_page_params:
			kodi_utils.add_dir(self.handle, next_page_params, 'Browse Into %s >>' \
					% (next_page_params.get('category_name', None) or next_page_params.get('name', None) or self.content_type), 'nextpage', kodi_utils.get_icon('nextpage_landscape'))
		kodi_utils.set_content(self.handle, self.content_type)
		kodi_utils.set_category(self.handle, self.category_name)
		kodi_utils.end_directory(self.handle, cacheToDisc=False)
		if self.is_external:
			property_key = self.folder_name or self.base_list_name or random_list_property_key(self.params)
			if property_key: kodi_utils.set_property('redlight.%s' % property_key, self.category_name)
		else: kodi_utils.set_view_mode(self.view_mode, self.content_type, self.is_external)

	def get_function(self):
		if self.action in self.movie_most_watched + self.tvshow_most_watched:
			from modules.most_watched import normalize_most_watched_action
			return manual_function_import('modules.most_watched', normalize_most_watched_action(self.action))
		return manual_function_import('apis.%s_api' % self.action.split('_')[0], self.action)

	def get_sample(self):
		return random.sample(range(1, self.max_range), self.sample_size)

def _shortcut_item_is_random(item):
	if item.get('random') == 'true': return True
	mode = item.get('mode', '')
	if mode.startswith('random.'): return True
	action = item.get('action', '')
	if action in RandomLists.movie_special_main or action in RandomLists.tvshow_special_main:
		if not item.get('key_id') and not item.get('query'): return True
	return False

def random_shortcut_folders(folder_name, random_results):
	random_check = kodi_utils.random_valid_type_check()
	random_results = [i for i in random_results if i['mode'].replace('random.', '') in random_check]
	handle = int(sys.argv[1])
	if not random_results:
		kodi_utils.set_category(handle, folder_name)
		return kodi_utils.end_directory(handle)
	database = RandomWidgets()
	is_external = kodi_utils.external()
	random_list, cache_to_memory = get_persistent_content(database, 'random_shortcut_folders_%s' % folder_name, is_external)
	if not random_list:
		if len(random_results) > 1: random_list = random.choice(random_results)
		else: random_list = random_results[0]
		is_random_item = _shortcut_item_is_random(random_list)
		random_list.update({'folder_name': folder_name, 'mode': random_list['mode'].replace('random.', '')})
		if is_random_item: random_list['random'] = 'true'
		if cache_to_memory: set_persistent_content(database, 'random_shortcut_folders_%s' % folder_name, random_list)
	if _shortcut_item_is_random(random_list): return RandomLists(random_list).run_random()
	if random_list.get('action') in ('tmdb_movies_discover', 'tmdb_tv_discover'): return RandomLists(random_list).run_random()
	menu_type = random_check[random_list['mode']]
	list_name = random_list.get('list_name', None) or random_list.get('name', None) or 'Random'
	if is_external: kodi_utils.set_property('redlight.%s' % folder_name, list_name)
	if menu_type == 'movie':
		return Movies(random_list).fetch_list()
	if menu_type == 'tvshow':
		return TVShows(random_list).fetch_list()
	if menu_type == 'season':
		from indexers.seasons import build_season_list
		return build_season_list(random_list)
	if menu_type == 'episode':
		from indexers.episodes import build_episode_list
		return build_episode_list(random_list)
	if menu_type == 'single_episode':
		from indexers.episodes import build_single_episode
		return build_single_episode(kodi_utils.random_episodes_check()[random_list['mode']], random_list)
	if menu_type == 'trakt_list':
		from indexers.trakt_lists import build_trakt_list
		return build_trakt_list(random_list)
	if menu_type == 'personal_list':
		from indexers.personal_lists import build_personal_list
		return build_personal_list(random_list)
	if menu_type == 'tmdb_list':
		from indexers.tmdb_lists import build_tmdb_list
		return build_tmdb_list(random_list)
	if menu_type == 'mdblist_list':
		from indexers.mdblist_lists import build_mdbl_list
		return build_mdbl_list(random_list)
	return kodi_utils.end_directory(int(sys.argv[1]))
