# -*- coding: utf-8 -*-
import time
from os import path
import sqlite3 as database
from contextlib import contextmanager
from modules import kodi_utils
logger = kodi_utils.logger

def table_creators():
	return {
'navigator_db': (
'CREATE TABLE IF NOT EXISTS navigator (list_name text, list_type text, list_contents text, unique (list_name, list_type))',),
'watched_db': (
'CREATE TABLE IF NOT EXISTS watched \
(db_type text not null, media_id text not null, season integer, episode integer, last_played text, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS progress \
(db_type text not null, media_id text not null, season integer, episode integer, resume_point text, curr_time text, \
last_played text, resume_id integer, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS watched_status (db_type text not null, media_id text not null, status text, unique (db_type, media_id))'),
'favorites_db': (
'CREATE TABLE IF NOT EXISTS favourites (db_type text not null, tmdb_id text not null, title text not null, unique (db_type, tmdb_id))',),
'settings_db': (
'CREATE TABLE IF NOT EXISTS settings (setting_id text not null unique, setting_type text, setting_default text, setting_value text)',),
'trakt_db': (
'CREATE TABLE IF NOT EXISTS trakt_data (id text unique, data text)',
'CREATE TABLE IF NOT EXISTS watched \
(db_type text not null, media_id text not null, season integer, episode integer, last_played text, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS progress \
(db_type text not null, media_id text not null, season integer, episode integer, resume_point text, curr_time text, \
last_played text, resume_id integer, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS watched_status (db_type text not null, media_id text not null, status text, unique (db_type, media_id))'),
'simkl_db': (
'CREATE TABLE IF NOT EXISTS simkl_data (id text unique, data text)',
'CREATE TABLE IF NOT EXISTS watched \
(db_type text not null, media_id text not null, season integer, episode integer, last_played text, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS progress \
(db_type text not null, media_id text not null, season integer, episode integer, resume_point text, curr_time text, \
last_played text, resume_id integer, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS watched_status (db_type text not null, media_id text not null, status text, unique (db_type, media_id))'),
'mdblist_db': (
'CREATE TABLE IF NOT EXISTS mdblist_data (id text unique, data text)',
'CREATE TABLE IF NOT EXISTS watched \
(db_type text not null, media_id text not null, season integer, episode integer, last_played text, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS progress \
(db_type text not null, media_id text not null, season integer, episode integer, resume_point text, curr_time text, \
last_played text, resume_id integer, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS watched_status (db_type text not null, media_id text not null, status text, unique (db_type, media_id))'),
'punchplay_db': (
'CREATE TABLE IF NOT EXISTS punchplay_data (id text unique, data text)',
'CREATE TABLE IF NOT EXISTS watched \
(db_type text not null, media_id text not null, season integer, episode integer, last_played text, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS progress \
(db_type text not null, media_id text not null, season integer, episode integer, resume_point text, curr_time text, \
last_played text, resume_id integer, title text, unique (db_type, media_id, season, episode))',
'CREATE TABLE IF NOT EXISTS watched_status (db_type text not null, media_id text not null, status text, unique (db_type, media_id))'),
'maincache_db': (
'CREATE TABLE IF NOT EXISTS maincache (id text unique, data text, expires integer)',),
'metacache_db': (
'CREATE TABLE IF NOT EXISTS metadata (db_type text not null, tmdb_id text not null, imdb_id text, tvdb_id text, meta text, expires integer, unique (db_type, tmdb_id))',
'CREATE TABLE IF NOT EXISTS season_metadata (tmdb_id text not null unique, meta text, expires integer)',
'CREATE TABLE IF NOT EXISTS function_cache (string_id text not null unique, data text, expires integer)'),
'debridcache_db': (
'CREATE TABLE IF NOT EXISTS debrid_data (hash text not null, debrid text not null, cached text, expires integer, unique (hash, debrid))',),
'lists_db': (
'CREATE TABLE IF NOT EXISTS lists (id text unique, data text, expires integer)',),
'external_db': (
'CREATE TABLE IF NOT EXISTS results_data (provider text not null, db_type text not null, tmdb_id text not null, title text, year integer, season text, episode text, results text, \
expires integer, unique (provider, db_type, tmdb_id, title, year, season, episode))',),
'discover_db': (
'CREATE TABLE IF NOT EXISTS discover (id text not null unique, db_type text not null, data text)',),
'episode_groups_db': (
'CREATE TABLE IF NOT EXISTS groups_data (tmdb_id text not null unique, data text)',),
'personal_lists_db': (
'CREATE TABLE IF NOT EXISTS personal_lists \
(name text, contents text, total integer, created text, sort_order integer, description text, seen text, poster text, fanart text, author text, updated text, unique (name, author))',),
'tmdb_lists_db': (
'CREATE TABLE IF NOT EXISTS tmdb_lists (id text unique, data text, expires integer)',),
'random_widgets_db': (
'CREATE TABLE IF NOT EXISTS random_widgets (id text unique, data text, expires integer)',),
'list_sort_db': (
'CREATE TABLE IF NOT EXISTS list_sort (scope text unique, spec text)',)
		}

