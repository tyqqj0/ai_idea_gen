# AI Idea Generator - 项目架构概览

> 最后更新：2025-12-31

## 📋 项目简介

飞书文档 AI 处理后端服务，支持自动处理飞书文档内容（思路扩展、深度调研等），在原文档同目录下创建 AI 处理后的子文档，并建立引用链接。

---

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户触发                              │
│  (飞书小组件 / API / 事件回调 / 卡片交互)                    │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                    API 路由层 (routes.py)                    │
│  - POST /api/addon/process  (主触发接口)                    │
│  - GET /api/addon/tasks/{task_id}  (任务状态查询)           │
│  - POST /api/feishu/event  (飞书事件回调)                   │
│  - POST /api/feishu/card_callback  (飞书卡片回调)           │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              触发服务层 (TriggerService)                     │
│  - 创建任务 (TaskStore)                                     │
│  - 幂等控制 (event_id 去重)                                 │
│  - 异步执行 (后台任务)                                      │
│  - 进度报告                                                 │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              流程编排层 (ProcessManager)                     │
│  1. 获取文档元信息 (FeishuClient)                           │
│  2. 读取文档内容 (FeishuClient)                             │
│  3. 选择并执行 Processor (WorkflowRegistry)                 │
│  4. 输出处理 (OutputHandler)                                │
│  5. 进度报告                                                │
└──────────┬──────────────────────────────────┬───────────────┘
           ↓                                  ↓
  ┌────────────────────┐           ┌────────────────────────┐
  │  处理器层           │           │  输出层                 │
  │  (Processors)       │           │  (OutputHandlers)      │
  └────────────────────┘           └────────────────────────┘
           ↓                                  ↓
  ┌────────────────────┐           ┌────────────────────────┐
  │  LLM 调用层         │           │  飞书 API 层            │
  │  (LLMClient)        │           │  (FeishuClient)        │
  └────────────────────┘           └────────────────────────┘
