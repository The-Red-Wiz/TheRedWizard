import shutil
import os
import zipfile
from zipfile import ZipFile
from pathlib import Path
import xbmc
import xbmcgui
from .addonvar import home, addon_profile, addon_path, setting, setting_set, translatePath, xbmcPath, addon_id, dp, local_string, addon_name, addon_icon, addon_fanart, os_name
from .utils import add_dir

p = Path(home)
backup_path = Path(translatePath(setting('backupfolder')))
backups = p / 'backups'
addons = p / 'addons'
media = p / 'media'
userdata = p / 'userdata'
wizard_path = Path(addon_path)
data_path = Path(addon_profile)
compression = zipfile.ZIP_DEFLATED

def log(_text, _var):
    xbmc.log(f'{_text} = {str(_var)}', xbmc.LOGINFO)

excludes = [p / 'addons/packages', p / 'addons/temp', p / 'userdata/Thumbnails', p / 'userdata/Database/Textures13.db', p / 'userdata/Database/Textures14.db', p / wizard_path]

def _foreign_native(filename):
    """Skip add-on natives that do not belong on this OS (e.g. Windows .dll on Android)."""
    name = filename.replace('\\', '/').lower()
    if not name.startswith('addons/'):
        return False
    ext = os.path.splitext(name)[1]
    if ext in ('.dll', '.pyd'):
        return os_name != 'Windows'
    if ext == '.so':
        return os_name not in ('Linux', 'Android')
    if ext == '.dylib':
        return os_name not in ('macOS', 'iOS')
    return False

def from_keyboard():
    kb = xbmc.Keyboard('', '[COLOR red]Enter Backup Name[/COLOR]', False)
    kb.doModal()
    if (kb.isConfirmed()):
        return kb.getText()
    else:
        return False

def backup_build():
    backup_path.mkdir(parents=True, exist_ok=True)
    k = from_keyboard()
    if k is False:
        return xbmcgui.Dialog().ok('[COLOR red]Backup[/COLOR]', '[COLOR gold]Backup Cancelled[/COLOR]')
    else:
        backup_name = backup_path / f'{k}.zip'
        
    addons_dirs, addons_files = ([x for x in addons.iterdir() if x.is_dir() and x not in excludes]), ([x for x in addons.iterdir() if x.is_file() and x not in excludes])

    media_dirs, media_files = ([x for x in media.iterdir() if x.is_dir() and x not in excludes]), ([x for x in media.iterdir() if x.is_file() and x not in excludes])

    userdata_dirs, userdata_files = ([x for x in userdata.iterdir() if x.is_dir() and x not in excludes]), ([x for x in userdata.iterdir() if x.is_file() and x not in excludes])
    
    zip_file = ZipFile(backup_name, 'w')
    xbmcgui.Dialog().notification(addon_name, 'Backup in progress, please wait!', addon_icon, 3000)
    for x in sorted(addons_dirs):
        for z in sorted([y for y in x.rglob('*') if y not in excludes]):
            try:
                if '__pycache__' not in str(z):
                    zip_file.write(z, str(z.relative_to(p)), compress_type=compression)
            except Exception as e:
                xbmc.log(f'Unable to compress file {str(z)}: {e}', xbmc.LOGINFO)
    for x in sorted(addons_files):
        try:
            zip_file.write(x, str(x.relative_to(p)), compress_type=compression)
        except Exception as e:
            xbmc.log(f'Unable to compress file {str(x)}: {e}', xbmc.LOGINFO)
    
    for x in sorted(media_dirs):
        for z in sorted([y for y in x.rglob('*') if y not in excludes]):
            try:
                zip_file.write(z, str(z.relative_to(p)), compress_type=compression)
            except Exception as e:
                xbmc.log(f'Unable to compress file {str(z)}: {e}', xbmc.LOGINFO)
    for x in sorted(media_files):
        try:
            zip_file.write(x, str(x.relative_to(p)), compress_type=compression)
        except Exception as e:
            xbmc.log(f'Unable to compress file {str(x)}: {e}', xbmc.LOGINFO)

    for x in sorted(userdata_dirs):
        for z in sorted([y for y in x.rglob('*') if y not in excludes]):
            try:
                zip_file.write(z, str(z.relative_to(p)), compress_type=compression)
            except Exception as e:
                xbmc.log(f'Unable to compress file {str(z)}: {e}', xbmc.LOGINFO)
    for x in sorted(userdata_files):
        try:
            zip_file.write(x, str(x.relative_to(p)), compress_type=compression)
        except Exception as e:
            xbmc.log(f'Unable to compress file {str(x)}: {e}', xbmc.LOGINFO)
    
    zip_file.close()
    xbmcgui.Dialog().ok('[COLOR red]Backup[/COLOR]', '[COLOR gold]Backup Complete[/COLOR]')

