from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import APP_NAME, APP_PRODUCT_NAME, APP_TITLE, APP_TOAST_APP_ID, APP_VERSION, AppConfig, load_config, normalize_time
from app import format_last_checked_at
from image_cache import ImageCacheService
from instagram_client import (
    InstagramPost,
    KST,
    MockInstagramClient,
    find_chrome_executable,
    refresh_runtime_instagram_session,
    is_plausible_shortcode,
    shortcode_from_permalink,
)
from main import (
    create_cached_post_from_state,
    create_lookup_failure_post,
    is_today_post,
    is_within_notification_window,
    notification_window_bounds,
    run_once,
)
from scheduler import COMMAND_TIMEOUT_SECONDS, run_command, task_target
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
    def test_star_icon_assets_are_multiresolution_and_transparent(self) -> None:
        from PIL import Image

        icon_path = ROOT / "assets" / "app_star_icon.ico"
        png_path = ROOT / "assets" / "app_star_icon.png"
        toast_path = ROOT / "assets" / "app_star_icon_toast.png"
        header_path = ROOT / "assets" / "app_star_installer_header.bmp"

        self.assertEqual(icon_path.read_bytes()[:4], b"\x00\x00\x01\x00")
        with Image.open(icon_path) as icon:
            sizes = set(icon.info.get("sizes", set()))
        self.assertTrue({(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}.issubset(sizes))
        for path in [png_path, toast_path]:
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getchannel("A").getextrema()[0], 0)
        with Image.open(header_path) as header:
            self.assertEqual(header.size, (150, 57))

    def test_legacy_icon_is_not_referenced_by_runtime_or_build_files(self) -> None:
        legacy_name = "app_" + "icon.ico"
        paths = [
            ROOT / "app.py",
            ROOT / "detail_window.py",
            ROOT / "toast_worker.py",
            ROOT / "build.ps1",
            ROOT / "StarRestaurantRadar.spec",
            ROOT / "installer" / "StarRestaurantRadar.nsi",
        ]
        for path in paths:
            self.assertNotIn(legacy_name, path.read_text(encoding="utf-8"), path.name)

    def test_normalize_time(self) -> None:
        self.assertEqual(normalize_time("10:00"), "10:00")
        self.assertEqual(normalize_time("9:5"), "09:05")
        self.assertEqual(normalize_time("nope"), "09:30")

    def test_default_notification_time_is_0930(self) -> None:
        self.assertEqual(AppConfig().notification_time, "09:30")

    def test_last_checked_at_is_formatted_for_people(self) -> None:
        kst = timezone(timedelta(hours=9))
        now = datetime(2026, 7, 2, 10, 0, tzinfo=kst)

        self.assertEqual(format_last_checked_at("2026-07-02T09:17:42+09:00", now), "오늘 오전 9:17")
        self.assertEqual(format_last_checked_at("2026-07-01T16:05:00+09:00", now), "어제 오후 4:05")
        self.assertEqual(
            format_last_checked_at("2026-06-30T13:02:00+09:00", now),
            "2026년 6월 30일 오후 1:02",
        )

    def test_notification_window_is_limited_to_one_hour_on_same_day(self) -> None:
        config = AppConfig(notification_time="10:00")
        self.assertFalse(is_within_notification_window(config, datetime(2026, 7, 1, 9, 59, tzinfo=KST)))
        self.assertTrue(is_within_notification_window(config, datetime(2026, 7, 1, 10, 0, tzinfo=KST)))
        self.assertTrue(is_within_notification_window(config, datetime(2026, 7, 1, 11, 0, tzinfo=KST)))
        self.assertFalse(is_within_notification_window(config, datetime(2026, 7, 1, 11, 0, 0, 1, tzinfo=KST)))

        late_config = AppConfig(notification_time="23:30")
        target_date = datetime(2026, 7, 1, tzinfo=KST).date()
        _start, end = notification_window_bounds(late_config, target_date)
        self.assertEqual(end.date(), target_date)
        self.assertFalse(is_within_notification_window(late_config, datetime(2026, 7, 2, 0, 10, tzinfo=KST)))

    def test_automatic_check_stops_before_fetch_outside_window(self) -> None:
        state_store = mock.Mock()
        with mock.patch("main.load_config", return_value=AppConfig(notification_time="10:00")), mock.patch(
            "main.setup_logging"
        ), mock.patch("main.StateStore", return_value=state_store), mock.patch("main.create_client") as client:
            result = run_once(now=datetime(2026, 7, 1, 11, 1, tzinfo=KST))

        self.assertEqual(result, 0)
        client.assert_not_called()
        self.assertIn("알림 가능 시간 아님", state_store.update.call_args_list[-1].kwargs["last_result"])

    def test_yesterday_post_is_not_automatically_notified_today(self) -> None:
        now = datetime(2026, 7, 1, 10, 30, tzinfo=KST)
        post = InstagramPost(
            post_id="Yesterday1",
            shortcode="Yesterday1",
            permalink="https://www.instagram.com/p/Yesterday1/",
            image_url=None,
            thumbnail_url=None,
            caption="yesterday",
            published_at=now - timedelta(days=1),
            media_type="image",
        )
        state_store = mock.Mock()
        client = mock.Mock()
        client.get_latest_post.return_value = post
        holiday = mock.Mock()
        holiday.should_run.return_value = (True, "ok")
        with mock.patch("main.load_config", return_value=AppConfig(notification_time="10:00")), mock.patch(
            "main.setup_logging"
        ), mock.patch("main.StateStore", return_value=state_store), mock.patch(
            "main.create_client", return_value=client
        ), mock.patch("main.HolidayService", return_value=holiday), mock.patch(
            "main.ToastService"
        ) as toast_service:
            result = run_once(now=now)

        self.assertEqual(result, 0)
        toast_service.assert_not_called()
        self.assertIn("오늘 게시물이 아니므로", state_store.update.call_args_list[-1].kwargs["last_result"])

    def test_today_post_check_uses_korean_date(self) -> None:
        now = datetime(2026, 7, 1, 10, 30, tzinfo=KST)
        post = InstagramPost("Today1", "Today1", "https://example.test", None, None, "", now, "image")
        self.assertTrue(is_today_post(post, now))

    def test_product_identity_is_starrestaurantradar(self) -> None:
        self.assertEqual(APP_NAME, "StarRestaurantRadar")
        self.assertEqual(APP_TITLE, "StarRestaurantRadar")
        self.assertEqual(APP_TOAST_APP_ID, "StarRestaurantRadar")
        self.assertEqual(APP_PRODUCT_NAME, "StarRestaurantRadar")
        self.assertEqual(APP_VERSION, "1.2.0")

    def test_scheduler_uses_noninteractive_source_check(self) -> None:
        executable, arguments = task_target()
        self.assertTrue(executable.lower().endswith(("pythonw.exe", "python.exe")))
        self.assertIn("app.py", arguments)
        self.assertIn("--run-once", arguments)

        install_task = (ROOT / "install_task.ps1").read_text(encoding="utf-8")
        self.assertIn('$NotifyTime = "09:30"', install_task)
        self.assertNotIn("--scheduled-check", install_task)

    def test_scheduler_command_timeout_returns_failure_instead_of_hanging(self) -> None:
        with mock.patch(
            "scheduler.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["slow-command"], COMMAND_TIMEOUT_SECONDS),
        ):
            result = run_command(["slow-command"])

        self.assertEqual(result.returncode, 124)
        self.assertIn("중단", result.stderr)

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
        self.assertTrue(AppConfig().only_today_posts)
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
        self.assertEqual(
            kwargs["icon"],
            {"placement": "appLogoOverride", "src": str(ROOT / "assets" / "app_star_icon_toast.png")},
        )
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
