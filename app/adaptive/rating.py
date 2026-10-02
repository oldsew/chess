from __future__ import annotations

from dataclasses import dataclass, replace

from app.adaptive.metrics import Performance
from app.config.settings import TUNING


@dataclass
class PlayerProfile:
    rating: float = TUNING["initial_rating"]
    confidence: float = 0.0
    offset: float = TUNING["default_offset"]
    games: int = 0
    peak: float = TUNING["initial_rating"]

    @property
    def target(self) -> float:
        return self.rating + self.offset


@dataclass
class RatingEvidence:
    score: float
    accuracy: float
    average_cpl: float
    mistakes: int
    blunders: int
    moves: int

    @classmethod
    def create(cls, score: float, metrics: Performance):
        return cls(score, metrics.accuracy, metrics.average_cpl, metrics.mistakes, metrics.blunders, metrics.moves)


def clamp(value, low, high):
    return max(low, min(high, value))


def quality(e: RatingEvidence) -> float:
    cfg = TUNING["rating"]
    if not e.moves:
        return 0
    raw = (e.accuracy - cfg["quality_base"]) / cfg["quality_scale"]
    penalty = min(0.35, e.average_cpl / 600) + min(0.3, (e.mistakes + 2 * e.blunders) / max(1, e.moves) * 0.6)
    return clamp(raw - penalty, -1, 1)


def update_rating(profile: PlayerProfile, bot_rating: float, evidence: RatingEvidence,
                  history: list[RatingEvidence]) -> PlayerProfile:
    cfg = TUNING["rating"]
    expected = 1 / (1 + 10 ** ((bot_rating - profile.rating) / 400))
    cap = cfg["caps"][0 if profile.games < cfg["calibration_games"] else
                       1 if profile.games < cfg["settling_games"] else 2]
    recent = (history + [evidence])[-TUNING["recent_window"]:]
    # More recent games have larger weights; the last five dominate the ten-game window.
    weighted_quality = sum(quality(e) * (i + 1) for i, e in enumerate(recent)) / sum(range(1, len(recent) + 1))
    q = (1 - cfg["recent_weight"]) * quality(evidence) + cfg["recent_weight"] * weighted_quality
    signal = cfg["result_weight"] * 2 * (evidence.score - expected) + cfg["quality_weight"] * q
    # A well-played loss is evidence of strength, and a lucky poor win grants little.
    if evidence.score == 0 and evidence.accuracy >= 85 and evidence.average_cpl < 45:
        signal = max(signal, -0.06)
    if evidence.score == 1 and evidence.accuracy < 60:
        signal = clamp(signal, 0, 0.1)
    # Very short games are weak evidence; resignation before any move should not affect calibration.
    reliability = min(1, evidence.moves / 12)
    delta = clamp(cap * signal * reliability, -cap, cap)
    rating = clamp(profile.rating + delta, TUNING["min_rating"], TUNING["max_rating"])
    offset = profile.offset
    last_five = recent[-5:]
    if len(last_five) == 5 and all(e.score == 0 and e.accuracy < 65 for e in last_five):
        offset -= cfg["offset_step"] * 2
    elif len(last_five) >= 3 and all(e.score == 1 and e.accuracy >= 80 for e in last_five[-3:]):
        offset += cfg["offset_step"]
    return replace(profile, rating=rating, confidence=min(1, profile.confidence + 0.06 * reliability),
                   offset=clamp(offset, TUNING["min_offset"], TUNING["max_offset"]),
                   games=profile.games + 1, peak=max(profile.peak, rating))
