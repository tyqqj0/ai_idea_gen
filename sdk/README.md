# Feishu AI Doc SDK（前端 JS/TS）

该 SDK 用于前端（云文档小组件 / Web）调用本项目后端 FastAPI：
- 触发处理：`POST /api/addon/process`
- 轮询任务：`GET /api/addon/tasks/{task_id}`

## 安装（本仓库内使用）

在你的前端项目中以 workspace/本地依赖方式引入，例如（示意）：

- npm：`npm i ../sdk`
- pnpm：`pnpm add ../sdk`

## 快速使用

```ts
import { FeishuAIDocSDK } from "@ai-idea-gen/feishu-doc-sdk";

const sdk = new FeishuAIDocSDK({
  baseUrl: "https://api.example.com",
  apiPrefix: "/api", // 默认就是 /api
});

// 触发并等待结果（内部自动轮询任务）
const res = await sdk.generate({
  docToken: "doxcnxxxx",
  userId: "ou_xxx",
  mode: "idea_expand",
  triggerSource: "docs_addon",
  onProgress: (p) => {
    // 后端会返回 progress: {stage, percent, message}
    console.log(`[${p.status}] ${p.percent ?? "-"}% ${p.stage ?? ""} ${p.message ?? ""}`);
  },
});

console.log(res.childDocUrl, res.task.status, res.task.result);
```

## 在飞书小组件环境中（建议）

如果你的环境需要 token，可通过 `authProvider` 注入（示意）：

```ts
const sdk = new FeishuAIDocSDK({
  baseUrl: "https://api.example.com",
  authProvider: async () => {
    // TODO：替换为你实际的小组件 token 获取方式
    return "your_token";
  },
});
```

## 业务流程（SDK 抽象）

- `trigger()`：只触发，拿到 `task_id`
- `getTask()`：查询任务状态
- `waitTask()`：轮询等待完成
- `generate()`：trigger + waitTask 一键完成


