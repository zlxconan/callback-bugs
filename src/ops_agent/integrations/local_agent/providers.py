"""LLMProviderPort implementations at the LangChain integration boundary."""

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr

from ops_agent.contracts import IncidentState, LLMRequest, LLMResponse, RuntimeTask, TaskResult
from ops_agent.integrations.local_agent.fake_runner import FakeTaskReasoner
from ops_agent.skills import CanonicalSkill


class OpenAICompatibleProviderConfig(BaseModel):
    """Endpoint configuration; no vendor or model name is hard-coded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(min_length=1)
    base_url: AnyHttpUrl
    api_key: SecretStr
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    json_mode: bool = True


class OpenAICompatibleProvider:
    """LangChain ChatOpenAI adapter for vLLM and compatible HTTP APIs."""

    def __init__(
        self,
        config: OpenAICompatibleProviderConfig,
        *,
        chat_model: BaseChatModel | None = None,
    ) -> None:
        self._config = config
        self._chat_model = chat_model or ChatOpenAI(
            model=config.model,
            base_url=str(config.base_url),
            api_key=config.api_key,
            temperature=config.temperature,
            timeout=config.timeout_seconds,
            model_kwargs=({"response_format": {"type": "json_object"}} if config.json_mode else {}),
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        system = SystemMessage(
            content=(
                "Complete exactly one RuntimeTask. Return only one JSON object matching the "
                "provided schema. Never invent evidence identifiers or workflow state."
            )
        )
        human = HumanMessage(
            content=json.dumps(
                {
                    "task": request.task.model_dump(mode="json"),
                    "state": json.loads(request.state_summary),
                    "skills": [
                        {"name": name, "instructions": instructions}
                        for name, instructions in zip(
                            request.skill_names,
                            request.skill_instructions,
                            strict=True,
                        )
                    ],
                    "required_output_field": request.required_output_field,
                    "output_schema": request.output_schema,
                },
                ensure_ascii=False,
            )
        )
        response = await self._chat_model.ainvoke([system, human])
        content = (
            response.content
            if isinstance(response.content, str)
            else json.dumps(response.content, ensure_ascii=False)
        )
        return LLMResponse(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="openai-compatible-provider",
            metadata={"base_url": str(self._config.base_url)},
            content=content,
            provider="openai-compatible",
            model=self._config.model,
        )


class FakeLLMProvider:
    """Deterministic provider returning JSON produced by the Step 5 Fake task reasoner."""

    def __init__(
        self,
        task_reasoner: FakeTaskReasoner,
        *,
        scripted_responses: list[str] | None = None,
    ) -> None:
        self._task_reasoner = task_reasoner
        self._scripted_responses = list(scripted_responses or [])
        self.call_count = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.call_count += 1
        if self._scripted_responses:
            content = self._scripted_responses.pop(0)
        else:
            result = await self._task_reasoner.reason(request.task, request.state)
            if result.typed_output is None:
                message = (
                    result.error.message if result.error is not None else "Fake reasoning failed"
                )
                raise RuntimeError(message)
            content = result.typed_output.model_dump_json()
        return LLMResponse(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="fake-llm-provider",
            metadata={"fake": True},
            content=content,
            provider="fake",
            model="fake-structured-model",
        )

    def as_reasoning_owner(self) -> "FakeReasoningOwner":
        return FakeReasoningOwner(self._task_reasoner)


class FakeReasoningOwner:
    """Deterministic non-LLM fallback after provider validation retries are exhausted."""

    def __init__(self, task_reasoner: FakeTaskReasoner) -> None:
        self._task_reasoner = task_reasoner

    async def reason(
        self,
        task: RuntimeTask,
        state: IncidentState,
        skills: tuple[CanonicalSkill, ...],
    ) -> TaskResult:
        del skills
        return await self._task_reasoner.reason(task, state)
