import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / 'plugin.audio.mp3streams' / 'default.py'


class _Addon:
	def getAddonInfo(self, key):
		return ''

	def getSetting(self, key):
		if key == 'folder_structure':
			return '1'
		return 'false'

	def openSettings(self):
		pass


class _FakeResponse:
	def __init__(self, chunks, headers=None, status_code=200):
		self._chunks = chunks
		self.headers = headers or {}
		self.status_code = status_code
		self.closed = False

	def raise_for_status(self):
		if self.status_code >= 400:
			raise Exception('HTTP %s' % self.status_code)

	def iter_content(self, chunk_size=1):
		for chunk in self._chunks:
			yield chunk

	def close(self):
		self.closed = True


def _install_stubs(tmpdir):
	xbmc = types.ModuleType('xbmc')
	xbmc.LOGINFO = 1
	xbmc.LOGERROR = 4
	xbmc.PLAYLIST_MUSIC = 0
	xbmc.getInfoLabel = lambda key: '20.0'
	xbmc.log = lambda *args, **kwargs: None
	xbmc.executebuiltin = lambda *args, **kwargs: None

	class _Player:
		def isPlayingAudio(self):
			return False

		def play(self, *args, **kwargs):
			pass

	class _PlayList:
		def __init__(self, *args, **kwargs):
			self.items = []

		def clear(self):
			self.items = []

		def add(self, *args, **kwargs):
			self.items.append(args)

		def size(self):
			return len(self.items)

	xbmc.Player = _Player
	xbmc.PlayList = _PlayList

	xbmcplugin = types.ModuleType('xbmcplugin')
	xbmcplugin.endOfDirectory = lambda *args, **kwargs: None
	xbmcplugin.addDirectoryItem = lambda *args, **kwargs: True

	xbmcgui = types.ModuleType('xbmcgui')

	class _Dialog:
		def ok(self, *args, **kwargs):
			pass

		def yesno(self, *args, **kwargs):
			return False

		def notification(self, *args, **kwargs):
			pass

	class _ListItem:
		def __init__(self, *args, **kwargs):
			pass

		def setArt(self, *args, **kwargs):
			pass

		def setInfo(self, *args, **kwargs):
			pass

		def setProperty(self, *args, **kwargs):
			pass

		def addContextMenuItems(self, *args, **kwargs):
			pass

		def setIconImage(self, *args, **kwargs):
			pass

	xbmcgui.Dialog = _Dialog
	xbmcgui.ListItem = _ListItem
	xbmcgui.DialogProgress = _Dialog

	xbmcvfs = types.ModuleType('xbmcvfs')
	xbmcvfs.translatePath = lambda path: path

	settings = types.ModuleType('settings')
	music_dir = os.path.join(tmpdir, 'music')
	download_list = os.path.join(tmpdir, 'downloads.list')
	settings.cookie_jar = lambda: os.path.join(tmpdir, 'cookiejar.lwp')
	settings.addon = lambda: _Addon()
	settings.keep_downloads = lambda: False
	settings.artist_icons = lambda: os.path.join(tmpdir, 'artist_icons')
	settings.favourites_file_artist = lambda: os.path.join(tmpdir, 'favourites_artist.list')
	settings.favourites_file_album = lambda: os.path.join(tmpdir, 'favourites_album.list')
	settings.favourites_file_songs = lambda: os.path.join(tmpdir, 'favourites_songs.list')
	settings.playlist_file = lambda: os.path.join(tmpdir, 'playlist_file.list')
	settings.hide_fanart = lambda: False
	settings.default_queue = lambda: False
	settings.default_queue_album = lambda: False
	settings.download_list = lambda: download_list
	settings.folder_structure = lambda: '1'
	settings.music_dir = lambda: music_dir
	settings.decode_text = lambda text: text
	settings.sanitize_filename = lambda text: (text or '').replace('/', ' - ').strip()
	settings.album_storage_folder = lambda artist, album, create=True: _album_folder(music_dir, artist, album, create)
	settings.album_track_basename = lambda track, songname: settings.sanitize_filename('%s. %s' % (str(track).replace('track', '').strip(), songname))
	settings.legacy_flat_album_storage_folder = lambda artist, album: os.path.join(music_dir, '%s - %s' % (artist, album))

	t0mm0 = types.ModuleType('t0mm0')
	common = types.ModuleType('t0mm0.common')
	net_module = types.ModuleType('t0mm0.common.net')

	class _Net:
		def set_cookies(self, *args, **kwargs):
			pass

		def save_cookies(self, *args, **kwargs):
			pass

	net_module.Net = _Net
	t0mm0.common = common
	common.net = net_module

	bs4 = types.ModuleType('bs4')
	bs4.BeautifulSoup = lambda *args, **kwargs: None

	mutagen = types.ModuleType('mutagen')
	easyid3 = types.ModuleType('mutagen.easyid3')
	mp3 = types.ModuleType('mutagen.mp3')
	easyid3.EasyID3 = object
	mp3.MP3 = object

	for name, module in (
		('xbmc', xbmc), ('xbmcplugin', xbmcplugin), ('xbmcgui', xbmcgui), ('xbmcvfs', xbmcvfs),
		('settings', settings), ('t0mm0', t0mm0), ('t0mm0.common', common), ('t0mm0.common.net', net_module),
		('bs4', bs4), ('mutagen', mutagen), ('mutagen.easyid3', easyid3), ('mutagen.mp3', mp3)):
		sys.modules[name] = module


