"""Build independent, perspective-correct table and chair layers."""

from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
TRANSPARENT = ROOT / "public" / "renders-transparent"
TRANSPARENT_MASTERS = ROOT / "public" / "renders-transparent-masters"
CHAIRS = ROOT / "public" / "chairs"
CELL = 600
FAMILIES = ("curved-back", "ladder-back", "spindle-back")
PERSPECTIVE_VIEWS = ("far-left", "far-right", "near-left", "near-right")


def crop_views():
    """Crop perspective-specific RGBA studies; never fake yaw with 2D shear."""
    source = Image.open(CHAIRS / "masters" / "chair-perspectives-transparent.png").convert("RGBA")
    ends = Image.open(CHAIRS / "masters" / "chair-ends-transparent.png").convert("RGBA")
    views = {}
    target = CHAIRS / "position-views"
    target.mkdir(parents=True, exist_ok=True)

    def take(sheet, column, row, columns, rows):
        cell_w, cell_h = sheet.width / columns, sheet.height / rows
        crop = sheet.crop((round(column * cell_w), round(row * cell_h),
                           round((column + 1) * cell_w), round((row + 1) * cell_h)))
        bbox = crop.getchannel("A").getbbox()
        return crop.crop(bbox) if bbox else crop

    for column, family in enumerate(FAMILIES):
        for row, view in enumerate(PERSPECTIVE_VIEWS):
            crop = take(source, column, row, 3, 6)
            crop.save(target / f"{family}-{view}.webp", "WEBP", lossless=True)
            views[(family, view)] = crop
        for row, view in enumerate(("end-left", "end-right")):
            crop = take(ends, column, row, 3, 2)
            crop.save(target / f"{family}-{view}.webp", "WEBP", lossless=True)
            views[(family, view)] = crop
    return views


def make_table_layers():
    """Normalize approved RGBA table masters without manufacturing an occlusion mask."""
    for source_path in TRANSPARENT_MASTERS.rglob("*.png"):
        target = (TRANSPARENT / source_path.relative_to(TRANSPARENT_MASTERS)).with_suffix(".webp")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = Image.open(source_path).convert("RGBA")
        columns = 3 if source_path.parent.name == "circle" else 4
        rows = 3
        cell_width = source.width // columns
        cell_height = source.height // rows
        result = Image.new("RGBA", (columns * CELL, rows * CELL))
        for row in range(rows):
            for column in range(columns):
                box = (column * cell_width, row * cell_height,
                       (column + 1) * cell_width, (row + 1) * cell_height)
                cutout = source.crop(box).resize((CELL, CELL), Image.Resampling.LANCZOS)
                result.alpha_composite(cutout, (column * CELL, row * CELL))
        result.save(target, "WEBP", lossless=True)


def transformed(source, height, width_factor=1.0, mirror=False, shear=0.0, rotation=0.0):
    ratio = height / source.height
    chair = source.resize((max(1, round(source.width * ratio * width_factor)), height), Image.Resampling.LANCZOS)
    if mirror:
        chair = ImageOps.mirror(chair)
    if shear:
        pad = abs(round(shear * height)) + 6
        chair = chair.transform((chair.width + pad, chair.height), Image.Transform.AFFINE,
                                (1, -shear, pad if shear > 0 else 0, 0, 1, 0),
                                Image.Resampling.BICUBIC)
    if rotation:
        chair = chair.rotate(rotation, Image.Resampling.BICUBIC, expand=True)
    return ImageEnhance.Contrast(chair).enhance(.96)


def place(canvas, source, x, bottom, **kwargs):
    chair = transformed(source, **kwargs)
    canvas.alpha_composite(chair, (round(x - chair.width / 2), round(bottom - chair.height)))


def positions(shape, row):
    count = (6, 8, 10)[row]
    per_side = (count - 2) // 2
    if shape == "circle":
        far_span, near_span = (170, 205, 230)[row], (205, 245, 275)[row]
    elif shape == "oval":
        far_span, near_span = (205, 275, 340)[row], (250, 330, 405)[row]
    else:
        far_span, near_span = (120, 215, 300)[row], (120, 230, 300)[row]
    def line(span):
        return [300 - span / 2 + (span * i / max(1, per_side - 1)) for i in range(per_side)]
    far, near = line(far_span), line(near_span)
    return far, near


