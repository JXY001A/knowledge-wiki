---
title: USB 音响控制
type: topic
tags: [基础设施, 硬件, 音频]
aliases: [音响, 音箱, 扬声器, 外放, 麦克风]
created: 2026-06-07
updated: 2026-06-08
sources: []
confidence: high
---

> DevMechin 外接 USB 音响+麦克风一体设备的硬件参数、权限配置与控制方法。共 2 块 Jieli Technology USB Composite Device，通过 ALSA 直接驱动（PipeWire 已屏蔽）。

## 设备信息

| 属性 | Card 2 | Card 3 |
|------|--------|--------|
| 设备名 | USB Composite Device | USB Composite Device |
| USB ID | `2d99:a074` | `4c4a:4155` |
| 制造商 | Jieli Technology | Jieli Technology |
| USB 端口 | `00:14.0` → 端口 `10.2` | `00:14.0` → 端口 `10.1` |
| 驱动 | `snd_usb_audio` | `snd_usb_audio` |
| 类型 | 麦克风 + 音箱一体 | 麦克风 + 音箱一体 |
| PCM 录音 | `/dev/snd/pcmC2D0c` | `/dev/snd/pcmC3D0c` |
| PCM 播放 | `/dev/snd/pcmC2D0p` | `/dev/snd/pcmC3D0p` |

### 音频参数

| 参数 | 麦克风（Capture） | 音箱（Playback） |
|------|-------------------|-------------------|
| 采样率 | 48000 Hz | 48000 Hz |
| 位深度 | S16_LE（16bit） | S16_LE（16bit） |
| 声道 | **1ch（Mono）** | **2ch（Stereo）** |
| 硬件音量范围 | 0–147（-28.37dB ~ -0.94dB） | 0–147（-28.37dB ~ -0.94dB） |

> **注意**：麦克风只支持单声道，音箱只支持立体声。直接 `arecord \| aplay` 会导致声道不匹配报警，需通过 `plughw` 自动转换，或 `sox` 重采样。

### Mixer 控制项

| 控制 | 类型 | 说明 |
|------|------|------|
| PCM Playback Volume | 音量（0–147） | 音箱输出 |
| PCM Playback Switch | 开关 | 音箱静音 |
| Mic Capture Volume | 音量（0–147） | 麦克风增益 |
| Mic Capture Switch | 开关 | 麦克风静音 |
| Auto Gain Control | 开关 | 自动增益（建议开启） |

**无 Mic Boost 硬件**，最大物理增益仅 -0.94dB。需要更大音量时用 `sox gain` 做软件放大（见下文）。

## 权限

设备文件属主 `root:audio`，`660` 权限。由于 systemd 用户服务不继承 `audio` 组，采用 **ACL 直接赋权** 方案：

```bash
# 一次性设置（设备重连后需重新执行）
sudo setfacl -m u:jxy001a1:rw /dev/snd/pcmC2D0c /dev/snd/pcmC2D0p \
    /dev/snd/pcmC3D0c /dev/snd/pcmC3D0p /dev/snd/controlC2 /dev/snd/controlC3
```

**持久化**：udev 规则 `/etc/udev/rules.d/99-alsa-acl.rules`，设备插入时自动应用 ACL。

## PipeWire 状态

DevMechin 上 PipeWire/WirePlumber 已在用户级 **屏蔽**（mask），原因：

1. **不识别 USB 声卡**：headless 环境 `alsa_monitor` 不工作，始终只有 null sink
2. **独占设备**：即使不显示设备，PipeWire 仍 mmap 锁定 PCM 节点，阻止 ALSA 直接访问
3. **GDM 冲突**：GDM 的 WirePlumber 也持有 control 设备句柄

恢复（如果需要桌面环境音频）：

```bash
systemctl --user unmask pipewire.service pipewire.socket \
    pipewire-pulse.service pipewire-pulse.socket wireplumber.service
systemctl --user start pipewire pipewire-pulse wireplumber
```

## 播放命令

### 测试音

```bash
# 440Hz 正弦波
speaker-test -D plughw:2,0 -t sine -f 440 -l 1
# 交替高低音
for f in 440 880 440 880 440 880; do
    speaker-test -D plughw:2,0 -t sine -f $f -l 1 2>/dev/null; sleep 0.3
done
```

### 播放音频文件

```bash
aplay -q -D plughw:2,0 file.wav          # WAV 直播
mpg123 -q -w /tmp/output.wav input.mp3   # MP3 → WAV
```

### TTS 语音合成

```bash
python3 -c "
import asyncio, edge_tts
async def main():
    tts = edge_tts.Communicate('你好，我是金显昱的小音响', 'zh-CN-XiaoxiaoNeural')
    await tts.save('/tmp/speech.mp3')
asyncio.run(main())
"
mpg123 -q -w /tmp/speech.wav /tmp/speech.mp3 && aplay -q -D plughw:2,0 /tmp/speech.wav
```

## 麦克风录制

### 测试录音

```bash
arecord -D plughw:2,0 -f S16_LE -r 48000 -c 1 -d 3 /tmp/test.wav
aplay /tmp/test.wav   # 回放检查
```

### 实时监听（麦克风 → 音箱环回）

systemd 用户服务 `~/.config/systemd/user/alsa-loopback.service`：

```ini
[Service]
Type=simple
ExecStart=/usr/bin/bash -c "while true; do \
    arecord -D plughw:2,0 -f S16_LE -r 48000 -c 1 2>/dev/null | \
    sox -t wav - -t wav - gain 30 2>/dev/null | \
    aplay -D plughw:2,0 -f S16_LE -r 48000 -c 2 2>/dev/null; \
    sleep 1; done"
Restart=always
RestartSec=3
```

操作：

```bash
systemctl --user start alsa-loopback.service    # 开启监听
systemctl --user stop alsa-loopback.service     # 关闭监听
systemctl --user status alsa-loopback.service   # 查看状态
```

`sox gain 30` 为软件增益（+30dB），补偿硬件无 Mic Boost 的问题。范围建议 10–50，太大有破音风险。

## 排障

| 现象 | 原因 | 解决 |
|------|------|------|
| `找不到音效卡` | PipeWire 占用或其他进程锁定了 PCM | `sudo fuser /dev/snd/pcmC2D0*` 杀掉占用进程 |
| `设备或资源忙` | PipeWire mmap 独占 | 已屏蔽 PipeWire，如恢复则需停止 |
| 环回无声 | ACL 失效（设备重连后） | 重跑 `setfacl` 或 `sudo udevadm trigger` |
| 麦克风声音小 | 硬件无 Boost，最大仅 -0.94dB | 加大 `sox gain` 值（当前 30） |
| 设备编号变化 | USB 口更换或重连顺序不同 | `cat /proc/asound/cards` 确认，按 USB ID 区分 |
| systemd 服务 `audio` 组报错 | 用户级 systemd 不支持 `SupplementaryGroups` | 使用 ACL 方案代替 |

## 相关

- [[DevMechin（AI 主机）]]
- [[RGB 灯带控制]]
- [[Wiki 目录]]
