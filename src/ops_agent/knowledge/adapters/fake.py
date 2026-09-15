"""Deterministic KnowledgePort implementation for the MVP Fake case."""

from ops_agent.contracts import (
    KnowledgeContext,
    KnowledgeQuery,
    ProblemContext,
    ProductContext,
    RawReference,
    TroubleshootingContext,
)


class FakeKnowledgeEngine:
    """Return fixed version and retry/idempotency knowledge without external I/O."""

    async def resolve_product(self, problem: ProblemContext) -> ProductContext:
        return ProductContext(
            schema_version=problem.schema_version,
            incident_id=problem.incident_id,
            request_id=problem.request_id,
            timestamp=problem.timestamp,
            source="fake-knowledge",
            metadata={"fake": True},
            product_name="Order Service",
            product_version="2026.09-retry-enabled",
            component="order-api.create-order",
            deployment_environment="fake",
            expected_behavior="客户端可在超时后重试，服务端应通过幂等键避免重复创建。",
            configuration={"client_retry_enabled": True, "idempotency_enforced": False},
        )

    async def query_product_knowledge(self, query: KnowledgeQuery) -> KnowledgeContext:
        return KnowledgeContext(
            schema_version=query.schema_version,
            incident_id=query.incident_id,
            request_id=query.request_id,
            timestamp=query.timestamp,
            source="fake-knowledge",
            metadata={"fake": True},
            query=query.query,
            facts=[
                "当前版本支持客户端重试。",
                "创建接口非幂等，存在重复创建风险。",
            ],
            references=[
                RawReference(
                    uri="fake://knowledge/order-service/retry-and-idempotency",
                    digest="sha256:fake-order-knowledge-v1",
                    media_type="application/json",
                )
            ],
            skill_ids=["fake.order-duplicate-troubleshooting.v1"],
            limitations=["仅覆盖固定 MVP 场景，不代表真实产品行为。"],
        )

    async def query_troubleshooting(self, query: KnowledgeQuery) -> TroubleshootingContext:
        return TroubleshootingContext(
            schema_version=query.schema_version,
            incident_id=query.incident_id,
            request_id=query.request_id,
            timestamp=query.timestamp,
            source="fake-knowledge",
            metadata={"fake": True},
            actions_taken=[],
            observed_results=[],
            known_workarounds=["临时关闭客户端自动重试。"],
            constraints=["禁止连接真实订单系统。", "仅允许 Fake 实验。"],
        )
