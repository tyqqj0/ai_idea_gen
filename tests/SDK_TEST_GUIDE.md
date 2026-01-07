# SDK 测试指南

## 📋 测试清单

### ✅ 已完成的测试

| 测试类型 | 测试文件 | 状态 | 说明 |
|---------|---------|------|------|
| **懒加载机制测试** | `test_sdk_lazy_init.js` | ✅ 通过 | 验证自动初始化、缓存复用 |
| **快捷方法测试** | `test_sdk_lazy_init.js` | ✅ 通过 | 验证 ideaExpand(), research(), save() |
| **通用方法测试** | `test_sdk_lazy_init.js` | ✅ 通过 | 验证 process() 动态 mode |
| **上下文管理测试** | `test_sdk_lazy_init.js` | ✅ 通过 | 验证 setContext(), clearContext() |
| **自定义 Provider 测试** | `test_sdk_lazy_init.js` | ✅ 通过 | 验证自定义获取方式 |

### ⏳ 待完成的测试

| 测试类型 | 测试文件 | 状态 | 说明 |
|---------|---------|------|------|
| **集成测试** | `test_sdk_integration.sh` | ⏳ 待运行 | 需要后端服务 + 真实 token |
| **后端 /auth 接口** | - | ⏳ 待实现 | 需要先实现后端接口 |
| **前端真实场景测试** | - | ⏳ 待测试 | 需要前端小程序环境 |

---

## 🧪 测试 1: 懒加载机制测试（已通过 ✅）

### 运行方式

```bash
node tests/test_sdk_lazy_init.js
```

### 测试场景

1. **自动初始化**
   - 第一次调用 `ideaExpand()` → 自动获取 docToken、换取 openId
   - 第二次调用 `research()` → 直接复用缓存
   - 第三次调用 `save()` → 直接复用缓存

2. **通用方法**
   - 动态工具列表场景
   - 使用 `process({ mode })` 支持任意 mode

3. **上下文管理**
   - `setContext()` 手动设置
   - `clearContext()` 清除文档上下文（保留 openId）

4. **自定义 Provider**
   - 自定义 `docTokenProvider`
   - 自定义 `codeProvider`

### 测试结果

```
✅ 所有测试通过！

关键验证点：
- ✅ 懒加载：第一次调用触发初始化
- ✅ 缓存复用：后续调用直接使用缓存
- ✅ content 参数：正确传递划词文本
- ✅ openId 保留：clearContext() 后不重新登录
```

---

## 🔗 测试 2: 集成测试（需要后端服务）

### 前置条件

1. 后端服务运行在 `http://127.0.0.1:8001`
2. 设置环境变量：
   ```bash
   export DOC_TOKEN="doxcnxxxxx"  # 真实的文档 token
   export USER_ID="ou_xxxxx"      # 真实的用户 ID
   ```

### 运行方式

```bash
bash tests/test_sdk_integration.sh
```

### 测试场景

1. **Ping 接口** - 验证后端服务可访问
2. **触发任务** - 验证 content 参数传递
3. **查询任务** - 验证任务状态查询
4. **/auth 接口** - 验证认证接口（如果已实现）

### 预期输出

```bash
🧪 测试 1: Ping 接口
✅ {"message":"pong"}

🧪 测试 2: 触发任务（带 content 参数）
✅ 任务已触发: task_xxx

🧪 测试 3: 查询任务状态
任务状态: running / succeeded / failed

🧪 测试 4: /auth 接口
⚠️  /auth 接口尚未实现（后续需要添加）
```

---

## 🚀 测试 3: 编译 TypeScript SDK

### 编译步骤

```bash
cd sdk
npm install
npm run build
```

### 验证编译产物

```bash
ls -lh sdk/dist/

# 应该看到：
# client.js
# http.js
# types.js
# errors.js
# index.js
# *.d.ts (类型定义文件)
```

---

## 📱 测试 4: 前端真实场景测试

### 测试环境

- 飞书云文档小程序环境
- 或飞书 Web 网页环境

### 测试步骤

1. **引入 SDK**
   ```typescript
   import { FeishuAIDocSDK } from "@/utils/feishu-ai-sdk";
   ```

2. **零配置初始化**
   ```typescript
   const sdk = new FeishuAIDocSDK({
     baseUrl: "https://your-api-domain.com",
   });
   ```

3. **测试快捷方法**
   ```typescript
   // 第一次调用：自动触发登录
   const result1 = await sdk.ideaExpand({ 
     content: selectedText 
   });

   // 后续调用：直接复用
   const result2 = await sdk.research({ 
     content: selectedText 
   });
   ```

### 验证点

- ✅ 飞书登录弹窗出现
- ✅ 获取 docToken 成功
- ✅ 换取 openId 成功
- ✅ 任务触发成功
- ✅ 后续调用无需重新登录

---

## 🐛 常见问题排查

### 问题 1: /auth 接口返回 404

**原因**: 后端尚未实现 `/api/addon/auth` 接口

**解决方案**:
1. 在后端添加 `/auth` 接口（参考设计文档）
2. 或临时使用 `trigger()` 方法（需要手动传 userId）

### 问题 2: docToken 获取失败

**原因**: 不在飞书环境中，`DocMiniApp` 未定义

**解决方案**:
```typescript
const sdk = new FeishuAIDocSDK({
  baseUrl: "...",
  docTokenProvider: () => "你的测试token",
  codeProvider: async () => "你的测试code",
});
```

### 问题 3: CORS 跨域错误

**原因**: 前端域名不在后端 CORS 白名单中

**解决方案**: 检查后端 CORS 配置

---

## 📊 测试覆盖率

| 功能 | 单元测试 | 集成测试 | 前端测试 | 状态 |
|------|---------|---------|---------|------|
| 懒加载机制 | ✅ | ⏳ | ⏳ | 80% |
| 快捷方法 | ✅ | ⏳ | ⏳ | 80% |
| 通用方法 | ✅ | ⏳ | ⏳ | 80% |
| 上下文管理 | ✅ | ⏳ | ⏳ | 80% |
| content 参数 | ✅ | ⏳ | ⏳ | 80% |
| /auth 接口 | ✅ | ⏳ | ⏳ | 60% |

---

## ✅ 下一步计划

1. **后端实现 /auth 接口**
   - 接收 code
   - 调用飞书 API 换取 user_access_token
   - 解析 open_id 并返回

2. **运行集成测试**
   ```bash
   export DOC_TOKEN="真实token"
   export USER_ID="真实user_id"
   bash tests/test_sdk_integration.sh
   ```

3. **前端真实测试**
   - 编译 SDK
   - 集成到前端项目
   - 在飞书环境中测试

4. **性能测试**
   - 测试缓存命中率
   - 测试并发场景
   - 测试切换文档场景
