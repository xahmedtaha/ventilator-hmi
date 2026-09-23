"""Colors, fonts, the Qt stylesheet and small widget helpers for the whole HMI.

Red, yellow and cyan are reserved for alarms (IEC 60601-1-8 alarm colors). Waveforms use green,
magenta and periwinkle; advisories (not alarms) use orange. The dark background suits ICU use and
keeps contrast high through VNC.
"""
from __future__ import annotations

from hmi.core.alarms.definitions import Priority
from hmi.qt import QtCore, QtGui, QtWidgets

BG = "#0b0f14"
SURFACE = "#141b24"
SURFACE_2 = "#1c2530"
BORDER = "#2a3645"
TEXT = "#e6edf3"
MUTED = "#8b98a5"
PRIMARY = "#4f6bff"
GO = "#1f9d55"
DANGER = "#8e2431"
ADVISORY = "#ff8a3d"
ALARM_COLORS = {Priority.HIGH: "#ff3b3b", Priority.MEDIUM: "#ffd000", Priority.LOW: "#22d3ee"}
ALARM_TEXT = {Priority.HIGH: "#ffffff", Priority.MEDIUM: "#111111", Priority.LOW: "#111111"}
WAVE_COLORS = {"pressure": "#7ee081", "flow": "#e879f9", "volume": "#a5b4fc"}

ALIGN_CENTER = QtCore.Qt.AlignmentFlag.AlignCenter

STYLESHEET = f"""
QMainWindow {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-size: 16px; }}
QLabel {{ background: transparent; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QPushButton {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
              padding: 6px 14px; min-height: 48px; font-size: 18px; color: {TEXT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: #55606c; background: #11161d; border-color: #1a222c; }}
QPushButton[role="primary"] {{ background: {PRIMARY}; border-color: {PRIMARY}; font-weight: 600; }}
QPushButton[role="go"] {{ background: {GO}; border-color: {GO}; font-weight: 700; }}
QPushButton[role="danger"] {{ background: {DANGER}; border-color: #b33a48; font-weight: 700; }}
QPushButton[role="toggle"]:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; font-weight: 600; }}
QPushButton[role="primary"]:disabled, QPushButton[role="go"]:disabled {{
    background: #11161d; border-color: #1a222c; color: #55606c; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: {SURFACE}; color: {MUTED}; padding: 12px 28px; margin-right: 6px;
               border-top-left-radius: 10px; border-top-right-radius: 10px; font-size: 18px; min-width: 150px; }}
QTabBar::tab:selected {{ background: {SURFACE_2}; color: {TEXT}; border-bottom: 3px solid {PRIMARY}; }}
QListWidget, QTableWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; gridline-color: {BORDER}; }}
QHeaderView::section {{ background: {SURFACE_2}; color: {MUTED}; border: none; padding: 6px; }}
QCheckBox {{ spacing: 12px; font-size: 18px; min-height: 44px; }}
QCheckBox::indicator {{ width: 28px; height: 28px; }}
QComboBox {{ min-height: 44px; font-size: 18px; padding: 4px 12px; background: {SURFACE_2};
            border: 1px solid {BORDER}; border-radius: 8px; }}
QScrollBar:vertical {{ width: 22px; background: {SURFACE}; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 8px; min-height: 40px; }}
"""


def apply_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    for r, color in ((role.Window, BG), (role.Base, SURFACE), (role.AlternateBase, SURFACE_2),
                     (role.Button, SURFACE_2), (role.Text, TEXT), (role.WindowText, TEXT),
                     (role.ButtonText, TEXT), (role.Highlight, PRIMARY), (role.HighlightedText, "#ffffff")):
        palette.setColor(r, QtGui.QColor(color))
    app.setPalette(palette)
    font = QtGui.QFont()
    font.setFamilies(["Segoe UI", "DejaVu Sans", "Noto Sans", "Arial"])
    font.setPixelSize(16)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)


def make_button(text: str, role: str | None = None) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    if role:
        button.setProperty("role", role)
    return button


def make_label(text: str = "", size: int = 16, bold: bool = False, muted: bool = False,
               color: str | None = None) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    style = [f"font-size: {size}px"]
    if bold:
        style.append("font-weight: 700")
    if muted or color:
        style.append(f"color: {color or MUTED}")
    label.setStyleSheet("; ".join(style) + ";")
    return label


def make_card() -> QtWidgets.QFrame:
    frame = QtWidgets.QFrame()
    frame.setObjectName("card")
    return frame


def transparent_for_mouse(*widgets: QtWidgets.QWidget) -> None:
    """Let clicks pass through labels placed inside a button."""
    for widget in widgets:
        widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