# Traced from the approved six-chair reference: the near side descends toward
# the camera from left to right, while the far side recedes behind the top.
# Eight- and ten-chair layouts extend the same perspective lines.
REFERENCE_RECTANGLE = (
    {
        "far": ((210, 330, 136, "far-left", .94), (330, 318, 124, "far-right", .88)),
        "near": ((330, 488, 168, "near-left", .98), (440, 452, 148, "near-right", .90)),
        "far_end": (518, 370, 132, .88),
        "near_end": (90, 455, 168, .98),
    },
    {
        "far": ((165, 335, 142, "far-left", .96), (280, 324, 132, "far-left", .92),
                (380, 312, 120, "far-right", .86)),
        "near": ((270, 500, 176, "near-left", 1), (365, 470, 160, "near-right", .94),
                 (450, 440, 144, "near-right", .88)),
        "far_end": (520, 382, 134, .88),
        "near_end": (80, 462, 172, .98),
    },
    {
        "far": ((135, 340, 144, "far-left", .98), (225, 332, 136, "far-left", .94),
                (310, 322, 128, "far-right", .90), (390, 312, 120, "far-right", .86)),
        "near": ((225, 510, 180, "near-left", 1), (305, 492, 170, "near-left", .97),
                 (380, 466, 158, "near-right", .93), (450, 440, 146, "near-right", .88)),
        "far_end": (522, 384, 136, .88),
        "near_end": (72, 470, 176, .98),
    },
)


def make_position_atlases(views):
    for shape in ("rectangle", "oval", "circle"):
        for family in FAMILIES:
            back_strip = Image.new("RGBA", (CELL, CELL * 3))
            front_strip = Image.new("RGBA", (CELL, CELL * 3))
            for row in range(3):
                back = Image.new("RGBA", (CELL, CELL))
                front = Image.new("RGBA", (CELL, CELL))
                if shape == "rectangle":
                    layout = REFERENCE_RECTANGLE[row]
                    for x, bottom, height, view, width_factor in layout["far"]:
                        place(back, views[(family, view)], x=x, bottom=bottom,
                              height=height, width_factor=width_factor)
                    for x, bottom, height, view, width_factor in layout["near"]:
                        place(front, views[(family, view)], x=x, bottom=bottom,
                              height=height, width_factor=width_factor)
                    x, bottom, height, width_factor = layout["far_end"]
                    place(back, views[(family, "end-right")], x=x, bottom=bottom,
                          height=height, width_factor=width_factor)
                    x, bottom, height, width_factor = layout["near_end"]
                    place(front, views[(family, "end-left")], x=x, bottom=bottom,
                          height=height, width_factor=width_factor)
                else:
                    far_xs, near_xs = positions(shape, row)
                    for index, x in enumerate(far_xs):
                        depth = index / max(1, len(far_xs) - 1)
                        view = "far-left" if x < CELL / 2 else "far-right"
                        place(back, views[(family, view)], x=x, bottom=304 - 10 * depth,
                              height=218 - round(18 * depth), width_factor=.9 - .07 * depth)
                    for index, x in enumerate(near_xs):
                        depth = index / max(1, len(near_xs) - 1)
                        view = "near-left" if x < CELL / 2 else "near-right"
                        place(front, views[(family, view)], x=x - 5, bottom=512 - 16 * depth,
                              height=238 - round(20 * depth), width_factor=.96 - .08 * depth)
                    place(back, views[(family, "end-right")], x=(450, 480, 510)[row],
                          bottom=366, height=206, width_factor=.88)
                    place(front, views[(family, "end-left")], x=(150, 110, 60)[row],
                          bottom=478, height=238, width_factor=.94)
                back_strip.alpha_composite(back, (0, row * CELL))
                front_strip.alpha_composite(front, (0, row * CELL))
            target = CHAIRS / "position-atlases" / shape
            target.mkdir(parents=True, exist_ok=True)
            back_strip.save(target / f"{family}-back.webp", "WEBP", lossless=True)
            front_strip.save(target / f"{family}-front.webp", "WEBP", lossless=True)


if __name__ == "__main__":
    chair_views = crop_views()
    make_table_layers()
    make_position_atlases(chair_views)
