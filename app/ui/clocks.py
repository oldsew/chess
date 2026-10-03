from __future__ import annotations

import math

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


def format_time(seconds: float | None):
    if seconds is None:
        return '∞'
    seconds = max(0, seconds)
    if seconds < 10:
        return f'0:{math.ceil(seconds * 10) / 10:04.1f}'
    whole = math.ceil(seconds)
    return f'{whole // 60}:{whole % 60:02d}'


class ClockPanel(QFrame):
    def __init__(self, name: str):
        super().__init__()
        self.setObjectName('clockPanel')
        self.setProperty('active', False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 8)
        layout.setSpacing(1)
        self.owner = QLabel(name)
        self.owner.setObjectName('clockOwner')
        self.time = QLabel('∞')
        self.time.setObjectName('clockTime')
        self.time.setAccessibleName(name)
        layout.addWidget(self.owner)
        layout.addWidget(self.time)

    def show_clock(self, owner: str, seconds: float | None, active: bool):
        self.owner.setText(owner)
        self.time.setText(format_time(seconds))
        if self.property('active') != active:
            self.setProperty('active', active)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
