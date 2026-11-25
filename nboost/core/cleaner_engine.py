"""
Nboost - core/cleaner_engine.py
Modules 1-3: Junk & Temp, Logs & Cache, Browser & App cleaning.

Every job function has the signature:
    job(dry_run: bool, log) -> int
where `log(str)` streams a line to the console widget and the return value
is bytes found (dry_run=True) or bytes actually freed (dry_run=False).

Nothing here deletes a path without first passing safety.is_protected_path(),
and browser/app cleaning never touches a file safety.is_credential_file() flags.
"""

from __future__ import annotations
import ctypes
import os
import shutil
import subprocess
import winreg
from dataclasses import dataclass, field
from typing import Callable, List

from . import safety

LogFn = Callable[[str], None]


def _noop_log(_msg: str) -> None:
    pass


def _dir_size(path: str) -> int:
    total = 0
    for entry in safety.safe_listdir(path):
        try:
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                total += _dir_size(entry.path)
            else:
                total += entry.stat().st_size
        except OSError:
            continue
    return total


def _remove_path(path: str) -> int:
    """Delete a file or directory tree, returning bytes freed. 0 on any refusal/error."""
    if safety.is_protected_path(path):
        return 0
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            size = _dir_size(path)
            shutil.rmtree(path, ignore_errors=True)
            return size if not os.path.exists(path) else 0
        elif os.path.isfile(path) or os.path.islink(path):
            size = os.path.getsize(path) if os.path.isfile(path) else 0
            os.remove(path)
            return size
    except OSError:
        return 0
    return 0


def _purge_dir_contents(path: str, log: LogFn, *, skip_credentials: bool = False,
                         dry_run: bool = False) -> int:
    """Delete everything INSIDE `path` but keep the directory itself. Returns bytes."""
    if not os.path.isdir(path) or safety.is_protected_path(path):
        return 0
    freed = 0
    for entry in safety.safe_listdir(path):
        try:
            if skip_credentials and entry.is_file() and safety.is_credential_file(entry.name):
                continue
            if safety.is_protected_path(entry.path):
                continue
            if dry_run:
                freed += entry.stat().st_size if entry.is_file() else _dir_size(entry.path)
            else:
                freed += _remove_path(entry.path)
        except OSError:
            continue
    if freed:
        log(f"    {'[scan]' if dry_run else '[clean]'} {path}  ->  {_human(freed)}")
    return freed


def _human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


# ---------------------------------------------------------------------------
# Module 1: Junk & Temp Cleaner
# ---------------------------------------------------------------------------

def job_windows_temp(dry_run: bool, log: LogFn = _noop_log) -> int:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    path = os.path.join(windir, "Temp")
    log(f"[Junk] Windows Temp: {path}")
    return _purge_dir_contents(path, log, dry_run=dry_run)


def job_user_temp(dry_run: bool, log: LogFn = _noop_log) -> int:
    path = os.environ.get("TEMP") or os.environ.get("TMP")
    if not path:
        log("[Junk] %temp% not resolvable, skipped.")
        return 0
    log(f"[Junk] User Temp (%temp%): {path}")
    return _purge_dir_contents(path, log, dry_run=dry_run)


def job_prefetch(dry_run: bool, log: LogFn = _noop_log) -> int:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    path = os.path.join(windir, "Prefetch")
    log(f"[Junk] Prefetch: {path}")
    return _purge_dir_contents(path, log, dry_run=dry_run)


def job_crash_dumps(dry_run: bool, log: LogFn = _noop_log) -> int:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    local_app = os.environ.get("LOCALAPPDATA", "")
    freed = 0
    candidates = [
        os.path.join(windir, "Minidump"),
        os.path.join(windir, "LiveKernelReports"),
        os.path.join(local_app, "CrashDumps") if local_app else "",
        os.path.join(windir, "memory.dmp"),  # single file, handled by _remove_path below
    ]
    log("[Junk] Crash dumps:")
    for c in candidates:
        if not c:
            continue
        if c.lower().endswith("memory.dmp"):
            if os.path.isfile(c):
                freed += _remove_path(c) if not dry_run else os.path.getsize(c)
                log(f"    {'[scan]' if dry_run else '[clean]'} {c}")
            continue
        freed += _purge_dir_contents(c, log, dry_run=dry_run)
    return freed


