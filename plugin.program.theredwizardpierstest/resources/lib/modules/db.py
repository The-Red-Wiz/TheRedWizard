import xbmc, xbmcaddon
import xbmcvfs
import sqlite3
import os
import time
from sqlite3 import Error
from .addonvar import addons_db


###################### Connect to Database ######################
def create_conn(db_file):
    try:
        conn = None
        try:
            conn = sqlite3.connect(db_file)
        except Error as e:
            print(e)

        return conn
    except:
        pass

############### Fetch Repo Last Check Date/Time ################
def repo_lastchk():
    # Create database connection
    conn = create_conn(addons_db)
    repos = conn.execute('SELECT lastcheck FROM repo')
    time = 0
    for lastchk in repos.fetchone():
        if lastchk:
            return lastchk
        else:
            return time
lastchk = repo_lastchk()
