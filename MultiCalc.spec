# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 + 图标 + 隐式导入收集。

设计要点：
- 可选目录（config / plugins / assets）不存在时自动跳过，不再报错
- excludes 只排除真正无关的包，标准库（unittest 等）不排
- 显式 hiddenimports 补上链式依赖易漏的模块
"""
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

ROOT = os.path.abspath(os.getcwd())


# ---------------------------------------------------------------------------
# 数据文件：仅加入存在的目录
# ---------------------------------------------------------------------------

def _add_if_dir(datas, path, dest=None, required=False):
    """如果 path 是目录就加入 datas；required=True 时不存在则报错。"""
    dest = dest or os.path.basename(path)
    if os.path.isdir(path):
        datas.append((path, dest))
        return True
    if required:
        raise SystemExit(f"必需的目录不存在：{path}")
    return False


datas = []
_add_if_dir(datas, os.path.join(ROOT, "config"), "config", required=True)
_add_if_dir(datas, os.path.join(ROOT, "plugins"), "plugins")
_add_if_dir(datas, os.path.join(ROOT, "assets"), "assets")

# 图标（可选）
_icon = os.path.join(ROOT, "assets", "icon.ico")
icon = _icon if os.path.exists(_icon) else None


# ---------------------------------------------------------------------------
# 隐式导入
# ---------------------------------------------------------------------------

hiddenimports = []
for pkg in ("sympy", "scipy", "matplotlib", "pint",
            "holidays", "dateutil", "pytz", "babel"):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# 显式声明：标准库 + 链式依赖
hiddenimports += [
    "pyparsing.testing",
    "unittest",
    "unittest.mock",
]


# ---------------------------------------------------------------------------
# 排除
# ---------------------------------------------------------------------------

excludes = [
    # 其他 Qt 绑定
    "PyQt5", "PyQt6", "PySide2",
    # 交互式开发工具
    "IPython", "jupyter", "notebook", "jupyterlab",
    # 测试框架（CI 已单独跑过）
    "pytest",
    # 其他 GUI
    "tkinter",
    # 消除打包期 WARNING
    "torch",                # scipy 的 array_api_compat 探测它
    "scipy._lib.array_api_compat.torch",
    "matplotlib.tests",     # 需要测试图片数据，不需要
]


# ---------------------------------------------------------------------------
# 打包
# ---------------------------------------------------------------------------

a = Analysis(
    ["main.py"],
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
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)
