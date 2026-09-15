# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：MultiCalc 打包配置。

- 若 assets/icon.ico 存在，用作 exe 图标；否则使用 PyInstaller 默认图标
- 打包 config/ 目录（默认设置、i18n、主题、离线汇率）
- 排除测试与开发依赖
"""
import os

from PyInstaller.utils.hooks import collect_submodules

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

ROOT = os.path.abspath(os.path.dirname(SPEC))  # noqa: F821  SPEC 由 PyInstaller 注入

ICON_PATH = os.path.join(ROOT, "assets", "icon.ico")
ICON = ICON_PATH if os.path.exists(ICON_PATH) else None

if ICON is None:
    print("[MultiCalc.spec] assets/icon.ico not found, using default icon")

# ---------------------------------------------------------------------------
# 数据文件（config 目录整体打包）
# ---------------------------------------------------------------------------

datas = [
    (os.path.join(ROOT, "config"), "config"),
]

# 可选：若 assets 目录存在，也一并打包（用于托盘图标等）
assets_dir = os.path.join(ROOT, "assets")
if os.path.isdir(assets_dir):
    datas.append((assets_dir, "assets"))

# ---------------------------------------------------------------------------
# 隐式导入
# ---------------------------------------------------------------------------

hiddenimports = [
    # Qt 后端
    "PySide6.QtSvg",
    "PySide6.QtNetwork",
    # matplotlib 后端
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_agg",
    # core 子模块
    "core.ai",
    "core.secrets",
    # 面板
    "ui.panels.ai",
    "ui.panels.script",
    # 键盘
    "ui.widgets.calc_keyboard",
    "ui.widgets.focus_tracker",
    "ui.widgets.key_button",
    "ui.widgets.keyboard_layouts",
]

# 自动收集可能被延迟导入的包
hiddenimports += collect_submodules("sympy")
hiddenimports += collect_submodules("pint")

# ---------------------------------------------------------------------------
# 排除项（减小体积）
# ---------------------------------------------------------------------------

excludes = [
    "tkinter",
    "test",
    "tests",
    "unittest",
    "pytest",
    "IPython",
    "jupyter",
    "notebook",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "wx",
]

# ---------------------------------------------------------------------------
# 构建
# ---------------------------------------------------------------------------

block_cipher = None

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MultiCalc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,          # 关键：None 时用默认图标
)