"""Prepare high-fidelity generated furniture masters as true-alpha sprites."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public" / "style-v2" / "source"
MASTERS = ROOT / "public" / "style-v2" / "chairs" / "masters"
TABLE_MASTERS = ROOT / "public" / "style-v2" / "tables" / "masters"


def border_connected_background(image: Image.Image) -> Image.Image:
    """Remove near-white pixels connected to the border, preserving pale wood."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def is_background(x: int, y: int) -> bool:
        red, green, blue = pixels[x, y]
        # Generated backgrounds are neutral and very bright. Warm wood pixels
        # are intentionally excluded even when their luminance is high.
        return min(red, green, blue) >= 238 and max(red, green, blue) - min(red, green, blue) <= 12

    for x in range(width):
        for y in (0, height - 1):
            if is_background(x, y):
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if is_background(x, y):
                queue.append((x, y))

    background = Image.new("L", rgb.size)
    mask = background.load()
    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if visited[index] or not is_background(x, y):
            continue
        visited[index] = 1
        mask[x, y] = 255
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                queue.append((nx, ny))

    # Feather only the extraction boundary; do not blur the furniture art.
    background = background.filter(ImageFilter.GaussianBlur(0.7))
    alpha = ImageOps.invert(background)
    result = rgb.convert("RGBA")
    result.putalpha(alpha)
    bbox = alpha.getbbox()
    if bbox:
        result = result.crop(bbox)
    padded = Image.new("RGBA", (result.width + 24, result.height + 24))
    padded.alpha_composite(result, (12, 12))
    return padded


def neutral_background_to_alpha(image: Image.Image) -> Image.Image:
    """Remove generated neutral background even inside enclosed furniture gaps.

    Border flood-fill is insufficient for chair openings bounded by the back,
    seat, legs, or stretchers.  These masters use a warm wood palette, so a
    bright, nearly neutral pixel is background rather than furniture.
    """
    rgb = image.convert("RGB")
    background = Image.new("L", rgb.size, 0)
    rgb_pixels = rgb.load()
    background_pixels = background.load()
    visited = bytearray(rgb.width * rgb.height)

    def is_neutral_background(x: int, y: int) -> bool:
        red, green, blue = rgb_pixels[x, y]
        return min(red, green, blue) >= 232 and max(red, green, blue) - min(red, green, blue) <= 14

    for y in range(rgb.height):
        for x in range(rgb.width):
            start = y * rgb.width + x
            if visited[start] or not is_neutral_background(x, y):
                continue
            visited[start] = 1
            queue = deque([(x, y)])
            component: list[tuple[int, int]] = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or nx >= rgb.width or ny < 0 or ny >= rgb.height:
                        continue
                    index = ny * rgb.width + nx
                    if visited[index] or not is_neutral_background(nx, ny):
                        continue
                    visited[index] = 1
                    queue.append((nx, ny))
            # Enclosed checkerboard/background fields are large continuous
            # regions. Small neutral highlights are part of the wood drawing.
            if len(component) >= 3_000:
                for px, py in component:
                    background_pixels[px, py] = 255

    background = background.filter(ImageFilter.GaussianBlur(0.45))
    alpha = ImageOps.invert(background)
    if "A" in image.getbands():
        # Keep every transparent opening already present in the approved art,
        # then additionally remove enclosed neutral fields that the original
        # border-only extraction could not reach.
        alpha = ImageChops.multiply(alpha, image.getchannel("A"))
    result = rgb.convert("RGBA")
    result.putalpha(alpha)
    bbox = alpha.getbbox()
    return result.crop(bbox) if bbox else result


def main() -> None:
    MASTERS.mkdir(parents=True, exist_ok=True)
    TABLE_MASTERS.mkdir(parents=True, exist_ok=True)
    for source in sorted(SOURCE.glob("*.png")):
        prepared = border_connected_background(Image.open(source))
        target = TABLE_MASTERS if source.name.startswith("table-") else MASTERS
        prepared.save(target / source.name, "PNG", optimize=True)

    # Table strips are built separately by build_chair_layers.py because each
    # edge profile now has genuinely different hand-drawn tabletop artwork.


if __name__ == "__main__":
    main()
