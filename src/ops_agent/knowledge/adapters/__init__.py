"""Knowledge adapter implementations."""

from ops_agent.knowledge.adapters.fake import FakeKnowledgeEngine
from ops_agent.knowledge.adapters.plugin import PluginKnowledgeEngine

__all__ = ["FakeKnowledgeEngine", "PluginKnowledgeEngine"]
