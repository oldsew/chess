"""A read-only cursor over the real game's move stack. No Undo or clock state."""
import chess


class PositionNavigator:
    def __init__(self):
        self.ply: int | None = None

    @property
    def viewing(self):
        return self.ply is not None

    def current(self):
        self.ply = None

    def select(self, ply: int, board: chess.Board):
        ply = max(0, min(ply, len(board.move_stack)))
        self.ply = ply if ply < len(board.move_stack) else None

    def back(self, board: chess.Board):
        if board.move_stack:
            self.select((len(board.move_stack) if self.ply is None else self.ply) - 1, board)

    def forward(self, board: chess.Board):
        if self.ply is not None:
            self.select(self.ply + 1, board)

    def position(self, board: chess.Board):
        if self.ply is None:
            return board.copy()
        position = board.root()
        for move in board.move_stack[:self.ply]:
            position.push(move)
        return position
