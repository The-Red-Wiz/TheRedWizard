import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHED_STATUS_PATH = ROOT / 'plugin.video.redlight' / 'resources' / 'lib' / 'modules' / 'watched_status.py'
STUB_MODULE_KEYS = (
	'apis', 'apis.trakt_api', 'apis.simkl_api', 'apis.mdblist_api',
	'caches', 'caches.base_cache', 'caches.trakt_cache',
	'modules', 'modules.kodi_utils', 'modules.utils', 'modules.metadata', 'modules.settings'
)


class FakeResult:
	def __init__(self, rows=None):
		self.rows = rows or []

	def fetchall(self):
		return self.rows

	def fetchone(self):
		return self.rows[0] if self.rows else None


class FakeDatabase:
	def __init__(self, rows=None):
		self.rows = rows or []
		self.deletes = []

	def execute(self, sql, params=None):
		if sql.startswith('SELECT'):
			return FakeResult(self.rows)
		if sql.startswith('DELETE'):
			self.deletes.append(params)
		return FakeResult()


def _load_watched_status_module(active_provider, databases, progress_calls):
	apis = types.ModuleType('apis')
	apis.__path__ = []

	trakt_api = types.ModuleType('apis.trakt_api')
	trakt_api.trakt_watched_status_mark = lambda *args, **kwargs: None
	trakt_api.trakt_official_status = lambda *args, **kwargs: True
	trakt_api.trakt_progress = lambda *args, **kwargs: progress_calls.append(('trakt', args, kwargs))
	trakt_api.trakt_get_hidden_items = lambda *args, **kwargs: []

	simkl_api = types.ModuleType('apis.simkl_api')
	simkl_api.simkl_watched_status_mark = lambda *args, **kwargs: None
	simkl_api.simkl_progress = lambda *args, **kwargs: progress_calls.append(('simkl', args, kwargs))
	simkl_api.simkl_official_status = lambda *args, **kwargs: True

	mdblist_api = types.ModuleType('apis.mdblist_api')
	mdblist_api.mdblist_watched_status_mark = lambda *args, **kwargs: None
	mdblist_api.mdblist_progress = lambda *args, **kwargs: progress_calls.append(('mdblist', args, kwargs))
	mdblist_api.mdblist_official_status = lambda *args, **kwargs: True

	caches = types.ModuleType('caches')
	caches.__path__ = []
	base_cache = types.ModuleType('caches.base_cache')
	base_cache.connect_database = lambda name: databases[name]
	base_cache.database = types.SimpleNamespace(connect=lambda path: None)
	trakt_cache = types.ModuleType('caches.trakt_cache')
	trakt_cache.clear_trakt_collection_watchlist_data = lambda *args, **kwargs: None

	modules = types.ModuleType('modules')
	modules.__path__ = []
	kodi_utils = types.ModuleType('modules.kodi_utils')
	kodi_utils.kodi_progress_background = lambda *args, **kwargs: None
	kodi_utils.sleep = lambda *args, **kwargs: None
	kodi_utils.get_video_database_path = lambda: ''
	kodi_utils.notification = lambda *args, **kwargs: None
	kodi_utils.kodi_refresh = lambda *args, **kwargs: None
	kodi_utils.logger = lambda *args, **kwargs: None

	utils = types.ModuleType('modules.utils')
	utils.get_datetime = lambda *args, **kwargs: None
	utils.adjust_premiered_date = lambda *args, **kwargs: None
	utils.sort_for_article = lambda value: value
	utils.TaskPool = lambda *args, **kwargs: None

	metadata = types.ModuleType('modules.metadata')
	settings = types.ModuleType('modules.settings')
	settings.watched_indicators = lambda: active_provider

	modules.kodi_utils = kodi_utils
	modules.utils = utils
	modules.metadata = metadata
	modules.settings = settings

	sys.modules['apis'] = apis
	sys.modules['apis.trakt_api'] = trakt_api
	sys.modules['apis.simkl_api'] = simkl_api
	sys.modules['apis.mdblist_api'] = mdblist_api
	sys.modules['caches'] = caches
	sys.modules['caches.base_cache'] = base_cache
	sys.modules['caches.trakt_cache'] = trakt_cache
	sys.modules['modules'] = modules
	sys.modules['modules.kodi_utils'] = kodi_utils
	sys.modules['modules.utils'] = utils
	sys.modules['modules.metadata'] = metadata
	sys.modules['modules.settings'] = settings

	spec = importlib.util.spec_from_file_location('watched_status_under_test', WATCHED_STATUS_PATH)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class WatchedStatusProviderOverrideTests(unittest.TestCase):
	def setUp(self):
		self._original_sys_modules = {}
		for key in STUB_MODULE_KEYS:
			if key in sys.modules:
				self._original_sys_modules[key] = sys.modules[key]

	def tearDown(self):
		for key in STUB_MODULE_KEYS:
			if key in self._original_sys_modules:
				sys.modules[key] = self._original_sys_modules[key]
			else:
				sys.modules.pop(key, None)

	def test_erase_bookmark_provider_override_does_not_delete_active_provider(self):
		progress_calls = []
		databases = {
			'watched_db': FakeDatabase(),
			'trakt_db': FakeDatabase(rows=[('123', '50', '1800', 'trakt-resume-id')]),
			'simkl_db': FakeDatabase(rows=[('123', '50', '1800', 'simkl-resume-id')]),
			'mdblist_db': FakeDatabase(),
		}
		module = _load_watched_status_module(2, databases, progress_calls)

		module.erase_bookmark('movie', '123', '', '', 'true', 1)

		self.assertEqual([('movie', '123', '', '')], databases['trakt_db'].deletes)
		self.assertEqual([], databases['simkl_db'].deletes)
		self.assertEqual('trakt', progress_calls[0][0])


if __name__ == '__main__':
	unittest.main()
