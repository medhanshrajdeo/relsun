"""
Mocked tests for app/agents/framework.py — the tool-use loop mechanics
(dispatch, message threading, agent-as-tool propagation, the turn cap)
verified for $0 against a scripted fake, per the "when to add the API
key" plan: this is exactly the class of bug that should never cost a
real Anthropic API call to find.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.agents.framework import MAX_TOOL_TURNS, Agent, Tool, agent_as_tool


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


def make_client(responses: list[FakeResponse]) -> FakeClient:
    return FakeClient(messages=FakeMessages(responses))


def test_no_tool_call_returns_text_directly():
    client = make_client([FakeResponse(content=[FakeTextBlock("hello there")], stop_reason="end_turn")])
    agent = Agent(name="test-agent", instructions="Be nice.")

    result = agent.run("hi", client=client)

    assert result == "hello there"
    assert len(client.messages.calls) == 1


def test_single_tool_call_dispatches_and_threads_result():
    calls = []

    def echo_handler(text: str, **_ignored: Any) -> str:
        calls.append(text)
        return f"echoed: {text}"

    echo_tool = Tool(
        name="echo",
        description="Echoes text back.",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        handler=echo_handler,
    )
    client = make_client(
        [
            FakeResponse(
                content=[FakeToolUseBlock(id="call_1", name="echo", input={"text": "hi"})],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeTextBlock("done: echoed: hi")], stop_reason="end_turn"),
        ]
    )
    agent = Agent(name="test-agent", instructions="Use the echo tool.", tools=[echo_tool])

    result = agent.run("please echo hi", client=client)

    assert result == "done: echoed: hi"
    assert calls == ["hi"]
    assert len(client.messages.calls) == 2
    # second call must carry the tool_result threaded back in
    second_call_messages = client.messages.calls[1]["messages"]
    assert second_call_messages[-1]["content"][0]["type"] == "tool_result"
    assert second_call_messages[-1]["content"][0]["content"] == "echoed: hi"


def test_agent_as_tool_propagates_client_and_context():
    session_marker = object()
    received_context = {}

    def leaf_handler(query: str, *, session: Any = None, **_ignored: Any) -> str:
        received_context["session"] = session
        return f"found: {query}"

    leaf_tool = Tool(
        name="search",
        description="Searches something.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        handler=leaf_handler,
    )
    child = Agent(name="child-agent", instructions="Search when asked.", tools=[leaf_tool])
    parent_tool = agent_as_tool(child, name="child", description="Hands off to the child agent.")
    parent = Agent(name="parent-agent", instructions="Delegate to child.", tools=[parent_tool])

    # One shared fake client services both the parent's and the child's
    # messages.create calls — agent_as_tool must pass the same client down.
    client = make_client(
        [
            FakeResponse(
                content=[FakeToolUseBlock(id="call_1", name="child", input={"prompt": "find widget"})],
                stop_reason="tool_use",
            ),
            # child agent's own turn, dispatched via child.run(client=...)
            FakeResponse(
                content=[FakeToolUseBlock(id="call_2", name="search", input={"query": "widget"})],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeTextBlock("widget found")], stop_reason="end_turn"),
            # parent's final turn after getting the child's tool_result back
            FakeResponse(content=[FakeTextBlock("parent: widget found")], stop_reason="end_turn"),
        ]
    )

    result = parent.run("find widget", client=client, context={"session": session_marker})

    assert result == "parent: widget found"
    assert received_context["session"] is session_marker
    assert len(client.messages.calls) == 4


def test_raw_schema_tool_sent_verbatim_and_never_dispatched():
    called = []
    server_tool = Tool(
        name="web_search",
        description="ignored",
        input_schema={},
        handler=lambda **_ignored: called.append("should not run"),
        raw_schema={"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
    )
    client = make_client([FakeResponse(content=[FakeTextBlock("found it")], stop_reason="end_turn")])
    agent = Agent(name="test-agent", instructions="Search the web.", tools=[server_tool])

    result = agent.run("look something up", client=client)

    assert result == "found it"
    assert called == []
    sent_tools = client.messages.calls[0]["tools"]
    assert sent_tools == [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]


def test_pause_turn_resends_and_continues_without_treating_as_final():
    client = make_client(
        [
            FakeResponse(content=[FakeTextBlock("still searching...")], stop_reason="pause_turn"),
            FakeResponse(content=[FakeTextBlock("final answer")], stop_reason="end_turn"),
        ]
    )
    agent = Agent(name="test-agent", instructions="Search the web.", tools=[])

    result = agent.run("look something up", client=client)

    assert result == "final answer"
    assert len(client.messages.calls) == 2
    # the paused turn's content was re-sent as the assistant's prior turn
    second_call_messages = client.messages.calls[1]["messages"]
    assert second_call_messages[-1]["role"] == "assistant"
    assert second_call_messages[-1]["content"] == [{"type": "text", "text": "still searching..."}]


def test_custom_max_tokens_is_used_on_every_request():
    client = make_client([FakeResponse(content=[FakeTextBlock("hi")], stop_reason="end_turn")])
    agent = Agent(name="test-agent", instructions="Be nice.", max_tokens=4096)

    agent.run("hi", client=client)

    assert client.messages.calls[0]["max_tokens"] == 4096


def test_turn_cap_raises_instead_of_looping_forever():
    responses = [
        FakeResponse(
            content=[FakeToolUseBlock(id=f"call_{i}", name="noop", input={})],
            stop_reason="tool_use",
        )
        for i in range(MAX_TOOL_TURNS)
    ]
    client = make_client(responses)
    noop_tool = Tool(
        name="noop",
        description="Does nothing.",
        input_schema={"type": "object", "properties": {}},
        handler=lambda **_ignored: "noop",
    )
    agent = Agent(name="looping-agent", instructions="Never stop.", tools=[noop_tool])

    with pytest.raises(RuntimeError, match="exceeded .* tool-use turns"):
        agent.run("go", client=client)

    assert len(client.messages.calls) == MAX_TOOL_TURNS
