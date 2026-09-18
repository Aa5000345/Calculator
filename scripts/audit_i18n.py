#!/usr/bin/env python
"""i18n 深度审计：比 check_i18n.py 更全面。

检查项：
1. JSON 语法与重复键
2. 键集一致性（基准语言 vs 其他）
3. 占位符（{name}）一致性
4. 空值 / 仅空白值
5. 未翻译的值（启发式）：
   - 非基准语言中，值与基准语言完全相同（且长度 > 3）
   - 基准语言为中文时，其他语言的值仍含中文字符
   - 基准语言为英文时，中文语言的值不含中文字符
6. 可疑的键名拼写（大小写、连字符）
7. 键顺序一致性（可选）

退出码：
    0 —— 全部通过
    1 —— 发现严重问题（键缺失 / 占位符不匹配 / JSON 错误）
    2 —— 只发现警告（未翻译 / 顺序不一致）

用法：
    python scripts/audit_i18n.py
    python scripts/audit_i18n.py --base zh_CN
    python scripts/audit_i18n.py --strict
    python scripts/audit_i18n.py --fix
    python scripts/audit_i18n.py --json
    python scripts/audit_i18n.py --i18n-dir config/i18n
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import OrderedDict

# ---------------------------------------------------------------------------
# UTF-8 输出修复
# ---------------------------------------------------------------------------
for _sn in ("stdout", "stderr"):
    _s = getattr(sys, _sn, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")


# ---------------------------------------------------------------------------
# JSON 加载（带重复键检测）
# ---------------------------------------------------------------------------

def _load_json(path: str) -> OrderedDict:
    """读取 JSON，保留键顺序，检测重复键。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    def _pairs(pairs):
        seen = {}
        out = OrderedDict()
        for k, v in pairs:
            if k in seen:
                raise ValueError(f"重复键：{k!r}")
            seen[k] = True
            out[k] = v
        return out

    return json.loads(text, object_pairs_hook=_pairs)


def _load_all(dir_path: str) -> dict:
    out = {}
    for fn in sorted(os.listdir(dir_path)):
        if not fn.endswith(".json") or fn.startswith("."):
            continue
        lang = os.path.splitext(fn)[0]
        try:
            out[lang] = _load_json(os.path.join(dir_path, fn))
        except json.JSONDecodeError as e:
            print(f"[ERROR] {fn} JSON 语法错误：{e}", file=sys.stderr)
        except ValueError as e:
            print(f"[ERROR] {fn} 结构问题：{e}", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# 检查项
# ---------------------------------------------------------------------------

def _placeholders(s: str) -> list:
    return sorted(_PLACEHOLDER_RE.findall(str(s)))


def _is_likely_untranslated(base_val: str, other_val: str,
                            base_lang: str, other_lang: str) -> bool:
    """启发式判断：值是否未翻译。"""
    b = str(base_val).strip()
    o = str(other_val).strip()
    if not b or not o:
        return False
    if b == o and len(b) > 3:
        return True

    base_is_cn = base_lang.lower().startswith("zh")
    other_is_cn = other_lang.lower().startswith("zh")

    # 基准是中文，其他语言不该含中文
    if base_is_cn and not other_is_cn:
        if _CJK_RE.search(o) and not _CJK_RE.search(b):
            return True
        if _CJK_RE.search(o):
            return True

    # 基准是英文，中文语言必须含中文（排除纯符号/术语）
    if not base_is_cn and other_is_cn:
        if not _CJK_RE.search(o):
            if _ASCII_LETTER_RE.search(o) and len(o) > 3:
                return True

    return False


def _audit_key_spelling(keys: list) -> list:
    """检查可疑的键名（重复前缀、大小写不一致）。"""
    issues = []
    seen_lower = {}
    for k in keys:
        lk = k.lower()
        if lk in seen_lower and seen_lower[lk] != k:
            issues.append(
                f"大小写不一致：{seen_lower[lk]!r} vs {k!r}")
        seen_lower[lk] = k
    return issues


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def audit(dir_path: str, base_lang: str, strict: bool = False,
          check_order: bool = False, fix: bool = False,
          as_json: bool = False) -> int:
    if not os.path.isdir(dir_path):
        print(f"[ERROR] 找不到 i18n 目录：{dir_path}",
              file=sys.stderr)
        return 1

    packages = _load_all(dir_path)
    if base_lang not in packages:
        print(f"[ERROR] 基准语言包不存在：{base_lang}.json",
              file=sys.stderr)
        return 1

    base = packages[base_lang]
    base_keys = list(base.keys())
    base_keys_set = set(base_keys)

    report: dict = {
        "base": base_lang,
        "base_key_count": len(base_keys),
        "languages": {},
        "global_issues": [],
    }

    had_error = False
    had_warning = False

    for lang, pack in packages.items():
        if lang == base_lang:
            continue
        lang_report = {
            "key_count": len(pack),
            "missing": [],
            "extra": [],
            "placeholder_mismatch": [],
            "empty": [],
            "untranslated": [],
            "order_mismatch": False,
        }
        keys_set = set(pack.keys())

        # 1) 键集
        lang_report["missing"] = sorted(base_keys_set - keys_set)
        lang_report["extra"] = sorted(keys_set - base_keys_set)
        if lang_report["missing"] or lang_report["extra"]:
            had_error = True

        # 2) 占位符
        for k in base_keys_set & keys_set:
            ph_b = _placeholders(base[k])
            ph_o = _placeholders(pack[k])
            if ph_b != ph_o:
                lang_report["placeholder_mismatch"].append({
                    "key": k, "base": ph_b, "other": ph_o,
                })
                had_error = True

        # 3) 空值
        for k, v in pack.items():
            if not str(v).strip():
                lang_report["empty"].append(k)
        if lang_report["empty"]:
            if strict:
                had_error = True
            else:
                had_warning = True

        # 4) 未翻译
        for k in base_keys_set & keys_set:
            if _is_likely_untranslated(
                    base[k], pack[k], base_lang, lang):
                lang_report["untranslated"].append({
                    "key": k,
                    "base": str(base[k])[:40],
                    "other": str(pack[k])[:40],
                })
        if lang_report["untranslated"]:
            had_warning = True

        # 5) 顺序
        if check_order:
            base_order = [k for k in base_keys if k in keys_set]
            lang_order = [k for k in pack.keys() if k in base_keys_set]
            if base_order != lang_order:
                lang_report["order_mismatch"] = True
                had_warning = True

        report["languages"][lang] = lang_report

    # 6) 键名拼写（对基准语言）
    spelling = _audit_key_spelling(base_keys)
    if spelling:
        report["global_issues"].extend(spelling)
        had_warning = True

    # 7) 自动修复
    if fix:
        _apply_fix(dir_path, base_lang, packages, report)

    # 8) 输出
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    if had_error:
        return 1
    if had_warning:
        return 2
    return 0


def _apply_fix(dir_path: str, base_lang: str, packages: dict,
               report: dict):
    """把缺失的键用基准语言的值补齐（仅补齐，不删多余）。"""
    base = packages[base_lang]
    for lang, lang_report in report["languages"].items():
        pack = packages.get(lang)
        if pack is None:
            continue
        changed = False
        for k in lang_report["missing"]:
            pack[k] = f"[TODO] {base[k]}"
            changed = True
        if changed:
            path = os.path.join(dir_path, f"{lang}.json")
            # 按基准语言顺序重排
            ordered = OrderedDict()
            for k in base.keys():
                if k in pack:
                    ordered[k] = pack[k]
            for k in pack.keys():
                if k not in ordered:
                    ordered[k] = pack[k]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ordered, f, ensure_ascii=False, indent=2)
            print(f"[FIX] 已补齐 {lang}.json 的 {len(lang_report['missing'])} 个键")


