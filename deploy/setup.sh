#!/bin/bash
# knowledge-wiki DevMechin 部署脚本
# 用法: ssh jxy001a1@192.168.71.127 "bash ~/code/knowledge-wiki/deploy/setup.sh"

set -e

WIKI_ROOT="$HOME/code/knowledge-wiki"

echo "=== knowledge-wiki 部署 ==="

# 1. Git 同步
echo "[1/6] 拉取最新代码..."
cd "$WIKI_ROOT"
git pull --rebase origin main

# 2. 创建 venv（如不存在）
echo "[2/6] 配置 Python 虚拟环境..."
if [ ! -d "$WIKI_ROOT/.venv" ]; then
    python3 -m venv "$WIKI_ROOT/.venv"
fi
source "$WIKI_ROOT/.venv/bin/activate"
pip install -e "$WIKI_ROOT"

# 3. 创建 .env 模板（如不存在）
echo "[3/6] 检查环境变量..."
ENV_FILE="$WIKI_ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "创建 .env 模板，请填入实际值: $ENV_FILE"
    cat > "$ENV_FILE" << 'EOF'
# knowledge-wiki 环境变量
WIKI_ROOT=/home/jxy001a1/code/knowledge-wiki

# 企业微信
WECOM_TOKEN=your_token
WECOM_AES_KEY=your_aes_key
WECOM_CORP_ID=your_corp_id
WECOM_SECRET=your_secret
WECOM_AGENT_ID=1000002

# MCP Server
MCP_HOST=127.0.0.1
MCP_PORT=9300

# Webhook
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=9400

# DeepSeek API
DEEPSEEK_API_KEY=your_api_key

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
EOF
    echo "!!! 请编辑 $ENV_FILE 填入实际密钥后重新运行此脚本"
    exit 1
fi

# 4. 安装 systemd 单元
echo "[4/6] 安装 systemd 服务..."
mkdir -p "$HOME/.config/systemd/user"
cp "$WIKI_ROOT/deploy/wiki-mcp.service" "$HOME/.config/systemd/user/"
cp "$WIKI_ROOT/deploy/wecom-webhook.service" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload

# 5. 停止旧服务
echo "[5/6] 迁移服务..."
systemctl --user stop wiki-mcp 2>/dev/null || true
systemctl --user stop wecom-webhook 2>/dev/null || true

# 6. 启动新服务
echo "[6/6] 启动新服务..."
systemctl --user enable wiki-mcp
systemctl --user enable wecom-webhook
systemctl --user restart wiki-mcp
systemctl --user restart wecom-webhook

echo ""
echo "=== 部署完成 ==="
echo "检查状态:"
systemctl --user status wiki-mcp --no-pager -l
systemctl --user status wecom-webhook --no-pager -l
echo ""
echo "迁移后清理（手动执行）:"
echo "  rm -rf ~/code/wiki-mcp-server ~/code/wecom-bot-webhook"
