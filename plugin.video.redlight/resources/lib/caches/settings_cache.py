# -*- coding: utf-8 -*-
import json
import re
from threading import Lock
from modules import kodi_utils
from caches.base_cache import connect_database
# logger = kodi_utils.logger

VALID_EXTRAS_CONTAINER_IDS = frozenset(range(2050, 2067))
_COLOR_SETTING_RE = re.compile(r'^[0-9A-Fa-f]{6}$|^[0-9A-Fa-f]{8}$')
_EXTRAS_LIST_DEFAULT = '2050,2051,2052,2053,2054,2055,2056,2057,2058,2059,2060,2061,2062,2063,2064,2065,2066'
_MAX_PROPERTY_LEN = 8192
_SETTINGS_PROPERTIES_LOADED = 'redlight.settings_properties_loaded'
_DEFERRED_SETUP_DONE = 'redlight.deferred_service_setup_done'
_SETTINGS_DB_MIGRATED = 'redlight.settings_db_migrated'
_SETTINGS_WIDGETS_MIGRATED = 'redlight.settings_widgets_migrated'
_SETTINGS_DB_SYNCED = 'redlight.settings_db_synced'
_SETTINGS_SYNC_FINGERPRINT = 'redlight.settings_sync_fingerprint'
_WIDGET_REFRESH_SCHEDULED = 'redlight.widgets_refresh_scheduled'
_NEW_SETTING_VALUE_MIGRATIONS = {
	'trakt.calendar_display': 'single_ep_display',
	'trakt.calendar_display_widget': 'single_ep_display_widget',
}
_bootstrap_lock = Lock()
_DEFAULTS_LIST = None
_DEFAULTS_MAP = None

def _properties_loaded():
	return kodi_utils.get_property(_SETTINGS_PROPERTIES_LOADED) == 'true'

def _settings_schema_token():
	return '%s:%s' % (kodi_utils.addon_info('version'), len(default_settings()))

def compute_settings_sync_fingerprint():
	return _settings_schema_token()

def mark_settings_sync_complete():
	kodi_utils.set_property(_SETTINGS_SYNC_FINGERPRINT, compute_settings_sync_fingerprint())

def settings_sync_needed():
	if kodi_utils.get_property(_SETTINGS_DB_SYNCED) != 'true':
		return True
	stored = kodi_utils.get_property(_SETTINGS_SYNC_FINGERPRINT) or ''
	return stored != compute_settings_sync_fingerprint()

def clear_settings_boot_state(clear_deferred=True):
	kodi_utils.clear_property(_SETTINGS_SYNC_FINGERPRINT)
	kodi_utils.clear_property(_SETTINGS_DB_SYNCED)
	kodi_utils.clear_property(_SETTINGS_PROPERTIES_LOADED)
	kodi_utils.clear_property(_SETTINGS_DB_MIGRATED)
	kodi_utils.clear_property(_SETTINGS_WIDGETS_MIGRATED)
	if clear_deferred:
		kodi_utils.clear_property(_DEFERRED_SETUP_DONE)

def bootstrap_settings_needed():
	if not _properties_loaded():
		return True
	if kodi_utils.get_property(_SETTINGS_DB_MIGRATED) == 'true':
		return True
	if kodi_utils.get_property(_DEFERRED_SETUP_DONE) != 'true':
		return True
	return False

def widgets_refresh_after_migration_needed():
	return kodi_utils.get_property(_SETTINGS_WIDGETS_MIGRATED) == 'true'

def service_bootstrap_needed():
	return bootstrap_settings_needed() or widgets_refresh_after_migration_needed()

def _new_settings_affect_widgets(insert_list):
	for item in insert_list:
		setting_id = item[0]
		if setting_id.startswith('migration.'):
			continue
		return True
	return False

def _new_setting_value(setting_id, setting_default, currentsettings, had_existing_settings) -> str:
	if not had_existing_settings:
		return setting_default
	old_setting_id = _NEW_SETTING_VALUE_MIGRATIONS.get(setting_id)
	if not old_setting_id:
		return setting_default
	return currentsettings.get(old_setting_id, setting_default)

_CREDENTIAL_STRING_SETTINGS = frozenset(('tmdb_api', 'trakt.client', 'trakt.secret', 'tmdb.lists_read_token', 'omdb_api'))

def normalize_credential_string(value):
	if value in (None, 'empty_setting'): return ''
	return str(value).strip()

def looks_like_tmdb_v4_jwt(value):
	value = normalize_credential_string(value)
	return len(value) > 48 and value.startswith('eyJ') and value.count('.') >= 2

def property_safe_string(value):
	if value is None: return ''
	value = str(value).replace('\x00', '')
	return ''.join(c for c in value if c >= ' ' or c in '\t\n\r')[:_MAX_PROPERTY_LEN]

def _sanitize_extras_list(value, fallback=_EXTRAS_LIST_DEFAULT):
	if value in (None, '', 'noop'): return fallback
	try: ids = [int(i.strip()) for i in str(value).split(',') if i.strip()]
	except: return fallback
	valid = [i for i in ids if i in VALID_EXTRAS_CONTAINER_IDS]
	if not valid: return fallback
	return ','.join(str(i) for i in valid)

def sanitize_setting_value(setting_id, value, setting_info=None, validate_paths=True):
	if setting_info is None: setting_info = default_setting_values(setting_id)
	default = setting_info['setting_default'] if setting_info else ''
	if value is None: return default
	value = property_safe_string(value)
	if setting_id in ('extras.order', 'extras.enabled'):
		fallback = setting_info['setting_default'] if setting_info else _EXTRAS_LIST_DEFAULT
		return _sanitize_extras_list(value, fallback)
	if setting_id == 'default_addon_fanart':
		if not validate_paths: return value or default
		path = kodi_utils.translate_path(value) if value else ''
		if path and kodi_utils.path_exists(path): return value
		return kodi_utils.addon_fanart()
	if setting_id == 'addon_icon_choice':
		if not validate_paths: return value or default
		path = kodi_utils.translate_path(value) if value else ''
		if path and kodi_utils.path_exists(path): return value
		return default or 'resources/media/addon_icons/icon.png'
	if setting_id.endswith('_highlight') or setting_id in ('window_theme', 'window_theme_contrast'):
		if _COLOR_SETTING_RE.match(value): return value.upper()
		return default
	if setting_info and setting_info.get('setting_type') == 'boolean':
		if value in ('true', 'false'): return value
		return default
	if setting_id == 'watched_indicators':
		from modules.settings import watched_provider_options
		value = str(value)
		opts = watched_provider_options()
		if value in opts: return value
		if value == '1':
			from caches.settings_cache import settings_cache
			token = settings_cache.read_db_value('trakt.token')
			if token not in (None, '0', '', 'empty_setting'): return value
		if value == '2':
			from modules.settings import simkl_user_active
			if simkl_user_active(): return value
		if value == '3':
			from modules.settings import mdblist_user_active
			if mdblist_user_active(): return value
		return '0'
	if setting_id == 'playback.subs_source':
		from modules.settings import subtitles_source_options
		value = str(value)
		opts = subtitles_source_options()
		if value in opts: return value
		if value == '2':
			return '1' if '1' in opts else '0'
		if value == '1':
			return '2' if '2' in opts else '0'
		return '0'
	if setting_id in ('stinger_alert.alert_timing', 'autoplay_alert_timing', 'autoscrape_alert_timing'):
		from modules.settings import alert_timing_options
		value = str(value)
		opts = alert_timing_options(next_episode=(setting_id != 'stinger_alert.alert_timing'))
		if value in opts: return value
		if value == '2':
			return '1' if '1' in opts else '0'
		return default if default in opts else ('1' if '1' in opts else '0')
	if setting_id == 'external_scraper.run_mode':
		value = str(value)
		opts = default_setting_values(setting_id)
		if opts and value in opts.get('settings_options', {}): return value
		return default if default in (opts or {}).get('settings_options', {}) else '1'
	if setting_id in _CREDENTIAL_STRING_SETTINGS:
		if value in (None, 'empty_setting', ''): return default if value is None else value
		return normalize_credential_string(value)
	if len(value) > _MAX_PROPERTY_LEN: return value[:_MAX_PROPERTY_LEN]
	return value

