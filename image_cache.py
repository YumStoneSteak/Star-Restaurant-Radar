from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import AppConfig
from instagram_client import InstagramPost

LOGGER = logging.getLogger(__name__)


class ImageCacheService:
    TOAST_IMAGE_ZOOM = 1.1

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.cache_dir = config.cache_path
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.toast_cache_dir = self.cache_dir / "toast"

    def cache_post_image(self, post: InstagramPost, allow_placeholder: bool = False) -> Path | None:
        if post.image_url:
            cached = self._download_image(post.image_url, post.post_id)
            if cached:
                return cached
        if allow_placeholder:
            return self._create_placeholder(post.post_id)
        return None

    def clear_cache(self) -> int:
        removed = 0
        for path in self.cache_dir.rglob("*"):
            if path.is_file():
                path.unlink()
                removed += 1
        for path in sorted((path for path in self.cache_dir.rglob("*") if path.is_dir()), reverse=True):
            try:
                path.rmdir()
            except OSError:
                pass
        return removed

    def create_toast_image(self, source_path: Path | None) -> Path | None:
        if not source_path or not source_path.exists():
            return None

        target = self.toast_cache_dir / f"{safe_filename(source_path.stem)}-toast.jpg"
        if target.exists() and target.stat().st_mtime >= source_path.stat().st_mtime:
            return target

        try:
            from PIL import Image, ImageOps
        except ImportError:
            LOGGER.info("Pillow is not installed; toast image zoom is skipped.")
            return None

        try:
            self.toast_cache_dir.mkdir(parents=True, exist_ok=True)
            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image)
                width, height = image.size
                if width <= 0 or height <= 0:
                    return None

                crop_width = max(1, round(width / self.TOAST_IMAGE_ZOOM))
                crop_height = max(1, round(height / self.TOAST_IMAGE_ZOOM))
                left = max(0, (width - crop_width) // 2)
                top = max(0, (height - crop_height) // 2)
                cropped = image.crop((left, top, left + crop_width, top + crop_height))
                resized = cropped.resize((width, height), Image.Resampling.LANCZOS)

                if resized.mode not in {"RGB", "L"}:
                    background = Image.new("RGB", resized.size, "#ffffff")
                    if "A" in resized.getbands():
                        background.paste(resized, mask=resized.getchannel("A"))
                    else:
                        background.paste(resized)
                    resized = background
                else:
                    resized = resized.convert("RGB")

                resized.save(target, format="JPEG", quality=90, optimize=True)
                return target
        except Exception:
            LOGGER.exception("Toast image zoom failed: %s", source_path)
            return None

    def _download_image(self, image_url: str, post_id: str) -> Path | None:
        suffix = self._guess_suffix(image_url)
        target = self.cache_dir / f"{safe_filename(post_id)}{suffix}"
        if target.exists():
            return target

        request = Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=15) as response:
                data = response.read()
        except (HTTPError, URLError, TimeoutError, OSError):
            LOGGER.exception("Image download failed: %s", image_url)
            return None

        try:
            target.write_bytes(data)
            self._resize_for_toast(target)
            return target
        except OSError:
            LOGGER.exception("Could not write cached image: %s", target)
            return None

    def _resize_for_toast(self, path: Path) -> None:
        if path.stat().st_size <= 1_000_000:
            return
        try:
            from PIL import Image
        except ImportError:
            LOGGER.info("Pillow is not installed; image resize is skipped.")
            return

        try:
            with Image.open(path) as image:
                image.thumbnail((1280, 1280))
                image.convert("RGB").save(path, format="JPEG", quality=82, optimize=True)
        except Exception:
            LOGGER.exception("Image resize failed: %s", path)

    def _create_placeholder(self, post_id: str) -> Path | None:
        target = self.cache_dir / f"{safe_filename(post_id)}.jpg"
        if target.exists():
            return target
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        image = Image.new("RGB", (960, 960), "#f5f1ea")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((70, 70, 890, 890), radius=36, fill="#ffffff", outline="#d6c7b3", width=4)
        draw.text((130, 310), "Byeolsikdang", fill="#2a2a2a")
        draw.text((130, 370), "Menu notification test", fill="#5f5a54")
        draw.text((130, 450), post_id, fill="#8c6f4f")
        image.save(target, format="JPEG", quality=88)
        return target

    def _guess_suffix(self, image_url: str) -> str:
        lowered = image_url.lower().split("?", 1)[0]
        for suffix in [".jpg", ".jpeg", ".png", ".webp"]:
            if lowered.endswith(suffix):
                return ".jpg" if suffix == ".jpeg" else suffix
        return ".jpg"


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "post"
