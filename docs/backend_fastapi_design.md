## 后端 FastAPI 服务设计与开发需求

本设计文档聚焦**后端服务**，后端将部署在服务器上，为云文档小组件、飞书事件回调、消息卡片回调等提供统一的能力。

目标是：**用一个尽量简单的 FastAPI 服务，支持多种触发方式（小组件按钮、标签自动触发等），并完成文档处理 + 子文档创建 + 自动提醒。**

> 相关总体需求见：`product_requirements.md`  
> 前端小组件设计见：`frontend_docs_addon_design.md`

---

### 一、整体架构

- **技术栈**
  - Python 3.x
  - FastAPI（或兼容的 ASGI 框架）
  - HTTP 客户端：`httpx` / `requests`（用于调用飞书 OpenAPI 及内部算法服务）

- **部署形态**
  - 长期运行的 Web 服务（可部署在云服务器 / Serverless / 容器环境等）。
  - 提供 HTTPS 入口（生产环境建议使用 HTTPS，便于小组件安全配置与飞书回调）。

- **对接对象**
  - 飞书开放平台：
    - 认证：`app_id` / `app_secret` → `app_access_token` / `tenant_access_token`
    - API：云文档读写、文档创建、消息发送、事件订阅回调、交互卡片回调等。
  - 内部“文档处理”算法 / AI 服务：
    - 理想形态为**一个 HTTP 接口**：请求中传入文档内容，响应中返回处理结果。

---

### 二、核心职责

1. **身份认证与 Token 管理**
   - 根据飞书开放平台规范，通过 `app_id` 和 `app_secret` 获取并缓存：
     - `tenant_access_token`（主要，用于调用租户级 API）。
   - 处理 Token 过期与重新获取。

2. **统一文档处理流程 `process_doc`**
   - 输入：文档标识（`doc_token`）、触发用户 ID、触发来源、可选模式参数。
   - 步骤：
     1. 根据 `doc_token` 获取原始文档内容。
     2. 把文档内容传给内部“文档处理”服务，得到结构化结果。
     3. 使用飞书 OpenAPI 创建一个“子文档”，将结果写入。
     4. 在原文档中插入指向子文档的链接（若使用 OpenAPI 修改文档结构）。
     5. 通过消息 / 卡片通知触发用户（及可选的文档所有者）。
   - 输出：处理结果状态、子文档信息等。

3. **多种触发入口的统一接入**
   - 来自 **云文档小组件前端**（显式按钮触发）。
   - 来自 **飞书事件订阅**（标签自动触发）。
   - （可选）来自 **消息卡片交互回调**。
   - 不同入口在路由上不同，但最终都委托给统一的 `process_doc` 流程。

---

### 三、路由设计（示例）

#### 3.1 健康检查

- `GET /health`
  - 用于运维/飞书接入时验证服务可用。

#### 3.2 供小组件前端调用的接口

- `POST /addon/process`
  - 说明：
    - 由云文档小组件前端发起，用于**显式触发**文档处理。
  - 请求体（示例）：

```json
{
  "doc_token": "doccnxxxxxxxx",
  "doc_title": "周报-2025W01",
  "user_id": "ou_xxx",
  "mode": "summary",
  "trigger_source": "docs_addon"
}
```

  - 处理逻辑：
    - 参数校验（`doc_token`、`user_id` 必填）。
    - 调用内部统一函数 `process_doc(...)`。
    - 返回标准响应 JSON（见 5.2）。

#### 3.3 事件订阅回调接口（标签自动触发）

- `POST /feishu/event`
  - 用途：
    - 接收飞书开放平台的事件推送（如文档内容更新事件）。
  - 要求：
    - 实现飞书事件订阅协议（包括首次 URL 校验、事件加解密（如开启安全模式）、`challenge` 响应等）。
  - 典型事件流程：
    1. 收到某个“文档更新事件”：
       - 提取文档 ID（`doc_token`）和操作人 `user_id`。
    2. 根据 `doc_token` 调飞书 OpenAPI 获取文档信息（标题 / 正文某部分）。
    3. 检查是否满足“自动处理标签”规则：
       - 如标题包含 `[自动处理]`。
       - 正文中存在 `#auto_process` 标记块。
    4. 若满足规则且未被处理过：
       - 调用 `process_doc(doc_token, user_id, mode="auto", trigger_source="event")`。
    5. 返回 `{"code":0,"msg":"ok"}` 或按飞书协议响应。

  - 需要考虑：
    - **幂等性 / 去重**：防止同一文档在短时间内被重复触发。
    - 可以在数据库或缓存记录“文档处理状态”（如：未处理 / 处理中 / 成功 / 失败）。

#### 3.4 消息卡片交互回调接口（可选）

- `POST /feishu/card_callback`
  - 用途：
    - 处理用户在飞书消息卡片上的按钮点击等交互。
  - 典型用法：
    - 用户在收到的通知卡片上点击“重新生成” → 服务端根据卡片携带的参数再次调用 `process_doc`。

---

### 四、与飞书开放平台的集成点

#### 4.1 认证与 Token

- 使用 `app_id` / `app_secret` 获取 `tenant_access_token`：
  - 可以在应用启动时获取，并在内存中缓存。
  - 在 API 调用返回“无效/过期 token”时自动刷新。

