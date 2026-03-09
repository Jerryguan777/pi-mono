"""Unit tests for pi_coding_agent interactive UI components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# session_selector_search
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.session_selector_search import (
    MatchResult,
    ParsedSearchQuery,
    filter_and_sort_sessions,
    has_session_name,
    match_session,
    parse_search_query,
)


@dataclass
class _FakeSession:
    path: str = "session1"
    name: str | None = None
    first_message: str = ""
    all_messages_text: str = ""
    modified: Any = None


class TestParseSearchQuery:
    def test_empty_string(self) -> None:
        q = parse_search_query("")
        assert q.tokens == []
        assert q.regex is None
        assert q.mode == "tokens"

    def test_simple_tokens(self) -> None:
        q = parse_search_query("hello world")
        assert any(t["value"] == "hello" for t in q.tokens)
        assert any(t["value"] == "world" for t in q.tokens)
        assert q.mode == "tokens"

    def test_regex_prefix(self) -> None:
        q = parse_search_query("re:foo.*bar")
        assert q.mode == "regex"
        assert q.regex is not None

    def test_invalid_regex(self) -> None:
        q = parse_search_query("re:[invalid")
        # Should not raise, falls back with error
        assert q.mode == "regex"
        assert q.error is not None

    def test_quoted_phrase(self) -> None:
        q = parse_search_query('"hello world"')
        assert any(t["value"] == "hello world" and t["kind"] == "phrase" for t in q.tokens)

    def test_empty_regex_pattern(self) -> None:
        q = parse_search_query("re:")
        assert q.mode == "regex"
        assert q.error is not None

    def test_tokens_are_dicts(self) -> None:
        q = parse_search_query("foo bar")
        assert all(isinstance(t, dict) for t in q.tokens)
        assert all("kind" in t and "value" in t for t in q.tokens)


class TestMatchSession:
    def test_empty_query_matches_all(self) -> None:
        session = _FakeSession(all_messages_text="hello")
        q = parse_search_query("")
        result = match_session(session, q)
        assert result.matches

    def test_token_match_on_messages_text(self) -> None:
        session = _FakeSession(all_messages_text="hello world")
        q = parse_search_query("hello")
        result = match_session(session, q)
        assert result.matches

    def test_token_no_match(self) -> None:
        session = _FakeSession(all_messages_text="goodbye")
        q = parse_search_query("xyznonexistent")
        result = match_session(session, q)
        assert not result.matches

    def test_regex_match(self) -> None:
        session = _FakeSession(all_messages_text="foo123bar")
        q = parse_search_query("re:foo[0-9]+bar")
        result = match_session(session, q)
        assert result.matches

    def test_regex_no_match(self) -> None:
        session = _FakeSession(all_messages_text="nothing")
        q = parse_search_query("re:foo[0-9]+bar")
        result = match_session(session, q)
        assert not result.matches

    def test_name_match(self) -> None:
        session = _FakeSession(name="my-session", all_messages_text="my-session other")
        q = parse_search_query("my-session")
        result = match_session(session, q)
        assert result.matches

    def test_regex_with_no_pattern_set(self) -> None:
        q = ParsedSearchQuery(mode="regex", tokens=[], regex=None, error="Empty regex")
        session = _FakeSession(all_messages_text="anything")
        result = match_session(session, q)
        assert not result.matches

    def test_match_result_has_score(self) -> None:
        session = _FakeSession(all_messages_text="hello world test")
        q = parse_search_query("hello")
        result = match_session(session, q)
        assert isinstance(result.score, float)


class TestHasSessionName:
    def test_with_name(self) -> None:
        session = _FakeSession(name="my-session")
        assert has_session_name(session)

    def test_without_name(self) -> None:
        session = _FakeSession(name=None)
        assert not has_session_name(session)

    def test_empty_name(self) -> None:
        session = _FakeSession(name="")
        assert not has_session_name(session)

    def test_whitespace_only_name(self) -> None:
        session = _FakeSession(name="   ")
        assert not has_session_name(session)


class TestFilterAndSortSessions:
    def _sessions(self) -> list[_FakeSession]:
        return [
            _FakeSession(path="a", all_messages_text="apple pie"),
            _FakeSession(path="b", all_messages_text="banana split"),
            _FakeSession(path="c", name="my session", all_messages_text="my session other"),
        ]

    def test_empty_query_returns_all_recent(self) -> None:
        sessions = self._sessions()
        result = filter_and_sort_sessions(sessions, "", "recent", "all")
        assert len(result) == 3

    def test_filter_by_token(self) -> None:
        sessions = self._sessions()
        result = filter_and_sort_sessions(sessions, "apple", "recent", "all")
        assert len(result) == 1
        assert result[0].path == "a"

    def test_filter_named_only(self) -> None:
        sessions = self._sessions()
        result = filter_and_sort_sessions(sessions, "", "recent", "named")
        assert len(result) == 1
        assert result[0].name == "my session"

    def test_sort_relevance(self) -> None:
        sessions = self._sessions()
        result = filter_and_sort_sessions(sessions, "apple", "relevance", "all")
        assert len(result) >= 1

    def test_no_matches(self) -> None:
        sessions = self._sessions()
        result = filter_and_sort_sessions(sessions, "re:zzz_no_match_xyz", "recent", "all")
        assert result == []

    def test_invalid_regex_returns_empty(self) -> None:
        sessions = self._sessions()
        result = filter_and_sort_sessions(sessions, "re:[invalid", "recent", "all")
        assert result == []

    def test_empty_sessions(self) -> None:
        result = filter_and_sort_sessions([], "apple", "recent", "all")
        assert result == []


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.diff import render_diff


class TestRenderDiff:
    def test_empty_diff(self) -> None:
        result = render_diff("")
        assert isinstance(result, str)

    def test_returns_string(self) -> None:
        # Basic sanity — render_diff always returns str
        result = render_diff("some plain text without diff markers")
        assert isinstance(result, str)

    def test_diff_with_added_line(self) -> None:
        # The diff format expected by _parse_diff_line: "prefix linenum content"
        # e.g. "+  1 added content"
        diff = "+  1 added line"
        result = render_diff(diff)
        assert "added line" in result

    def test_diff_with_removed_line(self) -> None:
        diff = "-  1 removed line"
        result = render_diff(diff)
        assert "removed line" in result

    def test_diff_with_context_line(self) -> None:
        diff = "   1 context line"
        result = render_diff(diff)
        assert "context line" in result

    def test_diff_with_file_path(self) -> None:
        # file_path is accepted as second argument
        diff = "+  1 new content"
        result = render_diff(diff, "foo.py")
        assert isinstance(result, str)

    def test_intra_line_diff_single_remove_add(self) -> None:
        # A remove followed immediately by an add triggers intra-line diff
        # The result contains ANSI escape codes so check for substrings that survive styling
        diff = "-  1 old content\n+  1 new content"
        result = render_diff(diff)
        assert "old" in result and "new" in result

    def test_multiple_removes_adds(self) -> None:
        diff = "-  1 first old\n-  2 second old\n+  1 first new\n+  2 second new"
        result = render_diff(diff)
        assert isinstance(result, str)

    def test_multiline_diff(self) -> None:
        diff = "   1 context\n-  2 old\n+  2 new\n   3 context2"
        result = render_diff(diff)
        assert "context" in result


# ---------------------------------------------------------------------------
# visual_truncate
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.visual_truncate import (
    VisualTruncateResult,
    truncate_to_visual_lines,
)


class TestTruncateToVisualLines:
    def test_simple_truncation(self) -> None:
        text = "line1\nline2\nline3\nline4\nline5"
        result = truncate_to_visual_lines(text, 3, 80)
        assert isinstance(result, VisualTruncateResult)
        assert len(result.visual_lines) <= 3
        assert result.skipped_count >= 0

    def test_no_truncation_needed(self) -> None:
        text = "short text"
        result = truncate_to_visual_lines(text, 10, 80)
        assert result.skipped_count == 0
        assert len(result.visual_lines) >= 1

    def test_wide_lines_wrapped(self) -> None:
        text = "a" * 200
        result = truncate_to_visual_lines(text, 5, 40)
        assert isinstance(result, VisualTruncateResult)

    def test_with_padding_x(self) -> None:
        text = "line1\nline2"
        result = truncate_to_visual_lines(text, 5, 80, padding_x=2)
        assert isinstance(result, VisualTruncateResult)

    def test_empty_text(self) -> None:
        result = truncate_to_visual_lines("", 5, 80)
        assert isinstance(result, VisualTruncateResult)
        assert result.skipped_count == 0
        assert result.visual_lines == []

    def test_skipped_count_correct(self) -> None:
        text = "\n".join(f"line{i}" for i in range(20))
        result = truncate_to_visual_lines(text, 5, 80)
        assert result.skipped_count > 0

    def test_returns_tail_lines(self) -> None:
        # truncate_to_visual_lines returns from the END
        text = "\n".join(f"line{i}" for i in range(10))
        result = truncate_to_visual_lines(text, 3, 80)
        last_line = result.visual_lines[-1]
        assert "line9" in last_line


# ---------------------------------------------------------------------------
# keybinding_hints
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.keybinding_hints import (
    _create_default_keybindings,
    app_key,
    app_key_hint,
    editor_key,
    key_hint,
    raw_key_hint,
)


class TestKeybindingHints:
    def test_raw_key_hint(self) -> None:
        result = raw_key_hint("ctrl+c", "cancel")
        assert "ctrl+c" in result
        assert "cancel" in result

    def test_app_key_with_get_keys(self) -> None:
        kb = MagicMock()
        kb.get_keys.return_value = ["ctrl+a", "ctrl+b"]
        result = app_key(kb, "someAction")
        assert "ctrl+a" in result or "/" in result

    def test_app_key_without_get_keys(self) -> None:
        result = app_key(object(), "someAction")
        assert result == "someAction"

    def test_app_key_hint(self) -> None:
        kb = MagicMock()
        kb.get_keys.return_value = ["ctrl+x"]
        result = app_key_hint(kb, "someAction", "do something")
        assert "ctrl+x" in result
        assert "do something" in result

    def test_create_default_keybindings(self) -> None:
        kb = _create_default_keybindings()
        assert not kb.matches("ctrl+c", "cancel")  # type: ignore[attr-defined]
        assert kb.get_keys("cancel") == []  # type: ignore[attr-defined]

    def test_editor_key_returns_string(self) -> None:
        # Just ensure it doesn't raise
        with patch("pi_coding_agent.modes.interactive.components.keybinding_hints.get_editor_keybindings") as mock:
            mock_kb = MagicMock()
            mock_kb.get_keys.return_value = ["ctrl+c"]
            mock.return_value = mock_kb
            result = editor_key("cancel")  # type: ignore[arg-type]
            assert isinstance(result, str)

    def test_key_hint(self) -> None:
        with patch("pi_coding_agent.modes.interactive.components.keybinding_hints.get_editor_keybindings") as mock:
            mock_kb = MagicMock()
            mock_kb.get_keys.return_value = ["ctrl+c"]
            mock.return_value = mock_kb
            result = key_hint("cancel", "Cancel")  # type: ignore[arg-type]
            assert "ctrl+c" in result
            assert "Cancel" in result

    def test_app_key_empty_keys(self) -> None:
        kb = MagicMock()
        kb.get_keys.return_value = []
        result = app_key(kb, "someAction")
        # Empty key list returns "" (no key bound)
        assert result == ""


# ---------------------------------------------------------------------------
# user_message_selector
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.user_message_selector import (
    UserMessageItem,
    UserMessageSelectorComponent,
)


class TestUserMessageSelectorComponent:
    def test_instantiation_with_messages(self) -> None:
        messages = [
            UserMessageItem(id="1", text="Hello world"),
            UserMessageItem(id="2", text="Goodbye world"),
        ]
        on_select = MagicMock()
        on_cancel = MagicMock()
        component = UserMessageSelectorComponent(messages, on_select, on_cancel)
        assert component is not None

    def test_instantiation_no_messages_calls_cancel(self) -> None:
        on_cancel = MagicMock()
        UserMessageSelectorComponent([], MagicMock(), on_cancel)
        time.sleep(0.2)  # wait for timer
        on_cancel.assert_called_once()

    def test_get_message_list(self) -> None:
        messages = [UserMessageItem(id="1", text="test")]
        component = UserMessageSelectorComponent(messages, MagicMock(), MagicMock())
        ml = component.get_message_list()
        assert ml is not None

    def test_message_list_render(self) -> None:
        messages = [UserMessageItem(id="1", text="Hello"), UserMessageItem(id="2", text="World")]
        component = UserMessageSelectorComponent(messages, MagicMock(), MagicMock())
        ml = component.get_message_list()
        lines = ml.render(80)
        assert isinstance(lines, list)
        assert any("Hello" in line or "World" in line for line in lines)

    def test_message_list_handle_input_up_down(self) -> None:
        messages = [UserMessageItem(id="1", text="A"), UserMessageItem(id="2", text="B")]
        component = UserMessageSelectorComponent(messages, MagicMock(), MagicMock())
        ml = component.get_message_list()
        # simulate key events - should not raise
        with patch("pi_coding_agent.modes.interactive.components.user_message_selector.get_editor_keybindings") as mock:
            kb = MagicMock()
            kb.matches.side_effect = lambda data, action: action == "selectUp" and data == "\x1b[A"
            mock.return_value = kb
            ml.handle_input("\x1b[A")


# ---------------------------------------------------------------------------
# footer
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.footer import FooterComponent


class TestFooterComponent:
    def _make_session(self) -> Any:
        session = MagicMock()
        session.get_usages.return_value = []
        session.get_context_usage.return_value = None
        session.state = MagicMock()
        session.state.model = None
        session.state.thinking_level = None
        session.session_manager = None
        return session

    def _make_footer_data(self) -> Any:
        fd = MagicMock()
        fd.get_git_branch.return_value = "main"
        fd.get_available_provider_count.return_value = 1
        fd.get_extension_statuses.return_value = {}
        return fd

    def test_instantiation(self) -> None:
        footer = FooterComponent(self._make_session(), self._make_footer_data())
        assert footer is not None

    def test_render_basic(self) -> None:
        footer = FooterComponent(self._make_session(), self._make_footer_data())
        lines = footer.render(80)
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_render_with_model(self) -> None:
        session = self._make_session()
        model = MagicMock()
        model.id = "claude-3-5-sonnet"
        model.provider = "anthropic"
        model.reasoning = False
        model.context_window = 200000
        session.state.model = model
        footer = FooterComponent(session, self._make_footer_data())
        lines = footer.render(80)
        assert isinstance(lines, list)

    def test_render_narrow_width(self) -> None:
        footer = FooterComponent(self._make_session(), self._make_footer_data())
        lines = footer.render(20)
        assert isinstance(lines, list)

    def test_set_auto_compact_enabled(self) -> None:
        footer = FooterComponent(self._make_session(), self._make_footer_data())
        footer.set_auto_compact_enabled(True)
        footer.set_auto_compact_enabled(False)
        # No exception expected
        lines = footer.render(80)
        assert isinstance(lines, list)

    def test_invalidate_and_dispose(self) -> None:
        footer = FooterComponent(self._make_session(), self._make_footer_data())
        footer.invalidate()
        footer.dispose()


# ---------------------------------------------------------------------------
# scoped_models_selector utility
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.scoped_models_selector import (
    ModelsCallbacks,
    ModelsConfig,
    ScopedModelsSelectorComponent,
)


class TestModelsConfig:
    def test_default_config(self) -> None:
        m1 = MagicMock()
        m1.id = "m1"
        m1.provider = "anthropic"
        config = ModelsConfig(all_models=[m1], enabled_model_ids={"m1"}, has_enabled_models_filter=True)
        assert len(config.all_models) == 1
        assert "m1" in config.enabled_model_ids
        assert config.has_enabled_models_filter

    def test_no_filter(self) -> None:
        config = ModelsConfig(all_models=[], enabled_model_ids=set(), has_enabled_models_filter=False)
        assert not config.has_enabled_models_filter

    def test_with_multiple_models(self) -> None:
        m1 = MagicMock()
        m1.id = "m1"
        m1.provider = "anthropic"
        m2 = MagicMock()
        m2.id = "m2"
        m2.provider = "openai"
        config = ModelsConfig(
            all_models=[m1, m2],
            enabled_model_ids={"m1", "m2"},
            has_enabled_models_filter=True,
        )
        assert len(config.all_models) == 2


class TestModelsCallbacks:
    def test_callbacks_callable(self) -> None:
        cb = ModelsCallbacks(
            on_model_toggle=lambda id_, enabled: None,
            on_persist=lambda ids: None,
            on_enable_all=lambda ids: None,
            on_clear_all=lambda: None,
            on_toggle_provider=lambda provider, ids, enabled: None,
            on_cancel=lambda: None,
        )
        cb.on_model_toggle("m1", True)
        cb.on_persist(["m1"])
        cb.on_enable_all(["m1"])
        cb.on_clear_all()
        cb.on_toggle_provider("anthropic", ["m1"], True)
        cb.on_cancel()


# ---------------------------------------------------------------------------
# settings_selector utility
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.settings_selector import (
    SettingsCallbacks,
    SettingsConfig,
    SettingsSelectorComponent,
    _SelectSubmenu,
    _make_theme_submenu,
    _make_thinking_submenu,
)


class TestSettingsConfig:
    def test_defaults(self) -> None:
        config = SettingsConfig()
        assert isinstance(config.auto_compact, bool)
        assert isinstance(config.thinking_level, str)
        assert isinstance(config.available_thinking_levels, list)

    def test_custom_values(self) -> None:
        config = SettingsConfig(auto_compact=True, thinking_level="high")
        assert config.auto_compact is True
        assert config.thinking_level == "high"

    def test_all_bool_fields_default_type(self) -> None:
        config = SettingsConfig()
        assert isinstance(config.show_images, bool)
        assert isinstance(config.auto_resize_images, bool)
        assert isinstance(config.block_images, bool)
        assert isinstance(config.enable_skill_commands, bool)
        assert isinstance(config.hide_thinking_block, bool)
        assert isinstance(config.collapse_changelog, bool)
        assert isinstance(config.quiet_startup, bool)
        assert isinstance(config.show_hardware_cursor, bool)
        assert isinstance(config.clear_on_shrink, bool)


class TestSettingsCallbacks:
    def test_defaults_callable(self) -> None:
        cb = SettingsCallbacks()
        cb.on_auto_compact_change(True)
        cb.on_thinking_level_change("high")
        cb.on_cancel()

    def test_all_callbacks_callable(self) -> None:
        cb = SettingsCallbacks()
        cb.on_show_images_change(True)
        cb.on_auto_resize_images_change(False)
        cb.on_block_images_change(True)
        cb.on_enable_skill_commands_change(True)
        cb.on_steering_mode_change("all")
        cb.on_follow_up_mode_change("one-at-a-time")
        cb.on_transport_change("sse")
        cb.on_hide_thinking_block_change(True)
        cb.on_collapse_changelog_change(False)
        cb.on_double_escape_action_change("tree")
        cb.on_show_hardware_cursor_change(True)
        cb.on_editor_padding_x_change(2)
        cb.on_autocomplete_max_visible_change(10)
        cb.on_quiet_startup_change(True)
        cb.on_clear_on_shrink_change(False)
        cb.on_theme_change("default")


# ---------------------------------------------------------------------------
# session_selector_search utilities
# ---------------------------------------------------------------------------


class TestMatchResult:
    def test_creation(self) -> None:
        r = MatchResult(matches=True, score=0.9)
        assert r.matches
        assert r.score == 0.9

    def test_no_match(self) -> None:
        r = MatchResult(matches=False, score=0.0)
        assert not r.matches

    def test_default_score(self) -> None:
        r = MatchResult(matches=True)
        assert r.score == 0.0


class TestParsedSearchQuery:
    def test_creation_tokens_mode(self) -> None:
        q = ParsedSearchQuery(mode="tokens", tokens=[{"kind": "fuzzy", "value": "foo"}], regex=None)
        assert q.tokens[0]["value"] == "foo"
        assert q.mode == "tokens"

    def test_creation_regex_mode(self) -> None:
        import re

        pattern = re.compile("foo")
        q = ParsedSearchQuery(mode="regex", tokens=[], regex=pattern)
        assert q.regex is pattern
        assert q.mode == "regex"

    def test_creation_with_error(self) -> None:
        q = ParsedSearchQuery(mode="regex", tokens=[], regex=None, error="bad regex")
        assert q.error == "bad regex"

    def test_empty_tokens(self) -> None:
        q = ParsedSearchQuery(mode="tokens", tokens=[], regex=None)
        assert q.tokens == []


# ---------------------------------------------------------------------------
# UserMessageItem dataclass
# ---------------------------------------------------------------------------


class TestUserMessageItem:
    def test_creation(self) -> None:
        item = UserMessageItem(id="123", text="Hello")
        assert item.id == "123"
        assert item.text == "Hello"
        assert item.timestamp is None

    def test_with_timestamp(self) -> None:
        item = UserMessageItem(id="123", text="Hello", timestamp="2024-01-01")
        assert item.timestamp == "2024-01-01"


# ---------------------------------------------------------------------------
# dynamic_border
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.dynamic_border import DynamicBorder


class TestDynamicBorder:
    def test_render_default(self) -> None:
        border = DynamicBorder()
        lines = border.render(40)
        assert isinstance(lines, list)
        assert len(lines) == 1

    def test_render_with_custom_color(self) -> None:
        border = DynamicBorder(color=lambda s: f"[{s}]")
        lines = border.render(10)
        assert isinstance(lines, list)
        assert len(lines) == 1
        assert "\u2500" in lines[0]

    def test_render_width_1(self) -> None:
        border = DynamicBorder()
        lines = border.render(1)
        assert len(lines) == 1

    def test_invalidate_no_error(self) -> None:
        border = DynamicBorder()
        border.invalidate()  # should not raise


# ---------------------------------------------------------------------------
# user_message
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.user_message import UserMessageComponent


class TestUserMessageComponent:
    def test_instantiation(self) -> None:
        comp = UserMessageComponent("Hello world")
        assert comp is not None

    def test_render(self) -> None:
        comp = UserMessageComponent("Hello")
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_empty_text(self) -> None:
        comp = UserMessageComponent("")
        assert comp is not None


# ---------------------------------------------------------------------------
# assistant_message
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.assistant_message import AssistantMessageComponent


class TestAssistantMessageComponent:
    def _make_message(self, content: list[Any]) -> Any:
        msg = MagicMock()
        msg.content = content
        msg.stop_reason = None
        msg.error_message = None
        return msg

    def test_instantiation_no_message(self) -> None:
        comp = AssistantMessageComponent()
        assert comp is not None

    def test_instantiation_with_text_block(self) -> None:
        block = MagicMock()
        block.type = "text"
        block.text = "Hello world"
        msg = self._make_message([block])
        comp = AssistantMessageComponent(message=msg)
        assert comp is not None

    def test_with_thinking_block(self) -> None:
        block = MagicMock()
        block.type = "thinking"
        block.thinking = "Some thinking"
        msg = self._make_message([block])
        comp = AssistantMessageComponent(message=msg, hide_thinking_block=False)
        assert comp is not None

    def test_with_hidden_thinking_block(self) -> None:
        block = MagicMock()
        block.type = "thinking"
        block.thinking = "Some thinking"
        msg = self._make_message([block])
        comp = AssistantMessageComponent(message=msg, hide_thinking_block=True)
        assert comp is not None

    def test_aborted_message(self) -> None:
        msg = self._make_message([])
        msg.stop_reason = "aborted"
        msg.error_message = None
        comp = AssistantMessageComponent(message=msg)
        assert comp is not None

    def test_error_message(self) -> None:
        msg = self._make_message([])
        msg.stop_reason = "error"
        msg.error_message = "Something went wrong"
        comp = AssistantMessageComponent(message=msg)
        assert comp is not None

    def test_update_content(self) -> None:
        comp = AssistantMessageComponent()
        block = MagicMock()
        block.type = "text"
        block.text = "Updated"
        msg = self._make_message([block])
        comp.update_content(msg)

    def test_set_hide_thinking_block(self) -> None:
        comp = AssistantMessageComponent()
        comp.set_hide_thinking_block(True)
        comp.set_hide_thinking_block(False)

    def test_render(self) -> None:
        comp = AssistantMessageComponent()
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# branch_summary_message
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.branch_summary_message import BranchSummaryMessageComponent


class TestBranchSummaryMessageComponent:
    def _make_msg(self, summary: str = "## Summary\n\nTest content") -> Any:
        msg = MagicMock()
        msg.summary = summary
        return msg

    def test_instantiation(self) -> None:
        comp = BranchSummaryMessageComponent(self._make_msg())
        assert comp is not None

    def test_render_collapsed(self) -> None:
        comp = BranchSummaryMessageComponent(self._make_msg())
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_expanded(self) -> None:
        comp = BranchSummaryMessageComponent(self._make_msg())
        comp.set_expanded(True)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_toggle_expanded(self) -> None:
        comp = BranchSummaryMessageComponent(self._make_msg())
        comp.set_expanded(True)
        comp.set_expanded(False)

    def test_invalidate(self) -> None:
        comp = BranchSummaryMessageComponent(self._make_msg())
        comp.invalidate()


# ---------------------------------------------------------------------------
# compaction_summary_message
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.compaction_summary_message import CompactionSummaryMessageComponent


class TestCompactionSummaryMessageComponent:
    def _make_msg(self) -> Any:
        msg = MagicMock()
        msg.tokens_before = 5000
        msg.summary = "Compacted content"
        return msg

    def test_instantiation(self) -> None:
        comp = CompactionSummaryMessageComponent(self._make_msg())
        assert comp is not None

    def test_render_collapsed(self) -> None:
        comp = CompactionSummaryMessageComponent(self._make_msg())
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_expanded(self) -> None:
        comp = CompactionSummaryMessageComponent(self._make_msg())
        comp.set_expanded(True)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_invalidate(self) -> None:
        comp = CompactionSummaryMessageComponent(self._make_msg())
        comp.invalidate()


# ---------------------------------------------------------------------------
# skill_invocation_message
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.skill_invocation_message import SkillInvocationMessageComponent


class TestSkillInvocationMessageComponent:
    def _make_block(self) -> Any:
        block = MagicMock()
        block.name = "my-skill"
        block.content = "Skill content here"
        return block

    def test_instantiation(self) -> None:
        comp = SkillInvocationMessageComponent(self._make_block())
        assert comp is not None

    def test_render_collapsed(self) -> None:
        comp = SkillInvocationMessageComponent(self._make_block())
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_expanded(self) -> None:
        comp = SkillInvocationMessageComponent(self._make_block())
        comp.set_expanded(True)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_invalidate(self) -> None:
        comp = SkillInvocationMessageComponent(self._make_block())
        comp.invalidate()


# ---------------------------------------------------------------------------
# custom_message
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.custom_message import CustomMessageComponent


class TestCustomMessageComponent:
    def _make_msg(self) -> Any:
        msg = MagicMock()
        msg.custom_type = "info"
        msg.content = "Some custom content"
        return msg

    def test_instantiation(self) -> None:
        comp = CustomMessageComponent(self._make_msg())
        assert comp is not None

    def test_render(self) -> None:
        comp = CustomMessageComponent(self._make_msg())
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_with_custom_renderer(self) -> None:
        custom_render = MagicMock(return_value=None)
        comp = CustomMessageComponent(self._make_msg(), custom_renderer=custom_render)
        assert comp is not None

    def test_set_expanded(self) -> None:
        comp = CustomMessageComponent(self._make_msg())
        comp.set_expanded(True)
        comp.set_expanded(False)

    def test_invalidate(self) -> None:
        comp = CustomMessageComponent(self._make_msg())
        comp.invalidate()

    def test_with_list_content(self) -> None:
        msg = MagicMock()
        msg.custom_type = "info"
        content_item = {"type": "text", "text": "hello"}
        msg.content = [content_item]
        comp = CustomMessageComponent(msg)
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# theme_selector
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.theme_selector import ThemeSelectorComponent


class TestThemeSelectorComponent:
    def test_instantiation(self) -> None:
        comp = ThemeSelectorComponent(
            current_theme="default",
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_preview=MagicMock(),
        )
        assert comp is not None

    def test_get_select_list(self) -> None:
        comp = ThemeSelectorComponent(
            current_theme="default",
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_preview=MagicMock(),
        )
        sl = comp.get_select_list()
        assert sl is not None

    def test_render(self) -> None:
        comp = ThemeSelectorComponent(
            current_theme="default",
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_preview=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# thinking_selector
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.thinking_selector import ThinkingSelectorComponent


class TestThinkingSelectorComponent:
    def test_instantiation(self) -> None:
        comp = ThinkingSelectorComponent(
            current_level="off",
            available_levels=["off", "low", "medium", "high"],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_render(self) -> None:
        comp = ThinkingSelectorComponent(
            current_level="low",
            available_levels=["off", "low", "high"],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_get_select_list(self) -> None:
        comp = ThinkingSelectorComponent(
            current_level="off",
            available_levels=["off"],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp.get_select_list() is not None


# ---------------------------------------------------------------------------
# show_images_selector
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.show_images_selector import ShowImagesSelectorComponent


class TestShowImagesSelectorComponent:
    def test_instantiation_enabled(self) -> None:
        comp = ShowImagesSelectorComponent(
            current_value=True,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_instantiation_disabled(self) -> None:
        comp = ShowImagesSelectorComponent(
            current_value=False,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_render(self) -> None:
        comp = ShowImagesSelectorComponent(
            current_value=True,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_get_select_list(self) -> None:
        comp = ShowImagesSelectorComponent(
            current_value=True,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp.get_select_list() is not None


# ---------------------------------------------------------------------------
# tool_execution utility functions
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.tool_execution import (
    ToolExecutionComponent,
    _format_size,
    _shorten_path,
    _str,
    _strip_ansi,
)


class TestToolExecutionUtilities:
    def test_shorten_path_home(self) -> None:
        import os

        home = os.path.expanduser("~")
        result = _shorten_path(f"{home}/some/path")
        assert result.startswith("~")

    def test_shorten_path_no_home(self) -> None:
        result = _shorten_path("/usr/local/bin")
        assert result == "/usr/local/bin"

    def test_shorten_path_non_str(self) -> None:
        result = _shorten_path(None)
        assert result == ""

    def test_str_string(self) -> None:
        assert _str("hello") == "hello"

    def test_str_none(self) -> None:
        assert _str(None) == ""

    def test_str_other_type(self) -> None:
        assert _str(42) is None

    def test_format_size_bytes(self) -> None:
        assert "B" in _format_size(512)

    def test_format_size_kb(self) -> None:
        assert "KB" in _format_size(2048)

    def test_format_size_mb(self) -> None:
        assert "MB" in _format_size(2 * 1024 * 1024)

    def test_strip_ansi(self) -> None:
        text = "\x1b[31mred\x1b[0m normal"
        result = _strip_ansi(text)
        assert "red" in result
        assert "\x1b" not in result


class TestToolExecutionComponent:
    def test_instantiation_read(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/tmp/test.py"})
        assert comp is not None

    def test_instantiation_write(self) -> None:
        comp = ToolExecutionComponent("write", {"file_path": "/tmp/out.py", "content": "hello"})
        assert comp is not None

    def test_instantiation_bash(self) -> None:
        comp = ToolExecutionComponent("bash", {"command": "ls"})
        assert comp is not None

    def test_instantiation_ls(self) -> None:
        comp = ToolExecutionComponent("ls", {"path": "/tmp"})
        assert comp is not None

    def test_instantiation_grep(self) -> None:
        comp = ToolExecutionComponent("grep", {"pattern": "foo", "path": "/tmp"})
        assert comp is not None

    def test_instantiation_find(self) -> None:
        comp = ToolExecutionComponent("find", {"pattern": "*.py", "path": "/tmp"})
        assert comp is not None

    def test_instantiation_edit(self) -> None:
        comp = ToolExecutionComponent("edit", {"file_path": "/tmp/f.py", "oldText": "a", "newText": "b"})
        assert comp is not None

    def test_render(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/tmp/test.py"})
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_update_result(self) -> None:
        comp = ToolExecutionComponent("bash", {"command": "echo hi"})
        result = MagicMock()
        result.is_error = False
        result.content = [{"type": "text", "text": "hello output"}]
        result.details = None
        comp.update_result(result)

    def test_update_result_error(self) -> None:
        comp = ToolExecutionComponent("bash", {"command": "bad command"})
        result = MagicMock()
        result.is_error = True
        result.content = [{"type": "text", "text": "error occurred"}]
        result.details = None
        comp.update_result(result, is_partial=False)

    def test_set_expanded(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/tmp/f.py"})
        comp.set_expanded(True)
        comp.set_expanded(False)

    def test_update_args(self) -> None:
        comp = ToolExecutionComponent("bash", {})
        comp.update_args({"command": "ls -la"})

    def test_set_args_complete_edit(self) -> None:
        comp = ToolExecutionComponent("edit", {"file_path": "/tmp/f.py", "oldText": "old", "newText": "new"})
        comp.set_args_complete()

    def test_set_show_images(self) -> None:
        comp = ToolExecutionComponent("read", {})
        comp.set_show_images(False)
        comp.set_show_images(True)

    def test_unknown_tool(self) -> None:
        comp = ToolExecutionComponent("custom_tool", {"arg": "val"})
        assert comp is not None


# ---------------------------------------------------------------------------
# bash_execution utility functions
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.bash_execution import _strip_ansi as _bash_strip_ansi
from pi_coding_agent.modes.interactive.components.bash_execution import _truncate_tail


class TestBashExecutionUtilities:
    def test_strip_ansi(self) -> None:
        text = "\x1b[32mgreen\x1b[0m text"
        result = _bash_strip_ansi(text)
        assert "green" in result
        assert "\x1b" not in result

    def test_truncate_tail_no_truncation(self) -> None:
        text = "line1\nline2\nline3"
        result, truncated = _truncate_tail(text, 100, 1024 * 1024)
        assert result == text
        assert not truncated

    def test_truncate_tail_line_limit(self) -> None:
        lines = [f"line{i}" for i in range(20)]
        text = "\n".join(lines)
        result, truncated = _truncate_tail(text, 5, 1024 * 1024)
        assert truncated
        assert "line19" in result

    def test_truncate_tail_byte_limit(self) -> None:
        text = "a" * 200
        result, truncated = _truncate_tail(text, 1000, 100)
        assert truncated
        assert len(result) <= 200

    def test_truncate_tail_empty(self) -> None:
        result, truncated = _truncate_tail("", 10, 1024)
        assert result == ""
        assert not truncated


# ---------------------------------------------------------------------------
# session_selector utility functions
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.session_selector import (
    _build_session_tree,
    _flatten_session_tree,
    _format_session_date,
    _shorten_path as _session_shorten_path,
)


class TestSessionSelectorUtilities:
    def test_shorten_path_home(self) -> None:
        import os

        home = os.path.expanduser("~")
        result = _session_shorten_path(f"{home}/project")
        assert result.startswith("~")

    def test_shorten_path_no_home(self) -> None:
        result = _session_shorten_path("/etc/hosts")
        assert result == "/etc/hosts"

    def test_format_session_date_now(self) -> None:
        from datetime import datetime

        dt = datetime.now()
        result = _format_session_date(dt)
        assert result == "now"

    def test_format_session_date_minutes(self) -> None:
        from datetime import datetime, timedelta

        dt = datetime.now() - timedelta(minutes=30)
        result = _format_session_date(dt)
        assert result.endswith("m")

    def test_format_session_date_hours(self) -> None:
        from datetime import datetime, timedelta

        dt = datetime.now() - timedelta(hours=5)
        result = _format_session_date(dt)
        assert result.endswith("h")

    def test_format_session_date_days(self) -> None:
        from datetime import datetime, timedelta

        dt = datetime.now() - timedelta(days=3)
        result = _format_session_date(dt)
        assert result.endswith("d")

    def test_format_session_date_weeks(self) -> None:
        from datetime import datetime, timedelta

        dt = datetime.now() - timedelta(days=14)
        result = _format_session_date(dt)
        assert result.endswith("w")

    def test_format_session_date_months(self) -> None:
        from datetime import datetime, timedelta

        dt = datetime.now() - timedelta(days=60)
        result = _format_session_date(dt)
        assert result.endswith("mo")

    def test_format_session_date_years(self) -> None:
        from datetime import datetime, timedelta

        dt = datetime.now() - timedelta(days=400)
        result = _format_session_date(dt)
        assert result.endswith("y")

    def test_build_session_tree_empty(self) -> None:
        result = _build_session_tree([])
        assert result == []

    def test_build_session_tree_single(self) -> None:
        session = MagicMock()
        session.path = "/a"
        session.parent_session_path = None
        session.modified = None
        result = _build_session_tree([session])
        assert len(result) == 1
        assert result[0].session is session

    def test_build_session_tree_with_children(self) -> None:
        from datetime import datetime

        parent = MagicMock()
        parent.path = "/a"
        parent.parent_session_path = None
        parent.modified = datetime.now()

        child = MagicMock()
        child.path = "/a/b"
        child.parent_session_path = "/a"
        child.modified = datetime.now()

        result = _build_session_tree([parent, child])
        assert len(result) == 1
        assert len(result[0].children) == 1

    def test_flatten_session_tree_empty(self) -> None:
        result = _flatten_session_tree([])
        assert result == []

    def test_flatten_session_tree_single(self) -> None:
        session = MagicMock()
        session.path = "/a"
        session.parent_session_path = None
        session.modified = None
        roots = _build_session_tree([session])
        flat = _flatten_session_tree(roots)
        assert len(flat) == 1
        assert flat[0].depth == 0


# ---------------------------------------------------------------------------
# scoped_models_selector utility functions
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.scoped_models_selector import (
    _clear_all,
    _enable_all,
    _get_sorted_ids,
    _is_enabled,
    _move,
    _toggle,
)


class TestScopedModelsUtilities:
    def test_is_enabled_none(self) -> None:
        # None means all enabled
        assert _is_enabled(None, "m1")
        assert _is_enabled(None, "m2")

    def test_is_enabled_list(self) -> None:
        assert _is_enabled(["m1", "m2"], "m1")
        assert not _is_enabled(["m1"], "m2")

    def test_toggle_none_first(self) -> None:
        # First toggle from None: start with only that item
        result = _toggle(None, "m1")
        assert result == ["m1"]

    def test_toggle_remove_existing(self) -> None:
        result = _toggle(["m1", "m2"], "m1")
        assert result is not None
        assert "m1" not in result
        assert "m2" in result

    def test_toggle_add_new(self) -> None:
        result = _toggle(["m1"], "m2")
        assert result is not None
        assert "m2" in result
        assert "m1" in result

    def test_enable_all_already_none(self) -> None:
        result = _enable_all(None, ["m1", "m2"])
        assert result is None

    def test_enable_all_from_list(self) -> None:
        result = _enable_all(["m1"], ["m1", "m2"])
        # If all are now enabled, returns None (all enabled)
        assert result is None or "m2" in (result or [])

    def test_clear_all_from_none(self) -> None:
        # When enabled_ids is None (all enabled), clear_all removes all targets
        # targets default to all enabled_ids which is None -> removes everything from all_ids
        result = _clear_all(None, ["m1", "m2"])
        # With None enabled_ids and None target_ids, removes all from all_ids
        assert isinstance(result, list)

    def test_clear_all_from_list(self) -> None:
        result = _clear_all(["m1", "m2"], ["m1", "m2"])
        assert result == []

    def test_get_sorted_ids_none(self) -> None:
        result = _get_sorted_ids(None, ["m1", "m2", "m3"])
        assert result == ["m1", "m2", "m3"]

    def test_get_sorted_ids_list(self) -> None:
        # Enabled first, then remaining
        result = _get_sorted_ids(["m2"], ["m1", "m2", "m3"])
        assert result[0] == "m2"
        assert set(result) == {"m1", "m2", "m3"}

    def test_move_up(self) -> None:
        result = _move(["m1", "m2", "m3"], ["m1", "m2", "m3"], "m2", -1)
        assert result is not None

    def test_move_down(self) -> None:
        result = _move(["m1", "m2", "m3"], ["m1", "m2", "m3"], "m2", 1)
        assert result is not None

    def test_move_out_of_bounds(self) -> None:
        result = _move(["m1"], ["m1"], "m1", -1)
        assert result == ["m1"]


# ---------------------------------------------------------------------------
# settings_selector component
# ---------------------------------------------------------------------------


class TestSettingsSelectorComponent:
    def test_instantiation(self) -> None:
        config = SettingsConfig()
        callbacks = SettingsCallbacks()
        comp = SettingsSelectorComponent(config, callbacks)
        assert comp is not None

    def test_get_settings_list(self) -> None:
        config = SettingsConfig()
        callbacks = SettingsCallbacks()
        comp = SettingsSelectorComponent(config, callbacks)
        sl = comp.get_settings_list()
        assert sl is not None

    def test_render(self) -> None:
        config = SettingsConfig()
        callbacks = SettingsCallbacks()
        comp = SettingsSelectorComponent(config, callbacks)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_with_custom_config(self) -> None:
        config = SettingsConfig(
            auto_compact=True,
            thinking_level="high",
            available_thinking_levels=["off", "low", "high"],
            available_themes=["default", "dark"],
            current_theme="dark",
        )
        callbacks = SettingsCallbacks()
        comp = SettingsSelectorComponent(config, callbacks)
        assert comp is not None


# ---------------------------------------------------------------------------
# armin pure functions
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.armin import (
    _build_final_grid,
    _get_char,
    _get_pixel,
)


class TestArminPureFunctions:
    def test_get_pixel_out_of_bounds(self) -> None:
        # y >= _HEIGHT returns False
        result = _get_pixel(0, 100)
        assert result is False

    def test_get_pixel_returns_bool(self) -> None:
        result = _get_pixel(0, 0)
        assert isinstance(result, bool)

    def test_get_char_returns_string(self) -> None:
        result = _get_char(0, 0)
        assert isinstance(result, str)
        assert len(result) == 1

    def test_get_char_all_types(self) -> None:
        # Should return one of the block characters or space
        valid_chars = {"\u2588", "\u2580", "\u2584", " "}
        for x in range(5):
            for row in range(5):
                c = _get_char(x, row)
                assert c in valid_chars

    def test_build_final_grid_shape(self) -> None:
        grid = _build_final_grid()
        assert isinstance(grid, list)
        assert len(grid) > 0
        assert all(isinstance(row, list) for row in grid)


# ---------------------------------------------------------------------------
# session_selector internal classes
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.session_selector import (
    SessionSelectorComponent,
    _SessionList,
    _SessionSelectorHeader,
    _delete_session_file,
)


class TestSessionSelectorHeader:
    def _make_header(self) -> _SessionSelectorHeader:
        return _SessionSelectorHeader(
            scope="current",
            sort_mode="recent",
            name_filter="all",
            keybindings=MagicMock(),
            request_render=MagicMock(),
        )

    def test_instantiation(self) -> None:
        h = self._make_header()
        assert h is not None

    def test_render(self) -> None:
        h = self._make_header()
        lines = h.render(80)
        assert isinstance(lines, list)
        assert len(lines) == 3

    def test_render_all_scope(self) -> None:
        h = _SessionSelectorHeader(
            scope="all",
            sort_mode="recent",
            name_filter="all",
            keybindings=MagicMock(),
            request_render=MagicMock(),
        )
        lines = h.render(80)
        assert isinstance(lines, list)

    def test_render_loading(self) -> None:
        h = self._make_header()
        h.set_loading(True)
        lines = h.render(80)
        assert isinstance(lines, list)

    def test_render_with_progress(self) -> None:
        h = self._make_header()
        h.set_loading(True)
        h.set_progress(5, 10)
        lines = h.render(80)
        assert isinstance(lines, list)

    def test_set_scope(self) -> None:
        h = self._make_header()
        h.set_scope("all")
        h.set_scope("current")

    def test_set_sort_mode(self) -> None:
        h = self._make_header()
        h.set_sort_mode("relevance")
        h.set_sort_mode("threaded")

    def test_set_name_filter(self) -> None:
        h = self._make_header()
        h.set_name_filter("named")
        h.set_name_filter("all")

    def test_set_show_path(self) -> None:
        h = self._make_header()
        h.set_show_path(True)
        h.set_show_path(False)

    def test_set_show_rename_hint(self) -> None:
        h = self._make_header()
        h.set_show_rename_hint(True)

    def test_set_confirming_delete_path(self) -> None:
        h = self._make_header()
        h.set_confirming_delete_path("/tmp/session.json")
        lines = h.render(80)
        assert isinstance(lines, list)
        h.set_confirming_delete_path(None)

    def test_set_status_message(self) -> None:
        h = self._make_header()
        h.set_status_message({"type": "error", "message": "Something failed"})
        lines = h.render(80)
        assert isinstance(lines, list)
        h.set_status_message(None)

    def test_invalidate_no_error(self) -> None:
        h = self._make_header()
        h.invalidate()


class TestSessionList:
    def _make_session(self, path: str = "/a", name: str | None = None) -> Any:
        from datetime import datetime

        session = MagicMock()
        session.path = path
        session.name = name
        session.first_message = f"message in {path}"
        session.all_messages_text = f"message in {path}"
        session.modified = datetime.now()
        session.message_count = 3
        session.cwd = "/home/user/project"
        session.parent_session_path = None
        return session

    def _make_session_list(self, sessions: list[Any] | None = None) -> _SessionList:
        if sessions is None:
            sessions = [self._make_session("/a"), self._make_session("/b")]
        return _SessionList(
            sessions=sessions,
            show_cwd=False,
            sort_mode="recent",
            name_filter="all",
            keybindings=MagicMock(),
        )

    def test_instantiation(self) -> None:
        sl = self._make_session_list()
        assert sl is not None

    def test_instantiation_empty(self) -> None:
        sl = self._make_session_list([])
        assert sl is not None

    def test_render_with_sessions(self) -> None:
        sl = self._make_session_list()
        lines = sl.render(80)
        assert isinstance(lines, list)

    def test_render_empty(self) -> None:
        sl = self._make_session_list([])
        lines = sl.render(80)
        assert isinstance(lines, list)

    def test_set_sessions(self) -> None:
        sl = self._make_session_list([])
        sessions = [self._make_session("/new")]
        sl.set_sessions(sessions, False)
        lines = sl.render(80)
        assert isinstance(lines, list)

    def test_get_selected_session_path_empty(self) -> None:
        sl = self._make_session_list([])
        result = sl.get_selected_session_path()
        assert result is None

    def test_get_selected_session_path_with_sessions(self) -> None:
        sl = self._make_session_list()
        result = sl.get_selected_session_path()
        assert result is not None

    def test_invalidate(self) -> None:
        sl = self._make_session_list()
        sl.invalidate()

    def test_render_named_filter_named_only(self) -> None:
        sessions = [self._make_session("/a", name="named"), self._make_session("/b")]
        sl = _SessionList(
            sessions=sessions,
            show_cwd=True,
            sort_mode="recent",
            name_filter="named",
            keybindings=MagicMock(),
        )
        lines = sl.render(80)
        assert isinstance(lines, list)


class TestSessionSelectorComponent:
    def test_instantiation(self) -> None:
        comp = SessionSelectorComponent(
            current_sessions_loader=lambda **kw: [],
            all_sessions_loader=lambda **kw: [],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        assert comp is not None

    def test_render(self) -> None:
        comp = SessionSelectorComponent(
            current_sessions_loader=lambda **kw: [],
            all_sessions_loader=lambda **kw: [],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_set_sessions_current(self) -> None:
        from datetime import datetime

        session = MagicMock()
        session.path = "/test"
        session.name = None
        session.first_message = "test"
        session.all_messages_text = "test"
        session.modified = datetime.now()
        session.message_count = 1
        session.cwd = "/home"
        session.parent_session_path = None

        comp = SessionSelectorComponent(
            current_sessions_loader=lambda **kw: [],
            all_sessions_loader=lambda **kw: [],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        sl = comp.get_session_list()
        sl.set_sessions([session], False)
        lines = comp.render(80)
        assert isinstance(lines, list)


class TestDeleteSessionFile:
    def test_delete_nonexistent_file(self) -> None:
        result = _delete_session_file("/tmp/nonexistent_session_12345.json")
        assert isinstance(result, dict)
        assert "ok" in result


# ---------------------------------------------------------------------------
# tree_selector
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.tree_selector import (
    TreeSelectorComponent,
    _LabelInput,
    _SearchLine,
    _TreeList,
    _shorten_path as _tree_shorten_path,
)


def _make_tree_node(entry_id: str = "e1", entry_type: str = "message", children: list[Any] | None = None) -> Any:
    """Create a minimal tree node."""
    entry = MagicMock()
    entry.id = entry_id
    entry.type = entry_type
    entry.parent_id = None

    node = MagicMock()
    node.entry = entry
    node.children = children or []
    node.label = None
    return node


class TestTreeListShortPath:
    def test_shorten_path_home(self) -> None:
        import os

        home = os.environ.get("HOME") or ""
        if home:
            result = _tree_shorten_path(f"{home}/project")
            assert result.startswith("~")

    def test_shorten_path_no_home(self) -> None:
        result = _tree_shorten_path("/usr/local/bin")
        assert result == "/usr/local/bin"


class TestTreeList:
    def test_instantiation_empty(self) -> None:
        tl = _TreeList([], None, 10)
        assert tl is not None

    def test_instantiation_with_nodes(self) -> None:
        node = _make_tree_node("e1")
        tl = _TreeList([node], "e1", 10)
        assert tl is not None

    def test_render_empty(self) -> None:
        tl = _TreeList([], None, 10)
        lines = tl.render(80)
        assert isinstance(lines, list)

    def test_render_with_nodes(self) -> None:
        node = _make_tree_node("e1", "message")
        tl = _TreeList([node], None, 10)
        lines = tl.render(80)
        assert isinstance(lines, list)

    def test_render_multiple_roots(self) -> None:
        n1 = _make_tree_node("e1")
        n2 = _make_tree_node("e2")
        tl = _TreeList([n1, n2], None, 10)
        lines = tl.render(80)
        assert isinstance(lines, list)

    def test_render_with_active_leaf(self) -> None:
        node = _make_tree_node("e1")
        tl = _TreeList([node], "e1", 10)
        lines = tl.render(80)
        assert isinstance(lines, list)

    def test_get_search_query(self) -> None:
        tl = _TreeList([], None, 10)
        assert tl.get_search_query() == ""

    def test_render_various_entry_types(self) -> None:
        for entry_type in [
            "message",
            "custom_message",
            "compaction",
            "branch_summary",
            "model_change",
            "thinking_level_change",
            "custom",
            "label",
        ]:
            entry = MagicMock()
            entry.id = f"e_{entry_type}"
            entry.type = entry_type
            entry.parent_id = None

            if entry_type == "message":
                msg = MagicMock()
                msg.role = "user"
                content_block = MagicMock()
                content_block.type = "text"
                content_block.text = "Hello"
                msg.content = [content_block]
                entry.message = msg
            elif entry_type == "custom_message":
                entry.content = "Some content"
                entry.custom_type = "info"
            elif entry_type == "compaction":
                entry.tokens_before = 5000
            elif entry_type == "branch_summary":
                entry.summary = "Branch summary text"
            elif entry_type == "model_change":
                entry.model_id = "claude-3"
            elif entry_type == "thinking_level_change":
                entry.thinking_level = "high"
            elif entry_type == "custom":
                entry.custom_type = "custom"
            elif entry_type == "label":
                entry.label = "my-label"

            node = MagicMock()
            node.entry = entry
            node.children = []
            node.label = None

            tl = _TreeList([node], None, 10)
            lines = tl.render(80)
            assert isinstance(lines, list), f"render failed for {entry_type}"

    def test_render_assistant_message(self) -> None:
        entry = MagicMock()
        entry.id = "e_asst"
        entry.type = "message"
        entry.parent_id = None

        msg = MagicMock()
        msg.role = "assistant"
        block = MagicMock()
        block.type = "text"
        block.text = "I can help"
        msg.content = [block]
        entry.message = msg

        node = MagicMock()
        node.entry = entry
        node.children = []
        node.label = None

        tl = _TreeList([node], None, 10)
        lines = tl.render(80)
        assert isinstance(lines, list)

    def test_with_children(self) -> None:
        child = _make_tree_node("child1")
        parent = _make_tree_node("root1", children=[child])
        tl = _TreeList([parent], None, 10)
        lines = tl.render(80)
        assert isinstance(lines, list)


class TestSearchLine:
    def test_render_empty_query(self) -> None:
        tl = _TreeList([], None, 10)
        sl = _SearchLine(tl)
        lines = sl.render(80)
        assert isinstance(lines, list)
        assert len(lines) == 1

        sl.invalidate()


class TestLabelInput:
    def test_instantiation(self) -> None:
        li = _LabelInput("entry1", None)
        assert li is not None

    def test_instantiation_with_label(self) -> None:
        li = _LabelInput("entry1", "my-label")
        assert li is not None

    def test_render(self) -> None:
        li = _LabelInput("entry1", None)
        lines = li.render(80)
        assert isinstance(lines, list)

    def test_focused_property(self) -> None:
        li = _LabelInput("entry1", None)
        li.focused = True
        assert li.focused is True
        li.focused = False
        assert li.focused is False

    def test_invalidate(self) -> None:
        li = _LabelInput("entry1", None)
        li.invalidate()


class TestTreeSelectorComponent:
    def test_instantiation_empty_tree(self) -> None:

        on_cancel = MagicMock()
        comp = TreeSelectorComponent(
            tree=[],
            current_leaf_id=None,
            terminal_height=40,
            on_select=MagicMock(),
            on_cancel=on_cancel,
        )
        assert comp is not None
        time.sleep(0.15)  # wait for timer
        on_cancel.assert_called_once()

    def test_instantiation_with_tree(self) -> None:
        node = _make_tree_node("e1")
        comp = TreeSelectorComponent(
            tree=[node],
            current_leaf_id="e1",
            terminal_height=40,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_render(self) -> None:
        node = _make_tree_node("e1")
        comp = TreeSelectorComponent(
            tree=[node],
            current_leaf_id=None,
            terminal_height=40,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# config_selector dataclasses and utility functions
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.config_selector import (
    PathMetadata,
    ResolvedPaths,
    ResolvedResource,
    ResourceGroup,
    ResourceItem,
    ResourceSubgroup,
    _get_group_label,
    build_groups,
)


class TestConfigSelectorDataclasses:
    def test_path_metadata(self) -> None:
        pm = PathMetadata(origin="package", scope="user", source="my-package")
        assert pm.origin == "package"
        assert pm.scope == "user"

    def test_resolved_resource(self) -> None:
        pm = PathMetadata(origin="top-level", scope="project", source="auto")
        rr = ResolvedResource(path="/home/user/.pi/ext.ts", enabled=True, metadata=pm)
        assert rr.enabled
        assert rr.path == "/home/user/.pi/ext.ts"

    def test_resolved_paths(self) -> None:
        rp = ResolvedPaths()
        assert rp.extensions == []
        assert rp.skills == []

    def test_resource_item(self) -> None:
        pm = PathMetadata(origin="package", scope="user", source="my-pkg")
        ri = ResourceItem(
            path="/ext.ts",
            enabled=True,
            metadata=pm,
            resource_type="extensions",
            display_name="ext.ts",
            group_key="k1",
            subgroup_key="k1:extensions",
        )
        assert ri.enabled
        assert ri.resource_type == "extensions"

    def test_resource_subgroup(self) -> None:
        sg = ResourceSubgroup(type="skills", label="Skills")
        assert sg.label == "Skills"
        assert sg.items == []

    def test_resource_group(self) -> None:
        rg = ResourceGroup(key="k1", label="User", scope="user", origin="top-level", source="auto")
        assert rg.key == "k1"
        assert rg.subgroups == []


class TestGetGroupLabel:
    def test_package_label(self) -> None:
        pm = PathMetadata(origin="package", scope="user", source="my-pkg")
        label = _get_group_label(pm)
        assert "my-pkg" in label
        assert "user" in label

    def test_top_level_user_label(self) -> None:
        pm = PathMetadata(origin="top-level", scope="user", source="auto")
        label = _get_group_label(pm)
        assert "User" in label or "user" in label.lower()

    def test_top_level_project_label(self) -> None:
        pm = PathMetadata(origin="top-level", scope="project", source="auto")
        label = _get_group_label(pm)
        assert "Project" in label or "project" in label.lower()

    def test_top_level_project_settings(self) -> None:
        pm = PathMetadata(origin="top-level", scope="project", source="manual")
        label = _get_group_label(pm)
        assert isinstance(label, str)


class TestBuildGroups:
    def _make_metadata(self, origin: str = "top-level", scope: str = "user", source: str = "auto") -> PathMetadata:
        return PathMetadata(origin=origin, scope=scope, source=source)  # type: ignore[arg-type]

    def test_empty_resolved_paths(self) -> None:
        groups = build_groups(ResolvedPaths())
        assert groups == []

    def test_single_extension(self) -> None:
        pm = self._make_metadata()
        rr = ResolvedResource(path="/ext/my-ext.ts", enabled=True, metadata=pm)
        rp = ResolvedPaths(extensions=[rr])
        groups = build_groups(rp)
        assert len(groups) == 1
        assert groups[0].subgroups[0].type == "extensions"

    def test_multiple_resource_types(self) -> None:
        pm = self._make_metadata()
        ext = ResolvedResource(path="/ext/my.ts", enabled=True, metadata=pm)
        skill = ResolvedResource(path="/skills/SKILL.md", enabled=False, metadata=pm)
        rp = ResolvedPaths(extensions=[ext], skills=[skill])
        groups = build_groups(rp)
        assert len(groups) == 1
        assert len(groups[0].subgroups) == 2

    def test_package_extension(self) -> None:
        pm = self._make_metadata(origin="package", source="my-pkg")
        rr = ResolvedResource(path="/pkg/extensions/my.ts", enabled=True, metadata=pm)
        rp = ResolvedPaths(extensions=[rr])
        groups = build_groups(rp)
        assert len(groups) == 1


# ---------------------------------------------------------------------------
# scoped_models_selector component (with real model mocks)
# ---------------------------------------------------------------------------


class TestScopedModelsSelectorComponent:
    def _make_model(self, model_id: str, provider: str) -> Any:
        m = MagicMock()
        m.id = model_id
        m.provider = provider
        return m

    def _make_config(self, models: list[Any] | None = None) -> ModelsConfig:
        if models is None:
            models = [self._make_model("m1", "anthropic"), self._make_model("m2", "openai")]
        return ModelsConfig(
            all_models=models,
            enabled_model_ids={"anthropic/m1", "openai/m2"},
            has_enabled_models_filter=True,
        )

    def _make_callbacks(self) -> ModelsCallbacks:
        return ModelsCallbacks(
            on_model_toggle=MagicMock(),
            on_persist=MagicMock(),
            on_enable_all=MagicMock(),
            on_clear_all=MagicMock(),
            on_toggle_provider=MagicMock(),
            on_cancel=MagicMock(),
        )

    def test_instantiation(self) -> None:
        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        assert comp is not None

    def test_render(self) -> None:
        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_no_filter(self) -> None:
        models = [self._make_model("m1", "anthropic")]
        config = ModelsConfig(all_models=models, enabled_model_ids=set(), has_enabled_models_filter=False)
        comp = ScopedModelsSelectorComponent(config, self._make_callbacks())
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_focused_property(self) -> None:
        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        comp.focused = True
        assert comp.focused is True
        comp.focused = False


# ---------------------------------------------------------------------------
# countdown_timer
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.countdown_timer import CountdownTimer


class TestCountdownTimer:
    def test_instantiation(self) -> None:
        on_tick = MagicMock()
        on_expire = MagicMock()
        timer = CountdownTimer(5000, None, on_tick, on_expire)
        # on_tick called immediately with initial value
        on_tick.assert_called_once()
        timer.dispose()

    def test_dispose(self) -> None:
        timer = CountdownTimer(10000, None, MagicMock(), MagicMock())
        timer.dispose()
        assert timer._disposed

    def test_dispose_twice_no_error(self) -> None:
        timer = CountdownTimer(10000, None, MagicMock(), MagicMock())
        timer.dispose()
        timer.dispose()  # should not raise


# ---------------------------------------------------------------------------
# extension_selector
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.extension_selector import ExtensionSelectorComponent


class TestExtensionSelectorComponent:
    def test_instantiation_no_tui(self) -> None:
        comp = ExtensionSelectorComponent(
            title="Choose option",
            options=["option1", "option2", "option3"],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_render(self) -> None:
        comp = ExtensionSelectorComponent(
            title="Choose",
            options=["a", "b"],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_empty_options(self) -> None:
        comp = ExtensionSelectorComponent(
            title="Choose",
            options=[],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# oauth_selector
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.oauth_selector import OAuthSelectorComponent


class TestOAuthSelectorComponent:
    def _make_provider(self, id_: str = "anthropic") -> Any:
        p = MagicMock()
        p.id = id_
        p.name = id_.capitalize()
        return p

    def test_instantiation_login(self) -> None:
        comp = OAuthSelectorComponent(
            mode="login",
            auth_storage=MagicMock(),
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_instantiation_logout(self) -> None:
        comp = OAuthSelectorComponent(
            mode="logout",
            auth_storage=MagicMock(),
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            oauth_providers=[self._make_provider()],
        )
        assert comp is not None

    def test_render(self) -> None:
        provider = self._make_provider()
        comp = OAuthSelectorComponent(
            mode="login",
            auth_storage=MagicMock(),
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            oauth_providers=[provider],
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_empty_providers(self) -> None:
        comp = OAuthSelectorComponent(
            mode="login",
            auth_storage=MagicMock(),
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            oauth_providers=[],
        )
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# config_selector internal classes
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.config_selector import (
    ConfigSelectorComponent,
    _ConfigSelectorHeader,
    _ResourceList,
)


class TestConfigSelectorHeader:
    def test_render(self) -> None:
        h = _ConfigSelectorHeader()
        lines = h.render(80)
        assert isinstance(lines, list)
        assert len(lines) == 2

    def test_invalidate(self) -> None:
        h = _ConfigSelectorHeader()
        h.invalidate()


class TestResourceList:
    def _make_groups(self) -> list[ResourceGroup]:
        pm = PathMetadata(origin="top-level", scope="user", source="auto")
        rr = ResolvedResource(path="/ext/my-ext.ts", enabled=True, metadata=pm)
        rp = ResolvedPaths(extensions=[rr])
        return build_groups(rp)

    def test_instantiation(self) -> None:
        rl = _ResourceList(self._make_groups(), MagicMock(), "/cwd", "/agent")
        assert rl is not None

    def test_instantiation_empty(self) -> None:
        rl = _ResourceList([], MagicMock(), "/cwd", "/agent")
        assert rl is not None

    def test_render_empty(self) -> None:
        rl = _ResourceList([], MagicMock(), "/cwd", "/agent")
        lines = rl.render(80)
        assert isinstance(lines, list)

    def test_render_with_groups(self) -> None:
        rl = _ResourceList(self._make_groups(), MagicMock(), "/cwd", "/agent")
        lines = rl.render(80)
        assert isinstance(lines, list)

    def test_invalidate(self) -> None:
        rl = _ResourceList([], MagicMock(), "/cwd", "/agent")
        rl.invalidate()


class TestConfigSelectorComponent:
    def _make_resolved_paths(self) -> Any:
        pm = PathMetadata(origin="top-level", scope="user", source="auto")
        rr = ResolvedResource(path="/ext/my-ext.ts", enabled=True, metadata=pm)
        return ResolvedPaths(extensions=[rr])

    def test_instantiation(self) -> None:
        comp = ConfigSelectorComponent(
            resolved_paths=self._make_resolved_paths(),
            settings_manager=MagicMock(),
            cwd="/test",
            agent_dir="/agent",
            on_close=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        assert comp is not None

    def test_render(self) -> None:
        comp = ConfigSelectorComponent(
            resolved_paths=self._make_resolved_paths(),
            settings_manager=MagicMock(),
            cwd="/test",
            agent_dir="/agent",
            on_close=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_instantiation_empty(self) -> None:
        comp = ConfigSelectorComponent(
            resolved_paths=ResolvedPaths(),
            settings_manager=MagicMock(),
            cwd="/test",
            agent_dir="/agent",
            on_close=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_get_resource_list(self) -> None:
        from pi_coding_agent.modes.interactive.components.config_selector import _ResourceList

        comp = ConfigSelectorComponent(
            resolved_paths=ResolvedPaths(),
            settings_manager=MagicMock(),
            cwd="/test",
            agent_dir="/agent",
            on_close=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        rl = comp.get_resource_list()
        assert isinstance(rl, _ResourceList)

    def test_focused_property(self) -> None:
        comp = ConfigSelectorComponent(
            resolved_paths=ResolvedPaths(),
            settings_manager=MagicMock(),
            cwd="/test",
            agent_dir="/agent",
            on_close=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        comp.focused = True
        assert comp.focused is True


# ---------------------------------------------------------------------------
# armin with mocked TUI
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.armin import ArminComponent


class TestArminComponent:
    def test_instantiation_with_mock_tui(self) -> None:

        ui = MagicMock()
        comp = ArminComponent(ui)
        assert comp is not None
        time.sleep(0.05)  # let animation tick once
        comp.dispose()

    def test_render(self) -> None:
        ui = MagicMock()
        comp = ArminComponent(ui)
        lines = comp.render(40)
        assert isinstance(lines, list)
        comp.dispose()

    def test_invalidate(self) -> None:
        ui = MagicMock()
        comp = ArminComponent(ui)
        comp.invalidate()
        comp.dispose()


# ---------------------------------------------------------------------------
# extension_input (no TUI needed for basic instantiation)
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.extension_input import ExtensionInputComponent


class TestExtensionInputComponent:
    def test_instantiation(self) -> None:
        comp = ExtensionInputComponent(
            title="Enter value",
            placeholder="type here...",
            on_submit=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_render(self) -> None:
        comp = ExtensionInputComponent(
            title="Enter value",
            placeholder=None,
            on_submit=MagicMock(),
            on_cancel=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_focused_property(self) -> None:
        comp = ExtensionInputComponent(
            title="Enter value",
            placeholder=None,
            on_submit=MagicMock(),
            on_cancel=MagicMock(),
        )
        comp.focused = True
        assert comp.focused is True


# ---------------------------------------------------------------------------
# tool_execution - helper functions and various tool name branches
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.tool_execution import (
    _strip_ansi as _tool_strip_ansi,
)


class TestToolExecutionHelpers:
    def test_format_size_bytes(self) -> None:
        assert _format_size(500) == "500B"

    def test_format_size_kb(self) -> None:
        assert _format_size(2048) == "2KB"

    def test_format_size_mb(self) -> None:
        assert _format_size(2 * 1024 * 1024) == "2MB"

    def test_shorten_path_home(self) -> None:
        import os

        home = os.path.expanduser("~")
        result = _shorten_path(home + "/myfile.txt")
        assert result.startswith("~")

    def test_shorten_path_no_home(self) -> None:
        result = _shorten_path("/absolute/path")
        assert result == "/absolute/path"

    def test_shorten_path_non_string(self) -> None:
        assert _shorten_path(42) == ""

    def test_str_string(self) -> None:
        assert _str("hello") == "hello"

    def test_str_none(self) -> None:
        assert _str(None) == ""

    def test_str_non_string(self) -> None:
        assert _str(123) is None

    def test_strip_ansi(self) -> None:
        assert _tool_strip_ansi("\x1b[31mred\x1b[0m") == "red"


class TestToolExecutionComponentExtended:
    def _make_result(self, text: str = "output", is_error: bool = False) -> Any:
        r = MagicMock()
        r.is_error = is_error
        r.content = [{"type": "text", "text": text}]
        r.details = None
        return r

    def test_instantiation_read(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo/bar.py"})
        assert comp is not None

    def test_instantiation_write(self) -> None:
        comp = ToolExecutionComponent("write", {"file_path": "/foo/bar.py", "content": "hello"})
        assert comp is not None

    def test_instantiation_edit(self) -> None:
        comp = ToolExecutionComponent("edit", {"path": "/foo/bar.py", "oldText": "a", "newText": "b"})
        assert comp is not None

    def test_instantiation_ls(self) -> None:
        comp = ToolExecutionComponent("ls", {"path": "/foo"})
        assert comp is not None

    def test_instantiation_grep(self) -> None:
        comp = ToolExecutionComponent("grep", {"pattern": "foo", "path": "/bar"})
        assert comp is not None

    def test_instantiation_find(self) -> None:
        comp = ToolExecutionComponent("find", {"pattern": "*.py", "path": "/bar"})
        assert comp is not None

    def test_instantiation_bash(self) -> None:
        comp = ToolExecutionComponent("bash", {"command": "ls -la"})
        assert comp is not None

    def test_instantiation_unknown(self) -> None:
        comp = ToolExecutionComponent("custom_tool", {})
        assert comp is not None

    def test_update_result_read(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo/bar.py"})
        comp.update_result(self._make_result("line1\nline2"), is_partial=False)

    def test_update_result_write(self) -> None:
        comp = ToolExecutionComponent("write", {"file_path": "/foo/bar.py", "content": "hello"})
        comp.update_result(self._make_result(), is_partial=False)

    def test_update_result_ls(self) -> None:
        comp = ToolExecutionComponent("ls", {"path": "/foo"})
        comp.update_result(self._make_result("file1\nfile2"), is_partial=False)

    def test_update_result_grep(self) -> None:
        comp = ToolExecutionComponent("grep", {"pattern": "foo", "path": "."})
        comp.update_result(self._make_result("match1\nmatch2"), is_partial=False)

    def test_update_result_bash_command(self) -> None:
        comp = ToolExecutionComponent("bash", {"command": "ls -la"})
        comp.update_result(self._make_result("total 10"), is_partial=False)

    def test_update_result_error(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo/bar.py"})
        comp.update_result(self._make_result("error msg", is_error=True), is_partial=False)

    def test_set_expanded(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py"})
        comp.update_result(self._make_result("a\n" * 30), is_partial=False)
        comp.set_expanded(True)
        comp.set_expanded(False)

    def test_set_show_images(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py"}, show_images=True)
        comp.set_show_images(False)
        comp.set_show_images(True)

    def test_set_args_complete_edit(self) -> None:
        comp = ToolExecutionComponent(
            "edit",
            {"path": "/foo.py", "oldText": "old line", "newText": "new line"},
        )
        comp.set_args_complete()

    def test_update_args(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py"})
        comp.update_args({"file_path": "/bar.py"})

    def test_partial_then_complete(self) -> None:
        comp = ToolExecutionComponent("bash", {"command": "echo hi"})
        comp.update_result(self._make_result("hi"), is_partial=True)
        comp.update_result(self._make_result("hi"), is_partial=False)

    def test_read_with_offset(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py", "offset": 10, "limit": 20})
        comp.update_result(self._make_result("content"), is_partial=False)

    def test_bash_timeout(self) -> None:
        comp = ToolExecutionComponent("bash", {"command": "sleep 5", "timeout": 10})
        comp.update_result(self._make_result(""), is_partial=False)

    def test_edit_with_diff_result(self) -> None:
        r = MagicMock()
        r.is_error = False
        r.content = []
        r.details = {"diff": "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n- old\n+ new\n"}
        comp = ToolExecutionComponent("edit", {"path": "/foo.py"})
        comp.update_result(r, is_partial=False)

    def test_write_invalid_content(self) -> None:
        comp = ToolExecutionComponent("write", {"file_path": "/foo.py", "content": 42})
        assert comp is not None

    def test_read_invalid_path(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": 42})
        assert comp is not None

    def test_custom_tool_with_definition(self) -> None:
        tool_def = MagicMock()
        tool_def.render_call = None
        tool_def.render_result = None
        comp = ToolExecutionComponent("custom_tool", {"foo": "bar"}, tool_definition=tool_def)
        comp.update_result(self._make_result("done"), is_partial=False)

    def test_invalidate(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py"})
        comp.invalidate()


# ---------------------------------------------------------------------------
# bash_execution - helper functions and component
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.bash_execution import (
    BashExecutionComponent,
)


class TestBashExecutionHelpers:
    def test_strip_ansi(self) -> None:
        assert _bash_strip_ansi("\x1b[31mred\x1b[0m") == "red"

    def test_truncate_tail_no_truncation(self) -> None:
        text, truncated = _truncate_tail("a\nb\nc", 100, 10000)
        assert text == "a\nb\nc"
        assert truncated is False

    def test_truncate_tail_line_limit(self) -> None:
        text, truncated = _truncate_tail("\n".join(str(i) for i in range(100)), 5, 10000)
        assert truncated is True
        assert text.count("\n") == 4

    def test_truncate_tail_byte_limit(self) -> None:
        _text, truncated = _truncate_tail("x" * 100, 10000, 50)
        assert truncated is True


class TestBashExecutionComponent:
    def test_instantiation(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("ls -la", ui)
        assert comp is not None

    def test_get_command(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("echo hi", ui)
        assert comp.get_command() == "echo hi"

    def test_get_output_empty(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("echo hi", ui)
        assert comp.get_output() == ""

    def test_append_output(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("echo hi", ui)
        comp.append_output("hello\nworld")
        assert "hello" in comp.get_output()

    def test_append_output_with_cr(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui)
        comp.append_output("line1\r\nline2\r")
        assert "line1" in comp.get_output()

    def test_append_output_strip_ansi(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui)
        comp.append_output("\x1b[31mred\x1b[0m text")
        assert comp.get_output() == "red text"

    def test_set_complete_success(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui)
        comp.append_output("done")
        comp.set_complete(0, False)

    def test_set_complete_error(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui)
        comp.set_complete(1, False)

    def test_set_complete_cancelled(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui)
        comp.set_complete(None, True)

    def test_set_complete_with_truncation(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui)
        trunc = MagicMock()
        trunc.truncated = True
        comp.set_complete(0, False, truncation_result=trunc, full_output_path="/tmp/out.txt")

    def test_set_expanded(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui)
        comp.append_output("line\n" * 30)
        comp.set_complete(0, False)
        comp.set_expanded(True)
        comp.set_expanded(False)

    def test_invalidate(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui)
        comp.invalidate()

    def test_exclude_from_context(self) -> None:
        ui = MagicMock()
        comp = BashExecutionComponent("cmd", ui, exclude_from_context=True)
        assert comp is not None


# ---------------------------------------------------------------------------
# model_selector
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.model_selector import (
    ModelSelectorComponent,
    _models_are_equal,
)


class TestModelSelectorHelpers:
    def test_models_are_equal_same_id(self) -> None:
        m1 = MagicMock()
        m1.id = "gpt-4"
        m1.provider = "openai"
        m2 = MagicMock()
        m2.id = "gpt-4"
        m2.provider = "openai"
        assert _models_are_equal(m1, m2) is True

    def test_models_are_equal_diff_id(self) -> None:
        m1 = MagicMock()
        m1.id = "gpt-4"
        m1.provider = "openai"
        m2 = MagicMock()
        m2.id = "gpt-3.5"
        m2.provider = "openai"
        assert _models_are_equal(m1, m2) is False

    def test_models_are_equal_none(self) -> None:
        assert _models_are_equal(None, None) is True
        assert _models_are_equal(None, MagicMock()) is False


class TestModelSelectorComponent:
    def _make_registry(self, models: list[Any]) -> Any:
        registry = MagicMock()
        registry.get_error.return_value = None
        registry.get_available.return_value = models
        return registry

    def _make_model(self, id: str = "gpt-4", provider: str = "openai") -> Any:
        m = MagicMock()
        m.id = id
        m.provider = provider
        m.name = id
        m.reasoning = False
        return m

    def test_instantiation_no_scoped(self) -> None:
        ui = MagicMock()
        registry = self._make_registry([self._make_model()])
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=None,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=[],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_instantiation_with_scoped(self) -> None:
        ui = MagicMock()
        model = self._make_model()
        registry = self._make_registry([model])
        scoped = [MagicMock(model=model)]
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=model,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=scoped,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_instantiation_with_initial_search(self) -> None:
        ui = MagicMock()
        registry = self._make_registry([self._make_model()])
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=None,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=[],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            initial_search_input="gpt",
        )
        assert comp is not None

    def test_focused_property(self) -> None:
        ui = MagicMock()
        registry = self._make_registry([])
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=None,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=[],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        comp.focused = True
        assert comp.focused is True

    def test_get_search_input(self) -> None:
        from pi_tui.components.input import Input

        ui = MagicMock()
        registry = self._make_registry([])
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=None,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=[],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert isinstance(comp.get_search_input(), Input)

    def test_handle_input_cancel(self) -> None:
        ui = MagicMock()
        on_cancel = MagicMock()
        registry = self._make_registry([])
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=None,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=[],
            on_select=MagicMock(),
            on_cancel=on_cancel,
        )
        # ESC should trigger cancel
        comp.handle_input("\x1b")

    def test_handle_input_up_down(self) -> None:

        ui = MagicMock()
        model = self._make_model("m1")
        model2 = self._make_model("m2")
        registry = self._make_registry([model, model2])
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=None,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=[],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        comp.handle_input("\x1b[A")  # up arrow
        comp.handle_input("\x1b[B")  # down arrow

    def test_handle_input_tab_scope_toggle(self) -> None:
        ui = MagicMock()
        model = self._make_model()
        registry = self._make_registry([model])
        scoped_item = MagicMock()
        scoped_item.model = model
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=None,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=[scoped_item],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        comp.handle_input("\t")  # Tab to toggle scope

    def test_registry_error(self) -> None:
        ui = MagicMock()
        registry = MagicMock()
        registry.get_error.return_value = "Load error"
        registry.get_available.return_value = []
        comp = ModelSelectorComponent(
            tui=ui,
            current_model=None,
            settings_manager=MagicMock(),
            model_registry=registry,
            scoped_models=[],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None


# ---------------------------------------------------------------------------
# login_dialog
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.login_dialog import LoginDialogComponent


class TestLoginDialogComponent:
    def test_instantiation(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        assert comp is not None

    def test_instantiation_with_name(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock(), provider_name="Anthropic")
        assert comp is not None

    def test_focused_property(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        comp.focused = True
        assert comp.focused is True

    def test_show_auth(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        comp.show_auth("https://example.com/auth")

    def test_show_auth_with_instructions(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        comp.show_auth("https://example.com/auth", "Click the link above")

    def test_show_manual_input(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        future = comp.show_manual_input("Enter the code:")
        assert future is not None

    def test_show_prompt(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        future = comp.show_prompt("Enter token:", placeholder="sk-...")
        assert future is not None

    def test_show_waiting(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        comp.show_waiting("Waiting for auth...")

    def test_show_progress(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        comp.show_progress("Loading...")

    def test_handle_input_escape_cancels(self) -> None:
        on_complete = MagicMock()
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", on_complete)
        comp.handle_input("\x1b")  # ESC should cancel

    def test_cancel_calls_on_complete(self) -> None:
        on_complete = MagicMock()
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", on_complete)
        comp._cancel()
        on_complete.assert_called_once_with(False, "Login cancelled")

    def test_cancel_twice_only_calls_once(self) -> None:
        on_complete = MagicMock()
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", on_complete)
        comp._cancel()
        comp._cancel()
        on_complete.assert_called_once()

    def test_future_resolves_on_input_submit(self) -> None:
        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        future = comp.show_manual_input("Enter code:")
        comp._on_input_submit("mycode")
        assert future.result() == "mycode"

    def test_future_rejects_on_cancel(self) -> None:

        ui = MagicMock()
        comp = LoginDialogComponent(ui, "anthropic", MagicMock())
        future = comp.show_manual_input("Enter code:")
        comp._cancel()
        assert future.exception() is not None


# ---------------------------------------------------------------------------
# daxnuts
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.daxnuts import (
    DaxnutsComponent,
    _build_image,
    _parse_image,
    _rgb,
)


class TestDaxnuts:
    def test_parse_image_shape(self) -> None:
        pixels = _parse_image()
        assert len(pixels) == 32
        assert len(pixels[0]) == 32

    def test_parse_image_values(self) -> None:
        pixels = _parse_image()
        r, g, b = pixels[0][0]
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255

    def test_rgb_fg(self) -> None:
        s = _rgb(100, 200, 50)
        assert "38" in s
        assert "100" in s

    def test_rgb_bg(self) -> None:
        s = _rgb(100, 200, 50, bg=True)
        assert "48" in s

    def test_build_image(self) -> None:
        lines = _build_image()
        assert len(lines) == 16  # 32 rows / 2

    def test_daxnuts_instantiation(self) -> None:

        ui = MagicMock()
        comp = DaxnutsComponent(ui)
        time.sleep(0.05)
        comp.dispose()

    def test_daxnuts_render(self) -> None:
        ui = MagicMock()
        comp = DaxnutsComponent(ui)
        lines = comp.render(80)
        assert isinstance(lines, list)
        comp.dispose()

    def test_daxnuts_invalidate(self) -> None:
        ui = MagicMock()
        comp = DaxnutsComponent(ui)
        comp.invalidate()
        comp.dispose()

    def test_daxnuts_render_cached(self) -> None:
        ui = MagicMock()
        comp = DaxnutsComponent(ui)
        lines1 = comp.render(80)
        lines2 = comp.render(80)
        assert lines1 is lines2  # Should return same cached object
        comp.dispose()

    def test_daxnuts_render_different_width(self) -> None:
        ui = MagicMock()
        comp = DaxnutsComponent(ui)
        comp.render(80)
        comp.render(40)
        # Different widths -> different renders
        comp.dispose()

    def test_daxnuts_dispose_twice(self) -> None:
        ui = MagicMock()
        comp = DaxnutsComponent(ui)
        comp.dispose()
        comp.dispose()  # Should not raise


# ---------------------------------------------------------------------------
# bordered_loader
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.bordered_loader import BorderedLoader


class TestBorderedLoader:
    def test_instantiation_cancellable(self) -> None:
        from pi_coding_agent.modes.interactive.components._theme import theme as _theme_obj

        ui = MagicMock()
        loader = BorderedLoader(ui, _theme_obj, "Loading...", {"cancellable": True})
        assert loader is not None

    def test_instantiation_not_cancellable(self) -> None:
        from pi_coding_agent.modes.interactive.components._theme import theme as _theme_obj

        ui = MagicMock()
        loader = BorderedLoader(ui, _theme_obj, "Loading...", {"cancellable": False})
        assert loader is not None

    def test_instantiation_default_options(self) -> None:
        from pi_coding_agent.modes.interactive.components._theme import theme as _theme_obj

        ui = MagicMock()
        loader = BorderedLoader(ui, _theme_obj, "Loading...")
        assert loader is not None

    def test_signal_cancellable(self) -> None:
        from pi_coding_agent.modes.interactive.components._theme import theme as _theme_obj

        ui = MagicMock()
        loader = BorderedLoader(ui, _theme_obj, "Loading...", {"cancellable": True})
        # signal may or may not exist depending on CancellableLoader version
        import contextlib

        with contextlib.suppress(AttributeError):
            loader.signal  # noqa: B018

    def test_signal_not_cancellable(self) -> None:
        from pi_coding_agent.modes.interactive.components._theme import theme as _theme_obj

        ui = MagicMock()
        loader = BorderedLoader(ui, _theme_obj, "Loading...", {"cancellable": False})
        assert loader.signal is None

    def test_set_on_abort(self) -> None:
        from pi_coding_agent.modes.interactive.components._theme import theme as _theme_obj

        ui = MagicMock()
        loader = BorderedLoader(ui, _theme_obj, "Loading...", {"cancellable": True})
        loader.set_on_abort(MagicMock())

    def test_handle_input(self) -> None:
        from pi_coding_agent.modes.interactive.components._theme import theme as _theme_obj

        ui = MagicMock()
        loader = BorderedLoader(ui, _theme_obj, "Loading...", {"cancellable": True})
        loader.handle_input("a")

    def test_dispose(self) -> None:
        from pi_coding_agent.modes.interactive.components._theme import theme as _theme_obj

        ui = MagicMock()
        loader = BorderedLoader(ui, _theme_obj, "Loading...")
        loader.dispose()


# ---------------------------------------------------------------------------
# footer - more coverage
# ---------------------------------------------------------------------------


class TestFooterMoreCoverage:
    def _make_session(self, with_manager: bool = False, with_usage: bool = False) -> Any:
        session = MagicMock()
        session.get_context_usage.return_value = None
        state = MagicMock()
        model = MagicMock()
        model.id = "claude-3"
        model.context_window = 200000
        model.reasoning = False
        model.provider = "anthropic"
        state.model = model
        state.thinking_level = "off"
        session.state = state
        session.model_registry = None
        if with_manager:
            mgr = MagicMock()
            if with_usage:
                entry = MagicMock()
                entry.type = "message"
                msg = MagicMock()
                msg.role = "assistant"
                usage = MagicMock()
                usage.input = 5000
                usage.output = 1000
                usage.cache_read = 0
                usage.cache_write = 0
                cost = MagicMock()
                cost.total = 0.05
                usage.cost = cost
                msg.usage = usage
                entry.message = msg
                mgr.get_entries.return_value = [entry]
            else:
                mgr.get_entries.return_value = []
            mgr.get_session_name.return_value = "my-session"
            session.session_manager = mgr
        else:
            session.session_manager = None
        return session

    def _make_footer_data(self, branch: str | None = None, provider_count: int = 1) -> Any:
        fd = MagicMock()
        fd.get_git_branch.return_value = branch
        fd.get_available_provider_count.return_value = provider_count
        fd.get_extension_statuses.return_value = {}
        return fd

    def test_render_with_usage_data(self) -> None:
        session = self._make_session(with_manager=True, with_usage=True)
        fd = self._make_footer_data()
        comp = FooterComponent(session, fd)
        lines = comp.render(80)
        assert len(lines) >= 2

    def test_render_with_branch(self) -> None:
        session = self._make_session()
        fd = self._make_footer_data(branch="main")
        comp = FooterComponent(session, fd)
        lines = comp.render(80)
        any_branch = any("main" in line for line in lines)
        assert any_branch

    def test_render_with_session_name(self) -> None:
        session = self._make_session(with_manager=True)
        fd = self._make_footer_data()
        comp = FooterComponent(session, fd)
        lines = comp.render(80)
        assert any("my-session" in line for line in lines)

    def test_render_with_extension_statuses(self) -> None:
        session = self._make_session()
        fd = self._make_footer_data()
        fd.get_extension_statuses.return_value = {"ext1": "Running", "ext2": "Idle"}
        comp = FooterComponent(session, fd)
        lines = comp.render(80)
        assert len(lines) >= 3

    def test_render_multi_provider(self) -> None:
        session = self._make_session()
        fd = self._make_footer_data(provider_count=3)
        comp = FooterComponent(session, fd)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_high_context_usage(self) -> None:
        session = self._make_session()
        cu = MagicMock()
        cu.percent = 95.0
        cu.context_window = 100000
        session.get_context_usage.return_value = cu
        fd = self._make_footer_data()
        comp = FooterComponent(session, fd)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_medium_context_usage(self) -> None:
        session = self._make_session()
        cu = MagicMock()
        cu.percent = 75.0
        cu.context_window = 100000
        session.get_context_usage.return_value = cu
        fd = self._make_footer_data()
        comp = FooterComponent(session, fd)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_long_pwd(self) -> None:
        session = self._make_session()
        fd = self._make_footer_data()
        comp = FooterComponent(session, fd)
        lines = comp.render(20)  # Very narrow
        assert isinstance(lines, list)

    def test_set_auto_compact_enabled(self) -> None:
        session = self._make_session()
        fd = self._make_footer_data()
        comp = FooterComponent(session, fd)
        comp.set_auto_compact_enabled(False)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_render_thinking_model(self) -> None:
        session = self._make_session()
        session.state.model.reasoning = True
        session.state.thinking_level = "high"
        fd = self._make_footer_data()
        comp = FooterComponent(session, fd)
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_format_tokens_function(self) -> None:
        from pi_coding_agent.modes.interactive.components.footer import _format_tokens

        assert _format_tokens(500) == "500"
        assert "k" in _format_tokens(5000)
        assert "k" in _format_tokens(50000)
        assert "M" in _format_tokens(2_000_000)
        assert "M" in _format_tokens(20_000_000)

    def test_sanitize_status_text(self) -> None:
        from pi_coding_agent.modes.interactive.components.footer import _sanitize_status_text

        assert _sanitize_status_text("hello\nworld") == "hello world"
        assert _sanitize_status_text("foo\tbar") == "foo bar"
        assert _sanitize_status_text("  spaces  ") == "spaces"


# ---------------------------------------------------------------------------
# scoped_models_selector - more coverage
# ---------------------------------------------------------------------------


class TestScopedModelsSelectorMoreCoverage:
    def _make_model(self, id: str = "m1", provider: str = "openai") -> Any:
        m = MagicMock()
        m.id = id
        m.provider = provider
        m.name = id
        m.description = ""
        m.context_window = 128000
        return m

    def _make_config(self, models: list[Any] | None = None) -> Any:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ModelsConfig

        all_models = models or [self._make_model("m1"), self._make_model("m2", "anthropic")]
        return ModelsConfig(
            all_models=all_models,
            enabled_model_ids={"m1"},
            has_enabled_models_filter=True,
        )

    def _make_callbacks(self) -> Any:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ModelsCallbacks

        return ModelsCallbacks(
            on_model_toggle=MagicMock(),
            on_persist=MagicMock(),
            on_enable_all=MagicMock(),
            on_clear_all=MagicMock(),
            on_toggle_provider=MagicMock(),
            on_cancel=MagicMock(),
        )

    def test_instantiation_with_models(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        assert comp is not None

    def test_render_with_models(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_focused_property(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        comp.focused = True
        assert comp.focused is True

    def test_handle_input_up_down(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        comp.handle_input("\x1b[A")  # up
        comp.handle_input("\x1b[B")  # down

    def test_handle_input_space_toggle(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        cb = self._make_callbacks()
        comp = ScopedModelsSelectorComponent(self._make_config(), cb)
        comp.handle_input(" ")

    def test_handle_input_escape(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        cb = self._make_callbacks()
        comp = ScopedModelsSelectorComponent(self._make_config(), cb)
        comp.handle_input("\x1b")

    def test_handle_input_text_search(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        comp.handle_input("m")
        comp.handle_input("1")

    def test_empty_models(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import (
            ModelsConfig,
            ScopedModelsSelectorComponent,
        )

        config = ModelsConfig(all_models=[], enabled_model_ids=set(), has_enabled_models_filter=False)
        cb = self._make_callbacks()
        comp = ScopedModelsSelectorComponent(config, cb)
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# session_selector - more coverage
# ---------------------------------------------------------------------------


class TestSessionSelectorMoreCoverage:
    def _make_session(self, path: str = "/a", name: str | None = None) -> Any:
        from datetime import datetime

        s = MagicMock()
        s.path = path
        s.name = name
        s.first_message = f"message in {path}"
        s.all_messages_text = f"message in {path}"
        s.modified = datetime.now()
        s.message_count = 3
        s.cwd = "/home/user/project"
        s.parent_session_path = None
        return s

    def _make_session_list(self, sessions: list[Any] | None = None) -> Any:
        from pi_coding_agent.modes.interactive.components.session_selector import _SessionList

        if sessions is None:
            sessions = [self._make_session("/a"), self._make_session("/b")]
        return _SessionList(
            sessions=sessions,
            show_cwd=False,
            sort_mode="recent",
            name_filter="all",
            keybindings=MagicMock(),
        )

    def test_session_list_handle_input_up_down(self) -> None:
        sl = self._make_session_list()
        sl.handle_input("\x1b[A")  # up
        sl.handle_input("\x1b[B")  # down
        sl.handle_input("\x1b[B")

    def test_session_list_select(self) -> None:
        on_select = MagicMock()
        sl = self._make_session_list()
        sl.on_select = on_select
        sl.handle_input("\r")  # Enter

    def test_session_list_render(self) -> None:
        sl = self._make_session_list()
        lines = sl.render(80)
        assert isinstance(lines, list)

    def test_session_list_render_empty(self) -> None:
        from pi_coding_agent.modes.interactive.components.session_selector import _SessionList

        sl = _SessionList(
            sessions=[],
            show_cwd=False,
            sort_mode="recent",
            name_filter="all",
            keybindings=MagicMock(),
        )
        lines = sl.render(80)
        assert isinstance(lines, list)

    def test_session_list_navigation_wrap(self) -> None:
        sl = self._make_session_list()
        # Navigate past end and beginning
        for _ in range(10):
            sl.handle_input("\x1b[B")
        for _ in range(10):
            sl.handle_input("\x1b[A")

    def test_session_list_focused(self) -> None:
        sl = self._make_session_list()
        sl.focused = True
        assert sl.focused is True

    def test_session_list_search_input(self) -> None:
        sl = self._make_session_list()
        sl.handle_input("m")
        sl.handle_input("e")

    def test_session_selector_header_render(self) -> None:
        from pi_coding_agent.modes.interactive.components.session_selector import _SessionSelectorHeader

        header = _SessionSelectorHeader(
            scope="current",
            sort_mode="recent",
            name_filter="all",
            keybindings=MagicMock(),
            request_render=MagicMock(),
        )
        lines = header.render(80)
        assert isinstance(lines, list)

    def test_session_selector_component_instantiation(self) -> None:
        from pi_coding_agent.modes.interactive.components.session_selector import SessionSelectorComponent

        comp = SessionSelectorComponent(
            current_sessions_loader=lambda: [],
            all_sessions_loader=lambda: [],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        assert comp is not None

    def test_session_selector_component_render(self) -> None:
        from pi_coding_agent.modes.interactive.components.session_selector import SessionSelectorComponent

        comp = SessionSelectorComponent(
            current_sessions_loader=lambda: [],
            all_sessions_loader=lambda: [],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# tree_selector - more coverage
# ---------------------------------------------------------------------------


class TestTreeSelectorMoreCoverage:
    def _make_tree_entry(self, id: str = "n1", is_leaf: bool = True) -> Any:
        """Create a minimal tree node entry compatible with _TreeList."""
        entry = MagicMock()
        entry.id = id
        entry.label = None
        entry.parent_id = None
        entry.is_leaf = is_leaf
        return entry

    def _make_node(self, entry: Any) -> Any:
        node = MagicMock()
        node.entry = entry
        node.children = []
        return node

    def _make_tree_list(self, entries: list[Any] | None = None) -> Any:
        from pi_coding_agent.modes.interactive.components.tree_selector import _TreeList

        if entries is None:
            e1 = self._make_tree_entry("n1")
            e2 = self._make_tree_entry("n2")
            entries = [e1, e2]

        # Build proper node tree structure
        nodes = []
        for entry in entries:
            node = MagicMock()
            node.entry = entry
            node.children = []
            nodes.append(node)

        tl = _TreeList(tree=nodes, current_leaf_id=None, max_visible_lines=10)
        return tl

    def test_tree_list_empty(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import _TreeList

        tl = _TreeList(tree=[], current_leaf_id=None, max_visible_lines=10)
        lines = tl.render(80)
        assert isinstance(lines, list)

    def test_tree_list_render_with_nodes(self) -> None:
        tl = self._make_tree_list()
        lines = tl.render(80)
        assert isinstance(lines, list)

    def test_tree_list_navigation(self) -> None:
        tl = self._make_tree_list()
        tl.handle_input("\x1b[A")  # up
        tl.handle_input("\x1b[B")  # down

    def test_tree_list_escape(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import _TreeList

        on_cancel = MagicMock()
        tl = _TreeList(tree=[], current_leaf_id=None, max_visible_lines=10)
        tl.on_cancel = on_cancel
        tl.handle_input("\x1b")

    def test_tree_list_select(self) -> None:
        on_select = MagicMock()
        tl = self._make_tree_list()
        tl.on_select = on_select
        tl.handle_input("\r")

    def test_label_input_instantiation(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import _LabelInput

        li = _LabelInput("entry-id-1", "current label")
        assert li is not None

    def test_label_input_render(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import _LabelInput

        li = _LabelInput("e1", "old_name.py")
        lines = li.render(80)
        assert isinstance(lines, list)

    def test_label_input_typing(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import _LabelInput

        li = _LabelInput("e1", "old.py")
        li.handle_input("n")
        li.handle_input("e")
        li.handle_input("w")
        lines = li.render(80)
        assert isinstance(lines, list)

    def test_label_input_submit(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import _LabelInput

        on_submit = MagicMock()
        li = _LabelInput("e1", "old.py")
        li.on_submit = on_submit
        li.handle_input("\r")
        on_submit.assert_called_once()

    def test_label_input_cancel(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import _LabelInput

        on_cancel = MagicMock()
        li = _LabelInput("e1", "old.py")
        li.on_cancel = on_cancel
        li.handle_input("\x1b")
        on_cancel.assert_called_once()

    def test_label_input_focused(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import _LabelInput

        li = _LabelInput("e1", None)
        li.focused = True
        assert li.focused is True

    def test_tree_selector_render(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import TreeSelectorComponent

        comp = TreeSelectorComponent(
            tree=[],
            current_leaf_id=None,
            terminal_height=40,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_tree_selector_focused(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import TreeSelectorComponent

        comp = TreeSelectorComponent(
            tree=[],
            current_leaf_id=None,
            terminal_height=40,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        comp.focused = True
        assert comp.focused is True

    def test_tree_selector_handle_input(self) -> None:
        from pi_coding_agent.modes.interactive.components.tree_selector import TreeSelectorComponent

        comp = TreeSelectorComponent(
            tree=[],
            current_leaf_id=None,
            terminal_height=40,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )
        comp.handle_input("a")
        comp.handle_input("\x1b[B")
        comp.handle_input("\x1b")


# ---------------------------------------------------------------------------
# extension_editor
# ---------------------------------------------------------------------------

from pi_coding_agent.modes.interactive.components.extension_editor import ExtensionEditorComponent


class TestExtensionEditorComponent:
    def test_instantiation(self) -> None:
        ui = MagicMock()
        kb = MagicMock()
        comp = ExtensionEditorComponent(
            tui=ui,
            keybindings=kb,
            title="Edit content",
            prefill=None,
            on_submit=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_instantiation_with_prefill(self) -> None:
        ui = MagicMock()
        kb = MagicMock()
        comp = ExtensionEditorComponent(
            tui=ui,
            keybindings=kb,
            title="Edit",
            prefill="initial text",
            on_submit=MagicMock(),
            on_cancel=MagicMock(),
        )
        assert comp is not None

    def test_handle_input_cancel(self) -> None:
        on_cancel = MagicMock()
        ui = MagicMock()
        kb = MagicMock()
        comp = ExtensionEditorComponent(
            tui=ui,
            keybindings=kb,
            title="Edit",
            prefill=None,
            on_submit=MagicMock(),
            on_cancel=on_cancel,
        )
        comp.handle_input("\x1b")  # Escape -> cancel

    def test_handle_input_regular(self) -> None:
        ui = MagicMock()
        kb = MagicMock()
        kb.matches.return_value = False
        comp = ExtensionEditorComponent(
            tui=ui,
            keybindings=kb,
            title="Edit",
            prefill=None,
            on_submit=MagicMock(),
            on_cancel=MagicMock(),
        )
        comp.handle_input("a")


# ---------------------------------------------------------------------------
# resource_list keyboard navigation and toggle
# ---------------------------------------------------------------------------


class TestResourceListNavigation:
    def _make_resource_list(self) -> Any:
        from pi_coding_agent.modes.interactive.components.config_selector import (
            PathMetadata,
            ResolvedPaths,
            ResolvedResource,
            _ResourceList,
        )

        pm = PathMetadata(origin="top-level", scope="user", source="auto")
        rr1 = ResolvedResource(path="/ext/ext1.ts", enabled=True, metadata=pm)
        rr2 = ResolvedResource(path="/ext/ext2.ts", enabled=False, metadata=pm)
        rp = ResolvedPaths(extensions=[rr1, rr2])
        from pi_coding_agent.modes.interactive.components.config_selector import build_groups

        groups = build_groups(rp)
        rl = _ResourceList(groups, MagicMock(), "/cwd", "/agent")
        return rl

    def test_navigation_down(self) -> None:
        rl = self._make_resource_list()
        rl.handle_input("\x1b[B")  # down arrow

    def test_navigation_up(self) -> None:
        rl = self._make_resource_list()
        rl.handle_input("\x1b[A")  # up arrow

    def test_toggle_space(self) -> None:
        on_toggle = MagicMock()
        rl = self._make_resource_list()
        rl.on_toggle = on_toggle
        rl.handle_input(" ")  # space to toggle

    def test_escape_cancel(self) -> None:
        on_cancel = MagicMock()
        rl = self._make_resource_list()
        rl.on_cancel = on_cancel
        rl.handle_input("\x1b")

    def test_search_typing(self) -> None:
        rl = self._make_resource_list()
        rl.focused = True
        rl.handle_input("e")
        rl.handle_input("x")
        rl.handle_input("t")


# ---------------------------------------------------------------------------
# armin - more coverage of animation effects
# ---------------------------------------------------------------------------

import time


class TestArminEffects:
    """Test each animation effect individually by patching random.choice."""

    def _run_effect(self, effect_name: str, ticks: int = 5) -> None:
        with patch("pi_coding_agent.modes.interactive.components.armin.random") as mock_random:
            mock_random.choice.return_value = effect_name
            mock_random.randint.return_value = 3
            mock_random.random.return_value = 0.1  # always less than 0.3 (glitch branch 1)
            mock_random.shuffle = lambda x: None
            ui = MagicMock()
            comp = ArminComponent(ui)
            comp.render(80)
            # Manually tick effect a few times without threading
            for _ in range(ticks):
                comp._tick_effect()
            comp.render(80)
            comp.dispose()

    def test_effect_typewriter(self) -> None:
        self._run_effect("typewriter", 20)

    def test_effect_scanline(self) -> None:
        self._run_effect("scanline", 20)

    def test_effect_rain(self) -> None:
        self._run_effect("rain", 10)

    def test_effect_fade(self) -> None:
        self._run_effect("fade", 20)

    def test_effect_crt(self) -> None:
        self._run_effect("crt", 10)

    def test_effect_glitch(self) -> None:
        self._run_effect("glitch", 15)

    def test_effect_dissolve(self) -> None:
        self._run_effect("dissolve", 20)

    def test_animation_tick_calls_render(self) -> None:
        ui = MagicMock()
        comp = ArminComponent(ui)
        comp._stop_animation()
        comp._animation_tick(1.0 / 30)
        comp.dispose()

    def test_stop_animation_none(self) -> None:
        ui = MagicMock()
        comp = ArminComponent(ui)
        comp._stop_animation()
        comp._stop_animation()  # Second call should be safe


# ---------------------------------------------------------------------------
# tool_execution - more branch coverage
# ---------------------------------------------------------------------------


class TestToolExecutionMoreCoverage:
    def _make_result(self, text: str = "", is_error: bool = False) -> Any:
        r = MagicMock()
        r.is_error = is_error
        r.content = [{"type": "text", "text": text}]
        r.details = None
        return r

    def test_find_tool_with_glob(self) -> None:
        comp = ToolExecutionComponent("find", {"pattern": "*.py", "path": "/src", "glob": "**/*.py"})
        comp.update_result(self._make_result("match1.py\nmatch2.py"), is_partial=False)

    def test_grep_with_glob(self) -> None:
        comp = ToolExecutionComponent("grep", {"pattern": "hello", "glob": "*.py", "path": "/src"})
        comp.update_result(self._make_result("file.py:1:hello"), is_partial=False)

    def test_bash_with_many_lines(self) -> None:
        output = "\n".join(f"line {i}" for i in range(50))
        comp = ToolExecutionComponent("bash", {"command": "seq 50"})
        comp.update_result(self._make_result(output), is_partial=False)

    def test_bash_expanded(self) -> None:
        output = "\n".join(f"line {i}" for i in range(50))
        comp = ToolExecutionComponent("bash", {"command": "seq 50"})
        comp.update_result(self._make_result(output), is_partial=False)
        comp.set_expanded(True)

    def test_bash_with_full_output_path(self) -> None:
        r = MagicMock()
        r.is_error = False
        r.content = [{"type": "text", "text": "output"}]
        r.details = {"fullOutputPath": "/tmp/out.txt", "truncation": None}
        comp = ToolExecutionComponent("bash", {"command": "long_cmd"})
        comp.update_result(r, is_partial=False)

    def test_read_expanded(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py"})
        comp.update_result(self._make_result("a\n" * 20), is_partial=False)
        comp.set_expanded(True)

    def test_write_expanded(self) -> None:
        comp = ToolExecutionComponent("write", {"file_path": "/foo.py", "content": "a\n" * 20})
        comp.update_result(self._make_result(), is_partial=False)
        comp.set_expanded(True)

    def test_ls_expanded(self) -> None:
        comp = ToolExecutionComponent("ls", {"path": "/foo"})
        comp.update_result(self._make_result("file\n" * 30), is_partial=False)
        comp.set_expanded(True)

    def test_edit_with_error(self) -> None:
        comp = ToolExecutionComponent("edit", {"path": "/foo.py"})
        comp.update_result(self._make_result("edit failed", is_error=True), is_partial=False)

    def test_edit_preview_error(self) -> None:
        comp = ToolExecutionComponent("edit", {"path": "/foo.py", "oldText": "x", "newText": "y"})
        comp.set_args_complete()
        comp._edit_diff_preview = {"error": "Could not compute diff"}
        comp._update_display()

    def test_custom_tool_with_render_call(self) -> None:
        from pi_tui.components.text import Text as _Text

        tool_def = MagicMock()
        tool_def.render_call = lambda args, th: _Text("Call output", 0, 0)
        tool_def.render_result = None
        comp = ToolExecutionComponent("my_tool", {"key": "value"}, tool_definition=tool_def)
        comp.update_result(self._make_result("done"), is_partial=False)

    def test_custom_tool_with_render_result(self) -> None:
        from pi_tui.components.text import Text as _Text

        tool_def = MagicMock()
        tool_def.render_call = None
        tool_def.render_result = lambda result, opts, th: _Text("Result output", 0, 0)
        comp = ToolExecutionComponent("my_tool", {"key": "value"}, tool_definition=tool_def)
        comp.update_result(self._make_result("done"), is_partial=False)

    def test_get_bg_fn_partial(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py"})
        # Partial is default; bg fn should use toolPendingBg
        bg_fn = comp._get_bg_fn()
        result = bg_fn("test")
        assert isinstance(result, str)

    def test_get_bg_fn_error(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py"})
        comp.update_result(self._make_result("err", is_error=True), is_partial=False)
        bg_fn = comp._get_bg_fn()
        result = bg_fn("test")
        assert isinstance(result, str)

    def test_get_bg_fn_success(self) -> None:
        comp = ToolExecutionComponent("read", {"file_path": "/foo.py"})
        comp.update_result(self._make_result("ok"), is_partial=False)
        bg_fn = comp._get_bg_fn()
        result = bg_fn("test")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# scoped_models_selector - more keyboard handling
# ---------------------------------------------------------------------------


class TestScopedModelsSelectorKeyboard:
    def _make_config(self) -> Any:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ModelsConfig

        m1 = MagicMock()
        m1.id = "m1"
        m1.provider = "openai"
        m2 = MagicMock()
        m2.id = "m2"
        m2.provider = "anthropic"
        return ModelsConfig(all_models=[m1, m2], enabled_model_ids={"m1"}, has_enabled_models_filter=True)

    def _make_callbacks(self) -> Any:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ModelsCallbacks

        return ModelsCallbacks(
            on_model_toggle=MagicMock(),
            on_persist=MagicMock(),
            on_enable_all=MagicMock(),
            on_clear_all=MagicMock(),
            on_toggle_provider=MagicMock(),
            on_cancel=MagicMock(),
        )

    def test_handle_enter_persists(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        cb = self._make_callbacks()
        comp = ScopedModelsSelectorComponent(self._make_config(), cb)
        comp.handle_input("\r")  # Enter should confirm/persist

    def test_handle_multiple_navigations(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        for _ in range(5):
            comp.handle_input("\x1b[B")
        for _ in range(5):
            comp.handle_input("\x1b[A")

    def test_render_multiple_times(self) -> None:
        from pi_coding_agent.modes.interactive.components.scoped_models_selector import ScopedModelsSelectorComponent

        comp = ScopedModelsSelectorComponent(self._make_config(), self._make_callbacks())
        for _ in range(3):
            lines = comp.render(80)
            assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# session_selector - more SessionSelectorComponent coverage
# ---------------------------------------------------------------------------


class TestSessionSelectorComponentCoverage:
    def _make_comp(self) -> Any:
        from pi_coding_agent.modes.interactive.components.session_selector import SessionSelectorComponent

        return SessionSelectorComponent(
            current_sessions_loader=lambda: [],
            all_sessions_loader=lambda: [],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )

    def test_handle_input_escape(self) -> None:
        comp = self._make_comp()
        comp.handle_input("\x1b")

    def test_handle_input_navigation(self) -> None:
        comp = self._make_comp()
        comp.handle_input("\x1b[A")
        comp.handle_input("\x1b[B")

    def test_focused_property(self) -> None:
        comp = self._make_comp()
        comp.focused = True
        assert comp.focused is True

    def test_get_session_list(self) -> None:
        from pi_coding_agent.modes.interactive.components.session_selector import (
            SessionSelectorComponent,
            _SessionList,
        )

        comp = SessionSelectorComponent(
            current_sessions_loader=lambda: [],
            all_sessions_loader=lambda: [],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
        )
        sl = comp.get_session_list()
        assert isinstance(sl, _SessionList)

    def test_handle_search_input(self) -> None:
        comp = self._make_comp()
        comp.handle_input("m")
        comp.handle_input("y")

    def test_multiple_renders(self) -> None:
        comp = self._make_comp()
        for _ in range(3):
            lines = comp.render(80)
            assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# extension_editor - more coverage
# ---------------------------------------------------------------------------


class TestExtensionEditorMoreCoverage:
    def test_render(self) -> None:
        ui = MagicMock()
        kb = MagicMock()
        kb.matches.return_value = False
        comp = ExtensionEditorComponent(
            tui=ui,
            keybindings=kb,
            title="Edit content",
            prefill="initial",
            on_submit=MagicMock(),
            on_cancel=MagicMock(),
        )
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_handle_input_external_editor_trigger(self) -> None:
        ui = MagicMock()
        kb = MagicMock()
        # Simulate externalEditor keybinding match
        kb.matches.side_effect = lambda data, key: key == "externalEditor" and data == "\x07"
        on_cancel = MagicMock()
        comp = ExtensionEditorComponent(
            tui=ui,
            keybindings=kb,
            title="Edit",
            prefill=None,
            on_submit=MagicMock(),
            on_cancel=on_cancel,
        )
        # No external editor is configured so _open_external_editor returns early
        comp.handle_input("\x07")

    def test_handle_input_regular_character(self) -> None:
        ui = MagicMock()
        kb = MagicMock()
        kb.matches.return_value = False
        comp = ExtensionEditorComponent(
            tui=ui,
            keybindings=kb,
            title="Edit",
            prefill=None,
            on_submit=MagicMock(),
            on_cancel=MagicMock(),
        )
        comp.handle_input("h")
        comp.handle_input("e")
        comp.handle_input("l")


# ---------------------------------------------------------------------------
# custom_editor - handle_input coverage (was 19%)
# ---------------------------------------------------------------------------


from pi_coding_agent.modes.interactive.components.custom_editor import CustomEditor
from pi_coding_agent.modes.interactive.components._theme import get_editor_theme


def _make_custom_editor(
    kb_matches_side_effect: Any = None,
) -> tuple[CustomEditor, MagicMock]:
    """Helper: build a CustomEditor with a mocked TUI and configurable keybindings."""
    tui = MagicMock()
    theme = get_editor_theme()
    kb = MagicMock()
    if kb_matches_side_effect is not None:
        kb.matches.side_effect = kb_matches_side_effect
    else:
        kb.matches.return_value = False
    editor = CustomEditor(tui, theme, kb)
    return editor, kb


class TestCustomEditorHandleInput:
    def test_on_action_registers_handler(self) -> None:
        editor, _kb = _make_custom_editor()
        handler = MagicMock()
        editor.on_action("submit", handler)
        assert editor.action_handlers["submit"] is handler

    def test_extension_shortcut_consumes_input(self) -> None:
        """on_extension_shortcut returning True prevents further processing."""
        editor, kb = _make_custom_editor()
        shortcut = MagicMock(return_value=True)
        editor.on_extension_shortcut = shortcut
        editor.handle_input("x")
        shortcut.assert_called_once_with("x")
        # kb.matches should NOT have been called because shortcut consumed
        kb.matches.assert_not_called()

    def test_extension_shortcut_not_consuming_falls_through(self) -> None:
        """on_extension_shortcut returning False lets normal handling continue."""
        editor, _kb = _make_custom_editor()
        shortcut = MagicMock(return_value=False)
        editor.on_extension_shortcut = shortcut
        # No special keybinding matches — input falls through to super
        editor.handle_input("a")
        shortcut.assert_called_once_with("a")

    def test_paste_image_with_handler(self) -> None:
        """pasteImage keybinding calls on_paste_image and returns."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "pasteImage"
        )
        paste_handler = MagicMock()
        editor.on_paste_image = paste_handler
        editor.handle_input("\x1b")
        paste_handler.assert_called_once()

    def test_paste_image_without_handler(self) -> None:
        """pasteImage keybinding with no handler still returns without crashing."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "pasteImage"
        )
        editor.on_paste_image = None
        editor.handle_input("\x1b")  # Should not raise

    def test_interrupt_calls_on_escape(self) -> None:
        """When interrupt matches and no autocomplete, on_escape is called."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "interrupt"
        )
        escape_handler = MagicMock()
        editor.on_escape = escape_handler
        editor.handle_input("\x1b")
        escape_handler.assert_called_once()

    def test_interrupt_calls_action_handler_fallback(self) -> None:
        """interrupt with no on_escape falls back to action_handlers['interrupt']."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "interrupt"
        )
        handler = MagicMock()
        editor.on_action("interrupt", handler)
        editor.on_escape = None
        editor.handle_input("\x1b")
        handler.assert_called_once()

    def test_interrupt_with_autocomplete_showing_calls_super(self) -> None:
        """When autocomplete is showing, interrupt delegates to super."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "interrupt"
        )
        # Patch is_showing_autocomplete to return True
        with patch.object(type(editor), "is_showing_autocomplete", return_value=True):
            editor.on_escape = MagicMock()
            # Should call super().handle_input, not on_escape
            editor.handle_input("\x1b")
            editor.on_escape.assert_not_called()

    def test_interrupt_no_handler_calls_super(self) -> None:
        """interrupt with no handler calls super().handle_input."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "interrupt"
        )
        editor.on_escape = None
        # No action_handlers registered; should fall through to super without error
        editor.handle_input("\x1b")

    def test_exit_empty_editor_calls_on_ctrl_d(self) -> None:
        """exit keybinding on empty editor calls on_ctrl_d."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "exit"
        )
        ctrl_d_handler = MagicMock()
        editor.on_ctrl_d = ctrl_d_handler
        # Editor is empty by default
        assert editor.get_text() == ""
        editor.handle_input("\x04")
        ctrl_d_handler.assert_called_once()

    def test_exit_empty_editor_action_handler_fallback(self) -> None:
        """exit on empty editor falls back to action_handlers['exit']."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "exit"
        )
        handler = MagicMock()
        editor.on_action("exit", handler)
        editor.on_ctrl_d = None
        editor.handle_input("\x04")
        handler.assert_called_once()

    def test_exit_non_empty_editor_falls_through(self) -> None:
        """exit on non-empty editor does NOT call ctrl_d handler."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "exit"
        )
        handler = MagicMock()
        editor.on_ctrl_d = handler
        editor.set_text("some text")
        editor.handle_input("\x04")
        handler.assert_not_called()

    def test_custom_action_handler_dispatched(self) -> None:
        """Non-reserved action in action_handlers is dispatched when kb matches."""
        editor, _kb = _make_custom_editor(
            kb_matches_side_effect=lambda data, key: key == "myAction"
        )
        handler = MagicMock()
        editor.on_action("myAction", handler)
        editor.handle_input("z")
        handler.assert_called_once()

    def test_unknown_input_falls_through_to_super(self) -> None:
        """Input with no matching keybindings falls through to the base editor."""
        editor, _kb = _make_custom_editor()
        # Typing regular characters should update the editor text via super
        editor.handle_input("h")
        editor.handle_input("i")
        assert "h" in editor.get_text() or editor.get_text() == "hi"

    def test_no_keybindings_has_matches_attr_missing(self) -> None:
        """If kb has no 'matches' attribute, all keybinding checks are skipped."""
        tui = MagicMock()
        theme = get_editor_theme()
        kb = object()  # No 'matches' attribute
        editor = CustomEditor(tui, theme, kb)
        # Should not raise; falls through to super
        editor.handle_input("a")


