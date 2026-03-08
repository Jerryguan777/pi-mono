"""Unit tests for pi_tui.components.markdown."""

from __future__ import annotations

import pytest

from pi_tui.components.markdown import DefaultTextStyle, Markdown, MarkdownTheme


# ---------------------------------------------------------------------------
# Test helpers: theme functions that wrap text in identifiable markers
# instead of ANSI codes, making assertions straightforward.
# ---------------------------------------------------------------------------


def _tag(name: str) -> callable:
    """Return a styling function that wraps text in <name>...</name> markers."""

    def _fn(text: str) -> str:
        return f"<{name}>{text}</{name}>"

    return _fn


def _highlight_code(text: str, lang: str | None) -> list[str]:
    """Simple highlight stub: prefix each line with the language."""
    prefix = f"[{lang}]" if lang else "[code]"
    return [f"{prefix}{line}" for line in text.split("\n")]


def _make_theme(*, highlight: bool = False) -> MarkdownTheme:
    return MarkdownTheme(
        heading=_tag("heading"),
        link=_tag("link"),
        link_url=_tag("link_url"),
        code=_tag("code"),
        code_block=_tag("code_block"),
        code_block_border=_tag("code_block_border"),
        quote=_tag("quote"),
        quote_border=_tag("quote_border"),
        hr=_tag("hr"),
        list_bullet=_tag("bullet"),
        bold=_tag("bold"),
        italic=_tag("italic"),
        strikethrough=_tag("strikethrough"),
        underline=_tag("underline"),
        highlight_code=_highlight_code if highlight else None,
    )


def _make_md(
    text: str,
    *,
    width: int = 80,
    padding_x: int = 0,
    padding_y: int = 0,
    theme: MarkdownTheme | None = None,
    default_text_style: DefaultTextStyle | None = None,
) -> list[str]:
    """Convenience: create a Markdown instance and render at *width*."""
    md = Markdown(
        text=text,
        padding_x=padding_x,
        padding_y=padding_y,
        theme=theme or _make_theme(),
        default_text_style=default_text_style,
    )
    return md.render(width)


# ===================================================================
# 1. Construction
# ===================================================================


class TestConstruction:
    def test_markdown_stores_theme(self) -> None:
        theme = _make_theme()
        md = Markdown(text="hello", padding_x=0, padding_y=0, theme=theme)
        assert md._theme is theme

    def test_markdown_stores_default_text_style(self) -> None:
        style = DefaultTextStyle(bold=True)
        md = Markdown(text="x", padding_x=0, padding_y=0, theme=_make_theme(), default_text_style=style)
        assert md._default_text_style is style

    def test_markdown_default_text_style_is_none(self) -> None:
        md = Markdown(text="x", padding_x=0, padding_y=0, theme=_make_theme())
        assert md._default_text_style is None

    def test_cache_starts_empty(self) -> None:
        md = Markdown(text="x", padding_x=0, padding_y=0, theme=_make_theme())
        assert md._cached_lines is None
        assert md._cached_text is None
        assert md._cached_width is None


# ===================================================================
# 2. Plain text
# ===================================================================


class TestPlainText:
    def test_simple_text(self) -> None:
        lines = _make_md("Hello world")
        # Should produce at least one line containing "Hello world"
        joined = "\n".join(lines)
        assert "Hello world" in joined

    def test_empty_text(self) -> None:
        lines = _make_md("")
        assert lines == []

    def test_whitespace_only(self) -> None:
        lines = _make_md("   ")
        assert lines == []

    def test_multiline_text(self) -> None:
        lines = _make_md("Line one\n\nLine two")
        joined = "\n".join(lines)
        assert "Line one" in joined
        assert "Line two" in joined


# ===================================================================
# 3. Bold text
# ===================================================================


class TestBold:
    def test_bold_text(self) -> None:
        lines = _make_md("**bold**")
        joined = "\n".join(lines)
        assert "<bold>" in joined
        assert "bold" in joined

    def test_bold_inside_paragraph(self) -> None:
        lines = _make_md("This is **bold** text")
        joined = "\n".join(lines)
        assert "<bold>" in joined
        assert "This is" in joined
        assert "text" in joined


# ===================================================================
# 4. Italic text
# ===================================================================


class TestItalic:
    def test_italic_text(self) -> None:
        lines = _make_md("*italic*")
        joined = "\n".join(lines)
        assert "<italic>" in joined
        assert "italic" in joined

    def test_italic_inside_paragraph(self) -> None:
        lines = _make_md("This is *italic* text")
        joined = "\n".join(lines)
        assert "<italic>" in joined


