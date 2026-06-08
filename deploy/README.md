# knowledge-wiki 部署指南

## 服务器信息

- 主机：DevMechin（8.133.175.201）
- 系统：Ubuntu 24.04
- 用户：jxy001a1
- FRP 隧道：端口 60022 → 内网 22

## 服务架构

```
:9300   wiki-mcp.service       MCP Server（AI 工具调用入口）
:9400   wecom-webhook.service   企业微信 Bot + Web 管理后台
内部     wiki-scheduler.service  定时调度器（早报/提醒/备份）
内部     alsa-loopback.service   USB 麦克风→音箱环回（用户级服务）
:11434  ollama                   本地 LLM 推理（qwen2.5:3b + qwen3-vl:8b）
```

## 首次部署

```bash
# 1. 克隆仓库
git clone git@github.com:JXY001A/knowledge-wiki.git ~/code/knowledge-wiki
cd ~/code/knowledge-wiki

# 2. 创建虚拟环境并安装
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. 配置环境变量
cp deploy/.env.example .env
vim .env  # 填入 DEEPSEEK_API_KEY、WECOM 等密钥

# 4. 安装 Node.js 依赖并构建前端
cd web && npm install && npm run build && cd ..

# 5. 安装 systemd 服务
sudo cp deploy/wiki-mcp.service deploy/wecom-webhook.service \
        deploy/wiki-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wiki-mcp wecom-webhook wiki-scheduler

# 6. 安装麦克风监听服务（用户级）
mkdir -p ~/.config/systemd/user
cp deploy/alsa-loopback.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable alsa-loopback.service
```

## 日常更新

```bash
cd ~/code/knowledge-wiki
git pull
source .venv/bin/activate
pip install -e .
cd web && npm install && npm run build && cd ..

# 同步前端构建到服务器
# web/build/ 不入 git，需要本地构建后 rsync
# 或直接在服务器上 npm run build

sudo systemctl restart wiki-mcp wecom-webhook wiki-scheduler
```

## 音频设备

两块 Jieli Technology USB 麦克风+音箱一体设备：

- Card 2（`2d99:a074`）：默认环回设备
- Card 3（`4c4a:4155`）：备用

权限通过 ACL 管理（`/etc/udev/rules.d/99-alsa-acl.rules`）。

```bash
# 开启/关闭麦克风监听
systemctl --user start alsa-loopback.service
systemctl --user stop alsa-loopback.service
```

## 数据库备份

自动备份：scheduler 每周日凌晨 3:00 SQL dump 到 `raw/assets/db-backup/`

手动备份：
```bash
python -m knowledge_wiki db backup
```
