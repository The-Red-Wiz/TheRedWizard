# -*- coding: utf-8 -*-
#Bugatsinho fixes 28/08/2018

import urllib.request, urllib.error, urllib.parse, re
import xbmcplugin, xbmcgui, xbmcvfs, os, xbmc, sys
import settings, time
import requests
from bs4 import BeautifulSoup
from t0mm0.common.net import Net
from threading import Thread
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3


cookie_jar = settings.cookie_jar()
net = Net()
ADDON = settings.addon()
GOTHAM_FIX = False
GOLDEN_PATH = False
KEEP_DOWNLOADS = settings.keep_downloads()
ARTIST_ART = settings.artist_icons()
FAV_ARTIST = settings.favourites_file_artist()
FAV_ALBUM = settings.favourites_file_album()
FAV_SONG = settings.favourites_file_songs()
PLAYLIST_FILE = settings.playlist_file()
HIDE_FANART = settings.hide_fanart()
QUEUE_SONGS = settings.default_queue()
QUEUE_ALBUMS = settings.default_queue_album()
DOWNLOAD_LIST = settings.download_list()
FOLDERSTRUCTURE = settings.folder_structure()
fanart = xbmcvfs.translatePath(os.path.join('special://home/addons/plugin.audio.mp3streams', 'fanart.jpg'))
art = xbmcvfs.translatePath(os.path.join('special://home/addons/plugin.audio.mp3streams', 'art')) + '/'
artgenre = xbmcvfs.translatePath(os.path.join('special://home/addons/plugin.audio.mp3streams/art', 'genre')) + '/'
artbillboard = xbmcvfs.translatePath(os.path.join('special://home/addons/plugin.audio.mp3streams/art', 'billboard')) + '/'
urllist = xbmcvfs.translatePath(os.path.join('special://home/addons/plugin.audio.mp3streams', 'lists', 'mp3url.list'))
audio_fanart = ""
iconart = xbmcvfs.translatePath(os.path.join('special://home/addons/plugin.audio.mp3streams', 'icon.png'))

def download_lock_path():
    return os.path.join(settings.music_dir(), 'downloading.txt')
xbmc_version=xbmc.getInfoLabel("System.BuildVersion")[:4]
ua = 'Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36'


GOTHAM_FIX_2 = ADDON.getSetting('gotham_fix_2') == 'true'
if GOTHAM_FIX_2:
    GOTHAM_FIX = False

def newPlay(pl, clear):
    if clear or (not xbmc.Player().isPlayingAudio()):
        xbmc.Player().play(pl)

def open_url(url):
    return requests.get(url, headers={'User-Agent': ua}, timeout=10).text
    """req = urllib.request.Request(url)
    req.add_header('User-Agent', ua)
    response = urllib.request.urlopen(req)
    link=response.read()
    response.close()
    return link"""

def GET_url(url):
    header_dict = {}
    if 'musicmp3' in url:
        header_dict['Accept'] = 'audio/webm,audio/ogg,udio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5'
        header_dict['User-Agent'] = 'AppleWebKit/<WebKit Rev>'
        header_dict['Host'] = 'musicmp3.ru'
        header_dict['Referer'] = 'http://musicmp3.ru/'
        header_dict['Connection'] = 'keep-alive'
    if 'goldenmp3' in url:
        header_dict['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        header_dict['User-Agent'] = ua
        header_dict['Host'] = 'www.goldenmp3.ru'
        header_dict['Referer'] = 'http://www.goldenmp3.ru/compilations/events/albums'
        header_dict['Connection'] = 'keep-alive'
    net.set_cookies(cookie_jar)
    #link = net.http_GET(url, headers=header_dict).content.encode("utf-8").rstrip()
    link = requests.get(url, header_dict, timeout=10).text
    net.save_cookies(cookie_jar)
    return link

def get_cookie():
    header_dict = {}
    header_dict['User-Agent'] = ua
    header_dict['Connection'] = 'keep-alive'
    net.set_cookies(cookie_jar)
    link = net.http_GET('http://musicmp3.ru/', headers=header_dict).content.encode("utf-8").rstrip()
    net.save_cookies(cookie_jar)

def normalize_search(query):
    return query.replace(' - ', ' ').replace('-', ' ').replace(' FT ', ' ').replace(' FEATURING ', ' ').replace('/', ' ')

def plugin_notice(message):
    try:
        xbmcgui.Dialog().notification('MP3 Streams', message, iconart, 3000, False)
    except TypeError:
        xbmcgui.Dialog().notification('MP3 Streams', message, iconart, 3000)

def return_to_previous_menu():
    xbmc.executebuiltin('Action(Back)')
    sys.exit(0)

def addon_root_url():
    return 'plugin://%s/' % ADDON.getAddonInfo('id')

def return_to_main_menu():
    xbmc.executebuiltin('Container.Update(%s,isdir)' % addon_root_url())
    sys.exit(0)

def track_number_from_title(title):
    title = settings.decode_text(title or '')
    match = re.match(r'^\s*(\d+)\.\s+', title)
    return match.group(1) if match else ''

def numbered_song_title(track, songname):
    songname = settings.decode_text(songname or '')
    if not track:
        return songname
    if re.match(r'^\s*%s\.\s+' % re.escape(str(track)), songname):
        return songname
    return "%s. %s" % (track, songname)

def album_download_names(name):
    name = settings.decode_text(name or '')
    parts = name.split(' - ')
    if len(parts) < 2:
        return 'Various', name
    artist = parts[0]
    album_parts = parts[1:-1] if len(parts) > 2 and re.match(r'^\d{4}$', parts[-1]) else parts[1:]
    return artist, ' - '.join(album_parts)

# RunPlugin / action-only modes must not call endOfDirectory or Kodi shows a blank list.
PLUGIN_ACTION_MODES = (8, 61, 62, 64, 65, 67, 68, 89, 99, 100, 201, 202, 333, 500)

def read_favourite_lines(file_path):
    if not os.path.isfile(file_path):
        return []
    content = read_from_file(file_path) or ''
    return [line for line in content.split('\n') if line.strip()]

def select_favourite_group(all_label, file_path, group_index, empty_message):
    lines = read_favourite_lines(file_path)
    if not lines:
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), empty_message, iconart, 3000)
        return None
    menu_texts = [all_label]
    for line in lines:
        parts = line.split('<>')
        group = parts[group_index] if len(parts) > group_index else 'Ungrouped'
        if group not in menu_texts:
            menu_texts.append(group)
    menu_id = xbmcgui.Dialog().select('Select Group', menu_texts)
    if menu_id < 0:
        return None
    return menu_texts[menu_id]

def pick_favourite_group(existing_groups):
    menu_texts = ['Add New Group'] + existing_groups
    menu_id = xbmcgui.Dialog().select('Select Group', menu_texts)
    if menu_id < 0:
        return None
    if menu_id == 0:
        keyboard = xbmc.Keyboard('', 'Create New Group', False)
        keyboard.doModal()
        if keyboard.isConfirmed():
            query = keyboard.getText().strip()
            if query:
                return query
        return None
    return menu_texts[menu_id]

def CATEGORIES():
    addDir('Artists','http://musicmp3.ru/artists.html',21,art + 'artists.jpg','')
    addDir('Top Albums','http://musicmp3.ru/genres.html',12,art + 'topalbums.jpg','')
    addDir('New Albums','http://musicmp3.ru/new_albums.html',12,art + 'newalbums.jpg','')
    addDir('Compilations','url',400,art + 'compilations.jpg','')
    addDir('Billboard Charts','url',101,art + 'billboardcharts.jpg','')
    addDir('Search Artists','url',24,art + 'searchartists.jpg','')
    addDir('Search Albums','url',24,art + 'searchalbums.jpg','')
    addDir('Search Songs','url',24,art + 'searchsongs.jpg','')
    addDir('Favourite Artists','url',63,art + 'favouriteartists.jpg','')
    addDir('Favourite Albums','url',66,art + 'favouritealbums.jpg','')
    addDir('Favourite Songs','url',69,art + 'favouritesongs.jpg','')
    addDirAudio('Instant Mix Favourite Songs (Shuffle and Play)','url',99,art + 'mixfavouritesongs.jpg','','','','','')
    addDirAudio('Instant Mix Favourite Albums (Shuffle and Play)','url',89,art + 'mixfavouritealbums.jpg','','','','','')
    addDirAudio('Clear Playlist','url',100,art + 'clearplaylist.jpg','','','','','')
    addDirAudio('Settings','url',8,iconart,'','','','','')
    #addDirAudio('Add ID3 Tags','url',300,art + 'addid3tags.jpg','','','','','')
    #addDir('Browse Alternate Source','url',700,artgenre + 'alternate.jpg','')

