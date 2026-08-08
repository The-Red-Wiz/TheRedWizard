# -*- coding: utf-8 -*-
import datetime
from caches.meta_cache import cache_function
from caches.lists_cache import lists_cache_object
from modules.settings import get_meta_filter, tmdb_api_key, lists_cache_duraton
from modules.kodi_utils import make_session, remove_keys
# from modules.kodi_utils import logger

session = make_session('https://api.themoviedb.org/3')

def tmdb_dict_removals():
	return ('adult', 'backdrop_path', 'genre_ids', 'original_language', 'original_title', 'overview', 'popularity', 'vote_count', 'video', 'origin_country', 'original_name')

def no_api_key():
	from modules.kodi_utils import notification
	notification('Please set a valid TMDb API Key')
	return []

def movie_details(tmdb_id, api_key):
	try:
		url = 'https://api.themoviedb.org/3/movie/%s?api_key=%s&language=en&append_to_response=external_ids,videos,credits,release_dates,alternative_titles,translations,' \
		'images,keywords&include_image_language=en,null' % (tmdb_id, api_key)
		return get_tmdb(url).json()
	except: return None

def tvshow_details(tmdb_id, api_key):
	try:
		url = 'https://api.themoviedb.org/3/tv/%s?api_key=%s&language=en&append_to_response=external_ids,videos,credits,content_ratings,alternative_titles,translations,' \
		'images,keywords&include_image_language=en,null' % (tmdb_id, api_key)
		return get_tmdb(url).json()
	except: return None

def episode_groups_data(tmdb_id):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'episode_groups_data_%s' % tmdb_id
	url = 'https://api.themoviedb.org/3/tv/%s/episode_groups?api_key=%s' % (tmdb_id, api_key)
	return cache_function(get_tmdb, string, url, expiration=168)

def episode_group_details(group_id):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'episode_groups_details_%s' % group_id
	url = 'https://api.themoviedb.org/3/tv/episode_group/%s?api_key=%s' % (group_id, api_key)
	return cache_function(get_tmdb, string, url, expiration=168)

def movie_set_details(collection_id, api_key):
	try:
		url = 'https://api.themoviedb.org/3/collection/%s?api_key=%s&language=en' % (collection_id, api_key)
		return get_tmdb(url).json()
	except: return None

def movie_external_id(external_source, external_id, api_key):
	try:
		string = 'movie_external_id_%s_%s' % (external_source, external_id)
		url = 'https://api.themoviedb.org/3/find/%s?api_key=%s&external_source=%s' % (external_id, api_key, external_source)
		result = cache_function(get_tmdb, string, url)
		result = result['movie_results']
		if result: return result[0]
		else: return None
	except: return None

def tvshow_external_id(external_source, external_id, api_key):
	try:
		string = 'tvshow_external_id_%s_%s' % (external_source, external_id)
		url = 'https://api.themoviedb.org/3/find/%s?api_key=%s&external_source=%s' % (external_id, api_key, external_source)
		result = cache_function(get_tmdb, string, url)
		tv_results = result.get('tv_results') or []
		if tv_results: return tv_results[0]
		# Season-split anime IMDb ids often map to an episode/season, not the show record.
		for key in ('tv_episode_results', 'tv_season_results'):
			for row in result.get(key) or []:
				show_id = row.get('show_id')
				if show_id: return {'id': show_id}
		return None
	except: return None

def tmdb_movies_oscar_winners(page_no):
	from modules.meta_lists import oscar_winners
	return oscar_winners()[page_no-1]

