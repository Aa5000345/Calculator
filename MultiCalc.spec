# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 + 图标 + 精细排除。

优化要点（v2）：
1. excludes 分组管理：Qt 其它绑定 / 交互式工具 / 测试框架 / 未用科学库
2. hiddenimports 用 collect_submodules 自动收集，避免手动漏项
3. UPX 启用，但排除会破坏签名的 dll
4. 分离 onefile / onedir 两种模式（用环境变量切换）
5. 排除 pix2tex / torch（可选依赖，按需安装）
6. 排除测试数据、示例、文档

构建：
    pyinstaller MultiCalc.spec.txt

    # onedir 模式（启动更快）
    set MC_ONEDIR=1 && pyinstaller MultiCalc.spec.txt

    # 关闭 UPX
    set MC_NO_UPX=1 && pyinstaller MultiCalc.spec.txt

    # Debug 模式（保留控制台）
    set MC_DEBUG=1 && pyinstaller MultiCalc.spec.txt
"""
import os
import sys
from PyInstaller.utils.hooks import (
    collect_submodules, collect_data_files, collect_dynamic_libs,
)

block_cipher = None

# ---------------------------------------------------------------------------
# 环境变量开关
# ---------------------------------------------------------------------------

ONEDIR = os.environ.get("MC_ONEDIR", "") not in ("", "0", "false")
NO_UPX = os.environ.get("MC_NO_UPX", "") not in ("", "0", "false")
DEBUG = os.environ.get("MC_DEBUG", "") not in ("", "0", "false")

ROOT = os.path.abspath(os.getcwd())


# ---------------------------------------------------------------------------
# 数据文件
# ---------------------------------------------------------------------------

datas = [
    (os.path.join(ROOT, "config"), "config"),
    (os.path.join(ROOT, "plugins"), "plugins"),
]

_assets = os.path.join(ROOT, "assets")
if os.path.isdir(_assets):
    datas.append((_assets, "assets"))

# 文档也打包一份（用户可以从 about 里打开）
for doc in ("README.md", "LICENSE", "SECURITY.md"):
    p = os.path.join(ROOT, doc)
    if os.path.exists(p):
        datas.append((p, "."))

_icon = os.path.join(ROOT, "assets", "icon.ico")
icon = _icon if os.path.exists(_icon) else None


# ---------------------------------------------------------------------------
# 隐式导入
# ---------------------------------------------------------------------------

hiddenimports = []

# 需要完整子模块的包
for pkg in (
    "sympy",
    "scipy",
    "matplotlib",
    "pint",
    "holidays",
    "dateutil",
    "pytz",
    "babel",
    "cryptography",
    "argon2",
):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# 明确需要但常被漏掉的
hiddenimports += [
    # pyparsing 链式依赖
    "pyparsing.testing",
    "unittest",
    "unittest.mock",
    # matplotlib 后端（Qt 用）
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_svg",
    "matplotlib.backends.backend_pdf",
    # scipy 优化 / 积分
    "scipy.optimize",
    "scipy.integrate",
    "scipy.stats",
    # sympy 解析
    "sympy.parsing.sympy_parser",
    "sympy.parsing.latex",
    # Qt
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    # cryptography 后端
    "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "cryptography.hazmat.primitives.kdf.scrypt",
    # zoneinfo（日期时区）
    "zoneinfo",
]


# ---------------------------------------------------------------------------
# 排除
# ---------------------------------------------------------------------------

excludes = [
    # ---- 其它 Qt 绑定 ----
    "PyQt5", "PyQt6", "PySide2", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml",
    "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtBluetooth",
    "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtWebChannel",

    # ---- 交互式开发工具 ----
    "IPython", "jupyter", "notebook", "jupyterlab",
    "ipykernel", "ipywidgets", "nbconvert", "nbformat",
    "qtconsole", "spyder",

    # ---- 测试框架 ----
    "pytest", "nose", "hypothesis", "coverage",
    "pytest_qt", "pytest_cov",

    # ---- 其它 GUI ----
    "tkinter", "turtle", "wx", "kivy", "pygame", "PySimpleGUI",

    # ---- 未用的大包 ----
    "tensorflow", "keras", "torch", "torchvision", "torchaudio",
    "pix2tex", "transformers", "datasets",
    "sklearn", "pandas", "openpyxl", "xlrd", "xlwt",
    "sqlalchemy", "pymongo", "redis", "psycopg2",
    "bokeh", "plotly", "dash", "streamlit", "gradio",
    "cv2", "PIL.ImageQt", "imageio_ffmpeg",

    # ---- 文档 / 测试数据 ----
    "sympy.testing", "scipy._lib._testutils",
    "matplotlib.tests", "numpy.tests",
    "cryptography.tests",

    # ---- 其它 ----
    "setuptools", "pkg_resources",
    "pip", "wheel", "distutils",
    "lib2to3", "pydoc", "doctest",
]


# ---------------------------------------------------------------------------
# 动态库
# ---------------------------------------------------------------------------

binaries = []
try:
    binaries += collect_dynamic_libs("cryptography")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=[ROOT],
    binaries=binaries,
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ---------------------------------------------------------------------------
# EXE / COLLECT
# ---------------------------------------------------------------------------

# UPX 排除项：这些 dll 被 UPX 压缩后可能无法加载
upx_exclude = [
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "python3.dll",
    "python3*.dll",
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "Qt6Svg.dll",
    "qwindows.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
]

_common = dict(
    name="MultiCalc",
    debug=DEBUG,
    bootloader_ignore_signals=False,
    strip=False,
    upx=(not NO_UPX),
    upx_exclude=upx_exclude,
    runtime_tmpdir=None,
    console=DEBUG,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

if ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
              **_common)
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=(not NO_UPX),
        upx_exclude=upx_exclude,
        name="MultiCalc",
    )
else:
    # onefile
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        **_common,
    )