import os
import sys
from urllib.request import Request, urlopen
import xbmc
import xbmcgui
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ICON = ADDON.getAddonInfo('icon')

class Downloader:
    def __init__(self, url):
        self.url = url
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        self.headers = {"User-Agent": self.user_agent}
        
    def get_urllib(self, decoding=True):
        req = Request(self.url, headers = self.headers)
        if decoding:
            return urlopen(req).read().decode('utf-8')
        return urlopen(req)
    
    def get_length(self, response):
        try:
            return response.getheader('content-length')
        except KeyError:
            return None
    
    def download_build(self, name, zippath):
        dp = xbmcgui.DialogProgress()
        response = self.get_urllib(decoding=False)
        length = self.get_length(response)
        if length is not None:
            length2 = int(int(length)/1000000)
            dp.create(f'[COLOR red]{name} - {length2}MB[/COLOR]', '[COLOR gold]Downloading your build...[/COLOR]')
        else:
            length2 = 'Unknown Size'
            dp.create(f'[COLOR red]{name} - {length2}[/COLOR]', '[COLOR gold]Downloading your build...[/COLOR]')
        
        dp.update(0, '[COLOR gold]Downloading your build...[/COLOR]')
        cancelled = False
        chunksize = 1000000
        size = 0
        with open(zippath, 'wb') as f:
            if length is not None:
                while True:
                    chunk = response.read(chunksize)
                    if not chunk:
                        break
                    size += len(chunk)
                    size2 = int(size/1000000)
                    perc = int(int(size)/int(length)*100)
                    f.write(chunk)
                    dp.update(perc, f'[COLOR gold]Downloading your build...[/COLOR][COLOR red]\n{size2}/{length2} MB[/COLOR]')
                    if dp.iscanceled():
                        cancelled = True
                        break
                    
            else:
                while True:
                    chunk = response.read(chunksize)
                    if not chunk:
                        break
                    size += len(chunk)
                    size2 = int(size/1000000)
                    f.write(chunk)
                    dp.update(50, f'[COLOR gold]Downloading your build...[/COLOR][COLOR red]\n{size2} MB[/COLOR]')
                    if dp.iscanceled():
                        cancelled = True
                        break
                        
        if cancelled is True:
            dp.close()
            os.unlink(zippath)
            dialog = xbmcgui.Dialog()
            dialog.notification(ADDON_NAME, '[COLOR gold]Download Cancelled![/COLOR]', icon=ICON)
            sys.exit()
        
        if length is not None:
            dp.update(100,
                f'[COLOR gold]Downloading your build... Done![/COLOR][COLOR red]\n{size2}/{length2} MB[/COLOR]'
            )
        else:
            dp.update(100, f'[COLOR gold]Downloading your build... Done![/COLOR][COLOR red]\n{size2} MB[/COLOR]')
        
        xbmc.sleep(500)
        dp.close()
    