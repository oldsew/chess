from __future__ import annotations

import chess
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget
from PySide6.QtSvg import QSvgRenderer
from app.config.settings import resource_root

THEMES = {
    "Сланец": ("#e3e7ed", "#71849a"),
    "Лес": ("#e9ecd9", "#78917b"),
    "Песок": ("#f0e5d0", "#b49b7c"),
}
GLYPHS = {chess.KING: "♚", chess.QUEEN: "♛", chess.ROOK: "♜", chess.BISHOP: "♝", chess.KNIGHT: "♞", chess.PAWN: "♟"}


class ChessBoard(QWidget):
    move_requested = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 360)
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

    def set_position(self, board: chess.Board):
        self.board = board.copy()
        self.selected = None
        self._dragging = False
        self.update()

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
        for square in chess.SQUARES:
            rect = self.square_rect(square)
            painter.fillRect(rect, QColor(light if (chess.square_rank(square) + chess.square_file(square)) % 2 else dark))
            if last_move and square in (last_move.from_square, last_move.to_square):
                painter.fillRect(rect, QColor(227, 191, 81, 110))
            if square == self.selected:
                painter.fillRect(rect, QColor(71, 173, 196, 150))
            if self.board.is_check() and square == self.board.king(self.board.turn):
                painter.fillRect(rect, QColor(226, 96, 100, 175))
            if self.highlight_legal and square in targets:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(28, 48, 64, 100))
                painter.drawEllipse(rect.center(), rect.width() * 0.09, rect.height() * 0.09)
            piece = self.board.piece_at(square)
            if piece and not (self._dragging and square == self._origin):
                self._draw_piece(painter, piece, rect)
        x, y, cell = self.geometry_values()
        painter.setPen(QColor("#9daabd"))
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
        if event.button() != Qt.LeftButton or not self.interactive:
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
        self.selected = square if self._can_select(square) else None
        self.update()

    def mouseMoveEvent(self, event):
        if self.interactive and self._origin is not None and self._press is not None:
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
                self.move_requested.emit(origin, target)
        self._dragging = False
        self._origin = None
        self._press = None
        self.update()
