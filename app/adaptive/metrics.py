from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass

import chess.engine

from app.config.settings import TUNING

CATEGORIES = ("Отличный", "Хороший", "Неточность", "Ошибка", "Грубая ошибка")
MATE_CP = 100_000


def score_cp(score: chess.engine.PovScore, color: bool) -> int:
    value = score.pov(color).score(mate_score=MATE_CP)
    if value is None:
        raise ValueError("Engine returned no score")
    return value


def centipawn_loss(before: int, after: int) -> int:
    return max(0, before - after)


def classify(cpl: int) -> str:
    return CATEGORIES[sum(cpl > threshold for threshold in TUNING["thresholds"])]


def move_accuracy(cpl: int) -> float:
    # Small deviations cost little; large tactical errors sharply reduce accuracy.
    return 100 * math.exp(-((max(0, cpl) / 130) ** 1.25))


@dataclass
class MoveAnalysis:
    ply: int
    san: str
    best_san: str
    before_cp: int
    after_cp: int
    cpl: int
    category: str
    before_label: str = ""
    after_label: str = ""


@dataclass
class Performance:
    accuracy: float
    average_cpl: float
    inaccuracies: int
    mistakes: int
    blunders: int
    excellent: int = 0
    good: int = 0
    moves: int = 0

    @classmethod
    def from_moves(cls, moves: list[MoveAnalysis]) -> Performance:
        counts = Counter(m.category for m in moves)
        n = len(moves)
        return cls(
            sum(move_accuracy(m.cpl) for m in moves) / n if n else 0,
            sum(m.cpl for m in moves) / n if n else 0,
            counts[CATEGORIES[2]], counts[CATEGORIES[3]], counts[CATEGORIES[4]],
            counts[CATEGORIES[0]], counts[CATEGORIES[1]], n,
        )

    def as_dict(self) -> dict:
        return asdict(self)
