"""Knowledge domain configuration and transport-independent errors."""

from ops_agent.knowledge.domain.config import KnowledgeConfig
from ops_agent.knowledge.domain.errors import (
    InvalidProductSkillError,
    KnowledgeDependencyError,
    KnowledgeDisabledError,
    KnowledgeError,
    KnowledgeResolutionError,
    UnknownProductError,
    UnknownProductVersionError,
)
from ops_agent.knowledge.domain.plugin_specs import (
    ProductSkillSpec,
    TroubleshootingSkillSpec,
)

__all__ = [
    "InvalidProductSkillError",
    "KnowledgeConfig",
    "KnowledgeDependencyError",
    "KnowledgeDisabledError",
    "KnowledgeError",
    "KnowledgeResolutionError",
    "ProductSkillSpec",
    "TroubleshootingSkillSpec",
    "UnknownProductError",
    "UnknownProductVersionError",
]