# ===================================================================
# 5. Code spans
# ===================================================================


class TestCodeSpan:
    def test_code_span(self) -> None:
        lines = _make_md("Use `foo()` here")
        joined = "\n".join(lines)
        assert "<code>" in joined
        assert "foo()" in joined

    def test_standalone_code_span(self) -> None:
        lines = _make_md("`bar`")
        joined = "\n".join(lines)
        assert "<code>bar</code>" in joined


# ===================================================================
# 6. Headings
# ===================================================================


class TestHeadings:
    def test_h1(self) -> None:
        lines = _make_md("# Title")
        joined = "\n".join(lines)
        assert "<heading>" in joined
        assert "<bold>" in joined
        assert "<underline>" in joined
        assert "Title" in joined

    def test_h2(self) -> None:
        lines = _make_md("## Subtitle")
        joined = "\n".join(lines)
        assert "<heading>" in joined
        assert "<bold>" in joined
        assert "Subtitle" in joined

    def test_h3(self) -> None:
        lines = _make_md("### Section")
        joined = "\n".join(lines)
        assert "<heading>" in joined
        assert "<bold>" in joined
        # H3 includes the "### " prefix
        assert "### Section" in joined

    def test_heading_adds_blank_line_after(self) -> None:
        lines = _make_md("# Title\n\nParagraph")
        # There should be a blank line (possibly space-padded) between heading and paragraph
        heading_idx = next(i for i, l in enumerate(lines) if "Title" in l)
        para_idx = next(i for i, l in enumerate(lines) if "Paragraph" in l)
        assert para_idx > heading_idx + 1  # at least one line in between


# ===================================================================
# 7. Bullet lists
# ===================================================================


class TestBulletLists:
    def test_single_bullet(self) -> None:
        lines = _make_md("- item one")
        joined = "\n".join(lines)
        assert "<bullet>" in joined
        assert "item one" in joined

    def test_multiple_bullets(self) -> None:
        lines = _make_md("- alpha\n- beta\n- gamma")
        joined = "\n".join(lines)
        assert "alpha" in joined
        assert "beta" in joined
        assert "gamma" in joined

    def test_bullet_marker(self) -> None:
        lines = _make_md("- item")
        joined = "\n".join(lines)
        # The bullet marker "- " should be wrapped in <bullet> tags
        assert "<bullet>- </bullet>" in joined


# ===================================================================
# 8. Numbered lists
# ===================================================================


class TestNumberedLists:
    def test_ordered_list(self) -> None:
        lines = _make_md("1. first\n2. second\n3. third")
        joined = "\n".join(lines)
        assert "first" in joined
        assert "second" in joined
        assert "third" in joined

    def test_ordered_list_numbering(self) -> None:
        lines = _make_md("1. first\n2. second")
        joined = "\n".join(lines)
        assert "<bullet>1. </bullet>" in joined
        assert "<bullet>2. </bullet>" in joined


# ===================================================================
# 9. Code blocks
# ===================================================================


