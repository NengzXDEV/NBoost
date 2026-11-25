"""
Nboost - core/workers.py
QThread workers so scanning/cleaning never freezes the UI thread.
"""

from __future__ import annotations
from typing import List, Set
from PyQt6.QtCore import QThread, pyqtSignal

from . import jobs
from . import registry_tools as regt
from . import duplicate_finder as dupf
from . import startup_manager as startm


class CleanWorker(QThread):
    log_line = pyqtSignal(str)
    finished_bytes = pyqtSignal(int)
    progress = pyqtSignal(int, int)  # done, total

    def __init__(self, selected_keys: Set[str], dry_run: bool, parent=None):
        super().__init__(parent)
        self.selected_keys = selected_keys
        self.dry_run = dry_run

    def run(self):
        total = jobs.run_selected(
            self.selected_keys, self.dry_run, self.log_line.emit,
            progress_cb=lambda d, t: self.progress.emit(d, t),
        )
        self.finished_bytes.emit(total)


class RegistryScanWorker(QThread):
    log_line = pyqtSignal(str)
    finished_entries = pyqtSignal(list)

    def run(self):
        entries = regt.scan_broken_entries(self.log_line.emit)
        self.finished_entries.emit(entries)


class RegistryCleanWorker(QThread):
    log_line = pyqtSignal(str)
    finished_count = pyqtSignal(int)

    def __init__(self, entries: List, parent=None):
        super().__init__(parent)
        self.entries = entries

    def run(self):
        n = regt.clean_broken_entries(self.entries, self.log_line.emit)
        self.finished_count.emit(n)


class DuplicateScanWorker(QThread):
    log_line = pyqtSignal(str)
    finished_groups = pyqtSignal(list)

    def run(self):
        groups = dupf.find_duplicates(self.log_line.emit)
        self.finished_groups.emit(groups)


class DuplicateCleanWorker(QThread):
    log_line = pyqtSignal(str)
    finished_bytes = pyqtSignal(int)

    def __init__(self, groups: List, parent=None):
        super().__init__(parent)
        self.groups = groups

    def run(self):
        freed = dupf.delete_duplicates(self.groups, self.log_line.emit)
        self.finished_bytes.emit(freed)


class StartupListWorker(QThread):
    log_line = pyqtSignal(str)
    finished_items = pyqtSignal(list)

    def run(self):
        items = startm.list_startup_items(self.log_line.emit)
        self.finished_items.emit(items)
