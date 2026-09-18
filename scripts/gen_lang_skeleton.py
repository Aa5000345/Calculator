#!/usr/bin/env python
"""语言包骨架生成器：从基准语言生成新语言的空骨架。

用法：
    # 从 zh_CN 生成 ja_JP 骨架
    python scripts/gen_lang_skeleton.py --base zh_CN --target ja_JP

    # 从 en_US 生成 zh_TW 骨架
    python scripts/gen_lang_skeleton.py --base en_US --target zh_TW

    # 强制覆盖已存在的文件
    python scripts/gen_lang_skeleton.py --base zh_CN --target ko_KR --force

生成的骨架：
    - key 集与基准一致
    - 值形如 "[TODO] <基准语言的值>"，便于翻译时对照
"""
from __future__ import annotations

import argparse
import json
import os
import sys


for _sn in ("stdout", "stderr"):
    _s = getattr(sys, _sn, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _repo_root() -> str:
    return os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=dict)


def gen_skeleton(base_path: str, target_path: str,
                 base_lang: str, force: bool = False) -> bool:
    if os.path.exists(target_path) and not force:
        print(f"[SKIP] 已存在：{target_path}")
        print("       如需覆盖，加 --force")
        return False

    base = _load(base_path)
    out = {}
    for k, v in base.items():
        if not str(v).strip():
            out[k] = f"[TODO] {k}"
        else:
            out[k] = f"[TODO] {v}"

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] 生成 {target_path}")
    print(f"     共 {len(out)} 个 key，请手动替换 [TODO] 前缀")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="MultiCalc 语言包骨架生成器")
    parser.add_argument("--base", default="zh_CN",
                        help="基准语言（默认 zh_CN）")
    parser.add_argument("--target", required=True,
                        help="目标语言代码（如 ja_JP）")
    parser.add_argument("--i18n-dir", default=None,
                        help="i18n 目录")
    parser.add_argument("--force", action="store_true",
                        help="覆盖已存在的文件")
    args = parser.parse_args()

    root = _repo_root()
    i18n_dir = args.i18n_dir or os.path.join(
        root, "config", "i18n")

    base_path = os.path.join(i18n_dir, f"{args.base}.json")
    target_path = os.path.join(
        i18n_dir, f"{args.target}.json")

    if not os.path.exists(base_path):
        print(f"[ERROR] 基准语言不存在：{base_path}",
              file=sys.stderr)
        sys.exit(1)

    ok = gen_skeleton(base_path, target_path,
                      args.base, force=args.force)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()