import os
import re
import shutil
import sqlite3
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import json
import shutil
from xml.etree import ElementTree as ET
from .skinSwitch import swapSkins
from .addonvar import setting, setting_set, currSkin, user_path, db_path, addon_name, textures_db, dialog, dp, xbmcPath, packages, addon_icon, local_string, addons_db, advancedsettings_xml
from .whitelist import EXCLUDES_INSTALL, EXCLUDES_FRESH

def purge_db(db):
    if os.path.exists(db):
        try:
            conn = sqlite3.connect(db)
            cur = conn.cursor()
        except Exception as e:
            xbmc.log("DB Connection Error: %s" % str(e), xbmc.LOGDEBUG)
            return False
    else: 
        xbmc.log('%s not found.' % db, xbmc.LOGINFO)
        return False
    cur.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    for table in cur.fetchall():
        if table[0] == 'version': 
            xbmc.log('Data from table `%s` skipped.' % table[0], xbmc.LOGDEBUG)
        else:
            try:
                cur.execute("DELETE FROM %s" % table[0])
                conn.commit()
                xbmc.log('Data from table `%s` cleared.' % table[0], xbmc.LOGDEBUG)
            except Exception as e:
                xbmc.log("DB Remove Table `%s` Error: %s" % (table[0], str(e)), xbmc.LOGERROR)
    conn.execute('VACUUM')
    conn.close()
    xbmc.log('%s DB Purging Complete.' % db, xbmc.LOGINFO)

def clear_thumbnails():
    try:
        if os.path.exists(os.path.join(user_path, 'Thumbnails')):
            shutil.rmtree(os.path.join(user_path, 'Thumbnails'))
    except Exception as e:
            xbmc.log('Failed to delete %s. Reason: %s' % (os.path.join(user_path, 'Thumbnails'), e), xbmc.LOGINFO)
            return
    try:
        purge_db(textures_db)
    except:
        xbmc.log('%s DB Purging Failed.' % textures_db, xbmc.LOGINFO)
    xbmc.sleep(1000)
    xbmcgui.Dialog().ok(addon_name, local_string(30037))  # Thumbnails Deleted

def advanced_set(buffer, ram, read):
    #xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"general.settinglevel","value":3},"id":1}')
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"filecache.buffermode","value":%s},"id":1}' %(buffer))
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"filecache.memorysize","value":%s},"id":1}' %(ram))
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"filecache.readfactor","value":%s},"id":1}' %(read))
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"filecache.chunksize","value":131072},"id":1}')
    #xbmcgui.Dialog().ok(addon_name, 'To save changes, please close Kodi, Press OK to force close Kodi')
    #xbmc.executebuiltin('Quit')
    xbmc.executebuiltin('ActivateWindowAndFocus(servicesettings), True')
    xbmc.executebuiltin('Action(Back)')

