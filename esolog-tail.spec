# -*- mode: python ; coding: utf-8 -*-
# ESO Log Tail GUI: onedir, windowed. Build with: pyinstaller esolog-tail.spec

import os

_icon = ['icon.ico'] if os.path.exists('icon.ico') else []

a = Analysis(
    ['src/esolog_gui.py'],
    pathex=['src'],
    binaries=[],
    # Bundled data: ability icons (scripts/extract_ability_icons.py), the
    # ESO-Hub link maps (scripts/generate_esohub_links.py), poison names,
    # armor weights and restoration staff ids (scripts/generate_poison_names.py,
    # scripts/generate_armor_weights.py, scripts/generate_restoration_staves.py)
    # and food and drink buff ids (scripts/generate_food_buffs.py)
    datas=([('icon.ico', '.')] if os.path.exists('icon.ico') else [])
          + [(d, d) for d in ('data/icons/abilities', 'data/esohub', 'data/items',
                              'data/buffs') if os.path.isdir(d)],
    hiddenimports=[
        'app_config',
        'app_startup',
        'engine_events',
        'esolog_tail',
        'fight_history',
        'gear_set_data',
        'gear_set_database',
        'gui',
        'gui.engine_worker',
        'gui.fight_render',
        'gui.main_window',
        'gui.settings_dialog',
        'log_archiver',
        'log_freshness',
        'version',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Build-time-only libraries
        'pandas', 'numpy', 'openpyxl', 'PIL',
        'tkinter',
        # Unused Qt modules (keep the bundle lean)
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
        'PySide6.QtBluetooth', 'PySide6.QtCharts', 'PySide6.QtConcurrent',
        'PySide6.QtDataVisualization', 'PySide6.QtDesigner', 'PySide6.QtHelp',
        'PySide6.QtLocation', 'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets', 'PySide6.QtNetworkAuth',
        'PySide6.QtNfc', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtPositioning',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuick3D',
        'PySide6.QtQuickControls2', 'PySide6.QtQuickWidgets',
        'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtSensors',
        'PySide6.QtSerialBus', 'PySide6.QtSerialPort', 'PySide6.QtSpatialAudio',
        'PySide6.QtSql', 'PySide6.QtStateMachine', 'PySide6.QtSvg',
        'PySide6.QtSvgWidgets', 'PySide6.QtTest', 'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools', 'PySide6.QtWebChannel', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets', 'PySide6.QtXml',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='esolog-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is off: it was only ever applied on a machine that happened to have
    # it installed (CI does not), and packed DLLs draw antivirus false alarms
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='esolog-gui',
)
