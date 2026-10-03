"""Presentation-only descriptions of a single already-committed chess move."""
from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class PieceMotion:
    piece: chess.Piece
    origin: int
    destination: int
    promoted_piece: chess.Piece | None = None


@dataclass(frozen=True)
class MoveTransition:
    motions: tuple[PieceMotion, ...]
    captured: chess.Piece | None = None
    captured_square: int | None = None

    @classmethod
    def between(cls, before: chess.Board, after: chess.Board) -> MoveTransition | None:
        # Resumes, new games and analysis navigation are snapshots, not moves to animate.
        if len(after.move_stack) != len(before.move_stack) + 1 or after.move_stack[:-1] != before.move_stack:
            return None
        move = after.peek()
        check = after.copy()
        check.pop()
        if check.fen() != before.fen():
            return None
        piece = before.piece_at(move.from_square)
        if piece is None:
            return None
        motions = [PieceMotion(piece, move.from_square, move.to_square,
                               after.piece_at(move.to_square) if move.promotion else None)]
        captured_square = move.to_square
        if before.is_en_passant(move):
            captured_square += -8 if before.turn else 8
        captured = before.piece_at(captured_square)
        if before.is_castling(move):
            rank = chess.square_rank(move.from_square)
            kingside = chess.square_file(move.to_square) > chess.square_file(move.from_square)
            origin = chess.square(7 if kingside else 0, rank)
            destination = chess.square(5 if kingside else 3, rank)
            rook = before.piece_at(origin)
            if rook:
                motions.append(PieceMotion(rook, origin, destination))
            captured = None
        return cls(tuple(motions), captured, captured_square if captured else None)
