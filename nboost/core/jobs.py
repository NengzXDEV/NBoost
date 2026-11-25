"""
Nboost - core/jobs.py
Flat registry mapping each checkbox in the UI to its job function, grouped
by module. The UI only needs to know checkbox ids; everything else about
"what actually happens" lives in cleaner_engine / ram_optimizer.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List

from . import cleaner_engine as ce
from . import ram_optimizer as ro

LogFn = Callable[[str], None]
JobFn = Callable[[bool, LogFn], int]


@dataclass
class JobSpec:
    key: str            # stable id, used by UI checkbox + settings persistence
    label: str          # shown next to the checkbox
    module: str         # section header
    fn: JobFn
    default_checked: bool = True


JOB_SPECS: List[JobSpec] = [
    # --- Module 1: Junk & Temp Cleaner ---
    JobSpec("win_temp", "Windows Temp", "Junk & Temp Cleaner", ce.job_windows_temp),
    JobSpec("user_temp", "User Temp (%temp%)", "Junk & Temp Cleaner", ce.job_user_temp),
    JobSpec("prefetch", "Prefetch", "Junk & Temp Cleaner", ce.job_prefetch),
    JobSpec("crash_dumps", "Crash Dumps", "Junk & Temp Cleaner", ce.job_crash_dumps),
    JobSpec("recycle_bin", "Recycle Bin", "Junk & Temp Cleaner", ce.job_recycle_bin),

    # --- Module 2: Log & Cache Cleaner ---
    JobSpec("event_logs", "Windows Event Logs", "Log & Cache Cleaner", ce.job_event_logs, default_checked=False),
    JobSpec("wu_cache", "Windows Update cache (SoftwareDistribution)", "Log & Cache Cleaner", ce.job_windows_update_cache),
    JobSpec("thumb_cache", "Thumbnail / Icon cache", "Log & Cache Cleaner", ce.job_thumbnail_icon_cache),
    JobSpec("dns_cache", "DNS cache", "Log & Cache Cleaner", ce.job_dns_cache),

    # --- Module 3: Browser & App Cleaner ---
    JobSpec("app_chrome", "Chrome cache/cookies", "Browser & App Cleaner",
            lambda dry, log: ce.job_browser_app_cache(dry, log, ["Chrome"])),
    JobSpec("app_edge", "Edge cache/cookies", "Browser & App Cleaner",
            lambda dry, log: ce.job_browser_app_cache(dry, log, ["Edge"])),
    JobSpec("app_discord", "Discord cache", "Browser & App Cleaner",
            lambda dry, log: ce.job_browser_app_cache(dry, log, ["Discord"])),
    JobSpec("app_steam", "Steam web/shader cache", "Browser & App Cleaner",
            lambda dry, log: ce.job_browser_app_cache(dry, log, ["Steam"])),

    # --- Module 4: Advanced System Optimization ---
    JobSpec("ram_standby", "Free standby RAM cache", "Advanced Optimization",
            lambda dry, log: 0 if dry else ro.free_standby_ram(log), default_checked=True),
    # registry / duplicates / startup are driven by their own dialogs (see main_window),
    # not a plain scan-and-delete byte count, so they aren't in this flat list.
]


def run_selected(selected_keys: set[str], dry_run: bool, log: LogFn,
                  progress_cb: Callable[[int, int], None] | None = None) -> int:
    """Runs every selected job in order, returns total bytes (found or freed).
    progress_cb(done, total) is called after each job, for the UI progress bar."""
    ordered = [s for s in JOB_SPECS if s.key in selected_keys]
    total_jobs = len(ordered)
    total_bytes = 0
    for i, spec in enumerate(ordered, start=1):
        try:
            total_bytes += spec.fn(dry_run, log)
        except Exception as e:  # never let one bad job kill the whole run
            log(f"[error] {spec.label} failed: {e}")
        if progress_cb:
            progress_cb(i, total_jobs)
    return total_bytes
