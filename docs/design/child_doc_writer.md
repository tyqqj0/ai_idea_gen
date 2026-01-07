# 交互模式 1：写子文档

## 1. 概述

"写子文档"是 AI 小工具体系的**核心输出能力**，提供通用的文档保存服务：

- **输入**：文本内容 + 原始文档位置 + 用户ID
- **输出**：自动判断场景（知识库/云盘）→ 创建文档 → 写入内容 → 授予权限 → 返回链接

## 2. 为什么需要"写子文档"

### 2.1 问题背景

在飞书生态中，保存 AI 生成的内容是一个复杂操作：

| 步骤 | 知识库场景 | 云盘场景 |
|------|-----------|---------|
| 判断场景 | 检测 wiki_node_token | 检测 folder_token 或退化 |
| 创建容器 | 创建子节点 | 创建文件夹（需去重） |
| 创建文档 | 创建 docx 文档 | 创建 docx 文档 |
| 写入内容 | Markdown → blocks → 写入 | 同左 |
| 添加权限 | wiki + node_token | folder + docx |
| 回链原文档 | 可选 | 可选 |

每个小工具（思路扩展、调研分析、图片理解...）都需要这套逻辑，**重复实现没有意义**。

### 2.2 解决方案

抽象成**通用能力**：

```
┌──────────────────────────────────────────────┐
│              各种小工具（处理层）              │
│  idea_expand / research / image_understand   │
│  输出：Markdown 文本                          │
└──────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│            写子文档（输出层）                  │
│  输入：Markdown + source_token + user_id      │
│  输出：新文档链接 + 元信息                     │
└──────────────────────────────────────────────┘
```

## 3. 接口设计

### 3.1 内部接口（Python）

```python
@dataclass
class WriteChildDocRequest:
    """写子文档请求"""
    content: str                    # 要写入的内容（Markdown）
    source_token: str               # 原始文档 token
    user_id: str                    # 用户 open_id
    
    # 可选参数
    title: str | None = None        # 文档标题（不传则自动生成）
    wiki_space_id: str | None = None   # 知识库空间 ID（如有）
    wiki_node_token: str | None = None # 知识库节点 token（如有）
    
    # 高级选项
    backlink: bool = True           # 是否回链到原文档
    grant_permission: bool = True   # 是否授予用户权限


@dataclass
class WriteChildDocResult:
    """写子文档结果"""
    success: bool
    
    # 新文档信息
    child_doc_token: str
    child_doc_url: str
    title: str
    
    # 容器信息（文件夹或知识库节点）
    container_token: str
    container_url: str
    container_name: str
    container_type: str  # 'folder' | 'wiki_node'
    
    # 状态信息
    permission_granted: bool
    permission_errors: list[str]
    backlink_success: bool
    backlink_error: str | None
    
    # 来源信息
    source_doc_token: str
    source_doc_url: str


class ChildDocWriter:
    """写子文档服务"""
    
    async def write(self, request: WriteChildDocRequest) -> WriteChildDocResult:
        """
        核心方法：根据请求自动完成子文档创建
        
        流程：
        1. 判断场景（知识库 or 云盘）
        2. 创建/复用容器
        3. 创建新文档
        4. 写入内容
        5. 授予权限
        6. 回链原文档（可选）
        7. 返回结果
        """
        pass
```

### 3.2 外部接口（REST API，未来可选）

如需直接暴露为 API：

```
POST /api/addon/save

Request:
{
  "content": "# 文档标题\n\n这是内容...",
  "source_token": "NrcPdK7WoolxxxxxxxxxVGTc0b",
  "title": "自定义标题（可选）",
  "wiki_space_id": "7xxx（可选）",
  "wiki_node_token": "wikcnxxx（可选）"
}

Response:
{
  "success": true,
  "child_doc_token": "Abc123xxx",
  "child_doc_url": "https://xxx.feishu.cn/docx/Abc123xxx",
  "title": "自动生成的标题",
  "container_token": "fldcnxxx",
  "container_url": "https://xxx.feishu.cn/drive/folder/fldcnxxx",
  "container_name": "原文档标题",
  "container_type": "folder",
  "permission_granted": true,
  "backlink_success": true
}
```

