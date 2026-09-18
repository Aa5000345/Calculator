#!/usr/bin/env python
"""构建辅助脚本：一条命令完成打包。

用法：
    # 默认（onefile）
    python scripts/build.py

    # onedir（启动更快，但产物是目录）
    python scripts/build.py --onedir

    # 不压缩（排错用）
    python scripts/build.py --no-upx

    # Debug（保留控制台）
    python scripts/build.py --debug

    # 清理构建产物
    python scripts/build.py --clean

    # 只检查依赖是否齐全
    python scripts/build.py --check
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys


for _sn in ("stdout", "stderr"):
    _s = getattr(sys, _sn, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLEAN_DIRS = ["build", "dist", "__pycache__"]
CLEAN_FILES = ["MultiCalc.exe", "MultiCalc"]
SPEC_IN = os.path.join(ROOT, "MultiCalc.spec.txt")
SPEC_ACTIVE = os.path.join(ROOT, "MultiCalc.spec")


# ---------------------------------------------------------------------------

def _check_dependencies() -> bool:
    """检查必需依赖是否已安装。"""
    ok = True

    # PyInstaller
    try:
        import PyInstaller  # noqa: F401
        print("[OK] PyInstaller")
    except ImportError:
        print("[MISS] PyInstaller —— 运行 pip install pyinstaller")
        ok = False

    # 运行依赖
    required = [
        "PySide6", "sympy", "numpy", "matplotlib",
        "requests", "pint", "scipy", "cryptography",
    ]
    for pkg in required:
        try:
            __import__(pkg)
            print(f"[OK] {pkg}")
        except ImportError:
            print(f"[MISS] {pkg}")
            ok = False

    # 可选依赖（只提示）
    optional = ["argon2", "bcrypt", "PIL", "qrcode", "holidays"]
    for pkg in optional:
        try:
            __import__(pkg)
            print(f"[OK] {pkg} (可选)")
        except ImportError:
            print(f"[--] {pkg} (可选，未安装)")

    return ok


def _clean():
    """清理构建产物。"""
    for d in CLEAN_DIRS:
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            print(f"[CLEAN] {p}")
            try:
                shutil.rmtree(p)
            except Exception as e:
                print(f"[WARN] 无法删除 {p}: {e}")

    for f in CLEAN_FILES:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            print(f"[CLEAN] {p}")
            try:
                os.remove(p)
            except Exception:
                pass

    # 清理 .spec 临时副本
    if os.path.exists(SPEC_ACTIVE):
        try:
            os.remove(SPEC_ACTIVE)
            print(f"[CLEAN] {SPEC_ACTIVE}")
        except Exception:
            pass


def _copy_spec():
    """把 MultiCalc.spec.txt 复制为 MultiCalc.spec（PyInstaller 需要）。"""
    if not os.path.exists(SPEC_IN):
        print(f"[ERROR] 找不到 {SPEC_IN}", file=sys.stderr)
        sys.exit(1)
    shutil.copyfile(SPEC_IN, SPEC_ACTIVE)
    print(f"[COPY] {SPEC_IN} -> {SPEC_ACTIVE}")


def _build(onedir: bool, no_upx: bool, debug: bool) -> int:
    """执行 PyInstaller。"""
    env = dict(os.environ)
    if onedir:
        env["MC_ONEDIR"] = "1"
    if no_upx:
        env["MC_NO_UPX"] = "1"
    if debug:
        env["MC_DEBUG"] = "1"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        SPEC_ACTIVE,
    ]
    print()
    print("=" * 60)
    print(" 构建命令：")
    print("   " + " ".join(cmd))
    print(" 环境变量：")
    for k in ("MC_ONEDIR", "MC_NO_UPX", "MC_DEBUG"):
        print(f"   {k}={env.get(k, '')}")
    print("=" * 60)
    print()

    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] 用户中断")
        return 130
    except Exception as e:
        print(f"[ERROR] 构建失败：{e}", file=sys.stderr)
        return 1

    return proc.returncode


def _report_output(onedir: bool):
    """报告产物大小。"""
    if onedir:
        dist_dir = os.path.join(ROOT, "dist", "MultiCalc")
        if not os.path.isdir(dist_dir):
            return
        total = 0
        for root, _dirs, files in os.walk(dist_dir):
            for f in files:
                try:
                    total += os.path.getsize(
                        os.path.join(root, f))
                except Exception:
                    pass
        mb = total / (1 << 20)
        print()
        print(f"[OK] 产物目录：{dist_dir}")
        print(f"[OK] 总大小：{mb:.1f} MiB")
    else:
        exe = os.path.join(ROOT, "dist", "MultiCalc.exe")
        if not os.path.exists(exe):
            exe = os.path.join(ROOT, "dist", "MultiCalc")
        if not os.path.exists(exe):
            return
        mb = os.path.getsize(exe) / (1 << 20)
        print()
        print(f"[OK] 产物：{exe}")
        print(f"[OK] 大小：{mb:.1f} MiB")


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MultiCalc 构建脚本")
    parser.add_argument("--onedir", action="store_true",
                        help="使用 onedir 模式（启动更快）")
    parser.add_argument("--no-upx", action="store_true",
                        help="关闭 UPX 压缩")
    parser.add_argument("--debug", action="store_true",
                        help="Debug 模式（保留控制台）")
    parser.add_argument("--clean", action="store_true",
                        help="清理构建产物后退出")
    parser.add_argument("--check", action="store_true",
                        help="只检查依赖")
    args = parser.parse_args()

    if args.check:
        ok = _check_dependencies()
        sys.exit(0 if ok else 1)

    if args.clean:
        _clean()
        print("[OK] 清理完成")
        sys.exit(0)

    # 检查依赖
    if not _check_dependencies():
        print()
        print("[WARN] 部分依赖缺失，构建可能失败")
        try:
            ans = input("继续？[y/N] ").strip().lower()
        except EOFError:
            ans = "n"
        if ans not in ("y", "yes"):
            sys.exit(1)

    # 清理旧产物
    _clean()

    # 复制 spec
    _copy_spec()

    # 构建
    code = _build(args.onedir, args.no_upx, args.debug)
    if code != 0:
        print(f"[FAIL] PyInstaller 退出码：{code}",
              file=sys.stderr)
        sys.exit(code)

    # 报告
    _report_output(args.onedir)

    # 清理临时 spec
    try:
        if os.path.exists(SPEC_ACTIVE):
            os.remove(SPEC_ACTIVE)
    except Exception:
        pass

    print()
    print("[OK] 构建完成")


if __name__ == "__main__":
    main()