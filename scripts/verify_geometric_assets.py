"""Verify generated configurator sprites retain the geometry/style contract."""

from collections import deque
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
GEOMETRIC_ASSETS = ROOT / "public" / "geometric-v1"
TABLE_ASSETS = ROOT / "public" / "style-v2" / "tables" / "strips"
COMPLETE_TABLE_MASTERS = ROOT / "public" / "style-v2" / "tables" / "complete-masters"
CHAIR_ASSETS = ROOT / "public" / "chairs" / "position-atlases"
CHAIR_VIEWS = ROOT / "public" / "chairs" / "position-views"
SHAPES = ("rectangle", "oval", "circle")
EDGE_PROFILES = {
    "rectangle": ("soft-square", "bullnose", "live-edge"),
    "oval": ("soft-square", "bullnose"),
    "circle": ("soft-square", "bullnose"),
}
CHAIRS = ("ladder-back", "spindle-back", "curved-back")
CELL_SIZE = 600
SAFETY_MARGIN = 3


def enclosed_openings(alpha):
    """Count substantial transparent openings enclosed by chair woodwork."""
    width, height = alpha.size
    pixels = alpha.load()
    visited = bytearray(width * height)
    openings = 0
    for y in range(height):
        for x in range(width):
            start = y * width + x
            if visited[start] or pixels[x, y] > 8:
                continue
            visited[start] = 1
            queue = deque([(x, y)])
            size = 0
            touches_border = False
            while queue:
                cx, cy = queue.popleft()
                size += 1
                touches_border |= cx in (0, width - 1) or cy in (0, height - 1)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    index = ny * width + nx
                    if visited[index] or pixels[nx, ny] > 8:
                        continue
                    visited[index] = 1
                    queue.append((nx, ny))
            if not touches_border and size > 1_000:
                openings += 1
    return openings


def main():
    failures = []
    straight_assets = list(TABLE_ASSETS.rglob("table-straight.png"))
    if straight_assets:
        failures.append(f"obsolete straight profile assets remain: {len(straight_assets)}")

    for shape, profiles in EDGE_PROFILES.items():
        for base_dir in sorted((TABLE_ASSETS / shape).glob("*")):
            for edge in profiles[1:]:
                master = COMPLETE_TABLE_MASTERS / shape / base_dir.name / f"table-{edge}.png"
                if not master.exists():
                    failures.append(f"missing complete master {master.relative_to(ROOT)}")
                    continue
                with Image.open(master) as image:
                    if image.mode != "RGBA" or image.getchannel("A").getextrema() != (0, 255):
                        failures.append(f"{master.relative_to(ROOT)} is not true-alpha RGBA")

    # Validate the assets used by the current three-layer compositor. Older
    # combined experiments can remain on disk without weakening this check.
    pngs = sorted(
        [path for path in GEOMETRIC_ASSETS.rglob("*.png")
         if path.name.startswith("table-") or path.parent.name == "chairs"]
        + list(TABLE_ASSETS.rglob("*.png"))
        + list(CHAIR_ASSETS.rglob("*.png"))
    )
    if not pngs:
        failures.append("no generated PNG assets found")

    for path in pngs:
        with Image.open(path) as image:
            if image.mode != "RGBA":
                failures.append(f"{path.relative_to(ROOT)} is not RGBA")
            if image.size != (600, 1800):
                failures.append(f"{path.relative_to(ROOT)} has size {image.size}")
            alpha = image.getchannel("A")
            for row in range(3):
                top = row * CELL_SIZE
                cell = alpha.crop((0, top, CELL_SIZE, top + CELL_SIZE))
                bounds = cell.getbbox()
                if bounds:
                    left, upper, right, lower = bounds
                    if (
                        left < SAFETY_MARGIN
                        or upper < SAFETY_MARGIN
                        or right > CELL_SIZE - SAFETY_MARGIN
                        or lower > CELL_SIZE - SAFETY_MARGIN
                    ):
                        failures.append(
                            f"{path.relative_to(ROOT)} row {row} artwork bounds "
                            f"{bounds} violate the {SAFETY_MARGIN}px safety margin"
                        )
                corners = ((0, top), (599, top), (0, top + 599), (599, top + 599))
                if any(alpha.getpixel(point) != 0 for point in corners):
                    failures.append(f"{path.relative_to(ROOT)} row {row} has a nontransparent corner")

                if TABLE_ASSETS in path.parents and bounds:
                    # Complete table drawings can have oval, circular, or
                    # irregular live-edge silhouettes, so a single inferred
                    # point is not a reliable surface test. The upper third of
                    # the artwork must instead contain a substantial opaque
                    # tabletop area.
                    table_height = max(1, lower - upper)
                    tabletop = cell.crop(
                        (left, upper, right, upper + max(1, table_height // 3))
                    )
                    opaque_pixels = sum(tabletop.histogram()[240:])
                    opaque_ratio = opaque_pixels / (tabletop.width * tabletop.height)
                    if opaque_ratio < 0.10:
                        failures.append(
                            f"{path.relative_to(ROOT)} row {row} has insufficient opaque "
                            f"tabletop coverage ({opaque_ratio:.1%})"
                        )

    for shape in SHAPES:
        for base_dir in sorted((TABLE_ASSETS / shape).glob("*")):
            profiles = []
            for edge in EDGE_PROFILES[shape]:
                path = base_dir / f"table-{edge}.png"
                if not path.exists():
                    failures.append(f"missing {path.relative_to(ROOT)}")
                    continue
                profiles.append((edge, Image.open(path).convert("RGBA")))
            for index, (edge, image) in enumerate(profiles):
                for other_edge, other in profiles[index + 1:]:
                    difference = ImageChops.difference(image, other)
                    changed = sum(difference.getchannel("A").histogram()[9:])
                    if changed < 250:
                        failures.append(
                            f"{shape}/{base_dir.name} edge profiles {edge} and {other_edge} "
                            f"are not visually distinct ({changed} changed alpha pixels)"
                        )

        for chair in CHAIRS:
            for layer in ("far", "near"):
                path = GEOMETRIC_ASSETS / shape / "chairs" / f"{chair}-{layer}.png"
                if not path.exists():
                    failures.append(f"missing {path.relative_to(ROOT)}")
            for layer in ("back", "front"):
                path = CHAIR_ASSETS / shape / f"{chair}-{layer}.png"
                if not path.exists():
                    failures.append(f"missing {path.relative_to(ROOT)}")

    minimum_openings = {"curved-back": 1, "ladder-back": 5, "spindle-back": 7}
    for chair, minimum in minimum_openings.items():
        for path in sorted(CHAIR_VIEWS.glob(f"{chair}-*.webp")):
            with Image.open(path) as image:
                openings = enclosed_openings(image.convert("RGBA").getchannel("A"))
            if openings < minimum:
                failures.append(
                    f"{path.relative_to(ROOT)} has {openings} transparent chair openings; "
                    f"expected at least {minimum}"
                )

    if failures:
        raise SystemExit("\n".join(failures))
    print(f"verified {len(pngs)} transparent geometry/style sprites")


if __name__ == "__main__":
    main()