def charts():
    addDir('BillBoard Hot 20 Singles','http://www.officialcharts.com/charts/billboard-hot-100-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('BillBoard 20 Albums','http://www.officialcharts.com/charts/billboard-200/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 100 Streaming Singles','http://www.officialcharts.com/charts/audio-streaming-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 100 UK Singles','http://www.officialcharts.com/charts/singles-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 100 UK Albums','http://www.officialcharts.com/charts/albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 100 End of Year Singles','http://www.officialcharts.com/charts/end-of-year-singles-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 100 End of Year Albums','http://www.officialcharts.com/charts/end-of-year-artist-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 100 Compilation Albums','http://www.officialcharts.com/charts/official-compilations-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 50 Soundtracks','http://www.officialcharts.com/charts/soundtrack-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 40 Dance Singles','http://www.officialcharts.com/charts/dance-singles-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 40 Dance Albums','http://www.officialcharts.com/charts/dance-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 40 R&B Singles','http://www.officialcharts.com/charts/r-and-b-singles-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 40 R&B Albums','http://www.officialcharts.com/charts/r-and-b-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 40 Rock/Metal Singles','http://www.officialcharts.com/charts/rock-and-metal-singles-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 40 Rock/Metal Albums','http://www.officialcharts.com/charts/rock-and-metal-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 50 Independent Singles','http://www.officialcharts.com/charts/independent-singles-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 50 Independent Albums','http://www.officialcharts.com/charts/independent-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 20 Country Albums','http://www.officialcharts.com/charts/country-artists-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 20 Country Compilation Albums','http://www.officialcharts.com/charts/country-compilations-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 50 Classical Compilation Albums','http://www.officialcharts.com/charts/classical-compilation-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 30 Jazz & Blues Albums','http://www.officialcharts.com/charts/jazz-and-blues-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    addDir('Top 20 Christian & Gospel Albums','http://www.officialcharts.com/charts/christian-and-gospel-albums-chart/',102,artbillboard +'billboardcharts.jpg','')
    #addDir('UK Single Chart - Top 100','https://www.billboard.com/charts/official-uk-songs',102,artbillboard +'uksinglecharttop100.jpg','')
    #addDir('BillBoard 200','https://www.billboard.com/charts/billboard-200',102,artbillboard +'billboard200.jpg','')
    #addDir('Hot 100 Singles','https://www.billboard.com/charts/hot-100',102,artbillboard +'hot100singles.jpg','')
    #addDir('Country Albums','http://www.billboard.com/charts/country-albums',102,artbillboard +'countryalbums.jpg','')
    #addDir('HeatSeeker Albums','http://www.billboard.com/charts/heatseekers-albums',102,artbillboard +'heatseekeralbums.jpg','')
    #addDir('Independent Albums','http://www.billboard.com/charts/independent-albums',102,artbillboard +'independentalbums.jpg','')
    #addDir('Catalogue Albums','http://www.billboard.com/charts/catalog-albums',102,artbillboard +'cataloguealbums.jpg','')
    #addDir('Folk Albums','http://www.billboard.com/charts/folk-albums',102,artbillboard +'folkalbums.jpg','')
    #addDir('Blues Albums','http://www.billboard.com/charts/blues-albums',102,artbillboard +'bluesalbums.jpg','')
    #addDir('Tastemaker Albums','http://www.billboard.com/charts/tastemaker-albums',102,artbillboard +'tastemakeralbums.jpg','')
    #addDir('Rock Albums','http://www.billboard.com/charts/rock-albums',102,artbillboard +'rockalbums.jpg','')
    #addDir('Alternative Albums','http://www.billboard.com/charts/alternative-albums',102,artbillboard +'alternativealbums.jpg','')
    #addDir('Hard Rock Albums','http://www.billboard.com/charts/hard-rock-albums',102,artbillboard +'hardrockalbums.jpg','')
    #addDir('Digital Albums','http://www.billboard.com/charts/digital-albums',102,artbillboard +'digitalalbums.jpg','')
    #addDir('R&B Albums','http://www.billboard.com/charts/r-b-hip-hop-albums',102,artbillboard +'randbalbums.jpg','')
    #addDir('Top R&B/Hip-Hop Albums','http://www.billboard.com/charts/r-and-b-albums',102,artbillboard +'toprandbandhiphop.jpg','')
    #addDir('Dance Electronic Albums','http://www.billboard.com/charts/dance-electronic-albums',102,artbillboard +'danceandelectronic.jpg','')

def chart_lists(name, url): #102
    
    req = urllib.request.Request(url)
    req.add_header('User-Agent', ua)
    response = urllib.request.urlopen(req)
    link = response.read().decode('utf-8')
    response.close()
    if "officialcharts.com" in url:
        soup = BeautifulSoup(link, 'html.parser')
        all_list = soup.find_all(class_='chart-image')
        for _list in all_list:
            try:
                audio = _list.find('audio')
                title = audio['data-title']
                artist = audio['data-artist']
                img = _list.find(class_='chart-image-large')
                iconimage = img.get('src')
            except TypeError:
                continue
            
            if 'singles' in name.lower():
                if '&' in artist or 'FT' in artist or 'FEATURING' in artist or '/' in artist or '/' in title:
                    addDir(f'{artist} - {title}', normalize_search(title),28,iconimage,'')
                    
                else:
                    addDir(f'{artist} - {title}', normalize_search(f'{artist} - {title}'),28,iconimage,'')
                    
            elif 'albums' in name.lower():
                addDir(f'{artist} - {title}','url',25,iconimage,'')
                
                
    elif "billboard.com" in url:
        link = link.replace('\n', '').replace('\t', '')
        match = re.compile('<span class="this-week">(.+?)</span> <span class="last-week">(.+?)</span></div><div class="row-image"(.+?)<div class="row-title"><h2>(.+?)</h2><h3><a href="(.+?)" data-tracklabel="Artist Name">(.+?)</a>').findall(link)
        for pos, lw, iconimage, title, artisturl, artist in match:
            text = "%s %s" % (artist, title)
            try:
                iconimage='http' + regex_from_to(iconimage,'http','"').replace(')','')
            except:
                iconimage='http://www.billboard.com/sites/all/themes/bb/images/default/no-album.png'
            if not 'Single' in name and not 'Best Songs of 2014' in text:
                addDir(artist + ' - ' + title,'url',25,iconimage,'')
            elif not 'Best Songs of 2014' in text:
                addDir(artist + ' - ' + title,'url',26,iconimage,'')
    else:
        all_list=regex_get_all(link,'<span class="chart_position','</header>')
        for a in all_list:
            title=regex_from_to(a,'<h1>','</h1>').rstrip()
            try:
                artist=regex_from_to(a,' title="','">').strip()
            except:
                artist=regex_from_to(a,'<p class="chart_info">','</p>').strip()
            try:
                iconimage=regex_from_to(a,'Image" src="','"')
            except:
                iconimage='http://www.billboard.com/sites/all/themes/bb/images/default/no-album.png'
            text = "%s %s" % (artist, title)
            if not 'Single' in name and not 'Best Songs of 2014' in text:
                addDir(artist + ' - ' + title,'url',25,iconimage,'')
            elif not 'Best Songs of 2014' in text:
                addDir(artist + ' - ' + title,'url',26,iconimage,'')

def artists(url):
    link = GET_url(url)#.decode('utf-8')
    addDir('All Artists','http://musicmp3.ru/main_artists.html?type=artist&page=1',31,art + 'allartists.jpg','')
    sub_dir = re.compile('<li class="menu_sub__item"><a class="menu_sub__link" href="(.+?)">(.+?)</a></li>').findall(link)
    for url1, title in sub_dir:
        iconimage = 'http://musicmp3.ru/i' + url1.replace('.html', '.jpg').replace('artists', 'genres').replace('tracks', 'track')
        if title != 'Other':
            addDir(title,'https://musicmp3.ru' + url1,41,artgenre + title.replace(' ','').replace('&amp;','_').lower() + '.jpg','')

def all_artists(name, url):
    link = GET_url(url)#.decode('utf-8')
    all_artists = re.compile('<li class="small_list__item"><a class="small_list__link" href="(.+?)">(.+?)</a></li>').findall(link)
    for url1, title in all_artists:
        icon_path = os.path.join(ARTIST_ART, settings.sanitize_filename(title) + '.jpg')
        if os.path.exists(icon_path):
            iconimage = icon_path
        else:
            iconimage = iconart
        addDir(title,'http://musicmp3.ru' + url1,22,iconimage,'artists')
    pgnumf = url.find('page=') + 5
    pgnum = int(url[pgnumf:]) + 1
    nxtpgurl = url[:pgnumf]
    nxtpgurl = "%s%s" % (nxtpgurl, pgnum)
    addDir('>> Next page', nxtpgurl, 31, art + 'nextpage.jpg', str(pgnumf))
    setView('files', 'default')

def sub_dir(name, url, icon):
    link = GET_url(url)#.decode('utf-8')
    addDir('Top ' + name + ' Artists',url + '?page=1',31,artgenre + name.replace(' ','').replace('&amp;','_').lower() +'/' + 'top' + name.replace(' ','').replace('&amp;','_').lower() + '.jpg','')
    sub_dir = re.compile('<li class="menu_sub__item"><a class="menu_sub__link" href="(.+?)">(.+?)</a></li>').findall(link)
    for url, title in sub_dir:
        addDir(title,'http://musicmp3.ru' + url + '?page=1',31,artgenre + name.replace(' ','').replace('&amp;','_').lower() +'/' + title.replace(' ','').replace('&amp;','_').lower() + '.jpg','')

def genres(name, url):
    link = GET_url(url)#.decode('utf-8')
    if name == 'Top Albums':
        addDir('Top Albums','http://musicmp3.ru/main_albums.html?gnr_id=&sort=top&type=album&page=1',15,art +'alltopalbums.jpg','')
    else:
        addDir('New Albums',url + '?page=1',15,art + 'allnewalbums.jpg','')
    sub_dir = re.compile('<li class="menu_sub__item"><a class="menu_sub__link" href="(.+?)">(.+?)</a></li>').findall(link)
    for url1, title in sub_dir:
        iconimage = 'http://musicmp3.ru/i' + url1.replace('.html', '.jpg').replace('tracks', 'track')
        addDir(title,'http://musicmp3.ru' + url1,14,artgenre + title.replace(' ','').replace('&amp;','_').lower() + '.jpg','')

def all_genres(name, url):
    nxtpgnum = int(url.replace('http://musicmp3.ru/main_albums.html?gnr_id=2&sort=top&type=album&page=', '')) + 1
    nxtpgurl = "%s%s" % ('http://musicmp3.ru/main_albums.html?gnr_id=2&sort=top&type=album&page=', str(nxtpgnum))
    link = GET_url(url)#.decode('utf-8')
    all_genres = re.compile('<li class="small_list__item"><a class="small_list__link" href="(.+?)">(.+?)</a></li>').findall(link)
    for url1, title in all_genres:
        addDir(title,'http://musicmp3.ru' + url1,22,'http://www.pearljamlive.com/images/pic_home.jpg','')
    addDir('>> Next page', nxtpgurl, 13, art + 'nextpage.jpg', next)

def genre_sub_dir(name, url, icon):
    link = GET_url(url)#.decode('utf-8')
    addDir('Top ' + name + ' Albums',url + '?page=1',15,artgenre + name.replace('and','&').replace(' ','').replace('&amp;','_').lower() +'/' + 'top' + name.replace('and','_').replace(' ','').replace('&amp;','_').lower() + '.jpg','')
    sub_dir = re.compile('<li class="menu_sub__item"><a class="menu_sub__link" href="(.+?)">(.+?)</a></li>').findall(link)
    for url, title in sub_dir:
        addDir(title,'http://musicmp3.ru' + url + '?page=1',15,artgenre + name.replace('and','&').replace(' ','').replace('&amp;','_').lower() +'/' + title.replace(' ','').replace('&amp;','_').lower() + '.jpg','')

def genre_sub_dir2(name, url, icon):
    link = GET_url(url)#.decode('utf-8')
    addDir('Top ' + name + ' Albums',url,15,os.path.join(artgenre, 'alltopalbums.jpg'),'')
    sub_dir = re.compile('<li class="menu_sub__item"><a class="menu_sub__link" href="(.+?)">(.+?)</a></li>').findall(link)
    for url, title in sub_dir:
        addDir(title,'http://musicmp3.ru' + url + '?page=1',15,icon,'')

def compilations_menu():
    addDir('Best Compilations','http://www.goldenmp3.ru/albums_showcase.html?section=compilations&type=albums&page=',401,art + 'topalbums.jpg','1')
    addDir('New Compilations','http://www.goldenmp3.ru/albums_showcase.html?section=compilations&sort=new&type=albums&page=',401,art + 'newalbums.jpg','1')
    addDir('Major Hits','http://www.goldenmp3.ru/albums_showcase.html?gnr_id=806&section=compilations&type=albums&page=',401,art + 'newalbums.jpg','1')
    addDir('Nightclub Hits','http://www.goldenmp3.ru/albums_showcase.html?gnr_id=822&section=compilations&type=albums&page=',401,art + 'newalbums.jpg','1')
    addDir('Chillout Hits','http://www.goldenmp3.ru/albums_showcase.html?gnr_id=848&section=compilations&type=albums&page=',401,art + 'newalbums.jpg','1')
    addDir('Tributes and Covers','http://www.goldenmp3.ru/albums_showcase.html?gnr_id=872&section=compilations&type=albums&page=',401,art + 'newalbums.jpg','1')
    addDir('Events','http://www.goldenmp3.ru/compilations/events/albums',401,art + 'newalbums.jpg','n')

def compilations_list(name, url, iconimage, page):
    link = open_url(url)
    match=re.compile('<a href="(.+?)"><img alt="(.+?)" src="(.+?)"/></a><a class="(.+?)" href="(.+?)">(.+?)</a><span class="(.+?)">(.+?)</span><span class="f_year">(.+?)</span><span class="ga_price">(.+?)</span>').findall(link)
    #match=re.compile('<a href="(.+?)"><img alt="(.+?)" src="(.+?)" /></a><a class="(.+?)" href="(.+?)">(.+?)</a><span class="(.+?)">(.+?)</span><span class="f_year">(.+?)</span><span class="ga_price">(.+?)</span></div>').findall(link)
    for link, d1, iconimage, cl, url2, title, cl, artist, year, prc in match:
        link ='http://www.goldenmp3.ru' + link
        addDir(title, link, 5, iconimage, 'albums')
    if page != 'n':
        nextpage = int(page) + 1
        nxtpgurl = "%s%s" % (url, nextpage)
        url = "%s%s" % (url, page)
        addDir('>> Next page', nxtpgurl, 401, art + 'nextpage.jpg', str(nextpage))
    setView('files', 'album')

def search(name, url):
    keyboard = xbmc.Keyboard('', name, False)
    keyboard.doModal()
    if not keyboard.isConfirmed():
        return_to_main_menu()
    query = keyboard.getText().strip()
    if not query:
        return_to_main_menu()
    if name == 'Search Artists':
        search_artists(query)
    elif name == 'Search Albums':
        search_albums(query)
    elif name == 'Search Songs':
        search_songs(query)

def search_artists(query):
    url = 'https://musicmp3.ru/search.html?text=%s&all=artists' % urllib.parse.quote_plus(normalize_search(query))
    link = GET_url(url)#.decode('utf-8')
    all_artists = re.compile('<a class="artist_preview__title" href="(.+?)">(.+?)</a>').findall(link)
    if not all_artists:
        plugin_notice('No artist results for: %s' % settings.decode_text(query))
        return_to_main_menu()
    for url1, title in all_artists:
        icon_path = os.path.join(ARTIST_ART, settings.sanitize_filename(title) + '.jpg')
        if os.path.exists(icon_path):
            iconimage = icon_path
        else:
            iconimage = iconart
        addDir(title,'http://musicmp3.ru' + url1,22,iconimage,'artists')

def search_albums(query):
    url = 'https://musicmp3.ru/search.html?text=%s&all=albums' % urllib.parse.quote_plus(normalize_search(query))
    link = GET_url(url)#.decode('utf-8')
    link = link.replace('<span class="album_report__artist">Various Artists</span>', '<a class="album_report__artist" href="/artist_various-artist.html">Various Artist</a>')
    all_albums = re.compile('<a class="album_report__link" href="(.+?)"><img class="album_report__image" src="(.+?)"/><span class="album_report__name">(.+?)</span></a>(.+?)album_report__artist" href="(.+?)">(.+?)</a>, <span class="album_report__date">(.+?)</span>').findall(link)
    #all_albums = re.compile('<a class="album_report__link" href="(.+?)"><img class="album_report__image" src="(.+?)" /><span class="album_report__name">(.+?)</span></a>(.+?)album_report__artist" href="(.+?)">(.+?)</a>, <span class="album_report__date">(.+?)</span>').findall(link)
    if not all_albums:
        plugin_notice('No album results for: %s' % settings.decode_text(query))
        return_to_main_menu()
    for url1,thumb,album,plot,artisturl,artist,year in all_albums:
        title = "%s - %s (%s)" % (artist, album, year)
        thumb = thumb.replace('al', 'alm').replace('covers', 'mcovers')
        addDir(title,'http://musicmp3.ru' + url1,5,thumb,'albums')
    setView('files', 'album')

def search_songs(query):
    playlist = []
    url = 'https://musicmp3.ru/search.html?text=%s&all=songs' % urllib.parse.quote_plus(normalize_search(query))
    link = GET_url(url)#.decode('utf-8')
    link = link.replace('<td class="song__artist song__artist--search">Various Artist</td>', '<td class="song__artist song__artist--search"><a class="song__link" href="/artist_various-artist.html">Various Artist</a></td>')
    match = re.compile('<tr class="song"><td class="song__play_button"><a class="player__play_btn js_play_btn" href="#" rel="(.+?)" title="Play track"/></td><td class="song__name song__name--search"><a class="song__link" href="(.+?)">(.+?)</a></td><td class="song__artist song__artist--search"><a class="song__link" href="(.+?)">(.+?)</a></td><td class="song__album song__album--search"><a class="song__link" href="(.+?)">(.+?)</a>').findall(link)
    if not match:
        plugin_notice('No song results for: %s' % settings.decode_text(query))
        return_to_main_menu()
    for id,songurl,song,artisturl,artist,albumurl,album in match:
        iconimage = ""
        url = 'https://listen.musicmp3.ru/' + id # 'http://files.musicmp3.ru/lofi/' + id
        #url = 'http://listen.musicmp3.ru/2f99f4bf4ce7b171/' + id
        artist = settings.decode_text(artist)
        song = settings.decode_text(song)
        album = settings.decode_text(album)
        title = "%s - %s - %s" % (artist, song, album)
        addDirAudio(title,url,10,iconimage,song,artist,album,'','')
        liz=xbmcgui.ListItem(song)
        liz.setArt({'icon': iconimage, 'thumb': iconimage}) 
        liz.setInfo('music', {'Title':song, 'Artist':artist, 'Album':album})
        liz.setProperty('mimetype', 'audio/mpeg')
        liz.setProperty('fanart_image', audio_fanart)
        playlist.append((url, liz))
    setView('music', 'song')

def album_list(name, url):
    link = GET_url(url)#.decode('utf-8')
    try:
        artist_url = regex_from_to(link, 'class="art_wrap__img" src="', '"')
        get_artist_icon(name, artist_url)
        xbmc.log("348 name = {0}\nartist_url = {1}".format(name, artist_url), xbmc.LOGINFO)
    except:
        pass
    all_albums = re.compile('<a class="album_report__link" href="(.+?)"><img alt="(.+?)" class="album_report__image" src="(.+?)"/><span class="album_report__name">(.+?)</span>(.+?)"album_report__artist" href="(.+?)">(.+?)</a>, <span class="album_report__date">(.+?)</span>').findall(link)
    #all_albums = re.compile('<a class="album_report__link" href="(.+?)"><img alt="(.+?)" class="album_report__image" src="(.+?)" /><span class="album_report__name">(.+?)</span>(.+?)"album_report__artist" href="(.+?)">(.+?)</a>, <span class="album_report__date">(.+?)</span>').findall(link)
    for url1,d1,thumb,album,plot,artisturl,artist,year in all_albums:
        title = "%s - %s - %s" % (artist, album, year)
        thumb = thumb.replace('al', 'alm').replace('covers', 'mcovers')
        addDir(title,'http://musicmp3.ru' + url1,5,thumb,'albums')
    pgnumf = url.find('page=') + 5
    pgnum = int(url[pgnumf:]) + 1
    nxtpgurl = url[:pgnumf]
    nxtpgurl = "%s%s" % (nxtpgurl, pgnum)
    addDir('>> Next page', nxtpgurl, 15, art + 'nextpage.jpg', str(pgnumf))
    setView('files', 'album')

def albums(name, url):
    duplicate = []
    link = GET_url(url)#.decode('utf-8')
    try:
        artist_url = regex_from_to(link, 'class="art_wrap__img" src="', '"')
        get_artist_icon(name, artist_url)
        xbmc.log("370 name = {0}\nartist_url = {1}".format(name, artist_url), xbmc.LOGINFO)
    except:
        pass
    all_albums = re.compile('<div class="album_report"><h5 class="album_report__heading"><a class="album_report__link" href="(.+?)"><img alt="(.+?)" class="album_report__image" src="(.+?)"/><span class="album_report__name">(.+?)</span></a></h5><div cla(.+?)lbum_report__second_line"><span class="album_report__date">(.+?)</span>').findall(link)
    #all_albums = re.compile('<div class="album_report"><h5 class="album_report__heading"><a class="album_report__link" href="(.+?)"><img alt="(.+?)" class="album_report__image" src="(.+?)"/><span class="album_report__name">(.+?)</span></a></h5><div class="album_report__second_line"><span class="album_report__date">(.+?)</span>').findall(link)
    for url1,d1,thumb,album,d2,year in all_albums:
        title = "%s - %s - %s" % (name, album, year)
        if title not in duplicate:
            duplicate.append(title)
            thumb = thumb.replace('al', 'alm').replace('covers', 'mcovers')
            addDir(title,'http://musicmp3.ru' + url1,5,thumb,'albums')
    setView('files', 'album')

def find_url(id):
    s = read_from_file(urllist)
    if id + '-' in s:
        search_list = s.split('\n')
        for list in search_list:
            if list != '':
                urlstart = list.split('-')
                urlid = urlstart[0]
                url = urlstart[1]
                if urlid == id:
                    return url
    else:
        return 'https://listen.musicmp3.ru/1d6c13041066bed9/'

def play_album(name, url, iconimage, mix, clear):
    if ' - ' in name:
        nartist=name.split(' - ')[0]
        nalbum=name.split(' - ')[1]
    else:
        nartist='Various'
        nalbum=name
    if GOLDEN_PATH:
        url=url.replace('http://','https://').replace('musicmp3','www.goldenmp3').replace('artist_','/').replace('__album_','/').replace('.html','')
    origurl=url
    if 'musicmp3' in origurl:
        std = 'id="(.+?)" itemprop="tracks" itemscope="itemscope" itemtype="http://schema.org/MusicRecording"><td class="song__play_button"><a class="player__play_btn js_play_btn" href="#" rel="(.+?)" title="Play track"/></td><td class="song__name"><div class="title_td_wrap"><meta content="(.+?)" itemprop="url"/><meta content="(.+?)" itemprop="duration"(.+?)<meta content="(.+?)" itemprop="inAlbum"/><meta content="(.+?)" itemprop="byArtist"/><span itemprop="name">(.+?)</span><div class="jp-seek-bar" data-time="(.+?)"><div class="jp-play-bar">'
        #std = 'id="(.+?)" itemprop="tracks" itemscope="itemscope" itemtype="http://schema.org/MusicRecording"><td class="song__play_button"><a class="player__play_btn js_play_btn" href="#" rel="(.+?)" title="Play track" /></td><td class="song__name"><div class="title_td_wrap"><meta content="(.+?)" itemprop="url" /><meta content="(.+?)" itemprop="duration"(.+?)<meta content="(.+?)" itemprop="inAlbum" /><meta content="(.+?)" itemprop="byArtist" /><span itemprop="name">(.+?)</span><div class="jp-seek-bar" data-time="(.+?)"><div class="jp-play-bar"></div></div></div></td><td class="(.+?)__service song__service--ringtone'
    elif 'goldenmp3' in origurl:#track,id,songurl,meta, d1,album,artist,songname,dur,artist1
        std = 'itemscope="(.+?)" itemtype="http://schema.org/MusicRecording"><td><a class="play" href="#" rel="(.+?)" title="Listen the song in low quality">(.+?)</a>(.+?)<td><div class="title_td_wrap">(.+?)<span itemprop="name">(.+?)</span>(.+?)<span class="artist">&ndash;&ensp;by (.+?)</span><div class="jp-seek-bar"><div class="jp-play-bar"></div></div></div></td><td>(.+?)</p></td><td><a class="price" href="/pricing.html"> </a></td></tr>'
        #std = 'itemscope="(.+?)" itemtype="http://schema.org/MusicRecording"><td><a class="play" href="#" rel="(.+?)" title="Listen the song in low quality">(.+?)</a>(.+?)<td><div class="title_td_wrap">(.+?)<span itemprop="(.+?)am(.+?)">(.+?)</span>&ensp;(.+?)<div class="jp-seek-bar"><div class="jp-play-bar"></div></div></div></td><td>(.+?)</p></td><td><a class="price" href="/pricing.html"> </a></td></tr>'
    else:
        std = 'prop="tracks" itemscope="(.+?)" itemtype="http://schema.org/MusicRecording"><td><a class="play" href="#" rel="(.+?)" title="Listen the song in low quality">(.+?)</td>(.+?)<div (.+?)="title_td_wrap">(.+?).<span (.+?)="name">(.+?)</span>&ensp;[(](.+?)[)]&ensp;<span class="artist">&ndash;&ensp;by (.+?)</span><div class="jp-seek-bar"><div class="jp-play-bar"></div>'
    alt = std.replace('rel="(.+?)', '')
    browse=False
    playlist=[]
    dialog = xbmcgui.Dialog()
    if mode != 6 and mix != 'mix' and mix != 'queue':
        if dialog.yesno("MP3 Streams", 'Browse songs or play full album?', 'Play Now','Browse'):
            browse=True
    match = []
    link  = GET_url(url)#.decode('utf-8')
    if 'musicmp3' in origurl:
        link = link.split('<tr class="song" ')
    elif 'goldenmp3' in origurl:
        link=regex_from_to(link,'<table class="title_list">','<div>Total')
        link = link.split('itemprop="tracks"')
    else:
        link = link.split('<tr item')
    for song in link:
        if 'rel=' in song:
            items = re.compile(std).findall(song)
            for item in items:
                match.append(item)
        else:
            items = re.compile(alt).findall(song)
            for item in items:
                item = (item[0], '', item[1], item[2], item[3], item[4], item[5], item[6], item[7], item[8])
                match.append(item)
    nItem = len(match)
    count=0
    if browse == True:
        for track,id,songurl,meta, d1,album,artist,songname,dur in match:
            count+=1
            if 'musicmp3' in origurl:
                trn = track.replace('track','')
            else:
                trn = album.replace('.&ensp','')
            if GOTHAM_FIX:
                url = find_url(trn).strip() + id
            else:
                url = 'https://listen.musicmp3.ru/' + id #'http://files.musicmp3.ru/lofi/' + id #find_url(trn).strip() + id
            songname = settings.decode_text(songname)
            if 'musicmp3' in origurl:
                artist = settings.decode_text(artist)
                album = settings.decode_text(album)
                title = "%s. %s" % (track.replace('track',''), songname)
            elif 'goldenmp3' in origurl:
                dur = artist.replace('(','').replace(')','')
                artist = settings.decode_text(nartist)
                ntrack = settings.decode_text(album)
                album = settings.decode_text(nalbum)
                title = "%s. %s - %s" % (count, ntrack, songname)
            else:
                artist = settings.decode_text(artist)
                album = settings.decode_text(name)
                title = "%s. %s" % (trn, songname)
                dur=dur.replace('(','').replace(')','')
                dur=str((int(dur.split(':')[0])*60) + int(dur.split(':')[1]))
            addDirAudio(title,url,10,iconimage,songname,artist,album,dur,'')
        return
    import playerMP3
    if mix != 'mix':
        dp = xbmcgui.DialogProgress()
        dp.create("MP3 Streams",'Creating Your Playlist')
        dp.update(0)
    for track,id,songurl,meta, d1,album,artist,songname,dur in match:
        count+=1
        if 'musicmp3' in origurl:
            trn = track.replace('track','')
        elif 'goldenmp3' in origurl:
            trn = str(count)
        else:
            trn = album.replace('.&ensp','')
        if GOTHAM_FIX:
            try:
                alturl = 'http://www.myfreemp3.eu/music/%s+%s' % (artist.replace('&amp; ', '').replace('& ', '').replace(' and ', ' '), songname.replace('&amp; ', '').replace('& ', '').replace(' and ', ' '))
                alturl = alturl.replace(' ', '+').lower()
                link = open_url(alturl)
                data = regex_from_to(link, 'data-aid=', '"').replace('"','').replace('\\','')
                url = 'http://myfreemp3.eu/play/%s_24662006e9/' % data
                response = requests.get(url,allow_redirects=False)
                url = response.headers['location']
            except:
                url = find_url(trn).strip() + id
        else:
            url = 'https://listen.musicmp3.ru/' + id  #'http://files.musicmp3.ru/lofi/' + id #find_url(trn).strip() + id
        songname = settings.decode_text(songname)
        if 'musicmp3' in origurl:
            artist = settings.decode_text(artist)
            album = settings.decode_text(album)
            title = "%s. %s" % (track.replace('track',''), songname)
        elif 'goldenmp3' in origurl:
            artist = settings.decode_text(nartist)
            ntrack = settings.decode_text(album)
            album = settings.decode_text(nalbum)
            title = "%s. %s - %s" % (count, ntrack, songname)
        else:
            artist = settings.decode_text(artist)
            album = settings.decode_text(name)
            title = "%s. %s" % (trn, songname)
            dur=str((int(dur.split(':')[0])*60) + int(dur.split(':')[1]))
        addDirAudio(title, url, 10, iconimage, songname, artist, album, dur, '')
        if 'musicmp3' in origurl:
            url, liz = playerMP3.getListItem(songname, artist, album, trn, iconimage, dur, url, fanart, 'true', GOTHAM_FIX_2)
        elif 'goldenmp3' in origurl:
            url, liz = playerMP3.getListItem(ntrack, songname, album, trn, iconimage, dur, url, fanart, 'true', GOTHAM_FIX_2)
        else:
            url, liz = playerMP3.getListItem(songname, artist, album, trn, iconimage, dur, url, fanart, 'true', GOTHAM_FIX_2)
        if FOLDERSTRUCTURE=="0":
            stored_path = os.path.join(settings.music_dir(), settings.sanitize_filename(artist), settings.sanitize_filename(album), settings.sanitize_filename(songname) + '.mp3')
        else:
            stored_path = os.path.join(settings.music_dir(), settings.sanitize_filename(artist + ' - ' + album), settings.sanitize_filename(songname) + '.mp3')
        if os.path.exists(stored_path):
            url = stored_path
        playlist.append((url, liz))
        if mix != 'mix':
            progress = len(playlist) / float(nItem) * 100
            dp.update(int(progress), 'Adding to Your Playlist' + title)
            if dp.iscanceled():
                return
    pl = get_XBMCPlaylist(clear)
    for url ,liz in playlist:
        if pl.size() < 1:
            pl.add(url,liz)
            xbmc.Player().play(pl)
        else:
            pl.add(url, liz)
        #if pl.size() > 3:
        #    break
    dp.close()
#    if float(xbmc_version) < 17:
#        newPlay(pl, clear)
#    else:
#        if clear or (not xbmc.Player().isPlayingAudio()):
#            xbmc.Player().play(pl)

def play_song(url, name, songname, artist, album, iconimage, dur, clear):
    import playerMP3
    try:
        track = int(name[:name.find('.')])
    except:
        track = 0
    url, liz = playerMP3.getListItem(songname, artist, album, track, iconimage, dur, url, fanart, 'true', GOTHAM_FIX_2)
    title=name
    if FOLDERSTRUCTURE=="0":
        stored_path = os.path.join(settings.music_dir(), settings.sanitize_filename(artist), settings.sanitize_filename(album), settings.sanitize_filename(title) + '.mp3')
    else:
        stored_path = os.path.join(settings.music_dir(), settings.sanitize_filename(artist + ' - ' + album), settings.sanitize_filename(title) + '.mp3')
    #if xbmc.Player().isPlayingAudio():
        #xbmc.Player().stop()
    if os.path.exists(stored_path):
        url = stored_path
    pl = get_XBMCPlaylist(clear)
    pl.add(url, liz)
    xbmc.Player().play(pl)
    #if clear or (not xbmc.Player().isPlayingAudio()):
        #xbmc.Player().play(pl)
    #playlist.append((newurl, liz))
    #for blob ,liz in playlist:
    #    try:
    #        if blob:
    #            pl.add(blob,liz)
    #    except:
    #        pass
    #newPlay(pl, clear)

def download_song(url, name, songname, artist, album, iconimage):
    display_name = settings.decode_text(songname or name)
    notification('MP3 Streams', 'Downloading: %s' % display_name, '3000', iconimage or iconart)
    track = track_number_from_title(name)
    filename_title = numbered_song_title(track, songname)
    safe_songname = settings.sanitize_filename(filename_title)
    artist_path = create_directory(settings.music_dir(), settings.decode_text(artist))
    album_path = create_directory(artist_path, settings.decode_text(album))
    list_data = "%s<>%s<>%s<>%s<>%s%s" % (album_path,artist,album,track,safe_songname,'.mp3')
    local_filename = os.path.join(album_path, safe_songname + '.mp3')
    headers = {'Host': 'listen.musicmp3.ru','Range': 'bytes=0-','User-Agent': 'AppleWebKit/<WebKit Rev>', 'Accept': 'audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5'}
    r = requests.get(url, headers=headers, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(): #chunk_size=1024
            if chunk:
                f.write(chunk)
                f.flush()
    #urllib.urlretrieve(url, local_filename)
    add_to_list(list_data, DOWNLOAD_LIST, False)
    notification('MP3 Streams', 'Download complete: %s' % display_name, '3000', iconimage or iconart)
'''
class DownloadMusicThread(Thread):
    def __init__(self, name, url, data_path, album_path):
        self.data = url
        self.path = data_path
        self.extpath = album_path
        Thread.__init__(self)

    def run(self):
        path = str(self.path)
        data = self.data
        extract = str(self.extpath)
        urllib.urlretrieve(data, path)
        notify = "%s,%s,%s" % ('XBMC.Notification(Download finished',clean_file_name(name, use_blanks=False),'4000)')
        xbmc.executebuiltin(notify)
        if mode!="download song":
            notify = "%s,%s,%s" % ('XBMC.Notification(Extracting songs',clean_file_name(name, use_blanks=False),'4000)')
            xbmc.executebuiltin(notify)
            time.sleep(1)
            extractfiles(path,extract)
            os.remove(path)
            notify = "%s,%s,%s" % ('XBMC.Notification(Finished',clean_file_name(name, use_blanks=False),'4000)')
            xbmc.executebuiltin(notify)
'''
def download_album(url, name, iconimage):
    nartist, nalbum = album_download_names(name)
    xbmc.log("nartist = {0}".format(nartist), xbmc.LOGINFO)
    xbmc.log("nalbum = {0}".format(nalbum), xbmc.LOGINFO)
    if GOLDEN_PATH:
        url = url.replace('http','https').replace('musicmp3','www.goldenmp3').replace('artist_','/').replace('__album_','/').replace('.html','')
    origurl = url
    xbmc.log("origurl = {0}".format(origurl), xbmc.LOGINFO)
    dialog = xbmcgui.Dialog()
    check_downloads = os.path.join(settings.music_dir(), 'downloading.txt')
    xbmc.log("check_downloads = {0}".format(check_downloads), xbmc.LOGINFO)
    if os.path.exists(check_downloads):
        dialog.ok("Album download in progress", 'Please wait for the current download to finish')
        return
    notification('MP3 Streams', 'Downloading album: %s' % settings.decode_text(name), '3000', iconimage or iconart)
    playlist = []
    link = GET_url(url)#.decode('utf-8')
    xbmc.log("link = {0}".format(link), xbmc.LOGINFO)
    if 'goldenmp3' in url:
        link = regex_from_to(link,'<table class="title_list">','<div>Total')
        match = re.compile('itemscope="(.+?)" itemtype="http://schema.org/MusicRecording"><td><a class="play" href="#" rel="(.+?)" title="Listen the song in low quality">(.+?)</a>(.+?)<td><div class="title_td_wrap">(.+?)<span itemprop="(.+?)am(.+?)">(.+?)</span>&ensp;(.+?)<div class="jp-seek-bar"><div class="jp-play-bar"></div></div></div></td><td>').findall(link)
    else:
        match = re.compile('<tr class="song" id="(.+?)" itemprop="tracks" itemscope="itemscope" itemtype="http://schema.org/MusicRecording"><td class="song__play_button"><a class="player__play_btn js_play_btn" href="#" rel="(.+?)" title="Play track"/></td><td class="song__name"><div class="title_td_wrap"><meta content="(.+?)" itemprop="url"/><meta content="(.+?)" itemprop="duration"/><meta content="(.+?)" itemprop="inAlbum"/><meta content="(.+?)" itemprop="byArtist"/><span itemprop="name">(.+?)</span><div class="jp-seek-bar" data-time="(.+?)">').findall(link)
    xbmc.log("match = {0}".format(match), xbmc.LOGINFO)
    nSong = len(match)
    count = 0
    album_path = create_directory(settings.music_dir(), nalbum)
    for track, id, songurl, meta, album, artist, songname, dur in match:
        count += 1
        songname = settings.decode_text(songname)
        if 'goldenmp3' in origurl:
            artist = settings.decode_text(nartist)
            album = settings.decode_text(nalbum)
            track = str(count)
        artist = settings.decode_text(artist)
        album = settings.decode_text(album)
        trn = track.replace('track','')
        #url = find_url(trn).strip() + id
        url = 'https://listen.musicmp3.ru/' + id #'http://files.musicmp3.ru/lofi/' + id
        playlist.append(songname)
        title = "%s. %s" % (track.replace('track',''), songname)
        safe_title = settings.sanitize_filename(title)
        list_data = "%s<>%s<>%s<>%s<>%s%s" % (album_path,artist,album,trn,safe_title,'.mp3')
        create_file(settings.music_dir(), "downloading.txt")
        local_filename = os.path.join(album_path, safe_title + '.mp3')
        headers = {'Host':'listen.musicmp3.ru', 'Range':'bytes=0-', 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:44.0) Gecko/20100101 Firefox/44.0', 'Accept':'audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5','Referer':'https://www.goldenmp3.ru'}
        r = requests.get(url, headers=headers, stream=True)
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
        #urllib.urlretrieve(url, local_filename)
        text = "%s of %s tracks downloaded" % (trn, nSong)
        notification(artist + ' ' + album, text, '3000', iconimage)
        add_to_list(list_data, DOWNLOAD_LIST, False)
    notification(nartist + ' ' + nalbum, 'Album download finished', '3000', iconimage)
    if os.path.exists(download_lock_path()):
        os.remove(download_lock_path())

def clear_lock():
    if os.path.exists(download_lock_path()):
        os.remove(download_lock_path())
        notification('Downloads', 'Unlocked', '3000', iconart)

def id3_tags():
    id3Thread = Getid3Thread()
    id3Thread.start()

class Getid3Thread(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        if os.path.isfile(DOWNLOAD_LIST):
            s = read_from_file(DOWNLOAD_LIST)
            search_list = s.split('\n')
            for list in search_list:
                if list != '':
                    splitlist = list.split('<>')
                    filename = os.path.join(splitlist[0], splitlist[4])
                    artist = splitlist[1]
                    album = splitlist[2]
                    track = splitlist[3]
                    trackname = splitlist[4]
                    tracktitle = trackname
                    if os.path.exists(filename):
                        audio = MP3(filename, ID3=EasyID3)
                        audio["title"] = tracktitle
                        audio["artist"] = artist
                        audio["album"] = album
                        audio["tracknumber"] = track
                        audio.save()
                        remove_from_list(list, DOWNLOAD_LIST)
        notification('Music Library', 'ID3 tags updated', '3000', iconart)
        xbmc.executebuiltin('UpdateLibrary(music)')

def get_artist_icon(name, url):
    xbmc.log("724 name = {0}\nurl = {1}".format(name, url), xbmc.LOGINFO)
    data_path = os.path.join(ARTIST_ART, settings.sanitize_filename(name) + '.jpg')
    xbmc.log("726 datapath = {0}".format(data_path), xbmc.LOGINFO)
    if not os.path.exists(data_path):
        dlThread = DownloadIconThread(name, url, data_path)
        dlThread.start()

def instant_mix():
    groupname = select_favourite_group('All Songs', FAV_SONG, 5, 'No favourite songs saved yet')
    if not groupname:
        return_to_previous_menu()
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()
    for line in read_favourite_lines(FAV_SONG):
        parts = line.split('<>')
        if len(parts) < 5:
            continue
        artist = settings.decode_text(parts[0])
        album = settings.decode_text(parts[1])
        songname = settings.decode_text(parts[2])
        url1 = parts[3]
        iconimage = parts[4]
        plname = parts[5] if len(parts) > 5 else 'Ungrouped'
        if plname == groupname or groupname == 'All Songs':
            play_song(url1, songname, songname, artist, album, iconimage, '', False)
    playlist.shuffle()

def instant_mix_album():
    groupname = select_favourite_group('All Albums', FAV_ALBUM, 3, 'No favourite albums saved yet')
    if not groupname:
        return_to_previous_menu()
    shuffleThread = ShuffleAlbumThread(groupname)
    shuffleThread.start()

class ShuffleAlbumThread(Thread):
    def __init__(self,groupname):
        self.groupname=groupname
        Thread.__init__(self)

    def run(self):
        groupname=self.groupname
        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        playlist.clear()
        if os.path.isfile(FAV_ALBUM):
            s = read_from_file(FAV_ALBUM)
            search_list = s.split('\n')
            for list in search_list:
                if list != '':
                    list1 = list.split('<>')
                    title = settings.decode_text(list1[0])
                    url = list1[1]
                    thumb = list1[2]
                    plname = list1[3] if len(list1) > 3 else 'Ungrouped'
                    if plname == groupname or groupname == 'All Albums':
                        play_album(title, url, thumb, 'mix', False)
                        playlist.shuffle()
                    time.sleep(15)

class DownloadIconThread(Thread):
    def __init__(self, name, url, data_path):
        self.data = url
        self.path = data_path
        Thread.__init__(self)

    def run(self):
        path = str(self.path)
        data = self.data
        urllib.request.urlretrieve(data, path)


def favourite_artists():
    lines = read_favourite_lines(FAV_ARTIST)
    if not lines:
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), 'No favourite artists saved yet', iconart, 3000)
        return_to_previous_menu()
    for line in lines:
        parts = line.split('<>')
        if len(parts) < 2:
            continue
        title = settings.decode_text(parts[0])
        url = parts[1]
        icon_path = os.path.join(ARTIST_ART, settings.sanitize_filename(title) + '.jpg')
        iconimage = icon_path if os.path.exists(icon_path) else iconart
        addDir(title, url, 22, iconimage, 'artists')

def favourite_albums():
    if not read_favourite_lines(FAV_ALBUM):
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), 'No favourite albums saved yet', iconart, 3000)
        return_to_previous_menu()
    groupname = select_favourite_group('All Albums', FAV_ALBUM, 3, 'No favourite albums saved yet')
    if not groupname:
        return_to_previous_menu()
    for line in read_favourite_lines(FAV_ALBUM):
        parts = line.split('<>')
        if len(parts) < 3:
            continue
        title = settings.decode_text(parts[0])
        url = parts[1]
        thumb = parts[2]
        plname = parts[3] if len(parts) > 3 else 'Ungrouped'
        if plname == groupname or groupname == 'All Albums':
            addDir(title, url, 5, thumb, plname + 'qqalbums')

