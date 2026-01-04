"""
元信息构建工具：为生成的文档追加元数据块
"""
from datetime import datetime
from typing import Optional


def build_metadata_section(
    *,
    mode: str,
    source_title: str,
    source_url: str,
    original_content: Optional[str] = None,
    trigger_source: Optional[str] = None,
    max_content_length: int = 5000,
) -> str:
    """
    构建元信息 Markdown 块，追加到结果文档末尾
    
    Args:
        mode: 处理模式（如 "idea_expand", "research"）
        source_title: 来源文档标题
        source_url: 来源文档链接
        original_content: 原始文档内容（可选，会被折叠显示）
        trigger_source: 触发来源（可选）
        max_content_length: 原始内容最大长度（超过则截断）
    
    Returns:
        格式化的 Markdown 元信息块
    """
    # 模式名称映射
    mode_names = {
        "idea_expand": "思路扩展",
        "research": "深度调研",
    }
    mode_name = mode_names.get(mode, mode)
    
    # 当前时间
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 构建基础信息（不使用表格，改用列表）
    metadata_lines = [
        "",
        "---",
        "",
        "## 📋 生成信息",
        "",
        f"- **处理模式**: {mode_name}",
        f"- **生成时间**: {timestamp}",
        f"- **来源文档**: [{source_title}]({source_url})",
    ]
    
    # 可选：添加触发来源
    if trigger_source:
        trigger_names = {
            "docs_addon": "云文档小组件",
            "manual_test": "手动测试",
            "api": "API 调用",
        }
        trigger_name = trigger_names.get(trigger_source, trigger_source)
        metadata_lines.append(f"- **触发来源**: {trigger_name}")
    
    metadata_lines.append("")
    
    # 可选：添加原始内容（使用 Markdown 代码块，不使用 HTML 标签）
    if original_content:
        # 截断过长内容
        content_to_show = original_content
        is_truncated = False
        
        if len(original_content) > max_content_length:
            content_to_show = original_content[:max_content_length]
            is_truncated = True
        
        metadata_lines.extend([
            "---",
            "",
            "### 📄 原始输入内容",
            "",
            "```",
            content_to_show,
            "```",
            "",
        ])
        
        if is_truncated:
            metadata_lines.append(f"*（内容过长，已截断至 {max_content_length} 字符）*")
            metadata_lines.append("")
    
    return "\n".join(metadata_lines)
