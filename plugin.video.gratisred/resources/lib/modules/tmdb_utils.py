# -*- coding: utf-8 -*-

import requests
import time
from requests.compat import json, str

from resources.lib.modules import control
from resources.lib.modules import log_utils

original_artwork = control.setting('original.artwork') or 'false'
if original_artwork == 'true':
    image_link = 'https://image.tmdb.org/t/p/original'
else:
    image_link = 'https://image.tmdb.org/t/p/w%s%s'

API_URL = 'https://api.themoviedb.org/3/'

ART_URL = 'https://image.tmdb.org/t/p/original'
HEADERS = {'Content-Type': 'application/json;charset=utf-8'}


def _tmdb_account_settings():
    return {
        'username': control.setting('tmdb.user') or '',
        'session_id': control.setting('tmdb.session') or '',
        'account_id': control.setting('tmdb.id') or '',
    }


def _tmdb_api_key():
    key = control.setting('tmdb.api')
    if not key:
        key = 'a0bf207c5ff6c0caabac0327e39b1cd2'
    return key


def unwrap_tmdb_list_item(item):
    """Normalise flat or nested TMDb list item payloads to (media_type, dict)."""
    if not isinstance(item, dict):
        return None, None
    media_type = (item.get('media_type') or '').lower()
    if media_type in ('movie', 'movies'):
        return 'movie', item
    if media_type in ('tv', 'show', 'series'):
        return 'tv', item
    for key, resolved in (('movie', 'movie'), ('tv', 'tv'), ('show', 'tv')):
        block = item.get(key)
        if isinstance(block, dict):
            payload = dict(block)
            payload.setdefault('media_type', resolved)
            return resolved, payload
    if item.get('title') or item.get('release_date'):
        return 'movie', item
    if item.get('name') or item.get('first_air_date'):
        return 'tv', item
    return None, item


def parse_genres(genres, line=True):
    new_genres = []
    try: # Made for movie collection list use.
        from resources.lib.indexers.metadata.tmdb import tmdb_various
        genre_list = tmdb_various.genre_list
        for genre in genres:
            if not genre:
                continue
            genre = '%s' % int(genre)
            new_genre = [i[0] for i in genre_list if i[1] == genre][0]
            if new_genre:
                new_genres.append(new_genre)
        if line:
            return ', '.join([i for i in new_genres])
        else:
            return new_genres
    except:
        #log_utils.log('parse_genres', 1)
        return new_genres


def getTMDbCredentialsInfo():
    s = _tmdb_account_settings()
    if s['session_id'] == '' or s['account_id'] == '':
        return False
    return True


