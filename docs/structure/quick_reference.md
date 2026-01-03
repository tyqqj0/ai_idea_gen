# 快速参考手册

> 最后更新：2025-12-31

快速查找常用命令、配置和代码片段。

---

## 📋 目录

- [启动和部署](#启动和部署)
- [配置文件](#配置文件)
- [API 接口](#api-接口)
- [测试命令](#测试命令)
- [常用代码片段](#常用代码片段)
- [故障排查](#故障排查)

---

## 启动和部署

### 本地开发启动

```bash
# 1. 启动服务
bash scripts/start_server.sh

# 2. 或者手动启动
cd /home/parser/code/ai_idea_gen
source venv/bin/activate  # 如果使用虚拟环境
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```

### 生产环境启动

```bash
# 使用 gunicorn + uvicorn workers
gunicorn backend.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001
```

### 健康检查

```bash
curl http://localhost:8001/health
# 返回: {"status": "ok"}
```

---

## 配置文件

### .env（环境变量）

```env
# 飞书应用配置
FEISHU_APP_ID=cli_xxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxx

# LLM API Keys
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxx
DEEP_RESEARCH_API_KEY=xxxxxxxxxxxxxxxxxxxxx

# 业务配置
PROCESS_TIMEOUT=60
WEBHOOK_OUTPUT_URL=https://example.com/webhook
WEBHOOK_OUTPUT_TIMEOUT_S=10.0
```

### llm_config.yml（LLM 配置）

```yaml
# Provider 定义
providers:
  primary_gemini:
    type: "openai-compatible"
    base_url: "https://zjuapi.com/v1"
    model: "gemini-2.5-flash-nothinking"
    api_key_env: "GEMINI_API_KEY"

# Chain 定义（Fallback 链）
chains:
  idea_expand:
    - provider: "primary_gemini"
      timeout_s: 60
  
  title_generation:
    - provider: "no_thinking_gemini"
      timeout_s: 15

# 全局配置
global:
  max_retries_per_provider: 1
  overall_timeout_s: 60
```

### workflow_config.yml（工作流配置）

```yaml
workflows:
  idea_expand:
    processor: "idea_expander"      # Processor 名称
    chain: "idea_expand"            # LLM Chain 名称
    output: "feishu_child_doc"      # OutputHandler 名称
    notify_user: false              # 是否发送通知
  
  research:
    processor: "research"
    chain: "research"
    output: "feishu_child_doc"
    notify_user: false
```

---

## API 接口

### 基础信息

- **Base URL**: `http://localhost:8001`
- **Content-Type**: `application/json`

### 主要接口

#### 1. 健康检查

```bash
GET /health
```

**响应**：
```json
{
  "status": "ok"
}
```

---

#### 2. 触发文档处理

```bash
POST /api/addon/process
```

**请求体**：
```json
{
  "token": "WTY1wJevAiiSm4kGTbfcboxXnVc",
  "user_id": "ou_xxxxxxxxxxxxx",
  "mode": "idea_expand",
  "trigger_source": "docs_addon"
}
```

**响应**（202 Accepted）：
```json
{
  "task_id": "7dfc27556c384ec396eb17fa21e7367b",
  "status": "accepted",
  "message": "Processing started"
}
```

---

#### 3. 查询任务状态

```bash
GET /api/addon/tasks/{task_id}
```

**响应**（处理中）：
```json
{
  "task_id": "7dfc2755...",
  "status": "running",
  "progress": {
    "stage": "llm",
    "percent": 35,
    "message": "调用模型生成内容"
  },
  "created_at": 1735632000.0
}
```

**响应**（成功）：
```json
{
  "task_id": "7dfc2755...",
  "status": "succeeded",
  "result": {
    "child_doc_token": "doccnXXXXXXXXXX",
    "child_doc_url": "https://feishu.cn/docx/doccnXXXXXXXXXX",
    "title": "AI驱动的产品创新方案",
    "summary": "扩展思路建议"
  },
  "created_at": 1735632000.0,
  "updated_at": 1735632045.0
}
```

**响应**（失败）：
```json
{
  "task_id": "7dfc2755...",
  "status": "failed",
  "error": "LLM API 调用失败",
  "created_at": 1735632000.0,
  "updated_at": 1735632010.0
}
```

---

#### 4. 飞书事件回调

```bash
POST /api/feishu/event
```

**请求体**（URL 验证）：
```json
{
  "challenge": "xxx"
}
```

**响应**：
```json
{
  "challenge": "xxx"
}
```

**请求体**（事件推送）：
```json
{
  "schema": "2.0",
  "header": {
    "event_id": "xxx",
    "event_type": "docx.document.updated_v1"
  },
  "event": {
    "doc_token": "doccnXXXXXXXXXX",
    "operator_id": "ou_xxxxxxxxxxxxx"
  }
}
```

**响应**：
```json
{
  "code": 0,
  "msg": "ok"
}
```

---

## 测试命令

### 手动测试脚本

#### 基础用法

```bash
python3 tests/manual_trigger.py \
  --token WTY1wJevAiiSm4kGTbfcboxXnVc \
  --user-id test_user_001 \
  --mode idea_expand
```

#### 完整参数

```bash
python3 tests/manual_trigger.py \
  --endpoint http://localhost:8001/api/addon/process \
  --token WTY1wJevAiiSm4kGTbfcboxXnVc \
  --user-id test_user_001 \
  --mode idea_expand \
  --trigger-source manual_test \
  --poll-interval 2.0 \
  --poll-timeout 180.0
```

#### 测试深度调研（长时任务）

```bash
python3 tests/manual_trigger.py \
  --token WTY1wJevAiiSm4kGTbfcboxXnVc \
  --user-id test_user_001 \
  --mode research \
  --poll-interval 15.0 \
  --poll-timeout 3600.0
```

#### 测试 Wiki 节点

```bash
python3 tests/manual_trigger.py \
  --token wikcnXXXXXXXXXX \
  --user-id test_user_001 \
  --mode idea_expand \
  --wiki-space-id 7123456789012345678
```

#### 不等待结果（快速测试）

```bash
python3 tests/manual_trigger.py \
  --token WTY1wJevAiiSm4kGTbfcboxXnVc \
  --user-id test_user_001 \
  --mode idea_expand \
  --no-wait
```

### 使用 curl 测试

#### 触发处理

```bash
curl -X POST http://localhost:8001/api/addon/process \
  -H "Content-Type: application/json" \
  -d '{
    "token": "WTY1wJevAiiSm4kGTbfcboxXnVc",
    "user_id": "test_user_001",
    "mode": "idea_expand"
  }'
```

#### 查询任务状态

```bash
curl http://localhost:8001/api/addon/tasks/7dfc27556c384ec396eb17fa21e7367b
```

---

## 常用代码片段

### 新增 Processor

```python
# 1. 创建文件：backend/services/processors/my_processor.py
from backend.services.processors.base import BaseDocProcessor, ProcessorResult
from textwrap import dedent

class MyProcessor(BaseDocProcessor):
    async def run(self, *, doc_content, doc_title, chain, context=None):
        system_prompt = dedent("""
            你是一个专业的...
            要求：
            - ...
            - ...
        """).strip()
        
        user_prompt = dedent(f"""
            文档标题：{doc_title}
            文档内容：
            {doc_content}
            
            请...
        """).strip()
        
        result = await self.llm_client.chat_completion(
            chain=chain,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        return ProcessorResult(
            title=f"{doc_title} - 我的处理",
            content_md=result.strip(),
            summary="处理完成",
            metadata={"mode": "my_mode"}
        )

# 2. 注册：backend/services/processors/registry.py
from backend.services.processors.my_processor import MyProcessor

PROCESSOR_REGISTRY = {
    # ... existing processors ...
    "my_processor": MyProcessor,
}

# 3. 配置：workflow_config.yml
workflows:
  my_mode:
    processor: "my_processor"
    chain: "my_chain"
    output: "feishu_child_doc"
    notify_user: true

# 4. LLM 配置：llm_config.yml
chains:
  my_chain:
    - provider: "primary_gemini"
      timeout_s: 60
```

### 新增 OutputHandler

```python
# 1. 创建文件：backend/services/outputs/my_output.py
from backend.services.outputs.base import BaseOutputHandler, OutputResult

class MyOutputHandler(BaseOutputHandler):
    def __init__(self, **kwargs):
        self._config = kwargs
    
    async def handle(self, *, ctx, source_doc, processor_result, notify_user):
        # 处理输出逻辑
        # 例如：发送邮件、写入数据库、推送通知等
        
        return OutputResult(
            child_doc_token=None,
            child_doc_url=None,
            metadata={"output": "my_output"}
        )

# 2. 注册：backend/services/outputs/registry.py
from backend.services.outputs.my_output import MyOutputHandler

def _make_my_output(feishu: FeishuClient, llm: LLMClient):
    return MyOutputHandler(config_key="value")

OUTPUT_REGISTRY = {
    # ... existing outputs ...
    "my_output": _make_my_output,
}

# 3. 配置：workflow_config.yml
workflows:
  my_mode:
    processor: "idea_expander"
    chain: "idea_expand"
    output: "my_output"
    notify_user: false
```

### 调用飞书 API

```python
from backend.services.feishu import FeishuClient

feishu = FeishuClient()

# 获取文档内容
doc_content = await feishu.get_doc_content("doccnXXXXXXXXXX")

# 创建子文档
child_doc_token = await feishu.create_child_doc(
    folder_token="fldcnXXXXXXXXXX",
    title="AI 生成的标题"
)

# 写入内容
await feishu.write_doc_content(
    child_doc_token,
    "# 标题\n\n内容..."
)

# 发送卡片
await feishu.send_card(
    user_id="ou_xxxxxxxxxxxxx",
    card_content={
        "header": {"title": {"tag": "plain_text", "content": "标题"}},
        "elements": [...]
    }
)
```

### 调用 LLM

```python
from backend.core.llm_client import LLMClient

llm = LLMClient()

# 简单调用
response = await llm.chat_completion(
    chain="idea_expand",
    messages=[
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "请帮我..."}
    ]
)

# 带参数调用
response = await llm.chat_completion(
    chain="title_generation",
    messages=[...],
    temperature=0.7,
    max_tokens=100
)
```

---

## 故障排查

### 常见问题

#### 1. 服务启动失败

**症状**：
```
ModuleNotFoundError: No module named 'xxx'
```

**解决**：
```bash
# 安装依赖
pip install -r backend/requirements.txt
```

---

#### 2. 飞书 API 调用失败

**症状**：
```
FeishuAPIError: Failed to get tenant_access_token
```

**检查**：
```bash
# 1. 检查 .env 配置
cat .env | grep FEISHU

# 2. 验证 App ID 和 Secret
# 在飞书开发者后台确认凭证
```

---

#### 3. LLM 调用超时

**症状**：
```
FallbackExhaustedError: All providers failed for chain=xxx
```

**检查**：
```bash
# 1. 检查网络连接
curl -I https://zjuapi.com

# 2. 检查 API Key
cat .env | grep API_KEY

# 3. 查看日志
tail -f logs/app.log | grep "LLM"
```

---

#### 4. 标题生成失败

**症状**：
日志显示 "标题生成失败，使用默认标题"

**原因**：
- LLM API 超时
- Chain 配置错误
- API Key 无效

**解决**：
```yaml
# 检查 llm_config.yml
chains:
  title_generation:
    - provider: "no_thinking_gemini"
      timeout_s: 15  # 确保超时足够
```

---

#### 5. 子文档创建失败

**症状**：
```
FeishuAPIError: Unable to parse child document token
```

**原因**：
- 权限不足（需要 `docx:write` 权限）
- folder_token 无效
- Wiki 节点不存在

**检查权限**：
1. 飞书开发者后台 → 应用详情 → 权限管理
2. 确认已开通：
   - `docx:read`
   - `docx:write`
   - `wiki:node:read`（如果使用 Wiki）
   - `wiki:node:write`（如果使用 Wiki）

---

#### 6. 任务状态查询 500 错误

**症状**：
```
PydanticSerializationError: Unable to serialize unknown type: <class 'function'>
```

**原因**：metadata 中包含不可序列化的对象（如函数）

**已修复**：v2025-12-31 版本已修复此问题

---

### 日志查看

#### 查看实时日志

```bash
# 如果使用 systemd
journalctl -u ai-idea-gen -f

# 如果使用 screen/tmux
tail -f logs/app.log
```

#### 查看特定模块日志

```bash
# LLM 调用日志
grep "LLM" logs/app.log

# 飞书 API 日志
grep "Feishu" logs/app.log

# 错误日志
grep "ERROR" logs/app.log
```

---

### 调试技巧

#### 1. 启用详细日志

```python
# backend/main.py
import logging

logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
```

#### 2. 单步测试

```python
# 测试飞书连接
from backend.services.feishu import FeishuClient
feishu = FeishuClient()
token = await feishu.get_tenant_access_token()
print(f"Token: {token[:10]}...")

# 测试 LLM 调用
from backend.core.llm_client import LLMClient
llm = LLMClient()
result = await llm.chat_completion(
    chain="title_generation",
    messages=[{"role": "user", "content": "Hello"}]
)
print(result)
```

#### 3. 使用 Python REPL

```bash
# 启动 Python REPL
python3

# 导入模块测试
from backend.services.feishu import FeishuClient
import asyncio

async def test():
    feishu = FeishuClient()
    content = await feishu.get_doc_content("doccnXXXXXXXXXX")
    print(content[:100])

asyncio.run(test())
```

---

## 性能监控

### 关键指标

- **API 响应时间**：< 200ms（触发接口）
- **任务处理时间**：
  - 思路扩展：30-60 秒
  - 深度调研：5-40 分钟
- **Token 缓存命中率**：> 95%
- **LLM Fallback 触发率**：< 5%

### 监控命令

```bash
# 查看进程状态
ps aux | grep uvicorn

# 查看内存使用
free -h

# 查看网络连接
netstat -antp | grep 8001

# 查看 CPU 使用
top -p $(pgrep -f uvicorn)
```

---

## 快速参考卡片

### 目录结构速查

```
backend/
├── api/routes.py          # API 路由
├── core/
│   ├── llm_client.py      # LLM 客户端
│   ├── manager.py         # 流程编排
│   └── task_store.py      # 任务存储
├── services/
│   ├── processors/        # 处理器
│   ├── outputs/           # 输出器
│   ├── utils/             # 工具层
│   └── feishu.py          # 飞书 API
├── config.py              # 配置
└── main.py                # 入口
```

### 配置文件速查

```
.env                       # 环境变量
llm_config.yml            # LLM 配置
workflow_config.yml       # 工作流配置
```

### 常用端口

```
8001                      # FastAPI 服务
```

### 关键概念

- **Mode**: 处理模式（idea_expand, research）
- **Chain**: LLM Provider 链（Fallback）
- **Processor**: 文档处理器（策略模式）
- **OutputHandler**: 输出处理器（策略模式）
- **Task**: 异步任务（task_id）

---

> 📝 **维护说明**：本文档随项目更新，请保持同步更新
