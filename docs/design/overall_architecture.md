# AI 小工具体系 - 整体架构设计

## 1. 核心理念

将"处理内容"和"保存输出"分离，形成可复用的分层架构：

- **处理层**：各种小工具的业务逻辑（如思路扩展、调研分析、图片理解等）
- **输出层**：通用的保存能力（如写子文档、发送消息、Webhook 回调等）

## 1.1 当前问题分析

### 当前架构（存在问题）

```
SDK (client.ts)                     后端
    │                                │
    │ trigger({                      │
    │   token,                       │
    │   userId,        ──────────→   API (/addon/process)
    │   mode,                        │
    │   wikiNodeToken?,              ↓
    │   wikiSpaceId?                ProcessManager.process_doc()
    │ })                             │
    │                                ├─→ 读取文档内容
    │                                ├─→ Processor.run() ──→ AI 处理
    │                                └─→ OutputHandler.handle()
    │                                         │
    │                                         ↓
    │                              FeishuChildDocOutputHandler
    │                              (混合了多种职责):
    │                                - 标题生成 (AI)
    │                                - 场景判断
    │                                - 文件夹创建
    │                                - 文档创建
    │                                - 内容写入
    │                                - 权限添加
    │                                - 回链
    │                                - 通知发送
```

### 当前问题

1. **缺少划词文本**：SDK 没有传 `content` (用户选中的文本)
2. **user_id 手动传入**：需要前端自己获取 open_id
3. **OutputHandler 职责过重**：`feishu_child_doc.py` 承担了太多职责
4. **写入逻辑不可复用**：其他工具想写子文档必须重新实现

## 1.2 新旧架构对比

### 新 ChildDocWriter vs 现有 FeishuChildDocOutputHandler

| 维度 | 现有 OutputHandler | 新 ChildDocWriter |
|------|-------------------|------------------|
| **定位** | 工作流的一环（和 Processor 绑定） | 独立的底层服务 |
| **职责** | 混合：标题生成 + 写入 + 通知 | 单一：只负责写入 |
| **输入** | ProcessorResult（需要先跑完 Processor） | 纯文本 + 位置信息 |
| **可复用性** | 仅限当前工作流 | 任意场景可调用 |
| **标题** | 内部生成 | 调用方提供（或默认自动生成） |
| **通知** | 内部发送 | 不处理（调用方自行决定） |

### 核心区别

**现有方式**：Processor → OutputHandler（一体化）
```python
# OutputHandler 知道太多事情
class FeishuChildDocOutputHandler:
    async def handle(self, ctx, source_doc, processor_result, notify_user):
        # 1. 生成标题（调用 AI）
        # 2. 判断场景
        # 3. 创建文件夹
        # 4. 创建文档
        # 5. 写入内容
        # 6. 权限
        # 7. 回链
        # 8. 发送通知
```

**新方式**：业务逻辑 → ChildDocWriter（解耦）
```python
# ChildDocWriter 只关心"写"
class ChildDocWriter:
    async def write(self, content, source_token, user_id, title=None):
        # 1. 判断场景
        # 2. 创建容器
        # 3. 创建文档
        # 4. 写入内容
        # 5. 权限
        # 6. 回链
        return result  # 调用方决定如何使用结果

# Processor 或 OutputHandler 调用 Writer
class IdeaExpandProcessor:
    async def run(self, ...):
        result = await self.ai_process(...)  # 业务逻辑
        saved = await self.writer.write(result.content, ...)  # 写入
        if notify:
            await self.feishu.send_card(...)  # 通知
```

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         前端（飞书云文档小程序）                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 职责：                                                       │   │
│  │ - UI 交互（划词、选择、按钮等）                                │   │
│  │ - 获取飞书环境信息（doc_token、user code）                    │   │
│  │ - 收集用户输入（选中文本、上传图片等）                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                              SDK                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 职责：                                                       │   │
│  │ - 封装后端 API 调用                                          │   │
│  │ - 管理用户会话（缓存 open_id）                                │   │
│  │ - 提供简洁接口给前端                                         │   │
│  │ - 任务轮询和状态管理                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                              后端                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                        API 层                                │   │
│  │  /api/addon/auth      - 用户认证（code → open_id）           │   │
│  │  /api/addon/process   - 触发处理任务                         │   │
│  │  /api/addon/tasks/:id - 查询任务状态                         │   │
│  │  /api/addon/save      - 通用保存接口（未来）                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                ↓                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       处理层（Processors）                    │   │
│  │  idea_expand  - 思路扩展                                     │   │
│  │  research     - 调研分析                                     │   │
│  │  image_understand - 图片理解（未来）                          │   │
│  │  ...                                                         │   │
│  │                                                               │   │
│  │  输入：原始内容、用户选中文本、附件等                          │   │
│  │  输出：处理后的文本（Markdown）                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                ↓                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       输出层（Outputs）                       │   │
│  │  feishu_child_doc - 写飞书子文档（知识库/云盘）               │   │
│  │  webhook          - Webhook 回调                             │   │
│  │  message          - 飞书消息通知                              │   │
│  │  ...                                                         │   │
│  │                                                               │   │
│  │  输入：文本内容 + 原始文档位置 + 用户ID                        │   │
│  │  输出：保存结果（新文档链接等）                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. 数据流