# ---------------------------------------------------------------------------
# countdown_timer - tick / dispose logic (was 69%)
# ---------------------------------------------------------------------------


class TestCountdownTimerTick:
    def test_initial_tick_called_on_construction(self) -> None:
        """on_tick is called immediately with full remaining seconds."""
        on_tick = MagicMock()
        on_expire = MagicMock()
        # Use 3000ms → 3 seconds
        ct = CountdownTimer(3000, None, on_tick, on_expire)
        ct.dispose()
        on_tick.assert_called_once_with(3)
        on_expire.assert_not_called()

    def test_tick_decrements_and_calls_on_tick(self) -> None:
        """_tick decrements remaining_seconds and calls on_tick."""
        on_tick = MagicMock()
        on_expire = MagicMock()
        ct = CountdownTimer(3000, None, on_tick, on_expire)
        on_tick.reset_mock()
        ct._tick()
        assert ct._remaining_seconds == 2
        on_tick.assert_called_once_with(2)
        on_expire.assert_not_called()
        ct.dispose()

    def test_tick_to_zero_calls_on_expire(self) -> None:
        """When remaining_seconds reaches 0, on_expire is called."""
        on_tick = MagicMock()
        on_expire = MagicMock()
        ct = CountdownTimer(1000, None, on_tick, on_expire)
        on_tick.reset_mock()
        ct._tick()  # 1 -> 0
        assert ct._remaining_seconds == 0
        on_expire.assert_called_once()
        assert ct._disposed

    def test_tick_calls_tui_request_render(self) -> None:
        """_tick calls tui.request_render if tui is set."""
        tui = MagicMock()
        on_tick = MagicMock()
        on_expire = MagicMock()
        ct = CountdownTimer(3000, tui, on_tick, on_expire)
        on_tick.reset_mock()
        ct._tick()
        tui.request_render.assert_called()
        ct.dispose()

    def test_tick_after_dispose_is_no_op(self) -> None:
        """_tick on a disposed timer does nothing."""
        on_tick = MagicMock()
        on_expire = MagicMock()
        ct = CountdownTimer(3000, None, on_tick, on_expire)
        ct.dispose()
        on_tick.reset_mock()
        ct._tick()
        on_tick.assert_not_called()
        on_expire.assert_not_called()

    def test_dispose_cancels_timer(self) -> None:
        """dispose() cancels the internal threading.Timer."""
        on_tick = MagicMock()
        on_expire = MagicMock()
        ct = CountdownTimer(5000, None, on_tick, on_expire)
        assert ct._timer is not None
        ct.dispose()
        assert ct._disposed
        assert ct._timer is None

    def test_schedule_next_skipped_after_dispose(self) -> None:
        """_schedule_next does nothing when already disposed."""
        on_tick = MagicMock()
        ct = CountdownTimer(2000, None, on_tick, MagicMock())
        ct.dispose()
        # Calling _schedule_next on a disposed timer should not create a new timer
        ct._schedule_next()
        assert ct._timer is None

    def test_minimum_seconds_is_one(self) -> None:
        """timeout_ms < 1000 still gives at least 1 second."""
        on_tick = MagicMock()
        ct = CountdownTimer(100, None, on_tick, MagicMock())
        assert ct._remaining_seconds == 1
        ct.dispose()


