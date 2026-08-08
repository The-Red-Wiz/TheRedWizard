# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import datetime
import random

import simplejson as json
import six
from six.moves import urllib_parse, zip, reduce

try:
    #from infotagger.listitem import ListItemInfoTag
    from resources.lib.modules.listitem import ListItemInfoTag
except:
    pass

from resources.lib.modules import cleantitle
from resources.lib.modules import client
from resources.lib.modules import control
from resources.lib.modules import scrape_sources
from resources.lib.modules import trakt
from resources.lib.modules import workers
from resources.lib.modules import log_utils

try:
    from sqlite3 import dbapi2 as database
except:
    from pysqlite2 import dbapi2 as database
try:
    import resolveurl
except:
    pass

kodi_version = control.getKodiVersion()


class sources:
    def __init__(self):
        #control.moderator()
        self.getConstants()
        self.sources = []
        self.filtered_sources = []
        self.debug_resolve = control.setting('addon.debug_resolve')
        self.quality_artwork = control.setting('quality.artwork') or 'false'
        self.quality_images = os.path.join(control.addonPath, 'resources/images/quality', '')
        self.max_quality = control.setting('quality.max') or '0'
        self.max_quality = int(self.max_quality)
        self.min_quality = control.setting('quality.min') or '3'
        self.min_quality = int(self.min_quality)
        self.pre_emp = control.setting('preemptive.termination') or 'false'
        self.pre_emp_type = control.setting('preemptive.type') or '0'
        self.pre_emp_limit = int(control.setting('preemptive.limit'))
        self.sort_provider = control.setting('sort.provider') or 'true'
        self.sort_hoster = control.setting('sort.hoster') or 'true'
        self.remove_cam = control.setting('remove.cam') or 'false'
        self.remove_captcha = control.setting('remove.captcha') or 'false'
        self.remove_hevc = control.setting('remove.hevc') or 'false'
        self.remove_dupes = control.setting('remove.dupes') or 'true'


    def errorForSources(self):
        control.abort_plugin_resolve()
        control.infoDialog('Error : No Stream Available.', sound=False, icon='INFO')


    def getConstants(self):
        self.itemProperty = 'plugin.video.gratisred.container.items'
        self.metaProperty = 'plugin.video.gratisred.container.meta'
        self.sourceFile = control.providercacheFile
        from resources.lib.sources import sources
        self.sourceDict = sources()
        self.hostDict = self.getHostDict()
        self.hostcapDict = ['flashx.tv', 'flashx.to', 'uptobox.com', 'uptostream.com', 'vshare.eu', 'rabbitstream.net', 'dokicloud.one']
        self.hostblockDict = ['youtube.com', 'youtu.be', 'youtube-nocookie.com']
        self.hostDict = [x for x in self.hostDict if not x in self.hostblockDict]


    def getHostDict(self):
        try:
            hostDict = resolveurl.relevant_resolvers(order_matters=True)
            hostDict = [i.domains for i in hostDict if not '*' in i.domains]
            hostDict = [i.lower() for i in reduce(lambda x, y: x + y, hostDict)]
            hostDict = [x for y, x in enumerate(hostDict) if x not in hostDict[:y]]
            return hostDict
        except:
            log_utils.log('getHostDict', 1)
            return []


    def sourcesResolve(self, item, info=False):
        try:
            self.url = None
            u = url = item['url']
            direct = item['direct']
            local = item.get('local', False)
            provider = item['provider']
            call = [i[1] for i in self.sourceDict if i[0] == provider][0]
            u = url = call.resolve(url)
            u = url = scrape_sources.prepare_link(url)
            if url == None or (not '://' in url and not local):
                raise Exception("url error")
            if not local:
                url = url[8:] if url.startswith('stack:') else url
                urls = []
                for part in url.split(' , '):
                    u = part
                    if not direct == True:
                        if control.setting('resolve.dbird') == 'true':
                            hmf = resolveurl.HostedMediaFile(url=u, include_disabled=True, include_universal=True)
                        else:
                            hmf = resolveurl.HostedMediaFile(url=u, include_disabled=True, include_universal=False)
                        if hmf.valid_url() == True:
                            part = hmf.resolve()
                    urls.append(part)
                url = 'stack://' + ' , '.join(urls) if len(urls) > 1 else urls[0]
            if url == False or url == None:
                raise Exception("url error")
            ext = url.split('?')[0].split('&')[0].split('|')[0].rsplit('.')[-1].replace('/', '').lower()
            if ext == 'rar':
                raise Exception("url error")
            try:
                headers = url.rsplit('|', 1)[1]
            except:
                headers = ''
            headers = urllib_parse.quote_plus(headers).replace('%3D', '=') if ' ' in headers else headers
            headers = dict(urllib_parse.parse_qsl(headers))
            if url.startswith('http') and '.m3u8' in url:
                try:
                    result = client.request(url.split('|')[0], headers=headers, output='geturl', timeout='10')
                except:
                    pass
            elif url.startswith('http'):
                try:
                    result = client.request(url.split('|')[0], headers=headers, output='chunk', timeout='10')
                except:
                    pass
            self.url = url
            return url
        except Exception as e:
            log_utils.log('Resolve failure: ({}) for url: {}'.format(e, item['url']))
            if self.debug_resolve == 'true':
                log_utils.log('sourcesResolve', 1)
            if info == True:
                self.errorForSources()
            return


    def sourcesDialog(self, items):
        try:
            labels = [i['label'] for i in items]
            select = control.selectDialog(labels)
            if select == -1:
                return 'close://'
            next = [y for x,y in enumerate(items) if x >= select]
            prev = [y for x,y in enumerate(items) if x < select][::-1]
            items = [items[select]]
            items = [i for i in items + next + prev][:40]
            header = control.addonInfo('name') + ': Resolving...'
            progressDialog = control.progressDialog if control.setting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(header, '')
            #progressDialog.update(0)
            block = None
            for i in range(len(items)):
                try:
                    if items[i]['source'] == block:
                        raise Exception()
                    w = workers.Thread(self.sourcesResolve, items[i])
                    w.start()
                    label = re.sub(r' {2,}', ' ', str(items[i]['label']))
                    try:
                        if progressDialog.iscanceled():
                            break
                        progressDialog.update(int((100 / float(len(items))) * i), label)
                    except:
                        progressDialog.update(int((100 / float(len(items))) * i), str(header) + '[CR]' + label)
                    offset = 60 * 2 if items[i].get('source').lower() in self.hostcapDict else 0
                    m = ''
                    for x in range(3600):
                        try:
                            if control.monitor.abortRequested():
                                return sys.exit()
                            if progressDialog.iscanceled():
                                return progressDialog.close()
                        except:
                            pass
                        k = control.condVisibility('Window.IsActive(virtualkeyboard)')
                        if k:
                            m += '1'; m = m[-1]
                        if (w.is_alive() == False or x > 30 + offset) and not k:
                            break
                        k = control.condVisibility('Window.IsActive(yesnoDialog)')
                        if k:
                            m += '1'; m = m[-1]
                        if (w.is_alive() == False or x > 30 + offset) and not k:
                            break
                        time.sleep(0.5)
                    for x in range(30):
                        try:
                            if control.monitor.abortRequested():
                                return sys.exit()
                            if progressDialog.iscanceled():
                                return progressDialog.close()
                        except:
                            pass
                        if m == '':
                            break
                        if w.is_alive() == False:
                            break
                        time.sleep(0.5)
                    if w.is_alive() == True:
                        block = items[i]['source']
                    if self.url == None:
                        raise Exception()
                    self.selectedSource = items[i]['label']
                    try:
                        progressDialog.close()
                    except:
                        pass
                    control.execute('Dialog.Close(virtualkeyboard)')
                    control.execute('Dialog.Close(yesnoDialog)')
                    return self.url
                except:
                    pass
            try:
                progressDialog.close()
            except:
                pass
            del progressDialog
        except:
            try:
                progressDialog.close()
            except:
                pass
            del progressDialog
            log_utils.log('sourcesDialog', 1)


    def sourcesDirect(self, items):
        filter = [i for i in items if i['source'].lower() in self.hostcapDict]
        items = [i for i in items if not i in filter]
        items = [i for i in items if ('autoplay' in i and i['autoplay'] == True) or not 'autoplay' in i]
        if control.setting('autoplay.sd') == 'true':
            items = [i for i in items if not i['quality'].lower() in ['4k', '1080p', '720p', 'hd']]
        u = None
        header = control.addonInfo('name') + ': Resolving...'
        try:
            control.sleep(1000)
            progressDialog = control.progressDialog if control.setting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(header, '')
            #progressDialog.update(0)
        except:
            pass
        for i in range(len(items)):
            label = re.sub(r' {2,}', ' ', str(items[i]['label']))
            try:
                if progressDialog.iscanceled():
                    break
                progressDialog.update(int((100 / float(len(items))) * i), label)
            except:
                progressDialog.update(int((100 / float(len(items))) * i), str(header) + '[CR]' + label)
            try:
                if control.monitor.abortRequested():
                    return sys.exit()
                url = self.sourcesResolve(items[i])
                if u == None:
                    u = url
                if not url == None:
                    break
            except:
                pass
        try:
            progressDialog.close()
        except:
            pass
        del progressDialog
        return u


    def prepareSources(self):
        try:
            control.makeFile(control.dataPath)
            dbcon = database.connect(self.sourceFile)
            dbcur = dbcon.cursor()
            dbcur.execute("CREATE TABLE IF NOT EXISTS rel_url (""source TEXT, ""imdb_id TEXT, ""season TEXT, ""episode TEXT, ""rel_url TEXT, ""UNIQUE(source, imdb_id, season, episode)"");")
            dbcur.execute("CREATE TABLE IF NOT EXISTS rel_src (""source TEXT, ""imdb_id TEXT, ""season TEXT, ""episode TEXT, ""hosts TEXT, ""added TEXT, ""UNIQUE(source, imdb_id, season, episode)"");")
        except:
            pass


    def getMovieSource(self, title, localtitle, aliases, year, imdb, tmdb, source, call):
        try:
            dbcon = database.connect(self.sourceFile)
            dbcur = dbcon.cursor()
        except:
            pass
        ''' Fix to stop items passed with a 0 IMDB id pulling old unrelated sources from the database. '''
        if imdb == '0':
            try:
                dbcur.execute("DELETE FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
                dbcur.execute("DELETE FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
                dbcon.commit()
            except:
                pass
        ''' END '''
        try:
            sources = []
            dbcur.execute("SELECT * FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            match = dbcur.fetchone()
            t1 = int(re.sub(r'[^0-9]', '', str(match[5])))
            t2 = int(datetime.datetime.now().strftime("%Y%m%d%H%M"))
            update = abs(t2 - t1) > 60
            if update == False:
                sources = eval(six.ensure_str(match[4]))
                return self.sources.extend(sources)
        except:
            pass
        try:
            url = None
            dbcur.execute("SELECT * FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            url = dbcur.fetchone()
            url = eval(six.ensure_str(url[4]))
        except:
            pass
        try:
            if url == None:
                url = call.movie(imdb, tmdb, title, localtitle, aliases, year)
            if url == None:
                raise Exception()
            dbcur.execute("DELETE FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            dbcur.execute("INSERT INTO rel_url Values (?, ?, ?, ?, ?)", (source, imdb, '', '', repr(url)))
            dbcon.commit()
        except:
            pass
        try:
            sources = []
            sources = call.sources(url, self.hostDict)
            if sources == None or sources == []:
                raise Exception()
            sources = [json.loads(t) for t in set(json.dumps(d, sort_keys=True) for d in sources)]
            for i in sources:
                i.update({'provider': source})
            self.sources.extend(sources)
            dbcur.execute("DELETE FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            dbcur.execute("INSERT INTO rel_src Values (?, ?, ?, ?, ?, ?)", (source, imdb, '', '', repr(sources), datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
            dbcon.commit()
        except:
            pass


    def getEpisodeSource(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, localtvshowtitle, aliases, premiered, source, call):
        try:
            dbcon = database.connect(self.sourceFile)
            dbcur = dbcon.cursor()
        except:
            pass
        try:
            sources = []
            dbcur.execute("SELECT * FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, season, episode))
            match = dbcur.fetchone()
            t1 = int(re.sub(r'[^0-9]', '', str(match[5])))
            t2 = int(datetime.datetime.now().strftime("%Y%m%d%H%M"))
            update = abs(t2 - t1) > 60
            if update == False:
                sources = eval(six.ensure_str(match[4]))
                return self.sources.extend(sources)
        except:
            pass
        try:
            url = None
            dbcur.execute("SELECT * FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            url = dbcur.fetchone()
            url = eval(six.ensure_str(url[4]))
        except:
            pass
        try:
            if url == None:
                url = call.tvshow(imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year)
            if url == None:
                raise Exception()
            dbcur.execute("DELETE FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            dbcur.execute("INSERT INTO rel_url Values (?, ?, ?, ?, ?)", (source, imdb, '', '', repr(url)))
            dbcon.commit()
        except:
            pass
        try:
            ep_url = None
            dbcur.execute("SELECT * FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, season, episode))
            ep_url = dbcur.fetchone()
            ep_url = eval(six.ensure_str(ep_url[4]))
        except:
            pass
        try:
            if url == None:
                raise Exception()
            if ep_url == None:
                ep_url = call.episode(url, imdb, tmdb, tvdb, title, premiered, season, episode)
            if ep_url == None:
                raise Exception()
            dbcur.execute("DELETE FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, season, episode))
            dbcur.execute("INSERT INTO rel_url Values (?, ?, ?, ?, ?)", (source, imdb, season, episode, repr(ep_url)))
            dbcon.commit()
        except:
            pass
        try:
            sources = []
            sources = call.sources(ep_url, self.hostDict)
            if sources == None or sources == []:
                raise Exception()
            sources = [json.loads(t) for t in set(json.dumps(d, sort_keys=True) for d in sources)]
            for i in sources:
                i.update({'provider': source})
            self.sources.extend(sources)
            dbcur.execute("DELETE FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, season, episode))
            dbcur.execute("INSERT INTO rel_src Values (?, ?, ?, ?, ?, ?)", (source, imdb, season, episode, repr(sources), datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
            dbcon.commit()
        except:
            pass


    def uniqueSourcesGen(self, sources):
        uniqueURLs = set()
        for source in sources:
            url = source.get('url')
            if isinstance(url, six.string_types):
                url = url.replace('http://', 'https://')
                if url not in uniqueURLs:
                    uniqueURLs.add(url)
                    yield source
                else:
                    pass
            else:
                yield source


    def sourcesSort(self):
        random.shuffle(self.sources)
        local = [i for i in self.sources if 'local' in i and i['local'] == True]
        self.sources = [i for i in self.sources if not i in local]
        if self.sort_provider == 'true':
            self.sources = sorted(self.sources, key=lambda k: k['provider'])
        if self.sort_hoster == 'true':
            self.sources = sorted(self.sources, key=lambda k: k['source'])
        filter = []
        filter += local
        filter += [i for i in self.sources if i['quality'].lower() == '4k']
        filter += [i for i in self.sources if i['quality'].lower() == '1080p']
        filter += [i for i in self.sources if i['quality'].lower() == '720p']
        filter += [i for i in self.sources if i['quality'].lower() == 'hd']
        filter += [i for i in self.sources if i['quality'].lower() == 'sd']
        filter += [i for i in self.sources if i['quality'].lower() in ['scr', 'cam']]
        self.sources = filter
        self.sources = self.sources[:4000]
        double_line = control.setting('sourcelist.linesplit') == '1'
        simple = control.setting('sourcelist.linesplit') == '2'
        single_line = control.setting('sourcelist.linesplit') == '0'
        for i in range(len(self.sources)):
            u = self.sources[i]['url']
            p = self.sources[i]['provider'].replace('_', '.')
            q = self.sources[i]['quality']
            s = self.sources[i]['source']
            try:
                f = ' / '.join(['%s' % info.strip() for info in self.sources[i].get('info', '').split('|')])
            except:
                f = ''
            if double_line:
                label = '%03d' % (int(i+1))
                if f:
                    label += ' | [B]%s[/B] | %s | [B]%s[/B][CR] [I]%s[/I]' % (q, p, s, f)
                else:
                    label += ' | [B]%s[/B] | %s | [B]%s[/B][CR]' % (q, p, s)
            elif simple:
                label = '%03d' % (int(i+1))
                label += ' | [B]%s[/B] | %s | [B]%s[/B]' % (q, p, s)
            else:
                label = '%03d' % (int(i+1))
                if f:
                    label += ' | [B]%s[/B] | %s | [B]%s[/B] | [I]%s[/I]' % (q, p, s, f)
                else:
                    label += ' | [B]%s[/B] | %s | [B]%s[/B] |' % (q, p, s)
            label = label.replace('[I]%s /[/I]' % f, '[I]%s[/I]' % f).replace('[I] /[/I]', '').replace('| 0 |', '|').replace(' |  |', ' |').replace('/ 0 /', '/').replace(' /  /', ' /')
            if double_line:
                label_up = label.split('[CR]')[0]
                label_up_clean = label_up.replace('[B]', '').replace('[/B]', '')
                label_down = label.split('[CR]')[1]
                label_down_clean = label_down.replace('[I]', '').replace('[/I]', '')
                if len(label_down_clean) > len(label_up_clean):
                    label_up += (len(label_down_clean) - len(label_up_clean)) * '  '
                    label = label_up + '[CR]' + label_down
            self.sources[i]['label'] = '[UPPERCASE]' + label + '[/UPPERCASE]'
        self.sources = [i for i in self.sources if 'label' in i]
        return self.sources


    def sourcesFilter(self, _content, sort=False):
        stotal = self.sources
        for i in self.sources:
            i_quality = i['quality'].lower()
            if i_quality == 'hd':
                i.update({'quality': '720p'})
            if _content == 'episode' and i_quality in ['scr', 'cam']:
                i.update({'quality': 'sd'})
            if i_quality == '4k':
                i.update({'q_filter': 0})
                if self.quality_artwork == 'true':
                    i.update({'thumb': self.quality_images + "4k.png"})
            elif i_quality == '1080p':
                i.update({'q_filter': 1})
                if self.quality_artwork == 'true':
                    i.update({'thumb': self.quality_images + "1080p.png"})
            elif i_quality == '720p':
                i.update({'q_filter': 2})
                if self.quality_artwork == 'true':
                    i.update({'thumb': self.quality_images + "720p.png"})
            else:
                i.update({'q_filter': 3})
                if self.quality_artwork == 'true':
                    i.update({'thumb': self.quality_images + "sd.png"})
        self.sources = [i for i in self.sources if self.max_quality <= i.get('q_filter', 3) <= self.min_quality]
        if self.remove_cam == 'true':
            self.sources = [i for i in self.sources if not i_quality in ['scr', 'cam']]
        try:
            if self.remove_dupes == 'true' and len(self.sources) > 1:
                self.sources = list(self.uniqueSourcesGen(self.sources))
        except:
            pass
        if self.remove_hevc == 'true':
            self.sources = [i for i in self.sources if not any(x in i['url'].lower() for x in ['hevc', 'h265', 'x265', 'h.265', 'x.265']) and not any(x in i.get('info', '').lower() for x in ['hevc', 'h265', 'x265', 'h.265', 'x.265'])]
        if self.remove_captcha == 'true':
            self.sources = [i for i in self.sources if not i['source'].lower() in self.hostcapDict]
        filtered_out = [i for i in stotal if not i in self.sources]
        self.filtered_sources.extend(filtered_out)
        if sort == True:
            self.sourcesSort()
        return self.sources


    def getSources(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, quality='720p', timeout=30):
        progressDialog = control.progressDialog if control.setting('progress.dialog') == '0' else control.progressDialogBG
        if progressDialog == control.progressDialogBG:
            control.idle()
        progressDialog.create('Providers:')
        self.prepareSources()
        sourceDict = self.sourceDict
        progressDialog.update(0, 'Preparing Sources...')
        content = 'movie' if tvshowtitle == None else 'episode'
        if content == 'movie':
            sourceDict = [(i[0], i[1], getattr(i[1], 'movie', None)) for i in sourceDict]
            genres = trakt.getGenre('movie', 'imdb', imdb)
        else:
            sourceDict = [(i[0], i[1], getattr(i[1], 'tvshow', None)) for i in sourceDict]
            genres = trakt.getGenre('show', 'tmdb', tmdb)
        sourceDict = [(i[0], i[1], i[2]) for i in sourceDict if not hasattr(i[1], 'genre_filter') or not i[1].genre_filter or any(x in i[1].genre_filter for x in genres)]
        sourceDict = [(i[0], i[1]) for i in sourceDict if not i[2] == None]
        try:
            sourceDict = [(i[0], i[1], control.setting('provider.' + i[0])) for i in sourceDict]
        except:
            sourceDict = [(i[0], i[1], 'true') for i in sourceDict]
        sourceDict = [(i[0], i[1]) for i in sourceDict if not i[2] == 'false']
        random.shuffle(sourceDict)
        threads = []
        if content == 'movie':
            title, imdb, year = cleantitle.scene_title(title, imdb, year)
            localtitle = self.getLocalTitle(title, imdb, content)
            aliases = self.getAliasTitles(imdb, localtitle, content)
            if not any(i.get('title', '').lower() == title.lower() for i in aliases):
                aliases.append({'country': 'us', 'title': title})
            if not any(i.get('title', '').lower() == localtitle.lower() for i in aliases):
                aliases.append({'country': 'us', 'title': localtitle})
            log_utils.log('Source Searching Info = [ movie_title: ' + title + ' | localtitle: ' + localtitle + ' | year: ' + year + ' | imdb: ' + imdb + ' ]')
            #log_utils.log('Source Searching Info = [ aliases: ' + repr(aliases) + ' ]')
            for i in sourceDict:
                threads.append(workers.Thread(self.getMovieSource, title, localtitle, aliases, year, imdb, tmdb, i[0], i[1]))
        else:
            tvshowtitle, imdb, year, season, episode = cleantitle.scene_tvtitle(tvshowtitle, imdb, year, season, episode)
            localtvshowtitle = self.getLocalTitle(tvshowtitle, imdb, content)
            aliases = self.getAliasTitles(imdb, localtvshowtitle, content)
            if not any(i.get('title', '').lower() == tvshowtitle.lower() for i in aliases):
                aliases.append({'country': 'us', 'title': tvshowtitle})
            if not any(i.get('title', '').lower() == localtvshowtitle.lower() for i in aliases):
                aliases.append({'country': 'us', 'title': localtvshowtitle})
            log_utils.log('Source Searching Info = [ tvshow_title: ' + tvshowtitle + ' | localtvshowtitle: ' + localtvshowtitle + ' | year: ' + year + ' | imdb: ' + imdb + ' | season: ' + season + ' | episode: ' + episode + ' ]')
            #log_utils.log('Source Searching Info = [ aliases: ' + repr(aliases) + ' ]')
            for i in sourceDict:
                threads.append(workers.Thread(self.getEpisodeSource, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, localtvshowtitle, aliases, premiered, i[0], i[1]))
        s = [i[0] + (i[1],) for i in zip(sourceDict, threads)]
        s = [(i[2].getName(), i[0]) for i in s]
        sourcelabelDict = dict([(i[0], i[1].upper()) for i in s])
        [i.start() for i in threads]
        try:
            _timeout = int(control.setting('providers.timeout'))
        except:
            _timeout = timeout
        start_time = time.time()
        end_time = start_time + _timeout
        string3 = 'Remaining Providers: %s'
        source_4k = source_1080 = source_720 = source_sd = total = source_filtered_out = 0
        line1 = line2 = ""
        total_format = '[COLOR %s][B]%s[/B][/COLOR]'
        pdiag_format = ' 4K: %s | 1080P: %s | 720P: %s | SD: %s [CR] Total: %s | Filtered: %s' if not progressDialog == control.progressDialogBG else ' 4K: %s | 1080P: %s | 720P: %s | SD: %s | T: %s (F: -%s)'
        scrape_cancelled = False
        for i in range(0, 4 * _timeout):
            try:
                if control.monitor.abortRequested():
                    return sys.exit()
                try:
                    if progressDialog.iscanceled():
                        scrape_cancelled = True
                        break
                except:
                    pass
                try:
                    if progressDialog.isFinished():
                        break
                except:
                    pass
                if self.sources:
                    self.sourcesFilter(content)
                    if self.min_quality == 0:
                        source_4k = len([e for e in self.sources if e['quality'].lower() == '4k'])
                    elif self.min_quality == 1:
                        source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                        if self.max_quality == 0:
                            source_4k = len([e for e in self.sources if e['quality'].lower() == '4k'])
                    elif self.min_quality == 2:
                        source_720 = len([e for e in self.sources if e['quality'].lower() in ['720p', 'hd']])
                        if self.max_quality == 0:
                            source_4k = len([e for e in self.sources if e['quality'].lower() == '4k'])
                            source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                        elif self.max_quality == 1:
                            source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                    elif self.min_quality == 3:
                        source_sd = len([e for e in self.sources if e['quality'].lower() in ['sd', 'scr', 'cam']])
                        if self.max_quality == 0:
                            source_4k = len([e for e in self.sources if e['quality'].lower() == '4k'])
                            source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                            source_720 = len([e for e in self.sources if e['quality'].lower() in ['720p', 'hd']])
                        elif self.max_quality == 1:
                            source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                            source_720 = len([e for e in self.sources if e['quality'].lower() in ['720p', 'hd']])
                        elif self.max_quality == 2:
                            source_720 = len([e for e in self.sources if e['quality'].lower() in ['720p', 'hd']])
                    total = source_4k + source_1080 + source_720 + source_sd
                    if self.pre_emp == 'true':
                        if self.pre_emp_type == '1':
                            if total >= self.pre_emp_limit:
                                break
                        else:
                            if self.max_quality == 0:
                                if source_4k >= self.pre_emp_limit:
                                    break
                            elif self.max_quality == 1:
                                if source_1080 >= self.pre_emp_limit:
                                    break
                            elif self.max_quality == 2:
                                if source_720 >= self.pre_emp_limit:
                                    break
                            elif self.max_quality == 3:
                                if source_sd >= self.pre_emp_limit:
                                    break
                    source_filtered_out = len([e for e in self.filtered_sources])
                source_4k_label = total_format % ('darkorange', source_4k) if source_4k == 0 else total_format % ('lime', source_4k)
                source_1080_label = total_format % ('darkorange', source_1080) if source_1080 == 0 else total_format % ('lime', source_1080)
                source_720_label = total_format % ('darkorange', source_720) if source_720 == 0 else total_format % ('lime', source_720)
                source_sd_label = total_format % ('darkorange', source_sd) if source_sd == 0 else total_format % ('lime', source_sd)
                source_total_label = total_format % ('darkorange', total) if total == 0 else total_format % ('lime', total)
                source_filtered_out_label = total_format % ('darkorange', source_filtered_out) if source_filtered_out == 0 else total_format % ('lime', source_filtered_out)
                try:
                    info = [sourcelabelDict[x.getName()] for x in threads if x.is_alive() == True]
                    line1 = pdiag_format % (source_4k_label, source_1080_label, source_720_label, source_sd_label, source_total_label, source_filtered_out_label)
                    if len(info) > 5:
                        line2 = 'Remaining Providers: %s' % (str(len(info)))
                    elif len(info) > 0:
                        line2 = 'Remaining Providers: %s' % (', '.join(info).upper().replace('_', '.'))
                    else:
                        break
                    current_time = time.time()
                    current_progress = current_time - start_time
                    percent = int((current_progress / float(_timeout)) * 100)
                    if not progressDialog == control.progressDialogBG:
                        progressDialog.update(max(1, percent), line1 + '[CR]' + line2)
                    else:
                        progressDialog.update(max(1, percent), 'Providers:', line1 + '[CR]' + line2)
                    if end_time < current_time:
                        break
                except:
                    log_utils.log('getSources', 1)
                    break
                control.sleep(250)
            except:
                log_utils.log('getSources', 1)
                pass
        if progressDialog == control.progressDialogBG:
            progressDialog.close()
            if not scrape_cancelled:
                self.sourcesFilter(content, sort=True)
        else:
            if not scrape_cancelled:
                self.sourcesFilter(content, sort=True)
            progressDialog.close()
        if scrape_cancelled:
            control.idle()
            return []
        if self.pre_emp == 'true':
            self.sourcesFilter(content, sort=True)
        del progressDialog
        del threads
        control.idle()
        #log_utils.log('getSources self.sources: \n' + repr(self.sources))
        return self.sources


    def addItem(self, title):
        def sourcesDirMeta(metadata):
            if metadata == None:
                return metadata
            allowed = ['icon', 'poster', 'fanart', 'thumb', 'clearlogo', 'clearart', 'discart', 'title', 'year', 'tvshowtitle', 'season', 'episode', 'rating', 'plot', 'trailer', 'mediatype']
            return {k: v for k,v in six.iteritems(metadata) if k in allowed}
        control.playlist.clear()
        items = control.window.getProperty(self.itemProperty)
        items = json.loads(items)
        if items == None or len(items) == 0:
            control.idle() ; sys.exit()
        meta = control.window.getProperty(self.metaProperty)
        meta = json.loads(meta)
        meta = sourcesDirMeta(meta)
        sysaddon = sys.argv[0]
        syshandle = int(sys.argv[1])
        downloads = True if control.setting('downloads') == 'true' and not (control.setting('movie.download.path') == '' or control.setting('tv.download.path') == '') else False
        listMeta = control.setting('sourcelist.meta')
        try:
            systitle = sysname = urllib_parse.quote_plus(title)
        except:
            systitle = sysname = urllib_parse.quote_plus(meta['title'])
        if 'tvshowtitle' in meta and 'season' in meta and 'episode' in meta:
            sysname += urllib_parse.quote_plus(' S%02dE%02d' % (int(meta['season']), int(meta['episode'])))
        elif 'year' in meta:
            sysname += urllib_parse.quote_plus(' (%s)' % meta['year'])
        poster = meta.get('poster') or control.addonPoster()
        if control.setting('show.fanart') == 'true':
            fanart = meta.get('fanart') or control.addonFanart()
        else:
            fanart = control.addonFanart()
        thumb = meta.get('thumb') or poster or fanart
        clearlogo = meta.get('clearlogo', '') or ''
        clearart = meta.get('clearart', '') or ''
        discart = meta.get('discart', '') or ''
        sysimage = urllib_parse.quote_plus(six.ensure_str(poster))
        for i in range(len(items)):
            try:
                try:
                    thumb = str(items[i]['thumb'])
                except:
                    thumb = thumb
                label = str(items[i]['label'])
                syssource = urllib_parse.quote_plus(json.dumps([items[i]]))
                sysurl = '%s?action=play_item&title=%s&source=%s' % (sysaddon, systitle, syssource)
                cm = []
                if downloads == True:
                    cm.append(('DownLoad', 'RunPlugin(%s?action=download&name=%s&image=%s&source=%s)' % (sysaddon, sysname, sysimage, syssource)))
                try:
                    item = control.item(label=label, offscreen=True)
                except:
                    item = control.item(label=label)
                item.addContextMenuItems(cm)
                if listMeta == 'true':
                    item.setArt({'thumb': thumb, 'icon': thumb, 'poster': poster, 'fanart': fanart, 'clearlogo': clearlogo, 'clearart': clearart, 'discart': discart})
                    video_streaminfo = {'codec': 'h264'}
                    if kodi_version >= 20:
                        info_tag = ListItemInfoTag(item, 'video')
                        info_tag.add_stream_info('video', video_streaminfo)
                        info_tag.set_info(control.metadataClean(meta))
                    else:
                        item.addStreamInfo('video', video_streaminfo)
                        item.setInfo(type='video', infoLabels=control.metadataClean(meta))
                else:
                    item.setArt({'thumb': thumb})
                    if kodi_version >= 20:
                        info_tag = ListItemInfoTag(item, 'video')
                        info_tag.set_info({})
                    else:
                        item.setInfo(type='video', infoLabels={})
                control.addItem(handle=syshandle, url=sysurl, listitem=item, isFolder=False)
            except:
                pass
        control.content(syshandle, 'files')
        control.directory(syshandle, cacheToDisc=True)


    def play(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select):
        try:
            control.clear_resolve_state()
            url = None
            items = self.getSources(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered)
            select = control.setting('hosts.mode') if select == None else select
            title = tvshowtitle if not tvshowtitle == None else title
            title = cleantitle.normalize(title)
            if len(items) > 0:
                if select == '1' and 'plugin' in control.infoLabel('Container.PluginName'):
                    control.window.clearProperty(self.itemProperty)
                    control.window.setProperty(self.itemProperty, json.dumps(items))
                    control.window.clearProperty(self.metaProperty)
                    control.window.setProperty(self.metaProperty, meta)
                    control.sleep(200)
                    # Release the PlayMedia resolve handle before switching to a folder list.
                    control.abort_plugin_resolve()
                    return control.execute('Container.Update(%s?action=add_item&title=%s)' % (sys.argv[0], urllib_parse.quote_plus(title)))
                elif select == '0' or select == '1':
                    url = self.sourcesDialog(items)
                else:
                    url = self.sourcesDirect(items)
            if url == 'close://' or url == None:
                self.url = url
                return self.errorForSources()
            try:
                meta = json.loads(meta)
            except:
                pass
            from resources.lib.modules.player import player
            player().run(title, year, season, episode, imdb, tmdb, tvdb, url, meta)
        except:
            log_utils.log('play', 1)
            control.abort_plugin_resolve()
            pass


    def playItem(self, title, source):
        try:
            control.clear_resolve_state()
            meta = control.window.getProperty(self.metaProperty)
            meta = json.loads(meta)
            year = meta['year'] if 'year' in meta else None
            season = meta['season'] if 'season' in meta else None
            episode = meta['episode'] if 'episode' in meta else None
            imdb = meta['imdb'] if 'imdb' in meta else None
            tvdb = meta['tvdb'] if 'tvdb' in meta else None
            tmdb = meta['tmdb'] if 'tmdb' in meta else None
            next = []
            prev = []
            total = []
            for i in range(1,1000):
                try:
                    u = control.infoLabel('ListItem(%s).FolderPath' % str(i))
                    if u in total:
                        raise Exception()
                    total.append(u)
                    u = dict(urllib_parse.parse_qsl(u.replace('?','')))
                    u = json.loads(u['source'])[0]
                    next.append(u)
                except:
                    break
            for i in range(-1000,0)[::-1]:
                try:
                    u = control.infoLabel('ListItem(%s).FolderPath' % str(i))
                    if u in total:
                        raise Exception()
                    total.append(u)
                    u = dict(urllib_parse.parse_qsl(u.replace('?','')))
                    u = json.loads(u['source'])[0]
                    prev.append(u)
                except:
                    break
            items = json.loads(source)
            items = [i for i in items+next+prev][:40]
            header = control.addonInfo('name') + ' : Resolving...'
            progressDialog = control.progressDialog if control.setting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(header, '')
            #progressDialog.update(0)
            block = None
            for i in range(len(items)):
                try:
                    label = re.sub(r' {2,}', ' ', str(items[i]['label']))
                    try:
                        if progressDialog.iscanceled():
                            break
                        progressDialog.update(int((100 / float(len(items))) * i), label)
                    except:
                        progressDialog.update(int((100 / float(len(items))) * i), str(header) + '[CR]' + label)
                    if items[i]['source'] == block:
                        raise Exception()
                    w = workers.Thread(self.sourcesResolve, items[i])
                    w.start()
                    offset = 60 * 2 if items[i].get('source').lower() in self.hostcapDict else 0
                    m = ''
                    for x in range(3600):
                        try:
                            if control.monitor.abortRequested():
                                return sys.exit()
                            if progressDialog.iscanceled():
                                try:
                                    progressDialog.close()
                                except:
                                    pass
                                return self.errorForSources()
                        except:
                            pass
                        k = control.condVisibility('Window.IsActive(virtualkeyboard)')
                        if k:
                            m += '1'; m = m[-1]
                        if (w.is_alive() == False or x > 30 + offset) and not k:
                            break
                        k = control.condVisibility('Window.IsActive(yesnoDialog)')
                        if k:
                            m += '1'; m = m[-1]
                        if (w.is_alive() == False or x > 30 + offset) and not k:
                            break
                        time.sleep(0.5)
                    for x in range(30):
                        try:
                            if control.monitor.abortRequested():
                                return sys.exit()
                            if progressDialog.iscanceled():
                                try:
                                    progressDialog.close()
                                except:
                                    pass
                                return self.errorForSources()
                        except:
                            pass
                        if m == '':
                            break
                        if w.is_alive() == False:
                            break
                        time.sleep(0.5)
                    if w.is_alive() == True:
                        block = items[i]['source']
                    if self.url == None:
                        raise Exception()
                    try:
                        progressDialog.close()
                    except:
                        pass
                    control.sleep(200)
                    control.execute('Dialog.Close(virtualkeyboard)')
                    control.execute('Dialog.Close(yesnoDialog)')
                    from resources.lib.modules.player import player
                    player().run(title, year, season, episode, imdb, tmdb, tvdb, self.url, meta)
                    return self.url
                except:
                    pass
            try:
                progressDialog.close()
            except:
                pass
            del progressDialog
            self.errorForSources()
        except:
            control.abort_plugin_resolve()
            pass


    def getLocalTitle(self, title, imdb, content):
        t = trakt.getMovieTranslation(imdb, 'en') if content == 'movie' else trakt.getTVShowTranslation(imdb, 'en')
        return t or title


    def getAliasTitles(self, imdb, localtitle, content):
        try:
            t = trakt.getMovieAliases(imdb) if content == 'movie' else trakt.getTVShowAliases(imdb)
            if not t: # Ghetto fix for when the results are none so the scrape process can still be ran.
                t = []
            #t = [i for i in t if i.get('country', '').lower() in ['en', '', 'us'] and i.get('title', '').lower() != localtitle.lower()]
            # Ditched t2 so the match alias def will work how i want it lol.
            return t
        except:
            return []


    def alterSources(self, url, meta):
        try:
            if control.setting('hosts.mode') == '2':
                url += '&select=1'
            else:
                url += '&select=2'
            control.execute('RunPlugin(%s)' % url)
        except:
            pass


    def enableAll(self):
        try:
            sourceDict = self.sourceDict
            for i in sourceDict:
                source_setting = 'provider.' + i[0]
                control.setSetting(source_setting, 'true')
        except:
            pass
        control.openSettings(query='4.1')


    def disableAll(self):
        try:
            sourceDict = self.sourceDict
            for i in sourceDict:
                source_setting = 'provider.' + i[0]
                control.setSetting(source_setting, 'false')
        except:
            pass
        control.openSettings(query='4.2')


    def getProviderDomains(self):
        try:
            list = []
            text = ''
            sourceDict = self.sourceDict
            log_provider_domains = control.setting('addon.log_providerdomains') or 'false'
            for i in sourceDict:
                try:
                    provider = i[0]
                    call = i[1]
                    domains = getattr(call, 'domains', None) or []
                    domains = [domain for domain in domains][:3]
                    domains_label = '[CR]-Last 3 Domains :  %s[CR]' % domains if domains else '[CR]'
                    base_link = getattr(call, 'base_link', '') or ''
                    if not base_link and domains:
                        base_link = domains[0] if str(domains[0]).startswith('http') else 'https://%s' % domains[0]
                    notes = getattr(call, 'notes', '') or ''
                    notes_label = '-Notes :  %s[CR]' % notes if notes else ''
                    scraper_label = '[B]%s :[/B]  %s%s%s' % (provider, base_link, domains_label, notes_label)
                    list.append(scraper_label)
                except:
                    continue
            for i in range(len(list)):
                text += "[CR][" + str(i+1) + "] " + list[i]
            if log_provider_domains == 'true':
                text2 = text.replace('[CR]', '\n').replace('[B]', '').replace('[/B]', '')
                log_utils.log('Provider Domains List: \n' + text2)
            control.textViewer2(text, 'Provider Domains')
        except:
            log_utils.log('getProviderDomains', 1)
            pass