## 4. 场景判断逻辑

```
                     ┌───────────────────┐
                     │ 有 wiki_node_token │
                     │ 和 wiki_space_id？ │
                     └─────────┬─────────┘
                               │
              ┌────── YES ─────┴───── NO ──────┐
              ↓                                ↓
    ┌─────────────────┐              ┌─────────────────┐
    │   知识库场景     │              │   云盘场景       │
    │                 │              │                 │
    │ 1. 创建子节点    │              │ 1. 获取父文件夹   │
    │ 2. 创建 docx    │              │ 2. 查询同名文件夹 │
    │ 3. 写入内容     │              │ 3. 创建/复用文件夹│
    │ 4. 添加权限     │              │ 4. 创建 docx     │
    │    (wiki)      │              │ 5. 写入内容      │
    │                 │              │ 6. 添加权限      │
    │                 │              │    (folder+docx) │
    └─────────────────┘              └─────────────────┘
```

## 5. 详细流程

### 5.1 知识库场景

```python
async def _write_to_wiki(self, req: WriteChildDocRequest) -> WriteChildDocResult:
    # 1. 创建子节点
    child_node = await feishu.wiki.create_child_node(
        space_id=req.wiki_space_id,
        parent_node_token=req.wiki_node_token,
        title=req.title or await self._generate_title(req.content),
    )
    
    # 2. 获取关联的 docx token
    child_doc_token = child_node.obj_token
    
    # 3. 写入内容
    await feishu.doc.write_markdown(
        document_id=child_doc_token,
        markdown=req.content,
    )
    
    # 4. 添加权限（用 node_token）
    if req.grant_permission:
        await feishu.drive.add_permission(
            token=child_node.node_token,  # 用 node_token!
            file_type="wiki",
            member_id=req.user_id,
            perm="edit",
            perm_type="container",
        )
    
    # 5. 回链原文档（可选）
    if req.backlink:
        await self._add_backlink(...)
    
    return WriteChildDocResult(...)
```

### 5.2 云盘场景

```python
async def _write_to_drive(self, req: WriteChildDocRequest) -> WriteChildDocResult:
    # 1. 获取原文档所在文件夹
    doc_meta = await feishu.drive.batch_get_meta([req.source_token])
    parent_folder = doc_meta.parent_token
    source_title = doc_meta.title
    
    # 2. 查询是否已有同名文件夹
    existing = await feishu.drive.list_files(
        folder_token=parent_folder,
        type_filter="folder",
    )
    folder_token = None
    for item in existing:
        if item.name == source_title:
            folder_token = item.token
            break
    
    # 3. 创建/复用文件夹
    if not folder_token:
        folder_token = await feishu.drive.create_folder(
            name=source_title,
            parent_token=parent_folder,
        )
    
    # 4. 创建 docx 文档
    doc_title = req.title or await self._generate_title(req.content)
    child_doc_token = await feishu.drive.create_file(
        name=doc_title,
        folder_token=folder_token,
        type="docx",
    )
    
    # 5. 写入内容
    await feishu.doc.write_markdown(
        document_id=child_doc_token,
        markdown=req.content,
    )
    
    # 6. 添加权限
    if req.grant_permission:
        # 文件夹权限
        await feishu.drive.add_permission(
            token=folder_token,
            file_type="folder",
            member_id=req.user_id,
            perm="view",
        )
        # 文档权限
        await feishu.drive.add_permission(
            token=child_doc_token,
            file_type="docx",
            member_id=req.user_id,
            perm="view",
        )
    
    # 7. 回链原文档（可选）
    if req.backlink:
        await self._add_backlink(...)
    
    return WriteChildDocResult(...)
```

## 6. 自动标题生成

如果调用方未指定标题，自动生成：

