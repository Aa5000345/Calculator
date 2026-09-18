# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 + 图标 + 隐式导入收集。

注意：
- excludes 只排除真正无关的包（其他 Qt 绑定 / 交互式工具 / pytest）
- 不要排除标准库（unittest / test / pydoc），否则 pyparsing、matplotlib
  之类的链式依赖会找不到模块
"""
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

ROOT = os.path.abspath(os.getcwd())

# ---------------- 数据文件 ----------------
datas = [
    (os.path.join(ROOT, "config"), "config"),
    (os.path.join(ROOT, "plugins"), "plugins"),
]

_assets = os.path.join(ROOT, "assets")
if os.path.isdir(_assets):
    datas.append((_assets, "assets"))

_icon = os.path.join(ROOT, "assets", "icon.ico")
icon = _icon if os.path.exists(_icon) else None

# ---------------- 隐式导入 ----------------
hiddenimports = []
for pkg in ("sympy", "scipy", "matplotlib", "pint",
            "holidays", "dateutil", "pytz", "babel"):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# 明确需要但常被漏掉的
hiddenimports += [
    "pyparsing.testing",     # matplotlib → pyparsing 的链式依赖，显式声明更稳
    "unittest",              # 同上；标准库模块，但显式声明能避免被剪
    "unittest.mock",
]

# ---------------- 排除（仅无关项） ----------------
excludes = [
    # 其他 Qt 绑定（只保留 PySide6）
    "PyQt5", "PyQt6", "PySide2",
    # 交互式开发工具
    "IPython", "jupyter", "notebook", "jupyterlab",
    # 测试框架（CI 已单独跑过）
    "pytest",
    # 其他 GUI
    "tkinter",
]

# ---------------- 打包 ----------------
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