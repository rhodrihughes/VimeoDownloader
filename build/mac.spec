# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller build/mac.spec

block_cipher = None

a = Analysis(
    ['../src/main.py'],
    pathex=['../src'],
    binaries=[],
    datas=[],
    hiddenimports=['customtkinter'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    bootloader_ignore_signals=False,
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
    icon='../assets/icon.icns',
    bundle_identifier='com.vimeodownloader.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '1.0.0',
    },
)