class SettingsCache:
	def __init__(self):
		self._db_cache = {}
		self._db_warmed = False

	def clear_db_cache(self):
		self._db_cache = {}
		self._db_warmed = False

	def _warm_db_cache(self):
		if self._db_warmed: return
		self._db_warmed = True
		try:
			for setting_id, setting_value in self.get_all().items():
				setting_info = default_setting_values(setting_id)
				if setting_info: setting_value = sanitize_setting_value(setting_id, setting_value, setting_info, validate_paths=False)
				else: setting_value = property_safe_string(setting_value)
				self._db_cache[setting_id] = setting_value
		except: pass

	def read_db_value(self, setting_id, validate_paths=False):
		setting_id = setting_id.replace('redlight.', '')
		if setting_id in self._db_cache: return self._db_cache[setting_id]
		if not self._db_warmed: self._warm_db_cache()
		if setting_id in self._db_cache: return self._db_cache[setting_id]
		try:
			dbcon = connect_database('settings_db')
			row = dbcon.execute('SELECT setting_value FROM settings WHERE setting_id = ?', (setting_id,)).fetchone()
			if not row:
				self._db_cache[setting_id] = None
				return None
			setting_value = row[0]
			setting_info = default_setting_values(setting_id)
			if setting_info: setting_value = sanitize_setting_value(setting_id, setting_value, setting_info, validate_paths=validate_paths)
			else: setting_value = property_safe_string(setting_value)
			self._db_cache[setting_id] = setting_value
			return setting_value
		except:
			self._db_cache[setting_id] = None
			return None

	def get(self, setting_id):
		return self.read_db_value(setting_id)

	def remove_setting(self, setting_id):
		dbcon = connect_database('settings_db')
		dbcon.execute('DELETE FROM settings WHERE setting_id = ?', (setting_id,))

	def get_many(self, settings_list):
		try:
			dbcon = connect_database('settings_db')
			results = dict(dbcon.execute('SELECT setting_id, setting_value FROM settings WHERE setting_id in (%s)' \
										% (', '.join('?' for _ in settings_list)), settings_list).fetchall())
			return results
		except: results = {}
		return results

	def get_all(self):
		dbcon = connect_database('settings_db')
		try: all_settings = dict(dbcon.execute('SELECT setting_id, setting_value FROM settings').fetchall())
		except: all_settings = {}
		return all_settings

	def set(self, setting_id, setting_value=None):
		setting_id = setting_id.replace('redlight.', '')
		self._db_cache.pop(setting_id, None)
		self._db_cache.pop('%s_name' % setting_id, None)
		dbcon = connect_database('settings_db')
		setting_info = default_setting_values(setting_id)
		if not setting_info: return
		setting_type, setting_default = setting_info['setting_type'], setting_info['setting_default']
		if setting_value is None: setting_value = setting_default
		setting_value = sanitize_setting_value(setting_id, setting_value, setting_info)
		instance_switch = None
		if setting_id == 'aiostreams.instance':
			old_instance = str(self.read_db_value('aiostreams.instance') or '0')
			new_instance = str(setting_value)
			if old_instance != new_instance:
				instance_switch = new_instance
				try:
					from apis.aiostreams_api import persist_active_profile
					persist_active_profile(old_instance)
				except: pass
		dbcon.execute('INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)', (setting_id, setting_type, setting_default, setting_value))
		if instance_switch is not None:
			try:
				from apis.aiostreams_api import apply_profile
				apply_profile(instance_switch)
			except: pass
		if _properties_loaded():
			self.set_memory_cache(setting_id, setting_value)
		if setting_type == 'action' and 'settings_options' in setting_info:
			name_setting_id = '%s_name' % setting_id
			if setting_id == 'watched_indicators':
				from modules.settings import watched_provider_options
				opts = watched_provider_options()
				name_setting_value = opts.get(str(setting_value)) or setting_info['settings_options'].get(str(setting_value), opts['0'])
			elif setting_id == 'playback.subs_source':
				from modules.settings import subtitles_source_options
				opts = subtitles_source_options()
				name_setting_value = opts.get(str(setting_value), opts['0'])
			elif setting_id in ('stinger_alert.alert_timing', 'autoplay_alert_timing', 'autoscrape_alert_timing'):
				from modules.settings import alert_timing_options
				opts = alert_timing_options(next_episode=(setting_id != 'stinger_alert.alert_timing'))
				name_setting_value = opts.get(str(setting_value), opts.get('1', opts.get('0', '')))
			else:
				name_setting_value = setting_info['settings_options'][setting_value]
			if setting_id == 'aiostreams.instance':
				try:
					from apis.aiostreams_api import INSTANCE_LABELS
					name_setting_value = INSTANCE_LABELS.get(str(setting_value), name_setting_value)
				except: pass
			dbcon.execute('INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)', (name_setting_id, 'name', '', name_setting_value))
			if _properties_loaded(): self.set_memory_cache(name_setting_id, name_setting_value)
		if _properties_loaded() and setting_id in ('aiostreams.instance', 'aiostreams.custom_url', 'provider.aiostreams'):
			try:
				from apis.aiostreams_api import refresh_settings_properties
				refresh_settings_properties()
			except: pass

	def set_many(self, settings_list, load_properties=True):
		dbcon = connect_database('settings_db')
		dbcon.executemany('INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)', settings_list)
		if load_properties:
			for item in settings_list: self.set_memory_cache(item[0], item[3] or item[2])

	def write_db(self, setting_id, setting_value, setting_info=None):
		setting_id = setting_id.replace('redlight.', '')
		self._db_cache.pop(setting_id, None)
		if setting_info is None: setting_info = default_setting_values(setting_id)
		if setting_info: setting_value = sanitize_setting_value(setting_id, setting_value, setting_info)
		else: setting_value = property_safe_string(setting_value)
		dbcon = connect_database('settings_db')
		if setting_info:
			dbcon.execute('INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)',
				(setting_id, setting_info['setting_type'], setting_info['setting_default'], setting_value))
		else:
			dbcon.execute('INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)', (setting_id, 'name', '', setting_value))

	def set_memory_cache(self, setting_id, setting_value):
		try:
			kodi_utils.set_property('redlight.%s' % setting_id, property_safe_string(setting_value))
		except: pass

	def delete_memory_cache(self, setting_id):
		clear_property('redlight.%s' % setting_id)

	def setting_info(self, setting_id):
		d_settings = default_settings()
		return [i for i in d_settings if i['setting_id'] == setting_id][0]

	def clean_database(self):
		try:
			dbcon = connect_database('settings_db')
			dbcon.execute('VACUUM')
			return True
		except: return False

settings_cache = SettingsCache()

def set_setting(setting_id, value):
	settings_cache.set(setting_id, value)

def get_setting(setting_id, fallback=''):
	if _properties_loaded():
		prop = kodi_utils.get_property(setting_id)
		if prop not in ('', None): return prop
	value = settings_cache.read_db_value(setting_id)
	if value not in ('', None): return value
	return fallback

def _apply_settings_properties_from_db():
	d_settings = default_settings()
	defaultsettings_ids = _defaultsettings_ids(d_settings)
	defaults_map = _get_defaults_map()
	currentsettings = settings_cache.get_all()
	for setting_id, value in currentsettings.items():
		if setting_id not in defaultsettings_ids: continue
		info = defaults_map.get(setting_id)
		if info: sanitized = sanitize_setting_value(setting_id, value, info, validate_paths=False)
		else: sanitized = property_safe_string(value)
		try: settings_cache.set_memory_cache(setting_id, sanitized)
		except: pass
		if setting_id == 'watched_indicators':
			try:
				from modules.settings import watched_provider_options
				opts = watched_provider_options()
				info = defaults_map.get(setting_id) or {}
				static_opts = info.get('settings_options', {})
				settings_cache.set_memory_cache('watched_indicators_name', opts.get(sanitized) or static_opts.get(sanitized, opts['0']))
			except: pass
		if setting_id == 'playback.subs_source':
			try:
				from modules.settings import subtitles_source_options
				opts = subtitles_source_options()
				settings_cache.set_memory_cache('playback.subs_source_name', opts.get(sanitized, opts['0']))
			except: pass
		if setting_id in ('stinger_alert.alert_timing', 'autoplay_alert_timing', 'autoscrape_alert_timing'):
			try:
				from modules.settings import alert_timing_options
				opts = alert_timing_options(next_episode=(setting_id != 'stinger_alert.alert_timing'))
				settings_cache.set_memory_cache('%s_name' % setting_id, opts.get(sanitized, opts.get('1', '')))
			except: pass
		elif setting_id == 'autoplay_skip_intro':
			try:
				opts = (defaults_map.get(setting_id) or {}).get('settings_options', {})
				settings_cache.set_memory_cache('%s_name' % setting_id, opts.get(sanitized, opts.get('0', '')))
			except: pass
	try:
		from apis.aiostreams_api import refresh_settings_properties
		refresh_settings_properties()
	except: pass
	try:
		from modules.settings import refresh_external_scraper_properties
		refresh_external_scraper_properties()
	except: pass
	kodi_utils.set_property(_SETTINGS_PROPERTIES_LOADED, 'true')
	settings_cache.clear_db_cache()

def get_many(settings_list):
	return settings_cache.get_many(settings_list)

def _defaultsettings_ids(d_settings):
	defaultsettings_ids = [i['setting_id'] for i in d_settings]
	defaultsettings_names = [i['setting_id'] for i in d_settings if 'settings_options' in i]
	defaultsettings_ids.extend(['%s_name' % i for i in defaultsettings_names])
	return defaultsettings_ids

_ACTIVE_KODI_PROFILE = 'redlight.active_kodi_profile'

def sync_kodi_profile_context():
	"""Reload settings properties when the active Kodi profile changes (multi-profile / shared Trakt)."""
	try:
		current = kodi_utils.translate_path(kodi_utils.addon_info('profile'))
	except:
		return False
	if not current:
		return False
	kodi_utils.set_property('redlight.addon_profile', current)
	previous = kodi_utils.get_property(_ACTIVE_KODI_PROFILE) or ''
	if previous != current:
		kodi_utils.set_property(_ACTIVE_KODI_PROFILE, current)
		kodi_utils.clear_property(_SETTINGS_PROPERTIES_LOADED)
		settings_cache.clear_db_cache()
		if kodi_utils.get_property(_SETTINGS_DB_SYNCED) == 'true':
			_apply_settings_properties_from_db()
		else:
			bootstrap_settings_properties(force=True)
		return True
	if not _properties_loaded():
		kodi_utils.set_property(_ACTIVE_KODI_PROFILE, current)
		if kodi_utils.get_property(_SETTINGS_DB_SYNCED) == 'true':
			_apply_settings_properties_from_db()
		else:
			bootstrap_settings_properties(force=True)
		return True
	if not previous:
		kodi_utils.set_property(_ACTIVE_KODI_PROFILE, current)
	return False

def ensure_settings_properties_loaded():
	sync_kodi_profile_context()
	if _properties_loaded(): return False
	with _bootstrap_lock:
		if _properties_loaded(): return False
		if kodi_utils.get_property(_SETTINGS_DB_SYNCED) == 'true':
			_apply_settings_properties_from_db()
			return True
		return bootstrap_settings_properties()

def refresh_settings_manager_properties():
	"""Republish settings.db to Home props before Settings Manager opens (boolean toggles need this)."""
	settings_cache.clear_db_cache()
	_apply_settings_properties_from_db()
	try:
		from modules.settings import refresh_playback_subs_source, refresh_alert_timing_settings, refresh_external_scraper_properties
		refresh_playback_subs_source()
		refresh_alert_timing_settings()
		refresh_external_scraper_properties()
	except: pass

