# Feishu AI Doc SDK（TypeScript/JavaScript）

该 SDK 用于前端（云文档小组件 / Web / 小程序）调用 AI Idea Generator 后端服务。

## ✨ 功能特点

- ✅ **自动初始化**：首次调用自动获取环境信息（docToken、openId），无需手动传参
- ✅ **懒加载机制**：环境信息获取一次后缓存复用，高效便捷
- ✅ **快捷方法**：`ideaExpand()`、`research()`、`save()` 语义化接口
- ✅ **通用方法**：`process({ mode })` 支持任意模式，灵活扩展
- ✅ **类型安全**：完整的 TypeScript 类型定义
- ✅ **状态追踪**：自动轮询任务状态，实时进度回调
- ✅ **环境适配**：支持浏览器、Node.js、小程序（可注入 fetch 实现）

---

## 📦 安装方式

### 方式 1：直接复制源码（推荐）

将 `sdk/src/` 目录下的所有 `.ts` 文件复制到你的前端项目中：

```
your-frontend-project/
  src/
    utils/
      feishu-ai-sdk/      # 复制到这里
        ├── client.ts
        ├── http.ts
        ├── types.ts
        ├── errors.ts
        └── index.ts
```

然后在你的代码中直接引入：

```typescript
import { FeishuAIDocSDK } from "@/utils/feishu-ai-sdk";
```

### 方式 2：本地依赖（开发环境）

如果在同一个 monorepo 中：

```bash
# pnpm
pnpm add ../sdk

# npm
npm install ../sdk
```

---

# 🚀 快速开始

### 🌟 推荐用法：零配置自动初始化

```typescript
import { FeishuAIDocSDK } from "@/utils/feishu-ai-sdk";

// 初始化（只需配置后端地址）
const sdk = new FeishuAIDocSDK({
  baseUrl: "http://127.0.0.1:8001",  // 本地开发
  // baseUrl: "https://your-api-domain.com",  // 生产环境
});

// 第一次调用：自动触发登录、获取 docToken、换取 openId
// 用户划词后点击"扩展思路"
const selectedText = getSelectedText();
const result = await sdk.ideaExpand({ content: selectedText });

console.log("生成完成:", result.childDocUrl);

// 后续调用：直接复用缓存，无感知
await sdk.research({ content: selectedText });
await sdk.save({ content: "我的笔记", title: "标题" });
```

### 示例 1：快捷方法（推荐）

```typescript
// 思路扩展
const result1 = await sdk.ideaExpand({ 
  content: "用户选中的文本" 
});

// 深度调研
const result2 = await sdk.research({ 
  content: "用户选中的文本" 
});

// 通用保存（不经过 AI 处理）
const result3 = await sdk.save({ 
  content: "要保存的内容",
  title: "文档标题" 
});

console.log(result1.childDocUrl);  // 新文档链接
console.log(result1.containerUrl); // 文件夹/节点链接
```

### 示例 2：通用方法（灵活调用）

```typescript
// 支持任意 mode，适合动态工具列表
const tools = [
  { id: "idea_expand", name: "扩展思路" },
  { id: "research", name: "深度调研" },
  { id: "summarize", name: "总结摘要" },  // 新工具无需改 SDK
];

async function handleToolClick(toolId: string) {
  const result = await sdk.process({
    mode: toolId,
    content: getSelectedText(),
  });
  showToast(`已生成：${result.childDocUrl}`);
}
```

### 示例 3：自定义获取方式（测试/特殊场景）

```typescript
const sdk = new FeishuAIDocSDK({
  baseUrl: "https://api.example.com",
  // 自定义 docToken 获取方式（用于测试）
  docTokenProvider: () => "hardcoded_token_for_test",
  // 自定义 code 获取方式
  codeProvider: async () => {
    // 自定义登录逻辑
    return "test_code";
  },
});
```

### 示例 3：分步调用（手动控制）

```typescript
// 步骤 1：触发任务
const accepted = await sdk.trigger({
  docToken: "doxcnxxxx",
  userId: "ou_xxx",
  mode: "idea_expand",
});

console.log("任务 ID:", accepted.task_id);

// 步骤 2：查询任务状态
const task = await sdk.getTask(accepted.task_id);
console.log("当前状态:", task.status);  // "running" | "succeeded" | "failed"

// 步骤 3：等待任务完成
const finalTask = await sdk.waitTask(accepted.task_id, {
  pollIntervalMs: 2000,
  timeoutMs: 180_000,
});

console.log("结果:", finalTask.result);
```