```python
async def _generate_title(self, content: str) -> str:
    """
    调用轻量 LLM 生成语义化标题
    
    输入：文档内容（截取前 1000 字）
    输出：简洁标题（10-20 字）
    """
    prompt = f"""根据以下内容生成一个简洁的中文标题（10-20字）：

{content[:1000]}

标题："""
    
    title = await llm.generate(prompt, model="gpt-4o-mini")
    return title.strip()
```

## 7. 错误处理

### 7.1 设计原则

- **非阻断**：权限添加失败、回链失败不影响主流程
- **全量返回**：所有状态都返回给调用方
- **详细日志**：便于问题排查

### 7.2 错误码处理

| 错误码 | 含义 | 处理方式 |
|--------|------|---------|
| 1062505 | 文件夹名称重复 | 忽略，说明已存在 |
| 1063001 | 权限参数错误 | 记录错误，继续 |
| 1770032 | 回链权限不足 | 记录错误，继续 |

### 7.3 返回结果示例

```python
WriteChildDocResult(
    success=True,
    child_doc_token="Abc123",
    child_doc_url="https://xxx.feishu.cn/docx/Abc123",
    title="AI 生成的思路扩展",
    container_token="fldcn123",
    container_url="https://xxx.feishu.cn/drive/folder/fldcn123",
    container_name="原文档标题",
    container_type="folder",
    permission_granted=True,
    permission_errors=[],
    backlink_success=False,
    backlink_error="1770032: forbidden",
    source_doc_token="NrcPdK7Wool",
    source_doc_url="https://xxx.feishu.cn/docx/NrcPdK7Wool",
)
```

## 8. 使用示例

### 8.1 处理器调用

```python
class IdeaExpandProcessor:
    async def process(self, ctx: ProcessContext) -> None:
        # 1. 读取原文档
        content = await self.feishu.doc.read_content(ctx.token)
        
        # 2. AI 处理
        result = await self.llm.expand_idea(
            content=content,
            selected_text=ctx.selected_text,  # 用户划词文本
        )
        
        # 3. 调用写子文档服务
        write_result = await self.child_doc_writer.write(
            WriteChildDocRequest(
                content=result.markdown,
                source_token=ctx.token,
                user_id=ctx.user_id,
                title=result.title,
                wiki_space_id=ctx.wiki_space_id,
                wiki_node_token=ctx.wiki_node_token,
            )
        )
        
        # 4. 返回结果
        return ProcessResult(
            child_doc_token=write_result.child_doc_token,
            child_doc_url=write_result.child_doc_url,
            ...
        )
```

### 8.2 前端/SDK 调用

```typescript
// SDK 使用（前端调用）
const result = await client.process({
  token: docToken,
  mode: 'idea_expand',
  content: selectedText,  // 用户划词的文本
});

// 结果
console.log('新文档链接:', result.child_doc_url);
console.log('文件夹链接:', result.container_url);
```

## 9. 与整体架构的关系

```
┌────────────────────────────────────────────────────────────────┐
│                        前端 + SDK                              │
│  获取：doc_token, selected_text, user_code                     │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│                        API 层                                  │
│  /process - 调度处理器和输出器                                  │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│                      处理层                                    │
│  idea_expand / research / ...                                  │
│  输入：原始内容 + 划词文本                                      │
│  输出：Markdown                                                │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│                    输出层（本文档）                             │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              ChildDocWriter (写子文档)                    │ │
│  │  - 场景判断                                               │ │
│  │  - 容器创建/复用                                          │ │
│  │  - 文档创建                                               │ │
│  │  - 内容写入                                               │ │
│  │  - 权限授予                                               │ │
│  │  - 回链（可选）                                           │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

## 10. 重构计划

当前 `feishu_child_doc.py` 混合了处理逻辑和写入逻辑，建议重构：

### 10.1 当前结构

```
outputs/
  feishu_child_doc.py  # 混合：处理调度 + 写入逻辑
```

### 10.2 目标结构

```
outputs/
  child_doc_writer.py  # 纯写入逻辑（本文档描述的能力）

# 处理器层面调用 writer
processors/
  idea_expand.py
    → 调用 child_doc_writer.write()
```

这样每个处理器专注于自己的业务逻辑，写入部分统一委托给 `ChildDocWriter`。
