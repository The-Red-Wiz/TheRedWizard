# -*- coding: utf-8 -*-

import sys

from resources.lib.modules import bookmarks
from resources.lib.modules import control
from resources.lib.modules import mdblist
from resources.lib.modules import simkl
from resources.lib.modules import trakt


def _provider():
    try:
        return simkl.getIndicatorsProvider()
    except Exception:
        return 'trakt' if trakt.getTraktIndicatorsInfo() else 'local'


_LIST_SYNC_SKIP_PROPS = {
    'trakt': 'gratisred.trakt_skip_list_sync',
    'simkl': 'gratisred.simkl_skip_list_sync',
    'mdblist': 'gratisred.mdblist_skip_list_sync',
}


def _arm_provider_list_sync_skip(provider=None):
    """Next list open already has a fresh local cache from the mark — skip a cloud pull."""
    provider = provider or _provider()
    prop = _LIST_SYNC_SKIP_PROPS.get(provider)
    if not prop:
        return
    try:
        control.window.setProperty(prop, 'true')
    except Exception:
        pass


def _consume_provider_list_sync_skip(provider=None):
    provider = provider or _provider()
    prop = _LIST_SYNC_SKIP_PROPS.get(provider)
    if not prop:
        return False
    try:
        if control.window.getProperty(prop) == 'true':
            control.window.clearProperty(prop)
            return True
    except Exception:
        pass
    return False


def getMovieIndicators(refresh=False):
    provider = _provider()
    if provider == 'local':
        try:
            return bookmarks._indicators()
        except Exception:
            return
    skip_sync = refresh and _consume_provider_list_sync_skip(provider)
    if provider == 'simkl':
        try:
            if refresh and not skip_sync:
                # Activities + date_from delta when possible (same idea as Trakt activity gate).
                simkl.syncSimklWatched(silent=True)
            return simkl.cachesyncMovies(timeout=720)
        except Exception:
            return
    if provider == 'mdblist':
        try:
            if refresh and not skip_sync:
                mdblist.syncMdblistWatched(silent=True)
            return mdblist.cachesyncMovies(timeout=720)
        except Exception:
            return
    try:
        if refresh == False or skip_sync:
            timeout = 720
        elif trakt.getWatchedActivity() < trakt.timeoutsyncMovies():
            timeout = 720
        else:
            timeout = 0
        return trakt.cachesyncMovies(timeout=timeout)
    except Exception:
        pass


def getTVShowIndicators(refresh=False):
    provider = _provider()
    if provider == 'local':
        try:
            return bookmarks._indicators()
        except Exception:
            return
    skip_sync = refresh and _consume_provider_list_sync_skip(provider)
    if provider == 'simkl':
        try:
            if refresh and not skip_sync:
                simkl.syncSimklWatched(silent=True)
            return simkl.cachesyncTVShows(timeout=720)
        except Exception:
            return
    if provider == 'mdblist':
        try:
            if refresh and not skip_sync:
                mdblist.syncMdblistWatched(silent=True)
            return mdblist.cachesyncTVShows(timeout=720)
        except Exception:
            return
    try:
        if refresh == False or skip_sync:
            timeout = 720
        elif trakt.getWatchedActivity() < trakt.timeoutsyncTVShows():
            timeout = 720
        else:
            timeout = 0
        return trakt.cachesyncTVShows(timeout=timeout)
    except Exception:
        pass


def getSeasonIndicators(imdb, tmdb=None):
    provider = _provider()
    if provider == 'simkl':
        try:
            return simkl.syncSeason(imdb, tmdb=tmdb)
        except Exception:
            return
    if provider == 'mdblist':
        try:
            return mdblist.syncSeason(imdb, tmdb=tmdb)
        except Exception:
            return
    try:
        if provider != 'trakt':
            raise Exception()
        return trakt.syncSeason(imdb)
    except Exception:
        pass


def getMovieOverlay(indicators_, imdb):
    try:
        if _provider() == 'local':
            overlay = bookmarks._get_watched('movie', imdb, '', '')
            return str(overlay)
        playcount = [i for i in indicators_ if i == imdb]
        overlay = 7 if len(playcount) > 0 else 6
        return str(overlay)
    except:
        return '6'