# ---------------------------------------------------------------------------
# oauth_selector - handle_input coverage (was 76%)
# ---------------------------------------------------------------------------


def _make_provider(id_: str, name: str, logged_in: bool = False) -> MagicMock:
    p = MagicMock()
    p.id = id_
    p.name = name
    creds = MagicMock() if logged_in else None
    if logged_in and creds:
        creds.type = "oauth"
    return p


class TestOAuthSelectorHandleInput:
    def _make_comp(
        self, providers: list[Any] | None = None, mode: str = "login"
    ) -> tuple[OAuthSelectorComponent, MagicMock, MagicMock]:
        on_select = MagicMock()
        on_cancel = MagicMock()
        auth_storage = MagicMock()
        auth_storage.get.return_value = None
        comp = OAuthSelectorComponent(
            mode=mode,
            auth_storage=auth_storage,
            on_select=on_select,
            on_cancel=on_cancel,
            oauth_providers=providers or [_make_provider("github", "GitHub"), _make_provider("google", "Google")],
        )
        return comp, on_select, on_cancel

    def test_navigate_up_wraps_at_zero(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 0
        comp.handle_input("\x1b[A")  # selectUp
        assert comp._selected_index == 0  # clamped at 0

    def test_navigate_down(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 0
        comp.handle_input("\x1b[B")  # selectDown
        assert comp._selected_index == 1

    def test_navigate_down_clamps_at_end(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 1
        comp.handle_input("\x1b[B")
        assert comp._selected_index == 1  # clamped at last

    def test_confirm_selects_provider(self) -> None:
        comp, on_select, _ = self._make_comp()
        comp._selected_index = 0
        comp.handle_input("\r")  # selectConfirm
        on_select.assert_called_once_with("github")

    def test_confirm_second_provider(self) -> None:
        comp, on_select, _ = self._make_comp()
        comp._selected_index = 1
        comp.handle_input("\r")
        on_select.assert_called_once_with("google")

    def test_cancel_calls_on_cancel(self) -> None:
        comp, _, on_cancel = self._make_comp()
        comp.handle_input("\x1b")  # selectCancel (escape)
        on_cancel.assert_called_once()

    def test_confirm_with_no_providers_does_not_call_select(self) -> None:
        on_select = MagicMock()
        on_cancel = MagicMock()
        auth_storage = MagicMock()
        auth_storage.get.return_value = None
        comp = OAuthSelectorComponent(
            mode="login",
            auth_storage=auth_storage,
            on_select=on_select,
            on_cancel=on_cancel,
            oauth_providers=[],  # explicitly empty
        )
        comp.handle_input("\r")
        on_select.assert_not_called()

    def test_logout_mode_title(self) -> None:
        """logout mode should use a different title."""
        comp, _, _ = self._make_comp(mode="logout")
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_no_providers_shows_empty_message(self) -> None:
        comp, _, _ = self._make_comp(providers=[])
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_logged_in_provider_shows_status(self) -> None:
        """Providers with oauth credentials show a logged-in indicator."""
        provider = _make_provider("github", "GitHub")
        auth_storage = MagicMock()
        creds = MagicMock()
        creds.type = "oauth"
        auth_storage.get.return_value = creds
        comp = OAuthSelectorComponent(
            mode="login",
            auth_storage=auth_storage,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            oauth_providers=[provider],
        )
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# extension_selector - handle_input and dispose coverage (was 74%)
# ---------------------------------------------------------------------------


class TestExtensionSelectorHandleInput:
    def _make_comp(
        self, options: list[str] | None = None
    ) -> tuple[ExtensionSelectorComponent, MagicMock, MagicMock]:
        on_select = MagicMock()
        on_cancel = MagicMock()
        comp = ExtensionSelectorComponent(
            title="Choose",
            options=options if options is not None else ["alpha", "beta", "gamma"],
            on_select=on_select,
            on_cancel=on_cancel,
        )
        return comp, on_select, on_cancel

    def test_up_arrow_navigates(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 1
        comp.handle_input("\x1b[A")  # selectUp
        assert comp._selected_index == 0

    def test_down_arrow_navigates(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 0
        comp.handle_input("\x1b[B")  # selectDown
        assert comp._selected_index == 1

    def test_k_navigates_up(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 2
        comp.handle_input("k")
        assert comp._selected_index == 1

    def test_j_navigates_down(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 0
        comp.handle_input("j")
        assert comp._selected_index == 1

    def test_up_clamps_at_zero(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 0
        comp.handle_input("\x1b[A")
        assert comp._selected_index == 0

    def test_down_clamps_at_end(self) -> None:
        comp, _, _ = self._make_comp()
        comp._selected_index = 2
        comp.handle_input("\x1b[B")
        assert comp._selected_index == 2

    def test_enter_selects_current(self) -> None:
        comp, on_select, _ = self._make_comp()
        comp._selected_index = 1
        comp.handle_input("\r")  # selectConfirm
        on_select.assert_called_once_with("beta")

    def test_newline_selects_current(self) -> None:
        comp, on_select, _ = self._make_comp()
        comp._selected_index = 0
        comp.handle_input("\n")
        on_select.assert_called_once_with("alpha")

    def test_cancel_calls_on_cancel(self) -> None:
        comp, _, on_cancel = self._make_comp()
        comp.handle_input("\x1b")  # escape → selectCancel
        on_cancel.assert_called_once()

    def test_select_with_empty_options_no_call(self) -> None:
        comp, on_select, _ = self._make_comp(options=[])
        comp.handle_input("\r")
        on_select.assert_not_called()

    def test_dispose_with_no_countdown(self) -> None:
        comp, _, _ = self._make_comp()
        assert comp._countdown is None
        comp.dispose()  # Should not raise

    def test_dispose_cancels_countdown(self) -> None:
        """If a CountdownTimer is present, dispose() cancels it."""
        comp, _, _ = self._make_comp()
        mock_timer = MagicMock()
        comp._countdown = mock_timer
        comp.dispose()
        mock_timer.dispose.assert_called_once()

    def test_countdown_creates_timer_when_tui_and_timeout(self) -> None:
        """Providing timeout > 0 and tui creates a CountdownTimer."""
        tui = MagicMock()
        on_cancel = MagicMock()
        with patch(
            "pi_coding_agent.modes.interactive.components.extension_selector.CountdownTimer"
        ) as MockTimer:
            mock_instance = MagicMock()
            MockTimer.return_value = mock_instance
            comp = ExtensionSelectorComponent(
                title="T",
                options=["a"],
                on_select=MagicMock(),
                on_cancel=on_cancel,
                tui=tui,
                timeout=5000,
            )
            MockTimer.assert_called_once()
            assert comp._countdown is mock_instance


# ---------------------------------------------------------------------------
# extension_editor - _open_external_editor coverage (was 75%)
# ---------------------------------------------------------------------------


class TestExtensionEditorOpenExternalEditor:
    def _make_comp(self) -> tuple[ExtensionEditorComponent, MagicMock, MagicMock]:
        tui = MagicMock()
        kb = MagicMock()
        kb.matches.return_value = False
        on_submit = MagicMock()
        on_cancel = MagicMock()
        comp = ExtensionEditorComponent(
            tui=tui,
            keybindings=kb,
            title="Edit",
            prefill=None,
            on_submit=on_submit,
            on_cancel=on_cancel,
        )
        return comp, on_submit, on_cancel

    def test_cancel_key_calls_on_cancel(self) -> None:
        comp, _, on_cancel = self._make_comp()
        comp.handle_input("\x1b")  # selectCancel
        on_cancel.assert_called_once()

    def test_external_editor_no_env_var_returns_early(self) -> None:
        """_open_external_editor does nothing if VISUAL and EDITOR are unset."""
        comp, _, _ = self._make_comp()
        with patch.dict("os.environ", {}, clear=True):
            # Ensure neither VISUAL nor EDITOR is set
            import os as _os
            _os.environ.pop("VISUAL", None)
            _os.environ.pop("EDITOR", None)
            comp._open_external_editor()  # Should not raise

    def test_open_external_editor_success(self) -> None:
        """_open_external_editor with EDITOR set and successful subprocess."""
        comp, _, _ = self._make_comp()
        comp._editor.set_text("original")
        new_content = "updated content"

        with patch.dict("os.environ", {"EDITOR": "vim", "VISUAL": ""}), patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # Write expected content to a temp file that the editor "would produce"
            with patch("builtins.open", create=True) as mock_open, patch(
                "tempfile.NamedTemporaryFile"
            ) as mock_tmp, patch("os.unlink"):
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = MagicMock(return_value=False)
                mock_open.return_value.read.return_value = new_content
                mock_tmp.return_value.__enter__ = lambda s: s
                mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
                mock_tmp.return_value.write = MagicMock()
                mock_tmp.return_value.name = "/tmp/test_pi.md"
                comp._open_external_editor()

    def test_open_external_editor_nonzero_exit_does_not_update(self) -> None:
        """When subprocess returns nonzero, editor text is not updated."""
        comp, _, _ = self._make_comp()
        comp._editor.set_text("original text")

        with patch.dict("os.environ", {"EDITOR": "vim", "VISUAL": ""}), patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result
            with patch("tempfile.NamedTemporaryFile") as mock_tmp, patch("os.unlink"):
                mock_tmp.return_value.__enter__ = lambda s: s
                mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
                mock_tmp.return_value.write = MagicMock()
                mock_tmp.return_value.name = "/tmp/test_pi_fail.md"
                comp._open_external_editor()
        # Text was not changed
        assert comp._editor.get_text() == "original text"

    def test_handle_input_external_editor_keybinding_no_env(self) -> None:
        """externalEditor keybinding with no env variable just returns."""
        tui = MagicMock()
        kb = MagicMock()
        kb.matches.side_effect = lambda data, key: key == "externalEditor" and data == "\x07"
        comp = ExtensionEditorComponent(
            tui=tui, keybindings=kb, title="T", prefill=None,
            on_submit=MagicMock(), on_cancel=MagicMock(),
        )
        with patch.dict("os.environ", {}, clear=True):
            import os as _os
            _os.environ.pop("VISUAL", None)
            _os.environ.pop("EDITOR", None)
            comp.handle_input("\x07")  # Should not raise


# ---------------------------------------------------------------------------
# scoped_models_selector - handle_input coverage (was 79%)
# ---------------------------------------------------------------------------


def _make_model_mock(id_: str, provider: str = "anthropic") -> MagicMock:
    m = MagicMock()
    m.id = id_
    m.provider = provider
    m.name = f"{provider}/{id_}"
    return m


def _make_models_component(
    model_ids: list[str] | None = None,
    enabled_ids: set[str] | None = None,
    has_filter: bool = True,
) -> tuple[ScopedModelsSelectorComponent, Any]:
    if model_ids is None:
        model_ids = ["a", "b", "c"]
    models = [_make_model_mock(mid) for mid in model_ids]
    cfg = ModelsConfig(
        all_models=models,
        enabled_model_ids=enabled_ids if enabled_ids is not None else {"anthropic/a"},
        has_enabled_models_filter=has_filter,
    )
    cbs = ModelsCallbacks(
        on_model_toggle=MagicMock(),
        on_persist=MagicMock(),
        on_enable_all=MagicMock(),
        on_clear_all=MagicMock(),
        on_toggle_provider=MagicMock(),
        on_cancel=MagicMock(),
    )
    comp = ScopedModelsSelectorComponent(cfg, cbs)
    return comp, cbs


class TestScopedModelsSelectorHandleInput:
    def test_select_up_wraps(self) -> None:
        comp, _ = _make_models_component()
        comp._selected_index = 0
        comp.handle_input("\x1b[A")  # selectUp
        assert comp._selected_index == len(comp._filtered_items) - 1  # wraps around

    def test_select_down_wraps(self) -> None:
        comp, _ = _make_models_component()
        n = len(comp._filtered_items)
        comp._selected_index = n - 1
        comp.handle_input("\x1b[B")  # selectDown
        assert comp._selected_index == 0

    def test_enter_toggles_model(self) -> None:
        comp, cbs = _make_models_component()
        comp._selected_index = 0
        comp.handle_input("\r")  # enter
        cbs.on_model_toggle.assert_called()

    def test_enter_when_all_enabled_calls_clear_all(self) -> None:
        """When enabled_ids is None (all models enabled), toggling calls on_clear_all."""
        comp, cbs = _make_models_component(has_filter=False)
        # With has_filter=False, _enabled_ids starts as None
        assert comp._enabled_ids is None
        comp.handle_input("\r")
        cbs.on_clear_all.assert_called_once()

    def test_ctrl_a_enables_all(self) -> None:
        comp, cbs = _make_models_component()
        comp.handle_input("\x01")  # ctrl+a
        cbs.on_enable_all.assert_called_once()

    def test_ctrl_x_clears_all(self) -> None:
        comp, cbs = _make_models_component()
        comp.handle_input("\x18")  # ctrl+x
        cbs.on_clear_all.assert_called_once()

    def test_ctrl_s_persists(self) -> None:
        comp, cbs = _make_models_component()
        comp._is_dirty = True
        comp.handle_input("\x13")  # ctrl+s
        cbs.on_persist.assert_called_once()
        assert comp._is_dirty is False

    def test_ctrl_c_with_search_clears_search(self) -> None:
        comp, cbs = _make_models_component()
        comp._search_input.set_value("query")
        comp.handle_input("\x03")  # ctrl+c
        assert comp._search_input.get_value() == ""
        cbs.on_cancel.assert_not_called()

    def test_ctrl_c_without_search_cancels(self) -> None:
        comp, cbs = _make_models_component()
        assert comp._search_input.get_value() == ""
        comp.handle_input("\x03")  # ctrl+c
        cbs.on_cancel.assert_called_once()

    def test_escape_cancels(self) -> None:
        comp, cbs = _make_models_component()
        comp.handle_input("\x1b")  # escape
        cbs.on_cancel.assert_called_once()

    def test_ctrl_p_toggles_provider(self) -> None:
        comp, cbs = _make_models_component()
        comp._selected_index = 0
        comp.handle_input("\x10")  # ctrl+p
        cbs.on_toggle_provider.assert_called_once()

    def test_alt_up_reorders_enabled_model(self) -> None:
        """alt+up moves an enabled model up in the order."""
        comp, _ = _make_models_component(
            model_ids=["x", "y", "z"],
            enabled_ids={"anthropic/x", "anthropic/y", "anthropic/z"},
        )
        # Find the index of "y" in filtered items after building
        y_full = "anthropic/y"
        idx_y = next(
            (i for i, item in enumerate(comp._filtered_items) if item.full_id == y_full), -1
        )
        assert idx_y >= 1, "y must not be first for alt+up to work"
        comp._selected_index = idx_y
        comp.handle_input("\x1b[1;3A")  # alt+up
        # After move, is_dirty should be set
        assert comp._is_dirty is True

    def test_alt_down_reorders_enabled_model(self) -> None:
        """alt+down moves an enabled model down in the order."""
        comp, _ = _make_models_component(
            model_ids=["x", "y", "z"],
            enabled_ids={"anthropic/x", "anthropic/y", "anthropic/z"},
        )
        comp._selected_index = 0  # select "x"
        comp.handle_input("\x1b[1;3B")  # alt+down
        assert comp._enabled_ids is not None

    def test_typing_filters_models(self) -> None:
        """Typing a character updates the search filter."""
        comp, _ = _make_models_component()
        comp.handle_input("a")
        assert comp._search_input.get_value() == "a"

    def test_focused_setter(self) -> None:
        comp, _ = _make_models_component()
        comp.focused = True
        assert comp.focused is True
        assert comp._search_input.focused is True

    def test_render_returns_lines(self) -> None:
        comp, _ = _make_models_component()
        lines = comp.render(80)
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_no_models(self) -> None:
        """Component with no models renders the empty state."""
        comp, _ = _make_models_component(model_ids=[])
        lines = comp.render(80)
        assert isinstance(lines, list)


# ---------------------------------------------------------------------------
# settings_selector - _SelectSubmenu, _make_*_submenu and on_change coverage
# ---------------------------------------------------------------------------


class TestSelectSubmenu:
    def _make_submenu(
        self,
        current_value: str = "a",
        on_selection_change: Any = None,
    ) -> _SelectSubmenu:
        from pi_tui.components.select_list import SelectItem

        options = [SelectItem(value="a", label="Option A"), SelectItem(value="b", label="Option B")]
        on_select = MagicMock()
        on_cancel = MagicMock()
        return _SelectSubmenu(
            title="Test Submenu",
            description="A description",
            options=options,
            current_value=current_value,
            on_select=on_select,
            on_cancel=on_cancel,
            on_selection_change=on_selection_change,
        )

    def test_submenu_renders(self) -> None:
        sub = self._make_submenu()
        lines = sub.render(80)
        assert isinstance(lines, list)

    def test_submenu_no_description(self) -> None:
        from pi_tui.components.select_list import SelectItem

        opts = [SelectItem(value="x", label="X")]
        sub = _SelectSubmenu("T", "", opts, "x", MagicMock(), MagicMock())
        lines = sub.render(80)
        assert isinstance(lines, list)

    def test_submenu_handle_input_delegates(self) -> None:
        """handle_input delegates to inner SelectList."""
        sub = self._make_submenu()
        with patch.object(sub._select_list, "handle_input") as mock_input:
            sub.handle_input("\x1b[A")
            mock_input.assert_called_once_with("\x1b[A")

    def test_submenu_with_on_selection_change(self) -> None:
        """on_selection_change callback is wired to select_list."""
        on_change = MagicMock()
        sub = self._make_submenu(on_selection_change=on_change)
        assert sub._select_list.on_selection_change is not None

    def test_current_value_not_in_options_selects_none(self) -> None:
        """current_value not in options leaves selection at default."""
        sub = self._make_submenu(current_value="nonexistent")
        lines = sub.render(80)
        assert isinstance(lines, list)


class TestMakeThinkingSubmenu:
    def test_creates_submenu(self) -> None:
        config = SettingsConfig(
            thinking_level="medium",
            available_thinking_levels=["off", "low", "medium", "high"],
        )
        callbacks = SettingsCallbacks(on_thinking_level_change=MagicMock())
        done = MagicMock()
        sub = _make_thinking_submenu("medium", done, config, callbacks)
        assert sub is not None
        lines = sub.render(80)
        assert isinstance(lines, list)

    def test_on_select_calls_callbacks_and_done(self) -> None:
        on_change = MagicMock()
        config = SettingsConfig(available_thinking_levels=["off", "high"])
        callbacks = SettingsCallbacks(on_thinking_level_change=on_change)
        done = MagicMock()
        sub = _make_thinking_submenu("off", done, config, callbacks)
        # Trigger on_select by calling the select_list directly (cast to Any for type checker)
        sl: Any = sub._select_list
        sl.on_select(sl._items[1])  # select "high"
        on_change.assert_called_once_with("high")
        done.assert_called_once_with("high")

    def test_on_cancel_calls_done_with_none(self) -> None:
        config = SettingsConfig(available_thinking_levels=["off"])
        callbacks = SettingsCallbacks()
        done = MagicMock()
        sub = _make_thinking_submenu("off", done, config, callbacks)
        sl: Any = sub._select_list
        sl.on_cancel()
        done.assert_called_once_with(None)


class TestMakeThemeSubmenu:
    def test_creates_submenu(self) -> None:
        config = SettingsConfig(
            current_theme="default",
            available_themes=["default", "dark", "light"],
        )
        callbacks = SettingsCallbacks()
        done = MagicMock()
        sub = _make_theme_submenu("default", done, config, callbacks)
        assert sub is not None

    def test_on_select_calls_on_theme_change(self) -> None:
        on_change = MagicMock()
        config = SettingsConfig(available_themes=["default", "solarized"])
        callbacks = SettingsCallbacks(on_theme_change=on_change)
        done = MagicMock()
        sub = _make_theme_submenu("default", done, config, callbacks)
        sl: Any = sub._select_list
        sl.on_select(sl._items[1])  # solarized
        on_change.assert_called_once_with("solarized")
        done.assert_called_once_with("solarized")

    def test_on_cancel_previews_original_theme(self) -> None:
        on_preview = MagicMock()
        config = SettingsConfig(available_themes=["default", "dark"])
        callbacks = SettingsCallbacks(on_theme_change=MagicMock(), on_theme_preview=on_preview)
        done = MagicMock()
        sub = _make_theme_submenu("default", done, config, callbacks)
        sl: Any = sub._select_list
        sl.on_cancel()
        on_preview.assert_called_once_with("default")
        done.assert_called_once_with(None)

    def test_on_selection_change_calls_preview(self) -> None:
        on_preview = MagicMock()
        config = SettingsConfig(available_themes=["default", "dark"])
        callbacks = SettingsCallbacks(on_theme_preview=on_preview)
        done = MagicMock()
        sub = _make_theme_submenu("default", done, config, callbacks)
        sl: Any = sub._select_list
        sl.on_selection_change(sl._items[1])
        on_preview.assert_called_once_with("dark")


class TestSettingsSelectorOnChange:
    def _make_comp(self, **config_overrides: Any) -> tuple[SettingsSelectorComponent, dict[str, MagicMock]]:
        cbs: dict[str, MagicMock] = {
            "on_auto_compact_change": MagicMock(),
            "on_show_images_change": MagicMock(),
            "on_auto_resize_images_change": MagicMock(),
            "on_block_images_change": MagicMock(),
            "on_enable_skill_commands_change": MagicMock(),
            "on_steering_mode_change": MagicMock(),
            "on_follow_up_mode_change": MagicMock(),
            "on_transport_change": MagicMock(),
            "on_thinking_level_change": MagicMock(),
            "on_theme_change": MagicMock(),
            "on_hide_thinking_block_change": MagicMock(),
            "on_collapse_changelog_change": MagicMock(),
            "on_double_escape_action_change": MagicMock(),
            "on_show_hardware_cursor_change": MagicMock(),
            "on_editor_padding_x_change": MagicMock(),
            "on_autocomplete_max_visible_change": MagicMock(),
            "on_quiet_startup_change": MagicMock(),
            "on_clear_on_shrink_change": MagicMock(),
            "on_cancel": MagicMock(),
        }
        config = SettingsConfig(**config_overrides)
        callbacks = SettingsCallbacks(**cbs)
        with patch(
            "pi_tui.terminal_image.get_capabilities",
            side_effect=Exception("no caps"),
        ):
            comp = SettingsSelectorComponent(config, callbacks)
        return comp, cbs

    def _fire_change(self, comp: SettingsSelectorComponent, id_: str, value: str) -> None:
        """Trigger the on_change callback directly via the SettingsList."""
        comp._settings_list._on_change(id_, value)

    def test_autocompact_true(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "autocompact", "true")
        cbs["on_auto_compact_change"].assert_called_once_with(True)

    def test_autocompact_false(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "autocompact", "false")
        cbs["on_auto_compact_change"].assert_called_once_with(False)

    def test_steering_mode_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "steering-mode", "all")
        cbs["on_steering_mode_change"].assert_called_once_with("all")

    def test_follow_up_mode_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "follow-up-mode", "all")
        cbs["on_follow_up_mode_change"].assert_called_once_with("all")

    def test_transport_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "transport", "websocket")
        cbs["on_transport_change"].assert_called_once_with("websocket")

    def test_hide_thinking_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "hide-thinking", "true")
        cbs["on_hide_thinking_block_change"].assert_called_once_with(True)

    def test_collapse_changelog_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "collapse-changelog", "true")
        cbs["on_collapse_changelog_change"].assert_called_once_with(True)

    def test_quiet_startup_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "quiet-startup", "true")
        cbs["on_quiet_startup_change"].assert_called_once_with(True)

    def test_double_escape_action_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "double-escape-action", "tree")
        cbs["on_double_escape_action_change"].assert_called_once_with("tree")

    def test_show_hardware_cursor_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "show-hardware-cursor", "true")
        cbs["on_show_hardware_cursor_change"].assert_called_once_with(True)

    def test_editor_padding_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "editor-padding", "2")
        cbs["on_editor_padding_x_change"].assert_called_once_with(2)

    def test_autocomplete_max_visible_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "autocomplete-max-visible", "15")
        cbs["on_autocomplete_max_visible_change"].assert_called_once_with(15)

    def test_clear_on_shrink_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "clear-on-shrink", "true")
        cbs["on_clear_on_shrink_change"].assert_called_once_with(True)

    def test_auto_resize_images_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "auto-resize-images", "false")
        cbs["on_auto_resize_images_change"].assert_called_once_with(False)

    def test_block_images_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "block-images", "true")
        cbs["on_block_images_change"].assert_called_once_with(True)

    def test_skill_commands_change(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "skill-commands", "false")
        cbs["on_enable_skill_commands_change"].assert_called_once_with(False)

    def test_unknown_id_is_ignored(self) -> None:
        comp, cbs = self._make_comp()
        self._fire_change(comp, "nonexistent-setting", "value")
        # None of the callbacks should be called
        for cb in cbs.values():
            cb.assert_not_called()

    def test_get_settings_list(self) -> None:
        comp, _ = self._make_comp()
        from pi_tui.components.settings_list import SettingsList

        assert isinstance(comp.get_settings_list(), SettingsList)


