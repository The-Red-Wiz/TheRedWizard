# -*- coding: utf-8 -*-
import calendar
import time
from threading import Thread
from caches.base_cache import connect_database
from modules import kodi_utils

# Keep local-only progress for a short window when PunchPlay /playback/in-progress
# has not caught up yet after stop (full-replace sync would otherwise wipe In Progress).
_LOCAL_PROGRESS_GRACE_SEC = 600

class PunchPlayCache:
	def get(self, string):
		try:
			dbcon = connect_database('punchplay_db')
			cache_data = dbcon.execute('SELECT data FROM punchplay_data WHERE id = ?', (string,)).fetchone()
			if cache_data: return eval(cache_data[0])
		except: pass
		return None

	def set(self, string, data):
		try:
			dbcon = connect_database('punchplay_db')
			dbcon.execute('INSERT OR REPLACE INTO punchplay_data (id, data) VALUES (?, ?)', (string, repr(data)))
		except: return None

	def delete(self, string):
		try:
			dbcon = connect_database('punchplay_db')
			dbcon.execute('DELETE FROM punchplay_data WHERE id = ?', (string,))
		except: pass

punchplay_cache = PunchPlayCache()

def _last_played_ts(last_played):
	if not last_played: return 0
	s = str(last_played).rstrip('Z').split('.')[0]
	try:
		if 'T' in s:
			return calendar.timegm(time.strptime(s, '%Y-%m-%dT%H:%M:%S'))
		return time.mktime(time.strptime(s, '%Y-%m-%d %H:%M:%S'))
	except Exception:
		return 0

def _merge_recent_local_progress(db_type, insert_list, key_fn):
	"""Preserve recent local-only progress rows missing from the remote replace set."""
	dbcon = connect_database('punchplay_db')
	remote_keys = {key_fn(i) for i in insert_list}
	cutoff = time.time() - _LOCAL_PROGRESS_GRACE_SEC
	keep = []
	try:
		rows = dbcon.execute(
			'SELECT db_type, media_id, season, episode, resume_point, curr_time, last_played, resume_id, title '
			'FROM progress WHERE db_type = ?', (db_type,)).fetchall()
	except Exception:
		return list(insert_list)
	for row in rows:
		if key_fn(row) in remote_keys:
			continue
		try:
			if float(row[4] or 0) <= 1:
				continue
		except Exception:
			continue
		if _last_played_ts(row[6]) >= cutoff:
			keep.append(tuple(row))
	if not keep:
		return list(insert_list)
	return list(insert_list) + keep

class PunchPlayWatched:
	def set_bulk_movie_watched(self, insert_list):
		self._delete('DELETE FROM watched WHERE db_type = ?', ('movie',))
		self._executemany('INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)

	def set_bulk_tvshow_watched(self, insert_list):
		self._delete('DELETE FROM watched WHERE db_type = ?', ('episode',))
		self._executemany('INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)

	def set_bulk_movie_progress(self, insert_list):
		merged = _merge_recent_local_progress('movie', insert_list, lambda r: str(r[1]))
		self._delete('DELETE FROM progress WHERE db_type = ?', ('movie',))
		self._executemany('INSERT OR IGNORE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', merged)

	def set_bulk_tvshow_progress(self, insert_list):
		merged = _merge_recent_local_progress(
			'episode', insert_list, lambda r: (str(r[1]), str(r[2]), str(r[3])))
		self._delete('DELETE FROM progress WHERE db_type = ?', ('episode',))
		self._executemany('INSERT OR IGNORE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', merged)

	def _executemany(self, command, insert_list):
		dbcon = connect_database('punchplay_db')
		dbcon.executemany(command, insert_list)

	def _delete(self, command, args):
		dbcon = connect_database('punchplay_db')
		dbcon.execute(command, args)
		# No VACUUM here — it rewrites the whole DB and blocks Next Episodes / list builds for many seconds.

punchplay_watched_cache = PunchPlayWatched()

def clear_all_punchplay_cache_data(silent=False, refresh=True):
	try:
		if not silent and not kodi_utils.confirm_dialog(): return False
		dbcon = connect_database('punchplay_db')
		dbcon.execute('DELETE FROM punchplay_data')
		dbcon.execute('DELETE FROM watched')
		dbcon.execute('DELETE FROM progress')
		try:
			from caches.lists_cache import lists_cache
			lists_cache.delete_like('punchplay_%')
		except: pass
		if not silent: kodi_utils.notification('PunchPlay Cache Cleared', 3000)
		if refresh:
			from apis.punchplay_api import punchplay_sync_activities
			Thread(target=punchplay_sync_activities, kwargs={'force_update': True}, daemon=True).start()
		return True
	except: return False