def getTVShowOverlay(indicators_, imdb, tmdb):
    try:
        if _provider() == 'local':
            playcount = bookmarks._get_watched('tvshow', imdb, '', '')
            return str(playcount)
        playcount = [i[0] for i in indicators_ if i[0] == tmdb and len(i[2]) >= int(i[1])]
        playcount = 7 if len(playcount) > 0 else 6
        return str(playcount)
    except:
        return '6'


def getSeasonOverlay(indicators_, imdb, season):
    try:
        if _provider() == 'local':
            playcount = bookmarks._get_watched('season', imdb, season, '')
            return str(playcount)
        playcount = [i for i in indicators_ if int(season) == int(i)]
        playcount = 7 if len(playcount) > 0 else 6
        return str(playcount)
    except:
        return '6'


def getEpisodeOverlay(indicators_, imdb, tmdb, season, episode):
    try:
        if _provider() == 'local':
            overlay = bookmarks._get_watched('episode', imdb, season, episode)
            return str(overlay)
        playcount = [i[2] for i in indicators_ if i[0] == tmdb]
        playcount = playcount[0] if len(playcount) > 0 else []
        playcount = [i for i in playcount if int(season) == int(i[0]) and int(episode) == int(i[1])]
        overlay = 7 if len(playcount) > 0 else 6
        return str(overlay)
    except:
        return '6'


PLAYBACK_MARKED_PROPERTY = 'gratisred.playback_marked_watched'


def _flag_playback_marked():
    """Remember that watched state changed during this play so UI can refresh after stop."""
    try:
        control.window.setProperty(PLAYBACK_MARKED_PROPERTY, 'true')
    except Exception:
        pass


def _notify_marked(watched):
    try:
        message = 'Marked as watched.' if int(watched) == 7 else 'Marked as unwatched.'
        control.infoDialog(message, sound=True)
    except Exception:
        pass


def _finish_manual_mark(watched):
    """Toast + list refresh for Trakt / Simkl / Gratis Red / MDBList manual mark."""
    try:
        control.idle()
    except Exception:
        pass
    _arm_provider_list_sync_skip()
    _notify_marked(watched)
    try:
        control.refresh_list()
    except Exception:
        pass


def markMovieDuringPlayback(imdb, watched, tmdb=None):
    provider = _provider()
    try:
        if provider == 'trakt':
            if int(watched) == 7:
                trakt.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                trakt.markMovieAsNotWatched(imdb, tmdb=tmdb)
            trakt.cachesyncMovies()
            _arm_provider_list_sync_skip('trakt')
            _flag_playback_marked()
            if trakt.getTraktAddonMovieInfo() == True:
                trakt.markMovieAsNotWatched(imdb, tmdb=tmdb)
        elif provider == 'simkl':
            if int(watched) == 7:
                simkl.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                simkl.markMovieAsNotWatched(imdb, tmdb=tmdb)
            simkl.cachesyncMovies(timeout=0)
            _arm_provider_list_sync_skip('simkl')
            _flag_playback_marked()
            if simkl.getSimklAddonMovieInfo() == True:
                simkl.markMovieAsNotWatched(imdb, tmdb=tmdb)
        elif provider == 'mdblist':
            if int(watched) == 7:
                mdblist.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                mdblist.markMovieAsNotWatched(imdb, tmdb=tmdb)
            mdblist.cachesyncMovies(timeout=0)
            _arm_provider_list_sync_skip('mdblist')
            _flag_playback_marked()
            if mdblist.mdblist_official_status():
                mdblist.markMovieAsNotWatched(imdb, tmdb=tmdb)
    except:
        pass
    try:
        if int(watched) == 7:
            bookmarks.reset(1, 1, 'movie', imdb, '', '')
    except:
        pass


