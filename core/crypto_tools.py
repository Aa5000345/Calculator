"""编码 / 哈希 / 对称加密 / 非对称加密 / PQC / 文件加密。

合并自：core/crypto_tools.py + core/crypto_advanced.py
        + core/file_crypto.py

对外接口：
    # 基础编码
    b64_encode, b64_decode, hex_encode, hex_decode,
    url_encode, url_decode, html_encode, html_decode
    # 经典密码
    rot13, caesar
    # 哈希 / HMAC
    hash_text, hmac_text
    # AES
    aes_gcm_encrypt, aes_gcm_decrypt, gen_aes_key
    # RSA
    rsa_generate, rsa_encrypt, rsa_decrypt
    # TOTP
    totp, gen_totp_secret
    # 密码强度
    password_strength
    # 高级编码
    base58_encode/decode, base32_encode/decode,
    base85_encode/decode, ascii85_encode/decode
    # 后端能力
    BackendInfo, backend_info
    # PQC
    mlkem_generate, mlkem_encapsulate, mlkem_decapsulate
    mldsa_generate, mldsa_sign, mldsa_verify
    slhdsa_generate, slhdsa_sign, slhdsa_verify
    # 对称 / 非对称
    chacha20_encrypt, chacha20_decrypt, chacha20_gen_key
    ed25519_generate, ed25519_sign, ed25519_verify
    x25519_generate, x25519_shared
    # 密码哈希 / 派生
    argon2_hash, argon2_verify, bcrypt_hash, bcrypt_verify
    derive_key
    # 文件加密
    encrypt_file, decrypt_file, get_file_info, is_encrypted_file
    FileHeaderV2, CryptoProgress
    # 工具
    gen_random_hex
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
from dataclasses import dataclass

from core.base import InputError, log_info, log_warn

__all__ = [
    # 编码
    "b64_encode", "b64_decode", "hex_encode", "hex_decode",
    "url_encode", "url_decode", "html_encode", "html_decode",
    "rot13", "caesar",
    "hash_text", "hmac_text",
    "aes_gcm_encrypt", "aes_gcm_decrypt", "gen_aes_key",
    "rsa_generate", "rsa_encrypt", "rsa_decrypt",
    "totp", "gen_totp_secret", "password_strength",
    # 高级编码
    "base58_encode", "base58_decode",
    "base32_encode", "base32_decode",
    "base85_encode", "base85_decode",
    "ascii85_encode", "ascii85_decode",
    # 后端
    "BackendInfo", "backend_info",
    # PQC
    "mlkem_generate", "mlkem_encapsulate", "mlkem_decapsulate",
    "mldsa_generate", "mldsa_sign", "mldsa_verify",
    "slhdsa_generate", "slhdsa_sign", "slhdsa_verify",
    # 对称 / 非对称
    "chacha20_encrypt", "chacha20_decrypt", "chacha20_gen_key",
    "ed25519_generate", "ed25519_sign", "ed25519_verify",
    "x25519_generate", "x25519_shared",
    # 密码哈希 / 派生
    "argon2_hash", "argon2_verify",
    "bcrypt_hash", "bcrypt_verify",
    "derive_key",
    # 文件加密
    "encrypt_file", "decrypt_file",
    "get_file_info", "is_encrypted_file",
    "FileHeaderV2", "CryptoProgress",
    # 工具
    "gen_random_hex",
]


# ===========================================================================
# 基础编码
# ===========================================================================

def b64_encode(text, url_safe=False) -> str:
    data = str(text).encode("utf-8")
    if url_safe:
        return base64.urlsafe_b64encode(data).decode("ascii")
    return base64.b64encode(data).decode("ascii")


def b64_decode(text, url_safe=False) -> str:
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


def hex_encode(text, upper=True, sep="") -> str:
    data = str(text).encode("utf-8")
    h = data.hex()
    if upper:
        h = h.upper()
    if sep:
        return sep.join(h[i:i + 2]
                        for i in range(0, len(h), 2))
    return h


def hex_decode(text) -> str:
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


def url_encode(text) -> str:
    return urllib.parse.quote(str(text), safe="")


def url_decode(text) -> str:
    return urllib.parse.unquote(str(text))


def html_encode(text) -> str:
    return html.escape(str(text))


def html_decode(text) -> str:
    return html.unescape(str(text))


# ===========================================================================
# 经典密码
# ===========================================================================

def rot13(text) -> str:
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


def caesar(text, shift) -> str:
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


def hash_text(text, algo="sha256", upper=True) -> dict:
    algo = algo.lower()
    if algo not in _HASHLIB_ALGOS:
        raise InputError(f"未知哈希算法：{algo}",
                         friendly_key="err_input")
    h = _HASHLIB_ALGOS[algo](str(text).encode("utf-8")).hexdigest()
    if upper:
        h = h.upper()
    return {"algo": algo, "digest": h}


def hmac_text(text, key, algo="sha256", upper=True) -> dict:
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
            "需要安装 cryptography 库：pip install cryptography",
            friendly_key="err_input")


def aes_gcm_encrypt(plaintext, key_hex) -> dict:
    _require_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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


def aes_gcm_decrypt(cipher_hex, key_hex) -> str:
    _require_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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
        raise InputError("密文过短", friendly_key="err_input")
    nonce, ct = data[:12], data[12:]
    aes = AESGCM(key)
    try:
        pt = aes.decrypt(nonce, ct, None)
    except Exception as e:
        raise InputError(f"解密失败（密钥或数据错误）：{e}",
                         friendly_key="err_input")
    return pt.decode("utf-8", errors="replace")


def gen_aes_key(bits=256) -> str:
    n = int(bits) // 8
    if n not in (16, 24, 32):
        raise InputError("AES 密钥长度必须为 128/192/256 位",
                         friendly_key="err_input")
    return secrets.token_hex(n).upper()


# ===========================================================================
# RSA
# ===========================================================================

def rsa_generate(bits=2048) -> dict:
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


def rsa_encrypt(plaintext, public_pem) -> str:
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import (
        hashes, serialization)
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


def rsa_decrypt(cipher_hex, private_pem) -> str:
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import (
        hashes, serialization)
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

def _hotp(key_bytes, counter, digits=6) -> str:
    counter_bytes = struct.pack(">Q", counter)
    h = hmac.new(key_bytes, counter_bytes, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = ((h[offset] & 0x7F) << 24 |
            (h[offset + 1] & 0xFF) << 16 |
            (h[offset + 2] & 0xFF) << 8 |
            (h[offset + 3] & 0xFF))
    return str(code % (10 ** digits)).zfill(digits)


def totp(secret_b32, digits=6, period=30, at_time=None) -> dict:
    s = (str(secret_b32).strip().upper()
         .replace(" ", "").replace("-", ""))
    pad = (-len(s)) % 8
    s += "=" * pad
    try:
        key = base64.b32decode(s)
    except Exception as e:
        raise InputError(f"Base32 密钥解析失败：{e}",
                         friendly_key="err_input")
    t = int(at_time) if at_time is not None else int(time.time())
    counter = t // int(period)
    code = _hotp(key, counter, int(digits))
    return {
        "code": code,
        "counter": counter,
        "period": int(period),
        "remaining": int(period) - (t % int(period)),
    }


def gen_totp_secret(bytes_len=20) -> str:
    return base64.b32encode(
        secrets.token_bytes(int(bytes_len))).decode("ascii")


# ===========================================================================
# 密码强度
# ===========================================================================

def password_strength(pw) -> dict:
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
# 高级编码：Base58 / Base32 / Base85 / Ascii85
# ===========================================================================

_B58_ALPHABET = (
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    "abcdefghijkmnopqrstuvwxyz")


def base58_encode(text) -> str:
    data = str(text).encode("utf-8")
    n = int.from_bytes(data, "big")
    out = []
    while n > 0:
        n, r = divmod(n, 58)
        out.append(_B58_ALPHABET[r])
    for b in data:
        if b == 0:
            out.append(_B58_ALPHABET[0])
        else:
            break
    return "".join(reversed(out)) or _B58_ALPHABET[0]


def base58_decode(text) -> str:
    s = str(text).strip()
    if not s:
        return ""
    n = 0
    for ch in s:
        idx = _B58_ALPHABET.find(ch)
        if idx < 0:
            raise InputError(f"非法 Base58 字符：{ch!r}")
        n = n * 58 + idx
    n_zeros = 0
    for ch in s:
        if ch == _B58_ALPHABET[0]:
            n_zeros += 1
        else:
            break
    body = (n.to_bytes((n.bit_length() + 7) // 8, "big")
            if n else b"")
    return (b"\x00" * n_zeros + body).decode(
        "utf-8", errors="replace")


def base32_encode(text, padding=True) -> str:
    data = str(text).encode("utf-8")
    out = base64.b32encode(data).decode("ascii")
    return out if padding else out.rstrip("=")


def base32_decode(text) -> str:
    s = str(text).strip()
    pad = (-len(s)) % 8
    s += "=" * pad
    try:
        data = base64.b32decode(s)
    except Exception as e:
        raise InputError(f"Base32 解码失败：{e}")
    return data.decode("utf-8", errors="replace")


def base85_encode(text) -> str:
    return base64.b85encode(str(text).encode("utf-8")).decode("ascii")


def base85_decode(text) -> str:
    try:
        data = base64.b85decode(str(text).strip().encode("ascii"))
    except Exception as e:
        raise InputError(f"Base85 解码失败：{e}")
    return data.decode("utf-8", errors="replace")


def ascii85_encode(text) -> str:
    return base64.a85encode(str(text).encode("utf-8")).decode("ascii")


def ascii85_decode(text) -> str:
    try:
        data = base64.a85decode(str(text).strip().encode("ascii"))
    except Exception as e:
        raise InputError(f"Ascii85 解码失败：{e}")
    return data.decode("utf-8", errors="replace")


# ===========================================================================
# 后端能力探测
# ===========================================================================

@dataclass
class BackendInfo:
    has_cryptography: bool = False
    cryptography_version: str = ""
    has_pqc_mlkem: bool = False
    has_pqc_mldsa: bool = False
    has_pqc_slhdsa: bool = False
    has_argon2: bool = False
    has_bcrypt: bool = False
    has_pycryptodome: bool = False
    openssl_version: str = ""

    def to_dict(self) -> dict:
        return {
            "cryptography": self.has_cryptography,
            "cryptography_version": self.cryptography_version,
            "pqc_mlkem": self.has_pqc_mlkem,
            "pqc_mldsa": self.has_pqc_mldsa,
            "pqc_slhdsa": self.has_pqc_slhdsa,
            "argon2": self.has_argon2,
            "bcrypt": self.has_bcrypt,
            "pycryptodome": self.has_pycryptodome,
            "openssl": self.openssl_version,
        }


_BACKEND_CACHE: BackendInfo | None = None


def backend_info(force: bool = False) -> BackendInfo:
    global _BACKEND_CACHE
    if _BACKEND_CACHE is not None and not force:
        return _BACKEND_CACHE

    info = BackendInfo()
    try:
        import cryptography
        info.has_cryptography = True
        info.cryptography_version = getattr(
            cryptography, "__version__", "")
    except ImportError:
        pass

    try:
        from cryptography.hazmat.backends.openssl.backend import (
            backend)
        info.openssl_version = backend.openssl_version_text()
    except Exception:
        pass

    if info.has_cryptography:
        try:
            from cryptography.hazmat.primitives.asymmetric import (
                mlkem)
            info.has_pqc_mlkem = hasattr(
                mlkem, "generate_keypair") or hasattr(
                mlkem, "MLKEM768")
        except Exception:
            pass
        try:
            from cryptography.hazmat.primitives.asymmetric import (
                mldsa)  # noqa: F401
            info.has_pqc_mldsa = True
        except Exception:
            pass
        try:
            from cryptography.hazmat.primitives.asymmetric import (
                slhdsa)  # noqa: F401
            info.has_pqc_slhdsa = True
        except Exception:
            pass

    try:
        import argon2  # noqa: F401
        info.has_argon2 = True
    except ImportError:
        pass

    try:
        import bcrypt  # noqa: F401
        info.has_bcrypt = True
    except ImportError:
        pass

    try:
        import Crypto  # noqa: F401
        info.has_pycryptodome = True
    except ImportError:
        pass

    _BACKEND_CACHE = info
    return info


# ===========================================================================
# PQC：ML-KEM（FIPS 203）
# ===========================================================================

_MLKEM_PARAMS = {
    "ML-KEM-512": "MLKEM512",
    "ML-KEM-768": "MLKEM768",
    "ML-KEM-1024": "MLKEM1024",
}


def _as_bytes(x) -> bytes:
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    if hasattr(x, "raw"):
        return bytes(x.raw)
    if hasattr(x, "__bytes__"):
        return bytes(x)
    try:
        return bytes(x)
    except Exception:
        raise InputError(f"无法转为 bytes：{type(x)}")


def _serialize_public(pk) -> bytes:
    if hasattr(pk, "public_bytes_raw"):
        return pk.public_bytes_raw()
    from cryptography.hazmat.primitives import serialization
    return pk.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _serialize_private(sk) -> bytes:
    if hasattr(sk, "private_bytes_raw"):
        return sk.private_bytes_raw()
    from cryptography.hazmat.primitives import serialization
    return sk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def mlkem_generate(level: str = "ML-KEM-768") -> dict:
    _require_crypto()
    try:
        from cryptography.hazmat.primitives.asymmetric import mlkem
    except ImportError:
        raise InputError(
            "当前 cryptography 版本不支持 ML-KEM；"
            "需要 cryptography>=48 且 OpenSSL 3.5+/AWS-LC/BoringSSL")

    name = _MLKEM_PARAMS.get(level.upper())
    if name is None:
        raise InputError(f"不支持的 ML-KEM 级别：{level}")
    cls = getattr(mlkem, name, None)
    if cls is None:
        raise InputError(
            f"当前后端不支持 {level}（OpenSSL 可能太旧）")

    try:
        sk = cls.generate_keypair()
    except Exception as e:
        raise InputError(f"生成 ML-KEM 密钥失败：{e}")

    try:
        pk_bytes = _serialize_public(sk.public_key())
        sk_bytes = _serialize_private(sk)
    except Exception:
        try:
            pk_bytes = sk.public_key().public_bytes_raw()
            sk_bytes = sk.private_bytes_raw()
        except Exception as e:
            raise InputError(f"序列化 ML-KEM 密钥失败：{e}")

    return {
        "level": level,
        "public_key": pk_bytes.hex().upper(),
        "private_key": sk_bytes.hex().upper(),
        "pk_size": len(pk_bytes),
        "sk_size": len(sk_bytes),
    }


def mlkem_encapsulate(level: str, public_key_hex: str) -> dict:
    _require_crypto()
    try:
        from cryptography.hazmat.primitives.asymmetric import mlkem
    except ImportError:
        raise InputError("当前 cryptography 不支持 ML-KEM")

    name = _MLKEM_PARAMS.get(level.upper())
    cls = getattr(mlkem, name, None) if name else None
    if cls is None:
        raise InputError(f"不支持：{level}")

    try:
        pk_bytes = bytes.fromhex(str(public_key_hex).strip())
    except Exception as e:
        raise InputError(f"公钥 hex 解析失败：{e}")

    try:
        pk = cls.public_key_from_bytes(pk_bytes)
    except Exception:
        try:
            pk = cls.from_public_bytes(pk_bytes)
        except Exception as e:
            raise InputError(f"公钥解析失败：{e}")

    try:
        shared, ct = pk.encapsulate()
    except Exception as e:
        raise InputError(f"封装失败：{e}")

    return {
        "level": level,
        "ciphertext": _as_bytes(ct).hex().upper(),
        "shared_secret": _as_bytes(shared).hex().upper(),
        "ct_size": len(_as_bytes(ct)),
        "ss_size": len(_as_bytes(shared)),
    }


def mlkem_decapsulate(level: str, private_key_hex: str,
                      ciphertext_hex: str) -> dict:
    _require_crypto()
    try:
        from cryptography.hazmat.primitives.asymmetric import mlkem
    except ImportError:
        raise InputError("当前 cryptography 不支持 ML-KEM")

    name = _MLKEM_PARAMS.get(level.upper())
    cls = getattr(mlkem, name, None) if name else None
    if cls is None:
        raise InputError(f"不支持：{level}")

    try:
        sk_bytes = bytes.fromhex(str(private_key_hex).strip())
        ct_bytes = bytes.fromhex(str(ciphertext_hex).strip())
    except Exception as e:
        raise InputError(f"hex 解析失败：{e}")

    try:
        sk = cls.private_key_from_bytes(sk_bytes)
    except Exception:
        try:
            sk = cls.from_private_bytes(sk_bytes)
        except Exception as e:
            raise InputError(f"私钥解析失败：{e}")

    try:
        shared = sk.decapsulate(ct_bytes)
    except Exception as e:
        raise InputError(f"解封装失败：{e}")

    return {
        "level": level,
        "shared_secret": _as_bytes(shared).hex().upper(),
        "ss_size": len(_as_bytes(shared)),
    }


# ===========================================================================
# PQC：ML-DSA（FIPS 204）
# ===========================================================================

_MLDSA_PARAMS = {
    "ML-DSA-44": "MLDSA44",
    "ML-DSA-65": "MLDSA65",
    "ML-DSA-87": "MLDSA87",
}


def mldsa_generate(level: str = "ML-DSA-65") -> dict:
    _require_crypto()
    try:
        from cryptography.hazmat.primitives.asymmetric import mldsa
    except ImportError:
        raise InputError(
            "当前 cryptography 不支持 ML-DSA；需要 cryptography>=48")

    name = _MLDSA_PARAMS.get(level.upper())
    if name is None:
        raise InputError(f"不支持的 ML-DSA 级别：{level}")
    cls = getattr(mldsa, name, None)
    if cls is None:
        raise InputError(f"当前后端不支持 {level}")

    try:
        sk = cls.generate_keypair()
    except Exception as e:
        raise InputError(f"生成 ML-DSA 密钥失败：{e}")

    pk_bytes = _serialize_public(sk.public_key())
    sk_bytes = _serialize_private(sk)
    return {
        "level": level,
        "public_key": pk_bytes.hex().upper(),
        "private_key": sk_bytes.hex().upper(),
        "pk_size": len(pk_bytes),
        "sk_size": len(sk_bytes),
    }


def mldsa_sign(level: str, private_key_hex: str,
               message: str) -> dict:
    _require_crypto()
    try:
        from cryptography.hazmat.primitives.asymmetric import mldsa
    except ImportError:
        raise InputError("当前 cryptography 不支持 ML-DSA")

    name = _MLDSA_PARAMS.get(level.upper())
    cls = getattr(mldsa, name, None) if name else None
    if cls is None:
        raise InputError(f"不支持：{level}")

    try:
        sk_bytes = bytes.fromhex(str(private_key_hex).strip())
    except Exception as e:
        raise InputError(f"私钥 hex 解析失败：{e}")

    try:
        sk = cls.private_key_from_bytes(sk_bytes)
    except Exception:
        try:
            sk = cls.from_private_bytes(sk_bytes)
        except Exception as e:
            raise InputError(f"私钥解析失败：{e}")

    try:
        sig = sk.sign(str(message).encode("utf-8"))
    except Exception as e:
        raise InputError(f"签名失败：{e}")

    return {
        "level": level,
        "signature": _as_bytes(sig).hex().upper(),
        "sig_size": len(_as_bytes(sig)),
        "message_size": len(str(message).encode("utf-8")),
    }


def mldsa_verify(level: str, public_key_hex: str,
                 message: str, signature_hex: str) -> dict:
    _require_crypto()
    try:
        from cryptography.hazmat.primitives.asymmetric import mldsa
    except ImportError:
        raise InputError("当前 cryptography 不支持 ML-DSA")

    name = _MLDSA_PARAMS.get(level.upper())
    cls = getattr(mldsa, name, None) if name else None
    if cls is None:
        raise InputError(f"不支持：{level}")

    try:
        pk_bytes = bytes.fromhex(str(public_key_hex).strip())
        sig_bytes = bytes.fromhex(str(signature_hex).strip())
    except Exception as e:
        raise InputError(f"hex 解析失败：{e}")

    try:
        pk = cls.public_key_from_bytes(pk_bytes)
    except Exception:
        try:
            pk = cls.from_public_bytes(pk_bytes)
        except Exception as e:
            raise InputError(f"公钥解析失败：{e}")

    try:
        pk.verify(sig_bytes, str(message).encode("utf-8"))
        return {"level": level, "valid": True, "reason": ""}
    except Exception as e:
        return {"level": level, "valid": False, "reason": str(e)}


# ===========================================================================
# PQC：SLH-DSA（FIPS 205）
# ===========================================================================

_SLHDSA_PARAMS = [
    "SLH-DSA-SHA2-128s", "SLH-DSA-SHA2-128f",
    "SLH-DSA-SHA2-192s", "SLH-DSA-SHA2-192f",
    "SLH-DSA-SHA2-256s", "SLH-DSA-SHA2-256f",
    "SLH-DSA-SHAKE-128s", "SLH-DSA-SHAKE-128f",
    "SLH-DSA-SHAKE-192s", "SLH-DSA-SHAKE-192f",
    "SLH-DSA-SHAKE-256s", "SLH-DSA-SHAKE-256f",
]


def _slhdsa_class(slhdsa, level: str):
    cls = getattr(slhdsa, level.replace("-", "_"), None)
    if cls is not None:
        return cls
    for attr in dir(slhdsa):
        if attr.upper().replace("_", "-") == level.upper():
            return getattr(slhdsa, attr)
    return None


def slhdsa_generate(level: str = "SLH-DSA-SHA2-128s") -> dict:
    _require_crypto()
    if level not in _SLHDSA_PARAMS:
        raise InputError(f"不支持的 SLH-DSA 参数：{level}")
    try:
        from cryptography.hazmat.primitives.asymmetric import (
            slhdsa)
    except ImportError:
        raise InputError(
            "当前 cryptography 不支持 SLH-DSA；"
            "需要 cryptography>=48")

    cls = _slhdsa_class(slhdsa, level)
    if cls is None:
        raise InputError(f"当前后端不支持：{level}")

    try:
        sk = cls.generate_keypair()
    except Exception as e:
        raise InputError(f"生成 SLH-DSA 密钥失败：{e}")

    pk_bytes = _serialize_public(sk.public_key())
    sk_bytes = _serialize_private(sk)
    return {
        "level": level,
        "public_key": pk_bytes.hex().upper(),
        "private_key": sk_bytes.hex().upper(),
        "pk_size": len(pk_bytes),
        "sk_size": len(sk_bytes),
    }


def slhdsa_sign(level: str, private_key_hex: str,
                message: str) -> dict:
    _require_crypto()
    if level not in _SLHDSA_PARAMS:
        raise InputError(f"不支持的 SLH-DSA 参数：{level}")
    try:
        from cryptography.hazmat.primitives.asymmetric import (
            slhdsa)
    except ImportError:
        raise InputError("当前 cryptography 不支持 SLH-DSA")

    cls = _slhdsa_class(slhdsa, level)
    if cls is None:
        raise InputError(f"当前后端不支持：{level}")

    try:
        sk_bytes = bytes.fromhex(str(private_key_hex).strip())
        sk = cls.private_key_from_bytes(sk_bytes)
    except Exception as e:
        raise InputError(f"私钥解析失败：{e}")

    try:
        sig = sk.sign(str(message).encode("utf-8"))
    except Exception as e:
        raise InputError(f"签名失败：{e}")

    return {
        "level": level,
        "signature": _as_bytes(sig).hex().upper(),
        "sig_size": len(_as_bytes(sig)),
    }


def slhdsa_verify(level: str, public_key_hex: str,
                  message: str, signature_hex: str) -> dict:
    _require_crypto()
    if level not in _SLHDSA_PARAMS:
        raise InputError(f"不支持的 SLH-DSA 参数：{level}")
    try:
        from cryptography.hazmat.primitives.asymmetric import (
            slhdsa)
    except ImportError:
        raise InputError("当前 cryptography 不支持 SLH-DSA")

    cls = _slhdsa_class(slhdsa, level)
    if cls is None:
        raise InputError(f"当前后端不支持：{level}")

    try:
        pk_bytes = bytes.fromhex(str(public_key_hex).strip())
        sig_bytes = bytes.fromhex(str(signature_hex).strip())
        pk = cls.public_key_from_bytes(pk_bytes)
    except Exception as e:
        raise InputError(f"解析失败：{e}")

    try:
        pk.verify(sig_bytes, str(message).encode("utf-8"))
        return {"level": level, "valid": True, "reason": ""}
    except Exception as e:
        return {"level": level, "valid": False, "reason": str(e)}


# ===========================================================================
# ChaCha20-Poly1305
# ===========================================================================

def chacha20_encrypt(plaintext: str, key_hex: str,
                     aad: str = "") -> dict:
    _require_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import (
        ChaCha20Poly1305)
    try:
        key = bytes.fromhex(str(key_hex).strip())
    except Exception as e:
        raise InputError(f"密钥 hex 解析失败：{e}")
    if len(key) != 32:
        raise InputError(
            "ChaCha20 密钥必须为 32 字节（64 hex 字符）")

    nonce = os.urandom(12)
    aead = ChaCha20Poly1305(key)
    aad_bytes = str(aad).encode("utf-8") if aad else None
    try:
        ct = aead.encrypt(
            nonce, str(plaintext).encode("utf-8"), aad_bytes)
    except Exception as e:
        raise InputError(f"加密失败：{e}")

    return {
        "nonce": nonce.hex().upper(),
        "ciphertext": ct.hex().upper(),
        "combined": (nonce + ct).hex().upper(),
        "aad": aad,
        "note": "combined = nonce || ciphertext",
    }


def chacha20_decrypt(combined_hex: str, key_hex: str,
                     aad: str = "") -> str:
    _require_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import (
        ChaCha20Poly1305)
    try:
        key = bytes.fromhex(str(key_hex).strip())
        data = bytes.fromhex(str(combined_hex).strip())
    except Exception as e:
        raise InputError(f"hex 解析失败：{e}")
    if len(key) != 32:
        raise InputError("密钥必须为 32 字节")
    if len(data) < 13:
        raise InputError("密文过短")

    nonce, ct = data[:12], data[12:]
    aead = ChaCha20Poly1305(key)
    aad_bytes = str(aad).encode("utf-8") if aad else None
    try:
        pt = aead.decrypt(nonce, ct, aad_bytes)
    except Exception as e:
        raise InputError(f"解密失败：{e}")
    return pt.decode("utf-8", errors="replace")


def chacha20_gen_key() -> str:
    return os.urandom(32).hex().upper()


# ===========================================================================
# Ed25519
# ===========================================================================

def ed25519_generate() -> dict:
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey)
    from cryptography.hazmat.primitives import serialization

    sk = Ed25519PrivateKey.generate()
    priv_pem = sk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    pub_pem = sk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    return {
        "private_key": priv_pem,
        "public_key": pub_pem,
        "private_hex": sk.private_bytes_raw().hex().upper(),
        "public_hex": (sk.public_key()
                       .public_bytes_raw().hex().upper()),
        "pk_size": 32, "sk_size": 32,
    }


def ed25519_sign(private_hex: str, message: str) -> dict:
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey)
    try:
        raw = bytes.fromhex(str(private_hex).strip())
        sk = Ed25519PrivateKey.from_private_bytes(raw)
    except Exception as e:
        raise InputError(f"私钥解析失败：{e}")

    sig = sk.sign(str(message).encode("utf-8"))
    return {
        "signature": sig.hex().upper(),
        "sig_size": len(sig),
    }


def ed25519_verify(public_hex: str, message: str,
                   signature_hex: str) -> dict:
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey)
    try:
        pk_raw = bytes.fromhex(str(public_hex).strip())
        sig = bytes.fromhex(str(signature_hex).strip())
        pk = Ed25519PublicKey.from_public_bytes(pk_raw)
    except Exception as e:
        raise InputError(f"解析失败：{e}")

    try:
        pk.verify(sig, str(message).encode("utf-8"))
        return {"valid": True, "reason": ""}
    except Exception as e:
        return {"valid": False, "reason": str(e)}


# ===========================================================================
# X25519
# ===========================================================================

def x25519_generate() -> dict:
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey)
    from cryptography.hazmat.primitives import serialization

    sk = X25519PrivateKey.generate()
    priv_pem = sk.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    pub_pem = sk.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return {
        "private_key": priv_pem,
        "public_key": pub_pem,
        "private_hex": sk.private_bytes_raw().hex().upper(),
        "public_hex": (sk.public_key()
                       .public_bytes_raw().hex().upper()),
    }


def x25519_shared(private_hex: str, peer_public_hex: str) -> dict:
    _require_crypto()
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey, X25519PublicKey)
    try:
        sk = X25519PrivateKey.from_private_bytes(
            bytes.fromhex(str(private_hex).strip()))
        pk = X25519PublicKey.from_public_bytes(
            bytes.fromhex(str(peer_public_hex).strip()))
    except Exception as e:
        raise InputError(f"解析失败：{e}")

    try:
        shared = sk.exchange(pk)
    except Exception as e:
        raise InputError(f"密钥交换失败：{e}")

    return {
        "shared_secret": shared.hex().upper(),
        "size": len(shared),
    }


# ===========================================================================
# 密码哈希
# ===========================================================================

def argon2_hash(password: str, *, time_cost: int = 3,
                memory_cost: int = 65536,
                parallelism: int = 4) -> dict:
    try:
        from argon2 import PasswordHasher
    except ImportError:
        raise InputError(
            "需要 argon2-cffi：pip install argon2-cffi")

    ph = PasswordHasher(
        time_cost=int(time_cost),
        memory_cost=int(memory_cost),
        parallelism=int(parallelism),
    )
    try:
        h = ph.hash(str(password))
    except Exception as e:
        raise InputError(f"哈希失败：{e}")
    return {
        "hash": h,
        "algorithm": "argon2id",
        "time_cost": time_cost,
        "memory_cost": memory_cost,
        "parallelism": parallelism,
    }


def argon2_verify(password: str, hash_str: str) -> dict:
    try:
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
    except ImportError:
        raise InputError("需要 argon2-cffi")
    ph = PasswordHasher()
    try:
        ph.verify(hash_str, str(password))
        return {"valid": True, "reason": ""}
    except VerifyMismatchError:
        return {"valid": False, "reason": "密码不匹配"}
    except Exception as e:
        return {"valid": False, "reason": str(e)}


def bcrypt_hash(password: str, rounds: int = 12) -> dict:
    try:
        import bcrypt as _bcrypt
    except ImportError:
        raise InputError("需要 bcrypt：pip install bcrypt")
    try:
        salt = _bcrypt.gensalt(rounds=int(rounds))
        h = _bcrypt.hashpw(str(password).encode("utf-8"), salt)
    except Exception as e:
        raise InputError(f"哈希失败：{e}")
    return {
        "hash": h.decode("ascii"),
        "algorithm": "bcrypt",
        "rounds": int(rounds),
    }


def bcrypt_verify(password: str, hash_str: str) -> dict:
    try:
        import bcrypt as _bcrypt
    except ImportError:
        raise InputError("需要 bcrypt")
    try:
        ok = _bcrypt.checkpw(
            str(password).encode("utf-8"),
            hash_str.encode("ascii"))
        return {"valid": bool(ok), "reason": ""}
    except Exception as e:
        return {"valid": False, "reason": str(e)}


# ===========================================================================
# 密钥派生
# ===========================================================================

def derive_key(password: str, *, algorithm: str = "argon2id",
               length: int = 32, salt_hex: str = "") -> dict:
    """从密码派生密钥。

    algorithm: ``"argon2id"`` / ``"scrypt"`` / ``"pbkdf2"``
    """
    length = int(length)
    if length < 16 or length > 1024:
        raise InputError("密钥长度需在 16 ~ 1024 字节")

    salt = (bytes.fromhex(salt_hex) if salt_hex
            else os.urandom(16))

    if algorithm == "argon2id":
        try:
            from argon2.low_level import (
                hash_secret_raw, Type)
        except ImportError:
            raise InputError("需要 argon2-cffi")
        try:
            key = hash_secret_raw(
                secret=str(password).encode("utf-8"),
                salt=salt,
                time_cost=3, memory_cost=65536,
                parallelism=4, hash_len=length,
                type=Type.ID,
            )
        except Exception as e:
            raise InputError(f"Argon2id 派生失败：{e}")
    elif algorithm == "scrypt":
        _require_crypto()
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        try:
            kdf = Scrypt(salt=salt, length=length,
                         n=1 << 15, r=8, p=1)
            key = kdf.derive(str(password).encode("utf-8"))
        except Exception as e:
            raise InputError(f"Scrypt 派生失败：{e}")
    elif algorithm == "pbkdf2":
        _require_crypto()
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import (
            PBKDF2HMAC)
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(), length=length,
                salt=salt, iterations=600_000)
            key = kdf.derive(str(password).encode("utf-8"))
        except Exception as e:
            raise InputError(f"PBKDF2 派生失败：{e}")
    else:
        raise InputError(f"未知派生算法：{algorithm}")

    return {
        "algorithm": algorithm,
        "salt": salt.hex().upper(),
        "key": key.hex().upper(),
        "length": length,
    }


# ===========================================================================
# 文件加密（v1 + v2）
# ===========================================================================

MAGIC_V1 = b"MCENC001"
MAGIC_V2 = b"MCENC002"
VERSION_1 = 1
VERSION_2 = 2

DEFAULT_CHUNK_SIZE = 1 << 20
DEFAULT_PBKDF2_ITERATIONS = 600_000
SCRYPT_N = 1 << 15
SCRYPT_R = 8
SCRYPT_P = 1
SALT_SIZE = 16
NONCE_PREFIX_SIZE = 4
GCM_TAG_SIZE = 16

CIPHER_AES_GCM = 1
CIPHER_CHACHA20 = 2

KDF_PBKDF2 = 1
KDF_SCRYPT = 2
KDF_ARGON2ID = 3


@dataclass
class FileHeaderV2:
    version: int
    cipher_type: int
    kdf_type: int
    kdf_param: int
    salt: bytes
    original_size: int
    chunk_size: int
    nonce_prefix: bytes
    has_keyfile: bool

    @property
    def cipher_name(self) -> str:
        return {
            CIPHER_AES_GCM: "AES-256-GCM",
            CIPHER_CHACHA20: "ChaCha20-Poly1305",
        }.get(self.cipher_type, "unknown")

    @property
    def kdf_name(self) -> str:
        return {
            KDF_PBKDF2: "PBKDF2-HMAC-SHA256",
            KDF_SCRYPT: "Scrypt",
            KDF_ARGON2ID: "Argon2id",
        }.get(self.kdf_type, "unknown")


@dataclass
class CryptoProgress:
    done: int
    total: int
    stage: str = ""

    @property
    def percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(100.0, self.done / self.total * 100.0)


def _derive_file_key(password: str, salt: bytes, kdf_type: int,
                     kdf_param: int) -> bytes:
    pw = str(password).encode("utf-8")

    if kdf_type == KDF_PBKDF2:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import (
            PBKDF2HMAC)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32,
            salt=salt, iterations=int(kdf_param))
        return kdf.derive(pw)

    if kdf_type == KDF_SCRYPT:
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        kdf = Scrypt(salt=salt, length=32,
                     n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
        return kdf.derive(pw)

    if kdf_type == KDF_ARGON2ID:
        try:
            from argon2.low_level import (
                hash_secret_raw, Type)
        except ImportError:
            raise InputError(
                "Argon2id 需要 argon2-cffi：pip install argon2-cffi")
        return hash_secret_raw(
            secret=pw, salt=salt,
            time_cost=int(kdf_param) or 3,
            memory_cost=65536, parallelism=4,
            hash_len=32, type=Type.ID,
        )

    raise InputError(f"未知 KDF 类型：{kdf_type}")


def _make_file_cipher(cipher_type: int, key: bytes):
    if cipher_type == CIPHER_AES_GCM:
        from cryptography.hazmat.primitives.ciphers.aead import (
            AESGCM)
        return AESGCM(key)
    if cipher_type == CIPHER_CHACHA20:
        from cryptography.hazmat.primitives.ciphers.aead import (
            ChaCha20Poly1305)
        return ChaCha20Poly1305(key)
    raise InputError(f"未知加密算法：{cipher_type}")


def _nonce(prefix: bytes, block_index: int) -> bytes:
    return prefix + block_index.to_bytes(8, "big")


def encrypt_file(in_path: str, out_path: str, password: str, *,
                 cipher: str = "aes-gcm",
                 kdf: str = "pbkdf2",
                 iterations: int = DEFAULT_PBKDF2_ITERATIONS,
                 chunk_size: int = DEFAULT_CHUNK_SIZE,
                 progress_cb=None,
                 cancelled=None) -> dict:
    """加密文件（v2 格式）。

    Args:
        cipher: ``"aes-gcm"`` 或 ``"chacha20"``
        kdf: ``"pbkdf2"`` / ``"scrypt"`` / ``"argon2id"``
    """
    _require_crypto()

    if not os.path.isfile(in_path):
        raise InputError(f"输入文件不存在：{in_path}")
    if os.path.abspath(in_path) == os.path.abspath(out_path):
        raise InputError("输入和输出不能是同一个文件")
    if not password:
        raise InputError("密码不能为空")

    cipher_type = {
        "aes-gcm": CIPHER_AES_GCM,
        "aes": CIPHER_AES_GCM,
        "chacha20": CIPHER_CHACHA20,
        "chacha20-poly1305": CIPHER_CHACHA20,
    }.get(cipher.lower())
    if cipher_type is None:
        raise InputError(f"未知加密算法：{cipher}")

    kdf_type = {
        "pbkdf2": KDF_PBKDF2,
        "scrypt": KDF_SCRYPT,
        "argon2id": KDF_ARGON2ID,
    }.get(kdf.lower())
    if kdf_type is None:
        raise InputError(f"未知 KDF：{kdf}")

    total_size = os.path.getsize(in_path)
    salt = os.urandom(SALT_SIZE)
    nonce_prefix = os.urandom(NONCE_PREFIX_SIZE)

    started = time.time()
    if progress_cb:
        progress_cb(CryptoProgress(0, total_size, "deriving key"))
    key = _derive_file_key(password, salt, kdf_type, iterations)
    aead = _make_file_cipher(cipher_type, key)

    done = 0
    block_idx = 0
    with open(in_path, "rb") as fin, open(out_path, "wb") as fout:
        fout.write(MAGIC_V2)
        fout.write(bytes([VERSION_2]))
        fout.write(bytes([cipher_type]))
        fout.write(bytes([kdf_type]))
        fout.write(struct.pack(">I", int(iterations)))
        fout.write(salt)
        fout.write(struct.pack(">Q", total_size))
        fout.write(struct.pack(">I", int(chunk_size)))
        fout.write(nonce_prefix)
        fout.write(b"\x00")  # has_keyfile = 0

        while True:
            if cancelled is not None and cancelled():
                raise InputError("已取消")
            chunk = fin.read(chunk_size)
            if not chunk:
                break
            nonce = _nonce(nonce_prefix, block_idx)
            ct = aead.encrypt(nonce, chunk, None)
            fout.write(struct.pack(">I", len(chunk)))
            fout.write(ct)
            done += len(chunk)
            block_idx += 1
            if progress_cb:
                progress_cb(CryptoProgress(
                    done, total_size, "encrypting"))

    elapsed = time.time() - started
    log_info(
        f"encrypt_file v2: {in_path} -> {out_path} "
        f"({total_size} bytes, {elapsed:.2f}s)",
        module="file_crypto")
    return {
        "in": in_path, "out": out_path,
        "size": total_size, "elapsed": elapsed,
        "chunks": block_idx,
        "cipher": ("AES-256-GCM"
                   if cipher_type == CIPHER_AES_GCM
                   else "ChaCha20-Poly1305"),
        "kdf": kdf_type,
    }


def decrypt_file(in_path: str, out_path: str, password: str, *,
                 progress_cb=None,
                 cancelled=None) -> dict:
    """解密文件（支持 v1 与 v2）。"""
    _require_crypto()

    if not os.path.isfile(in_path):
        raise InputError(f"文件不存在：{in_path}")

    with open(in_path, "rb") as fin:
        magic = fin.read(8)
        fin.seek(0)

        if magic == MAGIC_V1:
            return _decrypt_v1(
                in_path, out_path, password,
                progress_cb, cancelled)
        if magic == MAGIC_V2:
            return _decrypt_v2(
                in_path, out_path, password,
                progress_cb, cancelled)
        raise InputError("不是 MultiCalc 加密文件")


def _decrypt_v1(in_path, out_path, password, progress_cb,
                cancelled):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    started = time.time()
    done = 0
    block_idx = 0

    with open(in_path, "rb") as fin:
        if fin.read(8) != MAGIC_V1:
            raise InputError("v1 magic 不匹配")
        version = fin.read(1)[0]
        kdf_type = fin.read(1)[0]
        iterations = struct.unpack(">I", fin.read(4))[0]
        salt = fin.read(SALT_SIZE)
        original_size = struct.unpack(">Q", fin.read(8))[0]
        chunk_size = struct.unpack(">I", fin.read(4))[0]
        nonce_prefix = fin.read(NONCE_PREFIX_SIZE)

        key = _derive_file_key(password, salt, kdf_type, iterations)
        aes = AESGCM(key)

        with open(out_path, "wb") as fout:
            while True:
                if cancelled is not None and cancelled():
                    raise InputError("已取消")
                len_bytes = fin.read(4)
                if not len_bytes:
                    break
                if len(len_bytes) < 4:
                    raise InputError("文件截断")
                chunk_len = struct.unpack(">I", len_bytes)[0]
                ct = fin.read(chunk_len + GCM_TAG_SIZE)
                if len(ct) < chunk_len + GCM_TAG_SIZE:
                    raise InputError("文件截断")
                nonce = _nonce(nonce_prefix, block_idx)
                try:
                    pt = aes.decrypt(nonce, ct, None)
                except Exception as e:
                    raise InputError(f"解密失败：{e}")
                fout.write(pt)
                done += len(pt)
                block_idx += 1
                if progress_cb:
                    progress_cb(CryptoProgress(
                        done, original_size, "decrypting"))

    elapsed = time.time() - started
    return {
        "in": in_path, "out": out_path,
        "size": done, "elapsed": elapsed,
        "chunks": block_idx, "format": "v1",
    }


def _decrypt_v2(in_path, out_path, password, progress_cb,
                cancelled):
    started = time.time()

    with open(in_path, "rb") as fin:
        if fin.read(8) != MAGIC_V2:
            raise InputError("v2 magic 不匹配")
        version = fin.read(1)[0]
        cipher_type = fin.read(1)[0]
        kdf_type = fin.read(1)[0]
        kdf_param = struct.unpack(">I", fin.read(4))[0]
        salt = fin.read(SALT_SIZE)
        original_size = struct.unpack(">Q", fin.read(8))[0]
        chunk_size = struct.unpack(">I", fin.read(4))[0]
        nonce_prefix = fin.read(NONCE_PREFIX_SIZE)
        has_keyfile = fin.read(1)[0] == 1

        key = _derive_file_key(
            password, salt, kdf_type, kdf_param)
        aead = _make_file_cipher(cipher_type, key)

        done = 0
        block_idx = 0
        with open(out_path, "wb") as fout:
            while True:
                if cancelled is not None and cancelled():
                    raise InputError("已取消")
                len_bytes = fin.read(4)
                if not len_bytes:
                    break
                if len(len_bytes) < 4:
                    raise InputError("文件截断")
                chunk_len = struct.unpack(">I", len_bytes)[0]
                ct = fin.read(chunk_len + GCM_TAG_SIZE)
                if len(ct) < chunk_len + GCM_TAG_SIZE:
                    raise InputError("文件截断")
                nonce = _nonce(nonce_prefix, block_idx)
                try:
                    pt = aead.decrypt(nonce, ct, None)
                except Exception as e:
                    raise InputError(
                        f"解密失败（密码错误或文件损坏）：{e}")
                fout.write(pt)
                done += len(pt)
                block_idx += 1
                if progress_cb:
                    progress_cb(CryptoProgress(
                        done, original_size, "decrypting"))

    elapsed = time.time() - started
    return {
        "in": in_path, "out": out_path,
        "size": done, "elapsed": elapsed,
        "chunks": block_idx, "format": "v2",
        "cipher": ("AES-256-GCM"
                   if cipher_type == CIPHER_AES_GCM
                   else "ChaCha20-Poly1305"),
    }


def get_file_info(path: str) -> dict:
    """读取加密文件头（同时支持 v1/v2）。"""
    if not os.path.isfile(path):
        raise InputError(f"文件不存在：{path}")
    try:
        with open(path, "rb") as f:
            magic = f.read(8)
            f.seek(0)

            if magic == MAGIC_V1:
                return _info_v1(path, f)
            if magic == MAGIC_V2:
                return _info_v2(path, f)
            raise InputError("不是 MultiCalc 加密文件")
    except InputError:
        raise
    except Exception as e:
        raise InputError(f"读取文件头失败：{e}")


def _info_v1(path, f) -> dict:
    f.read(8)
    version = f.read(1)[0]
    kdf_type = f.read(1)[0]
    iterations = struct.unpack(">I", f.read(4))[0]
    salt = f.read(SALT_SIZE)
    original_size = struct.unpack(">Q", f.read(8))[0]
    chunk_size = struct.unpack(">I", f.read(4))[0]
    f.read(NONCE_PREFIX_SIZE)
    file_size = os.path.getsize(path)
    return {
        "format": "v1",
        "version": version,
        "cipher": "AES-256-GCM",
        "kdf": {1: "PBKDF2-HMAC-SHA256",
                2: "Scrypt"}.get(kdf_type, "unknown"),
        "iterations": iterations,
        "salt_hex": salt.hex().upper(),
        "original_size": original_size,
        "chunk_size": chunk_size,
        "file_size": file_size,
        "overhead": file_size - original_size,
    }


def _info_v2(path, f) -> dict:
    f.read(8)
    version = f.read(1)[0]
    cipher_type = f.read(1)[0]
    kdf_type = f.read(1)[0]
    kdf_param = struct.unpack(">I", f.read(4))[0]
    salt = f.read(SALT_SIZE)
    original_size = struct.unpack(">Q", f.read(8))[0]
    chunk_size = struct.unpack(">I", f.read(4))[0]
    f.read(NONCE_PREFIX_SIZE)
    has_keyfile = f.read(1)[0] == 1
    file_size = os.path.getsize(path)
    return {
        "format": "v2",
        "version": version,
        "cipher": {1: "AES-256-GCM",
                   2: "ChaCha20-Poly1305"}.get(
                       cipher_type, "unknown"),
        "kdf": {1: "PBKDF2-HMAC-SHA256",
                2: "Scrypt",
                3: "Argon2id"}.get(kdf_type, "unknown"),
        "kdf_param": kdf_param,
        "salt_hex": salt.hex().upper(),
        "original_size": original_size,
        "chunk_size": chunk_size,
        "has_keyfile": has_keyfile,
        "file_size": file_size,
        "overhead": file_size - original_size,
    }


def is_encrypted_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            m = f.read(8)
            return m in (MAGIC_V1, MAGIC_V2)
    except Exception:
        return False


# ===========================================================================
# 工具
# ===========================================================================

def gen_random_hex(n_bytes=32) -> str:
    return secrets.token_hex(int(n_bytes)).upper()