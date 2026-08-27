import six

from resources.lib import backup
from resources.lib import manage
from resources.lib.common import directory
from resources.lib.common import settings
from resources.lib.common import utils

folder_shortcut = utils.get_art("folder-shortcut")
folder_next = utils.get_art("folder-next")


def root_menu():
    directory.add_menu_item(
        title=30007,
        params={"mode": "group"},
        art=utils.get_art("folder"),
        isFolder=True,
    )
    directory.add_menu_item(
        title=30008, params={"mode": "tools"}, art=utils.get_art("tools"), isFolder=True
    )

    return True, "Shortcut Manager", None


def my_groups_menu():
    groups = [g for g in manage.find_defined_groups() if not g.get("parent")]
    if len(groups) > 0:
        for idx, group in enumerate(groups):
            group_name = group["label"]
            group_id = group["id"]

            cm = _create_group_context_items(group_id, idx, len(groups))

            directory.add_menu_item(
                title=six.text_type(group_name),
                params={"mode": "group", "group": group_id},
                info=group.get("info", {}),
                art=group.get("art") or folder_shortcut,
                cm=cm,
                isFolder=True,
            )
    else:
        directory.add_menu_item(
            title=30045,
            art=utils.get_art("alert"),
            isFolder=False,
            props={"specialsort": "bottom"},
        )
    directory.add_menu_item(
        title=30011,
        params={"mode": "manage", "action": "add_group"},
        art=folder_shortcut,
        props={"specialsort": "bottom"},
    )

    return True, utils.get_string(30007), None


def group_menu(group_id):
    _window = utils.get_active_window()

    group_def = manage.get_group_by_id(group_id)
    if not group_def:
        utils.log(
            '"{}" is missing, please repoint the shortcut to fix it.'.format(group_id),
            "error",
        )
        return False, "Shortcut Manager", None

    group_name = group_def["label"]
    paths = group_def["paths"]
    content = group_def.get("content")

    # Migrate any subfolders created before subfolders were tracked as
    # ordered path entries: append a pointer for each so they join the
    # unified ordering (landing below existing items, since new entries
    # are always appended at the end).
    known_children = {p["group"] for p in paths if p.get("target") == "subfolder"}
    migrated = False
    for child in manage.find_defined_groups("shortcut"):
        if child.get("parent") == group_id and child["id"] not in known_children:
            paths.append(_subfolder_pointer(child))
            migrated = True
    if migrated:
        manage.write_path(group_def)

    if len(paths) > 0:
        utils.log(u"Showing group: {}".format(six.text_type(group_name)), "debug")

        for idx, path_def in enumerate(paths):
            cm = []
            if path_def.get("target") == "subfolder":
                child_def = manage.get_group_by_id(path_def["group"])
                if not child_def:
                    # Broken pointer (target group missing) - skip rather
                    # than show a folder that leads nowhere.
                    continue

                if _window == "media":
                    cm = _create_subfolder_context_items(
                        path_def["group"], group_id, path_def["id"], idx, len(paths)
                    )

                directory.add_menu_item(
                    title=child_def.get("label", path_def.get("label", "")),
                    params={"mode": "group", "group": path_def["group"]},
                    art=child_def.get("art") or folder_next,
                    cm=cm,
                    isFolder=True,
                )
            else:
                if _window == "media":
                    cm = _create_path_context_items(group_id, path_def["id"], idx, len(paths))

                directory.add_menu_item(
                    title=path_def["label"],
                    params={"mode": "path", "group": group_id, "path_id": path_def["id"]},
                    info=path_def["file"],
                    art=path_def["file"].get("art", folder_shortcut),
                    cm=cm,
                    isFolder=False,
                )
    else:
        cm = [_add_subfolder_action(group_id)] if _window == "media" else []
        directory.add_menu_item(
            title=30018,
            art=utils.get_art("alert"),
            cm=cm,
            isFolder=False,
            props={"specialsort": "bottom"},
        )

    return True, group_name, content


