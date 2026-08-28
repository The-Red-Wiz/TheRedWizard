# -*- coding: utf-8 -*-
"""Cache built In Progress Episodes rows until progress / watched / settings change.

Mirrors nextep_cache: reopen without activity is a cache hit (listitem paint only).
Callers should refresh remote progress first, then token-check (refresh-then-token).
"""
from caches.main_cache import main_cache
# from modules.kodi_utils import logger

_CACHE_PREFIX = 'progress_ep_list_'
_CACHE_HOURS = 168  # safety TTL; activity token usually invalidates sooner


def _settings_fingerprint(watched_indicators, is_external):
	from modules import settings
	parts = (
		watched_indicators,
		1 if is_external else 0,
		settings.single_ep_display_format(is_external),
		1 if settings.single_ep_unwatched_episodes() else 0,
		1 if settings.single_ep_unwatched_in_title() else 0,
		1 if (is_external and settings.single_ep_widget_omit_tvshowtitle()) else 0,
		1 if (is_external and settings.single_ep_widget_omit_season_episode()) else 0,
		1 if settings.avoid_episode_spoilers() else 0,
		settings.date_offset(),
		settings.playback_key(),
		settings.lists_sort_order('progress'),
		1 if settings.ignore_articles() else 0,
		1 if settings.widget_hide_watched() else 0,
		2,  # cache schema: episode still on landscape
	)
	return '_'.join(str(p) for p in parts)


def cache_id(watched_indicators, is_external):
	return '%s%s' % (_CACHE_PREFIX, _settings_fingerprint(watched_indicators, is_external))


def _membership_key(data):
	"""Fingerprint the actual In Progress list identity (media/S/E/resume)."""
	parts = []
	for item in data or []:
		media_ids = item.get('media_ids') or {}
		parts.append('%s:%sx%s:%s' % (
			media_ids.get('tmdb'), item.get('season'), item.get('episode'),
			item.get('resume_point', item.get('resume', ''))
		))
	return '|'.join(parts)


def activity_token(watched_indicators, data=None):
	"""Changes when progress membership / resume / watched activity changes."""
	try:
		from modules.watched_status import get_database
		dbcon = get_database(watched_indicators)
		watched = dbcon.execute(
			'SELECT COUNT(*), COALESCE(MAX(last_played), "") FROM watched WHERE db_type = ?', ('episode',)
		).fetchone() or (0, '')
		progress = dbcon.execute(
			'SELECT COUNT(*), COALESCE(MAX(last_played), ""), '
			'COALESCE(SUM(CAST(resume_point AS FLOAT)), 0), '
			'COALESCE(GROUP_CONCAT(media_id || ":" || season || "x" || episode || ":" || resume_point), "") '
			'FROM progress WHERE db_type = ? AND CAST(resume_point AS FLOAT) > 1',
			('episode',)
		).fetchone() or (0, '', 0, '')
		token = '%s|%s|%s|%s|%s|%s|%s' % (
			watched_indicators, watched[0], watched[1],
			progress[0], progress[1], progress[2], progress[3]
		)
		if data is not None:
			token = '%s|m:%s' % (token, _membership_key(data))
		return token
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
