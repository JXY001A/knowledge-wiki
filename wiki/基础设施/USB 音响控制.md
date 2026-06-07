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

> DevMechin 外接 USB 音响的设备识别与命令行控制方法。Jieli Technology USB Composite Device，通过 PipeWire + ALSA 驱动。

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

### 测试音

```bash
# 440Hz 正弦波，1 秒
speaker-test -D plughw:2,0 -t sine -f 440 -l 1
```

### 音阶

```bash
# C 大调上行：C E G C'
for f in 523 659 784 1047; do
    speaker-test -D plughw:2,0 -t sine -f $f -l 1 2>/dev/null
    sleep 0.15
done
```

### 播放音频文件（需安装解码器）

```bash
# WAV 原文件
aplay -D plughw:2,0 file.wav

# MP3 / FLAC（PipeWire）
pw-play file.mp3
```

### 白噪声 / 粉红噪声

```bash
speaker-test -D plughw:2,0 -t pink -l 3
```

## 排障

| 现象 | 原因 | 解决 |
|------|------|------|
| `找不到音效卡` | 用户不在 `audio` 组 | `usermod -a -G audio` + 重登 |
| `Cannot get card index` | PipeWire 独占设备，需用 `plughw` | 使用 `plughw:2,0` 而非 `hw:2,0` |
| 设备突然不可用 | USB 断开重连后编号可能变化 | 检查 `/proc/asound/cards` 确认 card 编号 |
| `没有那个设备` | ALSA 无法直接访问，PipeWire 占用 | 改用 `pw-play` 或等待 PipeWire 释放 |

## 相关

- [[DevMechin（AI 主机）]]
- [[RGB 灯带控制]]
- [[Wiki 目录]]
