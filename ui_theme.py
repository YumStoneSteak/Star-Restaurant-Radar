from __future__ import annotations

from pathlib import Path


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
APP_ICON_PATH = ASSETS_DIR / "app_star_icon.ico"
APP_ICON_PNG_PATH = ASSETS_DIR / "app_star_icon.png"

NAVY = "#17324D"
MUTED = "#6B7B8C"
SUNNY = "#FFC83D"
SUNNY_HOVER = "#FFBA1F"
CREAM = "#FFF9EA"
WHITE = "#FFFFFF"
LINE = "#E4EAF0"


APP_QSS = f"""
QWidget {{
    color: {NAVY};
    background: {WHITE};
    font-family: "Segoe UI", "Malgun Gothic", sans-serif;
    font-size: 13px;
}}
QWidget#AppRoot, QWidget#DetailRoot {{
    background: {WHITE};
}}
QScrollArea#ContentScroll, QWidget#ScrollContent {{
    background: transparent;
    border: none;
}}
QFrame#SurfaceCard {{
    background-color: {CREAM};
    border: 1px solid #F0E4C7;
    border-radius: 16px;
}}
QFrame#StatusCard {{
    background-color: #F7F9FC;
    border: 1px solid {LINE};
    border-radius: 14px;
}}
QFrame#ButtonColumn, QFrame#HeaderFrame {{
    background: transparent;
    border: none;
}}
QLabel {{
    background: transparent;
}}
QLabel#BrandIcon {{
    background: transparent;
    border: none;
}}
QLabel#Title {{
    color: {NAVY};
    font-size: 22px;
    font-weight: 750;
}}
QLabel#DetailTitle {{
    color: {NAVY};
    font-size: 20px;
    font-weight: 750;
}}
QLabel#Subtitle {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#VersionBadge {{
    color: #8A6510;
    background: #FFF2C7;
    border: 1px solid #F4D97E;
    border-radius: 9px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 650;
}}
QLabel#SectionTitle {{
    color: {NAVY};
    font-size: 13px;
    font-weight: 700;
}}
QLabel#FieldLabel {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#TargetAccount {{
    color: {NAVY};
    background: {WHITE};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 7px 10px;
    font-weight: 700;
}}
QLabel#StatusBody {{
    color: #536576;
    font-size: 12px;
    line-height: 1.35;
}}
QLineEdit, QTimeEdit, QComboBox {{
    color: {NAVY};
    background-color: {WHITE};
    border: 1px solid #D6DEE7;
    border-radius: 10px;
    padding: 7px 10px;
    min-height: 24px;
    selection-background-color: {SUNNY};
    selection-color: {NAVY};
}}
QLineEdit:focus, QTimeEdit:focus, QComboBox:focus {{
    border: 2px solid {SUNNY};
    padding: 6px 9px;
}}
QTimeEdit::up-button, QTimeEdit::down-button {{
    width: 0;
    height: 0;
    border: none;
    background: transparent;
}}
QComboBox::drop-down {{
    border: none;
    width: 30px;
}}
QComboBox QAbstractItemView {{
    color: {NAVY};
    background-color: {WHITE};
    border: 1px solid {LINE};
    selection-background-color: #FFF1BF;
    selection-color: {NAVY};
}}
QCheckBox {{
    color: {NAVY};
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
}}
QCheckBox#AutoStartCheck {{
    color: {NAVY};
    background-color: #EAF2F8;
    border: 1px solid #BDD1E0;
    border-radius: 10px;
    padding: 7px 10px;
    font-weight: 650;
}}
QCheckBox#AutoStartCheck:hover {{
    background-color: #DFECF5;
    border-color: #AFC8DB;
}}
QPushButton {{
    color: {NAVY};
    background-color: {WHITE};
    border: 1px solid #D8E0E8;
    border-radius: 11px;
    padding: 9px 14px;
    min-height: 24px;
    font-weight: 650;
}}
QPushButton:hover {{
    background-color: #F7F9FC;
    border-color: #C8D2DD;
}}
QPushButton:pressed {{
    background-color: #EEF2F6;
}}
QPushButton:focus {{
    border: 2px solid {SUNNY};
    padding: 8px 13px;
}}
QPushButton:disabled {{
    color: #A9B3BD;
    background-color: #F4F6F8;
    border-color: #E6EAEE;
}}
QPushButton#PrimaryButton {{
    color: {NAVY};
    background-color: {SUNNY};
    border: 1px solid {SUNNY};
    font-weight: 750;
}}
QPushButton#PrimaryButton:hover {{
    background-color: {SUNNY_HOVER};
    border-color: {SUNNY_HOVER};
}}
QPushButton#PrimaryButton:pressed {{
    background-color: #F0A900;
    border-color: #F0A900;
}}
QPushButton#QuietButton {{
    color: #8E3440;
    background-color: #FDECEE;
    border: 1px solid #E9B8BF;
    min-height: 24px;
    padding: 9px 14px;
    font-weight: 700;
}}
QPushButton#QuietButton:hover {{
    color: #742832;
    background-color: #FADDE1;
    border-color: #D99AA4;
}}
QPushButton#QuietButton:pressed {{
    background-color: #F3C9CF;
    border-color: #CB818D;
}}
QLabel#ImagePreview {{
    color: {MUTED};
    background-color: #F7F9FC;
    border: 1px solid {LINE};
    border-radius: 15px;
}}
QMenu {{
    color: {NAVY};
    background: {WHITE};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 24px 7px 10px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: #FFF3C9;
}}
QScrollBar:vertical {{
    width: 8px;
    background: transparent;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    min-height: 28px;
    background: #D8E0E8;
    border-radius: 4px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QToolTip {{
    color: {NAVY};
    background: {WHITE};
    border: 1px solid {LINE};
    padding: 5px 7px;
}}
"""


def load_app_icon():  # type: ignore[no-untyped-def]
    from PySide6.QtGui import QIcon

    return QIcon(str(APP_ICON_PATH))


def brand_pixmap(size: int):  # type: ignore[no-untyped-def]
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap

    return QPixmap(str(APP_ICON_PNG_PATH)).scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def apply_light_theme(widget: object) -> None:
    try:
        from PySide6.QtCore import Qt

        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setStyleSheet(APP_QSS)
    except Exception:
        return
