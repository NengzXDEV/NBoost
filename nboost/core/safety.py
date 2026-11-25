"""
Nboost - core/safety.py
Central safety rules: paths and patterns that must never be touched,
regardless of which module is running. Every cleaner function imports
and checks against this before it deletes, patches, or disables anything.
"""

from __future__ import annotations
import os
import re

# --- Hard-protected directories -------------------------------------------------
# Absolute, case-insensitive prefixes. Anything resolving under these is refused,
# no matter which checkbox was ticked.
PROTECTED_DIR_PREFIXES = [
    os.environ.get("WINDIR", r"C:\Windows"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "SysWOW64"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "WinSxS"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Boot"),
    os.environ.get("ProgramFiles", r"C:\Program Files"),
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    os.environ.get("ProgramData", r"C:\ProgramData") + r"\Microsoft\Windows\Start Menu",
]

# Files that must never be deleted even if a scan walks over them
PROTECTED_FILENAMES = {
    "ntoskrnl.exe", "ntdll.dll", "winload.exe", "bootmgr", "bcd",
    "pagefile.sys", "hiberfil.sys", "swapfile.sys",
    "ntuser.dat", "ntuser.dat.log", "ntuser.ini",
    "sam", "security", "software", "system", "default",  # registry hives (no extension)
}

# Registry key roots that must never be auto-deleted by the broken-entry scanner,
# even if they "look" broken. These are high blast-radius areas.
PROTECTED_REGISTRY_PREFIXES = [
    r"HKEY_LOCAL_MACHINE\SYSTEM",
    r"HKEY_LOCAL_MACHINE\SECURITY",
    r"HKEY_LOCAL_MACHINE\SAM",
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon",
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options",
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography",
    r"HKEY_CLASSES_ROOT\CLSID",  # too large a blast radius for a "broken entry" heuristic
]

# Process/browser profile files that hold saved credentials - cleaner modules must
# skip these filenames outright even inside a cache/temp folder that's otherwise fair game.
CREDENTIAL_FILE_PATTERNS = [
    re.compile(r"^login data$", re.I),          # Chromium saved passwords
    re.compile(r"^login data-journal$", re.I),
    re.compile(r"^cookies$", re.I),              # handled separately/explicitly, not nuked blind
    re.compile(r"^web data$", re.I),             # autofill/cards
    re.compile(r"^key[3-9]?\.db$", re.I),        # Firefox key store
    re.compile(r"^logins\.json$", re.I),         # Firefox saved logins
    re.compile(r"^credentials\.db$", re.I),
    re.compile(r"^\.ldb$", re.I),
]

MIN_FREE_DISK_BYTES_AFTER_CLEAN = 200 * 1024 * 1024  # refuse to push C: below this


def is_protected_path(path: str) -> bool:
    """True if `path` (file or dir) must never be deleted/modified."""
    try:
        norm = os.path.normcase(os.path.abspath(path))
    except Exception:
        return True  # unresolvable path -> refuse, don't guess

    base = os.path.basename(norm)
    if base in PROTECTED_FILENAMES:
        return True

    for prefix in PROTECTED_DIR_PREFIXES:
        if not prefix:
            continue
        p = os.path.normcase(os.path.abspath(prefix))
        if norm == p or norm.startswith(p + os.sep):
            return True

    return False


def is_credential_file(filename: str) -> bool:
    return any(pat.match(filename) for pat in CREDENTIAL_FILE_PATTERNS)


def is_protected_registry_key(full_key_path: str) -> bool:
    norm = full_key_path.strip().upper()
    return any(norm.startswith(p.upper()) for p in PROTECTED_REGISTRY_PREFIXES)


def safe_listdir(path: str):
    """os.scandir wrapper that silently skips what it can't read instead of crashing a scan."""
    try:
        yield from os.scandir(path)
    except (PermissionError, FileNotFoundError, OSError):
        return
