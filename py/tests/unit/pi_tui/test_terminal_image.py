"""Tests for pi_tui.terminal_image module."""

from __future__ import annotations

import base64
import struct
from unittest.mock import patch

import pytest

from pi_tui.terminal_image import (
    CellDimensions,
    ImageDimensions,
    TerminalCapabilities,
    allocate_image_id,
    calculate_image_rows,
    detect_capabilities,
    encode_iterm2,
    encode_kitty,
    get_image_dimensions,
    is_image_line,
)


# ---------------------------------------------------------------------------
# detect_capabilities
# ---------------------------------------------------------------------------


class TestDetectCapabilities:
    """Tests for detect_capabilities with various env vars."""

    @patch.dict("os.environ", {"KITTY_WINDOW_ID": "1"}, clear=True)
    def test_kitty_via_window_id(self) -> None:
        caps = detect_capabilities()
        assert caps == TerminalCapabilities(images="kitty", true_color=True, hyperlinks=True)

    @patch.dict("os.environ", {"TERM_PROGRAM": "kitty"}, clear=True)
    def test_kitty_via_term_program(self) -> None:
        caps = detect_capabilities()
        assert caps.images == "kitty"

    @patch.dict("os.environ", {"TERM_PROGRAM": "ghostty"}, clear=True)
    def test_ghostty_via_term_program(self) -> None:
        caps = detect_capabilities()
        assert caps.images == "kitty"

    @patch.dict("os.environ", {"TERM": "xterm-ghostty"}, clear=True)
    def test_ghostty_via_term(self) -> None:
        caps = detect_capabilities()
        assert caps.images == "kitty"

    @patch.dict("os.environ", {"GHOSTTY_RESOURCES_DIR": "/usr/share/ghostty"}, clear=True)
    def test_ghostty_via_resources_dir(self) -> None:
        caps = detect_capabilities()
        assert caps.images == "kitty"

    @patch.dict("os.environ", {"WEZTERM_PANE": "0"}, clear=True)
    def test_wezterm_via_pane(self) -> None:
        caps = detect_capabilities()
        assert caps.images == "kitty"

    @patch.dict("os.environ", {"TERM_PROGRAM": "WezTerm"}, clear=True)
    def test_wezterm_via_term_program(self) -> None:
        caps = detect_capabilities()
        assert caps.images == "kitty"

    @patch.dict("os.environ", {"ITERM_SESSION_ID": "w0t0p0"}, clear=True)
    def test_iterm2_via_session_id(self) -> None:
        caps = detect_capabilities()
        assert caps.images == "iterm2"

    @patch.dict("os.environ", {"TERM_PROGRAM": "iTerm.app"}, clear=True)
    def test_iterm2_via_term_program(self) -> None:
        caps = detect_capabilities()
        assert caps.images == "iterm2"

    @patch.dict("os.environ", {"TERM_PROGRAM": "vscode"}, clear=True)
    def test_vscode_no_images(self) -> None:
        caps = detect_capabilities()
        assert caps.images is None
        assert caps.true_color is True

    @patch.dict("os.environ", {"TERM_PROGRAM": "alacritty"}, clear=True)
    def test_alacritty_no_images(self) -> None:
        caps = detect_capabilities()
        assert caps.images is None
        assert caps.true_color is True

    @patch.dict("os.environ", {"COLORTERM": "truecolor"}, clear=True)
    def test_generic_truecolor(self) -> None:
        caps = detect_capabilities()
        assert caps.images is None
        assert caps.true_color is True

    @patch.dict("os.environ", {"COLORTERM": "24bit"}, clear=True)
    def test_generic_24bit(self) -> None:
        caps = detect_capabilities()
        assert caps.images is None
        assert caps.true_color is True

    @patch.dict("os.environ", {}, clear=True)
    def test_unknown_terminal(self) -> None:
        caps = detect_capabilities()
        assert caps.images is None
        assert caps.true_color is False
        assert caps.hyperlinks is True


# ---------------------------------------------------------------------------
# encode_kitty
# ---------------------------------------------------------------------------


