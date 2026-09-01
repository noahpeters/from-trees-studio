"""Build independent, perspective-correct table and chair layers."""

from pathlib import Path
from collections import deque
import math
from PIL import Image, ImageEnhance, ImageOps

import generate_geometric_studies as geometry
from prepare_style_v2_masters import neutral_background_to_alpha

ROOT = Path(__file__).resolve().parents[1]
TRANSPARENT = ROOT / "public" / "renders-transparent"
TRANSPARENT_MASTERS = ROOT / "public" / "renders-transparent-masters"
CHAIRS = ROOT / "public" / "chairs"
STYLE_V2 = ROOT / "public" / "style-v2" / "chairs" / "masters"
STYLE_TABLE_MASTERS = ROOT / "public" / "style-v2" / "tables" / "masters"
STYLE_TABLE_COMPLETE_MASTERS = ROOT / "public" / "style-v2" / "tables" / "complete-masters"
STYLE_TABLE_STRIPS = ROOT / "public" / "style-v2" / "tables" / "strips"
CELL = 600
FAMILIES = ("curved-back", "ladder-back", "spindle-back")
PERSPECTIVE_VIEWS = ("far-left", "far-right", "near-left", "near-right")


def keep_largest_component(source):
    """Remove isolated alpha streaks while preserving the complete chair."""
    alpha = source.getchannel("A")
    width, height = alpha.size
    pixels = alpha.load()
    visited = bytearray(width * height)
    winner = []
    for y in range(height):
        for x in range(width):
            start = y * width + x
            if visited[start] or pixels[x, y] < 32:
                continue
            visited[start] = 1
            queue = deque([(x, y)])
            component = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue
                    index = ny * width + nx
                    if visited[index] or pixels[nx, ny] < 32:
                        continue
                    visited[index] = 1
                    queue.append((nx, ny))
            if len(component) > len(winner):
                winner = component
    mask = Image.new("L", source.size)
    mask_pixels = mask.load()
    for x, y in winner:
        mask_pixels[x, y] = pixels[x, y]
    cleaned = source.copy()
    cleaned.putalpha(mask)
    bbox = mask.getbbox()
    return cleaned.crop(bbox) if bbox else cleaned


def prepare_complete_table_masters():
    """Convert generated complete-table drawings to clean true-alpha masters."""
    for path in sorted(STYLE_TABLE_COMPLETE_MASTERS.rglob("table-*.png")):
        source = Image.open(path)
        prepared = source.convert("RGBA") if source.mode == "RGBA" else neutral_background_to_alpha(source)
        prepared = keep_largest_component(prepared)
        padded = Image.new("RGBA", (prepared.width + 24, prepared.height + 24))
        padded.alpha_composite(prepared, (12, 12))
        padded.save(path, "PNG", optimize=True)


