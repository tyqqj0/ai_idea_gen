"""
隔离测试：飞书 Markdown → Blocks 转换 API

目的：测试 dr_example.md 类型的 research 输出内容在转换时的行为
- 是转换失败？
- 还是 blocks 数量过多？
- 还是 <think> 标签导致的问题？
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from backend.services.feishu import FeishuClient, FeishuAPIError

# 测试用的 Markdown 内容路径
DR_EXAMPLE_PATH = Path(__file__).parent / "dr_example.md"


async def test_convert_full_content():
    """测试 1：完整内容转换"""
    print("\n" + "=" * 60)
    print("测试 1：完整 dr_example.md 内容转换")
    print("=" * 60)
    
    if not DR_EXAMPLE_PATH.exists():
        # 尝试从 tests 目录读取
        alt_path = Path(__file__).resolve().parents[1] / "dr_example.md"
        if alt_path.exists():
            content = alt_path.read_text(encoding="utf-8")
        else:
            print(f"❌ 找不到测试文件: {DR_EXAMPLE_PATH}")
            return None
    else:
        content = DR_EXAMPLE_PATH.read_text(encoding="utf-8")
    
    print(f"📄 内容长度: {len(content)} 字符")
    print(f"📄 行数: {len(content.splitlines())} 行")
    
    feishu = FeishuClient()
    
    try:
        result = await feishu.doc.convert_markdown_to_blocks(content)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        
        print(f"✅ 转换成功!")
        print(f"   - blocks 数量: {len(blocks)}")
        print(f"   - 顶层 blocks 数量: {len(first_level_ids)}")
        
        # 分析 block 类型分布
        block_types = {}
        for blk in blocks:
            bt = blk.get("block_type", "unknown")
            block_types[bt] = block_types.get(bt, 0) + 1
        print(f"   - block 类型分布: {block_types}")
        
        return {"success": True, "blocks_count": len(blocks), "first_level": len(first_level_ids)}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}


async def test_convert_without_think_tags():
    """测试 2：去掉 <think> 标签后的内容"""
    print("\n" + "=" * 60)
    print("测试 2：去掉 <think>...</think> 标签后的内容")
    print("=" * 60)
    
    # 读取文件
    alt_path = Path(__file__).resolve().parents[1] / "dr_example.md"
    if alt_path.exists():
        content = alt_path.read_text(encoding="utf-8")
    else:
        print(f"❌ 找不到测试文件")
        return None
    
    # 去掉 <think>...</think> 部分
    import re
    content_cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content_cleaned = content_cleaned.strip()
    
    print(f"📄 原始内容长度: {len(content)} 字符")
    print(f"📄 清理后内容长度: {len(content_cleaned)} 字符")
    print(f"📄 移除了: {len(content) - len(content_cleaned)} 字符")
    
    feishu = FeishuClient()
    
    try:
        result = await feishu.doc.convert_markdown_to_blocks(content_cleaned)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        
        print(f"✅ 转换成功!")
        print(f"   - blocks 数量: {len(blocks)}")
        print(f"   - 顶层 blocks 数量: {len(first_level_ids)}")
        
        return {"success": True, "blocks_count": len(blocks), "first_level": len(first_level_ids)}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}


async def test_convert_simple_markdown():
    """测试 3：简单 Markdown 内容（基准测试）"""
    print("\n" + "=" * 60)
    print("测试 3：简单 Markdown 内容（基准测试）")
    print("=" * 60)
    
    simple_md = """
# 测试标题

这是一段简单的文本。

## 二级标题

- 列表项 1
- 列表项 2

| 表头1 | 表头2 |
|-------|-------|
| 数据1 | 数据2 |

