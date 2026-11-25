"""
Nboost - core/registry_tools.py
Broken registry entry scanner for Module 4.

Scope is deliberately narrow and reversible:
  - HKCU\\Software + a handful of well-known HKLM "pointer" locations
    (Run keys, Uninstall entries, App Paths, MUICache, shared DLLs, etc.)
  - An entry is flagged "broken" only when it is a string value that looks
    like a filesystem path/command and that path does not exist on disk.
  - Before any delete, the exact key+value set is exported to a .reg file
    in the user's Documents folder so it's a one-click undo (double-click
    the .reg to restore).
  - Keys under safety.PROTECTED_REGISTRY_PREFIXES are never touched.
"""

from __future__ import annotations
import datetime
import os
import re
import shlex
import winreg
from dataclasses import dataclass
from typing import Callable, List, Tuple

from . import safety

LogFn = Callable[[str], None]

_HIVES = {
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
}

# (hive_name, subkey) roots to scan. Kept small and high-signal on purpose.
_SCAN_ROOTS = [
    ("HKEY_CURRENT_USER", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ("HKEY_CURRENT_USER", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Shared DLLs"),
    ("HKEY_CURRENT_USER", r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"),
]

_PATH_RE = re.compile(r'^(?:"([^"]+)"|([A-Za-z]:\\[^\s"]+(?:\.[A-Za-z0-9]+)?))')


@dataclass
class BrokenEntry:
    hive: str
    key_path: str      # relative to hive, e.g. r"Software\...\Run"
    value_name: str
    value_data: str
    missing_path: str


def _extract_referenced_path(value_data: str) -> str | None:
    """Pull a plausible file path out of a REG_SZ that might be a bare path,
    a quoted command line, or 'path arg1 arg2'."""
    if not value_data or not isinstance(value_data, str):
        return None
    m = _PATH_RE.match(value_data.strip())
    if m:
        return m.group(1) or m.group(2)
    # fall back: first shlex token if it looks like a path
    try:
        parts = shlex.split(value_data, posix=False)
    except ValueError:
        parts = value_data.split()
    if parts and (":\\" in parts[0] or parts[0].startswith("\\\\")):
        return parts[0].strip('"')
    return None


def scan_broken_entries(log: LogFn) -> List[BrokenEntry]:
    found: List[BrokenEntry] = []
    for hive_name, root in _SCAN_ROOTS:
        full_root_path = f"{hive_name}\\{root}"
        if safety.is_protected_registry_key(full_root_path):
            continue
        hive = _HIVES[hive_name]
        try:
            with winreg.OpenKey(hive, root, 0, winreg.KEY_READ) as key:
                found += _scan_key_values(hive_name, key, root)
        except FileNotFoundError:
            continue
        except OSError as e:
            log(f"    [skip] {full_root_path}: {e}")
            continue
    log(f"[Registry] scanned {len(_SCAN_ROOTS)} root keys, found {len(found)} broken reference(s)")
    return found


def _scan_key_values(hive_name: str, key, key_path: str) -> List[BrokenEntry]:
    out = []
    i = 0
    while True:
        try:
            name, data, vtype = winreg.EnumValue(key, i)
        except OSError:
            break
        i += 1
        if vtype != winreg.REG_SZ and vtype != winreg.REG_EXPAND_SZ:
            continue
        ref = _extract_referenced_path(os.path.expandvars(data) if isinstance(data, str) else data)
        if ref and not os.path.exists(ref):
            full_key = f"{hive_name}\\{key_path}"
            if safety.is_protected_registry_key(full_key):
                continue
            out.append(BrokenEntry(hive_name, key_path, name, str(data), ref))
    return out


def _backup_path() -> str:
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    os.makedirs(docs, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(docs, f"Nboost_registry_backup_{stamp}.reg")


def _export_entries(entries: List[BrokenEntry]) -> str:
    """Write a .reg file that restores exactly the values about to be deleted."""
    lines = ["Windows Registry Editor Version 5.00", ""]
    for e in entries:
        lines.append(f"[{e.hive}\\{e.key_path}]")
        escaped = e.value_data.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'"{e.value_name}"="{escaped}"')
        lines.append("")
    path = _backup_path()
    with open(path, "w", encoding="utf-16") as f:
        f.write("\n".join(lines))
    return path


def clean_broken_entries(entries: List[BrokenEntry], log: LogFn) -> int:
    """Deletes the given broken values after writing a restore-capable .reg backup.
    Returns count removed."""
    if not entries:
        return 0
    backup = _export_entries(entries)
    log(f"[Registry] backup written: {backup}")
    removed = 0
    for e in entries:
        full_key = f"{e.hive}\\{e.key_path}"
        if safety.is_protected_registry_key(full_key):
            continue
        hive = _HIVES[e.hive]
        try:
            with winreg.OpenKey(hive, e.key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, e.value_name)
                removed += 1
                log(f"    [clean] {full_key}\\{e.value_name}")
        except OSError as err:
            log(f"    [error] {full_key}\\{e.value_name}: {err}")
    return removed
