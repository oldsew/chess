from __future__ import annotations

import struct
import wave

import chess
import pytest
from PySide6.QtCore import QEasingCurve, QPointF, QTimer, Qt, QUrl
from PySide6.QtGui import QMouseEvent
from PySide6.QtMultimedia import QAudioDecoder
from PySide6.QtTest import QSignalSpy

from app.config.settings import resource_root
from app.services.game import GameState
from app.ui.board import ChessBoard
from app.ui.sounds import CUES, SoundPlayer
from app.ui.window import MainWindow


def animated_board(qtbot, before, uci):
    widget = ChessBoard()
    qtbot.addWidget(widget)
    widget.resize(600, 600)
    widget.show()
    widget.set_position(before)
    after = before.copy()
    move = chess.Move.from_uci(uci)
    assert move in before.legal_moves
    after.push(move)
    widget.set_position(after, animate=True)
    return widget, after


def test_nonblocking_eased_movement_keeps_committed_position(qtbot):
    widget, after = animated_board(qtbot, chess.Board(), 'e2e4')
    assert 220 <= widget.animation.duration() <= 280
    assert widget.animation.easingCurve().type() == QEasingCurve.OutCubic
    events = []
    QTimer.singleShot(40, lambda: events.append(widget.animating))
    qtbot.waitUntil(lambda: widget.progress > 0, timeout=1000)
    rect = widget.motion_rect(0)
    assert widget.square_rect(chess.E4).center().y() < rect.center().y() < widget.square_rect(chess.E2).center().y()
    assert widget.board.fen() == after.fen()
    qtbot.waitUntil(lambda: not widget.animating, timeout=1500)
    assert events == [True], 'Event loop was blocked by the animation'
    assert widget.board.move_stack == after.move_stack


@pytest.mark.parametrize('fen,uci,captured_square', [
    ('4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1', 'e4d5', chess.D5),
    ('4k3/8/8/3p4/4P3/8/8/4K3 b - - 0 1', 'd5e4', chess.E4),
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'e5d6', chess.D5),
    ('4k3/8/8/8/3Pp3/8/8/4K3 b - d3 0 1', 'e4d3', chess.D4),
])
def test_capture_and_en_passant_have_visible_fade(qtbot, fen, uci, captured_square):
    before = chess.Board(fen)
    widget, after = animated_board(qtbot, before, uci)
    assert widget.transition.captured == before.piece_at(captured_square)
    assert widget.transition.captured_square == captured_square
    widget.animation.pause()
    widget.animation.setCurrentTime(80)
    assert 0.2 < widget.capture_opacity < 0.8
    middle = widget.grab().toImage()
    widget.animation.setCurrentTime(int(widget.animation.duration() * .86))
    assert widget.capture_opacity < 0.05
    assert middle != widget.grab().toImage(), 'Capture frames were identical'
    assert widget.board.fen() == after.fen()


@pytest.mark.parametrize('color,uci,rook_origin,rook_destination', [
    ('w', 'e1g1', chess.H1, chess.F1), ('w', 'e1c1', chess.A1, chess.D1),
    ('b', 'e8g8', chess.H8, chess.F8), ('b', 'e8c8', chess.A8, chess.D8),
])
def test_castling_moves_king_and_rook_on_one_timeline(qtbot, color, uci, rook_origin, rook_destination):
    before = chess.Board(f'r3k2r/8/8/8/8/8/8/R3K2R {color} KQkq - 0 1')
    widget, _ = animated_board(qtbot, before, uci)
    king, rook = widget.transition.motions
    assert king.piece.piece_type == chess.KING
    assert (rook.origin, rook.destination) == (rook_origin, rook_destination)
    assert widget.transition.captured is None
    widget.animation.pause()
    widget.animation.setCurrentTime(80)
    for index, motion in enumerate((king, rook)):
        assert widget.motion_rect(index).center() not in (widget.square_rect(motion.origin).center(), widget.square_rect(motion.destination).center())


