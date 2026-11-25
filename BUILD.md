# Building Nboost.exe

## Requirements

- Windows 10/11
- Python 3.10+ on PATH
- Internet access for the first `pip install` (PyQt6 + psutil + pyinstaller wheels)

## One command

```bat
build_exe.bat
```

This creates `.venv`, installs `requirements.txt`, then runs PyInstaller against
`nboost.spec`. Output: `dist\Nboost.exe`.

## Manual build

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pyinstaller nboost.spec --noconfirm
```

## What the spec does

- Entry point: `main.py`
- Bundles `resources/theme.qss`, `resources/nboost.png`, `resources/nboost.ico`,
  and the two dev-link SVG icons as data files, unpacked at runtime via
  `nboost/core/paths.py` (`sys._MEIPASS` when frozen).
- `console=False` — windowed app, no terminal flashes on launch.
- `icon='nboost/resources/nboost.ico'` — taskbar/exe icon.
- `uac_admin=True` — the exe's manifest requests elevation on launch, since
  Event Log clearing, the Windows Update cache purge, and the standby-RAM
  purge all need Administrator. If you'd rather prompt only when those
  specific actions are used, set this to `False` and launch the exe
  normally — Nboost detects the non-elevated state and skips/flags those
  steps in the log instead of failing silently.

## Troubleshooting

- **"Failed to execute script main" on launch** — run the exe from a `cmd`
  window instead of double-clicking, to see the real traceback
  (`Nboost.exe` with `console=True` temporarily in the spec also works).
- **Antivirus flags the fresh build** — this is a near-universal false
  positive for PyInstaller's bootloader on a brand-new, unsigned binary with
  no reputation yet. Submit it to your AV vendor as a false positive, or
  code-sign the exe with a purchased certificate if you're distributing it
  publicly.
- **Icon not showing in Explorer** — Windows caches exe icons aggressively;
  rebuild the icon cache (`ie4uinit.exe -ClearIconCache`) or just move the
  exe to a new filename once.
- **UPX unavailable** — if `pyinstaller` warns it can't find UPX, either
  install it and put it on PATH, or set `upx=False` in `nboost.spec`; it
  only affects binary size, not functionality.
