"""
元信息构建器：在生成文档末尾添加处理元信息
"""
from datetime import datetime
from typing import Optional


# 模式名称映射（用于显示）
MODE_DISPLAY_NAMES = {
    "idea_expand": "思路扩展",
    "research": "深度调研",
}


def build_metadata_section(
    *,
    mode: str,
    source_title: str,
    source_url: str | None = None,
    original_content: str | None = None,
    trigger_source: str | None = None,
    timestamp: datetime | None = None,
) -> str:
    """
    构建元信息 Markdown 块，追加到结果文档末尾。
    
    Args:
        mode: 处理模式（如 "idea_expand", "research"）
        source_title: 来源文档标题
        source_url: 来源文档链接（可选）
        original_content: 原始文档内容（可选）
        trigger_source: 触发来源（可选）
        timestamp: 生成时间（可选，默认当前时间）
    
    Returns:
        格式化的 Markdown 元信息块
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    mode_display = MODE_DISPLAY_NAMES.get(mode, mode)
    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    # 构建元信息表格
    lines = [
        "",
        "---",
        "",
        "## 📋 生成信息",
        "",
        "| 项目 | 值 |",
        "|------|------|",
        f"| 处理模式 | {mode_display} |",
        f"| 生成时间 | {time_str} |",
    ]
    
    # 来源文档
    if source_url:
        lines.append(f"| 来源文档 | [{source_title}]({source_url}) |")
    else:
        lines.append(f"| 来源文档 | {source_title} |")
    
    # 触发来源（可选）
    if trigger_source:
        source_display = {
            "docs_addon": "飞书文档插件",
            "manual_test": "手动测试",
        }.get(trigger_source, trigger_source)
        lines.append(f"| 触发来源 | {source_display} |")
    
    lines.append("")
    
    # 原始内容（折叠显示，避免太长）
    if original_content:
        # 截断过长内容
        max_length = 5000
        content_to_show = original_content
        truncated = False
        
        if len(original_content) > max_length:
            content_to_show = original_content[:max_length]
            truncated = True
        
        lines.extend([
            "<details>",
            "<summary>📄 原始输入内容（点击展开）</summary>",
            "",
            "```",
            content_to_show,
            "```",
        ])
        
        if truncated:
            lines.append("")
            lines.append("*（内容过长，已截断至前 5000 字符）*")
        
        lines.extend([
            "",
            "</details>",
            "",
        ])
    
    return "\n".join(lines)
