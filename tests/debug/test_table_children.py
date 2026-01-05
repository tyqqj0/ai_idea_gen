#!/usr/bin/env python3
"""
调试表格 children 字段
"""
import asyncio
import sys
import json
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.services.feishu import FeishuClient


async def main():
    """查看表格的 children 结构"""
    
    table_md = """
| 列1 | 列2 |
|------|------|
| 值1 | 值2 |
"""
    
    feishu_client = FeishuClient()
    result = await feishu_client.convert_markdown_to_blocks(table_md)
    blocks = result["blocks"]
    first_level_block_ids = result["first_level_block_ids"]
    
    print("=" * 60)
    print("表格块的 children 结构:")
    print("=" * 60)
    
    # 找到表格容器块
    table_block = None
    for blk in blocks:
        if blk.get("block_id") in first_level_block_ids:
            table_block = blk
            break
    
    if table_block:
        print(f"\n表格容器块:")
        print(f"  block_id: {table_block.get('block_id')}")
        print(f"  block_type: {table_block.get('block_type')}")
        print(f"  children: {table_block.get('children', [])}")
        
        print(f"\n检查 children 中的 block_id 是否在 blocks 中:")
        all_block_ids = {b.get("block_id") for b in blocks}
        for child_id in table_block.get("children", []):
            exists = child_id in all_block_ids
            print(f"  - {child_id}: {'✅ 存在' if exists else '❌ 不存在'}")
        
        print(f"\n所有块的 block_id:")
        for i, blk in enumerate(blocks):
            bid = blk.get("block_id")
            btype = blk.get("block_type")
            is_top = "🔝" if bid in first_level_block_ids else "  "
            print(f"  {is_top} [{i}] {bid} (type={btype})")


if __name__ == "__main__":
    asyncio.run(main())
