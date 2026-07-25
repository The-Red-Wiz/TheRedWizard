import sys
import types
import unittest
from pathlib import Path


LIB_PATH = Path(__file__).resolve().parents[1] / 'plugin.video.redlight' / 'resources' / 'lib'
sys.path.insert(0, str(LIB_PATH))


def _install_stub(name, **attrs):
	module = types.ModuleType(name)
	for key, value in attrs.items():
		setattr(module, key, value)
	sys.modules[name] = module
	return module


_install_stub('caches')
_install_stub('caches.main_cache', cache_object=lambda *args, **kwargs: None)
_install_stub(
	'caches.settings_cache',
	get_setting=lambda setting_id, default='empty_setting': default,
	set_setting=lambda *args, **kwargs: None,
)
_install_stub('modules')
_install_stub(
	'modules.source_utils',
	supported_video_extensions=lambda: ('.mkv', '.mp4'),
	seas_ep_filter=lambda *args, **kwargs: False,
	extras=lambda: (),
)
_install_stub('modules.utils', copy2clip=lambda *args, **kwargs: None, make_qrcode=lambda *args, **kwargs: '')
_install_stub(
	'modules.kodi_utils',
	make_session=lambda *args, **kwargs: types.SimpleNamespace(request=lambda *a, **k: None, post=lambda *a, **k: None),
	ok_dialog=lambda *args, **kwargs: None,
	notification=lambda *args, **kwargs: None,
	progress_dialog=lambda *args, **kwargs: None,
	sleep=lambda *args, **kwargs: None,
)

from apis.offcloud_api import OffcloudAPI


class OffcloudResolveCleanupTests(unittest.TestCase):
	def test_resolve_via_cloud_does_not_delete_request_before_playback(self):
		api = OffcloudAPI()
		api.deleted = []
		api.add_magnet = lambda magnet_url: {
			'status': 'downloaded',
			'url': 'https://server.offcloud.com/cloud/download/request-123',
			'fileName': 'Movie.mkv',
			'requestId': 'request-123',
		}
		api.torrent_info = lambda request_id: ['https://server.offcloud.com/cloud/download/request-123/Movie.mkv']
		api.delete_torrent = lambda request_id: api.deleted.append(request_id)
		api.clear_cache = lambda *args, **kwargs: None
		api.requote_uri = lambda url: url

		url = api._resolve_via_cloud('magnet:?xt=urn:btih:abc', season=None, episode=None, store_to_cloud=False)

		self.assertEqual(url, 'https://server.offcloud.com/cloud/download/request-123/Movie.mkv')
		self.assertEqual(api.deleted, [])


if __name__ == '__main__':
	unittest.main()
