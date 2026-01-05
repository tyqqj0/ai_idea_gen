#!/bin/bash

set -e

echo "=================================="
echo "  AI Idea Gen 服务状态检查"
echo "=================================="
echo ""

# 检查 FastAPI 是否运行
if pgrep -f "uvicorn backend.main:app" > /dev/null; then
    echo "✅ FastAPI 运行中"
    PORT=$(ss -ltnp | grep uvicorn | awk '{print $4}' | cut -d: -f2 | head -1)
    if [ -n "$PORT" ]; then
        echo "   端口: $PORT"
        echo "   本地访问: http://127.0.0.1:$PORT/health"
    fi
else
    echo "❌ FastAPI 未运行"
fi

echo ""

# 检查 cloudflared 是否运行
if systemctl is-active --quiet cloudflared 2>/dev/null; then
    echo "✅ Cloudflare Tunnel 运行中"
    
    # 尝试获取配置的域名
    if [ -f ~/.cloudflared/config.yml ]; then
        HOSTNAME=$(grep "hostname:" ~/.cloudflared/config.yml | head -1 | awk '{print $2}')
        if [ -n "$HOSTNAME" ]; then
            echo "   域名: https://$HOSTNAME"
            echo "   测试访问: curl https://$HOSTNAME/health"
        fi
        
        # 显示 tunnel 名称
        TUNNEL_ID=$(grep "^tunnel:" ~/.cloudflared/config.yml | awk '{print $2}')
        if [ -n "$TUNNEL_ID" ]; then
            echo "   Tunnel ID: $TUNNEL_ID"
        fi
    fi
elif command -v cloudflared &> /dev/null; then
    echo "⚠️  cloudflared 已安装但未运行"
    echo "   启动命令: sudo systemctl start cloudflared"
else
    echo "❌ cloudflared 未安装"
fi

echo ""
echo "=================================="
echo "  查看日志"
echo "=================================="
echo "FastAPI:  tail -f /tmp/fastapi.log"
echo "Tunnel:   sudo journalctl -u cloudflared -f"
echo ""
