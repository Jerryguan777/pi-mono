"""Tests for pi_ai.transform_messages."""

from pi_ai.transform_messages import transform_messages
from pi_ai.types import (
    AssistantMessage,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def _assistant(
    content, *, provider="openai", api="openai-responses", model="gpt-5.2",
    stop_reason="stop",
):
    return AssistantMessage(
        content=content, provider=provider, api=api, model=model,
        stop_reason=stop_reason,
    )


def _model(provider="openai", api="openai-responses", model_id="gpt-5.2"):
    from pi_ai.types import Model
    return Model(id=model_id, api=api, provider=provider)


# ---------- user messages pass through ----------

def test_user_messages_unchanged():
    msgs = [UserMessage(content="hello")]
    result = transform_messages(msgs, _model())
    assert len(result) == 1
    assert result[0].content == "hello"


# ---------- thinking block transforms ----------

def test_same_model_keeps_thinking_with_signature():
    """Same model + signature → keep (needed for replay)."""
    msgs = [_assistant([ThinkingContent(thinking="hmm", thinking_signature="sig123")])]
    result = transform_messages(msgs, _model())
    assert len(result) == 1
    block = result[0].content[0]
    assert isinstance(block, ThinkingContent)
    assert block.thinking_signature == "sig123"


def test_same_model_keeps_empty_thinking_with_signature():
    """OpenAI encrypted reasoning: empty text but has signature → keep."""
    msgs = [_assistant([ThinkingContent(thinking="", thinking_signature="enc")])]
    result = transform_messages(msgs, _model())
    block = result[0].content[0]
    assert isinstance(block, ThinkingContent)
    assert block.thinking_signature == "enc"


def test_same_model_keeps_thinking_without_signature():
    """Same model, has text but no signature → keep."""
    msgs = [_assistant([ThinkingContent(thinking="let me think")])]
    result = transform_messages(msgs, _model())
    block = result[0].content[0]
    assert isinstance(block, ThinkingContent)
    assert block.thinking == "let me think"


def test_cross_model_converts_thinking_to_text():
    """Different model → thinking becomes plain text."""
    msgs = [_assistant(
        [ThinkingContent(thinking="reasoning here")],
        provider="anthropic", api="anthropic-messages", model="claude-sonnet",
    )]
    result = transform_messages(msgs, _model())  # openai model
    block = result[0].content[0]
    assert isinstance(block, TextContent)
    assert block.text == "reasoning here"


def test_cross_model_drops_empty_thinking():
    """Different model + empty thinking → dropped."""
    msgs = [_assistant(
        [ThinkingContent(thinking=""), TextContent(text="answer")],
        provider="anthropic", api="anthropic-messages", model="claude-sonnet",
    )]
    result = transform_messages(msgs, _model())
    assert len(result[0].content) == 1
    assert isinstance(result[0].content[0], TextContent)
    assert result[0].content[0].text == "answer"


def test_same_model_drops_empty_thinking_without_signature():
    """Same model + empty + no signature → dropped."""
    msgs = [_assistant([ThinkingContent(thinking="  "), TextContent(text="ok")])]
    result = transform_messages(msgs, _model())
    assert len(result[0].content) == 1
    assert result[0].content[0].text == "ok"


# ---------- text block transforms ----------

def test_same_model_keeps_text_signature():
    msgs = [_assistant([TextContent(text="hi", text_signature="sig")])]
    result = transform_messages(msgs, _model())
    assert result[0].content[0].text_signature == "sig"


def test_cross_model_strips_text_signature():
    msgs = [_assistant(
        [TextContent(text="hi", text_signature="sig")],
        provider="anthropic", api="anthropic-messages", model="claude",
    )]
    result = transform_messages(msgs, _model())
    assert result[0].content[0].text_signature is None


# ---------- tool call ID normalization ----------

def test_tool_call_id_normalization():
    """Cross-model with normalizer → IDs rewritten in both assistant and toolResult."""
    msgs = [
        _assistant(
            [ToolCall(id="very-long-id-from-openai|item_123", name="bash", arguments={})],
            provider="openai", api="openai-responses", model="gpt-5",
        ),
        ToolResultMessage(
            tool_call_id="very-long-id-from-openai|item_123",
            tool_name="bash",
            content=[TextContent(text="done")],
        ),
    ]
    # Target: anthropic model
    target = _model(provider="anthropic", api="anthropic-messages", model_id="claude")

    def normalizer(id_: str, model, source):
        return "short_" + id_[:8]

    result = transform_messages(msgs, target, normalize_tool_call_id=normalizer)
    # Assistant's tool call should have new ID
    tc = result[0].content[0]
    assert isinstance(tc, ToolCall)
    assert tc.id == "short_very-lon"
    # ToolResult should match
    assert result[1].tool_call_id == "short_very-lon"


def test_same_model_skips_normalization():
    """Same model → no ID normalization even if normalizer provided."""
    msgs = [
        _assistant([ToolCall(id="original", name="bash", arguments={})]),
        ToolResultMessage(tool_call_id="original", tool_name="bash",
                          content=[TextContent(text="ok")]),
    ]
    def normalizer(id_, model, source):
        return "changed"

    result = transform_messages(msgs, _model(), normalize_tool_call_id=normalizer)
    assert result[0].content[0].id == "original"
    assert result[1].tool_call_id == "original"


# ---------- thought_signature on tool calls ----------

def test_cross_model_strips_thought_signature_from_tool_call():
    msgs = [_assistant(
        [ToolCall(id="tc1", name="bash", arguments={}, thought_signature="google_sig")],
        provider="google", api="google-generative-ai", model="gemini",
    )]
    result = transform_messages(msgs, _model())
    tc = result[0].content[0]
    assert isinstance(tc, ToolCall)
    assert tc.thought_signature is None


def test_same_model_keeps_thought_signature():
    msgs = [_assistant(
        [ToolCall(id="tc1", name="bash", arguments={}, thought_signature="sig")],
        provider="google", api="google-generative-ai", model="gemini",
    )]
    target = _model(provider="google", api="google-generative-ai", model_id="gemini")
    result = transform_messages(msgs, target)
    assert result[0].content[0].thought_signature == "sig"


# ---------- error/aborted message filtering ----------

def test_error_messages_dropped():
    msgs = [
        UserMessage(content="hello"),
        _assistant([TextContent(text="partial")], stop_reason="error"),
        UserMessage(content="try again"),
        _assistant([TextContent(text="success")]),
    ]
    result = transform_messages(msgs, _model())
    assert len(result) == 3
    assert result[0].content == "hello"
    assert result[1].content == "try again"
    assert result[2].content[0].text == "success"


def test_aborted_messages_dropped():
    msgs = [
        _assistant([TextContent(text="interrupted")], stop_reason="aborted"),
    ]
    result = transform_messages(msgs, _model())
    assert len(result) == 0


# ---------- orphaned tool calls → synthetic results ----------

def test_orphaned_tool_calls_get_synthetic_results():
    """Tool calls without matching results → synthetic error results inserted."""
    msgs = [
        _assistant([
            ToolCall(id="tc1", name="bash", arguments={}),
            ToolCall(id="tc2", name="read", arguments={}),
        ]),
        ToolResultMessage(tool_call_id="tc1", tool_name="bash",
                          content=[TextContent(text="ok")]),
        # tc2 has no result
        UserMessage(content="continue"),
    ]
    result = transform_messages(msgs, _model())
    # assistant, tc1 result, synthetic tc2 result, user
    assert len(result) == 4
    synthetic = result[2]
    assert isinstance(synthetic, ToolResultMessage)
    assert synthetic.tool_call_id == "tc2"
    assert synthetic.is_error is True
    assert synthetic.content[0].text == "No result provided"


def test_orphaned_tool_calls_before_next_assistant():
    """Orphaned calls flushed when next assistant message arrives."""
    msgs = [
        _assistant([ToolCall(id="tc1", name="bash", arguments={})]),
        # No tool result for tc1
        _assistant([TextContent(text="retry")]),
    ]
    result = transform_messages(msgs, _model())
    # assistant, synthetic tc1 result, assistant
    assert len(result) == 3
    assert isinstance(result[1], ToolResultMessage)
    assert result[1].tool_call_id == "tc1"
    assert result[1].is_error is True


def test_no_synthetic_when_all_results_present():
    """All tool calls have results → no synthetic results added."""
    msgs = [
        _assistant([
            ToolCall(id="tc1", name="bash", arguments={}),
            ToolCall(id="tc2", name="read", arguments={}),
        ]),
        ToolResultMessage(tool_call_id="tc1", tool_name="bash",
                          content=[TextContent(text="ok")]),
        ToolResultMessage(tool_call_id="tc2", tool_name="read",
                          content=[TextContent(text="file content")]),
    ]
    result = transform_messages(msgs, _model())
    assert len(result) == 3  # no extras


# ---------- combined scenarios ----------

def test_error_msg_with_orphaned_tool_calls():
    """Error message dropped; its tool calls don't generate orphan results."""
    msgs = [
        _assistant(
            [ToolCall(id="tc1", name="bash", arguments={})],
            stop_reason="error",
        ),
        UserMessage(content="retry"),
    ]
    result = transform_messages(msgs, _model())
    # Error assistant dropped, no orphan since it was dropped
    assert len(result) == 1
    assert result[0].content == "retry"


def test_full_conversation_roundtrip():
    """Multi-turn conversation with cross-model, thinking, tools, errors."""
    msgs = [
        UserMessage(content="q1"),
        # Turn 1: anthropic assistant with thinking + tool call
        _assistant(
            [
                ThinkingContent(thinking="let me search"),
                TextContent(text="I'll look that up"),
                ToolCall(id="tc1", name="grep", arguments={"pattern": "foo"}),
            ],
            provider="anthropic", api="anthropic-messages", model="claude",
        ),
        ToolResultMessage(tool_call_id="tc1", tool_name="grep",
                          content=[TextContent(text="found it")]),
        # Turn 2: error
        _assistant(
            [TextContent(text="oops")],
            provider="anthropic", api="anthropic-messages", model="claude",
            stop_reason="error",
        ),
        # Turn 3: successful answer
        _assistant(
            [TextContent(text="the answer is 42")],
            provider="anthropic", api="anthropic-messages", model="claude",
        ),
    ]
    # Replay on openai model
    result = transform_messages(msgs, _model())
    assert len(result) == 4  # user, assistant (thinking→text), toolResult, assistant
    # Thinking converted to text for cross-model
    assert isinstance(result[1].content[0], TextContent)
    assert result[1].content[0].text == "let me search"
    # Error turn dropped
    assert result[3].content[0].text == "the answer is 42"


def test_immutability():
    """Original messages are not mutated."""
    original_tc = ToolCall(id="orig_id", name="bash", arguments={},
                           thought_signature="sig")
    original_msg = _assistant(
        [original_tc],
        provider="google", api="google-generative-ai", model="gemini",
    )
    msgs = [original_msg]
    transform_messages(msgs, _model())
    # Original should be untouched
    assert original_tc.thought_signature == "sig"
    assert original_tc.id == "orig_id"
    assert msgs[0].content[0].thought_signature == "sig"
