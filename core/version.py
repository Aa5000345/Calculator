"""语义化版本号解析与比较。

支持格式：
    X.Y.Z
    X.Y.Z-pre
    X.Y.Z-pre.N
    X.Y.Z+build
    X.Y.Z-pre.N+build

排序规则（遵循 semver 2.0 简化版）：
    1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-beta < 1.0.0-rc.1 < 1.0.0

对外接口：
    parse(v) -> Version
    compare(a, b) -> int  (-1 / 0 / 1)
    is_newer(latest, current) -> bool
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


_VERSION_RE = re.compile(
    r"^\s*v?"
    r"(?P<major>\d+)"
    r"(?:\.(?P<minor>\d+))?"
    r"(?:\.(?P<patch>\d+))?"
    r"(?:[-_](?P<pre>[0-9A-Za-z.\-]+))?"
    r"(?:\+(?P<meta>[0-9A-Za-z.\-]+))?"
    r"\s*$"
)


@dataclass
class Version:
    major: int = 0
    minor: int = 0
    patch: int = 0
    pre: tuple = ()
    meta: str = ""
    raw: str = ""

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            s += "-" + ".".join(str(x) for x in self.pre)
        if self.meta:
            s += "+" + self.meta
        return s

    def to_tuple(self) -> tuple:
        """用于直接比较的元组（不含 pre / meta）。"""
        return (self.major, self.minor, self.patch)


def _parse_pre(s: str) -> tuple:
    """把 pre-release 字符串拆成 (type_rank, parts) 元组。

    type_rank:
        0 = alpha
        1 = beta
        2 = rc
        3 = 其它
    """
    if not s:
        return ()
    parts = []
    lower = s.lower()
    if lower.startswith("alpha") or lower.startswith("a"):
        rank = 0
        rest = s[5:] if lower.startswith("alpha") else s[1:]
    elif lower.startswith("beta") or lower.startswith("b"):
        rank = 1
        rest = s[4:] if lower.startswith("beta") else s[1:]
    elif lower.startswith("rc"):
        rank = 2
        rest = s[2:]
    else:
        rank = 3
        rest = s

    nums = []
    for seg in rest.replace("-", ".").split("."):
        seg = seg.strip()
        if not seg:
            continue
        try:
            nums.append(int(seg))
        except ValueError:
            nums.append(seg)
    return (rank, tuple(nums))


def parse(v) -> Version:
    """把字符串解析为 Version。

    无法识别的返回 Version(0,0,0)，raw 保留原字符串。
    """
    s = str(v or "").strip()
    m = _VERSION_RE.match(s)
    if not m:
        return Version(raw=s)
    return Version(
        major=int(m.group("major") or 0),
        minor=int(m.group("minor") or 0),
        patch=int(m.group("patch") or 0),
        pre=_parse_pre(m.group("pre") or ""),
        meta=m.group("meta") or "",
        raw=s,
    )


def compare(a, b) -> int:
    """比较两个版本。

    返回：
        -1 —— a < b
         0 —— a == b
         1 —— a > b
    """
    va = a if isinstance(a, Version) else parse(a)
    vb = b if isinstance(b, Version) else parse(b)

    # 主版本
    ta = va.to_tuple()
    tb = vb.to_tuple()
    if ta < tb:
        return -1
    if ta > tb:
        return 1

    # 预发布：无 pre > 有 pre
    if not va.pre and not vb.pre:
        return 0
    if not va.pre:
        return 1
    if not vb.pre:
        return -1

    # 都有 pre：比较 rank 和 parts
    ra, pa = va.pre
    rb, pb = vb.pre
    if ra != rb:
        return -1 if ra < rb else 1
    if pa == pb:
        return 0
    # 逐项比较
    for x, y in zip(pa, pb):
        if type(x) is type(y):
            if x < y:
                return -1
            if x > y:
                return 1
        else:
            # 数字 < 字符串（semver 规则）
            if isinstance(x, int) and isinstance(y, str):
                return -1
            if isinstance(x, str) and isinstance(y, int):
                return 1
            xs, ys = str(x), str(y)
            if xs < ys:
                return -1
            if xs > ys:
                return 1
    if len(pa) < len(pb):
        return -1
    if len(pa) > len(pb):
        return 1
    return 0


def is_newer(latest, current) -> bool:
    """latest 是否比 current 新。"""
    return compare(latest, current) > 0


__all__ = ["Version", "parse", "compare", "is_newer"]