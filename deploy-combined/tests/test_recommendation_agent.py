"""
Mocked coverage for the Recommendation Agent's web-search wiring — $0,
no real API call. Verifies the server-tool schema is sent correctly and
that get_recommendation_tool is reachable from Party Request Agent,
mirroring the agent_as_tool propagation test in test_agent_framework.py.
"""

from dataclasses import dataclass, field
from typing import Any

from app.agents.party_request_agent import party_request_agent
from app.agents.recommendation_agent import (
    WEB_SEARCH_TOOL,
    get_recommendation_tool,
    recommendation_agent,
)


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class FakeResponse:
    content: list[Any]
    stop_reason: str


class FakeMessages:
    def __init__(self, responses: list[FakeResponse]):
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


@dataclass
class FakeClient:
    messages: FakeMessages = field(default_factory=lambda: FakeMessages([]))


def test_web_search_tool_schema_is_the_server_tool_shape():
    schema = WEB_SEARCH_TOOL.to_schema()
    assert schema == {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}


def test_recommendation_agent_only_has_web_search():
    assert [t.name for t in recommendation_agent.tools] == ["web_search"]


def test_party_request_agent_can_reach_recommendation_agent():
    assert get_recommendation_tool in party_request_agent.tools

    client = FakeClient(
        messages=FakeMessages(
            [
                # party_request_agent decides to call get_recommendation
                FakeResponse(
                    content=[
                        FakeToolUseBlock(
                            id="call_1", name="get_recommendation", input={"prompt": "look up Acme Corp"}
                        )
                    ],
                    stop_reason="tool_use",
                ),
                # recommendation_agent's own turn, resolved via web search server-side
                FakeResponse(content=[FakeTextBlock("Acme Corp HQ: 1 Main St, Springfield")], stop_reason="end_turn"),
                # party_request_agent's final turn after getting the sub-agent's result
                FakeResponse(content=[FakeTextBlock("I found a possible HQ address, want me to use it?")], stop_reason="end_turn"),
            ]
        )
    )

    result = party_request_agent.run("create a party for Acme Corp", client=client)

    assert result == "I found a possible HQ address, want me to use it?"
    assert len(client.messages.calls) == 3
    # the recommendation sub-agent's request carried the real web_search server tool
    recommendation_call = client.messages.calls[1]
    assert recommendation_call["tools"] == [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]
