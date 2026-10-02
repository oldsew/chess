from __future__ import annotations

import logging
import time

import chess

from app.adaptive.rating import RatingEvidence, update_rating
from app.database.store import Store
from app.services.game import GameState

log = logging.getLogger(__name__)


class Session:
    """Coordinates game persistence and profile updates independently of the GUI."""
    def __init__(self, store: Store):
        self.store = store
        self.game: GameState | None = None
        self._clock = time.monotonic()

    def start(self, color: bool):
        self.save()
        profile = self.store.profile()
        self.game = GameState(player_color=color, bot_rating=profile.target, rating_before=profile.rating)
        self._clock = time.monotonic()
        self.save()
        log.info("Game started: id=%s color=%s", self.game.database_id, color)
        return self.game

    def resume(self, game: GameState):
        self.save()
        self.game = game
        self._clock = time.monotonic()

    def save(self):
        if self.game:
            now = time.monotonic()
            if self.game.result == "*":
                self.game.elapsed_seconds += now - self._clock
            self._clock = now
            self.store.save_game(self.game)

    def play(self, move: chess.Move):
        if not self.game:
            raise ValueError("Нет активной партии")
        # Capture time before result becomes terminal.
        self.save()
        self.game.play(move)
        self.save()
        if self.game.result != "*":
            log.info("Game finished: %s", self.game.result)

    def resign(self):
        self.save()
        self.game.resign()
        self.save()
        log.info("Game resigned: %s", self.game.result)

    def complete(self, game, moves, metrics):
        profile = self.store.profile()
        evidence = RatingEvidence.create(game.player_score(), metrics)
        updated = update_rating(profile, game.bot_rating, evidence, self.store.evidence())
        self.store.finish_analysis(game, moves, metrics, updated)
        return self.store.profile()