@pytest.mark.parametrize('promotion', ['q', 'r', 'b', 'n'])
def test_promotion_crossfades_near_arrival(qtbot, promotion):
    widget, after = animated_board(qtbot, chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1'), 'a7a8' + promotion)
    motion = widget.transition.motions[0]
    assert motion.piece.piece_type == chess.PAWN
    assert motion.promoted_piece == after.piece_at(chess.A8)
    widget.animation.pause()
    widget.animation.setCurrentTime(70)
    assert widget.promotion_blend == 0
    widget.animation.setCurrentTime(int(widget.animation.duration() * .82))
    assert 0 < widget.promotion_blend < 1
    assert widget.motion_rect(0).center().y() < widget.square_rect(chess.A8).center().y() + 2


def test_refresh_preserves_animation_but_snapshot_navigation_cancels(qtbot):
    widget, after = animated_board(qtbot, chess.Board(), 'e2e4')
    widget.animation.pause()
    widget.animation.setCurrentTime(80)
    transition = widget.transition
    widget.set_position(after)  # The worker startup calls refresh again.
    assert widget.transition is transition and widget.animation.currentTime() == 80
    widget.set_position(chess.Board())
    assert not widget.animating and widget.progress == 1


def test_drag_drop_settles_from_pointer_instead_of_replaying_entire_move(qtbot):
    widget = ChessBoard()
    qtbot.addWidget(widget)
    widget.resize(600, 600)
    widget.show()
    widget.interactive = True
    def commit(origin, destination):
        after = widget.board.copy()
        after.push(chess.Move(origin, destination))
        widget.set_position(after, animate=True)
    widget.move_requested.connect(commit)
    start = widget.square_rect(chess.E2).center()
    target = QPointF((widget.square_rect(chess.E4).center() + QPointF(8, -4)).toPoint())
    qtbot.mousePress(widget, Qt.LeftButton, pos=start.toPoint())
    widget.mouseMoveEvent(QMouseEvent(QMouseEvent.MouseMove, target, target, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    qtbot.mouseRelease(widget, Qt.LeftButton, pos=target.toPoint())
    assert widget.animating
    assert (widget.motion_rect(0).center() - target).manhattanLength() < 0.01


@pytest.mark.parametrize('cue', CUES)
def test_bundled_short_pcm_sounds_decode_through_qt(qtbot, cue):
    path = resource_root() / f'resources/sounds/{cue}.wav'
    with wave.open(str(path)) as audio:
        assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
        assert 0.09 <= audio.getnframes() / audio.getframerate() <= 0.4
        pcm = audio.readframes(audio.getnframes())
        samples = struct.unpack(f'<{len(pcm)//2}h', pcm)
        assert 0 < max(abs(value) for value in samples) < 32767 * 0.2
    decoder = QAudioDecoder()
    decoded = []
    done = []
    decoder.bufferReady.connect(lambda: decoded.append(decoder.read().byteCount()))
    decoder.finished.connect(lambda: done.append(True))
    decoder.setSource(QUrl.fromLocalFile(str(path)))
    decoder.start()
    qtbot.waitUntil(lambda: bool(done) or decoder.error() != QAudioDecoder.NoError, timeout=5000)
    assert decoder.error() == QAudioDecoder.NoError, decoder.errorString()
    assert sum(decoded) == len(pcm)
    decoder.stop()


def test_sound_toggle_mutes_and_suppresses_pending_playback(qtbot):
    sounds = SoundPlayer()
    requests = QSignalSpy(sounds.cue_requested)
    sounds.play('move')
    assert requests.count() == 1
    sounds.set_enabled(False)
    sounds.play('capture')
    assert requests.count() == 1 and sounds._pending is None
    assert not any(effect.isPlaying() for effect in sounds.effects.values())
    sounds.set_enabled(True)
    sounds.play('check')
    assert requests.count() == 2
    sounds.stop()


@pytest.mark.parametrize('fen,uci,cue', [
    (chess.STARTING_FEN, 'e2e4', 'move'),
    ('4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1', 'e4d5', 'capture'),
    ('7k/8/8/8/8/8/8/R6K w - - 0 1', 'a1a8', 'check'),
    ('7k/8/5KQ1/8/8/8/8/8 w - - 0 1', 'g6g7', 'end'),
])
def test_game_events_use_custom_cues_and_never_beep(qtbot, tmp_path, monkeypatch, fen, uci, cue):
    from PySide6.QtWidgets import QApplication
    monkeypatch.setattr(QApplication, 'beep', lambda: pytest.fail('System beep must never be called'))
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.session.resume(GameState(board=chess.Board(fen)))
    window.session.save()
    window.refresh()
    monkeypatch.setattr(window, 'advance', lambda: None)
    requests = QSignalSpy(window.sounds.cue_requested)
    window.commit_move(chess.Move.from_uci(uci))
    assert requests.count() == 1 and requests.at(0) == [cue]
    window.close()
