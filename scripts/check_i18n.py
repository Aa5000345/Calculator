#!/usr/bin/env python
"""i18n 一致性检查。

校验内容：
1. config/i18n/ 下所有语言包 JSON 语法合法
2. 各语言包键集与基准语言（zh_CN）完全一致
3. 键值非空（空字符串视为未翻译）
4. 检查值里有未替换的 format 占位符不匹配（{k} 数量一致）

退出码：
  0 —— 全部通过
  1 —— 发现问题（CI 应视为失败）

用法：
  python scripts/check_i18n.py
  python scripts/check_i18n.py --base zh_CN      # 指定基准语言
  python scripts/check_i18n.py --strict          # 空值也视为错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def _repo_root() -> str:
    """返回项目根目录（scripts/ 的上一级）。"""
    return os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))


def _load_json(path: str) -> dict:
    """读 JSON 并检查重复键。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # 用 object_pairs_hook 检测重复键
    def _pairs(pairs):
        seen = set()
        for k, _ in pairs:
            if k in seen:
                raise ValueError(f"重复键: {k!r}")
            seen.add(k)
        return dict(pairs)

    return json.loads(text, object_pairs_hook=_pairs)


def _placeholders(s: str) -> list:
    return sorted(_PLACEHOLDER_RE.findall(str(s)))


# ---------------------------------------------------------------------------
# 主检查
# ---------------------------------------------------------------------------

def check(i18n_dir: str, base_lang: str, strict: bool) -> int:
    if not os.path.isdir(i18n_dir):
        print(f"[ERROR] 找不到 i18n 目录: {i18n_dir}", file=sys.stderr)
        return 1

    files = sorted(
        f for f in os.listdir(i18n_dir)
        if f.endswith(".json") and not f.startswith(".")
    )
    if not files:
        print(f"[ERROR] {i18n_dir} 下没有语言包", file=sys.stderr)
        return 1

    base_file = f"{base_lang}.json"
    if base_file not in files:
        print(f"[ERROR] 基准语言包不存在: {base_file}", file=sys.stderr)
        return 1

    # 加载所有语言包
    packages: dict = {}
    had_error = False

    for fn in files:
        path = os.path.join(i18n_dir, fn)
        try:
            data = _load_json(path)
        except json.JSONDecodeError as e:
            print(f"[ERROR] {fn} JSON 语法错误：{e}", file=sys.stderr)
            had_error = True
            continue
        except ValueError as e:
            print(f"[ERROR] {fn} 结构问题：{e}", file=sys.stderr)
            had_error = True
            continue

        if not isinstance(data, dict):
            print(f"[ERROR] {fn} 顶层必须是对象", file=sys.stderr)
            had_error = True
            continue

        packages[fn] = data

    if had_error:
        return 1

    base = packages.get(base_file, {})
    base_keys = set(base.keys())
    print(f"基准语言：{base_file}（{len(base_keys)} 个键）")
    print()

    # 逐个语言包对比
    for fn in files:
        if fn == base_file:
            continue
        other = packages[fn]
        other_keys = set(other.keys())

        missing = sorted(base_keys - other_keys)
        extra = sorted(other_keys - base_keys)

        issues = []

        if missing:
            issues.append(f"缺少 {len(missing)} 个键")
        if extra:
            issues.append(f"多出 {len(extra)} 个键")

        # 占位符检查
        placeholder_mismatch = []
        for k in base_keys & other_keys:
            ph_base = _placeholders(base[k])
            ph_other = _placeholders(other[k])
            if ph_base != ph_other:
                placeholder_mismatch.append(
                    (k, ph_base, ph_other))

        if placeholder_mismatch:
            issues.append(
                f"占位符不匹配 {len(placeholder_mismatch)} 个")

        # 空值检查
        empty = []
        if strict:
            for k, v in other.items():
                if not str(v).strip():
                    empty.append(k)
            if empty:
                issues.append(f"空值 {len(empty)} 个")

        if not issues:
            print(f"[OK]   {fn}（{len(other_keys)} 个键）")
            continue

        print(f"[FAIL] {fn}（{len(other_keys)} 个键）")
        for issue in issues:
            print(f"       - {issue}")

        if missing:
            print(f"       ✗ 缺少：")
            for k in missing[:30]:
                print(f"           - {k}")
            if len(missing) > 30:
                print(f"           ... 还有 {len(missing) - 30} 个")
        if extra:
            print(f"       ✗ 多出：")
            for k in extra[:30]:
                print(f"           + {k}")
            if len(extra) > 30:
                print(f"           ... 还有 {len(extra) - 30} 个")
        if placeholder_mismatch:
            print(f"       ✗ 占位符不匹配：")
            for k, a, b in placeholder_mismatch[:10]:
                print(f"           - {k}: base={a}  other={b}")
        if empty:
            print(f"       ✗ 空值：")
            for k in empty[:20]:
                print(f"           - {k}")

        had_error = True
        print()

    if had_error:
        print("i18n 一致性检查未通过")
        return 1

    print("i18n 一致性检查全部通过 ✓")
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MultiCalc i18n 一致性检查")
    parser.add_argument(
        "--base", default="zh_CN",
        help="基准语言（默认 zh_CN）")
    parser.add_argument(
        "--i18n-dir", default=None,
        help="i18n 目录（默认 <repo>/config/i18n）")
    parser.add_argument(
        "--strict", action="store_true",
        help="空值也视为错误")
    args = parser.parse_args()

    root = _repo_root()
    i18n_dir = args.i18n_dir or os.path.join(root, "config", "i18n")

    sys.exit(check(i18n_dir, args.base, args.strict))


if __name__ == "__main__":
    main()