excludes_freshstart = [addon_id, 'backups',  'Addons33.db', 'kodi.log']

def fresh_start_restore():
    for root, dirs, files in os.walk(xbmcPath, topdown=True):
        dirs[:] = [d for d in dirs if d not in excludes_freshstart]
        for name in files:
            if name not in excludes_freshstart:
                try:
                    os.unlink(os.path.join(root, name))
                except:
                    log('Error Deleting', name)
                    
    for root, dirs, files in os.walk(xbmcPath,topdown=True):
        dirs[:] = [d for d in dirs if d not in excludes_freshstart]
        for name in dirs:
            if name not in ['addons', 'userdata', 'Database', 'addon_data', 'backups', 'temp']:
                try:
                    shutil.rmtree(os.path.join(root,name),ignore_errors=True, onerror=None)
                except:
                    log('Error Deleting', name)

def get_backup_folder():
    dialog = xbmcgui.Dialog()
    fn = dialog.browseSingle(0, '[COLOR red]Select Backup Location[/COLOR]', 'local', '', False, False)
    setting_set('backupfolder', fn)

def reset_backup_folder():
    setting_set('backupfolder', 'special://home/backups')
    xbmcgui.Dialog().ok('[COLOR red]Backup Folder[/COLOR]', '[COLOR gold]Backup folder location set to default![/COLOR]')

def restore_menu():
    build_backups = ([x for x in backup_path.iterdir() if x.is_file() and str(x).endswith('.zip')])
    for build in build_backups:
        add_dir(str(build.stem), str(build), 15, addon_icon, addon_fanart, str(build.name), isFolder=False)

def restore_build(zippath):
    restore = xbmcgui.Dialog().yesno('[COLOR red]Restore[/COLOR]', '[COLOR gold]Are you sure you want to wipe your\ncurrent data and restore from backup?[/COLOR]')
    if restore is True:
        fresh_start_restore()
        if os.path.exists(zippath):
            dp.create('Restore', local_string(30034))  # Extracting files
            counter = 1
            with ZipFile(zippath, 'r') as z:
                files = z.infolist()
                for file in files:
                    filename = file.filename
                    filename_path = os.path.join(home, filename)
                    progress_percentage = int(counter/len(files)*100)
                    try:
                        if _foreign_native(filename):
                            xbmc.log(f'Skipped foreign binary {filename}', xbmc.LOGINFO)
                        elif not os.path.exists(filename_path) or 'Addons33.db' in filename:
                            z.extract(file, home)
                    except Exception as e:
                        xbmc.log(f'[COLOR gold]Error extracting {filename} - {e}[/COLOR]', xbmc.LOGINFO)
                    dp.update(progress_percentage, f'[COLOR gold]{local_string(30034)}[/COLOR][COLOR red]\n{progress_percentage}%\n{filename}[/COLOR]')
                    counter += 1
            from .build_install import check_binary
            check_binary()
            dp.update(100, local_string(30035))  # Done Extracting
            xbmcgui.Dialog().ok('[COLOR red]Restore[/COLOR]', '[COLOR gold]Restore Complete[/COLOR]')
            setting_set('firstrun', 'true')
            os._exit(1)
        else:
            xbmcgui.Dialog().ok('Restore', 'Backup Not Found')
    else:
        return False