def _subfolder_pointer(child_def):
    return {
        "id": utils.get_unique_id(child_def["label"]),
        "label": child_def["label"],
        "target": "subfolder",
        "group": child_def["id"],
        "file": {"filetype": "directory", "file": "", "art": {}},
        "version": settings.get_addon_info("version"),
    }


def _on_off_label(string_id, setting_id):
    state = utils.get_string(30169 if settings.get_setting_bool(setting_id) else 30170)
    return "{}: [B]{}[/B]".format(utils.get_string(string_id), state)


def tools_menu():
    color = settings.get_setting_string("ui.color") or "white"
    directory.add_menu_item(
        title="{}: [COLOR {}]{}[/COLOR]".format(utils.get_string(30103), color, color),
        params={"mode": "set_color"},
        art=utils.get_art("folder-settings"),
        isFolder=False,
    )
    directory.add_menu_item(
        title=30042,
        params={"mode": "wipe"},
        art=utils.get_art("remove"),
        isFolder=False,
    )
    directory.add_menu_item(
        title=30100,
        params={"mode": "skindebug"},
        art=utils.get_art("bug-outline"),
        isFolder=False,
    )
    directory.add_menu_item(
        title=_on_off_label(30112, "logging.debug"),
        params={"mode": "setting", "action": "toggle", "setting": "logging.debug"},
        art=utils.get_art("bug-outline"),
        isFolder=False,
    )
    directory.add_menu_item(
        title=_on_off_label(30004, "context.shortcutmanager"),
        params={"mode": "setting", "action": "toggle", "setting": "context.shortcutmanager"},
        art=folder_shortcut,
        isFolder=False,
    )
    directory.add_menu_item(
        title=_on_off_label(30037, "context.advanced"),
        params={"mode": "setting", "action": "toggle", "setting": "context.advanced"},
        art=utils.get_art("tools"),
        isFolder=False,
    )
    directory.add_menu_item(
        title="{}: {}".format(utils.get_string(30067), backup.get_backup_location()),
        params={"mode": "backup", "action": "location"},
        art=utils.get_art("folder"),
        isFolder=False,
    )
    directory.add_menu_item(
        title=30068,
        params={"mode": "backup", "action": "backup"},
        art=utils.get_art("folder-clone"),
        isFolder=False,
    )
    directory.add_menu_item(
        title=30069,
        params={"mode": "backup", "action": "restore"},
        art=utils.get_art("folder-next"),
        isFolder=False,
    )

    return True, utils.get_string(30008), None


def call_path(path_id):
    path_def = manage.get_path_by_id(path_id)
    if not path_def:
        return

    utils.call_builtin("Dialog.Close(busydialog)", 500)
    final_path = ""

    if path_def["target"] == "settings":
        final_path = "Addon.OpenSettings({})".format(
            path_def["file"]["file"]
            .replace("plugin://", "")
            .replace("script://", "")
            .replace("dependency://", "")
            .split("/")[0]
        )
    elif (
        path_def["target"] == "shortcut"
        and path_def["file"]["filetype"] == "file"
        and path_def["content"] != "addons"
    ):
        if path_def["file"]["file"] == "addons://install/":
            final_path = "InstallFromZip"
        elif not path_def["content"] or path_def["content"] == "files":
            if path_def["file"]["file"].startswith("androidapp://sources/apps/"):
                final_path = "StartAndroidActivity({})".format(
                    path_def["file"]["file"].replace("androidapp://sources/apps/", "")
                )
            elif path_def["file"]["file"].startswith("pvr://") or path_def["file"].get("type") in ["video", "movie", "episode", "musicvideo", "music", "song"]:
                final_path = "PlayMedia(\"{}\")".format(path_def["file"]["file"])
            else:
                final_path = "RunPlugin({})".format(path_def["file"]["file"])
        elif (
            all(i in path_def["file"]["file"] for i in ["(", ")"])
            and "://" not in path_def["file"]["file"]
        ):
            final_path = path_def["file"]["file"]
        else:
            final_path = "PlayMedia({})".format(path_def["file"]["file"])
    elif path_def["file"]["filetype"] == "directory" or path_def["content"] == "addons":
        final_path = "ActivateWindow({},{},return)".format(
            path_def.get("window", "Videos"), path_def["file"]["file"]
        )

    if final_path:
        utils.log("Calling path from {} using {}".format(path_id, final_path), "debug")
        utils.call_builtin(final_path)


