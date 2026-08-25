# -*- coding: utf-8 -*-
from threading import Thread
from datetime import datetime, timedelta
from windows.base_window import BaseDialog, window_manager, window_player
from apis import tmdb_api, imdb_api, omdb_api, ai_api, trakt_api
from indexers import dialogs, people
from indexers.images import Images
from modules import kodi_utils, settings, watched_status
from modules.utils import change_image_resolution, adjust_premiered_date, get_datetime, make_thread_list_enumerate, batch_replace, get_current_timestamp
from modules.meta_lists import networks, movie_genres, tvshow_genres
from modules.metadata import movieset_meta, episodes_meta, movie_meta, tvshow_meta
from modules.episode_tools import EpisodeTools
# logger = kodi_utils.logger

class Extras(BaseDialog):
	button_ids = (10, 11, 12, 13, 14, 15, 16, 17, 2050)
	plot_id, cast_id, recommended_id, related_id, more_like_this_id, ai_similar_id, reviews_id, comments_id, trivia_id = 2050, 2051, 2052, 2053, 2054, 2055, 2056, 2057, 2058
	blunders_id, parentsguide_id, in_lists_id, videos_id, year_id, genres_id, networks_id, collection_id = 2059, 2060, 2061, 2062, 2063, 2064, 2065, 2066
	parentsguide_icons = {'Sex & Nudity': kodi_utils.get_icon('sex_nudity'), 'Violence & Gore': kodi_utils.get_icon('violence'), 'Profanity': kodi_utils.get_icon('bad_language'),
							'Alcohol, Drugs & Smoking': kodi_utils.get_icon('drugs_alcohol'), 'Frightening & Intense Scenes': kodi_utils.get_icon('horror')}
	meta_ratings_values = (('Meta', 'metascore', 1), ('Tom/Critic', 'tomatometer', 2), ('Tom/User', 'tomatousermeter', 3), ('IMDb', 'imdb', 4), ('TMDb', 'tmdb', 5))
	media_alert = 'Press Info Button for [B]More Info[/B]'
	actor_alert = 'Press Context Button for [B]Search[/B]'
	list_alert = 'Press Context Button To [B]Like/Unlike List[/B]'
	
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.control_id = None
		self.items_list_ids = (self.recommended_id, self.related_id, self.more_like_this_id, self.ai_similar_id, self.year_id,
								self.genres_id, self.networks_id, self.collection_id)
		self.text_list_ids = (self.reviews_id, self.trivia_id, self.blunders_id, self.parentsguide_id, self.comments_id)
		self.open_folder_list_ids = (self.in_lists_id,)
		self.empty_poster = kodi_utils.get_icon('box_office')
		self.addon_fanart = kodi_utils.addon_fanart()
		self.button_label_values = kodi_utils.extras_button_label_values()
		self.set_starting_constants(kwargs)
		self.set_properties()
		self.tasks = (self.set_artwork, self.set_infoline1, self.set_infoline2, self.make_ratings, self.make_cast, self.make_recommended, self.make_related,
					self.make_more_like_this, self.make_ai_similar, self.make_imdb_extras, self.make_comments, self.make_in_lists, self.make_videos, self.make_year,
					self.make_genres, self.make_network, self.make_collection)

	def onInit(self):
		self.set_home_property('window_loaded', 'true')
		for i in self.tasks: Thread(target=i).start()
		self.set_default_focus()
		if self.starting_position:
			try: self.set_returning_focus(*self.starting_position)
			except: self.set_default_focus()

	def run(self):
		self.doModal()
		self.clearProperties()
		self.clear_home_property('window_theme.extras')
		self.clear_home_property('window_theme.highlight.extras')
		if self.selected: self.execute_code(self.selected)

	def onClick(self, controlID):
		self.control_id = None
		if controlID in self.button_ids: return exec('self.%s()' % self.button_action_dict[controlID])
		else: self.control_id = controlID

	def onAction(self, action):
		if action in self.closing_actions: return window_manager(self)
		if action == self.info_action:
			focus_id = self.getFocusId()
			if not focus_id in self.items_list_ids: return
			kodi_utils.show_busy_dialog()
			from modules.metadata import movie_meta, tvshow_meta
			chosen_listitem = self.get_listitem(focus_id)
			function = movie_meta if self.media_type == 'movie' else tvshow_meta
			meta = function('tmdb_id', chosen_listitem.getProperty('tmdb_id'), self.tmdb_api_key, self.mpaa_region, self.current_date)
			kodi_utils.hide_busy_dialog()
			self.show_extrainfo(meta)
		elif action in self.context_actions:
			focus_id = self.getFocusId()
			if focus_id == self.cast_id:
				person_name = self.get_listitem(focus_id).getProperty(self.item_action_dict[focus_id])
				return people.person_search(person_name)
			elif focus_id == self.in_lists_id:
				if not settings.trakt_user_active(): return self.notification('Trakt account not authorised')
				kodi_utils.show_busy_dialog()
				try:
					list_item, position = self.get_listitem(focus_id), self.get_position(focus_id)
					chosen = self.get_attribute(self, list_item.getProperty(self.item_action_dict[focus_id]))[self.get_position(focus_id)]
					user, list_slug = chosen['user']['ids']['slug'], chosen['ids']['slug']
					list_id = (chosen.get('ids') or {}).get('trakt')
					if chosen.get('type') == 'official' or user == 'Trakt Official': user = 'Trakt Official'
					payload = {'user': user, 'list_slug': list_slug, 'refresh': 'false'}
					if list_id not in (None, '', 0, '0'): payload['list_id'] = list_id
					elif user == 'Trakt Official':
						kodi_utils.hide_busy_dialog()
						return self.notification('Error with Trakt List')
					function, new_value = (trakt_api.trakt_like_a_list, 'true') if list_item.getProperty('liked_status') == 'false' else (trakt_api.trakt_unlike_a_list, 'false')
					new_value = 'true' if list_item.getProperty('liked_status') == 'false' else 'false'
					if function(payload): list_item.setProperty('liked_status', new_value)
				except:
					kodi_utils.hide_busy_dialog()
					return self.notification('Error with Trakt List')
				kodi_utils.hide_busy_dialog()
			else: return
		if not self.control_id: return
		if action in self.selection_actions:
			try: chosen_var = self.get_listitem(self.control_id).getProperty(self.item_action_dict[self.control_id])
			except: return
			if not chosen_var: return
			position = self.get_position(self.control_id)
			if self.control_id in self.items_list_ids:
				self.set_current_params()
				self.new_params = {'mode': 'extras_menu_choice', 'tmdb_id': chosen_var, 'media_type': self.media_type, 'is_external': self.is_external, 'stacked': 'true'}
				return window_manager(self)
			elif self.control_id == self.cast_id:
				self.set_current_params()
				self.new_params = {'mode': 'person_data_dialog', 'key_id': chosen_var, 'reference_tmdb_id': self.tmdb_id, 'is_external': self.is_external, 'stacked': 'true'}
				return window_manager(self)
			elif self.control_id == self.videos_id:
				self.set_current_params(set_starting_position=False)
				self.window_player_url = 'plugin://plugin.video.youtube/play/?video_id=%s' % chosen_var
				return window_player(self)
			elif self.control_id in self.text_list_ids:
				if self.control_id == self.parentsguide_id: return self.show_text_media(text=chosen_var)
				else: return self.select_item(self.control_id, self.show_text_media(text=self.get_attribute(self, chosen_var), current_index=position))
			elif self.control_id in self.open_folder_list_ids:
				try: chosen_var = self.get_listitem(self.control_id).getProperty(self.item_action_dict[self.control_id])
				except: return
				if not chosen_var: return
				try:
					self.close_all()
					chosen = self.get_attribute(self, chosen_var)[position]
					list_name = chosen['name']
					user = ((chosen.get('user') or {}).get('ids') or {}).get('slug')
					slug = (chosen.get('ids') or {}).get('slug')
					list_id = (chosen.get('ids') or {}).get('trakt')
					if chosen.get('type') == 'official' or user == 'Trakt Official':
						user = 'Trakt Official'
					url_params = {'mode': 'trakt.list.build_trakt_list', 'user': user, 'slug': slug, 'list_type': 'user_lists', 'list_name': list_name}
					if list_id not in (None, '', 0, '0'): url_params['list_id'] = list_id
					self.selected = self.folder_runner(url_params)
					self.close()
				except: return
			else: return

	def make_ratings(self, win_prop=4000):
		data, current_settings = self.get_omdb_ratings()
		final_ratings = []
		if not current_settings: return
		if len(data) == 1: return
		if len(current_settings) == 1:
			try:
				data = data[next((i[1] for i in self.meta_ratings_values if i[0] == current_settings[0]))]
				rating = data['rating']
				if rating in ('', '%'): return
				if data['rating'] in ('', '%'): return
				return self.set_infoline1(rating_data=data)
			except: return
		elif win_prop == 4000: self.set_infoline1(remove_rating=True)
		for check, prop, _id in self.meta_ratings_values:
			try:
				if check not in current_settings: continue
				rating = data[prop]['rating']
				if rating in ('', '%'): continue
				final_ratings.append({'prop': prop, '_id': _id, 'rating': rating, 'icon': data[prop]['icon']})
			except: pass
		if not final_ratings: return
		if len(final_ratings) == 1: return self.set_infoline1(rating_data=final_ratings[0])
		for item in final_ratings:
			self.setProperty('%s_rating' % item['prop'], 'true')
			self.set_label(win_prop + item['_id'], item['rating'])
			self.set_image(win_prop + 100 + item['_id'], 'redlight_flags/ratings/%s' % item['icon'])

	def make_plot_and_tagline(self):
		self.plot = self.meta_get('tvshow_plot', '') or self.meta_get('plot', '') or ''
		if not self.plot: return
		self.tagline = self.meta_get('tagline') or ''
		if self.tagline: self.plot = '[I]%s[/I][CR][CR]%s' % (self.tagline, self.plot)
		if self.plot_id in self.enabled_lists: self.setProperty('plot_enabled', 'true')

	def make_imdb_extras(self):
		imdb_extras = imdb_api.imdb_extras(self.imdb_id)
		self.make_reviews(imdb_extras['reviews'])
		self.make_trivia(imdb_extras['trivia'])
		self.make_blunders(imdb_extras['blunders'])
		self.make_parentsguide(imdb_extras['parentsguide'])

	def make_cast(self):
		if not self.cast_id in self.enabled_lists: return
		def builder():
			cast = self.meta_get('cast')
			for item in cast:
				try:
					listitem = self.make_listitem()
					name, role = item['name'], item['role']
					listitem.setProperty('name', '%s%s' % (name, ' as %s' % role if role else ''))
					listitem.setProperty('name_lookup', name)
					listitem.setProperty('thumbnail', item['thumbnail'] or icon)
					listitem.setProperty('info_alert', self.actor_alert)
					yield listitem
				except: pass
		try:
			icon = kodi_utils.get_icon('empty_person')
			item_list = list(builder())
			self.setProperty('cast.number', 'x%s' % len(item_list))
			self.item_action_dict[self.cast_id] = 'name_lookup'
			self.add_items(self.cast_id, item_list)
		except: pass

	def make_recommended(self):
		if not self.recommended_id in self.enabled_lists: return
		try:
			function = tmdb_api.tmdb_movies_recommendations if self.media_type == 'movie' else tmdb_api.tmdb_tv_recommendations
			data = function(self.tmdb_id, 1)['results']
			item_list = list(self.make_tmdb_listitems(data))
			self.setProperty('recommended.number', 'x%s' % len(item_list))
			self.item_action_dict[self.recommended_id] = 'tmdb_id'
			self.add_items(self.recommended_id, item_list)
		except: pass

	def make_related(self):
		if not self.related_id in self.enabled_lists: return
		def builder(position, item):
			try:
				details = function('trakt_dict', item, self.tmdb_api_key, self.mpaa_region, self.current_date, current_time=None)
				poster = details['poster']
				if self.rpdb_api_key and poster:
					try: poster = details['rpdb_poster'] % self.rpdb_api_key + self.rpdb_format
					except: pass
				elif not poster: poster = self.empty_poster
				listitem = self.make_listitem()
				listitem.setProperty('name', details['title'])
				listitem.setProperty('release_date', details['year'])
				listitem.setProperty('vote_average', '%.1f' % details['rating'])
				listitem.setProperty('thumbnail', poster)
				listitem.setProperty('tmdb_id', str(details['tmdb_id']))
				listitem.setProperty('info_alert', self.media_alert)
				item_list_append((listitem, position))
			except: pass
		if self.media_type == 'movie': data_function, function = trakt_api.trakt_movies_related, movie_meta
		else: data_function, function = trakt_api.trakt_tv_related, tvshow_meta
		data = [i['ids'] for i in data_function(self.imdb_id)]
		item_list = []
		item_list_append = item_list.append
		threads = list(make_thread_list_enumerate(builder, data))
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		item_list = [i[0] for i in item_list]
		self.setProperty('related.number', 'x%s' % len(item_list))
		self.item_action_dict[self.related_id] = 'tmdb_id'
		self.add_items(self.related_id, item_list)

	def make_more_like_this(self):
		if not self.more_like_this_id in self.enabled_lists: return
		def builder(position, item):
			try:
				details = function('imdb_id', item, self.tmdb_api_key, self.mpaa_region, self.current_date, current_time=None)					
				listitem = self.make_listitem()
				poster = details['poster']
				if self.rpdb_api_key and poster:
					try: poster = details['rpdb_poster'] % self.rpdb_api_key + self.rpdb_format
					except: pass
				elif not poster: poster = self.empty_poster
				listitem.setProperty('name', details['title'])
				listitem.setProperty('release_date', details['year'])
				listitem.setProperty('vote_average', '%.1f' % details['rating'])
				listitem.setProperty('thumbnail', poster)
				listitem.setProperty('tmdb_id', str(details['tmdb_id']))
				listitem.setProperty('info_alert', self.media_alert)
				item_list_append((listitem, position))
			except: pass
		data = imdb_api.imdb_more_like_this(self.imdb_id)
		function = movie_meta if self.media_type == 'movie' else tvshow_meta
		item_list = []
		item_list_append = item_list.append
		threads = list(make_thread_list_enumerate(builder, data))
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		item_list = [i[0] for i in item_list]
		self.setProperty('more_like_this.number', 'x%s' % len(item_list))
		self.item_action_dict[self.more_like_this_id] = 'tmdb_id'
		self.add_items(self.more_like_this_id, item_list)

	def make_ai_similar(self):
		if not self.ai_similar_id in self.enabled_lists: return
		def builder(position, item):
			try:
				details = function('tmdb_id', item['id'], self.tmdb_api_key, self.mpaa_region, self.current_date, current_time=None)					
				listitem = self.make_listitem()
				poster = details['poster']
				if self.rpdb_api_key and poster:
					try: poster = details['rpdb_poster'] % self.rpdb_api_key + self.rpdb_format
					except: pass
				elif not poster: poster = self.empty_poster
				listitem.setProperty('name', details['title'])
				listitem.setProperty('release_date', details['year'])
				listitem.setProperty('vote_average', '%.1f' % details['rating'])
				listitem.setProperty('thumbnail', poster)
				listitem.setProperty('tmdb_id', str(details['tmdb_id']))
				listitem.setProperty('info_alert', self.media_alert)
				item_list_append((listitem, position))
			except: pass
		try:
			data = ai_api.ai_similar('%s|%s' % (self.media_type, self.tmdb_id))['results']
			function = movie_meta if self.media_type == 'movie' else tvshow_meta
			item_list = []
			item_list_append = item_list.append
			threads = list(make_thread_list_enumerate(builder, data))
			[i.join() for i in threads]
			item_list.sort(key=lambda k: k[1])
			item_list = [i[0] for i in item_list]
			self.setProperty('ai_similar.number', 'x%s' % len(item_list))
			self.item_action_dict[self.ai_similar_id] = 'tmdb_id'
			self.add_items(self.ai_similar_id, item_list)
		except: pass

	def make_reviews(self, all_reviews):
		if not self.reviews_id in self.enabled_lists: return
		def builder():
			for item in self.all_reviews:
				try:
					listitem = self.make_listitem()
					listitem.setProperty('text', item)
					listitem.setProperty('content_list', 'all_reviews')
					yield listitem
				except: pass
		try:
			self.all_reviews = all_reviews
			item_list = list(builder())
			self.setProperty('imdb_reviews.number', 'x%s' % len(item_list))
			self.item_action_dict[self.reviews_id] = 'content_list'
			self.add_items(self.reviews_id, item_list)
		except: pass

	def make_comments(self):
		if not self.comments_id in self.enabled_lists: return
		def builder():
			for item in self.all_comments:
				try:
					listitem = self.make_listitem()
					listitem.setProperty('text', item)
					listitem.setProperty('content_list', 'all_comments')
					yield listitem
				except: pass
		try:
			self.all_comments = trakt_api.trakt_comments(self.media_type, self.imdb_id)
			item_list = list(builder())
			self.setProperty('trakt_comments.number', 'x%s' % len(item_list))
			self.item_action_dict[self.comments_id] = 'content_list'
			self.add_items(self.comments_id, item_list)
		except: pass

	def make_in_lists(self):
		if not self.in_lists_id in self.enabled_lists: return
		def builder():
			for count, item in enumerate(self.all_in_lists, 1):
				try:
					listitem = self.make_listitem()
					user_slug = ((item.get('user') or {}).get('ids') or {}).get('slug') or ''
					if item.get('type') == 'official': user_slug = 'Trakt Official'
					compare = ((item.get('ids') or {}).get('slug'), user_slug)
					tid = (item.get('ids') or {}).get('trakt')
					if (tid not in (None, '', 0, '0') and str(tid) in liked_ids) or compare in liked_pairs: liked = 'true'
					else: liked = 'false'
					likes = item.get('likes', '')
					likes_insert = '[CR]%s %s' % (likes, 'Likes' if likes > 1 else 'Like') if likes else '' 
					listitem.setProperty('name', template % (count, batch_replace(item['name'].upper(), replacements), likes_insert, user_slug, item['item_count']))
					listitem.setProperty('content_list', 'all_in_lists')
					listitem.setProperty('thumbnail', icon)
					listitem.setProperty('liked_status', liked)
					listitem.setProperty('info_alert', self.list_alert if settings.trakt_user_active() else '')
					yield listitem
				except: pass
		try:
			icon = kodi_utils.get_icon('trakt')
			liked_pairs, liked_ids = [], set()
			if settings.trakt_user_active():
				try:
					for i in trakt_api.trakt_get_lists('liked_lists') or []:
						lst = i.get('list') or {}
						ids = lst.get('ids') or {}
						tid = ids.get('trakt')
						if tid not in (None, '', 0, '0'): liked_ids.add(str(tid))
						user_s = ((lst.get('user') or {}).get('ids') or {}).get('slug') or ''
						if lst.get('type') == 'official': user_s = 'Trakt Official'
						liked_pairs.append((ids.get('slug'), user_s))
				except: liked_pairs, liked_ids = [], set()
			template, replacements = '%02d.[CR][B]%s[/B]%s[CR][CR]by %s[CR](x%02d)', (('-', ' '), ('_', ' '), ('.', ' '))
			self.all_in_lists = trakt_api.trakt_lists_with_media(self.media_type, self.imdb_id)
			item_list = list(builder())
			self.setProperty('trakt_in_lists.number', 'x%s' % len(item_list))
			self.item_action_dict[self.in_lists_id] = 'content_list'
			self.add_items(self.in_lists_id, item_list)
		except: pass

	def make_trivia(self, all_trivia):
		if not self.trivia_id in self.enabled_lists: return
		def builder():
			for item in self.all_trivia:
				try:
					listitem = self.make_listitem()
					listitem.setProperty('text', item)
					listitem.setProperty('content_list', 'all_trivia')
					yield listitem
				except: pass
		try:
			self.all_trivia = all_trivia
			item_list = list(builder())
			self.setProperty('imdb_trivia.number', 'x%s' % len(item_list))
			self.item_action_dict[self.trivia_id] = 'content_list'
			self.add_items(self.trivia_id, item_list)
		except: pass

	def make_blunders(self, all_blunders):
		if not self.blunders_id in self.enabled_lists: return
		def builder():
			for item in self.all_blunders:
				try:
					listitem = self.make_listitem()
					listitem.setProperty('text', item)
					listitem.setProperty('content_list', 'all_blunders')
					yield listitem
				except: pass
		try:
			self.all_blunders = all_blunders
			item_list = list(builder())
			self.setProperty('imdb_blunders.number', 'x%s' % len(item_list))
			self.item_action_dict[self.blunders_id] = 'content_list'
			self.add_items(self.blunders_id, item_list)
		except: pass

	def make_parentsguide(self, all_parentsguide):
		if not self.parentsguide_id in self.enabled_lists: return
		def builder():
			for item in all_parentsguide:
				try:
					listitem = self.make_listitem()
					name = item['title']
					ranking = item['ranking'].upper()
					if ranking == 'NONE': ranking = 'NO RANK'
					if item['content']: ranking += ' (x%02d)' % item['total_count']
					icon = self.parentsguide_icons[name]
					listitem.setProperty('name', name)
					listitem.setProperty('ranking', ranking)
					listitem.setProperty('thumbnail', icon)
					listitem.setProperty('content', item['content'])
					yield listitem
				except: pass
		try:
			item_list = list(builder())
			self.setProperty('imdb_parentsguide.number', 'x%s' % len(item_list))
			self.item_action_dict[self.parentsguide_id] = 'content'
			self.add_items(self.parentsguide_id, item_list)
		except: pass

	def make_videos(self):
		if not self.videos_id in self.enabled_lists: return
		def _sort_trailers(trailers):
			official_trailers = [i for i in trailers if i['official'] and i['type'] == 'Trailer' and 'official trailer' in i['name'].lower()]
			other_official_trailers = [i for i in trailers if i['official'] and i['type'] == 'Trailer' and not i in official_trailers]
			other_trailers = [i for i in trailers if i['type'] == 'Trailer' and not i in official_trailers  and not i in other_official_trailers]
			teaser_trailers = [i for i in trailers if i['type'] == 'Teaser']
			full_trailers = official_trailers + other_official_trailers + other_trailers + teaser_trailers
			features = [i for i in trailers if not i in full_trailers]
			return full_trailers + features
		def builder():
			for item in all_trailers:
				try:
					listitem = self.make_listitem()
					key = item['key']
					listitem.setProperty('name', item['name'])
					listitem.setProperty('thumbnail', 'https://img.youtube.com/vi/%s/0.jpg' % key)
					listitem.setProperty('key_id', key)
					yield listitem
				except: pass
		try:
			all_trailers = _sort_trailers(self.meta_get('all_trailers', []))
			item_list = list(builder())
			self.setProperty('youtube_videos.number', 'x%s' % len(item_list))
			self.item_action_dict[self.videos_id] = 'key_id'
			self.add_items(self.videos_id, item_list)
		except: pass

	def make_year(self):
		if not self.year_id in self.enabled_lists: return
		try:
			function = tmdb_api.tmdb_movies_year if self.media_type == 'movie' else tmdb_api.tmdb_tv_year
			data = self.remove_current_tmdb_mediaitem(function(self.year, 1)['results'])
			item_list = list(self.make_tmdb_listitems(data))
			self.setProperty('more_from_year.number', 'x%s' % len(item_list))
			self.item_action_dict[self.year_id] = 'tmdb_id'
			self.add_items(self.year_id, item_list)
		except: pass

	def make_genres(self):
		if not self.genres_id in self.enabled_lists: return
		try:
			function, genre_list = (tmdb_api.tmdb_movies_genres, movie_genres()) if self.media_type == 'movie' else (tmdb_api.tmdb_tv_genres, tvshow_genres())
			genre_list = ','.join([i['id'] for i in genre_list if i['name'] in self.genre])
			data = self.remove_current_tmdb_mediaitem(function(genre_list, 1)['results'])
			item_list = list(self.make_tmdb_listitems(data))
			self.setProperty('more_from_genres.number', 'x%s' % len(item_list))
			self.item_action_dict[self.genres_id] = 'tmdb_id'
			self.add_items(self.genres_id, item_list)
		except: pass

	def make_network(self):
		if not self.networks_id in self.enabled_lists: return
		try:
			network = self.meta_get('studio')[0]
			network_list = tmdb_api.tmdb_company_id(network)['results'] if self.media_type == 'movie' else networks()
			network_id = next(i['id'] for i in network_list if i['name'] == network)
			function = tmdb_api.tmdb_movies_companies if self.media_type == 'movie' else tmdb_api.tmdb_tv_networks
			data = self.remove_current_tmdb_mediaitem(function(network_id, 1)['results'])
			item_list = list(self.make_tmdb_listitems(data))
			self.setProperty('more_from_networks.number', 'x%s' % len(item_list))
			self.item_action_dict[self.networks_id] = 'tmdb_id'
			self.add_items(self.networks_id, item_list)
		except: pass

	def make_collection(self):
		if self.media_type != 'movie': return
		if not self.collection_id in self.enabled_lists: return
		try: coll_id = self.extra_info_get('collection_id')
		except: return
		if not coll_id: return
		try:
			data = movieset_meta(coll_id, self.tmdb_api_key)
			item_list = list(self.make_tmdb_listitems(sorted(data['parts'], key=lambda k: k['release_date'] or '2050')))
			self.setProperty('more_from_collection.name', data['title'])
			self.setProperty('more_from_collection.overview', data['plot'] or data['title'])
			self.setProperty('more_from_collection.poster', data['poster'] or self.empty_poster)
			self.setProperty('more_from_collection.number', 'x%s' % len(item_list))
			self.item_action_dict[self.collection_id] = 'tmdb_id'
			self.add_items(self.collection_id, item_list)
		except: pass

	def get_omdb_ratings(self):
		if not self.display_extra_ratings: return None, None
		current_settings = settings.extras_enabled_ratings()
		if not current_settings: return None, None
		data = self.meta_get('extra_ratings', None) or omdb_api.fetch_ratings_info(self.meta, self.omdb_api)
		if not data: return None, None
		if data['tmdb']['rating'] == '' and self.rating is not None: data['tmdb']['rating'] = self.rating
		return data, current_settings

	def get_release_year(self, release_data):
		try:
			if release_data in ('', None): release_data = 'N/A'
			else: release_data = release_data.split('-')[0]
		except: pass
		return release_data

	def get_progress(self, percent_watched):
		return '%s%% Watched' % percent_watched

	def get_finish(self, percent_watched):
		finish_str = 'No Finish Time'
		if self.duration_data:
			label = 'Finish Rewatching' if percent_watched == '100' else 'Finish Watching'
			kodi_clock = self.get_infolabel('System.Time')
			if any(i in kodi_clock for i in ('AM', 'PM')): _format = '%I:%M %p'
			else: _format = '%H:%M'
			if percent_watched in ('0', '100'): remaining_time = self.duration_data
			else: remaining_time = ((100 - int(percent_watched))/100) * self.duration_data
			current_time = datetime.now()
			finish_time = current_time + timedelta(minutes=remaining_time)
			finished = finish_time.strftime(_format)
			finish_str = '%s: %s' % (label, finished)
		return finish_str

	def get_duration(self):
		time_str = ''
		if self.duration_data:
			hour, minute = divmod(self.duration_data, 60)
			if hour: time_str += '%dh' % hour
			if minute: time_str += '%s%sm' % (' ' if hour else '', '%d' % minute if minute < 10 else '%02d' % minute)
		return time_str

	def get_last_aired(self):
		if self.extra_info_get('last_episode_to_air', False):
			last_ep = self.extra_info_get('last_episode_to_air')
			last_aired = 'S%.2dE%.2d' % (last_ep['season_number'], last_ep['episode_number'])
		else: return ''
		return 'Last Aired: %s' % last_aired

	def get_next_aired(self):
		if self.status in ('', 'Ended', 'Canceled'): return ''
		if self.extra_info_get('next_episode_to_air', False):
			next_ep = self.extra_info_get('next_episode_to_air')
			next_aired = 'S%.2dE%.2d' % (next_ep['season_number'], next_ep['episode_number'])
		else: return ''
		return 'Next Aired: %s' % next_aired

	def get_next_episode(self):
		self.nextep_season, self.nextep_episode = None, None
		value, curr_season_data, episode_date = '', [], None
		try:
			try:
				nextep_content = settings.nextep_method()
				ep_list = watched_status.get_next_episodes(nextep_content)
				ep_data = next((i for i in ep_list if i['media_ids']['tmdb'] == self.tmdb_id), None)
				orig_season, orig_episode = ep_data.get('season'), ep_data.get('episode')
			except: orig_season, orig_episode = 1, 0
			season_data = self.meta_get('season_data')
			watched_info = watched_status.watched_info_episode(self.tmdb_id, watched_status.get_database(settings.watched_indicators()))
			nextep_season, nextep_episode = watched_status.get_next(orig_season, orig_episode, watched_info, season_data, nextep_content, self.meta)
			if not nextep_season: return
			episodes_data = episodes_meta(nextep_season, self.meta)
			item = next((i for i in episodes_data if i['episode'] == nextep_episode), None)
			item_get = item.get
			episode_date, premiered = adjust_premiered_date(item_get('premiered'), settings.date_offset())
			if episode_date and self.current_date >= episode_date:
				self.nextep_season, self.nextep_episode = nextep_season, nextep_episode
				value = 'Next Episode: S%.2dE%.2d' % (self.nextep_season, self.nextep_episode)
		except: pass
		return value

	def make_tvshow_browse_params(self):
		all_episodes = settings.default_all_episodes()
		if all_episodes:
			if all_episodes == 1 and self.meta_get('total_seasons') > 1: url_params = {'mode': 'build_season_list', 'tmdb_id': self.tmdb_id}
			else: url_params = {'mode': 'build_episode_list', 'tmdb_id': self.tmdb_id, 'season': 'all'}
		else: url_params = {'mode': 'build_season_list', 'tmdb_id': self.tmdb_id}
		return url_params

	def remove_current_tmdb_mediaitem(self, data):
		return [i for i in data if int(i['id']) != self.tmdb_id]

	def make_tmdb_listitems(self, data):
		used_ids = []
		append = used_ids.append
		name_key = 'title' if self.media_type == 'movie' else 'name'
		release_key = 'release_date' if self.media_type == 'movie' else 'first_air_date'
		for item in data:
			try:
				tmdb_id = item['id']
				if tmdb_id in used_ids: continue
				listitem = self.make_listitem()
				year = self.get_release_year(item[release_key])
				poster = 'https://image.tmdb.org/t/p/%s%s' % ('w300', item['poster_path']) if item['poster_path'] else ''
				if self.rpdb_api_key and poster:
					media = 'movie' if self.media_type == 'movie' else 'series'
					try: poster = 'https://api.ratingposterdb.com/%s/tmdb/poster-default/%s-%s.jpg?fallback=true' % (self.rpdb_api_key, media, str(item['id'])) + self.rpdb_format
					except: pass
				elif not poster: poster = self.empty_poster
				listitem.setProperties({'name': item[name_key], 'release_date': year, 'vote_average': '%.1f' % item['vote_average'],
										'thumbnail': poster, 'tmdb_id': str(tmdb_id), 'info_alert': self.media_alert})
				append(tmdb_id)
				yield listitem
			except: pass

	def set_artwork(self):
		self.set_image(202, self.fanart)
		if self.clearlogo: self.set_image(201, self.clearlogo)
		else: self.setProperty('clearlogo', 'false')
		self.set_image(200, self.poster)

	def show_text_media(self, text, poster=None, current_index=None):
		return self.open_window(('windows.extras', 'ShowTextMedia'), 'textviewer_media.xml', text=text, poster=poster or self.poster, current_index=current_index)

	def tvshow_browse(self):
		self.close_all()
		url_params = self.make_tvshow_browse_params()
		self.selected = self.folder_runner(url_params)
		self.close()

	def movies_play(self):
		# Close Extras before scrape/play — otherwise results/resolve (and then the movie)
		# sit under extras.xml and playback looks like it is running "behind" the UI.
		self.close_all()
		self.selected = 'RunPlugin(%s)' % self.build_url({
			'mode': 'playback.%s' % self.playback_key, 'media_type': 'movie', 'tmdb_id': self.tmdb_id,
			self.playback_key: self.playback_key
		})
		self.close()

	def show_plot(self):
		return self.show_text_media(text=self.plot)

	def show_trailers(self):
		if not kodi_utils.addon_installed('plugin.video.youtube') or not kodi_utils.addon_enabled('plugin.video.youtube'):
			return kodi_utils.notification('Youtube Plugin needed for playback')
		self.set_current_params(set_starting_position=False)
		self.window_player_url = self.meta_get('trailer')
		return window_player(self)

	def show_images(self):
		return Images().run({'mode': 'tmdb_media_image_results', 'media_type': self.media_type, 'tmdb_id': self.tmdb_id, 'rootname': self.rootname})

	def show_extrainfo(self, meta=None):
		if meta:
			text = '[B]  •  [/B]'.join([i for i in (meta.get('year'), str(round(meta.get('rating'), 1)) if meta.get('rating') not in (0, 0.0, None) else None,
									meta.get('mpaa')) if i]) + '[CR][CR]%s' % meta.get('plot')
			poster = meta.get('poster', self.empty_poster)
		else: text, poster = dialogs.media_extra_info_choice({'media_type': self.media_type, 'meta': self.meta}), self.poster
		return self.show_text_media(text=text, poster=poster)

	def show_genres(self):
		if not self.genre: return
		genre_id = dialogs.genres_choice({'genres_list': movie_genres() if self.media_type == 'movie' else tvshow_genres(), 'genres': self.genre, 'poster': self.poster})
		if not genre_id: return
		self.close_all()
		mode, action = ('build_movie_list', 'tmdb_movies_genres') if self.media_type == 'movie' else ('build_tvshow_list', 'tmdb_tv_genres')
		self.selected = self.folder_runner({'mode': mode, 'action': action, 'key_id': genre_id})
		self.close()

	def show_keywords(self):
		keyword_id = dialogs.keywords_choice({'media_type': self.media_type, 'meta': self.meta})
		if not keyword_id: return
		self.close_all()
		mode, action = ('build_movie_list', 'tmdb_movie_keyword_results') if self.media_type == 'movie' else ('build_tvshow_list', 'tmdb_tv_keyword_results')
		self.selected = self.folder_runner({'mode': mode, 'action': action, 'key_id': keyword_id})
		self.close()

	def play_nextep(self):
		if self.nextep_season == None: return kodi_utils.ok_dialog(text='No Episodes Available')
		self.close_all()
		self.selected = 'RunPlugin(%s)' % self.build_url({
			'mode': 'playback.%s' % self.playback_key, 'media_type': 'episode', 'tmdb_id': self.tmdb_id,
			'season': self.nextep_season, 'episode': self.nextep_episode, 'autoplay': 'true',
			self.playback_key: self.playback_key
		})
		self.close()

	def play_random_episode(self):
		self.close_all()
		function = dialogs.random_choice({'meta': self.meta, 'poster': self.poster, 'return_choice': 'true'})
		if not function: return
		exec('EpisodeTools(self.meta).%s()' % function)
		self.close()

	def show_director(self):
		try: director = self.meta_get('director', None)[0]
		except: return self.notification('No Director Information Available')
		if not director: return
		self.set_current_params(set_starting_position=False)
		self.new_params = {'mode': 'person_data_dialog', 'key_id': director, 'is_external': self.is_external, 'stacked': 'true'}
		window_manager(self)

	def show_options(self):
		params = {'content': self.options_media_type, 'tmdb_id': str(self.tmdb_id), 'poster': self.poster, 'is_external': self.is_external, 'from_extras': 'true'}
		return dialogs.options_menu_choice(params, self.meta)

	def show_recommended(self):
		self.close_all()
		mode, action = ('build_movie_list', 'tmdb_movies_recommendations') if self.media_type == 'movie' else ('build_tvshow_list', 'tmdb_tv_recommendations')
		self.selected = self.folder_runner({'mode': mode, 'action': action, 'key_id': self.tmdb_id, 'name': 'Recommended based on %s' % self.title})
		self.close()

	def show_related(self):
		self.close_all()
		mode, action = ('build_movie_list', 'trakt_movies_related') if self.media_type == 'movie' else ('build_tvshow_list', 'trakt_tv_related')
		self.selected = self.folder_runner({'mode': mode, 'action': action, 'key_id': self.imdb_id, 'name': 'Related to %s' % self.title})
		self.close()

	def show_more_like_this(self):
		return self.show_network()
		self.close_all()
		mode = 'build_movie_list' if self.media_type == 'movie' else 'build_tvshow_list'
		self.selected = self.folder_runner({'mode': mode, 'action': 'imdb_more_like_this', 'key_id': self.imdb_id, 'name': 'More Like This based on %s' % self.title})
		self.close()

	def show_similar(self):
		self.close_all()
		mode = 'build_movie_list' if self.media_type == 'movie' else 'build_tvshow_list'
		self.selected = self.folder_runner({'mode': mode, 'action': 'ai_similar', 'key_id': '%s|%s' % (self.media_type, self.tmdb_id), 'name': 'Similar based on %s' % self.title})
		self.close()

	def show_reviews(self):
		if not self.all_reviews: return self.notification('No Reviews')
		return self.select_item(self.control_id, self.show_text_media(text=self.all_reviews, current_index=0))

	def show_comments(self):
		if not self.all_comments: return self.notification('No Comments')
		return self.select_item(self.control_id, self.show_text_media(text=self.all_comments, current_index=0))

	def show_trivia(self):
		if not self.all_trivia: return self.notification('No Trivia')
		return self.select_item(self.control_id, self.show_text_media(text=self.all_trivia, current_index=0))

	def show_blunders(self):
		if not self.all_blunders: return self.notification('No Blunders')
		return self.select_item(self.control_id, self.show_text_media(text=self.all_blunders, current_index=0))

	def show_year(self):
		if not self.year: return self.notification('Error getting Year')
		self.close_all()
		mode, action = ('build_movie_list', 'tmdb_movies_year') if self.media_type == 'movie' else ('build_tvshow_list', 'tmdb_tv_year')
		self.selected = self.folder_runner({'mode': mode, 'action': action, 'key_id': self.year, 'name': 'More from %s' % self.year})
		self.close()

	def show_genre(self):
		try:
			genre_list = ','.join([i['id'] for i in (movie_genres() if self.media_type == 'movie' else tvshow_genres()) if i['name'] in self.genre])
			if not genre_list: return self.notification('Error getting Genres')
		except: return self.notification('Error getting Genres')
		self.close_all()
		mode, action = ('build_movie_list', 'tmdb_movies_genres') if self.media_type == 'movie' else ('build_tvshow_list', 'tmdb_tv_genres')
		self.selected = self.folder_runner({'mode': mode, 'action': action, 'key_id': genre_list, 'name': 'More from %s' % ', '.join([i for i in self.genre])})
		self.close()

	def show_network(self):
		try:
			network = self.meta_get('studio')[0]
			network_id = tmdb_api.tmdb_company_id(network)['results'] if self.media_type == 'movie' else networks()
			network_id = next(i['id'] for i in network_id if i['name'] == network)
			if not network_id: return self.notification('Error getting Network')
		except: return self.notification('Error getting Network')
		self.close_all()
		mode, action = ('build_movie_list', 'tmdb_movies_companies') if self.media_type == 'movie' else ('build_tvshow_list', 'tmdb_tv_networks')
		self.selected = self.folder_runner({'mode': mode, 'action': action, 'key_id': network_id, 'name': 'More from %s' % network})
		self.close()

	def show_in_trakt_lists(self):
		self.close_all()
		media_type = 'movies' if self.media_type == 'movie' else 'shows'
		self.selected = self.folder_runner({'mode': 'trakt.list.in_trakt_lists', 'media_type': media_type,
											'imdb_id': self.imdb_id, 'category_name': '%s In Trakt Lists' % self.title})
		self.close()

	def show_trakt_manager(self):
		return dialogs.trakt_manager_choice({'tmdb_id': self.tmdb_id, 'imdb_id': self.imdb_id, 'tvdb_id': self.meta_get('tvdb_id', 'None'),
											'media_type': self.media_type, 'icon': self.poster})

	def show_simkl_manager(self):
		return dialogs.simkl_manager_choice({'tmdb_id': self.tmdb_id, 'imdb_id': self.imdb_id, 'tvdb_id': self.meta_get('tvdb_id', 'None'),
											'media_type': self.media_type, 'title': self.title, 'icon': self.poster})

	def show_mdblist_manager(self):
		return dialogs.mdblist_manager_choice({'tmdb_id': self.tmdb_id, 'imdb_id': self.imdb_id, 'tvdb_id': self.meta_get('tvdb_id', 'None'),
											'media_type': self.media_type, 'title': self.title, 'icon': self.poster})

	def show_punchplay_manager(self):
		return dialogs.punchplay_manager_choice({'tmdb_id': self.tmdb_id, 'imdb_id': self.imdb_id, 'tvdb_id': self.meta_get('tvdb_id', 'None'),
											'media_type': self.media_type, 'title': self.title, 'icon': self.poster})

	def show_personallists_manager(self):
		return dialogs.personallists_manager_choice({'list_type': self.media_type, 'tmdb_id': self.tmdb_id, 'title': self.title,
											'premiered': self.meta_get('premiered'), 'current_time': get_current_timestamp(), 'icon': self.poster})

	def show_tmdb_manager(self):
		return dialogs.tmdblists_manager_choice({'media_type': 'movie' if self.media_type == 'movie' else 'tv', 'tmdb_id': self.tmdb_id, 'icon': self.poster})

	def show_favorites_manager(self):
		return dialogs.favorites_manager_choice({'media_type': self.media_type, 'tmdb_id': str(self.tmdb_id), 'title': self.title, 'refresh': 'false'})

	def playback_choice(self):
		self.close_all()
		params = {'mode': 'playback_choice', 'media_type': self.media_type, 'meta': self.tmdb_id}
		self.selected = 'RunPlugin(%s)' % self.build_url(params)
		self.close()

	def assign_buttons(self):
		setting_id_base = 'redlight.extras.%s.button' % self.media_type
		for item in self.button_ids[:-1]:
			setting_id = setting_id_base + str(item)
			try:
				button_action = self.get_setting(setting_id)
				button_label = self.button_label_values[self.media_type][button_action]
			except:
				self.restore_setting_default({'setting_id': setting_id.replace('redlight.', ''), 'silent': 'true'})
				button_action = self.get_setting(setting_id)
				button_label = self.button_label_values[self.media_type][button_action]
			self.setProperty('button%s.label' % item, button_label)
			self.button_action_dict[item] = button_action
		self.button_action_dict[2050] = 'show_plot'

	def set_default_focus(self):
		try: self.setFocusId(10)
		except:
			self.close_all()
			self.close()

	def set_returning_focus(self, list_id, focus, sleep_time=700):
		try:
			self.sleep(sleep_time)
			self.setFocusId(list_id)
			self.select_item(list_id, focus)
		except: self.set_default_focus()

	def set_current_params(self, set_starting_position=True):
		self.current_params = {'mode': 'extras_menu_choice', 'tmdb_id': self.tmdb_id, 'media_type': self.media_type, 'is_external': self.is_external}
		if set_starting_position: self.current_params['starting_position'] = [self.control_id, self.get_position(self.control_id)]

	def set_starting_constants(self, kwargs):
		self.meta = kwargs.get('meta')
		self.meta_get = self.meta.get
		self.media_type, self.options_media_type = self.meta_get('mediatype'), kwargs.get('options_media_type')
		self.starting_position = kwargs.get('starting_position', None)
		self.is_external = kwargs.get('is_external').lower()
		self.item_action_dict, self.button_action_dict = {}, {}
		self.selected = None
		self.current_date = get_datetime()
		self.playback_key = settings.playback_key()
		self.current_params, self.new_params = {}, {}
		self.extra_info = self.meta_get('extra_info')
		self.extra_info_get = self.extra_info.get
		self.tmdb_id, self.imdb_id = self.meta_get('tmdb_id'), self.meta_get('imdb_id')
		self.folder_runner = kodi_utils.activate_window if self.is_external == 'true' else kodi_utils.container_update
		self.enabled_lists, self.enable_scrollbars = settings.extras_enabled(), settings.extras_enable_scrollbars()
		self.tmdb_api_key, self.omdb_api, self.mpaa_region = settings.tmdb_api_key(), settings.omdb_api_key(), settings.mpaa_region()
		self.display_extra_ratings = self.imdb_id and self.omdb_api not in ('empty_setting', '') and settings.extras_enable_extra_ratings()
		self.title, self.year, self.rootname = self.meta_get('title'), str(self.meta_get('year')), self.meta_get('rootname')
		rpdb_info = settings.rpdb_info('extras')
		self.rpdb_api_key, self.rpdb_format = rpdb_info['rpdb_api_key'], rpdb_info['rpdb_format']
		self.poster = self.meta_get('poster') or self.empty_poster
		self.fanart = self.meta_get('fanart') or self.addon_fanart
		self.clearlogo = self.meta_get('clearlogo') or ''
		self.landscape = self.meta_get('landscape') or ''
		self.rating = str(round(self.meta_get('rating'), 1)) if self.meta_get('rating') not in ('', '%', 0, 0.0, None) else None
		self.mpaa, self.genre, self.network = self.meta_get('mpaa'), self.meta_get('genre'), self.meta_get('studio') or ''
		self.status, self.duration_data = self.extra_info_get('status', '').replace(' Series', ''), int(float(self.meta_get('duration'))/60)
		self.status_infoline_value = self.make_status_infoline()
		self.stinger_dialog = self.make_stinger_dialog()
		self.single_rating_data = {'rating': self.rating, 'icon': 'tmdb.png'}
		self.make_plot_and_tagline()

	def set_properties(self):
		self.assign_buttons()
		self.set_home_property('window_theme.extras', self.get_home_property('window_theme'))
		self.setProperty('media_type', self.media_type), self.setProperty('title', self.title), self.setProperty('year', self.year), self.setProperty('plot', self.plot)
		self.setProperty('genre', ', '.join(self.genre)), self.setProperty('network', ', '.join(self.network)), self.setProperty('enable_scrollbars', self.enable_scrollbars)
		self.setProperty('display_extra_ratings', 'true' if self.display_extra_ratings else 'false')

	def make_status_infoline(self):
		status_str = self.status
		if self.media_type == 'tvshow' and self.status == 'Returning':
			try: next_aired_date = self.extra_info_get('next_episode_to_air')['air_date']
			except: next_aired_date = None
			if next_aired_date: status_str = '%s %s' % (self.status, adjust_premiered_date(next_aired_date, settings.date_offset())[0].strftime('%d %B %Y'))
		return status_str

	def make_stinger_dialog(self):
		stinger_dialog = ''
		if self.media_type == 'movie':
			stinger_keys = self.meta_get('stinger_keys', None)
			if not stinger_keys:
				try:
					keywords = self.meta_get('keywords', [])
					stinger_keys = [i['name'] for i in keywords['keywords'] if i['name'] in ('duringcreditsstinger', 'aftercreditsstinger')]
				except: pass
			if stinger_keys:
				stinger_names = tuple(sorted([{'duringcreditsstinger': 'During', 'aftercreditsstinger': 'After'}[i] for i in stinger_keys], reverse=True))
				stinger_dialog = {1: '%s Credits Stinger', 2: '%s & %s Credits Stinger'}[len(stinger_names)] % stinger_names
		return stinger_dialog

	def set_infoline1(self, rating_data=None, remove_rating=False):
		if remove_rating:
			rating = None
			self.set_image(203, '')
		else:
			data = rating_data or self.single_rating_data
			rating, image = data['rating'], 'redlight_flags/ratings/%s' % data['icon']
			if rating: self.set_image(203, image)
		self.set_label(2001, '[B]  •  [/B]'.join([i for i in (rating, self.year, self.mpaa, self.get_duration(), self.stinger_dialog, self.status_infoline_value) if i]))

	def set_infoline2(self):
		if self.media_type == 'movie':
			percent_watched = watched_status.get_progress_status_movie(watched_status.get_bookmarks_movie(), str(self.tmdb_id))
			if not percent_watched:
				try: percent_watched = '100' if watched_status.get_watched_status_movie(watched_status.watched_info_movie(), str(self.tmdb_id)) == 1 else '0'
				except: percent_watched = '0'
				if not percent_watched: percent_watched = 0
			line2 = '[B]  •  [/B]'.join([self.get_progress(percent_watched), self.get_finish(percent_watched)])
		else: line2 = '[B]  •  [/B]'.join([i for i in (self.get_next_episode(), self.get_last_aired(), self.get_next_aired()) if i])
		self.set_label(3001, line2)

	def close_all(self):
		kodi_utils.clear_property('redlight.window_stack')
		kodi_utils.close_all_dialog()

