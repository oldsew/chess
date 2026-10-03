"""Exercise animations and the real bundled Qt audio decoder inside the frozen executable."""
from __future__ import annotations

import json
import time

import chess
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QAudioDecoder, QMediaDevices, QSoundEffect

from app.config.settings import resource_root
from app.ui.sounds import CUES

# UI-only positions. No gameplay, ratings, database contents or analysis are changed.
SCENARIOS = [
    ('move', chess.STARTING_FEN, 'e2e4', 1, False, False),
    ('capture', '4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1', 'e4d5', 1, True, False),
    ('castle-white', 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1', 2, False, False),
    ('castle-black', 'r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1', 'e8c8', 2, False, False),
    ('en-passant', '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'e5d6', 1, True, False),
    ('promotion', '7k/P7/8/8/8/8/8/7K w - - 0 1', 'a7a8q', 1, False, True),
    ('capture-promotion', 'r6k/1P6/8/8/8/8/8/7K w - - 0 1', 'b7a8n', 1, True, True),
]


def attach_polish_smoke(app, window, report_path):
    state = {'index': 0, 'active': False, 'frames': 0, 'motion_seen': False,
             'started': time.monotonic(), 'animations': [], 'decoding': None, 'decoded': {}, 'bytes': 0,
             'cues': [], 'audio_status': {}, 'muted': False}
    timer = QTimer(window)
    timer.setInterval(12)
    # Explicitly test full motion even when the runner disables system animations.
    window.board.animations_enabled = True
    decoder = QAudioDecoder(window)
    window.polish_decoder = decoder
    window.sounds.cue_requested.connect(state['cues'].append)
    window.sounds.set_enabled(True)
    window.grab().save(str(report_path.with_suffix('.png')))

    def start_decode(cue):
        nonlocal decoder
        decoder.stop()
        decoder.deleteLater()
        decoder = QAudioDecoder(window)
        window.polish_decoder = decoder
        current = decoder
        byte_counts = []
        def buffer_ready():
            buffer = current.read()
            if buffer.isValid():
                byte_counts.append(buffer.byteCount())
        def decode_finished():
            state['decoded'][cue] = sum(byte_counts)
            if state['decoding'] == cue:
                state['decoding'] = None
        current.bufferReady.connect(buffer_ready)
        current.finished.connect(decode_finished)
        state['decoding'] = cue
        current.setSource(QUrl.fromLocalFile(str(resource_root() / f'resources/sounds/{cue}.wav')))
        current.start()

    def finish(success, message):
        timer.stop()
        decoder.stop()
        has_device = not QMediaDevices.defaultAudioOutput().isNull()
        report = {'success': success, 'message': message, 'window_visible': window.isVisible(),
                  'animations': state['animations'], 'decoded_audio_bytes': state['decoded'],
                  'audio_output_available': has_device, 'audio_status': state['audio_status'],
                  'audio_playback_requests': state['cues'], 'mute_verified': state['muted']}
        window.close()
        report['engine_closed'] = window.engine._engine is None
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        app.exit(0 if success else 1)

    def tick():
        try:
            if time.monotonic() - state['started'] > 25:
                raise AssertionError('UX smoke timed out')
            if state['index'] < len(SCENARIOS):
                name, fen, uci, count, capture, promotion = SCENARIOS[state['index']]
                if not state['active']:
                    before = chess.Board(fen)
                    move = chess.Move.from_uci(uci)
                    assert move in before.legal_moves
                    window.board.set_position(before)
                    after = before.copy()
                    after.push(move)
                    window.board.set_position(after, animate=True)
                    transition = window.board.transition
                    assert transition and len(transition.motions) == count
                    assert bool(transition.captured) == capture
                    assert bool(transition.motions[0].promoted_piece) == promotion
                    assert all(renderer.isValid() for renderer in window.board.renderers.values())
                    state.update(active=True, frames=0, motion_seen=False, transition=transition,
                                 expected_fen=after.fen(), began=time.monotonic())
                    return
                if window.board.animating:
                    state['frames'] += 1
                    if 0 < window.board.progress < 1:
                        rect = window.board.motion_rect(0)
                        target = window.board.square_rect(state['transition'].motions[0].destination)
                        state['motion_seen'] |= rect.center() != target.center()
                        if name == 'move' and state['frames'] == 5:
                            window.grab().save(str(report_path.with_name('polish-motion.png')))
                    return
                assert state['frames'] >= 3 and state['motion_seen'], 'No real intermediate animation frames'
                assert window.board.board.fen() == state['expected_fen'], 'Animation mutated the logical position'
                state['animations'].append({'name': name, 'frames': state['frames'],
                                            'elapsed_ms': round((time.monotonic() - state['began']) * 1000)})
                state['index'] += 1
                state['active'] = False
                return
            if state['decoding']:
                assert decoder.error() == QAudioDecoder.NoError, decoder.errorString()
                return
            remaining = [cue for cue in CUES if cue not in state['decoded']]
            if remaining:
                cue = remaining[0]
                start_decode(cue)
                window.sounds.play(cue)
                return
            assert all(count > 0 for count in state['decoded'].values()), 'Bundled audio did not decode'
            assert state['cues'] == list(CUES), 'Not all custom cues were routed to QSoundEffect'
            has_device = not QMediaDevices.defaultAudioOutput().isNull()
            state['audio_status'] = {cue: effect.status().name for cue, effect in window.sounds.effects.items()}
            if has_device:
                if any(effect.status() == QSoundEffect.Loading for effect in window.sounds.effects.values()):
                    return
                assert all(effect.status() == QSoundEffect.Ready for effect in window.sounds.effects.values()), 'Playback backend could not load a cue'
            window.sounds.set_enabled(False)
            window.sounds.play('move')
            state['muted'] = state['cues'] == list(CUES) and not any(e.isPlaying() for e in window.sounds.effects.values())
            assert state['muted'], 'Sound toggle did not mute playback'
            finish(True, 'Seven real animated transitions, bundled SVGs, four Qt-decoded audio cues and mute passed')
        except Exception as error:
            finish(False, f'{type(error).__name__}: {error}')

    timer.timeout.connect(tick)
    timer.start()
    return timer
