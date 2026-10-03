from __future__ import annotations

import logging
import time

import chess

from app.adaptive.rating import RatingEvidence, update_rating
from app.database.store import Store
from app.services.clocks import ChessClock, TimeControl
from app.services.game import GameState

log = logging.getLogger(__name__)


class Session:
    """Coordinates real game state, clocks, persistence and the unchanged rating algorithm."""
    def __init__(self, store: Store, now=time.monotonic):
        self.store = store
        self._now = now
        self.game: GameState | None = None
        self.clock: ChessClock | None = None
        self._anchor = now()
        self._running = False

    def start(self, color: bool, control: TimeControl | None = None):
        self.pause()
        profile = self.store.profile()
        self.game = GameState(player_color=color, bot_rating=profile.target, rating_before=profile.rating,
                              time_control=control or TimeControl())
        self.clock = ChessClock(self.game.time_control, self._now)
        self._anchor = self._now()
        self._running = True
        self.clock.start(self.game.board.turn, self._anchor)
        self.save()
        log.info("Game started: id=%s color=%s control=%s", self.game.database_id, color, self.game.time_control.key)
        return self.game

    def resume(self, game: GameState):
        self.pause()
        self.game = game
        self.clock = ChessClock.restore(game.time_control, game.clock_state, self._now)
        self._anchor = self._now()
        self._running = game.result == '*'
        if self._running:
            self.clock.start(game.board.turn, self._anchor)
        self.save()

    def _track_duration(self, at):
        if self.game and self._running and self.game.result == '*':
            self.game.elapsed_seconds += max(0, at - self._anchor)
        self._anchor = at

    def _persist(self, at):
        if self.game:
            if self.clock:
                self.game.clock_state = self.clock.snapshot(at, finished=self.game.result != '*')
            self.store.save_game(self.game)

    def save(self):
        if self.game:
            if self.check_timeout():
                return
            at = self._now()
            self._track_duration(at)
            self._persist(at)

    def pause(self):
        if self.game:
            self.check_timeout()
            at = self._now()
            self._track_duration(at)
            if self.clock:
                self.clock.pause(at)
            self._running = False
            self._persist(at)

    def _finish_timeout(self, loser, at):
        self._track_duration(at)
        self.game.timeout(loser)
        self.clock.pause(at)
        self._running = False
        self._persist(at)
        log.info("Game finished by timeout: id=%s result=%s", self.game.database_id, self.game.result)

    def check_timeout(self):
        if not self.game or self.game.result != '*' or not self.clock:
            return False
        at = self._now()
        loser = self.clock.flagged(at)
        if loser is None:
            return False
        self._finish_timeout(loser, at)
        return True

    def play(self, move: chess.Move) -> bool:
        if not self.game or self.game.result != '*':
            raise ValueError('Нет активной партии')
        if move not in self.game.board.legal_moves:
            raise ValueError('Недопустимый ход')
        at = self._now()
        color = self.game.board.turn
        if not self.clock.complete_move(color, at):
            self._finish_timeout(color, at)
            return False
        self._track_duration(at)
        self.game.play(move)
        if self.game.result != '*':
            self.clock.pause(at)
            self._running = False
            log.info('Game finished: %s (%s)', self.game.result, self.game.termination)
        self._persist(at)
        return True

    def resign(self):
        if self.check_timeout():
            return
        at = self._now()
        self._track_duration(at)
        self.game.resign()
        self.clock.pause(at)
        self._running = False
        self._persist(at)
        log.info('Game resigned: %s', self.game.result)

    def complete(self, game, moves, metrics):
        profile = self.store.profile()
        evidence = RatingEvidence.create(game.player_score(), metrics)
        updated = update_rating(profile, game.bot_rating, evidence, self.store.evidence())
        self.store.finish_analysis(game, moves, metrics, updated)
        return self.store.profile()
