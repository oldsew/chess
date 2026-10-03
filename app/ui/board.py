from __future__ import annotations

import chess
from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QVariantAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient, QPolygonF
from PySide6.QtWidgets import QWidget
from PySide6.QtSvg import QSvgRenderer
from app.config.settings import resource_root
from app.ui.transitions import MoveTransition
from app.config.gameplay import GAMEPLAY
import math

THEMES = {
    "Сланец": ("#e5e1d9", "#8c928e"),
    "Лес": ("#e9ecd9", "#78917b"),
    "Песок": ("#f0e5d0", "#b49b7c"),
}
MOVE_DURATION_MS = GAMEPLAY['move_duration_ms']


class ChessBoard(QWidget):
    move_requested = Signal(int, int)
    animation_started = Signal(object)
    animation_finished = Signal()
    presentation_finished = Signal()
    previous_requested = Signal()
    next_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 360)
        self.setFocusPolicy(Qt.StrongFocus)
        self.animations_enabled = True
        self._mate_pending = False
        self.mate_progress = 0.0
        self.setAccessibleName("Шахматная доска")
        self.board = chess.Board()
        self.orientation = chess.WHITE
        self.selected: int | None = None
        self.interactive = False
        self.player_color = chess.WHITE
        self.highlight_legal = True
        self.theme = "Сланец"
        self._press = None
        self._drag_point = None
        self._dragging = False
        self._origin = None
        self._drop_start: QPointF | None = None
        self._motion_start: QPointF | None = None
        self.transition: MoveTransition | None = None
        self.progress = 1.0
        self.annotations = []
        self.tactical_highlights = set()
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(MOVE_DURATION_MS)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._animation_frame)
        self.animation.finished.connect(self._animation_done)
        self.mate_animation = QVariantAnimation(self)
        self.mate_animation.setDuration(GAMEPLAY['mate_duration_ms'])
        self.mate_animation.setStartValue(0.0)
        self.mate_animation.setEndValue(1.0)
        self.mate_animation.setEasingCurve(QEasingCurve.Linear)
        self.mate_animation.valueChanged.connect(self._mate_frame)
        self.mate_animation.finished.connect(self._mate_done)
        self.renderers = {(color, piece): QSvgRenderer(str(resource_root() / "resources/pieces" / f"{color}-{chess.piece_name(piece)}.svg"))
                          for color in ["white", "black"] for piece in chess.PIECE_TYPES}

    def geometry_values(self):
        size = min(self.width(), self.height()) - 32
        return (self.width() - size) / 2, (self.height() - size) / 2, size / 8

    def square_at(self, point) -> int | None:
        x, y, cell = self.geometry_values()
        col, row = int((point.x() - x) // cell), int((point.y() - y) // cell)
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        return chess.square(col, 7 - row) if self.orientation else chess.square(7 - col, row)

    def square_rect(self, square: int) -> QRectF:
        x, y, cell = self.geometry_values()
        col = chess.square_file(square) if self.orientation else 7 - chess.square_file(square)
        row = 7 - chess.square_rank(square) if self.orientation else chess.square_rank(square)
        return QRectF(x + col * cell, y + row * cell, cell, cell)

    @property
    def animating(self) -> bool:
        return self.transition is not None

    def set_position(self, board: chess.Board, *, animate: bool = False, celebrate: bool = True):
        if board.fen() == self.board.fen() and board.move_stack == self.board.move_stack:
            # MainWindow can refresh twice during a move; keep the ongoing transition intact.
            self.update()
            return
        transition = MoveTransition.between(self.board, board) if animate and self.animations_enabled else None
        self.animation.stop()
        self.mate_animation.stop()
        self.mate_progress = 0
        self._mate_pending = animate and celebrate and self.animations_enabled and board.is_checkmate()
        self.transition = transition
        self._motion_start = None
        if transition and self._drop_start is not None:
            x, y, cell = self.geometry_values()
            self._motion_start = QPointF((self._drop_start.x() - x) / cell, (self._drop_start.y() - y) / cell)
        self._drop_start = None
        self.board = board.copy()
        self.selected = None
        self._dragging = False
        if transition:
            self.progress = 0.0
            self.animation_started.emit(transition)
            self.animation.start()
        else:
            self.progress = 1.0
            if self._mate_pending:
                self.mate_animation.start()
        self.update()

    def _animation_frame(self, progress):
        self.progress = float(progress)
        self.update()

    def _animation_done(self):
        self.transition = None
        self._motion_start = None
        self.progress = 1.0
        self.update()
        self.animation_finished.emit()
        if self._mate_pending:
            self.mate_animation.start()
        else:
            self.presentation_finished.emit()

    @property
    def presenting_end(self):
        return self._mate_pending

    def _mate_frame(self, progress):
        self.mate_progress = float(progress)
        self.update()

    def _mate_done(self):
        self._mate_pending = False
        self.mate_progress = 0
        self.update()
        self.presentation_finished.emit()

    @property
    def capture_opacity(self) -> float:
        t = min(1.0, self.animation.currentTime() / MOVE_DURATION_MS / 0.9)
        blend = t * t * (3 - 2 * t)
        return blend if self.transition and self.transition.reverse else 1 - blend

    @property
    def promotion_blend(self) -> float:
        elapsed = self.animation.currentTime() / MOVE_DURATION_MS
        t = max(0.0, min(1.0, elapsed / .4 if self.transition and self.transition.reverse else (elapsed - .6) / .4))
        return t * t * (3 - 2 * t)

    def motion_rect(self, index: int) -> QRectF:
        motion = self.transition.motions[index]
        origin = self.square_rect(motion.origin).center()
        if index == 0 and self._motion_start is not None:
            x, y, cell = self.geometry_values()
            origin = QPointF(x + self._motion_start.x() * cell, y + self._motion_start.y() * cell)
        target = self.square_rect(motion.destination).center()
        center = origin + (target - origin) * self.progress
        cell = self.geometry_values()[2]
        return QRectF(center.x() - cell / 2, center.y() - cell / 2, cell, cell)

    def _draw_piece(self, painter, piece, rect):
        margin = rect.width() * 0.06
        inner = rect.adjusted(margin, margin, -margin, -margin)
        self.renderers[("white" if piece.color else "black", piece.piece_type)].render(painter, inner)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        light, dark = THEMES.get(self.theme, THEMES["Сланец"])
        last_move = self.board.peek() if self.board.move_stack else None
        targets = {m.to_square for m in self.board.legal_moves if m.from_square == self.selected}
        moving_targets = {m.destination for m in self.transition.motions} if self.transition else set()
        if self.transition and self.transition.reverse and self.transition.captured:
            moving_targets.add(self.transition.captured_square)
        for square in chess.SQUARES:
            rect = self.square_rect(square)
            painter.fillRect(rect, QColor(light if (chess.square_rank(square) + chess.square_file(square)) % 2 else dark))
            if square in self.tactical_highlights:
                painter.fillRect(rect,QColor(190,120,58,38))
                painter.setPen(QPen(QColor(168,98,48,150),1.6))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(4,4,-4,-4),5,5)
            if last_move and square in (last_move.from_square, last_move.to_square):
                painter.fillRect(rect, QColor(245, 211, 135, 48))
                painter.setPen(QPen(QColor(252, 228, 175, 100), 1.2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 5, 5)
            if square == self.selected:
                painter.fillRect(rect, QColor(89, 185, 177, 48))
                painter.setPen(QPen(QColor(39, 119, 117, 170), 1.8))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 5, 5)
            if self.board.is_check() and square == self.board.king(self.board.turn):
                glow = QRadialGradient(rect.center(), rect.width() * 0.7)
                glow.setColorAt(0, QColor(201, 69, 82, 110))
                glow.setColorAt(1, QColor(201, 69, 82, 0))
                painter.fillRect(rect, glow)
            if self.highlight_legal and square in targets:
                if self.board.piece_at(square):
                    painter.setPen(QPen(QColor(32, 73, 74, 95), rect.width() * 0.035))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(rect.adjusted(5, 5, -5, -5))
                else:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(32, 73, 74, 85))
                    painter.drawEllipse(rect.center(), rect.width() * 0.075, rect.height() * 0.075)
            piece = self.board.piece_at(square)
            if piece and square not in moving_targets and not (self._dragging and square == self._origin):
                self._draw_piece(painter, piece, rect)
        if self.transition:
            if self.transition.captured:
                painter.save()
                painter.setOpacity(self.capture_opacity)
                self._draw_piece(painter, self.transition.captured, self.square_rect(self.transition.captured_square))
                painter.restore()
            for i, motion in enumerate(self.transition.motions):
                rect = self.motion_rect(i)
                if motion.promoted_piece:
                    blend = self.promotion_blend
                    painter.save()
                    painter.setOpacity(1 - blend)
                    self._draw_piece(painter, motion.piece, rect)
                    painter.setOpacity(blend)
                    self._draw_piece(painter, motion.promoted_piece, rect)
                    painter.restore()
                else:
                    self._draw_piece(painter, motion.piece, rect)
        if self._mate_pending and self.transition is None:
            king = self.board.king(self.board.turn)
            if king is not None:
                pulse = math.sin(math.pi * self.mate_progress) ** 2
                x, y, cell = self.geometry_values()
                painter.fillRect(QRectF(x, y, cell * 8, cell * 8), QColor(17, 24, 34, int(28 * pulse)))
                rect = self.square_rect(king)
                glow = QRadialGradient(rect.center(), rect.width() * 0.72)
                glow.setColorAt(0, QColor(230, 103, 98, int(120 * pulse)))
                glow.setColorAt(1, QColor(230, 103, 98, 0))
                painter.fillRect(rect, glow)
                self._draw_piece(painter, self.board.piece_at(king), rect)
        for origin, destination, role in self.annotations[:2]:
            start, end = self.square_rect(origin).center(), self.square_rect(destination).center()
            vector = end - start
            length = math.hypot(vector.x(), vector.y())
            if not length:
                continue
            direction = QPointF(vector.x()/length, vector.y()/length)
            normal = QPointF(-direction.y(), direction.x())
            cell = self.geometry_values()[2]
            end -= direction * cell * .18
            ink = QColor('#3c765a' if role == 'recommended' else '#a25d52')
            ink.setAlpha(170)
            painter.setPen(QPen(ink, cell * .045, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(start + direction * cell * .12, end)
            painter.setPen(Qt.NoPen)
            painter.setBrush(ink)
            painter.drawPolygon(QPolygonF([end, end-direction*cell*.17+normal*cell*.08,
                                           end-direction*cell*.17-normal*cell*.08]))
        x, y, cell = self.geometry_values()
        painter.setPen(QColor("#aaa9a3"))
        painter.setFont(QFont("Segoe UI", 9))
        for i in range(8):
            file_index = i if self.orientation else 7 - i
            rank_index = 7 - i if self.orientation else i
            painter.drawText(QRectF(x + i * cell, y + 8 * cell + 2, cell, 18), Qt.AlignCenter, chess.FILE_NAMES[file_index])
            painter.drawText(QRectF(x - 17, y + i * cell, 14, cell), Qt.AlignCenter, str(rank_index + 1))
        if self._dragging and self._drag_point is not None:
            piece = self.board.piece_at(self._origin)
            if piece:
                self._draw_piece(painter, piece, QRectF(self._drag_point.x() - cell / 2, self._drag_point.y() - cell / 2, cell, cell))

    def _can_select(self, square):
        piece = self.board.piece_at(square) if square is not None else None
        return piece and piece.color == self.player_color and self.board.turn == self.player_color

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
        if event.button() != Qt.LeftButton or not self.interactive or self.animating:
            return
        square = self.square_at(event.position())
        self._press = event.position()
        self._origin = square if self._can_select(square) else None
        if self.selected is not None and square is not None and square != self.selected:
            if any(m.from_square == self.selected and m.to_square == square for m in self.board.legal_moves):
                origin = self.selected
                self.selected = None
                self.move_requested.emit(origin, square)
                return
        self.selected = None if square == self.selected else square if self._can_select(square) else None
        self.update()

    def mouseMoveEvent(self, event):
        if self.interactive and not self.animating and self._origin is not None and self._press is not None:
            if (event.position() - self._press).manhattanLength() > 5:
                self._dragging = True
                self._drag_point = event.position()
                self.update()

    def mouseReleaseEvent(self, event):
        if self._dragging and self.interactive and self._origin is not None:
            target = self.square_at(event.position())
            origin = self._origin
            self.selected = None
            if target is not None:
                self._drop_start = event.position()
                self.move_requested.emit(origin, target)
                self._drop_start = None
        self._dragging = False
        self._origin = None
        self._press = None
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.previous_requested.emit()
            event.accept()
        elif event.key() == Qt.Key_Right:
            self.next_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)
