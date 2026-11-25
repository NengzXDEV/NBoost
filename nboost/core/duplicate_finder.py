"""
Nboost - core/duplicate_finder.py
Large duplicate file detector for Module 4.

Algorithm (keeps it to O(n log n) overall):
  1. Walk target roots, bucket files by size (files with a unique size can't
     have a duplicate, so they're discarded immediately - this is the main
     pruning step and is why this stays fast on big trees).
  2. Within each size bucket (len > 1), hash just the first 64 KB of each
     file (cheap partial hash) and re-bucket.
  3. Within each partial-hash bucket (len > 1), hash the full file (xxhash-
     speed via hashlib.blake2b) to confirm true duplicates.
  4. Group confirmed duplicates; caller keeps the oldest/first and may
     delete the rest.

Only files >= min_size_bytes are considered "large" (default 25 MB) to keep
this useful for disk-space recovery rather than flagging every duplicate
config file on the system.
"""

from __future__ import annotations
import hashlib
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List

from . import safety

LogFn = Callable[[str], None]

DEFAULT_ROOTS = lambda: [
    os.path.join(os.path.expanduser("~"), "Downloads"),
    os.path.join(os.path.expanduser("~"), "Documents"),
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.path.expanduser("~"), "Videos"),
    os.path.join(os.path.expanduser("~"), "Pictures"),
]

_PARTIAL_READ = 64 * 1024


@dataclass
class DuplicateGroup:
    size: int
    paths: List[str]

    @property
    def reclaimable(self) -> int:
        return self.size * (len(self.paths) - 1)


def _walk_files(roots: List[str]):
    for root in roots:
        if not os.path.isdir(root) or safety.is_protected_path(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if safety.is_protected_path(dirpath):
                dirnames[:] = []
                continue
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                yield full, st.st_size


def _partial_hash(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.blake2b(f.read(_PARTIAL_READ), digest_size=16).hexdigest()
    except OSError:
        return None


def _full_hash(path: str) -> str | None:
    h = hashlib.blake2b(digest_size=20)
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def find_duplicates(log: LogFn, roots: List[str] | None = None,
                     min_size_bytes: int = 25 * 1024 * 1024) -> List[DuplicateGroup]:
    roots = roots or DEFAULT_ROOTS()
    log(f"[Duplicates] scanning {len(roots)} folder(s) for files >= {min_size_bytes // (1024*1024)} MB")

    by_size: Dict[int, List[str]] = defaultdict(list)
    scanned = 0
    for path, size in _walk_files(roots):
        if size < min_size_bytes:
            continue
        by_size[size].append(path)
        scanned += 1
    log(f"    {scanned} large file(s) found, {sum(1 for v in by_size.values() if len(v) > 1)} size-collision bucket(s)")

    by_partial: Dict[str, List[str]] = defaultdict(list)
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for p in paths:
            ph = _partial_hash(p)
            if ph:
                by_partial[f"{size}:{ph}"].append(p)

    groups: List[DuplicateGroup] = []
    for key, paths in by_partial.items():
        if len(paths) < 2:
            continue
        by_full: Dict[str, List[str]] = defaultdict(list)
        for p in paths:
            fh = _full_hash(p)
            if fh:
                by_full[fh].append(p)
        for fh, confirmed in by_full.items():
            if len(confirmed) >= 2:
                size = os.path.getsize(confirmed[0])
                groups.append(DuplicateGroup(size=size, paths=confirmed))

    total_reclaimable = sum(g.reclaimable for g in groups)
    log(f"    {len(groups)} confirmed duplicate group(s), "
        f"{total_reclaimable / (1024**2):.1f} MB reclaimable if trimmed to one copy each")
    return groups


def delete_duplicates(groups: List[DuplicateGroup], log: LogFn, keep: str = "first") -> int:
    """Deletes every copy in each group except the one to keep. Returns bytes freed."""
    freed = 0
    for g in groups:
        ordered = sorted(g.paths, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
        survivor = ordered[0] if keep == "first" else ordered[-1]
        for p in g.paths:
            if p == survivor or safety.is_protected_path(p):
                continue
            try:
                size = os.path.getsize(p)
                os.remove(p)
                freed += size
                log(f"    [clean] removed duplicate {p}")
            except OSError as e:
                log(f"    [error] {p}: {e}")
    return freed