def favourite_songs():
    if not read_favourite_lines(FAV_SONG):
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), 'No favourite songs saved yet', iconart, 3000)
        return_to_previous_menu()
    groupname = select_favourite_group('All Songs', FAV_SONG, 5, 'No favourite songs saved yet')
    if not groupname:
        return_to_previous_menu()
    for line in read_favourite_lines(FAV_SONG):
        parts = line.split('<>')
        if len(parts) < 5:
            continue
        artist = settings.decode_text(parts[0])
        album = settings.decode_text(parts[1])
        title = settings.decode_text(parts[2])
        url = parts[3]
        iconimage = parts[4]
        plname = parts[5] if len(parts) > 5 else 'Ungrouped'
        if plname == groupname or groupname == 'All Songs':
            display = '%s - %s - %s' % (title, artist, album)
            addDirAudio(display, url, 10, iconimage, title, artist, album, 'qq' + plname, 'favsong')

def add_favourite(name, url, dir, text):
    splitdata = url.split('<>')
    name = settings.decode_text(name)
    if 'artist' in dir:
        artist = settings.decode_text(splitdata[0])
        url1 = splitdata[1]
        if add_to_list(url, dir, False):
            favourite_notice('Added to Favourite Artists: %s' % name)
        else:
            favourite_notice('Already in Favourite Artists: %s' % name)
        link = GET_url(url1)
        try:
            artist_url = regex_from_to(link, 'class="art_wrap__img" src="', '"')
            get_artist_icon(artist, artist_url)
        except:
            pass
        return
    existing_groups = []
    for line in read_favourite_lines(dir):
        parts = line.split('<>')
        if len(parts) > 3 and parts[3] not in existing_groups:
            existing_groups.append(parts[3])
    plname = pick_favourite_group(existing_groups)
    if not plname:
        return
    url = "%s<>%s" % (url, plname)
    icon = splitdata[2] if len(splitdata) > 2 else iconart
    if add_to_list(url, dir, False):
        favourite_notice('Added to Favourite Albums: %s (%s)' % (name, plname), icon)
    else:
        favourite_notice('Already in Favourite Albums: %s' % name, icon)

