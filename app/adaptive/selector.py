from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

import chess

from app.config.settings import TUNING


@dataclass
class BehaviorProfile:
    skill_level: int
    inaccuracy_probability: float
    mistake_probability: float
    blunder_probability: float
    max_allowed_cpl: float
    candidate_move_temperature: float
    search_time: float

    @classmethod
    def for_rating(cls, elo: float):
        points = TUNING["profiles"]
        elo = max(points[0]["elo"], min(points[-1]["elo"], elo))
        low, high = points[0], points[-1]
        for a, b in zip(points, points[1:]):
            if a["elo"] <= elo <= b["elo"]:
                low, high = a, b
                break
        t = (elo - low["elo"]) / (high["elo"] - low["elo"])
        values = {key: low[key] + t * (high[key] - low[key]) for key in cls.__dataclass_fields__}
        values["skill_level"] = round(values["skill_level"])
        return cls(**values)


@dataclass
class Candidate:
    move: chess.Move
    score: int
    mate: int | None = None


@dataclass
class Selection:
    move: chess.Move
    candidates: list[dict]
    profile: dict
    complexity: str
    delay: float


def select_move(board: chess.Board, candidates: list[Candidate], rating: float,
                rng: random.Random | None = None) -> Selection:
    rng = rng or random.Random()
    legal = [c for c in candidates if c.move in board.legal_moves]
    if not legal:
        raise ValueError("No legal engine candidates")
    profile = BehaviorProfile.for_rating(rating)
    best = max(c.score for c in legal)
    immediate_mates = []
    for c in legal:
        position = board.copy(stack=False)
        position.push(c.move)
        if position.is_checkmate():
            immediate_mates.append(c.move)
    phase = "endgame" if len(board.piece_map()) <= 12 else "opening" if board.fullmove_number <= 10 else "middlegame"
    spread = best - min(c.score for c in legal)
    complexity = "complex" if board.is_check() or spread > 150 else "simple" if len(legal) <= 2 or phase == "opening" else "normal"
    # Only plausible candidates are considered. Never inject random moves outside MultiPV.
    ceiling = profile.max_allowed_cpl
    if len([c for c in legal if best - c.score <= 50]) >= 3:
        ceiling = min(ceiling, 90)
    weights = []
    for c in legal:
        loss = max(0, best - c.score)
        allowed = loss <= ceiling
        # Keep proven mates; do not walk into a forced mate if a non-losing candidate exists.
        if immediate_mates:
            allowed = c.move in immediate_mates
        elif any(x.mate is not None and x.mate > 0 for x in legal):
            allowed = allowed and c.mate is not None and c.mate > 0
        elif c.mate is not None and c.mate < 0 and any(x.mate is None or x.mate > 0 for x in legal):
            allowed = False
        band_weight = (1 if loss <= 40 else profile.inaccuracy_probability if loss <= 90 else
                       profile.mistake_probability if loss <= 200 else profile.blunder_probability)
        temperature = profile.candidate_move_temperature * (1.15 if complexity == "complex" else 0.85 if phase == "endgame" else 1)
        weights.append(math.exp(-loss / max(1, temperature)) * band_weight if allowed else 0)
    total = sum(weights)
    if total == 0:
        weights = [float(c.score == best) for c in legal]
        total = sum(weights)
    probabilities = [w / total for w in weights]
    chosen = rng.choices(legal, weights=probabilities, k=1)[0]
    delay = rng.uniform(*TUNING["think_times"][complexity])
    debug = [{"move": board.san(c.move), "uci": c.move.uci(), "evaluation": c.score,
              "mate": c.mate, "cpl": max(0, best - c.score), "probability": p}
             for c, p in zip(legal, probabilities)]
    return Selection(chosen.move, debug, asdict(profile), complexity, delay)
