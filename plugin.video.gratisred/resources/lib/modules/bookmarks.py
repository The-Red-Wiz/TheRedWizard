# -*- coding: utf-8 -*-

try:
    from sqlite3 import dbapi2 as database
except:
    from pysqlite2 import dbapi2 as database

from resources.lib.modules import control
from resources.lib.modules import trakt
from resources.lib.modules import trakt_cache


def _indicators():
    control.makeFile(control.dataPath)
    dbcon = database.connect(control.bookmarksFile)
    dbcur = dbcon.cursor()
    dbcur.execute("SELECT * FROM bookmarks WHERE overlay = 7")
    match = dbcur.fetchall()
    if match:
        return [i[2] for i in match]
    dbcon.commit()


def _get_watched(media_type, imdb, season, episode):
    sql_select = "SELECT * FROM bookmarks WHERE imdb = '%s' AND overlay = 7" % imdb
    if media_type == 'episode':
        sql_select += " AND season = '%s' AND episode = '%s'" % (season, episode)
    control.makeFile(control.dataPath)
    dbcon = database.connect(control.bookmarksFile)
    dbcur = dbcon.cursor()
    dbcur.execute(sql_select)
    match = dbcur.fetchone()
    if match:
        return 7
    else:
        return 6
    dbcon.commit()


def _update_watched(media_type, new_value, imdb, season, episode):
    sql_update = "UPDATE bookmarks SET overlay = %s WHERE imdb = '%s'" % (new_value, imdb)
    if media_type == 'episode':
        sql_update += " AND season = '%s' AND episode = '%s'" % (season, episode)
    dbcon = database.connect(control.bookmarksFile)
    dbcur = dbcon.cursor()
    dbcur.execute(sql_update)
    dbcon.commit()


def _delete_record(media_type, imdb, season, episode):
    sql_delete = "DELETE FROM bookmarks WHERE imdb = '%s'" % imdb
    if media_type == 'episode':
        sql_delete += " AND season = '%s' AND episode = '%s'" % (season, episode)
    dbcon = database.connect(control.bookmarksFile)
    dbcur = dbcon.cursor()
    dbcur.execute(sql_delete)
    dbcon.commit()


def _runtime_minutes(*candidates):
    for value in candidates:
        try:
            if value in (None, '', 0, '0'):
                continue
            runtime = float(value)
            if runtime > 0:
                return runtime
        except Exception:
            pass
    return 0


def _ids_match(imdb_n, tmdb_n, item_imdb, item_tmdb):
    imdb_ok = imdb_n not in ('0', '') and item_imdb not in ('0', '') and imdb_n == item_imdb
    tmdb_ok = tmdb_n not in ('0', '') and item_tmdb not in ('0', '') and tmdb_n == item_tmdb
    return imdb_ok or tmdb_ok


def _simkl_resume(media_type, imdb, season, episode, tmdb=None):
    """Return (offset_seconds, progress_percent). Seconds may be 0 when runtime unknown."""
    from resources.lib.modules import simkl
    if not simkl.getSimklCredentialsInfo():
        return 0, 0
    try:
        imdb_n = simkl._normalize_imdb(imdb)
        tmdb_n = str(tmdb or '0')
        media_filter = 'episodes' if media_type == 'episode' else 'movies'
        for item in simkl.get_playback(media_filter):
            try:
                progress = float(item.get('progress') or 0)
            except Exception:
                continue
            if not (1 < progress < 92):
                continue
            if media_type == 'episode':
                show = item.get('show') or {}
                ep = item.get('episode') or {}
                ids = show.get('ids') or {}
                try:
                    if int(season) != int(ep.get('season')):
                        continue
                    if int(episode) != int(ep.get('number') or ep.get('episode') or -1):
                        continue
                except Exception:
                    continue
                if not _ids_match(imdb_n, tmdb_n, simkl._normalize_imdb(ids.get('imdb')), str(ids.get('tmdb') or '0')):
                    continue
                runtime = _runtime_minutes(ep.get('runtime'), show.get('runtime'), item.get('runtime'))
            else:
                movie = item.get('movie') or item
                ids = movie.get('ids') or {}
                if not _ids_match(imdb_n, tmdb_n, simkl._normalize_imdb(ids.get('imdb')), str(ids.get('tmdb') or '0')):
                    continue
                runtime = _runtime_minutes(movie.get('runtime'), item.get('runtime'))
            if runtime:
                return (float(progress) / 100.0) * runtime * 60.0, progress
            return 0, progress
    except Exception:
        pass
    return 0, 0


