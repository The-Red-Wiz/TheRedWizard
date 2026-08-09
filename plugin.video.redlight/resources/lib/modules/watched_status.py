# -*- coding: utf-8 -*-
from datetime import datetime
from threading import Thread
from apis.trakt_api import trakt_watched_status_mark, trakt_official_status, trakt_progress, trakt_get_hidden_items
from apis.simkl_api import simkl_watched_status_mark, simkl_progress, simkl_official_status
from apis.mdblist_api import mdblist_watched_status_mark, mdblist_progress, mdblist_official_status
from apis.punchplay_api import punchplay_watched_status_mark, punchplay_progress, punchplay_official_status
from caches.base_cache import connect_database, database
from caches.trakt_cache import clear_trakt_collection_watchlist_data
from modules.kodi_utils import kodi_progress_background, sleep, get_video_database_path, notification, kodi_refresh, logger, translate_path
from modules.utils import get_datetime, adjust_premiered_date, sort_for_article, TaskPool
from modules import metadata, settings
# from modules.kodi_utils import logger

def get_database(watched_indicators=None):
	return connect_database({0: 'watched_db', 1: 'trakt_db', 2: 'simkl_db', 3: 'mdblist_db', 4: 'punchplay_db'}[watched_indicators if watched_indicators is not None else settings.watched_indicators()])

# def cache_watched_tvshow_status(function, status_type, watched_indicators=None):
# 	watched_indicators = watched_indicators or settings.watched_indicators()
# 	dbcon = get_database(watched_indicators)
# 	cache = dbcon.execute('SELECT media_id, status FROM watched_status WHERE db_type = ?', (status_type,)).fetchone()
# 	if cache is not None:
# 		expiration, result = cache
# 		if int(expiration) > get_timestamp(): return eval(result)
# 		clear_cache_watched_tvshow_status(watched_indicators, (status_type,))
# 	result = function(status_type)
# 	dbcon.execute('INSERT OR REPLACE INTO watched_status VALUES (?, ?, ?)', (status_type, get_timestamp(12), repr(result)))
# 	return result or []

# def clear_cache_watched_tvshow_status(watched_indicators=None, status_types=('watched', 'progress')):
# 	try:
# 		watched_indicators = watched_indicators or settings.watched_indicators()
# 		dbcon = get_database()
# 		for status in status_types: dbcon.execute('DELETE FROM watched_status WHERE db_type = ?', (status,))
# 		dbcon.execute('VACUUM')
# 		return True
# 	except: return False

def get_hidden_progress_items(watched_indicators):
	try:
		if watched_indicators == 0:
			watched_db = get_database()
			watched_info = watched_db.execute('SELECT status FROM watched_status WHERE db_type = ?', ('hidden_progress_items',)).fetchone()[0]
			return eval(watched_info) or []
		elif watched_indicators == 2:
			from apis.simkl_api import simkl_get_dropped_items
			return simkl_get_dropped_items()
		elif watched_indicators == 3:
			from apis.mdblist_api import mdblist_get_dropped_items
			return mdblist_get_dropped_items()
		elif watched_indicators == 4:
			from apis.punchplay_api import punchplay_get_dropped_items
			return punchplay_get_dropped_items()
		else: return trakt_get_hidden_items('dropped')
	except: return []

def update_hidden_progress(media_id):
	watched_indicators = settings.watched_indicators()
	current_hidden = get_hidden_progress_items(watched_indicators)
	new_hidden = [i for i in current_hidden if i != int(media_id)]
	if new_hidden == current_hidden: return
	if watched_indicators == 0: function = hide_unhide_progress_items
	elif watched_indicators == 2:
		from apis.simkl_api import simkl_hide_unhide_progress_items as function
	elif watched_indicators == 3:
		from apis.mdblist_api import mdblist_hide_unhide_progress_items as function
	elif watched_indicators == 4:
		from apis.punchplay_api import punchplay_hide_unhide_progress_items as function
	else: from apis.trakt_api import hide_unhide_progress_items as function
	function({'action': 'undrop', 'media_type': 'shows', 'media_id': media_id, 'section': 'dropped', 'refresh': 'false'})

def hide_unhide_progress_items(params):
	action, media_id, refresh = params['action'], int(params.get('media_id', '0')), params.get('refresh', 'true') == 'true'
	current_items = get_hidden_progress_items(0) or []
	if action == 'drop': current_items.append(media_id)
	else: current_items.remove(media_id)
	watched_db = get_database()
	watched_info = watched_db.execute('INSERT OR REPLACE INTO watched_status VALUES (?, ?, ?)', ('hidden_progress_items', 'hidden', repr(current_items),))
	if refresh: kodi_refresh()

def get_last_played_value(watched_indicators):
	if watched_indicators == 0: return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	else: return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')

def make_batch_insert(action, media_type, media_id, season, episode, last_played, title):
	if action == 'mark_as_watched': return (media_type, media_id, season, episode, last_played, title)
	else: return (media_type, media_id, season, episode)

def refresh_container(refresh=True):
	if refresh: kodi_refresh()

def _schedule_playback_widget_refresh(from_playback):
	if from_playback:
		from modules.kodi_utils import schedule_playback_widget_refresh
		schedule_playback_widget_refresh()

def count_aired_episodes(meta, season=None, current_date=None, adjust_hours=None):
	"""Count episodes that have aired using the same premiered rules as episode lists.

	Keeps season/show episode totals in line with unaired colouring (TMDb date + 20:00 + UTC offset).
	If season is set, only that season is counted. Specials follow Exclude Specials from Progress.
	"""
	from modules.metadata import episodes_meta
	from modules.utils import adjust_premiered_date, get_datetime
	if not meta: return 0
	if current_date is None: current_date = get_datetime()
	if adjust_hours is None: adjust_hours = settings.date_offset()
	exclude_specials = settings.exclude_specials_from_progress()
	season_data = meta.get('season_data') or []
	if season is not None:
		seasons = [int(season)]
	else:
		seasons = sorted({int(i.get('season_number', 0)) for i in season_data
			if i.get('season_number') is not None and not (exclude_specials and int(i.get('season_number', 0)) == 0)})
	count = 0
	for snum in seasons:
		if exclude_specials and snum == 0: continue
		try: eps = episodes_meta(snum, meta) or []
		except Exception: eps = []
		for ep in eps:
			premiered = ep.get('premiered')
			if not premiered: continue
			try:
				ep_date = adjust_premiered_date(premiered, adjust_hours)[0]
			except Exception:
				continue
			if ep_date and ep_date <= current_date:
				count += 1
	return count

