"""位运算扩展：CRC / 哈希 / 位图可视化。"""
from __future__ import annotations

import hashlib
import zlib

from core.errors import InputError


# ---------------- CRC ----------------

def _crc16_ccitt(data: bytes, poly=0x1021, init=0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def crc32(text: str) -> dict:
    data = str(text).encode("utf-8")
    v = zlib.crc32(data) & 0xFFFFFFFF
    return {"crc32": v, "hex": f"0x{v:08X}"}


def crc16(text: str, kind: str = "ccitt") -> dict:
    data = str(text).encode("utf-8")
    if kind == "modbus":
        v = _crc16_modbus(data)
    else:
        v = _crc16_ccitt(data)
    return {f"crc16_{kind}": v, "hex": f"0x{v:04X}"}


# ---------------- Hash ----------------

def hash_text(text: str, algo: str = "sha256", upper=True) -> dict:
    algo = algo.lower()
    if algo == "md5":
        h = hashlib.md5
    elif algo == "sha1":
        h = hashlib.sha1
    elif algo == "sha224":
        h = hashlib.sha224
    elif algo == "sha256":
        h = hashlib.sha256
    elif algo == "sha384":
        h = hashlib.sha384
    elif algo == "sha512":
        h = hashlib.sha512
    elif algo == "sha3_256":
        h = hashlib.sha3_256
    elif algo == "sha3_512":
        h = hashlib.sha3_512
    elif algo == "blake2b":
        h = hashlib.blake2b
    elif algo == "blake2s":
        h = hashlib.blake2s
    else:
        raise InputError(f"未知哈希算法：{algo}", friendly_key="err_input")

    digest = h(str(text).encode("utf-8")).hexdigest()
    if upper:
        digest = digest.upper()
    return {"algo": algo, "digest": digest}


# ---------------- 位图可视化 ----------------

def int_to_bitmap(value, width: int = 32) -> dict:
    """把整数按位展开为二维 bit 网格（用于可视化）。

    返回 {'width': W, 'rows': R, 'bits': [[0/1, ...], ...]}。
    默认宽 = 位宽，行 = 1（单行）；宽 > 64 时自动换行成方阵。
    """
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise InputError("不是合法整数", friendly_key="err_input")
    w = int(width)
    if w <= 0 or w > 4096:
        raise InputError("位宽范围 1~4096", friendly_key="err_input")

    bits = [(v >> (w - 1 - i)) & 1 for i in range(w)]

    # 决定列数：优先 32 列；否则用 sqrt
    if w <= 64:
        cols = w
    else:
        import math
        cols = int(math.ceil(math.sqrt(w)))
    rows = (w + cols - 1) // cols
    # 补齐
    while len(bits) < rows * cols:
        bits.append(0)
    grid = [bits[i * cols:(i + 1) * cols] for i in range(rows)]
    return {"width": w, "cols": cols, "rows": rows, "bits": grid}


def bytes_to_bitmap(data: bytes, width: int = 8) -> dict:
    """把字节序列逐位展开。"""
    if width not in (8, 16, 32):
        width = 8
    v = int.from_bytes(data, "big", signed=False) if data else 0
    return int_to_bitmap(v, len(data) * 8)