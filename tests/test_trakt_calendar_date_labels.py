import importlib.util
import sys
import types
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UTILS_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'utils.py'
SETTINGS_CACHE_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'caches' / 'settings_cache.py'

STUB_MODULE_KEYS = ('modules', 'modules.kodi_utils', 'modules.settings', 'caches', 'caches.base_cache')


def _install_stub_modules():
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
	kodi_utils.sleep = lambda *args, **kwargs: None
	kodi_utils.translate_path = lambda path: path

	modules = types.ModuleType('modules')
	modules.__path__ = []
	modules.kodi_utils = kodi_utils
	settings = types.ModuleType('modules.settings')
	settings.max_threads = lambda: 1

	caches = types.ModuleType('caches')
	caches.__path__ = []
	base_cache = types.ModuleType('caches.base_cache')
	base_cache.connect_database = lambda name: None

	sys.modules['modules'] = modules
	sys.modules['modules.kodi_utils'] = kodi_utils
	sys.modules['modules.settings'] = settings
	sys.modules['caches'] = caches
	sys.modules['caches.base_cache'] = base_cache


def _load_module(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class TraktCalendarDateLabelTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls._original_sys_modules = {}
		for key in STUB_MODULE_KEYS:
			if key in sys.modules:
				cls._original_sys_modules[key] = sys.modules[key]
		_install_stub_modules()
		cls.utils = _load_module('utils_under_test', UTILS_PATH)
		cls.settings_cache = _load_module('settings_cache_under_test_date_labels', SETTINGS_CACHE_PATH)

	@classmethod
	def tearDownClass(cls):
		for key in STUB_MODULE_KEYS:
			if key in cls._original_sys_modules:
				sys.modules[key] = cls._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)

	def setUp(self):
		self.today = date(2026, 7, 19)

	def test_words_mode_uses_relative_labels(self):
		make_day = self.utils.make_day
		self.assertEqual('YESTERDAY', make_day(self.today, date(2026, 7, 18)))
		self.assertEqual('TODAY', make_day(self.today, date(2026, 7, 19)))
		self.assertEqual('TOMORROW', make_day(self.today, date(2026, 7, 20)))
		self.assertEqual('TUESDAY', make_day(self.today, date(2026, 7, 21)))

	def test_date_mode_ignores_relative_labels(self):
		make_day = self.utils.make_day
		self.assertEqual('07/19/2026', make_day(self.today, date(2026, 7, 19), '%m/%d/%Y', use_words=False))
		self.assertEqual('20/07/2026', make_day(self.today, date(2026, 7, 20), '%d/%m/%Y', use_words=False))
		self.assertEqual('2026-07-21', make_day(self.today, date(2026, 7, 21), '%Y-%m-%d', use_words=False))

	def test_default_setting_metadata(self):
		defaults = {s['setting_id']: s for s in self.settings_cache.default_settings()}
		setting = defaults.get('trakt.calendar_date_labels')
		self.assertIsNotNone(setting, 'trakt.calendar_date_labels missing from default settings')
		self.assertEqual('action', setting['setting_type'])
		self.assertEqual('0', setting['setting_default'])
		self.assertEqual({
			'0': 'Words / YYYY-MM-DD', '7': 'Words / MM-DD-YYYY', '8': 'Words / DD-MM-YYYY',
			'3': 'YYYY-MM-DD', '1': 'MM-DD-YYYY', '2': 'DD-MM-YYYY',
			'6': 'Day + YYYY-MM-DD', '4': 'Day + MM-DD-YYYY', '5': 'Day + DD-MM-YYYY'},
						 setting['settings_options'])


if __name__ == '__main__':
	unittest.main()
