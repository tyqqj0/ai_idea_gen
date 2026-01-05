#!/usr/bin/env python3
"""
测试飞书文档 token 类型识别

用于验证一个 token 是：
1. Wiki 节点
2. 云盘文件（Drive API 可访问）
3. 纯 docx 文档（只能通过 docx API 访问）
"""
import asyncio
import sys

from backend.services.feishu import FeishuClient


async def test_token_type(token: str):
    """测试 token 类型"""
    client = FeishuClient()
    
    print(f"\n{'='*60}")
    print(f"测试 Token: {token}")
    print(f"{'='*60}\n")
    
    # 1. 测试是否是 Wiki 节点
    print("🔍 测试 1: 检查是否是 Wiki 节点...")
    try:
        node = await client.wiki.get_node_by_token(node_token=token)
        print(f"✅ 是 Wiki 节点")
        print(f"   space_id: {node.get('space_id')}")
        print(f"   obj_token: {node.get('obj_token')}")
        print(f"   obj_type: {node.get('obj_type')}")
        return "wiki"
    except Exception as e:
        print(f"❌ 不是 Wiki 节点: {e}")
    
    # 2. 测试是否是云盘文件（Drive API）
    print("\n🔍 测试 2: 检查是否是云盘文件（Drive API）...")
    try:
        meta = await client.drive.get_file_meta(token)
        print(f"✅ 是云盘文件")
        print(f"   name: {meta.get('name')}")
        print(f"   parent_token: {meta.get('parent_token')}")
        print(f"   owner_id: {meta.get('owner_id')}")
        return "drive"
    except Exception as e:
        print(f"❌ 不是云盘文件: {e}")
    
    # 3. 测试是否是 docx 文档
    print("\n🔍 测试 3: 检查是否是 docx 文档...")
    try:
        meta = await client.doc.get_meta(token)
        print(f"✅ 是 docx 文档")
        print(f"   title: {meta.get('title')}")
        print(f"   document_id: {meta.get('document_id')}")
        print(f"   ⚠️  注意：docx API 不返回 parent_token，无法获取父文件夹信息")
        return "docx"
    except Exception as e:
        print(f"❌ 不是 docx 文档: {e}")
    
    print("\n❌ 未知的 token 类型！")
    return "unknown"


async def main():
    if len(sys.argv) < 2:
        print("用法: python test_token_type.py <token>")
        print("\n示例:")
        print("  python test_token_type.py OBBsdAHuNoH2fgxfeZ1cTfOKnQc")
        sys.exit(1)
    
    token = sys.argv[1]
    token_type = await test_token_type(token)
    
    print(f"\n{'='*60}")
    print(f"结论: Token 类型是 [{token_type}]")
    print(f"{'='*60}\n")
    
    if token_type == "docx":
        print("⚠️  该文档是纯 docx 文档，无法通过 Drive API 获取父文件夹信息。")
        print("💡 建议:")
        print("   1. 如果需要在云盘中组织文档，应该先创建文件夹")
        print("   2. 使用 drive.create_doc() 在文件夹中创建文档")
        print("   3. 或者使用知识库（Wiki）来管理文档层级关系")


if __name__ == "__main__":
    asyncio.run(main())