def bootstrap_settings_properties(force=False):
	db_migrated = kodi_utils.get_property(_SETTINGS_DB_MIGRATED) == 'true'
	if not force and _properties_loaded() and not db_migrated:
		return False
	with _bootstrap_lock:
		db_migrated = kodi_utils.get_property(_SETTINGS_DB_MIGRATED) == 'true'
		if not force and _properties_loaded() and not db_migrated:
			return False
		if force:
			kodi_utils.clear_property(_SETTINGS_PROPERTIES_LOADED)
			kodi_utils.clear_property(_SETTINGS_DB_SYNCED)
		if force or kodi_utils.get_property(_SETTINGS_DB_SYNCED) != 'true':
			sync_settings({'silent': 'true', 'load_properties': False, 'force': 'true'})
		else:
			kodi_utils.clear_property(_SETTINGS_PROPERTIES_LOADED)
		_apply_settings_properties_from_db()
		if db_migrated:
			kodi_utils.clear_property(_SETTINGS_DB_MIGRATED)
		return True

def schedule_widget_refresh_once(reload_skin=False):
	if kodi_utils.get_property(_WIDGET_REFRESH_SCHEDULED) == 'true': return
	kodi_utils.set_property(_WIDGET_REFRESH_SCHEDULED, 'true')
	try: kodi_utils.schedule_widget_refresh(silent=True, reload_skin=reload_skin)
	except: pass

def refresh_widgets_after_db_migration():
	if kodi_utils.get_property(_SETTINGS_WIDGETS_MIGRATED) != 'true': return
	kodi_utils.clear_property(_SETTINGS_WIDGETS_MIGRATED)
	schedule_widget_refresh_once(reload_skin=not kodi_utils.is_android())

def run_deferred_setup_if_needed():
	run_deferred_setup_background_if_needed()

def run_deferred_setup_background_if_needed():
	if kodi_utils.get_property(_DEFERRED_SETUP_DONE) == 'true': return
	kodi_utils.set_property(_DEFERRED_SETUP_DONE, 'true')
	from threading import Thread
	def _run():
		try:
			from service import run_deferred_service_setup
			run_deferred_service_setup()
		except Exception as e:
			kodi_utils.logger('run_deferred_setup_if_needed', str(e))
	Thread(target=_run, daemon=True).start()

_DIRECTORY_LISTING_MODES = frozenset((
	'build_movie_list', 'build_tvshow_list', 'build_season_list', 'build_episode_list',
	'build_in_progress_episode', 'build_recently_watched_episode', 'build_next_episode',
	'build_my_calendar', 'build_next_episode_manager'))

def is_directory_listing_mode(mode):
	if not mode: return False
	if mode.startswith('navigator.'): return True
	return mode in _DIRECTORY_LISTING_MODES

def should_block_bootstrap_on_entry(mode):
	"""Only block plugin entry when opening settings UI; listings read settings.db directly."""
	if mode in ('open_settings', 'sync_settings'):
		return True
	if mode and mode.startswith('settings_manager.'):
		return True
	return False

def load_settings_properties(force=False):
	bootstrap_settings_properties(force=force)
	refresh_widgets_after_db_migration()
	run_deferred_setup_if_needed()

def reload_after_settings_restore(imported_db_keys=()):
	"""Reload caches after a settings backup import without stopping the addon service."""
	clear_settings_boot_state(clear_deferred=True)
	kodi_utils.clear_property(_WIDGET_REFRESH_SCHEDULED)
	settings_cache.clear_db_cache()
	imported = set(imported_db_keys or ())
	if not imported or 'navigator_db' in imported:
		try:
			from caches.navigator_cache import navigator_cache
			for list_name in navigator_cache.main_menus:
				navigator_cache.delete_memory_cache(list_name, 'default')
				navigator_cache.delete_memory_cache(list_name, 'edited')
		except: pass
	try:
		sync_settings({'silent': 'true', 'load_properties': False})
	except Exception as e:
		kodi_utils.logger('reload_after_settings_restore', 'sync: %s' % e)
	try:
		kodi_utils.ensure_addon_xml_from_settings(force=True)
	except Exception as e:
		kodi_utils.logger('reload_after_settings_restore', 'addon_xml: %s' % e)
	from threading import Thread
	def _bootstrap():
		try:
			bootstrap_settings_properties(force=True)
			run_deferred_setup_background_if_needed()
			schedule_widget_refresh_once(reload_skin=False)
		except Exception as e:
			kodi_utils.logger('reload_after_settings_restore', 'bootstrap: %s' % e)
	Thread(target=_bootstrap, daemon=True).start()

def sync_settings(params={}):
	silent = params.get('silent', 'true') == 'true'
	force = params.get('force', False) == 'true'
	if 'load_properties' in params:
		load_properties = params.get('load_properties', True) == 'true'
	else:
		# AM Lite and boot service sync update settings.db only; full property reload is for Remake Settings Cache.
		load_properties = not silent
	if not force and not load_properties and not settings_sync_needed():
		return 'skipped'
	migrated = False
	widgets_migrated = False
	insert_list = []
	insert_list_append = insert_list.append
	currentsettings = settings_cache.get_all()
	had_existing_settings = bool(currentsettings)
	d_settings = default_settings()
	defaultsettings_ids = _defaultsettings_ids(d_settings)
	defaults_map = {i['setting_id']: i for i in d_settings}
	try:
		c_settings = currentsettings.items()
		obsoletesettings_ids = [k for k, v in c_settings if not k in defaultsettings_ids]
		if obsoletesettings_ids:
			for item in obsoletesettings_ids: settings_cache.remove_setting(item)
			migrated = True
			currentsettings = settings_cache.get_all()
	except: pass
	_setting_migrations = (
		('external.cache_check', 'rd.cache_check'),
		('external.include_uncached_torbox', 'tb.include_uncached'),
		('external.include_uncached_offcloud', 'oc.include_uncached'),
	)
	for old_id, new_id in _setting_migrations:
		if old_id not in currentsettings: continue
		if new_id not in currentsettings:
			value = currentsettings[old_id]
			settings_cache.write_db(new_id, value, defaults_map.get(new_id))
			currentsettings[new_id] = value
			if load_properties: settings_cache.set_memory_cache(new_id, value)
		settings_cache.remove_setting(old_id)
		currentsettings.pop(old_id, None)
		migrated = True
	_alert_timing_migrations = (
		('stinger_alert.use_chapters', 'stinger_alert.alert_timing'),
		('autoplay_use_chapters', 'autoplay_alert_timing'),
		('autoscrape_use_chapters', 'autoscrape_alert_timing'),
	)
	for old_id, new_id in _alert_timing_migrations:
		if old_id not in currentsettings: continue
		new_val = '1' if str(currentsettings[old_id]).lower() == 'true' else '0'
		settings_cache.write_db(new_id, new_val, defaults_map.get(new_id))
		currentsettings[new_id] = new_val
		if load_properties: settings_cache.set_memory_cache(new_id, new_val)
		settings_cache.remove_setting(old_id)
		currentsettings.pop(old_id, None)
		migrated = True
	if had_existing_settings and currentsettings.get('migration.cache_check_pm_oc_tb_v129e') != 'true':
		for cache_key in ('pm.cache_check', 'oc.cache_check', 'tb.cache_check'):
			if currentsettings.get(cache_key) == 'true': continue
			settings_cache.write_db(cache_key, 'true', defaults_map.get(cache_key))
			currentsettings[cache_key] = 'true'
			if load_properties: settings_cache.set_memory_cache(cache_key, 'true')
			migrated = True
		settings_cache.write_db('migration.cache_check_pm_oc_tb_v129e', 'true', defaults_map.get('migration.cache_check_pm_oc_tb_v129e'))
		currentsettings['migration.cache_check_pm_oc_tb_v129e'] = 'true'
		if load_properties: settings_cache.set_memory_cache('migration.cache_check_pm_oc_tb_v129e', 'true')
	if had_existing_settings and currentsettings.get('migration.ad_cache_check_removed_v173') != 'true':
		if currentsettings.get('ad.cache_check') == 'true':
			settings_cache.write_db('ad.cache_check', 'false', defaults_map.get('ad.cache_check'))
			currentsettings['ad.cache_check'] = 'false'
			if load_properties: settings_cache.set_memory_cache('ad.cache_check', 'false')
			migrated = True
		settings_cache.write_db('migration.ad_cache_check_removed_v173', 'true', defaults_map.get('migration.ad_cache_check_removed_v173'))
		currentsettings['migration.ad_cache_check_removed_v173'] = 'true'
		if load_properties: settings_cache.set_memory_cache('migration.ad_cache_check_removed_v173', 'true')
	if currentsettings:
		from modules.settings import migrate_simkl_context_menu_for_upgrade, migrate_mdblist_context_menu_for_upgrade, migrate_cm_manager_order_for_upgrade, migrate_external_scraper_context_menu_for_upgrade
		if migrate_simkl_context_menu_for_upgrade(had_existing_settings): migrated = True
		if migrate_mdblist_context_menu_for_upgrade(had_existing_settings): migrated = True
		if migrate_external_scraper_context_menu_for_upgrade(had_existing_settings): migrated = True
		if migrate_cm_manager_order_for_upgrade(): migrated = True
		if currentsettings.get('migration.my_content_nav_mode_v136') != 'true':
			try:
				from caches.navigator_cache import migrate_my_content_nav_mode
				if migrate_my_content_nav_mode(): migrated = True
			except: pass
			settings_cache.write_db('migration.my_content_nav_mode_v136', 'true', defaults_map.get('migration.my_content_nav_mode_v136'))
			currentsettings['migration.my_content_nav_mode_v136'] = 'true'
			if load_properties: settings_cache.set_memory_cache('migration.my_content_nav_mode_v136', 'true')
		for setting_id, value in list(currentsettings.items()):
			if setting_id not in defaults_map: continue
			sanitized = sanitize_setting_value(setting_id, value, defaults_map[setting_id], validate_paths=False)
			if sanitized != value:
				sanitized = sanitize_setting_value(setting_id, value, defaults_map[setting_id], validate_paths=True)
				settings_cache.write_db(setting_id, sanitized, defaults_map[setting_id])
				currentsettings[setting_id] = sanitized
				migrated = True
			if load_properties:
				settings_cache.set_memory_cache(setting_id, sanitized)
	for item in d_settings:
		setting_id = item['setting_id']
		if setting_id in currentsettings:
			continue
		setting_type = item['setting_type']
		setting_default = item['setting_default']
		setting_value = _new_setting_value(setting_id, setting_default, currentsettings, had_existing_settings)
		if setting_type == 'action' and 'settings_options' in item:
			if setting_id == 'aiostreams.instance':
				try:
					from apis.aiostreams_api import INSTANCE_LABELS
					name_default = INSTANCE_LABELS.get(setting_default, item['settings_options'][setting_default])
				except (ImportError, KeyError):
					name_default = item['settings_options'][setting_default]
				name_value = name_default
			else:
				name_default = item['settings_options'][setting_default]
				name_value = item['settings_options'].get(setting_value, name_default)
			insert_list_append((f'{setting_id}_name', 'name', name_default, name_value))
		insert_list_append((setting_id, setting_type, setting_default, setting_value))
	if insert_list:
		settings_cache.set_many(insert_list, load_properties=load_properties)
		migrated = True
		if _new_settings_affect_widgets(insert_list):
			widgets_migrated = True
	if had_existing_settings:
		from modules.settings import migrate_external_scraper_slots_for_upgrade, migrate_external_scraper_run_mode_for_upgrade
		if migrate_external_scraper_slots_for_upgrade(had_existing_settings): migrated = True
		if migrate_external_scraper_run_mode_for_upgrade(had_existing_settings): migrated = True
	if migrated and had_existing_settings:
		kodi_utils.set_property(_SETTINGS_DB_MIGRATED, 'true')
	if widgets_migrated and had_existing_settings:
		kodi_utils.set_property(_SETTINGS_WIDGETS_MIGRATED, 'true')
	if load_properties:
		settings_cache.clean_database()
		bootstrap_settings_properties(force=True)
		run_deferred_setup_if_needed()
		kodi_utils.set_property(_SETTINGS_DB_SYNCED, 'true')
		mark_settings_sync_complete()
	else:
		kodi_utils.set_property(_SETTINGS_DB_SYNCED, 'true')
		mark_settings_sync_complete()
		settings_cache.clear_db_cache()
		if _properties_loaded():
			_apply_settings_properties_from_db()
	if not silent: kodi_utils.notification('Settings Cache Remade')
	return 'synced'

