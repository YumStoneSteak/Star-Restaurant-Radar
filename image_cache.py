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
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.cache_dir = config.cache_path
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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
        for path in self.cache_dir.glob("*"):
            if path.is_file():
                path.unlink()
                removed += 1
        return removed

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