def locations():
	return {
'navigator_db': 'navigator.db', 'watched_db': 'watched.db', 'favorites_db': 'favourites.db', 'settings_db': 'settings.db', 'trakt_db': 'traktcache.db', 'simkl_db': 'simklcache.db', 'mdblist_db': 'mdblistcache.db', 'punchplay_db': 'punchplaycache.db',
'maincache_db': 'maincache.db', 'metacache_db': 'metacache.db', 'debridcache_db': 'debridcache.db', 'lists_db': 'lists.db', 'tmdb_lists_db': 'tmdb_lists.db',
'discover_db': 'discover.db', 'external_db': 'external.db', 'episode_groups_db': 'episode_groups.db', 'personal_lists_db': 'personal_lists.db',
'random_widgets_db': 'random_widgets.db', 'list_sort_db': 'list_sort.db'
			}

def database_locations(database_name):
	return kodi_utils.translate_path(path.join(path.join(kodi_utils.addon_profile(), 'databases'), locations()[database_name]))

def make_database(database_name):
	dbcon = database.connect(database_locations(database_name))
	all_commands = table_creators()[database_name]
	for command in all_commands: dbcon.execute(command)
	dbcon.close()

def make_databases():
	databases_path = path.join(kodi_utils.addon_profile(), 'databases/')
	if not kodi_utils.path_exists(databases_path): kodi_utils.make_directory(databases_path)
	all_locations = locations()
	for database_name in all_locations: make_database(database_name)

def connect_database(database_name):
	dbcon = database.connect(database_locations(database_name), timeout=20, isolation_level=None, check_same_thread=False)
	dbcon.execute('PRAGMA synchronous = NORMAL')
	dbcon.execute('PRAGMA journal_mode = WAL')
	return dbcon

@contextmanager
def open_db(database_name):
	dbcon = connect_database(database_name)
	try: yield dbcon
	finally:
		try: dbcon.close()
		except: pass

def ensure_database_tables(database_name):
	"""Create missing tables without deleting existing data (safe before service has run)."""
	db_dir = path.join(kodi_utils.addon_profile(), 'databases')
	if not kodi_utils.path_exists(db_dir):
		kodi_utils.make_directory(db_dir)
	dbcon = connect_database(database_name)
	try:
		for command in table_creators()[database_name]:
			dbcon.execute(command)
	finally:
		try: dbcon.close()
		except: pass

def ensure_listing_databases_ready():
	"""Plugin entry can run before the service; guarantee core DB tables and settings rows exist."""
	ensure_database_tables('settings_db')
	ensure_database_tables('navigator_db')
	if kodi_utils.get_property('redlight.settings_db_synced') != 'true':
		try:
			from caches.settings_cache import sync_settings
			sync_settings({'silent': 'true', 'load_properties': False})
		except: pass

def get_timestamp(offset=0):
	# Offset is in HOURS multiply by 3600 to get seconds
	return int(time.time()) + (offset*3600)

def remove_old_databases():
	databases_path = path.join(kodi_utils.addon_profile(), 'databases/')
	# Derived from locations() rather than hand-maintained: the hand-written list had drifted and
	# carried four database *keys* where filenames belong, which put personal_lists.db and
	# random_widgets.db outside the allowlist and marked both live files as stale.
	current_dbs = tuple(locations().values())
	try:
		files = kodi_utils.list_dirs(databases_path)[1]
		for item in files:
			if not item in current_dbs:
				try: kodi_utils.delete_file(databases_path + item)
				except: pass
	except: pass

