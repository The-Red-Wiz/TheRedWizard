# -*- coding: utf-8 -*-
"""Cache built Recently Watched Episodes rows until watched activity / settings change.

Mirrors nextep_cache: reopen without activity is a cache hit (listitem paint only).
"""
from caches.main_cache import main_cache
# from modules.kodi_utils import logger

_CACHE_PREFIX = 'recent_watched_ep_'
_CACHE_HOURS = 168  # safety TTL; activity token usually invalidates sooner


def _settings_fingerprint(watched_indicators, is_external, short_list=True):
	from modules import settings
	parts = (
		watched_indicators,
		1 if is_external else 0,
		1 if short_list else 0,
		settings.single_ep_display_format(is_external),
		1 if settings.single_ep_unwatched_episodes() else 0,
		1 if settings.single_ep_unwatched_in_title() else 0,
		1 if (is_external and settings.single_ep_widget_omit_tvshowtitle()) else 0,
		1 if (is_external and settings.single_ep_widget_omit_season_episode()) else 0,
		1 if settings.avoid_episode_spoilers() else 0,
		settings.date_offset(),
		settings.playback_key(),
		2,  # cache schema: episode still on landscape
	)
	return '_'.join(str(p) for p in parts)


def cache_id(watched_indicators, is_external, short_list=True):
	return '%s%s' % (_CACHE_PREFIX, _settings_fingerprint(watched_indicators, is_external, short_list))


def activity_token(watched_indicators, data=None):
	"""Changes when recently-watched membership / last_played changes."""
	try:
		from modules.watched_status import get_database
		dbcon = get_database(watched_indicators)
		watched = dbcon.execute(
			'SELECT COUNT(*), COALESCE(MAX(last_played), "") FROM watched WHERE db_type = ?', ('episode',)
		).fetchone() or (0, '')
		top = ''
		if data is not None:
			top = ','.join(
				'%s:%sx%s:%s' % (
					(i.get('media_ids') or {}).get('tmdb'), i.get('season'), i.get('episode'),
					i.get('last_played') or ''
				) for i in (data or [])[:20]
			)
		else:
			rows = dbcon.execute(
				'SELECT media_id, season, episode, last_played FROM watched WHERE db_type = ? '
				'ORDER BY last_played DESC LIMIT 20',
				('episode',)
			).fetchall() or []
			top = ','.join('%s:%sx%s:%s' % (r[0], r[1], r[2], r[3] or '') for r in rows)
		return '%s|%s|%s|%s' % (watched_indicators, watched[0], watched[1], top)
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
