# 任务通知与状态恢复设计计划

> 创建时间：2026-01-08
> 状态：计划中

## 1. 背景与需求

### 用户场景
1. 用户在云文档小卡片中点击"深度调研"
2. 任务开始执行（可能需要几分钟）
3. 用户可能离开当前文档，去做别的事情
4. 任务完成后：
   - 飞书机器人发消息通知用户
   - 用户回到文档，刷新页面后能看到任务结果

### 核心需求
- [ ] 错误信息传递：前端能看到详细错误
- [ ] 进度提示：长时间任务显示进度
- [ ] 完成通知：飞书机器人发消息
- [ ] 状态恢复：刷新页面后恢复任务状态

---

## 2. 架构设计

### 2.1 Task 定位

Task 是**全局概念**，不强制绑定特定场景：

```
Task（全局）
├── task_id: 唯一标识
├── user_id: 触发用户
├── status: pending | running | succeeded | failed
├── progress: { stage, percent, message }
├── result: { child_doc_url, ... }
├── error: 详细错误信息
├── created_at / updated_at
└── metadata: { doc_token?, mode, ... }  # 可选的场景信息
```

### 2.2 SDK 职责边界

**核心功能（必须）**：
- `getTask(taskId)` - 查询任务状态
- `waitTask(taskId, opts)` - 等待任务完成
- `process(opts)` / `ideaExpand()` / `research()` - 触发任务

**可选功能（推荐）**：
- `cache.saveTask(key, taskId)` - 保存任务 ID 到本地
- `cache.getLastTask(key)` - 获取最近的任务 ID
- `cache.clear(key)` - 清除缓存

**场景封装（应用层决定）**：
- docToken → taskId 映射由应用层管理
- SDK 提供工具，但不强制使用

### 2.3 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                         完整流程                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 用户点击"深度调研"                                           │
│     │                                                           │
│     ├─→ SDK.process({ mode: "research" })                       │
│     │     └─→ 返回 { task_id: "xxx" }                           │
│     │                                                           │
│     ├─→ 前端保存: localStorage[docToken] = taskId               │
│     │                                                           │
│     └─→ 显示进度（onProgress 回调）                              │
│                                                                 │
│  2. 后端执行任务...                                              │
│     │                                                           │
│     ├─→ 更新 progress: { stage: "llm", percent: 50 }            │
│     │                                                           │
│     └─→ 任务完成                                                 │
│           ├─→ 更新 result: { child_doc_url: "..." }             │
│           └─→ 发送飞书消息通知用户                               │
│                                                                 │
│  3. 用户刷新页面                                                 │
│     │                                                           │
│     ├─→ 读取 localStorage[docToken] → taskId                    │
│     │                                                           │
│     ├─→ SDK.getTask(taskId)                                     │
│     │                                                           │
│     └─→ 显示结果："上次任务已完成，点击查看"                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 实现计划

### Phase 1: 错误信息传递（短期）

**目标**：前端能看到详细的错误信息

**检查点**：
- [ ] 后端：任务失败时，error 字段包含详细信息
- [ ] SDK：GenerateResult 正确传递 task.error
- [ ] 前端：显示错误信息给用户

**涉及文件**：
- `backend/core/task_store.py` - 存储错误信息
- `backend/services/triggers/service.py` - 捕获并保存错误
- `sdk/src/client.ts` - 传递错误信息
- `sdk/src/types.ts` - 类型定义

### Phase 2: 飞书消息通知（短期）

**目标**：任务完成后发送消息通知用户

**实现方式**：
```python
# 任务完成时调用
await message_client.send_text(
    user_id=open_id,
    text=f"您的{mode}任务已完成，点击查看结果：{child_doc_url}"
)
```

**注意事项**：
- 需要开启应用的机器人能力
- 需要权限：`im:message:send_as_bot`
- 频率限制：5 QPS/用户

**涉及文件**：
- `backend/services/feishu/message.py` - 发送消息
- `backend/services/outputs/feishu_child_doc.py` - 完成时触发通知

### Phase 3: SDK 缓存助手（短期）

**目标**：SDK 提供可选的本地缓存工具

**API 设计**：
```typescript
class FeishuAIDocSDK {
  // 缓存助手
  public cache = {
    save: (key: string, taskId: string) => void,
    get: (key: string) => string | null,
    clear: (key: string) => void,
  };
  
  // 便捷方法（基于 docToken）
  public saveCurrentTask(taskId: string): void;
  public getLastTask(): Promise<TaskStatusResponse | null>;
  public clearLastTask(): void;
}
```

**涉及文件**：
- `sdk/src/client.ts` - 添加缓存方法

### Phase 4: 后端任务关联（中期）

**目标**：任务存储支持按 docToken/userId 查询

**数据结构扩展**：
```python
class Task:
    task_id: str
    user_id: str
    doc_token: str | None  # 新增
    # ...
```

**新增接口**：
- `GET /addon/tasks/by-doc?doc_token=xxx` - 查询文档相关任务
- `GET /addon/tasks/by-user?user_id=xxx` - 查询用户任务列表

**涉及文件**：
- `backend/core/task_store.py` - 扩展存储
- `backend/api/routes.py` - 新增接口

---

## 4. 飞书消息通知详细设计

### 4.1 权限配置

1. 在飞书开放平台开启应用的"机器人"能力
2. 申请权限：
   - `im:message:send_as_bot`（以应用身份发送消息）
   - `im:message`（获取与发送消息）

