from __future__ import annotations

import argparse
from pathlib import Path

from config import APP_TOAST_APP_ID


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a Windows toast notification.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--permalink", default="")
    parser.add_argument("--image", default="")
    args = parser.parse_args()

    show_toast(args.title, args.body, args.permalink, args.image)
    return 0


def show_toast(title: str, body: str, permalink: str = "", image: str = "") -> None:
    from win11toast import toast

    kwargs: dict[str, object] = {"duration": "short", "app_id": APP_TOAST_APP_ID}
    if permalink:
        kwargs["on_click"] = permalink
        kwargs["button"] = {
            "activationType": "protocol",
            "arguments": permalink,
            "content": "인스타그램에서 보기",
        }
    image_path = Path(image) if image else None
    if image_path and image_path.exists():
        kwargs["image"] = {"placement": "hero", "src": str(image_path)}

    try:
        toast(title, body, **kwargs)
    except Exception:
        toast(title, body, duration="short", app_id=APP_TOAST_APP_ID)


if __name__ == "__main__":
    raise SystemExit(main())
