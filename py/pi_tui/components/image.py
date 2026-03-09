"""Image display component using terminal image protocols."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pi_tui.terminal_image import (
    ImageDimensions,
    ImageRenderOptions,
    get_capabilities,
    get_image_dimensions,
    image_fallback,
    render_image,
)


@dataclass
class ImageTheme:
    """Styling for image fallback text."""

    fallback_color: Callable[[str], str]


@dataclass
class ImageOptions:
    """Options controlling image rendering."""

    max_width_cells: int | None = None
    max_height_cells: int | None = None
    filename: str | None = None
    image_id: int | None = None


class Image:
    """Renders an image using Kitty or iTerm2 protocols, with fallback text."""

    def __init__(
        self,
        base64_data: str,
        mime_type: str,
        theme: ImageTheme,
        options: ImageOptions | None = None,
        dimensions: ImageDimensions | None = None,
    ) -> None:
        opts = options or ImageOptions()
        self._base64_data = base64_data
        self._mime_type = mime_type
        self._theme = theme
        self._options = opts
        self._dimensions = (
            dimensions or get_image_dimensions(base64_data, mime_type) or ImageDimensions(width_px=800, height_px=600)
        )
        self._image_id = opts.image_id

        # Render cache
        self._cached_lines: list[str] | None = None
        self._cached_width: int | None = None

    def get_image_id(self) -> int | None:
        return self._image_id

    def invalidate(self) -> None:
        self._cached_lines = None
        self._cached_width = None

    def render(self, width: int) -> list[str]:
        if self._cached_lines is not None and self._cached_width == width:
            return self._cached_lines

        max_width = min(width - 2, self._options.max_width_cells or 60)
        caps = get_capabilities()
        lines: list[str]

        if caps.images is not None:
            result = render_image(
                self._base64_data,
                self._dimensions,
                ImageRenderOptions(
                    max_width_cells=max_width,
                    image_id=self._image_id,
                ),
            )

            if result is not None:
                if result.image_id is not None:
                    self._image_id = result.image_id

                lines = []
                for _ in range(result.rows - 1):
                    lines.append("")
                move_up = f"\x1b[{result.rows - 1}A" if result.rows > 1 else ""
                lines.append(move_up + result.sequence)
            else:
                fb = image_fallback(self._mime_type, self._dimensions, self._options.filename)
                lines = [self._theme.fallback_color(fb)]
        else:
            fb = image_fallback(self._mime_type, self._dimensions, self._options.filename)
            lines = [self._theme.fallback_color(fb)]

        self._cached_lines = lines
        self._cached_width = width
        return lines