def set_default(setting_ids):
	if not isinstance(setting_ids, list): setting_ids = [setting_ids]
	if not kodi_utils.confirm_dialog(text='Are You Sure?', ok_label='Yes', cancel_label='No', default_control=11): return
	for setting_id in setting_ids:
		try: set_setting(setting_id, default_setting_values(setting_id)['setting_default'])
		except: pass

def set_boolean(params):
	boolean_dict = {'true': 'false', 'false': 'true'}
	setting = params['setting_id']
	set_setting(setting, boolean_dict[get_setting('redlight.%s' % setting)])
	if setting.startswith('external_scraper.slot') and setting.endswith('.enabled'):
		try:
			from modules.settings import refresh_external_scraper_properties
			refresh_external_scraper_properties()
		except: pass

def set_string(params):
	setting_id = params['setting_id']
	current_value = get_setting('redlight.%s' % setting_id)
	current_value = current_value.replace('empty_setting', '')
	new_value = kodi_utils.kodi_dialog().input('', defaultt=current_value)
	if not new_value and not kodi_utils.confirm_dialog(text='Enter Blank Value?', ok_label='Yes', cancel_label='Re-Enter Value', default_control=11):
		return set_string(params)
	if setting_id in _CREDENTIAL_STRING_SETTINGS:
		new_value = normalize_credential_string(new_value)
	if setting_id == 'tmdb_api' and new_value and looks_like_tmdb_v4_jwt(new_value):
		kodi_utils.ok_dialog(heading='Wrong key type', text='This is a TMDb v4 Read Access Token (JWT), not the v3 API Key.[CR]Use TMDb Lists → Read Access Token for v4 tokens.')
		return set_string(params)
	if setting_id == 'playback.submaker_manifest' and new_value:
		new_value = new_value.strip()
	set_setting(setting_id, new_value or 'empty_setting')
	if setting_id in ('aiostreams.username', 'aiostreams.password', 'aiostreams.custom_url'):
		try:
			from apis.aiostreams_api import persist_active_profile
			persist_active_profile()
		except: pass
	if setting_id in ('playback.submaker_manifest', 'playback.opensubs_username', 'playback.opensubs_password'):
		try:
			refresh_settings_manager_properties()
		except: pass

def set_numeric(params):
	setting_id = params['setting_id']
	setting_values = default_setting_values(setting_id)
	values_get = setting_values.get
	min_value, max_value = int(values_get('min_value', '0')), int(values_get('max_value', '100000000000000'))
	negative_included = any((n < 0 for n in [min_value, max_value]))
	if negative_included:
		multiplier_values = [('Positive(+)', 1), ('Negative(-)', -1)]
		list_items = [{'line1': item[0]} for item in multiplier_values]
		kwargs = {'items': json.dumps(list_items), 'narrow_window': 'true', 'heading': 'Will this be a positive or negative number?'}
		multiplier = kodi_utils.select_dialog(multiplier_values, **kwargs)
	else: multiplier = None
	new_value = kodi_utils.kodi_dialog().input('Range [B]%s - %s[/B].' % (min_value, max_value), type=1)
	if not new_value: return
	if multiplier: new_value = str(int(float(new_value) * multiplier[1]))
	if int(new_value) < min_value or int(new_value) > max_value:
		kodi_utils.ok_dialog(text='Please Choose Between the Range [B]%s - %s[/B].' % (min_value, max_value))
		return set_numeric(params)
	set_setting(setting_id, new_value)

def set_path(params):
	setting_id = params['setting_id']
	browse_mode = int(default_setting_values(setting_id)['browse_mode'])
	current = get_setting('redlight.%s' % setting_id)
	if browse_mode == 0:
		force_defaultt = setting_id == 'import_export_directory'
		new_value = kodi_utils.browse_directory(current, heading='Choose folder', use_defaultt=True, force_defaultt=force_defaultt)
	else:
		result = kodi_utils.kodi_dialog().browse(browse_mode, 'Choose file', '', defaultt=current or None)
		new_value = result if result and str(result).strip() else None
	if not new_value:
		return
	set_setting(setting_id, new_value)
	if setting_id == 'import_export_directory':
		try:
			from modules import settings
			settings.ensure_import_export_directory()
		except:
			pass

def set_from_list(params):
	setting_id = params['setting_id']
	if setting_id == 'aiostreams.instance':
		from apis.aiostreams_api import instance_picker_list
		settings_list = instance_picker_list()
	elif setting_id == 'watched_indicators':
		from modules.settings import watched_provider_options
		settings_options = watched_provider_options().items()
		settings_list = [(v, k) for k, v in settings_options]
		settings_list.sort(key=lambda item: item[0].lower())
	elif setting_id == 'playback.subs_source':
		from modules.settings import subtitles_source_options
		settings_options = subtitles_source_options().items()
		settings_list = [(v, k) for k, v in settings_options]
	elif setting_id in ('stinger_alert.alert_timing', 'autoplay_alert_timing', 'autoscrape_alert_timing'):
		from modules.settings import alert_timing_options
		settings_options = alert_timing_options(next_episode=(setting_id != 'stinger_alert.alert_timing')).items()
		settings_list = [(v, k) for k, v in settings_options]
		settings_list.sort(key=lambda item: item[0].lower())
	else:
		settings_options = default_setting_values(setting_id)['settings_options'].items()
		settings_list = [(v, k) for k, v in settings_options]
		if setting_id == 'external_scraper.run_mode':
			_mode_order = ('1', '2', '3', '0')
			settings_list.sort(key=lambda item: _mode_order.index(item[1]) if item[1] in _mode_order else 99)
	new_value = kodi_utils.select_dialog(settings_list, **{'items': json.dumps([{'line1': item[0]} for item in settings_list]), 'narrow_window': 'true'})
	if not new_value: return
	setting_value = new_value[1]
	if setting_id == 'external_scraper.run_mode' and setting_value != '1':
		mode_opts = dict(default_setting_values(setting_id)['settings_options'])
		mode_label = mode_opts.get(setting_value, '')
		current = str(get_setting('redlight.external_scraper.run_mode', '1'))
		warning_text = (
			'Many indexers are volunteer-run community resources. '
			'[B]%s[/B] can query the same indexers multiple times. [B]Series (Fallback by Slot Order)[/B] is the recommended default.[CR][CR]'
			'Please scrape responsibly.' % mode_label
		)
		if current == '1':
			confirmed = kodi_utils.confirm_dialog(
				heading='Search Mode',
				text=warning_text,
				ok_label='Continue',
				cancel_label='Cancel',
				default_control=11,
			)
			if confirmed is None or not confirmed:
				return
		else:
			confirmed = kodi_utils.confirm_dialog(
				heading='Search Mode',
				text=warning_text,
				ok_label='Series (Fallback)',
				cancel_label='Continue',
				default_control=10,
			)
			if confirmed is None:
				return
			if confirmed:
				set_setting('external_scraper.run_mode', '1')
				try:
					settings_cache.set_memory_cache('external_scraper.run_mode', '1')
					settings_cache.set_memory_cache('external_scraper.run_mode_name', mode_opts.get('1', ''))
				except:
					pass
				return
	prev_value = get_setting('redlight.%s' % setting_id) if setting_id == 'watched_indicators' else None
	set_setting(setting_id, setting_value)
	if setting_id == 'external_scraper.run_mode':
		try:
			mode_opts = dict(default_setting_values(setting_id)['settings_options'])
			settings_cache.set_memory_cache(setting_id, str(setting_value))
			settings_cache.set_memory_cache('%s_name' % setting_id, mode_opts.get(str(setting_value), ''))
		except:
			pass
	if setting_id == 'watched_indicators' and setting_value == '3' and str(prev_value) != '3':
		try:
			from apis.mdblist_api import mdblist_sync_activities
			mdblist_sync_activities(force_update=True)
		except: pass
	if setting_id == 'watched_indicators' and setting_value == '2' and str(prev_value) != '2':
		try:
			from modules.settings import trakt_user_active, offer_trakt_import_to_simkl
			if trakt_user_active() and not offer_trakt_import_to_simkl():
				from apis.simkl_api import simkl_sync_activities
				simkl_sync_activities(force_update=True)
		except: pass

