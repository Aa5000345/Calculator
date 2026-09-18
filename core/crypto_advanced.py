"""高级加密算法：PQC + 其他常用算法。

覆盖：
- PQC：
  - ML-KEM-512/768/1024  密钥封装（NIST FIPS 203）
  - ML-DSA-44/65/87      数字签名（NIST FIPS 204）
  - SLH-DSA-SHA2-128s    哈希签名（NIST FIPS 205）
- 对称加密：
  - AES-256-GCM          已有的扩展
  - ChaCha20-Poly1305    RFC 8439
- 非对称加密：
  - Ed25519              签名
  - X25519               密钥交换
- 密钥派生：
  - Argon2id             RFC 9106（推荐）
  - Scrypt               RFC 7914
  - PBKDF2               RFC 8018
- 密码哈希：
  - Argon2               （需要 argon2-cffi）
  - bcrypt               （需要 bcrypt）
- 编码：
  - Base58               Bitcoin 风格（无外部依赖）
  - Base32               RFC 4648
  - Base85 / Ascii85
  - Base91

设计：
- 不直接依赖 cryptography 的所有子模块：延迟导入，失败时返回清晰错误
- 后端能力探测：`backend_info()` 返回当前可用算法
- 所有操作返回 dict，便于 UI 展示
"""
from __future__ import annotations

import hashlib
import hmac
import os
import struct
import time
from dataclasses import dataclass

from core.errors import InputError
from core.logger import log_warn


# ===========================================================================
# 后端探测
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
    """探测当前环境的加密后端能力（结果缓存）。"""
    global _BACKEND_CACHE
    if _BACKEND_CACHE is not None and not force:
        return _BACKEND_CACHE

    info = BackendInfo()

    # cryptography
    try:
        import cryptography
        info.has_cryptography = True
        info.cryptography_version = getattr(
            cryptography, "__version__", "")
    except ImportError:
        pass

    # OpenSSL 版本
    try:
        from cryptography.hazmat.backends.openssl.backend import (
            backend,
        )
        info.openssl_version = backend.openssl_version_text()
    except Exception:
        pass

    # PQC 支持探测
    if info.has_cryptography:
        try:
            from cryptography.hazmat.primitives.asymmetric import (
                mlkem,
            )
            info.has_pqc_mlkem = hasattr(
                mlkem, "generate_keypair") or hasattr(
                mlkem, "MLKEM768")
        except Exception:
            pass
        try:
            from cryptography.hazmat.primitives.asymmetric import (
                mldsa,
            )
            info.has_pqc_mldsa = True
        except Exception:
            pass
        try:
            from cryptography.hazmat.primitives.asymmetric import (
                slhdsa,
            )
            info.has_pqc_slhdsa = True
        except Exception:
            pass

    # argon2-cffi
    try:
        import argon2  # noqa: F401
        info.has_argon2 = True
    except ImportError:
        pass

    # bcrypt
    try:
        import bcrypt  # noqa: F401
        info.has_bcrypt = True
    except ImportError:
        pass

    # pycryptodome
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

# 安全级别 → 参数字典
_MLKEM_PARAMS = {
    "ML-KEM-512": "MLKEM512",
    "ML-KEM-768": "MLKEM768",
    "ML-KEM-1024": "MLKEM1024",
}


def mlkem_generate(level: str = "ML-KEM-768") -> dict:
    """生成 ML-KEM 密钥对。

    Args:
        level: ``"ML-KEM-512"`` / ``"ML-KEM-768"`` / ``"ML-KEM-1024"``

    Returns:
        ``{"level", "public_key", "private_key", "pk_size", "sk_size"}``
        密钥以 hex 字符串返回。
    """
    _require_cryptography()
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

    # 不同版本的 API 可能不同
    try:
        pk_bytes = _serialize_public(sk.public_key())
        sk_bytes = _serialize_private(sk)
    except Exception:
        # 旧版 API：直接有 .public_key() / .private_key()
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
    """用对方公钥封装一个共享密钥。

    Returns:
        ``{"level", "ciphertext", "shared_secret", ...}``
    """
    _require_cryptography()
    try:
        from cryptography.hazmat.primitives.asymmetric import mlkem
    except ImportError:
        raise InputError("当前 cryptography 不支持 ML-KEM")

    name = _MLKEM_PARAMS.get(level.upper())
    cls = getattr(mlkem, name, None)
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
    """解封装，恢复共享密钥。"""
    _require_cryptography()
    try:
        from cryptography.hazmat.primitives.asymmetric import mlkem
    except ImportError:
        raise InputError("当前 cryptography 不支持 ML-KEM")

    name = _MLKEM_PARAMS.get(level.upper())
    cls = getattr(mlkem, name, None)
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
    """生成 ML-DSA 签名密钥对。"""
    _require_cryptography()
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
    """用 ML-DSA 私钥签名。"""
    _require_cryptography()
    try:
        from cryptography.hazmat.primitives.asymmetric import mldsa
    except ImportError:
        raise InputError("当前 cryptography 不支持 ML-DSA")

    name = _MLDSA_PARAMS.get(level.upper())
    cls = getattr(mldsa, name, None)
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
    """验证 ML-DSA 签名。"""
    _require_cryptography()
    try:
        from cryptography.hazmat.primitives.asymmetric import mldsa
    except ImportError:
        raise InputError("当前 cryptography 不支持 ML-DSA")

    name = _MLDSA_PARAMS.get(level.upper())
    cls = getattr(mldsa, name, None)
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


