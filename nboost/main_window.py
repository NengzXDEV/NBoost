"""
Nboost - main_window.py
Assembles the sidebar, stacked pages (Dashboard / Cleaner / Advanced / About),
the live gauges, and the shared console at the bottom.
"""

from __future__ import annotations
import ctypes
import os
import sys

from PyQt6.QtCore import Qt, QTimer, QUrl, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QCheckBox, QButtonGroup, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QProgressBar,
    QAbstractItemView, QSizePolicy, QGraphicsDropShadowEffect,
)

from .core.system_monitor import SystemMonitor
from .core import jobs
from .core.paths import resource_path
from .core.workers import (
    CleanWorker, RegistryScanWorker, RegistryCleanWorker,
    DuplicateScanWorker, DuplicateCleanWorker, StartupListWorker,
)
from .core import startup_manager as startm
from .widgets.gauge_widget import GaugeWidget
from .widgets.console_widget import ConsoleWidget

DEV_TELEGRAM_URL = "https://t.me/nengzx_fernandez"
DEV_GITHUB_URL = "https://github.com/NengzXGODZ"


def _human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class GlassCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("glassCard")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nboost - System Cleaner & Optimizer")
        self.resize(1180, 760)
        self.setMinimumSize(1020, 660)
        self.setWindowIcon(QIcon(resource_path("nboost.png")))

        self._checkboxes: dict[str, QCheckBox] = {}
        self._last_scan_entries = []   # registry
        self._last_dup_groups = []     # duplicates
        self._startup_items = []

        self._build_ui()
        self._start_monitor()
        self._refresh_disk_free()

        if not _is_admin():
            self.console.append_line(
                "[warn] Not running as Administrator - Event Logs, Update cache, RAM "
                "standby purge and some registry keys will be skipped or partially fail."
            )

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("centralRoot")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_sidebar())

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(22, 20, 22, 18)
        right_l.setSpacing(14)

        self.stack = QStackedWidget()
        self.page_dashboard = self._build_dashboard_page()
        self.page_cleaner = self._build_cleaner_page()
        self.page_advanced = self._build_advanced_page()
        self.page_about = self._build_about_page()
        for p in (self.page_dashboard, self.page_cleaner, self.page_advanced, self.page_about):
            self.stack.addWidget(p)
        right_l.addWidget(self.stack, stretch=3)

        console_card = GlassCard()
        console_l = QVBoxLayout(console_card)
        console_l.setContentsMargins(14, 12, 14, 12)
        header = QHBoxLayout()
        title = QLabel("LIVE CLEANING LOG")
        title.setObjectName("sectionTitle")
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondaryBtn")
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(lambda: self.console.clear_log())
        header.addWidget(title)
        header.addStretch()
        header.addWidget(clear_btn)
        console_l.addLayout(header)
        self.console = ConsoleWidget()
        self.console.setMinimumHeight(170)
        console_l.addWidget(self.console)
        right_l.addWidget(console_card, stretch=2)

        outer.addWidget(right, stretch=1)

    def _build_sidebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("sidebar")
        bar.setFixedWidth(220)
        l = QVBoxLayout(bar)
        l.setContentsMargins(0, 0, 0, 16)
        l.setSpacing(2)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(20, 16, 20, 0)
        logo_lbl = QLabel()
        pix = QPixmap(resource_path("nboost.png"))
        if not pix.isNull():
            logo_lbl.setPixmap(pix.scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
        brand = QLabel("NBOOST")
        brand.setObjectName("brandLabel")
        brand.setContentsMargins(0, 0, 0, 0)
        logo_row.addWidget(logo_lbl)
        logo_row.addWidget(brand)
        logo_row.addStretch()
        l.addLayout(logo_row)
        sub = QLabel("system cleaner & optimizer")
        sub.setObjectName("brandSubLabel")
        sub.setContentsMargins(20, 2, 20, 16)
        l.addWidget(sub)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        nav_defs = [
            ("  Dashboard", "dashboard.svg", 0),
            ("  Cleaner", "cleaner.svg", 1),
            ("  Advanced", "gear.svg", 2),
            ("  About", "info.svg", 3),
        ]
        for text, icon, idx in nav_defs:
            btn = QPushButton(text)
            btn.setObjectName("navButton")
            btn.setIcon(QIcon(resource_path("icons", icon)))
            btn.setIconSize(QSize(18, 18))
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.clicked.connect(lambda _=False, i=idx: self.stack.setCurrentIndex(i))
            self.nav_group.addButton(btn, idx)
            l.addWidget(btn)

        l.addStretch()

        dev_row = QHBoxLayout()
        dev_row.setContentsMargins(20, 0, 20, 4)
        dev_label = QLabel("DEVELOPER")
        dev_label.setObjectName("brandSubLabel")
        l.addWidget(dev_label)
        dev_row.addWidget(self._icon_link_button("telegram.svg", DEV_TELEGRAM_URL,
                                                   "Telegram: @nengzx_fernandez"))
        dev_row.addWidget(self._icon_link_button("github.svg", DEV_GITHUB_URL,
                                                   "GitHub: NengzXGODZ"))
        dev_row.addStretch()
        l.addLayout(dev_row)

        admin_lbl = QLabel("Administrator" if _is_admin() else "Standard user")
        admin_lbl.setObjectName("brandSubLabel")
        admin_lbl.setStyleSheet(f"color: {'#00f5d4' if _is_admin() else '#ff9d4d'};")
        admin_lbl.setContentsMargins(20, 6, 0, 8)
        l.addWidget(admin_lbl)
        return bar

    def _icon_link_button(self, svg_name: str, url: str, tooltip: str) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(QIcon(resource_path("icons", svg_name)))
        btn.setIconSize(btn.iconSize() * 1.3)
        btn.setFixedSize(30, 30)
        btn.setToolTip(tooltip)
        btn.setObjectName("secondaryBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        return btn

    # ------------------------------------------------------------ Dashboard
    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(16)

        header = QVBoxLayout()
        t = QLabel("Dashboard")
        t.setObjectName("pageTitle")
        s = QLabel("Live system health and one-click boost")
        s.setObjectName("pageSubtitle")
        header.addWidget(t)
        header.addWidget(s)
        l.addLayout(header)

        gauges_card = GlassCard()
        gl = QHBoxLayout(gauges_card)
        gl.setContentsMargins(24, 24, 24, 24)
        gl.setSpacing(24)
        self.gauge_cpu = GaugeWidget("CPU", "#00f5d4")
        self.gauge_ram = GaugeWidget("RAM", "#ff2fb0")
        self.gauge_disk = GaugeWidget("DISK (C:)", "#7a3bff")
        for g in (self.gauge_cpu, self.gauge_ram, self.gauge_disk):
            gl.addWidget(g)
        l.addWidget(gauges_card)

        actions_card = GlassCard()
        al = QHBoxLayout(actions_card)
        al.setContentsMargins(24, 22, 24, 22)
        al.setSpacing(16)

        self.lbl_recoverable = QLabel("Recoverable: — ")
        self.lbl_recoverable.setObjectName("statValue")
        info_box = QVBoxLayout()
        info_lbl = QLabel("ESTIMATED RECOVERABLE SPACE")
        info_lbl.setObjectName("statLabel")
        info_box.addWidget(info_lbl)
        info_box.addWidget(self.lbl_recoverable)
        al.addLayout(info_box)
        al.addStretch()

        scan_btn = QPushButton("  Scan")
        scan_btn.setObjectName("primaryBtn")
        scan_btn.setIcon(QIcon(resource_path("icons", "search-dark.svg")))
        scan_btn.setIconSize(QSize(16, 16))
        scan_btn.clicked.connect(self._on_scan_clicked)
        self.boost_btn = QPushButton("  ONE-CLICK BOOST")
        self.boost_btn.setObjectName("boostBtn")
        self.boost_btn.setIcon(QIcon(resource_path("icons", "rocket-light.svg")))
        self.boost_btn.setIconSize(QSize(18, 18))
        self.boost_btn.clicked.connect(self._on_boost_clicked)
        al.addWidget(scan_btn)
        al.addWidget(self.boost_btn)
        l.addWidget(actions_card)

        self.dash_progress = QProgressBar()
        self.dash_progress.setRange(0, 100)
        self.dash_progress.setValue(0)
        self.dash_progress.setVisible(False)
        l.addWidget(self.dash_progress)

        l.addStretch()
        self._setup_boost_glow()
        return page

    def _setup_boost_glow(self):
        """Pulsing neon glow on the Boost button - purely cosmetic, animates blur radius."""
        glow = QGraphicsDropShadowEffect(self)
        glow.setColor(Qt.GlobalColor.magenta)
        glow.setOffset(0, 0)
        glow.setBlurRadius(18)
        self.boost_btn.setGraphicsEffect(glow)
        self._boost_glow = glow
        self._glow_anim = QPropertyAnimation(glow, b"blurRadius", self)
        self._glow_anim.setStartValue(14)
        self._glow_anim.setEndValue(34)
        self._glow_anim.setDuration(1100)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        # ping-pong forever: each leg is a one-shot animation, re-armed on finish
        self._glow_anim.finished.connect(self._reverse_glow)
        self._glow_anim.start()

    def _reverse_glow(self):
        s, e = self._glow_anim.startValue(), self._glow_anim.endValue()
        self._glow_anim.setStartValue(e)
        self._glow_anim.setEndValue(s)
        self._glow_anim.start()

    # -------------------------------------------------------------- Cleaner
    def _build_cleaner_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        header = QVBoxLayout()
        t = QLabel("Cleaner")
        t.setObjectName("pageTitle")
        s = QLabel("Pick what to scan and clean - Junk & Temp, Logs & Cache, Browser & App")
        s.setObjectName("pageSubtitle")
        header.addWidget(t)
        header.addWidget(s)
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_l = QVBoxLayout(inner)
        inner_l.setSpacing(14)

        modules = ["Junk & Temp Cleaner", "Log & Cache Cleaner", "Browser & App Cleaner"]
        for mod_name in modules:
            card = GlassCard()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 16, 20, 16)
            title = QLabel(mod_name.upper())
            title.setObjectName("sectionTitle")
            cl.addWidget(title)
            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            row = 0
            col = 0
            for spec in jobs.JOB_SPECS:
                if spec.module != mod_name:
                    continue
                cb = QCheckBox(spec.label)
                cb.setChecked(spec.default_checked)
                self._checkboxes[spec.key] = cb
                grid.addWidget(cb, row, col)
                col += 1
                if col >= 2:
                    col = 0
                    row += 1
            cl.addLayout(grid)
            inner_l.addWidget(card)

        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select all")
        select_all_btn.setObjectName("secondaryBtn")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        select_none_btn = QPushButton("Select none")
        select_none_btn.setObjectName("secondaryBtn")
        select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        scan_btn = QPushButton("  Scan selected")
        scan_btn.setObjectName("primaryBtn")
        scan_btn.setIcon(QIcon(resource_path("icons", "search-dark.svg")))
        scan_btn.setIconSize(QSize(16, 16))
        scan_btn.clicked.connect(self._on_scan_clicked)
        clean_btn = QPushButton("  Clean selected")
        clean_btn.setObjectName("primaryBtn")
        clean_btn.setIcon(QIcon(resource_path("icons", "broom-dark.svg")))
        clean_btn.setIconSize(QSize(16, 16))
        clean_btn.clicked.connect(self._on_clean_selected_clicked)
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(select_none_btn)
        btn_row.addStretch()
        btn_row.addWidget(scan_btn)
        btn_row.addWidget(clean_btn)
        outer.addLayout(btn_row)
        return page

    def _set_all_checked(self, state: bool):
        for cb in self._checkboxes.values():
            cb.setChecked(state)

    def _selected_keys(self) -> set[str]:
        return {k for k, cb in self._checkboxes.items() if cb.isChecked()}

    # ------------------------------------------------------------- Advanced
    def _build_advanced_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        header = QVBoxLayout()
        t = QLabel("Advanced Optimization")
        t.setObjectName("pageTitle")
        s = QLabel("Registry cleanup, duplicate files, startup programs, RAM")
        s.setObjectName("pageSubtitle")
        header.addWidget(t)
        header.addWidget(s)
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_l = QVBoxLayout(inner)
        inner_l.setSpacing(14)

        # RAM card
        ram_card = GlassCard()
        rl = QVBoxLayout(ram_card)
        rl.setContentsMargins(20, 16, 20, 16)
        rl.addWidget(self._section_title("STANDBY RAM CACHE"))
        rrow = QHBoxLayout()
        rrow.addWidget(QLabel("Purges the reclaimable standby list and trims working sets "
                               "system-wide (same mechanism as RAMMap's Empty Standby List)."))
        ram_btn = QPushButton("Free RAM now")
        ram_btn.setObjectName("primaryBtn")
        ram_btn.clicked.connect(self._on_free_ram_clicked)
        rrow.addWidget(ram_btn)
        rl.addLayout(rrow)
        inner_l.addWidget(ram_card)

        # Registry card
        reg_card = GlassCard()
        rgl = QVBoxLayout(reg_card)
        rgl.setContentsMargins(20, 16, 20, 16)
        rgl.addWidget(self._section_title("BROKEN REGISTRY ENTRIES"))
        self.reg_table = QTableWidget(0, 3)
        self.reg_table.setHorizontalHeaderLabels(["Key", "Value", "Missing target"])
        self.reg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.reg_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.reg_table.setMaximumHeight(160)
        rgl.addWidget(self.reg_table)
        rg_btns = QHBoxLayout()
        reg_scan_btn = QPushButton("Scan registry")
        reg_scan_btn.setObjectName("secondaryBtn")
        reg_scan_btn.clicked.connect(self._on_registry_scan_clicked)
        self.reg_clean_btn = QPushButton("Remove found entries (backs up first)")
        self.reg_clean_btn.setObjectName("dangerBtn")
        self.reg_clean_btn.clicked.connect(self._on_registry_clean_clicked)
        self.reg_clean_btn.setEnabled(False)
        rg_btns.addWidget(reg_scan_btn)
        rg_btns.addWidget(self.reg_clean_btn)
        rg_btns.addStretch()
        rgl.addLayout(rg_btns)
        inner_l.addWidget(reg_card)

        # Duplicates card
        dup_card = GlassCard()
        dl = QVBoxLayout(dup_card)
        dl.setContentsMargins(20, 16, 20, 16)
        dl.addWidget(self._section_title("LARGE DUPLICATE FILES"))
        dl.addWidget(QLabel("Scans Downloads / Documents / Desktop / Pictures / Videos for files ≥ 25 MB."))
        self.dup_table = QTableWidget(0, 3)
        self.dup_table.setHorizontalHeaderLabels(["Size", "Copies", "Reclaimable"])
        self.dup_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dup_table.setMaximumHeight(160)
        dl.addWidget(self.dup_table)
        d_btns = QHBoxLayout()
        dup_scan_btn = QPushButton("Scan for duplicates")
        dup_scan_btn.setObjectName("secondaryBtn")
        dup_scan_btn.clicked.connect(self._on_duplicate_scan_clicked)
        self.dup_clean_btn = QPushButton("Delete extra copies (keep oldest)")
        self.dup_clean_btn.setObjectName("dangerBtn")
        self.dup_clean_btn.clicked.connect(self._on_duplicate_clean_clicked)
        self.dup_clean_btn.setEnabled(False)
        d_btns.addWidget(dup_scan_btn)
        d_btns.addWidget(self.dup_clean_btn)
        d_btns.addStretch()
        dl.addLayout(d_btns)
        inner_l.addWidget(dup_card)

        # Startup card
        su_card = GlassCard()
        sul = QVBoxLayout(su_card)
        sul.setContentsMargins(20, 16, 20, 16)
        sul.addWidget(self._section_title("STARTUP PROGRAMS"))
        self.startup_table = QTableWidget(0, 3)
        self.startup_table.setHorizontalHeaderLabels(["Name", "Command", "Enabled"])
        self.startup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.startup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.startup_table.setMaximumHeight(180)
        sul.addWidget(self.startup_table)
        su_btns = QHBoxLayout()
        su_refresh_btn = QPushButton("Refresh list")
        su_refresh_btn.setObjectName("secondaryBtn")
        su_refresh_btn.clicked.connect(self._on_startup_refresh_clicked)
        su_toggle_btn = QPushButton("Toggle selected")
        su_toggle_btn.setObjectName("secondaryBtn")
        su_toggle_btn.clicked.connect(self._on_startup_toggle_clicked)
        su_btns.addWidget(su_refresh_btn)
        su_btns.addWidget(su_toggle_btn)
        su_btns.addStretch()
        sul.addLayout(su_btns)
        inner_l.addWidget(su_card)

        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)
        return page

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        return lbl

    # ----------------------------------------------------------------About
    def _build_about_page(self) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page)
        t = QLabel("About Nboost")
        t.setObjectName("pageTitle")
        l.addWidget(t)
        card = GlassCard()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        text = QLabel(
            "Nboost v1.0.0\n\n"
            "Safety exclusions (always enforced, every module):\n"
            "  • Windows, System32, SysWOW64, WinSxS, Boot, Program Files/(x86) are never touched.\n"
            "  • Browser/app cache cleaning explicitly skips Login Data, Web Data, cookies key\n"
            "    stores, and Firefox logins.json/key*.db - saved passwords are never removed.\n"
            "  • Registry cleanup never touches SYSTEM/SECURITY/SAM hives, Winlogon, or IFEO keys,\n"
            "    and always writes a restore .reg backup to Documents before deleting anything.\n"
            "  • Startup program changes are reversible toggles, never deletions.\n\n"
            "Run as Administrator for full access to Event Logs, Windows Update cache, and the\n"
            "standby RAM purge - without elevation these steps are skipped safely."
        )
        text.setWordWrap(True)
        text.setStyleSheet("color: #c9d1e3; font-size: 12.5px; line-height: 1.5;")
        cl.addWidget(text)
        l.addWidget(card)

        dev_card = GlassCard()
        dcl = QHBoxLayout(dev_card)
        dcl.setContentsMargins(20, 14, 20, 14)
        dcl.addWidget(QLabel("Built by NengzXGODZ"))
        dcl.addStretch()
        dcl.addWidget(self._icon_link_button("telegram.svg", DEV_TELEGRAM_URL, "Telegram"))
        dcl.addWidget(self._icon_link_button("github.svg", DEV_GITHUB_URL, "GitHub"))
        l.addWidget(dev_card)

        l.addStretch()
        return page

    # ------------------------------------------------------------ Monitor
    def _start_monitor(self):
        self.monitor = SystemMonitor(interval_ms=1200)
        self.monitor.stats_ready.connect(self._on_stats)
        self.monitor.start()

    def _on_stats(self, stats: dict):
        self.gauge_cpu.animate_to(stats["cpu"])
        self.gauge_ram.animate_to(stats["ram"], f'{stats["ram_used_gb"]:.1f}/{stats["ram_total_gb"]:.1f} GB')
        self.gauge_disk.animate_to(stats["disk"], f'{stats["disk_free_gb"]:.1f} GB free')

    def _refresh_disk_free(self):
        QTimer.singleShot(0, lambda: None)

    # ------------------------------------------------------------ Actions
    def _set_busy(self, busy: bool):
        self.dash_progress.setValue(0)
        self.dash_progress.setVisible(busy)
        self.boost_btn.setEnabled(not busy)

    def _on_progress(self, done: int, total: int):
        pct = int(done / total * 100) if total else 100
        self.dash_progress.setValue(pct)

    def _on_scan_clicked(self):
        selected = self._selected_keys() or {s.key for s in jobs.JOB_SPECS}
        self._set_busy(True)
        self.console.append_line("=== SCAN STARTED (no files will be deleted) ===")
        self._scan_worker = CleanWorker(selected, dry_run=True)
        self._scan_worker.log_line.connect(self.console.append_line)
        self._scan_worker.progress.connect(self._on_progress)
        self._scan_worker.finished_bytes.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_finished(self, total_bytes: int):
        self._set_busy(False)
        self.lbl_recoverable.setText(f"Recoverable: {_human(total_bytes)}")
        self.console.append_line(f"=== SCAN COMPLETE: {_human(total_bytes)} recoverable ===")

    def _on_clean_selected_clicked(self):
        selected = self._selected_keys()
        if not selected:
            QMessageBox.information(self, "Nboost", "Select at least one item to clean.")
            return
        self._run_clean(selected)

    def _on_boost_clicked(self):
        selected = {s.key for s in jobs.JOB_SPECS}  # one-click boost = everything
        self._run_clean(selected)

    def _run_clean(self, selected: set[str]):
        self._set_busy(True)
        self.console.append_line("=== CLEAN STARTED ===")
        self._clean_worker = CleanWorker(selected, dry_run=False)
        self._clean_worker.log_line.connect(self.console.append_line)
        self._clean_worker.progress.connect(self._on_progress)
        self._clean_worker.finished_bytes.connect(self._on_clean_finished)
        self._clean_worker.start()

    def _on_clean_finished(self, total_bytes: int):
        self._set_busy(False)
        self.lbl_recoverable.setText("Recoverable: — ")
        self.console.append_line(f"=== CLEAN COMPLETE: {_human(total_bytes)} freed ===")

    def _on_free_ram_clicked(self):
        self.console.append_line("=== RAM OPTIMIZATION STARTED ===")
        from .core import ram_optimizer as ro
        ro.free_standby_ram(self.console.append_line)
        self.console.append_line("=== RAM OPTIMIZATION COMPLETE ===")

    # -- Registry --
    def _on_registry_scan_clicked(self):
        self.console.append_line("=== REGISTRY SCAN STARTED ===")
        self._reg_scan_worker = RegistryScanWorker()
        self._reg_scan_worker.log_line.connect(self.console.append_line)
        self._reg_scan_worker.finished_entries.connect(self._on_registry_scan_done)
        self._reg_scan_worker.start()

    def _on_registry_scan_done(self, entries: list):
        self._last_scan_entries = entries
        self.reg_table.setRowCount(0)
        for e in entries:
            row = self.reg_table.rowCount()
            self.reg_table.insertRow(row)
            self.reg_table.setItem(row, 0, QTableWidgetItem(f"{e.hive}\\{e.key_path}"))
            self.reg_table.setItem(row, 1, QTableWidgetItem(e.value_name))
            self.reg_table.setItem(row, 2, QTableWidgetItem(e.missing_path))
        self.reg_clean_btn.setEnabled(bool(entries))
        self.console.append_line(f"=== REGISTRY SCAN COMPLETE: {len(entries)} broken entrie(s) ===")

    def _on_registry_clean_clicked(self):
        if not self._last_scan_entries:
            return
        reply = QMessageBox.question(
            self, "Confirm registry cleanup",
            f"Remove {len(self._last_scan_entries)} broken registry value(s)?\n"
            "A restore backup (.reg) will be written to Documents first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._reg_clean_worker = RegistryCleanWorker(self._last_scan_entries)
        self._reg_clean_worker.log_line.connect(self.console.append_line)
        self._reg_clean_worker.finished_count.connect(self._on_registry_clean_done)
        self._reg_clean_worker.start()

    def _on_registry_clean_done(self, n: int):
        self.console.append_line(f"=== REGISTRY CLEANUP COMPLETE: {n} entrie(s) removed ===")
        self.reg_table.setRowCount(0)
        self._last_scan_entries = []
        self.reg_clean_btn.setEnabled(False)

    # -- Duplicates --
    def _on_duplicate_scan_clicked(self):
        self.console.append_line("=== DUPLICATE SCAN STARTED ===")
        self._dup_scan_worker = DuplicateScanWorker()
        self._dup_scan_worker.log_line.connect(self.console.append_line)
        self._dup_scan_worker.finished_groups.connect(self._on_duplicate_scan_done)
        self._dup_scan_worker.start()

    def _on_duplicate_scan_done(self, groups: list):
        self._last_dup_groups = groups
        self.dup_table.setRowCount(0)
        for g in groups:
            row = self.dup_table.rowCount()
            self.dup_table.insertRow(row)
            self.dup_table.setItem(row, 0, QTableWidgetItem(_human(g.size)))
            self.dup_table.setItem(row, 1, QTableWidgetItem(str(len(g.paths))))
            self.dup_table.setItem(row, 2, QTableWidgetItem(_human(g.reclaimable)))
        self.dup_clean_btn.setEnabled(bool(groups))
        total = sum(g.reclaimable for g in groups)
        self.console.append_line(f"=== DUPLICATE SCAN COMPLETE: {_human(total)} reclaimable ===")

    def _on_duplicate_clean_clicked(self):
        if not self._last_dup_groups:
            return
        reply = QMessageBox.question(
            self, "Confirm duplicate cleanup",
            f"Delete extra copies in {len(self._last_dup_groups)} duplicate group(s), "
            "keeping the oldest copy of each?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._dup_clean_worker = DuplicateCleanWorker(self._last_dup_groups)
        self._dup_clean_worker.log_line.connect(self.console.append_line)
        self._dup_clean_worker.finished_bytes.connect(self._on_duplicate_clean_done)
        self._dup_clean_worker.start()

    def _on_duplicate_clean_done(self, freed: int):
        self.console.append_line(f"=== DUPLICATE CLEANUP COMPLETE: {_human(freed)} freed ===")
        self.dup_table.setRowCount(0)
        self._last_dup_groups = []
        self.dup_clean_btn.setEnabled(False)

    # -- Startup --
    def _on_startup_refresh_clicked(self):
        self.console.append_line("=== LOADING STARTUP PROGRAMS ===")
        self._startup_worker = StartupListWorker()
        self._startup_worker.log_line.connect(self.console.append_line)
        self._startup_worker.finished_items.connect(self._on_startup_loaded)
        self._startup_worker.start()

    def _on_startup_loaded(self, items: list):
        self._startup_items = items
        self.startup_table.setRowCount(0)
        for it in items:
            row = self.startup_table.rowCount()
            self.startup_table.insertRow(row)
            self.startup_table.setItem(row, 0, QTableWidgetItem(it.name))
            self.startup_table.setItem(row, 1, QTableWidgetItem(it.command))
            state_item = QTableWidgetItem("Enabled" if it.enabled else "Disabled")
            self.startup_table.setItem(row, 2, state_item)

    def _on_startup_toggle_clicked(self):
        rows = sorted({i.row() for i in self.startup_table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "Nboost", "Select one or more startup rows first.")
            return
        for r in rows:
            item = self._startup_items[r]
            startm.set_enabled(item, not item.enabled, self.console.append_line)
            item.enabled = not item.enabled
        self._on_startup_loaded(self._startup_items)

    def closeEvent(self, event):
        try:
            self.monitor.stop()
        except Exception:
            pass
        super().closeEvent(event)
