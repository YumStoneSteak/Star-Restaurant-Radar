from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"
SOURCE_PATH = ASSETS_DIR / "app_star_icon_source.png"
ICO_PATH = ASSETS_DIR / "app_star_icon.ico"
PNG_PATH = ASSETS_DIR / "app_star_icon.png"
TOAST_PATH = ASSETS_DIR / "app_star_icon_toast.png"
NSIS_HEADER_PATH = ASSETS_DIR / "app_star_installer_header.bmp"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def preserve_source() -> None:
    if SOURCE_PATH.exists():
        return
    if not ICO_PATH.exists():
        raise FileNotFoundError(f"아이콘 원본을 찾을 수 없습니다: {ICO_PATH}")
    SOURCE_PATH.write_bytes(ICO_PATH.read_bytes())


def normalized_artwork(source: Image.Image, margin_ratio: float = 0.09) -> Image.Image:
    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    thresholded = alpha.point(lambda value: 255 if value >= 6 else 0)
    bbox = thresholded.getbbox() or alpha.getbbox()
    if bbox is None:
        raise ValueError("아이콘 원본에 보이는 픽셀이 없습니다.")

    cropped = rgba.crop(bbox)
    artwork_size = max(cropped.size)
    margin = max(1, round(artwork_size * margin_ratio))
    canvas_size = artwork_size + margin * 2
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    offset = ((canvas_size - cropped.width) // 2, (canvas_size - cropped.height) // 2)
    canvas.alpha_composite(cropped, offset)
    return canvas


def contain(image: Image.Image, size: tuple[int, int], padding: int = 0) -> Image.Image:
    target = Image.new("RGBA", size, (255, 255, 255, 0))
    available = (max(1, size[0] - padding * 2), max(1, size[1] - padding * 2))
    scaled = image.copy()
    scaled.thumbnail(available, Image.Resampling.LANCZOS)
    target.alpha_composite(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2))
    return target


def generate_assets() -> None:
    preserve_source()
    with Image.open(SOURCE_PATH) as source:
        artwork = normalized_artwork(source)

    png = contain(artwork, (512, 512), padding=18)
    png.save(PNG_PATH, format="PNG", optimize=True)

    toast = contain(artwork, (128, 128), padding=5)
    toast.save(TOAST_PATH, format="PNG", optimize=True)

    ico_source = contain(artwork, (1024, 1024), padding=24)
    ico_source.save(ICO_PATH, format="ICO", sizes=[(size, size) for size in ICO_SIZES])

    header = Image.new("RGB", (150, 57), "#FFF8E7")
    header_icon = contain(artwork, (52, 52), padding=1)
    header.paste(header_icon, (94, 2), header_icon)
    header.save(NSIS_HEADER_PATH, format="BMP")


def validate_assets() -> None:
    if ICO_PATH.read_bytes()[:4] != b"\x00\x00\x01\x00":
        raise ValueError("app_star_icon.ico가 정식 ICO 형식이 아닙니다.")
    with Image.open(ICO_PATH) as icon:
        sizes = set(icon.info.get("sizes", set()))
    required = {(size, size) for size in (16, 32, 48, 64, 128, 256)}
    if not required.issubset(sizes):
        raise ValueError(f"ICO 해상도가 부족합니다: {sorted(sizes)}")
    with Image.open(PNG_PATH) as png:
        if png.mode != "RGBA" or png.getchannel("A").getextrema()[0] != 0:
            raise ValueError("UI용 PNG에 투명 배경이 없습니다.")
    with Image.open(NSIS_HEADER_PATH) as header:
        if header.size != (150, 57):
            raise ValueError(f"NSIS 헤더 크기가 올바르지 않습니다: {header.size}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate StarRestaurantRadar icon assets.")
    parser.add_argument("--check", action="store_true", help="Validate existing generated assets only.")
    args = parser.parse_args()
    if not args.check:
        generate_assets()
    validate_assets()
    print("Star icon assets are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
