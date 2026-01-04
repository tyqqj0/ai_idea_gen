#!/usr/bin/env python3
"""
测试主内容 + 元数据一起转换
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.services.feishu import FeishuClient
from backend.services.utils.metadata_builder import build_metadata_section


async def main():
    """测试主内容 + 元数据"""
    
    # 1. 模拟主内容（简单的 Markdown）
    main_content = """# 测试标题

## 第一部分

这是第一部分的内容。

- 列表项 1
- 列表项 2

## 第二部分

这是第二部分的内容。

1. 编号列表 1
2. 编号列表 2
"""
    
    # 2. 生成元数据
    metadata = build_metadata_section(
        mode="idea_expand",
        source_title="测试文档",
        source_url="https://feishu.cn/docx/test123",
        original_content="原始输入内容，用于测试",
        trigger_source="manual_test",
    )
    
    # 3. 拼接主内容 + 元数据
    full_content = main_content + metadata
    
    print("=" * 60)
    print("完整内容 (主内容 + 元数据):")
    print("=" * 60)
    print(full_content)
    print("=" * 60)
    print(f"\n总长度: {len(full_content)} 字符\n")
    
    # 4. 调用 convert 接口转换
    feishu_client = FeishuClient()
    
    try:
        print("正在调用 convert 接口...")
        result = await feishu_client.convert_markdown_to_blocks(full_content)
        
        blocks = result["blocks"]
        first_level_block_ids = result["first_level_block_ids"]
        
        print(f"✅ Convert 成功!")
        print(f"   blocks 数量: {len(blocks)}")
        print(f"   first_level_blocks 数量: {len(first_level_block_ids)}")
        
        # 5. 检查一致性
        all_block_ids = {b.get("block_id") for b in blocks}
        missing = [bid for bid in first_level_block_ids if bid not in all_block_ids]
        
        if missing:
            print(f"\n⚠️ 警告: 有 {len(missing)} 个 first_level_block_ids 不在 blocks 中:")
            for bid in missing[:3]:
                print(f"   - {bid}")
            return False
        else:
            print(f"\n✅ 所有 first_level_block_ids 都在 blocks 中")
        
        # 6. 尝试写入文档
        print(f"\n尝试写入到测试文档...")
        
        # 使用你的测试文档 token
        test_doc_token = "ExPWdT3IYo8xuMxhLDGc4YuknSe"  # 刚才创建的文档
        
        await feishu_client.write_doc_content(test_doc_token, full_content)
        
        print(f"✅ 写入成功!")
        print(f"   查看文档: https://feishu.cn/wiki/TqAvwCuooifVjpkVWO8cCMCGnhW")
        
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