def markEpisodeDuringPlayback(imdb, tmdb, season, episode, watched, tvdb=None):
    provider = _provider()
    try:
        if provider == 'trakt':
            if int(watched) == 7:
                trakt.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb, tvdb=tvdb)
            else:
                trakt.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb, tvdb=tvdb)
            trakt.cachesyncTVShows()
            _arm_provider_list_sync_skip('trakt')
            _flag_playback_marked()
            if trakt.getTraktAddonEpisodeInfo() == True:
                trakt.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb, tvdb=tvdb)
        elif provider == 'simkl':
            if int(watched) == 7:
                simkl.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                simkl.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            simkl.cachesyncTVShows(timeout=0)
            _arm_provider_list_sync_skip('simkl')
            _flag_playback_marked()
            if simkl.getSimklAddonEpisodeInfo() == True:
                simkl.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
        elif provider == 'mdblist':
            if int(watched) == 7:
                mdblist.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                mdblist.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            mdblist.cachesyncTVShows(timeout=0)
            _arm_provider_list_sync_skip('mdblist')
            _flag_playback_marked()
            if mdblist.mdblist_official_status():
                mdblist.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
    except:
        pass
    try:
        if int(watched) == 7:
            bookmarks.reset(1, 1, 'episode', imdb, season, episode)
    except:
        pass


def movies(imdb, watched, tmdb=None):
    control.busy()
    provider = _provider()
    try:
        if provider == 'trakt':
            if int(watched) == 7:
                trakt.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                trakt.markMovieAsNotWatched(imdb, tmdb=tmdb)
            trakt.cachesyncMovies()
        elif provider == 'simkl':
            if int(watched) == 7:
                simkl.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                simkl.markMovieAsNotWatched(imdb, tmdb=tmdb)
            simkl.cachesyncMovies(timeout=0)
        elif provider == 'mdblist':
            if int(watched) == 7:
                mdblist.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                mdblist.markMovieAsNotWatched(imdb, tmdb=tmdb)
            mdblist.cachesyncMovies(timeout=0)
        else:
            raise Exception()
    except:
        pass
    try:
        if int(watched) == 7:
            bookmarks.reset(1, 1, 'movie', imdb, '', '')
        else:
            bookmarks._delete_record('movie', imdb, '', '')
    except:
        pass
    _finish_manual_mark(watched)


def episodes(imdb, tmdb, season, episode, watched):
    control.busy()
    provider = _provider()
    try:
        if provider == 'trakt':
            if int(watched) == 7:
                trakt.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                trakt.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            trakt.cachesyncTVShows()
        elif provider == 'simkl':
            if int(watched) == 7:
                simkl.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                simkl.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            simkl.cachesyncTVShows(timeout=0)
        elif provider == 'mdblist':
            if int(watched) == 7:
                mdblist.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                mdblist.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            mdblist.cachesyncTVShows(timeout=0)
        else:
            raise Exception()
    except:
        pass
    try:
        if int(watched) == 7:
            bookmarks.reset(1, 1, 'episode', imdb, season, episode)
        else:
            bookmarks._delete_record('episode', imdb, season, episode)
    except:
        pass
    _finish_manual_mark(watched)


