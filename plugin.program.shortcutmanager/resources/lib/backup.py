import xbmc
import xbmcgui
import xbmcvfs

import os
import zipfile

import six

from resources.lib.common import settings
from resources.lib.common import utils

_addon_data = settings.get_addon_info("profile")
DEFAULT_BACKUP_LOCATION = "special://profile/plugin.program.shortcutmanager/backups/"


def get_backup_location():
    location = settings.get_setting_string("backup.location")
    if not location:
        location = DEFAULT_BACKUP_LOCATION
    return location


def get_backup_location_path():
    return utils.translatePath(get_backup_location())

_choices = [
    (".group", utils.get_string(30153), utils.get_string(30154)),
    (".xml", utils.get_string(30159), utils.get_string(30160)),
]


def location():
    dialog = xbmcgui.Dialog()
    folder = dialog.browse(
        0, utils.get_string(30067), "files", defaultt=get_backup_location_path()
    )
    del dialog

    if folder:
        settings.set_setting_string("backup.location", folder)


def backup():
    dialog = xbmcgui.Dialog()
    choice = dialog.yesno("Shortcut Manager", utils.get_string(30070))

    if choice:
        filename = dialog.input(utils.get_string(30071))

        if not filename:
            dialog.notification("Shortcut Manager", utils.get_string(30072))
            del dialog
            return

        backup_location = get_backup_location_path()
        if not xbmcvfs.exists(backup_location):
            try:
                xbmcvfs.mkdirs(backup_location)
            except Exception as e:
                utils.log(str(e), "error")
                dialog.notification("Shortcut Manager", utils.get_string(30073))
                del dialog
                return

        files = [
            x
            for x in xbmcvfs.listdir(_addon_data)[1]
            if any(x.endswith(i) for i in [".group", ".log", ".xml"])
        ]
        if len(files) == 0:
            dialog.notification("Shortcut Manager", utils.get_string(30045))
            del dialog
            return

        backup_dialog = xbmcgui.DialogProgress()
        backup_dialog.create(utils.get_string(30068), utils.get_string(30165))
        path = os.path.join(
            backup_location, "{}.zip".format(filename.replace(".zip", ""))
        )
        content = six.BytesIO()
        with zipfile.ZipFile(content, "w", zipfile.ZIP_DEFLATED) as z:
            for idx, file in enumerate(files):
                backup_dialog.update(int(idx / len(files) * 100))
                with xbmcvfs.File(os.path.join(_addon_data, file)) as f:
                    z.writestr(file, six.ensure_text(f.read()))

        backup_dialog.close()
        del backup_dialog

        with xbmcvfs.File(path, "w") as f:
            f.write(content.getvalue())

        dialog.notification("Shortcut Manager", utils.get_string(30166))
    del dialog


def restore():
    dialog = xbmcgui.Dialog()
    backup = dialog.browse(
        1,
        utils.get_string(30074),
        "",
        mask=".zip",
        defaultt=get_backup_location_path(),
    )

    if backup.endswith(".zip"):

        content = six.BytesIO(xbmcvfs.File(backup).readBytes())
        with zipfile.ZipFile(content, "r") as z:
            info = z.infolist()
            choice_items = []
            chosen = []
            for c in _choices:
                for i in info:
                    if i.filename.endswith(c[0]):
                        item = xbmcgui.ListItem(c[1], label2=c[2])
                        choice_items.append(item)
                        break
            choices = dialog.multiselect(
                utils.get_string(30075),
                choice_items,
                preselect=list(range(len(choice_items))),
                useDetails=True,
            )

            if choices:
                temp_path = os.path.join(_addon_data, "temp")
                if not xbmcvfs.exists(temp_path):
                    xbmcvfs.mkdirs(temp_path)

                restore_progress = xbmcgui.DialogProgress()
                overwrite = dialog.yesno("Shortcut Manager", utils.get_string(30076))

                if overwrite:
                    restore_progress.create(
                        utils.get_string(30069), utils.get_string(30161)
                    )
                    files = [
                        x
                        for x in xbmcvfs.listdir(_addon_data)[1]
                        if not x.endswith(".log")
                    ]
                    for idx, file in enumerate(files):
                        restore_progress.update(int(idx / len(files) * 100))
                        utils.remove_file(os.path.join(_addon_data, file))
                    restore_progress.close()

                restore_progress.create(
                    utils.get_string(30069), utils.get_string(30162)
                )
                utils.call_builtin("Extract({},{})".format(backup, temp_path))
                xbmc.sleep(1000)

                for t in choices:
                    ext = _choices[t][0]
                    restore_progress.update(
                        0,
                        utils.get_string(30163).format(
                            ext if type(ext) != tuple else ', '.join(ext)
                        ),
                    )
                    files = [
                        x for x in xbmcvfs.listdir(temp_path)[1] if x.endswith(ext)
                    ]
                    for idx, file in enumerate(files):
                        restore_progress.update(int(idx / len(files) * 100))
                        xbmcvfs.copy(
                            os.path.join(temp_path, file),
                            os.path.join(_addon_data, file),
                        )
                restore_progress.close()
                del restore_progress
                utils.wipe(temp_path, True)
                dialog.notification("Shortcut Manager", utils.get_string(30164))
            else:
                dialog.notification("Shortcut Manager", utils.get_string(30077))
        del dialog
    else:
        dialog.notification("Shortcut Manager", utils.get_string(30077))
        del dialog
        return
