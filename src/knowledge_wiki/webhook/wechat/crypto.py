"""企业微信消息加解密 — AES-256-CBC + SHA1 签名."""

import base64
import hashlib
import socket
import struct
from knowledge_wiki.config import settings


def _aes_key_bytes() -> bytes:
    """Base64 解码 AES Key（追加 '=' 补齐 padding）."""
    return base64.b64decode(settings.wecom_aes_key + "=")


def _pkcs7_unpad(data: bytes) -> bytes:
    """PKCS7 去填充."""
    n = data[-1]
    if n < 1 or n > 32:
        raise ValueError("bad PKCS7 padding")
    return data[:-n]


def decrypt_msg(encrypted: str) -> str:
    """AES 解密企业微信回调消息."""
    from Crypto.Cipher import AES

    aes_key = _aes_key_bytes()
    cipher = base64.b64decode(encrypted)
    cipher_obj = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
    plain = cipher_obj.decrypt(cipher)
    plain = _pkcs7_unpad(plain)
    msg_len = socket.ntohl(struct.unpack("I", plain[16:20])[0])
    msg = plain[20:20 + msg_len].decode("utf-8")
    corp_id = plain[20 + msg_len:].decode("utf-8")
    if corp_id != settings.wecom_corp_id:
        raise ValueError(f"CorpID mismatch: {corp_id} != {settings.wecom_corp_id}")
    return msg


def verify_signature(signature: str, timestamp: str, nonce: str, echostr: str) -> bool:
    """验证企业微信回调签名."""
    params = sorted([settings.wecom_token, timestamp, nonce, echostr])
    return hashlib.sha1("".join(params).encode()).hexdigest() == signature
