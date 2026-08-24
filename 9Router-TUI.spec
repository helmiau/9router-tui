# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for 9Router TUI — double-clickable .exe / Linux binary
# Build: pyinstaller 9Router-TUI.spec  atau  python -m PyInstaller 9Router-TUI.spec
# Output: dist/9Router-TUI.exe (Windows) / dist/9Router-TUI (Linux)
# Version is read from VERSION file (single source of truth)

import pathlib

_version_file = pathlib.Path(SPECPATH) / "VERSION"
try:
    _app_version = _version_file.read_text(encoding="utf-8").strip()
except Exception:
    _app_version = "1.0.0"

from PyInstaller.utils.hooks import collect_all

# Collect textual + rich fully (they use dynamic imports)
textual_datas, textual_binaries, textual_hidden = collect_all('textual')
rich_datas, rich_binaries, rich_hidden = collect_all('rich')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=textual_binaries + rich_binaries,
    datas=textual_datas + rich_datas + [('VERSION', '.'), ('_version.py', '.')],
    hiddenimports=textual_hidden + rich_hidden + [
        'client', 'updater', 'cli', '_version',
        'textual.widgets', 'textual.app', 'textual.binding',
        'textual.containers', 'textual.screen', 'textual.reactive',
        'rich.console', 'rich.table', 'rich.panel', 'rich.json',
        'requests', 'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='9Router-TUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # TUI butuh console — double-click akan buka jendela terminal otomatis
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # ganti ke 'icon.ico' jika ada
)