def progress_aired_eps(meta):
	"""Aired episode total used for show-level In Progress / Watched / progress %."""
	total = meta.get('total_aired_eps') or 0
	status = meta.get('status', '')
	# Still-airing: recount with premiered-date rules so totals match unaired colouring
	# (TMDb last_episode_to_air often lags same-day releases).
	if status not in ('Ended', 'Canceled'):
		try:
			return count_aired_episodes(meta)
		except Exception:
			return total
	if not settings.exclude_specials_from_progress(): return total
	extra_info = meta.get('extra_info') or {}
	last_ep = extra_info.get('last_episode_to_air')
	season_data = meta.get('season_data') or []
	if not season_data: return total
	# Ended/Canceled: count through last aired only so placeholder seasons (e.g. S2E1 with no
	# air date while last_episode_to_air is still S1 finales) do not inflate the total.
	if last_ep and status in ('Ended', 'Canceled'):
		try:
			last_s, last_e = int(last_ep['season_number']), int(last_ep['episode_number'])
			prior = sum(i.get('episode_count', 0) for i in season_data if 0 < i.get('season_number', 0) < last_s)
			cur = next((i for i in season_data if i.get('season_number') == last_s), None)
			cur_count = (cur or {}).get('episode_count') or 0
			if last_e <= cur_count: return prior + last_e
			return (prior + cur_count) or total
		except Exception:
			pass
	regular = sum(i.get('episode_count', 0) for i in season_data if i.get('season_number', 0) != 0)
	return regular if regular else total

def active_tvshows_information(status_type):
	def _process(item):
		media_id = item['media_id']
		meta = metadata.tvshow_meta('tmdb_id', media_id, api_key, mpaa_region, get_datetime())
		watched_status = get_watched_status_tvshow(watched_info.get(str(media_id)), progress_aired_eps(meta))[0]
		airing_status = meta.get('status', '')
		if status_type == 'watched':
			if watched_status == 1:
				if not include_other and airing_status not in ('Ended', 'Canceled'): return
				results_append(item)
		else:
			if watched_status == 0: results_append(item)
			elif include_other and airing_status not in ('Ended', 'Canceled'): results_append(item)
	results = []
	results_append = results.append
	watched_indicators = settings.watched_indicators()
	watched_info = watched_info_tvshow()
	if status_type == 'progress':
		hidden_items = get_hidden_progress_items(settings.watched_indicators())
		for k in hidden_items: watched_info.pop(str(k), None)
	api_key, mpaa_region = settings.tmdb_api_key(), settings.mpaa_region()
	watched_items = watched_info.items()
	data = [v for k, v in watched_items]
	progress_location = settings.tv_progress_location()
	if status_type == 'watched': include_other = progress_location in (0, 2)
	else: include_other = progress_location in (1, 2)
	threads = TaskPool().tasks(_process, data, min(len(data), settings.max_threads()))
	[i.join() for i in threads]
	return results

def watched_info_movie(watched_db=None):
	if not watched_db: watched_db = get_database()
	try:
		watched_info = watched_db.execute('SELECT media_id, title, last_played FROM watched WHERE db_type = ?', ('movie',)).fetchall()
		return dict([(i[0], {'media_id': i[0], 'title': i[1], 'last_played': i[2]}) for i in watched_info])
	except: return {}

def get_watched_status_movie(watched_info, media_id):
	if not watched_info: return 0
	try:
		watched = 1 if media_id in watched_info else 0
		return watched
	except: return 0

def get_bookmarks_movie(watched_db=None):
	if not watched_db: watched_db = get_database()
	try:
		info = watched_db.execute('SELECT media_id, resume_point, curr_time, resume_id FROM progress WHERE db_type = ?', ('movie',)).fetchall()
		info = dict([(i[0], {'media_id': i[0], 'resume_point': i[1], 'curr_time': i[2], 'resume_id': i[3]}) for i in info])
	except: info = {}
	return info

def meaningful_progress_percent(resume_point):
	"""Return rounded percent string only when progress is >1% (In Progress shelf threshold).

	Providers can leave a 0%/≤1% playback row after reset; string '0' is truthy in Python
	and would still show Red Light's Resume / Start over prompt.
	"""
	try:
		percent = float(resume_point)
		if percent > 1: return str(round(percent))
	except: pass
	return None

def get_progress_status_movie(progress_info, media_id):
	try: return meaningful_progress_percent(progress_info[media_id]['resume_point'])
	except: return None

def watched_info_tvshow(watched_db=None):
	if not watched_db: watched_db = get_database()
	try:
		if settings.exclude_specials_from_progress():
			data = watched_db.execute(
				'SELECT media_id, season, episode, title, MAX(last_played), '
				'SUM(CASE WHEN CAST(season AS INTEGER) > 0 THEN 1 ELSE 0 END) AS COUNTER '
				'FROM watched WHERE db_type = ? GROUP BY media_id '
				'HAVING SUM(CASE WHEN CAST(season AS INTEGER) > 0 THEN 1 ELSE 0 END) > 0',
				('episode',)).fetchall()
		else:
			data = watched_db.execute(
				'SELECT media_id, season, episode, title, MAX(last_played), COUNT(*) AS COUNTER '
				'FROM watched WHERE db_type = ? GROUP BY media_id',
				('episode',)).fetchall()
		return dict([(str(i[0]), {'media_id': str(i[0]), 'season': i[1], 'episode': i[2], 'title': i[3], 'last_played': i[4], 'total_played': i[5]}) for i in data])
	except: return {}