def _mdblist_resume(media_type, imdb, season, episode, tmdb=None):
    from resources.lib.modules import mdblist
    if not mdblist.getMdblistCredentialsInfo():
        return 0, 0
    try:
        imdb_n = mdblist._normalize_imdb(imdb)
        tmdb_n = str(tmdb or '0')
        media_filter = 'episodes' if media_type == 'episode' else 'movies'
        for item in mdblist.get_playback(media_filter):
            try:
                progress = float(item.get('progress') or 0)
            except Exception:
                continue
            if not (1 < progress < 92):
                continue
            if media_type == 'episode':
                show = item.get('show') or {}
                ep = item.get('episode') or {}
                ids = show.get('ids') or {}
                try:
                    if int(season) != int(ep.get('season')):
                        continue
                    if int(episode) != int(ep.get('number') or ep.get('episode') or -1):
                        continue
                except Exception:
                    continue
                if not _ids_match(imdb_n, tmdb_n, mdblist._normalize_imdb(ids.get('imdb')), str(ids.get('tmdb') or show.get('tmdb') or '0')):
                    continue
                runtime = _runtime_minutes(ep.get('runtime'), show.get('runtime'), item.get('runtime'))
            else:
                movie = item.get('movie') or item
                ids = movie.get('ids') or {}
                if not _ids_match(imdb_n, tmdb_n, mdblist._normalize_imdb(ids.get('imdb')), str(ids.get('tmdb') or movie.get('tmdb') or '0')):
                    continue
                runtime = _runtime_minutes(movie.get('runtime'), item.get('runtime'))
            if runtime:
                return (float(progress) / 100.0) * runtime * 60.0, progress
            return 0, progress
    except Exception:
        pass
    return 0, 0


def get_resume(media_type, imdb, season, episode, local=False, tmdb=None):
    """Return (offset_seconds, progress_percent). Percent is for Simkl when runtime is unknown."""
    source = control.setting('bookmarks.source')
    if source == '1' and trakt.getTraktCredentialsInfo() == True and local == False:
        try:
            offset = 0
            if media_type == 'episode':
                traktInfo = trakt_cache.get(trakt.getPlaybackEpisodes, trakt_cache.TTL_HISTORY_SEC) or []
                for i in traktInfo:
                    if imdb == i['show']['ids']['imdb']:
                        if int(season) == i['episode']['season'] and int(episode) == i['episode']['number']:
                            seekable = 1 < i['progress'] < 92
                            if seekable:
                                offset = (float(i['progress'] / 100) * int(i['episode']['runtime']) * 60)
                            else:
                                offset = 0
                            return offset, float(i.get('progress') or 0) if seekable else 0
            else:
                traktInfo = trakt_cache.get(trakt.getPlaybackMovies, trakt_cache.TTL_HISTORY_SEC) or []
                for i in traktInfo:
                    if imdb == i['movie']['ids']['imdb']:
                        seekable = 1 < i['progress'] < 92
                        if seekable:
                            offset = (float(i['progress'] / 100) * int(i['movie']['runtime']) * 60)
                        else:
                            offset = 0
                        return offset, float(i.get('progress') or 0) if seekable else 0
            return offset, 0
        except:
            return 0, 0
    if source == '2' and local == False:
        from resources.lib.modules import simkl
        if simkl.getSimklCredentialsInfo():
            return _simkl_resume(media_type, imdb, season, episode, tmdb=tmdb)
    if source == '3' and local == False:
        from resources.lib.modules import mdblist
        if mdblist.getMdblistCredentialsInfo():
            return _mdblist_resume(media_type, imdb, season, episode, tmdb=tmdb)
    try:
        sql_select = "SELECT * FROM bookmarks WHERE imdb = '%s'" % imdb
        if media_type == 'episode':
            sql_select += " AND season = '%s' AND episode = '%s'" % (season, episode)
        control.makeFile(control.dataPath)
        dbcon = database.connect(control.bookmarksFile)
        dbcur = dbcon.cursor()
        dbcur.execute("CREATE TABLE IF NOT EXISTS bookmarks (""timeInSeconds TEXT, ""type TEXT, ""imdb TEXT, ""season TEXT, ""episode TEXT, ""playcount INTEGER, ""overlay INTEGER, ""UNIQUE(imdb, season, episode)"");")
        dbcur.execute(sql_select)
        match = dbcur.fetchone()
        if match:
            offset = match[0]
            return float(offset), 0
        else:
            return 0, 0
        dbcon.commit()
    except:
        return 0, 0


