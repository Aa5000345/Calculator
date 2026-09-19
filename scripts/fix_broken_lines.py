#!/usr/bin/env python
"""修复 "import 语句与后续代码被空格粘在一行" 的问题。

问题模式（换行丢失）：
    from ui.widgets.dialogs import ShortcutEditor            self.editor = ShortcutEditor(
    from ui.widgets.dialogs import (                Shortcut...

修复后：
    from ui.widgets.dialogs import ShortcutEditor
    self.editor = ShortcutEditor(

    from ui.widgets.dialogs import (
        Shortcut...

用法：
    python scripts/fix_broken_lines.py              # dry-run
    python scripts/fix_broken_lines.py --apply      # 真正修复
"""
from __future__ import annotations

import argparse
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# 匹配：<缩进><import 语句><4+ 空格><非空字符...>
# import 语句部分：
#   - `from a.b.c import d`（可能以 `(` 结尾）
#   - `import a.b.c`
PATTERN = re.compile(
    r'^(\s*)'                           # 缩进
    r'('
    r'from\s+[\w.]+\s+import\s+(?:\(|[^,\s]+)'  # from X import Y 或 (
    r'|import\s+[\w.]+'                # import X
    r')'
    r'(\s{4,})'                        # 4+ 空格
    r'(\S.*?)$'                        # 剩余非空内容
)


def fix_line(line: str) -> str | None:
    """如果该行需要修复，返回修复后的多行文本（保留原行尾符）。"""
    raw = line.rstrip("\r\n")
    nl = line[len(raw):] or "\n"

    m = PATTERN.match(raw)
    if not m:
        return None

    indent, stmt, _spaces, rest = m.groups()
    return f"{indent}{stmt}{nl}{indent}{rest}{nl}"


def process_file(path: str, apply: bool) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return 0

    # 循环拆分，直到没有可拆的行
    n_fixed = 0
    while True:
        lines = text.splitlines(keepends=True)
        out_lines = []
        changed = False
        for ln in lines:
            fixed = fix_line(ln)
            if fixed is None:
                out_lines.append(ln)
            else:
                out_lines.append(fixed)
                n_fixed += 1
                changed = True
        text = "".join(out_lines)
        if not changed:
            break

    if n_fixed and apply:
        try:
            with open(path, "w", encoding="utf-8",
                      newline="") as f:
                f.write(text)
        except Exception as e:
            print(f"[ERROR] 写入失败 {path}: {e}",
                  file=sys.stderr)
            return 0

    return n_fixed


def iter_py_files(root: str):
    skip = {"__pycache__", ".git", ".venv", "venv",
            "build", "dist"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def main():
    parser = argparse.ArgumentParser(
        description="修复换行丢失的 import 行")
    parser.add_argument("--apply", action="store_true",
                        help="真正写入；默认 dry-run")
    parser.add_argument("--path", default=None,
                        help="只处理指定目录（默认 core/ 与 ui/）")
    args = parser.parse_args()

    repo = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))

    if args.path:
        roots = [args.path]
    else:
        roots = [os.path.join(repo, "core"),
                 os.path.join(repo, "ui")]

    n_files = 0
    n_lines = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        for p in iter_py_files(root):
            n = process_file(p, args.apply)
            if n:
                n_files += 1
                n_lines += n
                print(f"[{'FIX' if args.apply else 'DRY'}] "
                      f"{os.path.relpath(p, repo)}  "
                      f"({n} 处)")

    print()
    print(f"共 {n_files} 个文件，{n_lines} 处待修复。")
    if not args.apply and n_lines:
        print("提示：加 --apply 参数才会真正写入。")


if __name__ == "__main__":
    main()