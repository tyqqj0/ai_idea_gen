#!/usr/bin/env python3
"""
Debug script to test Markdown conversion for deep research content
"""

import asyncio
import json
from pathlib import Path

from backend.services.feishu.doc import FeishuDocClient
from backend.services.feishu import FeishuClient


async def test_convert_markdown():
    """Test converting the DR example markdown to blocks"""
    print("Testing Markdown conversion for deep research content...")
    
    # Read the example file
    dr_example_path = Path(__file__).parent / "dr_example.md"
    if not dr_example_path.exists():
        print(f"Error: {dr_example_path} not found!")
        return
    
    content = dr_example_path.read_text(encoding='utf-8')
    print(f"Read {len(content)} characters from {dr_example_path}")
    
    # Test conversion
    feishu = FeishuClient()
    doc_client = feishu.doc
    
    try:
        print("Attempting to convert markdown to blocks...")
        blocks = await doc_client.convert_to_blocks(content)
        print(f"✅ Success! Converted to {len(blocks)} blocks")
        
        # Show first few blocks as sample
        print("\nFirst 3 blocks:")
        for i, block in enumerate(blocks[:3]):
            print(f"  Block {i}: {json.dumps(block, ensure_ascii=False)[:200]}...")
        
        print(f"\nLast 3 blocks:")
        for i, block in enumerate(blocks[-3:], start=len(blocks)-3):
            print(f"  Block {i}: {json.dumps(block, ensure_ascii=False)[:200]}...")
            
    except Exception as e:
        print(f"❌ Error during conversion: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Let's also try to see what specific part might be problematic
        print("\nTrying to identify problematic sections...")
        
        # Test with smaller chunks
        lines = content.split('\n')
        chunk_size = 50
        for i in range(0, len(lines), chunk_size):
            chunk = '\n'.join(lines[i:i+chunk_size])
            if chunk.strip():
                try:
                    chunk_blocks = await doc_client.convert_to_blocks(chunk)
                    print(f"  Chunk {i//chunk_size + 1}: ✅ ({len(chunk_blocks)} blocks)")
                except Exception as chunk_e:
                    print(f"  Chunk {i//chunk_size + 1}: ❌ Error: {chunk_e}")
                    print(f"    First 200 chars: {chunk[:200]}...")
                    break


async def test_write_document():
    """Test writing the content to a real document"""
    print("\nTesting document write...")
    
    # Read the example file
    dr_example_path = Path(__file__).parent / "dr_example.md"
    content = dr_example_path.read_text(encoding='utf-8')
    
    # Get or create a test document
    feishu = FeishuClient()
    
    # For testing purposes, we'll create a temporary document
    # and then clean it up afterward
    print("Creating test document...")
    
    try:
        # Create a temporary document in root
        test_title = f"DR Debug Test {int(__import__('time').time())}"
        doc_token = await feishu.drive.create_doc(folder_token="", title=test_title)
        print(f"Created test document: {doc_token}")
        
        print("Writing content to document...")
        await feishu.write_doc_content(doc_token, content)
        print("✅ Successfully wrote content to document")
        
        # Clean up
        print("Cleaning up test document...")
        await feishu.drive.delete_file(doc_token)
        print("✅ Test document cleaned up")
        
    except Exception as e:
        print(f"❌ Error during document write: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # If creation failed, try with converted blocks
        if "create_doc" in str(e) or "drive" in str(e):
            print("Trying with pre-converted blocks...")
            try:
                doc_client = feishu.doc
                blocks = await doc_client.convert_to_blocks(content)
                
                # Try creating document with blocks directly
                from backend.services.feishu.doc import Block
                
                # Just test the conversion part
                print(f"Pre-converted to {len(blocks)} blocks, skipping write for now")
                
            except Exception as conv_e:
                print(f"❌ Also failed to convert: {conv_e}")


async def main():
    print("=" * 60)
    print("Deep Research Markdown Conversion Debug Tool")
    print("=" * 60)
    
    await test_convert_markdown()
    await test_write_document()
    
    print("\n" + "=" * 60)
    print("Debug complete!")


if __name__ == "__main__":
    asyncio.run(main())