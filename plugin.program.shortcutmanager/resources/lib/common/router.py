import traceback

try:
    from urllib.parse import parse_qsl
except ImportError:
    from urlparse import parse_qsl

from resources.lib import add
from resources.lib import backup
from resources.lib import edit
from resources.lib import menu
from resources.lib.common import directory
from resources.lib.common import settings
from resources.lib.common import utils


def _log_params(_params):
    msg = "[{}]"

    params = dict(parse_qsl(_params))
    if params:
        msg = msg.format("][".join([" {}: {} ".format(p, params[p]) for p in params]))
    else:
        msg = msg.format(" root ")
    utils.log(msg, "info")

    return params


def dispatch(_handle, _params):
    params = _log_params(_params)
    category = "Shortcut Manager"
    is_dir = False
    is_type = ""

    utils.ensure_addon_data()

    mode = params.get("mode", "")
    action = params.get("action", "")
    group = params.get("group", "")
    path_id = params.get("path_id", "")
    target = params.get("target", "")

    if not mode:
        is_dir, category, is_type = menu.root_menu()
    elif mode == "manage":
        if action == "add_group":
            if add.add_group():
                utils.update_container(True)
        elif action == "add_subfolder" and group:
            add.add_subfolder(group)
        elif action == "shift_path" and group and path_id and target:
            edit.shift_path(group, path_id, target)
        elif action == "shift_group" and group and target:
            edit.shift_group(group, target)
        elif action == "edit":
            edit.edit_dialog(group, type="group")
        elif action == "edit_path":
            edit.edit_dialog(group, path_id)
        elif action == "remove_group" and group:
            edit.remove_group(group)
        elif action == "remove_path" and group and path_id:
            edit.remove_path(group, path_id)
        elif action == "copy":
            if group:
                add.copy_group(group)
    elif mode == "group":
        if not group:
            is_dir, category, is_type = menu.my_groups_menu()
        else:
            is_dir, category, is_type = menu.group_menu(group)
    elif mode == "path":
        try:
            if path_id:
                menu.call_path(path_id)
        except Exception as e:
            utils.log(traceback.format_exc(), "error")
            is_dir, category, is_type = menu.show_error(path_id)
    elif mode == "tools":
        is_dir, category, is_type = menu.tools_menu()
    elif mode == "skindebug":
        utils.call_builtin("Skin.ToggleDebug")
    elif mode == "wipe":
        if utils.wipe():
            utils.ensure_addon_data()
            utils.update_container(True)
    elif mode == "set_color":
        utils.set_color(setting=True)
        utils.update_container()
    elif mode == "setting":
        setting_id = params.get("setting", "")
        if action == "toggle" and setting_id:
            settings.set_setting_bool(setting_id, not settings.get_setting_bool(setting_id))
            utils.update_container()
    elif mode == "backup" and action:
        if action == "location":
            backup.location()
            utils.update_container()
        elif action == "backup":
            backup.backup()
        elif action == "restore":
            backup.restore()
            utils.update_container(True)

    if is_dir:
        directory.finish_directory(
            _handle, category, is_type if is_type not in [None, "none", ""] else ""
        )
