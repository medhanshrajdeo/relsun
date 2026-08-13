"""
Shared agent framework — every agent in AGENT_INVENTORY.md is an instance
of Agent below, per the 2026-08-12 Agent Architecture Pivot addendum in
CONFIGURABLE_WORKFLOWS_AGENTS.md.

An Agent has plain-English `instructions` (the customer-editable, no-code
configuration surface — see the pivot addendum's "Configurability,
revised" section) and a list of Tools. A Tool is either a real function
(a DB read, a graph query, ...) or another Agent wrapped via
agent_as_tool() — the "an agent's tools can include other agents"
mechanism the whole hierarchy is modeled on. Which tool (if any) gets
called for a given prompt is a runtime decision the model makes from the
instructions; nothing here hardcodes a step sequence.

Handler convention: every Tool.handler is called as
`handler(**tool_input, **context)`, where `context` always includes
`client` (the Anthropic client in use, so agent_as_tool can propagate it
to a child Agent) plus whatever the caller passed in (e.g. `session`).
Handlers should declare the context keys they actually use as named
parameters and accept `**_ignored` for the rest, so the same context dict
can be threaded through every tool without each one needing to know about
keys it doesn't care about.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from app.config import settings

MAX_TOOL_TURNS = 6


class AgentNotConfiguredError(RuntimeError):
    """ANTHROPIC_API_KEY isn't set — expected in local dev until a real key
    is provisioned (see config.py)."""


_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if not settings.anthropic_api_key:
        raise AgentNotConfiguredError(
            "ANTHROPIC_API_KEY is not set — agents aren't available until an "
            "Anthropic API key is configured."
        )
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., str]

    def to_schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


@dataclass
class Agent:
    name: str
    instructions: str
    tools: list[Tool] = field(default_factory=list)
    model: str = ""

    def run(
        self,
        prompt: str,
        *,
        client: Anthropic | None = None,
        context: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        client = client or get_client()
        model = self.model or settings.anthropic_model
        run_context = dict(context or {})
        run_context["client"] = client

        tool_schemas = [t.to_schema() for t in self.tools]
        tools_by_name = {t.name: t for t in self.tools}
        # `history` is prior (user, assistant) turn *text* only — never the
        # internal tool-use blocks a past turn may have made along the way.
        # Those were this agent's own private reasoning for that turn, not
        # part of the conversation the next turn should see.
        messages: list[dict[str, Any]] = [dict(turn) for turn in (history or [])]
        messages.append({"role": "user", "content": prompt})

        for _ in range(MAX_TOOL_TURNS):
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=self.instructions,
                tools=tool_schemas,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                return _text_of(response, agent_name=self.name)

            messages.append({"role": "assistant", "content": _serialize_content(response.content)})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tool = tools_by_name.get(block.name)
                result_text = (
                    f"Unknown tool: {block.name}"
                    if tool is None
                    else tool.handler(**block.input, **run_context)
                )
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": str(result_text)}
                )
            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(f"Agent '{self.name}' exceeded {MAX_TOOL_TURNS} tool-use turns without a final answer.")


def _text_of(response: Any, *, agent_name: str) -> str:
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise RuntimeError(f"Agent '{agent_name}' returned no text response.")
    return text


def _serialize_content(content: list[Any]) -> list[dict[str, Any]]:
    blocks = []
    for block in content:
        if block.type == "text":
            blocks.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            blocks.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
    return blocks


def agent_as_tool(agent: Agent, *, name: str, description: str) -> Tool:
    """Wraps a child Agent's .run() as a callable Tool for a parent agent.
    Propagates the same client (real or, in tests, fake) and the rest of
    the ambient context (e.g. session) down to the child — the parent
    routing to a child agent doesn't need to know what that child needs
    internally, only that it exists and when to hand off to it."""

    def handler(prompt: str, client: Anthropic | None = None, **rest_context: Any) -> str:
        return agent.run(prompt, client=client, context=rest_context)

    return Tool(
        name=name,
        description=description,
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The request to hand off to this agent, in the user's own words or a summary of it.",
                }
            },
            "required": ["prompt"],
        },
        handler=handler,
    )