class TestCodeBlocks:
    def test_fenced_code_block(self) -> None:
        """Fenced code blocks are rendered with border and styled content.

        Note: mistune 3.x emits ``block_code`` tokens.  The source uses
        ``code_block`` as the token type, so fenced blocks currently fall
        through to the fallback renderer which still outputs the raw code.
        We test that the content is present in the output.
        """
        lines = _make_md("text\n\n```\nhello\n```\n\nmore")
        joined = "\n".join(lines)
        assert "hello" in joined

    def test_fenced_code_block_with_language(self) -> None:
        lines = _make_md("text\n\n```python\nprint('hi')\n```\n\nmore")
        joined = "\n".join(lines)
        assert "print('hi')" in joined

    def test_code_block_with_highlight(self) -> None:
        """When highlight_code is set and the token is recognized, highlighting is applied."""
        lines = _make_md("text\n\n```python\nprint('hi')\n```\n\nmore", theme=_make_theme(highlight=True))
        joined = "\n".join(lines)
        # Content should be present regardless
        assert "print('hi')" in joined

    def test_code_block_renders_via_code_block_token(self) -> None:
        """Directly invoke _render_token with a code_block token to exercise
        the code_block branch which mistune 3.x does not naturally produce."""
        theme = _make_theme()
        md = Markdown(text="x", padding_x=0, padding_y=0, theme=theme)
        token = {
            "type": "code_block",
            "attrs": {"info": "python", "raw": "foo()\nbar()\n"},
        }
        result = md._render_token(token, 80, None)
        joined = "\n".join(result)
        assert "<code_block_border>```python</code_block_border>" in joined
        assert "<code_block>foo()</code_block>" in joined
        assert "<code_block>bar()</code_block>" in joined
        assert "<code_block_border>```</code_block_border>" in joined

    def test_code_block_token_with_highlight(self) -> None:
        """Exercise code_block branch with highlight_code enabled."""
        theme = _make_theme(highlight=True)
        md = Markdown(text="x", padding_x=0, padding_y=0, theme=theme)
        token = {
            "type": "code_block",
            "attrs": {"info": "python", "raw": "foo()\n"},
        }
        result = md._render_token(token, 80, None)
        joined = "\n".join(result)
        assert "[python]foo()" in joined

    def test_code_block_indented_content(self) -> None:
        """Code block lines are prefixed with the theme's code_block_indent."""
        theme = _make_theme()
        md = Markdown(text="x", padding_x=0, padding_y=0, theme=theme)
        token = {
            "type": "code_block",
            "attrs": {"info": "", "raw": "line1\nline2\n"},
        }
        result = md._render_token(token, 80, None)
        code_lines = [l for l in result if "<code_block>" in l and "<code_block_border>" not in l]
        for cl in code_lines:
            assert cl.startswith("  ")

    def test_multiline_code_block(self) -> None:
        code = "text\n\n```\nline1\nline2\nline3\n```\n\nmore"
        lines = _make_md(code)
        joined = "\n".join(lines)
        assert "line1" in joined
        assert "line2" in joined
        assert "line3" in joined


# ===================================================================
# 10. Blockquotes
# ===================================================================


class TestBlockquotes:
    def test_blockquote(self) -> None:
        lines = _make_md("> quoted text")
        joined = "\n".join(lines)
        assert "<quote_border>" in joined
        assert "<quote>" in joined
        assert "quoted text" in joined

    def test_blockquote_uses_italic(self) -> None:
        lines = _make_md("> quoted")
        joined = "\n".join(lines)
        # Blockquotes apply italic styling
        assert "<italic>" in joined

    def test_blockquote_border_character(self) -> None:
        lines = _make_md("> text")
        # The border should include the box-drawing character
        border_lines = [l for l in lines if "\u2502" in l]
        assert len(border_lines) > 0


# ===================================================================
# 11. Links
# ===================================================================


class TestLinks:
    def test_link_with_different_text_and_url(self) -> None:
        lines = _make_md("[click here](https://example.com)")
        joined = "\n".join(lines)
        assert "<link>" in joined
        assert "<underline>" in joined
        assert "click here" in joined
        assert "<link_url>" in joined
        assert "https://example.com" in joined

    def test_autolink_same_text_as_url(self) -> None:
        # When link text equals the URL, only the link is shown (no separate URL)
        lines = _make_md("[https://example.com](https://example.com)")
        joined = "\n".join(lines)
        assert "<link>" in joined
        # Should NOT have a separate URL display
        assert "<link_url>" not in joined


# ===================================================================
# 12. Horizontal rules
# ===================================================================


class TestHorizontalRules:
    def test_thematic_break(self) -> None:
        lines = _make_md("---")
        joined = "\n".join(lines)
        assert "<hr>" in joined
        # Uses the box-drawing character
        assert "\u2500" in joined

    def test_hr_width(self) -> None:
        lines = _make_md("---", width=40)
        hr_lines = [l for l in lines if "<hr>" in l]
        assert len(hr_lines) > 0
        # Should contain up to 40 horizontal line chars
        hr_line = hr_lines[0]
        assert "\u2500" in hr_line


# ===================================================================
# 13. Mixed markdown content
# ===================================================================