def slhdsa_generate(level: str = "SLH-DSA-SHA2-128s") -> dict:
    """生成 SLH-DSA 签名密钥对（保守安全：仅依赖哈希）。"""
    _require_cryptography()
    if level not in _SLHDSA_PARAMS:
        raise InputError(f"不支持的 SLH-DSA 参数：{level}")

    try:
        from cryptography.hazmat.primitives.asymmetric import (
            slhdsa,
        )
    except ImportError:
        raise InputError(
            "当前 cryptography 不支持 SLH-DSA；需要 cryptography>=48")

    cls = getattr(slhdsa, level.replace("-", "_"), None)
    if cls is None:
        # 尝试其他命名
        for attr in dir(slhdsa):
            if attr.upper().replace("_", "-") == level.upper():
                cls = getattr(slhdsa, attr)
                break
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
    _require_cryptography()
    if level not in _SLHDSA_PARAMS:
        raise InputError(f"不支持的 SLH-DSA 参数：{level}")
    try:
        from cryptography.hazmat.primitives.asymmetric import (
            slhdsa,
        )
    except ImportError:
        raise InputError("当前 cryptography 不支持 SLH-DSA")

    cls = getattr(slhdsa, level.replace("-", "_"), None)
    if cls is None:
        for attr in dir(slhdsa):
            if attr.upper().replace("_", "-") == level.upper():
                cls = getattr(slhdsa, attr)
                break
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
    _require_cryptography()
    if level not in _SLHDSA_PARAMS:
        raise InputError(f"不支持的 SLH-DSA 参数：{level}")
    try:
        from cryptography.hazmat.primitives.asymmetric import (
            slhdsa,
        )
    except ImportError:
        raise InputError("当前 cryptography 不支持 SLH-DSA")

    cls = getattr(slhdsa, level.replace("-", "_"), None)
    if cls is None:
        for attr in dir(slhdsa):
            if attr.upper().replace("_", "-") == level.upper():
                cls = getattr(slhdsa, attr)
                break
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
    """ChaCha20-Poly1305 加密（RFC 8439）。"""
    _require_cryptography()
    from cryptography.hazmat.primitives.ciphers.aead import (
        ChaCha20Poly1305,
    )
    try:
        key = bytes.fromhex(str(key_hex).strip())
    except Exception as e:
        raise InputError(f"密钥 hex 解析失败：{e}")
    if len(key) != 32:
        raise InputError("ChaCha20 密钥必须为 32 字节（64 hex 字符）")

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
    """ChaCha20-Poly1305 解密。"""
    _require_cryptography()
    from cryptography.hazmat.primitives.ciphers.aead import (
        ChaCha20Poly1305,
    )
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
    _require_cryptography()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
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
        "public_hex": sk.public_key().public_bytes_raw().hex().upper(),
        "pk_size": 32, "sk_size": 32,
    }


def ed25519_sign(private_hex: str, message: str) -> dict:
    _require_cryptography()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
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
    _require_cryptography()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
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
    _require_cryptography()
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
    )
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
        "public_hex": sk.public_key().public_bytes_raw().hex().upper(),
    }


def x25519_shared(private_hex: str, peer_public_hex: str) -> dict:
    """计算共享密钥。"""
    _require_cryptography()
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey, X25519PublicKey,
    )
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
# 密码哈希：Argon2id / bcrypt
# ===========================================================================

def argon2_hash(password: str, *, time_cost: int = 3,
                memory_cost: int = 65536,
                parallelism: int = 4) -> dict:
    """Argon2id 哈希（推荐用于密码存储）。"""
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
# 编码：Base58 / Base32 / Base85 / Base91
# ===========================================================================

_B58_ALPHABET = (
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    "abcdefghijkmnopqrstuvwxyz"
)


