"""Tests for pi_coding_agent.cli.file_processor."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from pi_coding_agent.cli.file_processor import (
    ProcessedFiles,
    ProcessFileOptions,
    process_file_arguments,
)


@pytest.mark.asyncio
async def test_empty_file_args() -> None:
    result = await process_file_arguments([])
    assert result.text == ""
    assert result.images == []


@pytest.mark.asyncio
async def test_text_file(tmp_path: Path) -> None:
    content = "Hello, world!\nLine 2"
    f = tmp_path / "test.txt"
    f.write_text(content, encoding="utf-8")

    result = await process_file_arguments([str(f)])
    assert f'<file name="{f}">' in result.text
    assert content in result.text
    assert "</file>" in result.text
    assert result.images == []


@pytest.mark.asyncio
async def test_image_file_png(tmp_path: Path) -> None:
    # Minimal 1x1 PNG (89 bytes)
    png_data = (
        b"\x89PNG\r\n\x1a\n"  # signature
        b"\x00\x00\x00\rIHDR"  # IHDR chunk length + type
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"  # 1x1 RGB
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img = tmp_path / "test.png"
    img.write_bytes(png_data)

    result = await process_file_arguments([str(img)])
    assert len(result.images) == 1
    assert result.images[0]["type"] == "image"
    assert result.images[0]["mime_type"] == "image/png"
    # Verify base64 content is valid
    decoded = base64.b64decode(result.images[0]["data"])
    assert decoded == png_data
    # Text references the file
    assert f'<file name="{img}">' in result.text


@pytest.mark.asyncio
async def test_skip_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")

    result = await process_file_arguments([str(empty)])
    assert result.text == ""
    assert result.images == []


@pytest.mark.asyncio
async def test_multiple_files(tmp_path: Path) -> None:
    f1 = tmp_path / "a.txt"
    f1.write_text("File A", encoding="utf-8")
    f2 = tmp_path / "b.txt"
    f2.write_text("File B", encoding="utf-8")

    result = await process_file_arguments([str(f1), str(f2)])
    assert "File A" in result.text
    assert "File B" in result.text


@pytest.mark.asyncio
async def test_missing_file_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        await process_file_arguments([str(tmp_path / "nonexistent.txt")])
    assert exc_info.value.code == 1


def test_processed_files_defaults() -> None:
    pf = ProcessedFiles(text="", images=[])
    assert pf.text == ""
    assert pf.images == []


def test_process_file_options_defaults() -> None:
    opts = ProcessFileOptions()
    assert opts.auto_resize_images is True