---

## 🛠️ API 参考

### 核心方法

#### `ideaExpand(options)` - 思路扩展

```typescript
const result = await sdk.ideaExpand({
  content: "用户选中的文本",  // 可选
});
```

#### `research(options)` - 深度调研

```typescript
const result = await sdk.research({
  content: "用户选中的文本",  // 可选
});
```

#### `save(options)` - 通用保存

```typescript
const result = await sdk.save({
  content: "要保存的内容",  // 必选
  title: "文档标题",          // 可选，不传则自动生成
});
```

#### `process(options)` - 通用处理

```typescript
const result = await sdk.process({
  mode: "idea_expand",      // 必选：处理模式
  content: "用户文本",      // 可选：划词内容
});
```

### 高级方法

#### `setContext(ctx)` - 手动设置上下文

```typescript
sdk.setContext({
  docToken: "doxcn...",
  wikiNodeToken: "wikcn...",
  wikiSpaceId: "7xxx",
});
```

#### `clearContext()` - 清除上下文（切换文档时）

```typescript
sdk.clearContext();  // openId 不会被清除
```

### 原有方法（向后兼容）

#### `trigger(options)` - 触发任务

```typescript
const accepted = await sdk.trigger({
  token: "doxcn...",
  userId: "ou_xxx",  // 需手动传入
  mode: "idea_expand",
  content: "用户文本",
});
```

#### `generate(options)` - 一键生成

```typescript
const result = await sdk.generate({
  docToken: "doxcn...",
  userId: "ou_xxx",  // 需手动传入
  mode: "idea_expand",
  content: "用户文本",
  onProgress: (p) => console.log(p.message),
});
```

---

## 🔧 配置选项

### SDKConfig（SDK 初始化配置）

```typescript
interface SDKConfig {
  /** 后端 API 地址（必填）*/
  baseUrl: string;                // 如："https://api.example.com"
  
  /** API 路由前缀（可选，默认 "/api"）*/
  apiPrefix?: string;             // 如："/api/v1"
  
  /** 鉴权 token 提供函数（可选）*/
  authProvider?: () => Promise<string> | string;
  
  /** fetch 实现注入（可选，默认使用 globalThis.fetch）*/
  fetch?: typeof fetch;
  
  /** 自定义 docToken 获取方式（可选，默认从飞书环境获取）*/
  docTokenProvider?: () => string | Promise<string>;
  
  /** 自定义知识库信息获取方式（可选）*/
  wikiInfoProvider?: () => { nodeToken?: string; spaceId?: string } | Promise<...>;
  
  /** 自定义用户 code 获取方式（可选，默认调用 DocMiniApp.Service.User.login()）*/
  codeProvider?: () => Promise<string>;
}
```

### ProcessOptions / IdeaExpandOptions / ResearchOptions

```typescript
interface ProcessOptions {
  mode: string;      // 处理模式
  content?: string;  // 用户选中的文本
}

interface IdeaExpandOptions {
  content?: string;  // 用户选中的文本
}

interface ResearchOptions {
  content?: string;  // 用户选中的文本
}

interface SaveOptions {
  content: string;   // 要保存的内容（必填）
  title?: string;    // 文档标题（可选，不传则自动生成）
}
```

### GenerateOptions（生成任务配置，向后兼容）

```typescript
interface GenerateOptions {
  /** 文档 token（云盘文档：doxcn/doccn 开头）*/
  docToken: string;
  
  /** 统一 token（知识库：wikcn 开头，优先级高于 docToken）*/
  token?: string;
  
  /** 用户 ID（必填）*/
  userId: string;
  
  /** 处理模式（可选，默认 "idea_expand"）*/
  mode?: "idea_expand" | "research" | string;
  
  /** 触发来源（可选）*/
  triggerSource?: string;
  
  /** 知识库节点 token（知识库场景使用）*/
  wikiNodeToken?: string;
  
  /** 知识库空间 ID（知识库场景使用）*/
  wikiSpaceId?: string;
  
  /** 轮询间隔（毫秒，默认 2000）*/
  pollIntervalMs?: number;
  
  /** 超时时间（毫秒，默认 180000 = 3 分钟）*/
  timeoutMs?: number;
  
  /** 进度回调（可选）*/
  onProgress?: (evt: ProgressEvent) => void;
}
```