def tmdb_network_details(network_id):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_network_details_%s' % network_id
	url = 'https://api.themoviedb.org/3/network/%s?api_key=%s' % (network_id, api_key)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_keywords_by_query(query, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_keywords_by_query_%s_%s' % (query, page_no)
	url = 'https://api.themoviedb.org/3/search/keyword?api_key=%s&query=%s&page=%s' % (api_key, query, page_no)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_collections_by_query(query, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_collections_by_query_%s_%s' % (query, page_no)
	url = 'https://api.themoviedb.org/3/search/collection?api_key=%s&language=en-US&query=%s&page=%s' % (api_key, query, page_no)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_movie_keywords(tmdb_id):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movie_keywords_%s' % tmdb_id
	url = 'https://api.themoviedb.org/3/movie/%s/keywords?api_key=%s' % (tmdb_id, api_key)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_tv_keywords(tmdb_id):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_keywords_%s' % tmdb_id
	url = 'https://api.themoviedb.org/3/tv/%s/keywords?api_key=%s' % (tmdb_id, api_key)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_movie_keyword_results(tmdb_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movie_keyword_results_%s_%s' % (tmdb_id, page_no)
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&with_keywords=%s&page=%s' % (api_key, tmdb_id, page_no)
	return lists_cache_object(get_data, string, url, expiration=96)

def tmdb_tv_keyword_results(tmdb_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_keyword_results_%s_%s' % (tmdb_id, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&language=en-US&with_keywords=%s&page=%s' % (api_key, tmdb_id, page_no)
	return lists_cache_object(get_data, string, url, expiration=96)

def tmdb_movie_keyword_results_direct(query, page_no):
	if tmdb_api_key() in (None, 'empty_setting', ''): return no_api_key()
	try:
		results = tmdb_movie_keyword_results(tmdb_keywords_by_query(query, page_no)['results'][0]['id'], page_no)
		results['total_pages'] = 1
		return results
	except: return None

def tmdb_tv_keyword_results_direct(query, page_no):
	if tmdb_api_key() in (None, 'empty_setting', ''): return no_api_key()
	try:
		results = tmdb_tv_keyword_results(tmdb_keywords_by_query(query, page_no)['results'][0]['id'], page_no)
		results['total_pages'] = 1
		return results
	except: return None

def tmdb_company_id(query):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_company_id_%s' % query
	url = 'https://api.themoviedb.org/3/search/company?api_key=%s&query=%s' % (api_key, query)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_media_images(media_type, tmdb_id):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	if media_type in ('movie', 'movies'): media_type = 'movie'
	else: media_type = 'tv'
	string = 'tmdb_media_images_%s_%s' % (media_type, tmdb_id)
	url = 'https://api.themoviedb.org/3/%s/%s/images?include_image_language=en,null&api_key=%s' % (media_type, tmdb_id, api_key)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_media_videos(media_type, tmdb_id):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	if media_type in ('movie', 'movies'): media_type = 'movie'
	else: media_type = 'tv'
	string = 'tmdb_media_videos_%s_%s' % (media_type, tmdb_id)
	url = 'https://api.themoviedb.org/3/%s/%s/videos?api_key=%s' % (media_type, tmdb_id, api_key)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_movies_discover(query, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	if '[current_date]' in query: query = query.replace('[current_date]', get_current_date())
	if '[random]' in query: query = query.replace('[random]', '')
	string = url = query + '&api_key=%s&page=%s' % (api_key, page_no)
	return lists_cache_object(get_tmdb, string, url, json=True, expiration=min(lists_cache_duraton(), 24))

def tmdb_movies_popular(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_popular_%s' % page_no
	url = 'https://api.themoviedb.org/3/movie/popular?api_key=%s&language=en-US&region=US&with_original_language=en&page=%s' % (api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_popular_today(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_popular_today_%s' % page_no
	url = 'https://api.themoviedb.org/3/trending/movie/day?api_key=%s&language=en-US&region=US&with_original_language=en&page=%s' % (api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_blockbusters(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_blockbusters_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&with_original_language=en&sort_by=revenue.desc&page=%s' % (api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_in_theaters(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_in_theaters_%s' % page_no
	url = 'https://api.themoviedb.org/3/movie/now_playing?api_key=%s&language=en-US&region=US&with_original_language=en&page=%s' % (api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_upcoming(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, future_date = get_dates(31, reverse=False)
	string = 'tmdb_movies_upcoming_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&with_original_language=en&release_date.gte=%s&release_date.lte=%s' \
	'&with_release_type=3|2|1&page=%s' % (api_key, current_date, future_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_latest_releases(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, previous_date = get_dates(31, reverse=True)
	string = 'tmdb_movies_latest_releases_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&with_original_language=en&release_date.gte=%s&release_date.lte=%s' \
	'&with_release_type=4|5|6&page=%s' % (api_key, previous_date, current_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_premieres(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, previous_date = get_dates(31, reverse=True)
	string = 'tmdb_movies_premieres_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&with_original_language=en&release_date.gte=%s&release_date.lte=%s' \
	'&with_release_type=1|3|2&page=%s' % (api_key, previous_date, current_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_genres(genre_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_genres_%s_%s' % (genre_id, page_no)
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&with_genres=%s&language=en-US&region=US&with_original_language=en&sort_by=popularity.desc&release_date.lte=%s&page=%s' \
			% (api_key, genre_id, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_languages(language, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_languages_%s_%s' % (language, page_no)
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&with_original_language=%s&sort_by=popularity.desc&release_date.lte=%s&page=%s' \
			% (api_key, language, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_certifications(certification, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_certifications_%s_%s' % (certification, page_no)
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&with_original_language=en' \
	'&certification_country=US&certification=%s&sort_by=popularity.desc&release_date.lte=%s&page=%s' % (api_key, certification, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_year(year, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_year_%s_%s' % (year, page_no)
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&sort_by=popularity.desc&language=en-US&region=US&with_original_language=en&primary_release_year=%s&page=%s' \
							% (api_key, year, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_decade(decade, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_decade_%s_%s' % (decade, page_no)
	start = '%s-01-01' % decade
	end = get_dates(2)[0] if decade == '2020' else '%s-12-31' % str(int(decade) + 9)
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&sort_by=popularity.desc&language=en-US&region=US&with_original_language=en&primary_release_date.gte=%s' \
			'&primary_release_date.lte=%s&page=%s' % (api_key, start, end, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_providers(provider, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_providers_%s_%s' % (provider, page_no)
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&sort_by=popularity.desc&watch_region=US&with_watch_providers=%s&page=%s' % (api_key, provider, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_recommendations(tmdb_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_recommendations_%s_%s' % (tmdb_id, page_no)
	url = 'https://api.themoviedb.org/3/movie/%s/recommendations?api_key=%s&language=en-US&region=US&with_original_language=en&page=%s' % (tmdb_id, api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_search(query, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	meta_filter = get_meta_filter()
	string = 'tmdb_movies_search_%s_%s_%s' % (query, meta_filter, page_no)
	url = 'https://api.themoviedb.org/3/search/movie?api_key=%s&language=en-US&include_adult=%s&query=%s&page=%s' % (api_key, meta_filter, query, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_movies_companies(company_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_movies_companies_%s_%s' % (company_id, page_no)
	url = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&sort_by=popularity.desc&language=en-US&region=US&with_original_language=en&with_companies=%s&page=%s' \
							% (api_key, company_id, page_no)
	return lists_cache_object(get_data, string, url, expiration=168)

def tmdb_movies_reviews(tmdb_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	url = 'https://api.themoviedb.org/3/movie/%s/reviews?api_key=%s&page=%s' % (tmdb_id, api_key, page_no)
	return get_tmdb(url).json()

def tmdb_tv_discover(query, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	if '[current_date]' in query: query = query.replace('[current_date]', get_current_date())
	if '[random]' in query: query = query.replace('[random]', '')
	string = url = query + '&api_key=%s&page=%s' % (api_key, page_no)
	return lists_cache_object(get_tmdb, string, url, json=True, expiration=min(lists_cache_duraton(), 24))

def tmdb_tv_popular(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_popular_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&language=en-US&region=US&with_original_language=en' \
	'&without_keywords=210024&page=%s' % (api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_popular_today(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, previous_date = get_dates(180, reverse=True)
	string = 'tmdb_tv_popular_today_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&language=en-US&region=US&with_original_language=en&without_keywords=210024' \
	'&include_null_first_air_dates=false&first_air_date.gte=%s' \
	'&first_air_date.lte=%s&page=%s' % (api_key, previous_date, current_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_premieres(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, previous_date = get_dates(31, reverse=True)
	string = 'tmdb_tv_premieres_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&language=en-US&region=US&with_original_language=en&include_null_first_air_dates=false' \
	'&first_air_date.gte=%s&first_air_date.lte=%s&without_keywords=210024&page=%s' % (api_key, previous_date, current_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_airing_today(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	expiration = min(lists_cache_duraton(), 24)
	string = 'tmdb_tv_airing_today_%s' % page_no
	url = 'https://api.themoviedb.org/3/tv/airing_today?api_key=%s&language=en-US&region=US&with_original_language=en&without_keywords=210024&page=%s' \
	% (api_key, page_no)
	return lists_cache_object(get_data, string, url, expiration=expiration)

def tmdb_tv_on_the_air(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_on_the_air_%s' % page_no
	url = 'https://api.themoviedb.org/3/tv/on_the_air?api_key=%s&language=en-US&region=US&with_original_language=en&without_keywords=210024&page=%s' \
	% (api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_upcoming(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, future_date = get_dates(31, reverse=False)
	string = 'tmdb_tv_upcoming_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&language=en-US&region=US&with_original_language=en&without_keywords=210024' \
	'&first_air_date.gte=%s&first_air_date.lte=%s&page=%s' % (api_key, current_date, future_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_genres(genre_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_genres_%s_%s' % (genre_id, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&with_genres=%s&language=en-US&region=US&with_original_language=en' \
	'&include_null_first_air_dates=false&first_air_date.lte=%s&without_keywords=210024&page=%s' % (api_key, genre_id, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_languages(language, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_languages_%s_%s' % (language, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&language=en-US&include_null_first_air_dates=false&with_original_language=%s&first_air_date.lte=%s' \
	'&without_keywords=210024&page=%s' % (api_key, language, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_networks(network_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_networks_%s_%s' % (network_id, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&language=en-US&region=US&with_original_language=en&include_null_first_air_dates=false' \
	'&with_networks=%s&first_air_date.lte=%s&without_keywords=210024&page=%s' % (api_key, network_id, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_providers(provider, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_providers_%s_%s' % (provider, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&watch_region=US&with_watch_providers=%s&include_null_first_air_dates=false' \
	'&first_air_date.lte=%s&without_keywords=210024&page=%s' % (api_key, provider, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_year(year, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_year_%s_%s' % (year, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&language=en-US&region=US&with_original_language=en&include_null_first_air_dates=false' \
	'&first_air_date_year=%s&without_keywords=210024&page=%s' % (api_key, year, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_decade(decade, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_decade_%s_%s' % (decade, page_no)
	start = '%s-01-01' % decade
	end = get_dates(2)[0] if decade == '2020' else '%s-12-31' % str(int(decade) + 9)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&language=en-US&region=US&with_original_language=en&include_null_first_air_dates=false' \
	'&first_air_date.gte=%s&first_air_date.lte=%s&without_keywords=210024&page=%s' % (api_key, start, end, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_recommendations(tmdb_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_recommendations_%s_%s' % (tmdb_id, page_no)
	url = 'https://api.themoviedb.org/3/tv/%s/recommendations?api_key=%s&language=en-US&region=US&with_original_language=en&page=%s' % (tmdb_id, api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_search(query, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	meta_filter = get_meta_filter()
	string = 'tmdb_tv_search_%s_%s_%s' % (query, meta_filter, page_no)
	url = 'https://api.themoviedb.org/3/search/tv?api_key=%s&language=en-US&include_adult=%s&query=%s&page=%s' % (api_key, meta_filter, query, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_tv_reviews(tmdb_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	url = 'https://api.themoviedb.org/3/tv/%s/reviews?api_key=%s&page=%s' % (tmdb_id, api_key, page_no)
	return get_tmdb(url).json()

def tmdb_anime_popular(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_anime_popular_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&with_keywords=210024&page=%s' % (api_key, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_anime_popular_recent(page_no):
	from modules.meta_lists import years_tvshows
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_tv_anime_popular_recent_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&with_keywords=210024&sort_by=first_air_date.desc&include_null_first_air_dates=false&first_air_date_year=%s&page=%s' \
							% (api_key, years_tvshows()[0]['id'], page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_anime_premieres(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, previous_date = get_dates(93, reverse=True)
	string = 'tmdb_anime_premieres_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&with_keywords=210024&include_null_first_air_dates=false&first_air_date.gte=%s&first_air_date.lte=%s&page=%s' \
							% (api_key, previous_date, current_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_anime_upcoming(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, future_date = get_dates(93, reverse=False)
	string = 'tmdb_anime_upcoming_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&with_keywords=210024&first_air_date.gte=%s&first_air_date.lte=%s&sort_by=first_air_date.asc&page=%s' \
							% (api_key, current_date, future_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_anime_on_the_air(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	current_date, future_date = get_dates(7, reverse=False)
	string = 'tmdb_anime_on_the_air_%s' % page_no
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&with_keywords=210024&air_date.gte=%s&air_date.lte=%s&page=%s' \
							% (api_key, current_date, future_date, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_anime_genres(genre_id, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_anime_genres_%s_%s' % (genre_id, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&with_keywords=210024&with_genres=%s&include_null_first_air_dates=false&first_air_date.lte=%s&page=%s' \
							% (api_key, genre_id, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_anime_providers(provider, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_anime_providers2_%s_%s' % (provider, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&sort_by=popularity.desc&with_keywords=210024&watch_region=US&with_watch_providers=%s&include_null_first_air_dates=false' \
	'&first_air_date.lte=%s&page=%s' % (api_key, provider, get_current_date(), page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_anime_year(year, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_anime_year_%s_%s' % (year, page_no)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&with_keywords=210024&include_null_first_air_dates=false&first_air_date_year=%s&page=%s' % (api_key, year, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_anime_decade(decade, page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_anime_decade_%s_%s' % (decade, page_no)
	start = '%s-01-01' % decade
	end = get_dates(2)[0] if decade == '2020' else '%s-12-31' % str(int(decade) + 9)
	url = 'https://api.themoviedb.org/3/discover/tv?api_key=%s&with_keywords=210024&include_null_first_air_dates=false&first_air_date.gte=%s' \
			'&first_air_date.lte=%s&page=%s' % (api_key, start, end, page_no)
	return lists_cache_object(get_data, string, url)

def tmdb_popular_people(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_people_popular_%s' % page_no
	url = 'https://api.themoviedb.org/3/person/popular?api_key=%s&language=en&page=%s' % (api_key, page_no)
	return cache_function(get_tmdb, string, url, expiration=48)

def tmdb_trending_people_day(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_people_trending_day_%s' % page_no
	url = 'https://api.themoviedb.org/3/trending/person/day?api_key=%s&page=%s' % (api_key, page_no)
	return cache_function(get_tmdb, string, url, expiration=48)

def tmdb_trending_people_week(page_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_people_trending_week_%s' % page_no
	url = 'https://api.themoviedb.org/3/trending/person/week?api_key=%s&page=%s' % (api_key, page_no)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_people_full_info(actor_id):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	string = 'tmdb_people_full_info_%s' % actor_id
	url = 'https://api.themoviedb.org/3/person/%s?api_key=%s&language=en&append_to_response=external_ids,combined_credits,images,tagged_images' % (actor_id, api_key)
	return cache_function(get_tmdb, string, url, expiration=168)

def tmdb_people_info(query, page_no=1):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	meta_filter = get_meta_filter()
	string = 'tmdb_people_info_%s_%s_%s' % (query, meta_filter, page_no)
	url = 'https://api.themoviedb.org/3/search/person?api_key=%s&language=en&include_adult=%s&query=%s&page=%s' % (api_key, meta_filter, query, page_no)
	return cache_function(get_tmdb, string, url, expiration=4)

def season_episodes_details(tmdb_id, season_no):
	api_key = tmdb_api_key()
	if api_key in (None, 'empty_setting', ''): return no_api_key()
	try:
		url = 'https://api.themoviedb.org/3/tv/%s/season/%s?api_key=%s&language=en&append_to_response=credits' % (tmdb_id, season_no, api_key)
		return get_tmdb(url).json()
	except: return None

def get_dates(days, reverse=True):
	current_date = get_current_date(return_str=False)
	if reverse: new_date = (current_date - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
	else: new_date = (current_date + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
	return str(current_date), new_date

def get_current_date(return_str=True):
	if return_str: return str(datetime.date.today())
	else: return datetime.date.today()

def get_reviews_data(media_type, tmdb_id):
	def builder(media_type, tmdb_id):
		reviews_list, all_data = [], []
		template = '[B]%02d. %s%s[/B][CR][CR]%s'
		media_type = 'movie' if media_type in ('movie', 'movies') else 'tv'
		function = tmdb_movies_reviews if media_type  == 'movie' else tmdb_tv_reviews
		next_page, total_pages = 1, 1
		while next_page <= total_pages:
			data = function(tmdb_id, next_page)
			all_data += data['results']
			total_pages = data['total_pages']
			next_page = data['page'] + 1
		if all_data:
			for count, item in enumerate(all_data, 1):
				try:
					user = item['author'].upper()
					rating = item['author_details'].get('rating')
					if rating: rating = ' - %s/10' % str(rating).split('.')[0]
					else: rating = ''
					content = template % (count, user, rating, item['content'])
					reviews_list.append(content)
				except: pass
		return reviews_list
	string, url = 'tmdb_%s_reviews_%s' % (media_type ,tmdb_id), [media_type, tmdb_id]
	return cache_function(builder, string, url, json=False, expiration=168)

def get_data(url):
	return get_tmdb(url).json()

def get_tmdb(url):
	try: response = session.get(url, timeout=20.0)
	except: response = None
	return response