#### 4.2 文档相关接口

具体 API 名称以最新飞书 OpenAPI 文档为准，这里列出能力方向：

- **读取文档内容**
  - 通过 `doc_token` 获取文档结构和文本内容。
  - 处理时可根据需要转化为纯文本或带格式的结构。

- **创建子文档**
  - 使用“创建云文档”接口，在同一空间或指定文件夹下创建新文档。
  - 将处理结果写入新文档（可按 Markdown/结构化块写入）。

- **更新原文档**
  - 在原文档某位置插入“链接块”或一段文本：
    - 例如：`自动生成子文档：[xxx](子文档链接)`。
  - 具体实现取决于 Docs API 对 block 操作的支持情况。

#### 4.3 消息/卡片接口

- **发送普通消息**
  - 给指定 `user_id` 发送一条文本消息：
    - 内容包括：处理结果提示 + 子文档链接。

- **发送交互卡片（可选增强）**
  - 使用卡片模板（JSON）发送消息：
    - 显示子文档信息。
    - 携带“重新处理”“打开原文档”等按钮，按钮 `value` 中存放必要参数（`doc_token`、`mode` 等）。
  - 在 `/feishu/card_callback` 中解析交互 payload，再次调用 `process_doc`。

#### 4.4 事件订阅

- 在飞书开发者后台为应用开启并订阅：
  - 与 Docs 相关的文档更新事件（具体事件名以官方文档为准）。
  - 事件回调 URL 指向后端 `/feishu/event`。
  - 校验通过后，文档内容变化时会推送事件至上述接口。

---

### 五、与内部“文档处理服务”的集成

#### 5.1 调用方式

你计划的内部逻辑可以设计成**一个简单 HTTP 接口**，例如：

- **URL**：`POST /internal/process_doc`
- **请求体示例**：

```json
{
  "doc_token": "doccnxxxxxxxx",
  "title": "周报-2025W01",
  "content": "……整篇文档的纯文本或结构化内容……",
  "mode": "summary"
}
```

- **响应体示例**：

```json
{
  "status": "success",
  "result": {
    "title": "自动生成的子文档标题",
    "body_markdown": "这里是要写入子文档的内容（Markdown 或其他约定格式）"
  }
}
```

> 这样可以保持后端对飞书 OpenAPI 和处理逻辑的解耦：  
> FastAPI 负责“打通飞书 & 你的内部服务”；内部服务专注“接收文本 → 返回处理结果”。

#### 5.2 FastAPI 对外统一响应格式

无论触发来源（小组件 / 事件 / 卡片），建议统一对外响应格式，例如：

```json
{
  "status": "success",
  "message": "子文档已生成",
  "child_doc_token": "doccn_child_xxx",
  "child_doc_url": "https://xxx",
  "detail": {
    "mode": "summary",
    "processed_at": "2025-01-01T12:00:00Z"
  }
}
```

失败时：

```json
{
  "status": "failed",
  "message": "处理失败，请稍后重试",
  "error_code": "INTERNAL_PROCESS_ERROR"
}
```

---

### 六、数据与状态管理

- 可选使用的存储：
  - 轻量场景：仅使用内存缓存（适合 PoC，不建议生产）。
  - 正式环境：使用 Redis / 数据库（PostgreSQL / MySQL 等）记录：
    - 文档处理任务表：
      - `doc_token`
      - `trigger_source`（addon/event/card）
      - `status`（pending / processing / success / failed）
      - `child_doc_token`
      - `created_at` / `updated_at`
      - 错误信息
    - 用于：
      - 幂等控制（避免重复处理）。
      - 故障排查。

---

### 七、配置与环境变量

- 必要配置（通过环境变量注入）：
  - `FEISHU_APP_ID`
  - `FEISHU_APP_SECRET`
  - `INTERNAL_PROCESS_API_BASE`（内部处理服务地址）
  - （可选）`ALLOWED_ORIGINS`（CORS 配置，对 Docs add-on 前端域名放行）

- FastAPI 中需配置：
  - CORS 中间件，允许来自云文档小组件所在域的请求。

---

### 八、开发步骤建议

1. **搭建 FastAPI 项目骨架**
   - 创建基本 app，提供 `/health`。
   - 配置 CORS。

2. **实现与飞书的 Token 获取逻辑**
   - 通过简单的 `GET /token` 自测。

3. **实现 `/addon/process` 接口**
   - 使用模拟的数据或 mock 内部处理服务，先打通整体链路。

4. **实现 `process_doc` 核心逻辑**
   - 从飞书拉取文档内容 → 调内部服务 → 创建子文档 → 更新原文档 → 发消息。

5. **接入事件订阅 `/feishu/event`**
   - 通过飞书后台配置测试触发。

6. **（可选）实现卡片回调 `/feishu/card_callback`**
   - 结合通知卡片模板使用。

---

### 九、错误处理与监控（简要）

- 为关键步骤添加日志：
  - 接收请求、调用飞书 API、调用内部服务、写子文档、发消息。
- 对于关键错误场景：
  - 明确返回 `status: "failed"` 和 `error_code`。
  - 在日志中记录详细堆栈，便于排查。
- 可接入简单的监控/告警（如请求量、错误率）。