def crop_views():
    """Load high-fidelity perspective masters, falling back to legacy sheets."""
    if STYLE_V2.exists():
        views = {}
        target = CHAIRS / "position-views"
        target.mkdir(parents=True, exist_ok=True)
        for family in FAMILIES:
            for view in ("near-left", "far-left", "end-left", "rear-left"):
                candidates = (
                    STYLE_V2 / f"{family}-{view}-v3.png",
                    STYLE_V2 / f"{family}-{view}-v2.png",
                    STYLE_V2 / f"{family}-{view}.png",
                )
                source_path = next((path for path in candidates if path.exists()), candidates[-1])
                if not source_path.exists():
                    raise FileNotFoundError(source_path)
                source = Image.open(source_path)
                # Every high-fidelity chair master passes through the enclosed
                # background remover. Several ladder and spindle studies had
                # valid outer alpha but opaque white fields trapped between
                # rails, spindles, seats, legs, and stretchers.
                chair = neutral_background_to_alpha(source)
                chair = keep_largest_component(chair)
                chair.save(target / f"{family}-{view}.webp", "WEBP", lossless=True)
                views[(family, view)] = chair
                right_view = view.replace("left", "right")
                mirrored = ImageOps.mirror(chair)
                mirrored.save(target / f"{family}-{right_view}.webp", "WEBP", lossless=True)
                views[(family, right_view)] = mirrored
        return views

    """Crop perspective-specific RGBA studies; never fake yaw with 2D shear."""
    source_path = CHAIRS / "geometry" / "chair-perspectives-transparent.png"
    ends_path = ROOT / "_unused-assets" / "public" / "masters" / "chair-ends-transparent.png"
    source = Image.open(source_path).convert("RGBA")
    ends = Image.open(ends_path).convert("RGBA")
    views = {}
    target = CHAIRS / "position-views"
    target.mkdir(parents=True, exist_ok=True)

    def take(sheet, column, row, columns, rows):
        cell_w, cell_h = sheet.width / columns, sheet.height / rows
        crop = sheet.crop((round(column * cell_w), round(row * cell_h),
                           round((column + 1) * cell_w), round((row + 1) * cell_h)))
        # Generated masters contain stray edge pixels outside the centered
        # chair study. Remove that safety margin before component cleanup so a
        # single attached scanline cannot expand the chair's crop.
        inset_x = round(crop.width * .18)
        inset_y = round(crop.height * .015)
        crop = crop.crop((inset_x, inset_y, crop.width - inset_x, crop.height - inset_y))
        return keep_largest_component(crop)

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


def make_style_table_strips():
    """Fit complete profile-specific table masters to the physical projection."""
    edges = {
        "rectangle": ("soft-square", "bullnose", "live-edge"),
        "oval": ("soft-square", "bullnose"),
        "circle": ("soft-square", "bullnose"),
    }
    for master_path in sorted(STYLE_TABLE_MASTERS.glob("table-*.png")):
        _, shape, base = master_path.stem.split("-", 2)
        if shape not in edges:
            continue
        for edge in edges[shape]:
            profile_path = master_path if edge == "soft-square" else (
                STYLE_TABLE_COMPLETE_MASTERS / shape / base / f"table-{edge}.png"
            )
            if not profile_path.exists():
                raise FileNotFoundError(profile_path)
            profiled_master = Image.open(profile_path).convert("RGBA")
            strip = Image.new("RGBA", (CELL, CELL * 3))
            for row in range(3):
                if shape == "circle":
                    diameter = geometry.MODEL["table"]["circleDiameters"][row]
                    envelope = geometry.draw_table(diameter, diameter, base, shape, edge)
                else:
                    length = geometry.MODEL["table"]["rectangleLengths"][row]
                    envelope = geometry.draw_table(
                        length, geometry.MODEL["table"]["canonicalWidth"], base, shape, edge
                    )
                bbox = envelope.getbbox()
                if not bbox:
                    continue
                left, top, right, bottom = bbox
                table = profiled_master.resize(
                    (right - left, bottom - top), Image.Resampling.LANCZOS
                )
                cell = Image.new("RGBA", (CELL, CELL))
                cell.alpha_composite(table, (left, top))
                strip.alpha_composite(cell, (0, row * CELL))
            target = STYLE_TABLE_STRIPS / shape / base
            target.mkdir(parents=True, exist_ok=True)
            strip.save(target / f"table-{edge}.png", "PNG", optimize=True)


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


def chair_view(origin, yaw, _layer=None):
    """Choose the approved view nearest the camera's chair-local azimuth.

    Every chair's yaw already points its local forward axis at the table
    center.  View selection must therefore be based on where the fixed camera
    sits relative to that individual chair—not on the chair's screen side or
    on a neighboring chair that happened to look plausible.
    """
    camera_dx = geometry.CAMERA.x - origin.x
    camera_dz = geometry.CAMERA.z - origin.z
    cosine, sine = math.cos(yaw), math.sin(yaw)
    local_x = camera_dx * cosine + camera_dz * sine
    local_z = -camera_dx * sine + camera_dz * cosine
    azimuth = math.degrees(math.atan2(local_x, -local_z))
    magnitude = abs(azimuth)
    side = "left" if azimuth < 0 else "right"

    # The approved master set contains front three-quarter, side, and rear
    # three-quarter studies. These boundaries select the closest study while
    # retaining its detailed hand-drawn artwork. Mirroring is baked offline.
    if magnitude < 67.5:
        perspective = "far"
    elif magnitude < 122.5:
        perspective = "end"
    else:
        perspective = "rear"
    return f"{perspective}-{side}"


