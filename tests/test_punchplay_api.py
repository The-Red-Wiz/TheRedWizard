import importlib.util
import sys
import types
import unittest
from pathlib import Path


def load_punchplay_api():
	for name in list(sys.modules):
		if name == 'apis.punchplay_api':
			sys.modules.pop(name)

	settings_cache = types.ModuleType('caches.settings_cache')
	settings_cache.get_setting = lambda setting_id, default='': default
	settings_cache.set_setting = lambda setting_id, value: None
	settings_cache.settings_cache = types.SimpleNamespace(read_db_value=lambda key: '0', clear_db_cache=lambda: None)

	punchplay_cache = types.ModuleType('caches.punchplay_cache')
	punchplay_cache.punchplay_cache = types.SimpleNamespace(get=lambda key: None, set=lambda *args, **kwargs: None, delete=lambda key: None)
	punchplay_cache.punchplay_watched_cache = types.SimpleNamespace(
		set_bulk_movie_watched=lambda items: None,
		set_bulk_tvshow_watched=lambda items: None,
		set_bulk_movie_progress=lambda items: None,
		set_bulk_tvshow_progress=lambda items: None)
	punchplay_cache.clear_all_punchplay_cache_data = lambda silent=True, refresh=False: None

	caches = types.ModuleType('caches')
	caches.punchplay_cache = punchplay_cache

	kodi_utils = types.ModuleType('modules.kodi_utils')
	kodi_utils.addon_version = lambda: '0.0.0-test'
	kodi_utils.get_icon = lambda name: ''
	kodi_utils.addon_icon = lambda: ''
	kodi_utils.logger = lambda *args, **kwargs: None
	kodi_utils.service_scrobbler_defer = lambda *args, **kwargs: False

	settings = types.ModuleType('modules.settings')
	settings.punchplay_user_active = lambda: True

	utils = types.ModuleType('modules.utils')
	utils.copy2clip = lambda value: None
	utils.make_qrcode = lambda value: ''

	modules = types.ModuleType('modules')
	modules.kodi_utils = kodi_utils
	modules.settings = settings
	modules.utils = utils

	sys.modules.update({
		'caches': caches,
		'caches.settings_cache': settings_cache,
		'caches.punchplay_cache': punchplay_cache,
		'modules': modules,
		'modules.kodi_utils': kodi_utils,
		'modules.settings': settings,
		'modules.utils': utils,
	})

	module_path = Path(__file__).resolve().parents[1] / 'plugin.video.redlight' / 'resources' / 'lib' / 'apis' / 'punchplay_api.py'
	spec = importlib.util.spec_from_file_location('apis.punchplay_api', module_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class PunchPlayWatchedStatusMarkTests(unittest.TestCase):
	def setUp(self):
		self.api = load_punchplay_api()
		self.calls = []
		self.api.punchplay_user_active = lambda: True
		self.api.punchplay_sync_activities = lambda force_update=False: self.calls.append(('sync', force_update)) or 'success'

	def fake_call(self, path, method='get', data=None, query=None, retry=True):
		self.calls.append((path, method, data, query))
		if path == '/me/history':
			return {
				'items': [
					{'id': 'hist-1', 'type': 'episode', 'showTmdbId': 123, 'season': 1, 'episode': 2},
					{'id': 'hist-2', 'type': 'episode', 'showTmdbId': 123, 'season': 1, 'episode': 3},
				]
			}
		if path == '/watch-history/hist-1' and method == 'delete':
			return True
		if path == '/title/show/123/season/1/watch' and method == 'delete':
			return True
		self.fail('unexpected PunchPlay call: %r' % ((path, method, data, query),))

	def test_episode_unwatch_deletes_only_matching_history_entry(self):
		self.api.call_punchplay = self.fake_call

		ok = self.api.punchplay_watched_status_mark(
			'mark_as_unwatched', 'episode', '123', season=1, episode=2)

		self.assertTrue(ok)
		self.assertIn(('/me/history', 'get', None, {'limit': 100}), self.calls)
		self.assertIn(('/watch-history/hist-1', 'delete', None, None), self.calls)
		self.assertNotIn(('/title/show/123/season/1/watch', 'delete', None, None), self.calls)
		self.assertIn(('sync', True), self.calls)

	def test_season_unwatch_still_uses_season_endpoint(self):
		self.api.call_punchplay = self.fake_call

		ok = self.api.punchplay_watched_status_mark(
			'mark_as_unwatched', 'season', '123', season=1)

		self.assertTrue(ok)
		self.assertIn(('/title/show/123/season/1/watch', 'delete', None, None), self.calls)
		self.assertNotIn(('/me/history', 'get', None, {'limit': 100}), self.calls)
		self.assertIn(('sync', True), self.calls)


if __name__ == '__main__':
	unittest.main()