def add_favourite_song(name, url, dir, text):
    existing_groups = []
    for line in read_favourite_lines(dir):
        parts = line.split('<>')
        if len(parts) > 5 and parts[5] not in existing_groups:
            existing_groups.append(parts[5])
    plname = pick_favourite_group(existing_groups)
    if not plname:
        return
    splitdata = url.split('<>')
    songname = settings.decode_text(splitdata[2])
    iconimage = splitdata[4] if len(splitdata) > 4 else iconart
    url = "%s<>%s" % (url, plname)
    if add_to_list(url, dir, False):
        favourite_notice('Added to Favourite Songs: %s (%s)' % (songname, plname), iconimage)
    else:
        favourite_notice('Already in Favourite Songs: %s' % songname, iconimage)

def remove_from_favourites(name, url, dir, text):
    name = settings.decode_text(name)
    icon = iconart
    label = 'Favourites'
    if 'artist' in dir:
        label = 'Favourite Artists'
    elif 'album' in dir:
        label = 'Favourite Albums'
        parts = url.split('<>')
        if len(parts) > 2:
            icon = parts[2]
    elif 'song' in dir:
        label = 'Favourite Songs'
        parts = url.split('<>')
        if len(parts) > 4:
            icon = parts[4]
    if remove_from_list(url, dir, refresh=False):
        favourite_notice('Removed from %s: %s' % (label, name), icon)
        if not read_favourite_lines(dir):
            return_to_previous_menu()
        xbmc.executebuiltin("Container.Refresh")
    else:
        favourite_notice('Could not remove from %s: %s' % (label, name), icon)

