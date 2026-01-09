"""
使用飞书官方 SDK 测试 Markdown 转换和 Blocks 写入

目的：对比官方 SDK 与手搓版的差异，定位 invalid param 问题
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

import os
import lark_oapi as lark
from lark_oapi.api.docx.v1 import *

from backend.config import get_settings

DR_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "dr_example.md"


def get_client() -> lark.Client:
    """创建官方 SDK 客户端"""
    settings = get_settings()
    return lark.Client.builder() \
        .app_id(settings.FEISHU_APP_ID) \
        .app_secret(settings.FEISHU_APP_SECRET) \
        .log_level(lark.LogLevel.DEBUG) \
        .build()


def test_convert_simple():
    """测试 1：用官方 SDK 转换简单 Markdown"""
    print("\n" + "=" * 60)
    print("测试 1：官方 SDK - 转换简单 Markdown")
    print("=" * 60)
    
    simple_md = """# 测试标题

这是一段简单的文本。

## 二级标题

- 列表项 1
- 列表项 2
"""
    
    client = get_client()
    
    request = ConvertDocumentRequest.builder() \
        .request_body(ConvertDocumentRequestBody.builder()
            .content_type("markdown")
            .content(simple_md)
            .build()) \
        .build()
    
    response = client.docx.v1.document.convert(request)
    
    if not response.success():
        print(f"❌ 转换失败: code={response.code}, msg={response.msg}")
        print(f"   log_id: {response.get_log_id()}")
        return None
    
    data = response.data
    blocks = data.blocks if data.blocks else []
    first_level_block_ids = data.first_level_block_ids if data.first_level_block_ids else []
    
    print(f"✅ 转换成功!")
    print(f"   - blocks 数量: {len(blocks)}")
    print(f"   - 顶层 blocks: {len(first_level_block_ids)}")
    
    return {
        "blocks": blocks,
        "first_level_block_ids": first_level_block_ids,
    }


def test_convert_dr_content():
    """测试 2：用官方 SDK 转换 dr_example.md 内容"""
    print("\n" + "=" * 60)
    print("测试 2：官方 SDK - 转换 dr_example.md")
    print("=" * 60)
    
    if not DR_EXAMPLE_PATH.exists():
        print(f"❌ 找不到文件: {DR_EXAMPLE_PATH}")
        return None
    
    content = DR_EXAMPLE_PATH.read_text(encoding="utf-8")
    
    # 去掉 think 标签
    import re
    content_cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content_cleaned = content_cleaned.strip()
    
    print(f"📄 内容长度: {len(content_cleaned)} 字符")
    
    client = get_client()
    
    request = ConvertDocumentRequest.builder() \
        .request_body(ConvertDocumentRequestBody.builder()
            .content_type("markdown")
            .content(content_cleaned)
            .build()) \
        .build()
    
    response = client.docx.v1.document.convert(request)
    
    if not response.success():
        print(f"❌ 转换失败: code={response.code}, msg={response.msg}")
        print(f"   log_id: {response.get_log_id()}")
        return None
    
    data = response.data
    blocks = data.blocks if data.blocks else []
    first_level_block_ids = data.first_level_block_ids if data.first_level_block_ids else []
    
    print(f"✅ 转换成功!")
    print(f"   - blocks 数量: {len(blocks)}")
    print(f"   - 顶层 blocks: {len(first_level_block_ids)}")
    
    # 打印第一个 block 的结构（官方 SDK 格式）
    if blocks:
        print(f"\n📊 第一个 block 结构 (官方 SDK 格式):")
        first_block = blocks[0]
        print(f"   类型: {type(first_block)}")
        # 序列化看看
        if hasattr(first_block, '__dict__'):
            print(f"   属性: {list(first_block.__dict__.keys())[:10]}")
    
    return {
        "blocks": blocks,
        "first_level_block_ids": first_level_block_ids,
    }


def test_create_and_write():
    """测试 3：用官方 SDK 创建文档并写入 blocks"""
    print("\n" + "=" * 60)
    print("测试 3：官方 SDK - 创建文档并写入 blocks")
    print("=" * 60)
    
    # 先转换
    simple_md = "# 测试\n\n简单文本"
    
    client = get_client()
    
    # 1. 转换
    convert_request = ConvertDocumentRequest.builder() \
        .request_body(ConvertDocumentRequestBody.builder()
            .content_type("markdown")
            .content(simple_md)
            .build()) \
        .build()
    
    convert_response = client.docx.v1.document.convert(convert_request)
    
    if not convert_response.success():
        print(f"❌ 转换失败: code={convert_response.code}")
        return
    
    blocks = convert_response.data.blocks or []
    first_level_ids = convert_response.data.first_level_block_ids or []
    
    print(f"✅ 转换成功: {len(blocks)} blocks")
    
    # 2. 创建文档
    create_request = CreateDocumentRequest.builder() \
        .request_body(CreateDocumentRequestBody.builder()
            .folder_token("")
            .title("[SDK测试] 写入测试")
            .build()) \
        .build()
    
    create_response = client.docx.v1.document.create(create_request)
    
    if not create_response.success():
        print(f"❌ 创建文档失败: code={create_response.code}, msg={create_response.msg}")
        return
    
    doc_token = create_response.data.document.document_id
    print(f"✅ 创建文档成功: {doc_token}")
    
    # 3. 写入 blocks（使用 descendant 接口）
    # 正确的调用方式: client.docx.v1.document_block_descendant.create
    descendant_request = CreateDocumentBlockDescendantRequest.builder() \
        .document_id(doc_token) \
        .block_id(doc_token) \
        .document_revision_id(-1) \
        .request_body(CreateDocumentBlockDescendantRequestBody.builder()
            .children_id(first_level_ids)
            .index(0)
            .descendants(blocks)
            .build()) \
        .build()
    
    descendant_response = client.docx.v1.document_block_descendant.create(descendant_request)
    
    if not descendant_response.success():
        print(f"❌ 写入失败: code={descendant_response.code}, msg={descendant_response.msg}")
        print(f"   log_id: {descendant_response.get_log_id()}")
        # 打印详细错误
        if descendant_response.raw:
            print(f"   raw: {descendant_response.raw.content[:500]}")
        return
    
    print(f"✅ 写入成功!")
    print(f"   文档链接: https://feishu.cn/docx/{doc_token}")


def test_write_dr_content():
    """测试 4：用官方 SDK 写入 dr_example.md 内容"""
    print("\n" + "=" * 60)
    print("测试 4：官方 SDK - 写入 dr_example.md 内容")
    print("=" * 60)
    
    if not DR_EXAMPLE_PATH.exists():
        print(f"❌ 找不到文件")
        return
    
    content = DR_EXAMPLE_PATH.read_text(encoding="utf-8")
    
    import re
    content_cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content_cleaned = content_cleaned.strip()
    
    print(f"📄 内容长度: {len(content_cleaned)} 字符")
    
    client = get_client()
    
    # 1. 转换
    convert_request = ConvertDocumentRequest.builder() \
        .request_body(ConvertDocumentRequestBody.builder()
            .content_type("markdown")
            .content(content_cleaned)
            .build()) \
        .build()
    
    convert_response = client.docx.v1.document.convert(convert_request)
    
    if not convert_response.success():
        print(f"❌ 转换失败: code={convert_response.code}")
        return
    
    blocks = convert_response.data.blocks or []
    first_level_ids = convert_response.data.first_level_block_ids or []
    
    print(f"✅ 转换成功: {len(blocks)} blocks, {len(first_level_ids)} 顶层")
    
    # 2. 创建文档
    create_request = CreateDocumentRequest.builder() \
        .request_body(CreateDocumentRequestBody.builder()
            .folder_token("")
            .title("[SDK测试] DR内容写入")
            .build()) \
        .build()
    
    create_response = client.docx.v1.document.create(create_request)
    
    if not create_response.success():
        print(f"❌ 创建文档失败: code={create_response.code}")
        return
    
    doc_token = create_response.data.document.document_id
    print(f"✅ 创建文档成功: {doc_token}")
    
    # 3. 写入 - 使用正确的调用方式
    descendant_request = CreateDocumentBlockDescendantRequest.builder() \
        .document_id(doc_token) \
        .block_id(doc_token) \
        .document_revision_id(-1) \
        .request_body(CreateDocumentBlockDescendantRequestBody.builder()
            .children_id(first_level_ids)
            .index(0)
            .descendants(blocks)
            .build()) \
        .build()
    
    descendant_response = client.docx.v1.document_block_descendant.create(descendant_request)
    
    if not descendant_response.success():
        print(f"❌ 写入失败: code={descendant_response.code}, msg={descendant_response.msg}")
        print(f"   log_id: {descendant_response.get_log_id()}")
        return
    
    print(f"✅ 写入成功!")
    print(f"   文档链接: https://feishu.cn/docx/{doc_token}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", type=str, 
                        choices=["convert-simple", "convert-dr", "write-simple", "write-dr", "all"],
                        default="all")
    args = parser.parse_args()
    
    print("🔍 使用飞书官方 SDK 测试")
    print(f"   lark-oapi version: {lark.__version__ if hasattr(lark, '__version__') else 'unknown'}")
    
    if args.test in ["convert-simple", "all"]:
        test_convert_simple()
    
    if args.test in ["convert-dr", "all"]:
        test_convert_dr_content()
    
    if args.test in ["write-simple", "all"]:
        test_create_and_write()
    
    if args.test in ["write-dr", "all"]:
        test_write_dr_content()


if __name__ == "__main__":
    main()
