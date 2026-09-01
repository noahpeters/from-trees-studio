"""Extract one camera-registered table cell per base for image style transfer."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public" / "geometric-v1"
TARGET = ROOT / "public" / "style-v2" / "table-references"


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for shape in ("rectangle", "oval", "circle"):
        shape_root = SOURCE / shape
        if not shape_root.exists():
            continue
        for base in sorted(path for path in shape_root.iterdir() if path.is_dir() and path.name != "chairs"):
            source = base / "table-soft-square.png"
            if not source.exists():
                continue
            strip = Image.open(source).convert("RGBA")
            row_height = strip.height // 3
            cell = strip.crop((0, row_height, strip.width, row_height * 2))
            cell.save(TARGET / f"{shape}--{base.name}.png", "PNG", optimize=True)


if __name__ == "__main__":
    main()
