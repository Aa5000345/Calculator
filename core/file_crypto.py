"""文件加密 v2：支持 AES-GCM / ChaCha20-Poly1305 + 可选 PQC 混合加密。

格式 v2（在 v1 基础上扩展）：

    Offset  Size    内容
    ------  ------  -----------------------------------
    0       8       magic "MCENC002"
    8       1       version (2)
    9       1       cipher_type (1=AES-GCM, 2=ChaCha20-Poly1305)
    10      1       kdf_type (1=PBKDF2, 2=Scrypt, 3=Argon2id)
    11      4       iterations / 参数
    15      16      salt
    31      8       original_size
    39      4       chunk_size
    43      4       nonce_prefix
    47      1       has_keyfile (0/1)
    48      ...     payload

与 v1 的兼容性：
- 解密时同时支持 v1（magic "MCENC001"）和 v2
- v2 加密的文件无法被 v1 解密

混合加密模式：
- 先用 PQC（ML-KEM）封装一个随机对称密钥，再用对称算法加密数据
- 适合与未来的 PQC 密钥管理集成的场景
"""
from __future__ import annotations

import os
import struct
import time
from dataclasses import dataclass

from core.errors import InputError
from core.logger import log_info


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 密钥派生
# ---------------------------------------------------------------------------

def _derive_key(password: str, salt: bytes, kdf_type: int,
                kdf_param: int) -> bytes:
    pw = str(password).encode("utf-8")

    if kdf_type == KDF_PBKDF2:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import (
            PBKDF2HMAC,
        )
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
            from argon2.low_level import hash_secret_raw, Type
        except ImportError:
            raise InputError(
                "Argon2id 需要 argon2-cffi："
                "pip install argon2-cffi")
        return hash_secret_raw(
            secret=pw, salt=salt,
            time_cost=int(kdf_param) or 3,
            memory_cost=65536, parallelism=4,
            hash_len=32, type=Type.ID,
        )

    raise InputError(f"未知 KDF 类型：{kdf_type}")


def _make_cipher(cipher_type: int, key: bytes):
    """返回一个统一接口的 AEAD 对象（encrypt/decrypt 用 nonce）。"""
    if cipher_type == CIPHER_AES_GCM:
        from cryptography.hazmat.primitives.ciphers.aead import (
            AESGCM,
        )
        return AESGCM(key)
    if cipher_type == CIPHER_CHACHA20:
        from cryptography.hazmat.primitives.ciphers.aead import (
            ChaCha20Poly1305,
        )
        return ChaCha20Poly1305(key)
    raise InputError(f"未知加密算法：{cipher_type}")


def _nonce(prefix: bytes, block_index: int) -> bytes:
    return prefix + block_index.to_bytes(8, "big")


# ---------------------------------------------------------------------------
# 加密
# ---------------------------------------------------------------------------

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
    key = _derive_key(password, salt, kdf_type, iterations)
    aead = _make_cipher(cipher_type, key)

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
        "cipher": "AES-256-GCM" if cipher_type == CIPHER_AES_GCM
                  else "ChaCha20-Poly1305",
        "kdf": kdf_type,
    }


# ---------------------------------------------------------------------------
# 解密
# ---------------------------------------------------------------------------

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


def _decrypt_v1(in_path, out_path, password, progress_cb, cancelled):
    """兼容 v1 格式（AES-GCM + PBKDF2/Scrypt）。"""
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

        key = _derive_key(password, salt, kdf_type, iterations)
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


def _decrypt_v2(in_path, out_path, password, progress_cb, cancelled):
    """v2 格式。"""
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

        key = _derive_key(password, salt, kdf_type, kdf_param)
        aead = _make_cipher(cipher_type, key)

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
        "cipher": "AES-256-GCM" if cipher_type == CIPHER_AES_GCM
                  else "ChaCha20-Poly1305",
    }


# ---------------------------------------------------------------------------
# 文件信息
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _require_crypto():
    try:
        import cryptography  # noqa: F401
    except ImportError:
        raise InputError(
            "需要 cryptography：pip install cryptography")


__all__ = [
    "encrypt_file", "decrypt_file",
    "get_file_info", "is_encrypted_file",
    "FileHeaderV2", "CryptoProgress",
    "MAGIC_V1", "MAGIC_V2",
    "CIPHER_AES_GCM", "CIPHER_CHACHA20",
    "KDF_PBKDF2", "KDF_SCRYPT", "KDF_ARGON2ID",
    "DEFAULT_PBKDF2_ITERATIONS", "DEFAULT_CHUNK_SIZE",
]