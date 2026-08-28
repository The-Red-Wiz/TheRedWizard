# -*- coding: utf-8 -*-
"""Cache built Next Episodes rows until watched / progress / hide / local day changes.

Mirrors Umbrella's progress-list memoization: reopen without watched activity is a
cache hit (listitem paint only). After a watch, the activity token changes and the
list rebuilds — prefer incremental rebuild via show_activity when a stale payload exists.

Local calendar day is in the fingerprint so unaired (red) labels do not stick on
widgets after the episode has aired. Personal calendars already keyed on day.
"""
from caches.main_cache import main_cache
# from modules.kodi_utils import logger

_CACHE_PREFIX = 'nextep_list_'
_CACHE_HOURS = 168  # safety TTL; activity token usually invalidates sooner


def _settings_fingerprint(watched_indicators, mdblist_menu_next, is_anime_list, is_external, sort_key=None):
	from modules import settings
	from modules.utils import get_datetime
	resolved_sort = sort_key if sort_key in ('last_played', 'first_aired', 'name') else settings.nextep_sort_key()
	calendar_day = get_datetime(string=True)
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
		resolved_sort,
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
		calendar_day,
		5,  # cache schema: episode still on landscape (LandscapeInfo widgets)
	)
	return '_'.join(str(p) for p in parts)


def cache_id(watched_indicators, mdblist_menu_next, is_anime_list, is_external, sort_key=None):
	return '%s%s' % (_CACHE_PREFIX, _settings_fingerprint(watched_indicators, mdblist_menu_next, is_anime_list, is_external, sort_key))


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


def show_activity(watched_indicators):
	"""Per-show activity for incremental rebuild: watched + in-progress resume."""
	try:
		from modules.watched_status import get_database
		dbcon = get_database(watched_indicators)
		rows = dbcon.execute(
			'SELECT media_id, COALESCE(MAX(last_played), "") FROM watched WHERE db_type = ? GROUP BY media_id',
			('episode',)
		).fetchall() or []
		activity = {str(r[0]): (r[1] or '') for r in rows if r[0] not in (None, '')}
		prog_rows = dbcon.execute(
			'SELECT media_id, COALESCE(MAX(last_played), ""), '
			'COALESCE(SUM(CAST(resume_point AS FLOAT)), 0) '
			'FROM progress WHERE db_type = ? AND CAST(resume_point AS FLOAT) > 1 GROUP BY media_id',
			('episode',)
		).fetchall() or []
		for r in prog_rows:
			if r[0] in (None, ''): continue
			key = str(r[0])
			activity[key] = '%s|p:%s|%s' % (activity.get(key, ''), r[1] or '', r[2] or 0)
		return activity
	except:
		return {}


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


def get_stale_payload(cache_key):
	"""Return cached payload even when the activity token no longer matches."""
	try:
		payload = main_cache.get(cache_key)
		if not payload or not isinstance(payload, dict): return None
		packets = payload.get('packets')
		if not isinstance(packets, list) or not packets: return None
		return payload
	except:
		return None


def set_packets(cache_key, token, packets, show_activity_map=None):
	try:
		if not packets: return
		payload = {'token': token, 'packets': packets}
		if show_activity_map is not None:
			payload['show_activity'] = show_activity_map
		main_cache.set(cache_key, payload, expiration=_CACHE_HOURS)
	except:
		pass


def invalidate():
	"""Hard wipe — settings / fingerprint changes. Prefer soft invalidate on mark watched
	(activity token already changes; keep stale packets for incremental rebuild)."""
	try: main_cache.delete_like('%s%%' % _CACHE_PREFIX)
	except: pass
