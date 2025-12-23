from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from backend.core.manager import WorkflowConfig, WorkflowRegistry
from backend.core.workflow_config_models import WorkflowConfigFile
from backend.services.outputs.registry import get_output_factory
from backend.services.processors.registry import get_processor_cls

logger = logging.getLogger(__name__)


def load_workflow_registry(config_path: Optional[str] = None) -> WorkflowRegistry:
    """
    从 workflow_config.yml 加载 mode->WorkflowConfig 的映射，并构建 WorkflowRegistry。
    """

    default_path = Path(__file__).resolve().parents[2] / "workflow_config.yml"
    path = Path(config_path) if config_path else default_path
    if not path.exists():
        raise RuntimeError(f"workflow_config.yml not found at {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg = WorkflowConfigFile.model_validate(raw)

    mapping: dict[str, WorkflowConfig] = {}
    for mode, item in cfg.workflows.items():
        mapping[mode] = WorkflowConfig(
            processor_cls=get_processor_cls(item.processor),
            chain=item.chain,
            output_factory=get_output_factory(item.output),
            notify_user=item.notify_user,
        )

    logger.info("Loaded workflow registry from %s, modes=%s", path, list(mapping.keys()))
    return WorkflowRegistry(mapping)


def build_default_workflow_registry() -> WorkflowRegistry:
    """
    代码内置的默认组合配置（用于配置缺失时兜底）。
    """

    mapping: dict[str, WorkflowConfig] = {
        "idea_expand": WorkflowConfig(
            processor_cls=get_processor_cls("idea_expander"),
            chain="idea_expand",
            output_factory=get_output_factory("feishu_child_doc"),
            notify_user=True,
        ),
        "research": WorkflowConfig(
            processor_cls=get_processor_cls("research"),
            chain="research",
            output_factory=get_output_factory("feishu_child_doc"),
            notify_user=True,
        ),
    }
    return WorkflowRegistry(mapping)


