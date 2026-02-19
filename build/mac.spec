# -*- mode: python ; coding: utf-8 -*-
# Run from project root: pyinstaller build/mac.spec

import os
PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPECPATH), ''))
# SPECPATH is set by PyInstaller to the directory containing this spec file
# So PROJ_ROOT = parent of build/ = project root
PROJ_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

block_cipher = None

a = Analysis(
    [os.path.join(PROJ_ROOT, 'src', 'main.py')],
    pathex=[os.path.join(PROJ_ROOT, 'src')],
    binaries=[],
    datas=[],
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
    },
)