def position_view(shape, family, origin, yaw, layer):
    """Resolve approved family-specific views for each physical anchor."""
    view = chair_view(origin, yaw, layer)
    if shape not in ("rectangle", "oval"):
        return view

    # On rectangular-family tops, the camera-side physical end projects to
    # the lower-right of the study.
    # Its approved treatment is the inward-facing three-quarter study. The
    # rear study stops short of the tabletop axis, while the end study turns
    # past it; this intermediate view points the seat directly at the table.
    if layer == "near" and abs(origin.z) < .01 and origin.x < 0:
        return "near-right"

    # The opposite physical end uses the approved end-left treatment.
    if layer == "far" and abs(origin.z) < .01 and origin.x > 0:
        return "end-left"

    # Ladder-back viewpoint labels are not visually equivalent to the other
    # chair families. On the far long side, the mirrored master is the one
    # whose seat and back actually turn inward toward the tabletop.
    if family == "ladder-back" and layer == "far" and origin.z > 0:
        return "far-right"
    return view


def projected_seats(shape, row):
    if shape in ("rectangle", "oval"):
        length = geometry.MODEL["table"]["rectangleLengths"][row]
        band = ("small", "medium", "large")[row]
        return geometry.rectangular_seats(length, geometry.MODEL["table"]["canonicalWidth"], band)
    diameter = geometry.MODEL["table"]["circleDiameters"][row]
    return geometry.round_seats(diameter, (6, 8, 10)[row])


def place_projected(canvas, source, bbox):
    """Fit beautiful chair artwork to a physically projected chair envelope."""
    left, top, right, bottom = bbox
    target_height = bottom - top
    natural_width = source.width * target_height / source.height
    width_factor = (right - left) / natural_width
    place(canvas, source, x=(left + right) / 2, bottom=bottom,
          height=target_height, width_factor=width_factor)


def make_position_atlases(views, shapes=("rectangle", "oval", "circle")):
    """Bake detailed chair studies into exact geometry-derived envelopes.

    The inch model still owns every anchor, scale, yaw, depth, and layer.  A
    direction-specific approved drawing is fitted into that projected chair's
    final envelope during generation.  The browser receives finished sprites
    and performs no transforms.
    """
    for shape in shapes:
        for family in FAMILIES:
            back_strip = Image.new("RGBA", (CELL, CELL * 3))
            front_strip = Image.new("RGBA", (CELL, CELL * 3))
            for row in range(3):
                seats = projected_seats(shape, row)
                layers = {
                    "far": Image.new("RGBA", (CELL, CELL)),
                    "near": Image.new("RGBA", (CELL, CELL)),
                }
                for layer in ("far", "near"):
                    ordered = sorted(
                        (seat for seat in seats if seat[2] == layer),
                        key=lambda seat: geometry.project(seat[0])[2],
                        reverse=True,
                    )
                    for origin, yaw, _ in ordered:
                        guide = geometry.draw_chair(origin, yaw, family)
                        bbox = guide.getbbox()
                        if not bbox:
                            continue
                        view = position_view(shape, family, origin, yaw, layer)
                        place_projected(layers[layer], views[(family, view)], bbox)
                back = layers["far"]
                front = layers["near"]
                back_strip.alpha_composite(back, (0, row * CELL))
                front_strip.alpha_composite(front, (0, row * CELL))
            target = CHAIRS / "position-atlases" / shape
            target.mkdir(parents=True, exist_ok=True)
            back_strip.save(target / f"{family}-back.png", "PNG", optimize=True)
            front_strip.save(target / f"{family}-front.png", "PNG", optimize=True)


if __name__ == "__main__":
    make_table_layers()
    prepare_complete_table_masters()
    make_style_table_strips()
    make_position_atlases(crop_views())