def tvshows(tvshowtitle, imdb, tmdb, season, watched):
    control.busy()
    provider = _provider()
    try:
        if provider != 'local':
            raise Exception()
        from resources.lib.indexers import episodes
        name = control.addonInfo('name')
        dialog = control.progressDialogBG
        dialog.create(str(name), str(tvshowtitle))
        dialog.update(0, str(name), str(tvshowtitle))
        items = []
        if season:
            items = episodes.episodes().get(tvshowtitle, '0', imdb, tmdb, meta=None, season=season, idx=False)
            items = [i for i in items if int('%01d' % int(season)) == int('%01d' % int(i['season']))]
            items = [{'label': '%s S%02dE%02d' % (tvshowtitle, int(i['season']), int(i['episode'])), 'season': int('%01d' % int(i['season'])), 'episode': int('%01d' % int(i['episode'])), 'unaired': i['unaired']} for i in items]
            for i in range(len(items)):
                if control.monitor.abortRequested():
                    return sys.exit()
                dialog.update(int((100 / float(len(items))) * i), str(name), str(items[i]['label']))
                _season, _episode, unaired = items[i]['season'], items[i]['episode'], items[i]['unaired']
                if int(watched) == 7:
                    if not unaired == 'true':
                        bookmarks.reset(1, 1, 'episode', imdb, _season, _episode)
                else:
                    bookmarks._delete_record('episode', imdb, _season, _episode)
        else:
            seasons = episodes.seasons().get(tvshowtitle, '0', imdb, tmdb, meta=None, idx=False)
            seasons = [i['season'] for i in seasons]
            for s in seasons:
                items = episodes.episodes().get(tvshowtitle, '0', imdb, tmdb, meta=None, season=s, idx=False)
                items = [{'label': '%s S%02dE%02d' % (tvshowtitle, int(i['season']), int(i['episode'])), 'season': int('%01d' % int(i['season'])), 'episode': int('%01d' % int(i['episode'])), 'unaired': i['unaired']} for i in items]
                for i in range(len(items)):
                    if control.monitor.abortRequested():
                        return sys.exit()
                    dialog.update(int((100 / float(len(items))) * i), str(name), str(items[i]['label']))
                    _season, _episode, unaired = items[i]['season'], items[i]['episode'], items[i]['unaired']
                    if int(watched) == 7:
                        if not unaired == 'true':
                            bookmarks.reset(1, 1, 'episode', imdb, _season, _episode)
                    else:
                        bookmarks._delete_record('episode', imdb, _season, _episode)
        try:
            dialog.close()
        except:
            pass
    except:
        try:
            dialog.close()
        except:
            pass
    try:
        if provider == 'trakt':
            if season:
                if int(watched) == 7:
                    trakt.markSeasonAsWatched(imdb, season, tmdb=tmdb)
                else:
                    trakt.markSeasonAsNotWatched(imdb, season, tmdb=tmdb)
            else:
                if int(watched) == 7:
                    trakt.markTVShowAsWatched(imdb, tmdb=tmdb)
                else:
                    trakt.markTVShowAsNotWatched(imdb, tmdb=tmdb)
            trakt.cachesyncTVShows()
        elif provider == 'simkl':
            if season:
                from resources.lib.indexers import episodes
                items = episodes.episodes().get(tvshowtitle, '0', imdb, tmdb, meta=None, season=season, idx=False)
                items = [(int(i['season']), int(i['episode'])) for i in items]
                items = [i[1] for i in items if int('%01d' % int(season)) == int('%01d' % i[0])]
                for i in items:
                    if int(watched) == 7:
                        simkl.markEpisodeAsWatched(imdb, season, i, tmdb=tmdb)
                    else:
                        simkl.markEpisodeAsNotWatched(imdb, season, i, tmdb=tmdb)
            else:
                if int(watched) == 7:
                    simkl.markTVShowAsWatched(imdb, tmdb=tmdb)
                else:
                    simkl.markTVShowAsNotWatched(imdb, tmdb=tmdb)
            simkl.cachesyncTVShows(timeout=0)
        elif provider == 'mdblist':
            if season:
                from resources.lib.indexers import episodes
                items = episodes.episodes().get(tvshowtitle, '0', imdb, tmdb, meta=None, season=season, idx=False)
                items = [(int(i['season']), int(i['episode'])) for i in items]
                items = [i[1] for i in items if int('%01d' % int(season)) == int('%01d' % i[0])]
                for i in items:
                    if int(watched) == 7:
                        mdblist.markEpisodeAsWatched(imdb, season, i, tmdb=tmdb)
                    else:
                        mdblist.markEpisodeAsNotWatched(imdb, season, i, tmdb=tmdb)
            else:
                if int(watched) == 7:
                    mdblist.markTVShowAsWatched(imdb, tmdb=tmdb)
                else:
                    mdblist.markTVShowAsNotWatched(imdb, tmdb=tmdb)
            mdblist.cachesyncTVShows(timeout=0)
    except:
        pass
    _finish_manual_mark(watched)