class TestEncodeKitty:
    def test_small_data_single_chunk(self) -> None:
        data = base64.b64encode(b"hello").decode("ascii")
        result = encode_kitty(data)
        assert result.startswith("\x1b_G")
        assert result.endswith("\x1b\\")
        assert "a=T" in result
        assert "f=100" in result
        assert "q=2" in result
        assert data in result
        # Single chunk should NOT contain m= parameter
        assert "m=" not in result

    def test_large_data_multiple_chunks(self) -> None:
        # Create data larger than 4096 bytes
        raw = b"x" * 4000  # base64 of 4000 bytes is ~5336 chars, > 4096
        data = base64.b64encode(raw).decode("ascii")
        result = encode_kitty(data)
        # First chunk has m=1
        assert "m=1;" in result
        # Last chunk has m=0
        assert "m=0;" in result

    def test_columns_and_rows(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_kitty(data, columns=40, rows=10)
        assert "c=40" in result
        assert "r=10" in result

    def test_image_id(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_kitty(data, image_id=42)
        assert "i=42" in result

    def test_no_optional_params(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_kitty(data)
        assert "c=" not in result
        assert "r=" not in result
        assert "i=" not in result

    def test_chunk_boundary_exact(self) -> None:
        # Create base64 data exactly 4096 chars long (single chunk)
        # base64 encodes 3 bytes -> 4 chars, so 3072 bytes -> 4096 chars
        raw = b"A" * 3072
        data = base64.b64encode(raw).decode("ascii")
        assert len(data) == 4096
        result = encode_kitty(data)
        # Exactly 4096 should be single chunk (no m= parameter)
        assert "m=" not in result


# ---------------------------------------------------------------------------
# encode_iterm2
# ---------------------------------------------------------------------------


class TestEncodeIterm2:
    def test_basic_output(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_iterm2(data)
        assert result.startswith("\x1b]1337;File=")
        assert result.endswith("\x07")
        assert "inline=1" in result
        assert f":{data}\x07" in result

    def test_inline_false(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_iterm2(data, inline=False)
        assert "inline=0" in result

    def test_width_and_height(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_iterm2(data, width=80, height="auto")
        assert "width=80" in result
        assert "height=auto" in result

    def test_name(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_iterm2(data, name="photo.png")
        name_b64 = base64.b64encode(b"photo.png").decode("ascii")
        assert f"name={name_b64}" in result

    def test_preserve_aspect_ratio_false(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_iterm2(data, preserve_aspect_ratio=False)
        assert "preserveAspectRatio=0" in result

    def test_preserve_aspect_ratio_true_omitted(self) -> None:
        data = base64.b64encode(b"img").decode("ascii")
        result = encode_iterm2(data, preserve_aspect_ratio=True)
        # True is the default, so preserveAspectRatio param is NOT added
        assert "preserveAspectRatio" not in result


# ---------------------------------------------------------------------------
# get_image_dimensions - PNG
# ---------------------------------------------------------------------------


def _make_png(width: int, height: int) -> str:
    """Build a minimal valid PNG header and return base64."""
    # PNG signature (8 bytes) + IHDR length (4) + "IHDR" (4) + width (4) + height (4)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">II", width, height)
    # IHDR chunk: length(13) + "IHDR" + width + height + bit_depth + color + comp + filter + interlace
    ihdr_body = ihdr_data + b"\x08\x02\x00\x00\x00"  # 8-bit RGB, no interlace
    ihdr_length = struct.pack(">I", len(ihdr_body))
    data = sig + ihdr_length + b"IHDR" + ihdr_body
    return base64.b64encode(data).decode("ascii")


class TestGetImageDimensionsPng:
    def test_valid_png(self) -> None:
        b64 = _make_png(320, 240)
        dims = get_image_dimensions(b64, "image/png")
        assert dims is not None
        assert dims.width_px == 320
        assert dims.height_px == 240

    def test_large_png(self) -> None:
        b64 = _make_png(3840, 2160)
        dims = get_image_dimensions(b64, "image/png")
        assert dims is not None
        assert dims.width_px == 3840
        assert dims.height_px == 2160

    def test_invalid_png_signature(self) -> None:
        data = b"\x00" * 24
        b64 = base64.b64encode(data).decode("ascii")
        dims = get_image_dimensions(b64, "image/png")
        assert dims is None

    def test_too_short_png(self) -> None:
        data = b"\x89PNG"
        b64 = base64.b64encode(data).decode("ascii")
        dims = get_image_dimensions(b64, "image/png")
        assert dims is None


# ---------------------------------------------------------------------------
# get_image_dimensions - JPEG
# ---------------------------------------------------------------------------


def _make_jpeg(width: int, height: int) -> str:
    """Build a minimal JPEG with SOF0 marker and return base64."""
    # SOI marker
    data = b"\xFF\xD8"
    # APP0 marker (minimal, to advance past)
    app0_body = b"\x00" * 14
    data += b"\xFF\xE0" + struct.pack(">H", len(app0_body) + 2) + app0_body
    # SOF0 marker: FF C0, length, precision, height, width
    sof_body = struct.pack(">BHH", 8, height, width) + b"\x03" + b"\x00" * 9
    data += b"\xFF\xC0" + struct.pack(">H", len(sof_body) + 2) + sof_body
    return base64.b64encode(data).decode("ascii")


class TestGetImageDimensionsJpeg:
    def test_valid_jpeg(self) -> None:
        b64 = _make_jpeg(640, 480)
        dims = get_image_dimensions(b64, "image/jpeg")
        assert dims is not None
        assert dims.width_px == 640
        assert dims.height_px == 480

    def test_invalid_jpeg_signature(self) -> None:
        data = b"\x00\x00" + b"\x00" * 20
        b64 = base64.b64encode(data).decode("ascii")
        dims = get_image_dimensions(b64, "image/jpeg")
        assert dims is None

    def test_too_short_jpeg(self) -> None:
        data = b"\xFF"
        b64 = base64.b64encode(data).decode("ascii")
        dims = get_image_dimensions(b64, "image/jpeg")
        assert dims is None


# ---------------------------------------------------------------------------
# get_image_dimensions - GIF
# ---------------------------------------------------------------------------


def _make_gif(width: int, height: int) -> str:
    """Build a minimal GIF89a header and return base64."""
    data = b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00"
    return base64.b64encode(data).decode("ascii")


class TestGetImageDimensionsGif:
    def test_valid_gif89a(self) -> None:
        b64 = _make_gif(100, 50)
        dims = get_image_dimensions(b64, "image/gif")
        assert dims is not None
        assert dims.width_px == 100
        assert dims.height_px == 50

    def test_valid_gif87a(self) -> None:
        data = b"GIF87a" + struct.pack("<HH", 200, 100) + b"\x00\x00"
        b64 = base64.b64encode(data).decode("ascii")
        dims = get_image_dimensions(b64, "image/gif")
        assert dims is not None
        assert dims.width_px == 200
        assert dims.height_px == 100

    def test_invalid_gif_signature(self) -> None:
        data = b"GIF00a" + struct.pack("<HH", 100, 50) + b"\x00\x00"
        b64 = base64.b64encode(data).decode("ascii")
        dims = get_image_dimensions(b64, "image/gif")
        assert dims is None

    def test_too_short_gif(self) -> None:
        data = b"GIF89a"
        b64 = base64.b64encode(data).decode("ascii")
        dims = get_image_dimensions(b64, "image/gif")
        assert dims is None


# ---------------------------------------------------------------------------
# get_image_dimensions - unsupported MIME type
# ---------------------------------------------------------------------------


def test_unsupported_mime_type() -> None:
    b64 = base64.b64encode(b"data").decode("ascii")
    dims = get_image_dimensions(b64, "image/bmp")
    assert dims is None


# ---------------------------------------------------------------------------
# allocate_image_id
# ---------------------------------------------------------------------------


class TestAllocateImageId:
    def test_returns_positive_int(self) -> None:
        img_id = allocate_image_id()
        assert isinstance(img_id, int)
        assert img_id >= 1

    def test_within_range(self) -> None:
        for _ in range(100):
            img_id = allocate_image_id()
            assert 1 <= img_id <= 0xFFFFFFFF

    def test_ids_differ(self) -> None:
        ids = {allocate_image_id() for _ in range(50)}
        # With 32-bit random IDs, 50 samples should almost certainly all differ
        assert len(ids) == 50


# ---------------------------------------------------------------------------
# calculate_image_rows
# ---------------------------------------------------------------------------


class TestCalculateImageRows:
    def test_basic_calculation(self) -> None:
        dims = ImageDimensions(width_px=180, height_px=180)
        cell = CellDimensions(width_px=9, height_px=18)
        rows = calculate_image_rows(dims, target_width_cells=20, cell_dims=cell)
        # 20 cells * 9px = 180px target width, scale=1.0, 180/18 = 10 rows
        assert rows == 10

    def test_scaling_down(self) -> None:
        dims = ImageDimensions(width_px=360, height_px=360)
        cell = CellDimensions(width_px=9, height_px=18)
        rows = calculate_image_rows(dims, target_width_cells=20, cell_dims=cell)
        # target_width_px=180, scale=0.5, height=180, 180/18=10
        assert rows == 10

    def test_minimum_one_row(self) -> None:
        dims = ImageDimensions(width_px=1000, height_px=1)
        cell = CellDimensions(width_px=9, height_px=18)
        rows = calculate_image_rows(dims, target_width_cells=10, cell_dims=cell)
        assert rows >= 1

    def test_defaults_cell_dims(self) -> None:
        dims = ImageDimensions(width_px=90, height_px=36)
        rows = calculate_image_rows(dims, target_width_cells=10)
        # default cell: 9x18, target_width=90px, scale=1.0, 36/18=2
        assert rows == 2

    def test_fractional_rows_rounded_up(self) -> None:
        dims = ImageDimensions(width_px=90, height_px=37)
        cell = CellDimensions(width_px=9, height_px=18)
        rows = calculate_image_rows(dims, target_width_cells=10, cell_dims=cell)
        # scale=1.0, 37/18=2.055 -> ceil -> 3
        assert rows == 3


# ---------------------------------------------------------------------------
# is_image_line
# ---------------------------------------------------------------------------


class TestIsImageLine:
    def test_kitty_at_start(self) -> None:
        assert is_image_line("\x1b_Ga=T,f=100;data\x1b\\") is True

    def test_iterm2_at_start(self) -> None:
        assert is_image_line("\x1b]1337;File=inline=1:data\x07") is True

    def test_kitty_embedded(self) -> None:
        # Multi-row images may have cursor-up sequences before the image escape
        assert is_image_line("\x1b[1A\x1b_Gm=0;data\x1b\\") is True

    def test_iterm2_embedded(self) -> None:
        assert is_image_line("prefix\x1b]1337;File=inline=1:data\x07") is True

    def test_plain_text(self) -> None:
        assert is_image_line("Hello, world!") is False

    def test_empty_string(self) -> None:
        assert is_image_line("") is False

    def test_partial_kitty_prefix(self) -> None:
        assert is_image_line("\x1b_") is False

    def test_partial_iterm2_prefix(self) -> None:
        assert is_image_line("\x1b]1337") is False
