# Building Nboost.exe and NboostSetup.exe

## Requirements

- Windows 10/11
- Python 3.10+ on PATH
- Internet access for the first `pip install` (PyQt6 + psutil + pyinstaller wheels)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (works the same on the "7" preview builds) - only needed for the installer step

## Step 1 - build the exe

One command:

```bat
build_exe.bat
```

or the exact PyInstaller command by hand:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pyinstaller nboost.spec --noconfirm --clean
```

Output: `dist\Nboost.exe` - single file, windowed, icon + theme + resources baked in.

## Step 2 - build the installer (Inno Setup)

Once `dist\Nboost.exe` exists, compile `installer\nboost.iss`:

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\nboost.iss
```

(swap the path for wherever Inno Setup installed `ISCC.exe` - the "7"
preview installs to the same default location pattern). Output:

```
installer\Output\NboostSetup.exe
```

That's the single file you hand out / upload to a GitHub release - it
installs to Program Files, adds Start Menu + optional desktop shortcuts,
and requests admin at install time (the app itself still requests
elevation on launch, per the spec's `uac_admin=True`).

To rebuild after a code change: repeat Step 1, then re-run the `ISCC.exe`
command - no need to reopen the Inno Setup GUI.

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
