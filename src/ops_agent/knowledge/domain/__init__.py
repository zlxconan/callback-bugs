"""Knowledge domain configuration and transport-independent errors."""

from ops_agent.knowledge.domain.config import KnowledgeConfig
from ops_agent.knowledge.domain.errors import (
    KnowledgeDependencyError,
    KnowledgeDisabledError,
    KnowledgeError,
)

__all__ = [
    "KnowledgeConfig",
    "KnowledgeDependencyError",
    "KnowledgeDisabledError",
    "KnowledgeError",
]
