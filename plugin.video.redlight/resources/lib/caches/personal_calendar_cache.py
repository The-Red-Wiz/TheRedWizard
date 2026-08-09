# -*- coding: utf-8 -*-
"""Cache built personal calendar rows until feed / settings / watched / local day change.

Includes local calendar day in the fingerprint so Today/Yesterday labels do not stick overnight.
Fetch feed data first, then token-check (refresh-then-token).
"""
from caches.main_cache import main_cache
# from modules.kodi_utils import logger

_CACHE_PREFIX = 'personal_cal_list_'
_CACHE_HOURS = 48  # safety TTL; feed/settings/day/watched token usually invalidates sooner

PERSONAL_CALENDAR_KINDS = (
	'trakt_calendar', 'trakt_recently_aired', 'mdblist_calendar',
	'punchplay_calendar', 'simkl_calendar'
)


def _settings_fingerprint(kind, is_external):
	from caches.settings_cache import get_setting
	from modules import settings
	from modules.utils import get_datetime
	try: previous_days = int(get_setting('redlight.trakt.calendar_previous_days', '7'))
	except (TypeError, ValueError): previous_days = 7
	try: future_days = int(get_setting('redlight.trakt.calendar_future_days', '7'))
	except (TypeError, ValueError): future_days = 7
	calendar_day = get_datetime(string=True)  # local day — Today/Yesterday labels
	parts = (
		kind or '',
		1 if is_external else 0,
		previous_days,
		future_days,
		1 if settings.flatten_episodes() else 0,
		settings.calendar_sort_order(),
		settings.calendar_display_format(is_external),
		get_setting('redlight.trakt.calendar_date_labels', '0'),
		1 if (is_external and settings.single_ep_widget_omit_tvshowtitle()) else 0,
		1 if (is_external and settings.single_ep_widget_omit_season_episode()) else 0,
		1 if settings.avoid_episode_spoilers() else 0,
		1 if settings.single_ep_unwatched_episodes() else 0,
		1 if settings.single_ep_unwatched_in_title() else 0,
		1 if settings.widget_hide_watched() else 0,
		settings.date_offset(),
		settings.playback_key(),
		settings.watched_indicators(),
		calendar_day,
		1,  # cache schema
	)
	return '_'.join(str(p) for p in parts)


def cache_id(kind, is_external):
	return '%s%s' % (_CACHE_PREFIX, _settings_fingerprint(kind, is_external))


def activity_token(data, watched_indicators=None):
	"""Changes when capped feed membership or watched/progress activity changes."""
	import hashlib
	h = hashlib.md5()
	rows = data or []
	h.update(str(len(rows)).encode('utf-8'))
	for item in rows:
		media_ids = item.get('media_ids') or {}
		h.update(('%s|%s|%s|%s;' % (
			media_ids.get('tmdb'), item.get('season'), item.get('episode'),
			(item.get('first_aired') or '')[:19]
		)).encode('utf-8', 'replace'))
	try:
		from modules.watched_status import get_database
		if watched_indicators is None:
			from modules import settings
			watched_indicators = settings.watched_indicators()
		dbcon = get_database(watched_indicators)
		watched = dbcon.execute(
			'SELECT COUNT(*), COALESCE(MAX(last_played), "") FROM watched WHERE db_type = ?', ('episode',)
		).fetchone() or (0, '')
		progress = dbcon.execute(
			'SELECT COUNT(*), COALESCE(MAX(last_played), "") FROM progress WHERE db_type = ?', ('episode',)
		).fetchone() or (0, '')
		h.update(('|w:%s|%s|%s|%s|%s' % (
			watched_indicators, watched[0], watched[1], progress[0], progress[1]
		)).encode('utf-8', 'replace'))
	except:
		pass
	return h.hexdigest()


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
