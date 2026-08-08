# -*- coding: utf-8 -*-
"""Cache built Next Episodes rows until watched / progress / hide state changes.

Mirrors Umbrella's progress-list memoization: reopen without watched activity is a
cache hit (listitem paint only). After a watch, the activity token changes and the
list rebuilds once.
"""
from caches.main_cache import main_cache
# from modules.kodi_utils import logger

_CACHE_PREFIX = 'nextep_list_'
_CACHE_HOURS = 168  # safety TTL; activity token usually invalidates sooner


def _settings_fingerprint(watched_indicators, mdblist_menu_next, is_anime_list, is_external):
	from modules import settings
	parts = (
		watched_indicators,
		1 if mdblist_menu_next else 0,
		is_anime_list,
		1 if is_external else 0,
		settings.nextep_method(),
		settings.nextep_include_unwatched(),
		1 if settings.nextep_include_unaired() else 0,
		1 if settings.nextep_include_airdate() else 0,
		1 if settings.nextep_airing_today() else 0,
		1 if settings.nextep_limit_history() else 0,
		settings.nextep_limit() if settings.nextep_limit_history() else 0,
		settings.nextep_sort_key(),
		1 if settings.nextep_sort_direction() else 0,
		settings.single_ep_display_format(is_external),
		1 if settings.single_ep_unwatched_episodes() else 0,
		1 if settings.single_ep_unwatched_in_title() else 0,
		1 if (is_external and settings.single_ep_widget_omit_tvshowtitle()) else 0,
		1 if (is_external and settings.single_ep_widget_omit_season_episode()) else 0,
		1 if settings.avoid_episode_spoilers() else 0,
		settings.date_offset(),
		settings.playback_key(),
		settings.ignore_articles(),
		2,  # cache schema: no InfoTag resume; live progress on paint
	)
	return '_'.join(str(p) for p in parts)


def cache_id(watched_indicators, mdblist_menu_next, is_anime_list, is_external):
	return '%s%s' % (_CACHE_PREFIX, _settings_fingerprint(watched_indicators, mdblist_menu_next, is_anime_list, is_external))


def activity_token(watched_indicators):
	"""Changes when next-up membership / resume / hide state changes.

	Resume must fingerprint the actual percent values — COUNT/last_played alone
	stays stable when Simkl resets a row to 0% (In Progress empties, but a cached
	Next Episodes packet can still carry the old WatchedProgress / resume secs).
	"""
	try:
		from modules.watched_status import get_database, get_hidden_progress_items
		dbcon = get_database(watched_indicators)
		watched = dbcon.execute(
			'SELECT COUNT(*), COALESCE(MAX(last_played), "") FROM watched WHERE db_type = ?', ('episode',)
		).fetchone() or (0, '')
		# Only meaningful (>1%) progress — matches In Progress shelf + resume prompt.
		progress = dbcon.execute(
			'SELECT COUNT(*), COALESCE(MAX(last_played), ""), '
			'COALESCE(SUM(CAST(resume_point AS FLOAT)), 0), '
			'COALESCE(GROUP_CONCAT(media_id || ":" || season || "x" || episode || ":" || resume_point), "") '
			'FROM progress WHERE db_type = ? AND CAST(resume_point AS FLOAT) > 1',
			('episode',)
		).fetchone() or (0, '', 0, '')
		hidden = get_hidden_progress_items(watched_indicators) or []
		try: hidden_key = ','.join(str(i) for i in sorted(int(x) for x in hidden))
		except: hidden_key = str(len(hidden))
		return '%s|%s|%s|%s|%s|%s|%s|%s|%s' % (
			watched_indicators, watched[0], watched[1],
			progress[0], progress[1], progress[2], progress[3],
			len(hidden), hidden_key
		)
	except:
		return '0'


def get_packets(cache_key, token):
	try:
		payload = main_cache.get(cache_key)
		if not payload or not isinstance(payload, dict): return None
		if payload.get('token') != token: return None
		packets = payload.get('packets')
		if not isinstance(packets, list) or not packets: return None
		return packets
	except:
		return None


def set_packets(cache_key, token, packets):
	try:
		if not packets: return
		main_cache.set(cache_key, {'token': token, 'packets': packets}, expiration=_CACHE_HOURS)
	except:
		pass


def invalidate():
	try: main_cache.delete_like('%s%%' % _CACHE_PREFIX)
	except: pass
