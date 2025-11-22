# 后端详细设计文档 (Backend Detailed Design)

## 1. 设计目标

构建一个高可扩展、高鲁棒性的 FastAPI 后端，用于连接飞书文档与 AI 能力。核心要求包括：
- **配置管理**：所有敏感信息与可变参数通过 `.env` 管理。
- **AI 架构分层**：底层通信、Fallback 机制、Prompt 组装、业务策略严格解耦。
- **业务扩展性**：支持多种处理模式（Idea 扩展、深度调研等），易于增加新模式。
- **飞书原生集成**：支持在同一目录下创建子文档，并建立文档间关联。

---

## 2. 技术架构分层

### 2.1 配置层 (Configuration)
使用 `pydantic-settings` 读取 `.env` 文件。

```python
# 伪代码示例
class Settings(BaseSettings):
    FEISHU_APP_ID: str
    FEISHU_APP_SECRET: str
    
    # AI 配置
    AI_API_KEY_PRIMARY: str
    AI_BASE_URL_PRIMARY: str
    AI_MODEL_PRIMARY: str
    
    # Fallback 配置
    AI_API_KEY_BACKUP: str
    AI_BASE_URL_BACKUP: str
    AI_MODEL_BACKUP: str
    
    # 业务配置
    PROCESS_TIMEOUT: int = 60
```

### 2.2 AI 服务层 (The AI Stack)

这一层是系统的核心，按照你要求的“三层结构”进行设计：

#### Layer 1: 基础通信与 Fallback (LLM Client)
负责与 New API (或其他兼容 OpenAI 格式的 API) 进行 HTTP 交互。不关心具体业务，只关心“发送 Message，获取 Reply”。
- **功能**：
  - 封装 `httpx` 请求。
  - **实现 Fallback 机制**：当主线路 (Primary) 抛出网络错误或 5xx 错误时，自动切换到备用线路 (Backup)。
  - 统一错误处理。

#### Layer 2: Prompt 组装与上下文 (Prompt Engineering)
负责将业务需求转化为 LLM 能听懂的 Prompt。
- **功能**：
  - 维护不同模式的 Prompt 模板（例如 `PROMPT_IDEA_EXPAND` vs `PROMPT_RESEARCH`）。
  - 负责 Token 截断（防止文档过长爆 Token）。
  - 组装 System Prompt 和 User Content。

#### Layer 3: 业务策略调度 (Service Strategy)
负责根据前端传入的 `mode` 参数，选择不同的处理逻辑。这里使用 **策略模式 (Strategy Pattern)**。
- **基类**：`BaseDocProcessor`
- **子类实现**：
  - `IdeaExpanderProcessor`: 侧重发散性思维，Prompt 强调“头脑风暴”、“列出可能性”。
  - `ResearchProcessor`: 侧重深度，Prompt 强调“结构化”、“事实核查”、“总结”。
- **扩展性**：未来增加“翻译模式”或“润色模式”，只需增加一个新的 Processor 子类，不修改现有代码。

---

## 3. 详细业务流程 (Process Flow)

### 3.1 数据流向
`User Trigger` -> `FastAPI Endpoint` -> `ProcessManager` -> `Specific Processor` -> `Feishu API` & `AI Layer`

### 3.2 核心处理函数 `process_doc` 执行步骤

当收到请求（包含 `doc_token`, `user_id`, `mode`）时：

1.  **环境检查与鉴权**
    - 获取并校验 `tenant_access_token`。

2.  **获取原文档元数据 (Feishu API)**
    - 调用 `GET /drive/v1/files/{doc_token}/meta`。
    - **关键目的**：获取 `parent_token` (父文件夹 Token)。如果 `parent_token` 为空，则默认在根目录创建。

3.  **读取文档内容 (Feishu API)**
    - 调用 `GET /docx/v1/documents/{doc_token}/raw_content`。
    - 获取纯文本内容。

4.  **AI 处理 (AI Layer)**
    - `ProcessManager` 根据 `mode` 实例化对应的 Processor（例如 `IdeaExpanderProcessor`）。
    - Processor 组装 Prompt。
    - 调用底层 LLM Client (带 Fallback) 获取生成结果。

5.  **生成子文档 (Feishu API)**
    - 调用 `POST /docx/v1/documents`。
    - 参数：
      - `folder_token`: **原文档的 `parent_token`** (实现“当前目录下生成”)。
      - `title`: 比如 "AI分析: {原标题}"。
    - 得到 `child_doc_token`。

6.  **写入子文档内容 (Feishu API)**
    - 将 AI 返回的内容（Markdown）解析为飞书的 Blocks。
    - 调用 `POST /docx/v1/documents/{child_doc_token}/blocks` 写入内容。

7.  **关联回原文档 (Feishu API)**
    - 构造一个“链接块”或“引用块”。
    - 调用 `POST /docx/v1/documents/{doc_token}/blocks/{block_id}/children` (通常添加到文档末尾)。

8.  **异步通知**
    - 发送飞书卡片给 `user_id`，包含子文档的跳转链接。

---

## 4. 目录结构规划

```text
backend/
├── .env                  # 配置文件（不提交 Git）
├── main.py               # FastAPI 入口
├── config.py             # Pydantic 设置
├── requirements.txt
├── core/
│   ├── llm_client.py     # Layer 1: AI 基础通信 + Fallback
│   └── manager.py        # 业务编排入口
├── services/
│   ├── feishu.py         # 飞书 API 封装 (Auth, Drive, Docx, Im)
│   └── processors/       # Layer 2 & 3: 业务策略
│       ├── base.py       # 抽象基类
│       ├── expander.py   # 扩展思路模式
│       └── researcher.py # 调研模式
└── api/
    └── routes.py         # 路由定义
```

## 5. 关键数据结构

### 请求体 (Request Body)
```json
{
  "doc_token": "doxcn............",
  "user_id": "ou_.............",
  "mode": "idea_expand",  // 决定调用哪个 Processor
  "trigger_source": "addon_button"
}
```

### Fallback 配置逻辑
在 `core/llm_client.py` 中：
```python
async def chat_completion(messages):
    try:
        return await call_primary_api(messages)
    except (TimeoutError, APIConnectionError, RateLimitError) as e:
        logger.warning(f"Primary API failed: {e}, switching to backup...")
        return await call_backup_api(messages)
```

## 6. 开发路线图

1.  **Phase 1: 基础架构**
    - 初始化 FastAPI，配置 `.env` 读取。
    - 实现 `FeishuClient`：跑通 Token 获取、读取文档、创建文档（指定文件夹）。

2.  **Phase 2: AI 核心与 Fallback**
    - 实现 `LLMClient`，编写单元测试验证 Fallback 切换是否生效。

3.  **Phase 3: 业务逻辑串联**
    - 实现 `IdeaExpanderProcessor`。
    - 跑通 `process_doc` 全流程。

4.  **Phase 4: 插件对接**
    - 提供 API 给前端调用，联调测试。