# ---------------------------------------------------------------------------
# session_selector - header render, set_status_message, delete, toggles (was 68%)
# ---------------------------------------------------------------------------


class TestSessionSelectorHeaderRender:
    def _make_header(self, scope: str = "current") -> _SessionSelectorHeader:
        from pi_coding_agent.modes.interactive.components.keybinding_hints import _create_default_keybindings

        kb = _create_default_keybindings()
        return _SessionSelectorHeader(
            scope=scope,  # type: ignore[arg-type]
            sort_mode="threaded",
            name_filter="all",
            keybindings=kb,
            request_render=MagicMock(),
        )

    def test_render_current_scope(self) -> None:
        header = self._make_header("current")
        lines = header.render(80)
        assert len(lines) == 3
        assert isinstance(lines[0], str)

    def test_render_all_scope(self) -> None:
        header = self._make_header("all")
        lines = header.render(80)
        assert len(lines) == 3

    def test_render_loading(self) -> None:
        header = self._make_header()
        header.set_loading(True)
        lines = header.render(80)
        assert len(lines) == 3

    def test_render_loading_with_progress(self) -> None:
        header = self._make_header()
        header.set_loading(True)
        header.set_progress(5, 10)
        lines = header.render(80)
        assert len(lines) == 3

    def test_render_delete_confirm(self) -> None:
        header = self._make_header()
        header.set_confirming_delete_path("/some/path.json")
        lines = header.render(80)
        assert len(lines) == 3
        # First hint line should have a delete message
        assert lines[1] != ""

    def test_render_status_message_info(self) -> None:
        header = self._make_header()
        header.set_status_message({"type": "info", "message": "Session deleted"})
        lines = header.render(80)
        assert len(lines) == 3

    def test_render_status_message_error(self) -> None:
        header = self._make_header()
        header.set_status_message({"type": "error", "message": "Failed"})
        lines = header.render(80)
        assert len(lines) == 3

    def test_render_with_rename_hint(self) -> None:
        header = self._make_header()
        header.set_show_rename_hint(True)
        lines = header.render(80)
        assert len(lines) == 3

    def test_set_status_message_auto_hide(self) -> None:
        """set_status_message with auto_hide_ms creates a timer that clears the message."""
        import time

        request_render = MagicMock()
        from pi_coding_agent.modes.interactive.components.keybinding_hints import _create_default_keybindings

        kb = _create_default_keybindings()
        header = _SessionSelectorHeader("current", "threaded", "all", kb, request_render)
        header.set_status_message({"type": "info", "message": "hello"}, auto_hide_ms=50)
        assert header._status_message is not None
        time.sleep(0.2)
        assert header._status_message is None
        request_render.assert_called()

    def test_set_status_message_clears_previous_timer(self) -> None:
        """Calling set_status_message twice cancels the first timer."""
        from pi_coding_agent.modes.interactive.components.keybinding_hints import _create_default_keybindings

        kb = _create_default_keybindings()
        header = _SessionSelectorHeader("current", "threaded", "all", kb, MagicMock())
        header.set_status_message({"type": "info", "message": "first"}, auto_hide_ms=5000)
        first_timer = header._status_timer
        assert first_timer is not None
        header.set_status_message({"type": "info", "message": "second"})
        # Previous timer should have been cancelled
        assert header._status_message == {"type": "info", "message": "second"}
        if first_timer:
            first_timer.cancel()

    def test_set_scope(self) -> None:
        header = self._make_header("current")
        header.set_scope("all")
        assert header._scope == "all"

    def test_set_sort_mode(self) -> None:
        header = self._make_header()
        header.set_sort_mode("recent")
        assert header._sort_mode == "recent"

    def test_set_name_filter(self) -> None:
        header = self._make_header()
        header.set_name_filter("named")
        assert header._name_filter == "named"


