# -*- mode: python ; coding: utf-8 -*-
# Run from project root: pyinstaller build/mac.spec

import os
import sys
import glob

os.environ.setdefault('MACOSX_DEPLOYMENT_TARGET', '13.0')

PROJ_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

block_cipher = None

# Locate the Tcl/Tk framework bundled with this Python installation.
# python.org builds ship Tcl/Tk inside the framework at a known path.
_py_prefix = sys.prefix  # e.g. /Library/Frameworks/Python.framework/Versions/3.x
_tcltk_base = os.path.join(_py_prefix, 'lib')

# Collect all Tcl/Tk dylibs so they land next to the executable.
_tcltk_binaries = []
for _pattern in ('libtcl*.dylib', 'libtk*.dylib'):
    for _lib in glob.glob(os.path.join(_tcltk_base, _pattern)):
        _tcltk_binaries.append((_lib, '.'))

# Bundle the Tcl/Tk library data directories (init scripts, encodings, etc.)
_tcltk_datas = []
for _dir_pattern in ('tcl*', 'tk*'):
    for _d in glob.glob(os.path.join(_tcltk_base, _dir_pattern)):
        if os.path.isdir(_d):
            _tcltk_datas.append((_d, os.path.basename(_d)))

a = Analysis(
    [os.path.join(PROJ_ROOT, 'src', 'main.py')],
    pathex=[os.path.join(PROJ_ROOT, 'src')],
    binaries=_tcltk_binaries,
    datas=_tcltk_datas,
    hiddenimports=['customtkinter', 'tkinter', 'tkinter.filedialog', '_tkinter'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VimeoDownloader',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VimeoDownloader',
)

app = BUNDLE(
    coll,
    name='VimeoDownloader.app',
    icon=os.path.join(PROJ_ROOT, 'assets', 'macicon.icns'),
    bundle_identifier='com.vimeodownloader.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '13.0',
    },
)
