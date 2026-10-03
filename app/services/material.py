"""Read-only material information reconstructed from the displayed board's move stack."""
from __future__ import annotations

from dataclasses import dataclass

import chess

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
DISPLAY_ORDER = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN)


def material_balance(board: chess.Board, color: bool) -> int:
    return sum(value * (len(board.pieces(piece, color)) - len(board.pieces(piece, not color)))
               for piece, value in VALUES.items())


def captured_piece(board: chess.Board, move: chess.Move) -> chess.Piece | None:
    if board.is_en_passant(move):
        return chess.Piece(chess.PAWN, not board.turn)
    return board.piece_at(move.to_square) if board.is_capture(move) else None


@dataclass(frozen=True)
class MaterialSnapshot:
    white_lost: tuple[int, ...]
    black_lost: tuple[int, ...]
    white_balance: int

    def lost(self, color: bool):
        return self.white_lost if color else self.black_lost

    def balance(self, color: bool):
        return self.white_balance if color else -self.white_balance

    @classmethod
    def from_board(cls, board: chess.Board):
        position = board.root()
        losses = {chess.WHITE: [], chess.BLACK: []}
        for move in board.move_stack:
            piece = captured_piece(position, move)
            if piece and piece.piece_type != chess.KING:
                losses[piece.color].append(piece.piece_type)
            position.push(move)
        ordered = {color: tuple(piece for piece in DISPLAY_ORDER for lost in losses[color] if lost == piece)
                   for color in [chess.WHITE, chess.BLACK]}
        return cls(ordered[chess.WHITE], ordered[chess.BLACK], material_balance(board, chess.WHITE))
