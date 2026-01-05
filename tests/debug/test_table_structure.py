#!/usr/bin/env python3
"""
调试表格块结构
"""
import asyncio
import sys
import json
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.services.feishu import FeishuClient


async def main():
    """查看表格块的详细结构"""
    
    # 简单的表格 Markdown
    table_md = """
| 列1 | 列2 |
|------|------|
| 值1 | 值2 |
| 值3 | 值4 |
"""
    
    feishu_client = FeishuClient()
    
    print("=" * 60)
    print("表格 Markdown:")
    print("=" * 60)
    print(table_md)
    
    # 调用 convert
    result = await feishu_client.convert_markdown_to_blocks(table_md)
    blocks = result["blocks"]
    first_level_block_ids = result["first_level_block_ids"]
    
    print(f"\n转换后:")
    print(f"  blocks 数量: {len(blocks)}")
    print(f"  first_level_blocks 数量: {len(first_level_block_ids)}")
    print(f"\nfirst_level_block_ids:")
    for i, bid in enumerate(first_level_block_ids):
        print(f"  [{i}] {bid}")
    
    print(f"\n所有 blocks 详细信息:")
    print("=" * 60)
    for i, blk in enumerate(blocks):
        block_id = blk.get("block_id")
        block_type = blk.get("block_type")
        parent_id = blk.get("parent_id")
        children = blk.get("children", [])
        
        print(f"\n[{i}] block_id: {block_id}")
        print(f"    block_type: {block_type}")
        print(f"    parent_id: {parent_id}")
        print(f"    children: {len(children)} items")
        
        # 检查是否有 merge_info
        if "merge_info" in blk:
            print(f"    ⚠️ HAS merge_info at block level")
        
        # 检查嵌套字段中的 merge_info
        for key in ["table", "table_row", "table_cell"]:
            if key in blk and isinstance(blk[key], dict):
                if "merge_info" in blk[key]:
                    print(f"    ⚠️ HAS merge_info in blk['{key}']")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
