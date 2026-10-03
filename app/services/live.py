"""Lightweight position feedback, separate from final analysis and adaptive strength."""
from __future__ import annotations

from dataclasses import dataclass

import chess
import chess.engine

from app.config.gameplay import GAMEPLAY

CFG = GAMEPLAY['position_indicator']
LABELS = {
    -3: 'Соперник значительно впереди', -2: 'Преимущество у соперника',
    -1: 'Небольшое преимущество у соперника', 0: 'Шансы примерно равны',
    1: 'Небольшое преимущество у вас', 2: 'У вас преимущество', 3: 'Вы значительно впереди',
}


@dataclass(frozen=True)
class LiveEvaluation:
    fen: str
    white_cp: int | None
    mate_white: int | None
    mate_winner: bool | None
    depth: int
    white_label: str

    @classmethod
    def from_info(cls, board: chess.Board, info):
        score = info['score'].white()
        mate = score.mate()
        winner = score.score(mate_score=100000) > 0 if mate is not None else None
        return cls(board.fen(), score.score(), mate, winner, info.get('depth', 0), str(score))

    def player_cp(self, color: bool):
        return self.white_cp if color or self.white_cp is None else -self.white_cp

    def player_mate(self, color: bool):
        return self.mate_white if color or self.mate_white is None else -self.mate_white


def category(cp: int) -> int:
    magnitude = sum(abs(cp) > threshold for threshold in CFG['thresholds_cp'])
    return magnitude if cp >= 0 else -magnitude


class PositionIndicator:
    def __init__(self):
        self.level = 0
        self.text = LABELS[0]
        self.debug = {}

    def update(self, value: LiveEvaluation, color: bool):
        previous = self.level
        cp = value.player_cp(color)
        if value.mate_white is not None:
            self.text = 'У вас решающее преимущество' if value.mate_winner == color else 'Позиция критическая'
            candidate = None
        else:
            candidate = category(cp)
            small, medium, large = CFG['thresholds_cp']
            boundaries = [-large, -medium, -small, small, medium, large]
            margin = CFG['hysteresis_cp']
            while self.level < candidate and cp > boundaries[self.level + 3] + margin:
                self.level += 1
            while self.level > candidate and cp < boundaries[self.level + 2] - margin:
                self.level -= 1
            self.text = LABELS[self.level]
        self.debug = {'fen': value.fen, 'evaluation_white_cp': value.white_cp, 'evaluation_player_cp': cp,
                      'evaluation_white': value.white_label, 'mate_white': value.mate_white,
                      'mate_player': value.player_mate(color), 'mate_winner': value.mate_winner,
                      'live_depth': value.depth, 'live_requested_depth': CFG['depth'],
                      'category': self.text, 'thresholds_cp': CFG['thresholds_cp'],
                      'hysteresis_cp': CFG['hysteresis_cp'], 'previous_level': previous,
                      'level': self.level, 'candidate_level': candidate,
                      'hysteresis_held': candidate is not None and candidate != self.level}
        return self.text