def job_recycle_bin(dry_run: bool, log: LogFn = _noop_log) -> int:
    """Uses SHEmptyRecycleBinW for a real empty; size is estimated via $Recycle.Bin on each drive."""
    log("[Junk] Recycle Bin:")
    total = 0
    for drive_letter in "CDEFGH":
        bin_path = f"{drive_letter}:\\$Recycle.Bin"
        if os.path.isdir(bin_path):
            total += _dir_size(bin_path)
    log(f"    {'[scan]' if dry_run else '[clean]'} all drives -> {_human(total)}")
    if not dry_run and total > 0:
        SHERB_NOCONFIRMATION, SHERB_NOPROGRESSUI, SHERB_NOSOUND = 0x00000001, 0x00000002, 0x00000004
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        except Exception as e:  # pragma: no cover - platform-only
            log(f"    [error] SHEmptyRecycleBinW failed: {e}")
            return 0
    return total


# ---------------------------------------------------------------------------
# Module 2: Log & Cache Cleaner
# ---------------------------------------------------------------------------

_EVENT_LOG_CHANNELS = ["Application", "System", "Security", "Setup"]


def job_event_logs(dry_run: bool, log: LogFn = _noop_log) -> int:
    """Clears Windows Event Log channels via `wevtutil`. Size is estimated from .evtx files."""
    log("[Logs] Windows Event Logs:")
    windir = os.environ.get("WINDIR", r"C:\Windows")
    evtx_dir = os.path.join(windir, "System32", "winevt", "Logs")
    total = _dir_size(evtx_dir) if os.path.isdir(evtx_dir) else 0
    log(f"    {'[scan]' if dry_run else '[clean]'} {evtx_dir} -> {_human(total)}")
    if dry_run:
        return total
    cleared_any = False
    for channel in _EVENT_LOG_CHANNELS:
        try:
            subprocess.run(["wevtutil.exe", "cl", channel], check=False,
                            capture_output=True, timeout=15)
            cleared_any = True
        except Exception as e:  # pragma: no cover
            log(f"    [error] wevtutil cl {channel}: {e}")
    return total if cleared_any else 0


def job_windows_update_cache(dry_run: bool, log: LogFn = _noop_log) -> int:
    """SoftwareDistribution\\Download - must stop wuauserv first or files are locked."""
    windir = os.environ.get("WINDIR", r"C:\Windows")
    path = os.path.join(windir, "SoftwareDistribution", "Download")
    log(f"[Logs] Windows Update cache: {path}")
    if dry_run:
        return _dir_size(path)
    stopped = _service_stop("wuauserv")
    try:
        freed = _purge_dir_contents(path, log, dry_run=False)
    finally:
        if stopped:
            _service_start("wuauserv")
    return freed


def job_thumbnail_icon_cache(dry_run: bool, log: LogFn = _noop_log) -> int:
    local_app = os.environ.get("LOCALAPPDATA", "")
    cache_dir = os.path.join(local_app, "Microsoft", "Windows", "Explorer")
    log(f"[Logs] Thumbnail/Icon cache: {cache_dir}")
    freed = 0
    if os.path.isdir(cache_dir):
        for entry in safety.safe_listdir(cache_dir):
            name = entry.name.lower()
            if name.startswith("thumbcache_") or name.startswith("iconcache_"):
                size = entry.stat().st_size if entry.is_file() else 0
                if dry_run:
                    freed += size
                else:
                    freed += _remove_path(entry.path)
    if not dry_run and freed:
        # Explorer rebuilds these on demand; nudge it to drop in-memory handles.
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True)
        subprocess.Popen(["explorer.exe"])
    log(f"    {'[scan]' if dry_run else '[clean]'} -> {_human(freed)}")
    return freed


def job_dns_cache(dry_run: bool, log: LogFn = _noop_log) -> int:
    log("[Logs] DNS resolver cache: ipconfig /flushdns")
    if dry_run:
        return 0  # no meaningful disk size, this is RAM-resident cache
    try:
        subprocess.run(["ipconfig", "/flushdns"], check=False, capture_output=True, timeout=10)
    except Exception as e:  # pragma: no cover
        log(f"    [error] flushdns: {e}")
    return 0


