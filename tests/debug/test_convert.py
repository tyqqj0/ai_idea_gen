#!/usr/bin/env python3
"""
最小化脚本：直接调用飞书 convert 接口，验证返回的 blocks 结构和顺序
"""

import json
import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.llm_client import LLMClient
from backend.services.feishu import FeishuClient


async def main():
    """测试 convert 接口"""
    
    # 读取 test.md
    test_md_path = Path(__file__).parent / "test.md"
    with open(test_md_path, "r", encoding="utf-8") as f:
        content_md = f.read()
    
    print(f"📝 读取 test.md ({len(content_md)} 字符)")
    print("=" * 80)
    
    # 初始化 FeishuClient
    feishu_client = FeishuClient()
    
    # 调用 convert 接口
    print("\n🔄 调用 convert 接口...")
    try:
        blocks = await feishu_client.convert_markdown_to_blocks(content_md)
    except Exception as e:
        print(f"❌ convert 失败: {e}")
        return
    
    print(f"✅ convert 成功，返回 {len(blocks)} 个 blocks")
    print("=" * 80)
    
    # 打印每个 block 的完整结构（不含 content）
    print("\n📊 Block 结构详解：\n")
    for idx, blk in enumerate(blocks):
        print(f"[{idx}] Block #{idx}:")
        
        # 打印所有字段（除了那些含有大量文本的字段）
        for key, value in blk.items():
            if key in ["text", "heading1", "heading2", "heading3", "heading4", "heading5",
                       "heading6", "heading7", "heading8", "heading9", "bullet", "ordered",
                       "code", "quote", "table", "image", "file", "divider"]:
                # 这些字段通常包含 content，只打印字段名和类型
                if isinstance(value, dict):
                    print(f"  {key}: {type(value).__name__} with keys: {list(value.keys())}")
                else:
                    print(f"  {key}: {type(value).__name__}")
            else:
                # 其他字段完整打印
                if key in ["block_id", "block_type", "parent_id", "children"]:
                    print(f"  {key}: {value}")
                else:
                    print(f"  {key}: {value}")
        print()
    
    # 统计顶层块（不在任何 children 里的块）
    all_child_ids = set()
    for blk in blocks:
        if blk.get("children") and isinstance(blk["children"], list):
            all_child_ids.update(blk["children"])
    
    top_level_blocks = [
        blk for blk in blocks 
        if blk.get("block_id") and blk["block_id"] not in all_child_ids
    ]
    
    print("=" * 80)
    print(f"\n📈 统计信息：")
    print(f"  总 blocks 数: {len(blocks)}")
    print(f"  顶层块数: {len(top_level_blocks)}")
    print(f"  子块数: {len(all_child_ids)}")
    
    print(f"\n📋 顶层块顺序 (children_id 应该的顺序):")
    for idx, blk in enumerate(top_level_blocks):
        block_type = blk.get("block_type")
        block_id = blk.get("block_id")
        # 尝试获取块的内容摘要（第一个元素的内容）
        content_summary = "???"
        for key in ["text", "heading1", "heading2", "heading3", "heading4", "heading5",
                    "heading6", "heading7", "heading8", "heading9", "bullet", "ordered"]:
            if key in blk and isinstance(blk[key], dict):
                elements = blk[key].get("elements", [])
                if elements and isinstance(elements[0], dict):
                    text_run = elements[0].get("text_run", {})
                    if isinstance(text_run, dict):
                        content = text_run.get("content", "")
                        content_summary = content[:30] if content else "（空）"
                        break
        print(f"  [{idx}] type={block_type}, id={block_id}, content='{content_summary}'")
    
    # 检查是否有顺序信息
    print(f"\n🔍 检查顺序相关字段：")
    sample_block = blocks[0] if blocks else {}
    order_keys = ["index", "order", "position", "sequence", "sort", "rank", "weight"]
    found_order_keys = [k for k in order_keys if k in sample_block]
    if found_order_keys:
        print(f"  ✅ 找到顺序字段: {found_order_keys}")
    else:
        print(f"  ❌ 未找到顺序字段（index/order/position 等）")
        print(f"  块中的所有字段: {list(sample_block.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
