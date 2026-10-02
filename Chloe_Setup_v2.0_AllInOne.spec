# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Chloe\\installer\\setup_wizard.py'],
    pathex=['D:\\Chloe\\installer'],
    binaries=[],
    datas=[('D:\\Chloe\\installer\\chloe_payload.zip', '.'), ('D:\\Chloe\\backend\\app\\static\\favicon.ico', 'app/static')],
    hiddenimports=[],
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
    name='Chloe_Setup_v2.0_AllInOne',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:\\Chloe\\backend\\app\\static\\favicon.ico'],
)