def get_watched_status_tvshow(watched_info, aired_eps):
	if not watched_info: return 0, 0, aired_eps
	try:
		watched = min(watched_info['total_played'], aired_eps)
		unwatched = aired_eps - watched
		if watched >= aired_eps: playcount = 1
		else: playcount = 0
		return playcount, watched, unwatched
	except: return 0, 0, aired_eps

def get_progress_status_tvshow(watched, aired_eps):
	try: progress = int((float(watched)/aired_eps)*100) or 1
	except: progress = 1
	return progress

def watched_info_season(media_id, watched_db=None):
	if not watched_db: watched_db = get_database()
	try: watched_info = dict(watched_db.execute('SELECT season, COUNT(*) AS COUNTER FROM watched WHERE db_type = ? AND media_id = ? GROUP BY media_id, season',
							('episode', str(media_id))).fetchall())
	except: watched_info = {}
	return watched_info

def get_watched_status_season(watched_info, aired_eps):
	if not watched_info: return 0, 0, aired_eps
	try:
		watched = min(watched_info, aired_eps)
		unwatched = aired_eps - watched
		if watched >= aired_eps: playcount = 1
		else: playcount = 0
		return playcount, watched, unwatched
	except: return 0, 0, aired_eps

def get_progress_status_season(watched, aired_eps):
	try: progress = int((float(watched)/aired_eps)*100)
	except: progress = 0
	return progress

def watched_info_episode(media_id, watched_db=None):
	if not watched_db: watched_db = get_database()
	try: watched_info = watched_db.execute('SELECT season, episode FROM watched WHERE db_type = ? AND media_id = ?', ('episode', str(media_id))).fetchall()
	except: watched_info = []
	return watched_info

def get_watched_status_episode(watched_info, season_episode):
	try:
		season, episode = int(season_episode[0]), int(season_episode[1])
	except:
		return 0
	for row in watched_info:
		try:
			if int(row[0]) == season and int(row[1]) == episode:
				return 1
		except:
			pass
	return 0

def get_bookmarks_episode(media_id, season, watched_db=None):
	if not watched_db: watched_db = get_database()
	try:
		info = watched_db.execute('SELECT resume_point, curr_time, resume_id, episode FROM progress WHERE db_type = ? AND media_id = ? AND season = ?',
			('episode', str(media_id), int(season))).fetchall()
		info = dict([(i[3], {'resume_point': i[0], 'curr_time': i[1], 'resume_id': i[2]}) for i in info])
	except: info = {}
	return info

def get_bookmarks_all_episode(media_id, total_seasons, watched_db=None):
	if not watched_db: watched_db = get_database()
	all_seasons_info = {}
	for season in range(1, total_seasons + 1):
		try:
			season_info = get_bookmarks_episode(media_id, season, watched_db)
			all_seasons_info[season] = season_info
		except: pass
	return all_seasons_info

def get_progress_status_episode(progress_info, episode):
	try: return meaningful_progress_percent(progress_info[episode]['resume_point'])
	except: return None

def get_progress_status_all_episode(progress_info, season, episode):
	try: return meaningful_progress_percent(progress_info[season][episode]['resume_point'])
	except: return None

def get_resume_seconds(progress, duration):
	return float(int(float(progress)/100 * duration))

def apply_listitem_progress(info_tag, set_properties, progress, duration, is_external=False):
	"""Expose progress to skins without making the row Kodi-resumable.

	Never set a non-zero InfoTag resume on directory listitems. Also force
	resume to 0 so Kodi does not treat the row as resumable from a stale
	MyVideos bookmark for the same plugin:// path (that dialog runs before
	the plugin is invoked — skipping setResumePoint alone is not enough).
	WatchedProgress keeps skin bars; Red Light's source dialog is the resume prompt.
	"""
	try: info_tag.setResumePoint(0.0)
	except: pass
	if not meaningful_progress_percent(progress): return
	set_properties({'WatchedProgress': progress})

def clear_local_bookmarks():
	"""Remove Kodi MyVideos bookmarks for Red Light plugin paths.

	Kodi stores resume by filename for plugin:// URLs (via setResolvedUrl) and can
	show Resume / Start over on the home widget before scrape. Clear every non-empty
	MyVideos*.db — the version map alone can miss the live DB (e.g. empty 124 vs 131).
	"""
	import os
	db_dir = translate_path('special://profile/Database')
	paths = set()
	try:
		paths.add(get_video_database_path())
	except Exception:
		pass
	try:
		for name in os.listdir(db_dir):
			if name.startswith('MyVideos') and name.endswith('.db'):
				path = os.path.join(db_dir, name)
				try:
					if os.path.getsize(path) > 0: paths.add(path)
				except Exception:
					pass
	except Exception:
		pass
	for path in paths:
		try:
			dbcon = database.connect(path)
			try:
				file_ids = dbcon.execute(
					"SELECT idFile FROM files WHERE strFilename LIKE '%plugin.video.redlight%'").fetchall()
			except Exception:
				dbcon.close()
				continue
			if file_ids:
				for i in ('bookmark', 'streamdetails', 'files'):
					try: dbcon.executemany("DELETE FROM %s WHERE idFile=?" % i, file_ids)
					except Exception: pass
				try: dbcon.commit()
				except Exception: pass
			dbcon.close()
		except Exception:
			pass

def clear_listitem_kodi_resume(info_tag):
	"""Force directory rows non-resumable for Kodi's native prompt."""
	try: info_tag.setResumePoint(0.0)
	except: pass

def _write_local_progress(watched_indicators, media_type, tmdb_id, season, episode, resume_point, curr_time, title):
	if media_type == 'movie': season, episode = '', ''
	last_played = get_last_played_value(watched_indicators)
	dbcon = get_database(watched_indicators)
	dbcon.execute('INSERT OR REPLACE INTO progress VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
				(media_type, str(tmdb_id), season, episode, str(resume_point), str(curr_time), last_played, 0, title))