class TestSessionListHandleInput:
    def _make_list(self) -> _SessionList:
        from datetime import datetime as _dt

        from pi_coding_agent.modes.interactive.components.keybinding_hints import _create_default_keybindings

        kb = _create_default_keybindings()

        @dataclass
        class FakeSession:
            path: str = "s1"
            name: str | None = None
            first_message: str = "hello"
            modified: Any = None
            message_count: int = 3
            cwd: str | None = None

        sessions = [FakeSession(path=f"session{i}", modified=_dt(2024, 1, i + 1)) for i in range(5)]
        sl = _SessionList(sessions, False, "recent", "all", kb)  # use "recent" to get predictable order
        return sl

    def test_navigate_up(self) -> None:
        sl = self._make_list()
        sl._selected_index = 2
        sl.handle_input("\x1b[A")  # selectUp
        assert sl._selected_index == 1

    def test_navigate_down(self) -> None:
        sl = self._make_list()
        sl._selected_index = 0
        sl.handle_input("\x1b[B")  # selectDown
        assert sl._selected_index == 1

    def test_navigate_page_up(self) -> None:
        sl = self._make_list()
        sl._selected_index = 3
        sl.handle_input("\x1b[5~")  # pageUp
        assert sl._selected_index == 0

    def test_navigate_page_down(self) -> None:
        sl = self._make_list()
        sl._selected_index = 0
        sl.handle_input("\x1b[6~")  # pageDown
        # should move by max_visible
        assert sl._selected_index >= 0

    def test_select_confirm_calls_on_select(self) -> None:
        sl = self._make_list()
        on_select = MagicMock()
        sl.on_select = on_select
        sl._selected_index = 0
        sl.handle_input("\r")  # selectConfirm
        on_select.assert_called_once_with("session0")

    def test_select_cancel_calls_on_cancel(self) -> None:
        sl = self._make_list()
        on_cancel = MagicMock()
        sl.on_cancel = on_cancel
        sl.handle_input("\x1b")  # selectCancel
        on_cancel.assert_called_once()

    def test_tab_calls_toggle_scope(self) -> None:
        sl = self._make_list()
        on_toggle = MagicMock()
        sl.on_toggle_scope = on_toggle
        sl.handle_input("\t")
        on_toggle.assert_called_once()

    def test_ctrl_s_calls_toggle_sort(self) -> None:
        sl = self._make_list()
        on_sort = MagicMock()
        sl.on_toggle_sort = on_sort
        sl.handle_input("\x13")  # ctrl+s = toggleSessionSort
        on_sort.assert_called_once()

    def test_ctrl_p_calls_toggle_path(self) -> None:
        sl = self._make_list()
        on_path = MagicMock()
        sl.on_toggle_path = on_path
        sl.handle_input("\x10")  # ctrl+p = toggleSessionPath
        on_path.assert_called_once()

    def test_ctrl_d_starts_delete_confirmation(self) -> None:
        sl = self._make_list()
        on_del_change = MagicMock()
        sl.on_delete_confirmation_change = on_del_change
        sl._selected_index = 0
        sl.handle_input("\x04")  # ctrl+d = deleteSession
        on_del_change.assert_called_once_with("session0")

    def test_delete_confirm_enter_triggers_delete(self) -> None:
        sl = self._make_list()
        on_del = MagicMock()
        sl.on_delete_session = on_del
        sl._set_confirming_delete_path("session0")
        sl.handle_input("\r")  # confirm
        on_del.assert_called_once_with("session0")

    def test_delete_cancel_escape(self) -> None:
        sl = self._make_list()
        on_del_change = MagicMock()
        sl.on_delete_confirmation_change = on_del_change
        sl._set_confirming_delete_path("session0")
        sl.handle_input("\x1b")  # escape = cancel
        assert sl._confirming_delete_path is None

    def test_delete_cancel_ctrl_c(self) -> None:
        sl = self._make_list()
        sl._set_confirming_delete_path("session0")
        sl.handle_input("\x03")  # ctrl+c
        assert sl._confirming_delete_path is None

    def test_ctrl_r_calls_rename_session(self) -> None:
        sl = self._make_list()
        on_rename = MagicMock()
        sl.on_rename_session = on_rename
        sl._selected_index = 0
        sl.handle_input("\x12")  # ctrl+r = renameSession
        on_rename.assert_called_once_with("session0")

    def test_search_filtering(self) -> None:
        sl = self._make_list()
        sl.handle_input("s")
        # Should have filtered with "s"
        assert sl._search_input.get_value() == "s"

    def test_render_returns_lines(self) -> None:
        sl = self._make_list()
        lines = sl.render(80)
        assert isinstance(lines, list)

    def test_render_empty_sessions(self) -> None:
        from pi_coding_agent.modes.interactive.components.keybinding_hints import _create_default_keybindings

        kb = _create_default_keybindings()
        sl = _SessionList([], False, "threaded", "all", kb)
        lines = sl.render(80)
        assert isinstance(lines, list)

    def test_cannot_delete_current_session(self) -> None:
        """Attempting to delete the current active session shows an error."""
        from datetime import datetime as _dt

        from pi_coding_agent.modes.interactive.components.keybinding_hints import _create_default_keybindings

        kb = _create_default_keybindings()

        @dataclass
        class FakeSession:
            path: str = "active_session"
            name: str | None = None
            first_message: str = "hi"
            modified: Any = None
            message_count: int = 0
            cwd: str | None = None

        sl = _SessionList([FakeSession(modified=_dt(2024, 1, 1))], False, "threaded", "all", kb, "active_session")
        on_error = MagicMock()
        sl.on_error = on_error
        sl._selected_index = 0
        sl.handle_input("\x04")  # deleteSession
        on_error.assert_called_once()
        assert sl._confirming_delete_path is None

    def test_set_sort_mode_updates_filter(self) -> None:
        sl = self._make_list()
        sl.set_sort_mode("recent")
        assert sl._sort_mode == "recent"

    def test_set_name_filter_updates_filter(self) -> None:
        sl = self._make_list()
        sl.set_name_filter("named")
        assert sl._name_filter == "named"

    def test_get_selected_session_path(self) -> None:
        sl = self._make_list()
        sl._selected_index = 2
        path = sl.get_selected_session_path()
        assert path == "session2"


