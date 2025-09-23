# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/esolog_tail.py'],
    pathex=[],
    binaries=[],
    datas=[('data/gear_sets/LibSets_SetData.xlsm', 'data/gear_sets')],
    hiddenimports=['gear_set_database_optimized'],
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
    name='esolog-tail',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
