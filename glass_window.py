from __future__ import annotations


APP_QSS = """
QWidget {
    color: #f7f2ea;
    font-family: "Segoe UI", "Malgun Gothic", sans-serif;
    font-size: 14px;
}
QWidget#GlassRoot {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(42, 48, 58, 235),
        stop:0.55 rgba(47, 63, 76, 225),
        stop:1 rgba(95, 75, 62, 230));
    border-radius: 24px;
}
QScrollArea#ContentScroll, QWidget#ScrollContent {
    background: transparent;
    border: none;
}
QFrame#GlassCard {
    background-color: rgba(255, 255, 255, 34);
    border: 1px solid rgba(255, 255, 255, 78);
    border-radius: 22px;
}
QFrame#ButtonColumn {
    background: transparent;
    border: none;
}
QLabel#Title {
    font-size: 28px;
    font-weight: 700;
}
QLabel#Subtitle {
    color: rgba(247, 242, 234, 190);
}
QLineEdit, QTimeEdit, QComboBox {
    background-color: rgba(255, 255, 255, 38);
    border: 1px solid rgba(255, 255, 255, 80);
    border-radius: 12px;
    padding: 8px 10px;
    min-height: 26px;
}
QComboBox::drop-down {
    border: none;
    width: 34px;
}
QComboBox QAbstractItemView {
    background-color: rgba(48, 56, 66, 245);
    border: 1px solid rgba(255, 255, 255, 80);
    selection-background-color: rgba(255, 255, 255, 58);
}
QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 6px 10px;
}
QCheckBox {
    spacing: 9px;
}
QPushButton {
    background-color: rgba(255, 255, 255, 46);
    border: 1px solid rgba(255, 255, 255, 96);
    border-radius: 16px;
    padding: 9px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: rgba(255, 255, 255, 70);
}
QPushButton:pressed {
    background-color: rgba(255, 255, 255, 38);
}
QTextEdit {
    background-color: rgba(255, 255, 255, 28);
    border: 1px solid rgba(255, 255, 255, 62);
    border-radius: 18px;
    padding: 10px;
}
"""


def apply_glass_effect(widget: object) -> None:
    try:
        from PySide6.QtCore import Qt

        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    except Exception:
        return
