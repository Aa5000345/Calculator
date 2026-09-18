"""加密工具核心：编码 / 哈希 / HMAC / AES / RSA / TOTP / 密码强度。

变更历史：
- 第 3 轮：初版
- 第 8 轮：末尾追加 Base58 / Base32 / Base85 / Ascii85 转发
         （实际实现见 core.crypto_advanced）
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import math
import os
import secrets
import struct
import time
import urllib.parse

from core.errors import InputError


# ===========================================================================
# 编码（Base64 / Hex / URL / HTML）
# ===========================================================================

def b64_encode(text, url_safe=False):
    data = str(text).encode("utf-8")
    if url_safe:
        return base64.urlsafe_b64encode(data).decode("ascii")
    return base64.b64encode(data).decode("ascii")


def b64_decode(text, url_safe=False):
    try:
        s = str(text).strip()
        pad = (-len(s)) % 4
        s += "=" * pad
        data = (base64.urlsafe_b64decode(s) if url_safe
                else base64.b64decode(s))
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        raise InputError(f"Base64 解码失败：{e}",
                         friendly_key="err_input")


def hex_encode(text, upper=True, sep=""):
    data = str(text).encode("utf-8")
    h = data.hex()
    if upper:
        h = h.upper()
    if sep:
        return sep.join(h[i:i + 2]
                        for i in range(0, len(h), 2))
    return h


def hex_decode(text):
    s = (str(text).strip()
         .replace(" ", "").replace(":", "").replace("-", ""))
    if s.lower().startswith("0x"):
        s = s[2:]
    try:
        data = bytes.fromhex(s)
    except Exception as e:
        raise InputError(f"Hex 解码失败：{e}",
                         friendly_key="err_input")
    return data.decode("utf-8", errors="replace")


def url_encode(text):
    return urllib.parse.quote(str(text), safe="")


def url_decode(text):
    return urllib.parse.unquote(str(text))


def html_encode(text):
    return html.escape(str(text))


def html_decode(text):
    return html.unescape(str(text))


# ===========================================================================
# 经典密码
# ===========================================================================

def rot13(text):
    res = []
    for ch in str(text):
        if 'a' <= ch <= 'z':
            res.append(chr((ord(ch) - ord('a') + 13) % 26
                           + ord('a')))
        elif 'A' <= ch <= 'Z':
            res.append(chr((ord(ch) - ord('A') + 13) % 26
                           + ord('A')))
        else:
            res.append(ch)
    return "".join(res)


def caesar(text, shift):
    n = int(shift) % 26
    res = []
    for ch in str(text):
        if 'a' <= ch <= 'z':
            res.append(chr((ord(ch) - ord('a') + n) % 26
                           + ord('a')))
        elif 'A' <= ch <= 'Z':
            res.append(chr((ord(ch) - ord('A') + n) % 26
                           + ord('A')))
        else:
            res.append(ch)
    return "".join(res)


# ===========================================================================
# 哈希 / HMAC
# ===========================================================================

_HASHLIB_ALGOS = {
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


def hash_text(text, algo="sha256", upper=True):
    algo = algo.lower()
    if algo not in _HASHLIB_ALGOS:
        raise InputError(f"未知哈希算法：{algo}",
                         friendly_key="err_input")
    h = _HASHLIB_ALGOS[algo](
        str(text).encode("utf-8")).hexdigest()
    if upper:
        h = h.upper()
    return {"algo": algo, "digest": h}


def hmac_text(text, key, algo="sha256", upper=True):
    algo = algo.lower()
    if algo not in _HASHLIB_ALGOS:
        raise InputError(f"未知哈希算法：{algo}",
                         friendly_key="err_input")
    h = hmac.new(
        str(key).encode("utf-8"),
        str(text).encode("utf-8"),
        _HASHLIB_ALGOS[algo]).hexdigest()
    if upper:
        h = h.upper()
    return {"algo": f"hmac-{algo}", "digest": h}


# ===========================================================================
# AES-GCM
# ===========================================================================

def _require_crypto():
    try:
        import cryptography  # noqa: F401
        return True
    except ImportError:
        raise InputError(
            "需要安装 cryptography 库："
            "pip install cryptography",
            friendly_key="err_input")


def aes_gcm_encrypt(plaintext, key_hex):
    _require_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import (
        AESGCM,
    )
    try:
        key = bytes.fromhex(str(key_hex).strip())
    except Exception as e:
        raise InputError(f"密钥必须是十六进制：{e}",
                         friendly_key="err_input")
    if len(key) not in (16, 24, 32):
        raise InputError("AES 密钥长度必须为 16/24/32 字节",
                         friendly_key="err_input")
    nonce = os.urandom(12)
    aes = AESGCM(key)
    ct = aes.encrypt(nonce, str(plaintext).encode("utf-8"), None)
    return {
        "nonce": nonce.hex().upper(),
        "ciphertext": ct.hex().upper(),
        "combined": (nonce + ct).hex().upper(),
        "note": "combined = nonce || ciphertext",
    }


def aes_gcm_decrypt(cipher_hex, key_hex):
    _require_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import (
        AESGCM,
    )
    try:
        key = bytes.fromhex(str(key_hex).strip())
        data = bytes.fromhex(str(cipher_hex).strip())
    except Exception as e:
        raise InputError(f"十六进制解析失败：{e}",
                         friendly_key="err_input")
    if len(key) not in (16, 24, 32):
        raise InputError("AES 密钥长度必须为 16/24/32 字节",
                         friendly_key="err_input")
    if len(data) < 13:
        raise InputError("密文过短",
                         friendly_key="err_input")
    nonce, ct = data[:12], data[12:]
    aes = AESGCM(key)
    try:
        pt = aes.decrypt(nonce, ct, None)
    except Exception as e:
        raise InputError(
            f"解密失败（密钥或数据错误）：{e}",
            friendly_key="err_input")
    return pt.decode("utf-8", errors="replace")


def gen_aes_key(bits=256):
    n = int(bits) // 8
    if n not in (16, 24, 32):
        raise InputError(
            "AES 密钥长度必须为 128/192/256 位",
            friendly_key="err_input")
    return secrets.token_hex(n).upper()


# ===========================================================================
# RSA
# ===========================================================================

def rsa_generate(bits=2048):
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    n = int(bits)
    if n < 1024:
        raise InputError("RSA 位数至少 1024",
                         friendly_key="err_input")
    key = rsa.generate_private_key(
        public_exponent=65537, key_size=n)

    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    return {
        "private_key": priv_pem,
        "public_key": pub_pem,
        "bits": n,
    }


def rsa_encrypt(plaintext, public_pem):
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import (
        hashes, serialization,
    )
    try:
        pub = serialization.load_pem_public_key(
            str(public_pem).encode("ascii"))
    except Exception as e:
        raise InputError(f"公钥解析失败：{e}",
                         friendly_key="err_input")
    ct = pub.encrypt(
        str(plaintext).encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(), label=None))
    return ct.hex().upper()


def rsa_decrypt(cipher_hex, private_pem):
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import (
        hashes, serialization,
    )
    try:
        priv = serialization.load_pem_private_key(
            str(private_pem).encode("ascii"), password=None)
        ct = bytes.fromhex(str(cipher_hex).strip())
    except Exception as e:
        raise InputError(f"解析失败：{e}",
                         friendly_key="err_input")
    try:
        pt = priv.decrypt(
            ct,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(), label=None))
    except Exception as e:
        raise InputError(f"解密失败：{e}",
                         friendly_key="err_input")
    return pt.decode("utf-8", errors="replace")


# ===========================================================================
# TOTP / HOTP
# ===========================================================================

def _hotp(key_bytes, counter, digits=6):
    counter_bytes = struct.pack(">Q", counter)
    h = hmac.new(key_bytes, counter_bytes,
                 hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = ((h[offset] & 0x7F) << 24 |
            (h[offset + 1] & 0xFF) << 16 |
            (h[offset + 2] & 0xFF) << 8 |
            (h[offset + 3] & 0xFF))
    return str(code % (10 ** digits)).zfill(digits)


def totp(secret_b32, digits=6, period=30, at_time=None):
    s = (str(secret_b32).strip().upper()
         .replace(" ", "").replace("-", ""))
    pad = (-len(s)) % 8
    s += "=" * pad
    try:
        key = base64.b32decode(s)
    except Exception as e:
        raise InputError(
            f"Base32 密钥解析失败：{e}",
            friendly_key="err_input")
    t = (int(at_time) if at_time is not None
         else int(time.time()))
    counter = t // int(period)
    code = _hotp(key, counter, int(digits))
    return {
        "code": code,
        "counter": counter,
        "period": int(period),
        "remaining": int(period) - (t % int(period)),
    }


def gen_totp_secret(bytes_len=20):
    return base64.b32encode(
        secrets.token_bytes(int(bytes_len))).decode("ascii")


# ===========================================================================
# 密码强度
# ===========================================================================

def password_strength(pw):
    s = str(pw)
    if not s:
        return {"length": 0, "entropy": 0.0, "level": "empty"}

    pool = 0
    if any(c.islower() for c in s):
        pool += 26
    if any(c.isupper() for c in s):
        pool += 26
    if any(c.isdigit() for c in s):
        pool += 10
    if any(not c.isalnum() for c in s):
        pool += 33

    entropy = len(s) * math.log2(pool) if pool > 1 else 0
    if entropy < 28:
        level = "very_weak"
    elif entropy < 40:
        level = "weak"
    elif entropy < 60:
        level = "medium"
    elif entropy < 80:
        level = "strong"
    else:
        level = "very_strong"

    return {
        "length": len(s),
        "pool": pool,
        "entropy": round(entropy, 2),
        "level": level,
    }


# ===========================================================================
# Base58 / Base32 / Base85 / Ascii85（转发到 core.crypto_advanced）
# ===========================================================================

def base58_encode(text):
    """Base58 编码（Bitcoin 风格）。"""
    from core import crypto_advanced as ca
    return ca.base58_encode(text)


def base58_decode(text):
    """Base58 解码。"""
    from core import crypto_advanced as ca
    return ca.base58_decode(text)


def base32_encode(text, padding=True):
    """Base32 编码（RFC 4648）。"""
    from core import crypto_advanced as ca
    return ca.base32_encode(text, padding=padding)


def base32_decode(text):
    """Base32 解码。"""
    from core import crypto_advanced as ca
    return ca.base32_decode(text)


def base85_encode(text):
    """Base85（RFC 1924）编码。"""
    from core import crypto_advanced as ca
    return ca.base85_encode(text)


def base85_decode(text):
    """Base85（RFC 1924）解码。"""
    from core import crypto_advanced as ca
    return ca.base85_decode(text)


def ascii85_encode(text):
    """Ascii85（Adobe 风格）编码。"""
    from core import crypto_advanced as ca
    return ca.ascii85_encode(text)


def ascii85_decode(text):
    """Ascii85（Adobe 风格）解码。"""
    from core import crypto_advanced as ca
    return ca.ascii85_decode(text)


# ===========================================================================
# 会话密钥（内部工具）
# ===========================================================================

def gen_random_hex(n_bytes=32):
    """生成 n 字节的随机 hex。"""
    return secrets.token_hex(int(n_bytes)).upper()


__all__ = [
    # 编码
    "b64_encode", "b64_decode",
    "hex_encode", "hex_decode",
    "url_encode", "url_decode",
    "html_encode", "html_decode",
    # 经典密码
    "rot13", "caesar",
    # 哈希
    "hash_text", "hmac_text",
    # AES
    "aes_gcm_encrypt", "aes_gcm_decrypt", "gen_aes_key",
    # RSA
    "rsa_generate", "rsa_encrypt", "rsa_decrypt",
    # TOTP
    "totp", "gen_totp_secret",
    # 密码强度
    "password_strength",
    # 转发
    "base58_encode", "base58_decode",
    "base32_encode", "base32_decode",
    "base85_encode", "base85_decode",
    "ascii85_encode", "ascii85_decode",
    # 工具
    "gen_random_hex",
]