def get(media_type, imdb, season, episode, local=False, tmdb=None):
    offset, _percent = get_resume(media_type, imdb, season, episode, local=local, tmdb=tmdb)
    return offset


def reset(current_time, total_time, media_type, imdb, season='', episode=''):
    try:
        _playcount = 0
        overlay = 6
        timeInSeconds = str(current_time)
        ok = int(current_time) > 120 and (current_time / total_time) < .92
        watched = (current_time / total_time) >= .92
        sql_select = "SELECT * FROM bookmarks WHERE imdb = '%s'" % imdb
        if media_type == 'episode':
            sql_select += " AND season = '%s' AND episode = '%s'" % (season, episode)
        sql_update = "UPDATE bookmarks SET timeInSeconds = '%s' WHERE imdb = '%s'" % (timeInSeconds, imdb)
        if media_type == 'episode':
            sql_update += " AND season = '%s' AND episode = '%s'" % (season, episode)
        if media_type == 'movie':
            sql_update_watched = "UPDATE bookmarks SET timeInSeconds = '0', playcount = %s, overlay = %s WHERE imdb = '%s'" % ('%s', '%s', imdb)
        elif media_type == 'episode':
            sql_update_watched = "UPDATE bookmarks SET timeInSeconds = '0', playcount = %s, overlay = %s WHERE imdb = '%s' AND season = '%s' AND episode = '%s'" % ('%s', '%s', imdb, season, episode)
        if media_type == 'movie':
            sql_insert = "INSERT INTO bookmarks Values ('%s', '%s', '%s', '', '', '%s', '%s')" % (timeInSeconds, media_type, imdb, _playcount, overlay)
        elif media_type == 'episode':
            sql_insert = "INSERT INTO bookmarks Values ('%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (timeInSeconds, media_type, imdb, season, episode, _playcount, overlay)
        if media_type == 'movie':
            sql_insert_watched = "INSERT INTO bookmarks Values ('%s', '%s', '%s', '', '', '%s', '%s')" % (timeInSeconds, media_type, imdb, '%s', '%s')
        elif media_type == 'episode':
            sql_insert_watched = "INSERT INTO bookmarks Values ('%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (timeInSeconds, media_type, imdb, season, episode, '%s', '%s')
        control.makeFile(control.dataPath)
        dbcon = database.connect(control.bookmarksFile)
        dbcur = dbcon.cursor()
        dbcur.execute("CREATE TABLE IF NOT EXISTS bookmarks (""timeInSeconds TEXT, ""type TEXT, ""imdb TEXT, ""season TEXT, ""episode TEXT, ""playcount INTEGER, ""overlay INTEGER, ""UNIQUE(imdb, season, episode)"");")
        dbcur.execute(sql_select)
        match = dbcur.fetchone()
        if match:
            if ok:
                dbcur.execute(sql_update)
            elif watched:
                _playcount = match[5] + 1
                overlay = 7
                dbcur.execute(sql_update_watched % (_playcount, overlay))
        else:
            if ok:
                dbcur.execute(sql_insert)
            elif watched:
                _playcount = 1
                overlay = 7
                dbcur.execute(sql_insert_watched % (_playcount, overlay))
        dbcon.commit()
    except:
        pass
