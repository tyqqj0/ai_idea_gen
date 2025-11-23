# 飞书 AI 统一流程实施方案

## 1. 目标与范围
- 打通飞书文档与 AI 处理的主链路：读取原文、选择处理模式、生成子文档、插入引用、通知用户。
- 近期优先完成“非回调路径”（用户在插件中点按触发），回调/订阅等交互等飞书控制台配置完成后再推进。
- 保证架构层面可扩展：Processor 易于新增、LLM provider 可配置、流程可观测。

## 2. 近期优先级（按顺序执行）
1. **Feishu 接入层**（当前重点）：实现 Token 缓存、文档 CRUD、块写入/插入、卡片消息封装。
2. **LLM 配置与 Fallback**：完善 `llm_config.yml` + `.env` 的组合，构建多 provider fallback、链路配置与 Guardrail 钩子。
3. **Processor & ProcessManager 骨架**：完成处理模式注册表、Processor 运行模板、`ProcessManager.process_doc` 主流程、`TaskStore`（内存即可）。

> 回调路由 (`/feishu/event`, `/feishu/card_callback`) 暂缓，待飞书控制台配置敲定后再实现。当前仅聚焦 `/addon/process` 直触发。

## 3. 详细实施事项

### 3.1 Feishu 接入层
- `FeishuClient`
  - `get_tenant_access_token()`：内存缓存 + TTL，失败重试。
  - 文档接口：`get_document_raw`, `create_child_doc`, `append_blocks`, `insert_link_block`。
  - 消息接口：`send_card(user_id, card_content)`，用于初版通知。
  - 统一异常：转换为 `FeishuAPIError(code, detail)`，供上层识别。
- `LinkInjector`：封装“在原文末尾插入引用块”的逻辑，避免各 processor 重复实现。
- 记录 `request_id`, `doc_token`, `user_id`，便于日志追踪。

### 3.2 LLM 层与配置
- `.env` 维护密钥，`llm_config.yml` 只记录 `env_key`, `model`, `base_url`, `chain`。
- `LLMClient`
  - `build_provider` 支持 `openai-compatible` / `doubao` / 其他 HTTP Endpoint。
  - Chain 配置：每个 chain 定义 `providers`（按顺序 fallback）、`temperature`, `max_tokens`。
  - Guardrail Hooks：`pre_send(messages, ctx)`、`post_receive(output, ctx)`，先用空实现，方便后续扩展安全策略。

### 3.3 Processor & 流程编排
- `WorkflowRegistry`
  - 结构：`{"idea_expand": WorkflowConfig(processor="IdeaExpanderProcessor", chain="idea_chain", notify=True)}`。
  - 支持通过配置扩展，`ProcessManager` 查表选择 `processor_cls` 与 LLM chain。
- `BaseDocProcessor`
  - 方法：`prepare(ctx)`, `run(prepared, llm_client, chain)`, `post_process(result, ctx)`。
  - 统一 `ProcessResult`（`title`, `content_md`, `summary`, `metadata`）。
- 初始实现：
  - `IdeaExpanderProcessor`: 生成扩展提案列表。
  - `ResearchDigestProcessor`: 结构化总结 +行动项。
  - `MeetingSummaryProcessor`: 对后续扩展提供模板（可 stub）。
- `ProcessManager.process_doc`
  1. 获取 `WorkflowConfig`。
  2. 调用 `FeishuClient` 拉取原文内容 + 元数据。
  3. Processor 运行（含 LLM 调用）。
  4. 创建子文档、写入内容、插入引用。
  5. 发送卡片通知（如启用）。
  6. 更新 `TaskStore` 状态并返回结果。
- `TaskStore`（内存 Map）：`{task_id: {"status": "running|succeeded|failed", "result_doc": ...}}`，方便 `/addon/process` 立即返回 `task_id`。

### 3.4 可观测性与调试（当前阶段可部分实现）
- `AuditLogger`：统一 `log.info/event`，带 `trace_id`，Processor/Feishu/LLM 共用。
- 错误映射：`FeishuAPIError`、`LLMGenerationError`、`ProcessorError` 映射到用户提示。
- 手动触发链路测试：在 docs 目录记录 API 调用示例，便于 QA。

## 4. 下一阶段展望（待飞书回调配置完成）
- 回调路由实现（事件订阅、卡片按钮）。
- 幂等策略（事件 `event_id` 去重）。
- 更丰富的 Processor（翻译、润色、日报等）与多模型治理。
- TaskStore 替换为 Redis/DB，提供历史记录与并发控制。

---

> 备注：完成本文档后，立即启动 3.1–3.3 的实现；回调相关工作留待飞书控制台配置确认后再另行安排。