```

---

## 📁 目录结构

```
ai_idea_gen/
├── backend/                      # 后端服务
│   ├── api/                      # API 路由层
│   │   └── routes.py            # 路由定义与请求处理
│   │
│   ├── core/                     # 核心模块
│   │   ├── llm_client.py        # LLM 客户端（Fallback 机制）
│   │   ├── llm_config_models.py # LLM 配置数据模型
│   │   ├── providers.py         # LLM Provider 实现
│   │   ├── manager.py           # 流程编排器
│   │   ├── task_store.py        # 任务状态存储
│   │   ├── workflow_loader.py   # 工作流配置加载
│   │   └── workflow_config_models.py  # 工作流配置模型
│   │
│   ├── services/                 # 业务服务层
│   │   ├── processors/          # 处理器（策略模式）
│   │   │   ├── base.py          # 处理器抽象基类
│   │   │   ├── expander.py      # 思路扩展处理器
│   │   │   ├── researcher.py    # 深度调研处理器
│   │   │   └── registry.py      # 处理器注册表
│   │   │
│   │   ├── outputs/             # 输出处理器（策略模式）
│   │   │   ├── base.py          # 输出处理器抽象基类
│   │   │   ├── feishu_child_doc.py  # 飞书子文档输出
│   │   │   ├── webhook.py       # Webhook 推送输出
│   │   │   └── registry.py      # 输出处理器注册表
│   │   │
│   │   ├── triggers/            # 触发服务
│   │   │   └── service.py       # 触发服务实现
│   │   │
│   │   ├── utils/               # 工具层（新增）
│   │   │   ├── __init__.py
│   │   │   └── title_generator.py  # 智能标题生成器
│   │   │
│   │   └── feishu.py            # 飞书 API 封装
│   │
│   ├── config.py                # 全局配置
│   ├── main.py                  # FastAPI 应用入口
│   └── requirements.txt         # Python 依赖
│
├── sdk/                         # TypeScript SDK（前端）
│   ├── src/
│   │   ├── client.ts           # 客户端入口
│   │   ├── errors.ts           # 错误处理
│   │   ├── http.ts             # HTTP 请求封装
│   │   ├── types.ts            # 类型定义
│   │   └── index.ts            # 导出入口
│   ├── package.json
│   └── tsconfig.json
│
├── tests/                       # 测试文件
│   ├── manual_trigger.py       # 手动触发测试脚本
│   ├── test_output_feishu_child_doc.py
│   └── wiki_permission_probe.py
│
├── scripts/                     # 脚本
│   └── start_server.sh         # 服务启动脚本
│
├── docs/                        # 文档
│   ├── structure/              # 架构文档（本目录）
│   ├── backend_detailed_design.md
│   ├── backend_fastapi_design.md
│   ├── implementation_plan.md
│   └── product_requirements.md
│
├── .env                        # 环境变量（不提交）
├── env.example                 # 环境变量示例
├── llm_config.yml              # LLM 配置
├── workflow_config.yml         # 工作流配置
└── .gitignore
```

---

## 🔑 核心模块说明

### 1. API 路由层 (`backend/api/`)

**职责**：接收用户请求，参数校验，委托给业务层处理

**关键文件**：
- `routes.py`: 定义所有 HTTP 接口

**主要接口**：
- `POST /api/addon/process`: 主触发接口（小组件调用）
- `GET /api/addon/tasks/{task_id}`: 任务状态查询
- `POST /api/feishu/event`: 飞书事件回调
- `POST /api/feishu/card_callback`: 飞书卡片交互回调

---

### 2. 核心模块 (`backend/core/`)

#### 2.1 LLM 客户端 (`llm_client.py`)

**职责**：与 LLM API 通信，实现 Fallback 机制

**特性**：
- 多 Provider 支持（OpenAI 兼容、Doubao 等）
- Chain 配置（不同模式使用不同模型链）
- 自动 Fallback（主线路失败切换备用）
- 超时控制

**配置文件**：`llm_config.yml`

**关键概念**：
- **Provider**: LLM 提供商（如 Gemini、GPT 等）
- **Chain**: Provider 链（按顺序 Fallback）
- **Timeout**: 单个 Provider 超时时间

---

#### 2.2 流程编排器 (`manager.py`)

**职责**：统一处理流程编排

**核心类**：
- `ProcessManager`: 主流程管理器
- `WorkflowRegistry`: 工作流注册表（mode → 配置映射）
- `ProcessContext`: 处理上下文（doc_token, user_id, mode 等）
- `ProcessResult`: 处理结果

**处理流程**：
1. 获取文档元信息
2. 读取文档内容
3. 根据 mode 选择 Processor
4. 执行 Processor（调用 LLM）
5. 输出处理（创建子文档、回链、通知）

---

#### 2.3 任务存储 (`task_store.py`)

**职责**：管理任务状态（内存实现）

**功能**：
- 创建任务
- 更新进度
- 查询状态
- 幂等控制（event_id 去重）

**任务状态**：
- `running`: 处理中
- `succeeded`: 成功
- `failed`: 失败

---

### 3. 处理器层 (`backend/services/processors/`)

**设计模式**：策略模式

**职责**：根据不同 mode，执行不同的文档处理逻辑

**关键文件**：
- `base.py`: 处理器抽象基类
- `expander.py`: 思路扩展处理器
- `researcher.py`: 深度调研处理器（两阶段：refine → deep）
- `registry.py`: 处理器注册表

**输入**：
- `doc_content`: 文档内容
- `doc_title`: 文档标题
- `chain`: LLM 配置链名称
- `context`: 上下文信息

**输出**：
- `ProcessorResult`: 包含标题、内容（Markdown）、摘要、元数据

**扩展方式**：
1. 创建新的 Processor 类继承 `BaseDocProcessor`
2. 在 `registry.py` 注册
3. 在 `workflow_config.yml` 配置

---

### 4. 输出层 (`backend/services/outputs/`)

**设计模式**：策略模式

**职责**：将处理结果输出到不同目标（飞书文档、Webhook 等）

**关键文件**：
- `base.py`: 输出处理器抽象基类
- `feishu_child_doc.py`: 飞书子文档输出（主要）
- `webhook.py`: Webhook 推送输出
- `registry.py`: 输出处理器注册表

**输入**：
- `ProcessContext`: 处理上下文
- `SourceDoc`: 原文档信息
- `ProcessorResult`: 处理结果

**输出**：
- `OutputResult`: 包含子文档 token、URL、元数据

**核心功能**（飞书子文档）：
1. 智能标题生成（检测"未命名"时调用 AI）
2. 创建子文档（支持普通文档和 Wiki 知识库）
3. 写入内容（Markdown → Blocks）
4. 回链原文档
5. 发送通知卡片

---

### 5. 工具层 (`backend/services/utils/`)

#### 5.1 智能标题生成器 (`title_generator.py`) 🆕

**职责**：基于文档内容自动生成简洁、语义化的标题

**特性**：
- 提取内容前 N 字符（默认 800）
- 调用快速模型生成标题
- 自动清理标题（去引号、限长度）
- 失败时提供 fallback

**使用场景**：
- 原文档标题为"未命名文档"时自动生成
- 可被任何 OutputHandler 复用

**配置**：
- LLM Chain: `title_generation`
- Model: `no_thinking_gemini`（快速模型）
- Timeout: 15 秒

---

### 6. 飞书 API 层 (`backend/services/feishu.py`)

**职责**：封装飞书开放平台 API

**核心功能**：
- **Token 管理**：自动获取、缓存、刷新 `tenant_access_token`
- **文档操作**：
  - 获取文档元信息（`get_doc_meta`）
  - 读取文档内容（`get_doc_content`）
  - 创建子文档（`create_child_doc`）
  - 写入内容（`write_doc_content`）
  - Markdown 转 Blocks（`convert_markdown_to_blocks`）
  - 添加引用块（`append_reference_block`）
- **Wiki 知识库**：
  - 获取 Wiki 节点信息（`get_wiki_node_by_token`）
  - 创建 Wiki 子节点（`create_wiki_child_doc`）
- **消息通知**：
  - 发送卡片消息（`send_card`）

**容错机制**：
- Markdown 写入多级回退（convert → 单个 markdown block）
- 重试机制（API 调用失败自动重试）
- 长度截断（超长内容自动截断）

---

## 🔄 数据流转

### 完整流程示例（思路扩展模式）

```
1. 用户在飞书小组件点击"生成思路扩展"
   ↓
