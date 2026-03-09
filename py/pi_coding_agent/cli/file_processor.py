"""Process @file CLI arguments into text content and image attachments.

Python port of packages/coding-agent/src/cli/file-processor.ts.
"""

from __future__ import annotations

import base64
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Image extensions recognized as image files
_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})

# MIME type map by extension
_EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _detect_image_mime_type(path: Path) -> str | None:
    """Return the MIME type for an image file, or None if not a recognized image."""
    return _EXT_TO_MIME.get(path.suffix.lower())


@dataclass
class ProcessedFiles:
    """Result from processing @file arguments."""

    text: str
    images: list[Any] = field(default_factory=list)


@dataclass
class ProcessFileOptions:
    """Options for processing @file arguments."""

    # Whether to auto-resize images. Currently a no-op in Python (no resize lib).
    auto_resize_images: bool = True


async def process_file_arguments(
    file_args: list[str],
    options: ProcessFileOptions | None = None,
) -> ProcessedFiles:
    """Process @file arguments into text content and image attachments.

    For each file argument:
    - If it is a recognized image format: base64-encode and add to images list.
    - Otherwise: read as text and wrap in <file> tags.

    Exits with sys.exit(1) on error (file not found, read error).

    Args:
        file_args: List of file paths (without the leading '@').
        options: Processing options.

    Returns:
        ProcessedFiles with text and images.
    """
    if options is None:
        options = ProcessFileOptions()

    text = ""
    images: list[Any] = []

    for file_arg in file_args:
        # Expand tilde and resolve path
        absolute_path = Path(file_arg).expanduser().resolve()

        if not absolute_path.exists():
            print(f"Error: File not found: {absolute_path}", file=sys.stderr)
            raise SystemExit(1)

        # Skip empty files
        if absolute_path.stat().st_size == 0:
            continue

        mime_type = _detect_image_mime_type(absolute_path)

        if mime_type is not None:
            # Handle image file
            raw_bytes = absolute_path.read_bytes()
            base64_content = base64.b64encode(raw_bytes).decode("ascii")

            # Image resize is a no-op in Python (skip resize)
            attachment: dict[str, str] = {
                "type": "image",
                "mime_type": mime_type,
                "data": base64_content,
            }
            images.append(attachment)

            # Add text reference to image
            text += f'<file name="{absolute_path}"></file>\n'
        else:
            # Handle text file
            try:
                content = absolute_path.read_text(encoding="utf-8")
                text += f'<file name="{absolute_path}">\n{content}\n</file>\n'
            except OSError as error:
                print(
                    f"Error: Could not read file {absolute_path}: {error}",
                    file=sys.stderr,
                )
                raise SystemExit(1) from None

    return ProcessedFiles(text=text, images=images)
