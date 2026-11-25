# Nboost PyInstaller spec - builds a single-file, windowed .exe with the
# resources/ folder (theme, logo, icons) bundled alongside it.
#
# Build with:  pyinstaller nboost.spec
# Output:      dist/Nboost.exe

import glob

block_cipher = None

icon_svgs = [(p, 'resources/icons') for p in glob.glob('nboost/resources/icons/*.svg')]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('nboost/resources/theme.qss', 'resources'),
        ('nboost/resources/nboost.png', 'resources'),
        ('nboost/resources/nboost.ico', 'resources'),
    ] + icon_svgs,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Nboost',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed app, no terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='nboost/resources/nboost.ico',
    uac_admin=True,          # Nboost needs elevation for Event Logs / WU cache / RAM purge
)
