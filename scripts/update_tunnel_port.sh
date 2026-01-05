#!/bin/bash

set -e

# 配置变量
NEW_PORT=${1:-8001}
DOMAIN="api.aiinternet.online"
TUNNEL_NAME="ai-idea-gen"

echo "=========================================="
echo "  更新 Cloudflare Tunnel 端口配置"
echo "=========================================="
echo "新端口: $NEW_PORT"
echo "域名: $DOMAIN"
echo ""

# 提取 Tunnel ID
TUNNEL_ID=$(grep "^tunnel:" ~/.cloudflared/config.yml | awk '{print $2}')

if [ -z "$TUNNEL_ID" ]; then
    echo "❌ 错误：无法从配置文件中提取 Tunnel ID"
    exit 1
fi

echo "🔍 Tunnel ID: $TUNNEL_ID"
echo ""

# 更新用户配置文件
echo "📝 更新用户配置文件..."
cat > ~/.cloudflared/config.yml << EOF
tunnel: ${TUNNEL_ID}
credentials-file: /home/parser/.cloudflared/${TUNNEL_ID}.json

loglevel: info

ingress:
  - hostname: ${DOMAIN}
    service: http://localhost:${NEW_PORT}
    originRequest:
      connectTimeout: 30s
      noTLSVerify: true
  
  - service: http_status:404
EOF

# 更新系统配置文件
echo "📝 更新系统配置文件..."
sudo tee /etc/cloudflared/config.yml > /dev/null << EOF
tunnel: ${TUNNEL_ID}
credentials-file: /etc/cloudflared/${TUNNEL_ID}.json

loglevel: info

ingress:
  - hostname: ${DOMAIN}
    service: http://localhost:${NEW_PORT}
    originRequest:
      connectTimeout: 30s
      noTLSVerify: true
  
  - service: http_status:404
EOF

# 验证配置
echo "✅ 验证配置..."
cloudflared tunnel ingress validate

# 确保 DNS 路由已配置
echo "🌐 确保 DNS 路由已配置..."
cloudflared tunnel route dns ${TUNNEL_NAME} ${DOMAIN} 2>&1 | grep -q "already configured" && echo "   DNS 路由已存在" || echo "   DNS 路由已创建"

# 重启服务
echo "🔄 重启服务..."
sudo systemctl restart cloudflared

# 等待服务启动
sleep 2

# 检查服务状态
echo ""
echo "=========================================="
echo "  服务状态"
echo "=========================================="
sudo systemctl status cloudflared --no-pager

echo ""
echo "=========================================="
echo "  测试命令"
echo "=========================================="
echo "本地测试:  curl http://127.0.0.1:${NEW_PORT}/health"
echo "HTTPS测试: curl https://${DOMAIN}/health"
echo "浏览器:    https://${DOMAIN}/health"
echo ""
echo "查看日志:  sudo journalctl -u cloudflared -f"
echo ""
