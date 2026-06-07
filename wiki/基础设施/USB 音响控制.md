---
title: USB 音响控制
type: topic
tags: [基础设施, 硬件, 音频]
aliases: [音响, 音箱, 扬声器, 外放]
created: 2026-06-07
updated: 2026-06-07
sources: []
confidence: high
---

> DevMechin 外接 USB 音响的设备识别与命令行控制方法。Jieli Technology USB Composite Device，通过 ALSA 直接驱动（绕过 PipeWire）。

## 设备信息

| 属性 | 值 |
|------|-----|
| 设备名 | USB Composite Device |
| 制造商 | Jieli Technology |
| 连接方式 | USB（主板 `00:14.0`，端口 `10.2`） |
| ALSA 声卡编号 | `2`（card 2: Device） |
| 驱动 | `snd_usb_audio` |
| PCM 播放设备 | `/dev/snd/pcmC2D0p` |
| 音频服务 | PipeWire（用户级） + WirePlumber（会话管理） |

## 权限

- 设备文件属主 `root:audio`，`660` 权限
- 用户必须在 `audio` 组内才能访问

```bash
sudo usermod -a -G audio $USER
# 重新登录 SSH 生效
```

验证权限：

```bash
groups | grep audio
```

## 播放命令

> 所有命令需要 `sg audio -c` 前缀（如果 SSH 会话尚未加载 audio 组），或重新登录后直接用。

### 测试音

```bash
# 440Hz 正弦波，1 秒
sg audio -c 'speaker-test -D plughw:2,0 -t sine -f 440 -l 1'

# 交替高低音（6 声）
sg audio -c 'for f in 440 880 440 880 440 880; do
    speaker-test -D plughw:2,0 -t sine -f $f -l 1 2>/dev/null; sleep 0.3; done'
```

### 播放音频文件

```bash
# WAV（推荐 — 最稳定）
sg audio -c 'aplay -q -D plughw:2,0 file.wav'

# MP3（先转为 WAV 再播放）
mpg123 -q -w /tmp/output.wav input.mp3
sg audio -c 'aplay -q -D plughw:2,0 /tmp/output.wav'
```

### TTS 语音合成

```bash
# 安装 Microsoft Edge TTS
pip3 install edge-tts --break-system-packages

# 生成中文语音并播放
python3 -c "
import asyncio, edge_tts
async def main():
    tts = edge_tts.Communicate('你好，我是金显昱的小音响', 'zh-CN-XiaoxiaoNeural')
    await tts.save('/tmp/speech.mp3')
asyncio.run(main())
"
mpg123 -q -w /tmp/speech.wav /tmp/speech.mp3
sg audio -c 'aplay -q -D plughw:2,0 /tmp/speech.wav'
```

### 白噪声 / 粉红噪声

```bash
sg audio -c 'speaker-test -D plughw:2,0 -t pink -l 3'
```

## 排障

| 现象 | 原因 | 解决 |
|------|------|------|
| `找不到音效卡` | 用户不在 `audio` 组 | `usermod -a -G audio` + 重登 |
| PipeWire 抢占导致没声音 | WirePlumber 自动接管 USB 设备，`pw-play` 走 null sink | 绕过 PipeWire，直接用 ALSA `plughw:2,0` |
| `Cannot get card index` | PipeWire 独占设备 | 使用 `plughw:2,0` 而非 `hw:2,0` |
| 设备突然不可用 | USB 断开重连后编号可能变化 | `cat /proc/asound/cards` 确认 card 编号 |
| `mpg123` 输出无声音 | MP3 采样率与设备不匹配 | 先转为 48kHz WAV 再 `aplay` |

## 相关

- [[DevMechin（AI 主机）]]
- [[RGB 灯带控制]]
- [[Wiki 目录]]