2. 前端调用 POST /api/addon/process
   Body: {
     "token": "WTY1wJevAii...",
     "user_id": "ou_xxx",
     "mode": "idea_expand"
   }
   ↓
3. routes.py 接收请求，创建 ProcessContext
   ↓
4. TriggerService 创建任务（task_id: "7dfc2755..."）
   立即返回 202 Accepted: {"task_id": "7dfc2755..."}
   ↓
5. 后台异步执行 ProcessManager.process_doc()
   ├─ 5.1 获取文档元信息 (FeishuClient)
   │      → doc_title: "未命名文档"
   │      → parent_token: "xxx"
   │
   ├─ 5.2 读取文档内容 (FeishuClient)
   │      → doc_content: "产品创新方向：..."
   │
   ├─ 5.3 选择 Processor (WorkflowRegistry)
   │      → mode="idea_expand" → IdeaExpanderProcessor
   │
   ├─ 5.4 执行 Processor
   │   ├─ 组装 Prompt（system + user）
   │   ├─ 调用 LLMClient.chat_completion(chain="idea_expand")
   │   │   └─ 调用 primary_gemini (Fallback: no_thinking_gemini)
   │   └─ 返回 ProcessorResult
   │       ├─ title: "未命名文档 - 思路扩展"
   │       ├─ content_md: "# 延伸方向\n1. ..."
   │       └─ summary: "扩展思路建议"
   │
   └─ 5.5 输出处理 (FeishuChildDocOutputHandler)
       ├─ 检测到标题包含"未命名"
       ├─ 调用 TitleGenerator.generate_title()
       │   ├─ 提取 content_md 前 800 字符
       │   ├─ 调用 LLM (chain="title_generation")
       │   └─ 返回: "产品创新策略与实施方案"
       │
       ├─ 创建飞书子文档
       │   └─ title: "产品创新策略与实施方案"
       │
       ├─ 写入内容
       │   ├─ Markdown → Blocks 转换
       │   └─ 调用飞书 API 写入
       │
       ├─ 回链原文档
       │   └─ 在原文档末尾插入子文档链接
       │
       └─ 发送通知卡片
           └─ 推送给 user_id
   ↓
6. 更新任务状态 (TaskStore)
   status: "succeeded"
   result: {
     "child_doc_token": "doccn...",
     "child_doc_url": "https://feishu.cn/docx/...",
     "title": "产品创新策略与实施方案"
   }
   ↓
7. 用户轮询 GET /api/addon/tasks/{task_id}
   返回任务结果（包含子文档链接）
```

---

## ⚙️ 配置文件说明

### 1. `.env` - 环境变量

```env
# 飞书应用配置
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# LLM Provider 密钥
GEMINI_API_KEY=xxx
DEEP_RESEARCH_API_KEY=xxx

