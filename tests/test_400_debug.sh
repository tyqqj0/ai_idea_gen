#!/bin/bash
# 测试各种可能导致 400 错误的请求

BASE_URL="http://127.0.0.1:8001"

echo "=========================================="
echo "测试 1: 缺少 token 和 doc_token"
echo "=========================================="
curl -v -X POST "${BASE_URL}/api/addon/process" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_001",
    "mode": "idea_expand"
  }' 2>&1 | grep -E "HTTP|{.*}"

echo -e "\n=========================================="
echo "测试 2: token 和 doc_token 都是 null"
echo "=========================================="
curl -v -X POST "${BASE_URL}/api/addon/process" \
  -H "Content-Type: application/json" \
  -d '{
    "token": null,
    "doc_token": null,
    "user_id": "test_user_001",
    "mode": "idea_expand"
  }' 2>&1 | grep -E "HTTP|{.*}"

echo -e "\n=========================================="
echo "测试 3: token 和 doc_token 都是空字符串"
echo "=========================================="
curl -v -X POST "${BASE_URL}/api/addon/process" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "",
    "doc_token": "",
    "user_id": "test_user_001",
    "mode": "idea_expand"
  }' 2>&1 | grep -E "HTTP|{.*}"

echo -e "\n=========================================="
echo "测试 4: 缺少 user_id"
echo "=========================================="
curl -v -X POST "${BASE_URL}/api/addon/process" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "WTY1wJevAiiSm4kGTbfcboxXnVc",
    "mode": "idea_expand"
  }' 2>&1 | grep -E "HTTP|{.*}"

echo -e "\n=========================================="
echo "测试 5: 无效的 mode"
echo "=========================================="
curl -v -X POST "${BASE_URL}/api/addon/process" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "WTY1wJevAiiSm4kGTbfcboxXnVc",
    "user_id": "test_user_001",
    "mode": "invalid_mode"
  }' 2>&1 | grep -E "HTTP|{.*}"

echo -e "\n=========================================="
echo "测试 6: token 长度不够（< 27字符）"
echo "=========================================="
curl -v -X POST "${BASE_URL}/api/addon/process" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "short_token",
    "user_id": "test_user_001",
    "mode": "idea_expand"
  }' 2>&1 | grep -E "HTTP|{.*}"

echo -e "\n=========================================="
echo "测试 7: 正常请求（应该返回 202）"
echo "=========================================="
curl -v -X POST "${BASE_URL}/api/addon/process" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "WTY1wJevAiiSm4kGTbfcboxXnVc",
    "user_id": "test_user_001",
    "mode": "idea_expand"
  }' 2>&1 | grep -E "HTTP|{.*}"

echo -e "\n=========================================="
echo "测试完成！请查看服务器日志"
echo "=========================================="
