# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Collecting all tjk submodules explicitly to ensure nothing is missed
hidden_imports = collect_submodules('tjk')
# Add specific ones just in case
hidden_imports.extend([
    'tjk.coupon_generator', 
    'tjk.storage.db', 
    'tjk.analysis.history_processor',
    'tjk.analysis.decision_engine',
    'tjk.analysis.calibrator',
    'tjk.cli',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets'
])

a = Analysis(
    ['app_gui.py'],
    pathex=[os.path.abspath('src')],
    binaries=[],
    # Force copy the entire tjk package content to the bundle root 'tjk' folder
    datas=[('src/tjk', 'tjk')],   
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TJKKupon_Final',
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
)
