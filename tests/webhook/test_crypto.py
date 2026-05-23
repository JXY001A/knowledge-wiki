"""企业微信加解密测试."""

import hashlib

from knowledge_wiki.webhook.wechat.crypto import _pkcs7_unpad


def test_pkcs7_unpad_normal():
    """正常 PKCS7 去填充."""
    # 16 字节数据，padding 值为 5（即 5 个 0x05）
    data = b"Hello World!!\x00\x04" + b"\x05\x05\x05\x05\x05"
    # 实际：我们构造一个 11 字节 payload + 5 字节 padding
    payload = b"Hello World!"
    padded = payload + b"\x05" * 5  # 11 + 5 = 16
    result = _pkcs7_unpad(padded)
    assert result == payload


def test_pkcs7_unpad_invalid():
    """无效 padding 抛出 ValueError."""
    # 最后一个字节为 0
    try:
        _pkcs7_unpad(b"Hello World!\x00")
        assert False, "应抛出 ValueError"
    except ValueError:
        pass


def test_verify_signature_known_input():
    """SHA1 签名验证逻辑正确."""
    from knowledge_wiki.webhook.wechat.crypto import verify_signature

    # 固定输入，手动计算 SHA1
    token = "test_token"
    timestamp = "1234567890"
    nonce = "abcdefg"
    echostr = "hello"

    from knowledge_wiki.config import settings

    # Mock settings
    settings.wecom_token = "test_token"
    expected_params = sorted([token, timestamp, nonce, echostr])
    expected_sig = hashlib.sha1("".join(expected_params).encode()).hexdigest()

    assert verify_signature(expected_sig, timestamp, nonce, echostr) is True
    assert verify_signature("wrong_sig", timestamp, nonce, echostr) is False
