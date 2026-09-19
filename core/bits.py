"""位运算 / CRC / 哈希 / 位图可视化。

合并自：core/bits.py + core/bits_ext.py

对外接口：
    # 位运算
    to_unsigned, to_signed, twos_complement, bit_bin, bit_hex, bit_op
    # CRC
    crc32, crc16
    # Hash
    hash_text
    # 位图
    int_to_bitmap, bytes_to_bitmap
"""
from __future__ import annotations

import hashlib
import zlib

from core.base import InputError


__all__ = [
    "to_unsigned", "to_signed", "twos_complement",
    "bit_bin", "bit_hex", "bit_op",
    "crc32", "crc16", "hash_text",
    "int_to_bitmap", "bytes_to_bitmap",
]


# ===========================================================================
# 位运算
# ===========================================================================

def _mask(width: int) -> int:
    return (1 << width) - 1


def to_unsigned(value, width):
    return int(value) & _mask(width)


def to_signed(value, width):
    v = int(value) & _mask(width)
    if v & (1 << (width - 1)):
        v -= (1 << width)
    return v


def twos_complement(value, width):
    return to_signed(value, width)


def bit_bin(value, width):
    return format(int(value) & _mask(width), f"0{width}b")


def bit_hex(value, width):
    return format(int(value) & _mask(width), f"0{(width + 3) // 4}X")


def bit_op(a, b, op, width=32):
    a, b = to_unsigned(a, width), to_unsigned(b, width)
    if op == "and":
        r = a & b
    elif op == "or":
        r = a | b
    elif op == "xor":
        r = a ^ b
    elif op == "not":
        r = (~a) & _mask(width)
    elif op == "shl":
        r = (a << b) & _mask(width)
    elif op == "shr":
        r = (a >> b) & _mask(width)
    else:
        raise ValueError(f"未知运算：{op}")
    return r


# ===========================================================================
# CRC
# ===========================================================================

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


# ===========================================================================
# Hash
# ===========================================================================

def hash_text(text: str, algo: str = "sha256", upper=True) -> dict:
    algo = algo.lower()
    table = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha224": hashlib.sha224,
        "sha256": hashlib.sha256,
        "sha384": hashlib.sha384,
        "sha512": hashlib.sha512,
        "sha3_256": hashlib.sha3_256,
        "sha3_512": hashlib.sha3_512,
        "blake2b": hashlib.blake2b,
        "blake2s": hashlib.blake2s,
    }
    h = table.get(algo)
    if h is None:
        raise InputError(f"未知哈希算法：{algo}",
                         friendly_key="err_input")

    digest = h(str(text).encode("utf-8")).hexdigest()
    if upper:
        digest = digest.upper()
    return {"algo": algo, "digest": digest}


# ===========================================================================
# 位图可视化
# ===========================================================================

def int_to_bitmap(value, width: int = 32) -> dict:
    """把整数按位展开为二维 bit 网格。

    返回 {'width', 'cols', 'rows', 'bits'}。
    默认宽 = 位宽；宽 > 64 时自动换行成方阵。
    """
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise InputError("不是合法整数", friendly_key="err_input")
    w = int(width)
    if w <= 0 or w > 4096:
        raise InputError("位宽范围 1~4096",
                         friendly_key="err_input")

    bits = [(v >> (w - 1 - i)) & 1 for i in range(w)]

    if w <= 64:
        cols = w
    else:
        import math
        cols = int(math.ceil(math.sqrt(w)))
    rows = (w + cols - 1) // cols
    while len(bits) < rows * cols:
        bits.append(0)
    grid = [bits[i * cols:(i + 1) * cols] for i in range(rows)]
    return {"width": w, "cols": cols, "rows": rows, "bits": grid}


def bytes_to_bitmap(data: bytes, width: int = 8) -> dict:
    if width not in (8, 16, 32):
        width = 8
    v = (int.from_bytes(data, "big", signed=False)
         if data else 0)
    return int_to_bitmap(v, len(data) * 8)