def set_source_folder_path(params):
	setting_id = params['setting_id']
	current_setting = get_setting('redlight.%s' % setting_id)
	if current_setting not in (None, 'None', ''):
		if kodi_utils.confirm_dialog(text='Enter Blank Value?', ok_label='Yes', cancel_label='Re-Enter Value', default_control=11):
			return set_setting(setting_id, 'None')
	return set_path(params)

def restore_setting_default(params):
	silent = params.get('silent', 'false') == 'true'
	if not silent and not kodi_utils.confirm_dialog(): return
	try:
		setting_id = params['setting_id']
		setting_default = default_setting_values(setting_id)['setting_default']
		set_setting(setting_id, setting_default)
	except:
		if not silent: kodi_utils.ok_dialog(text='Error restoring default setting')

def default_setting_values(setting_id):
	if 'redlight.' in setting_id: setting_id = setting_id.replace('redlight.', '')
	return _get_defaults_map().get(setting_id)

def _get_defaults_map():
	global _DEFAULTS_MAP
	if _DEFAULTS_MAP is None: _DEFAULTS_MAP = {i['setting_id']: i for i in default_settings()}
	return _DEFAULTS_MAP

def default_settings():
	global _DEFAULTS_LIST
	if _DEFAULTS_LIST is not None: return _DEFAULTS_LIST
	_DEFAULTS_LIST = [
#===============================================================================#
#====================================GENERAL====================================#
#===============================================================================#
#==================== General
{'setting_id': 'auto_start_redlight', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'addon_icon_choice', 'setting_type': 'string', 'setting_default': 'resources/media/addon_icons/icon.png'},
{'setting_id': 'default_addon_fanart', 'setting_type': 'path', 'setting_default': kodi_utils.addon_fanart(), 'browse_mode': '2'},
{'setting_id': 'limit_concurrent_threads', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'max_threads', 'setting_type': 'action', 'setting_default': '60', 'min_value': '10', 'max_value': '250'},
#==================== Window Theme
{'setting_id': 'window_theme', 'setting_type': 'string', 'setting_default': 'CC1F2020'},
{'setting_id': 'window_theme_opacity', 'setting_type': 'string', 'setting_default': 'CC'},
#==================== Watched Indicators
{'setting_id': 'watched_indicators', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'3': 'MDBList', '0': 'Red Light', '2': 'Simkl', '1': 'Trakt'}},
#======+============= MDBList Cache
{'setting_id': 'mdblist.user', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'mdblist.client', 'setting_type': 'string', 'setting_default': 'JFZCpEIYFtpvGk47pEEprjEkXzlPL8hJR45jqddJ'},
{'setting_id': 'mdblist.token', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'mdblist.refresh', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'mdblist.sync_interval', 'setting_type': 'action', 'setting_default': '60', 'min_value': '5', 'max_value': '600'},
{'setting_id': 'mdblist.refresh_widgets', 'setting_type': 'boolean', 'setting_default': 'true'},
#======+============= Simkl Cache
{'setting_id': 'simkl.user', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'simkl.token', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'simkl.sync_interval', 'setting_type': 'action', 'setting_default': '60', 'min_value': '5', 'max_value': '600'},
{'setting_id': 'simkl.refresh_widgets', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'simkl.cm_menu_migrated', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'mdblist.cm_menu_migrated', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'external_scraper.cm_menu_migrated', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'cm_manager_order_migrated', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'cm_manager_order_migrated_v2', 'setting_type': 'boolean', 'setting_default': 'false'},
#======+============= Trakt Cache
{'setting_id': 'trakt.sync_interval', 'setting_type': 'action', 'setting_default': '60', 'min_value': '5', 'max_value': '600'},
{'setting_id': 'trakt.refresh_widgets', 'setting_type': 'boolean', 'setting_default': 'true'},
#==================== UTC Time Offset
{'setting_id': 'datetime.offset', 'setting_type': 'action', 'setting_default': '0', 'min_value': '-15', 'max_value': '15'},
#==================== Downloads
{'setting_id': 'movie_download_directory', 'setting_type': 'path', 'setting_default': 'special://profile/addon_data/plugin.video.redlight/Movies Downloads/', 'browse_mode': '0'},
{'setting_id': 'tvshow_download_directory', 'setting_type': 'path', 'setting_default': 'special://profile/addon_data/plugin.video.redlight/TV Show Downloads/', 'browse_mode': '0'},
{'setting_id': 'premium_download_directory', 'setting_type': 'path', 'setting_default': 'special://profile/addon_data/plugin.video.redlight/Premium Downloads/', 'browse_mode': '0'},
{'setting_id': 'image_download_directory', 'setting_type': 'path', 'setting_default': 'special://profile/addon_data/plugin.video.redlight/Image Downloads/', 'browse_mode': '0'},
{'setting_id': 'import_export_directory', 'setting_type': 'path', 'setting_default': 'special://profile/addon_data/plugin.video.redlight/Import Export/', 'browse_mode': '0'},


#================================================================================#
#====================================FEATURES====================================#
#================================================================================#
#==================== Extras
{'setting_id': 'extras.enable_extra_ratings', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'extras.enabled_ratings', 'setting_type': 'string', 'setting_default': 'Meta, Tom/Critic, Tom/User, IMDb, TMDb'},
{'setting_id': 'extras.enable_item_ratings', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'extras.enable_scrollbars', 'setting_type': 'boolean', 'setting_default': 'false'},
#==================== Special Open Actions
{'setting_id': 'media_open_action_movie', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'Open Extras', '2': 'Open Movie Set', '3': 'Both'}},
{'setting_id': 'media_open_action_tvshow', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'Open Extras'}},
#==================== AI Generated Similar Titles
{'setting_id': 'ai_model.order', 'setting_type': 'string', 'setting_default': 'gemini-2.5-flash-lite,llama-3.3-70b-versatile,gemma-3-27b-it,llama-3.1-8b-instant'},
{'setting_id': 'ai_model.limit', 'setting_type': 'action', 'setting_default': '15', 'min_value': '1', 'max_value': '25'},


