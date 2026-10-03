"""Bundled, asynchronous PCM cues. Never fall back to an OS notification sound."""
from __future__ import annotations

import logging

import chess
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QMediaDevices, QSoundEffect

from app.config.settings import resource_root

log = logging.getLogger(__name__)
CUES = ('move', 'capture', 'check', 'end')


def move_cue(before: chess.Board, after: chess.Board, move: chess.Move, result: str) -> str:
    if result != '*':
        return 'end'
    if after.is_check():
        return 'check'
    return 'capture' if before.is_capture(move) else 'move'


class SoundPlayer(QObject):
    cue_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self.effects = {}
        self._pending: str | None = None
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self._outputs_changed)
        for cue in CUES:
            self._load_effect(cue)

    def _load_effect(self, cue):
        effect = QSoundEffect(self)
        effect.setLoopCount(1)
        effect.setVolume(.65)
        effect.statusChanged.connect(lambda cue=cue: self._status_changed(cue))
        self.effects[cue] = effect
        effect.setSource(QUrl.fromLocalFile(str(resource_root() / f'resources/sounds/{cue}.wav')))

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if not enabled:
            self.stop()

    def play(self, cue: str):
        if not self.enabled:
            return
        if cue not in self.effects:
            raise ValueError(f'Unknown sound cue: {cue}')
        self.stop()
        self.cue_requested.emit(cue)
        self._pending = cue
        effect = self.effects[cue]
        if effect.status() == QSoundEffect.Ready:
            self._pending = None
            effect.play()
        elif effect.status() == QSoundEffect.Error:
            self._pending = None
            log.warning('Audio unavailable for %s; continuing silently', cue)

    def _status_changed(self, cue):
        effect = self.effects[cue]
        if effect.status() == QSoundEffect.Error:
            if self.devices.defaultAudioOutput().isNull():
                log.info('No audio output available for %s; continuing silently', cue)
            else:
                log.warning('Could not load bundled sound %s', cue)
        if self.enabled and self._pending == cue and effect.status() == QSoundEffect.Ready:
            self._pending = None
            effect.play()

    def _outputs_changed(self):
        # Resume cleanly if headphones/devices change. No stale sound is replayed.
        self.stop()
        for cue in CUES:
            self.effects[cue].deleteLater()
            self._load_effect(cue)

    def stop(self):
        self._pending = None
        for effect in self.effects.values():
            effect.stop()