def _add_subfolder_action(group_id):
    return (
        utils.get_string(30167),
        (
            "RunPlugin("
            "plugin://plugin.program.shortcutmanager/"
            "?mode=manage"
            "&action=add_subfolder"
            "&group={})"
        ).format(group_id),
    )


def _remove_group_action(group_id):
    return (
        utils.get_string(30012),
        (
            "RunPlugin("
            "plugin://plugin.program.shortcutmanager/"
            "?mode=manage"
            "&action=remove_group"
            "&group={})"
        ).format(group_id),
    )


def _remove_path_action(group_id, path_id):
    return (
        utils.get_string(30013),
        (
            "RunPlugin("
            "plugin://plugin.program.shortcutmanager/"
            "?mode=manage"
            "&action=remove_path"
            "&group={}"
            "&path_id={})"
        ).format(group_id, path_id),
    )


def _create_group_context_items(group_id, idx, length):
    cm = [
        (
            utils.get_string(30041),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=edit"
                "&group={})"
            ).format(group_id),
        ),
        (
            utils.get_string(30149) if idx > 0 else utils.get_string(30151),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=shift_group"
                "&target=up"
                "&group={})"
            ).format(group_id),
        ),
        (
            utils.get_string(30150) if idx < length - 1 else utils.get_string(30152),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=shift_group"
                "&target=down"
                "&group={})"
            ).format(group_id),
        ),
        (
            utils.get_string(30119),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=copy"
                "&group={})"
            ).format(group_id),
        ),
        _add_subfolder_action(group_id),
        _remove_group_action(group_id),
    ]

    return cm


def _create_subfolder_context_items(child_group_id, parent_group_id, pointer_id, idx, length):
    cm = [
        (
            utils.get_string(30041),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=edit"
                "&group={})"
            ).format(child_group_id),
        ),
        (
            utils.get_string(30149) if idx > 0 else utils.get_string(30151),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=shift_path"
                "&target=up"
                "&group={}"
                "&path_id={})"
            ).format(parent_group_id, pointer_id),
        ),
        (
            utils.get_string(30150) if idx < length - 1 else utils.get_string(30152),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=shift_path"
                "&target=down"
                "&group={}"
                "&path_id={})"
            ).format(parent_group_id, pointer_id),
        ),
        (
            utils.get_string(30119),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=copy"
                "&group={})"
            ).format(child_group_id),
        ),
        _add_subfolder_action(parent_group_id),
        _remove_group_action(child_group_id),
    ]

    return cm


def _create_path_context_items(group_id, path_id, idx, length):
    cm = [
        (
            utils.get_string(30030),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=edit_path"
                "&group={}"
                "&path_id={})"
            ).format(group_id, path_id),
        ),
        (
            utils.get_string(30014) if idx > 0 else utils.get_string(30086),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=shift_path"
                "&target=up"
                "&group={}"
                "&path_id={})"
            ).format(group_id, path_id),
        ),
        (
            utils.get_string(30015) if idx < length - 1 else utils.get_string(30085),
            (
                "RunPlugin("
                "plugin://plugin.program.shortcutmanager/"
                "?mode=manage"
                "&action=shift_path"
                "&target=down"
                "&group={}"
                "&path_id={})"
            ).format(group_id, path_id),
        ),
        _add_subfolder_action(group_id),
        _remove_path_action(group_id, path_id),
    ]

    return cm


def show_error(id, props=None):
    directory.add_menu_item(
        title=settings.get_localized_string(30137).format(id),
        art=utils.get_art("alert"),
        props=props,
        isFolder=False,
    )

    return True, id, None