def normalize_fav_name(text):
    return settings.decode_text(text).lower().replace(' and ', ' & ').strip()

def favourite_entry_key(line, fav_type):
    parts = line.split('<>')
    if fav_type == 'song' and len(parts) >= 4:
        return (
            normalize_fav_name(parts[0]),
            normalize_fav_name(parts[1]),
            normalize_fav_name(parts[2]),
            parts[3],
        )
    if fav_type == 'album' and len(parts) >= 2:
        return (normalize_fav_name(parts[0]), parts[1])
    if fav_type == 'artist' and len(parts) >= 2:
        return (normalize_fav_name(parts[0]), parts[1])
    return None

def favourite_file_type(file_path):
    if 'song' in file_path:
        return 'song'
    if 'album' in file_path:
        return 'album'
    return 'artist'

def find_favourite_index(query, search_file):
    lines = read_favourite_lines(search_file)
    if query in lines:
        return lines.index(query)
    fav_type = favourite_file_type(search_file)
    query_key = favourite_entry_key(query, fav_type)
    if not query_key:
        return -1
    for index, line in enumerate(lines):
        if favourite_entry_key(line, fav_type) == query_key:
            return index
    return -1

def find_list(query, search_file):
    return find_favourite_index(query, search_file)

def add_to_list(list, file, refresh):
    if find_favourite_index(list, file) >= 0:
        return False
    if os.path.isfile(file):
        content = read_from_file(file)
    else:
        content = ""
    lines = content.split('\n')
    s = '%s\n' % list
    for line in lines:
        if len(line) > 0:
            s = s + line + '\n'
    write_to_file(file, s)
    if refresh == True:
        xbmc.executebuiltin("Container.Refresh")
    return True

