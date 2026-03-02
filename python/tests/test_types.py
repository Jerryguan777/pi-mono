"""Tests for pi_ai types."""

from pi_ai.types import (
    AssistantMessage,
    Context,
    Cost,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)
from pi_ai.models import calculate_cost, get_model, Model, ModelCost


def test_text_content():
    tc = TextContent(text="hello")
    assert tc.type == "text"
    assert tc.text == "hello"


def test_thinking_content():
    tc = ThinkingContent(thinking="let me think...")
    assert tc.type == "thinking"
    assert tc.thinking == "let me think..."


def test_tool_call():
    tc = ToolCall(id="tc1", name="bash", arguments={"command": "ls"})
    assert tc.type == "toolCall"
    assert tc.name == "bash"
    assert tc.arguments == {"command": "ls"}


def test_user_message():
    msg = UserMessage(content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"
    assert msg.timestamp > 0


def test_user_message_with_content_blocks():
    msg = UserMessage(content=[TextContent(text="hello")])
    assert isinstance(msg.content, list)
    assert msg.content[0].text == "hello"


def test_assistant_message():
    msg = AssistantMessage(
        content=[TextContent(text="hi")],
        api="openai-responses",
        provider="openai",
        model="gpt-4o",
    )
    assert msg.role == "assistant"
    assert len(msg.content) == 1
    assert msg.stop_reason == "stop"


def test_tool_result_message():
    msg = ToolResultMessage(
        tool_call_id="tc1",
        tool_name="bash",
        content=[TextContent(text="output")],
    )
    assert msg.role == "toolResult"
    assert msg.tool_call_id == "tc1"
    assert not msg.is_error


def test_tool():
    tool = Tool(
        name="bash",
        description="Execute bash",
        parameters={"type": "object", "properties": {"command": {"type": "string"}}},
    )
    assert tool.name == "bash"


def test_context():
    ctx = Context(
        system_prompt="You are helpful",
        messages=[UserMessage(content="hello")],
        tools=[Tool(name="bash", description="exec")],
    )
    assert ctx.system_prompt == "You are helpful"
    assert len(ctx.messages) == 1
    assert len(ctx.tools) == 1


def test_usage():
    usage = Usage(input=100, output=50, total_tokens=150)
    assert usage.input == 100
    assert usage.cost.total == 0  # not calculated yet


def test_calculate_cost():
    model = Model(
        id="test",
        cost=ModelCost(input=2.0, output=8.0, cache_read=1.0, cache_write=0),
    )
    usage = Usage(input=1000, output=500)
    calculate_cost(model, usage)
    assert usage.cost.input == 2.0 / 1_000_000 * 1000
    assert usage.cost.output == 8.0 / 1_000_000 * 500
    assert usage.cost.total > 0


def test_get_model():
    model = get_model("openai", "gpt-4o")
    assert model.id == "gpt-4o"
    assert model.provider == "openai"
    assert model.api == "openai-responses"


def test_get_model_unknown():
    try:
        get_model("openai", "nonexistent")
        assert False, "Should have raised"
    except ValueError:
        pass