### 3.0 新架构完整数据流（重构后）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              前端（飞书小程序）                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. 用户划词选中文本 → selectedText                                      │ │
│  │ 2. 获取当前文档 → docToken, wikiNodeToken?, wikiSpaceId?               │ │
│  │ 3. 用户登录获取 code → DocMiniApp.Service.User.login()                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                                   SDK                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ // 1. 认证（一次性，缓存 openId）                                       │ │
│  │ await sdk.auth(code);  // 内部调用后端 /auth，缓存返回的 openId         │ │
│  │                                                                        │ │
│  │ // 2. 处理（SDK 自动附加 userId）                                       │ │
│  │ const result = await sdk.generate({                                    │ │
│  │   token: docToken,                                                     │ │
│  │   mode: 'idea_expand',                                                 │ │
│  │   content: selectedText,      // ← 新增：划词文本                       │ │
│  │   wikiNodeToken,                                                       │ │
│  │   wikiSpaceId,                                                         │ │
│  │ });                                                                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ↓                                   ↓
┌────────────────────────────────┐    ┌────────────────────────────────────────┐
│   POST /api/addon/auth         │    │   POST /api/addon/process              │
│   { code }                     │    │   { token, mode, content, userId, ... }│
│   → { open_id }                │    │   → { task_id }                        │
└────────────────────────────────┘    └────────────────────────────────────────┘
                                                        │
                                                        ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                            ProcessManager                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. 获取文档元信息                                                       │ │
│  │ 2. 读取文档内容                                                         │ │
│  │ 3. 调用 Processor（传入 content/selectedText）                          │ │
│  │ 4. Processor 返回 { title, content_md, summary }                       │ │
│  │ 5. 调用 ChildDocWriter.write()                                         │ │
│  │ 6. 可选：发送通知                                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                           ┌──────────┴──────────┐
                           ↓                     ↓
             ┌─────────────────────┐   ┌─────────────────────┐
             │   Processor         │   │   ChildDocWriter    │
             │   (业务逻辑)         │   │   (写入服务)         │
             │                     │   │                     │
             │   - 读取原文档       │   │   - 判断场景         │
             │   - 处理 selected   │   │   - 创建容器         │
             │   - 调用 AI 生成    │   │   - 创建文档         │
             │   - 生成标题/摘要   │   │   - 写入内容         │
             │                     │   │   - 添加权限         │
             │   输出：Markdown    │   │   - 回链             │
             └─────────────────────┘   └─────────────────────┘
```

### 3.1 完整请求流程

```
前端                     SDK                      后端
  │                       │                        │
  │ ① 用户划词/选择内容    │                        │
  │ ② 获取 doc_token      │                        │
  │ ③ 获取 user code      │                        │
  │                       │                        │
  │ ──── auth(code) ────→ │                        │
  │                       │ ──── /auth ──────────→ │
  │                       │ ←──── open_id ──────── │
  │ ←──── ready ───────── │                        │
  │                       │                        │
  │ ──── process() ─────→ │                        │
  │   {                   │                        │
  │     token,            │                        │
  │     mode,             │ ──── /process ───────→ │
  │     content (选中文本) │   + user_id            │ ④ 处理层执行
  │   }                   │                        │ ⑤ 输出层写入
  │                       │ ←──── task_id ──────── │
  │                       │                        │
  │                       │ ──── /tasks/:id ─────→ │
  │                       │ ←──── result ───────── │
  │ ←──── result ──────── │                        │
  │                       │                        │
```

### 3.2 关键数据结构

``typescript
// 处理请求
interface ProcessRequest {
  token: string;           // 原始文档 token
  mode: string;            // 处理模式 (idea_expand, research, ...)
  content?: string;        // 用户选中的文本（可选）
  user_id: string;         // 用户 open_id（SDK 自动附加）
  
  // 可选参数
  wiki_node_token?: string;  // 知识库节点 token
  wiki_space_id?: string;    // 知识库空间 ID
  trigger_source?: string;   // 触发来源
}

// 任务结果
interface TaskResult {
  task_id: string;
  status: 'pending' | 'processing' | 'succeeded' | 'failed';
  result?: {
    child_doc_token: string;
    child_doc_url: string;
    title: string;
    summary: string;
    // ...
  };
  error?: string;
  progress?: {
    stage: string;
    percent: number;
    message: string;
  };
}
```

## 4. 扩展性设计

### 4.1 新增处理器

只需在 `processors/` 下新增模块，实现统一接口：

``python
class MyProcessor(BaseProcessor):
    async def process(self, content: str, context: ProcessContext) -> ProcessResult:
        # 处理逻辑
        return ProcessResult(content_md=result, title=title, summary=summary)