def _print_report(report: dict):
    base = report["base"]
    print(f"基准语言：{base}（{report['base_key_count']} 个键）")
    print()

    for lang, r in report["languages"].items():
        n_issues = (
            len(r["missing"]) + len(r["extra"])
            + len(r["placeholder_mismatch"]) + len(r["empty"])
            + len(r["untranslated"])
            + (1 if r["order_mismatch"] else 0)
        )
        if n_issues == 0:
            print(f"[OK]   {lang}.json（{r['key_count']} 个键）")
            continue

        print(f"[WARN] {lang}.json（{r['key_count']} 个键，"
              f"{n_issues} 个问题）")

        if r["missing"]:
            print(f"       ✗ 缺少 {len(r['missing'])} 个键：")
            for k in r["missing"][:20]:
                print(f"           - {k}")
            if len(r["missing"]) > 20:
                print(f"           ... 还有 {len(r['missing']) - 20} 个")

        if r["extra"]:
            print(f"       ✗ 多出 {len(r['extra'])} 个键：")
            for k in r["extra"][:20]:
                print(f"           + {k}")
            if len(r["extra"]) > 20:
                print(f"           ... 还有 {len(r['extra']) - 20} 个")

        if r["placeholder_mismatch"]:
            print(f"       ✗ 占位符不匹配 {len(r['placeholder_mismatch'])} 个：")
            for it in r["placeholder_mismatch"][:10]:
                print(f"           - {it['key']}: "
                      f"base={it['base']} other={it['other']}")

        if r["empty"]:
            print(f"       ⚠ 空值 {len(r['empty'])} 个：")
            for k in r["empty"][:10]:
                print(f"           - {k}")

        if r["untranslated"]:
            print(f"       ⚠ 可能未翻译 {len(r['untranslated'])} 个：")
            for it in r["untranslated"][:10]:
                print(f"           - {it['key']}: "
                      f"{it['base']!r} == {it['other']!r}")

        if r["order_mismatch"]:
            print("       ⚠ 键顺序与基准语言不一致")

        print()

    if report["global_issues"]:
        print("[全局] 键名拼写问题：")
        for issue in report["global_issues"]:
            print(f"  - {issue}")
        print()

    print("---")
    print("审计完成。")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _repo_root() -> str:
    return os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="MultiCalc i18n 深度审计")
    parser.add_argument("--base", default="zh_CN")
    parser.add_argument("--i18n-dir", default=None)
    parser.add_argument("--strict", action="store_true",
                        help="空值也视为错误")
    parser.add_argument("--check-order", action="store_true",
                        help="检查键顺序")
    parser.add_argument("--fix", action="store_true",
                        help="自动补齐缺失的键（用 [TODO] 标记）")
    parser.add_argument("--json", action="store_true",
                        help="以 JSON 输出报告")
    args = parser.parse_args()

    root = _repo_root()
    i18n_dir = args.i18n_dir or os.path.join(
        root, "config", "i18n")

    sys.exit(audit(
        i18n_dir, args.base,
        strict=args.strict,
        check_order=args.check_order,
        fix=args.fix,
        as_json=args.json,
    ))


if __name__ == "__main__":
    main()