import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_CACHE_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'caches' / 'settings_cache.py'


def _load_settings_cache_module():
	properties = {}
	kodi_utils = types.ModuleType('modules.kodi_utils')
	kodi_utils.addon_fanart = lambda: ''
	kodi_utils.addon_info = lambda key: 'test-version' if key == 'version' else ''
	kodi_utils.clear_property = lambda key: properties.pop(key, None)
	kodi_utils.get_property = lambda key: properties.get(key, '')
	kodi_utils.is_android = lambda: False
	kodi_utils.logger = lambda *args, **kwargs: None
	kodi_utils.notification = lambda *args, **kwargs: None
	kodi_utils.path_exists = lambda path: False
	kodi_utils.schedule_widget_refresh = lambda **kwargs: None
	kodi_utils.set_property = lambda key, value: properties.__setitem__(key, value)
	kodi_utils.translate_path = lambda path: path

	modules = types.ModuleType('modules')
	modules.__path__ = []
	modules.kodi_utils = kodi_utils
	settings = types.ModuleType('modules.settings')
	settings.migrate_cm_manager_order_for_upgrade = lambda: False
	settings.migrate_external_scraper_context_menu_for_upgrade = lambda had_existing: False
	settings.migrate_external_scraper_run_mode_for_upgrade = lambda had_existing: False
	settings.migrate_external_scraper_slots_for_upgrade = lambda had_existing: False
	settings.migrate_mdblist_context_menu_for_upgrade = lambda had_existing: False
	settings.migrate_simkl_context_menu_for_upgrade = lambda had_existing: False

	caches = types.ModuleType('caches')
	caches.__path__ = []
	base_cache = types.ModuleType('caches.base_cache')
	base_cache.connect_database = lambda name: None

	sys.modules['modules'] = modules
	sys.modules['modules.kodi_utils'] = kodi_utils
	sys.modules['modules.settings'] = settings
	sys.modules['caches'] = caches
	sys.modules['caches.base_cache'] = base_cache

	spec = importlib.util.spec_from_file_location('settings_cache_under_test', SETTINGS_CACHE_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	module._test_properties = properties
	return module


class FakeSettingsCache:
	def __init__(self, initial=None):
		self.data = dict(initial or {})
		self.rows = {}

	def clean_database(self):
		return True

	def clear_db_cache(self):
		pass

	def get_all(self):
		return dict(self.data)

	def remove_setting(self, setting_id):
		self.data.pop(setting_id, None)

	def set_many(self, settings_list, load_properties=True):
		for row in settings_list:
			self.rows[row[0]] = row
			self.data[row[0]] = row[3]

	def set_memory_cache(self, setting_id, value):
		pass

	def write_db(self, setting_id, setting_value, setting_info=None):
		self.data[setting_id] = setting_value


class CalendarDisplayMigrationTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.module = _load_settings_cache_module()

	def setUp(self):
		self.module._test_properties.clear()
		self.module.default_settings = lambda: [
			{'setting_id': 'single_ep_display', 'setting_type': 'action', 'setting_default': '0',
			 'settings_options': {'0': 'TITLE: SxE - EPISODE', '1': 'SxE - EPISODE', '2': 'EPISODE'}},
			{'setting_id': 'single_ep_display_widget', 'setting_type': 'action', 'setting_default': '1',
			 'settings_options': {'0': 'TITLE: SxE - EPISODE', '1': 'SxE - EPISODE', '2': 'EPISODE'}},
			{'setting_id': 'trakt.calendar_display', 'setting_type': 'action', 'setting_default': '0',
			 'settings_options': {'0': 'TITLE: SxE - EPISODE', '1': 'SxE - EPISODE', '2': 'EPISODE'}},
			{'setting_id': 'trakt.calendar_display_widget', 'setting_type': 'action', 'setting_default': '1',
			 'settings_options': {'0': 'TITLE: SxE - EPISODE', '1': 'SxE - EPISODE', '2': 'EPISODE'}},
		]

	def _sync(self, initial):
		cache = FakeSettingsCache(initial)
		self.module.settings_cache = cache
		result = self.module.sync_settings({'silent': 'true', 'load_properties': 'false', 'force': 'true'})
		self.assertEqual('synced', result)
		return cache

	def test_upgrade_copies_existing_single_episode_preferences(self):
		cache = self._sync({
			'single_ep_display': '2',
			'single_ep_display_widget': '0',
		})

		self.assertEqual('2', cache.data['trakt.calendar_display'])
		self.assertEqual('0', cache.data['trakt.calendar_display_widget'])
		self.assertEqual('EPISODE', cache.data['trakt.calendar_display_name'])
		self.assertEqual('TITLE: SxE - EPISODE', cache.data['trakt.calendar_display_widget_name'])
		self.assertEqual('0', cache.rows['trakt.calendar_display'][2])
		self.assertEqual('1', cache.rows['trakt.calendar_display_widget'][2])

	def test_fresh_install_uses_new_setting_defaults(self):
		cache = self._sync({})

		self.assertEqual('0', cache.data['trakt.calendar_display'])
		self.assertEqual('1', cache.data['trakt.calendar_display_widget'])
		self.assertEqual('TITLE: SxE - EPISODE', cache.data['trakt.calendar_display_name'])
		self.assertEqual('SxE - EPISODE', cache.data['trakt.calendar_display_widget_name'])

	def test_existing_calendar_preferences_are_not_overwritten(self):
		cache = self._sync({
			'single_ep_display': '2',
			'single_ep_display_widget': '0',
			'trakt.calendar_display': '1',
			'trakt.calendar_display_widget': '2',
		})

		self.assertEqual('1', cache.data['trakt.calendar_display'])
		self.assertEqual('2', cache.data['trakt.calendar_display_widget'])


if __name__ == '__main__':
	unittest.main()
