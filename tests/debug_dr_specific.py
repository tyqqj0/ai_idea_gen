#!/usr/bin/env python3
"""
Debug script to test specific Markdown content that might be causing conversion issues
"""

import asyncio
import json
from pathlib import Path

from backend.services.feishu.doc import FeishuDocClient
from backend.services.feishu import FeishuClient


async def test_problematic_content():
    """Test specific content that might be problematic for飞书 conversion"""
    print("Testing specific problematic Markdown patterns...")
    
    # Read the example file
    dr_example_path = Path(__file__).parent / "dr_example.md"
    content = dr_example_path.read_text(encoding='utf-8')
    
    feishu = FeishuClient()
    doc_client = feishu.doc
    
    # Test 1: Full content
    print("\n1. Testing full content...")
    try:
        result = await doc_client.convert_markdown_to_blocks(content)
        print(f"   ✅ Full content converted: {len(result['blocks'])} blocks")
    except Exception as e:
        print(f"   ❌ Full content failed: {e}")
        
        # Test 2: Content without links
        print("\n2. Testing content without links...")
        content_no_links = '\n'.join(line for line in content.split('\n') if not line.strip().startswith('> 🔗'))
        try:
            result = await doc_client.convert_markdown_to_blocks(content_no_links)
            print(f"   ✅ No links converted: {len(result['blocks'])} blocks")
        except Exception as e2:
            print(f"   ❌ No links also failed: {e2}")
            
            # Test 3: Just the first part
            print("\n3. Testing first part only...")
            first_part = content.split('### ⏳ 开始执行深度研究')[0] + '### ⏳ 开始执行深度研究'
            try:
                result = await doc_client.convert_markdown_to_blocks(first_part)
                print(f"   ✅ First part converted: {len(result['blocks'])} blocks")
            except Exception as e3:
                print(f"   ❌ First part also failed: {e3}")
                
                # Test 4: Even smaller chunk
                print("\n4. Testing minimal content...")
                minimal = "# Test\n\nThis is a test.\n\n- Item 1\n- Item 2"
                try:
                    result = await doc_client.convert_markdown_to_blocks(minimal)
                    print(f"   ✅ Minimal converted: {len(result['blocks'])} blocks")
                except Exception as e4:
                    print(f"   ❌ Minimal also failed: {e4}")
    
    # Test 5: Specific problematic patterns from the DR content
    print("\n5. Testing specific patterns...")
    
    # Test bullet points with special chars
    pattern1 = """- (1) 调研现有科研项目管理工具
- (2) 深入分析飞书文档
- (a) 是否支持段落级或文档级的自定义多维标签（Tagging）；
- (b) 是否能基于标签自动生成时间轴或看板视图；"""
    
    try:
        result = await doc_client.convert_markdown_to_blocks(pattern1)
        print(f"   ✅ Bullet points with () converted: {len(result['blocks'])} blocks")
    except Exception as e:
        print(f"   ❌ Bullet points with () failed: {e}")
    
    # Test quote blocks with links
    pattern2 = """> 🔗 **[Best Scientific Documentation Tools](https://example.com)**
> Some description here."""
    
    try:
        result = await doc_client.convert_markdown_to_blocks(pattern2)
        print(f"   ✅ Quote with links converted: {len(result['blocks'])} blocks")
    except Exception as e:
        print(f"   ❌ Quote with links failed: {e}")
        
    # Test complex emojis and headers
    pattern3 = """### 📋 研究主题
云文档科研流程优化调研

### 🎯 研究方案
### Step 1: 研究网站"""
    
    try:
        result = await doc_client.convert_markdown_to_blocks(pattern3)
        print(f"   ✅ Emojis and headers converted: {len(result['blocks'])} blocks")
    except Exception as e:
        print(f"   ❌ Emojis and headers failed: {e}")


async def analyze_content_structure():
    """Analyze the structure of the DR content to identify potential issues"""
    print("\nAnalyzing content structure...")
    
    dr_example_path = Path(__file__).parent / "dr_example.md"
    content = dr_example_path.read_text(encoding='utf-8')
    
    lines = content.split('\n')
    
    print(f"Total lines: {len(lines)}")
    print(f"Total characters: {len(content)}")
    
    # Check for problematic patterns
    link_lines = [line for line in lines if '> 🔗' in line]
    print(f"Quote-link lines: {len(link_lines)}")
    
    bullet_lines = [line for line in lines if line.strip().startswith('- (')]
    print(f"Bullets with parentheses: {len(bullet_lines)}")
    
    header_lines = [line for line in lines if line.strip().startswith('#')]
    print(f"Header lines: {len(header_lines)}")
    
    emoji_headers = [line for line in lines if line.strip().startswith('### ') and '📋' in line]
    print(f"Emoji headers: {len(emoji_headers)}")
    
    # Check for very long lines (potential issue)
    long_lines = [line for line in lines if len(line) > 200]
    print(f"Lines longer than 200 chars: {len(long_lines)}")
    
    if long_lines:
        print("Sample long lines:")
        for i, line in enumerate(long_lines[:3]):
            print(f"  {i+1}: {line[:100]}...")


async def main():
    print("=" * 60)
    print("Deep Research Content Analysis Tool")
    print("=" * 60)
    
    await analyze_content_structure()
    await test_problematic_content()
    
    print("\n" + "=" * 60)
    print("Analysis complete!")


if __name__ == "__main__":
    asyncio.run(main())