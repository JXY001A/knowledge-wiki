"""speak-text 技能实现 — edge-tts 中文语音合成 + USB 音响播放."""

import asyncio
import subprocess
import re


def execute(context: dict) -> str:
    """企业微信指令 → TTS 语音合成 → USB 音响播放。

    context 需包含:
        input_text: 用户消息（如 "说 飞飞你在干嘛"）
        user_id: 企业微信用户 ID
        send_md: 发送 markdown 消息的函数
    """
    text = context.get("input_text", "").strip()
    user_id = context.get("user_id", "")
    send_md = context.get("send_md")

    # 去除 ? 前缀和触发词
    text = re.sub(r'^\?\s*', '', text)
    for prefix in ["说", "speak", "说话", "喊", "播放", "朗读"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            text = re.sub(r'^[：:，,\s]+', '', text)
            break

    if not text:
        if send_md:
            send_md(user_id, "请输入要说的内容，如：`说 你好`")
        return ""

    try:
        from knowledge_wiki.config import settings
        device = settings.tts_speaker_device

        async def _gen():
            import edge_tts
            communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
            await communicate.save("/tmp/speak-text.mp3")

        asyncio.run(_gen())

        subprocess.run(
            ["mpg123", "-q", "-w", "/tmp/speak-text.wav", "/tmp/speak-text.mp3"],
            timeout=10,
        )
        subprocess.run(
            ["aplay", "-q", "-D", device, "/tmp/speak-text.wav"],
            timeout=10,
        )

        if send_md:
            send_md(user_id, f"已播放：{text[:50]}")

        return ""

    except Exception as e:
        print(f"[speak-text] failed: {e}", flush=True)
        if send_md:
            send_md(user_id, f"语音播放失败：{e}")
        return ""