def check_databases_integrity(silent=False):
	integrity_check = {
	'settings_db': 1,              'navigator_db': 1,              'watched_db': 3,              'favorites_db': 1,              'trakt_db': 4,              'simkl_db': 4,              'mdblist_db': 4,              'punchplay_db': 4,
	'maincache_db': 1,             'metacache_db': 3,              'lists_db': 1,                'tmdb_lists_db': 1,             'discover_db': 1,
	'debridcache_db': 1,           'external_db': 1,               'episode_groups_db': 1,       'personal_lists_db': 1,         'random_widgets_db': 1,
	'list_sort_db': 1
			}
	def _process(database_name, tables):
		cursor, error = None, False
		try:
			database_location = database_locations(database_name)
			dbcon = database.connect(database_location)
			cursor = dbcon.cursor()
		except: error = True
		if cursor:
			try:
				cursor.execute('PRAGMA integrity_check')
				result = cursor.fetchone()
				if not 'ok' in result: error = True
			except: error = True
			try:
				cursor.execute('SELECT name FROM sqlite_master WHERE type="table";')
				current_tables = len([i[0] for i in cursor.fetchall()])
				if current_tables != tables: error = True
			except: error = True
		if error:
			database_errors.append(database_name)
			try:
				dbcon.close()
				kodi_utils.delete_file(database_location)
			except: pass
	database_errors = []
	for database_name, tables in integrity_check.items(): _process(database_name, tables)
	if database_errors:
		make_databases()
		if not silent: kodi_utils.ok_dialog(text='[B]Following Databases Rebuilt:[/B][CR][CR]%s' % ', '.join(database_errors))
	elif not silent: kodi_utils.notification('No Corrupt or Missing Databases', time=3000)

def get_size(file):
	with kodi_utils.open_file(file) as f: s = f.size()
	return s

def clean_databases():
	from caches.external_cache import external_cache
	from caches.main_cache import main_cache
	from caches.lists_cache import lists_cache
	from caches.meta_cache import meta_cache
	from caches.debrid_cache import debrid_cache
	clean_cache_list = (('EXTERNAL CACHE', external_cache, database_locations('external_db')),
						('MAIN CACHE', main_cache, database_locations('maincache_db')), ('LISTS CACHE', lists_cache, database_locations('lists_db')),
						('TMDB LISTS CACHE', lists_cache, database_locations('tmdb_lists_db')), ('META CACHE', meta_cache, database_locations('metacache_db')),
						('DEBRID CACHE', debrid_cache, database_locations('debridcache_db')),
						('RANDOM WIDGETS CACHE', debrid_cache, database_locations('random_widgets_db')))
	results = []
	append = results.append
	for item in clean_cache_list:
		name, function, location = item
		start_bytes = get_size(location)
		result = function.clean_database()
		if not result:
			append('[B]%s: [COLOR red]FAILED[/COLOR][/B]' % name)
			continue
		end_bytes = get_size(location)
		saved_bytes = start_bytes - end_bytes
		append('[B]%s: [COLOR green]SUCCESS[/COLOR][/B]\n    [B]Saved Size: %sMB[/B]\n    Start Size/End Size: %sMB/%sMB' \
		% (name, round(float(saved_bytes)/1024/1024, 2), round(float(start_bytes)/1024/1024, 2), round(float(end_bytes)/1024/1024, 2)))
	return kodi_utils.show_text('Cache Clean Results', text='\n----------------------------------\n'.join(results), font_size='large')

