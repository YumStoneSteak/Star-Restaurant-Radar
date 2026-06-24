from __future__ import annotations

import json
import sys
import unittest
from unittest import mock
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import APP_NAME, APP_PRODUCT_NAME, APP_TITLE, APP_TOAST_APP_ID, APP_VERSION, AppConfig, load_config, normalize_time
from image_cache import ImageCacheService
from instagram_client import (
    MockInstagramClient,
    find_chrome_executable,
    refresh_runtime_instagram_session,
    is_plausible_shortcode,
    shortcode_from_permalink,
)
from main import create_cached_post_from_state, create_lookup_failure_post
from scheduler import task_target
from state_store import StateStore
from update_service import (
    ReleaseAsset,
    UpdateError,
    extract_sha256,
    fetch_latest_release,
    is_newer_version,
    parse_latest_release,
    select_installer_asset,
    verify_sha256_file,
)


class CoreTests(unittest.TestCase):
    def test_normalize_time(self) -> None:
        self.assertEqual(normalize_time("10:00"), "10:00")
        self.assertEqual(normalize_time("9:5"), "09:05")
        self.assertEqual(normalize_time("nope"), "10:00")

    def test_product_identity_is_starrestaurantradar(self) -> None:
        self.assertEqual(APP_NAME, "StarRestaurantRadar")
        self.assertEqual(APP_TITLE, "StarRestaurantRadar")
        self.assertEqual(APP_TOAST_APP_ID, "StarRestaurantRadar")
        self.assertEqual(APP_PRODUCT_NAME, "StarRestaurantRadar")
        self.assertEqual(APP_VERSION, "1.1.0")

    def test_scheduler_starts_tray_visible_check(self) -> None:
        _executable, arguments = task_target()
        self.assertIn("--scheduled-check", arguments)
        self.assertNotIn("main.py", arguments)

    def test_config_loads_defaults_for_broken_json(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            path = tmp_path / "config.json"
            path.write_text("{broken", encoding="utf-8")
            config = load_config(path)
            self.assertEqual(config.instagram_username, "byeolsikdang")
            self.assertTrue(path.exists())
            self.assertTrue(list(tmp_path.glob("config.json.broken-*.bak")))

    def test_state_store_recovers_broken_json(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            path = tmp_path / "state.json"
            path.write_text("{broken", encoding="utf-8")
            state = StateStore(path).load()
            self.assertIsNone(state["last_checked_at"])
            self.assertTrue(list(tmp_path.glob("state.json.broken-*.bak")))

    def test_mock_client_returns_today_menu_post(self) -> None:
        post = MockInstagramClient(AppConfig()).get_latest_post("byeolsikdang")
        self.assertTrue(post.post_id.startswith("mock-"))
        self.assertTrue(post.permalink.startswith("https://www.instagram.com/p/"))
        self.assertIsNotNone(post.published_at)

    def test_browser_lookup_accepts_edge_env_fallback(self) -> None:
        import os
        import tempfile

        previous = {name: os.environ.get(name) for name in ["CHROME", "CHROME_PATH", "EDGE", "MSEDGE"]}
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                edge_path = Path(temp_dir) / "msedge.exe"
                edge_path.write_bytes(b"edge")
                os.environ.pop("CHROME", None)
                os.environ.pop("CHROME_PATH", None)
                os.environ["EDGE"] = str(edge_path)
                os.environ.pop("MSEDGE", None)

                self.assertEqual(find_chrome_executable(), str(edge_path))
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_rejects_locale_as_shortcode(self) -> None:
        self.assertFalse(is_plausible_shortcode("en_US"))
        self.assertTrue(is_plausible_shortcode("C0ffee_Menu1"))

    def test_lookup_failure_post_points_to_profile(self) -> None:
        post = create_lookup_failure_post("@byeolsikdang")
        self.assertEqual(post.media_type, "lookup_failure")
        self.assertEqual(post.permalink, "https://www.instagram.com/byeolsikdang/")
        self.assertTrue(AppConfig().use_instagram_login_session)
        self.assertFalse(AppConfig().only_today_posts)
        self.assertTrue(AppConfig().start_on_boot)

    def test_shortcode_from_post_or_reel_permalink(self) -> None:
        self.assertEqual(shortcode_from_permalink("https://www.instagram.com/p/C0ffee_Menu1/"), "C0ffee_Menu1")
        self.assertEqual(shortcode_from_permalink("https://www.instagram.com/reel/ABC123_def/"), "ABC123_def")
        self.assertEqual(shortcode_from_permalink("https://www.instagram.com/byeolsikdang/p/DZJZutHt7YA/"), "DZJZutHt7YA")
        self.assertIsNone(shortcode_from_permalink("https://www.instagram.com/byeolsikdang/"))

    def test_runtime_session_copy_skips_locks_and_caches(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "instagram_session"
            runtime = Path(temp_dir) / "instagram_session_runtime"
            (source / "Default" / "Network").mkdir(parents=True)
            (source / "Default" / "Cache").mkdir(parents=True)
            (source / "Default" / "Service Worker" / "CacheStorage").mkdir(parents=True)
            (source / "Default" / "Network" / "Cookies").write_text("cookies", encoding="utf-8")
            (source / "Default" / "Cache" / "data").write_text("cache", encoding="utf-8")
            (source / "Default" / "Service Worker" / "CacheStorage" / "data").write_text("cache", encoding="utf-8")
            (source / "SingletonLock").write_text("locked", encoding="utf-8")

            refresh_runtime_instagram_session(source, runtime)

            self.assertEqual((runtime / "Default" / "Network" / "Cookies").read_text(encoding="utf-8"), "cookies")
            self.assertFalse((runtime / "Default" / "Cache").exists())
            self.assertFalse((runtime / "Default" / "Service Worker").exists())
            self.assertFalse((runtime / "SingletonLock").exists())

    def test_cached_post_recovers_from_latest_cache_image(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            image_path = cache_dir / "DZoQZmjN8n6.jpg"
            image_path.write_bytes(b"image")

            cached = create_cached_post_from_state(AppConfig(cache_dir=str(cache_dir)), {})

            self.assertIsNotNone(cached)
            post, resolved_image_path = cached
            self.assertEqual(post.post_id, "DZoQZmjN8n6")
            self.assertEqual(post.permalink, "https://www.instagram.com/p/DZoQZmjN8n6/")
            self.assertEqual(resolved_image_path, image_path)

    def test_toast_worker_uses_app_id_and_hero_image(self) -> None:
        import tempfile
        import types

        import toast_worker

        calls = []

        def fake_toast(*args, **kwargs):
            calls.append((args, kwargs))

        sentinel = object()
        previous_win11toast = sys.modules.get("win11toast", sentinel)
        sys.modules["win11toast"] = types.SimpleNamespace(toast=fake_toast)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                image_path = Path(temp_dir) / "menu.jpg"
                image_path.write_bytes(b"image")

                toast_worker.show_toast("title", "body", "https://example.test/post", str(image_path))
        finally:
            if previous_win11toast is sentinel:
                sys.modules.pop("win11toast", None)
            else:
                sys.modules["win11toast"] = previous_win11toast

        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(args, ("title", "body"))
        self.assertEqual(kwargs["app_id"], APP_TOAST_APP_ID)
        self.assertEqual(kwargs["image"], {"placement": "hero", "src": str(image_path)})

    def test_toast_image_zoom_keeps_original_and_writes_toast_cache(self) -> None:
        import tempfile

        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            source_path = cache_dir / "DZoQZmjN8n6.jpg"
            image = Image.new("RGB", (110, 100), "#ffffff")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 15, 99), fill="#ff0000")
            draw.rectangle((16, 0, 94, 99), fill="#00ff00")
            draw.rectangle((95, 0, 109, 99), fill="#0000ff")
            image.save(source_path, format="JPEG", quality=95)
            original_bytes = source_path.read_bytes()

            toast_path = ImageCacheService(AppConfig(cache_dir=str(cache_dir))).create_toast_image(source_path)

            self.assertIsNotNone(toast_path)
            assert toast_path is not None
            self.assertEqual(toast_path.parent, cache_dir / "toast")
            self.assertEqual(toast_path.name, "DZoQZmjN8n6-toast.jpg")
            self.assertTrue(toast_path.exists())
            self.assertEqual(source_path.read_bytes(), original_bytes)
            with Image.open(toast_path) as toast_image:
                self.assertEqual(toast_image.size, (110, 100))
            self.assertNotEqual(toast_path.read_bytes(), original_bytes)

    def test_clear_cache_removes_toast_cache_files(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            toast_dir = cache_dir / "toast"
            toast_dir.mkdir(parents=True)
            (cache_dir / "DZoQZmjN8n6.jpg").write_bytes(b"original")
            (toast_dir / "DZoQZmjN8n6-toast.jpg").write_bytes(b"toast")

            removed = ImageCacheService(AppConfig(cache_dir=str(cache_dir))).clear_cache()

            self.assertEqual(removed, 2)
            self.assertFalse(any(cache_dir.rglob("*")))

    def test_update_version_comparison(self) -> None:
        self.assertTrue(is_newer_version("v1.0.1", "1.0.0"))
        self.assertFalse(is_newer_version("v1.0.0", "1.0.0"))
        self.assertFalse(is_newer_version("0.9.9", "1.0.0"))

    def test_update_release_parsing_selects_installer_and_checksum(self) -> None:
        release = {
            "tag_name": "v1.0.1",
            "html_url": "https://github.com/YumStoneSteak/Star-Restaurant-Radar/releases/tag/v1.0.1",
            "assets": [
                {
                    "name": "StarRestaurantRadar-Setup-v1.0.1.exe.sha256",
                    "browser_download_url": "https://example.test/checksum",
                    "size": 64,
                },
                {
                    "name": "StarRestaurantRadar-Setup-v1.0.1.exe",
                    "browser_download_url": "https://example.test/installer",
                    "size": 123,
                },
            ],
        }

        update = parse_latest_release(release)

        self.assertIsNotNone(update)
        self.assertEqual(update.version, "1.0.1")
        self.assertEqual(update.installer_asset.name, "StarRestaurantRadar-Setup-v1.0.1.exe")
        self.assertEqual(update.checksum_asset.name, "StarRestaurantRadar-Setup-v1.0.1.exe.sha256")

    def test_update_installer_asset_selection_fallback(self) -> None:
        asset = select_installer_asset(
            [
                ReleaseAsset("notes.txt", "https://example.test/notes"),
                ReleaseAsset("StarRestaurantRadar-Setup.exe", "https://example.test/setup"),
            ]
        )

        self.assertIsNotNone(asset)
        self.assertEqual(asset.name, "StarRestaurantRadar-Setup.exe")

    def test_fetch_latest_release_uses_ssl_context(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps({"tag_name": "v1.1.0", "assets": []}).encode("utf-8")

        ssl_context = object()

        with mock.patch("update_service.create_ssl_context", return_value=ssl_context), mock.patch(
            "update_service.urlopen", return_value=FakeResponse()
        ) as mocked_urlopen:
            release = fetch_latest_release(timeout=7)

        self.assertEqual(release["tag_name"], "v1.1.0")
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 7)
        self.assertIs(mocked_urlopen.call_args.kwargs["context"], ssl_context)

    def test_fetch_latest_release_certificate_error_message(self) -> None:
        with mock.patch(
            "update_service.urlopen",
            side_effect=URLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"),
        ):
            with self.assertRaises(UpdateError) as error:
                fetch_latest_release()

        self.assertIn("인증서 검증", str(error.exception))

    def test_sha256_extraction_and_verification(self) -> None:
        import hashlib
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "installer.exe"
            path.write_bytes(b"installer")
            digest = hashlib.sha256(b"installer").hexdigest()

            self.assertEqual(extract_sha256(f"{digest}  installer.exe"), digest)
            verify_sha256_file(path, f"{digest}  installer.exe")


if __name__ == "__main__":
    unittest.main()
