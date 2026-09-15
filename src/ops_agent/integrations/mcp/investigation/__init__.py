"""Backward-compatible alias for the observability MCP adapter."""

from ops_agent.integrations.mcp.observability import create_observability_mcp

__all__ = ["create_observability_mcp"]