---

## 📊 进度回调

`onProgress` 回调会在任务状态或进度发生变化时触发：

```typescript
onProgress: (evt) => {
  console.log(evt.taskId);    // 任务 ID
  console.log(evt.status);    // "running" | "succeeded" | "failed"
  console.log(evt.stage);     // 当前阶段，如 "llm_refine", "llm_research"
  console.log(evt.percent);   // 进度百分比 (0-100)
  console.log(evt.message);   // 进度消息
  console.log(evt.raw);       // 完整的任务状态响应
}
```

**典型进度阶段：**

- `idea_expand` 模式：`llm_expand` → `output_write` → 完成
- `research` 模式：`llm_refine` → `llm_research` → `output_write` → 完成

---

## ❌ 错误处理

```typescript
import { HTTPError, TimeoutError } from "@/utils/feishu-ai-sdk";

try {
  const result = await sdk.generate({ ... });
} catch (error) {
  if (error instanceof HTTPError) {
    console.error("HTTP 错误:", error.status, error.bodyText);
  } else if (error instanceof TimeoutError) {
    console.error("任务超时:", error.message);
  } else {
    console.error("未知错误:", error);
  }
}
```

**错误类型：**

- `HTTPError`：HTTP 请求失败（如 404、500）
- `TimeoutError`：任务超时
- `SDKError`：其他 SDK 错误

---

## 🌐 环境适配

### 浏览器环境

```typescript
const sdk = new FeishuAIDocSDK({
  baseUrl: "https://api.example.com",
});
```

### 小程序环境（需要注入 fetch）

```typescript
import { fetch } from "@tarojs/taro";  // 以 Taro 为例

const sdk = new FeishuAIDocSDK({
  baseUrl: "https://api.example.com",
  fetch: fetch,  // 注入小程序的 fetch 实现
});
```

### 需要鉴权的环境

```typescript
const sdk = new FeishuAIDocSDK({
  baseUrl: "https://api.example.com",
  authProvider: async () => {
    // 返回你的 token（可以是异步获取）
    return await getMyAuthToken();
  },
});
```

---

## 📝 完整示例

查看 `examples/basic-usage.ts` 获取更多示例：

- ✅ 云盘文档 - 思路扩展
- ✅ 知识库文档 - 深度调研
- ✅ 分步调用（手动控制）
- ✅ 错误处理

---

## 🔗 API 参考

### SDK 方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `trigger(options)` | 触发处理任务 | `Promise<AddonProcessAccepted>` |
| `getTask(taskId)` | 查询任务状态 | `Promise<TaskStatusResponse>` |
| `waitTask(taskId, opts?)` | 等待任务完成（轮询）| `Promise<TaskStatusResponse>` |
| `generate(options)` | 一键调用（触发+等待）| `Promise<GenerateResult>` |

### 返回类型

```typescript
// 触发任务返回
interface AddonProcessAccepted {
  task_id: string;
  status: "accepted";
  message: string;
}

// 任务状态
interface TaskStatusResponse {
  task_id: string;
  status: "running" | "succeeded" | "failed";
  result?: Record<string, unknown> | null;
  error?: string | null;
  progress?: {
    stage?: string;
    percent?: number;
    message?: string;
  } | null;
  created_at: number;
  updated_at?: number | null;
}

// 生成结果
interface GenerateResult {
  task: TaskStatusResponse;
  childDocUrl?: string;      // 子文档链接
  childDocToken?: string;    // 子文档 token
}
```

---

## 💡 使用建议

1. **推荐使用 `generate()` 方法**：自动处理轮询，提供进度回调
2. **知识库场景**：使用 `token` 参数（wikcn 开头），需提供 `wikiSpaceId`
3. **云盘场景**：使用 `docToken` 参数（doxcn/doccn 开头）
4. **深度调研**：建议设置更长的 `timeoutMs`（如 5 分钟）
5. **错误处理**：捕获 `HTTPError` 和 `TimeoutError`，提供友好提示

---

## 📄 License

MIT


