"""Web search tool using Tavily API."""

from __future__ import annotations

import os
from typing import Any

import httpx

from pi_agent.types import AgentTool, AgentToolResult, AgentToolUpdateCallback
from pi_ai.types import TextContent


class WebSearchTool(AgentTool):
    def __init__(self):
        self.name = "web_search"
        self.label = "web search"
        self.description = (
            "Search the web using Tavily API. Returns relevant results with snippets. "
            "Use for current events, facts, or information not in training data."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "number", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        }

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        on_update: AgentToolUpdateCallback | None = None,
    ) -> AgentToolResult:
        query = params["query"]
        max_results = int(params.get("max_results", 5))

        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            raise ValueError("TAVILY_API_KEY environment variable required for web search.")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": True,
                },
            )
            response.raise_for_status()
            data = response.json()

        # Format results
        parts: list[str] = []

        answer = data.get("answer")
        if answer:
            parts.append(f"**Answer:** {answer}\n")

        results = data.get("results", [])
        for i, result in enumerate(results, 1):
            title = result.get("title", "")
            url = result.get("url", "")
            snippet = result.get("content", "")
            parts.append(f"{i}. **{title}**\n   {url}\n   {snippet}\n")

        if not parts:
            return AgentToolResult(content=[TextContent(text="No results found.")])

        return AgentToolResult(content=[TextContent(text="\n".join(parts))])
