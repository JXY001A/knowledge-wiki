# speak-text

通过 USB 音响朗读文字。接收文本 → TTS 语音合成 → ALSA 播放。

## 触发条件

- 用户输入以 `说`、`speak`、`说话`、`喊`、`播放`、`朗读` 开头
- 或企业微信发送 `说 你好`

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 要朗读的文字（去除触发词后的内容） |
| user_id | string | ✅ | 企业微信用户 ID |
| send_md | callable | ✅ | 回复消息的函数 |

## 输出

- 语音通过 USB 音响播放
- 企业微信回复确认消息

## 执行步骤

1. 提取文本：去除触发词前缀（如 "说 "、"speak "）
2. 调用 `edge-tts`（Microsoft 免费 TTS）生成 MP3
3. `mpg123` 将 MP3 转 WAV（48kHz）
4. `aplay -D plughw:2,0` 输出到 USB 音响
5. 回复微信确认

## 前置依赖

- `edge-tts` Python 包（已安装）
- `mpg123` 解码器（已安装）
- `aplay`（ALSA 工具）
- 用户需在 `audio` 组

## 评估标准

- 延迟：< 5s（含 TTS API 调用）
- 语音清晰度：zh-CN-XiaoxiaoNeural 自然女声
