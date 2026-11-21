# -*- mode: python ; coding: utf-8 -*-
# ESO Log Tail GUI: onedir, windowed. Build with: pyinstaller esolog-tail.spec

import os
import sys

_icon = ['icon.ico'] if os.path.exists('icon.ico') else []

a = Analysis(
    ['src/esolog_gui.py'],
    pathex=['src'],
    binaries=[],
    # Bundled data: ability icons (scripts/extract_ability_icons.py), the
    # ESO-Hub link maps (scripts/generate_esohub_links.py), poison names,
    # armor weights and weapon types (scripts/generate_poison_names.py,
    # scripts/generate_armor_weights.py, scripts/generate_weapon_types.py)
    # food and drink buff ids (scripts/generate_food_buffs.py), the sets'
    # penetration and crit bonuses (scripts/generate_set_offense.py) and the
    # trials' and arenas' art (scripts/extract_instance_art.py).
    # CI has each built bundle read every table (src/self_check.py, issue
    # #237): a table added here needs an entry in its TABLES, which a unit
    # test asks for
    datas=([('icon.ico', '.')] if os.path.exists('icon.ico') else [])
          + [(d, d) for d in ('data/icons/abilities', 'data/esohub', 'data/items',
                              'data/buffs', 'data/skills', 'data/sets',
                              'data/art/instances') if os.path.isdir(d)],
    hiddenimports=[
        'app_config',
        'app_startup',
        'banner_capture',
        'desktop_duplication',
        'engine_events',
        'esolog_tail',
        'fight_history',
        'gear_set_data',
        'gear_set_database',
        'gui',
        'gui.banner_burst',
        'gui.engine_worker',
        'gui.fight_render',
        'gui.main_window',
        'gui.settings_dialog',
        'log_archiver',
        'log_freshness',
        'log_open',
        'recycle_bin',
        'self_check',
        'split_retention',
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
        # QtNetwork: the update check uses urllib. Left in, its hook bundles
        # whichever OpenSSL DLLs are on the build machine's PATH.
        'PySide6.QtMultimediaWidgets', 'PySide6.QtNetwork', 'PySide6.QtNetworkAuth',
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
# The bundled data's game version and each table's date
# (scripts/stamp_data_version.py), for the staleness check and About. A
# build without it would ship a check that can never say the game is newer,
# so its absence stops the build
if not os.path.exists('data/version.json'):
    raise SystemExit('data/version.json is missing: run scripts/stamp_data_version.py')
a.datas += [('data/version.json', 'data/version.json', 'DATA')]
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

# macOS (issue #32): the app bundle, dist/ESO Log Tail.app. No signing
# identity is named: PyInstaller gives the bundle an ad-hoc signature, and a
# release is signed afterwards, in a job of its own.
if sys.platform == 'darwin':
    sys.path.insert(0, os.path.join(SPECPATH, 'src'))
    from version import __version__ as _version

    # macOS shows this when it asks the user whether the app may read a
    # folder. One sentence for every place a log can be: the game writes in
    # Documents, and a log opened for review can be anywhere
    _why_files = ('ESO Log Tail reads the Encounter.log the game writes, '
                  'and the logs you open for review.')
    app = BUNDLE(
        coll,
        name='ESO Log Tail.app',
        icon='icon.icns' if os.path.exists('icon.icns') else None,
        bundle_identifier='com.brainsnorkel.esolog-tail',
        version=_version,
        info_plist={
            'CFBundleDisplayName': 'ESO Log Tail',
            'CFBundleVersion': _version,
            'NSHighResolutionCapable': True,
            # The oldest macOS CI starts the app on (the smoke-macos job in
            # .github/workflows/build-installers.yml). The stamp check reads
            # it from here: scripts/check_macos_stamps.py
            'LSMinimumSystemVersion': '15.0',
            'LSApplicationCategoryType': 'public.app-category.utilities',
            'NSDocumentsFolderUsageDescription': _why_files,
            'NSDesktopFolderUsageDescription': _why_files,
            'NSDownloadsFolderUsageDescription': _why_files,
            'NSRemovableVolumesUsageDescription': _why_files,
            'NSNetworkVolumesUsageDescription': _why_files,
            'NSFileProviderDomainUsageDescription': _why_files,
        },
    )