def erase_bookmark(media_type, media_id, season='', episode='', refresh='false', watched_indicators=None):
	try:
		if watched_indicators is None: watched_indicators = settings.watched_indicators()
		watched_db = get_database(watched_indicators)
		if watched_indicators == 1:
			try:
				if media_type == 'episode': resume_id = get_bookmarks_episode(str(media_id), season, watched_db)[int(episode)]['resume_id']
				else: resume_id = get_bookmarks_movie(watched_db)[str(media_id)]['resume_id']
				sleep(1000)
				trakt_progress('clear_progress', media_type, media_id, 0, season, episode, resume_id)
			except: pass
		elif watched_indicators == 2:
			try:
				if media_type == 'episode': resume_id = get_bookmarks_episode(str(media_id), season, watched_db)[int(episode)]['resume_id']
				else: resume_id = get_bookmarks_movie(watched_db)[str(media_id)]['resume_id']
				sleep(1000)
				simkl_progress('clear_progress', media_type, media_id, 0, season, episode, resume_id)
			except: pass
		elif watched_indicators == 3:
			try:
				if media_type == 'episode': resume_id = get_bookmarks_episode(str(media_id), season, watched_db)[int(episode)]['resume_id']
				else: resume_id = get_bookmarks_movie(watched_db)[str(media_id)]['resume_id']
				sleep(1000)
				mdblist_progress('clear_progress', media_type, media_id, 0, season, episode, resume_id)
			except: pass
		elif watched_indicators == 4:
			try:
				if media_type == 'episode': resume_id = get_bookmarks_episode(str(media_id), season, watched_db)[int(episode)]['resume_id']
				else: resume_id = get_bookmarks_movie(watched_db)[str(media_id)]['resume_id']
				sleep(1000)
				punchplay_progress('clear_progress', media_type, media_id, 0, season, episode, resume_id)
			except: pass
		watched_db.execute('DELETE FROM progress where db_type = ? and media_id = ? and season = ? and episode = ?', (media_type, media_id, season, episode))
		refresh_container(refresh == 'true')
	except: pass

def batch_erase_bookmark(watched_indicators, insert_list, action):
	try:
		watched_db = get_database(watched_indicators)
		if action == 'mark_as_watched': modified_list = [(i[0], i[1], i[2], i[3]) for i in insert_list]
		else: modified_list = insert_list
		if watched_indicators in (1, 2, 3, 4):
			if watched_indicators == 1: progress_fn = trakt_progress
			elif watched_indicators == 2: progress_fn = simkl_progress
			elif watched_indicators == 3: progress_fn = mdblist_progress
			else: progress_fn = punchplay_progress
			def _process():
				for i in insert_list:
					try:
						media_id, season, episode = i[1], i[2], i[3]
						resume_id = get_bookmarks_episode(str(media_id), season, watched_db)[int(episode)]['resume_id']
						sleep(1000)
						progress_fn('clear_progress', i[0], i[1], 0, i[2], i[3], resume_id)
					except: pass
			Thread(target=_process).start()
		watched_db.executemany('DELETE FROM progress where db_type = ? and media_id = ? and season = ? and episode = ?', modified_list)
	except: pass

def set_bookmark(params, remote=True):
	'''Write resume progress. remote=False writes local DB only (playback stop path).'''
	try:
		media_type, tmdb_id, curr_time, total_time = params.get('media_type'), params.get('tmdb_id'), params.get('curr_time'), params.get('total_time')
		refresh = False if params.get('from_playback', 'false') == 'true' else True
		title, season, episode = params.get('title'), params.get('season'), params.get('episode')
		adjusted_current_time = float(curr_time) - 5
		resume_point = round(adjusted_current_time/float(total_time)*100,1)
		watched_indicators = settings.watched_indicators()
		_write_local_progress(watched_indicators, media_type, tmdb_id, season, episode, resume_point, curr_time, title)
		if not remote:
			return
		if watched_indicators == 1 and trakt_official_status(media_type):
			trakt_progress('set_progress', media_type, tmdb_id, resume_point, season, episode, refresh_trakt=False)
		elif watched_indicators == 2 and simkl_official_status(media_type):
			simkl_progress('set_progress', media_type, tmdb_id, resume_point, season, episode, refresh_simkl=False)
		elif watched_indicators == 3 and mdblist_official_status(media_type):
			mdblist_progress('set_progress', media_type, tmdb_id, resume_point, season, episode, refresh_mdblist=False)
		elif watched_indicators == 4 and punchplay_official_status(media_type):
			punchplay_progress('set_progress', media_type, tmdb_id, resume_point, season, episode, refresh_punchplay=False)
		if params.get('from_playback', 'false') == 'true': _schedule_playback_widget_refresh(True)
		else: refresh_container(refresh)
	except: pass

def mark_movie(params):
	action, media_type = params.get('action'), 'movie'
	refresh, from_playback = params.get('refresh', 'true') == 'true', params.get('from_playback', 'false') == 'true'
	if from_playback: refresh = False
	tmdb_id, title = params.get('tmdb_id'), params.get('title')
	watched_indicators = settings.watched_indicators()
	if watched_indicators == 1:
		if from_playback and trakt_official_status(media_type) == False: sleep(1000)
		elif not trakt_watched_status_mark(action, 'movies', tmdb_id) and not from_playback: return notification('Error')
		clear_trakt_collection_watchlist_data('watchlist', media_type)
	elif watched_indicators == 2:
		if from_playback and simkl_official_status(media_type) == False: sleep(1000)
		elif not simkl_watched_status_mark(action, 'movie', tmdb_id) and not from_playback: return notification('Error')
	elif watched_indicators == 3:
		if from_playback and mdblist_official_status(media_type) == False: sleep(1000)
		elif not mdblist_watched_status_mark(action, 'movie', tmdb_id) and not from_playback: return notification('Error')
	elif watched_indicators == 4:
		if from_playback and punchplay_official_status(media_type) == False: sleep(1000)
		elif not punchplay_watched_status_mark(action, 'movie', tmdb_id, title=title, year=params.get('year')) and not from_playback:
			return notification('Error')
	watched_status_mark(watched_indicators, media_type, tmdb_id, action, title=title)
	_schedule_playback_widget_refresh(from_playback)
	refresh_container(refresh)
	if not from_playback: notification('Success')

