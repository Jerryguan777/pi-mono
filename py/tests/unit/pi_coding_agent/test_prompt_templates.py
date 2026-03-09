"""Tests for prompt template loading and expansion."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pi_coding_agent.core.prompt_templates import (
    PromptTemplate,
    expand_prompt_template,
    load_prompt_templates,
    parse_command_args,
    substitute_args,
)


class TestParseCommandArgs:
    def test_simple_words(self) -> None:
        assert parse_command_args("foo bar baz") == ["foo", "bar", "baz"]

    def test_single_quoted_string(self) -> None:
        assert parse_command_args("'hello world'") == ["hello world"]

    def test_double_quoted_string(self) -> None:
        assert parse_command_args('"hello world"') == ["hello world"]

    def test_mixed_quoted_and_unquoted(self) -> None:
        result = parse_command_args('foo "bar baz" qux')
        assert result == ["foo", "bar baz", "qux"]

    def test_empty_string(self) -> None:
        assert parse_command_args("") == []

    def test_extra_whitespace(self) -> None:
        assert parse_command_args("  foo   bar  ") == ["foo", "bar"]

    def test_tabs(self) -> None:
        assert parse_command_args("foo\tbar") == ["foo", "bar"]


class TestSubstituteArgs:
    def test_positional_args(self) -> None:
        result = substitute_args("Hello $1, you are $2", ["Alice", "tall"])
        assert result == "Hello Alice, you are tall"

    def test_missing_positional_arg_is_empty(self) -> None:
        result = substitute_args("$1 $2 $3", ["a", "b"])
        assert result == "a b "

    def test_dollar_at_all_args(self) -> None:
        result = substitute_args("Args: $@", ["a", "b", "c"])
        assert result == "Args: a b c"

    def test_dollar_arguments_all_args(self) -> None:
        result = substitute_args("Args: $ARGUMENTS", ["x", "y"])
        assert result == "Args: x y"

    def test_slice_from_nth(self) -> None:
        result = substitute_args("Rest: ${@:2}", ["a", "b", "c", "d"])
        assert result == "Rest: b c d"

    def test_slice_with_length(self) -> None:
        result = substitute_args("Slice: ${@:2:2}", ["a", "b", "c", "d"])
        assert result == "Slice: b c"

    def test_no_args(self) -> None:
        result = substitute_args("Hello $1", [])
        assert result == "Hello "

    def test_literal_text_unchanged(self) -> None:
        result = substitute_args("No placeholders here", ["a", "b"])
        assert result == "No placeholders here"

    def test_multiple_positional(self) -> None:
        result = substitute_args("$1 + $2 = $3", ["1", "2", "3"])
        assert result == "1 + 2 = 3"


class TestExpandPromptTemplate:
    def _make_template(self, name: str, content: str) -> PromptTemplate:
        return PromptTemplate(
            name=name,
            description="Test template",
            content=content,
            source="test",
            file_path=f"/fake/{name}.md",
        )

    def test_non_template_text_returned_as_is(self) -> None:
        templates = [self._make_template("greet", "Hello $1")]
        result = expand_prompt_template("just plain text", templates)
        assert result == "just plain text"

    def test_expands_known_template(self) -> None:
        templates = [self._make_template("greet", "Hello $1")]
        result = expand_prompt_template("/greet World", templates)
        assert result == "Hello World"

    def test_unknown_template_returns_original(self) -> None:
        templates = [self._make_template("greet", "Hello $1")]
        result = expand_prompt_template("/unknown foo", templates)
        assert result == "/unknown foo"

    def test_no_args_template(self) -> None:
        templates = [self._make_template("test", "Fixed content")]
        result = expand_prompt_template("/test", templates)
        assert result == "Fixed content"

    def test_multiple_args(self) -> None:
        templates = [self._make_template("sum", "$1 + $2 = done")]
        result = expand_prompt_template("/sum alpha beta", templates)
        assert result == "alpha + beta = done"

    def test_all_args_substitution(self) -> None:
        templates = [self._make_template("all", "All args: $@")]
        result = expand_prompt_template("/all a b c", templates)
        assert result == "All args: a b c"

    def test_quoted_args(self) -> None:
        templates = [self._make_template("greet", "Hello $1")]
        result = expand_prompt_template('/greet "World Today"', templates)
        assert result == "Hello World Today"


class TestLoadPromptTemplates:
    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            templates = load_prompt_templates(
                {
                    "cwd": tmpdir,
                    "agent_dir": tmpdir,
                    "include_defaults": False,
                    "prompt_paths": [],
                }
            )
            assert templates == []

    def test_loads_md_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir()
            tmpl_file = prompts_dir / "greet.md"
            tmpl_file.write_text("---\ndescription: A greeting template\n---\nHello $1!")

            templates = load_prompt_templates(
                {
                    "cwd": tmpdir,
                    "agent_dir": tmpdir,
                    "include_defaults": True,
                    "prompt_paths": [],
                }
            )
            assert len(templates) == 1
            assert templates[0].name == "greet"
            assert "Hello $1!" in templates[0].content

    def test_loads_from_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / "custom.md"
            tmpl_file.write_text("---\ndescription: Custom\n---\nContent")

            templates = load_prompt_templates(
                {
                    "cwd": tmpdir,
                    "include_defaults": False,
                    "prompt_paths": [str(tmpl_file)],
                }
            )
            assert len(templates) == 1
            assert templates[0].name == "custom"