def authTMDb(reopen_settings=False):
    from resources.lib.modules import auth_utils
    progress = None
    try:
        account = _tmdb_account_settings()
        if account['session_id'] != '':
            control.infoDialog('TMDb is already authorised. Use Revoke TMDb Account to sign out.', sound=True)
            return
        progress = auth_utils.auth_progress_dialog('TMDb Authorise', '')
        progress.update('Connecting to TMDb...')
        headers = auth_utils.tmdb_read_headers()
        response = requests.post('https://api.themoviedb.org/4/auth/request_token', headers=headers, timeout=20)
        data = response.json()
        if not data.get('success') or not data.get('request_token'):
            raise Exception('request_token failed')
        request_token = data['request_token']
        auth_url = 'https://www.themoviedb.org/auth/access?request_token=%s' % request_token
        progress.update('Preparing QR code...')
        qr_code = auth_utils.make_qrcode(auth_url) or ''
        short_url = auth_utils.make_tinyurl(auth_url)
        auth_utils.copy2clip(auth_url)
        insert = '[CR]OR visit [B]%s[/B]' % short_url if short_url else ''
        content = ('Scan the [B]QR Code[/B]%s[CR][CR]'
                   'Confirm access at themoviedb.org[CR][CR]Waiting for authorisation...' % insert)
        progress.update(content, qr_path=qr_code)
        expires_in = 180
        poll_interval = 2.5
        success = None
        start = time.time()
        while not progress.iscanceled() and (time.time() - start) < expires_in and success is None:
            if auth_utils.auth_progress_wait(progress, poll_interval):
                break
            try:
                poll = requests.post('https://api.themoviedb.org/4/auth/access_token',
                    json={'request_token': request_token}, headers=headers, timeout=20).json()
                if poll.get('success') and poll.get('access_token'):
                    success = poll
                    break
            except Exception:
                pass
        canceled = progress.iscanceled()
        auth_utils.close_auth_progress_dialog(progress)
        progress = None
        if canceled or not success:
            control.infoDialog('TMDb Auth Canceled.' if canceled else 'TMDb Auth Failed.', sound=True)
            return
        access_token = success['access_token']
        convert = requests.post('https://api.themoviedb.org/3/authentication/session/convert/4',
            json={'access_token': access_token}, headers=headers, timeout=20).json()
        session_id = convert.get('session_id')
        if not convert.get('success') or not session_id:
            raise Exception('session convert failed')
        account_info = requests.get('https://api.themoviedb.org/3/account',
            params={'session_id': session_id}, headers=headers, timeout=20).json()
        control.setSetting('tmdb.session', session_id)
        control.setSetting('tmdb.id', str(account_info.get('id', '')))
        control.setSetting('tmdb.user', str(account_info.get('username', '')))
        control.infoDialog('TMDb Auth Successful.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
        return
    except Exception:
        control.infoDialog('TMDb Auth Failed.', sound=True)
        return
    finally:
        if progress is not None:
            auth_utils.close_auth_progress_dialog(progress)


def delete_session(reopen_settings=False):
    account = _tmdb_account_settings()
    if account['session_id'] == '':
        control.infoDialog('No TMDb account is authorised.', sound=True)
        return
    try:
        url = API_URL + 'authentication/session?api_key=%s' % _tmdb_api_key()
        post = {"session_id": "%s" % str(account['session_id'])}
        result = requests.delete(url, data=json.dumps(post), headers=HEADERS).json()
        if not result.get('success') is True:
            log_utils.log('TMDb delete_session API failed: %s' % result, 1)
    except Exception as e:
        log_utils.log('TMDb delete_session API error: %s' % e, 1)
    control.setSetting('tmdb.session', '')
    control.setSetting('tmdb.id', '')
    control.setSetting('tmdb.user', '')
    control.infoDialog('TMDb Account Revoked.', sound=True)
    control.finish_auth_ui(reopen_settings=reopen_settings)


def get_account_details(session_id):
    try:
        url = API_URL + 'account?api_key=%s&session_id=%s' % (_tmdb_api_key(), session_id)
        result = requests.get(url, headers=HEADERS).json()
        account_username = result['username']
        account_name = result['name']
        account_id = result['id']
        account_include_adult = result['include_adult']
        account_iso_639_1 = result['iso_639_1']
        account_iso_3166_1 = result['iso_3166_1']
        control.setSetting('tmdb.id', str(account_id))
        message = ('username: %s' % str(account_username) + '[CR]' + 'name: %s' % str(account_name) + '[CR]' + 'id: %s' % str(account_id) + '[CR]' + 'include_adult: %s' % str(account_include_adult) + '[CR]' + 'iso_639_1: %s' % str(account_iso_639_1) + '[CR]' + 'iso_3166_1: %s' % str(account_iso_3166_1))
        return control.okDialog(message, heading='TMDB Account Details')
    except:
        #log_utils.log('get_account_details', 1)
        pass


def _tmdb_guess_list_type_from_name(name):
    name = (name or '').lower()
    if any(token in name for token in ('tv show', 'tv shows', 'series', 'television')):
        return 'tv'
    if 'movie' in name or 'film' in name:
        return 'movie'
    return None


def _tmdb_probe_list_type(list_id):
    try:
        list_url = API_URL + 'list/%s?api_key=%s&language=en-US&page=1' % (list_id, _tmdb_api_key())
        result = requests.get(list_url, headers=HEADERS, timeout=30).json()
        items = result.get('items') or result.get('results') or []
        has_movie = has_tv = False
        for raw in items[:12]:
            media_type, item = unwrap_tmdb_list_item(raw)
            if not item:
                continue
            if media_type == 'movie':
                has_movie = True
            elif media_type == 'tv':
                has_tv = True
        if has_tv and not has_movie:
            return 'tv'
        if has_movie and not has_tv:
            return 'movie'
        if has_tv:
            return 'tv'
        if has_movie:
            return 'movie'
    except:
        pass
    return None


def _tmdb_resolve_list_type(list_meta_type, list_id=None, list_name=None):
    list_meta_type = (list_meta_type or '').lower()
    probed = _tmdb_probe_list_type(list_id) if list_id else None
    if probed:
        return probed
    name_guess = _tmdb_guess_list_type_from_name(list_name)
    if name_guess:
        return name_guess
    if list_meta_type in ('movie', 'movies'):
        return 'movie'
    if list_meta_type in ('tv', 'series', 'show', 'shows'):
        return 'tv'
    return None


def _tmdb_list_matches_menu(list_type, list_meta_type, list_id=None, list_name=None):
    resolved = _tmdb_resolve_list_type(list_meta_type, list_id, list_name)
    if not list_type:
        return True
    if not resolved:
        return False
    if list_type == 'movie':
        return resolved == 'movie'
    return resolved == 'tv'


def get_created_lists(url=None, list_type=None):
    items = []
    try:
        if not getTMDbCredentialsInfo():
            return items
        account = _tmdb_account_settings()
        if not url:
            url = API_URL + 'list/%s?api_key=%s&language=en-US&page=1' % ('%s', _tmdb_api_key())
        page = 1
        total_pages = 1
        while page <= total_pages:
            lists_url = API_URL + 'account/%s/lists?api_key=%s&language=en-US&session_id=%s&page=%s' % (
                account['account_id'], _tmdb_api_key(), account['session_id'], page)
            result = requests.get(lists_url, headers=HEADERS, timeout=30).json()
            lists = result.get('results') or []
            if not lists:
                break
            try:
                total_pages = max(int(result.get('total_pages') or 1), page)
            except Exception:
                total_pages = page
            for lst in lists:
                list_name = lst['name']
                list_id = lst['id']
                resolved = _tmdb_resolve_list_type(lst.get('list_type'), list_id, list_name)
                if list_type and resolved != list_type:
                    continue
                if not resolved:
                    continue
                list_url = url % list_id
                action = 'movies' if resolved == 'movie' else 'tvshows'
                from resources.lib.modules import shelf_sort
                items.append({
                    'name': list_name,
                    'url': list_url,
                    'context': list_url,
                    'list_id': list_id,
                    'image': 'tmdb.png',
                    'action': action,
                    'sort_provider': 'tmdb',
                    'sort_key': shelf_sort.personal_shelf_key(list_id),
                })
            page += 1
        return items
    except:
        #log_utils.log('get_created_lists', 1)
        return items


def create_list(name):
    try:
        url = API_URL + 'list?api_key=%s&session_id=%s' % (_tmdb_api_key(), _tmdb_account_settings()['session_id'])
        post = {"name": "%s" % str(name), "description": "created_userlist", "language": "en"}
        result = requests.post(url, data=json.dumps(post), headers=HEADERS).json()
        if not result.get('success') is True:
            raise Exception()
        list_id = result['list_id']
        return list_id
    except:
        #log_utils.log('add_to_watchlist', 1)
        return


def add_to_list(tmdb, list_id):
    try:
        url = API_URL + 'list/%s/add_item?api_key=%s&session_id=%s' % (list_id, _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        post = {"media_id": "%s" % str(tmdb)}
        result = requests.post(url, data=json.dumps(post), headers=HEADERS).json()
        if not result.get('success') is True:
            raise Exception()
        return True
    except:
        #log_utils.log('add_to_list', 1)
        return False


def remove_from_list(tmdb, list_id):
    try:
        url = API_URL + 'list/%s/remove_item?api_key=%s&session_id=%s' % (list_id, _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        post = {"media_id": "%s" % str(tmdb)}
        result = requests.post(url, data=json.dumps(post), headers=HEADERS).json()
        if not result.get('success') is True:
            raise Exception()
        return True
    except:
        #log_utils.log('remove_from_list', 1)
        return False


def get_movie_favorites():
    try:
        url = API_URL + 'account/%s/favorite/movies?api_key=%s&session_id=%s&language=en-US&page=1' % (_tmdb_account_settings()['account_id'], _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        return url
    except:
        #log_utils.log('get_movie_favorites', 1)
        return


def get_tvshow_favorites():
    try:
        url = API_URL + 'account/%s/favorite/tv?api_key=%s&session_id=%s&language=en-US&page=1' % (_tmdb_account_settings()['account_id'], _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        return url
    except:
        #log_utils.log('get_tvshow_favorites', 1)
        return


def add_to_favorites(tmdb, media_type):
    try:
        url = API_URL + 'account/%s/favorite?api_key=%s&session_id=%s' % (_tmdb_account_settings()['account_id'], _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        post = {"media_type": "%s" % str(media_type), "media_id": "%s" % str(tmdb), "favorite": True}
        result = requests.post(url, data=json.dumps(post), headers=HEADERS).json()
        if not result.get('success') is True:
            raise Exception()
        return True
    except:
        #log_utils.log('add_to_favorites', 1)
        return False


def remove_from_favorites(tmdb, media_type):
    try:
        url = API_URL + 'account/%s/favorite?api_key=%s&session_id=%s' % (_tmdb_account_settings()['account_id'], _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        post = {"media_type": "%s" % str(media_type), "media_id": "%s" % str(tmdb), "favorite": False}
        result = requests.post(url, data=json.dumps(post), headers=HEADERS).json()
        if not result.get('success') is True:
            raise Exception()
        return True
    except:
        #log_utils.log('remove_from_favorites', 1)
        return False


def get_movie_watchlist():
    try:
        url = API_URL + 'account/%s/watchlist/movies?api_key=%s&session_id=%s&language=en-US&page=1' % (_tmdb_account_settings()['account_id'], _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        return url
    except:
        #log_utils.log('get_movie_watchlist', 1)
        return


def get_tvshow_watchlist():
    try:
        url = API_URL + 'account/%s/watchlist/tv?api_key=%s&session_id=%s&language=en-US&page=1' % (_tmdb_account_settings()['account_id'], _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        return url
    except:
        #log_utils.log('get_tvshow_watchlist', 1)
        return


def add_to_watchlist(tmdb, media_type):
    try:
        url = API_URL + 'account/%s/watchlist?api_key=%s&session_id=%s' % (_tmdb_account_settings()['account_id'], _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        post = {"media_type": "%s" % str(media_type), "media_id": "%s" % str(tmdb), "watchlist": True}
        result = requests.post(url, data=json.dumps(post), headers=HEADERS).json()
        if not result.get('success') is True:
            raise Exception()
        return True
    except:
        #log_utils.log('add_to_watchlist', 1)
        return False


def remove_from_watchlist(tmdb, media_type):
    try:
        url = API_URL + 'account/%s/watchlist?api_key=%s&session_id=%s' % (_tmdb_account_settings()['account_id'], _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        post = {"media_type": "%s" % str(media_type), "media_id": "%s" % str(tmdb), "watchlist": False}
        result = requests.post(url, data=json.dumps(post), headers=HEADERS).json()
        if not result.get('success') is True:
            raise Exception()
        return True
    except:
        #log_utils.log('remove_from_watchlist', 1)
        return False


def choose_list_sort(media, shelf, label=None):
    from resources.lib.modules import shelf_sort
    shelf_sort.choose_list_sort(
        'tmdb', media, shelf, sortable=shelf_sort.TMDB_SORTABLE, heading_label=label)


def apply_my_shelf_sort(items, url, media):
    from resources.lib.modules import shelf_sort
    shelf = shelf_sort.tmdb_shelf_from_url(url)
    if not shelf:
        return items
    return shelf_sort.sort_items(items, 'tmdb', media, shelf, sortable=shelf_sort.TMDB_SORTABLE)


def _item_in_created_list(tmdb, list_id):
    try:
        url = API_URL + 'list/%s/item_status?api_key=%s&session_id=%s&media_id=%s' % (
            list_id, _tmdb_api_key(), _tmdb_account_settings()['session_id'], tmdb)
        result = requests.get(url, headers=HEADERS, timeout=20).json()
        return bool(result.get('item_present'))
    except Exception:
        return False


def _account_favorite_watchlist(tmdb, media_type):
    try:
        states = get_movie_account_states(tmdb) if media_type == 'movie' else get_tvshow_account_states(tmdb)
        if not isinstance(states, dict):
            return False, False
        return bool(states.get('favorite')), bool(states.get('watchlist'))
    except Exception:
        return False, False


def manager(name, imdb, tmdb, content):
    try:
        if not getTMDbCredentialsInfo():
            return control.infoDialog('Authorise TMDb first.', sound=True, icon='ERROR')
        if not tmdb:
            return control.infoDialog('Missing TMDb ID for Lists Manager.', heading=str(name), sound=True, icon='ERROR')
        media_type = 'movie' if content == 'movie' else 'tv'
        in_favorites, in_watchlist = _account_favorite_watchlist(tmdb, media_type)
        choices = []
        if in_favorites:
            choices.append(('Remove from [B]Favorites[/B]', 'favorites_remove', None, 'Favorites'))
        else:
            choices.append(('Add to [B]Favorites[/B]', 'favorites_add', None, 'Favorites'))
        if in_watchlist:
            choices.append(('Remove from [B]Watchlist[/B]', 'watchlist_remove', None, 'Watchlist'))
        else:
            choices.append(('Add to [B]Watchlist[/B]', 'watchlist_add', None, 'Watchlist'))
        choices.append(('Add to [B]new List[/B]', 'list_new', None, 'new List'))
        for entry in get_created_lists(list_type=media_type):
            list_id = entry.get('list_id')
            list_name = entry.get('name') or ''
            if not list_id or not list_name:
                continue
            if _item_in_created_list(tmdb, list_id):
                choices.append(('Remove from [B]%s[/B]' % list_name, 'list_remove', list_id, list_name))
            else:
                choices.append(('Add to [B]%s[/B]' % list_name, 'list_add', list_id, list_name))
        select = control.selectDialog([c[0] for c in choices], 'TMDb Lists Manager')
        if select < 0:
            return
        _, action, list_id, label = choices[select]
        ok = False
        if action == 'favorites_add':
            ok = add_to_favorites(tmdb, media_type)
        elif action == 'favorites_remove':
            ok = remove_from_favorites(tmdb, media_type)
        elif action == 'watchlist_add':
            ok = add_to_watchlist(tmdb, media_type)
        elif action == 'watchlist_remove':
            ok = remove_from_watchlist(tmdb, media_type)
        elif action == 'list_new':
            k = control.keyboard('', 'Add to [B]new List[/B]')
            k.doModal()
            new = k.getText() if k.isConfirmed() else None
            if new is None or new == '':
                return
            created_id = create_list(new)
            if not created_id:
                return control.infoDialog('Could not create list.', heading=str(name), sound=True, icon='ERROR')
            ok = add_to_list(tmdb, created_id)
            label = new
            action = 'list_add'
        elif action == 'list_add':
            ok = add_to_list(tmdb, list_id)
        elif action == 'list_remove':
            ok = remove_from_list(tmdb, list_id)
        if not ok:
            verb = 'add to' if 'add' in action or action == 'list_new' else 'remove from'
            return control.infoDialog('Could not %s %s.' % (verb, label), heading=str(name), sound=True, icon='ERROR')
        message = ('Added to %s.' if 'add' in action else 'Removed from %s.') % label
        try:
            control.refresh_list()
        except Exception:
            pass
        control.infoDialog(message, heading=str(name), sound=True, icon=control.infoLabel('ListItem.Icon'))
    except Exception:
        #log_utils.log('manager', 1)
        control.infoDialog('TMDb Lists Manager failed.', heading=str(name), sound=True, icon='ERROR')


def get_movie_account_states(tmdb):
    try:
        url = API_URL + 'movie/%s/account_states?api_key=%s&session_id=%s' % (tmdb, _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        result = requests.get(url, headers=HEADERS, timeout=20)
        return result.json()
    except:
        #log_utils.log('get_movie_account_states', 1)
        return


def get_tvshow_account_states(tmdb):
    try:
        url = API_URL + 'tv/%s/account_states?api_key=%s&session_id=%s' % (tmdb, _tmdb_api_key(), _tmdb_account_settings()['session_id'])
        result = requests.get(url, headers=HEADERS, timeout=20)
        return result.json()
    except:
        #log_utils.log('get_tvshow_account_states', 1)
        return



def get_movie_alternative_titles(tmdb):
    try:
        url = API_URL + 'movie/%s/alternative_titles?api_key=%s&country=US&language=en-US' % (tmdb, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS).json()
        results = result['titles']
        #{"iso_3166_1": "US", "title": "Fight Club","type": ""},
        return results
    except:
        #log_utils.log('get_movie_alternative_titles', 1)
        return


def get_tvshow_alternative_titles(tmdb):
    try:
        url = API_URL + 'tv/%s/alternative_titles?api_key=%s&country=US&language=en-US' % (tmdb, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS).json()
        results = result['results']
        #{"title": "Game of Thrones - Das Lied von Eis und Feuer", "iso_3166_1": "DE"},
        return results
    except:
        #log_utils.log('get_tvshow_alternative_titles', 1)
        return


def get_movie_external_ids(tmdb):
    try:
        url = API_URL + 'movie/%s/external_ids?api_key=%s&language=en-US' % (tmdb, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS)
        return result.json()
    except:
        #log_utils.log('get_movie_external_ids', 1)
        return


def get_tvshow_external_ids(tmdb):
    try:
        url = API_URL + 'tv/%s/external_ids?api_key=%s&language=en-US' % (tmdb, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS)
        return result.json()
    except:
        #log_utils.log('get_tvshow_external_ids', 1)
        return


def get_season_external_ids(tmdb, season):
    try:
        url = API_URL + 'tv/%s/season/%s/external_ids?api_key=%s&language=en-US' % (tmdb, season, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS)
        return result.json()
    except:
        #log_utils.log('get_season_external_ids', 1)
        return


def get_episode_external_ids(tmdb, season, episode):
    try:
        url = API_URL + 'tv/%s/season/%s/episode/%s/external_ids?api_key=%s&language=en-US' % (tmdb, season, episode, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS)
        return result.json()
    except:
        #log_utils.log('get_episode_external_ids', 1)
        return


def find_movie_by_external_source(imdb):
    try:
        url = API_URL + 'find/%s?api_key=%s&language=en-US&external_source=imdb_id' % (imdb, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS).json()
        item = result['movie_results'][0]
        return item
    except:
        #log_utils.log('find_movie_by_external_source', 1)
        return


def find_tvshow_by_external_source(imdb=None, tvdb=None):
    try:
        if imdb:
            url = API_URL + 'find/%s?api_key=%s&language=en-US&external_source=imdb_id' % (imdb, _tmdb_api_key())
        elif tvdb:
            url = API_URL + 'find/%s?api_key=%s&language=en-US&external_source=tvdb_id' % (tvdb, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS).json()
        item = result['tv_results'][0]
        return item
    except:
        #log_utils.log('find_tvshow_by_external_source', 1)
        return


def get_movie_trailers(tmdb):
    try:
        url = API_URL + 'movie/%s/videos?api_key=%s&language=en-US' % (tmdb, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS).json()
        items = result['results']
        return items
    except:
        #log_utils.log('get_movie_trailers', 1)
        return


def get_tvshow_trailers(tmdb):
    try:
        url = API_URL + 'tv/%s/videos?api_key=%s&language=en-US' % (tmdb, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS).json()
        items = result['results']
        return items
    except:
        #log_utils.log('get_tvshow_trailers', 1)
        return


def get_season_trailers(tmdb, season):
    try:
        url = API_URL + 'tv/%s/season/%s/videos?api_key=%s&language=en-US' % (tmdb, season, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS).json()
        items = result['results']
        return items
    except:
        #log_utils.log('get_season_trailers', 1)
        return


def get_episode_trailers(tmdb, season, episode):
    try:
        url = API_URL + 'tv/%s/season/%s/episode/%s/videos?api_key=%s&language=en-US' % (tmdb, season, episode, _tmdb_api_key())
        result = requests.get(url, headers=HEADERS).json()
        items = result['results']
        return items
    except:
        #log_utils.log('get_episode_trailers', 1)
        return


###################################################
###################################################


def get_tmdb_artwork(tmdb, content, season=None, episode=None):
    try:
        media_type = "movie" if content == "movie" else "tv"
        if season and episode:
            ending = '%s/%s/season/%s/episode/%s/images?api_key=%s' % (media_type, tmdb, season, episode, _tmdb_api_key())
        elif season:
            ending = '%s/%s/season/%s/images?api_key=%s' % (media_type, tmdb, season, _tmdb_api_key())
        else:
            ending = '%s/%s/images?api_key=%s' % (media_type, tmdb, _tmdb_api_key())
        url = API_URL + ending
        result = requests.get(url, headers=HEADERS).json()
        #log_utils.log('Testing - get_tmdb_artwork result: \n' + repr(result))
        try:
            poster = result.get('posters', [])
            if poster and poster != []:
                poster = [x for x in poster if x.get('iso_639_1') == 'en'] + [x for x in poster if not x.get('iso_639_1') == 'en']
                poster = [(x['width'], x['file_path']) for x in poster]
                poster = [(x[0], x[1]) if x[0] < 500 else ('500', x[1]) for x in poster]
                if poster:
                    if original_artwork == 'true':
                        poster = image_link + poster[0][1]
                    else:
                        poster = image_link % poster[0]
                else:
                    poster = '0'
            else:
                poster = '0'
            #poster = poster.encode('utf-8')
        except:
            poster = '0'
        try:
            fanart = result.get('backdrops', [])
            if fanart and fanart != []:
                fanart = [x for x in fanart if x.get('iso_639_1') == 'en'] + [x for x in fanart if not x.get('iso_639_1') == 'en']
                fanart = [x for x in fanart if x.get('width') == 1920] + [x for x in fanart if x.get('width') < 1920]
                fanart = [(x['width'], x['file_path']) for x in fanart]
                fanart = [(x[0], x[1]) if x[0] < 1280 else ('1280', x[1]) for x in fanart]
                if fanart:
                    if original_artwork == 'true':
                        fanart = image_link + fanart[0][1]
                    else:
                        fanart = image_link % fanart[0]
                else:
                    fanart = '0'
            else:
                fanart = '0'
            #fanart = fanart.encode('utf-8')
        except:
            fanart = '0'
        try:
            fanart2 = result.get('stills', [])
            if fanart2 and fanart2 != []:
                fanart2 = [x for x in fanart2 if x.get('iso_639_1') == 'en'] + [x for x in fanart2 if not x.get('iso_639_1') == 'en']
                fanart2 = [x for x in fanart2 if x.get('width') == 1920] + [x for x in fanart2 if x.get('width') < 1920]
                fanart2 = [(x['width'], x['file_path']) for x in fanart2]
                fanart2 = [(x[0], x[1]) if x[0] < 1280 else ('300', x[1]) for x in fanart2]
                if fanart2:
                    if original_artwork == 'true':
                        fanart2 = image_link + fanart2[0][1]
                    else:
                        fanart2 = image_link % fanart2[0]
                else:
                    fanart2 = '0'
            else:
                fanart2 = '0'
            #fanart2 = fanart2.encode('utf-8')
        except:
            fanart2 = '0'
        try:
            banner = result.get('logos', [])
            if banner and banner != []:
                banner = [x for x in banner if x.get('iso_639_1') == 'en'] + [x for x in banner if not x.get('iso_639_1') == 'en']
                banner = [(x['width'], x['file_path']) for x in banner]
                banner = [(x[0], x[1]) if x[0] < 500 else ('500', x[1]) for x in banner]
                if banner:
                    if original_artwork == 'true':
                        banner = image_link + banner[0][1]
                    else:
                        banner = image_link % banner[0]
                else:
                    banner = '0'
            else:
                banner = '0'
            #banner = banner.encode('utf-8')
        except:
            banner = '0'
        fanart = fanart if not fanart == '0' else fanart2
    except:
        poster = fanart = banner = '0'
        #log_utils.log('get_tmdb_artwork', 1)
    return poster, fanart, banner


###################################################
###################################################


# https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key=<<api_key>>&language=en-US
# https://api.themoviedb.org/3/person/{person_id}/tv_credits?api_key=<<api_key>>&language=en-US
# https://api.themoviedb.org/3/person/{person_id}/movie_credits?api_key=<<api_key>>&language=en-US


def get_popular_people(url, content):
    try:
        list = []
        media_type = "movie" if content == "movie" else "tv"
        if not url:
            #url = API_URL + 'discover/%s?api_key=%s&with_people=%s&language=en-US&page=1' % (media_type, _tmdb_api_key(), '%s')
            url = API_URL + 'person/%s/%s_credits?api_key=%s&language=en-US' % ('%s', media_type, _tmdb_api_key())
        list_url = API_URL + 'person/popular?api_key=%s&language=en-US&page=1' % _tmdb_api_key()
        result = requests.get(list_url, headers=HEADERS).json()
        try:
            page = int(result['page'])
            total = int(result['total_pages'])
            if page >= total:
                raise Exception()
            if not 'page=' in list_url:
                raise Exception()
            next = '%s&page=%s' % (list_url.split('&page=', 1)[0], str(page+1))
        except:
            next = ''
        items = result['results']
        for item in items:
            person_name = item['name']
            person_id = item['id']
            person_url = url % person_id
            try:
                person_art = ART_URL + item['profile_path']
            except:
                person_art = 'tmdb.png'
            list.append({'name': person_name, 'url': person_url, 'person_id': person_id, 'image': person_art, 'next': next})
        return list
    except:
        #log_utils.log('get_popular_people', 1)
        return list


def find_people(url, query, content):
    try:
        list = []
        media_type = "movie" if content == "movie" else "tv"
        if not url:
            #url = API_URL + 'discover/%s?api_key=%s&with_people=%s&language=en-US&page=1' % (media_type, _tmdb_api_key(), '%s')
            url = API_URL + 'person/%s/%s_credits?api_key=%s&language=en-US' % ('%s', media_type, _tmdb_api_key())
        list_url = API_URL + 'search/person?api_key=%s&query=%s&language=en-US&page=1' % (_tmdb_api_key(), query)
        result = requests.get(list_url, headers=HEADERS).json()
        try:
            page = int(result['page'])
            total = int(result['total_pages'])
            if page >= total:
                raise Exception()
            if not 'page=' in list_url:
                raise Exception()
            next = '%s&page=%s' % (list_url.split('&page=', 1)[0], str(page+1))
        except:
            next = ''
        items = result['results']
        for item in items:
            person_name = item['name']
            person_id = item['id']
            person_url = url % person_id
            try:
                person_art = ART_URL + item['profile_path']
            except:
                person_art = 'tmdb.png'
            list.append({'name': person_name, 'url': person_url, 'person_id': person_id, 'image': person_art, 'next': next})
        return list
    except:
        #log_utils.log('find_people', 1)
        return list


def find_keyword(url, query, content):
    try:
        list = []
        media_type = "movie" if content == "movie" else "tv"
        if not url:
            url = API_URL + 'discover/%s?api_key=%s&with_keywords=%s&language=en-US&page=1' % (media_type, _tmdb_api_key(), '%s')
        list_url = API_URL + 'search/keyword?api_key=%s&query=%s&language=en-US&page=1' % (_tmdb_api_key(), query)
        result = requests.get(list_url, headers=HEADERS).json()
        try:
            page = int(result['page'])
            total = int(result['total_pages'])
            if page >= total:
                raise Exception()
            if not 'page=' in list_url:
                raise Exception()
            next = '%s&page=%s' % (list_url.split('&page=', 1)[0], str(page+1))
        except:
            next = ''
        items = result['results']
        for item in items:
            keyword_name = item['name']
            keyword_id = item['id']
            keyword_url = url % keyword_id
            list.append({'name': keyword_name, 'url': keyword_url, 'keyword_id': keyword_id, 'image': 'tmdb.png', 'next': next})
        return list
    except:
        #log_utils.log('find_keyword', 1)
        return list


def find_companies(query, content):
    try:
        list = []
        media_type = "movie" if content == "movie" else "tv"
        list_url = API_URL + 'search/company?api_key=%s&query=%s&page=1' % (_tmdb_api_key(), query)
        result = requests.get(list_url, headers=HEADERS).json()
        try:
            page = int(result['page'])
            total = int(result['total_pages'])
            if page >= total:
                raise Exception()
            if not 'page=' in list_url:
                raise Exception()
            next = '%s&page=%s' % (list_url.split('&page=', 1)[0], str(page+1))
        except:
            next = ''
        items = result['results']
        for item in items:
            company_name = item['name']
            company_id = item['id']
            try:
                company_art = ART_URL + item['logo_path']
            except:
                company_art = 'tmdb.png'
            company_url = API_URL + 'discover/%s?api_key=%s&with_companies=%s&language=en-US&page=1' % (media_type, _tmdb_api_key(), company_id)
            list.append({'name': company_name, 'url': company_url, 'company_id': company_id, 'image': company_art, 'next': next})
        return list
    except:
        #log_utils.log('find_companies', 1)
        return list


def find_collection(query):
    try:
        list = []
        list_url = API_URL + 'search/collection?api_key=%s&query=%s&page=1' % (_tmdb_api_key(), query)
        result = requests.get(list_url, headers=HEADERS).json()
        try:
            page = int(result['page'])
            total = int(result['total_pages'])
            if page >= total:
                raise Exception()
            if not 'page=' in list_url:
                raise Exception()
            next = '%s&page=%s' % (list_url.split('&page=', 1)[0], str(page+1))
        except:
            next = ''
        items = result['results']
        for item in items:
            try:
                collection_name = item['name']
                collection_id = item['id']
                try:
                    collection_poster = ART_URL + item['poster_path']
                    collection_fanart = ART_URL + item['backdrop_path']
                except:
                    collection_poster = 'tmdb.png'
                    collection_fanart = None
                collection_url = API_URL + 'collection/%s?api_key=%s&language=en-US&page=1' % (collection_id, _tmdb_api_key())
                list.append({'name': collection_name, 'url': collection_url, 'collection_id': collection_id, 'poster': collection_poster, 'fanart': collection_fanart, 'image': 'tmdb.png', 'next': next})
            except:
                #log_utils.log('find_collection', 1)
                pass
            
        return list
    except:
        #log_utils.log('find_collection', 1)
        return list