def mark_tvshow(params):
	title, action, tmdb_id = params.get('title', ''), params.get('action'), params.get('tmdb_id')
	try: tvdb_id = int(params.get('tvdb_id', '0'))
	except: tvdb_id = 0
	watched_indicators = settings.watched_indicators()
	progress_backround = kodi_progress_background()
	progress_backround.create('[B]Please Wait..[/B]', '')
	if watched_indicators == 1:
		if not trakt_watched_status_mark(action, 'shows', tmdb_id, tvdb_id): return notification('Error')
		clear_trakt_collection_watchlist_data('watchlist', 'tvshow')
	elif watched_indicators == 2:
		if not simkl_watched_status_mark(action, 'tvshow', tmdb_id, tvdb_id): return notification('Error')
	elif watched_indicators == 3:
		if not mdblist_watched_status_mark(action, 'tvshow', tmdb_id, tvdb_id): return notification('Error')
	elif watched_indicators == 4:
		if not punchplay_watched_status_mark(action, 'tvshow', tmdb_id, tvdb_id, title=title, year=params.get('year')):
			return notification('Error')
	current_date = get_datetime()
	insert_list = []
	insert_append = insert_list.append
	meta = metadata.tvshow_meta('tmdb_id', tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
	season_data = meta['season_data']
	season_data = [i for i in season_data if i['season_number'] > 0]
	total = len(season_data)
	last_played = get_last_played_value(watched_indicators)
	for count, item in enumerate(season_data, 1):
		season_number = item['season_number']
		ep_data = metadata.episodes_meta(season_number, meta)
		for ep in ep_data:
			season_number = ep['season']
			ep_number = ep['episode']
			display = '%s - S%.2dE%.2d' % (title, int(season_number), int(ep_number))
			progress_backround.update(int(float(count)/float(total)*100), '[B]Please Wait..[/B]', display)
			episode_date, premiered = adjust_premiered_date(ep['premiered'], settings.date_offset())
			if episode_date and current_date < episode_date: continue
			insert_append(make_batch_insert(action, 'episode', tmdb_id, season_number, ep_number, last_played, title))
	batch_watched_status_mark(watched_indicators, insert_list, action)
	progress_backround.close()
	refresh_container()
	notification('Success')

def mark_season(params):
	season = int(params.get('season'))
	if season == 0: return notification('Failed')
	insert_list = []
	insert_append = insert_list.append
	action, title, tmdb_id = params.get('action'), params.get('title'), params.get('tmdb_id')
	try: tvdb_id = int(params.get('tvdb_id', '0'))
	except: tvdb_id = 0
	watched_indicators = settings.watched_indicators()
	heading = '[B]Mark Watched %s[/B]' if action == 'mark_as_watched' else '[B]Mark Unwatched %s[/B]'
	if watched_indicators == 1:
		if not trakt_watched_status_mark(action, 'season', tmdb_id, tvdb_id, season): return notification('Error')
		clear_trakt_collection_watchlist_data('watchlist', 'tvshow')
	elif watched_indicators == 2:
		if not simkl_watched_status_mark(action, 'season', tmdb_id, tvdb_id, season): return notification('Error')
	elif watched_indicators == 3:
		if not mdblist_watched_status_mark(action, 'season', tmdb_id, tvdb_id, season): return notification('Error')
	elif watched_indicators == 4:
		if not punchplay_watched_status_mark(action, 'season', tmdb_id, tvdb_id, season, title=title, year=params.get('year')):
			return notification('Error')
	progress_backround = kodi_progress_background()
	progress_backround.create('[B]Please Wait..[/B]', '')
	current_date = get_datetime()
	meta = metadata.tvshow_meta('tmdb_id', tmdb_id, settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
	ep_data = metadata.episodes_meta(season, meta)
	last_played = get_last_played_value(watched_indicators)
	for count, item in enumerate(ep_data, 1):
		season_number = item['season']
		ep_number = item['episode']
		display = '%s - S%.2dE%.2d' % (title, season_number, ep_number)
		episode_date, premiered = adjust_premiered_date(item['premiered'], settings.date_offset())
		if episode_date and current_date < episode_date: continue
		progress_backround.update(int(float(count) / float(len(ep_data)) * 100), '[B]Please Wait..[/B]', display)
		insert_append(make_batch_insert(action, 'episode', tmdb_id, season_number, ep_number, last_played, title))
	batch_watched_status_mark(watched_indicators, insert_list, action)
	progress_backround.close()
	refresh_container()
	notification('Success')

def mark_episode(params):
	season, episode, title = int(params.get('season')), int(params.get('episode')), params.get('title')
	if season == 0: return notification('Failed')
	action, media_type = params.get('action'), 'episode'
	refresh, from_playback = params.get('refresh', 'true') == 'true', params.get('from_playback', 'false') == 'true'
	if from_playback: refresh = False
	tmdb_id = params.get('tmdb_id')
	try: tvdb_id = int(params.get('tvdb_id', '0'))
	except: tvdb_id = 0
	watched_indicators = settings.watched_indicators()
	if watched_indicators == 1:
		if from_playback and trakt_official_status(media_type) == False: sleep(1000)
		elif not trakt_watched_status_mark(action, media_type, tmdb_id, tvdb_id, season, episode) and not from_playback:
			return notification('Error')
		clear_trakt_collection_watchlist_data('watchlist', 'tvshow')
	elif watched_indicators == 2:
		if from_playback and simkl_official_status(media_type) == False: sleep(1000)
		elif not simkl_watched_status_mark(action, media_type, tmdb_id, tvdb_id, season, episode) and not from_playback: return notification('Error')
	elif watched_indicators == 3:
		if from_playback and mdblist_official_status(media_type) == False: sleep(1000)
		elif not mdblist_watched_status_mark(action, media_type, tmdb_id, tvdb_id, season, episode) and not from_playback: return notification('Error')
	elif watched_indicators == 4:
		if from_playback and punchplay_official_status(media_type) == False: sleep(1000)
		elif not punchplay_watched_status_mark(
				action, media_type, tmdb_id, tvdb_id, season, episode, title=title, year=params.get('year')
				) and not from_playback:
			return notification('Error')
	watched_status_mark(watched_indicators, media_type, tmdb_id, action, season, episode, title)
	update_hidden_progress(tmdb_id)
	_schedule_playback_widget_refresh(from_playback)
	refresh_container(refresh)
	if not from_playback: notification('Success')

def unmark_previous_episode(params):
	try:
		season, episode = int(params.get('season')), int(params.get('episode'))
		if episode == 1:
			season = params['season'] = season - 1
			meta = metadata.tvshow_meta('tmdb_id', params.get('tmdb_id'), settings.tmdb_api_key(), settings.mpaa_region(), get_datetime())
			params['episode'] = episode = next((i for i in meta['season_data'] if i['season_number'] == season))['episode_count']
		else: episode = params['episode'] = episode - 1
		return mark_episode(params)
	except: notification('Error')

def _invalidate_nextep_list_cache():
	# Soft no-op: activity_token already changes on mark watched / progress writes.
	# Hard-deleting packets forced a full Next Episodes rebuild and blocked incremental
	# reuse of clean show rows from the stale payload.
	return

def watched_status_mark(watched_indicators, media_type='', media_id='', action='', season='', episode='', title=''):
	try:
		last_played = get_last_played_value(watched_indicators)
		dbcon = get_database(watched_indicators)
		if action == 'mark_as_watched':
			dbcon.execute('INSERT OR REPLACE INTO watched VALUES (?, ?, ?, ?, ?, ?)', (media_type, media_id, season, episode, last_played, title))
		elif action == 'mark_as_unwatched':
			dbcon.execute('DELETE FROM watched WHERE (db_type = ? and media_id = ? and season = ? and episode = ?)', (media_type, media_id, season, episode))
		erase_bookmark(media_type, media_id, season, episode)
		if media_type == 'episode': _invalidate_nextep_list_cache()
		# if media_type == 'episode': clear_cache_watched_tvshow_status()
	except: notification('Error')

def batch_watched_status_mark(watched_indicators, insert_list, action):
	try:
		dbcon = get_database(watched_indicators)
		if action == 'mark_as_watched':
			dbcon.executemany('INSERT OR IGNORE INTO watched VALUES (?, ?, ?, ?, ?, ?)', insert_list)
		elif action == 'mark_as_unwatched':
			dbcon.executemany('DELETE FROM watched WHERE (db_type = ? and media_id = ? and season = ? and episode = ?)', insert_list)
		batch_erase_bookmark(watched_indicators, insert_list, action)
		_invalidate_nextep_list_cache()
		# clear_cache_watched_tvshow_status()
	except: notification('Error')

def get_next_episodes(nextep_content, watched_indicators=None):
	watched_db = get_database(watched_indicators)
	if nextep_content == 0:
		sql = '''WITH cte AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY media_id ORDER BY season DESC, episode DESC) rn FROM watched WHERE db_type = ?)
				SELECT media_id, season, episode, title, last_played FROM cte WHERE rn = 1'''
	else:
		sql = '''WITH cte AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY media_id ORDER BY last_played DESC) rn FROM watched WHERE db_type = ?)
				SELECT media_id, season, episode, title, last_played FROM cte WHERE rn = 1'''
	data = watched_db.execute(sql, ('episode',)).fetchall()
	data = [{'media_ids': {'tmdb': int(i[0])}, 'season': int(i[1]), 'episode': int(i[2]), 'title': i[3], 'last_played': i[4]} for i in data]
	data.sort(key=lambda x: (x['last_played']), reverse=True)
	return data

def _season_episode_numbers(meta, season_number):
	"""Actual TMDb episode numbers for a season (supports absolute numbering e.g. One Piece S23E1170)."""
	try:
		from modules.metadata import episodes_meta
		eps = episodes_meta(season_number, meta) or []
		return sorted({int(e['episode']) for e in eps if e.get('episode') not in (None, '')})
	except Exception:
		return []

def _next_season_numbers(season_data, after_season):
	try:
		return sorted(i['season_number'] for i in (season_data or []) if i.get('season_number', 0) > after_season)
	except Exception:
		return []

def _find_next_unwatched_episode(season, episode, watched_info, season_data, meta=None):
	try:
		if meta is not None:
			seasons = sorted({i['season_number'] for i in (season_data or []) if i.get('season_number', 0) >= season})
			for item_season in seasons:
				nums = _season_episode_numbers(meta, item_season)
				if not nums: continue
				candidates = [n for n in nums if n > episode] if item_season == season else nums
				for n in candidates:
					if not get_watched_status_episode(watched_info, (item_season, n)):
						return item_season, n
			return None, None
		# Legacy relative 1..episode_count path (no meta).
		relevant_seasons = [i for i in season_data if i['season_number'] >= season]
		for item in relevant_seasons:
			episode_count, item_season = item['episode_count'], item['season_number']
			if season == item_season:
				if episode >= episode_count:
					continue
				episode_range = range(episode + 1, episode_count + 1)
			else:
				episode_range = range(1, episode_count + 1)
			next_episode = next((i for i in episode_range if not get_watched_status_episode(watched_info, (item_season, i))), None)
			if next_episode:
				return item_season, next_episode
	except: pass
	return None, None

def get_next(season, episode, watched_info, season_data, nextep_content, meta=None):
	"""Return (season, episode) for the next episode after the given watched S/E.

	When meta is provided, episode numbers come from TMDb season episode lists so shows that use
	absolute numbering inside seasons (e.g. One Piece S23E1156+) resolve correctly. Without meta,
	falls back to treating episodes as 1..episode_count (legacy).
	"""
	if episode == 0:
		if meta is not None:
			nums = _season_episode_numbers(meta, season)
			if nums: return season, nums[0]
		return season, 1
	if nextep_content == 0:
		try:
			if meta is not None:
				nums = _season_episode_numbers(meta, season)
				later = [n for n in nums if n > episode]
				if later: return season, later[0]
				for ns in _next_season_numbers(season_data, season):
					nnums = _season_episode_numbers(meta, ns)
					if nnums: return ns, nnums[0]
				return None, None
			episode_count = next((i['episode_count'] for i in season_data if i['season_number'] == season), None)
			season = season if episode < episode_count else season + 1
			episode = episode + 1 if episode < episode_count else 1
		except Exception:
			return None, None
	else:
		season, episode = _find_next_unwatched_episode(season, episode, watched_info, season_data, meta)
	return season, episode

def _movie_progress_list(dbcon):
	data = dbcon.execute('SELECT media_id, title, last_played, resume_point FROM progress WHERE db_type = ?', ('movie',)).fetchall()
	return [{'media_id': i[0], 'title': i[1], 'last_played': i[2]} for i in data if i[0] and float(i[3] or 0) > 1]

def _refresh_trakt_movie_progress():
	try:
		if settings.watched_indicators() != 1 or not settings.trakt_user_active(): return
		from modules.kodi_utils import boot_trakt_list_refresh_allowed
		if not boot_trakt_list_refresh_allowed(): return
		from apis.trakt_api import trakt_playback_progress, trakt_progress_movies
		trakt_progress_movies(trakt_playback_progress())
	except: pass

def _refresh_simkl_tvshow_watched():
	# Activity-gated (same as SimklMonitor / TV show lists) — skip full watched pull when unchanged.
	try:
		if settings.watched_indicators() != 2 or not settings.simkl_user_active(): return
		from apis.simkl_api import simkl_sync_activities
		simkl_sync_activities()
	except: pass

def _refresh_simkl_progress():
	# Activity-gated playback refresh — parity with Trakt/MDBList/PunchPlay on In Progress open.
	try:
		if settings.watched_indicators() != 2 or not settings.simkl_user_active(): return
		from apis.simkl_api import simkl_sync_activities
		simkl_sync_activities()
	except: pass

def _purge_negligible_progress(dbcon):
	# Drop leftover ≤1% rows so local DB matches In Progress / resume thresholds.
	try: dbcon.execute('DELETE FROM progress WHERE CAST(resume_point AS FLOAT) <= 1')
	except: pass

def _refresh_mdblist_watched():
	# Activity-gated (same as MDBListMonitor / TV show lists) — skip full watched pull when unchanged.
	try:
		if settings.watched_indicators() != 3 or not settings.mdblist_user_active(): return
		from apis.mdblist_api import mdblist_sync_activities
		mdblist_sync_activities()
	except: pass

def _refresh_mdblist_tvshow_watched():
	_refresh_mdblist_watched()

def _refresh_mdblist_movie_progress():
	try:
		if settings.watched_indicators() != 3 or not settings.mdblist_user_active(): return
		from apis.mdblist_api import mdblist_sync_activities
		mdblist_sync_activities()
	except: pass

def _refresh_mdblist_episode_progress():
	try:
		if settings.watched_indicators() != 3 or not settings.mdblist_user_active(): return
		from apis.mdblist_api import mdblist_sync_activities
		mdblist_sync_activities()
	except: pass

def _refresh_punchplay_watched():
	# Change-feed gated (same idea as Simkl/MDBList activities) — skip full history when unchanged.
	try:
		if settings.watched_indicators() != 4 or not settings.punchplay_user_active(): return
		# Set by punchplay_watched_status_mark so Container.Refresh after mark/unmark does not
		# block on a full history rebuild while DialogBusy is up.
		from modules.kodi_utils import get_property, clear_property
		if get_property('redlight.punchplay_skip_list_sync') == 'true':
			clear_property('redlight.punchplay_skip_list_sync')
			return
		from apis.punchplay_api import punchplay_sync_activities
		punchplay_sync_activities()
	except: pass

def _refresh_punchplay_tvshow_watched():
	_refresh_punchplay_watched()

def _refresh_punchplay_progress():
	# Progress-only is a single light call; still go through sync so change-feed can skip work.
	try:
		if settings.watched_indicators() != 4 or not settings.punchplay_user_active(): return
		from apis.punchplay_api import punchplay_sync_activities
		punchplay_sync_activities()
	except: pass

def _refresh_trakt_episode_progress():
	try:
		if settings.watched_indicators() != 1 or not settings.trakt_user_active(): return
		from modules.kodi_utils import boot_trakt_list_refresh_allowed
		if not boot_trakt_list_refresh_allowed(): return
		from apis.trakt_api import trakt_playback_progress, trakt_progress_tv
		trakt_progress_tv(trakt_playback_progress())
	except: pass

def _refresh_trakt_tvshow_watched():
	# Activity-gated (same as Simkl/MDBList/PunchPlay / TraktMonitor) — skip full
	# sync/watched/shows pull when Trakt activities say nothing changed.
	try:
		if settings.watched_indicators() != 1 or not settings.trakt_user_active(): return
		from modules.kodi_utils import boot_trakt_list_refresh_allowed
		if not boot_trakt_list_refresh_allowed(): return
		from apis.trakt_api import trakt_sync_activities
		trakt_sync_activities()
	except: pass

def _episode_progress_list(dbcon):
	data = dbcon.execute('SELECT media_id, season, episode, resume_point, last_played, title FROM progress WHERE db_type = ?', ('episode',)).fetchall()
	return [{'media_ids': {'tmdb': i[0]}, 'season': int(i[1]), 'episode': int(i[2]), 'resume_point': float(i[3]), 'date': i[4], 'title': i[5]}
		for i in data if i[0] and float(i[3] or 0) > 1]

def _sort_progress_list(data):
	if settings.lists_sort_order('progress') == 0: return sort_for_article(data, 'title', settings.ignore_articles())
	return sorted(data, key=lambda x: x['last_played'], reverse=True)

def get_in_progress_movies(dummy_arg, page_no):
	clear_local_bookmarks()
	watched_indicators = settings.watched_indicators()
	dbcon = get_database(watched_indicators)
	data = _movie_progress_list(dbcon)
	source = 'local'
	if watched_indicators == 1 and settings.trakt_user_active():
		_refresh_trakt_movie_progress()
		data = _movie_progress_list(dbcon)
		if data: source = 'trakt'
	elif watched_indicators == 2 and settings.simkl_user_active():
		_refresh_simkl_progress()
		_purge_negligible_progress(dbcon)
		data = _movie_progress_list(dbcon)
		if data: source = 'simkl'
	elif watched_indicators == 3 and settings.mdblist_user_active():
		_refresh_mdblist_movie_progress()
		data = _movie_progress_list(dbcon)
		if data: source = 'mdblist'
	elif watched_indicators == 4 and settings.punchplay_user_active():
		_refresh_punchplay_progress()
		data = _movie_progress_list(dbcon)
		if data: source = 'punchplay'
	else:
		_purge_negligible_progress(dbcon)
		data = _movie_progress_list(dbcon)
	logger('Red Light', 'get_in_progress_movies: %s item(s) from %s' % (len(data), source))
	return _sort_progress_list(data)

def get_in_progress_tvshows(dummy_arg, page_no):
	clear_local_bookmarks()
	source = 'local'
	if settings.watched_indicators() == 1 and settings.trakt_user_active():
		_refresh_trakt_tvshow_watched()
		source = 'trakt'
	elif settings.watched_indicators() == 2 and settings.simkl_user_active():
		_refresh_simkl_tvshow_watched()
		source = 'simkl'
	elif settings.watched_indicators() == 3 and settings.mdblist_user_active():
		_refresh_mdblist_tvshow_watched()
		source = 'mdblist'
	elif settings.watched_indicators() == 4 and settings.punchplay_user_active():
		_refresh_punchplay_tvshow_watched()
		source = 'punchplay'
	results = active_tvshows_information('progress')
	logger('Red Light', 'get_in_progress_tvshows: %s item(s) from %s' % (len(results), source))
	if settings.lists_sort_order('progress') == 0: results = sort_for_article(results, 'title', settings.ignore_articles())
	else: results = sorted(results, key=lambda x: x['last_played'], reverse=True)
	return results

def get_in_progress_tvshow_ids(watched_db=None):
	"""TMDb IDs for shows that have at least one in-progress episode resume bookmark."""
	if not watched_db: watched_db = get_database()
	try:
		rows = watched_db.execute(
			'SELECT DISTINCT media_id FROM progress WHERE db_type = ? AND CAST(resume_point AS FLOAT) > 1',
			('episode',)).fetchall()
		return set(str(i[0]) for i in rows if i[0] not in (None, ''))
	except:
		return set()

def get_in_progress_episodes():
	clear_local_bookmarks()
	watched_indicators = settings.watched_indicators()
	dbcon = get_database(watched_indicators)
	episode_list = _episode_progress_list(dbcon)
	source = 'local'
	_skip_sync = False
	try:
		from modules.kodi_utils import playback_list_sync_skip_recent
		_skip_sync = playback_list_sync_skip_recent()
	except: pass
	if _skip_sync:
		_purge_negligible_progress(dbcon)
		episode_list = _episode_progress_list(dbcon)
		logger('Red Light', 'get_in_progress_episodes: %s item(s) from local (skip provider sync)' % len(episode_list))
	elif watched_indicators == 1 and settings.trakt_user_active():
		_refresh_trakt_episode_progress()
		episode_list = _episode_progress_list(dbcon)
		if episode_list: source = 'trakt'
	elif watched_indicators == 2 and settings.simkl_user_active():
		_refresh_simkl_progress()
		_purge_negligible_progress(dbcon)
		episode_list = _episode_progress_list(dbcon)
		if episode_list: source = 'simkl'
	elif watched_indicators == 3 and settings.mdblist_user_active():
		_refresh_mdblist_episode_progress()
		episode_list = _episode_progress_list(dbcon)
		if episode_list: source = 'mdblist'
	elif watched_indicators == 4 and settings.punchplay_user_active():
		_refresh_punchplay_progress()
		episode_list = _episode_progress_list(dbcon)
		if episode_list: source = 'punchplay'
	else:
		_purge_negligible_progress(dbcon)
		episode_list = _episode_progress_list(dbcon)
	if not _skip_sync:
		logger('Red Light', 'get_in_progress_episodes: %s item(s) from %s' % (len(episode_list), source))
	if settings.lists_sort_order('progress') == 0: episode_list = sort_for_article(episode_list, 'title', settings.ignore_articles())
	else: episode_list.sort(key=lambda k: k['date'], reverse=True)
	return episode_list

def get_watched_items(media_type, page_no):
	if settings.watched_indicators() == 3 and settings.mdblist_user_active():
		_refresh_mdblist_watched()
	elif settings.watched_indicators() == 4 and settings.punchplay_user_active():
		_refresh_punchplay_watched()
	if media_type == 'tvshow': results = active_tvshows_information('watched')
	else: results = [v for k,v in watched_info_movie().items()]
	if settings.lists_sort_order('watched') == 0: results = sort_for_article(results, 'title', settings.ignore_articles())
	else: results = sorted(results, key=lambda x: x['last_played'], reverse=True)
	return results

def get_recently_watched(media_type, short_list=0):
	watched_indicators = settings.watched_indicators()
	if watched_indicators == 3 and settings.mdblist_user_active():
		_refresh_mdblist_watched()
	elif watched_indicators == 4 and settings.punchplay_user_active():
		_refresh_punchplay_watched()
	if media_type == 'movie':
		watched_movies = watched_info_movie().items()
		data = sorted([v for k,v in watched_movies], key=lambda x: x['last_played'], reverse=True)
		if short_list: data = data[:20]
	elif media_type == 'tvshow':
		watched_tvshows = watched_info_tvshow().items()
		data = sorted([v for k,v in watched_tvshows], key=lambda x: x['last_played'], reverse=True)
		if short_list: data = data[:20]
	else:
		dbcon = get_database(watched_indicators)
		data = dbcon.execute('SELECT media_id, season, episode, title, last_played FROM watched WHERE db_type = ? ORDER BY last_played DESC', ('episode',)).fetchall()
		data = [{'media_ids': {'tmdb': int(i[0])}, 'season': int(i[1]), 'episode': int(i[2]), 'title': i[3], 'last_played': i[4]}
					for i in data]
		if short_list: data = data[:20]
	return data