class ShowTextMedia(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.text = kwargs.get('text')
		self.position = kwargs.get('current_index', None)
		self.text_is_list = isinstance(self.text, list)
		self.len_text = len(self.text) if self.text_is_list else None
		self.window_id = 2099
		self.setProperty('poster', kwargs.get('poster'))

	def run(self):
		self.doModal()
		return self.position

	def onInit(self):
		self.update_text()
		self.setFocusId(self.window_id)	

	def onAction(self, action):
		if action in self.closing_actions: return self.close()
		if self.text_is_list:
			if action == self.left_action: return self.update_text('previous')
			if action == self.right_action: return self.update_text('next')

	def update_text(self, direction=None):
		if direction == 'previous': self.position = self.position - 1 if self.position > 0 else self.len_text - 1
		elif direction == 'next': self.position = 0 if self.position == self.len_text - 1 else self.position + 1
		self.set_text(2001, self.text[self.position] if self.text_is_list else self.text)
		if self.text_is_list:
			if self.position == 0: self.setProperty('previous_display', 'false')
			else: self.setProperty('previous_display', 'true')
			if self.position == self.len_text - 1: self.setProperty('next_display', 'false')
			else: self.setProperty('next_display', 'true')
		else: self.setProperty('previous_display', 'false'), self.setProperty('next_display', 'false')