def remove_from_list(list, file, refresh=True):
    index = find_favourite_index(list, file)
    if index >= 0:
        lines = read_favourite_lines(file)
        lines.pop(index)
        s = ''
        for line in lines:
            if len(line) > 0:
                s = s + line + '\n'
        write_to_file(file, s)
        if refresh:
            xbmc.executebuiltin("Container.Refresh")
        return True
    return False

def write_to_file(path, content, append=False, silent=False):
    try:
        if append:
            f = open(path, 'a')
        else:
            f = open(path, 'w')
        f.write(content)
        f.close()
        return True
    except:
        if not silent:
            print(("Could not write to " + path))
        return False

def read_from_file(path, silent=False):
    try:
        f = open(path, 'r')
        r = f.read()
        f.close()
        return str(r)
    except:
        if not silent:
            print(("Could not read from " + path))
        return None

def notification(title, message, ms, nart):
    try:
        duration = int(ms)
    except:
        duration = 3000
    icon = nart or iconart
    try:
        xbmcgui.Dialog().notification(title, message, icon, duration, False)
    except TypeError:
        try:
            xbmcgui.Dialog().notification(title, message, icon, duration)
        except:
            xbmc.executebuiltin('Notification(%s,%s,%s,%s)' % (title, message, duration, icon))

