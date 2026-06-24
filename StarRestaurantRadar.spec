# -*- mode: python ; coding: utf-8 -*-

import importlib.util

from PyInstaller.utils.hooks import collect_data_files


if importlib.util.find_spec('certifi') is not None:
    certifi_datas = collect_data_files('certifi')
    certifi_hiddenimports = ['certifi']
elif importlib.util.find_spec('pip._vendor.certifi') is not None:
    certifi_datas = collect_data_files('pip._vendor.certifi')
    certifi_hiddenimports = ['pip._vendor.certifi']
else:
    certifi_datas = []
    certifi_hiddenimports = []


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), *certifi_datas],
    hiddenimports=certifi_hiddenimports,
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
    [],
    exclude_binaries=True,
    name='StarRestaurantRadar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StarRestaurantRadar',
)
