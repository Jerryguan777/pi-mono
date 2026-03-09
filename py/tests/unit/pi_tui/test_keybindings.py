"""Tests for pi_tui.keybindings module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pi_tui.keybindings import (
    DEFAULT_EDITOR_KEYBINDINGS,
    EditorKeybindingsManager,
    get_editor_keybindings,
    set_editor_keybindings,
)


# ============================================================================
# DEFAULT_EDITOR_KEYBINDINGS
# ============================================================================


class TestDefaultEditorKeybindings:
    """Tests that DEFAULT_EDITOR_KEYBINDINGS contains the expected actions."""

    def test_has_cursor_movement_actions(self) -> None:
        cursor_actions = [
            "cursorUp",
            "cursorDown",
            "cursorLeft",
            "cursorRight",
            "cursorWordLeft",
            "cursorWordRight",
            "cursorLineStart",
            "cursorLineEnd",
            "jumpForward",
            "jumpBackward",
            "pageUp",
            "pageDown",
        ]
        for action in cursor_actions:
            assert action in DEFAULT_EDITOR_KEYBINDINGS, f"Missing cursor action: {action}"

    def test_has_deletion_actions(self) -> None:
        deletion_actions = [
            "deleteCharBackward",
            "deleteCharForward",
            "deleteWordBackward",
            "deleteWordForward",
            "deleteToLineStart",
            "deleteToLineEnd",
        ]
        for action in deletion_actions:
            assert action in DEFAULT_EDITOR_KEYBINDINGS, f"Missing deletion action: {action}"

    def test_has_text_input_actions(self) -> None:
        for action in ["newLine", "submit", "tab"]:
            assert action in DEFAULT_EDITOR_KEYBINDINGS, f"Missing text input action: {action}"

    def test_has_selection_actions(self) -> None:
        selection_actions = [
            "selectUp",
            "selectDown",
            "selectPageUp",
            "selectPageDown",
            "selectConfirm",
            "selectCancel",
        ]
        for action in selection_actions:
            assert action in DEFAULT_EDITOR_KEYBINDINGS, f"Missing selection action: {action}"

    def test_has_clipboard_actions(self) -> None:
        assert "copy" in DEFAULT_EDITOR_KEYBINDINGS

    def test_has_kill_ring_actions(self) -> None:
        assert "yank" in DEFAULT_EDITOR_KEYBINDINGS
        assert "yankPop" in DEFAULT_EDITOR_KEYBINDINGS

    def test_has_undo_action(self) -> None:
        assert "undo" in DEFAULT_EDITOR_KEYBINDINGS

    def test_has_tool_output_actions(self) -> None:
        assert "expandTools" in DEFAULT_EDITOR_KEYBINDINGS

    def test_has_session_actions(self) -> None:
        session_actions = [
            "toggleSessionPath",
            "toggleSessionSort",
            "renameSession",
            "deleteSession",
            "deleteSessionNoninvasive",
        ]
        for action in session_actions:
            assert action in DEFAULT_EDITOR_KEYBINDINGS, f"Missing session action: {action}"

    def test_specific_default_bindings(self) -> None:
        assert DEFAULT_EDITOR_KEYBINDINGS["cursorUp"] == "up"
        assert DEFAULT_EDITOR_KEYBINDINGS["cursorDown"] == "down"
        assert DEFAULT_EDITOR_KEYBINDINGS["submit"] == "enter"
        assert DEFAULT_EDITOR_KEYBINDINGS["tab"] == "tab"
        assert DEFAULT_EDITOR_KEYBINDINGS["newLine"] == "shift+enter"
        assert DEFAULT_EDITOR_KEYBINDINGS["copy"] == "ctrl+c"
        assert DEFAULT_EDITOR_KEYBINDINGS["yank"] == "ctrl+y"
        assert DEFAULT_EDITOR_KEYBINDINGS["undo"] == "ctrl+-"

    def test_multi_key_bindings(self) -> None:
        """Actions with multiple key bindings should be lists."""
        assert DEFAULT_EDITOR_KEYBINDINGS["cursorLeft"] == ["left", "ctrl+b"]
        assert DEFAULT_EDITOR_KEYBINDINGS["cursorRight"] == ["right", "ctrl+f"]
        assert DEFAULT_EDITOR_KEYBINDINGS["cursorWordLeft"] == ["alt+left", "ctrl+left", "alt+b"]
        assert DEFAULT_EDITOR_KEYBINDINGS["cursorWordRight"] == ["alt+right", "ctrl+right", "alt+f"]
        assert DEFAULT_EDITOR_KEYBINDINGS["cursorLineStart"] == ["home", "ctrl+a"]
        assert DEFAULT_EDITOR_KEYBINDINGS["cursorLineEnd"] == ["end", "ctrl+e"]
        assert DEFAULT_EDITOR_KEYBINDINGS["deleteCharForward"] == ["delete", "ctrl+d"]
        assert DEFAULT_EDITOR_KEYBINDINGS["deleteWordBackward"] == ["ctrl+w", "alt+backspace"]
        assert DEFAULT_EDITOR_KEYBINDINGS["selectCancel"] == ["escape", "ctrl+c"]


# ============================================================================
# EditorKeybindingsManager construction
# ============================================================================


class TestEditorKeybindingsManagerConstruction:
    """Tests for EditorKeybindingsManager initialization."""

    def test_default_construction(self) -> None:
        manager = EditorKeybindingsManager()
        # Should have all default actions
        for action in DEFAULT_EDITOR_KEYBINDINGS:
            keys = manager.get_keys(action)
            assert len(keys) > 0, f"Action {action} should have at least one key"

    def test_construction_with_none_config(self) -> None:
        manager = EditorKeybindingsManager(config=None)
        keys = manager.get_keys("submit")
        assert keys == ["enter"]

    def test_construction_with_empty_config(self) -> None:
        manager = EditorKeybindingsManager(config={})
        keys = manager.get_keys("submit")
        assert keys == ["enter"]

    def test_construction_with_override_single_key(self) -> None:
        manager = EditorKeybindingsManager(config={"submit": "ctrl+enter"})
        keys = manager.get_keys("submit")
        assert keys == ["ctrl+enter"]

    def test_construction_with_override_multiple_keys(self) -> None:
        manager = EditorKeybindingsManager(config={"submit": ["enter", "ctrl+enter"]})
        keys = manager.get_keys("submit")
        assert keys == ["enter", "ctrl+enter"]

    def test_construction_override_does_not_affect_other_actions(self) -> None:
        manager = EditorKeybindingsManager(config={"submit": "ctrl+enter"})
        # cursorUp should still have the default
        keys = manager.get_keys("cursorUp")
        assert keys == ["up"]

    def test_construction_with_custom_action(self) -> None:
        """Config can add actions not in defaults."""
        manager = EditorKeybindingsManager(config={"customAction": "ctrl+x"})
        keys = manager.get_keys("customAction")
        assert keys == ["ctrl+x"]

    def test_single_key_defaults_become_lists(self) -> None:
        """Single-string defaults should be normalized to lists internally."""
        manager = EditorKeybindingsManager()
        keys = manager.get_keys("cursorUp")
        assert isinstance(keys, list)
        assert keys == ["up"]

    def test_list_defaults_are_preserved(self) -> None:
        manager = EditorKeybindingsManager()
        keys = manager.get_keys("cursorLeft")
        assert keys == ["left", "ctrl+b"]


# ============================================================================
# get_keys()
# ============================================================================


class TestGetKeys:
    """Tests for EditorKeybindingsManager.get_keys()."""

    def test_returns_keys_for_known_action(self) -> None:
        manager = EditorKeybindingsManager()
        keys = manager.get_keys("cursorUp")
        assert keys == ["up"]

    def test_returns_empty_list_for_unknown_action(self) -> None:
        manager = EditorKeybindingsManager()
        keys = manager.get_keys("nonExistentAction")
        assert keys == []

    def test_returns_copy_not_reference(self) -> None:
        """get_keys should return a copy so mutations don't affect internals."""
        manager = EditorKeybindingsManager()
        keys = manager.get_keys("cursorLeft")
        keys.append("ctrl+z")
        # Internal state should be unaffected
        assert manager.get_keys("cursorLeft") == ["left", "ctrl+b"]

    def test_returns_all_keys_for_multi_key_action(self) -> None:
        manager = EditorKeybindingsManager()
        keys = manager.get_keys("cursorWordLeft")
        assert keys == ["alt+left", "ctrl+left", "alt+b"]


