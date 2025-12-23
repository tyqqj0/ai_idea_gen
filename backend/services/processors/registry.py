from __future__ import annotations

from typing import Dict, Type

from backend.services.processors.base import BaseDocProcessor
from backend.services.processors.expander import IdeaExpanderProcessor
from backend.services.processors.researcher import ResearchProcessor


PROCESSOR_REGISTRY: Dict[str, Type[BaseDocProcessor]] = {
    "idea_expander": IdeaExpanderProcessor,
    "research": ResearchProcessor,
}


def get_processor_cls(name: str) -> Type[BaseDocProcessor]:
    try:
        return PROCESSOR_REGISTRY[name]
    except KeyError as exc:  # noqa: B904
        raise ValueError(f"Unknown processor: {name}") from exc
