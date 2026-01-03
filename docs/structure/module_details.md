# 核心模块详细说明

> 最后更新：2025-12-31

本文档详细说明各核心模块的实现细节、接口定义和使用方式。

---

## 📋 目录

- [1. LLM 客户端 (LLMClient)](#1-llm-客户端-llmclient)
- [2. 流程编排器 (ProcessManager)](#2-流程编排器-processmanager)
- [3. 处理器层 (Processors)](#3-处理器层-processors)
- [4. 输出层 (OutputHandlers)](#4-输出层-outputhandlers)
- [5. 飞书客户端 (FeishuClient)](#5-飞书客户端-feishuclient)
- [6. 工具层 (Utils)](#6-工具层-utils)
- [7. 任务存储 (TaskStore)](#7-任务存储-taskstore)

---

## 1. LLM 客户端 (LLMClient)

**文件位置**：`backend/core/llm_client.py`

### 1.1 核心职责

- 与 LLM API 进行通信
- 实现多 Provider Fallback 机制
- 管理超时和重试
- 统一错误处理

### 1.2 关键类和接口

#### LLMClient

```python
class LLMClient:
    async def chat_completion(
        self,
        *,
        chain: str,              # Chain 名称（如 "idea_expand"）
        messages: List[Dict],    # 消息列表
        **options: Any           # 额外选项（temperature 等）
    ) -> str:
        """
        统一的 LLM 调用接口
        
        Returns:
            生成的文本内容
            
        Raises:
            FallbackExhaustedError: 所有 Provider 都失败
            NonRetryableLLMError: 不可重试的错误
        """
```

### 1.3 配置结构

**文件**：`llm_config.yml`

```yaml
providers:
  provider_name:
    type: "openai-compatible"  # Provider 类型
    base_url: "https://..."    # API 基础 URL
    model: "model-name"        # 模型名称
    api_key_env: "ENV_VAR"     # 环境变量名

chains:
  chain_name:
    - provider: "provider_name"  # Provider 名称
      timeout_s: 60              # 超时时间（秒）

global:
  max_retries_per_provider: 1   # 每个 Provider 最大重试次数
  overall_timeout_s: 60         # 全局超时
```

### 1.4 Fallback 机制

**流程**：
```
1. 选择 Chain（如 "idea_expand"）
2. 遍历 Chain 中的 Provider 列表
3. 对每个 Provider：
   a. 尝试调用
   b. 成功 → 返回结果
   c. 可重试错误 → 继续下一个
   d. 不可重试错误 → 直接抛出
4. 所有 Provider 失败 → 抛出 FallbackExhaustedError
```

**错误分类**：
- **可重试**：网络错误、超时、5xx 错误
- **不可重试**：参数错误、认证失败、配额耗尽

### 1.5 使用示例

```python
llm_client = LLMClient()

# 调用 LLM
response = await llm_client.chat_completion(
    chain="idea_expand",
    messages=[
        {"role": "system", "content": "你是一个..."},
        {"role": "user", "content": "请..."}
    ],
    temperature=0.7
)
```

---

## 2. 流程编排器 (ProcessManager)

**文件位置**：`backend/core/manager.py`

### 2.1 核心职责

- 编排整个处理流程
- 选择合适的 Processor 和 OutputHandler
- 管理进度报告
- 异常处理和日志记录

### 2.2 关键类和接口

#### ProcessContext

```python
@dataclass
class ProcessContext:
    doc_token: str                  # 文档 token
    user_id: str                    # 用户 ID
    mode: str                       # 处理模式
    trigger_source: str | None      # 触发来源
    wiki_node_token: str | None     # Wiki 节点 token
    wiki_space_id: str | None       # Wiki 空间 ID
```

#### ProcessResult

```python
@dataclass
class ProcessResult:
    child_doc_token: Optional[str]       # 子文档 token
    child_doc_url: Optional[str]         # 子文档 URL
    processor_result: ProcessorResult    # 处理器结果
    output_result: OutputResult          # 输出结果
```

#### ProcessManager

```python
class ProcessManager:
    async def process_doc(
        self, 
        ctx: ProcessContext,
        *, 
        progress: ProgressFn | None = None
    ) -> ProcessResult:
        """
        主处理流程
        
        Args:
            ctx: 处理上下文
            progress: 进度回调函数
            
        Returns:
            处理结果
        """
```

### 2.3 处理流程

```python
# 详细流程
async def process_doc(ctx: ProcessContext):
    # 1. 获取 Workflow 配置
    workflow = registry.get(ctx.mode)
    
    # 2. 获取文档元信息
    await progress("fetch_meta", 5, "获取文档元信息")
    file_meta = await feishu.get_doc_meta(ctx.doc_token)
    
    # 3. 读取文档内容
    await progress("fetch_content", 15, "读取文档内容")
    doc_content = await feishu.get_doc_content(ctx.doc_token)
    
    # 4. 执行 Processor
    await progress("llm", 35, "调用模型生成内容")
    processor = workflow.processor_cls(llm_client)
    processor_result = await processor.run(
        doc_content=doc_content,
        doc_title=doc_title,
        chain=workflow.chain
    )
    
    # 5. 输出处理
    await progress("output", 80, "输出落地（写入/推送）")
    output_handler = workflow.output_factory(feishu, llm_client)
    output_result = await output_handler.handle(
        ctx=ctx,
        source_doc=SourceDoc(...),
        processor_result=processor_result
    )
    
    # 6. 返回结果
    await progress("done", 100, "处理完成")
    return ProcessResult(...)
```

### 2.4 进度报告

**进度回调签名**：
```python
ProgressFn = Callable[[str, int, str], Awaitable[None]]
# 参数：(stage, percent, message)
```

**标准进度阶段**：
- `fetch_meta` (5%): 获取文档元信息
- `fetch_content` (15%): 读取文档内容
- `llm` (35%): 调用模型生成内容
- `output` (80%): 输出落地
- `done` (100%): 处理完成

---

## 3. 处理器层 (Processors)

**目录位置**：`backend/services/processors/`

### 3.1 核心职责

- 根据不同模式处理文档内容
- 组装 LLM Prompt
- 调用 LLM 生成结果
- 返回标准化结果

### 3.2 抽象基类

#### BaseDocProcessor

```python
class BaseDocProcessor(ABC):
    def __init__(self, llm_client: LLMClientLike) -> None:
        self.llm_client = llm_client
    
    @abstractmethod
    async def run(
        self,
        *,
        doc_content: str,           # 文档内容
        doc_title: str,             # 文档标题
        chain: str,                 # LLM Chain 名称
        context: Dict[str, Any] | None = None  # 上下文信息
    ) -> ProcessorResult:
        """处理文档内容，返回标准化结果"""
```

#### ProcessorResult

```python
@dataclass
class ProcessorResult:
    title: str                          # 生成的标题
    content_md: str                     # 生成的内容（Markdown）
    summary: Optional[str] = None       # 摘要
    metadata: Optional[Dict] = None     # 元数据
```

### 3.3 具体实现

#### 3.3.1 IdeaExpanderProcessor（思路扩展）

**文件**：`processors/expander.py`

**特点**：
- 侧重发散性思维
- 生成 3-5 个延伸方向
- Prompt 强调"头脑风暴"、"列出可能性"

**Prompt 结构**：
```python
system_prompt = """
你是一个产品创意顾问，擅长基于已有文档提出多样化的延伸点子。
- 输出使用 Markdown，按"摘要 / 延伸方向 / 下一步行动"结构组织。
- 给出有区分度的要点，每条用序号或小标题。
- 保持客观、具体，可执行。
"""

user_prompt = f"""
当前文档标题：{doc_title}
文档正文：
{doc_content}

请基于内容生成 3-5 个延伸方向并补充对应的实施建议。
"""
```

**调用参数**：
- Chain: `idea_expand`
- Temperature: 0.7（允许创造性）

---

#### 3.3.2 ResearchProcessor（深度调研）

**文件**：`processors/researcher.py`

**特点**：
- 两阶段处理（Refine → Deep Research）
- 侧重深度和结构化
- 支持长时任务

**阶段 1: Refine（优化指令）**

```python
# Prompt
system_prompt = """
你是提示词优化器，负责把用户的需求转成可执行的"深度调研指令"。
要求：
- 输出简洁要点列表，覆盖：调研主题、核心问题、需验证的假设、关键信息源。
- 保持中立，避免臆测，必要时明确"不足/待确认"。
"""

user_prompt = f"""
原文标题：{doc_title}
原文内容：
{doc_content}

请生成一份"深度调研指令"，便于后续模型据此完成调研。
"""

# 调用参数
chain: "research_refine"
temperature: 0.3（更精确）
```

**阶段 2: Deep Research（深度调研）**

```python
# Prompt
system_prompt = """
你是深度研究助手，请基于给定的"调研指令"生成完整的调研报告（Markdown）。
输出结构建议：
- 背景与范围
- 核心发现（分点描述，可含引用或出处说明）
- 论证与证据（说明依据，标注可能的不确定性）
- 风险与待验证问题
- 建议行动（具体、可执行）
如信息不足，请明确哪些部分缺乏支撑，不要编造。
"""

user_prompt = f"""
调研指令：
{refined_prompt}

请直接输出 Markdown 调研报告。
"""

# 调用参数
chain: "research_deep"
temperature: 0.2（更严谨）
timeout: 2500s（长时任务）
```

**进度报告**：
```python
await progress("llm_refine", 45, "优化调研指令")
# ... refine 阶段 ...
await progress("llm_research", 70, "深度调研中，可能耗时较长")
# ... deep research 阶段 ...
await progress("llm_done", 90, "调研结果已生成")
```

### 3.4 扩展新 Processor

**步骤**：

1. **创建新类**：
```python
# backend/services/processors/my_processor.py
from backend.services.processors.base import BaseDocProcessor, ProcessorResult

class MyProcessor(BaseDocProcessor):
    async def run(self, *, doc_content, doc_title, chain, context=None):
        # 1. 组装 Prompt
        system_prompt = "..."
        user_prompt = f"..."
        
        # 2. 调用 LLM
        result = await self.llm_client.chat_completion(
            chain=chain,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        # 3. 返回结果
        return ProcessorResult(
            title=f"{doc_title} - 我的处理",
            content_md=result,
            summary="处理完成",
            metadata={"mode": "my_mode"}
        )
```

2. **注册到 Registry**：
```python
# backend/services/processors/registry.py
from backend.services.processors.my_processor import MyProcessor

PROCESSOR_REGISTRY = {
    "idea_expander": IdeaExpanderProcessor,
    "research": ResearchProcessor,
    "my_processor": MyProcessor,  # 新增
}
```

3. **配置 Workflow**：
```yaml
# workflow_config.yml
workflows:
  my_mode:
    processor: "my_processor"
    chain: "my_chain"
    output: "feishu_child_doc"
    notify_user: true
```

4. **配置 LLM Chain**：
```yaml
# llm_config.yml
chains:
  my_chain:
    - provider: "primary_gemini"
      timeout_s: 60
```

---

## 4. 输出层 (OutputHandlers)

**目录位置**：`backend/services/outputs/`

### 4.1 核心职责

- 将处理结果输出到不同目标
- 创建子文档（飞书）
- 推送通知（Webhook、卡片消息）
- 回链原文档

### 4.2 抽象基类

#### BaseOutputHandler

```python
class BaseOutputHandler(ABC):
    @abstractmethod
    async def handle(
        self,
        *,
        ctx: ProcessContext,                # 处理上下文
        source_doc: SourceDoc,              # 原文档信息
        processor_result: ProcessorResult,  # 处理器结果
        notify_user: bool = True            # 是否通知用户
    ) -> OutputResult:
        """处理输出"""
```

#### SourceDoc

```python
@dataclass
class SourceDoc:
    doc_token: str              # 文档 token
    title: str                  # 文档标题
    parent_token: Optional[str] # 父目录 token
```

#### OutputResult

```python
@dataclass
class OutputResult:
    child_doc_token: Optional[str]   # 子文档 token
    child_doc_url: Optional[str]     # 子文档 URL
    metadata: Optional[Dict] = None  # 元数据
```

### 4.3 具体实现

#### 4.3.1 FeishuChildDocOutputHandler

**文件**：`outputs/feishu_child_doc.py`

**核心功能**：

**1. 智能标题生成** 🆕
```python
# 检测"未命名"文档
title = processor_result.title
if "未命名" in title:
    # 调用 TitleGenerator
    title = await self._title_generator.generate_title(
        content_md=processor_result.content_md,
        mode=ctx.mode,
        original_doc_title=source_doc.title
    )
```

**2. 创建子文档（支持 Wiki）**
```python
if wiki_node_token:
    # === Wiki 知识库路径 ===
    child_node = await feishu.create_wiki_child_doc(
        space_id=wiki_space_id,
        parent_node_token=wiki_node_token,
        title=title
    )
    child_doc_token = child_node["obj_token"]
else:
    # === 云盘路径 ===
    child_doc_token = await feishu.create_child_doc(
        folder_token=parent_token,
        title=title
    )
```

**3. 写入内容**
```python
await feishu.write_doc_content(
    child_doc_token,
    processor_result.content_md
)
```

**4. 回链原文档**
```python
await feishu.append_reference_block(
    source_doc.doc_token,
    title,
    child_doc_url
)
```

**5. 发送通知卡片**
```python
if notify_user:
    card = self._build_notify_card(...)
    await feishu.send_card(
        user_id=ctx.user_id,
        card_content=card
    )
```

---

#### 4.3.2 WebhookOutputHandler

**文件**：`outputs/webhook.py`

**功能**：将结果推送到外部 Webhook

**Payload 结构**：
```json
{
  "mode": "idea_expand",
  "doc_token": "doccn...",
  "user_id": "ou_...",
  "title": "生成的标题",
  "content_md": "# 内容...",
  "summary": "摘要",
  "metadata": {...}
}
```

**配置**：
```env
WEBHOOK_OUTPUT_URL=https://example.com/webhook
WEBHOOK_OUTPUT_TIMEOUT_S=10.0
```

### 4.4 扩展新 OutputHandler

**步骤**：

1. **创建新类**：
```python
# backend/services/outputs/my_output.py
from backend.services.outputs.base import BaseOutputHandler, OutputResult

class MyOutputHandler(BaseOutputHandler):
    async def handle(self, *, ctx, source_doc, processor_result, notify_user):
        # 1. 处理输出逻辑
        # 例如：发送邮件、写入数据库等
        
        # 2. 返回结果
        return OutputResult(
            child_doc_token=None,  # 如果不创建文档
            child_doc_url=None,
            metadata={"output": "my_output"}
        )
```

2. **注册到 Registry**：
```python
# backend/services/outputs/registry.py
def _make_my_output(feishu: FeishuClient, llm: LLMClient):
    return MyOutputHandler(...)

OUTPUT_REGISTRY = {
    "feishu_child_doc": _make_feishu_child_doc_output,
    "webhook": _make_webhook_output,
    "my_output": _make_my_output,  # 新增
}
```

3. **配置 Workflow**：
```yaml
# workflow_config.yml
workflows:
  my_mode:
    processor: "idea_expander"
    chain: "idea_expand"
    output: "my_output"  # 使用新的输出
    notify_user: false
```

---

## 5. 飞书客户端 (FeishuClient)

**文件位置**：`backend/services/feishu.py`

### 5.1 核心职责

- Token 管理（获取、缓存、刷新）
- 文档操作（读、写、创建）
- Wiki 知识库操作
- 消息发送

### 5.2 关键接口

#### Token 管理

```python
async def get_tenant_access_token() -> str:
    """获取并缓存 tenant_access_token"""
```

**实现细节**：
- 内存缓存
- TTL 控制（提前 60 秒刷新）
- 线程安全（asyncio.Lock）

#### 文档操作

```python
# 获取文档元信息
async def get_doc_meta(doc_token: str) -> Dict[str, Any]:
    """返回: title, parent_token 等"""

# 获取文档内容
async def get_doc_content(doc_token: str) -> str:
    """返回纯文本内容"""

# 创建子文档
async def create_child_doc(folder_token: str, title: str) -> str:
    """返回: child_doc_token"""

# 写入文档内容
async def write_doc_content(doc_token: str, content_md: str) -> None:
    """Markdown → Blocks → 写入"""

# 添加引用块
async def append_reference_block(
    doc_token: str, 
    child_title: str, 
    child_url: str
) -> None:
    """在文档末尾添加链接"""
```

#### Wiki 操作

```python
# 获取 Wiki 节点信息
async def get_wiki_node_by_token(node_token: str) -> Dict[str, Any]:
    """返回: space_id, obj_token 等"""

# 创建 Wiki 子节点
async def create_wiki_child_doc(
    space_id: str,
    parent_node_token: str,
    title: str,
    obj_type: str = "docx"
) -> Dict[str, Any]:
    """返回: node_token, obj_token 等"""
```

#### 消息发送

```python
async def send_card(
    user_id: str,
    card_content: Dict[str, Any],
    receive_id_type: str = "open_id"
) -> None:
    """发送飞书卡片消息"""
```

### 5.3 容错机制

#### Markdown 写入多级回退

```python
async def write_doc_content(doc_token, content_md):
    # 1. 长度截断
    if len(content_md) > 60000:
        content_md = content_md[:60000] + "\n\n（内容已截断）"
    
    # 2. 优先：Markdown → Blocks
    try:
        blocks = await convert_markdown_to_blocks(content_md)
        if len(blocks) <= 1000:
            await add_blocks_descendant(doc_token, blocks)
            return
    except FeishuAPIError:
        pass  # 降级
    
    # 3. 回退：单个 markdown block
    markdown_block = {
        "block_type": "markdown",
        "markdown": {"content": content_md}
    }
    await add_blocks_descendant(doc_token, [markdown_block])
```

#### 重试机制

```python
async def _request_with_retry(method, path, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await self._request(method, path)
        except FeishuAPIError as exc:
            if exc.status_code == 404 and attempt < max_retries - 1:
                await asyncio.sleep(5.0)
                continue
            raise
```

---

## 6. 工具层 (Utils)

**目录位置**：`backend/services/utils/`

### 6.1 TitleGenerator（智能标题生成器）

**文件**：`utils/title_generator.py`

#### 核心功能

- 基于文档内容生成语义化标题
- 使用快速 LLM 模型（15秒内完成）
- 自动清理标题格式
- 失败时提供 fallback

#### 接口定义

```python
class TitleGenerator:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        chain: str = "title_generation",
        content_preview_length: int = 800,
        max_title_length: int = 30
    ):
        """初始化"""
    
    async def generate_title(
        self,
        *,
        content_md: str,                    # 文档内容
        mode: str,                          # 处理模式
        original_doc_title: str | None      # 原标题（参考）
    ) -> str:
        """
        生成标题
        
        Returns:
            生成的标题（失败时返回 fallback）
        """
```

#### 工作流程

```python
# 1. 提取内容预览
content_preview = content_md[:800]

# 2. 构造 Prompt
system_prompt = """
你是一个专业的标题生成助手。
要求：
- 标题长度不超过 30 个字符
- 直接体现文档的核心主题或价值
- 避免使用"未命名"、"文档"等通用词汇
"""

user_prompt = f"""
请为以下内容生成一个简洁的标题：
---
{content_preview}
---
"""

# 3. 调用 LLM
generated_title = await llm_client.chat_completion(
    chain="title_generation",
    messages=[...],
    temperature=0.7
)

# 4. 清理标题
title = clean_title(generated_title)
# - 移除引号
# - 只保留第一行
# - 限制长度

# 5. 返回结果
return title
```

#### 使用示例

```python
# 在 OutputHandler 中使用
title_generator = TitleGenerator(llm_client=llm_client)

if "未命名" in title:
    title = await title_generator.generate_title(
        content_md=processor_result.content_md,
        mode=ctx.mode,
        original_doc_title=source_doc.title
    )
```

---

## 7. 任务存储 (TaskStore)

**文件位置**：`backend/core/task_store.py`

### 7.1 核心职责

- 管理任务状态（内存实现）
- 提供任务查询
- 支持幂等控制
- 记录进度信息

### 7.2 数据结构

#### Task 结构

```python
{
    "status": "running" | "succeeded" | "failed",
    "created_at": float,           # 创建时间戳
    "updated_at": float | None,    # 更新时间戳
    "context": Dict[str, Any],     # 处理上下文
    "progress": {                  # 进度信息
        "stage": str,
        "percent": int,
        "message": str
    },
    "result": Dict[str, Any] | None,  # 成功结果
    "error": str | None                # 错误信息
}
```

### 7.3 关键接口

```python
class TaskStore:
    async def create_task(
        self, 
        *, 
        context: Dict[str, Any],
        idempotency_key: str | None = None
    ) -> str:
        """创建任务，返回 task_id"""
    
    async def update_progress(
        self,
        task_id: str,
        *,
        stage: str,
        percent: int | None = None,
        message: str | None = None
    ) -> None:
        """更新任务进度"""
    
    async def succeed(
        self, 
        task_id: str, 
        result: Dict[str, Any]
    ) -> None:
        """标记任务成功"""
    
    async def fail(
        self, 
        task_id: str, 
        error: str
    ) -> None:
        """标记任务失败"""
    
    async def get(
        self, 
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """查询任务状态"""
```

### 7.4 幂等控制

**实现**：
```python
# 内部维护 idempotency_key → task_id 映射
self._idempotency: Dict[str, str] = {}

async def create_task(self, *, context, idempotency_key):
    if idempotency_key:
        existing = self._idempotency.get(idempotency_key)
        if existing and existing in self._tasks:
            return existing  # 返回已存在的任务
    
    # 创建新任务
    task_id = uuid.uuid4().hex
    self._tasks[task_id] = {...}
    
    if idempotency_key:
        self._idempotency[idempotency_key] = task_id
    
    return task_id
```

**应用场景**：
- 飞书事件回调（使用 `event_id` 去重）
- 卡片按钮交互（使用 `request_id` 去重）

### 7.5 未来扩展

**当前限制**：
- 仅内存存储（重启丢失）
- 不支持分布式
- 无持久化

**升级方向**：
- **Redis**：支持分布式、持久化
- **数据库**：支持历史记录、统计分析

**Redis 实现示例**：
```python
class RedisTaskStore(TaskStore):
    async def create_task(self, *, context, idempotency_key):
        task_id = uuid.uuid4().hex
        await redis.setex(
            f"task:{task_id}",
            3600,  # TTL: 1 hour
            json.dumps({
                "status": "running",
                "context": context,
                ...
            })
        )
        return task_id
```

---

## 📚 参考资料

- [架构概览](architecture_overview.md)
- [飞书开放平台文档](https://open.feishu.cn/document/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Pydantic 文档](https://docs.pydantic.dev/)

---

> 📝 **维护说明**：本文档随项目更新，请保持同步更新
