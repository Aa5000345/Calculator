# -*- mode: python ; coding: utf-8 -*-
import os

root_dir = os.path.abspath('.')

a = Analysis(
    ['main.py'],                          # 主入口
    pathex=[root_dir],                    # 项目根目录加入 Python 路径
    binaries=[],
    datas=[
        ('config', 'config'),             # 完整包含 config/ 目录（i18n + 默认设置 + 离线汇率）
    ],
    hiddenimports=[
        # PySide6 核心模块
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtNetwork', 'shiboken6',
        # 项目自定义模块（PyInstaller 有时无法自动识别）
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
        # matplotlib 后端（如果使用了 QtAgg）
        'matplotlib.backends.backend_qtagg',
        # scipy / sympy 的隐式导入
        'scipy.special', 'scipy.stats',
        'sympy.parsing.sympy_parser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除未使用的重型/无关模块，控制体积
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
    upx=True,                  # 如已安装 UPX 则启用压缩
    upx_exclude=[
        'vcruntime140.dll',    # 排除 C 运行时 DLL，避免 UPX 压缩后兼容性问题
        'msvcp140.dll',
        'python3*.dll',
    ],
    runtime_tmpdir=None,
    console=False,             # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',    # 如有图标，取消注释并指向正确路径
)