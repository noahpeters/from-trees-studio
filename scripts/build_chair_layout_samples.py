"""Create a review-only sheet for the proposed 6/8/10-chair layouts."""

from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
CELL = 600
PANEL = (250, 250, 250, 255)
FAMILIES = ("curved-back", "ladder-back", "spindle-back")
VIEWS = ("front", "rear", "side")


def transparent_cell(source: Image.Image, column: int, row: int) -> Image.Image:
    left = round(column * source.width / 3)
    top = round(row * source.height / 3)
    right = round((column + 1) * source.width / 3)
    bottom = round((row + 1) * source.height / 3)
    inset = 26
    crop = source.crop((left + inset, top + inset, right - inset, bottom - inset)).convert("RGB")
    background = Image.new("RGB", crop.size, (252, 246, 235))
    difference = ImageChops.difference(crop, background)
    red, green, blue = difference.split()
    alpha = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    alpha = alpha.point(lambda value: 0 if value < 9 else min(255, (value - 9) * 8))
    alpha = alpha.point(lambda value: 0 if value < 108 else value)
    result = crop.convert("RGBA")
    result.putalpha(alpha)
    bbox = alpha.getbbox()
    return result.crop(bbox) if bbox else result


def resized(source: Image.Image, height: int, mirror: bool = False) -> Image.Image:
    ratio = height / source.height
    chair = source.resize((round(source.width * ratio), height), Image.Resampling.LANCZOS)
    if mirror:
        chair = ImageOps.mirror(chair)
    return ImageEnhance.Contrast(chair).enhance(0.95)


def paste_center(canvas: Image.Image, chair: Image.Image, x: int, bottom: int) -> None:
    canvas.alpha_composite(chair, (round(x - chair.width / 2), bottom - chair.height))


def make_sample(cutouts: dict[tuple[str, str], Image.Image], row: int, family: str) -> Image.Image:
    count = (6, 8, 10)[row]
    per_side = (count - 2) // 2
    spread = (210, 330, 430)[row]
    xs = [300 - spread / 2 + index * spread / (per_side - 1) for index in range(per_side)]
    back = Image.new("RGBA", (CELL, CELL))
    front = Image.new("RGBA", (CELL, CELL))
    for index, x in enumerate(xs):
        paste_center(back, resized(cutouts[(family, "front")], 154, index % 2 == 1), round(x), 330)
        paste_center(front, resized(cutouts[(family, "rear")], 180, index % 2 == 0), round(x), 535)
    # Left end faces right; right end faces left.
    paste_center(front, resized(cutouts[(family, "side")], 155, True), 65, 430)
    paste_center(front, resized(cutouts[(family, "side")], 155, False), 535, 430)

    table_sheet = Image.open(PUBLIC / "renders-transparent" / "rectangle" / "curved-slab-frame.webp").convert("RGBA")
    table = table_sheet.crop((0, row * CELL, CELL, (row + 1) * CELL))
    # Opaque tabletop plane, colored exactly like the panel, prevents far-side
    # chair lines from showing through while the rest remains transparent.
    masks = (
        [(61, 182), (389, 131), (538, 177), (205, 251)],
        [(39, 180), (401, 128), (546, 177), (185, 253)],
        [(20, 180), (412, 125), (556, 176), (165, 255)],
    )
    tabletop = Image.new("RGBA", (CELL, CELL))
    ImageDraw.Draw(tabletop).polygon(masks[row], fill=PANEL)

    result = Image.new("RGBA", (CELL, CELL), PANEL)
    result.alpha_composite(back)
    result.alpha_composite(tabletop)
    result.alpha_composite(table)
    result.alpha_composite(front)
    return result


if __name__ == "__main__":
    source = Image.open(PUBLIC / "chairs" / "chair-views.png")
    cutouts = {
        (family, view): transparent_cell(source, column, row)
        for column, family in enumerate(FAMILIES)
        for row, view in enumerate(VIEWS)
    }
    review = Image.new("RGBA", (CELL * 3, CELL), PANEL)
    for row in range(3):
        review.alpha_composite(make_sample(cutouts, row, "spindle-back"), (row * CELL, 0))
    review.convert("RGB").save(PUBLIC / "chairs" / "layout-samples.jpg", quality=94)
