"""Generate geometry-v1 configurator sprites from the documented inch model."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
MODEL = json.loads((ROOT / "configurator-geometry.json").read_text())
STYLE = json.loads((ROOT / "configurator-render-style.json").read_text())
TARGET = ROOT / "public" / "geometric-v1"
CELL = MODEL["stage"]["width"]
PROJECTION_OFFSET_X, PROJECTION_OFFSET_Y = MODEL["stage"].get("projectionOffset", [0, 0])
AA = 4
INK = tuple(STYLE["palette"]["primaryLine"])
LIGHT_INK = tuple(STYLE["palette"]["secondaryLine"])
CONSTRUCTION = tuple(STYLE["palette"]["constructionLine"])
WOOD = tuple(STYLE["palette"]["woodTop"])
WOOD_SIDE = tuple(STYLE["palette"]["woodSide"])
WOOD_DARK = tuple(STYLE["palette"]["woodShadow"])
JITTER = STYLE["linework"]["coordinateJitterPixels"] * AA


@dataclass(frozen=True)
class V3:
    x: float
    y: float
    z: float


def sub(a: V3, b: V3) -> V3:
    return V3(a.x - b.x, a.y - b.y, a.z - b.z)


def dot(a: V3, b: V3) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z


def cross(a: V3, b: V3) -> V3:
    return V3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def unit(v: V3) -> V3:
    magnitude = math.sqrt(dot(v, v)) or 1
    return V3(v.x / magnitude, v.y / magnitude, v.z / magnitude)


camera = MODEL["camera"]
CAMERA = V3(*camera["position"])
TARGET_POINT = V3(*camera["target"])
FORWARD = unit(sub(TARGET_POINT, CAMERA))
RIGHT = unit(cross(FORWARD, V3(0, 1, 0)))
UP = unit(cross(RIGHT, FORWARD))
FOCAL = (CELL * .5) / math.tan(math.radians(camera["verticalFieldOfViewDegrees"] / 2))


def project(point: V3) -> tuple[float, float, float]:
    relative = sub(point, CAMERA)
    depth = dot(relative, FORWARD)
    return (
        CELL / 2 + PROJECTION_OFFSET_X + dot(relative, RIGHT) * FOCAL / depth,
        CELL / 2 + PROJECTION_OFFSET_Y - dot(relative, UP) * FOCAL / depth,
        depth,
    )


def rotate(point: V3, origin: V3, yaw: float) -> V3:
    cosine, sine = math.cos(yaw), math.sin(yaw)
    x, z = point.x - origin.x, point.z - origin.z
    return V3(origin.x + x * cosine - z * sine, point.y, origin.z + x * sine + z * cosine)


def canvas() -> Image.Image:
    return Image.new("RGBA", (CELL * AA, CELL * AA))


def xy(point: V3) -> tuple[int, int]:
    x, y, _ = project(point)
    return round(x * AA), round(y * AA)


def jittered(points, salt=0):
    seed = salt
    for x, y in points:
        seed ^= (x * 73856093) ^ (y * 19349663)
    rng = random.Random(seed)
    return [
        (round(x + rng.uniform(-JITTER, JITTER)), round(y + rng.uniform(-JITTER, JITTER)))
        for x, y in points
    ]


def roughened(points, salt=0, amplitude=.55):
    """Subdivide straight segments into a restrained, pencil-like wandering path."""
    if len(points) < 2:
        return points
    seed = salt
    for x, y in points:
        seed ^= (x * 73856093) ^ (y * 19349663)
    rng = random.Random(seed)
    result = []
    for index, (start, end) in enumerate(zip(points, points[1:])):
        dx, dy = end[0] - start[0], end[1] - start[1]
        magnitude = math.hypot(dx, dy) or 1
        nx, ny = -dy / magnitude, dx / magnitude
        segments = max(2, min(8, round(magnitude / (18 * AA))))
        if index == 0:
            result.append(start)
        for step in range(1, segments + 1):
            fraction = step / segments
            offset = 0 if step == segments else rng.uniform(-amplitude, amplitude) * AA
            result.append((
                round(start[0] + dx * fraction + nx * offset),
                round(start[1] + dy * fraction + ny * offset),
            ))
    return result


def sketch_path(draw, points, fill=INK, width=None, closed=False):
    if len(points) < 2:
        return
    if width is None:
        width = STYLE["linework"]["primaryWidth"]
    path = points + ([points[0]] if closed else [])
    under = roughened(jittered(path, 41), 141, .42)
    echo = roughened(jittered(path, 97), 197, .32)
    primary = roughened(jittered(path, 13), 113, .48)
    # Two translucent graphite passes create an organic edge without loose marks.
    draw.line(under, fill=CONSTRUCTION, width=max(1, round((width + .55) * AA)), joint="curve")
    draw.line(echo, fill=LIGHT_INK, width=max(1, round(STYLE["linework"]["secondaryWidth"] * AA)), joint="curve")
    draw.line(primary, fill=fill, width=max(1, round(width * AA)), joint="curve")


def point_in_polygon(point, polygon_points):
    x, y = point
    inside = False
    previous = polygon_points[-1]
    for current in polygon_points:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / ((y2 - y1) or 1) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def pencil_wash(draw, polygon_points, salt=0):
    """Add sparse, clipped graphite texture without construction-line artifacts."""
    min_x = min(point[0] for point in polygon_points)
    max_x = max(point[0] for point in polygon_points)
    min_y = min(point[1] for point in polygon_points)
    max_y = max(point[1] for point in polygon_points)
    area_hint = max(0, max_x - min_x) * max(0, max_y - min_y)
    if area_hint < 180 * AA * AA:
        return
    rng = random.Random(salt + sum(x * 31 + y * 17 for x, y in polygon_points))
    stroke_count = min(44, max(8, round(area_hint / (1500 * AA * AA))))
    graphite = (132, 113, 92, 28)
    for _ in range(stroke_count):
        start = (rng.uniform(min_x, max_x), rng.uniform(min_y, max_y))
        angle = rng.uniform(-.24, .24)
        run = rng.uniform(2.5, 8.5) * AA
        end = (start[0] + math.cos(angle) * run, start[1] + math.sin(angle) * run)
        if point_in_polygon(start, polygon_points) and point_in_polygon(end, polygon_points):
            draw.line(roughened([
                (round(start[0]), round(start[1])),
                (round(end[0]), round(end[1])),
            ], round(start[0] + start[1]), .18), fill=graphite, width=max(1, round(.32 * AA)))


def polygon(draw: ImageDraw.ImageDraw, points: list[V3], fill=WOOD, outline=INK, width=1.25):
    projected = [xy(point) for point in points]
    draw.polygon(projected, fill=fill)
    pencil_wash(draw, projected, 300 if fill == WOOD else 500)
    if fill in (WOOD_SIDE, WOOD_DARK) and len(projected) == 4:
        # Short, irregular strokes suggest grain; full ruled hatching reads as CAD.
        for index, fraction in enumerate((.18, .37, .61, .79)):
            start_fraction = .14 + (index % 2) * .12
            end_fraction = min(.9, start_fraction + .28 + (index % 3) * .08)
            left = (
                projected[0][0] + (projected[3][0] - projected[0][0]) * fraction,
                projected[0][1] + (projected[3][1] - projected[0][1]) * fraction,
            )
            right = (
                projected[1][0] + (projected[2][0] - projected[1][0]) * fraction,
                projected[1][1] + (projected[2][1] - projected[1][1]) * fraction,
            )
            start = (
                round(left[0] + (right[0] - left[0]) * start_fraction),
                round(left[1] + (right[1] - left[1]) * start_fraction),
            )
            end = (
                round(left[0] + (right[0] - left[0]) * end_fraction),
                round(left[1] + (right[1] - left[1]) * end_fraction),
            )
            draw.line(roughened([start, end], 200 + index, .24), fill=CONSTRUCTION, width=max(1, round(.38 * AA)))
    sketch_path(draw, projected, outline, width, closed=True)


def line(draw: ImageDraw.ImageDraw, a: V3, b: V3, fill=INK, width=1.6):
    sketch_path(draw, [xy(a), xy(b)], fill, width)


def wood_column(draw, a: V3, b: V3, width: float, fill=WOOD_SIDE):
    points = [xy(a), xy(b)]
    draw.line(points, fill=INK, width=max(1, round((width + 1.1) * AA)))
    draw.line(points, fill=fill, width=max(1, round(width * AA)))
    sketch_path(draw, points, INK, 1.0)
    offset = max(1, round(width * AA * .22))
    highlight = [(points[0][0] - offset, points[0][1]), (points[1][0] - offset, points[1][1])]
    draw.line(highlight, fill=LIGHT_INK, width=max(1, round(.55 * AA)))


def clipped_grain(image: Image.Image, outline: list[V3], length: float, width: float):
    mask = Image.new("L", image.size)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.polygon([xy(point) for point in outline], fill=255)
    texture = Image.new("RGBA", image.size)
    texture_draw = ImageDraw.Draw(texture, "RGBA")
    half_l, half_w = length / 2, width / 2
    count = STYLE["texture"]["topGrainLines"]
    rng = random.Random(round(length * 13 + width * 17))
    for index in range(count):
        z = rng.uniform(-half_w * .76, half_w * .76)
        run = rng.uniform(length * .2, length * .52)
        start = rng.uniform(-half_l + 5, half_l - run - 4)
        points = []
        for segment in range(6):
            x = start + run * segment / 5
            wave = math.sin(segment * 1.15 + index * .8) * rng.uniform(.12, .48)
            points.append(xy(V3(x, 30.04, z + wave)))
        sketch_path(texture_draw, points, LIGHT_INK, .42)
    image.alpha_composite(Image.composite(texture, Image.new("RGBA", image.size), mask))


def face_depth(points: list[V3]) -> float:
    return sum(project(point)[2] for point in points) / len(points)


def box_faces(x1, x2, y1, y2, z1, z2):
    return [
        ([V3(x1, y2, z1), V3(x2, y2, z1), V3(x2, y2, z2), V3(x1, y2, z2)], WOOD),
        ([V3(x1, y1, z1), V3(x2, y1, z1), V3(x2, y2, z1), V3(x1, y2, z1)], WOOD_SIDE),
        ([V3(x1, y1, z2), V3(x2, y1, z2), V3(x2, y2, z2), V3(x1, y2, z2)], WOOD_SIDE),
        ([V3(x1, y1, z1), V3(x1, y1, z2), V3(x1, y2, z2), V3(x1, y2, z1)], WOOD_DARK),
        ([V3(x2, y1, z1), V3(x2, y1, z2), V3(x2, y2, z2), V3(x2, y2, z1)], WOOD_DARK),
    ]


def tapered_leg(draw, top: V3, bottom: V3, width_top=3.2, width_bottom=2.2):
    top_screen = xy(top)
    bottom_screen = xy(bottom)
    dx, dy = bottom_screen[0] - top_screen[0], bottom_screen[1] - top_screen[1]
    magnitude = math.hypot(dx, dy) or 1
    nx, ny = -dy / magnitude, dx / magnitude
    tw, bw = width_top * AA, width_bottom * AA
    points = [
        (round(top_screen[0] + nx * tw), round(top_screen[1] + ny * tw)),
        (round(top_screen[0] - nx * tw), round(top_screen[1] - ny * tw)),
        (round(bottom_screen[0] - nx * bw), round(bottom_screen[1] - ny * bw)),
        (round(bottom_screen[0] + nx * bw), round(bottom_screen[1] + ny * bw)),
    ]
    draw.polygon(points, fill=WOOD_SIDE)
    sketch_path(draw, points, INK, 1.15, closed=True)
    draw.line([points[0], points[3]], fill=LIGHT_INK, width=round(.7 * AA))


def sculpted_rail(draw, points: list[V3], visual_width: float = 5.2):
    """Draw a filled, softly irregular timber following a projected 3D curve."""
    projected = [xy(point) for point in points]
    if len(projected) < 2:
        return
    left, right = [], []
    half = visual_width * AA
    for index, point in enumerate(projected):
        previous = projected[max(0, index - 1)]
        following = projected[min(len(projected) - 1, index + 1)]
        dx, dy = following[0] - previous[0], following[1] - previous[1]
        magnitude = math.hypot(dx, dy) or 1
        nx, ny = -dy / magnitude, dx / magnitude
        left.append((round(point[0] + nx * half), round(point[1] + ny * half)))
        right.append((round(point[0] - nx * half), round(point[1] - ny * half)))
    ribbon = left + list(reversed(right))
    draw.polygon(ribbon, fill=WOOD_SIDE)
    pencil_wash(draw, ribbon, 840)
    sketch_path(draw, ribbon, INK, 1.15, closed=True)
    sketch_path(draw, projected, LIGHT_INK, .5)


def draw_slab(draw, x1, x2, z1, z2, top=28.5, thickness=3.5):
    faces = box_faces(x1, x2, top - thickness, top, z1, z2)
    for points, fill in sorted(faces, reverse=True, key=lambda item: face_depth(item[0])):
        polygon(draw, points, fill)


def draw_base(draw, length: float, width: float, base_style: str):
    half_l, half_w = length / 2, width / 2
    end_x = max(half_l - min(13, length * .16), half_l * .55)

    if base_style in ("mid-century-splayed", "four-tapered-legs"):
        legs = []
        for x in (-end_x, end_x):
            for z in (-half_w + 5, half_w - 5):
                splayed = base_style == "mid-century-splayed"
                outward_x = (-4 if x < 0 else 4) if splayed else 0
                outward_z = (-3 if z < 0 else 3) if splayed else 0
                top = V3(x, 28.4, z)
                bottom = V3(x + outward_x, 0, z + outward_z)
                legs.append((project(bottom)[2], top, bottom))
        for _, top, bottom in sorted(legs, reverse=True, key=lambda item: item[0]):
            tapered_leg(draw, top, bottom, 3.2, 1.8 if base_style == "four-tapered-legs" else 2.2)
        if base_style == "mid-century-splayed":
            # Apronless sculpted underframe: two shallow arched side rails merge
            # visually into the set-back splayed legs. Geometry remains tied to
            # the same physical camera and 30-inch table height.
            for z in (-half_w + 5, half_w - 5):
                curve = []
                for index in range(25):
                    fraction = index / 24
                    x = -end_x + (2 * end_x * fraction)
                    y = 25.8 - 7.2 * math.sin(math.pi * fraction)
                    curve.append(V3(x, y, z))
                sculpted_rail(draw, curve, 2.8)
        return

    if base_style in ("turned-legs-classic", "turned-legs-simplified"):
        for x in (-end_x, end_x):
            for z in (-half_w + 5, half_w - 5):
                wood_column(draw, V3(x, 0, z), V3(x, 28.5, z), 5.5)
                if base_style == "turned-legs-classic":
                    for y, radius in ((5, 3.0), (12, 4.4), (20, 3.4), (25, 4.0)):
                        wood_column(draw, V3(x - radius / 2, y, z), V3(x + radius / 2, y, z), 3.2, WOOD)
                else:
                    for y in (8, 20):
                        wood_column(draw, V3(x - 1.8, y, z), V3(x + 1.8, y, z), 2.4, WOOD)
        return

    if base_style == "curved-slab-frame":
        draw_slab(draw, -end_x - 4, -end_x + 4, -half_w + 3, half_w - 3, 28.5, 27)
        draw_slab(draw, end_x - 4, end_x + 4, -half_w + 3, half_w - 3, 28.5, 27)
        draw_slab(draw, -end_x + 2, end_x - 2, -half_w + 4, -half_w + 9, 6, 5)
        return

    if base_style in ("a-frame", "x-trestle"):
        for x in (-end_x, end_x):
            for sign in (-1, 1):
                if base_style == "a-frame":
                    top = V3(x, 28.5, sign * 6)
                    bottom = V3(x, 0, sign * (half_w - 2))
                else:
                    top = V3(x, 28.5, sign * (half_w - 5))
                    bottom = V3(x, 0, -sign * (half_w - 2))
                tapered_leg(draw, top, bottom, 2.6, 2.8)
        draw_slab(draw, -end_x, end_x, -2, 2, 12, 3)
        return

    if base_style == "curved-trestle":
        for x in (-end_x, end_x):
            line(draw, V3(x, 0, -half_w + 5), V3(x, 28.5, -5), INK, 7)
            line(draw, V3(x, 28.5, -5), V3(x, 0, half_w - 5), INK, 7)
        draw_slab(draw, -end_x, end_x, -2, 2, 10, 3)
        return

    # Pedestal families use one or two centered masses depending on length.
    pedestal_xs = (0,) if length <= 84 else (-length * .24, length * .24)
    for x in pedestal_xs:
        if base_style == "solid-pedestal":
            draw_slab(draw, x - 6, x + 6, -half_w + 7, half_w - 7, 28.5, 25)
        elif base_style == "tapered-pedestal":
            tapered_leg(draw, V3(x, 28.5, 0), V3(x, 3, 0), 9, 13)
            draw_slab(draw, x - 11, x + 11, -half_w + 5, half_w - 5, 3, 2.5)
        else:  # sculpted turned pedestal
            wood_column(draw, V3(x, 3, 0), V3(x, 28.5, 0), 12, WOOD_SIDE)
            for y, radius in ((5, 16), (10, 11), (16, 15), (22, 10), (27, 13)):
                wood_column(draw, V3(x - radius / 2, y, 0), V3(x + radius / 2, y, 0), 4.5, WOOD)
            draw_slab(draw, x - 12, x + 12, -half_w + 6, half_w - 6, 3, 2.5)


def top_outline(length: float, width: float, shape: str, edge_style: str):
    half_l, half_w = length / 2, width / 2
    if shape in ("oval", "circle"):
        return [
            V3(math.cos(angle) * half_l, 30, math.sin(angle) * half_w)
            for angle in [index * math.tau / 48 for index in range(48)]
        ]
    if edge_style == "live-edge":
        points = []
        segments = 12
        for index in range(segments + 1):
            x = -half_l + length * index / segments
            z = -half_w + math.sin(index * 1.7) * 1.1
            points.append(V3(x, 30, z))
        for index in range(segments, -1, -1):
            x = -half_l + length * index / segments
            z = half_w + math.sin(index * 1.45 + .8) * .9
            points.append(V3(x, 30, z))
        return points
    radius = 3.5 if edge_style == "bullnose" else (1.8 if edge_style == "soft-square" else 0)
    if radius == 0:
        return [V3(-half_l, 30, -half_w), V3(half_l, 30, -half_w), V3(half_l, 30, half_w), V3(-half_l, 30, half_w)]
    points = []
    for cx, cz, start in ((-half_l + radius, -half_w + radius, math.pi), (half_l - radius, -half_w + radius, -math.pi / 2), (half_l - radius, half_w - radius, 0), (-half_l + radius, half_w - radius, math.pi / 2)):
        for index in range(5):
            angle = start + index * math.pi / 8
            points.append(V3(cx + math.cos(angle) * radius, 30, cz + math.sin(angle) * radius))
    return points


def draw_top(draw, length: float, width: float, shape: str, edge_style: str):
    top = top_outline(length, width, shape, edge_style)
    lower = [V3(point.x, 28.5, point.z) for point in top]
    # Draw the visible skirt as small opaque quads, then the opaque top plane.
    faces = []
    for index, point in enumerate(top):
        next_index = (index + 1) % len(top)
        faces.append([lower[index], lower[next_index], top[next_index], point])
    for face in sorted(faces, reverse=True, key=face_depth):
        polygon(draw, face, WOOD_SIDE, width=1.1)
    polygon(draw, top, WOOD, width=1.5)
    if edge_style == "bullnose":
        inset = [V3(point.x * .985, 29.15, point.z * .985) for point in top]
        for index in range(0, len(inset), max(1, len(inset) // 20)):
            next_index = (index + 1) % len(inset)
            line(draw, inset[index], inset[next_index], LIGHT_INK, .7)


def draw_table(length: float, width: float, base_style: str, shape="rectangle", edge_style="soft-square") -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    half_l, half_w = length / 2, width / 2
    inset_x = min(13, length * .16)
    draw_base(draw, length, width, base_style)

    four_legged = {
        "four-tapered-legs",
        "turned-legs-classic",
        "turned-legs-simplified",
    }
    if base_style in four_legged:
        apron_faces = []
        apron_faces += box_faces(-half_l + inset_x - 2, half_l - inset_x + 2, 24.5, 29, -half_w + 3, -half_w + 5)
        apron_faces += box_faces(-half_l + inset_x - 2, half_l - inset_x + 2, 24.5, 29, half_w - 5, half_w - 3)
        apron_faces += box_faces(-half_l + inset_x - 3, -half_l + inset_x - 1, 24.5, 29, -half_w + 4, half_w - 4)
        apron_faces += box_faces(half_l - inset_x + 1, half_l - inset_x + 3, 24.5, 29, -half_w + 4, half_w - 4)
        for points, fill in sorted(apron_faces, reverse=True, key=lambda item: face_depth(item[0])):
            polygon(draw, points, fill)

    outline = top_outline(length, width, shape, edge_style)
    draw_top(draw, length, width, shape, edge_style)
    clipped_grain(image, outline, length, width)
    return image.resize((CELL, CELL), Image.Resampling.LANCZOS)


def chair_points(origin: V3, yaw: float, local: V3) -> V3:
    return rotate(V3(origin.x + local.x, local.y, origin.z + local.z), origin, yaw)


def chair_timber(draw, p, a, b, width_top=1.5, width_bottom=None, fill=WOOD_SIDE):
    """A softly tapered chair part with an opaque face and restrained pencil grain."""
    width_bottom = width_top if width_bottom is None else width_bottom
    top_screen = xy(p(*a))
    bottom_screen = xy(p(*b))
    dx, dy = bottom_screen[0] - top_screen[0], bottom_screen[1] - top_screen[1]
    magnitude = math.hypot(dx, dy) or 1
    nx, ny = -dy / magnitude, dx / magnitude
    # Width values describe the half-width of the projected timber, matching the
    # table-leg renderer. The earlier half-factor made every chair read as a
    # wireframe beside the finished table artwork.
    tw, bw = width_top * AA, width_bottom * AA
    shape = [
        (round(top_screen[0] + nx * tw), round(top_screen[1] + ny * tw)),
        (round(top_screen[0] - nx * tw), round(top_screen[1] - ny * tw)),
        (round(bottom_screen[0] - nx * bw), round(bottom_screen[1] - ny * bw)),
        (round(bottom_screen[0] + nx * bw), round(bottom_screen[1] + ny * bw)),
    ]
    draw.polygon(shape, fill=fill)
    pencil_wash(draw, shape, round(sum(top_screen) + sum(bottom_screen)))
    sketch_path(draw, shape, INK, 1.0, closed=True)
    # A single quiet grain line gives the part dimension without reading as CAD.
    center = roughened([top_screen, bottom_screen], round(top_screen[0] + bottom_screen[1]), .18)
    draw.line(center, fill=LIGHT_INK, width=max(1, round(.5 * AA)))


def chair_rail(draw, p, a, b, width=1.25, fill=WOOD_SIDE):
    chair_timber(draw, p, a, b, width, width, fill)


def chair_seat_outline(p, hw, hd, y):
    """A subtly bowed, softened seat perimeter in local chair coordinates."""
    return [
        p(-hw + .9, y, -hd),
        p(0, y, -hd - .45),
        p(hw - .9, y, -hd),
        p(hw, y, -hd + 1.0),
        p(hw, y, hd - 1.0),
        p(hw - .9, y, hd),
        p(-hw + .9, y, hd),
        p(-hw, y, hd - 1.0),
        p(-hw, y, -hd + 1.0),
    ]


def draw_chair(origin: V3, yaw: float, style: str = "ladder-back") -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image, "RGBA")
    seat_w = MODEL["chair"]["seatWidth"]
    seat_d = MODEL["chair"]["seatDepth"]
    seat_h = MODEL["chair"]["seatHeight"]
    back_h = MODEL["chair"]["overallHeight"]
    hw, hd = seat_w / 2, seat_d / 2
    p = lambda x, y, z: chair_points(origin, yaw, V3(x, y, z))

    # The chair is a joined object, not a collection of sticks. Rear legs continue
    # through the seat into slightly flared back posts; front legs splay subtly.
    back_z = hd - 1.0
    front_z = -hd + 1.35
    leg_specs = [
        ((-hw + 1.3, seat_h - .7, front_z), (-hw - .35, 0, front_z - .8), 1.8, 1.35),
        ((hw - 1.3, seat_h - .7, front_z), (hw + .35, 0, front_z - .8), 1.8, 1.35),
        ((-hw + 1.15, seat_h - .5, back_z), (-hw - .15, 0, back_z + 1.25), 2.0, 1.45),
        ((hw - 1.15, seat_h - .5, back_z), (hw + .15, 0, back_z + 1.25), 2.0, 1.45),
    ]

    # Low stretchers and the far legs are behind the seat, as on the reference chairs.
    chair_rail(draw, p, (-hw + .1, 6.2, front_z), (hw - .1, 6.2, front_z), 1.0, WOOD_DARK)
    chair_rail(draw, p, (-hw + .1, 6.2, back_z), (hw - .1, 6.2, back_z), 1.0, WOOD_DARK)
    chair_rail(draw, p, (-hw + .4, 7.0, front_z), (-hw + .4, 7.0, back_z), .95, WOOD_SIDE)
    chair_rail(draw, p, (hw - .4, 7.0, front_z), (hw - .4, 7.0, back_z), .95, WOOD_SIDE)
    for top, bottom, top_width, bottom_width in sorted(
        leg_specs,
        key=lambda item: project(p(*item[1]))[2],
        reverse=True,
    ):
        chair_timber(draw, p, top, bottom, top_width, bottom_width, WOOD_SIDE)

    # Opaque seat with a hand-shaped front edge, visible thickness, and a real under-rail.
    lower = chair_seat_outline(p, hw, hd, seat_h - 1.7)
    top = chair_seat_outline(p, hw, hd, seat_h)
    side_faces = []
    for index in range(len(top)):
        next_index = (index + 1) % len(top)
        face = [lower[index], lower[next_index], top[next_index], top[index]]
        side_faces.append((face_depth(face), face))
    for depth, face in sorted(side_faces, reverse=True):
        polygon(draw, face, WOOD_DARK if depth < project(origin)[2] else WOOD_SIDE, width=.9)
    polygon(draw, top, WOOD, width=1.25)
    # Sparse seat grain follows the seat width rather than using ruled glue lines.
    for index, z in enumerate((-4.8, -1.6, 1.9, 5.0)):
        line(draw, p(-hw + 2.2, seat_h + .03, z), p(hw - 2.2, seat_h + .03, z + .25 * (-1 if index % 2 else 1)), LIGHT_INK, .42)
    # Rails beneath the seat make the construction believable without a heavy apron.
    chair_rail(draw, p, (-hw + 1.0, seat_h - 3.1, front_z), (hw - 1.0, seat_h - 3.1, front_z), 1.35, WOOD_DARK)
    chair_rail(draw, p, (-hw + 1.0, seat_h - 3.0, back_z), (hw - 1.0, seat_h - 3.0, back_z), 1.15, WOOD_SIDE)

    # Back posts taper upward and lean back just enough to read as a real dining chair.
    chair_timber(draw, p, (-hw + 1.15, seat_h - .2, back_z), (-hw + .25, back_h, back_z + 1.25), 2.0, 1.45, WOOD_SIDE)
    chair_timber(draw, p, (hw - 1.15, seat_h - .2, back_z), (hw - .25, back_h, back_z + 1.25), 2.0, 1.45, WOOD_SIDE)
    if style == "spindle-back":
        # Windsor-inspired fan: shaped crest, seven slender spindles, opaque wood.
        crest = []
        for index in range(13):
            x = -hw + .4 + (seat_w - .8) * index / 12
            crown = 1.55 * (1 - (x / hw) ** 2)
            crest.append(p(x, back_h - .8 + crown, back_z + 1.25))
        sculpted_rail(draw, crest, 1.65)
        for index in range(7):
            fraction = index / 6
            x_bottom = -hw + 3.2 + (seat_w - 6.4) * fraction
            x_top = -hw + 2.0 + (seat_w - 4.0) * fraction
            crown = 1.2 * (1 - (x_top / hw) ** 2)
            chair_timber(draw, p, (x_bottom, seat_h + 1.8, back_z), (x_top, back_h - 1.7 + crown, back_z + 1.15), .72, .52, WOOD)
    elif style == "curved-back":
        # Broad, gently bowed crest panel with eased ends, grain and double pencil edge.
        upper, lower = [], []
        for index in range(15):
            x = -hw + .5 + (seat_w - 1) * index / 14
            crown = 1.65 * (1 - (x / hw) ** 2)
            bow = 1.2 * (1 - (x / hw) ** 2)
            upper.append(p(x, back_h - .55 + crown, back_z + 1.1 + bow))
            lower.append(p(x, back_h - 5.35 + crown * .52, back_z + .9 + bow))
        polygon(draw, upper + list(reversed(lower)), WOOD_SIDE, width=1.25)
        for fraction in (.27, .52, .74):
            x1 = -hw + 2.2
            x2 = hw - 2.2
            y = back_h - 4.45 + fraction * 2.9
            line(draw, p(x1, y, back_z + 1.85), p(x2, y + .15, back_z + 1.85), LIGHT_INK, .38)
    else:
        # Three substantial, softly bowed ladder rails—not weightless rectangles.
        for rail_index, y in enumerate((seat_h + 6.4, seat_h + 12.2, seat_h + 18.0)):
            curve = []
            for index in range(11):
                x = -hw + 1.15 + (seat_w - 2.3) * index / 10
                bow = 1.0 * (1 - (x / hw) ** 2)
                curve.append(p(x, y + .35 * math.sin(index * math.pi / 10), back_z + .6 + bow))
            sculpted_rail(draw, curve, 1.55 if rail_index < 2 else 1.7)
    return image.resize((CELL, CELL), Image.Resampling.LANCZOS)


def rectangular_seats(length: float, width: float, band: str):
    fractions = MODEL["rectangularAnchors"][band]
    half_l, half_w = length / 2, width / 2
    clearance = MODEL["chair"]["tableEdgeClearance"]
    center_offset = MODEL["chair"]["seatDepth"] / 2 + clearance
    usable_half = max(0, half_l - MODEL["chair"]["seatWidth"] / 2 - 4)
    seats = []
    for fraction in fractions:
        x = fraction * usable_half
        seats.append((V3(x, 0, -half_w - center_offset), math.pi, "near"))
        seats.append((V3(x, 0, half_w + center_offset), 0, "far"))
    seats.append((V3(-half_l - center_offset, 0, 0), math.pi / 2, "near"))
    seats.append((V3(half_l + center_offset, 0, 0), -math.pi / 2, "far"))
    return seats


def round_seats(diameter: float, count: int):
    radius = diameter / 2 + MODEL["chair"]["seatDepth"] / 2 + MODEL["chair"]["tableEdgeClearance"]
    center_depth = project(V3(0, 0, 0))[2]
    seats = []
    for index in range(count):
        angle = -math.pi * .75 + index * math.tau / count
        origin = V3(math.cos(angle) * radius, 0, math.sin(angle) * radius)
        yaw = angle - math.pi / 2
        layer = "far" if project(origin)[2] > center_depth else "near"
        seats.append((origin, yaw, layer))
    return seats


def composite_chairs(seats, layer: str, style: str) -> Image.Image:
    result = Image.new("RGBA", (CELL, CELL))
    ordered = sorted((seat for seat in seats if seat[2] == layer), key=lambda seat: project(seat[0])[2], reverse=True)
    for origin, yaw, _ in ordered:
        result.alpha_composite(draw_chair(origin, yaw, style))
    return result


def save_strip(images: list[Image.Image], path: Path):
    strip = Image.new("RGBA", (CELL, CELL * len(images)))
    for row, image in enumerate(images):
        strip.alpha_composite(image, (0, row * CELL))
    path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(path, "PNG", optimize=True)


def generate_first_slice():
    lengths = MODEL["table"]["rectangleLengths"]
    width = MODEL["table"]["canonicalWidth"]
    bands = ("small", "medium", "large")
    chair_layers = {
        style: {"far": [], "near": []}
        for style in ("ladder-back", "spindle-back", "curved-back")
    }
    for length, band in zip(lengths, bands):
        seats = rectangular_seats(length, width, band)
        for style, layers in chair_layers.items():
            layers["far"].append(composite_chairs(seats, "far", style))
            layers["near"].append(composite_chairs(seats, "near", style))
    chair_base = TARGET / "rectangle" / "chairs"
    for style, layers in chair_layers.items():
        save_strip(layers["far"], chair_base / f"{style}-far.png")
        save_strip(layers["near"], chair_base / f"{style}-near.png")

    edge_sets = {
        "rectangle": ("soft-square", "bullnose", "live-edge"),
        "oval": ("soft-square", "bullnose"),
    }
    for shape, edges in edge_sets.items():
        for base_style in MODEL["baseStyles"]:
            for edge_style in edges:
                tables = [draw_table(length, width, base_style, shape, edge_style) for length in lengths]
                save_strip(tables, TARGET / shape / base_style / f"table-{edge_style}.png")
        shape_chairs = TARGET / shape / "chairs"
        for style, layers in chair_layers.items():
            save_strip(layers["far"], shape_chairs / f"{style}-far.png")
            save_strip(layers["near"], shape_chairs / f"{style}-near.png")

    diameters = MODEL["table"]["circleDiameters"]
    circle_counts = (6, 8, 10)
    circle_chairs = {style: {"far": [], "near": []} for style in chair_layers}
    for diameter, count in zip(diameters, circle_counts):
        seats = round_seats(diameter, count)
        for style, layers in circle_chairs.items():
            layers["far"].append(composite_chairs(seats, "far", style))
            layers["near"].append(composite_chairs(seats, "near", style))
    for style, layers in circle_chairs.items():
        save_strip(layers["far"], TARGET / "circle" / "chairs" / f"{style}-far.png")
        save_strip(layers["near"], TARGET / "circle" / "chairs" / f"{style}-near.png")
    for base_style in MODEL["roundBaseStyles"]:
        for edge_style in ("soft-square", "bullnose"):
            tables = [draw_table(diameter, diameter, base_style, "circle", edge_style) for diameter in diameters]
            save_strip(tables, TARGET / "circle" / base_style / f"table-{edge_style}.png")


if __name__ == "__main__":
    generate_first_slice()
