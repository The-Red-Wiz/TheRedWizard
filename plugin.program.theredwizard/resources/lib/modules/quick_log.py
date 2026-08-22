import json
import os
import re
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from urllib.request import Request, urlopen

addon = xbmcaddon.Addon()
addon_name = addon.getAddonInfo('name')
addon_icon = addon.getAddonInfo('icon')
log_path = xbmcvfs.translatePath('special://logpath/')
PASTE_URL = 'https://paste.kodi.tv/'
USER_AGENT = 'script.kodi.loguploader: 1.0'
MAX_BYTES = 1000000
COUNTDOWN_SECS = 180

def copy_to_clipboard(text):
    if not text:
        return False
    try:
        if sys.platform == 'win32':
            from subprocess import Popen, PIPE
            process = Popen(['clip'], stdin=PIPE)
            process.communicate(input=text.strip().encode('utf-8'))
            return process.returncode == 0
        if sys.platform == 'darwin':
            from subprocess import Popen, PIPE
            process = Popen(['pbcopy'], stdin=PIPE)
            process.communicate(input=text.strip().encode('utf-8'))
            return process.returncode == 0
        if sys.platform.startswith('linux'):
            from subprocess import Popen, PIPE
            process = Popen(['xsel', '-bi'], stdin=PIPE)
            process.communicate(input=text.strip().encode('utf-8'))
            return process.returncode == 0
    except Exception:
        pass
    return False

def _read_log(file_name):
    path = os.path.join(log_path, file_name)
    if not xbmcvfs.exists(path) and not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8', errors='ignore') as log_file:
        text = log_file.read()
    encoded = text.encode('utf-8', errors='ignore')
    if len(encoded) > MAX_BYTES:
        encoded = encoded[-MAX_BYTES:]
    return encoded

def _upload(data):
    request = Request(
        PASTE_URL + 'documents',
        data=data,
        headers={'User-Agent': USER_AGENT}
    )
    response = json.loads(urlopen(request, timeout=30).read().decode('utf-8'))
    key = response.get('key')
    if not key:
        raise ValueError('No paste key returned')
    return PASTE_URL + key

def upload_logfile():
    choices = [('[COLOR gold]Current Kodi Log[/COLOR]', 'kodi.log'), ('[COLOR gold]Previous Kodi Log[/COLOR]', 'kodi.old.log')]
    index = xbmcgui.Dialog().select('[COLOR red]Choose which log to upload[/COLOR]', [item[0] for item in choices])
    if index < 0:
        return
    log_name, file_name = choices[index]
    if not xbmcgui.Dialog().yesno(
        addon_name,
        '[COLOR gold]Upload {0} to paste.kodi.tv?[CR][CR]The link can be shared with support. Logs can contain device and account details.[/COLOR]'.format(log_name),
        yeslabel='Upload',
        nolabel='Cancel',
        defaultbutton=xbmcgui.DLG_YESNO_YES_BTN
    ):
        return
    data = _read_log(file_name)
    if not data:
        xbmcgui.Dialog().ok(addon_name, '[COLOR gold]{0} was not found.[/COLOR]'.format(log_name))
        return
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
    try:
        url = _upload(data)
    except Exception as error:
        xbmc.log('Log upload failed: %s' % error, xbmc.LOGINFO)
        xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
        xbmcgui.Dialog().ok(addon_name, '[COLOR gold]Log upload failed. Please try again later.[/COLOR]')
        return
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    copied = copy_to_clipboard(url)
    copied_line = '[CR][COLOR gold]The link has been copied to the clipboard.[/COLOR]' if copied else ''
    progress = xbmcgui.DialogProgress()
    progress.create(addon_name)
    remaining = COUNTDOWN_SECS
    while remaining > 0 and not progress.iscanceled():
        percent = int(100 * remaining / COUNTDOWN_SECS)
        progress.update(
            percent,
            '[COLOR gold]Share this link with support:[/COLOR][CR][CR][COLOR red][B]{0}[/B][/COLOR]{1}[CR][CR][COLOR gold]Closes in {2} seconds.[/COLOR]'.format(
                url, copied_line, remaining
            )
        )
        xbmc.sleep(1000)
        remaining -= 1
    progress.close()

def log_viewer():
    pattern = re.compile('EXCEPTION Thrown(.+?)-->End of Python script error report<--', re.MULTILINE | re.DOTALL)
    addons_path = xbmcvfs.translatePath('special://home/addons')
    choice = xbmcgui.Dialog().yesnocustom(addon_name, '[COLOR gold]Select Log Type:[/COLOR]', 'Kodi.log', nolabel='Error Log', yeslabel='Kodi.old')
    if choice == 2 or choice == 0:
        path = os.path.join(log_path, 'kodi.log')
    elif choice == 1:
        path = os.path.join(log_path, 'kodi.old.log')
    else:
        return
    if not xbmcvfs.exists(path) and not os.path.exists(path):
        xbmcgui.Dialog().ok(addon_name, '[COLOR gold]That log file was not found.[/COLOR]')
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as log_file:
        log = log_file.read()
    if choice == 0:
        errors = pattern.findall(log)
        if errors:
            message = '\n'.join('*** Error ***\n\n{0}\n*** End of Error Report ***\n'.format(error) for error in errors)
        else:
            message = 'No Errors Found'
    else:
        message = log.replace(addons_path, addons_path + '\n')
        max_chars = 250000
        if len(message) > max_chars:
            message = '[Showing the last part of the log. Use Upload Kodi Log to share the full file.]\n\n' + message[-max_chars:]

    class Logview(xbmcgui.WindowXMLDialog):
        ACTION_PREVIOUS_MENU = 10
        ACTION_NAV_BACK = 92
        ACTION_MOUSE_WHEEL_UP = 104
        ACTION_MOUSE_WHEEL_DOWN = 105

        def onInit(self):
            self.getControl(300).setText(message)
            if message.strip() == 'No Errors Found':
                self.setFocusId(302)
            else:
                self.setFocusId(301)

        def onAction(self, action):
            action_id = action.getId()
            if action_id in (self.ACTION_NAV_BACK, self.ACTION_PREVIOUS_MENU):
                self.close()
                return
            if action_id == self.ACTION_MOUSE_WHEEL_UP:
                xbmc.executebuiltin('Action(PageUp)')
            elif action_id == self.ACTION_MOUSE_WHEEL_DOWN:
                xbmc.executebuiltin('Action(PageDown)')

        def onClick(self, controlId):
            if controlId == 302:
                self.close()

    dialog = Logview('logview.xml', addon.getAddonInfo('path'), 'Default', '720p')
    dialog.doModal()
    del dialog
