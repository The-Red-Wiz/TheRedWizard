# -*- coding: utf-8 -*-
from threading import Thread
from caches.base_cache import connect_database
from modules import kodi_utils

class SimklCache:
	def get(self, string):
		try:
			dbcon = connect_database('simkl_db')
			cache_data = dbcon.execute('SELECT data FROM simkl_data WHERE id = ?', (string,)).fetchone()
			if cache_data: return eval(cache_data[0])
		except: pass
		return None

	def set(self, string, data):
		try:
			dbcon = connect_database('simkl_db')
			dbcon.execute('INSERT OR REPLACE INTO simkl_data (id, data) VALUES (?, ?)', (string, repr(data)))
		except: return None

	def delete(self, string):
		try:
			dbcon = connect_database('simkl_db')
			dbcon.execute('DELETE FROM simkl_data WHERE id = ?', (string,))
		except: pass

simkl_cache = SimklCache()

class SimklWatched:
	def set_bulk_movie_watched(self, insert_list):
		self._delete('DELETE FROM watched WHERE db_type = ?', ('movie',))
		self._executemany('INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)

	def set_bulk_tvshow_watched(self, insert_list):
		self._delete('DELETE FROM watched WHERE db_type = ?', ('episode',))
		self._executemany('INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)

	def merge_bulk_movie_watched(self, insert_list):
		"""Upsert movie watched rows from a date_from delta (does not wipe the table)."""
		if not insert_list: return
		self._executemany('INSERT OR REPLACE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)

	def merge_bulk_tvshow_watched(self, insert_list, touched_media_ids=None):
		"""Replace watched episodes for shows present in a date_from delta.

		Clears each touched media_id first so unwatched/removed episodes drop locally.
		"""
		ids = set(str(i) for i in (touched_media_ids or []))
		if not ids and insert_list:
			ids = set(str(i[1]) for i in insert_list)
		if not ids: return
		dbcon = connect_database('simkl_db')
		for media_id in ids:
			dbcon.execute('DELETE FROM watched WHERE db_type = ? AND media_id = ?', ('episode', media_id))
		if insert_list:
			dbcon.executemany('INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)

	def set_bulk_movie_progress(self, insert_list):
		self._delete('DELETE FROM progress WHERE db_type = ?', ('movie',))
		self._executemany('INSERT OR IGNORE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', insert_list)

	def set_bulk_tvshow_progress(self, insert_list):
		self._delete('DELETE FROM progress WHERE db_type = ?', ('episode',))
		self._executemany('INSERT OR IGNORE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', insert_list)

	def _executemany(self, command, insert_list):
		dbcon = connect_database('simkl_db')
		dbcon.executemany(command, insert_list)

	def _delete(self, command, args):
		dbcon = connect_database('simkl_db')
		dbcon.execute(command, args)
		# No VACUUM here — same as PunchPlay/Trakt watched writes: full rewrite blocks
		# Next Episodes / list builds after playback on slow storage. Clear Cache still vacuums.

simkl_watched_cache = SimklWatched()

def reset_activity(latest_activities):
	string = 'simkl_get_activity'
	try:
		dbcon = connect_database('simkl_db')
		data = dbcon.execute('SELECT data FROM simkl_data WHERE id = ?', (string,)).fetchone()
		cached_data = eval(data[0]) if data else default_activities()
		dbcon.execute('DELETE FROM simkl_data WHERE id=?', (string,))
		simkl_cache.set(string, latest_activities)
	except: cached_data = default_activities()
	return cached_data

def default_activities():
	return {'all': '2020-01-01T00:00:01.000Z', 'movies': {'completed': '2020-01-01T00:00:01.000Z', 'playback': '2020-01-01T00:00:01.000Z', 'removed_from_list': '2020-01-01T00:00:01.000Z'},
		'tv_shows': {'completed': '2020-01-01T00:00:01.000Z', 'playback': '2020-01-01T00:00:01.000Z', 'removed_from_list': '2020-01-01T00:00:01.000Z'}}

def clear_all_simkl_cache_data(silent=False, refresh=True):
	try:
		if not silent and not kodi_utils.confirm_dialog(): return False
		dbcon = connect_database('simkl_db')
		dbcon.execute('DELETE FROM simkl_data')
		dbcon.execute('DELETE FROM watched')
		dbcon.execute('DELETE FROM progress')
		dbcon.execute('VACUUM')
		try:
			from caches.lists_cache import lists_cache
			lists_cache.delete_like('simkl_all_items_%')
		except: pass
		if not silent: kodi_utils.notification('Simkl Cache Cleared', 3000)
		if refresh:
			from apis.simkl_api import simkl_sync_activities
			Thread(target=simkl_sync_activities, kwargs={'force_update': True}).start()
		return True
	except: return False
