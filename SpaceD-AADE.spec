# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('gui/cesium_app/index.html', 'gui/cesium_app'),
        ('gui/cesium_app/*.js',       'gui/cesium_app'),
        ('adapters/gmat/templates/*.j2', 'adapters/gmat/templates'),
        ('data/design_templates/*.j2',   'data/design_templates'),
        ('config/*.json',                'config'),
    ],
    hiddenimports=[
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel',
        'plotly',
        'jinja2',
        'numpy',
        'scipy',
        'adapters.ipsap.ipsap_adapter',
        'core.domain.structural',
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
    [],
    exclude_binaries=True,
    name='SpaceD-AADE',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SpaceD-AADE',
)
