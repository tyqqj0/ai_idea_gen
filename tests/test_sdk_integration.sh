#!/bin/bash
#
# SDK 集成测试脚本
# 
# 前置条件：
#   1. 后端服务运行在 http://127.0.0.1:8001
#   2. 设置环境变量：DOC_TOKEN, USER_ID
#
# 运行方式：
#   export DOC_TOKEN="doxcnxxxxx"
#   export USER_ID="ou_xxxxx"
#   bash tests/test_sdk_integration.sh
#

set -e

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
DOC_TOKEN="${DOC_TOKEN:-}"
USER_ID="${USER_ID:-}"

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════════╗"
echo "║                     SDK 集成测试（需要后端服务）                           ║"
echo "╚═══════════════════════════════════════════════════════════════════════════╝"
echo ""

# 检查环境变量
if [ -z "$DOC_TOKEN" ]; then
  echo "⚠️  警告: DOC_TOKEN 未设置，将使用占位符（可能失败）"
  DOC_TOKEN="doccnPlaceholder"
fi

if [ -z "$USER_ID" ]; then
  echo "⚠️  警告: USER_ID 未设置，将使用占位符（可能失败）"
  USER_ID="ou_placeholder"
fi

echo "配置信息:"
echo "  BASE_URL: $BASE_URL"
echo "  DOC_TOKEN: ${DOC_TOKEN:0:15}..."
echo "  USER_ID: ${USER_ID:0:15}..."
echo ""

# ========================================
# 测试 1: Ping 接口
# ========================================
echo "════════════════════════════════════════════════════════════════════════════"
echo "🧪 测试 1: Ping 接口"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

curl -s "$BASE_URL/api/ping" | jq . || echo "❌ Ping 失败"
echo ""

# ========================================
# 测试 2: 触发任务（带 content 参数）
# ========================================
echo "════════════════════════════════════════════════════════════════════════════"
echo "🧪 测试 2: 触发任务（带 content 参数）"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

PAYLOAD=$(cat <<EOF
{
  "token": "$DOC_TOKEN",
  "user_id": "$USER_ID",
  "mode": "idea_expand",
  "content": "这是用户划词选中的文本内容，用于测试 content 参数传递",
  "trigger_source": "integration_test"
}
EOF
)

echo "📤 发送请求:"
echo "$PAYLOAD" | jq .
echo ""

RESPONSE=$(curl -s -X POST "$BASE_URL/api/addon/process" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo "📥 响应:"
echo "$RESPONSE" | jq .
echo ""

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id // empty')

if [ -z "$TASK_ID" ]; then
  echo "❌ 未能获取 task_id，测试失败"
  exit 1
fi

echo "✅ 任务已触发: $TASK_ID"
echo ""

# ========================================
# 测试 3: 查询任务状态
# ========================================
echo "════════════════════════════════════════════════════════════════════════════"
echo "🧪 测试 3: 查询任务状态"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

echo "等待 2 秒后查询..."
sleep 2

TASK_RESPONSE=$(curl -s "$BASE_URL/api/addon/tasks/$TASK_ID")

echo "📥 任务状态:"
echo "$TASK_RESPONSE" | jq .
echo ""

TASK_STATUS=$(echo "$TASK_RESPONSE" | jq -r '.status // empty')
echo "任务状态: $TASK_STATUS"
echo ""

# ========================================
# 测试 4: 验证后端支持 /auth 接口（如果已实现）
# ========================================
echo "════════════════════════════════════════════════════════════════════════════"
echo "🧪 测试 4: /auth 接口（如果已实现）"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

AUTH_PAYLOAD='{"code":"test_code_12345"}'

echo "📤 发送请求:"
echo "$AUTH_PAYLOAD" | jq .
echo ""

AUTH_RESPONSE=$(curl -s -X POST "$BASE_URL/api/addon/auth" \
  -H "Content-Type: application/json" \
  -d "$AUTH_PAYLOAD" || echo '{"error":"接口未实现"}')

echo "📥 响应:"
echo "$AUTH_RESPONSE" | jq . || echo "$AUTH_RESPONSE"
echo ""

if echo "$AUTH_RESPONSE" | jq -e '.open_id' > /dev/null 2>&1; then
  echo "✅ /auth 接口已实现"
else
  echo "⚠️  /auth 接口尚未实现（后续需要添加）"
fi

echo ""

# ========================================
# 测试总结
# ========================================
echo "════════════════════════════════════════════════════════════════════════════"
echo "🎉 测试完成！"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
echo "后续步骤："
echo "  1. 如果 /auth 接口未实现，需要在后端添加"
echo "  2. 编译 TypeScript SDK: cd sdk && npm run build"
echo "  3. 在前端项目中引入 SDK 进行真实测试"
echo ""
