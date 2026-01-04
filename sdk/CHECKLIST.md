# ✅ SDK 使用检查清单

## 📋 复制到前端项目前的准备

- [ ] 确认后端服务已启动并可访问
- [ ] 确认后端 API 地址（如 `http://127.0.0.1:8001`）
- [ ] 确认后端已配置 CORS，允许前端域名访问

---

## 📦 复制文件到前端

### 方法 1：手动复制（推荐）

```bash
# 1. 在前端项目中创建目录
mkdir -p your-frontend-project/src/utils/feishu-ai-sdk

# 2. 复制源代码文件
cp ai_idea_gen/sdk/src/*.ts your-frontend-project/src/utils/feishu-ai-sdk/
```

**需要复制的文件（5 个）：**
- [ ] `client.ts`
- [ ] `http.ts`
- [ ] `types.ts`
- [ ] `errors.ts`
- [ ] `index.ts`

### 方法 2：复制整个目录

```bash
cp -r ai_idea_gen/sdk/src your-frontend-project/src/utils/feishu-ai-sdk
```

---

## 🔧 前端项目集成

- [ ] 文件已复制到前端项目
- [ ] TypeScript 编译器能识别这些文件（无报错）
- [ ] 已配置路径别名（可选，如 `@/utils`）

---

## 🚀 代码集成测试

### 基础测试

```typescript
import { FeishuAIDocSDK } from "@/utils/feishu-ai-sdk";

// 1. 初始化测试
const sdk = new FeishuAIDocSDK({
  baseUrl: "http://127.0.0.1:8001",  // 替换为你的后端地址
});

console.log("✅ SDK 初始化成功");
```

- [ ] 代码无编译错误
- [ ] 能正确导入 SDK 类

### 功能测试（可选）

```typescript
// 2. 触发任务测试
async function testTrigger() {
  try {
    const result = await sdk.trigger({
      docToken: "test_doc_token",  // 替换为真实 token
      userId: "test_user_id",      // 替换为真实 user_id
      mode: "idea_expand",
    });
    console.log("✅ 触发成功:", result.task_id);
  } catch (error) {
    console.error("❌ 触发失败:", error);
  }
}
```

- [ ] 能成功触发任务
- [ ] 返回正确的 `task_id`

---

## 🎯 生产环境检查

- [ ] 已将 `baseUrl` 改为生产环境地址
- [ ] 已配置环境变量（开发 vs 生产）
- [ ] 已添加错误处理和用户提示
- [ ] 已添加进度显示 UI
- [ ] 已测试超时场景
- [ ] 已测试网络错误场景

---

## 📝 文档参考

- [ ] 已阅读 `README.md`（完整 API 文档）
- [ ] 已阅读 `INTEGRATION.md`（集成指南）
- [ ] 已查看 `examples/basic-usage.ts`（示例代码）

---

## 🔍 常见问题排查

### 问题 1：无法导入 SDK

**检查：**
- [ ] 文件路径是否正确
- [ ] 是否有 TypeScript 编译错误
- [ ] 路径别名是否配置正确

### 问题 2：跨域错误（CORS）

**检查：**
- [ ] 后端是否配置 CORS
- [ ] `allow_origins` 是否包含前端地址
- [ ] 是否使用了正确的请求方法（POST/GET）

### 问题 3：任务一直 pending

**检查：**
- [ ] 后端服务是否正常运行
- [ ] 任务是否真的在执行（查看后端日志）
- [ ] 超时时间是否足够（深度调研需要 5 分钟+）

---

## 📊 性能优化建议

- [ ] 使用 `onProgress` 提供实时反馈
- [ ] 根据模式设置合理的超时时间
- [ ] 在生产环境启用日志记录
- [ ] 考虑添加重试机制（针对网络错误）

---

## ✨ 完成！

当所有检查项都完成后，SDK 就可以正常使用了！🎉

**下一步：**
1. 参考 `examples/basic-usage.ts` 编写你的业务代码
2. 根据需要调整配置和错误处理
3. 在测试环境充分测试后再部署到生产环境