def favourite_notice(message, icon=None):
    notification('MP3 Streams', message, '3000', icon or iconart)

def get_params():
    param = []
    paramstring = sys.argv[2]
    if len(paramstring) >= 2:
            params = sys.argv[2]
            cleanedparams = params.replace('?','')
            if (params[len(params)-1] == '/'):
                    params = params[0:len(params)-2]
            pairsofparams = cleanedparams.split('&')
            param = {}
            for i in range(len(pairsofparams)):
                    splitparams = {}
                    splitparams = pairsofparams[i].split('=')
                    if (len(splitparams)) == 2:
                            param[splitparams[0]] = splitparams[1]
    return param

def get_XBMCPlaylist(clear):
    pl = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    if clear:
        pl.clear()
    return pl

def clear_playlist():
    pl = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    pl.clear()
    notification('Playlist', 'Cleared', '2000', iconart)

def create_directory(dir_path, dir_name=None):
    if dir_name:
        dir_path = os.path.join(dir_path, settings.sanitize_filename(dir_name))
    dir_path = dir_path.strip()
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path

def create_file(dir_path, file_name=None):
    if file_name:
        file_path = os.path.join(dir_path, settings.sanitize_filename(file_name))
    file_path = file_path.strip()
    if not os.path.exists(file_path):
        f = open(file_path, 'w')
        f.write('')
        f.close()
    return file_path

def regex_from_to(text, from_string, to_string, excluding=True):
    if excluding:
        r = re.search("(?i)" + from_string + "([\S\s]+?)" + to_string, text).group(1)
    else:
        r = re.search("(?i)(" + from_string + "[\S\s]+?" + to_string + ")", text).group(1)
    return r

def regex_get_all(text, start_with, end_with):
    r = re.findall("(?i)(" + start_with + "[\S\s]+?" + end_with + ")", text) 
    return r

def setView(content, viewType):
    if content:
        xbmcplugin.setContent(int(sys.argv[1]), content)

def addLink(name,url,iconimage):
        ok = True
        liz = xbmcgui.ListItem(name, iconImage="DefaultVideo.png", thumbnailImage=iconimage)
        liz.setInfo( type="Audio", infoLabels={ "Title": name } )
        liz.setProperty('fanart_image', audio_fanart)
        ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=liz)
        return ok

def addDir(name, url, mode, iconimage, type):
        name = settings.decode_text(name)
        type1 = type
        type = type.replace('qq','')
        suffix = ""
        if type == "artists":
            list = "%s<>%s" % (str(name).lower(),url)
        else:
            if 'qq' in type1:
                spltype1 = type1.split('qq')
                list = "%s<>%s<>%s<>%s" % (str(name).lower(),url,str(iconimage),spltype1[0])
            else:
                list = "%s<>%s<>%s" % (str(name).lower(),url,str(iconimage))
        list = list.replace(',', '')
        u = sys.argv[0]+"?url="+urllib.parse.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.parse.quote_plus(name)+"&iconimage="+urllib.parse.quote_plus(iconimage)+"&list="+str(list)+"&type="+str(type)
        ok = True
        contextMenuItems = []
        if type == "artists":
            if find_list(list, FAV_ARTIST) < 0:
                suffix = ""
                contextMenuItems.append(("[COLOR lime]Add to Favourite Artists[/COLOR]",'RunPlugin(%s?name=%s&url=%s&mode=61)' % (sys.argv[0], urllib.parse.quote_plus(name), urllib.parse.quote_plus(list))))
            else:
                suffix = ' [COLOR lime]+[/COLOR]'
                contextMenuItems.append(("[COLOR orange]Remove from Favourite Artists[/COLOR]",'RunPlugin(%s?name=%s&url=%s&mode=62)' % (sys.argv[0], urllib.parse.quote_plus(name), urllib.parse.quote_plus(list))))
        if 'album' in type:
            download_album = '%s?name=%s&url=%s&iconimage=%s&mode=202' % (sys.argv[0], urllib.parse.quote(name), url, iconimage)
            xbmc.log("1230 sys.argv[0] = {0}\nurllib.quote(name) = {1}\nurl = {2}\niconimage = {3}".format(sys.argv[0], urllib.parse.quote(name), url, iconimage), xbmc.LOGINFO)
            contextMenuItems.append(('[COLOR cyan]Download Album[/COLOR]', 'RunPlugin(%s)' % download_album))
            if os.path.exists(download_lock_path()):
                contextMenuItems.append(("Clear Download Lock",'RunPlugin(%s?name=%s&url=%s&iconimage=%s&mode=333)'%(sys.argv[0], urllib.parse.quote(name), url, iconimage)))
            if QUEUE_ALBUMS:
                play_music = '%s?name=%s&url=%s&iconimage=%s&mode=7' % (sys.argv[0], urllib.parse.quote(name), url, iconimage)
                contextMenuItems.append(('[COLOR cyan]Play/Browse Album[/COLOR]', 'RunPlugin(%s)' % play_music))
            else:
                queue_music = '%s?name=%s&url=%s&iconimage=%s&mode=6' % (sys.argv[0], urllib.parse.quote(name), url, iconimage)
                contextMenuItems.append(('[COLOR cyan]Queue Album[/COLOR]', 'RunPlugin(%s)' % queue_music))
            if not 'qq' in type1:
                suffix = ""
                contextMenuItems.append(("[COLOR lime]Add to Favourite Albums[/COLOR]",'RunPlugin(%s?name=%s&url=%s&mode=64)' % (sys.argv[0], urllib.parse.quote_plus(name.replace(',', '')), urllib.parse.quote_plus(list))))
            else:
                suffix = ' [COLOR lime]+[/COLOR]'
                contextMenuItems.append(("[COLOR orange]Remove from Favourite Albums[/COLOR]",'RunPlugin(%s?name=%s&url=%s&mode=65)' % (sys.argv[0], urllib.parse.quote_plus(name.replace(',', '')), urllib.parse.quote_plus(list))))
        liz = xbmcgui.ListItem(name + suffix)
        liz.setArt({'icon': "DefaultAudio.png", 'thumb': iconimage}) 
        liz.addContextMenuItems(contextMenuItems, replaceItems=False)
        liz.setInfo( type="Audio", infoLabels={ "Title": name } )
        liz.setProperty('fanart_image', fanart)
        ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=u,listitem=liz,isFolder=True)
        return ok