```

### 4.2 新增输出方式

只需在 `outputs/` 下新增模块，实现统一接口：

``python
class MyOutput(BaseOutput):
    async def handle(self, ctx: ProcessContext, result: ProcessResult, ...) -> OutputResult:
        # 输出逻辑
        return OutputResult(...)
```

### 4.3 新增前端

SDK 保持通用，只需适配新平台获取环境信息的方式：

- 飞书小程序：`DocMiniApp.Service.User.login()`
- 飞书 Web：飞书 JSSDK
- 其他平台：自定义方式

## 5. 未来规划

### 5.1 通用保存接口

独立的保存 API，可被任何工具调用：

```
POST /api/addon/save
{
  "content": "要保存的内容",
  "source_token": "原始文档位置",
  "user_id": "ou_xxx",
  "title": "文档标题（可选，不传则自动生成）"
}
```

### 5.2 更多输入方式

- 图片理解
- 文件批量读取
- 语音输入
- ...

### 5.3 更多输出方式

- 飞书消息卡片
- 邮件发送
- 第三方存储
- ...

## 6. SDK 数据流详解

### 6.1 当前 SDK 问题

```typescript
// 当前 SDK 需要手动传 userId
await sdk.trigger({
  token: docToken,
  userId: "ou_xxx",  // ← 前端需要自己获取
  mode: "idea_expand",
  // 没有 content/selectedText 参数！
});
```

### 6.2 新 SDK 设计

``typescript
// 1. 初始化
const sdk = new FeishuAIDocSDK({ baseUrl: "https://api.example.com" });

// 2. 认证（前端获取 code 后调用一次）
const code = await DocMiniApp.Service.User.login();  // 飞书 API
await sdk.auth(code);  // SDK 内部：调用后端 /auth，缓存 openId

// 3. 处理（SDK 自动附加 userId）
const result = await sdk.generate({
  token: docToken,
  mode: "idea_expand",
  content: selectedText,      // ← 新增：用户选中的文本
  wikiNodeToken,              // 可选
  wikiSpaceId,                // 可选
});

// 4. 结果
console.log(result.childDocUrl);      // 新文档链接
console.log(result.containerUrl);     // 文件夹/节点链接
```

### 6.3 SDK 新增接口

``typescript
// types.ts 新增
interface AuthRequest {
  code: string;
}

interface AuthResponse {
  open_id: string;
}

interface TriggerOptions {
  token: string;
  mode: string;
  content?: string;           // 新增：划词文本
  wikiNodeToken?: string;
  wikiSpaceId?: string;
  triggerSource?: string;
  // userId 不再需要传入，SDK 自动附加
}

// client.ts 新增
class FeishuAIDocSDK {
  private openId: string | null = null;

  async auth(code: string): Promise<void> {
    const resp = await this.http.postJSON<AuthResponse>("/addon/auth", { code });
    this.openId = resp.open_id;
  }

  async trigger(options: TriggerOptions): Promise<AddonProcessAccepted> {
    if (!this.openId) {
      throw new Error("Not authenticated. Call auth() first.");
    }
    const payload = {
      ...options,
      user_id: this.openId,  // 自动附加
    };
    return await this.http.postJSON("/addon/process", payload);
  }
}
```

## 7. 重构计划

### 7.1 改动范围

| 组件 | 改动内容 |
|------|---------|
| **SDK** | 新增 `auth()` 方法，`trigger()` 新增 `content` 参数，自动附加 `userId` |
| **后端 API** | 新增 `/addon/auth` 接口，`/addon/process` 新增 `content` 字段 |
| **ProcessContext** | 新增 `selected_text` 字段（已有，确认使用） |
| **ChildDocWriter** | 新建，从 `feishu_child_doc.py` 抽取写入逻辑 |
| **OutputHandler** | 简化，调用 ChildDocWriter，只处理通知 |

### 7.2 具体步骤

**Phase 1: SDK + 后端认证（解决 userId 自动获取）**

1. 后端新增 `/api/addon/auth` 接口
2. SDK 新增 `auth(code)` 方法
3. SDK `trigger()` 自动附加 `userId`

**Phase 2: 划词文本传递**

1. SDK `trigger()` 新增 `content` 参数
2. 后端 `/addon/process` 接收 `content`
3. ProcessContext 使用 `selected_text` 字段

**Phase 3: 抽取 ChildDocWriter**

1. 创建 `backend/services/outputs/child_doc_writer.py`
2. 将写入逻辑从 `feishu_child_doc.py` 抽取
3. `feishu_child_doc.py` 调用 ChildDocWriter
4. 验证功能不变

**Phase 4: 可选优化**

1. 新增 `/api/addon/save` 独立保存接口
2. 支持更多前端平台（Web JSSDK 等）

### 7.3 文件变更预览

```
sdk/src/
  client.ts      # 新增 auth(), 修改 trigger()
  types.ts       # 新增 AuthRequest, AuthResponse, content 字段

backend/
  api/routes.py  # 新增 /addon/auth
  core/manager.py  # ProcessContext 已有 selected_text
  services/outputs/
    child_doc_writer.py  # 新建：纯写入服务
    feishu_child_doc.py  # 简化：调用 writer + 通知
```

