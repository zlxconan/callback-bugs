"""In-process Knowledge service entry point."""

from collections.abc import Awaitable
from typing import TypeVar

from ops_agent.contracts import (
    KnowledgeContext,
    KnowledgeQuery,
    ModuleHealth,
    ProblemContext,
    ProductContext,
    TroubleshootingContext,
)
from ops_agent.knowledge.domain import (
    KnowledgeConfig,
    KnowledgeDependencyError,
    KnowledgeDisabledError,
    KnowledgeError,
)
from ops_agent.knowledge.ports import KnowledgePort

T = TypeVar("T")


class KnowledgeService:
    """Stable application boundary delegating work to a Knowledge adapter."""

    def __init__(self, adapter: KnowledgePort, config: KnowledgeConfig) -> None:
        self._adapter = adapter
        self._config = config

    async def health(self) -> ModuleHealth:
        return ModuleHealth(
            module="knowledge",
            status="ok" if self._config.enabled else "disabled",
            adapter=self._config.adapter_name,
        )

    async def resolve_product(self, problem: ProblemContext) -> ProductContext:
        self._ensure_enabled()
        return await self._execute(self._adapter.resolve_product(problem))

    async def query_product_knowledge(self, query: KnowledgeQuery) -> KnowledgeContext:
        self._ensure_enabled()
        return await self._execute(self._adapter.query_product_knowledge(query))

    async def query_troubleshooting(self, query: KnowledgeQuery) -> TroubleshootingContext:
        self._ensure_enabled()
        return await self._execute(self._adapter.query_troubleshooting(query))

    def _ensure_enabled(self) -> None:
        if not self._config.enabled:
            raise KnowledgeDisabledError("Knowledge module is disabled")

    @staticmethod
    async def _execute(operation: Awaitable[T]) -> T:
        try:
            return await operation
        except KnowledgeError:
            raise
        except Exception as error:
            raise KnowledgeDependencyError(str(error)) from error