#==================================================================================#
#====================================CONTENT=======================================#
#==================================================================================#
#==================== General
{'setting_id': 'paginate.lists', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Off', '1': 'Within Addon Only', '2': 'Widgets Only', '3': 'Both'}},
{'setting_id': 'paginate.limit_addon', 'setting_type': 'action', 'setting_default': '20'},
{'setting_id': 'paginate.limit_widgets', 'setting_type': 'action', 'setting_default': '20'},
{'setting_id': 'paginate.jump_to', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'ignore_articles', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'recommend_service', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Recommended (TMDb)', '1': 'More Like This (IMDb)',
'2': 'Similar (AI)', '3': 'Related (Trakt)'}},
{'setting_id': 'recommend_seed', 'setting_type': 'action', 'setting_default': '5', 'settings_options': {'1': 'Last Watched Only', '2': 'Last 2 Watched',
'3': 'Last 3 Watched', '4': 'Last 4 Watched', '5': 'Last 5 Watched', '6': 'Last 6 Watched', '7': 'Last 7 Watched', '8': 'Last 8 Watched',
'9': 'Last 9 Watched', '10': 'Last 10 Watched'}},
{'setting_id': 'mpaa_region', 'setting_type': 'string', 'setting_default': 'US'},
{'setting_id': 'lists_cache_duraton', 'setting_type': 'string', 'setting_default': '24'},
{'setting_id': 'tv_progress_location', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Watched', '1': 'In Progress', '2': 'Both'}},
{'setting_id': 'show_specials', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'use_season_name', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'default_all_episodes', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Never', '1': 'If Only One Season', '2': 'Always'}},
{'setting_id': 'avoid_episode_spoilers', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'include_anime_tvshow', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'show_unaired_watchlist', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'meta_filter', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'use_viewtypes', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'manual_viewtypes', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'view.main', 'setting_type': 'string', 'setting_default': '55'},
{'setting_id': 'view.movies', 'setting_type': 'string', 'setting_default': '500'},
{'setting_id': 'view.tvshows', 'setting_type': 'string', 'setting_default': '500'},
{'setting_id': 'view.seasons', 'setting_type': 'string', 'setting_default': '55'},
{'setting_id': 'view.episodes', 'setting_type': 'string', 'setting_default': '55'},
{'setting_id': 'view.episodes_single', 'setting_type': 'string', 'setting_default': '55'},
{'setting_id': 'view.premium', 'setting_type': 'string', 'setting_default': '55'},
#==================== Contents Sort Order For Watched Progress
{'setting_id': 'sort.progress', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Title', '1': 'Recently Watched'}},
{'setting_id': 'sort.watched', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Title', '1': 'Recently Watched'}},
#==================== Contents Sort Order For Simkl Lists
{'setting_id': 'sort.simkl', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Title', '1': 'Date Added (desc)', '2': 'Release Date (desc)', '3': 'Date Added (asc)', '4': 'Release Date (asc)'}},
#==================== Contents Sort Order For Trakt Lists
{'setting_id': 'sort.collection', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Title', '1': 'Date Added (desc)', '2': 'Release Date (desc)', '3': 'Date Added (asc)', '4': 'Release Date (asc)'}},
{'setting_id': 'sort.watchlist', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Title', '1': 'Date Added (desc)', '2': 'Release Date (desc)', '3': 'Date Added (asc)', '4': 'Release Date (asc)'}},
#==================== Contents Sort Order For TMDb Lists
{'setting_id': 'tmdbsort.watchlist', 'setting_type': 'action', 'setting_default': '4', 'settings_options': {'0': 'Title', '1': 'Release Date (asc)', '2': 'Release Date (desc)',
'3': 'Shuffle', '4': 'Default from TMDb (None)'}},
{'setting_id': 'tmdbsort.favorites', 'setting_type': 'action', 'setting_default': '4', 'settings_options': {'0': 'Title', '1': 'Release Date (asc)', '2': 'Release Date (desc)',
'3': 'Shuffle', '4': 'Default from TMDb (None)'}},
#==================== Personal Lists
{'setting_id': 'personal_list.sort_unseen_to_top', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'personal_list.highlight_unseen', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'personal_list.unseen_highlight', 'setting_type': 'string', 'setting_default': 'FF4DDBFF'},
{'setting_id': 'personal_list.show_author', 'setting_type': 'boolean', 'setting_default': 'true'},
#==================== Widgets
{'setting_id': 'widget_refresh_timer', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'widget_refresh_notification', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'widget_hide_watched', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'widget_hide_next_page', 'setting_type': 'boolean', 'setting_default': 'false'},
#==================== RPDb Ratings Posters
{'setting_id': 'rpdb_enabled', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'Movies', '2': 'TV Shows', '3': 'Both'}},
{'setting_id': 'rpdb_format', 'setting_type': 'string', 'setting_default': ''},
#==================== Context Menu
{'setting_id': 'context_menu.enabled', 'setting_type': 'string',
'setting_default': 'extras,options,playback_options,external_scraper_settings,browse_movie_set,browse_seasons,browse_episodes,recommended,related,more_like_this,similar,in_trakt_list,' \
'mdblist_manager,simkl_manager,trakt_manager,tmdb_manager,personal_manager,favorites_manager,mark_watched,unmark_previous_episode,exit,refresh,reload'},
{'setting_id': 'context_menu.order', 'setting_type': 'string',
'setting_default': 'extras,options,playback_options,external_scraper_settings,browse_movie_set,browse_seasons,browse_episodes,recommended,related,more_like_this,similar,in_trakt_list,' \
'mdblist_manager,simkl_manager,trakt_manager,tmdb_manager,personal_manager,favorites_manager,mark_watched,unmark_previous_episode,exit,refresh,reload'},


#==================================================================================#
#====================================SINGLE EPISODE LISTS==========================#
#==================================================================================#
#==================== General
{'setting_id': 'single_ep_display', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'TITLE: SxE - EPISODE', '1': 'SxE - EPISODE', '2': 'EPISODE'}},
{'setting_id': 'single_ep_display_widget', 'setting_type': 'action', 'setting_default': '1', 'settings_options': {'0': 'TITLE: SxE - EPISODE', '1': 'SxE - EPISODE', '2': 'EPISODE'}},
{'setting_id': 'single_ep_unwatched_episodes', 'setting_type': 'boolean', 'setting_default': 'false'},
#==================== Next Episodes
{'setting_id': 'nextep.method', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Last Aired', '1': 'Last Watched'}},
{'setting_id': 'nextep.sort_type', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Recently Watched', '1': 'Airdate', '2': 'Title'}},
{'setting_id': 'nextep.sort_order', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Descending', '1': 'Ascending'}},
{'setting_id': 'nextep.limit_history', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'nextep.limit', 'setting_type': 'action', 'setting_default': '20', 'min_value': '1', 'max_value': '200'},
{'setting_id': 'nextep.include_unwatched', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'Watchlist', '2': 'Favorites', '3': 'Both'}},
{'setting_id': 'nextep.include_airdate', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'nextep.airing_today', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'nextep.include_unaired', 'setting_type': 'boolean', 'setting_default': 'false'},
#======+============= Trakt Calendar
{'setting_id': 'trakt.flatten_episodes', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'trakt.calendar_display', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'TITLE: SxE - EPISODE', '1': 'SxE - EPISODE', '2': 'EPISODE'}},
{'setting_id': 'trakt.calendar_display_widget', 'setting_type': 'action', 'setting_default': '1', 'settings_options': {'0': 'TITLE: SxE - EPISODE', '1': 'SxE - EPISODE', '2': 'EPISODE'}},
{'setting_id': 'trakt.calendar_sort_order', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Descending', '1': 'Ascending'}},
{'setting_id': 'trakt.calendar_previous_days', 'setting_type': 'action', 'setting_default': '7', 'min_value': '0', 'max_value': '14'},
{'setting_id': 'trakt.calendar_future_days', 'setting_type': 'action', 'setting_default': '7', 'min_value': '0', 'max_value': '14'},


#=====================================================================================#
#====================================META ACCOUNTS====================================#
#=====================================================================================#
#==================== Trakt
#==================== Trakt
{'setting_id': 'trakt.user', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'trakt.client', 'setting_type': 'string', 'setting_default': '30e6c73030cc41dbff996200ac3060cde689555ba207020e08a2175533b912c3'},
{'setting_id': 'trakt.secret', 'setting_type': 'string', 'setting_default': '726f6b12a9f0079d5850a7bb0e15860725cd487cbfb54ce5471de217639465c5'},
#==================== TMDb API
{'setting_id': 'tmdb_api', 'setting_type': 'string', 'setting_default': 'a0bf207c5ff6c0caabac0327e39b1cd2'},
#==================== TMDb Lists
{'setting_id': 'tmdb.lists_read_token', 'setting_type': 'string', 'setting_default': 'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJhMGJmMjA3YzVmZjZjMGNhYWJhYzAzMjdlMzliMWNkMiIsIm5iZiI6MTUwMzk0ODAxMC43NTQsInN1YiI6IjU5YTQ2Y2U4YzNhMzY4MGIxMjAwMjgxYiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.2pYaMVzWy-TNg2SBlkP_CrYWpaxcU7LZIZLPdgJp9jw'},
{'setting_id': 'tmdb.token', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'tmdb.username', 'setting_type': 'string', 'setting_default': 'empty_setting'},
#==================== OMDb
{'setting_id': 'omdb_api', 'setting_type': 'string', 'setting_default': 'empty_setting'},
#==================== RPDb
{'setting_id': 'rpdb_api', 'setting_type': 'string', 'setting_default': 't0-free-rpdb'},
#==================== Google API
{'setting_id': 'google_api', 'setting_type': 'string', 'setting_default': 'empty_setting'},
#==================== GROQ API
{'setting_id': 'groq_api', 'setting_type': 'string', 'setting_default': 'empty_setting'},


#=====================================================================================#
#====================================STREAMING ACCOUNTS===============================#
#=====================================================================================#
#==================== External
{'setting_id': 'provider.external', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'external_scraper.name', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'external_scraper.slot1.module', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'external_scraper.slot1.name', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'external_scraper.slot1.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'external_scraper.slot2.module', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'external_scraper.slot2.name', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'external_scraper.slot2.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'external_scraper.slot3.module', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'external_scraper.slot3.name', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'external_scraper.slot3.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'external_scraper.run_mode', 'setting_type': 'action', 'setting_default': '1', 'settings_options': {'1': 'Series (Fallback by Slot Order)', '2': 'Series (All Slots in Order)', '3': 'Primary Slot + Parallel Fallback', '0': 'Parallel (All Enabled Slots)'}},
{'setting_id': 'migration.external_scraper_slots_v160', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'migration.cache_check_pm_oc_tb_v129e', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'migration.ad_cache_check_removed_v173', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'migration.my_content_nav_mode_v136', 'setting_type': 'boolean', 'setting_default': 'false'},
#==================== Real Debrid
{'setting_id': 'rd.token', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'rd.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'rd.cache_check', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'rd.account_id', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'store_resolved_to_cloud.real-debrid', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'All', '2': 'Show Packs Only'}},
{'setting_id': 'provider.rd_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'rd_cloud.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'check.rd_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.rd_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results.sort_rdcloud_first', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'rd.priority', 'setting_type': 'action', 'setting_default': '10', 'min_value': '1', 'max_value': '10'},
{'setting_id': 'rd.alternate_base_url', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'rd.free_active_slot', 'setting_type': 'boolean', 'setting_default': 'false'},
#==================== Premiumize
{'setting_id': 'pm.token', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'pm.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'pm.cache_check', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'pm.include_uncached', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'pm.account_id', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'store_resolved_to_cloud.premiumize.me', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'All', '2': 'Show Packs Only'}},
{'setting_id': 'provider.pm_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'pm_cloud.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'check.pm_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.pm_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results.sort_pmcloud_first', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'pm.priority', 'setting_type': 'action', 'setting_default': '10', 'min_value': '1', 'max_value': '10'},
#==================== All Debrid
{'setting_id': 'ad.token', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'ad.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'ad.cache_check', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'ad.account_id', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'store_resolved_to_cloud.alldebrid', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'All', '2': 'Show Packs Only'}},
{'setting_id': 'provider.ad_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'ad_cloud.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'check.ad_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.ad_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results.sort_adcloud_first', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'ad.priority', 'setting_type': 'action', 'setting_default': '10', 'min_value': '1', 'max_value': '10'},
#==================== Offcloud
{'setting_id': 'oc.token', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'oc.account_id', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'oc.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'oc.cache_check', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'oc.include_uncached', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'store_resolved_to_cloud.offcloud', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'All', '2': 'Show Packs Only'}},
{'setting_id': 'oc.notify_cloud_ready', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'provider.oc_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'oc_cloud.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'check.oc_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.oc_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results.sort_occloud_first', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'oc.priority', 'setting_type': 'action', 'setting_default': '10', 'min_value': '1', 'max_value': '10'},
#==================== TorBox
{'setting_id': 'tb.token', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'tb.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'tb.cache_check', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'tb.include_uncached', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'store_resolved_to_cloud.torbox', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'All', '2': 'Show Packs Only'}},
{'setting_id': 'tb.notify_cloud_ready', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'provider.tb_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'tb_cloud.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'check.tb_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.tb_cloud', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results.sort_tbcloud_first', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'tb.priority', 'setting_type': 'action', 'setting_default': '10', 'min_value': '1', 'max_value': '10'},
#==================== EasyNews
{'setting_id': 'provider.easynews', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'services.expiry_alert_days', 'setting_type': 'action', 'setting_default': '7', 'min_value': '0', 'max_value': '90'},
{'setting_id': 'services.expiry_alert_state', 'setting_type': 'string', 'setting_default': '{}'},
{'setting_id': 'easynews_user', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'easynews_password', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'easynews.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'easynews.filter_lang', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'easynews.exclude_adult', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'easynews.lang_filters', 'setting_type': 'string', 'setting_default': 'eng'},
{'setting_id': 'easynews.refresh_credentials', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'easynews.lang_include_unknown', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'easynews.fallback_search', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'easynews.search_width', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Focused', '1': 'Balanced', '2': 'Broad'}},
{'setting_id': 'check.easynews', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.easynews', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'en.priority', 'setting_type': 'action', 'setting_default': '7', 'min_value': '1', 'max_value': '10'},
#==================== AIOStreams
{'setting_id': 'provider.aiostreams', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'aiostreams.instance', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {
	'0': 'Kuu — https://aiostreams.stremio.ru',
	'1': 'Viren — https://aiostreams.viren070.me',
	'2': 'Yeb — https://aiostreams.fortheweak.cloud',
	'3': 'Midnight — https://aiostreamsfortheweebsstable.midnightignite.me',
	'4': 'Custom — set URL below',
	# '5' ElfHosted — hidden from picker (Search API disabled on public host); keep id reserved.
}},
{'setting_id': 'aiostreams.profiles', 'setting_type': 'string', 'setting_default': '{}'},
{'setting_id': 'aiostreams.custom_url', 'setting_type': 'string', 'setting_default': ''},
{'setting_id': 'aiostreams.username', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'aiostreams.password', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'aiostreams.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'aiostreams.preserve_order', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'check.aiostreams', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.aiostreams', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'aio.priority', 'setting_type': 'action', 'setting_default': '7', 'min_value': '1', 'max_value': '10'},
{'setting_id': 'provider.aiostreams_highlight', 'setting_type': 'string', 'setting_default': 'FF00D4FF'},
#=========+========== Folders
{'setting_id': 'provider.folders', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'folders.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'check.folders', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.folders', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results.sort_folders_first', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'results.folders_ignore_filters', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'folders.priority', 'setting_type': 'action', 'setting_default': '6', 'min_value': '1', 'max_value': '10'},
#==================== NZB Indexers
{'setting_id': 'provider.nzb', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'nzb1.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'nzb1.label', 'setting_type': 'string', 'setting_default': 'NZB Indexer 1'},
{'setting_id': 'nzb1.url', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'nzb1.key', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'nzb2.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'nzb2.label', 'setting_type': 'string', 'setting_default': 'NZB Indexer 2'},
{'setting_id': 'nzb2.url', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'nzb2.key', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'nzb3.enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'nzb3.label', 'setting_type': 'string', 'setting_default': 'NZB Indexer 3'},
{'setting_id': 'nzb3.url', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'nzb3.key', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'nzb.title_filter', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'nzb.fallback_search', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'nzb.search_width', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Focused', '1': 'Balanced', '2': 'Broad'}},
{'setting_id': 'check.nzb', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay.nzb', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'nzb.priority', 'setting_type': 'action', 'setting_default': '7', 'min_value': '1', 'max_value': '10'},
{'setting_id': 'provider.nzb_highlight', 'setting_type': 'string', 'setting_default': 'FFD4A017'},


#===============================================================================#
#====================================RESULTS====================================#
#===============================================================================#
#==================== Display
{'setting_id': 'results.timeout', 'setting_type': 'action', 'setting_default': '20', 'min_value': '1'},
{'setting_id': 'results.list_format', 'setting_type': 'string', 'setting_default': 'List'},
#==================== Rescrape
{'setting_id': 'rescrape.cache_ignored', 'setting_type': 'action', 'setting_default': '1', 'settings_options': {'0': 'Off', '1': 'Auto', '2': 'Prompt'}},
{'setting_id': 'rescrape.cache_ignored.order', 'setting_type': 'action', 'setting_default': '0', 'min_value': '1', 'max_value': '5'},
{'setting_id': 'rescrape.imdb_year', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Off', '1': 'Auto', '2': 'Prompt'}},
{'setting_id': 'rescrape.imdb_year.order', 'setting_type': 'action', 'setting_default': '1', 'min_value': '1', 'max_value': '5'},
{'setting_id': 'rescrape.with_all', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Off', '1': 'Auto', '2': 'Prompt'}},
{'setting_id': 'rescrape.with_all.order', 'setting_type': 'action', 'setting_default': '2', 'min_value': '1', 'max_value': '5'},
{'setting_id': 'rescrape.episode_group', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Off', '1': 'Auto', '2': 'Prompt'}},
{'setting_id': 'rescrape.episode_group.order', 'setting_type': 'action', 'setting_default': '3', 'min_value': '1', 'max_value': '5'},
{'setting_id': 'rescrape.ignore_filters', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Off', '1': 'Auto', '2': 'Prompt'}},
{'setting_id': 'rescrape.ignore_filters.order', 'setting_type': 'action', 'setting_default': '4', 'min_value': '1', 'max_value': '5'},
{'setting_id': 'rescrape.full_scrape', 'setting_type': 'action', 'setting_default': '2', 'settings_options': {'0': 'Off', '1': 'Auto', '2': 'Prompt'}},
{'setting_id': 'rescrape.full_scrape.order', 'setting_type': 'action', 'setting_default': '5', 'min_value': '1', 'max_value': '5'},
#==================== Sorting and Filtering
{'setting_id': 'results.sort_order_display', 'setting_type': 'string', 'setting_default': 'Quality, Size, Provider'},
{'setting_id': 'results.filter_size_method', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Off', '1': 'Use Line Speed', '2': 'Use Size'}},
{'setting_id': 'results.line_speed', 'setting_type': 'action', 'setting_default': '25', 'min_value': '1'},
{'setting_id': 'results.movie_size_max', 'setting_type': 'action', 'setting_default': '10000', 'min_value': '1'},
{'setting_id': 'results.episode_size_max', 'setting_type': 'action', 'setting_default': '3000', 'min_value': '1'},
{'setting_id': 'results.movie_size_min', 'setting_type': 'action', 'setting_default': '0', 'min_value': '0'},
{'setting_id': 'results.episode_size_min', 'setting_type': 'action', 'setting_default': '0', 'min_value': '0'},
{'setting_id': 'results.size_unknown', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'results.size_sort_weighted', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results.size_sort_direction', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Descending', '1': 'Ascending'}},
{'setting_id': 'results.uncached_min_seeders', 'setting_type': 'action', 'setting_default': '0', 'min_value': '0'},
{'setting_id': 'results.limit_number_quality', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'results.limit_number_total', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'results.include.unknown.size', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'filter.include_prerelease', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Include', '1': 'Exclude'}},
{'setting_id': 'filter.hevc', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Include', '1': 'Exclude'}},
{'setting_id': 'filter.hevc.max_quality', 'setting_type': 'action', 'setting_default': '4K', 'settings_options': {'4K': '4K', '1080p': '1080p', '720p': '720p', 'SD': 'SD'}},
{'setting_id': 'filter.hevc.max_autoplay_quality', 'setting_type': 'action', 'setting_default': '4K', 'settings_options': {'4K': '4K', '1080p': '1080p', '720p': '720p', 'SD': 'SD'}},
{'setting_id': 'filter.3d', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Include', '1': 'Exclude'}},
{'setting_id': 'filter.hdr', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Include', '1': 'Exclude'}},
{'setting_id': 'filter.dv', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Include', '1': 'Exclude'}},
{'setting_id': 'filter.av1', 'setting_type': 'action', 'setting_default': '0', 'settings_options':{'0': 'Include', '1': 'Exclude'}},
{'setting_id': 'filter.enhanced_upscaled', 'setting_type': 'action', 'setting_default': '0', 'settings_options':{'0': 'Include', '1': 'Exclude'}},
{'setting_id': 'filter.sort_to_top', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'Source Select', '2': 'Autoplay', '3': 'Both'}},
{'setting_id': 'filter.preferred_filters', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'filter_audio', 'setting_type': 'string', 'setting_default': 'empty_setting'},
#==================== Results Color Highlights
{'setting_id': 'highlight.type', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Provider', '1': 'Quality', '2': 'Single Color'}},
{'setting_id': 'provider.easynews_highlight', 'setting_type': 'string', 'setting_default': 'FF00B3B2'},
{'setting_id': 'provider.debrid_cloud_highlight', 'setting_type': 'string', 'setting_default': 'FF7A01CC'},
{'setting_id': 'provider.folders_highlight', 'setting_type': 'string', 'setting_default': 'FFB36B00'},
{'setting_id': 'provider.rd_highlight', 'setting_type': 'string', 'setting_default': 'FF3C9900'},
{'setting_id': 'provider.pm_highlight', 'setting_type': 'string', 'setting_default': 'FFFF3300'},
{'setting_id': 'provider.ad_highlight', 'setting_type': 'string', 'setting_default': 'FFE6B800'},
{'setting_id': 'provider.oc_highlight', 'setting_type': 'string', 'setting_default': 'FF5C6BC0'},
{'setting_id': 'provider.tb_highlight', 'setting_type': 'string', 'setting_default': 'FF01662A'},
{'setting_id': 'scraper_4k_highlight', 'setting_type': 'string', 'setting_default': 'FFFF00FE'},
{'setting_id': 'scraper_1080p_highlight', 'setting_type': 'string', 'setting_default': 'FFE6B800'},
{'setting_id': 'scraper_720p_highlight', 'setting_type': 'string', 'setting_default': 'FF3C9900'},
{'setting_id': 'scraper_SD_highlight', 'setting_type': 'string', 'setting_default': 'FF0166FF'},
{'setting_id': 'scraper_single_highlight', 'setting_type': 'string', 'setting_default': 'FF008EB2'},
{'setting_id': 'scraper_total_highlight', 'setting_type': 'string', 'setting_default': 'FFFFFFFF'},
{'setting_id': 'highlight.scrape_progress_colours', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'highlight.tint_focused_background', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'highlight.background_opacity', 'setting_type': 'string', 'setting_default': '66'},
{'setting_id': 'highlight.background_opacity_name', 'setting_type': 'string', 'setting_default': '40%'},


#===============================================================================#
#===================================PLAYBACK====================================#
#===============================================================================#
#==================== Playback Movies
{'setting_id': 'auto_play_movie', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results_quality_movie', 'setting_type': 'string', 'setting_default': 'SD, 720p, 1080p, 4K'},
{'setting_id': 'autoplay_quality_movie', 'setting_type': 'string', 'setting_default': 'SD, 720p, 1080p, 4K'},
{'setting_id': 'auto_resume_movie', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Never', '1': 'Always', '2': 'Autoplay Only'}},
{'setting_id': 'stinger_alert.show', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'stinger_alert.window_percentage', 'setting_type': 'action', 'setting_default': '90', 'min_value': '1', 'max_value': '99'},
{'setting_id': 'stinger_alert.alert_timing', 'setting_type': 'action', 'setting_default': '1', 'settings_options': {'0': 'Playback Percentage', '1': 'Chapter Info', '2': 'Subtitles Info'}},
#==================== Playback Episodes
{'setting_id': 'auto_play_episode', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'results_quality_episode', 'setting_type': 'string', 'setting_default': 'SD, 720p, 1080p, 4K'},
{'setting_id': 'autoplay_quality_episode', 'setting_type': 'string', 'setting_default': 'SD, 720p, 1080p, 4K'},
{'setting_id': 'autoplay_next_episode', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoplay_alert_method', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Window', '1': 'Notification'}},
{'setting_id': 'autoplay_default_action', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Play', '1': 'Cancel', '2': 'Pause & Wait'}},
{'setting_id': 'autoplay_next_window_percentage', 'setting_type': 'action', 'setting_default': '95', 'min_value': '75', 'max_value': '99'},
{'setting_id': 'autoplay_alert_timing', 'setting_type': 'action', 'setting_default': '1', 'settings_options': {'0': 'Playback Percentage', '1': 'Chapter Info', '2': 'Subtitles Info', '3': 'IntroDB Info'}},
{'setting_id': 'autoplay_skip_intro', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Off', '2': 'Auto', '1': 'Prompt'}},
{'setting_id': 'skip_intro_all_episodes', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'autoplay_watching_check', 'setting_type': 'action', 'setting_default': '3', 'min_value': '0', 'max_value': '5'},
{'setting_id': 'autoplay_random_continual_watching_check', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'autoscrape_next_episode', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'autoscrape_next_window_percentage', 'setting_type': 'action', 'setting_default': '95', 'min_value': '75', 'max_value': '99'},
{'setting_id': 'autoscrape_alert_timing', 'setting_type': 'action', 'setting_default': '1', 'settings_options': {'0': 'Playback Percentage', '1': 'Chapter Info', '2': 'Subtitles Info', '3': 'IntroDB Info'}},
{'setting_id': 'autoscrape_confirm', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'auto_resume_episode', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Never', '1': 'Always', '2': 'Autoplay Only'}},
#==================== Playback Utilities
{'setting_id': 'playback.limit_resolve', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'easynews.playback_method', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'None', '1': 'Retry', '2': 'No Seek', '3': 'Both'}},
{'setting_id': 'easynews.playback_method_retries', 'setting_type': 'action', 'setting_default': '1', 'min_value': '1', 'max_value': '4'},
{'setting_id': 'easynews.playback_method_limited', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'playback.volumecheck_enabled', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'playback.volumecheck_percent', 'setting_type': 'action', 'setting_default': '50', 'min_value': '1', 'max_value': '100'},
{'setting_id': 'playback.auto_enable_subs', 'setting_type': 'boolean', 'setting_default': 'false'},
{'setting_id': 'playback.opensubs_api_key', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'playback.opensubs_username', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'playback.opensubs_password', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'playback.subs_source', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'Local Subtitles', '1': 'SubMaker', '2': 'OpenSubtitles'}},
{'setting_id': 'playback.submaker_manifest', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'playback.submaker_language', 'setting_type': 'action', 'setting_default': '0', 'settings_options': {'0': 'English', '1': 'Arabic', '2': 'Bengali',
'3': 'Bulgarian', '4': 'Chinese', '5': 'Croatian', '6': 'Czech', '7': 'Danish', '8': 'Dutch', '9': 'Finnish', '10': 'French', '11': 'German',
'12': 'Greek', '13': 'Hebrew', '14': 'Hindi', '15': 'Hungarian', '16': 'Icelandic', '17': 'Indonesian', '18': 'Italian', '19': 'Japanese',
'20': 'Korean', '21': 'Malay', '22': 'Norwegian', '23': 'Persian', '24': 'Polish', '25': 'Portuguese', '26': 'Portuguese (Brazil)', '27': 'Punjabi',
'28': 'Romanian', '29': 'Russian', '30': 'Serbian', '31': 'Slovenian', '32': 'Spanish', '33': 'Swedish', '34': 'Tagalog', '35': 'Tamil', '36': 'Telugu',
'37': 'Thai', '38': 'Turkish', '39': 'Ukrainian', '40': 'Urdu', '41': 'Vietnamese', '42': 'Forced Only (Local Subs)'}},
{'setting_id': 'playback.submaker_prefer_local', 'setting_type': 'boolean', 'setting_default': 'true'},
{'setting_id': 'playback.subs_show_notifications', 'setting_type': 'boolean', 'setting_default': 'true'},


#=========================================================================================#
#======================================HIDDEN=============================================#
#=========================================================================================#
{'setting_id': 'tmdb.account_id', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'tmdb.session_id', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'tmdb.account_session_id', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'reuse_language_invoker', 'setting_type': 'string', 'setting_default': 'true'},
{'setting_id': 'addon_icon_choice_name', 'setting_type': 'string', 'setting_default': 'icon.png'},
{'setting_id': 'widget_refresh_timer_name', 'setting_type': 'string', 'setting_default': 'Off'},
{'setting_id': 'mpaa_region_display_name', 'setting_type': 'string', 'setting_default': 'United States'},
{'setting_id': 'lists_cache_duraton_display_name', 'setting_type': 'string', 'setting_default': '1 Day'},
{'setting_id': 'results.limit_number_quality_name', 'setting_type': 'string', 'setting_default': 'Off'},
{'setting_id': 'results.limit_number_total_name', 'setting_type': 'string', 'setting_default': 'Off'},
{'setting_id': 'rpdb_format_name', 'setting_type': 'string', 'setting_default': 'Default'},
{'setting_id': 'window_theme_contrast', 'setting_type': 'string', 'setting_default': 'FF4a4347'},
{'setting_id': 'window_theme_name', 'setting_type': 'string', 'setting_default': 'Dark'},
{'setting_id': 'window_theme_opacity_name', 'setting_type': 'string', 'setting_default': '80%'},
{'setting_id': 'external_scraper.module', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'trakt.next_daily_clear', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'trakt.expires', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'trakt.refresh', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'trakt.token', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'playback.opensubs_token', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'tmdblist.list_sort', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'tmdblist.list_sort_name', 'setting_type': 'string', 'setting_default': 'Title'},
{'setting_id': 'personal_list.list_sort', 'setting_type': 'string', 'setting_default': '0'},
{'setting_id': 'personal_list.list_sort_name', 'setting_type': 'string', 'setting_default': 'Title'},
{'setting_id': 'rd.client_id', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'rd.refresh', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'rd.secret', 'setting_type': 'string', 'setting_default': 'empty_setting'},
{'setting_id': 'results.sort_order', 'setting_type': 'string', 'setting_default': '1'},
{'setting_id': 'folder1.display_name', 'setting_type': 'string', 'setting_default': 'Folder 1'},
{'setting_id': 'folder1.movies_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder1.tv_shows_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder2.display_name', 'setting_type': 'string', 'setting_default': 'Folder 2'},
{'setting_id': 'folder2.movies_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder2.tv_shows_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder3.display_name', 'setting_type': 'string', 'setting_default': 'Folder 3'},
{'setting_id': 'folder3.movies_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder3.tv_shows_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder4.display_name', 'setting_type': 'string', 'setting_default': 'Folder 4'},
{'setting_id': 'folder4.movies_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder4.tv_shows_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder5.display_name', 'setting_type': 'string', 'setting_default': 'Folder 5'},
{'setting_id': 'folder5.movies_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'folder5.tv_shows_directory', 'setting_type': 'path', 'setting_default': 'None', 'browse_mode': '0'},
{'setting_id': 'extras.enabled', 'setting_type': 'string', 'setting_default': '2050,2051,2052,2053,2054,2055,2056,2057,2058,2059,2060,2061,2062,2063,2064,2065,2066'},
{'setting_id': 'extras.order', 'setting_type': 'string', 'setting_default': '2050,2051,2052,2053,2054,2055,2056,2057,2058,2059,2060,2061,2062,2063,2064,2065,2066'},
{'setting_id': 'rescrape.enabled', 'setting_type': 'string', 'setting_default': 'cache_ignored,imdb_year,with_all,episode_group,ignore_filters,full_scrape'},
{'setting_id': 'rescrape.order', 'setting_type': 'string', 'setting_default': 'cache_ignored,imdb_year,with_all,episode_group,ignore_filters,full_scrape'},
{'setting_id': 'extras.tvshow.button10', 'setting_type': 'string', 'setting_default': 'tvshow_browse'},
{'setting_id': 'extras.tvshow.button11', 'setting_type': 'string', 'setting_default': 'show_trailers'},
{'setting_id': 'extras.tvshow.button12', 'setting_type': 'string', 'setting_default': 'show_keywords'},
{'setting_id': 'extras.tvshow.button13', 'setting_type': 'string', 'setting_default': 'show_images'},
{'setting_id': 'extras.tvshow.button14', 'setting_type': 'string', 'setting_default': 'show_extrainfo'},
{'setting_id': 'extras.tvshow.button15', 'setting_type': 'string', 'setting_default': 'show_genres'},
{'setting_id': 'extras.tvshow.button16', 'setting_type': 'string', 'setting_default': 'play_nextep'},
{'setting_id': 'extras.tvshow.button17', 'setting_type': 'string', 'setting_default': 'show_options'},
{'setting_id': 'extras.movie.button10', 'setting_type': 'string', 'setting_default': 'movies_play'},
{'setting_id': 'extras.movie.button11', 'setting_type': 'string', 'setting_default': 'show_trailers'},
{'setting_id': 'extras.movie.button12', 'setting_type': 'string', 'setting_default': 'show_keywords'},
{'setting_id': 'extras.movie.button13', 'setting_type': 'string', 'setting_default': 'show_images'},
{'setting_id': 'extras.movie.button14', 'setting_type': 'string', 'setting_default': 'show_extrainfo'},
{'setting_id': 'extras.movie.button15', 'setting_type': 'string', 'setting_default': 'show_genres'},
{'setting_id': 'extras.movie.button16', 'setting_type': 'string', 'setting_default': 'show_director'},
{'setting_id': 'extras.movie.button17', 'setting_type': 'string', 'setting_default': 'show_options'},
	]
	return _DEFAULTS_LIST
