# -*- coding: utf-8 -*-

import re
import os
import sys
import datetime

import simplejson as json
import six
from six.moves import range, urllib_parse, zip

try:
    #from infotagger.listitem import ListItemInfoTag
    from resources.lib.modules.listitem import ListItemInfoTag
except:
    pass

from resources.lib.indexers import navigator

from resources.lib.modules import cache
from resources.lib.modules import cleantitle
from resources.lib.modules import client
from resources.lib.modules import client_utils
from resources.lib.modules import control
from resources.lib.modules import favorites
from resources.lib.modules import libtools
from resources.lib.modules import metacache
from resources.lib.modules import playcount
from resources.lib.modules import tmdb_utils
from resources.lib.modules import trakt
from resources.lib.modules import views
from resources.lib.modules import workers
#from resources.lib.modules import log_utils

try:
    from sqlite3 import dbapi2 as database
except:
    from pysqlite2 import dbapi2 as database

params = dict(urllib_parse.parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()
action = params.get('action')
#control.moderator()
kodi_version = control.getKodiVersion()


class tvshows:
    def __init__(self):
        self.list = []
        self.datetime = datetime.datetime.utcnow()
        self.systime = (self.datetime).strftime('%Y%m%d%H%M%S%f')
        self.year_date = (self.datetime - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
        self.month_date = (self.datetime - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        self.today_date = (self.datetime).strftime('%Y-%m-%d')
        self.addon_caching = control.setting('addon.caching') or 'true'
        self.addon_caching_timeout = int(control.setting('addon.caching_timeout')) or int('12')
        self.specials = control.setting('tv.specials') or 'true'
        self.shownoyear = control.setting('show.noyear') or 'false'
        self.showunaired = control.setting('showunaired') or 'true'
        self.unairedcolor = control.setting('unaired.color') or ''
        if self.unairedcolor == '':
            self.unairedcolor = 'darkred'
        self.hq_artwork = control.setting('fanart.artwork') or 'false'
        self.hq_artwork_size = control.setting('fanart.artwork_size') or 'false'
        self.studio_artwork = control.setting('studio.artwork') or 'false'
        self.items_per_page = str(control.setting('items.per.page')) or '20'
        self.lang = control.apiLanguage()['tmdb'] or 'en'
        self.trakt_user = control.setting('trakt.user').strip()
        self.tmdb_key = control.setting('tmdb.api') or ''
        if self.tmdb_key == '' or self.tmdb_key == None:
            self.tmdb_key = 'a0bf207c5ff6c0caabac0327e39b1cd2'
        self.fanart_tv_headers = {'api-key': 'cb36b6d02c5a0f8c74f2c836af02793d'}
        self.fanart_tv_user = control.setting('fanart.api') or ''
        if not self.fanart_tv_user == '' or self.fanart_tv_user == None:
            self.fanart_tv_headers.update({'client-key': self.fanart_tv_user})
        self.trakt_link = 'https://api.trakt.tv'
        # NOTE (1.0.2): switched from the public website (HTML scraping) to
        # the official JSON API.  The old ``tvmaze_list()`` parsed
        # ``div#w1`` / ``span.title`` from the rendered HTML which broke
        # whenever tvmaze.com tweaked its markup.  The new flow uses
        # ``api.tvmaze.com`` consistently.
        self.tvmaze_link = 'https://api.tvmaze.com'
        self.tmdb_link = 'https://api.themoviedb.org'
        self.tvmaze_info_link = 'https://api.tvmaze.com/shows/%s'
        self.tvmaze_popular_link  = self.tvmaze_link + '/shows?page=0'
        self.tvmaze_updates_day_link   = self.tvmaze_link + '/updates/shows?since=day'
        self.tvmaze_updates_week_link  = self.tvmaze_link + '/updates/shows?since=week'
        self.tvmaze_updates_month_link = self.tvmaze_link + '/updates/shows?since=month'
        self.fanart_tv_art_link = 'http://webservice.fanart.tv/tv/%s'
        self.search_tvshows_source = control.setting('search.tvshows.source') or '0'
        # My Trakt shelves must not use Kodi disc cache or add/remove looks stuck.
        self.cacheToDisc = True
        self.info_tvshows_source = control.setting('info.tvshows.source') or '0'
        self.info_art_source = control.setting('info.art.source') or '0'
        self.original_artwork = control.setting('original.artwork') or 'false'
        if self.original_artwork == 'true':
            self.tmdb_image_link = 'https://image.tmdb.org/t/p/original'
        else:
            self.tmdb_image_link = 'https://image.tmdb.org/t/p/w%s%s'
        self.tmdb_info_link = self.tmdb_link + '/3/tv/%s?api_key=%s&language=en-US&append_to_response=credits,content_ratings,external_ids' % ('%s', self.tmdb_key)

        self.tmdb_search_link = self.tmdb_link + '/3/search/tv?api_key=%s&query=%s&language=en-US&page=1' % (self.tmdb_key, '%s')
        self.tmdb_popular_link = self.tmdb_link + '/3/tv/popular?api_key=%s&language=en-US&page=1' % self.tmdb_key
        self.tmdb_featured_link = self.tmdb_link + '/3/discover/tv?api_key=%s&vote_count.gte=100&sort_by=first_air_date.desc&language=en-US&page=1' % self.tmdb_key
        self.tmdb_toprated_link = self.tmdb_link + '/3/tv/top_rated?api_key=%s&language=en-US&page=1' % self.tmdb_key
        self.tmdb_views_link = self.tmdb_link + '/3/discover/tv?api_key=%s&vote_count.gte=100&sort_by=vote_average.desc&language=en-US&page=1' % self.tmdb_key
        self.tmdb_airing_link = self.tmdb_link + '/3/tv/airing_today?api_key=%s&language=en-US&page=1' % self.tmdb_key
        self.tmdb_active_link = self.tmdb_link + '/3/tv/on_the_air?api_key=%s&language=en-US&page=1' % self.tmdb_key
        self.tmdb_premiere_link = self.tmdb_link + '/3/discover/tv?api_key=%s&first_air_date.gte=%s&first_air_date.lte=%s&language=en-US&page=1' % (self.tmdb_key, self.year_date, self.today_date)
        self.tmdb_trending_day_link = self.tmdb_link + '/3/trending/tv/day?api_key=%s&language=en-US&page=1' % self.tmdb_key
        self.tmdb_trending_week_link = self.tmdb_link + '/3/trending/tv/week?api_key=%s&language=en-US&page=1' % self.tmdb_key
        self.tmdb_genre_link = self.tmdb_link + '/3/discover/tv?api_key=%s&with_genres=%s&language=en-US&page=1' % (self.tmdb_key, '%s')
        self.tmdb_networks_link = self.tmdb_link + '/3/discover/tv?api_key=%s&with_networks=%s&language=en-US&page=1' % (self.tmdb_key, '%s')
        self.tmdb_year_link = self.tmdb_link + '/3/discover/tv?api_key=%s&first_air_date_year=%s&language=en-US&page=1' % (self.tmdb_key, '%s')
        self.tmdb_decade_link = self.tmdb_link + '/3/discover/tv?api_key=%s&first_air_date.gte=%s&first_air_date.lte=%s&language=en-US&page=1' % (self.tmdb_key, '%s', '%s')
        self.tmdb_language_link = self.tmdb_link + '/3/discover/tv?api_key=%s&with_original_language=%s&language=en-US&page=1' % (self.tmdb_key, '%s')
        self.tmdb_collections_link = self.tmdb_link + '/3/collection/%s?api_key=%s&language=en-US&page=1' % ('%s', self.tmdb_key)
        self.tmdb_userlists_link = self.tmdb_link + '/3/list/%s?api_key=%s&language=en-US&page=1' % ('%s', self.tmdb_key)
        self.tmdb_jew250tv_link = self.tmdb_userlists_link % ('86660')
        self.tmdb_jewtestshows_link = self.tmdb_userlists_link % ('97124')
        self.tmdb_huluorig_link = self.tmdb_userlists_link % ('47716')
        self.tmdb_netflixorig_link = self.tmdb_userlists_link % ('47713')
        self.tmdb_amazonorig_link = self.tmdb_userlists_link % ('47714')
        self.tmdb_favorites_link = tmdb_utils.get_tvshow_favorites()
        self.tmdb_watchlist_link = tmdb_utils.get_tvshow_watchlist()

        self.trakt_search_link = self.trakt_link + '/search/show?query=%s&limit=%s&page=1' % ('%s', self.items_per_page)
        self.trakt_history_link = self.trakt_link + '/users/me/history/shows?limit=%s&page=1' % self.items_per_page
        self.trakt_popular_link = self.trakt_link + '/shows/popular?limit=%s&page=1' % self.items_per_page
        self.trakt_featured_link = self.trakt_link + '/recommendations/shows?limit=%s&page=1' % self.items_per_page
        self.trakt_trending_link = self.trakt_link + '/shows/trending?limit=%s&page=1' % self.items_per_page
        self.trakt_anticipated_link = self.trakt_link + '/shows/anticipated?limit=%s&page=1' % self.items_per_page
        self.trakt_premieres_link = self.trakt_link + '/calendars/all/shows/premieres?limit=%s&page=1' % self.items_per_page
        self.trakt_update_link = self.trakt_link + '/shows/updates/%s?limit=%s&page=1' % ('%s', self.items_per_page)
        self.trakt_related_link = self.trakt_link + '/shows/%s/related'
        self.trakt_list_link = self.trakt_link + '/users/%s/lists/%s/items'
        self.trakt_lists_link = self.trakt_link + '/users/me/lists'
        # FIX: see movies.py for full explanation.  ``?limit=1000000`` is
        # silently clamped by Trakt and only the first page was ever read,
        # hiding every liked list past the first chunk.  Using the
        # documented ``limit=1000&page=1`` starting point plus the new
        # ``getTraktAsJsonPaged`` helper guarantees we walk every page.
        self.trakt_likedlists_link = self.trakt_link + '/users/likes/lists?limit=1000&page=1'
        # PAGINATION FIX: see movies.py for the full rationale.  Adding
        # ``?limit=N&page=1`` lets the existing next-page logic inside
        # ``trakt_list()`` kick in for large TV watchlists / favorites /
        # libraries instead of dumping every show on one directory page.
        self.trakt_collection_link = self.trakt_link + '/users/me/collection/shows?limit=%s&page=1' % self.items_per_page
        self.trakt_watchlist_link = self.trakt_link + '/users/me/watchlist/shows?limit=%s&page=1' % self.items_per_page
        self.trakt_watchedlist_link = self.trakt_link + '/users/me/watched/shows?extended=noseasons'
        self.trakt_favorites_link = self.trakt_link + '/users/me/favorites/shows?limit=%s&page=1' % self.items_per_page
        self.trakt_played1_link = self.trakt_link + '/shows/played/weekly?limit=%s&page=1' % self.items_per_page
        self.trakt_played2_link = self.trakt_link + '/shows/played/monthly?limit=%s&page=1' % self.items_per_page
        self.trakt_played3_link = self.trakt_link + '/shows/played/yearly?limit=%s&page=1' % self.items_per_page
        self.trakt_played4_link = self.trakt_link + '/shows/played/all?limit=%s&page=1' % self.items_per_page
        self.trakt_collected1_link = self.trakt_link + '/shows/collected/weekly?limit=%s&page=1' % self.items_per_page
        self.trakt_collected2_link = self.trakt_link + '/shows/collected/monthly?limit=%s&page=1' % self.items_per_page
        self.trakt_collected3_link = self.trakt_link + '/shows/collected/yearly?limit=%s&page=1' % self.items_per_page
        self.trakt_collected4_link = self.trakt_link + '/shows/collected/all?limit=%s&page=1' % self.items_per_page
        self.trakt_watched1_link = self.trakt_link + '/shows/watched/weekly?limit=%s&page=1' % self.items_per_page
        self.trakt_watched2_link = self.trakt_link + '/shows/watched/monthly?limit=%s&page=1' % self.items_per_page
        self.trakt_watched3_link = self.trakt_link + '/shows/watched/yearly?limit=%s&page=1' % self.items_per_page
        self.trakt_watched4_link = self.trakt_link + '/shows/watched/all?limit=%s&page=1' % self.items_per_page


    def favorites(self):
        try:
            items = favorites.getFavorites('tvshow')
            self.list = [i[1] for i in items]
            for i in self.list:
                if not 'year' in i:
                    i['year'] = '0'
                if not 'name' in i:
                    i['name'] = i['title']
                try:
                    #i['title'] = i['title'].encode('utf-8')
                    i['title'] = client_utils.replaceHTMLCodes(i['title'])
                except:
                    pass
                try:
                    #i['name'] = i['name'].encode('utf-8')
                    i['name'] = client_utils.replaceHTMLCodes(i['name'])
                except:
                    pass
                if not 'duration' in i:
                    i['duration'] = '0'
                if not 'imdb' in i:
                    i['imdb'] = '0'
                if not 'tmdb' in i:
                    i['tmdb'] = '0'
                if not 'tvdb' in i:
                    i['tvdb'] = '0'
                if not 'poster' in i:
                    i['poster'] = '0'
                if not 'banner' in i:
                    i['banner'] = '0'
                if not 'fanart' in i:
                    i['fanart'] = '0'
            self.worker()
            self.list = sorted(self.list, key=lambda k: k['title'])
            self.tvshowDirectory(self.list)
        except:
            #log_utils.log('favorites', 1)
            return


    def search_term_menu(self, select):
        navigator.navigator().addDirectoryItem('New Search...', 'tvshows_searchterm&select=%s' % select, 'search.png', 'DefaultTVShows.png')
        dbcon = database.connect(control.searchFile)
        dbcur = dbcon.cursor()
        try:
            dbcur.executescript("CREATE TABLE IF NOT EXISTS %s (ID Integer PRIMARY KEY AUTOINCREMENT, term);" % select)
        except:
            pass
        dbcur.execute("SELECT * FROM %s ORDER BY ID DESC" % select)
        delete_option = False
        for (id, term) in dbcur.fetchall():
            delete_option = True
            navigator.navigator().addDirectoryItem(term.title(), 'tvshows_searchterm&select=%s&name=%s' % (select, term), 'search.png', 'DefaultTVShows.png')
        dbcur.close()
        if delete_option:
            navigator.navigator().addDirectoryItem('Clear Search History', 'clear_search_cache&select=%s' % select, 'tools.png', 'DefaultAddonProgram.png')
        navigator.navigator().endDirectory(cached=False)


    def search_term(self, select, q=None):
        control.idle()
        if (q == None or q == ''):
            k = control.keyboard('', 'Search') ; k.doModal()
            q = k.getText() if k.isConfirmed() else None
        if (q == None or q == ''):
            return
        q = q.lower()
        dbcon = database.connect(control.searchFile)
        dbcur = dbcon.cursor()
        dbcur.execute("DELETE FROM %s WHERE term = ?" % select, (q,))
        dbcur.execute("INSERT INTO %s VALUES (?, ?)" % select, (None, q))
        dbcon.commit()
        dbcur.close()
        if select == 'tvshow':
            if self.search_tvshows_source == '1':
                url = self.trakt_search_link % urllib_parse.quote_plus(q)
            else:
                url = self.tmdb_search_link % urllib_parse.quote_plus(q)
            self.get(url)
        elif select == 'people':
            self.search_tmdb_people(q)
        elif select == 'keywords':
            self.search_tmdb_keyword(q)
        elif select == 'companies':
            self.search_tmdb_companies(q)
        elif select == 'collections':
            self.search_tmdb_collection(q)


    def search_tmdb_people(self, q=None):
        query = urllib_parse.quote_plus(q)
        self.list = tmdb_utils.find_people(None, query, 'tv')
        for i in range(0, len(self.list)):
            self.list[i].update({'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def search_tmdb_keyword(self, q=None):
        query = urllib_parse.quote_plus(q)
        self.list = tmdb_utils.find_keyword(None, query, 'tv')
        for i in range(0, len(self.list)):
            self.list[i].update({'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def search_tmdb_companies(self, q=None):
        query = urllib_parse.quote_plus(q)
        self.list = tmdb_utils.find_companies(query, 'tv')
        for i in range(0, len(self.list)):
            self.list[i].update({'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def search_tmdb_collection(self, q=None):
        query = urllib_parse.quote_plus(q)
        self.list = tmdb_utils.find_collection(query)
        for i in range(0, len(self.list)):
            self.list[i].update({'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_genres(self):
        from resources.lib.indexers.metadata.tmdb import tmdb_various
        genres = tmdb_various.tv_genre_list
        for item in genres:
            self.list.append({'name': item[0], 'url': self.tmdb_genre_link % item[1], 'image': 'genres.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_languages(self):
        from resources.lib.indexers.metadata.tmdb import tmdb_various
        languages = tmdb_various.language_list
        for item in languages:
            self.list.append({'name': item[0], 'url': self.tmdb_language_link % item[1], 'image': 'languages.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_popular_companies(self):
        from resources.lib.indexers.metadata.tmdb import tmdb_production_companies
        companies = tmdb_production_companies.companies
        for item in companies:
            item_url = self.tmdb_link + '/3/discover/tv?api_key=%s&with_companies=%s&language=en-US&page=1' % (self.tmdb_key, '%s')
            if self.original_artwork == 'true':
                item_art = self.tmdb_image_link + item['image'] if 'image' in item and not item['image'] == None else 'tmdb.png'
            else:
                item_art = self.tmdb_image_link % ('300', item['image']) if 'image' in item and not item['image'] == None else 'tmdb.png'
            self.list.append({'name': item['name'], 'url': item_url % item['id'], 'image': item_art, 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_popular_keywords(self):
        from resources.lib.indexers.metadata.tmdb import tmdb_keywords
        keywords = tmdb_keywords.keywords_list
        for item in keywords:
            item_url = self.tmdb_link + '/3/discover/tv?api_key=%s&with_keywords=%s&language=en-US&page=1' % (self.tmdb_key, '%s')
            self.list.append({'name': item['name'], 'url': item_url % item['id'], 'image': 'tmdb.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_popular_people(self):
        self.list = tmdb_utils.get_popular_people(None, 'tv')
        for i in range(0, len(self.list)):
            self.list[i].update({'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_years(self):
        year = (self.datetime.strftime('%Y'))
        for i in range(int(year)+1, 1900, -1):
            self.list.append({'name': str(i), 'url': self.tmdb_year_link % str(i), 'image': 'years.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_decades(self):
        year = (self.datetime.strftime('%Y'))
        dec = int(year[:3]) * 10
        for i in range(dec, 1890, -10):
            self.list.append({'name': str(i) + 's', 'url': self.tmdb_decade_link % (str(i) + '-01-01', str(i+9) + '-01-01'), 'image': 'years.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_networks(self):
        from resources.lib.indexers.metadata.tmdb import tmdb_networks
        networks = tmdb_networks.networks
        for network in networks:
            network_name = network['name']
            network_id = network['id']
            network_origin_country = network['origin_country']
            network_url = self.tmdb_networks_link % network_id
            network_label = '%s (%s)' % (network_name, network_origin_country) if network_origin_country else network_name
            self.list.append({'name': network_label, 'url': network_url, 'image': 'networks.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdbTvLists(self):
        from resources.lib.indexers.metadata.tmdb import tmdb_userlists
        userlists = tmdb_userlists.tmdb_TvLists
        for i in userlists:
            self.list.append({'name': i[0], 'url': self.tmdb_userlists_link % i[1], 'image': 'tmdb.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def userlists_trakt(self):
        userlists = []
        try:
            if trakt.getTraktCredentialsInfo() == False:
                raise Exception()
            activity = trakt.getActivity()
            from resources.lib.modules import trakt_cache
            userlists += trakt_cache.get(
                trakt.user_list_directory_tvshow,
                trakt_cache.TTL_LISTS_SEC,
                self.trakt_lists_link,
                self.trakt_list_link,
                self.trakt_user,
            )
        except:
            pass
        self.list = userlists
        if not self.list:
            if trakt.getTraktCredentialsInfo() == False:
                control.infoDialog('Connect Trakt in Settings > Account Settings to see your lists.', sound=True)
            else:
                control.infoDialog('No Trakt TV lists found.', sound=True)
        self.list = sorted(self.list, key=lambda k: (k['image'], k['name'].lower()))
        self.addDirectory(self.list)
        return self.list


    def userlists_trakt_liked(self):
        userlists = []
        try:
            if trakt.getTraktCredentialsInfo() == False:
                raise Exception()
            activity = trakt.getActivity()
            from resources.lib.modules import trakt_cache
            userlists += trakt_cache.get(
                trakt.user_list_directory_tvshow,
                trakt_cache.TTL_LISTS_SEC,
                self.trakt_likedlists_link,
                self.trakt_list_link,
                self.trakt_user,
            )
        except:
            pass
        self.list = userlists
        if not self.list:
            if trakt.getTraktCredentialsInfo() == False:
                control.infoDialog('Connect Trakt in Settings > Account Settings to see your lists.', sound=True)
            else:
                control.infoDialog('No Trakt TV lists found.', sound=True)
        self.list = sorted(self.list, key=lambda k: (k['image'], k['name'].lower()))
        self.addDirectory(self.list)
        return self.list


    def userlists_tmdb(self):
        userlists = []
        try:
            if tmdb_utils.getTMDbCredentialsInfo() == False:
                raise Exception()
            userlists += tmdb_utils.get_created_lists(self.tmdb_userlists_link, list_type='tv')
        except:
            pass
        self.list = userlists
        if not self.list:
            if tmdb_utils.getTMDbCredentialsInfo() == False:
                control.infoDialog('Authorize TMDb in Settings > Account Settings to see your lists.', sound=True)
            else:
                control.infoDialog('No TMDb TV lists found.', sound=True)
        self.list = sorted(self.list, key=lambda k: (k['image'], k['name'].lower()))
        self.addDirectory(self.list)
        return self.list


    def userlists_mdblist(self):
        from resources.lib.modules import mdblist as mdblist_mod
        self.list = mdblist_mod.user_list_directory('user', 'tvshows')
        if not self.list:
            if not mdblist_mod.getMdblistCredentialsInfo():
                control.infoDialog('Authorize MDBList in Settings > Account Settings to see your lists.', sound=True)
            else:
                control.infoDialog('No MDBList TV lists found.', sound=True)
        self.list = sorted(self.list, key=lambda k: (k.get('name') or '').lower())
        self.addDirectory(self.list)
        return self.list


    def userlists_mdblist_liked(self):
        from resources.lib.modules import mdblist as mdblist_mod
        self.list = mdblist_mod.user_list_directory('liked', 'tvshows')
        if not self.list:
            if not mdblist_mod.getMdblistCredentialsInfo():
                control.infoDialog('Authorize MDBList in Settings > Account Settings to see your lists.', sound=True)
            else:
                control.infoDialog('No liked MDBLists found.', sound=True)
        self.list = sorted(self.list, key=lambda k: (k.get('name') or '').lower())
        self.addDirectory(self.list)
        return self.list


    def userlists_mdblist_top(self):
        from resources.lib.modules import mdblist as mdblist_mod
        self.list = mdblist_mod.user_list_directory('top', 'tvshows')
        if not self.list:
            control.infoDialog('No popular MDBLists found.', sound=True)
        self.list = sorted(self.list, key=lambda k: (k.get('name') or '').lower())
        self.addDirectory(self.list)
        return self.list


    def local_library(self):
        self.list = libtools.libtvshows().scan_local_items()
        if not self.list:
            control.infoDialog('No TV shows found in your local library folder.', sound=True)
        self.tvshowDirectory(self.list)
        return self.list


    def trakt_list(self, url, user):
        try:
            q = dict(urllib_parse.parse_qsl(urllib_parse.urlsplit(url).query))
            q.update({'extended': 'full'})
            q = (urllib_parse.urlencode(q)).replace('%2C', ',')
            u = url.replace('?' + urllib_parse.urlparse(url).query, '') + '?' + q
            result = trakt.getTraktAsJson(u)
            if result is None:
                try:
                    from kodi_six import xbmc as _xbmc
                    _xbmc.log('[Gratis Red] trakt_list empty/failed for %s' % u, _xbmc.LOGINFO)
                except Exception:
                    pass
                result = []
            items = []
            for i in result:
                try:
                    if not isinstance(i, dict):
                        continue
                    if 'show' in i and isinstance(i.get('show'), dict):
                        row = dict(i['show'])
                        row['collected_at'] = i.get('listed_at') or i.get('last_collected_at') or i.get('collected_at') or ''
                        if i.get('paused_at'):
                            row['paused_at'] = i.get('paused_at')
                        items.append(row)
                    else:
                        items.append(i)
                except:
                    pass
            try:
                q = dict(urllib_parse.parse_qsl(urllib_parse.urlsplit(url).query))
                if not int(q['limit']) == len(items):
                    raise Exception()
                q.update({'page': str(int(q['page']) + 1)})
                q = (urllib_parse.urlencode(q)).replace('%2C', ',')
                next = url.replace('?' + urllib_parse.urlparse(url).query, '') + '?' + q
                next = six.ensure_str(next)
            except:
                next = ''
            before = len(items)
            start = len(self.list)
            for item in items:
                try:
                    title = item['title']
                    title = re.sub(r'\s(|[(])(UK|US|AU|\d{4})(|[)])$', '', title)
                    title = client_utils.replaceHTMLCodes(title)
                    year = item.get('year')
                    if not year:
                        year = '0'
                    else:
                        year = re.sub(r'[^0-9]', '', str(year))
                    if int(year) > int(self.datetime.strftime('%Y')):
                        if self.shownoyear != 'true':
                            raise Exception()
                    imdb = item.get('ids', {}).get('imdb')
                    if not imdb:
                        imdb = '0'
                    else:
                        imdb = 'tt' + re.sub(r'[^0-9]', '', str(imdb))
                    tmdb = item.get('ids', {}).get('tmdb')
                    if not tmdb:
                        tmdb = '0'
                    else:
                        tmdb = str(tmdb)
                    tvdb = item.get('ids', {}).get('tvdb')
                    if not tvdb:
                        tvdb = '0'
                    else:
                        tvdb = re.sub(r'[^0-9]', '', str(tvdb))
                    paused_at = item.get('paused_at')
                    if not paused_at:
                        paused_at = '0'
                    else:
                        paused_at = re.sub(r'[^0-9]+', '', str(paused_at))
                    collected_at = item.get('collected_at') or ''
                    self.list.append({'title': title, 'originaltitle': title, 'year': year, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'next': next, 'paused_at': paused_at, 'collected_at': collected_at})
                except:
                    #log_utils.log('trakt_list', 1)
                    pass
            appended = len(self.list) - start
            if before and appended != before:
                try:
                    from kodi_six import xbmc as _xbmc
                    _xbmc.log(
                        '[Gratis Red] trakt_list dropped %s/%s items for %s' % (
                            before - appended, before, u),
                        _xbmc.LOGINFO)
                except Exception:
                    pass
        except:
            #log_utils.log('trakt_list', 1)
            pass
        return self.list


    def trakt_user_list(self, url, user):
        try:
            # FIX (Trakt lists missing): use the paginated helper so that
            # every page of the user's personal / liked lists is merged
            # into a single array before we render the directory.  The
            # previous single-page call made larger Trakt accounts look
            # like the API was "blocking" them when in reality only page
            # 1 was being requested.
            items = trakt.getTraktAsJsonPaged(url)
            if not items:
                items = []
            for item in items:
                try:
                    try:
                        name = item['list']['name']
                    except:
                        name = item['name']
                    name = client_utils.replaceHTMLCodes(name)
                    try:
                        url = (trakt.slug(item['list']['user']['username']), item['list']['ids']['slug'])
                    except:
                        url = ('me', item['ids']['slug'])
                    url = self.trakt_list_link % url
                    self.list.append({'name': name, 'url': url, 'context': url, 'image': 'trakt.png'})
                except:
                    #log_utils.log('trakt_user_list', 1)
                    pass
        except:
            #log_utils.log('trakt_user_list', 1)
            pass
        return self.list


    def tvmaze_list(self, url):
        """
        API-based replacement for the old HTML-scraping version.

        Recognised URL patterns (all on ``https://api.tvmaze.com``):
          /shows?page=N                           - 250 shows / page (id-ordered)
          /shows?page=N&network=ID                - filter to traditional network
          /shows?page=N&webchannel=ID             - filter to streaming channel
          /shows?page=N&genre=NAME                - filter by genre
          /shows?page=N&country=CC                - filter by network country
          /updates/shows?since=day|week|month     - {showId: ts} -> top-by-id
          /search/shows?q=X                       - full-text search

        Items are converted to the same dict shape used by the TMDb / Trakt
        list builders so the rest of the pipeline (worker, metacache,
        directory) keeps working untouched.
        """
        try:
            from six.moves.urllib_parse import urlparse, parse_qs
            parsed = urlparse(url)
            path = parsed.path
            qs = parse_qs(parsed.query)

            # Decide which endpoint to call and which client-side filter
            # to apply.
            page = int((qs.get('page') or ['0'])[0])
            network_id    = (qs.get('network')    or [''])[0]
            webchannel_id = (qs.get('webchannel') or [''])[0]
            genre_filter  = (qs.get('genre')      or [''])[0]
            country       = (qs.get('country')    or [''])[0]
            since         = (qs.get('since')      or [''])[0]
            search_q      = (qs.get('q')          or [''])[0]

            shows = []
            next_url = ''

            if '/updates/shows' in path:
                # /updates/shows?since=X  -> dict {id: timestamp}.  Pull
                # the top 60 most-recently-updated ids and resolve them.
                upd = client.scrapePage(url, timeout='30').json() or {}
                ids = sorted(upd.items(), key=lambda kv: int(kv[1]), reverse=True)
                ids = [i[0] for i in ids][:60]
                def _fetch(_id, _bucket):
                    try:
                        s = client.scrapePage(self.tvmaze_info_link % _id, timeout='30').json()
                        if s and 'id' in s:
                            _bucket.append(s)
                    except Exception:
                        pass
                bucket = []
                threads = [workers.Thread(_fetch, i, bucket) for i in ids]
                [t.start() for t in threads]
                [t.join() for t in threads]
                shows = bucket

            elif '/search/shows' in path:
                res = client.scrapePage(url, timeout='30').json() or []
                shows = [r.get('show', {}) for r in res if r.get('show')]

            else:
                # /shows?page=N  (with optional client-side filter)
                #
                # BUG FIX (v1.0.4): for any *filtered* query (network /
                # webchannel / genre / country) the old code only fetched
                # a single 250-show page and then filtered it client-side.
                # Because TVmaze paginates ``/shows`` by show-id (oldest
                # first), most networks/webchannels have at most a handful
                # of matching shows in any given page - so users were
                # seeing empty or partial lists ("some networks open but
                # don't show all the shows").  We now sweep across many
                # pages in parallel and aggregate the matches before
                # returning.  Each page is fetched with the same caching
                # the unfiltered branch already enjoys (the upstream
                # ``cache.get(self.tvmaze_list, ...)`` covers the whole
                # call).
                if network_id or webchannel_id or genre_filter or country:
                    # Use the shared cached "all shows" pool instead of
                    # sweeping pages per click - one ~25 s pool build
                    # is amortised across every Networks / WebChannels /
                    # Genres / Countries query for the whole TTL window.
                    if self.addon_caching == 'true':
                        pool = cache.get(self._tvmaze_pool, self.addon_caching_timeout)
                    else:
                        pool = self._tvmaze_pool()
                    pool = pool or []

                    if network_id:
                        nid = int(network_id)
                        shows = [s for s in pool if (s.get('network') or {}).get('id') == nid]
                    elif webchannel_id:
                        wid = int(webchannel_id)
                        shows = [s for s in pool if (s.get('webChannel') or {}).get('id') == wid]
                    elif genre_filter:
                        g = genre_filter.lower()
                        shows = [s for s in pool if g in [x.lower() for x in (s.get('genres') or [])]]
                    else:  # country
                        cc = country.upper()
                        def _cc(s):
                            n = s.get('network') or s.get('webChannel') or {}
                            c = (n.get('country') or {}).get('code', '') or ''
                            return c.upper()
                        shows = [s for s in pool if _cc(s) == cc]

                    # Sort matches by TVmaze popularity weight so the most
                    # relevant titles surface first, then page-window the
                    # result set so the directory loads quickly.
                    shows = sorted(shows,
                                   key=lambda s: int(s.get('weight') or 0),
                                   reverse=True)
                    PAGE_SIZE = 80
                    total_matches = len(shows)
                    start = page * PAGE_SIZE
                    shows = shows[start:start + PAGE_SIZE]
                    has_more = (start + PAGE_SIZE) < total_matches
                else:
                    # Unfiltered "Most Popular" page-0 view.
                    page_url = '%s/shows?page=%s' % (self.tvmaze_link, page)
                    shows = client.scrapePage(page_url, timeout='30').json() or []
                    # No filter -> "Most Popular"-style ordering: TVmaze
                    # sorts /shows by id (oldest first), so we re-sort by
                    # its built-in ``weight`` field (popularity score).
                    shows = sorted(shows, key=lambda s: int(s.get('weight') or 0), reverse=True)
                    # PERF FIX (v1.0.3): the old code pushed all 250
                    # rows from a single TVmaze page through worker(),
                    # which performs a TMDb info lookup *per show*
                    # (often falling back to a Trakt search when imdb
                    # is missing).  250 lookups in 40-thread batches
                    # routinely took 60-120 s, which the user reported
                    # as "Most Popular Shows takes an age to load".
                    # Showing only the top 80 by weight cuts the wait
                    # to under 15 s while leaving the existing
                    # next-page link in place for users who want more.
                    shows = shows[:80]
                    has_more = True

                # Pagination: always offer a "next page" link when there
                # is more to show.
                if shows and has_more and page < 200:
                    parts = []
                    for k in ('network', 'webchannel', 'genre', 'country'):
                        v = qs.get(k)
                        if v:
                            parts.append('%s=%s' % (k, v[0]))
                    parts.append('page=%s' % (page + 1))
                    next_url = '%s/shows?%s' % (self.tvmaze_link, '&'.join(parts))

            # ---- normalise into the addon's standard show-dict shape ----
            for item in shows:
                try:
                    title = item.get('name')
                    if not title:
                        continue
                    title = re.sub(r'\s(|[(])(UK|US|AU|\d{4})(|[)])$', '', title)
                    title = client_utils.replaceHTMLCodes(title)

                    premiered = item.get('premiered') or ''
                    try:
                        premiered = re.findall(r'(\d{4}-\d{2}-\d{2})', premiered)[0]
                    except Exception:
                        premiered = '0'

                    year = item.get('premiered') or ''
                    try:
                        year = re.findall(r'(\d{4})', year)[0]
                    except Exception:
                        year = '0'

                    if year != '0' and int(year) > int(self.datetime.strftime('%Y')):
                        if self.shownoyear != 'true':
                            continue

                    externals = item.get('externals') or {}
                    imdb = externals.get('imdb')
                    imdb = ('tt' + re.sub(r'[^0-9]', '', str(imdb))) if imdb else '0'
                    tvdb = externals.get('thetvdb')
                    tvdb = re.sub(r'[^0-9]', '', str(tvdb)) if tvdb else '0'

                    content = (item.get('type') or '').lower() or '0'
                    if content != '0':
                        content = six.ensure_str(content)

                    self.list.append({
                        'title': title, 'originaltitle': title,
                        'year': year, 'premiered': premiered,
                        'imdb': imdb, 'tvdb': tvdb, 'tmdb': '0',
                        'content': content, 'next': next_url,
                    })
                except Exception:
                    continue
            return self.list
        except Exception:
            #log_utils.log('tvmaze_list', 1)
            return self.list


    # ------ menus driven by the (now actually-existing) tvmaze metadata ------

    def _tvmaze_pool(self):
        """
        Build a deduplicated pool of every show on TVmaze.

        Used by the Networks / WebChannels / Genres / Countries menus so
        that filtering by ``network=ID`` / ``webchannel=ID`` / ``genre`` /
        ``country`` actually returns the network's real catalogue
        instead of just the handful of matching shows that happen to
        live on TVmaze's first id-ordered page.

        Wrapped by the caller in ``cache.get(...)`` so the slow-but-only-
        once page-sweep (~25 s for ~360 pages) is amortised across every
        subsequent click for the whole cache TTL window.

        Returns a list of TVmaze show dicts (the raw JSON shape from
        ``GET /shows?page=N``), trimmed to the fields downstream
        ``tvmaze_list()`` actually uses so the cache row stays small
        enough to round-trip through pickle/zlib quickly.
        """
        try:
            BATCH_SIZE = 25  # parallel page fetches per batch
            MAX_PAGES  = 400 # safety cap (TVmaze currently has ~370)

            pool = []
            page = 0
            done = False

            while not done and page < MAX_PAGES:
                bucket = []

                def _fetch(p, _bucket):
                    try:
                        data = client.scrapePage(
                            '%s/shows?page=%s' % (self.tvmaze_link, p),
                            timeout='30').json()
                    except Exception:
                        data = None
                    _bucket.append((p, data))

                threads = [workers.Thread(_fetch, page + i, bucket)
                           for i in range(BATCH_SIZE)]
                [t.start() for t in threads]
                [t.join() for t in threads]

                bucket.sort(key=lambda kv: kv[0])
                for p, data in bucket:
                    if not isinstance(data, list) or len(data) == 0:
                        # 404 / empty -> we've reached the end of the
                        # TVmaze id-paginated catalogue.
                        done = True
                        continue
                    for s in data:
                        try:
                            pool.append({
                                'id'        : s.get('id'),
                                'name'      : s.get('name'),
                                'premiered' : s.get('premiered'),
                                'type'      : s.get('type'),
                                'weight'    : s.get('weight'),
                                'genres'    : s.get('genres') or [],
                                'externals' : s.get('externals') or {},
                                'network'   : s.get('network') or {},
                                'webChannel': s.get('webChannel') or {},
                            })
                        except Exception:
                            continue
                page += BATCH_SIZE
            return pool
        except Exception:
            return []


    def tvmaze_networks(self):
        from resources.lib.indexers.metadata.tvmaze import tvmaze_networks
        for i in tvmaze_networks.networks:
            self.list.append({'name': i[0], 'url': self.tvmaze_link + i[1], 'image': 'networks.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tvmaze_webchannels(self):
        from resources.lib.indexers.metadata.tvmaze import tvmaze_networks
        for i in tvmaze_networks.webchannels:
            self.list.append({'name': i[0], 'url': self.tvmaze_link + i[1], 'image': 'networks.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tvmaze_genres(self):
        # Genres TVmaze advertises on its show records.
        genres = ['Action', 'Adult', 'Adventure', 'Anime', 'Children',
                  'Comedy', 'Crime', 'DIY', 'Drama', 'Espionage', 'Family',
                  'Fantasy', 'Food', 'History', 'Horror', 'Legal', 'Medical',
                  'Music', 'Mystery', 'Nature', 'Romance', 'Science-Fiction',
                  'Sports', 'Supernatural', 'Thriller', 'Travel', 'War',
                  'Western']
        for g in genres:
            url = '%s/shows?page=0&genre=%s' % (self.tvmaze_link, g)
            self.list.append({'name': g, 'url': url, 'image': 'genres.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tvmaze_countries(self):
        countries = [('United States', 'US'), ('United Kingdom', 'GB'),
                     ('Australia', 'AU'), ('Canada', 'CA'), ('Japan', 'JP'),
                     ('Korea, Republic of', 'KR'), ('France', 'FR'),
                     ('Germany', 'DE'), ('Spain', 'ES'), ('Italy', 'IT'),
                     ('Mexico', 'MX'), ('Brazil', 'BR'), ('India', 'IN'),
                     ('Sweden', 'SE'), ('Denmark', 'DK'), ('Norway', 'NO'),
                     ('Netherlands', 'NL'), ('Ireland', 'IE'),
                     ('New Zealand', 'NZ'), ('Israel', 'IL')]
        for name, cc in countries:
            url = '%s/shows?page=0&country=%s' % (self.tvmaze_link, cc)
            self.list.append({'name': name, 'url': url, 'image': 'languages.png', 'action': 'tvshows'})
        self.addDirectory(self.list)
        return self.list


    def tmdb_list(self, url):
        try:
            if 'date[' in url:
                for i in re.findall(r'date\[(\d+)\]', url):
                    url = url.replace('date[%s]' % i, (self.datetime - datetime.timedelta(days=int(i))).strftime('%Y-%m-%d'))
            result = client.scrapePage(url, timeout='30').json()
            try:
                page = int(result['page'])
                total = int(result['total_pages'])
                if page >= total:
                    raise Exception()
                if not 'page=' in url:
                    raise Exception()
                next = '%s&page=%s' % (url.split('&page=', 1)[0], str(page+1))
            except:
                next = ''
            if 'results' in result:
                items = result['results']
            elif 'items' in result:
                items = result['items']
            elif 'parts' in result:
                items = result['parts']
            elif 'cast' in result:
                items = result['cast']
            for raw in items:
                try:
                    media_type, item = tmdb_utils.unwrap_tmdb_list_item(raw)
                    if media_type != 'tv' or not item:
                        raise Exception()
                    if 'media_type' in item and not item['media_type'] == 'tv':
                        raise Exception()
                    title = item['name']
                    title = client_utils.replaceHTMLCodes(title)
                    originaltitle = item['original_name']
                    originaltitle = client_utils.replaceHTMLCodes(originaltitle)
                    if not originaltitle:
                        originaltitle = title
                    premiered = item.get('first_air_date')
                    if not premiered:
                        premiered = '0'
                    try:
                        year = re.findall(r'(\d{4})', premiered)[0]
                    except:
                        year = ''
                    if not year:
                        year = '0'
                    if int(year) > int(self.datetime.strftime('%Y')):
                        if self.shownoyear != 'true':
                            raise Exception()
                    tmdb = item.get('id')
                    if not tmdb:
                        tmdb = '0'
                    else:
                        tmdb = re.sub(r'[^0-9]', '', str(tmdb))
                    self.list.append({'title': title, 'originaltitle': originaltitle, 'premiered': premiered, 'year': year, 'imdb': '0', 'tmdb': tmdb, 'tvdb': '0', 'next': next})
                except:
                    #log_utils.log('tmdb_list', 1)
                    pass
        except:
            #log_utils.log('tmdb_list', 1)
            pass
        return self.list


    def get_fanart_tv_artwork(self, id): #tvdb
        try:
            art = client.scrapePage(self.fanart_tv_art_link % id, headers=self.fanart_tv_headers, timeout='30').json()
            try:
                poster = art.get('tvposter')
                if poster:
                    poster = [x for x in poster if x.get('lang') == 'en'][::-1] + [x for x in poster if x.get('lang') in ['00', '']][::-1]
                    poster = poster[0].get('url')
                    if poster and self.hq_artwork_size:
                        poster = poster.replace('/fanart/', '/preview/')
                    if not poster:
                        poster = '0'
                else:
                    poster = '0'
            except:
                poster = '0'
            try:
                if 'showbackground' in art:
                    fanart = art.get('showbackground')
                else:
                    fanart = art.get('tvthumb')
                if fanart:
                    fanart = [x for x in fanart if x.get('lang') == 'en'][::-1] + [x for x in fanart if x.get('lang') in ['00', '']][::-1]
                    fanart = fanart[0].get('url')
                    if fanart and self.hq_artwork_size:
                        fanart = fanart.replace('/fanart/', '/preview/')
                    if not fanart:
                        fanart = '0'
                else:
                    fanart = '0'
            except:
                fanart = '0'
            try:
                banner = art.get('tvbanner')
                if banner:
                    banner = [x for x in banner if x.get('lang') == 'en'][::-1] + [x for x in banner if x.get('lang') in ['00', '']][::-1]
                    banner = banner[0].get('url')
                    if banner and self.hq_artwork_size:
                        banner = banner.replace('/fanart/', '/preview/')
                    if not banner:
                        banner = '0'
                else:
                    banner = '0'
            except:
                banner = '0'
            try:
                if 'hdtvlogo' in art:
                    clearlogo = art.get('hdtvlogo')
                else:
                    clearlogo = art.get('clearlogo')
                if clearlogo:
                    clearlogo = [x for x in clearlogo if x.get('lang') == 'en'][::-1] + [x for x in clearlogo if x.get('lang') in ['00', '']][::-1]
                    clearlogo = clearlogo[0].get('url')
                    if clearlogo and self.hq_artwork_size:
                        clearlogo = clearlogo.replace('/fanart/', '/preview/')
                    if not clearlogo:
                        clearlogo = '0'
                else:
                    clearlogo = '0'
            except:
                clearlogo = '0'
            try:
                if 'hdclearart' in art:
                    clearart = art.get('hdclearart')
                else:
                    clearart = art.get('clearart')
                if clearart:
                    clearart = [x for x in clearart if x.get('lang') == 'en'][::-1] + [x for x in clearart if x.get('lang') in ['00', '']][::-1]
                    clearart = clearart[0].get('url')
                    if clearart and self.hq_artwork_size:
                        clearart = clearart.replace('/fanart/', '/preview/')
                    if not clearart:
                        clearart = '0'
                else:
                    clearart = '0'
            except:
                clearart = '0'
            try:
                if 'tvthumb' in art:
                    landscape = art.get('tvthumb')
                else:
                    landscape = art.get('showbackground')
                if landscape:
                    landscape = [x for x in landscape if x.get('lang') == 'en'][::-1] + [x for x in landscape if x.get('lang') in ['00', '']][::-1]
                    landscape = landscape[0].get('url')
                    if landscape and self.hq_artwork_size:
                        landscape = landscape.replace('/fanart/', '/preview/')
                    if not landscape:
                        landscape = '0'
                else:
                    landscape = '0'
            except:
                landscape = '0'
        except:
            poster = fanart = banner = clearlogo = clearart = landscape = '0'
        return poster, fanart, banner, clearlogo, clearart, landscape


    def trakt_info(self, i):
        try:
            if self.list[i]['metacache'] == True:
                return
            imdb = self.list[i]['imdb'] if 'imdb' in self.list[i] else '0'
            tmdb = self.list[i]['tmdb'] if 'tmdb' in self.list[i] else '0'
            tvdb = self.list[i]['tvdb'] if 'tvdb' in self.list[i] else '0'
            if imdb == '0' and not tmdb == '0':
                try:
                    temp_item = tmdb_utils.get_tvshow_external_ids(tmdb)
                    imdb = temp_item.get('imdb_id', '0') or '0'
                except:
                    pass
            if imdb == '0' and tmdb == '0':
                try:
                    temp_item = trakt.SearchTVShow(self.list[i]['title'], self.list[i]['year'])
                    if temp_item[0]['show']['title'].lower() != self.list[i]['title'].lower() or int(temp_item[0]['show']['year']) != int(self.list[i]['year']):
                        raise Exception()
                    imdb = temp_item[0]['show'].get('ids', {}).get('imdb') or '0'
                    tmdb = temp_item[0]['show'].get('ids', {}).get('tmdb') or '0'
                except:
                    pass
            if not imdb or imdb == '0':
                raise Exception()
            item = trakt.getTVShowSummary(imdb, full=True)
            if not item:
                raise Exception()
            if not tmdb or tmdb == '0':
                tmdb = item.get('ids', {}).get('tmdb', '0')
            if not tvdb or tvdb == '0':
                tvdb = item.get('ids', {}).get('tvdb', '0')
            title = self.list[i].get('title')
            if not title or title == '0':
                title = item.get('title')
            title = client_utils.replaceHTMLCodes(title)
            originaltitle = self.list[i].get('originaltitle')
            if not originaltitle or originaltitle == '0':
                originaltitle = title
            originaltitle = client_utils.replaceHTMLCodes(originaltitle)
            year = self.list[i].get('year', '0')
            if not year or year == '0':
                year = item.get('year', '0')
            if year and year != '0':
                year = re.compile(r'(\d{4})').findall(year)[0] or '0'
            else:
                year = '0'
            premiered = self.list[i].get('premiered', '0')
            if not premiered or premiered == '0':
                premiered = item.get('first_aired', '0')
            if premiered and premiered != '0':
                premiered = re.compile(r'(\d{4}-\d{2}-\d{2})').findall(premiered)[0]
            else:
                premiered = '0'
            if self.studio_artwork == 'true':
                studio = trakt.getStudio(imdb, 'shows')
                if studio and studio != []:
                    studio = [x['name'] for x in studio]
                else:
                    studio = []
            else:
                studio = []
            genre = item.get('genres', [])
            if genre and genre != []:
                genre = [x.title() for x in genre]
                #genre = ' / '.join(genre).strip()
            else:
                genre = []
            duration = item.get('runtime', '0')
            if not duration or duration == '0':
                duration = '0'
            status = item.get('status', '0')
            if not status or status == '0':
                status = '0'
            rating = item.get('rating', '0')
            if not rating or rating == '0' or rating == '0.0':
                rating = '0'
            votes = item.get('votes', '0')
            #votes = str(format(int(votes), ',d'))
            if not votes or votes == '0':
                votes = '0'
            mpaa = item.get('certification', '0')
            if not mpaa or mpaa == '0':
                mpaa = '0'
            plot = item.get('overview', '0')
            if not plot or plot == '0':
                plot = '0'
            tagline = item.get('tagline', '0')
            if not tagline or tagline == '0':
                tagline = '0'
            people = trakt.getPeople(imdb, 'shows')
            castwiththumb = []
            try:
                r_cast = people.get('cast', [])#[:30]
                for person in r_cast:
                    castwiththumb.append({'name': person['person']['name'], 'role': person['character'], 'thumbnail': ''})
                #castwiththumb = [(person['name'], person['role']) for person in castwiththumb]
            except:
                pass
            if not castwiththumb:
                castwiththumb = []
            try:
                if 'crew' in people and 'directing' in people['crew']:
                    director = [director['person']['name'] for director in people['crew']['directing'] if director['job'].lower() == 'director']
                    #director = ', '.join([director['person']['name'] for director in people['crew']['directing'] if director['job'].lower() == 'director'])
                else:
                    director = []
            except:
                director = []
            try:
                if 'crew' in people and 'writing' in people['crew']:
                    writer = [writer['person']['name'] for writer in people['crew']['writing'] if writer['job'].lower() in ['writer', 'screenplay', 'author']]#'Original Series Creator'
                    #writer = ', '.join([writer['person']['name'] for writer in people['crew']['writing'] if writer['job'].lower() in ['writer', 'screenplay', 'author']])
                else:
                    writer = []
            except:
                writer = []
            poster, fanart, banner = tmdb_utils.get_tmdb_artwork(tmdb, 'tv')
            if self.hq_artwork == 'true':
                poster2, fanart2, banner, clearlogo, clearart, landscape = self.get_fanart_tv_artwork(tvdb)
            else:
                poster2, fanart2, banner = poster, fanart, banner
                clearlogo = clearart = landscape = '0'
            if self.info_art_source == '1':
                poster = poster2 if not poster2 == '0' else poster
                fanart = fanart2 if not fanart2 == '0' else fanart
            elif self.info_art_source == '2':
                poster = poster2 if not poster2 == '0' else poster
                fanart = fanart2 if not fanart2 == '0' else fanart
            else:
                poster = poster if not poster == '0' else poster2
                fanart = fanart if not fanart == '0' else fanart2
            item = {'title': title, 'originaltitle': originaltitle, 'year': year, 'premiered': premiered, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'status': status, 'studio': studio, 'genre': genre,
                'duration': duration, 'rating': rating, 'votes': votes, 'mpaa': mpaa, 'plot': plot, 'tagline': tagline, 'castwiththumb': castwiththumb, 'director': director, 'writer': writer,
                'poster': poster, 'fanart': fanart, 'banner': banner, 'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape
            }
            item = dict((k,v) for k, v in six.iteritems(item) if not v == '0')
            self.list[i].update(item)
            meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'lang': self.lang, 'item': item}
            self.meta.append(meta)
        except:
            #log_utils.log('trakt_info', 1)
            pass


    def tmdb_info(self, i):
        try:
            if self.list[i]['metacache'] == True:
                return
            imdb = self.list[i]['imdb'] if 'imdb' in self.list[i] else '0'
            tmdb = self.list[i]['tmdb'] if 'tmdb' in self.list[i] else '0'
            tvdb = self.list[i]['tvdb'] if 'tvdb' in self.list[i] else '0'
            if tmdb == '0' and not imdb == '0':
                try:
                    temp_item = tmdb_utils.find_tvshow_by_external_source(imdb=imdb)
                    tmdb = temp_item.get('id', '0') or '0'
                except:
                    pass
            if tmdb == '0' and not imdb == '0':
                try:
                    temp_item = trakt.getTVShowSummary(imdb)
                    tmdb = temp_item.get('ids', {}).get('tmdb', '0') or '0'
                except:
                    pass
            if tmdb == '0' and imdb == '0':
                try:
                    temp_item = trakt.SearchTVShow(self.list[i]['title'], self.list[i]['year'])
                    if temp_item[0]['show']['title'].lower() != self.list[i]['title'].lower() or int(temp_item[0]['show']['year']) != int(self.list[i]['year']):
                        raise Exception()
                    imdb = temp_item[0]['show'].get('ids', {}).get('imdb') or '0'
                    tmdb = temp_item[0]['show'].get('ids', {}).get('tmdb') or '0'
                except:
                    pass
            if not tmdb or tmdb == '0':
                raise Exception()
            url = self.tmdb_info_link % tmdb
            item = client.scrapePage(url, timeout='30').json()
            if not item:
                raise Exception()
            if not imdb or imdb == '0':
                imdb = item.get('external_ids', {}).get('imdb_id', '0')
            if not tvdb or tvdb == '0':
                tvdb = item.get('external_ids', {}).get('tvdb_id', '0')
            title = self.list[i].get('title')
            if not title or title == '0':
                title = item.get('name')
            title = client_utils.replaceHTMLCodes(title)
            originaltitle = self.list[i].get('originaltitle')
            if not originaltitle or originaltitle == '0':
                originaltitle = item.get('original_name')
            originaltitle = client_utils.replaceHTMLCodes(originaltitle)
            year = self.list[i].get('year', '0')
            if not year or year == '0':
                year = item.get('first_air_date', '0')
            if year and year != '0':
                year = re.compile(r'(\d{4})').findall(year)[0]
            else:
                year = '0'
            premiered = self.list[i].get('premiered', '0')
            if not premiered or premiered == '0':
                premiered = item.get('first_air_date', '0')
            if premiered and premiered != '0':
                premiered = re.compile(r'(\d{4}-\d{2}-\d{2})').findall(premiered)[0]
            else:
                premiered = '0'
            if self.studio_artwork == 'true':
                studio = item.get('networks', [])
                if studio and studio != []:
                    studio = [x['name'] for x in studio]
                else:
                    studio = []
            else:
                studio = []
            genre = item.get('genres', [])
            if genre and genre != []:
                genre = [x['name'] for x in genre]
                #genre = ' / '.join(genre).strip()
            else:
                genre = []
            try:
                duration = item['episode_run_time'][0]
                duration = str(duration)
            except:
                duration = '0'
            if not duration or duration == '0':
                duration = '0'
            status = item.get('status', '0')
            if not status or status == '0':
                status = '0'
            rating = item.get('vote_average', '0')
            if not rating or rating == '0' or rating == '0.0':
                rating = '0'
            votes = item.get('vote_count', '0')
            #votes = str(format(int(votes), ',d'))
            if not votes or votes == '0':
                votes = '0'
            try:
                mpaa = item['content_ratings']['results']
                mpaa = [x['rating'] for x in mpaa if x['iso_3166_1'] == 'US'][0]
            except:
                mpaa = '0'
            if not mpaa or mpaa == '0':
                mpaa = '0'
            plot = item.get('overview', '0')
            if not plot or plot == '0':
                plot = '0'
            tagline = item.get('tagline', '0')
            if not tagline or tagline == '0':
                tagline = '0'
            castwiththumb = []
            try:
                r_cast = item['credits']['cast'][:30]
                for person in r_cast:
                    _icon = person.get('profile_path')
                    if self.original_artwork == 'true':
                        icon = self.tmdb_image_link + _icon if _icon else ''
                    else:
                        icon = self.tmdb_image_link % ('185', _icon) if _icon else ''
                    castwiththumb.append({'name': person['name'], 'role': person['character'], 'thumbnail': icon})
            except:
                pass
            if not castwiththumb:
                castwiththumb = []
            poster = item.get('poster_path', '')
            if poster and poster != '':
                if self.original_artwork == 'true':
                    poster = self.tmdb_image_link + poster
                else:
                    poster = self.tmdb_image_link % ('500', poster)
            else:
                poster = '0'
            fanart = item.get('backdrop_path', '')
            if fanart and fanart != '':
                if self.original_artwork == 'true':
                    fanart = self.tmdb_image_link + fanart
                else:
                    fanart = self.tmdb_image_link % ('1280', fanart)
            else:
                fanart = '0'
            if self.hq_artwork == 'true':
                poster2, fanart2, banner, clearlogo, clearart, landscape = self.get_fanart_tv_artwork(tvdb)
            else:
                poster2, fanart2, banner = tmdb_utils.get_tmdb_artwork(tmdb, 'tv')
                clearlogo = clearart = landscape = '0'
            if self.info_art_source == '1':
                poster = poster2 if not poster2 == '0' else poster
                fanart = fanart2 if not fanart2 == '0' else fanart
            elif self.info_art_source == '2':
                poster = poster2 if not poster2 == '0' else poster
                fanart = fanart2 if not fanart2 == '0' else fanart
            else:
                poster = poster if not poster == '0' else poster2
                fanart = fanart if not fanart == '0' else fanart2
            item = {'title': title, 'originaltitle': originaltitle, 'year': year, 'premiered': premiered, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'status': status, 'studio': studio,
                'genre': genre, 'duration': duration, 'rating': rating, 'votes': votes, 'mpaa': mpaa, 'plot': plot, 'tagline': tagline, 'castwiththumb': castwiththumb,
                'poster': poster, 'fanart': fanart, 'banner': banner, 'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape
            }
            item = dict((k,v) for k, v in six.iteritems(item) if not v == '0')
            self.list[i].update(item)
            meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'lang': self.lang, 'item': item}
            self.meta.append(meta)
        except:
            #log_utils.log('tmdb_info', 1)
            pass


    def worker(self):
        try:
            self.meta = []
            if self.info_tvshows_source == '1':
                final_info = self.trakt_info
            else:
                final_info = self.tmdb_info
            total = len(self.list)
            for i in range(0, total):
                self.list[i].update({'metacache': False})
            self.list = metacache.fetch(self.list, self.lang)
            for r in range(0, total, 40):
                threads = []
                for i in range(r, r+40):
                    if i < total:
                        threads.append(workers.Thread(final_info, i))
                [i.start() for i in threads]
                [i.join() for i in threads]
            if self.meta:
                metacache.insert(self.meta)
            #self.list = [i for i in self.list]
        except:
            #log_utils.log('worker', 1)
            pass


    def get(self, url, idx=True, create_directory=True):
        try:
            self._list_key = str(url or '')
            if url and str(url).startswith('simkl_'):
                from resources.lib.modules import simkl as simkl_mod
                key = str(url)
                if key.startswith('simkl_trending_'):
                    period = key.replace('simkl_trending_', '') or 'today'
                    self.list = simkl_mod.directory_trending('tv', period)
                else:
                    status = key[6:]
                    self.list = simkl_mod.directory_tvshows(status)
                if idx == True:
                    self.worker()
                if idx == True and create_directory == True:
                    self.tvshowDirectory(self.list)
                return self.list
            if url and str(url).startswith('mdblist_'):
                from resources.lib.modules import mdblist as mdblist_mod
                self.list = mdblist_mod.directory_from_url(url, 'tvshows') or []
                if idx == True:
                    self.worker()
                if idx == True and create_directory == True:
                    self.tvshowDirectory(self.list)
                return self.list
            try:
                url = getattr(self, url + '_link')
            except:
                pass
            try:
                u = urllib_parse.urlparse(url).netloc.lower()
            except:
                pass
            if u in self.tmdb_link and ('/list/' in url or '/collection/' in url):
                if self.addon_caching == 'true':
                    self.list = cache.get(self.tmdb_list, self.addon_caching_timeout, url)
                else:
                    self.list = self.tmdb_list(url)
                if '/list/' in url:
                    self.list = tmdb_utils.apply_my_shelf_sort(self.list, url, 'tvshows')
                else:
                    self.list = sorted(self.list, key=lambda k: k['year'])
                if idx == True:
                    self.worker()
            elif u in self.tmdb_link and self.tmdb_search_link in url:
                if self.addon_caching == 'true':
                    self.list = cache.get(self.tmdb_list, self.addon_caching_timeout, url)
                else:
                    self.list = self.tmdb_list(url)
                if idx == True:
                    self.worker()
            elif u in self.tmdb_link:
                if self.addon_caching == 'true':
                    self.list = cache.get(self.tmdb_list, self.addon_caching_timeout, url)
                else:
                    self.list = self.tmdb_list(url)
                self.list = tmdb_utils.apply_my_shelf_sort(self.list, url, 'tvshows')
                if idx == True:
                    self.worker()
            elif u in self.trakt_link and '/users/' in url:
                try:
                    if url == self.trakt_history_link:
                        raise Exception()
                    if not '/users/me/' in url:
                        raise Exception()
                    self.cacheToDisc = False
                    # Watchlist / Library / Favorites / personal lists change via
                    # Manager — always live-fetch so remove is visible on Refresh.
                    if any(x in url for x in (
                        '/watchlist/', '/collection/', '/favorites/', '/lists/'
                    )):
                        raise Exception()
                    if self.addon_caching != 'true':
                        raise Exception()
                    from resources.lib.modules import trakt_cache
                    self.list = trakt_cache.get(
                        self.trakt_list, trakt_cache.TTL_LISTS_SEC, url, self.trakt_user
                    ) or []
                except:
                    if '/users/me/' in (url or ''):
                        self.cacheToDisc = False
                    self.list = self.trakt_list(url, self.trakt_user)
                self.list = trakt.apply_my_shelf_sort(self.list, url, 'tvshows')
                self.list = trakt.filter_shelf_exclusions(self.list, url)
                if idx == True:
                    self.worker()
            #elif u in self.trakt_link and self.trakt_search_link in url:
                #if self.addon_caching == 'true':
                    #self.list = cache.get(self.trakt_list, self.addon_caching_timeout, url, self.trakt_user)
                #else:
                    #self.list = self.trakt_list(url, self.trakt_user)
                #if idx == True:
                    #self.worker()
            elif u in self.trakt_link:
                if self.addon_caching == 'true':
                    self.list = cache.get(self.trakt_list, self.addon_caching_timeout, url, self.trakt_user)
                else:
                    self.list = self.trakt_list(url, self.trakt_user)
                if idx == True:
                    self.worker()
            elif u in self.tvmaze_link:
                if self.addon_caching == 'true':
                    self.list = cache.get(self.tvmaze_list, self.addon_caching_timeout, url)
                else:
                    self.list = self.tvmaze_list(url)
                if idx == True:
                    self.worker()
            if idx == True and create_directory == True:
                self.tvshowDirectory(self.list)
            return self.list
        except:
            #log_utils.log('get', 1)
            pass


    def tvshowDirectory(self, items):
        sysaddon = sys.argv[0]
        syshandle = int(sys.argv[1])
        items = control.filter_watchlist_unaired(items, getattr(self, '_list_key', ''), self.today_date, media='tvshow')
        if items == None or len(items) == 0:
            control.idle()
            control.content(syshandle, 'tvshows')
            control.directory(syshandle, cacheToDisc=self.cacheToDisc)
            return
        addonPoster, addonBanner = control.addonPoster(), control.addonBanner()
        addonFanart, settingFanart = control.addonFanart(), control.setting('show.fanart')
        traktCredentials = trakt.getTraktCredentialsInfo()
        tmdbCredentials = tmdb_utils.getTMDbCredentialsInfo()
        indicators = playcount.getTVShowIndicators()#refresh=True) if action == 'tvshows' else playcount.getTVShowIndicators()
        from resources.lib.modules import simkl as simkl_mod
        from resources.lib.modules import mdblist as mdblist_mod
        simklCredentials = simkl_mod.getSimklCredentialsInfo()
        mdblistCredentials = mdblist_mod.getMdblistCredentialsInfo()
        _ind = simkl_mod.getIndicatorsProvider()
        if _ind == 'trakt':
            watchedMenu, unwatchedMenu = '[I]Watched in Trakt[/I]', '[I]Unwatched in Trakt[/I]'
        elif _ind == 'simkl':
            watchedMenu, unwatchedMenu = '[I]Watched in Simkl[/I]', '[I]Unwatched in Simkl[/I]'
        elif _ind == 'mdblist':
            watchedMenu, unwatchedMenu = '[I]Watched in MDBList[/I]', '[I]Unwatched in MDBList[/I]'
        else:
            watchedMenu, unwatchedMenu = '[I]Watched in Gratis Red[/I]', '[I]Unwatched in Gratis Red[/I]'
        nextMenu = '[I]Next Page[/I]'
        try:
            favitems = favorites.getFavorites('tvshow')
            favitems = [i[0] for i in favitems]
        except:
            pass
        tv_library = libtools.libtvshows()
        for i in items:
            try:
                label = i['title']
                status = i.get('status', 'N/A')
                try:
                    label = '%s (%s)' % (label, status)
                    premiered = i['premiered']
                    if (premiered == '0' and status in ['Upcoming', 'In Production', 'Planned']) or (int(re.sub(r'[^0-9]', '', premiered)) > int(re.sub(r'[^0-9]', '', str(self.today_date)))):
                        label = '[COLOR %s][I]%s[/I][/COLOR]' % (self.unairedcolor, label)
                except:
                    pass
                poster = i['poster'] if 'poster' in i and not i['poster'] == '0' else addonPoster
                fanart = i['fanart'] if 'fanart' in i and not i['fanart'] == '0' else addonFanart
                banner1 = i.get('banner', '')
                banner = banner1 or fanart or addonBanner
                if 'landscape' in i and not i['landscape'] == '0':
                    landscape = i['landscape']
                else:
                    landscape = fanart
                systitle = sysname = urllib_parse.quote_plus(i['title'])
                sysimage = urllib_parse.quote_plus(poster)
                seasons_meta = {'poster': poster, 'fanart': fanart, 'banner': banner, 'clearlogo': i.get('clearlogo', '0'), 'clearart': i.get('clearart', '0'), 'landscape': landscape}
                seas_meta = urllib_parse.quote_plus(json.dumps(seasons_meta))
                #sysmeta = urllib_parse.quote_plus(json.dumps(seasons_meta)) #Retweaked this bit a bit so fav's would work properly, compare to old versions to see it all.
                imdb, tvdb, tmdb, year = i.get('imdb', ''), i.get('tvdb', ''), i.get('tmdb', ''), i.get('year', '')
                meta = dict((k,v) for k, v in six.iteritems(i) if not v == '0')
                meta.update({'mediatype': 'tvshow'})
                meta.update({'code': tmdb, 'imdbnumber': imdb, 'imdb_id': imdb, 'tmdb_id': tmdb, 'tvdb_id': tvdb})
                meta.update({'tvshowtitle': i['title']})
                meta.update({'trailer': '%s?action=trailer&name=%s&tmdb=%s&imdb=%s' % (sysaddon, systitle, tmdb, imdb)})
                if not 'duration' in i:
                    meta.update({'duration': '60'})
                elif i['duration'] == '0':
                    meta.update({'duration': '60'})
                try:
                    meta.update({'duration': str(int(meta['duration']) * 60)})
                except:
                    pass
                sysmeta = urllib_parse.quote_plus(json.dumps(meta))
                cm = []
                cm.append(('Clean Tools Widget', 'RunPlugin(%s?action=cleantools_widget)' % sysaddon))
                cm.append(('Clear Providers', 'RunPlugin(%s?action=clear_sources)' % sysaddon))
                cm.append(('Find Similar', 'Container.Update(%s?action=tvshows&url=%s)' % (sysaddon, self.trakt_related_link % imdb)))
                cm.append(('Queue Item', 'RunPlugin(%s?action=queue_item)' % sysaddon))
                if simklCredentials == True:
                    cm.append(('Simkl Lists Manager', 'RunPlugin(%s?action=simkl_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, sysname, imdb, tmdb)))
                if mdblistCredentials == True:
                    cm.append(('MDBList Lists Manager', 'RunPlugin(%s?action=mdblist_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, sysname, imdb, tmdb)))
                if tmdbCredentials == True:
                    cm.append(('TMDb Lists Manager', 'RunPlugin(%s?action=tmdb_manager&name=%s&tmdb=%s&content=tvshow)' % (sysaddon, sysname, tmdb)))
                if traktCredentials == True:
                    cm.append(('Trakt Lists Manager', 'RunPlugin(%s?action=trakt_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, sysname, imdb, tmdb)))
                libtools.append_tvshow_library_cm(cm, sysaddon, tv_library, i['title'], year, imdb, tmdb)
                if action == 'tvFavorites':
                    cm.append(('Remove from MyFavorites', 'RunPlugin(%s?action=deleteFavorite&meta=%s&content=tvshow)' % (sysaddon, sysmeta)))
                else:
                    if not imdb in favitems:
                        cm.append(('Add to MyFavorites', 'RunPlugin(%s?action=addFavorite&meta=%s&content=tvshow)' % (sysaddon, sysmeta)))
                    else:
                        cm.append(('Remove from MyFavorites', 'RunPlugin(%s?action=deleteFavorite&meta=%s&content=tvshow)' % (sysaddon, sysmeta)))
                if kodi_version < 17:
                    cm.append(('Information', 'Action(Info)'))
                try:
                    overlay = int(playcount.getTVShowOverlay(indicators, imdb, tmdb))
                    if overlay == 7:
                        cm.append((unwatchedMenu, 'RunPlugin(%s?action=tvshows_playcount&name=%s&imdb=%s&tmdb=%s&query=6)' % (sysaddon, systitle, imdb, tmdb)))
                        meta.update({'playcount': 1, 'overlay': 7})
                    else:
                        cm.append((watchedMenu, 'RunPlugin(%s?action=tvshows_playcount&name=%s&imdb=%s&tmdb=%s&query=7)' % (sysaddon, systitle, imdb, tmdb)))
                        meta.update({'playcount': 0, 'overlay': 6})
                except:
                    pass
                try:
                    item = control.item(label=label, offscreen=True)
                except:
                    item = control.item(label=label)
                art = {}
                art.update({'icon': poster, 'thumb': poster, 'poster': poster, 'tvshow.poster': poster, 'season.poster': poster, 'banner': banner, 'landscape': landscape})
                if settingFanart == 'true':
                    art.update({'fanart': fanart})
                else:
                    art.update({'fanart': addonFanart})
                if 'clearlogo' in i and not i['clearlogo'] == '0':
                    art.update({'clearlogo': i['clearlogo']})
                if 'clearart' in i and not i['clearart'] == '0':
                    art.update({'clearart': i['clearart']})
                item.setArt(art)
                item.addContextMenuItems(cm)
                if kodi_version >= 20:
                    info_tag = ListItemInfoTag(item, 'video')
                castwiththumb = i.get('castwiththumb')
                if castwiththumb and not castwiththumb == '0':
                    if kodi_version >= 18:
                        if kodi_version >= 20:
                            info_tag.set_cast(castwiththumb)
                        else:
                            item.setCast(castwiththumb)
                    else:
                        cast = [(p['name'], p['role']) for p in castwiththumb]
                        meta.update({'cast': cast})
                if kodi_version >= 20:
                    info_tag.set_info(control.metadataClean(meta))
                else:
                    item.setInfo(type='Video', infoLabels=control.metadataClean(meta))
                video_streaminfo = {'codec': 'h264'}
                if kodi_version >= 20:
                    info_tag.add_stream_info('video', video_streaminfo)
                else:
                    item.addStreamInfo('video', video_streaminfo)
                url = '%s?action=seasons&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s&meta=%s' % (sysaddon, systitle, year, imdb, tmdb, seas_meta)
                control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
            except:
                #log_utils.log('tvshowDirectory', 1)
                pass
        try:
            url = items[0]['next']
            if url == '':
                raise Exception()
            icon = control.addonNext()
            url = '%s?action=tvshows&url=%s' % (sysaddon, urllib_parse.quote_plus(url))
            try:
                item = control.item(label=nextMenu, offscreen=True)
            except:
                item = control.item(label=nextMenu)
            item.setArt({'icon': icon, 'thumb': icon, 'poster': icon, 'banner': icon, 'fanart': addonFanart})
            control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
        except:
            pass
        control.content(syshandle, 'tvshows')
        control.directory(syshandle, cacheToDisc=self.cacheToDisc)
        views.setView('tvshows')


    def addDirectory(self, items, queue=False):
        if items == None or len(items) == 0:
            control.idle()
            #sys.exit()
        sysaddon = sys.argv[0]
        syshandle = int(sys.argv[1])
        addonFanart = control.addonFanart()
        for i in items:
            try:
                name = i['name']
                image = i['image']
                url = '%s?action=%s' % (sysaddon, i['action'])
                try:
                    url += '&url=%s' % urllib_parse.quote_plus(i['url'])
                except:
                    pass
                cm = []
                cm.append(('Clean Tools Widget', 'RunPlugin(%s?action=cleantools_widget)' % sysaddon))
                if queue == True:
                    cm.append(('Queue Item', 'RunPlugin(%s?action=queue_item)' % sysaddon))
                try:
                    sort_provider = i.get('sort_provider')
                    sort_key = i.get('sort_key')
                    if sort_provider and sort_key:
                        media = 'movies' if i.get('action') == 'movies' else 'tvshows'
                        action = '%s_list_sort&media=%s&status=%s&label=%s' % (
                            sort_provider, media, sort_key, urllib_parse.quote_plus(name))
                        cm.append(('Set Sort Order', 'RunPlugin(%s?action=%s)' % (sysaddon, action)))
                except Exception:
                    pass
                try:
                    cm.append(('Add to Library', 'RunPlugin(%s?action=tvshows_to_library&url=%s)' % (sysaddon, urllib_parse.quote_plus(i['context']))))
                except:
                    pass
                try:
                    item = control.item(label=name, offscreen=True)
                except:
                    item = control.item(label=name)
                fanart = i['fanart'] if 'fanart' in i and not (i['fanart'] == '0' or i['fanart'] == None) else addonFanart
                control.set_menu_item_art(item, image, fanart=fanart)
                item.addContextMenuItems(cm)
                control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
            except:
                #log_utils.log('addDirectory', 1)
                pass
        from resources.lib.modules import views
        views.endMenuDirectory(syshandle)


