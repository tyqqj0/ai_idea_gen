"""
测试元信息构建器的输出格式
"""
from datetime import datetime
from backend.services.outputs.metadata_builder import build_metadata_section


def test_metadata_section_format():
    """测试元信息块的格式"""
    
    # 模拟数据
    result = build_metadata_section(
        mode="idea_expand",
        source_title="测试文档标题",
        source_url="https://feishu.cn/docx/test123",
        original_content="这是原始文档内容\n包含多行文本\n用于测试",
        trigger_source="docs_addon",
        timestamp=datetime(2026, 1, 4, 10, 30, 0),
    )
    
    print("=" * 60)
    print("元信息块预览：")
    print("=" * 60)
    print(result)
    print("=" * 60)
    
    # 验证关键元素
    assert "---" in result
    assert "## 📋 生成信息" in result
    assert "思路扩展" in result
    assert "2026-01-04 10:30:00" in result
    assert "测试文档标题" in result
    assert "飞书文档插件" in result
    assert "<details>" in result
    assert "这是原始文档内容" in result
    
    print("\n✅ 格式验证通过！")


def test_metadata_section_without_content():
    """测试没有原始内容的情况"""
    
    result = build_metadata_section(
        mode="research",
        source_title="深度调研测试",
        source_url="https://feishu.cn/wiki/test456",
        original_content=None,  # 不传原始内容
        trigger_source=None,
        timestamp=datetime(2026, 1, 4, 11, 0, 0),
    )
    
    print("\n" + "=" * 60)
    print("无原始内容的元信息块预览：")
    print("=" * 60)
    print(result)
    print("=" * 60)
    
    # 验证关键元素
    assert "深度调研" in result
    assert "2026-01-04 11:00:00" in result
    assert "<details>" not in result  # 没有原始内容就不显示折叠块
    
    print("\n✅ 无内容格式验证通过！")


def test_metadata_section_long_content():
    """测试超长内容的截断"""
    
    long_content = "A" * 6000  # 超过 5000 字符
    
    result = build_metadata_section(
        mode="idea_expand",
        source_title="超长内容测试",
        original_content=long_content,
    )
    
    # 验证截断
    assert "（内容过长，已截断至前 5000 字符）" in result
    assert len(result) < len(long_content)  # 确实被截断了
    
    print("\n✅ 超长内容截断验证通过！")


if __name__ == "__main__":
    test_metadata_section_format()
    test_metadata_section_without_content()
    test_metadata_section_long_content()
    print("\n🎉 所有测试通过！")
