import importlib.util
import os
import sys
import tempfile
import types
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(ROOT, 'plugin.audio.mp3streams', 'settings.py')


class FakeAddon:
    values = {}

    def __init__(self, id=None):
        self.id = id

    def getSetting(self, key):
        return self.values.get(key, '')


def load_settings(temp_dir, folder_structure='1'):
    FakeAddon.values = {
        'folder_structure': folder_structure,
        'music_dir_mode': 'Default folder',
    }

    def translate_path(path):
        if path.startswith('special://profile/'):
            return os.path.join(temp_dir, path.replace('special://profile/', ''))
        return path

    sys.modules['xbmcvfs'] = types.SimpleNamespace(translatePath=translate_path)
    sys.modules['xbmcaddon'] = types.SimpleNamespace(Addon=FakeAddon)

    spec = importlib.util.spec_from_file_location('mp3streams_settings_under_test', SETTINGS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AlbumStorageTests(unittest.TestCase):
    def test_flat_album_names_escape_embedded_separator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = load_settings(temp_dir, folder_structure='1')

            first = os.path.basename(settings.album_storage_folder('AB', 'C - D', create=False))
            second = os.path.basename(settings.album_storage_folder('AB - C', 'D', create=False))

        self.assertEqual(first, 'AB - C%20-%20D')
        self.assertEqual(second, 'AB%20-%20C - D')
        self.assertNotEqual(first, second)

    def test_legacy_flat_name_documents_old_collision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = load_settings(temp_dir, folder_structure='1')

            first = settings.legacy_flat_album_folder_name('AB', 'C - D')
            second = settings.legacy_flat_album_folder_name('AB - C', 'D')

        self.assertEqual(first, 'AB - C - D')
        self.assertEqual(second, 'AB - C - D')


if __name__ == '__main__':
    unittest.main()