# 业务配置
PROCESS_TIMEOUT=60
WEBHOOK_OUTPUT_URL=https://example.com/webhook
```

---

### 2. `llm_config.yml` - LLM 配置

```yaml
providers:
  primary_gemini:
    type: "openai-compatible"
    base_url: "https://zjuapi.com/v1"
    model: "gemini-2.5-flash-nothinking"
    api_key_env: "GEMINI_API_KEY"

  deep_research_zju:
    type: "openai-compatible"
    base_url: "https://zjuapi.com/v1"
    model: "gemini-3-pro-deepsearch"
    api_key_env: "DEEP_RESEARCH_API_KEY"

chains:
  idea_expand:
    - provider: "primary_gemini"
  
  research_refine:
    - provider: "primary_gemini"
      timeout_s: 120
  
  research_deep:
    - provider: "deep_research_zju"
      timeout_s: 2500
  
  title_generation:  # 🆕 智能标题生成
    - provider: "no_thinking_gemini"
      timeout_s: 15

global:
  max_retries_per_provider: 1
  overall_timeout_s: 60
```

---

### 3. `workflow_config.yml` - 工作流配置

```yaml
workflows:
  idea_expand:
    processor: "idea_expander"      # 使用哪个 Processor
    chain: "idea_expand"            # 使用哪个 LLM Chain
    output: "feishu_child_doc"      # 使用哪个 OutputHandler
    notify_user: false              # 是否发送通知

  research:
    processor: "research"
    chain: "research"
    output: "feishu_child_doc"
    notify_user: false
```

---

## 🎨 设计模式与架构优势

### 1. 策略模式（Strategy Pattern）

**应用场景**：
- **Processor 层**：不同的处理模式（思路扩展、深度调研）
- **Output 层**：不同的输出目标（飞书文档、Webhook）

**优势**：
- ✅ 易扩展：新增模式只需添加新类，不修改现有代码
- ✅ 解耦：业务逻辑与框架分离
- ✅ 可测试：每个策略独立测试

---

### 2. 工厂模式（Factory Pattern）

**应用场景**：
- `ProcessorRegistry`: 根据名称创建 Processor 实例
- `OutputRegistry`: 根据名称创建 OutputHandler 实例

**优势**：
- ✅ 统一创建逻辑
- ✅ 配置驱动（通过 YAML 配置）

---

### 3. 三层 AI 架构

```
Layer 1: 基础通信 + Fallback (LLMClient)
    ↓
Layer 2: Prompt 组装 (Processor)
    ↓
