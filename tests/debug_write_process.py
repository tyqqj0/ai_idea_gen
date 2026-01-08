#!/usr/bin/env python3
"""
Debug script to test the actual document writing process step by step
"""

import asyncio
import json
from pathlib import Path

from backend.services.feishu.doc import FeishuDocClient
from backend.services.feishu import FeishuClient


async def test_detailed_write_process():
    """Test the writing process step by step"""
    print("Testing detailed document write process...")
    
    # Read the example file
    dr_example_path = Path(__file__).parent / "dr_example.md"
    content = dr_example_path.read_text(encoding='utf-8')
    
    feishu = FeishuClient()
    doc_client = feishu.doc
    
    # Step 1: Convert to blocks (this worked in previous test)
    print("\n1. Converting content to blocks...")
    try:
        convert_result = await doc_client.convert_markdown_to_blocks(content)
        blocks = convert_result["blocks"]
        first_level_block_ids = convert_result["first_level_block_ids"]
        
        print(f"   ✅ Converted to {len(blocks)} blocks")
        print(f"   ✅ First level block IDs: {len(first_level_block_ids)}")
        
        # Step 2: Create a test document
        print("\n2. Creating test document...")
        test_title = f"Write Process Debug {int(__import__('time').time())}"
        doc_token = await feishu.drive.create_doc(folder_token="", title=test_title)
        print(f"   ✅ Created test document: {doc_token}")
        
        # Step 3: Try to add blocks using add_blocks_descendant directly
        print("\n3. Testing add_blocks_descendant...")
        try:
            await doc_client.add_blocks_descendant(
                doc_token, 
                blocks,
                first_level_block_ids,
            )
            print("   ✅ Successfully added blocks to document")
        except Exception as e:
            print(f"   ❌ add_blocks_descendant failed: {e}")
            print(f"      Error type: {type(e).__name__}")
            
            # Step 4: Try fallback to single text block
            print("\n4. Testing fallback to single text block...")
            try:
                fallback_block = {
                    "block_id": "plain_text_1",
                    "block_type": 2,  # 文本块
                    "text": {
                        "elements": [
                            {"text_run": {"content": content[:50000]}}  # Truncate to be safe
                        ]
                    },
                    "children": [],
                }
                await doc_client.add_blocks_descendant(
                    doc_token, 
                    [fallback_block], 
                    ["plain_text_1"]
                )
                print("   ✅ Successfully added fallback text block")
            except Exception as e2:
                print(f"   ❌ Fallback also failed: {e2}")
        
        # Cleanup
        print("\n5. Cleaning up test document...")
        try:
            # Since we saw delete_file doesn't exist, let's just try to archive or ignore
            print(f"   ℹ️  Skipping cleanup for test document: {doc_token}")
        except Exception as e:
            print(f"   ⚠️  Cleanup failed: {e}")
        
    except Exception as e:
        print(f"   ❌ Conversion failed: {e}")


async def test_write_content_method():
    """Test the actual write_content method that's used in production"""
    print("\n" + "="*50)
    print("Testing write_content method (production path)...")
    
    # Read the example file
    dr_example_path = Path(__file__).parent / "dr_example.md"
    content = dr_example_path.read_text(encoding='utf-8')
    
    feishu = FeishuClient()
    doc_client = feishu.doc
    
    # Create a test document
    print("1. Creating test document...")
    test_title = f"Write Content Test {int(__import__('time').time())}"
    doc_token = await feishu.drive.create_doc(folder_token="", title=test_title)
    print(f"   ✅ Created test document: {doc_token}")
    
    # Call the write_content method that's actually used
    print("2. Calling write_content method...")
    try:
        await doc_client.write_content(doc_token, content)
        print("   ✅ write_content succeeded!")
    except Exception as e:
        print(f"   ❌ write_content failed: {e}")
        print(f"      Error type: {type(e).__name__}")
        
        # Let's check the exact error more closely
        import traceback
        print(f"      Full traceback:")
        traceback.print_exc()
    
    print(f"3. Test document left for inspection: {doc_token}")


async def test_small_chunks():
    """Test writing small chunks to identify the problematic part"""
    print("\n" + "="*50)
    print("Testing incremental write to identify problematic sections...")
    
    dr_example_path = Path(__file__).parent / "dr_example.md"
    content = dr_example_path.read_text(encoding='utf-8')
    
    feishu = FeishuClient()
    doc_client = feishu.doc
    
    # Split content into sections by headers
    sections = []
    current_section = []
    lines = content.split('\n')
    
    for line in lines:
        if line.startswith('#'):
            if current_section:
                sections.append('\n'.join(current_section))
                current_section = []
        current_section.append(line)
    
    if current_section:
        sections.append('\n'.join(current_section))
    
    print(f"Split content into {len(sections)} sections")
    
    # Create a test document
    test_title = f"Incremental Write Test {int(__import__('time').time())}"
    doc_token = await feishu.drive.create_doc(folder_token="", title=test_title)
    print(f"Created test document: {doc_token}")
    
    for i, section in enumerate(sections):
        if section.strip():
            print(f"\nTesting section {i+1}/{len(sections)}...")
            try:
                # Clear the document and write just this section
                # Actually, we'll just test conversion
                result = await doc_client.convert_markdown_to_blocks(section)
                print(f"   Section {i+1}: ✅ Converted ({len(result['blocks'])} blocks)")
                
                # Now try to write it
                test_title_section = f"Section {i+1} Test {int(__import__('time').time())}"
                section_doc = await feishu.drive.create_doc(folder_token="", title=test_title_section)
                
                await doc_client.write_content(section_doc, section)
                print(f"   Section {i+1}: ✅ Written successfully")
                
            except Exception as e:
                print(f"   Section {i+1}: ❌ Failed - {e}")
                print(f"     First 200 chars: {section[:200]}...")


async def main():
    print("=" * 60)
    print("Deep Research Document Write Process Debug Tool")
    print("=" * 60)
    
    await test_detailed_write_process()
    await test_write_content_method()
    await test_small_chunks()
    
    print("\n" + "=" * 60)
    print("Debug complete!")


if __name__ == "__main__":
    asyncio.run(main())