def clear_cache(cache_type, silent=False):
	def _confirm(): return silent or kodi_utils.confirm_dialog()
	success = True
	if cache_type == 'meta':
		from caches.meta_cache import delete_meta_cache
		success = delete_meta_cache(silent=silent)
	elif cache_type == 'internal_scrapers':
		if not _confirm(): return
		from apis import easynews_api
		results = []
		results.append(easynews_api.clear_media_results_database())
		try:
			from apis import comet_api
			results.append(comet_api.clear_comet_cache())
		except Exception:
			results.append(False)
		try:
			from apis import nyaa_api
			results.append(nyaa_api.clear_nyaa_cache())
		except Exception:
			results.append(False)
		for item in ('pm_cloud', 'rd_cloud', 'ad_cloud', 'oc_cloud', 'tb_cloud', 'folders'): results.append(clear_cache(item, silent=True))
		success = False not in results
	elif cache_type == 'easynews_scrape':
		if not _confirm(): return
		from apis import easynews_api
		success = easynews_api.clear_media_results_database()
	elif cache_type == 'external_scrapers':
		from caches.external_cache import external_cache
		from caches.debrid_cache import debrid_cache
		results = []
		for item in (external_cache, debrid_cache): results.append(item.clear_cache())
		success = False not in results
	elif cache_type == 'trakt':
		from caches.trakt_cache import clear_all_trakt_cache_data
		success = clear_all_trakt_cache_data(silent=silent)
	elif cache_type == 'simkl':
		from caches.simkl_cache import clear_all_simkl_cache_data
		success = clear_all_simkl_cache_data(silent=silent)
	elif cache_type == 'mdblist':
		from caches.mdblist_cache import clear_all_mdblist_cache_data
		success = clear_all_mdblist_cache_data(silent=silent)
	elif cache_type == 'punchplay':
		from caches.punchplay_cache import clear_all_punchplay_cache_data
		success = clear_all_punchplay_cache_data(silent=silent)
	elif cache_type == 'imdb':
		if not _confirm(): return
		from apis.imdb_api import clear_imdb_cache
		success = clear_imdb_cache()
	elif cache_type == 'subtitles':
		if not _confirm(): return
		from indexers.subtitles import clear_subtitles_cache
		clear_subtitles_cache()
		success = True
	elif cache_type == 'pm_cloud':
		if not _confirm(): return
		from apis.premiumize_api import Premiumize
		success = Premiumize.clear_cache()
	elif cache_type == 'rd_cloud':
		if not _confirm(): return
		from apis.real_debrid_api import RealDebrid
		success = RealDebrid.clear_cache()
	elif cache_type == 'ad_cloud':
		if not _confirm(): return
		from apis.alldebrid_api import AllDebrid
		success = AllDebrid.clear_cache()
	elif cache_type == 'oc_cloud':
		if not _confirm(): return
		from apis.offcloud_api import Offcloud
		success = Offcloud.clear_cache()
	elif cache_type == 'tb_cloud':
		if not _confirm(): return
		from apis.torbox_api import TorBox
		success = TorBox.clear_cache()
	elif cache_type == 'folders':
		if not _confirm(): return
		from caches.main_cache import main_cache
		success = main_cache.delete_all_folderscrapers()
	elif cache_type == 'list':
		if not _confirm(): return
		from caches.lists_cache import lists_cache
		success = lists_cache.delete_all_lists()
	elif cache_type == 'ai_functions':
		if not _confirm(): return
		from caches.lists_cache import lists_cache
		success = lists_cache.delete_all_ai_lists()
	elif cache_type == 'tmdb_list':
		if not _confirm(): return
		from caches.tmdb_lists import tmdb_lists_cache
		success = tmdb_lists_cache.clear_all()
	else:# main
		if not _confirm(): return
		from caches.main_cache import main_cache
		success = main_cache.delete_all()
	# Trakt/Simkl/MDBList/PunchPlay already toast a named "… Cache Cleared" in their clear helpers.
	if not silent and success and cache_type not in ('trakt', 'simkl', 'mdblist', 'punchplay'):
		clear_names = {
			'meta': 'Meta Cache', 'internal_scrapers': 'Internal Scrapers Cache', 'easynews_scrape': 'EasyNews Scrape Cache',
			'external_scrapers': 'External Scrapers Cache', 'imdb': 'IMDb Cache', 'subtitles': 'Subtitles Cache',
			'pm_cloud': 'Premiumize Cloud Cache', 'rd_cloud': 'Real Debrid Cloud Cache', 'ad_cloud': 'All Debrid Cloud Cache',
			'oc_cloud': 'Offcloud Cloud Cache', 'tb_cloud': 'TorBox Cloud Cache', 'folders': 'Folders Cache',
			'list': 'Lists Cache', 'ai_functions': 'AI Data Cache', 'tmdb_list': 'TMDb Lists Cache', 'main': 'Main Cache'}
		name = clear_names.get(cache_type)
		kodi_utils.notification('%s Cleared' % name if name else 'Success', 3000)
	return success

