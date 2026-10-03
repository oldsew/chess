from __future__ import annotations

import chess
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QFont
from PySide6.QtWidgets import QWidget

from app.services.material import MaterialSnapshot


class MaterialStrip(QWidget):
    """Small SVG strips above/below the board, sharing its renderers and orientation."""
    def __init__(self, renderers):
        super().__init__()
        self.renderers = renderers
        self.setFixedHeight(30)
        self.setMinimumWidth(360)
        self.snapshot = MaterialSnapshot((), (), 0)
        self.color = chess.BLACK
        self.player_color = chess.WHITE
        self.show_balance = False
        self.setToolTip('Потери восстановлены из взятий. Материал: пешка 1, конь/слон 3, ладья 5, ферзь 9. Это не оценка позиции.')

    def set_material(self, snapshot, color, player_color, show_balance=False):
        self.snapshot, self.color, self.player_color = snapshot, color, player_color
        self.show_balance = show_balance
        self.setAccessibleName(('Потеряны белые: ' if color else 'Потеряны чёрные: ') +
                               ', '.join(chess.piece_name(p) for p in snapshot.lost(color)) +
                               (f'; материальный баланс игрока {snapshot.balance(player_color):+d}' if show_balance else ''))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont('Segoe UI', 9))
        painter.setPen(QColor('#9daabd'))
        painter.drawText(QRectF(8, 0, 132, 30), Qt.AlignVCenter, 'Потеряны ' + ('белые' if self.color else 'чёрные'))
        lost = self.snapshot.lost(self.color)
        x = 140.
        max_x = self.width() - (118 if self.show_balance else 8)
        # Promotions can produce extra captured pieces: scale spacing to fit instead of clipping.
        widths = [12 if p == chess.PAWN else 20 for p in lost]
        scale = min(1., max(0., max_x - x - 22) / max(1, sum(widths)))
        if lost:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor('#607187'))
            painter.drawRoundedRect(QRectF(x+3,3,22+sum(widths[:-1])*scale,24),4,4)
        for i, piece in enumerate(lost):
            self.renderers[('white' if self.color else 'black', piece)].render(painter, QRectF(x, 1, 24, 28))
            x += widths[i] * scale
        if not lost:
            painter.drawText(QRectF(x, 0, 24, 30), Qt.AlignVCenter, '—')
        if self.show_balance:
            value = self.snapshot.balance(self.player_color)
            painter.setPen(QColor('#bdd5ce'))
            painter.drawText(QRectF(self.width() - 115, 0, 107, 30), Qt.AlignVCenter | Qt.AlignRight,
                             f'Материал {value:+d}' if value else 'Материал =')
