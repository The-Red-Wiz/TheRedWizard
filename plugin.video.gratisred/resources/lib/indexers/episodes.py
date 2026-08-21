# -*- coding: utf-8 -*-

import re
import os
import sys
import datetime

import simplejson as json
import six
from six.moves import range, urllib_parse

try:
    #from infotagger.listitem import ListItemInfoTag
    from resources.lib.modules.listitem import ListItemInfoTag
except:
    pass

from resources.lib.modules import tmdb_utils
from resources.lib.modules import trakt
from resources.lib.modules import bookmarks
from resources.lib.modules import control
from resources.lib.modules import client
from resources.lib.modules import client_utils
from resources.lib.modules import cache
from resources.lib.modules import playcount
from resources.lib.modules import libtools
from resources.lib.modules import workers
from resources.lib.modules import views
#from resources.lib.modules import log_utils

params = dict(urllib_parse.parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()
action = params.get('action')
#control.moderator()
kodi_version = control.getKodiVersion()


class seasons:
    def __init__(self):
        self.list = []
        self.datetime = datetime.datetime.utcnow()
        self.today_date = self.datetime.strftime('%Y-%m-%d')
        self.addon_caching = control.setting('addon.caching') or 'true'
        self.addon_caching_timeout = int(control.setting('addon.caching_timeout')) or int('12')
        self.lang = control.apiLanguage()['tmdb'] or 'en'
        self.specials = control.setting('tv.specials') or 'false'
        self.shownoyear = control.setting('show.noyear') or 'false'
        self.showunaired = control.setting('showunaired') or 'true'
        self.unairedcolor = control.setting('unaired.color') or ''
        if self.unairedcolor == '':
            self.unairedcolor = 'darkred'
        self.tmdb_key = control.setting('tmdb.api') or ''
        if self.tmdb_key == '' or self.tmdb_key == None:
            self.tmdb_key = 'a0bf207c5ff6c0caabac0327e39b1cd2'
        self.tmdb_link = 'https://api.themoviedb.org'
        self.original_artwork = control.setting('original.artwork') or 'false'
        if self.original_artwork == 'true':
            self.tmdb_image_link = 'https://image.tmdb.org/t/p/original'
        else:
            self.tmdb_image_link = 'https://image.tmdb.org/t/p/w%s%s'
        self.tmdb_info_link = self.tmdb_link + '/3/tv/%s?api_key=%s&language=en-US&append_to_response=credits,content_ratings,external_ids' % ('%s', self.tmdb_key)
        self.info_tvshows_source = control.setting('info.tvshows.source') or '0'


    def trakt_info(self, tvshowtitle, year, imdb, tmdb, meta=None, lite=False):
        try:
            tvdb = '0'
            if imdb == '0' and not tmdb == '0':
                try:
                    temp_item = tmdb_utils.get_tvshow_external_ids(tmdb)
                    imdb = temp_item.get('imdb_id', '0') or '0'
                except:
                    pass
            if imdb == '0' and tmdb == '0':
                try:
                    temp_item = trakt.SearchTVShow(tvshowtitle, year)
                    if temp_item[0]['show']['title'].lower() != tvshowtitle.lower() or int(temp_item[0]['show']['year']) != int(year):
                        raise Exception()
                    imdb = temp_item[0]['show']['ids'].get('imdb', '0') or '0'
                    tmdb = temp_item[0]['show']['ids'].get('tmdb', '0') or '0'
                    if tvdb == '0':
                        tvdb = temp_item[0]['show']['ids'].get('tvdb', '0') or '0'
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
            studio = trakt.getStudio(imdb, 'shows')
            if studio and studio != []:
                studio = [x['name'] for x in studio]
            else:
                studio = []
            genre = item.get('genres', [])
            if genre and genre != []:
                genre = [x.title() for x in genre]
                #genre = ' / '.join(genre).strip()
            else:
                genre = []
            duration = item.get('runtime', '0')
            duration = str(duration)
            if not duration or duration == '0':
                duration = '0'
            mpaa = item.get('certification', '0')
            if not mpaa or mpaa == '0':
                mpaa = '0'
            status = item.get('status', '0')
            if not status or status == '0':
                status = '0'
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
            show_plot = item.get('overview', '0')
            if not show_plot or show_plot == '0':
                show_plot = '0'
            else:
                show_plot = client_utils.replaceHTMLCodes(show_plot)
            unaired = ''
            clearlogo = clearart = landscape = '0'
            if meta:
                _meta = json.loads(urllib_parse.unquote_plus(meta))
                show_poster, fanart, banner, clearlogo, clearart, landscape = _meta['poster'], _meta['fanart'], _meta['banner'], _meta['clearlogo'], _meta['clearart'], _meta['landscape']
            else:
                show_poster, fanart, banner = tmdb_utils.get_tmdb_artwork(tmdb, 'tv')
            seasons = trakt.getSeasonsSummary(imdb, full=True)
            if self.specials == 'false':
                seasons = [s for s in seasons if not s['number'] == 0]
            for item in seasons:
                try:
                    season = str(int(item['number']))
                    premiered = item.get('first_aired', '0')
                    if premiered and premiered != '0':
                        premiered = re.compile(r'(\d{4}-\d{2}-\d{2})').findall(premiered)[0]
                    if status == 'Ended':
                        pass
                    elif not premiered or premiered == '0':
                        if self.shownoyear != 'true':
                            raise Exception()
                    elif int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
                        unaired = 'true'
                        if self.showunaired != 'true':
                            raise Exception()
                    plot = item.get('overview', '0')
                    if not plot or plot == '0':
                        plot = show_plot
                    else:
                        plot = client_utils.replaceHTMLCodes(plot)
                    season_poster, season_fanart, season_banner = tmdb_utils.get_tmdb_artwork(tmdb, 'tv', season=season)
                    poster = season_poster if not season_poster == '0' else show_poster
                    fanart = season_fanart if not season_fanart == '0' else fanart
                    banner = season_banner if not season_banner == '0' else banner
                    self.list.append({'season': season, 'tvshowtitle': tvshowtitle, 'year': year, 'premiered': premiered, 'status': status, 'studio': studio, 'genre': genre, 'duration': duration, 'mpaa': mpaa, 'castwiththumb': castwiththumb,
                        'plot': plot, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'poster': poster, 'fanart': fanart, 'banner': banner,'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape, 'unaired': unaired}
                    )
                except:
                    #log_utils.log('trakt_info', 1)
                    pass
        except:
            #log_utils.log('trakt_info', 1)
            pass
        return self.list


    def tmdb_list(self, tvshowtitle, year, imdb, tmdb, meta=None, lite=False):
        try:
            tvdb = '0'
            if tmdb == '0' and not imdb == '0':
                try:
                    temp_item = tmdb_utils.find_tvshow_by_external_source(imdb=imdb)
                    tmdb = temp_item.get('id', '0') or '0'
                except:
                    pass
            if imdb == '0' and tmdb == '0':
                try:
                    temp_item = trakt.SearchTVShow(tvshowtitle, year)
                    if temp_item[0]['show']['title'].lower() != tvshowtitle.lower() or int(temp_item[0]['show']['year']) != int(year):
                        raise Exception()
                    imdb = temp_item[0]['show']['ids'].get('imdb', '0') or '0'
                    tmdb = temp_item[0]['show']['ids'].get('tmdb', '0') or '0'
                    if tvdb == '0':
                        tvdb = temp_item[0]['show']['ids'].get('tvdb', '0') or '0'
                except:
                    pass
            if not tmdb or tmdb == '0':
                raise Exception()
            seasons_url = self.tmdb_info_link % tmdb
            item = client.scrapePage(seasons_url, timeout='30').json()
            if not item:
                raise Exception()
            if not imdb or imdb == '0':
                imdb = item.get('external_ids', {}).get('imdb_id', '0')
            if not tvdb or tvdb == '0':
                tvdb = item.get('external_ids', {}).get('tvdb_id', '0')
            studio = item.get('networks', [])
            if studio and studio != []:
                studio = [x['name'] for x in studio]
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
            try:
                mpaa = item['content_ratings']['results']
                mpaa = [x['rating'] for x in mpaa if x['iso_3166_1'] == 'US'][0]
            except:
                mpaa = '0'
            if not mpaa or mpaa == '0':
                mpaa = '0'
            show_plot = item.get('overview', '0')
            if not show_plot or show_plot == '0':
                show_plot = '0'
            else:
                show_plot = client_utils.replaceHTMLCodes(show_plot)
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
            unaired = ''
            banner = clearlogo = clearart = landscape = '0'
            if meta:
                _meta = json.loads(urllib_parse.unquote_plus(meta))
                show_poster, fanart, banner, clearlogo, clearart, landscape = _meta['poster'], _meta['fanart'], _meta['banner'], _meta['clearlogo'], _meta['clearart'], _meta['landscape']
            else:
                show_poster = item.get('poster_path', '')
                if show_poster and show_poster != '':
                    if self.original_artwork == 'true':
                        show_poster = self.tmdb_image_link + show_poster
                    else:
                        show_poster = self.tmdb_image_link % ('500', show_poster)
                else:
                    show_poster = '0'
                fanart = item.get('backdrop_path', '')
                if fanart and fanart != '':
                    if self.original_artwork == 'true':
                        fanart = self.tmdb_image_link + fanart
                    else:
                        fanart = self.tmdb_image_link % ('1280', fanart)
                else:
                    fanart = '0'
            seasons = item['seasons']
            if self.specials == 'false':
                seasons = [s for s in seasons if not s['season_number'] == 0]
            for item in seasons:
                try:
                    season = str(int(item['season_number']))
                    premiered = item.get('air_date', '0')
                    if status == 'Ended':
                        pass
                    elif not premiered or premiered == '0':
                        if self.shownoyear != 'true':
                            raise Exception()
                    elif int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
                        unaired = 'true'
                        if self.showunaired != 'true':
                            raise Exception()
                    plot = item.get('overview', '0')
                    if not plot or plot == '0':
                        plot = show_plot
                    else:
                        plot = client_utils.replaceHTMLCodes(plot)
                    poster = item.get('poster_path', '')
                    if poster and poster != '':
                        if self.original_artwork == 'true':
                            poster = self.tmdb_image_link + poster
                        else:
                            poster = self.tmdb_image_link % ('500', poster)
                    else:
                        poster = show_poster
                    self.list.append({'season': season, 'tvshowtitle': tvshowtitle, 'year': year, 'premiered': premiered, 'status': status, 'studio': studio, 'genre': genre, 'duration': duration, 'mpaa': mpaa, 'castwiththumb': castwiththumb,
                        'plot': plot, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'poster': poster, 'fanart': fanart, 'banner': banner,'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape, 'unaired': unaired}
                    )
                except:
                    #log_utils.log('tmdb_list', 1)
                    pass
        except:
            #log_utils.log('tmdb_list', 1)
            pass
        return self.list


    def get(self, tvshowtitle, year, imdb, tmdb, meta, idx=True, create_directory=True):
        try:
            if self.info_tvshows_source == '1':
                final_info = self.trakt_info
            else:
                final_info = self.tmdb_list
            if idx == True:
                if self.addon_caching == 'true':
                    self.list = cache.get(final_info, self.addon_caching_timeout, tvshowtitle, year, imdb, tmdb, meta)
                else:
                    self.list = final_info(tvshowtitle, year, imdb, tmdb, meta)
                if create_directory == True:
                    self.seasonDirectory(self.list)
                return self.list
            else:
                self.list = final_info(tvshowtitle, year, imdb, tmdb, lite=True)
                return self.list
        except:
            #log_utils.log('get', 1)
            pass


    def seasonDirectory(self, items):
        sysaddon = sys.argv[0]
        syshandle = int(sys.argv[1])
        if items == None or len(items) == 0:
            control.idle()
            control.content(syshandle, 'seasons')
            control.directory(syshandle, cacheToDisc=False)
            return
        addonPoster = control.addonPoster()
        addonBanner = control.addonBanner()
        addonFanart = control.addonFanart()
        settingFanart = control.setting('show.fanart')
        traktCredentials = trakt.getTraktCredentialsInfo()
        tmdbCredentials = tmdb_utils.getTMDbCredentialsInfo()
        try:
            indicators = playcount.getSeasonIndicators(items[0]['imdb'], items[0].get('tmdb'))
        except:
            pass
        from resources.lib.modules import simkl as simkl_mod
        from resources.lib.modules import mdblist as mdblist_mod
        simklCredentials = simkl_mod.getSimklCredentialsInfo()
        mdblistCredentials = mdblist_mod.getMdblistCredentialsInfo()
        _ind = simkl_mod.getIndicatorsProvider()
        if _ind == 'trakt':
            watchedMenu, unwatchedMenu = 'Watched in Trakt', 'Unwatched in Trakt'
        elif _ind == 'simkl':
            watchedMenu, unwatchedMenu = 'Watched in Simkl', 'Unwatched in Simkl'
        elif _ind == 'mdblist':
            watchedMenu, unwatchedMenu = 'Watched in MDBList', 'Unwatched in MDBList'
        else:
            watchedMenu, unwatchedMenu = 'Watched in Gratis Red', 'Unwatched in Gratis Red'
        tv_library = libtools.libtvshows()
        for i in items:
            try:
                label = 'Season %s' % i['season']
                try:
                    stats = re.findall(r'(\d{4})', i['premiered'])[0]
                except:
                    stats = i['premiered']
                label = '%s (%s)' % (label, stats)
                try:
                    if i['unaired'] == 'true':
                        label = '[COLOR %s][I]%s[/I][/COLOR]' % (self.unairedcolor, label)
                except:
                    pass
                systitle = sysname = urllib_parse.quote_plus(i['tvshowtitle'])
                poster = i['poster'] if 'poster' in i and not i['poster'] == '0' else addonPoster
                fanart = i['fanart'] if 'fanart' in i and not i['fanart'] == '0' else addonFanart
                banner1 = i.get('banner', '')
                banner = banner1 or fanart or addonBanner
                if 'landscape' in i and not i['landscape'] == '0':
                    landscape = i['landscape']
                else:
                    landscape = fanart
                ep_meta = {'poster': poster, 'fanart': fanart, 'banner': banner, 'clearlogo': i.get('clearlogo', '0'), 'clearart': i.get('clearart', '0'), 'landscape': landscape, 'duration': i.get('duration', '45'), 'status': i.get('status', '0')}
                sysmeta = urllib_parse.quote_plus(json.dumps(ep_meta))
                imdb, tvdb, tmdb, year, season, fanart, duration, status = i['imdb'], i['tvdb'], i['tmdb'], i['year'], i['season'], i['fanart'], i['duration'], i['status']
                meta = dict((k,v) for k, v in six.iteritems(i) if not v == '0')
                meta.update({'mediatype': 'season'})
                meta.update({'title': label, 'tvshowtitle': i['tvshowtitle']})
                meta.update({'code': tmdb, 'imdbnumber': imdb, 'imdb_id': imdb, 'tvdb_id': tvdb})
                meta.update({'trailer': '%s?action=trailer&name=%s&tmdb=%s&imdb=%s&season=%s' % (sysaddon, systitle, tmdb, imdb, season)})
                if not 'duration' in i:
                    meta.update({'duration': '60'})
                elif i['duration'] == '0':
                    meta.update({'duration': '60'})
                try:
                    meta.update({'duration': str(int(meta['duration']) * 60)})
                except:
                    pass
                try:
                    seasonYear = i['premiered']
                    seasonYear = re.findall(r'(\d{4})', seasonYear)[0]
                    meta.update({'year': seasonYear})
                except:
                    pass
                cm = []
                cm.append(('Clean Tools Widget', 'RunPlugin(%s?action=cleantools_widget)' % sysaddon))
                cm.append(('Clear Providers', 'RunPlugin(%s?action=clear_sources)' % sysaddon))
                cm.append(('Queue Item', 'RunPlugin(%s?action=queue_item)' % sysaddon))
                if simklCredentials == True:
                    cm.append(('Simkl Lists Manager', 'RunPlugin(%s?action=simkl_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, sysname, imdb, tmdb)))
                if mdblistCredentials == True:
                    cm.append(('MDBList Lists Manager', 'RunPlugin(%s?action=mdblist_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, sysname, imdb, tmdb)))
                if tmdbCredentials == True:
                    cm.append(('TMDb Lists Manager', 'RunPlugin(%s?action=tmdb_manager&name=%s&tmdb=%s&content=tvshow)' % (sysaddon, sysname, tmdb)))
                if traktCredentials == True:
                    cm.append(('Trakt Lists Manager', 'RunPlugin(%s?action=trakt_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, sysname, imdb, tmdb)))
                libtools.append_tvshow_library_cm(cm, sysaddon, tv_library, i['tvshowtitle'], year, imdb, tmdb)
                if kodi_version < 17:
                    cm.append(('Information', 'Action(Info)'))
                try:
                    overlay = int(playcount.getSeasonOverlay(indicators, imdb, season))
                    if overlay == 7:
                        cm.append((unwatchedMenu, 'RunPlugin(%s?action=tvshows_playcount&name=%s&imdb=%s&tmdb=%s&season=%s&query=6)' % (sysaddon, systitle, imdb, tmdb, season)))
                        meta.update({'playcount': 1, 'overlay': 7})
                    else:
                        cm.append((watchedMenu, 'RunPlugin(%s?action=tvshows_playcount&name=%s&imdb=%s&tmdb=%s&season=%s&query=7)' % (sysaddon, systitle, imdb, tmdb, season)))
                        meta.update({'playcount': 0, 'overlay': 6})
                except:
                    pass
                try:
                    item = control.item(label=label, offscreen=True)
                except:
                    item = control.item(label=label)
                art = {}
                art.update({'icon': poster, 'thumb': poster, 'poster': poster, 'banner': banner, 'landscape': landscape})
                if settingFanart == 'true':
                    art.update({'fanart': fanart})
                elif not addonFanart == None:
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
                season_info = control.metadataClean(meta)
                season_info.pop('tvshowtitle', None)
                if kodi_version >= 20:
                    info_tag.set_info(season_info)
                else:
                    item.setInfo(type='Video', infoLabels=season_info)
                video_streaminfo = {'codec': 'h264'}
                if kodi_version >= 20:
                    info_tag.add_stream_info('video', video_streaminfo)
                else:
                    item.addStreamInfo('video', video_streaminfo)
                url = '%s?action=episodes&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&season=%s' % (sysaddon, systitle, year, imdb, tmdb, sysmeta, season)
                control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
            except:
                #log_utils.log('seasonDirectory', 1)
                pass
        try:
            control.property(syshandle, 'showplot', items[0]['plot'])
        except:
            #log_utils.log('seasonDirectory', 1)
            pass
        control.content(syshandle, 'seasons')
        control.directory(syshandle, cacheToDisc=False)
        views.setView('seasons')


class episodes:
    def __init__(self):
        self.list = []
        self.datetime = datetime.datetime.utcnow()
        self.systime = self.datetime.strftime('%Y%m%d%H%M%S%f')
        self.today_date = self.datetime.strftime('%Y-%m-%d')
        self.addon_caching = control.setting('addon.caching') or 'true'
        self.addon_caching_timeout = int(control.setting('addon.caching_timeout')) or int('12')
        self.episode_thumbs = control.setting('episode.thumbs') or 'false'
        self.episode_views = control.setting('episode.views') or 'false'
        self.shownoyear = control.setting('show.noyear') or 'false'
        self.showunaired = control.setting('showunaired') or 'true'
        self.unairedcolor = control.setting('unaired.color') or ''
        if self.unairedcolor == '':
            self.unairedcolor = 'darkred'
        self.specials = control.setting('tv.specials') or 'true'
        self.lang = control.apiLanguage()['tmdb'] or 'en'
        self.hq_artwork = control.setting('fanart.artwork') or 'false'
        self.hq_artwork_size = control.setting('fanart.artwork_size') or 'false'
        self.tmdb_key = control.setting('tmdb.api') or ''
        if self.tmdb_key == '' or self.tmdb_key == None:
            self.tmdb_key = 'a0bf207c5ff6c0caabac0327e39b1cd2'
        self.trakt_user = control.setting('trakt.user').strip()
        self.trakt_item_limit = str(control.setting('trakt.item.limit')) or '100'
        self.fanart_tv_headers = {'api-key': 'cb36b6d02c5a0f8c74f2c836af02793d'}
        self.fanart_tv_user = control.setting('fanart.api') or ''
        if not self.fanart_tv_user == '' or self.fanart_tv_user == None:
            self.fanart_tv_headers.update({'client-key': self.fanart_tv_user})
        self.trakt_link = 'https://api.trakt.tv'
        self.tvmaze_link = 'https://api.tvmaze.com'
        self.tmdb_link = 'https://api.themoviedb.org'
        self.fanart_tv_art_link = 'http://webservice.fanart.tv/tv/%s'
        self.original_artwork = control.setting('original.artwork') or 'false'
        if self.original_artwork == 'true':
            self.tmdb_image_link = 'https://image.tmdb.org/t/p/original'
        else:
            self.tmdb_image_link = 'https://image.tmdb.org/t/p/w%s%s'
        self.info_tvshows_source = control.setting('info.tvshows.source') or '0'

        self.tmdb_season_link = self.tmdb_link + '/3/tv/%s/season/%s?api_key=%s&language=en-US&append_to_response=aggregate_credits' % ('%s', '%s', self.tmdb_key)
        self.tmdb_episode_link = self.tmdb_link + '/3/tv/%s/season/%s/episode/%s?api_key=%s&language=en-US&append_to_response=credits' % ('%s', '%s', '%s', self.tmdb_key)
        self.tmdb_by_query_imdb_link = self.tmdb_link + '/3/find/%s?api_key=%s&external_source=imdb_id' % ('%s', self.tmdb_key)
        self.tmdb_search_link = self.tmdb_link + '/3/search/tv?api_key=%s&language=en-US&query=%s&page=1' % (self.tmdb_key, '%s')

        self.trakt_mycalendar_link = self.trakt_link + '/calendars/my/shows/date[30]/31/' #go back 30 and show all shows aired until tomorrow
        self.trakt_progress_link = self.trakt_link + '/users/me/watched/shows'
        self.trakt_hiddenprogress_link = self.trakt_link + '/users/hidden/progress_watched?limit=1000&type=show'
        self.trakt_history_link = self.trakt_link + '/users/me/history/shows?limit=300' # '40'
        self.trakt_ondeck_link = self.trakt_link + '/sync/playback/episodes?limit=20'
        self.trakt_list_link = self.trakt_link + '/users/%s/lists/%s/items'
        self.trakt_lists_link = self.trakt_link + '/users/me/lists'
        # FIX: see movies.py for full explanation.  Trakt paginates every
        # /users/likes/lists response and silently clamps ``limit`` to the
        # documented maximum of 1000.  The old URL passed ``limit=1000000``
        # and the consumer only read page 1, so any user with more than
        # one page of liked lists lost everything past the first page.
        self.trakt_likedlists_link = self.trakt_link + '/users/likes/lists?limit=1000&page=1'

        self.tvmaze_added_link = self.tvmaze_link + '/schedule'
        self.tvmaze_calendar_link = self.tvmaze_link + '/schedule?date=%s'
        # NEW (1.0.2): premieres + streaming-today endpoints exposed in
        # the rebuilt "Explore TVmaze" menu.  ``calendar()`` recognises
        # the ``tvmaze_link`` host and routes both through ``tvmaze_list``.
        self.tvmaze_streaming_today_link = self.tvmaze_link + '/schedule/web?date=' + self.today_date
        self.tvmaze_premieres_today_link = self.tvmaze_link + '/schedule?country=US&date=' + self.today_date + '&premieres=1'


    def get(self, tvshowtitle, year, imdb, tmdb, meta, season=None, episode=None, idx=True, create_directory=True):
        try:
            if self.info_tvshows_source == '1':
                final_info = self.trakt_info
            else:
                final_info = self.tmdb_list
            if idx == True:
                if season == None or episode == None:
                    if self.addon_caching == 'true':
                        self.list = cache.get(final_info, self.addon_caching_timeout, tvshowtitle, year, imdb, tmdb, season, meta)
                    else:
                        self.list = final_info(tvshowtitle, year, imdb, tmdb, season, meta)
                else:
                    if self.addon_caching == 'true':
                        self.list = cache.get(final_info, self.addon_caching_timeout, tvshowtitle, year, imdb, tmdb, season, meta)
                    else:
                        self.list = final_info(tvshowtitle, year, imdb, tmdb, season, meta)
                    num = [x for x,y in enumerate(self.list) if y['season'] == str(season) and y['episode'] == str(episode)][-1]
                    self.list = [y for x,y in enumerate(self.list) if x >= num]
                if create_directory == True:
                    self.episodeDirectory(self.list)
                return self.list
            else:
                self.list = final_info(tvshowtitle, year, imdb, tmdb, season, lite=True)
                return self.list
        except:
            #log_utils.log('get', 1)
            pass


    def calendar(self, url):
        try:
            if url and str(url).startswith('simkl_'):
                if str(url) == 'simkl_progress':
                    self.list = self.simkl_progress_list()
                elif str(url) == 'simkl_ondeck':
                    self.list = self.simkl_ondeck_list()
                elif str(url) == 'simkl_mycalendar':
                    self.list = self.simkl_calendar_list()
                else:
                    self.list = []
                if not isinstance(self.list, list):
                    self.list = []
                self.episodeDirectory(self.list)
                return self.list
            if url and str(url).startswith('mdblist_'):
                if str(url) == 'mdblist_progress':
                    self.list = self.mdblist_progress_list()
                elif str(url) == 'mdblist_ondeck':
                    self.list = self.mdblist_ondeck_list()
                elif str(url) == 'mdblist_mycalendar':
                    self.list = self.mdblist_calendar_list()
                else:
                    self.list = []
                if not isinstance(self.list, list):
                    self.list = []
                self.episodeDirectory(self.list)
                return self.list
            try:
                url = getattr(self, url + '_link')
            except:
                pass
            if self.trakt_link in url and url == self.trakt_ondeck_link:
                self.blist = []
                if self.addon_caching == 'true':
                    self.blist = cache.get(self.trakt_episodes_list, self.addon_caching_timeout, url, self.trakt_user, self.lang)
                else:
                    self.blist = self.trakt_episodes_list(url, self.trakt_user, self.lang)
                self.list = []
                if self.addon_caching == 'true':
                    self.list = cache.get(self.trakt_episodes_list, self.addon_caching_timeout, url, self.trakt_user, self.lang)
                else:
                    self.list = self.trakt_episodes_list(url, self.trakt_user, self.lang)
                self.list = sorted(self.list, key=lambda k: int(k['paused_at']), reverse=True)
            elif self.trakt_link in url and url == self.trakt_progress_link:
                self.blist = []
                if self.addon_caching == 'true':
                    self.blist = cache.get(self.trakt_progress_list, self.addon_caching_timeout, url, self.trakt_user, self.lang)
                else:
                    self.blist = self.trakt_progress_list(url, self.trakt_user, self.lang)
                self.list = []
                if self.addon_caching == 'true':
                    self.list = cache.get(self.trakt_progress_list, self.addon_caching_timeout, url, self.trakt_user, self.lang)
                else:
                    self.list = self.trakt_progress_list(url, self.trakt_user, self.lang)
            elif self.trakt_link in url and url == self.trakt_mycalendar_link:
                self.blist = []
                if self.addon_caching == 'true':
                    self.blist = cache.get(self.trakt_episodes_list, self.addon_caching_timeout, url, self.trakt_user, self.lang)
                else:
                    self.blist = self.trakt_episodes_list(url, self.trakt_user, self.lang)
                self.list = []
                if self.addon_caching == 'true':
                    self.list = cache.get(self.trakt_episodes_list, self.addon_caching_timeout, url, self.trakt_user, self.lang)
                else:
                    self.list = self.trakt_episodes_list(url, self.trakt_user, self.lang)
                self.list = sorted(self.list, key=lambda k: k['premiered'], reverse=True)
            elif self.trakt_link in url and url == self.trakt_history_link:
                # Live fetch (no 12h cache). One enrichment pass only —
                # calling trakt_episodes_list twice without clearing self.list
                # appended every episode twice ("2 of everything").
                self.blist = []
                self.list = []
                self.list = self.trakt_episodes_list(url, self.trakt_user, self.lang)
                self.list = sorted(self.list, key=lambda k: int(k.get('watched_at') or 0), reverse=True)
            elif self.trakt_link in url and '/users/' in url:
                if self.addon_caching == 'true' and '/users/me/' in url:
                    from resources.lib.modules import trakt_cache
                    self.list = trakt_cache.get(
                        self.trakt_list, trakt_cache.TTL_LISTS_SEC, url, self.trakt_user
                    ) or []
                elif self.addon_caching == 'true':
                    self.list = cache.get(self.trakt_list, self.addon_caching_timeout, url, self.trakt_user)
                else:
                    self.list = self.trakt_list(url, self.trakt_user)
                self.list = self.list[::-1]
            elif self.trakt_link in url:
                if self.addon_caching == 'true':
                    self.list = cache.get(self.trakt_list, self.addon_caching_timeout, url, self.trakt_user)
                else:
                    self.list = self.trakt_list(url, self.trakt_user)
            elif self.tvmaze_link in url and url == self.tvmaze_added_link:
                urls = [i['url'] for i in self.calendars(idx=False)][:5]
                self.list = []
                for url in urls:
                    if self.addon_caching == 'true':
                        chunk = cache.get(self.tvmaze_list, self.addon_caching_timeout, url, True)
                    else:
                        chunk = self.tvmaze_list(url, True)
                    # FIX (v1.0.3): tvmaze_list may return None (legacy)
                    # or a non-iterable from a stale cache entry.  Guard
                    # the accumulator so a single bad day never breaks
                    # the entire "New Episodes (US TV)" directory.
                    if isinstance(chunk, list):
                        self.list += chunk
            elif self.tvmaze_link in url:
                if self.addon_caching == 'true':
                    self.list = cache.get(self.tvmaze_list, self.addon_caching_timeout, url, False)
                else:
                    self.list = self.tvmaze_list(url, False)
                # FIX (v1.0.3): never let self.list be None - downstream
                # episodeDirectory() iterates without a guard.
                if not isinstance(self.list, list):
                    self.list = []
            self.episodeDirectory(self.list)
            return self.list
        except:
            #log_utils.log('calendar', 1)
            pass


    def widget(self):
        if trakt.getTraktIndicatorsInfo() == True:
            setting = control.setting('episode.widget.alt')
        else:
            setting = control.setting('episode.widget')
        if setting == '2':
            self.calendar(self.tvmaze_added_link)
        elif setting == '3':
            self.calendar(self.trakt_progress_link)
        elif setting == '4':
            self.calendar(self.trakt_mycalendar_link)
        else:
            self.calendars()


    def calendars(self, idx=True):
        m = ('January|February|March|April|May|June|July|August|September|October|November|December').split('|')
        try:
            months = [(m[0], 'January'), (m[1], 'February'), (m[2], 'March'), (m[3], 'April'), (m[4], 'May'), (m[5], 'June'), (m[6], 'July'), (m[7], 'August'), (m[8], 'September'), (m[9], 'October'), (m[10], 'November'), (m[11], 'December')]
        except:
            months = []
        d = ('Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday').split('|')
        try:
            days = [(d[0], 'Monday'), (d[1], 'Tuesday'), (d[2], 'Wednesday'), (d[3], 'Thursday'), (d[4], 'Friday'), (d[5], 'Saturday'), (d[6], 'Sunday')]
        except:
            days = []
        for i in range(0, 30):
            try:
                name = (self.datetime - datetime.timedelta(days = i))
                name = ('[B]%s[/B] : %s' % (name.strftime('%A'), six.ensure_str(name.strftime('%d %B'))))
                for m in months:
                    name = name.replace(m[1], m[0])
                for d in days:
                    name = name.replace(d[1], d[0])
                try:
                    name = six.ensure_str(name)
                except:
                    pass
                url = self.tvmaze_calendar_link % (self.datetime - datetime.timedelta(days=int(i))).strftime('%Y-%m-%d')
                self.list.append({'name': name, 'url': url, 'image': 'calendar.png', 'action': 'calendar'})
            except:
                #log_utils.log('calendars', 1)
                pass
        if idx == True:
            self.addDirectory(self.list)
        return self.list


    def userlists(self):
        userlists = []
        try:
            if trakt.getTraktCredentialsInfo() == False:
                raise Exception()
            activity = trakt.getActivity()
            from resources.lib.modules import trakt_cache
            userlists += trakt_cache.get(
                trakt.user_list_directory_episode,
                trakt_cache.TTL_LISTS_SEC,
                self.trakt_lists_link,
                self.trakt_list_link,
                self.trakt_user,
            )
            userlists += trakt_cache.get(
                trakt.user_list_directory_episode,
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
                control.infoDialog('No Trakt episode or TV lists found.', sound=True)
        for i in range(0, len(self.list)):
            if not self.list[i].get('action'):
                self.list[i].update({'action': 'calendar'})
            self.list[i].update({'image': 'userlists.png'})
        self.addDirectory(self.list, queue=True)
        return self.list


    def trakt_list(self, url, user):
        itemlist = []
        try:
            if 'date[' in url:
                for i in re.findall(r'date\[(\d+)\]', url):
                    url = url.replace('date[%s]' % i, (self.datetime - datetime.timedelta(days=int(i))).strftime('%Y-%m-%d'))
            q = dict(urllib_parse.parse_qsl(urllib_parse.urlsplit(url).query))
            q.update({'extended': 'full'})
            q = (urllib_parse.urlencode(q)).replace('%2C', ',')
            u = url.replace('?' + urllib_parse.urlparse(url).query, '') + '?' + q
            items = trakt.getTraktAsJson(u)
            for item in items:
                try:
                    if '/sync/playback' in url and control.playback_progress_stale(item):
                        raise Exception()
                    title = item.get('episode', {}).get('title')
                    if not title:
                        raise Exception()
                    else:
                        title = client_utils.replaceHTMLCodes(title)
                    season = item.get('episode', {}).get('season', '0')
                    if not season or season == '0':
                        raise Exception()
                    else:
                        season = re.sub(r'[^0-9]', '', '%01d' % int(season))
                    episode = item.get('episode', {}).get('number', '0')
                    if not episode or episode == '0':
                        raise Exception()
                    else:
                        episode = re.sub(r'[^0-9]', '', '%01d' % int(episode))
                    tvshowtitle = item.get('show', {}).get('title')
                    if not tvshowtitle:
                        raise Exception()
                    else:
                        tvshowtitle = client_utils.replaceHTMLCodes(tvshowtitle)
                    year = item.get('show', {}).get('year', '0')
                    if not year or year == '0':
                        year = '0'
                    else:
                        year = re.sub(r'[^0-9]', '', str(year))
                    imdb = item['show'].get('ids', {}).get('imdb') or '0'
                    if not imdb or imdb == '0':
                        imdb = '0'
                    else:
                        imdb = 'tt' + re.sub(r'[^0-9]', '', str(imdb))
                    tvdb = item['show'].get('ids', {}).get('tvdb') or '0'
                    if not tvdb or tvdb == '0':
                        tvdb = '0'
                    else:
                        tvdb = re.sub(r'[^0-9]', '', str(tvdb))
                    tmdb = item['show'].get('ids', {}).get('tmdb') or '0'
                    if not tmdb or tmdb == '0':
                        raise Exception()
                    else:
                        tmdb = str(tmdb)
                    premiered = item.get('episode', {}).get('first_aired', '0')
                    if premiered and premiered != '0':
                        premiered = re.compile(r'(\d{4}-\d{2}-\d{2})').findall(premiered)[0]
                    else:
                        premiered = '0'
                    studio = item.get('show', {}).get('network')
                    if studio and studio != []:
                        #studio = [x['name'] for x in studio]#[0]
                        #studio = [x.title() for x in studio]#[0]
                        studio = [studio.title()]#[0] ## Ghetto rig for studio being a single item lol.
                    else:
                        studio = []#'0'
                    genre = item.get('show', {}).get('genres')
                    if genre and genre != []:
                        genre = [i.title() for i in genre]
                    else:
                        genre = []#'0'
                    #genre = ' / '.join(genre)
                    duration = item.get('show', {}).get('runtime', '0')
                    if not duration or duration == '0':
                        duration = '0'
                    else:
                        duration = str(duration)
                    rating = item.get('episode', {}).get('rating', '0')
                    if not rating or rating == '0' or rating == '0.0':
                        rating = '0'
                    else:
                        rating = str(rating)
                    votes = item.get('episode', {}).get('votes', '0')
                    if not votes or votes == '0':
                        votes = '0'
                    else:
                        votes = str(votes)
                    #try:
                        #votes = str(format(int(votes),',d'))
                    #except:
                        #pass
                    #if not votes:
                        #votes = '0'
                    mpaa = item.get('show', {}).get('certification')
                    if not mpaa:
                        mpaa = '0'
                    plot = item.get('episode', {}).get('overview')
                    if not plot:
                        plot = item.get('show', {}).get('overview')
                    if not plot:
                        plot = '0'
                    else:
                        plot = client_utils.replaceHTMLCodes(plot)
                    paused_at = item.get('paused_at', '0') or '0'
                    if paused_at and paused_at != '0':
                        paused_at = re.sub(r'[^0-9]+', '', paused_at)
                    else:
                        paused_at = '0'
                    watched_at = item.get('watched_at', '0') or '0'
                    if watched_at and watched_at != '0':
                        watched_at = re.sub(r'[^0-9]+', '', watched_at)
                    else:
                        watched_at = '0'
                    try:
                        if self.lang == 'en':
                            raise Exception()
                        trans_item = trakt.getTVShowTranslation(imdb, lang=self.lang, season=season, episode=episode, full=True)
                        title = client_utils.replaceHTMLCodes(trans_item.get('title')) or title
                        plot = client_utils.replaceHTMLCodes(trans_item.get('overview')) or plot
                        #tvshowtitle = trakt.getTVShowTranslation(imdb, lang=self.lang) or tvshowtitle
                    except:
                        pass
                    itemlist.append({'title': title, 'season': season, 'episode': episode, 'tvshowtitle': tvshowtitle, 'year': year, 'premiered': premiered, 'status': 'Continuing', 'studio': studio, 'genre': genre,
                        'duration': duration, 'rating': rating, 'votes': votes, 'mpaa': mpaa, 'plot': plot, 'imdb': imdb, 'tvdb': tvdb, 'tmdb': tmdb, 'poster': '0', 'thumb': '0', 'paused_at': paused_at, 'watched_at': watched_at}
                    )
                except:
                    #log_utils.log('trakt_list', 1)
                    pass
        except:
            #log_utils.log('trakt_list', 1)
            pass
        # FIX (Trakt history only shows old stuff):
        # The blanket ``[::-1]`` reverse below flips Trakt's newest-first
        # ordering into oldest-first.  Downstream, ``trakt_episodes_list``
        # truncates with ``items[:100]`` which then keeps the OLDEST 100
        # of the 300 fetched (``/users/me/history/shows?limit=300``) -
        # so the History view literally never showed any recent watches.
        # We now keep Trakt's natural order for the history endpoint
        # (newest first) and only apply the legacy reverse for the
        # non-history callers that expect it (user lists / calendars,
        # which are re-reversed or re-sorted by their own callers).
        if '/history/' not in url:
            itemlist = itemlist[::-1]
        return itemlist


### Recode Stopped Here...
    def trakt_progress_list(self, url, user, lang):
        try:
            url += '?extended=full'
            result = trakt.getTraktAsJson(url)
        except:
            #log_utils.log('trakt_progress_list', 1)
            return
        items = []
        sortorder = control.setting('prgr.sortorder')
        for item in result:
            try:
                num_1 = 0
                for i in range(0, len(item['seasons'])):
                    if item['seasons'][i]['number'] > 0:
                        num_1 += len(item['seasons'][i]['episodes'])
                num_2 = int(item['show']['aired_episodes'])
                if num_1 >= num_2:
                    raise Exception()
                season = str(item['seasons'][-1]['number'])
                episode = [x for x in item['seasons'][-1]['episodes'] if 'number' in x]
                episode = sorted(episode, key=lambda x: x['number'])
                episode = str(episode[-1]['number'])
                tvshowtitle = item.get('show', {}).get('title')
                if not tvshowtitle:
                    raise Exception()
                else:
                    tvshowtitle = client_utils.replaceHTMLCodes(tvshowtitle)
                year = item.get('show', {}).get('year', '0')
                if not year or year == '0':
                    year = '0'
                else:
                    year = re.sub(r'[^0-9]', '', str(year))
                if int(year) > int(self.datetime.strftime('%Y')):
                    if self.shownoyear != 'true':
                        raise Exception()
                imdb = item['show'].get('ids', {}).get('imdb') or '0'
                if not imdb or imdb == '0':
                    imdb = '0'
                else:
                    imdb = 'tt' + re.sub(r'[^0-9]', '', str(imdb))
                tvdb = item['show'].get('ids', {}).get('tvdb') or '0'
                if not tvdb or tvdb == '0':
                    tvdb == '0'
                else:
                    tvdb = re.sub(r'[^0-9]', '', str(tvdb))
                tmdb = item['show'].get('ids', {}).get('tmdb') or '0'
                if not tvdb or tvdb == '0':
                    tmdb = '0'
                else:
                    tmdb = str(tmdb)
                studio = item.get('show', {}).get('network')
                if studio and studio != []:
                    #studio = [x['name'] for x in studio]#[0]
                    #studio = [x.title() for x in studio]#[0]
                    studio = [studio.title()]#[0] ## Ghetto rig for studio being a single item lol.
                else:
                    studio = []#'0'
                duration = item.get('show', {}).get('runtime', '0')
                if not duration or duration == '0':
                    duration = '0'
                else:
                    duration = str(duration)
                mpaa = item.get('show', {}).get('certification')
                if not mpaa:
                    mpaa = '0'
                status = item.get('show', {}).get('status')
                if not status:
                    status = '0'
                genre = item.get('show', {}).get('genres')
                if genre and genre != []:
                    genre = [i.title() for i in genre]
                else:
                    genre = []#'0'
                #genre = ' / '.join(genre)
                last_watched = item.get('last_watched_at', '0') or '0'
                if last_watched and last_watched != '0':
                    last_watched = re.sub(r'[^0-9]+', '', last_watched)
                else:
                    last_watched = '0'
                items.append({'imdb': imdb, 'tvdb': tvdb, 'tmdb': tmdb, 'tvshowtitle': tvshowtitle, 'year': year, 'studio': studio, 'duration': duration, 'mpaa': mpaa,
                    'status': status, 'genre': genre, 'snum': season, 'enum': episode, '_last_watched': last_watched}
                )
            except:
                #log_utils.log('trakt_progress_list', 1)
                pass
        try:
            result = trakt.getTraktAsJson(self.trakt_hiddenprogress_link)
            result = [str(i['show']['ids']['tmdb']) for i in result]
            items = [i for i in items if not i['tmdb'] in result]
        except:
            #log_utils.log('trakt_progress_list', 1)
            pass
        def items_list(i):
            tmdb, imdb, tvdb = i['tmdb'], i['imdb'], i['tvdb']
            if (not tmdb or tmdb == '0') and not imdb == '0':
                try:
                    url = self.tmdb_by_query_imdb_link % imdb
                    result = client.scrapePage(url, timeout='30').json()
                    id = result.get('tv_results', [])[0]
                    tmdb = id.get('id')
                    if not tmdb:
                        tmdb = '0'
                    else:
                        tmdb = str(tmdb)
                except:
                    #log_utils.log('trakt_progress_list', 1)
                    pass
            try:
                item = [x for x in self.blist if x['tmdb'] == tmdb and x['snum'] == i['snum'] and x['enum'] == i['enum']][0]
                item['action'] = 'episodes'
                self.list.append(item)
                return
            except:
                #log_utils.log('trakt_progress_list', 1)
                pass
            try:
                if tmdb == '0':
                    raise Exception()
                _episode = str(int(i['enum']) + 1)
                _season = str(int(i['snum']) + 1)
                url = self.tmdb_episode_link % (tmdb, i['snum'], _episode)
                item = client.scrapePage(url, timeout='30').json()
                if item.get('status_code') == 34:
                    url2 = self.tmdb_episode_link % (tmdb, _season, '1')
                    item = client.scrapePage(url2, timeout='30').json()
                try:
                    premiered = item.get('air_date')
                except:
                    premiered = ''
                if not premiered:
                    premiered = '0'
                unaired = ''
                if i['status'] == 'Ended':
                    pass
                elif premiered == '0':
                    if self.shownoyear != 'true':
                        raise Exception()
                elif int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
                    unaired = 'true'
                    if self.showunaired != 'true':
                        raise Exception()
                title = item.get('name')
                if not title:
                    title = '0'
                else:
                    title = client_utils.replaceHTMLCodes(title)
                season = item.get('season_number', i['snum']) ## Added i['snum'] to counter a odd error, think it works out lol.
                season = '%01d' % int(season)
                #if int(season) == 0:# and self.specials != 'true':
                    #raise Exception()
                episode = item.get('episode_number', i['enum']) ## Added i['enum'] to counter a odd error, think it works out lol.
                episode = '%01d' % int(episode)
                tvshowtitle = i['tvshowtitle']
                year = i['year']
                try:
                    thumb = item.get('still_path')
                except:
                    thumb = ''
                if not (thumb == '' or thumb == None):
                    if self.original_artwork == 'true':
                        thumb = self.tmdb_image_link + thumb
                    else:
                        thumb = self.tmdb_image_link % ('300', thumb)
                else:
                    thumb = '0'
                try:
                    rating = str(item['vote_average'])
                except:
                    rating = ''
                if not rating:
                    rating = '0'
                try:
                    votes = str(item['vote_count'])
                except:
                    votes = ''
                if not votes:
                    votes = '0'
                try:
                    plot = item.get('overview')
                except:
                    plot = ''
                if not plot:
                    plot = '0'
                else:
                    plot = client_utils.replaceHTMLCodes(plot)
                try:
                    r_crew = item['crew']
                    director = [d['name'] for d in r_crew if d['job'] == 'Director']
                    #director = ', '.join([d['name'] for d in director])
                    if not director:
                        director = []#'0'
                    writer = [w['name'] for w in r_crew if w['job'] == 'Writer']
                    #writer = ', '.join([w['name'] for w in writer])
                    if not writer:
                        writer = []#'0'
                except:
                    director = []#''
                    writer = []#''
                castwiththumb = []
                try:
                    r_cast = item['credits']['cast'][:30]
                    for person in r_cast:
                        _icon = person['profile_path']
                        if self.original_artwork == 'true':
                            icon = self.tmdb_image_link + _icon if _icon else ''
                        else:
                            icon = self.tmdb_image_link % ('185', _icon) if _icon else ''
                        castwiththumb.append({'name': person['name'], 'role': person['character'], 'thumbnail': icon})
                except:
                    pass
                if not castwiththumb:
                    castwiththumb = '0'
                poster = fanart = banner = landscape = clearlogo = clearart = '0'
                if not tvdb == '0':
                    poster, fanart, banner, clearlogo, clearart, landscape = self.get_fanart_tv_artwork(tvdb)
                self.list.append({'title': title, 'season': season, 'episode': episode, 'tvshowtitle': tvshowtitle, 'year': year, 'premiered': premiered, 'studio': i.get('studio'), 'genre': i.get('genre'), 'status': i.get('status'),
                    'duration': i.get('duration'), 'rating': rating, 'votes': votes, 'mpaa': i.get('mpaa'), 'director': director, 'writer': writer, 'castwiththumb': castwiththumb, 'plot': plot,
                    'poster': poster, 'banner': banner, 'fanart': fanart, 'thumb': thumb, 'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape, 'snum': i['snum'], 'enum': i['enum'], 'action': 'episodes',
                    'unaired': unaired, '_last_watched': i['_last_watched'], 'imdb': imdb, 'tvdb': tvdb, 'tmdb': tmdb, '_sort_key': max(i['_last_watched'],premiered)}
                )
            except:
                #log_utils.log('trakt_progress_list', 1)
                pass
        try:
            if self.trakt_item_limit == '50':
                items = items[:50]
            elif self.trakt_item_limit == '150':
                items = items[:150]
            else:
                items = items[:100]
            threads = []
            for i in items:
                threads.append(workers.Thread(items_list, i))
            [i.start() for i in threads]
            [i.join() for i in threads]
            if sortorder == '0':
                self.list = sorted(self.list, key=lambda k: k['premiered'], reverse=True)
            else:
                self.list = sorted(self.list, key=lambda k: k['_sort_key'], reverse=True)
        except:
            #log_utils.log('trakt_progress_list', 1)
            pass
        return self.list


    def simkl_calendar_list(self):
        """Upcoming episodes for the user's Simkl shelves (CDN calendar filtered)."""
        from resources.lib.modules import simkl as simkl_mod
        try:
            items = simkl_mod.calendar_episode_items(mine_only=True)
        except Exception:
            return []
        return self._enrich_calendar_tips(items)


    def mdblist_calendar_list(self):
        from resources.lib.modules import mdblist as mdblist_mod
        try:
            items = mdblist_mod.calendar_episode_items()
        except Exception:
            return []
        return self._enrich_calendar_tips(items)


    def _enrich_calendar_tips(self, items):
        self.list = []

        def items_list(i):
            tmdb, imdb, tvdb = i.get('tmdb', '0'), i.get('imdb', '0'), i.get('tvdb', '0')
            if (not tmdb or tmdb == '0') and imdb and imdb != '0':
                try:
                    url = self.tmdb_by_query_imdb_link % imdb
                    result = client.scrapePage(url, timeout='30').json()
                    id = result.get('tv_results', [])[0]
                    tmdb = str(id.get('id') or '0')
                except Exception:
                    pass
            try:
                if tmdb == '0':
                    raise Exception()
                url = self.tmdb_episode_link % (tmdb, i['season'], i['episode'])
                item = client.scrapePage(url, timeout='30').json()
                if item.get('status_code') == 34:
                    # Fall back to calendar tip without full TMDb meta.
                    self.list.append(dict(i, tmdb=tmdb))
                    return
                title = client_utils.replaceHTMLCodes(item.get('name') or i.get('title') or '0')
                season = '%01d' % int(item.get('season_number', i['season']))
                episode = '%01d' % int(item.get('episode_number', i['episode']))
                premiered = item.get('air_date') or i.get('premiered') or '0'
                try:
                    thumb = item.get('still_path') or ''
                except Exception:
                    thumb = ''
                if thumb:
                    if self.original_artwork == 'true':
                        thumb = self.tmdb_image_link + thumb
                    else:
                        thumb = self.tmdb_image_link % ('300', thumb)
                else:
                    thumb = '0'
                try:
                    plot = client_utils.replaceHTMLCodes(item.get('overview') or '0')
                except Exception:
                    plot = '0'
                try:
                    rating = str(item.get('vote_average') or '0')
                except Exception:
                    rating = '0'
                poster = fanart = banner = landscape = clearlogo = clearart = '0'
                if tvdb and tvdb != '0':
                    poster, fanart, banner, clearlogo, clearart, landscape = self.get_fanart_tv_artwork(tvdb)
                unaired = ''
                try:
                    if premiered and premiered != '0':
                        if int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
                            unaired = 'true'
                except Exception:
                    pass
                self.list.append({
                    'title': title, 'season': season, 'episode': episode,
                    'tvshowtitle': i.get('tvshowtitle'), 'year': i.get('year', '0'),
                    'premiered': premiered, 'studio': i.get('studio') or [], 'genre': i.get('genre') or [],
                    'status': i.get('status') or '0', 'duration': i.get('duration') or '0',
                    'rating': rating, 'votes': '0', 'mpaa': i.get('mpaa') or '0',
                    'director': [], 'writer': [], 'castwiththumb': '0', 'plot': plot,
                    'poster': poster, 'banner': banner, 'fanart': fanart, 'thumb': thumb,
                    'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape,
                    'imdb': imdb, 'tvdb': tvdb, 'tmdb': tmdb, 'unaired': unaired,
                    'paused_at': '0', 'watched_at': '0',
                })
            except Exception:
                pass

        try:
            threads = []
            for i in items:
                threads.append(workers.Thread(items_list, i))
            [i.start() for i in threads]
            [i.join() for i in threads]
            self.list = sorted(self.list, key=lambda k: k.get('premiered') or '', reverse=True)
        except Exception:
            pass
        return self.list


    def simkl_progress_list(self):
        """Continue Watching for Simkl — next episode after last watched tip."""
        from resources.lib.modules import simkl as simkl_mod
        try:
            items = simkl_mod.progress_seeds()
        except Exception:
            return []
        return self._cloud_progress_list(items)


    def mdblist_progress_list(self):
        from resources.lib.modules import mdblist as mdblist_mod
        try:
            items = mdblist_mod.progress_seeds()
        except Exception:
            return []
        return self._cloud_progress_list(items)


    def _cloud_progress_list(self, items):
        self.list = []
        sortorder = control.setting('prgr.sortorder')

        def items_list(i):
            tmdb, imdb, tvdb = i['tmdb'], i['imdb'], i['tvdb']
            if (not tmdb or tmdb == '0') and not imdb == '0':
                try:
                    url = self.tmdb_by_query_imdb_link % imdb
                    result = client.scrapePage(url, timeout='30').json()
                    id = result.get('tv_results', [])[0]
                    tmdb = id.get('id')
                    if not tmdb:
                        tmdb = '0'
                    else:
                        tmdb = str(tmdb)
                except Exception:
                    pass
            try:
                if tmdb == '0':
                    raise Exception()
                _episode = str(int(i['enum']) + 1)
                _season = str(int(i['snum']) + 1)
                url = self.tmdb_episode_link % (tmdb, i['snum'], _episode)
                item = client.scrapePage(url, timeout='30').json()
                if item.get('status_code') == 34:
                    url2 = self.tmdb_episode_link % (tmdb, _season, '1')
                    item = client.scrapePage(url2, timeout='30').json()
                    if item.get('status_code') == 34:
                        raise Exception()
                try:
                    premiered = item.get('air_date') or '0'
                except Exception:
                    premiered = '0'
                if not premiered:
                    premiered = '0'
                unaired = ''
                if i.get('status') == 'Ended':
                    pass
                elif premiered == '0':
                    if self.shownoyear != 'true':
                        raise Exception()
                elif int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
                    unaired = 'true'
                    if self.showunaired != 'true':
                        raise Exception()
                title = item.get('name') or '0'
                title = client_utils.replaceHTMLCodes(title)
                season = '%01d' % int(item.get('season_number', i['snum']))
                episode = '%01d' % int(item.get('episode_number', i['enum']))
                try:
                    thumb = item.get('still_path') or ''
                except Exception:
                    thumb = ''
                if thumb:
                    if self.original_artwork == 'true':
                        thumb = self.tmdb_image_link + thumb
                    else:
                        thumb = self.tmdb_image_link % ('300', thumb)
                else:
                    thumb = '0'
                try:
                    rating = str(item.get('vote_average') or '0')
                except Exception:
                    rating = '0'
                try:
                    votes = str(item.get('vote_count') or '0')
                except Exception:
                    votes = '0'
                try:
                    plot = client_utils.replaceHTMLCodes(item.get('overview') or '0')
                except Exception:
                    plot = '0'
                poster = fanart = banner = landscape = clearlogo = clearart = '0'
                if not tvdb == '0':
                    poster, fanart, banner, clearlogo, clearart, landscape = self.get_fanart_tv_artwork(tvdb)
                last_watched = i.get('_last_watched', '0') or '0'
                self.list.append({
                    'title': title, 'season': season, 'episode': episode,
                    'tvshowtitle': i['tvshowtitle'], 'year': i.get('year', '0'),
                    'premiered': premiered, 'studio': i.get('studio'), 'genre': i.get('genre'),
                    'status': i.get('status'), 'duration': i.get('duration'), 'rating': rating,
                    'votes': votes, 'mpaa': i.get('mpaa'), 'director': [], 'writer': [],
                    'castwiththumb': '0', 'plot': plot, 'poster': poster, 'banner': banner,
                    'fanart': fanart, 'thumb': thumb, 'clearlogo': clearlogo, 'clearart': clearart,
                    'landscape': landscape, 'snum': i['snum'], 'enum': i['enum'], 'action': 'episodes',
                    'unaired': unaired, '_last_watched': last_watched, 'imdb': imdb, 'tvdb': tvdb,
                    'tmdb': tmdb, '_sort_key': max(last_watched, premiered),
                })
            except Exception:
                pass

        try:
            threads = []
            for i in items:
                threads.append(workers.Thread(items_list, i))
            [i.start() for i in threads]
            [i.join() for i in threads]
            if sortorder == '0':
                self.list = sorted(self.list, key=lambda k: k.get('premiered') or '', reverse=True)
            else:
                self.list = sorted(self.list, key=lambda k: k.get('_sort_key') or '', reverse=True)
        except Exception:
            pass
        return self.list


    def simkl_ondeck_list(self):
        """In Progress Episodes from Simkl /sync/playback."""
        from resources.lib.modules import simkl as simkl_mod
        try:
            items = simkl_mod.playback_episode_items()
        except Exception:
            return []
        return self._playback_episode_list(items)


    def mdblist_ondeck_list(self):
        from resources.lib.modules import mdblist as mdblist_mod
        try:
            items = mdblist_mod.playback_episode_items()
        except Exception:
            return []
        return self._playback_episode_list(items)


    def _playback_episode_list(self, items):
        self.list = []

        def items_list(i):
            tmdb, imdb, tvdb = i.get('tmdb', '0'), i.get('imdb', '0'), i.get('tvdb', '0')
            if (not tmdb or tmdb == '0') and imdb and imdb != '0':
                try:
                    url = self.tmdb_by_query_imdb_link % imdb
                    result = client.scrapePage(url, timeout='30').json()
                    id = result.get('tv_results', [])[0]
                    tmdb = str(id.get('id') or '0')
                except Exception:
                    pass
            try:
                if tmdb == '0' or i.get('season') == '0':
                    raise Exception()
                url = self.tmdb_episode_link % (tmdb, i['season'], i['episode'])
                item = client.scrapePage(url, timeout='30').json()
                if item.get('status_code') == 34:
                    raise Exception()
                title = client_utils.replaceHTMLCodes(item.get('name') or i.get('title') or '0')
                season = '%01d' % int(item.get('season_number', i['season']))
                episode = '%01d' % int(item.get('episode_number', i['episode']))
                premiered = item.get('air_date') or '0'
                try:
                    thumb = item.get('still_path') or ''
                except Exception:
                    thumb = ''
                if thumb:
                    if self.original_artwork == 'true':
                        thumb = self.tmdb_image_link + thumb
                    else:
                        thumb = self.tmdb_image_link % ('300', thumb)
                else:
                    thumb = '0'
                try:
                    plot = client_utils.replaceHTMLCodes(item.get('overview') or '0')
                except Exception:
                    plot = '0'
                try:
                    rating = str(item.get('vote_average') or '0')
                except Exception:
                    rating = '0'
                poster = fanart = banner = landscape = clearlogo = clearart = '0'
                if tvdb and tvdb != '0':
                    poster, fanart, banner, clearlogo, clearart, landscape = self.get_fanart_tv_artwork(tvdb)
                self.list.append({
                    'title': title, 'season': season, 'episode': episode,
                    'tvshowtitle': i.get('tvshowtitle'), 'year': i.get('year', '0'),
                    'premiered': premiered, 'studio': i.get('studio') or [], 'genre': i.get('genre') or [],
                    'status': i.get('status') or '0', 'duration': i.get('duration') or '0',
                    'rating': rating, 'votes': '0', 'mpaa': i.get('mpaa') or '0',
                    'director': [], 'writer': [], 'castwiththumb': '0', 'plot': plot,
                    'poster': poster, 'banner': banner, 'fanart': fanart, 'thumb': thumb,
                    'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape,
                    'imdb': imdb, 'tvdb': tvdb, 'tmdb': tmdb,
                    'paused_at': i.get('paused_at') or '0', 'watched_at': '0',
                })
            except Exception:
                pass

        try:
            threads = []
            for i in items:
                threads.append(workers.Thread(items_list, i))
            [i.start() for i in threads]
            [i.join() for i in threads]
            self.list = sorted(self.list, key=lambda k: int(k.get('paused_at') or 0), reverse=True)
        except Exception:
            pass
        return self.list


    def trakt_episodes_list(self, url, user, lang):
        items = self.trakt_list(url, user)
        self.list = []
        def items_list(i):
            tmdb, imdb, tvdb = i['tmdb'], i['imdb'], i['tvdb']
            if (not tmdb or tmdb == '0') and not imdb == '0':
                try:
                    url = self.tmdb_by_query_imdb_link % imdb
                    result = client.scrapePage(url, timeout='30').json()
                    id = result.get('tv_results', [])[0]
                    tmdb = id.get('id')
                    if not tmdb:
                        tmdb = '0'
                    else:
                        tmdb = str(tmdb)
                except:
                    #log_utils.log('trakt_episodes_list', 1)
                    pass
            try:
                item = [x for x in self.blist if x['tmdb'] == tmdb and x['season'] == i['season'] and x['episode'] == i['episode']][0]
                if item['poster'] == '0':
                    raise Exception()
                self.list.append(item)
                return
            except:
                #log_utils.log('trakt_episodes_list', 1)
                pass
            try:
                if tmdb == '0':
                    raise Exception()
                if i['season'] == '0':
                    raise Exception()
                url = self.tmdb_episode_link % (tmdb, i['season'], i['episode'])
                item = client.scrapePage(url, timeout='30').json()
                title = item['name']
                if not title:
                    title = '0'
                else:
                    title = client_utils.replaceHTMLCodes(title)
                season = item['season_number']
                season = '%01d' % season
                #if int(season) == 0:# and self.specials != 'true':
                    #raise Exception()
                episode = item['episode_number']
                episode = '%01d' % episode
                tvshowtitle = i['tvshowtitle']
                premiered = i['premiered']
                status, duration, mpaa, studio, genre, year = i['status'], i['duration'], i['mpaa'], i['studio'], i['genre'], i['year']
                rating, votes = i['rating'], i['votes']
                try:
                    thumb = item['still_path']
                except:
                    thumb = ''
                if not (thumb == '' or thumb == None):
                    if self.original_artwork == 'true':
                        thumb = self.tmdb_image_link + item['still_path']
                    else:
                        thumb = self.tmdb_image_link % ('300', thumb)
                else:
                    thumb = '0'
                try:
                    plot = item['overview']
                except:
                    plot = ''
                if not plot:
                    plot = i['plot']
                else:
                    plot = client_utils.replaceHTMLCodes(plot)
                try:
                    r_crew = item['crew']
                    director = [d['name'] for d in r_crew if d['job'] == 'Director']
                    #director = ', '.join([d['name'] for d in director])
                    writer = [w['name'] for w in r_crew if w['job'] == 'Writer']
                    #writer = ', '.join([w['name'] for w in writer])
                except:
                    director = writer = []#''
                if not director:
                    director = []#'0'
                if not writer:
                    writer = []#'0'
                castwiththumb = []
                try:
                    r_cast = item['credits']['cast'][:30]
                    for person in r_cast:
                        _icon = person['profile_path']
                        if self.original_artwork == 'true':
                            icon = self.tmdb_image_link + _icon if _icon else ''
                        else:
                            icon = self.tmdb_image_link % ('185', _icon) if _icon else ''
                        castwiththumb.append({'name': person['name'], 'role': person['character'], 'thumbnail': icon})
                except:
                    pass
                if not castwiththumb:
                    castwiththumb = '0'
                paused_at = i.get('paused_at', '0') or '0'
                watched_at = i.get('watched_at', '0') or '0'
                poster = fanart = banner = landscape = clearlogo = clearart = '0'
                if not tvdb == '0':
                    poster, fanart, banner, clearlogo, clearart, landscape = self.get_fanart_tv_artwork(tvdb)
                self.list.append({'title': title, 'season': season, 'episode': episode, 'tvshowtitle': tvshowtitle, 'year': year, 'premiered': premiered, 'status': status, 'studio': studio, 'genre': genre,
                    'duration': duration, 'rating': rating, 'votes': votes, 'mpaa': mpaa, 'director': director, 'writer': writer, 'castwiththumb': castwiththumb, 'plot': plot,
                    'imdb': imdb, 'tvdb': tvdb, 'tmdb': tmdb, 'poster': poster, 'banner': banner, 'fanart': fanart, 'thumb': thumb, 'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape,
                    'paused_at': paused_at, 'watched_at': watched_at}
                )
            except:
                #log_utils.log('trakt_episodes_list', 1)
                pass
        if self.trakt_item_limit == '50':
            items = items[:50]
        elif self.trakt_item_limit == '150':
            items = items[:150]
        else:
            items = items[:100]
        threads = []
        for i in items:
            threads.append(workers.Thread(items_list, i))
        [i.start() for i in threads]
        [i.join() for i in threads]
        return self.list


    def trakt_user_list(self, url, user):
        # FIX (two bugs):
        #   1. ``items`` was being populated inside the ``try`` block but
        #      the ``for item in items`` loop that used it lived *outside*
        #      the try.  Any network / 5xx error in ``getTraktAsJson``
        #      left ``items`` undefined and the whole episodes-calendar
        #      directory raised ``UnboundLocalError`` – the user saw no
        #      Trakt lists at all.
        #   2. ``getTraktAsJson`` only ever fetched page 1, so large
        #      accounts (>1 page of personal or liked lists) had the rest
        #      silently dropped.  Using ``getTraktAsJsonPaged`` walks the
        #      ``X-Pagination-Page-Count`` header and returns every page.
        items = []
        try:
            items = trakt.getTraktAsJsonPaged(url) or []
        except:
            #log_utils.log('trakt_user_list', 1)
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
                self.list.append({'name': name, 'url': url, 'context': url})
            except:
                #log_utils.log('trakt_user_list', 1)
                pass
        self.list = sorted(self.list, key=lambda k: k['name'])
        return self.list


    def tvmaze_list(self, url, limit):
        itemlist = []
        try:
            # ``&premieres=1`` is an addon-side flag, NOT a TVmaze param.
            # Strip it before the request so the API still returns data,
            # but remember to filter premieres only on the way back.
            premieres_only = '&premieres=1' in url or '?premieres=1' in url
            req_url = url.replace('&premieres=1', '').replace('?premieres=1', '?').replace('?&', '?').rstrip('?')
            if not req_url.endswith('/schedule') and req_url.endswith('/'):
                req_url = req_url[:-1]
            items = client.scrapePage(req_url, timeout='30').json()
        except:
            # FIX (v1.0.3): always return a *list*, never None.  The old
            # bare ``return`` caused ``self.list += tvmaze_list(...)`` in
            # calendar() to crash with TypeError, which Kodi then logged
            # as "Error getting plugin://..." for New Episodes (US TV).
            #log_utils.log('tvmaze_list', 1)
            return []
        # FIX (v1.0.3): TVmaze occasionally responds with a dict (error
        # payload) or None.  Guard the iteration so we still return [].
        if not isinstance(items, list):
            return []
        # FIX (v1.0.3): "Premiering Today (US TV)" - on most days TVmaze
        # has zero S1E1 episodes scheduled, so filtering client-side on
        # ``?premieres=1`` returned an empty directory and the menu
        # appeared "broken".  When the user explicitly asked for
        # premieres and the requested day has none, widen the search to
        # the next 14 days so the section is always populated.
        if premieres_only:
            try:
                widened = []
                seen_dates = set()
                base = req_url.split('?')[0]
                from six.moves.urllib_parse import urlparse, parse_qs
                qs = parse_qs(urlparse(req_url).query)
                country = (qs.get('country') or ['US'])[0]
                start_date = (qs.get('date') or [self.today_date])[0]
                try:
                    start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d')
                except Exception:
                    start_dt = self.datetime
                for offset in range(0, 14):
                    d = (start_dt + datetime.timedelta(days=offset)).strftime('%Y-%m-%d')
                    if d in seen_dates:
                        continue
                    seen_dates.add(d)
                    if offset == 0:
                        day_items = items
                    else:
                        day_url = '%s?country=%s&date=%s' % (base, country, d)
                        try:
                            day_items = client.scrapePage(day_url, timeout='30').json()
                        except Exception:
                            day_items = []
                        if not isinstance(day_items, list):
                            day_items = []
                    for it in day_items:
                        try:
                            if int(it.get('season') or 0) == 1 and int(it.get('number') or 0) == 1:
                                widened.append(it)
                        except Exception:
                            continue
                    if len(widened) >= 25:
                        break
                items = widened
            except Exception:
                pass
        for item in items:
            try:
                # ``/schedule/web`` returns the show under ``_embedded.show``;
                # ``/schedule`` returns it under ``show``.  Normalise.
                show = item.get('show') or (item.get('_embedded') or {}).get('show') or {}
                if not show:
                    raise Exception()
                if not 'english' in (show.get('language') or '').lower():
                    raise Exception()
                if limit == True and not 'scripted' in (show.get('type') or '').lower():
                    raise Exception()
                title = item['name']
                if title == None or title == '':
                    raise Exception()
                title = client_utils.replaceHTMLCodes(title)
                season = item['season']
                season = re.sub(r'[^0-9]', '', '%01d' % int(season))
                if season == '0':
                    raise Exception()
                episode = item['number']
                episode = re.sub(r'[^0-9]', '', '%01d' % int(episode))
                if episode == '0':
                    raise Exception()
                if premieres_only and not (season == '1' and episode == '1'):
                    raise Exception()
                tvshowtitle = show.get('name')
                if tvshowtitle == None or tvshowtitle == '':
                    raise Exception()
                tvshowtitle = client_utils.replaceHTMLCodes(tvshowtitle)
                year = show.get('premiered') or ''
                year = re.findall(r'(\d{4})', year)[0]
                imdb = (show.get('externals') or {}).get('imdb')
                if imdb == None or imdb == '':
                    imdb = '0'
                else:
                    imdb = 'tt' + re.sub(r'[^0-9]', '', str(imdb))
                tvdb = (show.get('externals') or {}).get('thetvdb')
                if tvdb == None or tvdb == '':
                    tvdb = '0'
                tvdb = re.sub(r'[^0-9]', '', str(tvdb))
                poster1 = '0'
                try:
                    poster1 = show['image']['original']
                except:
                    poster1 = '0'
                if poster1 == None or poster1 == '':
                    poster1 = '0'
                try:
                    thumb1 = show['image']['original']
                except:
                    thumb1 = '0'
                try:
                    thumb2 = item['image']['original']
                except:
                    thumb2 = '0'
                if thumb2 == None or thumb2 == '0':
                    thumb = thumb1
                else:
                    thumb = thumb2
                if thumb == None or thumb == '':
                    thumb = '0'
                premiered = item.get('airdate') or ''
                try:
                    premiered = re.findall(r'(\d{4}-\d{2}-\d{2})', premiered)[0]
                except:
                    premiered = '0'
                try:
                    studio = show.get('network') or show.get('webChannel') or {}
                    if isinstance(studio, dict):
                        studio = [studio.get('name')] if studio.get('name') else []
                    elif isinstance(studio, list):
                        studio = [x['name'] for x in studio]
                except:
                    studio = []
                if studio == '' or studio == None or studio == []:
                    studio = []
                try:
                    genre = show.get('genres') or []
                    genre = [i.title() for i in genre]
                except:
                    genre = []
                if genre == '' or genre == None or genre == []:
                    genre = []
                try:
                    duration = show.get('runtime')
                except:
                    duration = '0'
                if duration == None:
                    duration = '0'
                try:
                    rating = (show.get('rating') or {}).get('average')
                except:
                    rating = '0'
                if rating == None or rating == '0.0':
                    rating = '0'
                votes = '0'
                try:
                    plot = show.get('summary') or '0'
                except:
                    plot = '0'
                if plot == None:
                    plot = '0'
                plot = re.sub(r'<.+?>|</.+?>|\n', '', plot)
                plot = client_utils.replaceHTMLCodes(plot)
                poster2 = fanart = banner = landscape = clearlogo = clearart = '0'
                if not tvdb == '0':
                    poster2, fanart, banner, clearlogo, clearart, landscape = self.get_fanart_tv_artwork(tvdb)
                poster = poster2 if not poster2 == '0' else poster1
                itemlist.append({'title': title, 'season': season, 'episode': episode, 'tvshowtitle': tvshowtitle, 'year': year, 'premiered': premiered, 'status': 'Continuing',
                    'studio': studio, 'genre': genre, 'duration': duration, 'rating': rating, 'votes': votes, 'plot': plot, 'imdb': imdb, 'tvdb': tvdb, 'tmdb': '0',
                    'thumb': thumb, 'poster': poster, 'banner': banner, 'fanart': fanart, 'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape}
                )
            except:
                #log_utils.log('tvmaze_list', 1)
                pass
        itemlist = itemlist[::-1]
        return itemlist


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


    def trakt_info(self, tvshowtitle, year, imdb, tmdb, season, meta=None, lite=False):
        try:
            tvdb = '0'
            if imdb == '0' and not tmdb == '0':
                temp_item = tmdb_utils.get_tvshow_external_ids(tmdb)
                imdb = temp_item.get('imdb_id', '0')
            if imdb == '0' and tmdb == '0':
                temp_item = trakt.SearchTVShow(tvshowtitle, year)
                if temp_item[0]['show']['title'] != tvshowtitle or int(temp_item[0]['show']['year']) != int(year):
                    raise Exception()
                imdb = temp_item[0]['show']['ids'].get('imdb', '0')
                tmdb = temp_item[0]['show']['ids'].get('tmdb', '0')
                if tvdb == '0':
                    tvdb = temp_item[0]['show']['ids'].get('tvdb', '0')
        except:
            #log_utils.log('trakt_info', 1)
            return
        try:
            if not imdb or imdb == '0':
                raise Exception()
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
            episodes = trakt.getEpisodeSummary(imdb, season, full=True)
            if not episodes:
                raise Exception()
            if self.specials == 'false':
                episodes = [e for e in episodes if not e['season'] == 0]
        except:
            #log_utils.log('trakt_info', 1)
            return
        clearlogo = clearart = landscape = duration = status = '0'
        if meta:
            _meta = json.loads(urllib_parse.unquote_plus(meta))
            poster, fanart, banner, clearlogo, clearart, landscape, duration, status = _meta['poster'], _meta['fanart'], _meta['banner'], _meta['clearlogo'], _meta['clearart'], _meta['landscape'], _meta['duration'], _meta['status']
        else:
            poster, fanart, banner = tmdb_utils.get_tmdb_artwork(tmdb, 'tv', season=season)
        for item in episodes:
            try:
                title = item.get('title', '0')
                title = client_utils.replaceHTMLCodes(title)
                label = title
                season = str(item.get('season'))
                episode = str(item.get('number'))
                premiered = item.get('first_aired', '0')
                if premiered and premiered != '0':
                    premiered = re.compile(r'(\d{4}-\d{2}-\d{2})').findall(premiered)[0]
                else:
                    premiered = '0'
                unaired = ''
                if not premiered or premiered == '0':
                    if self.shownoyear != 'true':
                        raise Exception()
                elif int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
                    unaired = 'true'
                    if self.showunaired != 'true':
                        raise Exception()
                rating = item.get('rating', '0')
                if not rating or rating == '0' or rating == '0.0':
                    rating = '0'
                votes = item.get('votes', '0')
                #votes = str(format(int(votes), ',d'))
                if not votes or votes == '0':
                    votes = '0'
                episodeplot = item.get('overview', '0')
                if not episodeplot or episodeplot == '0':
                    episodeplot = '0'
                else:
                    episodeplot = client_utils.replaceHTMLCodes(episodeplot)
                episode_poster, episode_fanart, episode_banner = tmdb_utils.get_tmdb_artwork(tmdb, 'tv', season=season, episode=episode)
                thumb = episode_fanart if not episode_fanart == '0' else fanart
                ### These 3 lines are not really needed from what i can tell but oh well lol.
                poster = episode_poster if not episode_poster == '0' else poster
                fanart = fanart if not fanart == '0' else episode_fanart
                banner = episode_banner if not episode_banner == '0' else banner
                #############################################################################
                self.list.append({'title': title, 'label': label, 'season': season, 'episode': episode, 'tvshowtitle': tvshowtitle, 'year': year, 'premiered': premiered,
                    'rating': rating, 'votes': votes, 'director': director, 'writer': writer, 'castwiththumb': castwiththumb, 'duration': duration,
                    'status': status, 'plot': episodeplot, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'unaired': unaired, 'thumb': thumb, 'poster': poster,
                    'fanart': fanart, 'banner': banner,'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape}
                )
            except:
                #log_utils.log('trakt_info', 1)
                pass
        return self.list


    def tmdb_list(self, tvshowtitle, year, imdb, tmdb, season, meta=None, lite=False):
        try:
            tvdb = '0'
            if tmdb == '0' and not imdb == '0':
                try:
                    url = self.tmdb_by_query_imdb_link % imdb
                    result = client.scrapePage(url, timeout='30').json()
                    id = result.get('tv_results', [])[0]
                    tmdb = id.get('id')
                    if not tmdb:
                        tmdb = '0'
                    else:
                        tmdb = str(tmdb)
                except:
                    #log_utils.log('tmdb_list', 1)
                    pass
            if tmdb == '0':
                try:
                    url = self.tmdb_search_link % (urllib_parse.quote(tvshowtitle)) + '&first_air_date_year=' + year
                    result = client.scrapePage(url, timeout='30').json()
                    results = result['results']
                    show = [r for r in results if cleantitle.get(r.get('name')) == cleantitle.get(self.list[i]['title'])][0]# and re.findall(r'(\d{4})', r.get('first_air_date'))[0] == self.list[i]['year']][0]
                    tmdb = show.get('id')
                    if not tmdb:
                        tmdb = '0'
                    else:
                        tmdb = str(tmdb)
                except:
                    #log_utils.log('tmdb_list', 1)
                    pass
        except:
            #log_utils.log('tmdb_list', 1)
            return
        try:
            if tmdb == '0':
                raise Exception()
            episodes_url = self.tmdb_season_link % (tmdb, season)
            result = client.scrapePage(episodes_url, timeout='30').json()
            #result = control.six_decode(result)
            episodes = result.get('episodes', [])
            r_cast = result.get('aggregate_credits', {}).get('cast', [])
            if self.specials == 'false':
                episodes = [e for e in episodes if not e['season_number'] == 0]
        except:
            #log_utils.log('tmdb_list', 1)
            return
        try:
            poster = result['poster_path']
        except:
            poster = ''
        if not (poster == '' or poster == None):
            if self.original_artwork == 'true':
                poster = self.tmdb_image_link + poster
            else:
                poster = self.tmdb_image_link % ('500', poster)
        else:
            poster = '0'
        fanart = banner = clearlogo = clearart = landscape = duration = status = '0'
        if meta:
            _meta = json.loads(urllib_parse.unquote_plus(meta))
            poster, fanart, banner, clearlogo, clearart, landscape, duration, status = _meta['poster'], _meta['fanart'], _meta['banner'], _meta['clearlogo'], _meta['clearart'], _meta['landscape'], _meta['duration'], _meta['status']
        for item in episodes:
            try:
                try:
                    title = item['name']
                except:
                    title = ''
                if not title:
                    title = '0'
                else:
                    title = client_utils.replaceHTMLCodes(title)
                label = title
                season = str(item['season_number'])
                episode = str(item['episode_number'])
                try:
                    premiered = item['air_date']
                except:
                    premiered = '0'
                unaired = ''
                if not premiered or premiered == '0':
                    if self.shownoyear != 'true':
                        raise Exception()
                elif int(re.sub(r'[^0-9]', '', str(premiered))) > int(re.sub(r'[^0-9]', '', str(self.today_date))):
                    unaired = 'true'
                    if self.showunaired != 'true':
                        raise Exception()
                try:
                    rating = str(item['vote_average'])
                except:
                    rating = ''
                if not rating:
                    rating = '0'
                try:
                    votes = str(item['vote_count'])
                except:
                    votes = ''
                if not votes:
                    votes = '0'
                try:
                    episodeplot = item['overview']
                except:
                    episodeplot = ''
                if not episodeplot:
                    episodeplot = '0'
                else:
                    episodeplot = client_utils.replaceHTMLCodes(episodeplot)
                try:
                    r_crew = item['crew']
                    director = [d['name'] for d in r_crew if d['job'] == 'Director']
                    #director = ', '.join([d['name'] for d in director])
                    writer = [w['name'] for w in r_crew if w['job'] == 'Writer']
                    #writer = ', '.join([w['name'] for w in writer])
                except:
                    director = writer = []#''
                if not director:
                    director = []#'0'
                if not writer:
                    writer = []#'0'
                castwiththumb = []
                try:
                    for person in r_cast[:30]:
                        _icon = person['profile_path']
                        if self.original_artwork == 'true':
                            icon = self.tmdb_image_link + _icon if _icon else ''
                        else:
                            icon = self.tmdb_image_link % ('185', _icon) if _icon else ''
                        castwiththumb.append({'name': person['name'], 'role': person['roles'][0]['character'], 'thumbnail': icon})
                except:
                    pass
                if not castwiththumb:
                    castwiththumb = '0'
                try:
                    thumb_path = item['still_path']
                except:
                    thumb_path = ''
                if thumb_path:
                    if self.original_artwork == 'true':
                        thumb = self.tmdb_image_link + thumb_path
                    else:
                        thumb = self.tmdb_image_link % ('300', thumb_path)
                else:
                    thumb = fanart
                self.list.append({'title': title, 'label': label, 'season': season, 'episode': episode, 'tvshowtitle': tvshowtitle, 'year': year, 'premiered': premiered,
                    'rating': rating, 'votes': votes, 'director': director, 'writer': writer, 'castwiththumb': castwiththumb, 'duration': duration,
                    'status': status, 'plot': episodeplot, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'unaired': unaired, 'thumb': thumb, 'poster': poster,
                    'fanart': fanart, 'banner': banner,'clearlogo': clearlogo, 'clearart': clearart, 'landscape': landscape}
                )
            except:
                #log_utils.log('tmdb_list', 1)
                pass
        return self.list


    def episodeDirectory(self, items):
        # FIX (v1.0.3): always finalise the directory even if items is
        # None or empty - the old code called control.idle() then fell
        # through to ``for i in items:`` which raised TypeError on None
        # and prevented control.directory() from ever being reached.
        # Kodi then logged "XFILE::CDirectory::GetDirectory - Error
        # getting plugin://..." for every empty TVmaze section
        # (Premiering Today on a slow news day, Streaming Today, etc.).
        if items is None:
            items = []
        if len(items) == 0:
            sysaddon = sys.argv[0]
            syshandle = int(sys.argv[1])
            control.idle()
            control.content(syshandle, 'episodes')
            control.directory(syshandle, cacheToDisc=False)
            return
        sysaddon = sys.argv[0]
        syshandle = int(sys.argv[1])
        addonPoster = control.addonPoster()
        addonBanner = control.addonBanner()
        addonFanart = control.addonFanart()
        settingFanart = control.setting('show.fanart')
        traktCredentials = trakt.getTraktCredentialsInfo()
        tmdbCredentials = tmdb_utils.getTMDbCredentialsInfo()
        isPlayable = True if not 'plugin' in control.infoLabel('Container.PluginName') else False
        indicators = playcount.getTVShowIndicators(refresh=True)
        try:
            multi = [i['tvshowtitle'] for i in items]
        except:
            multi = []
        multi = len([x for y,x in enumerate(multi) if x not in multi[:y]])
        multi = True if multi > 1 else False
        try:
            sysaction = items[0]['action']
        except:
            sysaction = ''
        isFolder = False if not sysaction == 'episodes' else True
        playbackMenu = 'Select Source' if control.setting('hosts.mode') == '2' else 'Auto Play'
        from resources.lib.modules import simkl as simkl_mod
        from resources.lib.modules import mdblist as mdblist_mod
        simklCredentials = simkl_mod.getSimklCredentialsInfo()
        mdblistCredentials = mdblist_mod.getMdblistCredentialsInfo()
        _ind = simkl_mod.getIndicatorsProvider()
        if _ind == 'trakt':
            watchedMenu, unwatchedMenu = 'Watched in Trakt', 'Unwatched in Trakt'
        elif _ind == 'simkl':
            watchedMenu, unwatchedMenu = 'Watched in Simkl', 'Unwatched in Simkl'
        elif _ind == 'mdblist':
            watchedMenu, unwatchedMenu = 'Watched in MDBList', 'Unwatched in MDBList'
        else:
            watchedMenu, unwatchedMenu = 'Watched in Gratis Red', 'Unwatched in Gratis Red'
        tv_library = libtools.libtvshows()
        for i in items:
            try:
                if not 'label' in i:
                    i['label'] = i['title']
                if i['label'] == '0':
                    label = '%sx%02d . %s %s' % (i['season'], int(i['episode']), 'Episode', i['episode'])
                else:
                    label = '%sx%02d . %s' % (i['season'], int(i['episode']), i['label'])
                if multi == True:
                    label = '%s - %s' % (i['tvshowtitle'], label)
                try:
                    if i['unaired'] == 'true':
                        label = '[COLOR %s][I]%s[/I][/COLOR]' % (self.unairedcolor, label)
                except:
                    pass
                imdb, tvdb, tmdb, year, season, episode = i['imdb'], i['tvdb'], i['tmdb'], i['year'], i['season'], i['episode']
                poster = i['poster'] if 'poster' in i and not i['poster'] == '0' else addonPoster
                fanart = i['fanart'] if 'fanart' in i and not i['fanart'] == '0' else addonFanart
                banner1 = i.get('banner', '')
                banner = banner1 or fanart or addonBanner
                if 'landscape' in i and not i['landscape'] == '0':
                    landscape = i['landscape']
                else:
                    landscape = fanart
                seasons_meta = {'poster': poster, 'fanart': fanart, 'banner': banner, 'clearlogo': i.get('clearlogo', '0'), 'clearart': i.get('clearart', '0'), 'landscape': landscape, 'duration': i.get('duration', '0'), 'status': i.get('status', '0')}
                seas_meta = urllib_parse.quote_plus(json.dumps(seasons_meta))
                systitle = urllib_parse.quote_plus(i['title'])
                systvshowtitle = urllib_parse.quote_plus(i['tvshowtitle'])
                syspremiered = urllib_parse.quote_plus(i['premiered'])
                meta = dict((k,v) for k, v in six.iteritems(i) if not v == '0')
                meta.update({'mediatype': 'episode'})
                meta.update({'code': tmdb, 'imdbnumber': imdb})
                meta.update({'trailer': '%s?action=trailer&name=%s&tmdb=%s&imdb=%s&season=%s&episode=%s' % (sysaddon, systvshowtitle, tmdb, imdb, season, episode)})
                if not 'duration' in i:
                    meta.update({'duration': '45'})
                elif i['duration'] == '0':
                    meta.update({'duration': '45'})
                try:
                    meta.update({'duration': str(int(meta['duration']) * 60)})
                except:
                    pass
                try:
                    meta.update({'year': re.findall(r'(\d{4})', i['premiered'])[0]})
                except:
                    pass
                try:
                    meta.update({'title': i['label']})
                except:
                    pass
                try:
                    meta.update({'tvshowyear': i['year']}) # Kodi uses the year (the year the show started) as the year for the episode. Change it from the premiered date.
                except:
                    pass
                meta.update({'poster': poster, 'fanart': fanart, 'banner': banner})
                sysmeta = urllib_parse.quote_plus(json.dumps(meta))
                url = '%s?action=play&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&season=%s&episode=%s&tvshowtitle=%s&premiered=%s&meta=%s&t=%s' % (sysaddon, systitle, year, imdb, tmdb, tvdb, season, episode, systvshowtitle, syspremiered, sysmeta, self.systime)
                sysurl = urllib_parse.quote_plus(url)
                path = '%s?action=play&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&season=%s&episode=%s&tvshowtitle=%s&premiered=%s' % (sysaddon, systitle, year, imdb, tmdb, tvdb, season, episode, systvshowtitle, syspremiered)
                if isFolder == True:
                    url = '%s?action=episodes&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&season=%s&episode=%s' % (sysaddon, systvshowtitle, year, imdb, tmdb, seas_meta, season, episode)
                cm = []
                cm.append(('Clean Tools Widget', 'RunPlugin(%s?action=cleantools_widget)' % sysaddon))
                cm.append(('Clear Providers', 'RunPlugin(%s?action=clear_sources)' % sysaddon))
                if multi == True:
                    cm.append(('Browse Series', 'Container.Update(%s?action=seasons&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s&meta=%s,return)' % (sysaddon, systvshowtitle, year, imdb, tmdb, seas_meta)))
                cm.append(('Queue Item', 'RunPlugin(%s?action=queue_item)' % sysaddon))
                if simklCredentials == True:
                    cm.append(('Simkl Lists Manager', 'RunPlugin(%s?action=simkl_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, systvshowtitle, imdb, tmdb)))
                if mdblistCredentials == True:
                    cm.append(('MDBList Lists Manager', 'RunPlugin(%s?action=mdblist_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, systvshowtitle, imdb, tmdb)))
                if tmdbCredentials == True:
                    cm.append(('TMDb Lists Manager', 'RunPlugin(%s?action=tmdb_manager&name=%s&tmdb=%s&content=tvshow)' % (sysaddon, systvshowtitle, tmdb)))
                if traktCredentials == True:
                    cm.append(('Trakt Lists Manager', 'RunPlugin(%s?action=trakt_manager&name=%s&imdb=%s&tmdb=%s&content=tvshow)' % (sysaddon, systvshowtitle, imdb, tmdb)))
                libtools.append_tvshow_library_cm(cm, sysaddon, tv_library, i['tvshowtitle'], year, imdb, tmdb)
                if kodi_version < 17:
                    cm.append(('Information', 'Action(Info)'))
                try:
                    overlay = int(playcount.getEpisodeOverlay(indicators, imdb, tmdb, season, episode))
                    if overlay == 7:
                        cm.append((unwatchedMenu, 'RunPlugin(%s?action=episodes_playcount&imdb=%s&tmdb=%s&season=%s&episode=%s&query=6)' % (sysaddon, imdb, tmdb, season, episode)))
                        meta.update({'playcount': 1, 'overlay': 7})
                    else:
                        cm.append((watchedMenu, 'RunPlugin(%s?action=episodes_playcount&imdb=%s&tmdb=%s&season=%s&episode=%s&query=7)' % (sysaddon, imdb, tmdb, season, episode)))
                        meta.update({'playcount': 0, 'overlay': 6})
                except:
                    pass
                if isFolder == False:
                    cm.append((playbackMenu, 'RunPlugin(%s?action=alter_sources&url=%s&meta=%s)' % (sysaddon, sysurl, sysmeta)))
                try:
                    item = control.item(label=label, offscreen=True)
                except:
                    item = control.item(label=label)
                art = {}
                if self.episode_thumbs == 'true':
                    thumb = poster
                else:
                    thumb = meta.get('thumb', '') or fanart
                clearlogo = meta.get('clearlogo', '')
                clearart = meta.get('clearart', '')
                art.update({'icon': thumb, 'thumb': thumb, 'banner': banner, 'poster': thumb, 'tvshow.poster': poster, 'season.poster': poster, 'landscape': landscape, 'clearlogo': clearlogo, 'clearart': clearart})
                if settingFanart == 'true':
                    art.update({'fanart': fanart})
                elif not addonFanart == None:
                    art.update({'fanart': addonFanart})
                item.setArt(art)
                item.addContextMenuItems(cm)
                if isPlayable:
                    item.setProperty('IsPlayable', 'true')
                offset = bookmarks.get('episode', imdb, season, episode, True)
                if float(offset) > 120:
                    percentPlayed = int(float(offset) / float(meta['duration']) * 100)
                    item.setProperty('resumetime', str(offset))
                    item.setProperty('percentplayed', str(percentPlayed))
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
                control.addItem(handle=syshandle, url=url, listitem=item, isFolder=isFolder)
            except:
                #log_utils.log('episodeDirectory', 1)
                pass
        if self.episode_views == 'true':
            control.content(syshandle, 'seasons')
            control.directory(syshandle, cacheToDisc=True)
            views.setView('seasons')
        else:
            control.content(syshandle, 'episodes')
            control.directory(syshandle, cacheToDisc=True)
            views.setView('episodes')


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
                    item = control.item(label=name, offscreen=True)
                except:
                    item = control.item(label=name)
                control.set_menu_item_art(item, image, fanart=addonFanart)
                item.addContextMenuItems(cm)
                control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
            except:
                #log_utils.log('addDirectory', 1)
                pass
        from resources.lib.modules import views
        views.endMenuDirectory(syshandle)


