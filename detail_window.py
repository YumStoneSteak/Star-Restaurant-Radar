from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from config import load_config
from state_store import StateStore


def run_detail(post_id: str | None = None) -> int:
    try:
        from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
    except ImportError:
        print("PySide6가 설치되어 있지 않습니다. requirements.txt를 설치한 뒤 다시 실행해 주세요.")
        return 1

    class DetailWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.config = load_config()
            self.state = StateStore().load()
            self.permalink = self.state.get("last_permalink") or f"https://www.instagram.com/{self.config.instagram_username}/"
            self.setObjectName("GlassRoot")
            self.setWindowTitle("오늘의 별식당 메뉴")
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.setMinimumWidth(460)
            self.setStyleSheet(_detail_qss())

            root = QVBoxLayout(self)
            root.setContentsMargins(18, 18, 18, 18)
            card = QFrame()
            card.setObjectName("GlassCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(22, 22, 22, 22)
            layout.setSpacing(14)

            title = QLabel("오늘의 별식당 메뉴")
            title.setObjectName("Title")
            layout.addWidget(title)

            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setMinimumHeight(320)
            image_label.setObjectName("ImagePreview")
            image_path = self.state.get("last_image_path")
            if image_path and Path(image_path).exists():
                pixmap = QPixmap(image_path)
                image_label.setPixmap(pixmap.scaledToWidth(420, Qt.TransformationMode.SmoothTransformation))
            else:
                image_label.setText("이미지 없이 링크만 표시합니다.")
            image_label.mousePressEvent = lambda event: self.open_link()
            layout.addWidget(image_label)

            posted = QLabel(f"게시물 ID: {post_id or self.state.get('last_notified_post_id') or '-'}")
            posted.setObjectName("Subtitle")
            layout.addWidget(posted)

            link = QLabel(self.permalink)
            link.setWordWrap(True)
            link.setObjectName("Subtitle")
            layout.addWidget(link)

            buttons = QHBoxLayout()
            open_button = QPushButton("인스타그램에서 보기")
            open_button.clicked.connect(self.open_link)
            close_button = QPushButton("닫기")
            close_button.clicked.connect(self.close)
            buttons.addWidget(open_button)
            buttons.addWidget(close_button)
            layout.addLayout(buttons)

            root.addWidget(card)
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
    window = DetailWindow()
    window.show()
    return app.exec()


def _detail_qss() -> str:
    from glass_window import APP_QSS

    return (
        APP_QSS
        + """
QLabel#ImagePreview {
    background-color: rgba(255, 255, 255, 34);
    border: 1px solid rgba(255, 255, 255, 78);
    border-radius: 22px;
}
"""
    )


if __name__ == "__main__":
    post_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(run_detail(post_id_arg))

