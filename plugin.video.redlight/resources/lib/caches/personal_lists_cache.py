# -*- coding: utf-8 -*-
from modules import kodi_utils
from caches.base_cache import connect_database, get_timestamp
# from modules.kodi_utils import logger

class PersonalListsCache:
	def make_list(self, list_name, author, sort_order, description, seen='false', poster='', fanart=''):
		try:
			time_stamp = get_timestamp()
			if not author: author = 'Unknown'
			dbcon = connect_database('personal_lists_db')
			dbcon.execute('INSERT OR REPLACE INTO personal_lists VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
						(list_name, repr([]), 0, time_stamp, sort_order, description, seen, poster, fanart, author, time_stamp))
			return True
		except: return False

	def delete_list(self, list_name, author):
		try:
			dbcon = connect_database('personal_lists_db')
			dbcon.execute('DELETE FROM personal_lists WHERE name=? AND author=?', (list_name, author))
			dbcon.execute('VACUUM')
			return True
		except: return False

	def delete_list_contents(self, list_name, author):
		try:
			dbcon = connect_database('personal_lists_db')
			dbcon.execute('UPDATE personal_lists SET contents=?, total=? WHERE name=? AND author=?', (repr([]), '0', list_name, author))
			return True
		except: return False

	def update_single_detail(self, set_prop, new_value, list_name, author):
		try:
			dbcon = connect_database('personal_lists_db')
			dbcon.execute('UPDATE personal_lists SET %s=? WHERE name=? AND author=?' % set_prop, (new_value, list_name, author))
		except: pass

	def get_lists(self):
		try:
			dbcon = connect_database('personal_lists_db')
			all_lists = dbcon.execute('SELECT name, total, created, sort_order, description, seen, poster, fanart, author, updated FROM personal_lists').fetchall()
			return [{'name': str(i[0]), 'total': i[1], 'created_at': i[2], 'sort_order': i[3], 'description': i[4], 'seen': i[5],
					'poster': i[6] or '', 'fanart': i[7] or '', 'author': i[8], 'updated': i[9]} for i in all_lists]
		except: return []

	def get_list(self, list_name, author, update_seen=True, seen='true', dbcon=None):
		content = []
		try:
			if not dbcon: dbcon = connect_database('personal_lists_db')
			content = eval(dbcon.execute('SELECT contents FROM personal_lists WHERE name=? AND author=?', (list_name, author)).fetchone()[0])
			if (update_seen and self.new_list_check(seen)): self.update_single_detail('seen', 'true', list_name, author)
		except: pass
		return content

	def add_remove_list_item(self, list_name, author, action, new_contents):
		try:
			dbcon = connect_database('personal_lists_db')
			contents = self.get_list(list_name, author, update_seen=False, dbcon=dbcon)
			if action == 'add':
				if [str(i['media_id']) for i in contents if str(new_contents['media_id']) == str(i['media_id'])]:
					return kodi_utils.LIST_ITEM_ALREADY_IN_LIST
				command = 'UPDATE personal_lists SET contents=?, total=total+1, updated=? WHERE name=?'
				contents.append(new_contents)
			else:
				if not [str(i['media_id']) for i in contents if str(new_contents) == str(i['media_id'])]:
					return kodi_utils.LIST_ITEM_NOT_IN_LIST
				command = 'UPDATE personal_lists SET contents=?, total=total-1, updated=? WHERE name=?'
				contents = [i for i in contents if not str(i['media_id']) == str(new_contents)]
			dbcon.execute(command, (repr(contents), get_timestamp(), list_name))
			if action == 'add': return 'Added to %s' % list_name
			return 'Removed from %s' % list_name
		except: return 'Error'

	def add_many_list_items(self, list_name, author, new_contents):
		try:
			dbcon = connect_database('personal_lists_db')
			contents = self.get_list(list_name, author, update_seen=False, dbcon=dbcon)
			if contents:
				movies_compare_ids = [str(i['media_id']) for i in contents if i['type'] == 'movie']
				tvshows_compare_ids = [str(i['media_id']) for i in contents if i['type'] == 'tvshow']
				movies_new = [i for i in new_contents if i['type'] == 'movie' and str(i['media_id']) not in movies_compare_ids]
				tvshows_new = [i for i in new_contents if i['type'] == 'tvshow' and str(i['media_id']) not in tvshows_compare_ids]
				new_contents = movies_new + tvshows_new
			contents.extend(new_contents)
			dbcon.execute('UPDATE personal_lists SET contents=?, total=?, updated=? WHERE name=? AND author=?', (repr(contents), len(contents), get_timestamp(), list_name, author))
			return 'Success'
		except: return 'Error'

	def get_all_sort_orders(self):
		"""Every list's stored sort_order. Raises on a locked database - deliberately, unlike its
		neighbours: its only caller is the one-time sort migration, which must be able to tell an
		empty store from an unreadable one. Returning {} on failure would look like a clean success,
		let the migration record itself as done, and delete every stored preference on the next sync.
		"""
		dbcon = connect_database('personal_lists_db')
		rows = dbcon.execute('SELECT name, author, sort_order FROM personal_lists').fetchall()
		return dict(((i[0], i[1]), i[2]) for i in rows)

	def get_list_names_and_authors(self):
		data = self.get_lists()
		return [(i['name'], i['author']) for i in data]

	def new_list_check(self, seen):
		return seen != 'true'

personal_lists_cache = PersonalListsCache()
