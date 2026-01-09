"""
隔离测试：飞书文档写入流程

目的：测试 convert 成功后，add_blocks_descendant 写入是否失败
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from backend.services.feishu import FeishuClient, FeishuAPIError

# 测试用的文档 token（需要是一个有写权限的空白测试文档）
# 可以通过命令行参数传入
TEST_DOC_TOKEN = None

DR_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "dr_example.md"


async def test_write_simple_content(doc_token: str):
    """测试 1：写入简单内容"""
    print("\n" + "=" * 60)
    print("测试 1：写入简单 Markdown 内容")
    print("=" * 60)
    
    simple_md = """
# 测试标题

这是一段简单的文本。

## 二级标题

- 列表项 1
- 列表项 2
"""
    
    feishu = FeishuClient()
    
    try:
        print("📝 开始转换...")
        result = await feishu.doc.convert_markdown_to_blocks(simple_md)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        print(f"   转换成功: blocks={len(blocks)}, first_level={len(first_level_ids)}")
        
        print("📝 开始写入...")
        await feishu.doc.add_blocks_descendant(
            doc_token,
            blocks,
            first_level_ids,
        )
        print("✅ 写入成功!")
        return {"success": True}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


async def test_write_full_dr_content(doc_token: str):
    """测试 2：写入完整 dr_example.md 内容（包含 think 标签）"""
    print("\n" + "=" * 60)
    print("测试 2：写入完整 dr_example.md 内容（包含 think）")
    print("=" * 60)
    
    if not DR_EXAMPLE_PATH.exists():
        print(f"❌ 找不到测试文件: {DR_EXAMPLE_PATH}")
        return None
    
    content = DR_EXAMPLE_PATH.read_text(encoding="utf-8")
    print(f"📄 内容长度: {len(content)} 字符（包含 think 标签）")
    
    feishu = FeishuClient()
    
    try:
        print("📝 开始转换...")
        result = await feishu.doc.convert_markdown_to_blocks(content)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        print(f"   转换成功: blocks={len(blocks)}, first_level={len(first_level_ids)}")
        
        print("📝 开始写入...")
        await feishu.doc.add_blocks_descendant(
            doc_token,
            blocks,
            first_level_ids,
        )
        print("✅ 写入成功!")
        return {"success": True, "blocks": len(blocks)}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        # 打印更详细的错误信息
        error_str = str(e)
        print(f"   详细错误: {error_str[:500]}")
        return {"success": False, "error": error_str}
    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


async def test_write_without_think(doc_token: str):
    """测试 3：写入去掉 think 标签的内容（对比测试）"""
    print("\n" + "=" * 60)
    print("测试 3：写入去掉 <think> 标签的内容（对比）")
    print("=" * 60)
    
    if not DR_EXAMPLE_PATH.exists():
        print(f"❌ 找不到测试文件")
        return None
    
    content = DR_EXAMPLE_PATH.read_text(encoding="utf-8")
    
    import re
    content_cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content_cleaned = content_cleaned.strip()
    
    print(f"📄 清理后内容长度: {len(content_cleaned)} 字符")
    
    feishu = FeishuClient()
    
    try:
        print("📝 开始转换...")
        result = await feishu.doc.convert_markdown_to_blocks(content_cleaned)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        print(f"   转换成功: blocks={len(blocks)}, first_level={len(first_level_ids)}")
        
        print("📝 开始写入...")
        await feishu.doc.add_blocks_descendant(
            doc_token,
            blocks,
            first_level_ids,
        )
        print("✅ 写入成功!")
        return {"success": True, "blocks": len(blocks)}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        error_str = str(e)
        print(f"   详细错误: {error_str[:500]}")
        return {"success": False, "error": error_str}
    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


async def test_write_in_chunks(doc_token: str, chunk_size: int = 50):
    """测试 4：分批写入（更小的 chunk）"""
    print("\n" + "=" * 60)
    print(f"测试 4：分批写入（chunk_size={chunk_size}）")
    print("=" * 60)
    
    if not DR_EXAMPLE_PATH.exists():
        print(f"❌ 找不到测试文件")
        return None
    
    content = DR_EXAMPLE_PATH.read_text(encoding="utf-8")
    
    feishu = FeishuClient()
    
    try:
        print("📝 开始转换...")
        result = await feishu.doc.convert_markdown_to_blocks(content)
        blocks = result.get("blocks", [])
        first_level_ids = result.get("first_level_block_ids", [])
        print(f"   转换成功: blocks={len(blocks)}, first_level={len(first_level_ids)}")
        
        print(f"📝 开始分批写入（每批 {chunk_size} 个 blocks）...")
        await feishu.doc.add_blocks_descendant(
            doc_token,
            blocks,
            first_level_ids,
            chunk_size=chunk_size,
        )
        print("✅ 写入成功!")
        return {"success": True, "blocks": len(blocks)}
        
    except FeishuAPIError as e:
        print(f"❌ 飞书 API 错误: {e}")
        error_str = str(e)
        print(f"   详细错误: {error_str[:500]}")
        return {"success": False, "error": error_str}
    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


async def create_test_doc():
    """创建一个测试文档用于写入测试"""
    print("\n🔧 创建测试文档...")
    
    feishu = FeishuClient()
    
    try:
        # 在根目录创建测试文档
        doc_token = await feishu.drive.create_doc(
            folder_token="",  # 根目录
            title=f"[测试] Blocks 写入测试",
        )
        print(f"✅ 创建测试文档成功: {doc_token}")
        print(f"   链接: https://feishu.cn/docx/{doc_token}")
        return doc_token
    except FeishuAPIError as e:
        print(f"❌ 创建文档失败: {e}")
        return None


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="测试飞书文档写入")
    parser.add_argument("--doc-token", type=str, help="测试文档的 token（不提供则自动创建）")
    parser.add_argument("--create-only", action="store_true", help="只创建测试文档，不执行写入测试")
    parser.add_argument("--test", type=str, choices=["simple", "full", "no_think", "chunks", "all"], 
                        default="all", help="执行哪个测试")
    args = parser.parse_args()
    
    print("🔍 飞书文档写入测试")
    print("目的：定位 add_blocks_descendant 写入是否失败\n")
    
    # 获取或创建测试文档
    doc_token = args.doc_token
    if not doc_token:
        doc_token = await create_test_doc()
        if not doc_token:
            print("❌ 无法创建测试文档，退出")
            return
    
    if args.create_only:
        print("\n✅ 文档已创建，退出")
        return
    
    print(f"\n📄 使用测试文档: {doc_token}")
    print(f"   链接: https://feishu.cn/docx/{doc_token}")
    
    results = {}
    
    if args.test in ["simple", "all"]:
        results["simple"] = await test_write_simple_content(doc_token)
    
    if args.test in ["full", "all"]:
        results["full"] = await test_write_full_dr_content(doc_token)
    
    if args.test in ["no_think", "all"]:
        results["no_think"] = await test_write_without_think(doc_token)
    
    if args.test in ["chunks", "all"]:
        results["chunks"] = await test_write_in_chunks(doc_token, chunk_size=50)
    
    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for name, result in results.items():
        if result is None:
            print(f"  {name}: ⏭️ 跳过")
        elif result.get("success"):
            print(f"  {name}: ✅ 成功")
        else:
            print(f"  {name}: ❌ 失败 - {result.get('error', 'unknown')[:80]}...")


if __name__ == "__main__":
    asyncio.run(main())
