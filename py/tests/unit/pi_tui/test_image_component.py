"""Tests for pi_tui.components.image module."""

from __future__ import annotations

from unittest.mock import patch

from pi_tui.components.image import Image, ImageOptions, ImageTheme
from pi_tui.terminal_image import (
    ImageDimensions,
    RenderResult,
    TerminalCapabilities,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity_color(s: str) -> str:
    return s


def _bracket_color(s: str) -> str:
    return f"<{s}>"


def _make_theme(color_fn: object | None = None) -> ImageTheme:
    return ImageTheme(fallback_color=color_fn or _identity_color)  # type: ignore[arg-type]


_NO_IMAGE_CAPS = TerminalCapabilities(images=None, true_color=True, hyperlinks=True)
_KITTY_CAPS = TerminalCapabilities(images="kitty", true_color=True, hyperlinks=True)


# ---------------------------------------------------------------------------
# ImageOptions dataclass
# ---------------------------------------------------------------------------


class TestImageOptions:
    def test_defaults(self) -> None:
        opts = ImageOptions()
        assert opts.max_width_cells is None
        assert opts.max_height_cells is None
        assert opts.filename is None
        assert opts.image_id is None

    def test_custom_values(self) -> None:
        opts = ImageOptions(max_width_cells=40, max_height_cells=20, filename="photo.png", image_id=42)
        assert opts.max_width_cells == 40
        assert opts.max_height_cells == 20
        assert opts.filename == "photo.png"
        assert opts.image_id == 42


# ---------------------------------------------------------------------------
# ImageTheme dataclass
# ---------------------------------------------------------------------------


class TestImageTheme:
    def test_fallback_color_stored(self) -> None:
        theme = _make_theme(_bracket_color)
        assert theme.fallback_color("hello") == "<hello>"

    def test_identity_color(self) -> None:
        theme = _make_theme(_identity_color)
        assert theme.fallback_color("test") == "test"


# ---------------------------------------------------------------------------
# Image construction
# ---------------------------------------------------------------------------


class TestImageConstruction:
    @patch("pi_tui.components.image.get_image_dimensions")
    def test_default_options_when_none(self, mock_get_dims: object) -> None:
        """When options is None, defaults are used."""
        dims = ImageDimensions(width_px=100, height_px=200)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        assert img._options.max_width_cells is None
        assert img._options.filename is None
        assert img._image_id is None

    @patch("pi_tui.components.image.get_image_dimensions")
    def test_explicit_options(self, mock_get_dims: object) -> None:
        opts = ImageOptions(max_width_cells=30, image_id=99)
        dims = ImageDimensions(width_px=100, height_px=200)
        img = Image("b64data", "image/png", _make_theme(), options=opts, dimensions=dims)
        assert img._options.max_width_cells == 30
        assert img._image_id == 99

    @patch("pi_tui.components.image.get_image_dimensions", return_value=ImageDimensions(width_px=320, height_px=240))
    def test_dimensions_from_get_image_dimensions(self, mock_get_dims: object) -> None:
        """When dimensions is not provided, get_image_dimensions is called."""
        img = Image("b64data", "image/png", _make_theme())
        assert img._dimensions == ImageDimensions(width_px=320, height_px=240)

    @patch("pi_tui.components.image.get_image_dimensions", return_value=None)
    def test_fallback_dimensions_when_detection_fails(self, mock_get_dims: object) -> None:
        """When get_image_dimensions returns None, default 800x600 is used."""
        img = Image("b64data", "image/png", _make_theme())
        assert img._dimensions == ImageDimensions(width_px=800, height_px=600)

    def test_explicit_dimensions_skips_detection(self) -> None:
        """When dimensions is explicitly provided, get_image_dimensions is not called."""
        dims = ImageDimensions(width_px=500, height_px=400)
        with patch("pi_tui.components.image.get_image_dimensions"):
            img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
            # get_image_dimensions is not called because we short-circuit with `or`
            # but due to how `or` works, if dims is provided it won't be called
            assert img._dimensions == dims

    def test_get_image_id(self) -> None:
        opts = ImageOptions(image_id=123)
        dims = ImageDimensions(width_px=100, height_px=100)
        img = Image("b64data", "image/png", _make_theme(), options=opts, dimensions=dims)
        assert img.get_image_id() == 123

    def test_get_image_id_none(self) -> None:
        dims = ImageDimensions(width_px=100, height_px=100)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        assert img.get_image_id() is None


# ---------------------------------------------------------------------------
# render() — fallback (no image protocol)
# ---------------------------------------------------------------------------


class TestRenderFallback:
    @patch("pi_tui.components.image.get_capabilities", return_value=_NO_IMAGE_CAPS)
    def test_no_image_caps_returns_fallback(self, mock_caps: object) -> None:
        dims = ImageDimensions(width_px=640, height_px=480)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        lines = img.render(80)
        assert len(lines) == 1
        assert "[Image:" in lines[0]
        assert "640x480" in lines[0]

    @patch("pi_tui.components.image.get_capabilities", return_value=_NO_IMAGE_CAPS)
    def test_fallback_includes_filename(self, mock_caps: object) -> None:
        dims = ImageDimensions(width_px=640, height_px=480)
        opts = ImageOptions(filename="screenshot.png")
        img = Image("b64data", "image/png", _make_theme(), options=opts, dimensions=dims)
        lines = img.render(80)
        assert "screenshot.png" in lines[0]

    @patch("pi_tui.components.image.get_capabilities", return_value=_NO_IMAGE_CAPS)
    def test_fallback_applies_theme_color(self, mock_caps: object) -> None:
        dims = ImageDimensions(width_px=100, height_px=100)
        theme = _make_theme(_bracket_color)
        img = Image("b64data", "image/png", theme, dimensions=dims)
        lines = img.render(80)
        assert lines[0].startswith("<")
        assert lines[0].endswith(">")

    @patch("pi_tui.components.image.render_image", return_value=None)
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_fallback_when_render_image_returns_none(self, mock_caps: object, mock_render: object) -> None:
        """When caps.images is not None but render_image returns None, fallback is used."""
        dims = ImageDimensions(width_px=640, height_px=480)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        lines = img.render(80)
        assert len(lines) == 1
        assert "[Image:" in lines[0]


# ---------------------------------------------------------------------------
# render() — with image protocol
# ---------------------------------------------------------------------------


class TestRenderWithProtocol:
    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_single_row_image(self, mock_caps: object, mock_render: object) -> None:
        mock_render.return_value = RenderResult(sequence="IMG_SEQ", rows=1, image_id=5)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=50)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        lines = img.render(80)
        # Single row: no empty lines before, just the sequence
        assert len(lines) == 1
        assert lines[0] == "IMG_SEQ"

    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_multi_row_image(self, mock_caps: object, mock_render: object) -> None:
        mock_render.return_value = RenderResult(sequence="IMG_SEQ", rows=4, image_id=10)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=800, height_px=600)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        lines = img.render(80)
        # rows-1 empty lines + 1 line with move_up + sequence
        assert len(lines) == 4
        for i in range(3):
            assert lines[i] == ""
        assert "\x1b[3A" in lines[3]  # move up 3 lines
        assert "IMG_SEQ" in lines[3]

    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_image_id_updated_from_result(self, mock_caps: object, mock_render: object) -> None:
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1, image_id=77)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        assert img.get_image_id() is None
        img.render(80)
        assert img.get_image_id() == 77

    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_image_id_not_updated_when_result_none(self, mock_caps: object, mock_render: object) -> None:
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1, image_id=None)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        opts = ImageOptions(image_id=42)
        img = Image("b64data", "image/png", _make_theme(), options=opts, dimensions=dims)
        img.render(80)
        assert img.get_image_id() == 42


