# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Metro Package Review.
Bundles everything into a single .exe with hidden source code.

Build:  pyinstaller build.spec
Output: dist/MetroPackageReview.exe
"""

import os, sys
from pathlib import Path

# Use the directory containing this spec file
try:
    ROOT = str(Path(SPECPATH).parent.resolve())  # noqa: F821
except NameError:
    ROOT = os.path.dirname(os.path.abspath(__file__))

# Verify main.py is actually there, otherwise try cwd
if not os.path.isfile(os.path.join(ROOT, 'main.py')):
    ROOT = os.getcwd()

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'metro_train_image.png'), '.'),
        (os.path.join(ROOT, 'logo_top_left.png'), '.'),
        (os.path.join(ROOT, 'reference_docs'), 'reference_docs'),
        (os.path.join(ROOT, 'modules'), 'modules'),
        (os.path.join(ROOT, 'orchestrator.py'), '.'),
        (os.path.join(ROOT, 'ui.py'), '.'),
    ],
    hiddenimports=[
        'modules',
        'modules.asset_register_checker',
        'modules.ifc_checker',
        'modules.nwc_checker',
        'orchestrator',
        'openpyxl',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter',
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'pytest', 'unittest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MetroPackageReview',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed — no terminal pops up
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=os.path.join(ROOT, 'logo_top_left.png'),
)