def clear_all_cache():
	if not kodi_utils.confirm_dialog(): return
	from modules.search import clear_easynews_search_history
	progressDialog = kodi_utils.progress_dialog()
	line = 'Clearing....[CR]%s'
	caches = (('meta', 'Meta Cache'), ('ai_functions', 'AI Data Cache'), ('list', 'List Data Cache'), ('main', 'Main Cache'),
			('tmdb_list', 'TMDb Personal List Cache'), ('imdb', 'IMDb Cache'), ('mdblist', 'MDBList Cache'), ('punchplay', 'PunchPlay Cache'), ('simkl', 'Simkl Cache'),
			('trakt', 'Trakt Cache'), ('subtitles', 'Subtitles Cache'), ('internal_scrapers', 'Internal Scrapers Cache'),
			('external_scrapers', 'External Scrapers Cache'), ('ad_cloud', 'All Debrid Cloud'), ('oc_cloud', 'Offcloud Cloud'),
			('pm_cloud', 'Premiumize Cloud'), ('rd_cloud', 'Real Debrid Cloud'), ('tb_cloud', 'TorBox Cloud'))
	for count, cache_type in enumerate(caches, 1):
		try:
			progressDialog.update(line % (cache_type[1]), int(float(count) / float(len(caches)) * 100))
			clear_cache(cache_type[0], silent=True)
			kodi_utils.sleep(1000)
		except: pass
	try: clear_easynews_search_history(silent=True)
	except: pass
	progressDialog.close()
	kodi_utils.sleep(100)
	kodi_utils.ok_dialog(text='Success')

def refresh_cached_data(meta):
	from caches.meta_cache import meta_cache
	media_type, tmdb_id, imdb_id = meta['mediatype'], meta['tmdb_id'], meta['imdb_id']
	try: meta_cache.delete(media_type, 'tmdb_id', tmdb_id, meta)
	except: return kodi_utils.notification('Error')
	from apis.imdb_api import refresh_imdb_meta_data
	refresh_imdb_meta_data(imdb_id)
	kodi_utils.notification('Success')
	kodi_utils.kodi_refresh()

def columns_in_table(database, table, check_existence=''):
	dbcon = connect_database(database)
	all_columns = [i[1] for i in dbcon.execute('PRAGMA table_info(%s);' % table).fetchall()]
	if check_existence: return check_existence in all_columns
	return all_columns

def insert_new_column_in_table(database, table, new_column, new_column_properties):
	try:
		dbcon = connect_database(database)
		dbcon.execute('ALTER TABLE %s ADD COLUMN %s %s;' % (table, new_column, new_column_properties))
		return True
	except: return False

def check_and_insert_new_columns(database, table, new_column, new_column_properties):
	#Check for existence of any column in databases and insert if not present
	try:
		if not columns_in_table(database, table, new_column):
			success = insert_new_column_in_table(database, table, new_column, new_column_properties)
			if not success: kodi_utils.notification('Error with [B]%s[/B] Database. Missing Column [B]%s[/B]' % (database.upper(), new_column.upper()))
	except: kodi_utils.notification('Error Checking Database Table/s: %s' % database)

class BaseCache(object):
	def __init__(self, dbfile, table):
		self.table = table
		self.dbfile = dbfile

	def get(self, string):
		result = None
		try:
			current_time = get_timestamp()
			dbcon = connect_database(self.dbfile)
			cache_data = dbcon.execute('SELECT expires, data FROM %s WHERE id = ?' % self.table, (string,)).fetchone()
			if cache_data:
				if cache_data[0] > current_time:
					result = eval(cache_data[1])
				else: self.delete(string)
		except: pass
		return result

	def set(self, string, data, expiration=720):
		try:
			dbcon = connect_database(self.dbfile)
			expires = get_timestamp(expiration)
			dbcon.execute('INSERT OR REPLACE INTO %s(id, data, expires) VALUES (?, ?, ?)' % self.table, (string, repr(data), int(expires)))
		except: return None

	def delete(self, string):
		try:
			dbcon = connect_database(self.dbfile)
			dbcon.execute('DELETE FROM %s WHERE id = ?' % self.table, (string,))
		except: pass

	def delete_like(self, string):
		try:
			dbcon = connect_database(self.dbfile)
			dbcon.execute('DELETE FROM %s WHERE id LIKE ?' % self.table, (string,))
		except: pass

	def manual_connect(self, dbfile):
		return connect_database(dbfile)