# ============================================================================
# matches()
# ============================================================================


class TestMatches:
    """Tests for EditorKeybindingsManager.matches()."""

    def test_matches_single_key_action(self) -> None:
        manager = EditorKeybindingsManager()
        # "cursorUp" is bound to "up", which maps to legacy sequence \x1b[A
        assert manager.matches("\x1b[A", "cursorUp") is True

    def test_no_match_for_wrong_key(self) -> None:
        manager = EditorKeybindingsManager()
        # "cursorUp" should not match down arrow
        assert manager.matches("\x1b[B", "cursorUp") is False

    def test_matches_unknown_action_returns_false(self) -> None:
        manager = EditorKeybindingsManager()
        assert manager.matches("\x1b[A", "nonExistentAction") is False

    def test_matches_multi_key_action_first_key(self) -> None:
        manager = EditorKeybindingsManager()
        # "cursorLeft" is bound to ["left", "ctrl+b"]
        # left arrow legacy sequence
        assert manager.matches("\x1b[D", "cursorLeft") is True

    def test_matches_multi_key_action_second_key(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+b is \x02
        assert manager.matches("\x02", "cursorLeft") is True

    def test_matches_enter_for_submit(self) -> None:
        manager = EditorKeybindingsManager()
        assert manager.matches("\r", "submit") is True

    def test_matches_tab(self) -> None:
        manager = EditorKeybindingsManager()
        assert manager.matches("\t", "tab") is True

    def test_matches_backspace_for_delete_char_backward(self) -> None:
        manager = EditorKeybindingsManager()
        assert manager.matches("\x7f", "deleteCharBackward") is True

    def test_matches_ctrl_a_for_cursor_line_start(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+a is \x01
        assert manager.matches("\x01", "cursorLineStart") is True

    def test_matches_ctrl_e_for_cursor_line_end(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+e is \x05
        assert manager.matches("\x05", "cursorLineEnd") is True

    def test_matches_ctrl_k_for_delete_to_line_end(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+k is \x0b
        assert manager.matches("\x0b", "deleteToLineEnd") is True

    def test_matches_ctrl_u_for_delete_to_line_start(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+u is \x15
        assert manager.matches("\x15", "deleteToLineStart") is True

    def test_matches_ctrl_y_for_yank(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+y is \x19
        assert manager.matches("\x19", "yank") is True

    def test_matches_ctrl_w_for_delete_word_backward(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+w is \x17
        assert manager.matches("\x17", "deleteWordBackward") is True

    def test_matches_escape_for_select_cancel(self) -> None:
        manager = EditorKeybindingsManager()
        assert manager.matches("\x1b", "selectCancel") is True

    def test_matches_ctrl_c_for_select_cancel(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+c is \x03
        assert manager.matches("\x03", "selectCancel") is True

    def test_matches_ctrl_c_for_copy(self) -> None:
        manager = EditorKeybindingsManager()
        assert manager.matches("\x03", "copy") is True

    def test_matches_with_overridden_binding(self) -> None:
        manager = EditorKeybindingsManager(config={"submit": "ctrl+enter"})
        # Original enter should no longer match
        assert manager.matches("\r", "submit") is False

    def test_matches_delete_for_delete_char_forward(self) -> None:
        manager = EditorKeybindingsManager()
        # delete key legacy sequence
        assert manager.matches("\x1b[3~", "deleteCharForward") is True

    def test_matches_ctrl_d_for_delete_char_forward(self) -> None:
        manager = EditorKeybindingsManager()
        # ctrl+d is \x04
        assert manager.matches("\x04", "deleteCharForward") is True

    def test_matches_home_for_cursor_line_start(self) -> None:
        manager = EditorKeybindingsManager()
        assert manager.matches("\x1b[H", "cursorLineStart") is True

    def test_matches_end_for_cursor_line_end(self) -> None:
        manager = EditorKeybindingsManager()
        assert manager.matches("\x1b[F", "cursorLineEnd") is True


# ============================================================================
# set_config()
# ============================================================================


class TestSetConfig:
    """Tests for EditorKeybindingsManager.set_config()."""

    def test_set_config_overrides_action(self) -> None:
        manager = EditorKeybindingsManager()
        manager.set_config({"submit": "ctrl+m"})
        keys = manager.get_keys("submit")
        assert keys == ["ctrl+m"]

    def test_set_config_preserves_defaults_for_non_overridden(self) -> None:
        manager = EditorKeybindingsManager()
        manager.set_config({"submit": "ctrl+m"})
        keys = manager.get_keys("cursorUp")
        assert keys == ["up"]

    def test_set_config_can_add_new_action(self) -> None:
        manager = EditorKeybindingsManager()
        manager.set_config({"myCustom": "ctrl+shift+x"})
        keys = manager.get_keys("myCustom")
        assert keys == ["ctrl+shift+x"]

    def test_set_config_replaces_previous_config(self) -> None:
        manager = EditorKeybindingsManager()
        manager.set_config({"submit": "ctrl+m"})
        # Now set a different config - previous overrides should be gone
        manager.set_config({"cursorUp": "ctrl+p"})
        # submit should be back to default
        keys = manager.get_keys("submit")
        assert keys == ["enter"]
        # cursorUp should have the new override
        keys = manager.get_keys("cursorUp")
        assert keys == ["ctrl+p"]

    def test_set_config_with_empty_dict_restores_defaults(self) -> None:
        manager = EditorKeybindingsManager(config={"submit": "ctrl+m"})
        assert manager.get_keys("submit") == ["ctrl+m"]
        manager.set_config({})
        assert manager.get_keys("submit") == ["enter"]

    def test_set_config_with_list_value(self) -> None:
        manager = EditorKeybindingsManager()
        manager.set_config({"submit": ["enter", "ctrl+m"]})
        keys = manager.get_keys("submit")
        assert keys == ["enter", "ctrl+m"]

    def test_set_config_matches_use_new_bindings(self) -> None:
        manager = EditorKeybindingsManager()
        manager.set_config({"cursorUp": "ctrl+p"})
        # ctrl+p is \x10
        assert manager.matches("\x10", "cursorUp") is True
        # original up arrow should no longer match
        assert manager.matches("\x1b[A", "cursorUp") is False


# ============================================================================
# get_editor_keybindings() / set_editor_keybindings()
# ============================================================================


class TestGlobalKeybindings:
    """Tests for get_editor_keybindings() and set_editor_keybindings()."""

    def test_get_editor_keybindings_returns_manager(self) -> None:
        with patch("pi_tui.keybindings._global_editor_keybindings", None):
            manager = get_editor_keybindings()
            assert isinstance(manager, EditorKeybindingsManager)

    def test_get_editor_keybindings_returns_same_instance(self) -> None:
        with patch("pi_tui.keybindings._global_editor_keybindings", None):
            manager1 = get_editor_keybindings()
            manager2 = get_editor_keybindings()
            assert manager1 is manager2

    def test_set_editor_keybindings_replaces_global(self) -> None:
        with patch("pi_tui.keybindings._global_editor_keybindings", None):
            original = get_editor_keybindings()
            custom = EditorKeybindingsManager(config={"submit": "ctrl+m"})
            set_editor_keybindings(custom)
            current = get_editor_keybindings()
            assert current is custom
            assert current is not original

    def test_set_editor_keybindings_custom_manager_has_overrides(self) -> None:
        with patch("pi_tui.keybindings._global_editor_keybindings", None):
            custom = EditorKeybindingsManager(config={"submit": "ctrl+m"})
            set_editor_keybindings(custom)
            manager = get_editor_keybindings()
            assert manager.get_keys("submit") == ["ctrl+m"]

    def test_get_editor_keybindings_default_has_all_actions(self) -> None:
        with patch("pi_tui.keybindings._global_editor_keybindings", None):
            manager = get_editor_keybindings()
            for action in DEFAULT_EDITOR_KEYBINDINGS:
                assert len(manager.get_keys(action)) > 0
