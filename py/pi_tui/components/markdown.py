"""Markdown rendering component using mistune for AST parsing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import mistune

from pi_tui.terminal_image import is_image_line
from pi_tui.utils import (
    apply_background_to_line,
    visible_width,
    wrap_text_with_ansi,
)


@dataclass
class DefaultTextStyle:
    """Default text styling for markdown content."""

    color: Callable[[str], str] | None = None
    bg_color: Callable[[str], str] | None = None
    bold: bool = False
    italic: bool = False
    strikethrough: bool = False
    underline: bool = False


@dataclass
class MarkdownTheme:
    """Theme functions for markdown elements.

    Each function takes text and returns styled text with ANSI codes.
    """

    heading: Callable[[str], str]
    link: Callable[[str], str]
    link_url: Callable[[str], str]
    code: Callable[[str], str]
    code_block: Callable[[str], str]
    code_block_border: Callable[[str], str]
    quote: Callable[[str], str]
    quote_border: Callable[[str], str]
    hr: Callable[[str], str]
    list_bullet: Callable[[str], str]
    bold: Callable[[str], str]
    italic: Callable[[str], str]
    strikethrough: Callable[[str], str]
    underline: Callable[[str], str]
    highlight_code: Callable[[str, str | None], list[str]] | None = None
    code_block_indent: str = "  "


@dataclass
class _InlineStyleContext:
    apply_text: Callable[[str], str]
    style_prefix: str


class Markdown:
    """Renders markdown text to styled terminal lines.

    Uses ``mistune`` to parse markdown into an AST, then renders each
    token to ANSI-styled terminal output with word wrapping.
    """

    def __init__(
        self,
        text: str,
        padding_x: int,
        padding_y: int,
        theme: MarkdownTheme,
        default_text_style: DefaultTextStyle | None = None,
    ) -> None:
        self._text = text
        self._padding_x = padding_x
        self._padding_y = padding_y
        self._theme = theme
        self._default_text_style = default_text_style
        self._default_style_prefix: str | None = None

        # Render cache
        self._cached_text: str | None = None
        self._cached_width: int | None = None
        self._cached_lines: list[str] | None = None

    def set_text(self, text: str) -> None:
        self._text = text
        self.invalidate()

    def invalidate(self) -> None:
        self._cached_text = None
        self._cached_width = None
        self._cached_lines = None
        self._default_style_prefix = None

    def render(self, width: int) -> list[str]:
        # Check cache
        if self._cached_lines is not None and self._cached_text == self._text and self._cached_width == width:
            return self._cached_lines

        content_width = max(1, width - self._padding_x * 2)

        # Empty text produces no output
        if not self._text or self._text.strip() == "":
            result: list[str] = []
            self._cached_text = self._text
            self._cached_width = width
            self._cached_lines = result
            return result

        normalized_text = self._text.replace("\t", "   ")

        # Parse markdown to AST tokens
        md = mistune.create_markdown(renderer=None)
        raw_tokens = md(normalized_text)
        tokens: list[dict[str, Any]] = raw_tokens if isinstance(raw_tokens, list) else []

        # Render tokens to styled lines
        rendered_lines: list[str] = []
        for i, token in enumerate(tokens):
            next_token_type = tokens[i + 1]["type"] if i + 1 < len(tokens) else None
            token_lines = self._render_token(token, content_width, next_token_type)
            rendered_lines.extend(token_lines)

        # Wrap lines
        wrapped_lines: list[str] = []
        for line in rendered_lines:
            if is_image_line(line):
                wrapped_lines.append(line)
            else:
                wrapped_lines.extend(wrap_text_with_ansi(line, content_width))

        # Add margins and background
        left_margin = " " * self._padding_x
        right_margin = " " * self._padding_x
        bg_fn = self._default_text_style.bg_color if self._default_text_style else None
        content_lines: list[str] = []

        for line in wrapped_lines:
            if is_image_line(line):
                content_lines.append(line)
                continue
            line_with_margins = left_margin + line + right_margin
            if bg_fn:
                content_lines.append(apply_background_to_line(line_with_margins, width, bg_fn))
            else:
                vis_len = visible_width(line_with_margins)
                pad_needed = max(0, width - vis_len)
                content_lines.append(line_with_margins + " " * pad_needed)

        # Top/bottom padding
        empty_line = " " * width
        empty_lines: list[str] = []
        for _ in range(self._padding_y):
            if bg_fn:
                empty_lines.append(apply_background_to_line(empty_line, width, bg_fn))
            else:
                empty_lines.append(empty_line)

        result = [*empty_lines, *content_lines, *empty_lines]

        self._cached_text = self._text
        self._cached_width = width
        self._cached_lines = result

        return result if result else [""]

    # ------------------------------------------------------------------
    # Default style helpers
    # ------------------------------------------------------------------

    def _apply_default_style(self, text: str) -> str:
        if not self._default_text_style:
            return text
        styled = text
        if self._default_text_style.color:
            styled = self._default_text_style.color(styled)
        if self._default_text_style.bold:
            styled = self._theme.bold(styled)
        if self._default_text_style.italic:
            styled = self._theme.italic(styled)
        if self._default_text_style.strikethrough:
            styled = self._theme.strikethrough(styled)
        if self._default_text_style.underline:
            styled = self._theme.underline(styled)
        return styled

    def _get_default_style_prefix(self) -> str:
        if not self._default_text_style:
            return ""
        if self._default_style_prefix is not None:
            return self._default_style_prefix
        sentinel = "\x00"
        styled = sentinel
        if self._default_text_style.color:
            styled = self._default_text_style.color(styled)
        if self._default_text_style.bold:
            styled = self._theme.bold(styled)
        if self._default_text_style.italic:
            styled = self._theme.italic(styled)
        if self._default_text_style.strikethrough:
            styled = self._theme.strikethrough(styled)
        if self._default_text_style.underline:
            styled = self._theme.underline(styled)
        idx = styled.find(sentinel)
        self._default_style_prefix = styled[:idx] if idx >= 0 else ""
        return self._default_style_prefix

    def _get_style_prefix(self, style_fn: Callable[[str], str]) -> str:
        sentinel = "\x00"
        styled = style_fn(sentinel)
        idx = styled.find(sentinel)
        return styled[:idx] if idx >= 0 else ""

    def _get_default_inline_style_context(self) -> _InlineStyleContext:
        return _InlineStyleContext(
            apply_text=self._apply_default_style,
            style_prefix=self._get_default_style_prefix(),
        )

    # ------------------------------------------------------------------
    # Token rendering
    # ------------------------------------------------------------------

    def _render_token(
        self,
        token: dict[str, Any],
        width: int,
        next_token_type: str | None,
    ) -> list[str]:
        lines: list[str] = []
        token_type = token.get("type", "")

        if token_type == "heading":
            depth = token.get("attrs", {}).get("level", 1)
            heading_prefix = "#" * depth + " "
            heading_text = self._render_inline_tokens(token.get("children", []))
            if depth == 1:
                styled = self._theme.heading(self._theme.bold(self._theme.underline(heading_text)))
            elif depth == 2:
                styled = self._theme.heading(self._theme.bold(heading_text))
            else:
                styled = self._theme.heading(self._theme.bold(heading_prefix + heading_text))
            lines.append(styled)
            if next_token_type != "blank_line":
                lines.append("")

        elif token_type == "paragraph":
            para_text = self._render_inline_tokens(token.get("children", []))
            lines.append(para_text)
            if next_token_type and next_token_type not in ("list", "blank_line"):
                lines.append("")

        elif token_type == "code_block":
            info = token.get("attrs", {}).get("info", "") or ""
            raw_code = token.get("attrs", {}).get("raw", "") or token.get("raw", "") or ""
            # mistune includes trailing newline; strip it
            code_text = raw_code.rstrip("\n")
            indent = self._theme.code_block_indent
            lines.append(self._theme.code_block_border(f"```{info}"))
            if self._theme.highlight_code:
                highlighted = self._theme.highlight_code(code_text, info or None)
                for hl_line in highlighted:
                    lines.append(f"{indent}{hl_line}")
            else:
                for code_line in code_text.split("\n"):
                    lines.append(f"{indent}{self._theme.code_block(code_line)}")
            lines.append(self._theme.code_block_border("```"))
            if next_token_type != "blank_line":
                lines.append("")

        elif token_type == "list":
            list_lines = self._render_list(token, 0)
            lines.extend(list_lines)

        elif token_type == "table":
            table_lines = self._render_table(token, width)
            lines.extend(table_lines)

        elif token_type == "block_quote":

            def quote_style(t: str) -> str:
                return self._theme.quote(self._theme.italic(t))

            quote_ctx = _InlineStyleContext(
                apply_text=quote_style,
                style_prefix=self._get_style_prefix(quote_style),
            )
            # Render blockquote children
            quote_text_parts: list[str] = []
            for child in token.get("children", []):
                if child.get("type") == "paragraph":
                    quote_text_parts.append(self._render_inline_tokens(child.get("children", []), quote_ctx))
                else:
                    quote_text_parts.append(self._render_inline_tokens([child], quote_ctx))
            quote_text = "\n".join(quote_text_parts)
            quote_content_width = max(1, width - 2)
            for quote_line in quote_text.split("\n"):
                wrapped = wrap_text_with_ansi(quote_line, quote_content_width)
                for wl in wrapped:
                    lines.append(self._theme.quote_border("\u2502 ") + wl)
            if next_token_type != "blank_line":
                lines.append("")

        elif token_type == "thematic_break":
            lines.append(self._theme.hr("\u2500" * min(width, 80)))
            if next_token_type != "blank_line":
                lines.append("")

        elif token_type == "block_html":
            raw = token.get("raw", "") or token.get("children", "")
            if isinstance(raw, str):
                lines.append(self._apply_default_style(raw.strip()))

        elif token_type == "blank_line":
            lines.append("")

        else:
            # Fallback: try text or children
            text = token.get("raw", "") or token.get("text", "")
            if isinstance(text, str) and text:
                lines.append(text)
            elif token.get("children"):
                rendered = self._render_inline_tokens(token["children"])
                if rendered:
                    lines.append(rendered)

        return lines

    # ------------------------------------------------------------------
    # Inline token rendering
    # ------------------------------------------------------------------

    def _render_inline_tokens(
        self,
        tokens: list[dict[str, Any]],
        style_context: _InlineStyleContext | None = None,
    ) -> str:
        result = ""
        ctx = style_context or self._get_default_inline_style_context()
        apply_text = ctx.apply_text
        style_prefix = ctx.style_prefix

        def apply_text_with_newlines(text: str) -> str:
            segments = text.split("\n")
            return "\n".join(apply_text(s) for s in segments)

        for token in tokens:
            tt = token.get("type", "")

            if tt == "text":
                children = token.get("children")
                if children and isinstance(children, list):
                    result += self._render_inline_tokens(children, ctx)
                else:
                    raw = token.get("raw", "") or token.get("children", "")
                    if isinstance(raw, str):
                        result += apply_text_with_newlines(raw)

            elif tt == "paragraph":
                result += self._render_inline_tokens(token.get("children", []), ctx)

            elif tt == "strong":
                bold_content = self._render_inline_tokens(token.get("children", []), ctx)
                result += self._theme.bold(bold_content) + style_prefix

            elif tt == "emphasis":
                italic_content = self._render_inline_tokens(token.get("children", []), ctx)
                result += self._theme.italic(italic_content) + style_prefix

            elif tt == "codespan":
                raw = token.get("raw", "") or token.get("children", "")
                if isinstance(raw, str):
                    result += self._theme.code(raw) + style_prefix

            elif tt == "link":
                link_text = self._render_inline_tokens(token.get("children", []), ctx)
                attrs = token.get("attrs", {}) or {}
                href = attrs.get("url", "") or ""
                # Get the plain text for comparison
                plain_children = token.get("children", [])
                plain_text = self._get_plain_text(plain_children)
                href_for_cmp = href[7:] if href.startswith("mailto:") else href
                if plain_text in (href, href_for_cmp):
                    result += self._theme.link(self._theme.underline(link_text)) + style_prefix
                else:
                    result += (
                        self._theme.link(self._theme.underline(link_text))
                        + self._theme.link_url(f" ({href})")
                        + style_prefix
                    )

            elif tt == "softbreak" or tt == "linebreak":
                result += "\n"

            elif tt == "strikethrough":
                del_content = self._render_inline_tokens(token.get("children", []), ctx)
                result += self._theme.strikethrough(del_content) + style_prefix

            elif tt == "block_html" or tt == "inline_html":
                raw = token.get("raw", "") or token.get("children", "")
                if isinstance(raw, str):
                    result += apply_text_with_newlines(raw)

            elif tt == "image":
                # Render image alt text as fallback
                attrs = token.get("attrs", {}) or {}
                alt = attrs.get("alt", "") or ""
                if alt:
                    result += apply_text(f"[Image: {alt}]")

            else:
                # Fallback
                raw = token.get("raw", "") or token.get("children", "")
                if isinstance(raw, str) and raw:
                    result += apply_text_with_newlines(raw)
                elif isinstance(raw, list):
                    result += self._render_inline_tokens(raw, ctx)

        return result

    def _get_plain_text(self, tokens: list[dict[str, Any]]) -> str:
        """Extract plain text from inline tokens (for comparison)."""
        result = ""
        for token in tokens:
            tt = token.get("type", "")
            if tt == "text":
                children = token.get("children")
                if isinstance(children, str):
                    result += children
                elif isinstance(children, list):
                    result += self._get_plain_text(children)
                else:
                    raw = token.get("raw", "")
                    if isinstance(raw, str):
                        result += raw
            elif tt == "codespan":
                raw = token.get("raw", "") or token.get("children", "")
                if isinstance(raw, str):
                    result += raw
            else:
                children = token.get("children")
                if isinstance(children, list):
                    result += self._get_plain_text(children)
                elif isinstance(children, str):
                    result += children
        return result

    # ------------------------------------------------------------------
    # List rendering
    # ------------------------------------------------------------------

    def _render_list(self, token: dict[str, Any], depth: int) -> list[str]:
        lines: list[str] = []
        indent = "  " * depth
        attrs = token.get("attrs", {}) or {}
        ordered = attrs.get("ordered", False)
        start_number = attrs.get("start", 1) or 1
        items = token.get("children", [])

        for i, item in enumerate(items):
            if item.get("type") != "list_item":
                continue
            bullet = f"{start_number + i}. " if ordered else "- "
            item_lines = self._render_list_item(item.get("children", []), depth)

            if item_lines:
                first_line = item_lines[0]
                # Check for nested list (heuristic)
                is_nested = first_line.startswith("  ") and "\x1b" in first_line
                if is_nested:
                    lines.append(first_line)
                else:
                    lines.append(indent + self._theme.list_bullet(bullet) + first_line)

                for j in range(1, len(item_lines)):
                    line = item_lines[j]
                    is_nested_line = line.startswith("  ") and "\x1b" in line
                    if is_nested_line:
                        lines.append(line)
                    else:
                        lines.append(f"{indent}  {line}")
            else:
                lines.append(indent + self._theme.list_bullet(bullet))

        return lines

    def _render_list_item(self, tokens: list[dict[str, Any]], parent_depth: int) -> list[str]:
        lines: list[str] = []
        for token in tokens:
            tt = token.get("type", "")
            if tt == "list":
                nested = self._render_list(token, parent_depth + 1)
                lines.extend(nested)
            elif tt == "paragraph":
                text = self._render_inline_tokens(token.get("children", []))
                lines.append(text)
            elif tt == "code_block":
                info = token.get("attrs", {}).get("info", "") or ""
                raw_code = token.get("attrs", {}).get("raw", "") or token.get("raw", "") or ""
                code_text = raw_code.rstrip("\n")
                ind = self._theme.code_block_indent
                lines.append(self._theme.code_block_border(f"```{info}"))
                if self._theme.highlight_code:
                    highlighted = self._theme.highlight_code(code_text, info or None)
                    for hl_line in highlighted:
                        lines.append(f"{ind}{hl_line}")
                else:
                    for code_line in code_text.split("\n"):
                        lines.append(f"{ind}{self._theme.code_block(code_line)}")
                lines.append(self._theme.code_block_border("```"))
            elif tt == "text":
                children = token.get("children")
                if isinstance(children, list) and children:
                    text = self._render_inline_tokens(children)
                else:
                    raw = token.get("raw", "") or (children if isinstance(children, str) else "")
                    text = self._apply_default_style(raw) if raw else ""
                if text:
                    lines.append(text)
            else:
                text = self._render_inline_tokens([token])
                if text:
                    lines.append(text)
        return lines

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _get_longest_word_width(self, text: str, max_width: int | None = None) -> int:
        words = [w for w in text.split() if w]
        longest = 0
        for word in words:
            longest = max(longest, visible_width(word))
        if max_width is not None:
            return min(longest, max_width)
        return longest

    def _wrap_cell_text(self, text: str, max_width: int) -> list[str]:
        return wrap_text_with_ansi(text, max(1, max_width))

    def _render_table(self, token: dict[str, Any], available_width: int) -> list[str]:
        lines: list[str] = []
        children = token.get("children", [])

        # Find head and body
        head_rows: list[dict[str, Any]] = []
        body_rows: list[dict[str, Any]] = []
        for child in children:
            if child.get("type") == "table_head":
                head_rows = child.get("children", [])
            elif child.get("type") == "table_body":
                body_rows = child.get("children", [])

        if not head_rows:
            return lines

        # Get header cells
        header_row = head_rows[0] if head_rows else {}
        header_cells = header_row.get("children", [])
        num_cols = len(header_cells)
        if num_cols == 0:
            return lines

        # Border overhead: "| " + (n-1) * " | " + " |" = 3n + 1
        border_overhead = 3 * num_cols + 1
        available_for_cells = available_width - border_overhead
        if available_for_cells <= num_cols:
            # Too narrow -- fall back to raw text
            raw = token.get("raw", "")
            if raw:
                lines.extend(wrap_text_with_ansi(raw, available_width))
            lines.append("")
            return lines

        max_unbroken = 30

        # Natural and min widths
        natural_widths: list[int] = []
        min_word_widths: list[int] = []
        for i in range(num_cols):
            cell = header_cells[i] if i < len(header_cells) else {}
            header_text = self._render_inline_tokens(cell.get("children", []))
            natural_widths.append(visible_width(header_text))
            min_word_widths.append(max(1, self._get_longest_word_width(header_text, max_unbroken)))

        for row in body_rows:
            row_cells = row.get("children", [])
            for i in range(min(len(row_cells), num_cols)):
                cell_text = self._render_inline_tokens(row_cells[i].get("children", []))
                if i < len(natural_widths):
                    natural_widths[i] = max(natural_widths[i], visible_width(cell_text))
                    min_word_widths[i] = max(
                        min_word_widths[i],
                        self._get_longest_word_width(cell_text, max_unbroken),
                    )

        min_column_widths = list(min_word_widths)
        min_cells_width = sum(min_column_widths)

        if min_cells_width > available_for_cells:
            min_column_widths = [1] * num_cols
            remaining = available_for_cells - num_cols
            if remaining > 0:
                total_weight = sum(max(0, w - 1) for w in min_word_widths)
                growth = [
                    (int(max(0, w - 1) / total_weight * remaining) if total_weight > 0 else 0) for w in min_word_widths
                ]
                for i in range(num_cols):
                    min_column_widths[i] += growth[i]
                allocated = sum(growth)
                leftover = remaining - allocated
                for i in range(num_cols):
                    if leftover <= 0:
                        break
                    min_column_widths[i] += 1
                    leftover -= 1
            min_cells_width = sum(min_column_widths)

        # Calculate final column widths
        total_natural = sum(natural_widths) + border_overhead
        if total_natural <= available_width:
            column_widths = [max(natural_widths[i], min_column_widths[i]) for i in range(num_cols)]
        else:
            total_grow = sum(max(0, natural_widths[i] - min_column_widths[i]) for i in range(num_cols))
            extra = max(0, available_for_cells - min_cells_width)
            column_widths = []
            for i in range(num_cols):
                delta = max(0, natural_widths[i] - min_column_widths[i])
                grow = int(delta / total_grow * extra) if total_grow > 0 else 0
                column_widths.append(min_column_widths[i] + grow)

            allocated = sum(column_widths)
            remaining_space = available_for_cells - allocated
            while remaining_space > 0:
                grew = False
                for i in range(num_cols):
                    if remaining_space <= 0:
                        break
                    if column_widths[i] < natural_widths[i]:
                        column_widths[i] += 1
                        remaining_space -= 1
                        grew = True
                if not grew:
                    break

        # Top border
        top_cells = ["\u2500" * w for w in column_widths]
        lines.append(f"\u250c\u2500{'\u2500\u252c\u2500'.join(top_cells)}\u2500\u2510")

        # Header
        header_cell_lines: list[list[str]] = []
        for i in range(num_cols):
            cell = header_cells[i] if i < len(header_cells) else {}
            text = self._render_inline_tokens(cell.get("children", []))
            header_cell_lines.append(self._wrap_cell_text(text, column_widths[i]))

        header_line_count = max((len(cl) for cl in header_cell_lines), default=1)
        for line_idx in range(header_line_count):
            parts = []
            for col_idx in range(num_cols):
                cl = header_cell_lines[col_idx]
                text = cl[line_idx] if line_idx < len(cl) else ""
                padded = text + " " * max(0, column_widths[col_idx] - visible_width(text))
                parts.append(self._theme.bold(padded))
            lines.append(f"\u2502 {' \u2502 '.join(parts)} \u2502")

        # Separator
        sep_cells = ["\u2500" * w for w in column_widths]
        separator = f"\u251c\u2500{'\u2500\u253c\u2500'.join(sep_cells)}\u2500\u2524"
        lines.append(separator)

        # Data rows
        for row_index, row in enumerate(body_rows):
            row_cells = row.get("children", [])
            row_cell_lines: list[list[str]] = []
            for i in range(num_cols):
                cell = row_cells[i] if i < len(row_cells) else {}
                text = self._render_inline_tokens(cell.get("children", []))
                row_cell_lines.append(self._wrap_cell_text(text, column_widths[i]))

            row_line_count = max((len(cl) for cl in row_cell_lines), default=1)
            for line_idx in range(row_line_count):
                parts = []
                for col_idx in range(num_cols):
                    cl = row_cell_lines[col_idx]
                    text = cl[line_idx] if line_idx < len(cl) else ""
                    padded = text + " " * max(0, column_widths[col_idx] - visible_width(text))
                    parts.append(padded)
                lines.append(f"\u2502 {' \u2502 '.join(parts)} \u2502")

            if row_index < len(body_rows) - 1:
                lines.append(separator)

        # Bottom border
        bottom_cells = ["\u2500" * w for w in column_widths]
        lines.append(f"\u2514\u2500{'\u2500\u2534\u2500'.join(bottom_cells)}\u2500\u2518")
        lines.append("")
        return lines
