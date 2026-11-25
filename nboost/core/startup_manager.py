"""
Nboost - core/startup_manager.py
Startup program manager for Module 4.

Reversible by design: "disabling" an entry never deletes it.
  - Registry Run-key entries are moved to a sibling "...\\Run-NboostDisabled"
    key (re-enable = move it back).
  - Startup-folder shortcuts are renamed with a ".nboostdisabled" suffix
    (Windows ignores them while renamed; re-enable = strip the suffix).
"""

from __future__ import annotations
import os
import winreg
from dataclasses import dataclass
from typing import Callable, List

LogFn = Callable[[str], None]

_RUN_ROOTS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
]
_DISABLED_SUFFIX = "-NboostDisabled"

_STARTUP_FOLDERS = lambda: [
    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
    os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
]


@dataclass
class StartupItem:
    source: str        # "registry" | "folder"
    hive_name: str      # "" for folder items
    key_path: str        # "" for folder items
    name: str
    command: str
    enabled: bool
    file_path: str = ""  # populated for folder items


def _hive_name(h) -> str:
    return "HKEY_CURRENT_USER" if h == winreg.HKEY_CURRENT_USER else "HKEY_LOCAL_MACHINE"


def list_startup_items(log: LogFn) -> List[StartupItem]:
    items: List[StartupItem] = []

    for hive, root in _RUN_ROOTS:
        for key_path, enabled in ((root, True), (root + _DISABLED_SUFFIX, False)):
            try:
                with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                    i = 0
                    while True:
                        try:
                            name, data, _vtype = winreg.EnumValue(key, i)
                        except OSError:
                            break
                        i += 1
                        items.append(StartupItem(
                            source="registry", hive_name=_hive_name(hive),
                            key_path=key_path, name=name, command=str(data), enabled=enabled,
                        ))
            except FileNotFoundError:
                continue

    for folder in _STARTUP_FOLDERS():
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            full = os.path.join(folder, fn)
            if not os.path.isfile(full):
                continue
            enabled = not fn.endswith(".nboostdisabled")
            display = fn[: -len(".nboostdisabled")] if not enabled else fn
            items.append(StartupItem(
                source="folder", hive_name="", key_path="", name=display,
                command=full, enabled=enabled, file_path=full,
            ))

    log(f"[Startup] found {len(items)} startup entr{'y' if len(items)==1 else 'ies'}")
    return items


def set_enabled(item: StartupItem, enabled: bool, log: LogFn) -> bool:
    if item.source == "folder":
        return _set_folder_enabled(item, enabled, log)
    return _set_registry_enabled(item, enabled, log)


def _set_registry_enabled(item: StartupItem, enabled: bool, log: LogFn) -> bool:
    hive = winreg.HKEY_CURRENT_USER if item.hive_name == "HKEY_CURRENT_USER" else winreg.HKEY_LOCAL_MACHINE
    base_root = item.key_path.replace(_DISABLED_SUFFIX, "")
    src_key_path = item.key_path
    dst_key_path = base_root if enabled else base_root + _DISABLED_SUFFIX

    if src_key_path == dst_key_path:
        return True  # already in desired state

    try:
        with winreg.CreateKeyEx(hive, dst_key_path, 0, winreg.KEY_SET_VALUE) as dst:
            winreg.SetValueEx(dst, item.name, 0, winreg.REG_SZ, item.command)
        with winreg.OpenKey(hive, src_key_path, 0, winreg.KEY_SET_VALUE) as src:
            winreg.DeleteValue(src, item.name)
        log(f"    [startup] {item.name}: {'enabled' if enabled else 'disabled'}")
        return True
    except OSError as e:
        log(f"    [error] toggling {item.name}: {e}")
        return False


def _set_folder_enabled(item: StartupItem, enabled: bool, log: LogFn) -> bool:
    path = item.file_path
    if enabled and path.endswith(".nboostdisabled"):
        new_path = path[: -len(".nboostdisabled")]
    elif not enabled and not path.endswith(".nboostdisabled"):
        new_path = path + ".nboostdisabled"
    else:
        return True
    try:
        os.rename(path, new_path)
        item.file_path = new_path
        log(f"    [startup] {item.name}: {'enabled' if enabled else 'disabled'}")
        return True
    except OSError as e:
        log(f"    [error] toggling {item.name}: {e}")
        return False
