import xbmcgui

import os

try:
    from urllib.parse import parse_qsl
    from urllib.parse import unquote
except ImportError:
    from urlparse import parse_qsl
    from urllib import unquote

from resources.lib import manage
from resources.lib.common import settings
from resources.lib.common import utils

_addon_data = settings.get_addon_info("profile")

# Shortcut, Clone as Shortcut Group, Settings Shortcut
shortcut_types = [
    30032,
    30059,
    30034,
]

type_labels = [
    30144,
    30146,
    30148,
]

folder_shortcut = utils.get_art("folder-shortcut")
folder_settings = utils.get_art("folder-settings")
folder_clone = utils.get_art("folder-clone")
_folder_art = {
    30032: folder_shortcut,
    30059: folder_clone,
    30034: folder_settings,
}


def add(labels):
    _type = _add_as(labels["file"])
    if not _type:
        return

    if _type != "clone":
        labels["target"] = _type
        group_def = _group_dialog()
        if group_def:
            _add_path(group_def, labels)
    else:
        labels["target"] = "shortcut"
        _copy_path(labels)

    utils.update_container(True)


def build_labels(source, path_def=None, target=""):
    if source == "context" and not path_def and not target:
        content = utils.get_infolabel("Container.Content")
        labels = {
            "label": utils.get_infolabel("ListItem.Label"),
            "content": content if content else "videos",
        }

        path_def = {
            "file": utils.get_infolabel("ListItem.FolderPath"),
            "filetype": "directory"
            if utils.get_condition("Container.ListItem.IsFolder")
            else "file",
            "art": {},
        }  # would be fun to set some "placeholder" art here

        for i in utils.get_info_keys() + ["DBType"]:
            info = utils.get_infolabel("ListItem.{}".format(i.capitalize()))
            if info and not info.startswith("ListItem"):
                path_def[i if i != "DBType" else "type"] = info

        for i in utils.art_types:
            art = utils.get_infolabel("ListItem.Art({})".format(i))
            if art:
                path_def["art"][i] = utils.clean_artwork_url(art)
        for i in ["icon", "thumb"]:
            art = utils.clean_artwork_url(utils.get_infolabel("ListItem.{}".format(i)))
            if art:
                path_def["art"][i] = art
    elif source == "json" and path_def and target:
        labels = {"label": path_def["label"], "content": "videos", "target": target}

    labels["file"] = (
        path_def
        if path_def
        else {key: path_def[key] for key in path_def if path_def[key]}
    )
    path = labels["file"]["file"]

    if path != "addons://user/":
        path = path.replace("addons://user/", "plugin://")
        path = path.replace("addons://dependencies/", "dependency://")
    if "plugin://plugin.video.themoviedb.helper" in path and not "&widget=True" in path:
        path += "&widget=True"
    labels["file"]["file"] = path

    labels["color"] = settings.get_setting_string("ui.color")

    for _key in utils.windows:
        if any(i in path for i in utils.windows[_key]):
            labels["window"] = _key

    return labels


def _add_as(path_def):
    path = path_def["file"]
    types = list(zip(shortcut_types[:], type_labels[:]))
    if path_def["filetype"] == "directory" and utils.get_active_window() != "home":
        types = list(zip(shortcut_types[:2], type_labels[:2]))
    else:
        if any(
            i in path for i in ["addons://user", "plugin://", "script://"]
        ) and not parse_qsl(path):
            pass
        elif "dependency://" in path:
            types = [(shortcut_types[2], type_labels[2])]
        else:
            types = [(shortcut_types[0], type_labels[0])]

    options = []
    for type in types:
        li = xbmcgui.ListItem(utils.get_string(type[0]), utils.get_string(type[1]))
        li.setArt(_folder_art[type[0]])
        options.append(li)

    dialog = xbmcgui.Dialog()
    idx = dialog.select(utils.get_string(30061), options, useDetails=True)
    del dialog

    if idx < 0:
        return

    chosen = types[idx][0]
    if chosen == shortcut_types[0]:
        return "shortcut"
    elif chosen == shortcut_types[1]:
        return "clone"
    elif chosen == shortcut_types[2]:
        return "settings"


def _group_dialog(group_id=None):
    groups = manage.find_defined_groups("shortcut")
    ids = [group["id"] for group in groups]

    index = -1
    options = []

    new_shortcut = xbmcgui.ListItem(utils.get_string(30011))
    new_shortcut.setArt(folder_shortcut)
    options.append(new_shortcut)

    if group_id:
        index = ids.index(group_id) + 1

    for group in groups:
        item = xbmcgui.ListItem(group["label"])
        item.setArt(folder_shortcut)
        options.append(item)

    dialog = xbmcgui.Dialog()
    choice = dialog.select(
        utils.get_string(30035), options, preselect=index, useDetails=True
    )
    del dialog

    if choice < 0:
        dialog = xbmcgui.Dialog()
        dialog.notification("Shortcut Manager", utils.get_string(30020))
        del dialog
    elif choice == 0:
        return _group_dialog(add_group())
    else:
        return groups[choice - 1]


