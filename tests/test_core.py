from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import AppConfig, load_config, normalize_time
from instagram_client import (
    MockInstagramClient,
    refresh_runtime_instagram_session,
    is_plausible_shortcode,
    shortcode_from_permalink,
)
from main import create_cached_post_from_state, create_lookup_failure_post
from state_store import StateStore
from update_service import (
    ReleaseAsset,
    extract_sha256,
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

    def test_rejects_locale_as_shortcode(self) -> None:
        self.assertFalse(is_plausible_shortcode("en_US"))
        self.assertTrue(is_plausible_shortcode("C0ffee_Menu1"))

    def test_lookup_failure_post_points_to_profile(self) -> None:
        post = create_lookup_failure_post("@byeolsikdang")
        self.assertEqual(post.media_type, "lookup_failure")
        self.assertEqual(post.permalink, "https://www.instagram.com/byeolsikdang/")
        self.assertTrue(AppConfig().use_instagram_login_session)
        self.assertFalse(AppConfig().only_today_posts)
        self.assertFalse(AppConfig().start_on_boot)

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
                    "name": "Star-Restaurant-Radar-Setup-v1.0.1.exe.sha256",
                    "browser_download_url": "https://example.test/checksum",
                    "size": 64,
                },
                {
                    "name": "Star-Restaurant-Radar-Setup-v1.0.1.exe",
                    "browser_download_url": "https://example.test/installer",
                    "size": 123,
                },
            ],
        }

        update = parse_latest_release(release)

        self.assertIsNotNone(update)
        self.assertEqual(update.version, "1.0.1")
        self.assertEqual(update.installer_asset.name, "Star-Restaurant-Radar-Setup-v1.0.1.exe")
        self.assertEqual(update.checksum_asset.name, "Star-Restaurant-Radar-Setup-v1.0.1.exe.sha256")

    def test_update_installer_asset_selection_fallback(self) -> None:
        asset = select_installer_asset(
            [
                ReleaseAsset("notes.txt", "https://example.test/notes"),
                ReleaseAsset("Star-Restaurant-Radar-Setup.exe", "https://example.test/setup"),
            ]
        )

        self.assertIsNotNone(asset)
        self.assertEqual(asset.name, "Star-Restaurant-Radar-Setup.exe")

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
