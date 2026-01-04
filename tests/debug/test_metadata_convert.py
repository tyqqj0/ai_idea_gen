#!/usr/bin/env python3
"""
测试元数据 Markdown 转换
验证 build_metadata_section 生成的内容能否正确转换为飞书块
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.services.feishu import FeishuClient
from backend.services.utils.metadata_builder import build_metadata_section


async def main():
    """测试元数据转换"""
    
    # 1. 生成元数据内容
    metadata_md = build_metadata_section(
        mode="idea_expand",
        source_title="测试文档",
        source_url="https://feishu.cn/docx/test123",
        original_content="这是一段测试内容\n包含多行\n用于验证",
        trigger_source="manual_test",
        max_content_length=5000,
    )
    
    print("=" * 60)
    print("生成的元数据 Markdown:")
    print("=" * 60)
    print(metadata_md)
    print("=" * 60)
    print(f"\n元数据长度: {len(metadata_md)} 字符\n")
    
    # 2. 调用 convert 接口转换
    feishu_client = FeishuClient()
    
    try:
        print("正在调用 convert 接口...")
        result = await feishu_client.convert_markdown_to_blocks(metadata_md)
        
        blocks = result["blocks"]
        first_level_block_ids = result["first_level_block_ids"]
        
        print(f"✅ Convert 成功!")
        print(f"   blocks 数量: {len(blocks)}")
        print(f"   first_level_blocks 数量: {len(first_level_block_ids)}")
        print(f"\n前 5 个 first_level_block_ids:")
        for i, bid in enumerate(first_level_block_ids[:5]):
            print(f"   [{i}] {bid}")
        
        print(f"\n前 5 个 blocks 的 block_id:")
        for i, blk in enumerate(blocks[:5]):
            bid = blk.get("block_id")
            btype = blk.get("block_type")
            print(f"   [{i}] {bid} (type={btype})")
        
        # 3. 检查是否所有 first_level_block_ids 都在 blocks 中
        all_block_ids = {b.get("block_id") for b in blocks}
        missing = [bid for bid in first_level_block_ids if bid not in all_block_ids]
        
        if missing:
            print(f"\n⚠️ 警告: 有 {len(missing)} 个 first_level_block_ids 不在 blocks 中:")
            for bid in missing[:3]:
                print(f"   - {bid}")
        else:
            print(f"\n✅ 所有 first_level_block_ids 都在 blocks 中")
        
    except Exception as e:
        print(f"❌ Convert 失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
