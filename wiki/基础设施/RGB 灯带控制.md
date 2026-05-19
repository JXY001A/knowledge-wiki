---
title: RGB 灯带控制
type: topic
tags: [基础设施, 硬件]
aliases: [RGB控制, 关灯]
created: 2026-05-19
updated: 2026-05-19
sources: []
confidence: medium
---

> DevMechin 主机 RGB 设备清单与控制方法记录。主板 5 区 + 显卡 5 区 + 内存 2 组共 4 个 RGB 设备，当前使用 OpenRGB 进行控制。

## 设备清单

```bash
# 扫描命令
sudo openrgb -l
```

| 设备 | 型号 | 接口 | 灯区数 | 关灯模式 |
|------|------|------|--------|----------|
| 主板 | Z790M AORUS ELITE AX ICE（IT5701） | HID `/dev/hidraw3` | 5 | Direct + 黑 |
| 显卡 | Gigabyte RTX 4080 SUPER GAMING OC | I2C `/dev/i2c-7` | 5 | Direct + 黑 |
| 内存 0 | ENE DRAM | I2C `/dev/i2c-6` addr 0x71 | 1（8 灯） | Off 模式 |
| 内存 1 | ENE DRAM | I2C `/dev/i2c-6` addr 0x73 | 1（8 灯） | Off 模式 |

### 主板 5 个灯区

| 编号 | 名称 | 说明 |
|------|------|------|
| 0 | Digital LED 1 | ARGB 口 1 |
| 1 | Digital LED 2 | ARGB 口 2（风扇灯带可能在此） |
| 2 | Logo | 主板 Logo |
| 3 | 12V RGB Strip 1 | 12V RGB 条 1 |
| 4 | 12V RGB Strip 2 | 12V RGB 条 2 |

## 控制方法

### OpenRGB（已安装 v0.9.1948）

安装来源：GitLab CI 产物，解包 deb 安装。二进制路径：`/usr/bin/openrgb`。

**关灯命令：**

```bash
# 需要先启动服务器
sudo openrgb --server &
sleep 2

# 全部设备设为黑色
sudo openrgb --client localhost:6742 -d 0 --mode off          # 内存0（支持Off模式）
sudo openrgb --client localhost:6742 -d 1 --mode off          # 内存1（支持Off模式）
sudo openrgb --client localhost:6742 -d 2 --mode direct -c 000000  # 显卡（Direct+黑）
sudo openrgb --client localhost:6742 -d 3 --mode direct -c 000000  # 主板（Direct+黑，全5区）

# 主板单个灯区
sudo openrgb --client localhost:6742 -d 3 -z 0 --mode direct -c 000000  # Digital LED 1
sudo openrgb --client localhost:6742 -d 3 -z 1 --mode direct -c 000000  # Digital LED 2
sudo openrgb --client localhost:6742 -d 3 -z 2 --mode direct -c 000000  # Logo
sudo openrgb --client localhost:6742 -d 3 -z 3 --mode direct -c 000000  # 12V Strip 1
sudo openrgb --client localhost:6742 -d 3 -z 4 --mode direct -c 000000  # 12V Strip 2

# 清理服务器
sudo pkill openrgb
```

**⚠️ 已知问题：**
- OpenRGB CLI 无法脱离服务器独立运行，必须 `--server` + `--client` 配合使用
- 多次连接后服务器可能 segfault，表现为 `ConnectionRefusedError`
- 显卡和主板不支持 "Off" 模式，需用 `direct` 模式 + `000000` 黑色替代
- 启动服务器后要用 `--client localhost:6742` 而非省略 host（省略会连不到）
- 风扇灯带如果连在独立控制器而非主板 ARGB 口上，软件无法控制

### 终极方案：BIOS 关闭

如果软件控制不稳定，进 BIOS（Del 键）→ RGB Fusion → 全部 Off。硬件级别，必定生效。

## 其他尝试过但未成功的方案

| 方案 | 结果 |
|------|------|
| 直接写 `/dev/hidraw3`（HID 命令） | Permission denied，需逆向 ITE 协议 |
| `liquidctl` | 安装 hash 校验失败，不支持 ITE 芯片 |
| OpenRGB GUI（远程 Wayland）| SSH 无法传递 Wayland session |
| `openrgb --mode off` | 显卡和主板不支持 Off 模式 |

## 相关

- [[DevMechin（AI 主机）]]
- [[Ollama]]
- [[Wiki 目录]]
