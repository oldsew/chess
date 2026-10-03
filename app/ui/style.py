"""Shared neutral desktop surfaces and semantic, text-first position colors."""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton

ADVANTAGE_COLORS = {-3: '#e77972', -2: '#da9992', -1: '#d2b2ac', 0: '#dddcd6',
                     1: '#b8ccad', 2: '#91bd99', 3: '#6fcb92'}

STYLE = """
QWidget { background: #222321; color: #e5e3dc; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
QLabel#title { font-size: 24px; font-weight: 600; }
QLabel#subtitle, QLabel#clockOwner { color: #aaa9a1; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #41423d,stop:0.08 #393a35,stop:1 #30312d);
 border: 1px solid #51524b; border-top-color: #65665d; border-radius: 7px; padding: 8px 13px; min-height: 18px; }
QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4a4b44,stop:1 #3a3b35); border-color: #727268; }
QPushButton:pressed { background: #292a26; border-top-color: #33342e; padding-top: 9px; padding-bottom: 7px; }
QPushButton:focus { border-color: #b4b09b; }
QPushButton:disabled { color: #77786f; background: #2b2c28; border-color: #3a3b35; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #626952,stop:1 #434c3b); border-color: #7b8567; }
QPushButton#primary:hover { background: #58634b; }
QPushButton#primary:pressed { background: #39422f; }
QPushButton#primary:disabled { background: #30332a; border-color: #484c3d; color: #868b7d; }
QComboBox, QSpinBox { padding: 6px 8px; background: #30312d; border: 1px solid #52534b; border-radius: 6px; min-height: 18px; }
QComboBox:disabled, QSpinBox:disabled { color: #85867c; border-color: #3b3c36; }
QComboBox QAbstractItemView { background: #30312d; selection-background-color: #54574a; }
QListWidget, QTextEdit, QTableWidget { background: #292a26; border: 1px solid #494a42; border-radius: 7px; padding: 4px; }
QListWidget::item { padding: 3px; }
QListWidget::item:selected { background: #505648; color: #f0eee7; border-radius: 4px; }
QTableView { selection-background-color: #505648; selection-color: #f0eee7; gridline-color: #41423a; }
QHeaderView::section { background: #353630; padding: 6px; border: 1px solid #494a42; }
QSplitter::handle { background: #222321; width: 6px; }
QScrollArea { border: 1px solid #494a42; border-radius: 7px; background: #292a26; }
QScrollArea QWidget#coachPanel { background: #292a26; }
QScrollArea#sidebarScroll { border: none; background: #222321; }
QFrame#clockPanel { background: #2d2e29; border: 1px solid #494a42; border-radius: 7px; }
QFrame#clockPanel[active="true"] { background: #343a2e; border-color: #83916c; }
QLabel#clockOwner { font-size: 12px; }
QLabel#clockTime { font-size: 24px; font-weight: 600; }
QLabel#positionIndicator { padding: 7px 8px; font-size: 13px; background: #2b2d27; border: 1px solid #43473b; border-radius: 7px; }
QLabel#sectionTitle { font-size: 12px; color: #aaa99c; font-weight: 600; padding-top: 6px; }
QLabel#playedMove { font-size: 18px; font-weight: 600; }
QLabel#coachAdvice { padding: 6px 0; }
QLabel#recommendation { color: #bdcfac; padding: 5px 0; }
QLabel#coachSummary[severity="error"] { color: #ddb2a8; }
QLabel#coachSummary[severity="good"] { color: #b6cba7; }
QToolTip { background: #393a34; color: #e5e3dc; border: 1px solid #68695e; padding: 5px; }
"""


def soften_primary_button(button: QPushButton):
    # A single small shadow on the main action; no effects on the board or animated pieces.
    shadow = QGraphicsDropShadowEffect(button)
    shadow.setBlurRadius(9)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 60))
    button.setGraphicsEffect(shadow)


def show_advantage(label, indicator, active=True):
    level = indicator.level
    if indicator.debug.get('mate_winner') is not None:
        level = 3 if indicator.text == 'У вас решающее преимущество' else -3
    ink = ADVANTAGE_COLORS[level] if active else ADVANTAGE_COLORS[0]
    label.setStyleSheet(f'color: {ink};')
    label.setProperty('advantageLevel', level if active else 0)