def _service_stop(name: str) -> bool:
    try:
        r = subprocess.run(["sc", "stop", name], capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def _service_start(name: str) -> bool:
    try:
        r = subprocess.run(["sc", "start", name], capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Module 3: Browser & App Cleaner (cache/cookies/temp only - never credentials)
# ---------------------------------------------------------------------------

@dataclass
class AppCacheTarget:
    name: str
    dirs: List[str] = field(default_factory=list)
    purge_credential_safe: bool = True  # if True, skip_credentials is enforced


def _chromium_paths(base_profile_root: str) -> List[str]:
    """Given e.g. %LOCALAPPDATA%/Google/Chrome/User Data, return cache-ish subpaths
    across Default + Profile N, deliberately NOT including 'Login Data' etc."""
    out = []
    if not os.path.isdir(base_profile_root):
        return out
    for entry in safety.safe_listdir(base_profile_root):
        if not entry.is_dir():
            continue
        if entry.name == "Default" or entry.name.startswith("Profile "):
            profile = entry.path
            out += [
                os.path.join(profile, "Cache"),
                os.path.join(profile, "Code Cache"),
                os.path.join(profile, "GPUCache"),
                os.path.join(profile, "Service Worker", "CacheStorage"),
                os.path.join(profile, "Cookies"),           # file; deleted via skip-credentials filter below
            ]
    return out


def _get_app_targets() -> List[AppCacheTarget]:
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    targets = []

    chrome_root = os.path.join(local, "Google", "Chrome", "User Data")
    targets.append(AppCacheTarget("Chrome", _chromium_paths(chrome_root)))

    edge_root = os.path.join(local, "Microsoft", "Edge", "User Data")
    targets.append(AppCacheTarget("Edge", _chromium_paths(edge_root)))

    discord_root = os.path.join(roaming, "discord")
    targets.append(AppCacheTarget("Discord", [
        os.path.join(discord_root, "Cache"),
        os.path.join(discord_root, "Code Cache"),
        os.path.join(discord_root, "GPUCache"),
        os.path.join(discord_root, "Service Worker", "CacheStorage"),
    ]))

    steam_root = _find_steam_root()
    steam_dirs = []
    if steam_root:
        steam_dirs += [
            os.path.join(steam_root, "appcache", "httpcache"),
            os.path.join(steam_root, "depotcache"),
            os.path.join(steam_root, "logs"),
        ]
        # Shader/web caches live here too; htmlcache holds no saved passwords (those are
        # in loginusers.vdf / ssfn files, which we never touch).
        steam_dirs.append(os.path.join(steam_root, "config", "htmlcache"))
    targets.append(AppCacheTarget("Steam", steam_dirs))

    return targets


def _find_steam_root() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            path, _ = winreg.QueryValueEx(key, "SteamPath")
            return path.replace("/", "\\")
    except OSError:
        for guess in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
            if os.path.isdir(guess):
                return guess
    return None


def job_browser_app_cache(dry_run: bool, log: LogFn = _noop_log,
                           selected_apps: List[str] | None = None) -> int:
    """selected_apps filters to a subset of {"Chrome","Edge","Discord","Steam"}; None = all."""
    total = 0
    for target in _get_app_targets():
        if selected_apps is not None and target.name not in selected_apps:
            continue
        if not target.dirs:
            continue
        log(f"[Apps] {target.name}:")
        for d in target.dirs:
            if os.path.isfile(d):
                # e.g. a lone Cookies file - purge contents-of-file not possible, just
                # size/remove it directly, still gated by credential-file filter.
                if safety.is_credential_file(os.path.basename(d)):
                    continue
                if safety.is_protected_path(d):
                    continue
                try:
                    size = os.path.getsize(d)
                except OSError:
                    size = 0
                if dry_run:
                    total += size
                else:
                    total += _remove_path(d)
                log(f"    {'[scan]' if dry_run else '[clean]'} {d} -> {_human(size)}")
            else:
                total += _purge_dir_contents(d, log, skip_credentials=True, dry_run=dry_run)
    return total
