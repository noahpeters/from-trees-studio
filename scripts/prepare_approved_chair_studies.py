"""Remove only the exterior paper from approved full-perspective studies."""

from pathlib import Path
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public" / "chairs" / "approved"


def remove_exterior_paper(path: Path) -> None:
    image = Image.open(path).convert("RGB")
    flooded = image.copy()
    marker = (255, 0, 255)
    width, height = flooded.size
    for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        ImageDraw.floodfill(flooded, point, marker, thresh=23)
    alpha = Image.new("L", image.size, 255)
    source_pixels = flooded.load()
    alpha_pixels = alpha.load()
    for y in range(height):
        for x in range(width):
            if source_pixels[x, y] == marker:
                alpha_pixels[x, y] = 0
    result = image.convert("RGBA")
    result.putalpha(alpha)
    result.save(path.with_suffix(".webp"), "WEBP", lossless=True)


if __name__ == "__main__":
    for source in SOURCE.rglob("*.png"):
        remove_exterior_paper(source)
