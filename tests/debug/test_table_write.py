#!/usr/bin/env python3
"""
测试单独写入表格
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.services.feishu import FeishuClient


async def main():
    """测试写入表格"""
    
    # 简单的表格
    table_md = """# 测试表格

## 生成信息

| 项目 | 值 |
|------|------|
| 处理模式 | 思路扩展 |
| 生成时间 | 2026-01-04 16:45:00 |
"""
    
    feishu_client = FeishuClient()
    
    print("=" * 60)
    print("测试内容:")
    print("=" * 60)
    print(table_md)
    
    # 测试文档 token
    test_doc_token = "ExPWdT3IYo8xuMxhLDGc4YuknSe"
    
    try:
        print(f"\n尝试写入...")
        await feishu_client.write_doc_content(test_doc_token, table_md)
        print(f"✅ 写入成功!")
        print(f"   查看文档: https://feishu.cn/wiki/TqAvwCuooifVjpkVWO8cCMCGnhW")
    except Exception as e:
        print(f"❌ 写入失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
