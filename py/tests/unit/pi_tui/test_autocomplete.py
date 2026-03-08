"""Tests for pi_tui.autocomplete module."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pi_tui.autocomplete import (
    AutocompleteItem,
    CombinedAutocompleteProvider,
    CompletionResult,
    SlashCommand,
    SuggestionResult,
    _build_completion_value,
    _expand_home_path,
    _extract_quoted_prefix,
    _find_last_delimiter,
    _find_unclosed_quote_start,
    _is_token_start,
    _parse_path_prefix,
    _ParsedPrefix,
    _walk_directory_with_fd,
)
from pi_tui.components.select_list import SelectItem


# ---------------------------------------------------------------------------
# AutocompleteItem alias
# ---------------------------------------------------------------------------


class TestAutocompleteItemAlias:
    def test_is_same_as_select_item(self) -> None:
        assert AutocompleteItem is SelectItem

    def test_create_instance(self) -> None:
        item = AutocompleteItem(value="foo", label="Foo", description="desc")
        assert item.value == "foo"
        assert item.label == "Foo"
        assert item.description == "desc"

    def test_description_default_none(self) -> None:
        item = AutocompleteItem(value="v", label="l")
        assert item.description is None


# ---------------------------------------------------------------------------
# SlashCommand dataclass
# ---------------------------------------------------------------------------


class TestSlashCommand:
    def test_basic_creation(self) -> None:
        cmd = SlashCommand(name="help", description="Show help")
        assert cmd.name == "help"
        assert cmd.description == "Show help"
        assert cmd.get_argument_completions is None

    def test_defaults(self) -> None:
        cmd = SlashCommand(name="test")
        assert cmd.description is None
        assert cmd.get_argument_completions is None

    def test_with_argument_completions(self) -> None:
        def completions(text: str) -> list[AutocompleteItem] | None:
            return [AutocompleteItem(value="arg1", label="arg1")]

        cmd = SlashCommand(name="cmd", description="desc", get_argument_completions=completions)
        result = cmd.get_argument_completions("some text")  # type: ignore[misc]
        assert result is not None
        assert len(result) == 1
        assert result[0].value == "arg1"


# ---------------------------------------------------------------------------
# Private helper functions
# ---------------------------------------------------------------------------


class TestFindLastDelimiter:
    def test_no_delimiter(self) -> None:
        assert _find_last_delimiter("hello") == -1

    def test_space(self) -> None:
        assert _find_last_delimiter("hello world") == 5

    def test_tab(self) -> None:
        assert _find_last_delimiter("hello\tworld") == 5

    def test_quote(self) -> None:
        assert _find_last_delimiter('path "file') == 5

    def test_equals(self) -> None:
        assert _find_last_delimiter("key=val") == 3

    def test_single_quote(self) -> None:
        assert _find_last_delimiter("it's") == 2

    def test_empty_string(self) -> None:
        assert _find_last_delimiter("") == -1

    def test_multiple_delimiters_returns_last(self) -> None:
        assert _find_last_delimiter("a b c") == 3


class TestFindUnclosedQuoteStart:
    def test_no_quotes(self) -> None:
        assert _find_unclosed_quote_start("hello") is None

    def test_closed_quote(self) -> None:
        assert _find_unclosed_quote_start('"hello"') is None

    def test_unclosed_quote(self) -> None:
        assert _find_unclosed_quote_start('"hello') == 0

    def test_unclosed_after_closed(self) -> None:
        assert _find_unclosed_quote_start('"a" "b') == 4

    def test_empty(self) -> None:
        assert _find_unclosed_quote_start("") is None

    def test_multiple_closed(self) -> None:
        assert _find_unclosed_quote_start('"a" "b"') is None


class TestIsTokenStart:
    def test_start_of_string(self) -> None:
        assert _is_token_start("hello", 0) is True

    def test_after_space(self) -> None:
        assert _is_token_start("a b", 2) is True

    def test_after_tab(self) -> None:
        assert _is_token_start("a\tb", 2) is True

    def test_middle_of_word(self) -> None:
        assert _is_token_start("hello", 2) is False


class TestExtractQuotedPrefix:
    def test_no_quotes(self) -> None:
        assert _extract_quoted_prefix("hello") is None

    def test_closed_quotes(self) -> None:
        assert _extract_quoted_prefix('"hello"') is None

    def test_unclosed_quote_at_start(self) -> None:
        assert _extract_quoted_prefix('"path/to') == '"path/to'

    def test_unclosed_at_prefix(self) -> None:
        assert _extract_quoted_prefix('@"path/to') == '@"path/to'

    def test_unclosed_quote_after_space(self) -> None:
        assert _extract_quoted_prefix('some "path') == '"path'

    def test_at_prefix_not_at_token_start(self) -> None:
        # @ not at a token boundary: "x@" has unclosed quote starting at index 0
        # but text[quote_start-1] check won't apply since quote_start == 0
        assert _extract_quoted_prefix('x@"path') is None

    def test_unclosed_not_at_token_start(self) -> None:
        # e.g. 'ab"cd' -- unclosed at index 2, but index 2 is not a token start
        assert _extract_quoted_prefix('ab"cd') is None


class TestParsePathPrefix:
    def test_at_quoted(self) -> None:
        result = _parse_path_prefix('@"some/path')
        assert result.raw_prefix == "some/path"
        assert result.is_at_prefix is True
        assert result.is_quoted_prefix is True

    def test_quoted(self) -> None:
        result = _parse_path_prefix('"some/path')
        assert result.raw_prefix == "some/path"
        assert result.is_at_prefix is False
        assert result.is_quoted_prefix is True

    def test_at(self) -> None:
        result = _parse_path_prefix("@src/file")
        assert result.raw_prefix == "src/file"
        assert result.is_at_prefix is True
        assert result.is_quoted_prefix is False

    def test_plain(self) -> None:
        result = _parse_path_prefix("src/file")
        assert result.raw_prefix == "src/file"
        assert result.is_at_prefix is False
        assert result.is_quoted_prefix is False


class TestBuildCompletionValue:
    def test_plain_file(self) -> None:
        result = _build_completion_value("file.py", is_directory=False, is_at_prefix=False, is_quoted_prefix=False)
        assert result == "file.py"

    def test_at_prefix(self) -> None:
        result = _build_completion_value("file.py", is_directory=False, is_at_prefix=True, is_quoted_prefix=False)
        assert result == "@file.py"

    def test_quoted(self) -> None:
        result = _build_completion_value("file.py", is_directory=False, is_at_prefix=False, is_quoted_prefix=True)
        assert result == '"file.py"'

    def test_at_quoted(self) -> None:
        result = _build_completion_value("file.py", is_directory=False, is_at_prefix=True, is_quoted_prefix=True)
        assert result == '@"file.py"'

    def test_space_in_path_forces_quotes(self) -> None:
        result = _build_completion_value("my file.py", is_directory=False, is_at_prefix=False, is_quoted_prefix=False)
        assert result == '"my file.py"'

    def test_at_prefix_with_space_in_path(self) -> None:
        result = _build_completion_value("my file.py", is_directory=False, is_at_prefix=True, is_quoted_prefix=False)
        assert result == '@"my file.py"'

    def test_directory(self) -> None:
        result = _build_completion_value("dir/", is_directory=True, is_at_prefix=False, is_quoted_prefix=False)
        assert result == "dir/"


class TestExpandHomePath:
    def test_tilde_slash(self) -> None:
        home = os.path.expanduser("~")
        assert _expand_home_path("~/foo") == os.path.join(home, "foo")

    def test_tilde_only(self) -> None:
        assert _expand_home_path("~") == os.path.expanduser("~")

    def test_no_tilde(self) -> None:
        assert _expand_home_path("foo") == "foo"

    def test_tilde_trailing_slash_preserved(self) -> None:
        result = _expand_home_path("~/foo/")
        assert result.endswith("/")

    def test_tilde_slash_no_trailing(self) -> None:
        result = _expand_home_path("~/foo")
        assert not result.endswith("/")


# ---------------------------------------------------------------------------
# _walk_directory_with_fd
# ---------------------------------------------------------------------------


class TestWalkDirectoryWithFd:
    def test_success(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file.py\nsubdir/\n"

        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result) as mock_run:
            entries = _walk_directory_with_fd("/base", "/usr/bin/fd", "query", 50)

        assert len(entries) == 2
        assert entries[0] == {"path": "file.py", "is_directory": False}
        assert entries[1] == {"path": "subdir/", "is_directory": True}

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "/usr/bin/fd"
        assert "--base-directory" in args
        assert "query" in args

    def test_empty_query_no_extra_arg(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file.py\n"

        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result) as mock_run:
            _walk_directory_with_fd("/base", "/usr/bin/fd", "", 50)

        args = mock_run.call_args[0][0]
        # Empty query should not append extra arg
        assert args[-1] != ""

    def test_timeout(self) -> None:
        with patch("pi_tui.autocomplete.subprocess.run", side_effect=subprocess.TimeoutExpired("fd", 10)):
            entries = _walk_directory_with_fd("/base", "/usr/bin/fd", "q", 50)
        assert entries == []

    def test_file_not_found(self) -> None:
        with patch("pi_tui.autocomplete.subprocess.run", side_effect=FileNotFoundError):
            entries = _walk_directory_with_fd("/base", "/usr/bin/fd", "q", 50)
        assert entries == []

    def test_os_error(self) -> None:
        with patch("pi_tui.autocomplete.subprocess.run", side_effect=OSError):
            entries = _walk_directory_with_fd("/base", "/usr/bin/fd", "q", 50)
        assert entries == []

    def test_nonzero_returncode(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            entries = _walk_directory_with_fd("/base", "/usr/bin/fd", "q", 50)
        assert entries == []

    def test_empty_stdout(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            entries = _walk_directory_with_fd("/base", "/usr/bin/fd", "q", 50)
        assert entries == []

    def test_git_entries_filtered(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ".git\n.git/config\nfoo/.git/bar\nreal.py\n"

        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            entries = _walk_directory_with_fd("/base", "/usr/bin/fd", "", 50)
        assert len(entries) == 1
        assert entries[0]["path"] == "real.py"

    def test_blank_lines_skipped(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "a.py\n\nb.py\n"

        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            entries = _walk_directory_with_fd("/base", "/usr/bin/fd", "", 50)
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# CombinedAutocompleteProvider — construction
# ---------------------------------------------------------------------------


class TestCombinedAutocompleteProviderConstruction:
    def test_defaults(self) -> None:
        provider = CombinedAutocompleteProvider()
        assert provider.commands == []
        assert provider.base_path == os.getcwd()
        assert provider.fd_path is None

    def test_custom_args(self) -> None:
        cmds = [SlashCommand(name="test")]
        provider = CombinedAutocompleteProvider(commands=cmds, base_path="/tmp", fd_path="/usr/bin/fd")
        assert provider.commands is cmds
        assert provider.base_path == "/tmp"
        assert provider.fd_path == "/usr/bin/fd"


# ---------------------------------------------------------------------------
# get_suggestions — slash commands
# ---------------------------------------------------------------------------


class TestGetSuggestionsSlashCommands:
    def setup_method(self) -> None:
        self.provider = CombinedAutocompleteProvider(
            commands=[
                SlashCommand(name="help", description="Show help"),
                SlashCommand(name="history", description="Show history"),
                SlashCommand(name="clear", description="Clear screen"),
            ],
            base_path="/tmp/test",
        )

    def test_slash_prefix_returns_matching_commands(self) -> None:
        result = self.provider.get_suggestions(["/h"], 0, 2)
        assert result is not None
        assert result["prefix"] == "/h"
        values = [item.value for item in result["items"]]
        assert "help" in values
        assert "history" in values

    def test_slash_only_returns_all_commands(self) -> None:
        result = self.provider.get_suggestions(["/"], 0, 1)
        assert result is not None
        assert len(result["items"]) == 3

    def test_slash_no_match_returns_none(self) -> None:
        result = self.provider.get_suggestions(["/zzz"], 0, 4)
        assert result is None

    def test_slash_command_with_argument_completions(self) -> None:
        def get_args(text: str) -> list[AutocompleteItem] | None:
            return [AutocompleteItem(value="arg1", label="arg1")]

        provider = CombinedAutocompleteProvider(
            commands=[SlashCommand(name="model", description="Set model", get_argument_completions=get_args)],
        )
        result = provider.get_suggestions(["/model arg"], 0, 10)
        assert result is not None
        assert result["prefix"] == "arg"
        assert result["items"][0].value == "arg1"

    def test_slash_command_argument_unknown_command(self) -> None:
        provider = CombinedAutocompleteProvider(
            commands=[SlashCommand(name="model")],
        )
        result = provider.get_suggestions(["/unknown arg"], 0, 12)
        assert result is None

    def test_slash_command_argument_no_completions_func(self) -> None:
        provider = CombinedAutocompleteProvider(
            commands=[SlashCommand(name="model")],
        )
        result = provider.get_suggestions(["/model arg"], 0, 10)
        assert result is None

    def test_slash_command_argument_completions_returns_none(self) -> None:
        def get_args(text: str) -> list[AutocompleteItem] | None:
            return None

        provider = CombinedAutocompleteProvider(
            commands=[SlashCommand(name="model", get_argument_completions=get_args)],
        )
        result = provider.get_suggestions(["/model arg"], 0, 10)
        assert result is None

    def test_slash_with_autocomplete_item_commands(self) -> None:
        provider = CombinedAutocompleteProvider(
            commands=[AutocompleteItem(value="help", label="help", description="Show help")],
        )
        result = provider.get_suggestions(["/h"], 0, 2)
        assert result is not None
        values = [item.value for item in result["items"]]
        assert "help" in values


# ---------------------------------------------------------------------------
# get_suggestions — @ file search (fuzzy)
# ---------------------------------------------------------------------------


class TestGetSuggestionsAtFile:
    def test_at_prefix_triggers_fuzzy_search(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "src/main.py\n"

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")

        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            result = provider.get_suggestions(["@main"], 0, 5)

        assert result is not None
        assert result["prefix"] == "@main"
        assert len(result["items"]) > 0

    def test_at_prefix_no_fd_path(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path=None)
        result = provider.get_suggestions(["@main"], 0, 5)
        assert result is None

    def test_at_prefix_empty_query(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file.py\ndir/\n"

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            result = provider.get_suggestions(["@"], 0, 1)
        assert result is not None

    def test_at_quoted_prefix(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "my file.py\n"

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            result = provider.get_suggestions(['@"my f'], 0, 6)
        assert result is not None
        assert result["prefix"] == '@"my f'

    def test_at_after_space(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file.py\n"

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            result = provider.get_suggestions(["look at @fi"], 0, 11)
        assert result is not None
        assert result["prefix"] == "@fi"

    def test_at_no_results(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            result = provider.get_suggestions(["@nonexistent"], 0, 12)
        assert result is None


# ---------------------------------------------------------------------------
# get_suggestions — file path completion
# ---------------------------------------------------------------------------


class TestGetSuggestionsFilePath:
    def test_dot_slash_triggers_completion(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").touch()
        (tmp_path / "subdir").mkdir()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_suggestions(["./"], 0, 2)
        assert result is not None
        assert len(result["items"]) >= 2

    def test_dot_dot_slash(self, tmp_path: Path) -> None:
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (tmp_path / "parent_file.txt").touch()

        provider = CombinedAutocompleteProvider(base_path=str(subdir))
        result = provider.get_suggestions(["../"], 0, 3)
        assert result is not None

    def test_partial_filename(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").touch()
        (tmp_path / "math.py").touch()
        (tmp_path / "other.txt").touch()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_suggestions(["ma"], 0, 2)
        # "ma" doesn't start with "/" or "." so it won't trigger unless it contains /
        assert result is None

    def test_path_with_slash(self, tmp_path: Path) -> None:
        subdir = tmp_path / "src"
        subdir.mkdir()
        (subdir / "main.py").touch()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_suggestions(["src/"], 0, 4)
        assert result is not None
        values = [item.value for item in result["items"]]
        assert any("main.py" in v for v in values)

    def test_no_suggestions_for_nonexistent_dir(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/tmp/nonexistent_dir_12345")
        result = provider.get_suggestions(["./"], 0, 2)
        assert result is None

    def test_empty_line_no_trigger(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/tmp")
        result = provider.get_suggestions([""], 0, 0)
        assert result is None

    def test_cursor_at_start(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/tmp")
        result = provider.get_suggestions(["hello"], 0, 0)
        assert result is None

    def test_multiline_with_cursor_on_second_line(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").touch()
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_suggestions(["first line", "./"], 1, 2)
        assert result is not None

    def test_cursor_line_out_of_range(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/tmp")
        result = provider.get_suggestions(["hello"], 5, 0)
        assert result is None

    def test_directories_sorted_first(self, tmp_path: Path) -> None:
        (tmp_path / "aaa_file.txt").touch()
        (tmp_path / "aaa_dir").mkdir()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_suggestions(["./aaa"], 0, 5)
        assert result is not None
        labels = [item.label for item in result["items"]]
        # Directory should come first
        dir_idx = next(i for i, l in enumerate(labels) if l.endswith("/"))
        file_idx = next(i for i, l in enumerate(labels) if not l.endswith("/"))
        assert dir_idx < file_idx

    def test_quoted_path_prefix(self, tmp_path: Path) -> None:
        (tmp_path / "my file.txt").touch()
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_suggestions(['"my'], 0, 3)
        assert result is not None


# ---------------------------------------------------------------------------
# apply_completion — slash commands
# ---------------------------------------------------------------------------


class TestApplyCompletionSlashCommands:
    def setup_method(self) -> None:
        self.provider = CombinedAutocompleteProvider()

    def test_apply_slash_command(self) -> None:
        item = AutocompleteItem(value="help", label="help")
        result = self.provider.apply_completion(["/h"], 0, 2, item, "/h")
        assert result["lines"] == ["/help "]
        assert result["cursor_line"] == 0
        assert result["cursor_col"] == 6  # len("/help ")

    def test_apply_slash_command_full_match(self) -> None:
        item = AutocompleteItem(value="clear", label="clear")
        result = self.provider.apply_completion(["/clear"], 0, 6, item, "/clear")
        assert result["lines"] == ["/clear "]
        assert result["cursor_col"] == 7

    def test_apply_slash_command_preserves_rest(self) -> None:
        item = AutocompleteItem(value="help", label="help")
        result = self.provider.apply_completion(["/h more text"], 0, 2, item, "/h")
        assert result["lines"] == ["/help  more text"]


# ---------------------------------------------------------------------------
# apply_completion — file paths
# ---------------------------------------------------------------------------


class TestApplyCompletionFilePaths:
    def setup_method(self) -> None:
        self.provider = CombinedAutocompleteProvider()

    def test_apply_file_path(self) -> None:
        item = AutocompleteItem(value="./src/main.py", label="main.py")
        result = self.provider.apply_completion(["./sr"], 0, 4, item, "./sr")
        assert result["lines"] == ["./src/main.py"]
        assert result["cursor_col"] == len("./src/main.py")

    def test_apply_directory_path(self) -> None:
        item = AutocompleteItem(value="./src/", label="src/")
        result = self.provider.apply_completion(["./s"], 0, 3, item, "./s")
        assert result["lines"] == ["./src/"]
        # For directories, cursor goes to end of value
        assert result["cursor_col"] == len("./src/")

    def test_apply_preserves_text_after_cursor(self) -> None:
        item = AutocompleteItem(value="./src/main.py", label="main.py")
        result = self.provider.apply_completion(["./sr rest"], 0, 4, item, "./sr")
        assert result["lines"] == ["./src/main.py rest"]


# ---------------------------------------------------------------------------
# apply_completion — @ file mentions
# ---------------------------------------------------------------------------


class TestApplyCompletionAtFile:
    def setup_method(self) -> None:
        self.provider = CombinedAutocompleteProvider()

    def test_apply_at_file(self) -> None:
        item = AutocompleteItem(value="@src/main.py", label="main.py")
        result = self.provider.apply_completion(["@sr"], 0, 3, item, "@sr")
        assert result["lines"] == ["@src/main.py "]
        assert result["cursor_col"] == len("@src/main.py ")

    def test_apply_at_directory(self) -> None:
        item = AutocompleteItem(value="@src/", label="src/")
        result = self.provider.apply_completion(["@s"], 0, 2, item, "@s")
        # Directory: no trailing space
        assert result["lines"] == ["@src/"]

    def test_apply_at_file_after_text(self) -> None:
        item = AutocompleteItem(value="@file.py", label="file.py")
        result = self.provider.apply_completion(["look at @fi"], 0, 11, item, "@fi")
        assert result["lines"] == ["look at @file.py "]

    def test_apply_at_quoted_file(self) -> None:
        item = AutocompleteItem(value='@"my file.py"', label="my file.py")
        result = self.provider.apply_completion(['@"my'], 0, 4, item, '@"my')
        assert "@" in result["lines"][0]

    def test_apply_at_quoted_with_trailing_quote(self) -> None:
        # When prefix is quoted and item ends with ", and after cursor starts with "
        item = AutocompleteItem(value='@"my file.py"', label="my file.py")
        result = self.provider.apply_completion(['@"my" rest'], 0, 4, item, '@"my')
        # Should consume the trailing quote
        assert result["lines"][0].count('"') >= 2


# ---------------------------------------------------------------------------
# apply_completion — slash command arguments
# ---------------------------------------------------------------------------


class TestApplyCompletionSlashCommandArgs:
    def setup_method(self) -> None:
        self.provider = CombinedAutocompleteProvider()

    def test_apply_argument_completion(self) -> None:
        item = AutocompleteItem(value="gpt-4", label="gpt-4")
        result = self.provider.apply_completion(["/model gp"], 0, 9, item, "gp")
        assert result["lines"] == ["/model gpt-4"]
        assert result["cursor_col"] == len("/model gpt-4")


# ---------------------------------------------------------------------------
# get_force_file_suggestions
# ---------------------------------------------------------------------------


class TestGetForceFileSuggestions:
    def test_returns_suggestions_on_empty(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").touch()
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_force_file_suggestions([""], 0, 0)
        assert result is not None
        assert len(result["items"]) >= 1

    def test_returns_none_for_slash_command(self, tmp_path: Path) -> None:
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_force_file_suggestions(["/help"], 0, 5)
        assert result is None

    def test_returns_suggestions_after_space_in_slash(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").touch()
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        # "/cmd " with space means it's no longer a bare slash command
        result = provider.get_force_file_suggestions(["/cmd ./"], 0, 7)
        assert result is not None

    def test_returns_suggestions_for_partial_path(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").touch()
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_force_file_suggestions(["fi"], 0, 2)
        assert result is not None
        assert any("file.txt" in item.label for item in result["items"])

    def test_returns_none_when_no_files(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/tmp/nonexistent_12345")
        result = provider.get_force_file_suggestions(["./"], 0, 2)
        assert result is None


# ---------------------------------------------------------------------------
# should_trigger_file_completion
# ---------------------------------------------------------------------------


class TestShouldTriggerFileCompletion:
    def test_normal_text_returns_true(self) -> None:
        provider = CombinedAutocompleteProvider()
        assert provider.should_trigger_file_completion(["hello"], 0, 5) is True

    def test_slash_command_returns_false(self) -> None:
        provider = CombinedAutocompleteProvider()
        assert provider.should_trigger_file_completion(["/help"], 0, 5) is False

    def test_slash_command_with_space_returns_true(self) -> None:
        provider = CombinedAutocompleteProvider()
        assert provider.should_trigger_file_completion(["/model arg"], 0, 10) is True

    def test_empty_line_returns_true(self) -> None:
        provider = CombinedAutocompleteProvider()
        assert provider.should_trigger_file_completion([""], 0, 0) is True

    def test_cursor_beyond_lines(self) -> None:
        provider = CombinedAutocompleteProvider()
        assert provider.should_trigger_file_completion(["hello"], 5, 0) is True


# ---------------------------------------------------------------------------
# _extract_at_prefix
# ---------------------------------------------------------------------------


class TestExtractAtPrefix:
    def setup_method(self) -> None:
        self.provider = CombinedAutocompleteProvider()

    def test_simple_at(self) -> None:
        assert self.provider._extract_at_prefix("@file") == "@file"

    def test_at_after_space(self) -> None:
        assert self.provider._extract_at_prefix("look at @file") == "@file"

    def test_no_at(self) -> None:
        assert self.provider._extract_at_prefix("hello") is None

    def test_at_in_middle_of_word(self) -> None:
        # "user@host" - @ is not at a token start
        assert self.provider._extract_at_prefix("user@host") is None

    def test_at_quoted(self) -> None:
        assert self.provider._extract_at_prefix('@"path') == '@"path'

    def test_at_at_start(self) -> None:
        assert self.provider._extract_at_prefix("@") == "@"


# ---------------------------------------------------------------------------
# _extract_path_prefix
# ---------------------------------------------------------------------------


class TestExtractPathPrefix:
    def setup_method(self) -> None:
        self.provider = CombinedAutocompleteProvider()

    def test_dot_slash(self) -> None:
        assert self.provider._extract_path_prefix("./") == "./"

    def test_dot_dot_slash(self) -> None:
        assert self.provider._extract_path_prefix("../") == "../"

    def test_tilde_slash(self) -> None:
        assert self.provider._extract_path_prefix("~/") == "~/"

    def test_path_with_slash(self) -> None:
        assert self.provider._extract_path_prefix("src/file") == "src/file"

    def test_plain_word_no_trigger(self) -> None:
        assert self.provider._extract_path_prefix("hello") is None

    def test_force_extract(self) -> None:
        assert self.provider._extract_path_prefix("hello", force_extract=True) == "hello"

    def test_after_space(self) -> None:
        assert self.provider._extract_path_prefix("look at ./file") == "./file"

    def test_quoted_path(self) -> None:
        assert self.provider._extract_path_prefix('"path/to') == '"path/to'

    def test_empty_after_space(self) -> None:
        # Text ending with space, no path prefix
        result = self.provider._extract_path_prefix("hello ")
        assert result == ""

    def test_dot_prefix(self) -> None:
        assert self.provider._extract_path_prefix(".file") == ".file"

    def test_force_extract_after_delimiter(self) -> None:
        result = self.provider._extract_path_prefix("key=val", force_extract=True)
        assert result == "val"


# ---------------------------------------------------------------------------
# _resolve_scoped_fuzzy_query
# ---------------------------------------------------------------------------


class TestResolveScopedFuzzyQuery:
    def test_simple_scoped_query(self, tmp_path: Path) -> None:
        subdir = tmp_path / "src"
        subdir.mkdir()
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider._resolve_scoped_fuzzy_query("src/main")
        assert result is not None
        assert result["query"] == "main"
        assert result["display_base"] == "src/"

    def test_no_slash(self) -> None:
        provider = CombinedAutocompleteProvider()
        assert provider._resolve_scoped_fuzzy_query("main") is None

    def test_nonexistent_dir(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/tmp")
        result = provider._resolve_scoped_fuzzy_query("nonexistent_dir_12345/file")
        assert result is None

    def test_home_scoped(self) -> None:
        provider = CombinedAutocompleteProvider()
        home = os.path.expanduser("~")
        if Path(home).is_dir():
            result = provider._resolve_scoped_fuzzy_query("~/file")
            assert result is not None
            assert result["display_base"] == "~/"

    def test_absolute_path_scoped(self, tmp_path: Path) -> None:
        provider = CombinedAutocompleteProvider()
        result = provider._resolve_scoped_fuzzy_query(f"{tmp_path}/file")
        assert result is not None
        assert result["query"] == "file"


# ---------------------------------------------------------------------------
# _scoped_path_for_display
# ---------------------------------------------------------------------------


class TestScopedPathForDisplay:
    def test_root_display_base(self) -> None:
        result = CombinedAutocompleteProvider._scoped_path_for_display("/", "file.py")
        assert result == "/file.py"

    def test_non_root(self) -> None:
        result = CombinedAutocompleteProvider._scoped_path_for_display("src/", "main.py")
        assert result == "src/main.py"


# ---------------------------------------------------------------------------
# _score_entry
# ---------------------------------------------------------------------------


class TestScoreEntry:
    def setup_method(self) -> None:
        self.provider = CombinedAutocompleteProvider()

    def test_exact_match(self) -> None:
        score = self.provider._score_entry("src/main.py", "main.py", is_directory=False)
        assert score == 100

    def test_starts_with(self) -> None:
        score = self.provider._score_entry("src/main.py", "main", is_directory=False)
        assert score == 80

    def test_contains(self) -> None:
        score = self.provider._score_entry("src/my_main.py", "main", is_directory=False)
        assert score == 50

    def test_path_contains(self) -> None:
        score = self.provider._score_entry("main/other.py", "main", is_directory=False)
        assert score == 30

    def test_no_match(self) -> None:
        score = self.provider._score_entry("src/other.py", "xyz", is_directory=False)
        assert score == 0

    def test_directory_bonus(self) -> None:
        file_score = self.provider._score_entry("src/main", "main", is_directory=False)
        dir_score = self.provider._score_entry("src/main/", "main", is_directory=True)
        assert dir_score == file_score + 10

    def test_no_directory_bonus_when_no_match(self) -> None:
        score = self.provider._score_entry("src/other/", "xyz", is_directory=True)
        assert score == 0

    def test_case_insensitive(self) -> None:
        score = self.provider._score_entry("src/Main.py", "main.py", is_directory=False)
        assert score == 100


# ---------------------------------------------------------------------------
# _get_fuzzy_file_suggestions
# ---------------------------------------------------------------------------


class TestGetFuzzyFileSuggestions:
    def test_no_fd_path(self) -> None:
        provider = CombinedAutocompleteProvider(fd_path=None)
        assert provider._get_fuzzy_file_suggestions("query", is_quoted_prefix=False) == []

    def test_with_results(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "src/main.py\nsrc/utils/\n"

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            suggestions = provider._get_fuzzy_file_suggestions("main", is_quoted_prefix=False)

        assert len(suggestions) > 0
        # Check that entries have @ prefix
        assert all(item.value.startswith("@") for item in suggestions)

    def test_quoted_prefix(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "my file.py\n"

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            suggestions = provider._get_fuzzy_file_suggestions("my", is_quoted_prefix=True)

        assert len(suggestions) > 0
        # Quoted values should have quotes
        assert any('"' in item.value for item in suggestions)

    def test_empty_query(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file.py\ndir/\n"

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            suggestions = provider._get_fuzzy_file_suggestions("", is_quoted_prefix=False)

        assert len(suggestions) > 0

    def test_scoped_query(self, tmp_path: Path) -> None:
        subdir = tmp_path / "src"
        subdir.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "main.py\n"

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path), fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            suggestions = provider._get_fuzzy_file_suggestions("src/main", is_quoted_prefix=False)

        assert len(suggestions) > 0
        # Display should include the scoped base
        assert any("src/" in (item.description or "") for item in suggestions)

    def test_os_error_returns_empty(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", side_effect=OSError):
            suggestions = provider._get_fuzzy_file_suggestions("query", is_quoted_prefix=False)
        assert suggestions == []

    def test_directory_label_has_slash(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "mydir/\n"

        provider = CombinedAutocompleteProvider(base_path="/tmp", fd_path="/usr/bin/fd")
        with patch("pi_tui.autocomplete.subprocess.run", return_value=mock_result):
            suggestions = provider._get_fuzzy_file_suggestions("", is_quoted_prefix=False)

        assert len(suggestions) == 1
        assert suggestions[0].label.endswith("/")


# ---------------------------------------------------------------------------
# _get_file_suggestions (via filesystem)
# ---------------------------------------------------------------------------


class TestGetFileSuggestions:
    def test_basic_listing(self, tmp_path: Path) -> None:
        (tmp_path / "alpha.py").touch()
        (tmp_path / "beta.py").touch()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        suggestions = provider._get_file_suggestions("./")
        assert len(suggestions) >= 2
        labels = [s.label for s in suggestions]
        assert "alpha.py" in labels
        assert "beta.py" in labels

    def test_directory_has_slash_in_label(self, tmp_path: Path) -> None:
        (tmp_path / "mydir").mkdir()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        suggestions = provider._get_file_suggestions("./")
        assert any(s.label == "mydir/" for s in suggestions)

    def test_prefix_filters(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").touch()
        (tmp_path / "other.py").touch()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        suggestions = provider._get_file_suggestions("./ma")
        labels = [s.label for s in suggestions]
        assert "main.py" in labels
        assert "other.py" not in labels

    def test_at_prefix(self, tmp_path: Path) -> None:
        (tmp_path / "file.py").touch()

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        suggestions = provider._get_file_suggestions("@")
        assert len(suggestions) >= 1
        assert all("@" in s.value for s in suggestions)

    def test_oserror_returns_empty(self) -> None:
        provider = CombinedAutocompleteProvider(base_path="/nonexistent_dir_12345")
        suggestions = provider._get_file_suggestions("./")
        assert suggestions == []

    def test_absolute_path(self, tmp_path: Path) -> None:
        (tmp_path / "file.py").touch()
        provider = CombinedAutocompleteProvider(base_path="/somewhere_else")
        suggestions = provider._get_file_suggestions(f"{tmp_path}/")
        labels = [s.label for s in suggestions]
        assert "file.py" in labels

    def test_home_path(self) -> None:
        provider = CombinedAutocompleteProvider()
        suggestions = provider._get_file_suggestions("~/")
        # Home directory should have some files
        assert len(suggestions) > 0

    def test_quoted_at_prefix(self, tmp_path: Path) -> None:
        (tmp_path / "file.py").touch()
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        suggestions = provider._get_file_suggestions('@"')
        assert len(suggestions) >= 1

    def test_symlink_directory(self, tmp_path: Path) -> None:
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()
        link = tmp_path / "link_dir"
        link.symlink_to(real_dir)

        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        suggestions = provider._get_file_suggestions("./")
        labels = [s.label for s in suggestions]
        assert "link_dir/" in labels or "real_dir/" in labels


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_lines_list(self) -> None:
        provider = CombinedAutocompleteProvider()
        result = provider.get_suggestions([], 0, 0)
        # cursor_line >= len(lines), so current_line = ""
        assert result is None

    def test_multiline_slash_on_second_line(self) -> None:
        provider = CombinedAutocompleteProvider(
            commands=[SlashCommand(name="help", description="Help")],
        )
        # Slash on line 1 (not line 0) — should still work
        result = provider.get_suggestions(["first line", "/h"], 1, 2)
        assert result is not None

    def test_apply_completion_cursor_line_out_of_range(self) -> None:
        provider = CombinedAutocompleteProvider()
        item = AutocompleteItem(value="test", label="test")
        # cursor_line beyond lines length causes IndexError on assignment
        with pytest.raises(IndexError):
            provider.apply_completion(["hello"], 5, 0, item, "")

    def test_single_result_matching_prefix(self, tmp_path: Path) -> None:
        (tmp_path / "exact").touch()
        provider = CombinedAutocompleteProvider(base_path=str(tmp_path))
        result = provider.get_suggestions(["./exact"], 0, 7)
        # Should still return the result
        assert result is not None

    def test_apply_completion_quoted_prefix_with_trailing_quote_consumed(self) -> None:
        provider = CombinedAutocompleteProvider()
        item = AutocompleteItem(value='"my file.py"', label="my file.py")
        # prefix is quoted, item ends with ", after cursor starts with "
        result = provider.apply_completion(['"my" rest'], 0, 3, item, '"my')
        # The trailing quote from after_cursor should be consumed
        lines = result["lines"]
        assert len(lines) == 1