### 4.2 发送接口

```
POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id

Headers:
  Authorization: Bearer {tenant_access_token}
  Content-Type: application/json

Body:
{
  "receive_id": "用户的open_id",
  "content": "{\"text\":\"您的云文档任务已完成\"}",
  "msg_type": "text"
}
```

### 4.3 消息内容（初期简单版）

```
您的「深度调研」任务已完成 ✅
点击查看结果：{child_doc_url}
```

### 4.4 消息内容（后续卡片版）

```json
{
  "msg_type": "interactive",
  "content": {
    "config": { "wide_screen_mode": true },
    "header": {
      "title": { "tag": "plain_text", "content": "任务完成通知" },
      "template": "green"
    },
    "elements": [
      {
        "tag": "div",
        "text": { "tag": "plain_text", "content": "您的「深度调研」任务已完成" }
      },
      {
        "tag": "action",
        "actions": [{
          "tag": "button",
          "text": { "tag": "plain_text", "content": "查看结果" },
          "type": "primary",
          "url": "{child_doc_url}"
        }]
      }
    ]
  }
}
```

### 4.5 错误处理

| 错误码 | 含义 | 处理方式 |
|--------|------|----------|
| 230013 | 用户不在应用可用范围 | 记录日志，不重试 |
| 230006 | 未开启机器人能力 | 检查应用配置 |
| 99991663 | 消息频率限制 | 等待后重试 |

---

## 5. 讨论点

### 已确定
- [x] Task 是全局概念，不强制绑定文档
- [x] SDK 提供缓存工具，但不强制使用
- [x] 消息通知初期简单实现（文本 + 链接）

### 待讨论
- [ ] 任务过期时间：LocalStorage 缓存多久清理？
- [ ] 多任务场景：同一文档连续触发多个任务怎么处理？
- [ ] 卡片消息：后续是否需要更丰富的消息格式？

---

## 6. 后端状态分析（代码审查结果）

### 6.1 Task 通用性 ✅

Task 机制对所有 mode（idea_expand / research / 未来任何 mode）**完全通用**：

```python
# TriggerService.trigger() - 接受任意 mode
task_id = await self._tasks.create_task(context=asdict(ctx), ...)

# ProcessManager.process_doc() - 根据 mode 选择不同的 workflow
workflow = self._registry.get(ctx.mode)  # 通用分发
```

### 6.2 现有进度阶段 ✅

从 `manager.py` 看，进度更新已经比较完善：

| 阶段 | 百分比 | 描述 |
|------|--------|------|
| accepted | 0% | 任务已创建 |
| queued | 0% | 任务已进入队列 |
| started | 1% | 开始处理 |
| fetch_meta | 5% | 获取文档元信息 |
| fetch_content | 15% | 读取文档内容 |
| llm | 35% | 调用模型生成内容 |
| output | 80% | 输出落地 |
| done | 100% | 处理完成 |

### 6.3 发现的问题 ⚠️

#### 问题 1: 错误信息不够详细

```python
# service.py 第 57 行
await self._tasks.fail(task_id, str(exc))  # 只是 str(exc)
```

对于 `NonRetryableLLMError: 403 无权访问...`，前端只能看到字符串，没有：
- 错误类型（LLMError / FeishuAPIError / ...）
- 错误码
- 修复建议

#### 问题 2: context 信息没有暴露给 API

```python
# task_store.py - 存储了 context
self._tasks[task_id] = {
    "context": context,  # 包含 mode, doc_token, user_id
    ...
}

# routes.py - 返回时没有包含 context
return TaskStatusResponse(
    task_id=task_id,
    status=task["status"],
    # ❌ 缺少 mode / doc_token / user_id
)
```

前端不知道：
- 这个任务是什么类型（idea_expand / research）
- 这个任务属于哪个文档
- 这个任务是谁触发的

### 6.4 建议补充的字段

#### API 响应补充：

```typescript
interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  
  // 新增：任务元信息（从 context 提取）
  mode?: string;           // idea_expand / research
  doc_token?: string;      // 关联的文档
  user_id?: string;        // 触发用户
  
  // 现有字段
  progress?: { stage, percent, message };
  result?: { child_doc_token, child_doc_url, ... };
  error?: string;          // 建议结构化
  
  created_at: number;
  updated_at?: number;
}
```

#### 错误信息结构化：

```typescript
interface TaskError {
  type: string;        // "LLMError" / "FeishuAPIError" / ...
  message: string;     // 错误描述
  code?: string;       // 错误码
  suggestion?: string; // 修复建议
}
```

---

## 7. 优先级排序

### P0 - 立即（影响核心体验）

1. **错误信息传递**
   - 后端：结构化错误存储
   - API：返回详细错误信息
   - SDK：传递错误给前端

2. **飞书消息通知**
   - 任务完成发送消息
   - 包含结果链接

### P1 - 短期（提升体验）

3. **API 返回任务元信息**
   - 返回 mode / doc_token / user_id
   - 前端可以显示任务类型

4. **SDK 缓存助手**
   - 本地缓存 taskId
   - 支持恢复上次任务

### P2 - 中期（完善功能）

5. **后端任务关联查询**
   - 按 docToken 查询
   - 按 userId 查询

6. **任务列表/历史**
   - 用户查看历史任务
   - 任务取消功能