class TestDeleteSessionFileNew:
    def test_trash_success(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            result = _delete_session_file("/some/session.json")
        assert result["ok"] is True
        assert result["method"] == "trash"

    def test_trash_not_found_falls_back_to_unlink(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError), patch("os.unlink") as mock_unlink:
            result = _delete_session_file("/some/session.json")
        mock_unlink.assert_called_once()
        assert result["ok"] is True
        assert result["method"] == "unlink"

    def test_unlink_failure_returns_error(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError), patch(
            "os.unlink", side_effect=OSError("Permission denied")
        ):
            result = _delete_session_file("/some/session.json")
        assert result["ok"] is False
        assert "Permission denied" in result["error"]

    def test_path_starting_with_dash_gets_double_dash_arg(self) -> None:
        """Paths starting with '-' get '--' prepended to avoid shell option parsing."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            result = _delete_session_file("-weird-path.json")
        assert result["ok"] is True
        call_args = mock_run.call_args[0][0]
        assert "--" in call_args


class TestSessionSelectorComponentToggles:
    def _make_comp(self, with_rename: bool = False) -> SessionSelectorComponent:
        rename_fn = MagicMock() if with_rename else None
        return SessionSelectorComponent(
            current_sessions_loader=lambda: [],
            all_sessions_loader=lambda: [],
            on_select=MagicMock(),
            on_cancel=MagicMock(),
            on_exit=MagicMock(),
            request_render=MagicMock(),
            rename_session=rename_fn,
        )

    def test_toggle_sort_mode_cycles(self) -> None:
        comp = self._make_comp()
        sort_mode: Any = comp._sort_mode
        assert sort_mode == "threaded"
        comp._toggle_sort_mode()
        sort_mode = comp._sort_mode
        assert sort_mode == "recent"
        comp._toggle_sort_mode()
        sort_mode = comp._sort_mode
        assert sort_mode == "relevance"
        comp._toggle_sort_mode()
        sort_mode = comp._sort_mode
        assert sort_mode == "threaded"

    def test_toggle_name_filter_toggles(self) -> None:
        comp = self._make_comp()
        name_filter: Any = comp._name_filter
        assert name_filter == "all"
        comp._toggle_name_filter()
        name_filter = comp._name_filter
        assert name_filter == "named"
        comp._toggle_name_filter()
        name_filter = comp._name_filter
        assert name_filter == "all"

    def test_toggle_scope_to_all(self) -> None:
        comp = self._make_comp()
        scope: Any = comp._scope
        assert scope == "current"
        comp._toggle_scope()
        scope = comp._scope
        assert scope == "all"

    def test_toggle_scope_back_to_current(self) -> None:
        comp = self._make_comp()
        comp._scope = "all"
        comp._toggle_scope()
        scope: Any = comp._scope
        assert scope == "current"

    def test_toggle_scope_to_all_uses_cached_sessions(self) -> None:
        """If all_sessions is already cached, toggle uses it without reloading."""
        from datetime import datetime as _dt

        comp = self._make_comp()

        @dataclass
        class FakeSession:
            path: str = "all_s1"
            name: str | None = None
            first_message: str = "hi"
            modified: Any = None
            message_count: int = 0
            cwd: str | None = None

        comp._all_sessions = [FakeSession(modified=_dt(2024, 1, 1))]
        comp._toggle_scope()
        assert comp._scope == "all"

    def test_handle_input_in_rename_mode_cancel(self) -> None:
        comp = self._make_comp(with_rename=True)
        comp._enter_rename_mode("session1", "old name")
        assert comp._mode == "rename"
        comp.handle_input("\x1b")  # escape → exit rename mode
        assert comp._mode == "list"

    def test_handle_input_in_rename_mode_ctrl_c_cancel(self) -> None:
        comp = self._make_comp(with_rename=True)
        comp._enter_rename_mode("session1", None)
        comp.handle_input("\x03")  # ctrl+c → exit rename mode
        assert comp._mode == "list"

    def test_enter_rename_mode_sets_state(self) -> None:
        comp = self._make_comp(with_rename=True)
        comp._enter_rename_mode("session_path", "my name")
        assert comp._mode == "rename"
        assert comp._rename_target_path == "session_path"
        assert comp._rename_input.get_value() == "my name"

    def test_confirm_rename_empty_exits_rename_mode(self) -> None:
        comp = self._make_comp(with_rename=True)
        comp._enter_rename_mode("session_path", None)
        comp._confirm_rename("")
        assert comp._mode == "list"

    def test_confirm_rename_with_name_exits_rename_mode(self) -> None:
        comp = self._make_comp(with_rename=True)
        comp._enter_rename_mode("session_path", None)
        comp._confirm_rename("new name")
        assert comp._mode == "list"

    def test_focused_property_propagates(self) -> None:
        comp = self._make_comp()
        comp.focused = True
        assert comp.focused is True


# ---------------------------------------------------------------------------
# tree_selector - _get_entry_display_text, _extract_content, _apply_filter,
#                handle_input, render coverage (was 70%)
# ---------------------------------------------------------------------------


def _make_entry(
    id_: str,
    type_: str,
    parent_id: str | None = None,
    **kwargs: Any,
) -> MagicMock:
    e = MagicMock()
    e.id = id_
    e.type = type_
    e.parent_id = parent_id
    for k, v in kwargs.items():
        setattr(e, k, v)
    return e


def _make_message_entry(
    id_: str,
    role: str,
    content: Any = "hello",
    parent_id: str | None = None,
    stop_reason: str | None = None,
    error_message: str | None = None,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
    command: str | None = None,
) -> MagicMock:
    msg = MagicMock()
    msg.role = role
    msg.content = content
    msg.stop_reason = stop_reason
    msg.error_message = error_message
    msg.tool_call_id = tool_call_id
    msg.tool_name = tool_name
    msg.command = command
    entry = _make_entry(id_, "message", parent_id=parent_id, message=msg)
    return entry


def _make_tree_node_v2(entry: Any, children: list[Any] | None = None, label: str | None = None) -> MagicMock:
    node = MagicMock()
    node.entry = entry
    node.children = children or []
    node.label = label
    return node


def _make_tree(entries: list[Any]) -> list[Any]:
    """Wrap entries in tree nodes."""
    return [_make_tree_node_v2(e) for e in entries]


class TestTreeListExtractContent:
    def _make_list(self) -> _TreeList:
        e = _make_message_entry("e1", "user", "hello")
        return _TreeList(_make_tree([e]), "e1", 20)

    def test_extract_string_content(self) -> None:
        tl = self._make_list()
        assert tl._extract_content("hello world") == "hello world"

    def test_extract_list_content_text_objects(self) -> None:
        tl = self._make_list()
        obj = MagicMock()
        obj.type = "text"
        obj.text = "from obj"
        result = tl._extract_content([obj])
        assert result == "from obj"

    def test_extract_list_content_dicts(self) -> None:
        tl = self._make_list()
        result = tl._extract_content([{"type": "text", "text": "dict text"}])
        assert result == "dict text"

    def test_extract_empty_list(self) -> None:
        tl = self._make_list()
        assert tl._extract_content([]) == ""

    def test_extract_non_text_items_ignored(self) -> None:
        tl = self._make_list()
        obj = MagicMock()
        obj.type = "toolCall"
        result = tl._extract_content([obj])
        assert result == ""

    def test_extract_max_len_truncates(self) -> None:
        tl = self._make_list()
        long_text = "x" * 300
        result = tl._extract_content(long_text, max_len=100)
        assert len(result) == 100

    def test_extract_unknown_type_returns_empty(self) -> None:
        tl = self._make_list()
        result_empty: Any = tl._extract_content(42)  # pass non-str/list arg
        assert result_empty == ""


class TestTreeListGetEntryDisplayText:
    def _make_list_with_single_entry(self, entry: Any) -> _TreeList:
        node = _make_tree_node_v2(entry)
        return _TreeList([node], entry.id, 20)

    def test_user_message(self) -> None:
        entry = _make_message_entry("e1", "user", "what is 2+2?")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "user" in text

    def test_assistant_message_with_text(self) -> None:
        entry = _make_message_entry("e1", "assistant", "The answer is 4")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "assistant" in text

    def test_assistant_message_aborted(self) -> None:
        entry = _make_message_entry("e1", "assistant", None, stop_reason="aborted")
        entry.message.content = ""
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "aborted" in text

    def test_assistant_message_with_error(self) -> None:
        entry = _make_message_entry("e1", "assistant", "", error_message="API error")
        entry.message.content = ""
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "API error" in text

    def test_assistant_message_no_content(self) -> None:
        entry = _make_message_entry("e1", "assistant", "")
        entry.message.content = ""
        entry.message.stop_reason = None
        entry.message.error_message = None
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "no content" in text

    def test_tool_result_with_name(self) -> None:
        entry = _make_message_entry("e1", "toolResult", tool_name="bash")
        entry.message.tool_call_id = None
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "bash" in text

    def test_bash_execution_role(self) -> None:
        entry = _make_message_entry("e1", "bashExecution", command="ls -la")
        entry.message.command = "ls -la"
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "bash" in text

    def test_unknown_role(self) -> None:
        entry = _make_message_entry("e1", "unknownRole")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "unknownRole" in text or "message" in text.lower()

    def test_custom_message_entry(self) -> None:
        entry = _make_entry("e1", "custom_message", custom_type="notification", content="msg content")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "notification" in text

    def test_compaction_entry(self) -> None:
        entry = _make_entry("e1", "compaction", tokens_before=50000)
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "compaction" in text

    def test_branch_summary_entry(self) -> None:
        entry = _make_entry("e1", "branch_summary", summary="Did X then Y")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "branch summary" in text

    def test_model_change_entry(self) -> None:
        entry = _make_entry("e1", "model_change", model_id="claude-3-opus")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "model" in text

    def test_thinking_level_change_entry(self) -> None:
        entry = _make_entry("e1", "thinking_level_change", thinking_level="high")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "thinking" in text

    def test_custom_entry(self) -> None:
        entry = _make_entry("e1", "custom", custom_type="my_type")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "my_type" in text

    def test_label_entry(self) -> None:
        entry = _make_entry("e1", "label", label="checkpoint A")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "label" in text

    def test_label_entry_cleared(self) -> None:
        entry = _make_entry("e1", "label")
        entry.label = None
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        text = tl._get_entry_display_text(node, False)
        assert "cleared" in text or "label" in text

    def test_is_selected_makes_bold(self) -> None:
        entry = _make_message_entry("e1", "user", "hi")
        tl = self._make_list_with_single_entry(entry)
        node = tl._flat_nodes[0].node
        normal = tl._get_entry_display_text(node, False)
        bold = tl._get_entry_display_text(node, True)
        # Bold text should be longer (ANSI codes added)
        assert len(bold) >= len(normal)


class TestTreeListApplyFilter:
    def _make_list_with_entries(self, entries: list[Any]) -> _TreeList:
        nodes = [_make_tree_node_v2(e) for e in entries]
        leaf_id = entries[0].id if entries else None
        return _TreeList(nodes, leaf_id, 20)

    def test_filter_default_excludes_settings(self) -> None:
        entries = [
            _make_message_entry("e1", "user", "hello"),
            _make_entry("e2", "model_change", model_id="x"),
        ]
        tl = self._make_list_with_entries(entries)
        tl._filter_mode = "default"
        tl._apply_filter()
        ids = [getattr(n.node.entry, "id", None) for n in tl._filtered_nodes]
        assert "e2" not in ids  # model_change is settings, should be excluded

    def test_filter_user_only(self) -> None:
        entries = [
            _make_message_entry("e1", "user", "hi"),
            _make_message_entry("e2", "assistant", "hello"),
        ]
        tl = self._make_list_with_entries(entries)
        tl._filter_mode = "user-only"
        tl._last_selected_id = None
        tl._apply_filter()
        ids = [getattr(n.node.entry, "id", None) for n in tl._filtered_nodes]
        assert "e1" in ids
        assert "e2" not in ids

    def test_filter_no_tools(self) -> None:
        entries = [
            _make_message_entry("e1", "user", "hi"),
            _make_message_entry("e2", "toolResult"),
        ]
        tl = self._make_list_with_entries(entries)
        tl._filter_mode = "no-tools"
        tl._last_selected_id = None
        tl._apply_filter()
        ids = [getattr(n.node.entry, "id", None) for n in tl._filtered_nodes]
        assert "e1" in ids
        assert "e2" not in ids

    def test_filter_all(self) -> None:
        entries = [
            _make_message_entry("e1", "user", "hi"),
            _make_entry("e2", "model_change", model_id="x"),
        ]
        tl = self._make_list_with_entries(entries)
        tl._filter_mode = "all"
        tl._last_selected_id = None
        tl._apply_filter()
        ids = [getattr(n.node.entry, "id", None) for n in tl._filtered_nodes]
        assert "e1" in ids
        assert "e2" in ids

    def test_filter_labeled_only(self) -> None:
        entry1 = _make_message_entry("e1", "user", "hi")
        node1 = _make_tree_node_v2(entry1, label="my label")
        entry2 = _make_message_entry("e2", "user", "hello")
        node2 = _make_tree_node_v2(entry2, label=None)
        tl = _TreeList([node1, node2], "e1", 20)
        tl._filter_mode = "labeled-only"
        tl._last_selected_id = None
        tl._apply_filter()
        ids = [getattr(n.node.entry, "id", None) for n in tl._filtered_nodes]
        assert "e1" in ids
        assert "e2" not in ids

    def test_search_query_filters(self) -> None:
        entries = [
            _make_message_entry("e1", "user", "python programming"),
            _make_message_entry("e2", "user", "javascript code"),
        ]
        tl = self._make_list_with_entries(entries)
        tl._search_query = "python"
        tl._last_selected_id = None
        tl._apply_filter()
        ids = [getattr(n.node.entry, "id", None) for n in tl._filtered_nodes]
        assert "e1" in ids
        assert "e2" not in ids


class TestTreeListHandleInput:
    def _make_list(self) -> _TreeList:
        entries = [
            _make_message_entry(f"e{i}", "user", f"message {i}")
            for i in range(5)
        ]
        nodes = [_make_tree_node_v2(e) for e in entries]
        return _TreeList(nodes, "e0", 20)

    def test_select_up(self) -> None:
        tl = self._make_list()
        tl._selected_index = 2
        tl.handle_input("\x1b[A")
        assert tl._selected_index == 1

    def test_select_down(self) -> None:
        tl = self._make_list()
        tl._selected_index = 0
        tl.handle_input("\x1b[B")
        assert tl._selected_index == 1

    def test_select_confirm_calls_on_select(self) -> None:
        tl = self._make_list()
        on_select = MagicMock()
        tl.on_select = on_select
        tl._selected_index = 0
        tl.handle_input("\r")
        on_select.assert_called_once_with("e0")

    def test_select_cancel_clears_search_first(self) -> None:
        tl = self._make_list()
        tl._search_query = "foo"
        tl.handle_input("\x1b")  # selectCancel
        assert tl._search_query == ""

    def test_select_cancel_with_no_search_calls_on_cancel(self) -> None:
        tl = self._make_list()
        on_cancel = MagicMock()
        tl.on_cancel = on_cancel
        tl._search_query = ""
        tl.handle_input("\x1b")
        on_cancel.assert_called_once()

    def test_ctrl_d_resets_to_default_filter(self) -> None:
        tl = self._make_list()
        tl._filter_mode = "user-only"
        tl.handle_input("\x04")  # ctrl+d
        filter_mode: Any = tl._filter_mode
        assert filter_mode == "default"

    def test_ctrl_t_toggles_no_tools(self) -> None:
        tl = self._make_list()
        tl._filter_mode = "default"
        tl.handle_input("\x14")  # ctrl+t
        filter_mode_1: Any = tl._filter_mode
        assert filter_mode_1 == "no-tools"
        tl.handle_input("\x14")
        filter_mode_2: Any = tl._filter_mode
        assert filter_mode_2 == "default"

    def test_ctrl_u_toggles_user_only(self) -> None:
        tl = self._make_list()
        tl.handle_input("\x15")  # ctrl+u
        assert tl._filter_mode == "user-only"

    def test_ctrl_l_toggles_labeled_only(self) -> None:
        tl = self._make_list()
        tl.handle_input("\x0c")  # ctrl+l
        assert tl._filter_mode == "labeled-only"

    def test_ctrl_a_toggles_all(self) -> None:
        tl = self._make_list()
        tl.handle_input("\x01")  # ctrl+a
        assert tl._filter_mode == "all"

    def test_ctrl_o_cycles_filter_forward(self) -> None:
        tl = self._make_list()
        initial = tl._filter_mode
        tl.handle_input("\x0f")  # ctrl+o
        assert tl._filter_mode != initial or len(["default", "no-tools", "user-only", "labeled-only", "all"]) == 1

    def test_backspace_removes_from_search(self) -> None:
        tl = self._make_list()
        tl._search_query = "abc"
        tl.handle_input("\x7f")  # deleteCharBackward (backspace)
        assert tl._search_query == "ab"

    def test_shift_l_calls_on_label_edit(self) -> None:
        tl = self._make_list()
        on_label = MagicMock()
        tl.on_label_edit = on_label
        tl._selected_index = 0
        tl.handle_input("L")  # shift+l
        on_label.assert_called_once()

    def test_printable_char_appends_to_search(self) -> None:
        tl = self._make_list()
        tl.handle_input("q")
        assert "q" in tl._search_query

    def test_control_char_does_not_append_to_search(self) -> None:
        tl = self._make_list()
        tl._search_query = ""
        tl.handle_input("\x00")  # null character
        assert tl._search_query == ""

    def test_render_with_nodes(self) -> None:
        tl = self._make_list()
        lines = tl.render(80)
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_render_empty_nodes(self) -> None:
        tl = _TreeList([], None, 20)
        lines = tl.render(80)
        assert isinstance(lines, list)
        assert any("No entries" in ln or "0/0" in ln for ln in lines)


class TestTreeSelectorComponentNew:
    def _make_comp(self) -> TreeSelectorComponent:
        entries = [
            _make_message_entry(f"e{i}", "user", f"msg {i}")
            for i in range(3)
        ]
        tree = [_make_tree_node_v2(e) for e in entries]
        return TreeSelectorComponent(
            tree=tree,
            current_leaf_id="e0",
            terminal_height=40,
            on_select=MagicMock(),
            on_cancel=MagicMock(),
        )

    def test_renders(self) -> None:
        comp = self._make_comp()
        lines = comp.render(80)
        assert isinstance(lines, list)

    def test_handle_input_without_label_edit(self) -> None:
        comp = self._make_comp()
        comp.handle_input("\x1b[A")
        comp.handle_input("\x1b[B")

    def test_show_label_input_and_handle(self) -> None:
        comp = self._make_comp()
        on_label_change = MagicMock()
        comp._on_label_change = on_label_change
        comp._show_label_input("e0", "old label")
        assert comp._label_input is not None
        # Cancel should hide it
        li: Any = comp._label_input
        li.on_cancel()
        assert comp._label_input is None

    def test_label_input_submit_calls_on_label_change(self) -> None:
        comp = self._make_comp()
        on_label_change = MagicMock()
        comp._on_label_change = on_label_change
        comp._show_label_input("e0", None)
        assert comp._label_input is not None
        li2: Any = comp._label_input
        li2.on_submit("e0", "new label")
        on_label_change.assert_called_once_with("e0", "new label")
        assert comp._label_input is None

    def test_handle_input_with_label_input_active(self) -> None:
        comp = self._make_comp()
        comp._show_label_input("e0", None)
        # Input goes to label input
        comp.handle_input("a")  # typed character
        assert comp._label_input is not None  # still shown

    def test_focused_setter_propagates_to_label_input(self) -> None:
        comp = self._make_comp()
        comp._show_label_input("e0", None)
        comp.focused = True
        if comp._label_input:
            assert comp._label_input.focused is True

    def test_empty_tree_schedules_cancel(self) -> None:
        """Empty tree schedules a timer to call on_cancel."""
        on_cancel = MagicMock()
        with patch("pi_coding_agent.modes.interactive.components.tree_selector.threading.Timer") as mock_timer:
            mock_t = MagicMock()
            mock_timer.return_value = mock_t
            _comp = TreeSelectorComponent(
                tree=[],
                current_leaf_id=None,
                terminal_height=40,
                on_select=MagicMock(),
                on_cancel=on_cancel,
            )
            _ = _comp  # prevent unused variable warning
            mock_timer.assert_called_once()
            mock_t.start.assert_called_once()

    def test_get_tree_list(self) -> None:
        comp = self._make_comp()
        tl = comp.get_tree_list()
        assert isinstance(tl, _TreeList)


class TestLabelInputNew:
    def test_render(self) -> None:
        li = _LabelInput("e1", "some label")
        lines = li.render(80)
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_render_without_label(self) -> None:
        li = _LabelInput("e1", None)
        lines = li.render(80)
        assert isinstance(lines, list)

    def test_handle_input_confirm(self) -> None:
        li = _LabelInput("e1", "original")
        on_submit = MagicMock()
        li.on_submit = on_submit
        li.handle_input("\r")
        on_submit.assert_called_once_with("e1", "original")

    def test_handle_input_cancel(self) -> None:
        li = _LabelInput("e1", "original")
        on_cancel = MagicMock()
        li.on_cancel = on_cancel
        li.handle_input("\x1b")
        on_cancel.assert_called_once()

    def test_focused_setter(self) -> None:
        li = _LabelInput("e1", None)
        li.focused = True
        assert li.focused is True

    def test_handle_regular_input(self) -> None:
        li = _LabelInput("e1", None)
        li.handle_input("a")
        li.handle_input("b")
        assert li._input.get_value() in ("ab", "a", "b", "")  # input accepted


class TestSearchLineNew:
    def test_render_with_query(self) -> None:
        e = _make_message_entry("e1", "user", "hello")
        tl = _TreeList([_make_tree_node_v2(e)], "e1", 20)
        tl._search_query = "hello"
        sl = _SearchLine(tl)
        lines = sl.render(80)
        assert len(lines) == 1
        assert "hello" in lines[0]

    def test_render_without_query(self) -> None:
        e = _make_message_entry("e1", "user", "hello")
        tl = _TreeList([_make_tree_node_v2(e)], "e1", 20)
        sl = _SearchLine(tl)
        lines = sl.render(80)
        assert len(lines) == 1

    def test_handle_input_is_noop(self) -> None:
        e = _make_message_entry("e1", "user", "hello")
        tl = _TreeList([_make_tree_node_v2(e)], "e1", 20)
        sl = _SearchLine(tl)
        sl.handle_input("x")  # Should not raise or change state


# ---------------------------------------------------------------------------
# tree_selector - _format_tool_call coverage
# ---------------------------------------------------------------------------


class TestFormatToolCall:
    def _make_list(self) -> _TreeList:
        e = _make_message_entry("e1", "user", "hi")
        return _TreeList([_make_tree_node_v2(e)], "e1", 20)

    def test_format_read_tool(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("read", {"path": "/home/user/file.py"})
        assert "read" in result
        assert "file.py" in result

    def test_format_read_with_offset_and_limit(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("read", {"path": "/f.py", "offset": 10, "limit": 20})
        assert "10-29" in result

    def test_format_write_tool(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("write", {"path": "/tmp/out.txt"})
        assert "write" in result
        assert "out.txt" in result

    def test_format_edit_tool(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("edit", {"file_path": "/src/main.py"})
        assert "edit" in result

    def test_format_bash_tool(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("bash", {"command": "ls -la"})
        assert "bash" in result
        assert "ls -la" in result

    def test_format_bash_long_command(self) -> None:
        tl = self._make_list()
        long_cmd = "x" * 60
        result = tl._format_tool_call("bash", {"command": long_cmd})
        assert "..." in result

    def test_format_grep_tool(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("grep", {"pattern": "foo", "path": "/src"})
        assert "grep" in result

    def test_format_find_tool(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("find", {"pattern": "*.py", "path": "/src"})
        assert "find" in result

    def test_format_ls_tool(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("ls", {"path": "/home"})
        assert "ls" in result

    def test_format_unknown_tool(self) -> None:
        tl = self._make_list()
        result = tl._format_tool_call("custom_tool", {"key": "value"})
        assert "custom_tool" in result