# ---------------------------------------------------------------------------
# render() — width constraints
# ---------------------------------------------------------------------------


class TestRenderWidthConstraint:
    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_max_width_from_render_width(self, mock_caps: object, mock_render: object) -> None:
        """max_width = min(width - 2, max_width_cells or 60)."""
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        # No max_width_cells, width=50 -> max_width = min(48, 60) = 48
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        img.render(50)
        call_args = mock_render.call_args  # type: ignore[attr-defined]
        render_opts = call_args[0][2]  # third positional arg: ImageRenderOptions
        assert render_opts.max_width_cells == 48

    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_max_width_cells_option_limits(self, mock_caps: object, mock_render: object) -> None:
        """When max_width_cells is set and smaller than width-2, it wins."""
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        opts = ImageOptions(max_width_cells=20)
        img = Image("b64data", "image/png", _make_theme(), options=opts, dimensions=dims)
        img.render(80)
        call_args = mock_render.call_args  # type: ignore[attr-defined]
        render_opts = call_args[0][2]
        assert render_opts.max_width_cells == 20

    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_narrow_width_constrains_further(self, mock_caps: object, mock_render: object) -> None:
        """When width-2 is smaller than max_width_cells, width-2 wins."""
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        opts = ImageOptions(max_width_cells=60)
        img = Image("b64data", "image/png", _make_theme(), options=opts, dimensions=dims)
        img.render(30)  # width-2 = 28 < 60
        call_args = mock_render.call_args  # type: ignore[attr-defined]
        render_opts = call_args[0][2]
        assert render_opts.max_width_cells == 28


# ---------------------------------------------------------------------------
# Caching behavior
# ---------------------------------------------------------------------------


class TestCaching:
    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_same_width_uses_cache(self, mock_caps: object, mock_render: object) -> None:
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        result1 = img.render(80)
        result2 = img.render(80)
        assert result1 is result2
        assert mock_render.call_count == 1  # type: ignore[attr-defined]

    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_different_width_invalidates_cache(self, mock_caps: object, mock_render: object) -> None:
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        img.render(80)
        img.render(100)
        assert mock_render.call_count == 2  # type: ignore[attr-defined]

    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_invalidate_clears_cache(self, mock_caps: object, mock_render: object) -> None:
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        img.render(80)
        img.invalidate()
        img.render(80)
        assert mock_render.call_count == 2  # type: ignore[attr-defined]

    @patch("pi_tui.components.image.get_capabilities", return_value=_NO_IMAGE_CAPS)
    def test_fallback_is_also_cached(self, mock_caps: object) -> None:
        dims = ImageDimensions(width_px=100, height_px=100)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        result1 = img.render(80)
        result2 = img.render(80)
        assert result1 is result2

    @patch("pi_tui.components.image.render_image")
    @patch("pi_tui.components.image.get_capabilities", return_value=_KITTY_CAPS)
    def test_invalidate_resets_both_fields(self, mock_caps: object, mock_render: object) -> None:
        mock_render.return_value = RenderResult(sequence="SEQ", rows=1)  # type: ignore[attr-defined]
        dims = ImageDimensions(width_px=100, height_px=100)
        img = Image("b64data", "image/png", _make_theme(), dimensions=dims)
        img.render(80)
        assert img._cached_lines is not None
        assert img._cached_width == 80
        img.invalidate()
        assert img._cached_lines is None
        assert img._cached_width is None
