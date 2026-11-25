"""
Nboost - core/paths.py
Resolves bundled resource paths correctly both when run from source and
when frozen into a standalone .exe by PyInstaller (which unpacks data
files into sys._MEIPASS at runtime).
"""

from __future__ import annotations
import os
import sys


def base_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../nboost


def resource_path(*parts: str) -> str:
    return os.path.join(base_dir(), "resources", *parts)
