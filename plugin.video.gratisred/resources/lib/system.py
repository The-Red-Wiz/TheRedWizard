# -*- coding: utf-8 -*-

from six.moves.urllib_parse import parse_qsl


def router(_argv):
    params = dict(parse_qsl(_argv.replace('?', '')))
    action = params.get('action')
    select = params.get('select')
    url = params.get('url')
    query = params.get('query')
    id = params.get('id')
    setting = params.get('setting')
    source = params.get('source')
    content = params.get('content')
    image = params.get('image')
    meta = params.get('meta')
    item = params.get('item')
    imdb = params.get('imdb')
    tmdb = params.get('tmdb')
    tvdb = params.get('tvdb')
    name = params.get('name')
    title = params.get('title')
    tvshowtitle = params.get('tvshowtitle')
    season = params.get('season')
    episode = params.get('episode')
    year = params.get('year')
    premiered = params.get('premiered')
    windowedtrailer = params.get('windowedtrailer')
    windowedtrailer = int(windowedtrailer) if windowedtrailer in ("0", "1") else 0


    if action == None:
        #from resources.lib.modules import cache
        from resources.lib.indexers import navigator
        #cache.cache_version_check()
        navigator.navigator().root()


    elif action == 'open_root':
        from resources.lib.indexers import navigator
        navigator.navigator().root()


    elif action == 'add_item':
        from resources.lib.modules import sources
        sources.sources().addItem(title)


    elif action == 'add_view':
        from resources.lib.modules import views
        views.addView(views.normalize_view_content(content))


    elif action == 'alter_sources':
        from resources.lib.modules import sources
        sources.sources().alterSources(url, meta)


    elif action == 'artwork':
        from resources.lib.modules import control
        control.artwork()


    elif action == 'auth_tmdb':
        from resources.lib.modules import tmdb_utils
        reopen = (params.get('source') or '').lower() == 'settings'
        tmdb_utils.authTMDb(reopen_settings=reopen)


    elif action == 'revoke_tmdb':
        from resources.lib.modules import tmdb_utils
        reopen = (params.get('source') or '').lower() == 'settings'
        tmdb_utils.delete_session(reopen_settings=reopen)


    elif action == 'auth_trakt':
        from resources.lib.modules import trakt
        reopen = (params.get('source') or '').lower() == 'settings'
        trakt.authTrakt(reopen_settings=reopen)


    elif action == 'revoke_trakt':
        from resources.lib.modules import trakt
        reopen = (params.get('source') or '').lower() == 'settings'
        trakt.revokeTrakt(reopen_settings=reopen)


    elif action == 'auth_simkl':
        from resources.lib.modules import simkl
        reopen = (params.get('source') or '').lower() == 'settings'
        simkl.authSimkl(reopen_settings=reopen)


    elif action == 'revoke_simkl':
        from resources.lib.modules import simkl
        reopen = (params.get('source') or '').lower() == 'settings'
        simkl.revokeSimkl(reopen_settings=reopen)


    elif action == 'refresh_simkl_cache':
        from resources.lib.modules import simkl
        simkl.refreshSimklCache()


    elif action == 'auth_mdblist':
        from resources.lib.modules import mdblist
        reopen = (params.get('source') or '').lower() == 'settings'
        mdblist.authMdblist(reopen_settings=reopen)


    elif action == 'revoke_mdblist':
        from resources.lib.modules import mdblist
        reopen = (params.get('source') or '').lower() == 'settings'
        mdblist.revokeMdblist(reopen_settings=reopen)


    elif action == 'refresh_mdblist_cache':
        from resources.lib.modules import mdblist
        mdblist.refreshMdblistCache()


    elif action == 'mdblist_list_sort':
        from resources.lib.modules import mdblist
        mdblist.choose_list_sort(params.get('media'), params.get('status'), label=params.get('label'))


    elif action == 'simkl_list_sort':
        from resources.lib.modules import simkl
        simkl.choose_list_sort(params.get('media'), params.get('status'))


    elif action == 'trakt_list_sort':
        from resources.lib.modules import trakt
        trakt.choose_list_sort(params.get('media'), params.get('status'), label=params.get('label'))


    elif action == 'tmdb_list_sort':
        from resources.lib.modules import tmdb_utils
        tmdb_utils.choose_list_sort(params.get('media'), params.get('status'), label=params.get('label'))


    elif action == 'choose_indicators':
        from resources.lib.modules import simkl
        reopen = (params.get('source') or '').lower() == 'settings'
        simkl.choose_indicators(reopen_settings=reopen)


    elif action == 'my_simkl_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mysimkl()


    elif action == 'my_simkl_movies_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mysimklmovies()


    elif action == 'my_simkl_tvshows_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mysimkltvshows()


    elif action == 'my_mdblist_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mymdblist()


    elif action == 'my_mdblist_movies_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mymdblistmovies()


    elif action == 'my_mdblist_tvshows_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mymdblisttvshows()


    elif action == 'opensubs_check':
        from resources.lib.apis import opensubs_api
        reopen = (params.get('source') or '').lower() == 'settings'
        opensubs_api.check_account(reopen_settings=reopen)


    elif action == 'movie_from_library':
        from resources.lib.modules import libtools
        libtools.libmovies().remove(title, year, imdb)


    elif action == 'movie_refresh_library':
        from resources.lib.modules import libtools
        libtools.libmovies().refresh(name, title, year, imdb)


    elif action == 'tvshow_from_library':
        from resources.lib.modules import libtools
        libtools.libtvshows().remove(tvshowtitle, year, imdb, tmdb)


    elif action == 'tvshow_refresh_library':
        from resources.lib.modules import libtools
        libtools.libtvshows().refresh(tvshowtitle, year, imdb, tmdb)


    elif action == 'calendar':
        from resources.lib.indexers import episodes
        episodes.episodes().calendar(url)


    elif action == 'calendars':
        from resources.lib.indexers import episodes
        episodes.episodes().calendars()


    elif action == 'clean_settings':
        from resources.lib.indexers import navigator
        navigator.navigator().cleanSettings()


    elif action == 'cleantools_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().cleantools()


    elif action == 'cleantools_widget':
        from resources.lib.indexers import navigator
        navigator.navigator().cleantools_widget()


    elif action == 'clear_all_cache':
        from resources.lib.indexers import navigator
        navigator.navigator().clearCacheAll()


    elif action == 'clear_cache':
        from resources.lib.indexers import navigator
        navigator.navigator().clearCache()


    elif action == 'clear_debuglog':
        from resources.lib.indexers import navigator
        navigator.navigator().clearDebugLog()


    elif action == 'clear_meta_cache':
        from resources.lib.indexers import navigator
        navigator.navigator().clearCacheMeta()


    elif action == 'clear_resolveurl_cache':
        from resources.lib.modules import control
        control.execute('RunPlugin(plugin://script.module.resolveurl/?mode=reset_cache)')


    elif action == 'clear_search_cache':
        from resources.lib.indexers import navigator
        navigator.navigator().clearCacheSearch(select)


    elif action == 'clear_sources':
        from resources.lib.indexers import navigator
        navigator.navigator().clearCacheProviders()


    elif action == 'refresh_trakt_cache':
        # Wired to the "Refresh Trakt Cache" entry at the bottom of the
        # My Trakt menu (see indexers/navigator.py mytrakt()).  Drops
        # only the 5 min short-TTL ``trakt_cache`` table so users can
        # manually resync when Trakt upstream changes something (new
        # list, renamed list, removed favourite, ...) without waiting
        # for the TTL or blowing away the 12h TMDb / meta caches.
        from resources.lib.indexers import navigator
        navigator.navigator().refreshTraktCache()


    elif action == 'clear_viewtypes':
        from resources.lib.indexers import navigator
        navigator.navigator().clearViewTypes()


    elif action == 'color_choice':
        from resources.lib.modules import colorcode
        colorcode.colorChoice(setting, query)


    elif action == 'devtools_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().devtools()


    elif action == 'disable_all':
        from resources.lib.modules import sources
        sources.sources().disableAll()


    elif action == 'download':
        import simplejson as json
        from resources.lib.modules import downloader
        from resources.lib.modules import sources
        downloader.download(name, image, sources.sources().sourcesResolve(json.loads(source)[0], True))


    elif action == 'download_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().downloads()


    elif action == 'enable_all':
        from resources.lib.modules import sources
        sources.sources().enableAll()


    elif action == 'episode_widget':
        from resources.lib.indexers import episodes
        episodes.episodes().widget()


    elif action == 'episodes':
        from resources.lib.indexers import episodes
        episodes.episodes().get(tvshowtitle, year, imdb, tmdb, meta, season, episode)


    elif action == 'episodes_playcount':
        from resources.lib.modules import playcount
        playcount.episodes(imdb, tmdb, season, episode, query)


    elif action == 'episodes_userlists':
        from resources.lib.indexers import episodes
        episodes.episodes().userlists()


    elif action == 'library_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().library()


    elif action == 'library_movies':
        from resources.lib.indexers import movies
        movies.movies().local_library()


    elif action == 'library_tvshows':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().local_library()


    elif action == 'moreplugs_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().moreplugs()


    elif action == 'movie_to_library':
        from resources.lib.modules import libtools
        libtools.libmovies().add(name, title, year, imdb, tmdb)


    elif action == 'movies':
        from resources.lib.indexers import movies
        movies.movies().get(url)


    elif action == 'movies_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().movies()


    elif action == 'movies_playcount':
        from resources.lib.modules import playcount
        playcount.movies(imdb, query, tmdb=tmdb)


    elif action == 'movies_tmdb_certifications':
        from resources.lib.indexers import movies
        movies.movies().tmdb_certifications()


    elif action == 'movies_tmdb_collections_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tmdbMovieCollections()


    elif action == 'movies_tmdb_collections_alphabetical_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tmdbMovieCollectionsAlphabetical()


    elif action == 'movies_tmdb_collections_genres_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tmdbMovieCollectionsGenres()


    elif action == 'movies_tmdb_collections_genres':
        from resources.lib.indexers import movies
        movies.movies().tmdb_collections_genres(url)


    elif action == 'movies_tmdb_collections':
        from resources.lib.indexers import movies
        movies.movies().tmdb_collections(url)


    elif action == 'movies_tmdb_years':
        from resources.lib.indexers import movies
        movies.movies().tmdb_years()


    elif action == 'movies_tmdb_decades':
        from resources.lib.indexers import movies
        movies.movies().tmdb_decades()


    elif action == 'movies_tmdb_genres':
        from resources.lib.indexers import movies
        movies.movies().tmdb_genres()


    elif action == 'movies_tmdb_languages':
        from resources.lib.indexers import movies
        movies.movies().tmdb_languages()


    elif action == 'movies_tmdb_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().movieTMDb()


    elif action == 'movies_tmdb_popular_companies':
        from resources.lib.indexers import movies
        movies.movies().tmdb_popular_companies()


    elif action == 'movies_tmdb_popular_keywords':
        from resources.lib.indexers import movies
        movies.movies().tmdb_popular_keywords()


    elif action == 'movies_tmdb_popular_people':
        from resources.lib.indexers import movies
        movies.movies().tmdb_popular_people()


    elif action == 'movies_search':
        from resources.lib.indexers import movies
        movies.movies().search_term_menu(select)


    elif action == 'movies_searchterm':
        from resources.lib.indexers import movies
        movies.movies().search_term(select, name)


    elif action == 'movies_tmdb_userlists':
        from resources.lib.indexers import movies
        movies.movies().tmdb_userlists_list(url)


    elif action == 'movies_tmdb_userlists_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tmdbMovieLists()


    elif action == 'movies_to_library':
        from resources.lib.modules import libtools
        libtools.libmovies().range(url)


    elif action == 'movies_to_library_silent':
        from resources.lib.modules import libtools
        libtools.libmovies().silent(url)


    elif action == 'movies_trakt_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().movieTrakt()


    elif action == 'movies_simkl_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().movieSimkl()


    elif action == 'movies_trakt_moviemosts':
        from resources.lib.indexers import navigator
        navigator.navigator().movieMosts()


    elif action == 'movies_userlists_trakt':
        from resources.lib.indexers import movies
        movies.movies().userlists_trakt()


    elif action == 'movies_userlists_trakt_liked':
        from resources.lib.indexers import movies
        movies.movies().userlists_trakt_liked()


    elif action == 'movies_userlists_tmdb':
        from resources.lib.indexers import movies
        movies.movies().userlists_tmdb()


    elif action == 'movies_userlists_mdblist':
        from resources.lib.indexers import movies
        movies.movies().userlists_mdblist()


    elif action == 'movies_userlists_mdblist_liked':
        from resources.lib.indexers import movies
        movies.movies().userlists_mdblist_liked()


    elif action == 'movies_userlists_mdblist_top':
        from resources.lib.indexers import movies
        movies.movies().userlists_mdblist_top()


    elif action == 'my_tmdb_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mytmdb()


    elif action == 'my_tmdb_movies_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mytmdbmovies()


    elif action == 'my_tmdb_tvshows_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mytmdbtvshows()


    elif action == 'my_trakt_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mytrakt()


    elif action == 'my_trakt_movies_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mytraktmovies()


    elif action == 'my_trakt_tvshows_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mytrakttvshows()


    elif action == 'my_userlists_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().myuserlists()


    elif action == 'my_userlists_movies_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().myuserlistsmovies()


    elif action == 'my_userlists_tvshows_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().myuserliststvshows()


    elif action == 'mylists_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().mylists()


    elif action == 'open_resolveurl_settings':
        import resolveurl
        resolveurl.display_settings()


    elif action == 'open_settings':
        from resources.lib.modules import control
        control.openSettings(query, id)


    elif action == 'play':
        from resources.lib.modules import sources
        sources.sources().play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select)


    elif action == 'play_item':
        from resources.lib.modules import sources
        sources.sources().playItem(title, source)


    elif action == 'queue_item':
        from resources.lib.modules import control
        control.queueItem()


    elif action == 'search_movies_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().search_movies()


    elif action == 'search_tvshows_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().search_tvshows()


    elif action == 'seasons':
        from resources.lib.indexers import episodes
        episodes.seasons().get(tvshowtitle, year, imdb, tmdb, meta)


    elif action == 'service':
        from resources.lib.modules import libtools
        libtools.libepisodes().service()


    elif action == 'scraper_test':
        from resources.lib.modules import scraper_tester
        scraper_tester.test_all()


    elif action == 'scraper_test_one':
        from resources.lib.modules import scraper_tester
        scraper_tester.test_one()


    elif action == 'show_changelog':
        from resources.lib.modules import changelog_notice
        changelog_notice.show(force=True, auto_dismiss=True)


    elif action == 'dismiss_changelog':
        from resources.lib.modules import changelog_notice
        changelog_notice.dismiss_only()
        from resources.lib.modules import control
        try:
            control.execute('Container.Refresh')
        except Exception:
            pass


    elif action == 'tools_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tools()


    elif action == 'tmdb_manager':
        from resources.lib.modules import tmdb_utils
        tmdb_utils.manager(name, imdb, tmdb, content)


    elif action == 'trakt_manager':
        from resources.lib.modules import trakt
        trakt.manager(name, imdb, tmdb, content)


    elif action == 'simkl_manager':
        from resources.lib.modules import simkl
        simkl.manager(name, imdb, tmdb, content)


    elif action == 'mdblist_manager':
        from resources.lib.modules import mdblist
        mdblist.manager(name, imdb, tmdb, content)


    elif action == 'tvshow_to_library':
        from resources.lib.modules import libtools
        libtools.libtvshows().add(tvshowtitle, year, imdb, tmdb)


    elif action == 'tvshows':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().get(url)


    elif action == 'tvshows_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tvshows()


    elif action == 'tvshows_tvmaze_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tvTVmaze()


    elif action == 'tvshows_playcount':
        from resources.lib.modules import playcount
        playcount.tvshows(name, imdb, tmdb, season, query)


    elif action == 'tvshows_tmdb_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tvTMDb()


    elif action == 'tvshows_tmdb_networks':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdb_networks()


    elif action == 'tvshows_tmdb_genres':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdb_genres()


    elif action == 'tvshows_tmdb_languages':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdb_languages()


    elif action == 'tvshows_tmdb_years':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdb_years()


    elif action == 'tvshows_tmdb_decades':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdb_decades()


    elif action == 'tvshows_tmdb_popular_companies':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdb_popular_companies()


    elif action == 'tvshows_tmdb_popular_keywords':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdb_popular_keywords()


    elif action == 'tvshows_tmdb_popular_people':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdb_popular_people()


    elif action == 'tvshows_search':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().search_term_menu(select)


    elif action == 'tvshows_searchterm':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().search_term(select, name)


    elif action == 'tvshows_tmdb_userlists':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tmdbTvLists()


    elif action == 'tvshows_tmdb_userlists_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tmdbShowLists()


    elif action == 'tvshows_to_library':
        from resources.lib.modules import libtools
        libtools.libtvshows().range(url)


    elif action == 'tvshows_to_library_silent':
        from resources.lib.modules import libtools
        libtools.libtvshows().silent(url)


    elif action == 'tvshows_trakt_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tvTrakt()


    elif action == 'tvshows_simkl_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tvSimkl()


    elif action == 'tvshows_trakt_showmosts':
        from resources.lib.indexers import navigator
        navigator.navigator().showMosts()


    elif action == 'tvshows_tvmaze_networks':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tvmaze_networks()


    elif action == 'tvshows_tvmaze_webchannels':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tvmaze_webchannels()


    elif action == 'tvshows_tvmaze_genres':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tvmaze_genres()


    elif action == 'tvshows_tvmaze_countries':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().tvmaze_countries()


    elif action == 'tvshows_tvmaze_updates_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().tvTVmazeUpdates()


    elif action == 'tvshows_userlists_trakt':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().userlists_trakt()


    elif action == 'tvshows_userlists_trakt_liked':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().userlists_trakt_liked()


    elif action == 'tvshows_userlists_tmdb':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().userlists_tmdb()


    elif action == 'tvshows_userlists_mdblist':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().userlists_mdblist()


    elif action == 'tvshows_userlists_mdblist_liked':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().userlists_mdblist_liked()


    elif action == 'tvshows_userlists_mdblist_top':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().userlists_mdblist_top()


    elif action == 'update_library':
        from resources.lib.modules import libtools
        libtools.libepisodes().update(query)


    elif action == 'changelog':
        from resources.lib.modules import log_utils
        log_utils.changelog()


    elif action == 'view_debuglog':
        from resources.lib.modules import log_utils
        log_utils.view_log()


    elif action == 'views_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().views_menu()


    elif action == 'views_pick':
        from resources.lib.indexers import navigator
        navigator.navigator().views_pick(content)


    elif action == 'trailer':
        from resources.lib.modules import control
        if not control.condVisibility('System.HasAddon(plugin.video.youtube)'):
            control.installAddon('plugin.video.youtube')
        from resources.lib.modules import trailer
        trailer.source().get(name, url, tmdb, imdb, season, episode, windowedtrailer)


    elif action == 'sky_channels_menu':
        from resources.lib.indexers.plugins import channels
        channels.channels().get()


    elif action == 'tvpassport_menu':
        from resources.lib.indexers.plugins import tvpassport
        tvpassport.listings().root()


    elif action == 'tvpassport_movies_today_list':
        from resources.lib.indexers.plugins import tvpassport
        tvpassport.listings().movies_today_list(url)


    elif action == 'tvpassport_stations_movies_list':
        from resources.lib.indexers.plugins import tvpassport
        tvpassport.listings().stations_movies_list(url)


    elif action == 'daddy_menu':
        from resources.lib.indexers.plugins import daddylive
        daddylive.listings().root()


    elif action == 'daddy_channels':
        from resources.lib.indexers.plugins import daddylive
        daddylive.listings().channels()


    elif action == 'daddy_cats':
        from resources.lib.indexers.plugins import daddylive
        from six.moves.urllib_parse import unquote_plus
        daddylive.listings().categories(unquote_plus(url))


    elif action == 'daddy_events':
        from resources.lib.indexers.plugins import daddylive
        from six.moves.urllib_parse import unquote_plus
        daddylive.listings().events(unquote_plus(url))


    elif action == 'daddy_play':
        from resources.lib.indexers.plugins import daddylive
        from six.moves.urllib_parse import unquote_plus
        daddylive.listings().play(unquote_plus(url))


    elif action == 'flixed_menu':
        from resources.lib.indexers.plugins import flixed
        flixed.listings().root()


    elif action == 'flixed_scrape_channel':
        from resources.lib.indexers.plugins import flixed
        flixed.listings().scrape_channel(url)


    elif action == 'watchonline_menu':
        from resources.lib.indexers.plugins import watchonline
        watchonline.Indexer().root()


    elif action == 'watchonline_scrape_seasons':
        from resources.lib.indexers.plugins import watchonline
        watchonline.Indexer().scrape_seasons(url)


    elif action == 'watchonline_scrape_episodes':
        from resources.lib.indexers.plugins import watchonline
        watchonline.Indexer().scrape_episodes(url)


    elif action == 'watchonline_scrape_episode':
        from resources.lib.indexers.plugins import watchonline
        watchonline.Indexer().scrape_episode(url)


    elif action == 'installs_menu':
        from resources.lib.indexers import navigator
        navigator.navigator().installsmenu()


    elif action == 'installAddon':
        from resources.lib.modules import control
        refresh_menu = params.get('refresh') == 'installs_menu'
        control.installAddon(id, refresh_menu=refresh_menu)


    elif action == 'alt_play':
        from resources.lib.modules import player
        player.playItem(url)
        #player.playMedia(url)


    elif action == 'favoritesNavigator':
        from resources.lib.indexers import navigator
        navigator.navigator().favorites()


    elif action == 'movieFavorites':
        from resources.lib.indexers import movies
        movies.movies().favorites()


    elif action == 'tvFavorites':
        from resources.lib.indexers import tvshows
        tvshows.tvshows().favorites()


    elif action == 'addFavorite':
        from resources.lib.modules import favorites
        favorites.addFavorite(meta, content)


    elif action == 'deleteFavorite':
        from resources.lib.modules import favorites
        favorites.deleteFavorite(meta, content)


    elif action == 'get_provider_domains':
        from resources.lib.modules import sources
        sources.sources().getProviderDomains()


    elif action == 'gdriveplayer.root':
        from resources.lib.indexers.plugins import gdriveplayer
        gdriveplayer.indexer().root()


    elif action == 'gdriveplayer.search':
        from resources.lib.indexers.plugins import gdriveplayer
        gdriveplayer.indexer().search(url)


    elif action == 'gdriveplayer.newest':
        from resources.lib.indexers.plugins import gdriveplayer
        gdriveplayer.indexer().newest(url)


    elif action == 'gdriveplayer.details':
        from resources.lib.indexers.plugins import gdriveplayer
        gdriveplayer.indexer().details(url, image, item)


    elif action == 'gdriveplayer.sources':
        from resources.lib.indexers.plugins import gdriveplayer
        gdriveplayer.indexer().sources(url, image)


    elif action == 'testing':
        from resources.lib.modules import log_utils
        try:
            test = []
            """ # Some saved testing items...
            Movie_imdb = 'tt0379786'
            Movie_tmdb = '16320'
            Movie_title = 'Serenity'
            Movie_year = '2005'
            TVShow_imdb = 'tt0303461'
            TVShow_tmdb = '1437'
            TVShow_title = 'Firefly'
            TVShow_year = '2002'
            TVShow_season = '1'
            TVShow_episode = '4'
            """
            
            log_utils.log('Testing - test: ' + repr(test))
        except:
            log_utils.log('Testing', 1)
            pass













