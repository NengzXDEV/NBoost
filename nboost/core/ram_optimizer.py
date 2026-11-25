"""
Nboost - core/ram_optimizer.py
Standby-list purge + per-process working-set trim.

This is the same technique RAMMap / EmptyStandbyList.exe use: it enables
SeProfileSingleProcessPrivilege and SeIncreaseQuotaPrivilege on our own token,
then calls ntdll!NtSetSystemInformation(SystemMemoryListInformation, ...) to
tell the memory manager to purge the standby list (cached/mapped file pages
that are reclaimable) and optionally the modified/priority-0 lists. It does
NOT touch pagefile contents or dirty data - Windows won't let you purge those
without flushing first, which this call already respects.
"""

from __future__ import annotations
import ctypes
import ctypes.wintypes as wt
from typing import Callable

LogFn = Callable[[str], None]

# --- Win32 privilege plumbing -----------------------------------------------

advapi32 = ctypes.windll.advapi32
kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll
psapi = ctypes.windll.psapi

TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wt.DWORD), ("HighPart", wt.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wt.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wt.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


def _enable_privilege(name: str) -> bool:
    h_token = wt.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(),
                                      TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                                      ctypes.byref(h_token)):
        return False
    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            return False
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0] = LUID_AND_ATTRIBUTES(luid, SE_PRIVILEGE_ENABLED)
        advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None)
        return ctypes.get_last_error() == 0 or kernel32.GetLastError() == 0
    finally:
        kernel32.CloseHandle(h_token)


# --- NtSetSystemInformation / SystemMemoryListInformation -------------------

SystemMemoryListInformation = 0x50

# MEMORY_LIST_COMMAND values (winternl / public from RAMMap source & MSDN leaks)
MemoryPurgeStandbyList = 4         # evict reclaimable standby (cached file) pages
MemoryPurgeLowPriorityStandbyList = 5
MemoryEmptyWorkingSets = 2         # trim every process's working set


def purge_standby_list(log: LogFn) -> bool:
    """Defeats: stale 'available RAM looks low because of cache' complaints by
    forcing Windows to drop reclaimable standby pages immediately.
    Caught by: nothing security-relevant - this is a documented admin operation,
    gated purely by SeProfileSingleProcessPrivilege, which we request explicitly."""
    if not _enable_privilege("SeProfileSingleProcessPrivilege"):
        log("    [error] could not enable SeProfileSingleProcessPrivilege (run as Administrator)")
        return False
    cmd = ctypes.c_ulong(MemoryPurgeStandbyList)
    status = ntdll.NtSetSystemInformation(SystemMemoryListInformation,
                                           ctypes.byref(cmd), ctypes.sizeof(cmd))
    if status != 0:
        log(f"    [error] NtSetSystemInformation(PurgeStandbyList) status=0x{status & 0xffffffff:08x}")
        return False
    log("    standby list purged")
    return True


def trim_all_working_sets(log: LogFn) -> bool:
    """System-wide EmptyWorkingSets request: tells every process to give back
    physical pages it isn't actively using back to the memory manager."""
    if not _enable_privilege("SeProfileSingleProcessPrivilege"):
        return False
    if not _enable_privilege("SeIncreaseQuotaPrivilege"):
        pass  # not fatal, some SKUs don't require it for the system-wide call
    cmd = ctypes.c_ulong(MemoryEmptyWorkingSets)
    status = ntdll.NtSetSystemInformation(SystemMemoryListInformation,
                                           ctypes.byref(cmd), ctypes.sizeof(cmd))
    if status != 0:
        log(f"    [error] NtSetSystemInformation(EmptyWorkingSets) status=0x{status & 0xffffffff:08x}")
        return False
    log("    working sets trimmed system-wide")
    return True


def free_standby_ram(log: LogFn) -> int:
    """High-level entry point used by the UI. Returns an estimate of bytes
    reclaimed (delta in available physical memory before/after)."""
    import psutil
    before = psutil.virtual_memory().available
    log("[RAM] Purging standby list and trimming working sets...")
    ok1 = purge_standby_list(log)
    ok2 = trim_all_working_sets(log)
    after = psutil.virtual_memory().available
    delta = max(0, after - before)
    if ok1 or ok2:
        log(f"    reclaimed ~{delta / (1024**2):.0f} MB of available RAM")
    return delta
