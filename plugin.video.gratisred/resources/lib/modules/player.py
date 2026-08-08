# -*- coding: utf-8 -*-

import sys
import threading

from kodi_six import xbmc
import simplejson as json
import six
from six.moves import urllib_parse

try:
    #from infotagger.listitem import ListItemInfoTag
    from resources.lib.modules.listitem import ListItemInfoTag
except:
    pass

from resources.lib.modules import bookmarks
from resources.lib.modules import control
from resources.lib.modules import cleantitle
from resources.lib.modules import playcount
from resources.lib.modules import subtitles as subtitle_service
from resources.lib.modules import simkl
from resources.lib.modules import trakt

try:
    import resolveurl
except:
    pass

kodi_version = control.getKodiVersion()


def playItem(url):
    try:
        if resolveurl.HostedMediaFile(url):
            url = resolveurl.resolve(url)
        item = control.item(path=url)
        item.setProperty('IsPlayable', 'true')
        control.player.play(url, item)
    except:
        control.infoDialog('Error : No Stream Available.', sound=False, icon='INFO')
        return


def playMedia(url):
    try:
        if resolveurl.HostedMediaFile(url):
            url = resolveurl.resolve(url)
        control.execute('PlayMedia(%s)' % url)
    except:
        control.infoDialog('Error : No Stream Available.', sound=False, icon='INFO')
        return


