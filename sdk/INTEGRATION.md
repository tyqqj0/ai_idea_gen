# SDK 前端集成指南

## 📦 如何将 SDK 复制到前端项目

### 步骤 1：复制源代码文件

将以下文件复制到你的前端项目中：

```bash
# 从后端项目复制到前端项目
cp -r ai_idea_gen/sdk/src/* your-frontend-project/src/utils/feishu-ai-sdk/
```

**需要复制的文件：**
```
sdk/src/
├── client.ts      # SDK 主类
├── http.ts        # HTTP 客户端
├── types.ts       # TypeScript 类型定义
├── errors.ts      # 错误类型
└── index.ts       # 统一导出
```

**前端项目结构示例：**
```
your-frontend-project/
  src/
    utils/
      feishu-ai-sdk/      ← 复制到这里
        ├── client.ts
        ├── http.ts
        ├── types.ts
        ├── errors.ts
        └── index.ts
```

---

### 步骤 2：在前端代码中引入

```typescript
// 方式 1：使用路径别名（推荐）
import { FeishuAIDocSDK } from "@/utils/feishu-ai-sdk";

// 方式 2：使用相对路径
import { FeishuAIDocSDK } from "../../utils/feishu-ai-sdk";
```

---

### 步骤 3：初始化 SDK

```typescript
const sdk = new FeishuAIDocSDK({
  // 本地开发环境
  baseUrl: "http://127.0.0.1:8001",
  
  // 生产环境（替换为你的后端域名）
  // baseUrl: "https://your-backend-api.com",
});
```

---

## 🚀 快速使用示例

### 示例 1：云盘文档 - 思路扩展

```typescript
import { FeishuAIDocSDK } from "@/utils/feishu-ai-sdk";

async function expandIdea(docToken: string, userId: string) {
  const sdk = new FeishuAIDocSDK({
    baseUrl: "https://your-backend-api.com",
  });

  try {
    const result = await sdk.generate({
      docToken: docToken,
      userId: userId,
      mode: "idea_expand",
      
      onProgress: (p) => {
        // 显示进度
        console.log(`进度: ${p.percent ?? 0}%`);
        console.log(`状态: ${p.message}`);
      },
    });

    // 成功后的处理
    console.log("生成完成！");
    console.log("子文档链接:", result.childDocUrl);
    
    // 可以跳转到子文档
    window.open(result.childDocUrl, "_blank");
    
  } catch (error) {
    console.error("生成失败:", error);
  }
}
```

### 示例 2：知识库文档 - 深度调研

```typescript
async function deepResearch(wikiToken: string, spaceId: string, userId: string) {
  const sdk = new FeishuAIDocSDK({
    baseUrl: "https://your-backend-api.com",
  });

  try {
    const result = await sdk.generate({
      token: wikiToken,           // 知识库 node_token (wikcn 开头)
      userId: userId,
      mode: "research",
      wikiSpaceId: spaceId,
      
      // 深度调研可能需要更长时间
      timeoutMs: 300_000,         // 5 分钟
      pollIntervalMs: 3000,       // 每 3 秒轮询
      
      onProgress: (p) => {
        // 更新 UI 进度条
        updateProgressBar(p.percent ?? 0);
        updateStatusMessage(p.message ?? "处理中...");
      },
    });

    console.log("调研完成:", result.childDocUrl);
    
  } catch (error) {
    console.error("调研失败:", error);
  }
}
```

---

## 🎨 在 React 中使用

```typescript
import { useState } from "react";
import { FeishuAIDocSDK } from "@/utils/feishu-ai-sdk";

function DocumentProcessor() {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<string | null>(null);

  const handleGenerate = async () => {
    const sdk = new FeishuAIDocSDK({
      baseUrl: "https://your-backend-api.com",
    });

    try {
      const res = await sdk.generate({
        docToken: "doxcnxxxx",
        userId: "ou_xxx",
        mode: "idea_expand",
        
        onProgress: (p) => {
          setProgress(p.percent ?? 0);
          setStatus(p.message ?? "");
        },
      });

      setResult(res.childDocUrl ?? null);
    } catch (error) {
      console.error(error);
      setStatus("生成失败");
    }
  };

  return (
    <div>
      <button onClick={handleGenerate}>生成思路扩展</button>
      
      {progress > 0 && (
        <div>
          <div className="progress-bar" style={{ width: `${progress}%` }} />
          <p>{status}</p>
        </div>
      )}
      
      {result && (
        <a href={result} target="_blank">查看生成的文档</a>
      )}
    </div>
  );
}
```

