from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone

import chess
import chess.pgn

from app.services.clocks import TimeControl


@dataclass
class GameState:
    player_color: chess.Color = chess.WHITE
    bot_rating: float = 1100
    rating_before: float = 1000
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    board: chess.Board = field(default_factory=chess.Board)
    result: str = "*"
    elapsed_seconds: float = 0
    database_id: int | None = None
    time_control: TimeControl = field(default_factory=TimeControl)
    clock_state: dict | None = None
    termination: str = ""

    def play(self, move: chess.Move):
        if self.result != "*":
            raise ValueError("Партия уже завершена")
        if move not in self.board.legal_moves:
            raise ValueError("Недопустимый ход")
        self.board.push(move)
        outcome = self.board.outcome(claim_draw=True)
        if outcome:
            self.result = outcome.result()
            self.termination = outcome.termination.name.lower()

    def resign(self):
        if self.result == "*":
            self.result = "0-1" if self.player_color else "1-0"
            self.termination = "resignation"

    def timeout(self, loser: chess.Color):
        if self.result == "*":
            self.result = "1/2-1/2" if self.board.has_insufficient_material(not loser) else "0-1" if loser else "1-0"
            self.termination = "timeout"

    def pgn(self) -> str:
        game = chess.pgn.Game.from_board(self.board)
        game.headers.update({
            "Event": "Adaptive Chess", "Date": self.started_at[:10].replace("-", "."),
            "White": "Игрок" if self.player_color else "Adaptive Chess",
            "Black": "Adaptive Chess" if self.player_color else "Игрок", "Result": self.result,
        })
        if self.time_control.timed:
            game.headers["TimeControl"] = self.time_control.pgn_value
        if self.termination == "timeout":
            game.headers["Termination"] = "time forfeit"
        return str(game)

    @classmethod
    def from_pgn(cls, text: str, **kwargs) -> GameState:
        parsed = chess.pgn.read_game(io.StringIO(text))
        if parsed is None or parsed.errors:
            raise ValueError("Не удалось прочитать сохранённую партию")
        state = cls(board=parsed.end().board(), **kwargs)
        state.result = parsed.headers.get("Result", "*")
        if state.result != "*" and not state.termination:
            outcome = state.board.outcome(claim_draw=True)
            state.termination = (outcome.termination.name.lower() if outcome and outcome.result() == state.result else
                                 "timeout" if parsed.headers.get("Termination") == "time forfeit" else
                                 "draw" if state.result == "1/2-1/2" else "unknown")
        return state

    def player_score(self) -> float:
        if self.result == "*":
            raise ValueError("Партия ещё продолжается")
        if self.result == "1/2-1/2":
            return 0.5
        return float((self.result == "1-0") == self.player_color)