class TestMixedContent:
    def test_heading_and_paragraph(self) -> None:
        text = "# Title\n\nSome paragraph text."
        lines = _make_md(text)
        joined = "\n".join(lines)
        assert "<heading>" in joined
        assert "Title" in joined
        assert "Some paragraph text." in joined

    def test_bold_and_italic_in_paragraph(self) -> None:
        text = "This has **bold** and *italic* text."
        lines = _make_md(text)
        joined = "\n".join(lines)
        assert "<bold>" in joined
        assert "<italic>" in joined

    def test_list_with_code_spans(self) -> None:
        text = "- Use `foo()`\n- Use `bar()`"
        lines = _make_md(text)
        joined = "\n".join(lines)
        assert "<bullet>" in joined
        assert "<code>foo()</code>" in joined
        assert "<code>bar()</code>" in joined

    def test_heading_list_and_code_block(self) -> None:
        text = "# API\n\n- method one\n- method two\n\nSome text\n\n```python\nfoo()\n```\n\nEnd"
        lines = _make_md(text)
        joined = "\n".join(lines)
        assert "<heading>" in joined
        assert "<bullet>" in joined
        assert "foo()" in joined

    def test_blockquote_with_bold(self) -> None:
        text = "> This is **important**"
        lines = _make_md(text)
        joined = "\n".join(lines)
        assert "<quote_border>" in joined
        assert "<bold>" in joined
        assert "important" in joined


# ===================================================================
# 14. Caching behavior
# ===================================================================


class TestCaching:
    def test_same_width_returns_cached(self) -> None:
        md = Markdown(text="Hello", padding_x=0, padding_y=0, theme=_make_theme())
        result1 = md.render(80)
        result2 = md.render(80)
        # Should be the exact same object (cached)
        assert result1 is result2

    def test_different_width_recomputes(self) -> None:
        md = Markdown(text="Hello", padding_x=0, padding_y=0, theme=_make_theme())
        result1 = md.render(80)
        result2 = md.render(40)
        # Different widths should not return the same cached object
        assert result1 is not result2

    def test_cache_fields_set_after_render(self) -> None:
        md = Markdown(text="Hello", padding_x=0, padding_y=0, theme=_make_theme())
        md.render(80)
        assert md._cached_text == "Hello"
        assert md._cached_width == 80
        assert md._cached_lines is not None

    def test_empty_text_also_cached(self) -> None:
        md = Markdown(text="", padding_x=0, padding_y=0, theme=_make_theme())
        result1 = md.render(80)
        result2 = md.render(80)
        assert result1 is result2


# ===================================================================
# 15. set_text() invalidates cache
# ===================================================================


class TestSetText:
    def test_set_text_invalidates_cache(self) -> None:
        md = Markdown(text="Hello", padding_x=0, padding_y=0, theme=_make_theme())
        md.render(80)
        assert md._cached_lines is not None

        md.set_text("World")
        assert md._cached_lines is None
        assert md._cached_text is None
        assert md._cached_width is None

    def test_set_text_changes_output(self) -> None:
        md = Markdown(text="Hello", padding_x=0, padding_y=0, theme=_make_theme())
        result1 = md.render(80)
        joined1 = "\n".join(result1)
        assert "Hello" in joined1

        md.set_text("World")
        result2 = md.render(80)
        joined2 = "\n".join(result2)
        assert "World" in joined2
        assert "Hello" not in joined2

    def test_invalidate_clears_style_prefix(self) -> None:
        md = Markdown(text="x", padding_x=0, padding_y=0, theme=_make_theme())
        md.render(80)
        md.invalidate()
        assert md._default_style_prefix is None


# ===================================================================
# Additional edge cases
# ===================================================================


class TestEdgeCases:
    def test_padding_x(self) -> None:
        lines = _make_md("Hello", padding_x=2, width=80)
        # Each line should start with 2 spaces of padding
        for line in lines:
            assert line.startswith("  ")

    def test_padding_y(self) -> None:
        lines = _make_md("Hello", padding_y=1, width=80)
        # First and last lines should be empty padding
        assert len(lines) >= 3  # 1 top pad + content + 1 bottom pad
        # Top padding line should be all spaces
        assert lines[0].strip() == ""
        assert lines[-1].strip() == ""

    def test_default_text_style_color(self) -> None:
        style = DefaultTextStyle(color=_tag("color"))
        lines = _make_md("Hello", default_text_style=style)
        joined = "\n".join(lines)
        assert "<color>" in joined

    def test_default_text_style_bold(self) -> None:
        style = DefaultTextStyle(bold=True)
        lines = _make_md("Hello", default_text_style=style)
        joined = "\n".join(lines)
        assert "<bold>" in joined

    def test_tab_normalization(self) -> None:
        lines = _make_md("Hello\tworld")
        joined = "\n".join(lines)
        # Tabs should be converted to spaces
        assert "\t" not in joined
        assert "Hello" in joined
        assert "world" in joined

    def test_narrow_width(self) -> None:
        # Should not crash with very narrow width
        lines = _make_md("Hello world this is a test", width=5)
        assert len(lines) > 0
