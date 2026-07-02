from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from config import load_config
from state_store import StateStore


def run_detail(post_id: str | None = None, smoke_test: bool = False) -> int:
    try:
        from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
    except ImportError:
        print("PySide6가 설치되어 있지 않습니다. requirements.txt를 설치한 뒤 다시 실행해 주세요.")
        return 1

    from ui_theme import apply_light_theme, brand_pixmap, load_app_icon

    class DetailWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.config = load_config()
            self.state = StateStore().load()
            self.permalink = self.state.get("last_permalink") or f"https://www.instagram.com/{self.config.instagram_username}/"
            self.setObjectName("DetailRoot")
            self.setWindowTitle("오늘의 별식당 메뉴")
            self.setWindowIcon(load_app_icon())
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.setMinimumSize(460, 560)
            self.resize(500, 640)
            apply_light_theme(self)

            root = QVBoxLayout(self)
            root.setContentsMargins(20, 18, 20, 20)
            root.setSpacing(12)

            header = QFrame()
            header.setObjectName("HeaderFrame")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(2, 0, 2, 0)
            header_layout.setSpacing(11)
            icon = QLabel()
            icon.setObjectName("BrandIcon")
            icon.setFixedSize(48, 48)
            icon.setPixmap(brand_pixmap(46))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(icon)
            header_copy = QVBoxLayout()
            header_copy.setSpacing(1)
            title = QLabel("오늘의 별식당 메뉴")
            title.setObjectName("DetailTitle")
            subtitle = QLabel("새 메뉴를 가볍게 확인해 보세요.")
            subtitle.setObjectName("Subtitle")
            header_copy.addWidget(title)
            header_copy.addWidget(subtitle)
            header_layout.addLayout(header_copy, 1)
            root.addWidget(header)

            card = QFrame()
            card.setObjectName("SurfaceCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 16, 16, 14)
            layout.setSpacing(10)

            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setMinimumHeight(320)
            image_label.setObjectName("ImagePreview")
            image_path = self.state.get("last_image_path")
            if image_path and Path(image_path).exists():
                pixmap = QPixmap(image_path)
                image_label.setPixmap(
                    pixmap.scaled(
                        430,
                        350,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                image_label.setText("이미지가 없으면 Instagram 링크로 안내해 드려요.")
            image_label.mousePressEvent = lambda event: self.open_link()
            layout.addWidget(image_label, 1)

            posted = QLabel(f"게시물 ID  {post_id or self.state.get('last_notified_post_id') or '-'}")
            posted.setObjectName("Subtitle")
            layout.addWidget(posted)

            link = QLabel(self.permalink)
            link.setWordWrap(True)
            link.setMinimumHeight(56)
            link.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            link.setObjectName("Subtitle")
            layout.addWidget(link)

            buttons = QHBoxLayout()
            buttons.setSpacing(8)
            open_button = QPushButton("Instagram에서 보기")
            open_button.setObjectName("PrimaryButton")
            open_button.clicked.connect(self.open_link)
            close_button = QPushButton("닫기")
            close_button.setObjectName("QuietButton")
            close_button.clicked.connect(self.close)
            buttons.addWidget(open_button, 1)
            buttons.addWidget(close_button)
            layout.addLayout(buttons)

            root.addWidget(card, 1)
            self.animation = QPropertyAnimation(self, b"windowOpacity")
            self.animation.setDuration(220)
            self.animation.setStartValue(0.0)
            self.animation.setEndValue(1.0)
            self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            super().showEvent(event)
            self.animation.start()

        def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            if event.key() == Qt.Key.Key_Escape:
                self.close()
            else:
                super().keyPressEvent(event)

        def open_link(self) -> None:
            webbrowser.open(self.permalink)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationDisplayName("오늘의 별식당 메뉴")
    app.setWindowIcon(load_app_icon())
    window = DetailWindow()
    window.show()
    if smoke_test:
        app.processEvents()
        failures = []
        if window.objectName() != "DetailRoot":
            failures.append("detail light theme root is missing")
        if window.windowIcon().isNull():
            failures.append("detail window icon is missing")
        buttons = window.findChildren(QPushButton)
        if not any(button.objectName() == "PrimaryButton" for button in buttons):
            failures.append("detail primary button style is missing")
        for widget_class in [QLabel, QPushButton]:
            for widget in window.findChildren(widget_class):
                if widget.isVisible() and widget.height() + 1 < widget.sizeHint().height():
                    label = widget.text() if hasattr(widget, "text") else widget.__class__.__name__
                    failures.append(
                        f"detail widget is clipped: {label} height={widget.height()} hint={widget.sizeHint().height()}"
                    )
        window.close()
        if failures:
            print("Detail layout smoke test failed:")
            for failure in failures:
                print(f"- {failure}")
            return 1
        print("Detail layout smoke test passed")
        return 0
    return app.exec()


if __name__ == "__main__":
    post_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(run_detail(post_id_arg))
