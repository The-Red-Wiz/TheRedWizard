import xbmcgui
import xbmcvfs

import os

from resources.lib.common import settings
from resources.lib.common import utils

_addon_data = settings.get_addon_info("profile")
_userdata = "special://profile/"


def write_path(group_def, path_def=None, update=""):
    filename = os.path.join(_addon_data, "{}.group".format(group_def["id"]))

    if path_def:
        if update:
            for path in group_def["paths"]:
                if path["id"] == update:
                    path["version"] = settings.get_addon_info("version")
                    group_def["paths"][group_def["paths"].index(path)] = path_def
        else:
            group_def["paths"].append(path_def)

    group_def["version"] = settings.get_addon_info("version")
    utils.write_json(filename, group_def)


def get_group_by_id(group_id):
    if not group_id:
        return {}

    filename = "{}.group".format(group_id)
    path = os.path.join(_addon_data, filename)

    try:
        group_def = utils.read_json(path)
    except ValueError:
        utils.log("Unable to parse: {}".format(path))
        return

    return group_def


def get_path_by_id(path_id, group_id=None):
    if not path_id:
        return {}

    for defined in find_defined_paths(group_id):
        if defined.get("id", "") == path_id:
            return defined


def highest_group_sort_order():
    groups = find_defined_groups()
    return groups[-1].get("sort_order", 0) if len(groups) > 0 else 0


def find_defined_groups(_type=""):
    groups = []
    sort_order = 0

    for filename in [
        x for x in xbmcvfs.listdir(_addon_data)[1] if x.endswith(".group")
    ]:
        path = os.path.join(_addon_data, filename)

        group_def = utils.read_json(path)
        if group_def:
            if not group_def.get("sort_order"):
                group_def["sort_order"] = "{}".format(sort_order)
                utils.write_json(path, group_def)
            if group_def.get("content") is None:
                group_def["content"] = ""
                utils.write_json(path, group_def)

            if _type:
                if group_def["type"] == _type:
                    groups.append(group_def)
            else:
                groups.append(group_def)
        sort_order += 1

    return sorted(groups, key=lambda x: int(x["sort_order"]))


def find_defined_paths(group_id=None):
    if group_id:
        filename = "{}.group".format(group_id)
        path = os.path.join(_addon_data, filename)

        group_def = utils.read_json(path)
        if group_def:
            return group_def.get("paths", [])
        else:
            return []
    else:
        paths = []
        for group in find_defined_groups():
            group_paths = find_defined_paths(group_id=group.get("id"))
            for path in group_paths:
                paths.append(path)
        return paths


def choose_paths(
    label=utils.get_string(30121),
    paths=None,
    threshold=None,
    indices=True,
    single=False,
):
    if paths is None:
        return []

    idx = None
    idxs = []
    dialog = xbmcgui.Dialog()

    if len(paths) == 1:
        if indices:
            return 0 if single else [0]
        else:
            return paths[0] if single else [paths[0]]

    if single:
        idx = dialog.select(
            label,
            [i["label"] for i in paths],
        )
    else:
        idxs = dialog.multiselect(
            label,
            [i["label"] for i in paths],
            preselect=(
                list(range(len(paths)))
                if len(paths) <= threshold or threshold == -1
                else []
            )
            if threshold is not None
            else list(range(len(paths))),
        )
    del dialog

    if single and idx is not None:
        return idx if indices else paths[idx]
    elif not single and idxs is not None:
        return idxs if indices else [paths[i] for i in idxs]