Layer 3: 业务策略调度 (ProcessManager)
```

**优势**：
- ✅ 职责清晰：通信、Prompt、业务分离
- ✅ 可靠性高：Fallback 机制保证可用性
- ✅ 易维护：修改 Prompt 不影响通信层

---

### 4. 异步任务模式

**实现**：
- API 立即返回 `task_id`（202 Accepted）
- 后台异步执行处理流程
- 客户端轮询任务状态

**优势**：
- ✅ 用户体验好：不阻塞请求
- ✅ 支持长时任务：深度调研可能耗时数分钟
- ✅ 容错性强：任务失败不影响 API 可用性

---

## 🚀 关键特性

### 1. 智能标题生成 🆕

**特性**：
- 自动检测"未命名文档"
- 调用快速 LLM 生成语义化标题
- 提取内容前 800 字符分析
- 标题长度限制（30 字符）
- 失败时自动 fallback

**技术亮点**：
- 通用工具层设计，可复用
- 使用快速模型（15秒内完成）
- 不影响主流程性能

---

### 2. LLM Fallback 机制

**实现**：
- Chain 配置：定义 Provider 顺序
- 主线路失败自动切换备用
- 不可重试错误直接抛出

**容错策略**：
- 网络错误 → Fallback
- 超时错误 → Fallback
- API 错误 → Fallback
- 参数错误 → 不 Fallback（直接失败）

---

### 3. Wiki 知识库支持

**特性**：
- 自动识别 Wiki 节点 vs 普通文档
- 在知识库中创建子节点（保持层级关系）
- 兼容云盘文档和知识库文档

**实现**：
- Token 解析逻辑：尝试作为 Wiki 节点查询
- 失败则降级为普通文档处理

---

### 4. Markdown 写入防护

**策略**：
1. 长度截断（60000 字符上限）
2. 优先：Markdown → Blocks 批量写入
3. 失败回退：单个 markdown block

**容错机制**：
- Convert 失败 → 降级
- Blocks 数量过多（>1000）→ 降级
- 写入失败 → 重试（最多 3 次）

---

## 📊 性能优化

### 1. Token 缓存

**实现**：
- 内存缓存 `tenant_access_token`
- TTL 控制（提前 60 秒刷新）
- 线程安全（asyncio.Lock）

**效果**：
- 减少 Token 请求次数
- 降低 API 调用延迟

---

### 2. 快速模型选择

**场景**：
- 标题生成：使用 `no_thinking_gemini`（快速模型）
- 思路扩展：使用 `primary_gemini`（平衡模型）
- 深度调研：使用 `deep_research_zju`（强大但慢）

**策略**：
- 根据任务复杂度选择合适的模型
- 标题生成 15 秒超时
- 深度调研 2500 秒超时

---

### 3. 异步并发

**实现**：
- FastAPI 异步路由
- httpx 异步 HTTP 客户端
- asyncio 异步任务调度

**效果**：
- 高并发处理能力
- 不阻塞主线程

---

## 🔒 安全性

### 1. 敏感信息保护

- ✅ `.env` 不提交到 Git
- ✅ Token 打码显示（日志中只显示前4后4）
- ✅ 后端持有凭证，前端不暴露

### 2. 权限控制

- ✅ 使用 `tenant_access_token`（应用级权限）
- ✅ Wiki 操作需要 `wiki:node:read/write` 权限
- ✅ 文档操作需要 `docx:read/write` 权限

---

## 🧪 测试

### 1. 手动测试脚本

**文件**：`tests/manual_trigger.py`

**用法**：
```bash
python3 tests/manual_trigger.py \
  --token WTY1wJevAii... \
  --user-id test_user_001 \
  --mode idea_expand \
  --poll-timeout 3600
```

**支持的参数**：
- `--token`: 文档 token 或 Wiki node token
- `--user-id`: 用户 open_id
- `--mode`: 处理模式（idea_expand / research）
- `--poll-interval`: 轮询间隔（秒）
- `--poll-timeout`: 轮询超时（秒）
- `--no-wait`: 不等待结果

---

## 🔮 未来扩展方向

### 1. 新增处理模式

**方式**：
1. 创建新的 Processor（继承 `BaseDocProcessor`）
2. 在 `processors/registry.py` 注册
3. 在 `workflow_config.yml` 配置
4. 在 `llm_config.yml` 配置对应 chain

**示例**：
- 会议总结模式（`MeetingSummaryProcessor`）
- 文档翻译模式（`TranslationProcessor`）
- 内容润色模式（`PolishProcessor`）

---

### 2. 新增输出方式

**方式**：
1. 创建新的 OutputHandler（继承 `BaseOutputHandler`）
2. 在 `outputs/registry.py` 注册
3. 在 `workflow_config.yml` 配置

**示例**：
- 邮件发送（`EmailOutputHandler`）
- 企业微信推送（`WeComOutputHandler`）
- 数据库存储（`DatabaseOutputHandler`）

---

### 3. 任务存储升级

**当前**：内存存储（`TaskStore`）

**未来**：
- Redis：支持分布式、持久化
- 数据库：支持历史记录、查询统计

---

### 4. 更多 AI 能力

**示例**：
- 自动摘要生成
- 关键词提取
- 内容分类
- 智能问答

**实现**：通过工具层（`services/utils/`）提供通用能力

---

## 📚 相关文档

- [产品需求文档](../product_requirements.md)
- [后端详细设计](../backend_detailed_design.md)
- [后端 FastAPI 设计](../backend_fastapi_design.md)
- [实施计划](../implementation_plan.md)

---

## 🤝 贡献指南

### 新增功能流程

1. 确定功能属于哪一层（Processor / Output / Utils）
2. 创建新类并实现接口
3. 在对应的 Registry 注册
4. 更新配置文件（`workflow_config.yml` / `llm_config.yml`）
5. 编写测试
6. 更新文档

### 代码规范

- 使用 Python 3.10+ 特性
- 遵循 PEP 8 代码风格
- 使用 type hints
- 添加必要的文档字符串
- 日志记录关键步骤

---

> 📝 **维护说明**：本文档随项目更新，请保持同步更新