class player(xbmc.Player):
    def __init__ (self):
        xbmc.Player.__init__(self)


    def run(self, title, year, season, episode, imdb, tmdb, tvdb, url, meta):
        try:
            control.sleep(200)
            self.totalTime = 0
            self.currentTime = 0
            self.content = 'movie' if season == None or episode == None else 'episode'
            self.title = title
            self.year = year
            self.name = urllib_parse.quote_plus(title) + urllib_parse.quote_plus(' (%s)' % year) if self.content == 'movie' else urllib_parse.quote_plus(title) + urllib_parse.quote_plus(' S%01dE%01d' % (int(season), int(episode)))
            self.name = urllib_parse.unquote_plus(self.name)
            self.season = '%01d' % int(season) if self.content == 'episode' else None
            self.episode = '%01d' % int(episode) if self.content == 'episode' else None
            self.DBID = None
            self.imdb = imdb if not imdb == None else '0'
            self.tmdb = tmdb if not tmdb == None else '0'
            self.tvdb = tvdb if not tvdb == None else '0'
            self.ids = {'imdb': self.imdb, 'tmdb': self.tmdb, 'tvdb': self.tvdb}
            self.ids = dict((k,v) for k, v in six.iteritems(self.ids) if not v == '0')
            self.offset, self.resume_percent = bookmarks.get_resume(self.content, imdb, season, episode, tmdb=self.tmdb)
            self._simkl_scrobble_started = False
            self._trakt_scrobble_started = False
            self._trakt_scrobble_finalized = False
            self._trakt_pending_stop_percent = None
            # Do not seed from bookmark — failed/zero-time stops must not scrobble at stale resume %.
            self._last_percent = 0.0
            poster, thumb, fanart, clearlogo, clearart, discart, meta = self.getMeta(meta)
            item = control.item(path=url)
            if self.content == 'movie':
                item.setArt({'icon': thumb, 'thumb': thumb, 'poster': poster, 'fanart': fanart, 'clearlogo': clearlogo, 'clearart': clearart, 'discart': discart})
            else:
                item.setArt({'icon': thumb, 'thumb': thumb, 'tvshow.poster': poster, 'season.poster': poster, 'fanart': fanart, 'clearlogo': clearlogo, 'clearart': clearart})
            if kodi_version >= 20:
                info_tag = ListItemInfoTag(item, 'video')
                info_tag.set_info(control.metadataClean(meta))
            else:
                item.setInfo(type='Video', infoLabels=control.metadataClean(meta))
            # Prefer setResolvedUrl when the plugin handle expects it (Kodi 22 widgets /
            # PlayMedia). Player().play() from a plugin is unsupported and can leave the
            # original plugin:// item unresolved → "One or more items failed to play".
            played_via_resolve = False
            try:
                handle = control.plugin_handle()
                if handle > 0:
                    control.resolve(handle, True, item)
                    control.mark_resolve_sent()
                    played_via_resolve = True
            except Exception:
                pass
            if not played_via_resolve:
                self.play(url, item)
            control.window.setProperty('script.trakt.ids', json.dumps(self.ids))
            self.keepPlaybackAlive()
            # Stop after CloseFile — never sync-HTTP inside onPlayBackStopped (freezes Kodi).
            self._trakt_scrobble_finalize()
            control.window.clearProperty('script.trakt.ids')
        except:
            try:
                self._trakt_scrobble_finalize()
            except Exception:
                pass
            control.abort_plugin_resolve()
            return


    def getMeta(self, meta):
        try:
            poster = meta.get('poster', '') or control.addonPoster()
            thumb = meta.get('thumb', '') or poster
            fanart = meta.get('fanart', '') or control.addonFanart()
            clearlogo = meta.get('clearlogo', '') or ''
            clearart = meta.get('clearart', '') or ''
            discart = meta.get('discart', '') or ''
            return poster, thumb, fanart, clearlogo, clearart, discart, meta
        except:
            pass
        try:
            if not self.content == 'movie':
                raise Exception()
            meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "originaltitle", "year", "genre", "studio", "country", "runtime", "rating", "votes", "mpaa", "director", "writer", "plot", "plotoutline", "tagline", "thumbnail", "file"]}, "id": 1}' % (self.year, str(int(self.year)+1), str(int(self.year)-1)))
            meta = six.ensure_text(meta, errors='ignore')
            meta = json.loads(meta)['result']['movies']
            t = cleantitle.get(self.title)
            meta = [i for i in meta if self.year == str(i['year']) and (t == cleantitle.get(i['title']) or t == cleantitle.get(i['originaltitle']))][0]
            for k, v in six.iteritems(meta):
                if type(v) == list:
                    try:
                        meta[k] = str(' / '.join([six.ensure_str(i) for i in v]))
                    except:
                        meta[k] = ''
                else:
                    try:
                        meta[k] = str(six.ensure_str(v))
                    except:
                        meta[k] = str(v)
            if not 'plugin' in control.infoLabel('Container.PluginName'):
                self.DBID = meta['movieid']
            poster = thumb = meta['thumbnail']
            return poster, thumb, '', '', '', '', meta
        except:
            pass
        try:
            if not self.content == 'episode':
                raise Exception()
            meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "year", "thumbnail", "file"]}, "id": 1}' % (self.year, str(int(self.year)+1), str(int(self.year)-1)))
            meta = six.ensure_text(meta, errors='ignore')
            meta = json.loads(meta)['result']['tvshows']
            t = cleantitle.get(self.title)
            meta = [i for i in meta if self.year == str(i['year']) and t == cleantitle.get(i['title'])][0]
            tvshowid = meta['tvshowid'] ; poster = meta['thumbnail']
            meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params":{ "tvshowid": %d, "filter":{"and": [{"field": "season", "operator": "is", "value": "%s"}, {"field": "episode", "operator": "is", "value": "%s"}]}, "properties": ["title", "season", "episode", "showtitle", "firstaired", "runtime", "rating", "director", "writer", "plot", "thumbnail", "file"]}, "id": 1}' % (tvshowid, self.season, self.episode))
            meta = six.ensure_text(meta, errors='ignore')
            meta = json.loads(meta)['result']['episodes'][0]
            for k, v in six.iteritems(meta):
                if type(v) == list:
                    try:
                        meta[k] = str(' / '.join([six.ensure_str(i) for i in v]))
                    except:
                        meta[k] = ''
                else:
                    try:
                        meta[k] = str(six.ensure_str(v))
                    except:
                        meta[k] = str(v)
            if not 'plugin' in control.infoLabel('Container.PluginName'):
                self.DBID = meta['episodeid']
            thumb = meta['thumbnail']
            return poster, thumb, '', '', '', '', meta
        except:
            pass
        poster, thumb, fanart, clearlogo, clearart, discart, meta = '', '', '', '', '', '', {'title': self.name}
        return poster, thumb, fanart, clearlogo, clearart, discart, meta


    def keepPlaybackAlive(self):
        pname = '%s.player.overlay' % control.addonInfo('id')
        control.window.clearProperty(pname)
        if self.content == 'movie':
            overlay = playcount.getMovieOverlay(playcount.getMovieIndicators(), self.imdb)
        elif self.content == 'episode':
            overlay = playcount.getEpisodeOverlay(playcount.getTVShowIndicators(), self.imdb, self.tmdb, self.season, self.episode)
        else:
            overlay = '6'
        for i in range(0, 240):
            if self.isPlayingVideo():
                break
            xbmc.sleep(1000)
        # Backup if onAVStarted never ran on this Player instance.
        if self.isPlayingVideo():
            self._ensure_live_scrobble_start()
        if overlay == '7':
            while self.isPlayingVideo():
                try:
                    self.totalTime = self.getTotalTime()
                    self.currentTime = self.getTime()
                    self._update_last_percent()
                except:
                    pass
                xbmc.sleep(2000)
        elif self.content == 'movie':
            while self.isPlayingVideo():
                try:
                    self.totalTime = self.getTotalTime()
                    self.currentTime = self.getTime()
                    self._update_last_percent()
                    watcher = (self.currentTime / self.totalTime >= .92)
                    property = control.window.getProperty(pname)
                    if watcher == True and not property == '7':
                        control.window.setProperty(pname, '7')
                        playcount.markMovieDuringPlayback(self.imdb, '7', self.tmdb)
                except:
                    pass
                xbmc.sleep(2000)
        elif self.content == 'episode':
            while self.isPlayingVideo():
                try:
                    self.totalTime = self.getTotalTime()
                    self.currentTime = self.getTime()
                    self._update_last_percent()
                    watcher = (self.currentTime / self.totalTime >= .92)
                    property = control.window.getProperty(pname)
                    if watcher == True and not property == '7':
                        control.window.setProperty(pname, '7')
                        playcount.markEpisodeDuringPlayback(self.imdb, self.tmdb, self.season, self.episode, '7', self.tvdb)
                except:
                    pass
                xbmc.sleep(2000)
        control.window.clearProperty(pname)


    def _update_last_percent(self):
        try:
            total = float(self.totalTime or 0)
            current = float(self.currentTime or 0)
            if total > 0:
                self._last_percent = max(0, min(100, (current / total) * 100.0))
        except Exception:
            pass


    def _ensure_live_scrobble_start(self):
        start_pct = float(getattr(self, '_last_percent', 0) or 0) or self._playback_percent()
        if not getattr(self, '_simkl_scrobble_started', False):
            self._simkl_scrobble_started = True
            self._simkl_scrobble('start', percent=start_pct)
        if not getattr(self, '_trakt_scrobble_started', False):
            self._trakt_scrobble_started = True
            self._trakt_scrobble('start', percent=start_pct)

    def _playback_folder_is_sources(self):
        """True when the visible plugin folder is the sources / play container."""
        try:
            folder = control.infoLabel('Container.FolderPath') or ''
            return any(x in folder for x in (
                'action=add_item', 'action=play_item', 'action=play_', 'action=sources'
            ))
        except Exception:
            return False


    def _refresh_after_playback_mark(self):
        """Refresh a content list after auto-mark — never the sources folder.

        After play, FolderPath is usually add_item (sources). Refreshing that
        races two listings and blanks the screen (or hard-crashes with Update).
        Episode/Library checkmarks update when the user returns to those lists.
        """
        try:
            if control.window.getProperty(playcount.PLAYBACK_MARKED_PROPERTY) != 'true':
                return
            control.window.clearProperty(playcount.PLAYBACK_MARKED_PROPERTY)
            if self._playback_folder_is_sources():
                return
            control.refresh()
        except Exception:
            pass


    def libForPlayback(self):
        try:
            if self.DBID == None:
                raise Exception()
            if self.content == 'movie':
                rpc = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": {"movieid" : %s, "playcount" : 1 }, "id": 1 }' % str(self.DBID)
            elif self.content == 'episode':
                rpc = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": {"episodeid" : %s, "playcount" : 1 }, "id": 1 }' % str(self.DBID)
            control.jsonrpc(rpc)
            if not self._playback_folder_is_sources():
                control.refresh()
        except:
            pass


    def idleForPlayback(self):
        for i in range(0, 400):
            if control.condVisibility('Window.IsActive(busydialog)') == 1 or control.condVisibility('Window.IsActive(busydialognocancel)') == 1:
                control.idle()
            else:
                control.execute('Dialog.Close(all,true)')
                break
            control.sleep(100)


    def _resume_offset(self):
        offset = float(getattr(self, 'offset', 0) or 0)
        if offset > 120:
            return offset
        percent = float(getattr(self, 'resume_percent', 0) or 0)
        if not (1 < percent < 92):
            return 0
        try:
            total = float(self.getTotalTime() or self.totalTime or 0)
        except Exception:
            total = float(getattr(self, 'totalTime', 0) or 0)
        if total <= 120:
            return 0
        return (percent / 100.0) * total


    def _resume_source_label(self):
        source = control.setting('bookmarks.source')
        if source == '1' and trakt.getTraktCredentialsInfo() == True:
            return '[CR]  (Trakt)'
        if source == '2' and simkl.getSimklCredentialsInfo():
            return '[CR]  (Simkl)'
        return ''


    def _playback_percent(self):
        try:
            total = float(self.totalTime or self.getTotalTime() or 0)
            current = float(self.currentTime or self.getTime() or 0)
            if total <= 0:
                return 0
            return max(0, min(100, (current / total) * 100.0))
        except Exception:
            return 0


    def _simkl_scrobble(self, action, percent=None):
        if simkl.getIndicatorsProvider() != 'simkl':
            return
        if percent is None:
            percent = self._playback_percent()
        media_type = 'movie' if self.content == 'movie' else 'episode'
        args = (action, media_type, percent)
        kwargs = {
            'tmdb': self.tmdb if self.tmdb not in (None, '0') else None,
            'imdb': self.imdb if self.imdb not in (None, '0') else None,
            'season': self.season,
            'episode': self.episode,
        }
        try:
            threading.Thread(target=simkl.simkl_scrobble, args=args, kwargs=kwargs).start()
        except Exception:
            pass


    def _trakt_scrobble(self, action, percent=None, sync=False):
        if not trakt.getTraktIndicatorsInfo():
            return
        if percent is None:
            percent = self._playback_percent()
        # Trakt 422 on stop below 1% leaves Playing now stuck — clamp for stop.
        if action == 'stop':
            try:
                percent = float(percent or 0)
            except Exception:
                percent = 0
            if percent < 1:
                percent = 1
        media_type = 'movie' if self.content == 'movie' else 'episode'
        args = (action, media_type, percent)
        kwargs = {
            'tmdb': self.tmdb if self.tmdb not in (None, '0') else None,
            'imdb': self.imdb if self.imdb not in (None, '0') else None,
            'tvdb': self.tvdb if self.tvdb not in (None, '0') else None,
            'season': self.season,
            'episode': self.episode,
        }
        try:
            if sync:
                trakt.trakt_scrobble(*args, **kwargs)
            else:
                threading.Thread(target=trakt.trakt_scrobble, args=args, kwargs=kwargs).start()
        except Exception:
            pass


    def _trakt_scrobble_finalize(self):
        """Clear Playing now after the player has closed (safe to block briefly)."""
        if getattr(self, '_trakt_scrobble_finalized', False):
            return
        self._trakt_scrobble_finalized = True
        # Always attempt stop when Indicators=Trakt for this playback — even if start
        # callback was missed, a prior start (or stuck Playing now) still needs clearing.
        if not trakt.getTraktIndicatorsInfo():
            return
        pct = getattr(self, '_trakt_pending_stop_percent', None)
        if pct is None:
            pct = getattr(self, '_last_percent', None)
        if pct is None:
            try:
                pct = float(self._playback_percent() or 0)
            except Exception:
                pct = 1
        try:
            pct = float(pct or 0)
        except Exception:
            pct = 1
        if pct < 1:
            pct = 1
        self._trakt_scrobble('stop', percent=pct, sync=True)


    def _offer_resume(self, offset):
        if control.setting('bookmarks') != 'true' or offset <= 120 or not self.isPlayingVideo():
            return
        if control.setting('bookmarks.auto') == 'true':
            self.seekTime(float(offset))
            return
        self.pause()
        minutes, seconds = divmod(float(offset), 60)
        hours, minutes = divmod(minutes, 60)
        label = '%02d:%02d:%02d' % (hours, minutes, seconds)
        label = control.lang2(12022).format(label)
        label += self._resume_source_label()
        if kodi_version < 18:
            label = six.ensure_str(label)
        yes = control.yesnoDialog(label, heading=control.lang2(13404))
        if yes:
            self.seekTime(float(offset))
        control.sleep(1000)
        self.pause()


    def onAVStarted(self):
        control.execute('Dialog.Close(all,true)')
        offset = self._resume_offset()
        self._offer_resume(offset)
        self._ensure_live_scrobble_start()
        subtitle_service.subtitles().get(self.imdb, self.season, self.episode, year=self.year, title=self.title)
        self.idleForPlayback()


    def onPlayBackStarted(self):
        if kodi_version < 18:
            control.execute('Dialog.Close(all,true)')
            offset = self._resume_offset()
            self._offer_resume(offset)
            self._ensure_live_scrobble_start()
            subtitle_service.subtitles().get(self.imdb, self.season, self.episode, year=self.year, title=self.title)
            self.idleForPlayback()
        else:
            pass
            #self.onAVStarted()


    def onPlayBackPaused(self):
        try:
            self.totalTime = self.getTotalTime()
            self.currentTime = self.getTime()
            self._update_last_percent()
        except Exception:
            pass
        percent = self._playback_percent() or getattr(self, '_last_percent', 0) or 0
        if 1 <= percent < 92:
            self._simkl_scrobble('pause', percent=percent)
            self._trakt_scrobble('pause', percent=percent)


    def onPlayBackStopped(self):
        try:
            try:
                self.totalTime = self.getTotalTime() or self.totalTime
                self.currentTime = self.getTime() or self.currentTime
                self._update_last_percent()
            except Exception:
                pass
            if self.totalTime == 0 or self.currentTime == 0:
                if getattr(self, '_trakt_scrobble_started', False) or trakt.getTraktIndicatorsInfo():
                    # Failed open / zero progress — clear Playing now at 1%, never bookmark resume %.
                    self._trakt_pending_stop_percent = 1
                control.sleep(2000)
                return
            percent = self._playback_percent() or getattr(self, '_last_percent', 0) or 0
            self._trakt_pending_stop_percent = 100 if percent >= 92 else percent
            if percent >= 92:
                self._simkl_scrobble('stop', percent=100)
            elif percent >= 1:
                self._simkl_scrobble('pause', percent=percent)
            bookmarks.reset(self.currentTime, self.totalTime, self.content, self.imdb, self.season, self.episode)
            if float(self.currentTime / self.totalTime) >= 0.92:
                self.libForPlayback()
        finally:
            # Same Container.Refresh as manual Watched — after playback, all platforms (#157).
            self._refresh_after_playback_mark()


    def onPlayBackEnded(self):
        try:
            if not self.totalTime:
                self.totalTime = self.getTotalTime()
            self.currentTime = self.totalTime
        except Exception:
            pass
        self.libForPlayback()
        self.onPlayBackStopped()
        # Optional setting — never on sources (doubles with mark-refresh / blanks UI).
        if control.setting('crefresh') == 'true' and not self._playback_folder_is_sources():
            control.refresh()