def _album_folder(base, artist, album, create=True):
	path = os.path.join(base, '%s - %s' % (artist, album))
	if create and not os.path.exists(path):
		os.makedirs(path)
	return path


def _load_default_module(tmpdir):
	_install_stubs(tmpdir)
	original_argv = sys.argv[:]
	sys.argv = ['plugin://plugin.audio.mp3streams', '1', '?mode=123&url=dummy']
	try:
		spec = importlib.util.spec_from_file_location('mp3streams_default_under_test', DEFAULT_PATH)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		return module
	finally:
		sys.argv = original_argv


class Mp3StreamsDownloadHardeningTests(unittest.TestCase):
	def test_valid_audio_replaces_final_file_after_validation(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			module = _load_default_module(tmpdir)
			payload = b'ID3' + (b'\x00' * 2048)
			final_path = os.path.join(tmpdir, 'track.mp3')
			with open(final_path, 'wb') as existing:
				existing.write(b'existing-good-file')
			module.requests.get = lambda *args, **kwargs: _FakeResponse(
				[payload],
				{'Content-Type': 'audio/mpeg', 'Content-Length': str(len(payload))})

			module._download_audio_to_file('https://example.test/track', final_path, {})

			with open(final_path, 'rb') as downloaded:
				self.assertEqual(payload, downloaded.read())
			self.assertFalse(os.path.exists('%s.%s.part' % (final_path, os.getpid())))

	def test_html_response_is_rejected_and_existing_file_is_preserved(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			module = _load_default_module(tmpdir)
			final_path = os.path.join(tmpdir, 'track.mp3')
			with open(final_path, 'wb') as existing:
				existing.write(b'existing-good-file')
			body = b'<html>not audio</html>' + (b'x' * 2048)
			module.requests.get = lambda *args, **kwargs: _FakeResponse(
				[body],
				{'Content-Type': 'text/html', 'Content-Length': str(len(body))})

			with self.assertRaises(module.DownloadValidationError):
				module._download_audio_to_file('https://example.test/track', final_path, {})

			with open(final_path, 'rb') as existing:
				self.assertEqual(b'existing-good-file', existing.read())
			self.assertFalse(os.path.exists('%s.%s.part' % (final_path, os.getpid())))

	def test_download_song_failure_does_not_update_downloads_list(self):
		with tempfile.TemporaryDirectory() as tmpdir:
			module = _load_default_module(tmpdir)
			body = b'<html>blocked</html>' + (b'x' * 2048)
			module.requests.get = lambda *args, **kwargs: _FakeResponse(
				[body],
				{'Content-Type': 'text/html', 'Content-Length': str(len(body))})
			added = []
			module.add_to_list = lambda list_data, file_path, refresh: added.append(list_data)

			ok = module.download_song('https://example.test/track', '1. Song', 'Song', 'Artist', 'Album', '')

			self.assertFalse(ok)
			self.assertEqual([], added)
			final_path = os.path.join(tmpdir, 'music', 'Artist - Album', '1. Song.mp3')
			self.assertFalse(os.path.exists(final_path))


if __name__ == '__main__':
	unittest.main()
