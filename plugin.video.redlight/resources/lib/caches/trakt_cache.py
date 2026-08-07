# -*- coding: utf-8 -*-
from threading import Thread
from caches.base_cache import connect_database
from modules.kodi_utils import sleep, confirm_dialog, close_all_dialog, notification
# from modules.kodi_utils import logger

class TraktCache:	
	def get(self, string):
		result = None
		try:
			dbcon = connect_database('trakt_db')
			cache_data = dbcon.execute('SELECT data FROM trakt_data WHERE id = ?', (string,)).fetchone()
			if cache_data: result = eval(cache_data[0])
		except: pass
		return result

	def set(self, string, data):
		try:
			dbcon = connect_database('trakt_db')
			dbcon.execute('INSERT OR REPLACE INTO trakt_data (id, data) VALUES (?, ?)', (string, repr(data)))
		except: return None

	def delete(self, string):
		try:
			dbcon = connect_database('trakt_db')
			dbcon.execute('DELETE FROM trakt_data WHERE id = ?', (string,))
		except: pass

trakt_cache = TraktCache()

class TraktWatched():
	def set_bulk_tvshow_status(self, insert_list):
		self._delete('DELETE FROM watched_status', ())
		self._executemany('INSERT INTO watched_status VALUES (?, ?, ?)', insert_list)

	def set_tvshow_status(self, insert_dict):
		dbcon = connect_database('trakt_db')
		dbcon.execute('INSERT OR REPLACE INTO trakt_data (id, data) VALUES (?, ?)', ('trakt_tvshow_status', repr(insert_dict),))

	def set_bulk_movie_watched(self, insert_list):
		if not insert_list: return
		self._delete('DELETE FROM watched WHERE db_type = ?', ('movie',))
		self._executemany('INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)

	def set_bulk_tvshow_watched(self, insert_list):
		if not insert_list: return
		self._delete('DELETE FROM watched WHERE db_type = ?', ('episode',))
		self._executemany('INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)

	def set_bulk_movie_progress(self, insert_list):
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM progress WHERE db_type = ? AND resume_id != 0', ('movie',))
		if insert_list: dbcon.executemany('INSERT OR REPLACE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', insert_list)

	def set_bulk_tvshow_progress(self, insert_list):
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM progress WHERE db_type = ? AND resume_id != 0', ('episode',))
		if insert_list: dbcon.executemany('INSERT OR REPLACE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', insert_list)

	def _executemany(self, command, insert_list):
		dbcon = connect_database('trakt_db')
		dbcon.executemany(command, insert_list)

	def _delete(self, command, args):
		dbcon = connect_database('trakt_db')
		dbcon.execute(command, args)
		# No VACUUM here — rewrites the whole DB and can stall Next Episodes / list
		# rebuilds for many seconds after playback (esp. on SD / slow Android storage).
		# Manual Clear Cache / Clean Databases still vacuum.

trakt_watched_cache = TraktWatched()

def cache_trakt_object(function, string, url):
	cache = trakt_cache.get(string)
	if cache is not None: return cache
	result = function(url)
	trakt_cache.set(string, result)
	return result

def set_list_custom_sort(list_id, data):
	string = 'trakt_list_custom_sort_%s' % list_id
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('INSERT OR REPLACE INTO trakt_data (id, data) VALUES (?, ?)', (string, repr(data)))
		return True
	except: return False

def delete_list_custom_sort(list_id):
	string = 'trakt_list_custom_sort_%s' % list_id
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM trakt_data WHERE id=?', (string,))
		return True
	except: return False

def get_list_custom_sort(list_id):
	string = 'trakt_list_custom_sort_%s' % list_id
	try:
		dbcon = connect_database('trakt_db')
		cache_data = dbcon.execute('SELECT data FROM trakt_data WHERE id = ?', (string,)).fetchone()
		return eval(cache_data[0])
	except: return {}

def get_all_lists_custom_sort_strict():
	"""Every stored per-list custom sort. Raises on a locked database or a corrupt row.

	The one-time sort migration reads the store through this, not through the swallowing
	get_all_lists_custom_sort() below: an empty dict means "nothing stored" and lets the
	migration record itself as done, so a read failure that returned {} would look exactly
	like a clean success and delete every stored preference on the following sync.
	"""
	dbcon = connect_database('trakt_db')
	all_cache_data = dbcon.execute('SELECT data FROM trakt_data WHERE id LIKE %s' % "'trakt_list_custom_sort_%'").fetchall()
	all_cache_data = (eval(i[0]) for i in all_cache_data)
	return dict([(i['list_id'], {'sort_by': i['sort_by'], 'sort_how': i['sort_how']}) for i in all_cache_data])

def get_all_lists_custom_sort():
	try: return get_all_lists_custom_sort_strict()
	except: return {}

def valid_trakt_activities(data):
	return isinstance(data, dict) and 'all' in data and isinstance(data.get('movies'), dict) and isinstance(data.get('episodes'), dict)

def reset_activity(latest_activities):
	string = 'trakt_get_activity'
	try:
		dbcon = connect_database('trakt_db')
		data = dbcon.execute('SELECT data FROM trakt_data WHERE id = ?', (string,)).fetchone()
		if data:
			cached_data = eval(data[0])
			if not valid_trakt_activities(cached_data):
				cached_data = default_activities()
				dbcon.execute('DELETE FROM trakt_data WHERE id=?', (string,))
		else: cached_data = default_activities()
		if valid_trakt_activities(latest_activities):
			dbcon.execute('DELETE FROM trakt_data WHERE id=?', (string,))
			trakt_cache.set(string, latest_activities)
	except: cached_data = default_activities()
	return cached_data

def clear_daily_cache():
	clear_trakt_calendar()
	clear_trakt_list_data('my_lists')
	clear_trakt_list_data('liked_lists')
	clear_trakt_list_data('user_lists')
	clear_trakt_list_contents_data('my_lists')
	clear_trakt_list_contents_data('liked_lists')
	clear_trakt_list_contents_data('user_lists')

def clear_trakt_hidden_data(list_type):
	string = 'trakt_hidden_items_%s' % list_type
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM trakt_data WHERE id=?', (string,))
	except: pass

def clear_trakt_collection_watchlist_data(list_type, media_type):
	if media_type == 'movies': media_type = 'movie'
	if media_type in ('tvshows', 'shows'): media_type = 'tvshow'
	string = 'trakt_%s_%s' % (list_type, media_type)
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM trakt_data WHERE id=?', (string,))
	except: pass

def clear_trakt_calendar():
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM trakt_data WHERE id LIKE "%s"' % 'trakt_get_my_calendar_%')
	except: return

def clear_trakt_list_contents_data(list_type):
	string = 'trakt_list_contents_' + list_type + '_%'
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM trakt_data WHERE id LIKE "%s"' % string)
	except: pass

def clear_trakt_list_data(list_type):
	string = 'trakt_%s' % list_type
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM trakt_data WHERE id=?', (string,))
	except: pass

def clear_trakt_recommendations():
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM trakt_data WHERE id LIKE "%s"' % 'trakt_recommendations_%')
	except: return

def clear_trakt_favorites():
	try:
		dbcon = connect_database('trakt_db')
		dbcon.execute('DELETE FROM trakt_data WHERE id LIKE "%s"' % 'trakt_favorites_%')
	except: return

def clear_all_trakt_cache_data(silent=False, refresh=True):
	try:
		if not silent and not confirm_dialog(): return False
		from caches.main_cache import main_cache
		main_cache_dbcon = connect_database('maincache_db')
		lists_with_media = main_cache_dbcon.execute('SELECT id FROM maincache WHERE id LIKE %s' % "'trakt_lists_with_media_%'").fetchall()
		for item in lists_with_media:
			try: main_cache.delete(item[0])
			except: pass
		main_cache.clean_database()
		dbcon = connect_database('trakt_db')
		for table in ('progress', 'watched', 'watched_status'): dbcon.execute('DELETE FROM %s' % table)
		dbcon.execute('DELETE FROM trakt_data WHERE id NOT LIKE %s' % "'trakt_list_custom_sort_%'")
		dbcon.execute('VACUUM')
		if not silent: notification('Trakt Cache Cleared', 3000)
		if refresh:
			from apis.trakt_api import trakt_sync_activities
			Thread(target=trakt_sync_activities, kwargs={'force_update': True}).start()
		return True
	except: return False

def default_activities():
	return {
			'all': '2024-01-22T00:22:21.000Z',
			'movies':
				{
				'watched_at': '2020-01-01T00:00:01.000Z',
				'collected_at': '2020-01-01T00:00:01.000Z',
				'rated_at': '2020-01-01T00:00:01.000Z',
				'watchlisted_at': '2020-01-01T00:00:01.000Z',
				'favorited_at': '2020-01-01T00:00:01.000Z',
				'recommendations_at': '2020-01-01T00:00:01.000Z',
				'commented_at': '2020-01-01T00:00:01.000Z',
				'paused_at': '2020-01-01T00:00:01.000Z',
				'hidden_at': '2020-01-01T00:00:01.000Z'
				},
			'episodes':
				{
				'watched_at': '2020-01-01T00:00:01.000Z',
				'collected_at': '2020-01-01T00:00:01.000Z',
				'rated_at': '2020-01-01T00:00:01.000Z',
				'watchlisted_at': '2020-01-01T00:00:01.000Z',
				'commented_at': '2020-01-01T00:00:01.000Z',
				'paused_at': '2020-01-01T00:00:01.000Z'
				},
			'shows':
				{
				'rated_at': '2020-01-01T00:00:01.000Z',
				'watchlisted_at': '2020-01-01T00:00:01.000Z',
				'favorited_at': '2020-01-01T00:00:01.000Z',
				'recommendations_at': '2020-01-01T00:00:01.000Z',
				'commented_at': '2020-01-01T00:00:01.000Z',
				'dropped_at': '2020-01-01T00:00:01.000Z'
				},
			'seasons':
				{
				'rated_at': '2020-01-01T00:00:01.000Z',
				'watchlisted_at': '2020-01-01T00:00:01.000Z',
				'commented_at': '2020-01-01T00:00:01.000Z',
				'hidden_at': '2020-01-01T00:00:01.000Z'
				},
			'comments':
				{
				'liked_at': '2020-01-01T00:00:01.000Z',
				'blocked_at': '2020-01-01T00:00:01.000Z'
				},
			'lists':
				{
				'liked_at': '2020-01-01T00:00:01.000Z',
				'updated_at': '2020-01-01T00:00:01.000Z',
				'commented_at': '2020-01-01T00:00:01.000Z'
				},
			'watchlist':
				{
				'updated_at': '2020-01-01T00:00:01.000Z'
				},
			'favorites':
				{
				'updated_at': '2020-01-01T00:00:01.000Z'
				},
			'recommendations':
				{
				'updated_at': '2020-01-01T00:00:01.000Z'
				},
			'collaborations':
				{
				'updated_at': '2020-01-01T00:00:01.000Z'
				},
			'account':
				{
				'settings_at': '2020-01-01T00:00:01.000Z',
				'followed_at': '2020-01-01T00:00:01.000Z',
				'following_at': '2020-01-01T00:00:01.000Z',
				'pending_at': '2020-01-01T00:00:01.000Z',
				'requested_at': '2020-01-01T00:00:01.000Z'
				},
			'saved_filters':
				{
				'updated_at': '2020-01-01T00:00:01.000Z'
				},
			'notes':
				{
				'updated_at': '2020-01-01T00:00:01.000Z'
				}
			}
	