# -*- mode: python ; coding: utf-8 -*-
import os

root_dir = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[root_dir],
    binaries=[],
    datas=[
        ('config', 'config'),
    ],
    hiddenimports=[
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtNetwork', 'shiboken6',
        'core', 'core.engine', 'core.settings', 'core.i18n',
        'core.history', 'core.rates', 'core.crypto_tools',
        'core.probability', 'core.finance', 'core.dates',
        'core.bits', 'core.bits_ext', 'core.random_ext',
        'core.constants', 'core.units', 'core.worker',
        'core.logger', 'core.errors', 'core.error_handler',
        'core.updater', 'core.plugins', 'core.latex_ext',
        'ui', 'ui.panels', 'ui.latex_widget',
        'ui.shortcuts', 'ui.split_view', 'ui.tray',
        'ui.command_palette', 'ui.settings_dialog',
        'matplotlib.backends.backend_qtagg',
        'matplotlib.backends.backend_agg',
        'matplotlib.backends.backend_svg',
        'matplotlib.backends.backend_pdf',
        'pint', 'pint.registry',
        'pytz', 'dateutil', 'dateutil.parser',
        'holidays',
        'babel', 'babel.numbers', 'babel.dates',
        'cryptography',
        'scipy.special', 'scipy.stats',
        'sympy.parsing.sympy_parser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'PyQt5', 'PyQt6', 'PySide2',
        'pandas', 'IPython', 'jupyter', 'notebook',
        'tests', 'examples', 'docs',
        'setuptools', 'pip', 'wheel',
    ],
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
    name='MultiCalc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
