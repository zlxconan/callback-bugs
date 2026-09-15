"""Investigation domain configuration and transport-independent errors."""

from ops_agent.investigation.domain.config import InvestigationConfig
from ops_agent.investigation.domain.errors import (
    InvestigationDependencyError,
    InvestigationDisabledError,
    InvestigationError,
)

__all__ = [
    "InvestigationConfig",
    "InvestigationDependencyError",
    "InvestigationDisabledError",
    "InvestigationError",
]
