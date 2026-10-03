"""Monotonic chess clocks. GUI timers only request snapshots; they never advance time."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import time
from typing import Callable

import chess

from app.config.gameplay import GAMEPLAY


@dataclass(frozen=True)
class TimeControl:
    key: str = 'none'
    label: str = 'Без времени'
    initial_seconds: float | None = None
    increment: float = 0
    category: str = 'unlimited'

    def __post_init__(self):
        if self.initial_seconds is not None and (not math.isfinite(self.initial_seconds) or self.initial_seconds <= 0):
            raise ValueError('Начальное время должно быть положительным')
        if not math.isfinite(self.increment) or self.increment < 0:
            raise ValueError('Добавление не может быть отрицательным')

    def as_dict(self):
        return asdict(self)

    @property
    def timed(self):
        return self.initial_seconds is not None

    @property
    def short_label(self):
        return self.key if self.timed else 'Без времени'

    @property
    def pgn_value(self):
        return f'{self.initial_seconds:g}+{self.increment:g}' if self.timed else '-'


TIME_CONTROLS = tuple(TimeControl(**value) for value in GAMEPLAY['time_controls'])


def time_control(key: str) -> TimeControl:
    return next((control for control in TIME_CONTROLS if control.key == key), TIME_CONTROLS[0])


class ChessClock:
    def __init__(self, control: TimeControl, now: Callable[[], float] = time.monotonic):
        self.control = control
        self._now = now
        self._remaining = {chess.WHITE: control.initial_seconds, chess.BLACK: control.initial_seconds}
        self.active: bool = chess.WHITE
        self.running = False
        self._anchor: float | None = None

    def remaining(self, color: bool, at: float | None = None) -> float | None:
        value = self._remaining[color]
        if value is None:
            return None
        at = self._now() if at is None else at
        if self.running and color == self.active:
            value -= max(0, at - self._anchor)
        return max(0, value)

    def _charge(self, at: float):
        if self.running:
            self._remaining[self.active] = self.remaining(self.active, at)
            self._anchor = at

    def start(self, color: bool, at: float | None = None):
        at = self._now() if at is None else at
        self._charge(at)
        self.active = color
        self.running = True
        self._anchor = at

    def flagged(self, at: float | None = None) -> bool | None:
        if self.running and self.control.timed and self.remaining(self.active, at) <= 0:
            return self.active
        return None

    def complete_move(self, color: bool, at: float | None = None) -> bool:
        at = self._now() if at is None else at
        if not self.running or self.active != color:
            raise ValueError('Часы не соответствуют очереди хода')
        self._charge(at)
        if self.control.timed:
            if self._remaining[color] <= 0:
                return False
            self._remaining[color] += self.control.increment
        self.active = not color
        self._anchor = at
        return True

    def pause(self, at: float | None = None):
        at = self._now() if at is None else at
        self._charge(at)
        self.running = False
        self._anchor = None

    def snapshot(self, at: float | None = None, *, finished: bool = False) -> dict:
        at = self._now() if at is None else at
        return {'control': self.control.as_dict(), 'initial_seconds': self.control.initial_seconds,
                'increment': self.control.increment, 'white_seconds': self.remaining(chess.WHITE, at),
                'black_seconds': self.remaining(chess.BLACK, at),
                'active_color': 'white' if self.active else 'black',
                # A saved snapshot is always paused: application downtime never consumes time.
                'state': 'finished' if finished else 'paused'}

    @classmethod
    def restore(cls, control: TimeControl, state: dict | None, now=time.monotonic):
        clock = cls(control, now)
        if state:
            for color, key in [(chess.WHITE, 'white_seconds'), (chess.BLACK, 'black_seconds')]:
                value = state.get(key, control.initial_seconds)
                if control.timed:
                    if not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ValueError('Некорректное сохранённое время')
                    clock._remaining[color] = max(0, value)
            clock.active = state.get('active_color') != 'black'
        return clock
