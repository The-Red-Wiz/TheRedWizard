import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


SIMKL_PATH = Path(__file__).resolve().parents[1] / 'plugin.video.gratisred' / 'resources' / 'lib' / 'modules' / 'simkl.py'


def _install_module(name):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


def _load_simkl():
    for name in (
        'resources',
        'resources.lib',
        'resources.lib.modules',
        'resources.lib.modules.cache',
        'resources.lib.modules.control',
        'resources.lib.modules.log_utils',
        'gratisred_simkl_under_test',
    ):
        sys.modules.pop(name, None)

    _install_module('resources')
    _install_module('resources.lib')
    modules_pkg = _install_module('resources.lib.modules')

    settings = {
        'simkl.token': 'token',
        'simkl.user': 'user',
    }
    control = types.ModuleType('resources.lib.modules.control')
    control.settings = settings
    control.selected = -1
    control.labels = []
    control.dialogs = []
    control.setting = lambda key: settings.get(key, '')
    control.setSetting = lambda key, value: settings.__setitem__(key, value)
    control.addonInfo = lambda key: '1.0'
    control.infoLabel = lambda key: 'icon.png'
    control.sleep = lambda milliseconds: None

    def select_dialog(labels, heading):
        control.labels = labels
        return control.selected

    def info_dialog(*args, **kwargs):
        control.dialogs.append((args, kwargs))

    control.selectDialog = select_dialog
    control.infoDialog = info_dialog

    cache = types.ModuleType('resources.lib.modules.cache')
    cache.get = lambda func, timeout, *args: func(*args)
    cache.remove = lambda func, *args: None

    log_utils = types.ModuleType('resources.lib.modules.log_utils')
    log_utils.log = lambda *args, **kwargs: None

    sys.modules['resources.lib.modules.control'] = control
    sys.modules['resources.lib.modules.cache'] = cache
    sys.modules['resources.lib.modules.log_utils'] = log_utils
    modules_pkg.control = control
    modules_pkg.cache = cache
    modules_pkg.log_utils = log_utils

    spec = importlib.util.spec_from_file_location('gratisred_simkl_under_test', str(SIMKL_PATH))
    simkl = importlib.util.module_from_spec(spec)
    sys.modules['gratisred_simkl_under_test'] = simkl
    spec.loader.exec_module(simkl)
    return simkl, control


class SimklManagerTests(unittest.TestCase):

    def test_manager_only_removes_selected_status_membership(self):
        simkl, control = _load_simkl()
        calls = []

        def fetch_status(media_kind, status):
            if media_kind == 'movies' and status == 'completed':
                return [{'ids': {'tmdb': 123, 'imdb': 'tt7654321'}}]
            return []

        def call_simkl(path, data=None, method=None):
            calls.append((path, data, method))
            return {'deleted': {'movies': 1}}

        control.selected = 1

        with mock.patch.object(simkl, '_fetch_status', fetch_status), \
                mock.patch.object(simkl, 'call_simkl', call_simkl), \
                mock.patch.object(simkl, 'refreshSimklCache', lambda: None):
            simkl.manager('Example Movie', 'tt7654321', '123', 'movie')

        self.assertEqual(control.labels, [
            'Add to [B]Plan to Watch[/B]',
            'Remove from [B]Completed[/B]',
            'Add to [B]Dropped[/B]',
        ])
        self.assertEqual(calls, [
            ('/sync/history/remove', {'movies': [{'ids': {'tmdb': 123, 'imdb': 'tt7654321'}}]}, None)
        ])

    def test_manager_rechecks_membership_before_destructive_remove(self):
        simkl, control = _load_simkl()
        calls = []
        completed_checks = {'count': 0}

        def fetch_status(media_kind, status):
            if media_kind == 'movies' and status == 'completed':
                completed_checks['count'] += 1
                if completed_checks['count'] == 1:
                    return [{'ids': {'tmdb': 123, 'imdb': 'tt7654321'}}]
            return []

        control.selected = 1

        with mock.patch.object(simkl, '_fetch_status', fetch_status), \
                mock.patch.object(simkl, 'call_simkl', lambda *args, **kwargs: calls.append((args, kwargs))):
            simkl.manager('Example Movie', 'tt7654321', '123', 'movie')

        self.assertEqual(control.labels[1], 'Remove from [B]Completed[/B]')
        self.assertEqual(calls, [])
        self.assertEqual(control.dialogs[-1][0][0], 'Item is not in Completed.')


if __name__ == '__main__':
    unittest.main()
