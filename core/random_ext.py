"""随机扩展：种子 / 分布 / 洗牌 / 抽样 / UUID / 密码。"""
from __future__ import annotations

import random
import secrets
import string
import uuid

from core.errors import InputError


_PW_SAFE = string.ascii_letters + string.digits
_PW_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>/?"


def make_rng(seed=None):
    if seed in (None, "", "random"):
        return random.Random()
    try:
        return random.Random(int(seed))
    except (TypeError, ValueError):
        return random.Random(str(seed))


def distribution_sample(kind: str, n: int, params: dict, seed=None):
    """按分布抽样。kind: uniform | normal | exponential | int | choice。"""
    n = int(n)
    if n <= 0:
        raise InputError("数量必须大于 0", friendly_key="err_input")
    rng = make_rng(seed)

    if kind == "uniform":
        lo = float(params.get("low", 0))
        hi = float(params.get("high", 1))
        if lo > hi:
            raise InputError("low > high", friendly_key="err_input")
        return [rng.uniform(lo, hi) for _ in range(n)]
    if kind == "normal":
        mu = float(params.get("mu", 0))
        sigma = float(params.get("sigma", 1))
        if sigma <= 0:
            raise InputError("sigma 必须大于 0", friendly_key="err_input")
        return [rng.gauss(mu, sigma) for _ in range(n)]
    if kind == "exponential":
        lam = float(params.get("lambda", 1))
        if lam <= 0:
            raise InputError("lambda 必须大于 0", friendly_key="err_input")
        return [rng.expovariate(lam) for _ in range(n)]
    if kind == "int":
        lo = int(params.get("low", 0))
        hi = int(params.get("high", 100))
        if lo > hi:
            raise InputError("low > high", friendly_key="err_input")
        return [rng.randint(lo, hi) for _ in range(n)]
    if kind == "choice":
        pool = params.get("pool") or []
        if not pool:
            raise InputError("候选池为空", friendly_key="err_input")
        return [rng.choice(pool) for _ in range(n)]
    raise InputError(f"未知分布：{kind}", friendly_key="err_input")


def shuffle_list(items, seed=None):
    arr = list(items)
    rng = make_rng(seed)
    rng.shuffle(arr)
    return arr


def sample_from_list(items, k, replace=False, seed=None):
    arr = list(items)
    k = int(k)
    if k < 0 or (not replace and k > len(arr)):
        raise InputError("抽样数量非法", friendly_key="err_input")
    rng = make_rng(seed)
    if replace:
        return [rng.choice(arr) for _ in range(k)]
    return rng.sample(arr, k)


def uuid_list(n=1, version=4):
    n = int(n)
    if n <= 0:
        raise InputError("数量必须大于 0", friendly_key="err_input")
    out = []
    for _ in range(n):
        if version == 1:
            out.append(str(uuid.uuid1()))
        elif version == 3:
            out.append(str(uuid.uuid3(uuid.NAMESPACE_DNS, secrets.token_hex(8))))
        elif version == 5:
            out.append(str(uuid.uuid5(uuid.NAMESPACE_DNS, secrets.token_hex(8))))
        else:
            out.append(str(uuid.uuid4()))
    return out


def password_gen(length=16, upper=True, lower=True, digits=True,
                 symbols=False, exclude_ambiguous=False):
    length = int(length)
    if length < 4:
        raise InputError("密码长度至少 4", friendly_key="err_input")
    pools = []
    if upper:
        pools.append(string.ascii_uppercase)
    if lower:
        pools.append(string.ascii_lowercase)
    if digits:
        pools.append(string.digits)
    if symbols:
        pools.append(_PW_SYMBOLS)
    if not pools:
        raise InputError("至少启用一类字符", friendly_key="err_input")

    if exclude_ambiguous:
        amb = "Il1O0"
        pools = ["".join(c for c in p if c not in amb) for p in pools]

    rng = secrets.SystemRandom()
    # 保证每类至少一个
    pw = [rng.choice(p) for p in pools]
    all_chars = "".join(pools)
    while len(pw) < length:
        pw.append(rng.choice(all_chars))
    rng.shuffle(pw)
    return "".join(pw)