---

## 🎨 在 Vue 中使用

```vue
<template>
  <div>
    <button @click="handleGenerate">生成思路扩展</button>
    
    <div v-if="progress > 0">
      <div class="progress-bar" :style="{ width: `${progress}%` }"></div>
      <p>{{ status }}</p>
    </div>
    
    <a v-if="result" :href="result" target="_blank">查看生成的文档</a>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { FeishuAIDocSDK } from '@/utils/feishu-ai-sdk';

const progress = ref(0);
const status = ref('');
const result = ref<string | null>(null);

const handleGenerate = async () => {
  const sdk = new FeishuAIDocSDK({
    baseUrl: 'https://your-backend-api.com',
  });

  try {
    const res = await sdk.generate({
      docToken: 'doxcnxxxx',
      userId: 'ou_xxx',
      mode: 'idea_expand',
      
      onProgress: (p) => {
        progress.value = p.percent ?? 0;
        status.value = p.message ?? '';
      },
    });

    result.value = res.childDocUrl ?? null;
  } catch (error) {
    console.error(error);
    status.value = '生成失败';
  }
};
</script>
```

---

## ⚙️ 环境配置建议

### 开发环境 vs 生产环境

```typescript
// config.ts
const API_BASE_URL = process.env.NODE_ENV === 'production'
  ? 'https://api.production.com'
  : 'http://127.0.0.1:8001';

export const sdk = new FeishuAIDocSDK({
  baseUrl: API_BASE_URL,
});
```

### 小程序环境

```typescript
// 以 Taro 为例
import Taro from '@tarojs/taro';

const sdk = new FeishuAIDocSDK({
  baseUrl: 'https://your-backend-api.com',
  fetch: Taro.request as any,  // 注入小程序的请求方法
});
```

---

## 🔍 常见问题

### Q1: 如何处理跨域问题？

**A:** 在后端配置 CORS，允许前端域名访问：

```python
# backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 你的前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Q2: 如何在飞书小组件中使用？

**A:** 飞书小组件有自己的鉴权机制，需要提供 `authProvider`：

```typescript
const sdk = new FeishuAIDocSDK({
  baseUrl: "https://your-backend-api.com",
  authProvider: async () => {
    // 从飞书小组件获取 token
    const token = await getFeishuToken();
    return token;
  },
});
```

### Q3: 如何取消正在进行的任务？

**A:** 当前版本不支持取消任务，但可以停止轮询：

```typescript
let cancelled = false;

const result = await sdk.generate({
  // ...
  onProgress: (p) => {
    if (cancelled) {
      throw new Error("用户取消");
    }
  },
});

// 用户点击取消按钮时
cancelButton.onclick = () => {
  cancelled = true;
};
```

---

## 📝 完整的类型定义

SDK 提供完整的 TypeScript 类型支持，你可以直接导入使用：

```typescript
import type {
  SDKConfig,
  TriggerOptions,
  GenerateOptions,
  GenerateResult,
  TaskStatusResponse,
  TaskStatus,
} from "@/utils/feishu-ai-sdk";
```

---

## 🎯 最佳实践

1. **错误处理**：始终使用 `try-catch` 包裹 SDK 调用
2. **进度反馈**：使用 `onProgress` 提供实时反馈，提升用户体验
3. **超时设置**：根据不同模式设置合理的超时时间
   - `idea_expand`: 默认 3 分钟
   - `research`: 建议 5 分钟或更长
4. **环境区分**：开发环境和生产环境使用不同的 `baseUrl`
5. **日志记录**：在生产环境记录错误日志，便于问题排查

---

## 📞 获取帮助

- 查看完整文档：`sdk/README.md`
- 查看示例代码：`sdk/examples/basic-usage.ts`
- 后端 API 文档：访问 `http://your-backend-api.com/docs`