def addDirAudio(name, url, mode, iconimage, songname, artist, album, dur, type):
        name = settings.decode_text(name)
        songname = settings.decode_text(songname)
        artist = settings.decode_text(artist)
        album = settings.decode_text(album)
        suffix = ""
        if 'qq' in dur:
            list = "%s<>%s<>%s<>%s<>%s<>%s" % (str(artist),str(album),str(songname).lower(),url,str(iconimage),str(dur).replace('qq',''))
        else:
            list = "%s<>%s<>%s<>%s<>%s" % (str(artist),str(album),str(songname).lower(),url,str(iconimage))
        list = list.replace(',', '')
        contextMenuItems = []
        u = sys.argv[0]+"?url="+urllib.parse.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.parse.quote_plus(name)+"&iconimage="+urllib.parse.quote_plus(iconimage)+"&songname="+urllib.parse.quote_plus(songname)+"&artist="+urllib.parse.quote_plus(artist)+"&album="+urllib.parse.quote_plus(album)+"&dur="+str(dur)+"&type="+str(type)
        ok=True
        if os.path.exists(download_lock_path()):
            contextMenuItems.append(("Clear Download Lock",'RunPlugin(%s?url=%s&name=%s&iconimage=%s&songname=%s&artist=%s&album=%s&mode=333)' % (sys.argv[0], urllib.parse.quote_plus(url), urllib.parse.quote_plus(name), urllib.parse.quote_plus(iconimage), urllib.parse.quote_plus(songname), urllib.parse.quote_plus(artist), urllib.parse.quote_plus(album))))
        download_song = '%s?url=%s&name=%s&iconimage=%s&songname=%s&artist=%s&album=%s&mode=201' % (sys.argv[0], urllib.parse.quote_plus(url), urllib.parse.quote_plus(name), urllib.parse.quote_plus(iconimage), urllib.parse.quote_plus(songname), urllib.parse.quote_plus(artist), urllib.parse.quote_plus(album))
        contextMenuItems.append(('[COLOR cyan]Download Song[/COLOR]', 'RunPlugin(%s)' % download_song))
        if QUEUE_SONGS:
            play_song = '%s?url=%s&name=%s&iconimage=%s&songname=%s&artist=%s&album=%s&dur=%s&mode=18' % (sys.argv[0], urllib.parse.quote_plus(url), urllib.parse.quote_plus(name), urllib.parse.quote_plus(iconimage), urllib.parse.quote_plus(songname), urllib.parse.quote_plus(artist), urllib.parse.quote_plus(album), urllib.parse.quote_plus(str(dur)))
            contextMenuItems.append(('[COLOR cyan]Play Song[/COLOR]', 'RunPlugin(%s)' % play_song))
        else:
            queue_song = '%s?url=%s&name=%s&iconimage=%s&songname=%s&artist=%s&album=%s&dur=%s&mode=11' % (sys.argv[0], urllib.parse.quote_plus(url), urllib.parse.quote_plus(name), urllib.parse.quote_plus(iconimage), urllib.parse.quote_plus(songname), urllib.parse.quote_plus(artist), urllib.parse.quote_plus(album), urllib.parse.quote_plus(str(dur)))
            contextMenuItems.append(('[COLOR cyan]Queue Song[/COLOR]', 'RunPlugin(%s)' % queue_song))
        if type != 'favsong':
            suffix = ""
            contextMenuItems.append(("[COLOR lime]Add to Favourite Songs[/COLOR]",'RunPlugin(%s?name=%s&url=%s&mode=67)' % (sys.argv[0], urllib.parse.quote_plus(name.replace(',', '')), urllib.parse.quote_plus(list))))
        else:
            suffix = ' [COLOR lime]+[/COLOR]'
            contextMenuItems.append(("[COLOR orange]Remove from Favourite Songs[/COLOR]",'RunPlugin(%s?name=%s&url=%s&mode=68)' % (sys.argv[0], urllib.parse.quote_plus(name.replace(',', '')), urllib.parse.quote_plus(list))))
        liz = xbmcgui.ListItem(name + suffix)
        liz.setArt({'icon': "DefaultAudio.png", 'thumb': iconimage}) 
        liz.addContextMenuItems(contextMenuItems, replaceItems=False)
        liz.setInfo( type="Audio", infoLabels={ "Title": songname or name, "Artist": artist, "Album": album } )
        if HIDE_FANART == False:
            liz.setProperty('fanart_image', fanart)
        ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=u,listitem=liz)
        return ok

params = get_params()
url = None
name = None
mode = None
songname = None
artist= None
album = None
iconimage = None 
dur = None
type = None

try:
        url = urllib.parse.unquote_plus(params["url"])
except:
        pass
try:
        name = settings.decode_text(urllib.parse.unquote_plus(params["name"]))
except:
        pass
try:
        mode=int(params["mode"])
except:
        pass
try:
        iconimage = urllib.parse.unquote_plus(params["iconimage"])
except:
        pass
try:
        songname = settings.decode_text(urllib.parse.unquote_plus(params["songname"]))
except:
        pass
try:
        artist = settings.decode_text(urllib.parse.unquote_plus(params["artist"]))
except:
        pass
try:
        album = settings.decode_text(urllib.parse.unquote_plus(params["album"]))
except:
        pass
try:
        list = str(params["list"])
except:
        pass
try:
        dur = str(params["dur"])
except:
        pass
try:
        type = str(params["type"])
except:
        pass

if mode == None or url==None or len(url)<1:
    CATEGORIES()
    #get_cookie()

elif mode == 4:
     charts()

elif mode ==5:
    if QUEUE_ALBUMS:
        play_album(name, url, iconimage, 'queue', False)
    else:
        play_album(name, url, iconimage, '', True)

elif mode ==6:
    play_album(name, url, iconimage,'', False)

elif mode ==7:
    play_album(name, url, iconimage,'browse', False)

elif mode ==8:
    ADDON.openSettings()

elif mode == 10:
    if QUEUE_SONGS:
        play_song(url, name, songname, artist, album, iconimage, dur, False)
    else:
        play_song(url, name, songname, artist, album, iconimage, dur, True)

elif mode == 11:
    play_song(url, name, songname, artist, album, iconimage, dur, False)

elif mode == 18:
    play_song(url, name, songname, artist, album, iconimage, dur, True)

elif mode == 21:
    artists(url)

elif mode == 31:
    all_artists(name, url)

elif mode == 41:
    sub_dir(name, url, iconimage)

elif mode == 22:
    albums(name, url)

elif mode == 12:
    genres(name, url)

elif mode == 13:
    all_genres(name, url)

elif mode == 14:
    genre_sub_dir(name, url, iconimage)

elif mode == 16:
    genre_sub_dir2(name, url, iconimage)

elif mode == 15:
    album_list(name, url)

elif mode == 24:
    search(name, url)

elif mode == 25:
    search_albums(name)

elif mode == 26:
    search_songs(name)

elif mode == 27:
    search_artists(name)

elif mode == 28:
    search_songs(url)

elif mode == 61:
    add_favourite(name, url, FAV_ARTIST, "Added to Favourites")

elif mode == 62:
    remove_from_favourites(name, url, FAV_ARTIST, "Removed from Favourites")

elif mode == 63:
    favourite_artists()

elif mode == 64:
    add_favourite(name, url, FAV_ALBUM, "Added to Favourites")

elif mode == 65:
    remove_from_favourites(name, url, FAV_ALBUM, "Removed from Favourites")

elif mode == 67:
    add_favourite_song(name, url, FAV_SONG, 'Added to Favourites')

elif mode == 69:
    favourite_songs()

elif mode == 68:
    remove_from_favourites(name, url, FAV_SONG, "Removed from Favourites")

elif mode == 66:
    favourite_albums()

elif mode == 99:
    instant_mix()

elif mode == 89:
    instant_mix_album()

elif mode == 100:
    clear_playlist()

elif mode == 101:
    charts()

elif mode == 102:
    chart_lists(name, url)

elif mode == 201:
    download_song(url, name, songname, artist, album, iconimage)

elif mode == 202:
    download_album(url, name, iconimage)

elif mode == 300:
    id3_tags()

elif mode == 333:
    clear_lock()

elif mode == 400:
   compilations_menu()

elif mode == 401:
   compilations_list(name, url, iconimage, type)

elif mode == 500:
    ADDON.openSettings()

elif mode == 999:
    import playerMP3
    playerMP3.play(sys, params)

if mode in PLUGIN_ACTION_MODES:
    sys.exit(0)

xbmcplugin.endOfDirectory(int(sys.argv[1]))