[链接文字](https://example.com)

```python
print("Hello World")
```
"""
    
    print(f"📄 内容长度: {len(simple_md)} 字符")
    
    feishu = FeishuClient()
    
    try:
        result = await feishu.doc.convert_markdown_to_blocks(simple_md)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        
        print(f"✅ 转换成功!")
        print(f"   - blocks 数量: {len(blocks)}")
        print(f"   - 顶层 blocks 数量: {len(first_level_ids)}")
        
        return {"success": True, "blocks_count": len(blocks), "first_level": len(first_level_ids)}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        return {"success": False, "error": str(e)}


async def test_convert_only_think_content():
    """测试 4：只测试 <think> 标签内的内容"""
    print("\n" + "=" * 60)
    print("测试 4：只测试 <think>...</think> 内的内容")
    print("=" * 60)
    
    # 读取文件
    alt_path = Path(__file__).resolve().parents[1] / "dr_example.md"
    if alt_path.exists():
        content = alt_path.read_text(encoding="utf-8")
    else:
        print(f"❌ 找不到测试文件")
        return None
    
    # 提取 <think>...</think> 部分（不包含标签本身）
    import re
    match = re.search(r"<think>(.*?)</think>", content, flags=re.DOTALL)
    if not match:
        print("❌ 未找到 <think> 标签")
        return None
    
    think_content = match.group(1).strip()
    print(f"📄 <think> 内容长度: {len(think_content)} 字符")
    print(f"📄 行数: {len(think_content.splitlines())} 行")
    
    feishu = FeishuClient()
    
    try:
        result = await feishu.doc.convert_markdown_to_blocks(think_content)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        
        print(f"✅ 转换成功!")
        print(f"   - blocks 数量: {len(blocks)}")
        print(f"   - 顶层 blocks 数量: {len(first_level_ids)}")
        
        return {"success": True, "blocks_count": len(blocks), "first_level": len(first_level_ids)}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        return {"success": False, "error": str(e)}


async def test_convert_with_think_tags_as_text():
    """测试 5：保留 <think> 标签但作为普通文本"""
    print("\n" + "=" * 60)
    print("测试 5：<think> 标签作为普通文本（转义或代码块）")
    print("=" * 60)
    
    # 读取文件
    alt_path = Path(__file__).resolve().parents[1] / "dr_example.md"
    if alt_path.exists():
        content = alt_path.read_text(encoding="utf-8")
    else:
        print(f"❌ 找不到测试文件")
        return None
    
    # 把 <think> 和 </think> 替换为转义版本或其他形式
    content_escaped = content.replace("<think>", "【思考过程开始】\n")
    content_escaped = content_escaped.replace("</think>", "\n【思考过程结束】")
    
    print(f"📄 转义后内容长度: {len(content_escaped)} 字符")
    
    feishu = FeishuClient()
    
    try:
        result = await feishu.doc.convert_markdown_to_blocks(content_escaped)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        
        print(f"✅ 转换成功!")
        print(f"   - blocks 数量: {len(blocks)}")
        print(f"   - 顶层 blocks 数量: {len(first_level_ids)}")
        
        if len(blocks) > 1000:
            print(f"⚠️  blocks 数量超过 1000，会触发降级!")
        
        return {"success": True, "blocks_count": len(blocks), "first_level": len(first_level_ids)}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        return {"success": False, "error": str(e)}


async def main():
    print("🔍 飞书 Markdown → Blocks 转换测试")
    print("目的：定位 research 模式内容写入降级的原因")
    
    results = {}
    
    # 测试 3：基准测试（简单内容）
    results["simple"] = await test_convert_simple_markdown()
    
    # 测试 1：完整内容
    results["full"] = await test_convert_full_content()
    
    # 测试 2：去掉 think 标签
    results["no_think"] = await test_convert_without_think_tags()
    
    # 测试 4：只测试 think 内容
    results["only_think"] = await test_convert_only_think_content()
    
    # 测试 5：think 标签转义
    results["think_escaped"] = await test_convert_with_think_tags_as_text()
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for name, result in results.items():
        if result is None:
            print(f"  {name}: ⏭️ 跳过")
        elif result.get("success"):
            blocks = result.get("blocks_count", 0)
            status = "⚠️ 超限" if blocks > 1000 else "✅"
            print(f"  {name}: {status} blocks={blocks}")
        else:
            print(f"  {name}: ❌ 失败 - {result.get('error', 'unknown')[:50]}...")
    
    print("\n💡 分析结论：")
    
    # 分析
    if results.get("simple", {}).get("success") and not results.get("full", {}).get("success"):
        print("   → 完整内容导致转换失败，问题在内容本身")
        
        if results.get("no_think", {}).get("success"):
            print("   → 去掉 <think> 后成功，问题定位：<think> 标签导致转换失败")
        elif results.get("only_think", {}).get("success"):
            print("   → <think> 内容本身可以转换，问题可能在标签语法")
    
    elif results.get("full", {}).get("success"):
        blocks = results["full"].get("blocks_count", 0)
        if blocks > 1000:
            print(f"   → 转换成功但 blocks={blocks} 超过 1000，触发降级逻辑")
        else:
            print(f"   → 转换成功且 blocks={blocks} 未超限，需要进一步检查写入逻辑")


if __name__ == "__main__":
    asyncio.run(main())
