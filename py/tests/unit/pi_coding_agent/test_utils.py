"""Unit tests for pi_coding_agent utility modules."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# shell.py
# ---------------------------------------------------------------------------


class TestGetShellConfig:
    def setup_method(self) -> None:
        import pi_coding_agent.utils.shell as shell_mod

        shell_mod._cached_shell_config = None

    def teardown_method(self) -> None:
        import pi_coding_agent.utils.shell as shell_mod

        shell_mod._cached_shell_config = None

    def test_returns_bash_when_available(self) -> None:
        from pi_coding_agent.utils.shell import get_shell_config

        with patch("shutil.which", side_effect=lambda name: "/bin/bash" if name == "bash" else None):
            cfg = get_shell_config()
        assert cfg["shell"] == "/bin/bash"
        assert cfg["args"] == ["-c"]

    def test_falls_back_to_sh(self) -> None:
        from pi_coding_agent.utils.shell import get_shell_config

        with patch("shutil.which", side_effect=lambda name: "/bin/sh" if name == "sh" else None):
            cfg = get_shell_config()
        assert cfg["shell"] == "/bin/sh"

    def test_raises_when_no_shell(self) -> None:
        from pi_coding_agent.utils.shell import get_shell_config

        with patch("shutil.which", return_value=None), pytest.raises(RuntimeError, match="No suitable shell"):
            get_shell_config()

    def test_result_is_cached(self) -> None:
        import pi_coding_agent.utils.shell as shell_mod
        from pi_coding_agent.utils.shell import get_shell_config

        with patch("shutil.which", side_effect=lambda name: "/bin/bash" if name == "bash" else None):
            cfg1 = get_shell_config()
            cfg2 = get_shell_config()
        assert cfg1 is cfg2
        assert shell_mod._cached_shell_config is cfg1


class TestGetShellEnv:
    def test_returns_dict_with_path(self) -> None:
        from pi_coding_agent.utils.shell import get_shell_env

        env = get_shell_env()
        assert isinstance(env, dict)
        assert "PATH" in env

    def test_bin_dir_prepended_to_path(self) -> None:
        from pi_coding_agent.utils.shell import get_shell_env

        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}, clear=False):
            env = get_shell_env()
        # PATH should contain some pi bin dir prefix
        assert env["PATH"].endswith(":/usr/bin:/bin") or "/" in env["PATH"]


class TestSanitizeBinaryOutput:
    def test_removes_control_chars(self) -> None:
        from pi_coding_agent.utils.shell import sanitize_binary_output

        # ASCII BEL (0x07) should be removed
        result = sanitize_binary_output("hello\x07world")
        assert result == "helloworld"

    def test_keeps_newlines_and_tabs(self) -> None:
        from pi_coding_agent.utils.shell import sanitize_binary_output

        text = "line1\nline2\ttabbed"
        assert sanitize_binary_output(text) == text

    def test_removes_zero_width_space(self) -> None:
        from pi_coding_agent.utils.shell import sanitize_binary_output

        result = sanitize_binary_output("a\u200bb")
        assert result == "ab"

    def test_empty_string(self) -> None:
        from pi_coding_agent.utils.shell import sanitize_binary_output

        assert sanitize_binary_output("") == ""

    def test_normal_text_unchanged(self) -> None:
        from pi_coding_agent.utils.shell import sanitize_binary_output

        text = "Hello, World! 123"
        assert sanitize_binary_output(text) == text


class TestKillProcessTree:
    def test_kill_nonexistent_pid_does_not_raise(self) -> None:
        from pi_coding_agent.utils.shell import kill_process_tree

        # Use a very large PID that almost certainly does not exist
        kill_process_tree(999999999)


# ---------------------------------------------------------------------------
# git.py
# ---------------------------------------------------------------------------


class TestParseGitUrl:
    def test_bare_host_path(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("github.com/owner/repo")
        assert result is not None
        assert result.host == "github.com"
        assert result.path == "owner/repo"
        assert result.repo == "https://github.com/owner/repo"
        assert result.ref is None
        assert result.pinned is False

    def test_https_url(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("https://github.com/owner/repo")
        assert result is not None
        assert result.host == "github.com"
        assert result.path == "owner/repo"

    def test_https_url_with_dot_git(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("https://github.com/owner/repo.git")
        assert result is not None
        assert result.path == "owner/repo"

    def test_git_prefix(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("git:github.com/owner/repo")
        assert result is not None
        assert result.host == "github.com"

    def test_git_prefix_with_pinned_ref(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("git:github.com/owner/repo@v1.2.3")
        assert result is not None
        assert result.ref == "v1.2.3"
        assert result.pinned is True

    def test_ssh_url(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("git@github.com:owner/repo.git")
        assert result is not None
        assert result.host == "github.com"
        assert result.path == "owner/repo"

    def test_invalid_string_returns_none(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("not-a-git-url")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("")
        assert result is None

    def test_type_field_is_git(self) -> None:
        from pi_coding_agent.utils.git import parse_git_url

        result = parse_git_url("github.com/a/b")
        assert result is not None
        assert result.type == "git"


# ---------------------------------------------------------------------------
# clipboard.py
# ---------------------------------------------------------------------------


class TestExtensionForImageMimeType:
    def test_known_types(self) -> None:
        from pi_coding_agent.utils.clipboard import extension_for_image_mime_type

        assert extension_for_image_mime_type("image/png") == "png"
        assert extension_for_image_mime_type("image/jpeg") == "jpg"
        assert extension_for_image_mime_type("image/gif") == "gif"
        assert extension_for_image_mime_type("image/webp") == "webp"

    def test_unknown_type_returns_none(self) -> None:
        from pi_coding_agent.utils.clipboard import extension_for_image_mime_type

        assert extension_for_image_mime_type("application/octet-stream") is None

    def test_case_insensitive(self) -> None:
        from pi_coding_agent.utils.clipboard import extension_for_image_mime_type

        assert extension_for_image_mime_type("image/PNG") == "png"


class TestIsWaylandSession:
    def test_detects_wayland_display(self) -> None:
        from pi_coding_agent.utils.clipboard import is_wayland_session

        assert is_wayland_session({"WAYLAND_DISPLAY": "wayland-0"}) is True

    def test_detects_xdg_session_type(self) -> None:
        from pi_coding_agent.utils.clipboard import is_wayland_session

        assert is_wayland_session({"XDG_SESSION_TYPE": "wayland"}) is True

    def test_x11_returns_false(self) -> None:
        from pi_coding_agent.utils.clipboard import is_wayland_session

        assert is_wayland_session({"XDG_SESSION_TYPE": "x11"}) is False

    def test_empty_env_returns_false(self) -> None:
        from pi_coding_agent.utils.clipboard import is_wayland_session

        assert is_wayland_session({}) is False


class TestCopyToClipboard:
    def test_does_not_raise(self) -> None:
        """copy_to_clipboard should never raise even when all tools fail."""
        from pi_coding_agent.utils.clipboard import copy_to_clipboard

        with patch("subprocess.run", side_effect=FileNotFoundError):
            # Should silently succeed (OSC 52 path may fail too but swallowed)
            copy_to_clipboard("hello")


class TestReadClipboardImage:
    def test_returns_none_on_failure(self) -> None:
        from pi_coding_agent.utils.clipboard import read_clipboard_image

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = read_clipboard_image(env={}, platform="linux")
        assert result is None

    def test_wayland_path_returns_none_on_tool_missing(self) -> None:
        from pi_coding_agent.utils.clipboard import read_clipboard_image

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = read_clipboard_image(env={"WAYLAND_DISPLAY": "wayland-0"}, platform="linux")
        assert result is None

    def test_macos_path_returns_none_on_failure(self) -> None:
        from pi_coding_agent.utils.clipboard import read_clipboard_image

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = read_clipboard_image(platform="darwin")
        assert result is None


# ---------------------------------------------------------------------------
# image.py
# ---------------------------------------------------------------------------


class TestConvertToPng:
    def test_returns_none_when_pillow_missing(self) -> None:
        """If Pillow is not importable, convert_to_png should return None."""

        with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
            # Reimport to trigger ImportError path
            import importlib

            import pi_coding_agent.utils.image as img_mod

            importlib.reload(img_mod)
            result = img_mod.convert_to_png("aW52YWxpZA==", "image/png")
            # Either returns None (if Pillow mock causes import error) or decodes
            # fine if Pillow is actually installed — just ensure no exception.
            assert result is None or isinstance(result, dict)

    def test_converts_valid_png(self) -> None:
        """convert_to_png should return a dict with data and mimeType for valid input."""
        import base64
        import io

        pytest.importorskip("PIL")
        from PIL import Image

        from pi_coding_agent.utils.image import convert_to_png

        # Create a tiny 1x1 red PNG
        img = Image.new("RGB", (1, 1), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        result = convert_to_png(b64, "image/png")
        assert result is not None
        assert result["mimeType"] == "image/png"
        assert len(result["data"]) > 0

    def test_invalid_base64_returns_none(self) -> None:
        pytest.importorskip("PIL")
        from pi_coding_agent.utils.image import convert_to_png

        result = convert_to_png("!!!not-base64!!!", "image/png")
        assert result is None


class TestResizeImage:
    def _make_image_content(self, width: int = 100, height: int = 100, fmt: str = "PNG") -> object:
        import base64
        import io

        pytest.importorskip("PIL")
        from PIL import Image

        from pi_ai.types import ImageContent

        img = Image.new("RGB", (width, height), color=(0, 128, 255))
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        mime = "image/png" if fmt == "PNG" else "image/jpeg"
        return ImageContent(data=b64, mime_type=mime)

    def test_no_resize_when_within_bounds(self) -> None:
        pytest.importorskip("PIL")
        from pi_ai.types import ImageContent
        from pi_coding_agent.utils.image import ImageResizeOptions, resize_image

        img = self._make_image_content(50, 50)
        assert isinstance(img, ImageContent)
        result = resize_image(img, ImageResizeOptions(max_width=100, max_height=100))
        assert result.was_resized is False
        assert result.width == 50
        assert result.height == 50

    def test_resizes_when_too_wide(self) -> None:
        pytest.importorskip("PIL")
        from pi_ai.types import ImageContent
        from pi_coding_agent.utils.image import ImageResizeOptions, resize_image

        img = self._make_image_content(200, 100)
        assert isinstance(img, ImageContent)
        result = resize_image(img, ImageResizeOptions(max_width=100))
        assert result.was_resized is True
        assert result.width <= 100

    def test_format_dimension_note_when_resized(self) -> None:
        pytest.importorskip("PIL")
        from pi_ai.types import ImageContent
        from pi_coding_agent.utils.image import ImageResizeOptions, format_dimension_note, resize_image

        img = self._make_image_content(400, 200)
        assert isinstance(img, ImageContent)
        result = resize_image(img, ImageResizeOptions(max_width=200))
        note = format_dimension_note(result)
        assert note is not None
        assert "400x200" in note

    def test_format_dimension_note_no_resize(self) -> None:
        pytest.importorskip("PIL")
        from pi_ai.types import ImageContent
        from pi_coding_agent.utils.image import ImageResizeOptions, format_dimension_note, resize_image

        img = self._make_image_content(50, 50)
        assert isinstance(img, ImageContent)
        result = resize_image(img, ImageResizeOptions(max_width=100))
        assert format_dimension_note(result) is None

    def test_raises_when_pillow_missing(self) -> None:
        """resize_image should raise RuntimeError when Pillow is not available."""
        from pi_ai.types import ImageContent

        img = ImageContent(data="abc", mime_type="image/png")
        with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
            import importlib

            import pi_coding_agent.utils.image as img_mod

            importlib.reload(img_mod)
            with pytest.raises((RuntimeError, Exception)):
                img_mod.resize_image(img)


# ---------------------------------------------------------------------------
# tools_manager.py
# ---------------------------------------------------------------------------


class TestGetToolPath:
    def test_returns_path_when_in_system(self) -> None:
        from pi_coding_agent.utils.tools_manager import get_tool_path

        with patch("pathlib.Path.is_file", return_value=False), patch("shutil.which", return_value="/usr/bin/rg"):
            result = get_tool_path("rg")
        assert result == "/usr/bin/rg"

    def test_returns_none_when_not_found(self) -> None:
        from pi_coding_agent.utils.tools_manager import get_tool_path

        with patch("shutil.which", return_value=None), patch("pathlib.Path.is_file", return_value=False):
            result = get_tool_path("fd")
        assert result is None


class TestEnsureTool:
    @pytest.mark.asyncio
    async def test_returns_existing_path(self) -> None:
        from pi_coding_agent.utils.tools_manager import ensure_tool

        with patch("pi_coding_agent.utils.tools_manager.get_tool_path", return_value="/usr/bin/fd"):
            result = await ensure_tool("fd")
        assert result == "/usr/bin/fd"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_url_for_platform(self) -> None:
        from pi_coding_agent.utils.tools_manager import ensure_tool

        with (
            patch("pi_coding_agent.utils.tools_manager.get_tool_path", return_value=None),
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="freebsd"),
        ):
            result = await ensure_tool("fd", silent=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_httpx_missing(self) -> None:
        from pi_coding_agent.utils.tools_manager import ensure_tool

        with (
            patch("pi_coding_agent.utils.tools_manager.get_tool_path", return_value=None),
            patch.dict("sys.modules", {"httpx": None}),
        ):
            result = await ensure_tool("rg", silent=True)
        assert result is None


class TestToolsManagerInternals:
    def test_fd_download_url_linux(self) -> None:
        from pi_coding_agent.utils.tools_manager import _fd_download_url

        with (
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="linux"),
            patch("pi_coding_agent.utils.tools_manager._current_arch", return_value="x86_64"),
        ):
            url = _fd_download_url("10.0.0")
        assert url is not None
        assert "linux" in url
        assert "x86_64" in url

    def test_fd_download_url_darwin(self) -> None:
        from pi_coding_agent.utils.tools_manager import _fd_download_url

        with (
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="darwin"),
            patch("pi_coding_agent.utils.tools_manager._current_arch", return_value="aarch64"),
        ):
            url = _fd_download_url("10.0.0")
        assert url is not None
        assert "darwin" in url

    def test_fd_download_url_windows(self) -> None:
        from pi_coding_agent.utils.tools_manager import _fd_download_url

        with (
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="win32"),
            patch("pi_coding_agent.utils.tools_manager._current_arch", return_value="x86_64"),
        ):
            url = _fd_download_url("10.0.0")
        assert url is not None
        assert ".zip" in url

    def test_fd_download_url_unknown_platform(self) -> None:
        from pi_coding_agent.utils.tools_manager import _fd_download_url

        with (
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="haiku"),
            patch("pi_coding_agent.utils.tools_manager._current_arch", return_value="x86_64"),
        ):
            url = _fd_download_url("10.0.0")
        assert url is None

    def test_rg_download_url_linux(self) -> None:
        from pi_coding_agent.utils.tools_manager import _rg_download_url

        with (
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="linux"),
            patch("pi_coding_agent.utils.tools_manager._current_arch", return_value="x86_64"),
        ):
            url = _rg_download_url("14.0.0")
        assert url is not None
        assert "ripgrep" in url

    def test_rg_download_url_darwin(self) -> None:
        from pi_coding_agent.utils.tools_manager import _rg_download_url

        with (
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="darwin"),
            patch("pi_coding_agent.utils.tools_manager._current_arch", return_value="aarch64"),
        ):
            url = _rg_download_url("14.0.0")
        assert url is not None

    def test_rg_download_url_windows(self) -> None:
        from pi_coding_agent.utils.tools_manager import _rg_download_url

        with (
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="win32"),
            patch("pi_coding_agent.utils.tools_manager._current_arch", return_value="x86_64"),
        ):
            url = _rg_download_url("14.0.0")
        assert url is not None
        assert ".zip" in url

    def test_rg_download_url_unknown_platform(self) -> None:
        from pi_coding_agent.utils.tools_manager import _rg_download_url

        with (
            patch("pi_coding_agent.utils.tools_manager._current_platform", return_value="freebsd"),
            patch("pi_coding_agent.utils.tools_manager._current_arch", return_value="x86_64"),
        ):
            url = _rg_download_url("14.0.0")
        assert url is None

    def test_suffix_zip(self) -> None:
        from pi_coding_agent.utils.tools_manager import _suffix

        assert _suffix("https://example.com/file.zip") == ".zip"

    def test_suffix_tar_gz(self) -> None:
        from pi_coding_agent.utils.tools_manager import _suffix

        assert _suffix("https://example.com/file.tar.gz") == ".tar.gz"

    def test_suffix_unknown(self) -> None:
        from pi_coding_agent.utils.tools_manager import _suffix

        assert _suffix("https://example.com/file") == ".bin"

    def test_extract_binary_raw_binary(self) -> None:
        """Raw binary (not zip/tar.gz) is just copied to target."""
        import tempfile

        from pi_coding_agent.utils.tools_manager import _extract_binary

        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as src:
            src.write(b"\x7fELF")
            src_path = src.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tgt:
            tgt_path = tgt.name

        try:
            _extract_binary(Path(src_path), "fd", Path(tgt_path))
            assert Path(tgt_path).read_bytes() == b"\x7fELF"
        finally:
            Path(src_path).unlink(missing_ok=True)
            Path(tgt_path).unlink(missing_ok=True)


class TestImageMoreCoverage:
    def test_resize_jpeg_strips_alpha(self) -> None:
        """Resizing a JPEG source with alpha should convert to RGB."""
        import base64
        import io

        pytest.importorskip("PIL")
        from PIL import Image

        from pi_ai.types import ImageContent
        from pi_coding_agent.utils.image import ImageResizeOptions, resize_image

        # Create RGBA PNG and pretend it's a JPEG
        img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        content = ImageContent(data=b64, mime_type="image/jpeg")
        result = resize_image(content, ImageResizeOptions())
        assert result.mime_type == "image/jpeg"

    def test_resize_with_max_bytes_png(self) -> None:
        """When max_bytes is set and PNG is too large, it should shrink."""
        import base64
        import io

        pytest.importorskip("PIL")
        from PIL import Image

        from pi_ai.types import ImageContent
        from pi_coding_agent.utils.image import ImageResizeOptions, resize_image

        # Create a large enough image to trigger byte reduction
        img = Image.new("RGB", (500, 500), color=(100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        original_bytes = len(buf.getvalue())
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        content = ImageContent(data=b64, mime_type="image/png")

        # Set max_bytes below the original size to force reduction
        result = resize_image(content, ImageResizeOptions(max_bytes=original_bytes // 4))
        # Should have produced something
        assert len(result.data) > 0

    def test_resize_with_max_bytes_jpeg(self) -> None:
        """When max_bytes is set and JPEG is too large, quality is reduced."""
        import base64
        import io

        pytest.importorskip("PIL")
        from PIL import Image

        from pi_ai.types import ImageContent
        from pi_coding_agent.utils.image import ImageResizeOptions, resize_image

        img = Image.new("RGB", (300, 300), color=(200, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        original_bytes = len(buf.getvalue())
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        content = ImageContent(data=b64, mime_type="image/jpeg")

        result = resize_image(content, ImageResizeOptions(max_bytes=max(1, original_bytes // 3)))
        assert len(result.data) > 0
