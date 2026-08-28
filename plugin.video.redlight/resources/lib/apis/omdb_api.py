# -*- coding: utf-8 -*-
from xml.dom.minidom import parseString as mdParse
from caches.meta_cache import meta_cache
from modules.metadata import movie_expiry, tvshow_expiry
from modules.utils import get_datetime, get_current_timestamp
from modules.kodi_utils import make_session
# from modules.kodi_utils import logger

session = make_session('http://www.omdbapi.com/')

class OMDbAPI:
	def fetch_info(self, meta, api_key):
		imdb_id = meta.get('imdb_id')
		if not imdb_id or not api_key: return {}
		self.api_key = api_key
		data = self.process_result(imdb_id, meta)
		return data

	def process_result(self, imdb_id, meta):
		data = {}
		self.result = self.get_result(imdb_id)
		if not self.result: return {}
		self.result_get = self.result.get
		metascore_rating, tomatometer_rating, tomatousermeter_rating = self.process_rating('metascore'), self.process_rating('tomatoMeter'), self.process_rating('tomatoUserMeter')
		imdb_rating, tomato_image = self.process_rating('imdbRating'), self.process_rating('tomatoImage')
		if tomato_image: tomatometer_icon = 'rtcertified.png' if tomato_image == 'certified' else 'rtfresh.png' if tomato_image == 'fresh' else 'rtrotten.png'
		elif tomatometer_rating: tomatometer_icon = 'rtfresh.png' if int(tomatometer_rating) > 59 else 'rtrotten.png'
		else: tomatometer_icon = 'rtrotten.png'
		if tomatousermeter_rating: tomatousermeter_icon = 'popcorn.png' if int(tomatousermeter_rating) > 59 else 'popcorn_spilt.png'
		else: tomatousermeter_icon = 'popcorn_spilt.png'		
		data = {
				'metascore': {'rating': '%s%%' %  metascore_rating, 'icon': 'metacritic.png'},
				'tomatometer': {'rating': '%s%%' % tomatometer_rating, 'icon': tomatometer_icon},
				'tomatousermeter': {'rating': '%s%%' % tomatousermeter_rating, 'icon': tomatousermeter_icon},
				'imdb': {'rating': imdb_rating, 'icon': 'imdb.png'},
				'tmdb': {'rating': str(round(meta.get('rating'), 1)) if meta.get('rating') not in (0, 0.0, None) else '', 'icon': 'tmdb.png'},
				}
		media_type = meta.get('mediatype')
		expiry_function = movie_expiry if media_type == 'movie' else tvshow_expiry
		meta['extra_ratings'] = data
		meta_cache.set(media_type, 'tmdb_id', meta, expiry_function(get_datetime(), meta), get_current_timestamp())
		return data

	def get_result(self, imdb_id):
		try:
			result = session.get('http://www.omdbapi.com/?apikey=%s&i=%s&tomatoes=True&r=xml' % (self.api_key, imdb_id), timeout=20).text
			response_test = dict(mdParse(result).getElementsByTagName('root')[0].attributes.items())
			if not response_test.get('response', 'False') == 'True': return None
			return dict(mdParse(result).getElementsByTagName('movie')[0].attributes.items())
		except: return None

	def process_rating(self, rating_name):
		return self.result_get(rating_name, '').replace('N/A', '')

def test_key(api_key):
	"""Return (ok, message) for Settings → Test API Key. Fight Club is always on OMDb."""
	if api_key in (None, '', 'empty_setting', 'None'):
		return False, 'Enter an OMDb API key first.'
	try:
		data = session.get('http://www.omdbapi.com/?apikey=%s&i=tt0137523&r=json' % api_key, timeout=15).json()
		if not isinstance(data, dict):
			return False, 'OMDb returned an unexpected response.'
		if str(data.get('Response', '')).lower() == 'true':
			return True, 'OMDb API key is valid.'
		error = data.get('Error') or 'OMDb rejected the key.'
		return False, error
	except Exception as e:
		return False, 'OMDb request failed.[CR]%s' % str(e)

fetch_ratings_info = OMDbAPI().fetch_info
