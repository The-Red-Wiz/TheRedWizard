import xbmcvfs
import xbmcaddon
import os
import re
import html

ADDON = xbmcaddon.Addon(id='plugin.audio.mp3streams')
DATA_PATH = os.path.join(xbmcvfs.translatePath('special://profile/addon_data/plugin.audio.mp3streams'), '')

def cookie_jar():
    return create_file(DATA_PATH, "cookiejar.lwp")
	
def addon():
    return ADDON
		
def artist_icons():
    return create_directory(DATA_PATH, "artist_icons")
	
def folder_structure():
    return ADDON.getSetting('folder_structure')
	
def favourites_file_artist():
    return create_file(DATA_PATH, "favourites_artist.list")
	
def favourites_file_album():
    return create_file(DATA_PATH, "favourites_album.list")
	
def download_list():
    return create_file(DATA_PATH, "downloads.list")
	
def favourites_file_songs():
    return create_file(DATA_PATH, "favourites_songs.list")
	
def playlist_file():
    return create_file(DATA_PATH, "playlist_file.list")
	
def uses_custom_music_dir():
    mode = ADDON.getSetting('music_dir_mode')
    if mode in ('1', 'Custom folder'):
        return True
    if mode in ('0', 'Default folder'):
        return False
    return ADDON.getSetting('custom_directory') == 'true'

def custom_directory():
    return uses_custom_music_dir()
		
def keep_downloads():
    if ADDON.getSetting('keep_downloads') == "true":
        return True
    else:
        return False
		
def gotham_fix():
    if ADDON.getSetting('gotham_fix') == "true":
        return True
    else:
        return False
		
def golden_path():
    if ADDON.getSetting('golden_path') == "true":
        return True
    else:
        return False
		
def default_queue():
    if ADDON.getSetting('default_queue') == "true":
        return True
    else:
        return False
		
def hide_fanart():
    if ADDON.getSetting('hide_fanart') == "true":
        return True
    else:
        return False
		
def default_queue_album():
    if ADDON.getSetting('default_queue_album') == "true":
        return True
    else:
        return False
		
def default_music_dir():
    return create_directory(DATA_PATH, "music")

def music_dir():
    if not uses_custom_music_dir():
        return default_music_dir()
    folder = ADDON.getSetting('music_dir')
    if not folder or folder == 'set':
        return default_music_dir()
    folder = xbmcvfs.translatePath(folder)
    return create_directory(folder, "")
	
def decode_text(text):
    if not text:
        return text
    return html.unescape(text)

def sanitize_filename(text):
    if not text:
        return text
    text = decode_text(text)
    for char, replacement in (
        ('/', ' - '),
        ('\\', ' - '),
        (':', ' -'),
        ('*', ''),
        ('?', ''),
        ('"', ''),
        ('<', ''),
        ('>', ''),
        ('|', ''),
    ):
        text = text.replace(char, replacement)
    return text.strip()

ALBUM_YEAR_SUFFIX_RE = re.compile(r'^(.*) \((\d{4})\)$')

def parse_album_year_suffix(album):
    """If album ends with ' (YYYY)', return (title, year), else (album, '')."""
    album = decode_text(album or '').strip()
    match = ALBUM_YEAR_SUFFIX_RE.match(album)
    if match and match.group(1).strip():
        return match.group(1).strip(), match.group(2)
    return album, ''

def album_storage_title(album, year=''):
    """Folder name: 'Album (1979)' when year is known; do not double-append."""
    album = decode_text(album or '').strip()
    year = str(year or '').strip()
    if not re.match(r'^\d{4}$', year):
        return album
    _bare, existing = parse_album_year_suffix(album)
    if existing == year:
        return album
    return '%s (%s)' % (album, year)

def album_lookup_titles(album):
    """Preferred storage title first, then title without (YYYY) for legacy folders."""
    album = decode_text(album or '').strip()
    titles = []
    seen = set()
    for title in (album, parse_album_year_suffix(album)[0]):
        if title and title not in seen:
            titles.append(title)
            seen.add(title)
    return titles

def year_from_storage_name(path_or_name):
    """YYYY from 'Album (1979)' or a folder path whose basename ends that way."""
    name = decode_text(path_or_name or '').strip().rstrip('/\\')
    if not name:
        return ''
    for candidate in (os.path.basename(name), name):
        _bare, year = parse_album_year_suffix(candidate)
        if year:
            return year
    return ''

FLAT_ALBUM_SEPARATOR = ' - '
_FLAT_ALBUM_ESCAPES = (
    ('%', '%25'),
    ('/', '%2F'),
    ('\\', '%5C'),
    (':', '%3A'),
    ('*', '%2A'),
    ('?', '%3F'),
    ('"', '%22'),
    ('<', '%3C'),
    ('>', '%3E'),
    ('|', '%7C'),
)

def flat_album_component(text):
    """Escape path-invalid chars and embedded ' - ' so flat Artist - Album folders stay unique."""
    text = decode_text(text or '')
    for char, replacement in _FLAT_ALBUM_ESCAPES:
        text = text.replace(char, replacement)
    return text.replace(FLAT_ALBUM_SEPARATOR, '%20-%20').strip()

def flat_album_folder_name(artist, album):
    return FLAT_ALBUM_SEPARATOR.join((flat_album_component(artist), flat_album_component(album))).strip()

def legacy_flat_album_folder_name(artist, album):
    return sanitize_filename(decode_text(artist or '') + FLAT_ALBUM_SEPARATOR + decode_text(album or ''))

def create_directory(dir_path, dir_name=None):
    if dir_name:
        dir_path = os.path.join(dir_path, sanitize_filename(dir_name))
    dir_path = dir_path.strip()
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path

def album_storage_folder(artist, album, create=True):
    """One folder per album (album artist + title, with year when known)."""
    artist = decode_text(artist or '')
    album = decode_text(album or '')
    base = music_dir()
    if folder_structure() == "0":
        path = os.path.join(base, sanitize_filename(artist), sanitize_filename(album))
    else:
        path = os.path.join(base, flat_album_folder_name(artist, album))
    path = path.strip()
    if create and not os.path.exists(path):
        os.makedirs(path)
    return path

def legacy_flat_album_storage_folder(artist, album):
    return os.path.join(music_dir(), legacy_flat_album_folder_name(artist, album)).strip()

def album_track_basename(track, songname):
    songname = decode_text(songname or '')
    track = str(track or '').replace('track', '').strip()
    if not track:
        return sanitize_filename(songname)
    prefix = '%s. ' % track
    if songname.startswith(prefix):
        return sanitize_filename(songname)
    return sanitize_filename('%s. %s' % (track, songname))

def album_track_file_path(artist, album, track, songname, create_dir=True):
    folder = album_storage_folder(artist, album, create=create_dir)
    return os.path.join(folder, album_track_basename(track, songname) + '.mp3')

def create_file(dir_path, file_name=None):
    if file_name:
        file_path = os.path.join(dir_path, sanitize_filename(file_name))
    file_path = file_path.strip()
    if not os.path.exists(file_path):
        f = open(file_path, 'w')
        f.write('')
        f.close()
    return file_path
	
create_directory(DATA_PATH, "")
   