def add_group(group_name=""):
    dialog = xbmcgui.Dialog()
    group_name = dialog.input(heading=utils.get_string(30022), defaultt=group_name)
    group_id = ""

    if group_name:
        group_id = utils.get_unique_id(group_name)
        filename = os.path.join(_addon_data, "{}.group".format(group_id))
        group_def = {
            "label": group_name,
            "type": "shortcut",
            "paths": [],
            "id": group_id,
            "art": folder_shortcut,
            "version": settings.get_addon_info("version"),
            "content": "",
            "sort_order": "{}".format(int(manage.highest_group_sort_order()) + 1),
        }

        utils.write_json(filename, group_def)
    else:
        dialog.notification("Shortcut Manager", utils.get_string(30023))

    del dialog
    return group_id


def add_subfolder(parent_group_id):
    parent_def = manage.get_group_by_id(parent_group_id)
    if not parent_def or parent_def.get("type") != "shortcut":
        return

    dialog = xbmcgui.Dialog()
    group_name = dialog.input(heading=utils.get_string(30167))
    del dialog

    if not group_name:
        return

    group_id = utils.get_unique_id(group_name)
    filename = os.path.join(_addon_data, "{}.group".format(group_id))
    group_def = {
        "label": group_name,
        "type": "shortcut",
        "paths": [],
        "id": group_id,
        "parent": parent_group_id,
        "art": folder_shortcut,
        "version": settings.get_addon_info("version"),
        "content": "",
        "sort_order": "{}".format(int(manage.highest_group_sort_order()) + 1),
    }

    utils.write_json(filename, group_def)

    # Track the subfolder as an ordered entry in the parent's own path list
    # (appended at the end, so it lands below existing items by default)
    # rather than only via the "parent" link, so it can be freely reordered
    # alongside regular shortcuts with the same up/down actions.
    pointer = {
        "id": utils.get_unique_id(group_name),
        "label": group_name,
        "target": "subfolder",
        "group": group_id,
        "file": {"filetype": "directory", "file": "", "art": {}},
        "version": settings.get_addon_info("version"),
    }
    manage.write_path(parent_def, path_def=pointer)

    utils.update_container(True)
    return group_id


def copy_group(group_id):
    old_group_def = manage.get_group_by_id(group_id)

    new_group_id = add_group(old_group_def.get("label"))
    if not new_group_id:
        return
    new_group_def = manage.get_group_by_id(new_group_id)
    new_group_def["art"] = old_group_def.get("art", {})
    new_group_def["content"] = old_group_def.get(
        "content", new_group_def.get("content", "files")
    )

    # Subfolders are excluded from copying: copying a pointer would leave
    # two groups referencing the same underlying subfolder, and copying
    # the whole nested tree isn't supported.
    paths = [
        p for p in old_group_def.get("paths", []) if p.get("target") != "subfolder"
    ]
    new_group_def["paths"] = manage.choose_paths(
        utils.get_string(30120), paths, indices=False
    )
    manage.write_path(new_group_def)

    utils.update_container(True)


def _add_path(group_def, labels, over=False):
    if not over:
        heading = utils.get_string(30027)

        dialog = xbmcgui.Dialog()
        labels["label"] = dialog.input(heading=heading, defaultt=labels["label"])
        del dialog

    labels["id"] = utils.get_unique_id(labels["label"])
    labels["version"] = settings.get_addon_info("version")

    if labels["target"] == "settings":
        labels["file"]["filetype"] = "file"
        labels["file"]["file"] = labels["file"]["file"].split("&")[0]
    elif labels["target"] == "shortcut" and labels["file"]["filetype"] == "file":
        labels["content"] = None

    manage.write_path(group_def, path_def=labels)


def _list_directory(path):
    """One-off directory listing used by "Clone as Shortcut Group". Unlike
    the addon's old live widgets, cloned shortcuts are a snapshot taken at
    creation time, so this intentionally skips any caching/refresh machinery."""
    params = {
        "jsonrpc": "2.0",
        "method": "Files.GetDirectory",
        "params": {
            "properties": utils.get_info_keys(),
            "directory": path,
        },
        "id": 1,
    }
    result = utils.call_jsonrpc(params)
    files = (
        result.get("result", {}).get("files", []) if "error" not in result else []
    )

    new_files = []
    for file in files:
        new_file = {k: v for k, v in file.items() if v is not None}
        if "art" in new_file:
            for art in new_file["art"]:
                new_file["art"][art] = utils.clean_artwork_url(file["art"][art])
        new_files.append(new_file)

    return new_files


def _copy_path(path_def):
    group_def = _group_dialog()
    if not group_def:
        return

    progress = xbmcgui.DialogProgressBG()
    progress.create("Shortcut Manager", utils.get_string(30141))
    progress.update(1, "Shortcut Manager", utils.get_string(30142))

    files = _list_directory(path_def["file"]["file"])
    if not files:
        progress.close()
        return
    done = 0
    for file in files:
        done += 1
        if file.get("type") in ["movie", "episode", "musicvideo", "song"]:
            continue
        progress.update(
            int(done / float(len(files)) * 100),
            heading=utils.get_string(30141),
            message=file.get("label"),
        )

        labels = build_labels("json", file, "shortcut")
        _add_path(group_def, labels, over=True)
    progress.close()
    del progress
    dialog = xbmcgui.Dialog()
    dialog.notification(
        "Shortcut Manager", utils.get_string(30104).format(len(files), group_def["label"])
    )
    del dialog