def _auto_detect_cache_mb():
    """A third of free RAM, clamped to 20–1024 MB (EZ Maintenance+ heuristic)."""
    free_mem_label = xbmc.getInfoLabel('System.FreeMemory')
    free_mb_digits = re.sub('[^0-9]', '', free_mem_label or '')
    free_mb = int(free_mb_digits) if free_mb_digits else 0
    return max(20, min(1024, free_mb // 3))

def advanced_settings():
    selection = xbmcgui.Dialog().select(local_string(30038), ['[COLOR gold]1GB Devices (e.g., 1st-3rd gen Firestick/Firestick Lite)[/COLOR]','[COLOR gold]1.5GB Devices (e.g., 4K Firestick)[/COLOR]','[COLOR gold]2GB+ Devices (e.g., Shield Pro/Shield Tube/FireTV Cube)[/COLOR]','[COLOR gold]Auto Detect (based on free RAM)[/COLOR]','[COLOR gold]Default (Reset to Default)[/COLOR]'])  # Select Ram Size
    if selection==0:
        advanced_set('2', '128', '0')
    elif selection==1:
        advanced_set('2', '192', '0')
    elif selection==2:
        advanced_set('2', '256', '0')
    elif selection==3:
        ram = _auto_detect_cache_mb()
        advanced_set('2', str(ram), '0')
        xbmc.sleep(1000)
        xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Cache set to %s MB from free RAM[/COLOR]' % ram, addon_icon, 3000)
        return
    elif selection==4:
        advanced_set('4', '20', '400')
    else:
        return
    xbmc.sleep(1000)
    xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Cache Settings updated![/COLOR]', addon_icon, 3000)

def _pretty_print(current, parent=None, index=-1, depth=0):
    for i, node in enumerate(current):
        _pretty_print(node, current, i, depth + 1)
    if parent is not None:
        if index == 0:
            parent.text = '\n' + ('\t' * depth)
        else:
            parent[index - 1].tail = '\n' + ('\t' * depth)
        if index == len(parent) - 1:
            current.tail = '\n' + ('\t' * (depth - 1))
            
def splash(on_off):
    if not xbmcvfs.exists(advancedsettings_xml): #If advacnedsettings.xml does not exist copy blank file
        shutil.copyfile(advancedsettings_blank, advancedsettings_xml)
    if xbmcvfs.exists(advancedsettings_xml):
        tree = ET.parse(advancedsettings_xml) #Parse Advancedsettings.xml
        root = tree.getroot()
        item = root.find('splash')
        if item is None: #If splash does not exist create element
            element = ET.Element('advancedsettings')
            sub_element = ET.SubElement(element, 'splash')
            sub_element.text = on_off
            root.insert(0, sub_element)
            _pretty_print(root)
            tree = ET.ElementTree(root)
            tree.write(advancedsettings_xml) #Write settings to advancedsettings.xml
        else:
            for splash in root.iter('splash'): #If splash element exists write setting
                    splash.text = on_off
                    tree = ET.ElementTree(root)
                    tree.write(advancedsettings_xml)

def skin_override(skin, xml):
    if xbmcvfs.exists(xml):
        tree = ET.parse(xml) #Parse Advancedsettings.xml
        root = tree.getroot()
        #Create lookandfeel/skin elements
        element = ET.Element('advancedsettings')
        sub_element = ET.SubElement(element, 'lookandfeel')
        sub_element_skin = ET.SubElement(sub_element, 'skin')
        sub_element_skin.text = skin
        root.insert(0, sub_element)
        _pretty_print(root)
        tree = ET.ElementTree(root)
        tree.write(xml) #Write settings to advancedsettings.xml

def skin_override_disable():
    if xbmcvfs.exists(advancedsettings_xml):
        tree = ET.parse(advancedsettings_xml) #Parse Advancedsettings.xml
        root = tree.getroot()
        if len(root.findall('lookandfeel')) == 0: #Check if skin settings exist
            pass
        else:
            for lookandfeel in root.findall('lookandfeel'):
                root.remove(lookandfeel) #Remove skin settings from advancedsettings.xml
                tree = ET.ElementTree(root)
                tree.write(advancedsettings_xml)

def fresh_start(standalone=False):
    if standalone:
        yesFresh = dialog.yesno(local_string(30066), local_string(30042), nolabel=local_string(30032), yeslabel=local_string(30012))  # Are you sure?
        if not yesFresh:
            quit()
    '''if not currSkin() in ['skin.estuary']:
        swapSkins('skin.estuary')
        x = 0
        xbmc.sleep(100)
        while not xbmc.getCondVisibility("Window.isVisible(yesnodialog)") and x < 150:
            x += 1
            xbmc.sleep(100)
            xbmc.executebuiltin('SendAction(Select)')
        if xbmc.getCondVisibility("Window.isVisible(yesnodialog)"):
            xbmc.executebuiltin('SendClick(11)')
        else: 
            xbmc.log('Fresh Install: Skin Swap Timed Out!', xbmc.LOGINFO)
            return False
        xbmc.sleep(100)
    if not currSkin() in ['skin.estuary']:
        xbmc.log('Fresh Install: Skin Swap failed.', xbmc.LOGINFO)
        return'''
    dp.create(addon_name, local_string(30043))  # Deleting files and folders...
    xbmc.sleep(100)
    dp.update(30, local_string(30043))
    xbmc.sleep(100)
    if standalone:
        dp.close()
        xbmc.sleep(500)
        for root, dirs, files in os.walk(xbmcPath, topdown=True):
            dirs[:] = [d for d in dirs if d not in EXCLUDES_FRESH]
            for name in files:
                if name not in EXCLUDES_FRESH:
                    try:
                        os.remove(os.path.join(root, name))
                    except:
                        xbmc.log('Unable to delete ' + name, xbmc.LOGINFO)
        dp.update(60, local_string(30043))
        xbmc.sleep(100)    
        for root, dirs, files in os.walk(xbmcPath,topdown=True):
            dirs[:] = [d for d in dirs if d not in EXCLUDES_FRESH]
            for name in dirs:
                if name not in ['addons', 'userdata', 'Database', 'addon_data', 'backups', 'temp']:
                    try:
                        shutil.rmtree(os.path.join(root,name),ignore_errors=True, onerror=None)
                    except:
                        xbmc.log('Unable to delete ' + name, xbmc.LOGINFO)
    if not standalone:
        for root, dirs, files in os.walk(xbmcPath, topdown=True):
            dirs[:] = [d for d in dirs if d not in EXCLUDES_INSTALL]
            for name in files:
                if name not in EXCLUDES_INSTALL:
                    try:
                        os.remove(os.path.join(root, name))
                    except:
                        xbmc.log('Unable to delete ' + name, xbmc.LOGINFO)
        dp.update(60, local_string(30043))
        xbmc.sleep(100)
        for root, dirs, files in os.walk(xbmcPath,topdown=True):
            dirs[:] = [d for d in dirs if d not in EXCLUDES_INSTALL]
            for name in dirs:
                if name not in ['addons', 'userdata', 'Database', 'addon_data', 'backups', 'temp']:
                    try:
                        shutil.rmtree(os.path.join(root,name),ignore_errors=True, onerror=None)
                    except:
                        xbmc.log('Unable to delete ' + name, xbmc.LOGINFO)
    dp.update(60, local_string(30043))
    xbmc.sleep(100)
    if not os.path.exists(packages):
        os.mkdir(packages)
    dp.update(100, local_string(30044))  # Done Deleting Files
    xbmc.sleep(1000)
    purge_db(textures_db)
    if standalone is True:
        setting_set('firstrun', 'true')
        setting_set('buildname', 'No Build Installed')
        setting_set('buildversion', '0')
        setting_set('skin_protection', 'false')
        purge_db(textures_db)
        truncate_tables(Fresh=True)
        xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Fresh Start Complete![/COLOR]', addon_icon, 3000)
        xbmc.sleep(4000)
        xbmcgui.Dialog().notification(addon_name, '[COLOR gold]Force Closing Kodi![/COLOR]', addon_icon, 3000)
        xbmc.sleep(3500)
        os._exit(1)
    else:
        return

def clean_backups():
    for filename in os.listdir(packages):
        file_path = os.path.join(packages, filename)
        try:
            os.unlink(file_path)
        except OSError:
            shutil.rmtree(file_path)

def clear_packages_startup():
    if not os.path.exists(packages):
        return
    count = len(os.listdir(packages))
    raw = setting('autoclearpackages')
    try:
        user_setting = int(raw)
    except (TypeError, ValueError):
        user_setting = 1 if raw == 'true' else 0
    if ((user_setting == 1 and count >= 1) or (user_setting == 2 and count >= 10) or (user_setting == 3 and count >= 20)):
        clear_packages()
        
def clear_packages():
    file_count = len([name for name in os.listdir(packages)])
    for filename in os.listdir(packages):
        file_path = os.path.join(packages, filename)
        try:
               if os.path.isfile(file_path) or os.path.islink(file_path):
                   os.unlink(file_path)
               elif os.path.isdir(file_path):
                   shutil.rmtree(file_path)
        except Exception as e:
            xbmc.log('Failed to delete %s. Reason: %s' % (file_path, e), xbmc.LOGINFO)
    xbmcgui.Dialog().notification(addon_name, str(file_count)+' ' + local_string(30046), addon_icon, 5000, sound=False)  # Packages Cleared

def truncate_tables(Fresh=False):
    try:
        con = sqlite3.connect(addons_db)
        cursor = con.cursor()
        for repo_id in ('repository.xbmc.org', 'repository.redwizard'):
            cursor.execute('UPDATE repo SET version = ?, checksum = ?, lastcheck = ? WHERE addonID = ?', ('', '', '', repo_id))
        if Fresh:
            cursor.execute('DELETE FROM addonlinkrepo;',)
            cursor.execute('DELETE FROM addons;',)
            cursor.execute('DELETE FROM package;',)
            cursor.execute('DELETE FROM repo;',)
            cursor.execute('DELETE FROM update_rules;',)
            cursor.execute('DELETE FROM version;',)
        con.commit()
    except sqlite3.Error as e:
        xbmc.log('There was an error reading the database - %s' %e, xbmc.LOGINFO)
        return ''
    finally:
        try:
            if con:
                con.close()
        except UnboundLocalError as e:
            xbmc.log('%s: There was an error connecting to the database - %s' % (xbmcaddon.Addon().getAddonInfo('name'), e), xbmc.LOGINFO)
    try:
        con = sqlite3.connect(addons_db)
        cursor = con.cursor()
        cursor.execute('VACUUM;',)
        con.commit()
    except sqlite3.Error as e:
        xbmc.log(f"Failed to vacuum data from the sqlite table: {e}", xbmc.LOGINFO)
    finally:
        if con:
            con.close()