def base58_encode(text: str) -> str:
    """Base58 编码（Bitcoin 风格）。"""
    data = str(text).encode("utf-8")
    n = int.from_bytes(data, "big")
    out = []
    while n > 0:
        n, r = divmod(n, 58)
        out.append(_B58_ALPHABET[r])
    # 前导零字节
    for b in data:
        if b == 0:
            out.append(_B58_ALPHABET[0])
        else:
            break
    return "".join(reversed(out)) or _B58_ALPHABET[0]


def base58_decode(s: str) -> str:
    s = str(s).strip()
    if not s:
        return ""
    n = 0
    for ch in s:
        idx = _B58_ALPHABET.find(ch)
        if idx < 0:
            raise InputError(f"非法 Base58 字符：{ch!r}")
        n = n * 58 + idx
    # 前导 '1' → 前导零字节
    n_zeros = 0
    for ch in s:
        if ch == _B58_ALPHABET[0]:
            n_zeros += 1
        else:
            break
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return (b"\x00" * n_zeros + body).decode("utf-8", errors="replace")


def base32_encode(text: str, padding: bool = True) -> str:
    import base64
    data = str(text).encode("utf-8")
    out = base64.b32encode(data).decode("ascii")
    return out if padding else out.rstrip("=")


def base32_decode(s: str) -> str:
    import base64
    s = str(s).strip()
    pad = (-len(s)) % 8
    s += "=" * pad
    try:
        data = base64.b32decode(s)
    except Exception as e:
        raise InputError(f"Base32 解码失败：{e}")
    return data.decode("utf-8", errors="replace")


def base85_encode(text: str) -> str:
    import base64
    return base64.b85encode(str(text).encode("utf-8")).decode("ascii")


def base85_decode(s: str) -> str:
    import base64
    try:
        data = base64.b85decode(str(s).strip().encode("ascii"))
    except Exception as e:
        raise InputError(f"Base85 解码失败：{e}")
    return data.decode("utf-8", errors="replace")


def ascii85_encode(text: str) -> str:
    import base64
    return base64.a85encode(str(text).encode("utf-8")).decode("ascii")


def ascii85_decode(s: str) -> str:
    import base64
    try:
        data = base64.a85decode(str(s).strip().encode("ascii"))
    except Exception as e:
        raise InputError(f"Ascii85 解码失败：{e}")
    return data.decode("utf-8", errors="replace")


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
                hash_secret_raw, Type,
            )
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
        _require_cryptography()
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        try:
            kdf = Scrypt(salt=salt, length=length,
                         n=1 << 15, r=8, p=1)
            key = kdf.derive(str(password).encode("utf-8"))
        except Exception as e:
            raise InputError(f"Scrypt 派生失败：{e}")
    elif algorithm == "pbkdf2":
        _require_cryptography()
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import (
            PBKDF2HMAC,
        )
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
# 内部工具
# ===========================================================================

def _require_cryptography():
    try:
        import cryptography  # noqa: F401
    except ImportError:
        raise InputError(
            "需要 cryptography：pip install cryptography")


def _as_bytes(x) -> bytes:
    """把 cryptography 的返回值统一转 bytes。"""
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    # 某些 API 返回带 .raw 属性的对象
    if hasattr(x, "raw"):
        return bytes(x.raw)
    if hasattr(x, "__bytes__"):
        return bytes(x)
    # SharedSecret 等：可能有 .secret 或直接用 bytes
    try:
        return bytes(x)  # type: ignore[arg-type]
    except Exception:
        raise InputError(f"无法转为 bytes：{type(x)}")


def _serialize_public(pk) -> bytes:
    """序列化公钥为 raw bytes（如果可用），否则用 PEM。"""
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


__all__ = [
    # 后端
    "BackendInfo", "backend_info",
    # PQC
    "mlkem_generate", "mlkem_encapsulate", "mlkem_decapsulate",
    "mldsa_generate", "mldsa_sign", "mldsa_verify",
    "slhdsa_generate", "slhdsa_sign", "slhdsa_verify",
    # 对称
    "chacha20_encrypt", "chacha20_decrypt", "chacha20_gen_key",
    # 非对称
    "ed25519_generate", "ed25519_sign", "ed25519_verify",
    "x25519_generate", "x25519_shared",
    # 密码哈希
    "argon2_hash", "argon2_verify",
    "bcrypt_hash", "bcrypt_verify",
    # 编码
    "base58_encode", "base58_decode",
    "base32_encode", "base32_decode",
    "base85_encode", "base85_decode",
    "ascii85_encode", "ascii85_decode",
    # 派生
    "derive_key",
]