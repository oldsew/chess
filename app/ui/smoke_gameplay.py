"""Deterministic clock/UI checks plus real Stockfish and mate presentation in the executable."""
from __future__ import annotations

import json
import time

import chess
from PySide6.QtCore import QTimer

from app.services.clocks import TIME_CONTROLS, time_control
from app.services.game import GameState
from app.services.session import Session


class SmokeTime:
    """Inject elapsed intervals, so a flag test never waits a full minute in CI."""
    def __init__(self):
        self.value = 1000.

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def attach_gameplay_smoke(app, window, report_path):
    now = SmokeTime()
    window.session = Session(window.store, now)
    window.board.animations_enabled = True
    window.settings.values['sound'] = True
    window.settings.values['developer_mode'] = True
    window.apply_settings()
    window.board.animations_enabled = True
    state = {'phase': 'presets', 'index': 0, 'presets': [], 'results': [],
             'mate_frames': 0, 'mate_motion_seen': False, 'started': time.monotonic(), 'cues': []}
    window.sounds.cue_requested.connect(state['cues'].append)
    original_show_result = window.show_result

    def show_result(game, profile, metrics):
        assert not window.board.presenting_end and not window.board.animating, 'Result interrupted board presentation'
        state['results'].append({'termination': game.termination, 'result': game.result, 'rating_games': profile.games})
        original_show_result(game, profile, metrics)

    window.show_result = show_result
    timer = QTimer(window)
    timer.setInterval(20)

    def finish(success, message):
        timer.stop()
        report = {'success': success, 'message': message, 'window_visible': window.isVisible(),
                  'database_created': (window.directory / 'chess.sqlite3').is_file(),
                  'settings_created': (window.directory / 'settings.json').is_file(),
                  'presets': state['presets'], 'black_indicator': state.get('black_indicator'),
                  'mate_frames': state['mate_frames'], 'results': state['results'], 'cues': state['cues'],
                  'simulated_elapsed_for_timeout': True}
        window.grab().save(str(report_path.with_suffix('.png')))
        window.close()
        report['engine_closed'] = window.engine._engine is None
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        app.exit(0 if success else 1)

    def tick():
        try:
            if time.monotonic() - state['started'] > 65:
                raise AssertionError('Gameplay smoke timed out')
            if state['phase'] == 'presets':
                if state['index'] < len(TIME_CONTROLS):
                    control = TIME_CONTROLS[state['index']]
                    window.time_combo.setCurrentIndex(window.time_combo.findData(control.key))
                    game = window.session.start(chess.WHITE, control)
                    window.refresh()
                    assert window.control_label.text() == control.short_label
                    assert window.player_clock.property('active') is True
                    now.advance(3)
                    assert window.session.play(chess.Move.from_uci('e2e4'))
                    window.refresh()
                    assert window.bot_clock.property('active') is True
                    if control.timed:
                        assert window.session.clock.remaining(chess.WHITE) == control.initial_seconds - 3 + control.increment
                    now.advance(4)
                    assert window.session.play(chess.Move.from_uci('e7e5'))
                    window.refresh()
                    if control.timed:
                        assert window.session.clock.remaining(chess.BLACK) == control.initial_seconds - 4 + control.increment
                    else:
                        assert window.player_clock.time.text() == window.bot_clock.time.text() == '∞'
                    original = game.pgn(), game.board.fen()
                    window.previous_position()
                    assert window.navigator.ply == 1 and not window.board.interactive
                    assert not window.resign_button.isEnabled()
                    window.human_move(chess.G1,chess.F3)
                    assert (game.pgn(),game.board.fen()) == original
                    before = window.session.clock.remaining(chess.WHITE)
                    now.advance(5)
                    window.tick_clocks()
                    if control.timed:
                        assert window.session.clock.remaining(chess.WHITE) == before - 5
                    window.next_position()
                    window.previous_position()
                    window.current_position()
                    assert window.board.board.fen() == game.board.fen() and not window.navigator.viewing
                    window.session.pause()
                    loaded = window.store.load_game(game.database_id)
                    snapshot = loaded.clock_state.copy()
                    now.advance(3600)
                    window.session.resume(loaded)
                    assert loaded.clock_state == snapshot, 'Resume charged application downtime'
                    state['presets'].append({'control':control.key, 'increment':control.increment,
                                             'navigation':True, 'restore':True})
                    state['index'] += 1
                    return
                window.time_combo.setCurrentIndex(window.time_combo.findData('3+2'))
                window._start_game(chess.BLACK)
                state['phase'] = 'black'
                return
            if state['phase'] == 'black':
                if window.busy or window.board.animating:
                    return
                assert len(window.game.board.move_stack) == 1, 'Real Stockfish did not reply for black player'
                debug = window.indicator.debug
                if debug.get('fen') != window.game.board.fen():
                    return
                assert debug['evaluation_white_cp'] is not None
                assert debug['evaluation_player_cp'] == -debug['evaluation_white_cp']
                assert window.game.player_color == chess.BLACK and window.board.orientation == chess.BLACK
                assert window.session.clock.active == chess.BLACK
                assert window.debug.isVisible() and 'evaluation_player_cp' in window.debug.toPlainText()
                state['black_indicator'] = debug
                window.grab().save(str(report_path.with_name('gameplay-black.png')))
                window.invalidate_worker()
                game = GameState(board=chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1'),
                                 time_control=time_control('5+3'))
                window.session.resume(game)
                window.navigator.current()
                window.refresh()
                window.human_move(chess.G6,chess.G7)
                assert game.result == '1-0' and game.termination == 'checkmate'
                assert window.board.presenting_end and not window.session.clock.running
                state['mate_pgn'] = game.pgn()
                state['phase'] = 'mate'
                return
            if state['phase'] == 'mate':
                assert window.game.pgn() == state['mate_pgn'], 'Presentation changed PGN'
                if window.board.presenting_end:
                    assert not state['results'], 'Mate result opened before pulse ended'
                    if not window.board.animating and 0 < window.board.mate_progress < 1:
                        state['mate_frames'] += 1
                        state['mate_motion_seen'] = True
                        if state['mate_frames'] == 8:
                            window.grab().save(str(report_path.with_name('gameplay-mate.png')))
                    return
                if window.busy or not state['results']:
                    return
                assert state['mate_frames'] >= 5 and state['mate_motion_seen']
                row = window.store.history()[0]
                assert row['rated'] and row['termination'] == 'checkmate' and row['result'] == '1-0'
                assert window.store.profile().games == 1
                window.show_analysis(window.game.database_id)
                window.show_history()
                assert len(window.dialogs) >= 3
                window.time_combo.setCurrentIndex(window.time_combo.findData('1+0'))
                window._start_game(chess.WHITE)
                now.advance(61)
                window.tick_clocks()
                assert window.game.result == '0-1' and window.game.termination == 'timeout'
                assert window.player_clock.time.text() == '0:00.0'
                assert window.result_title(window.game) == 'Поражение по времени'
                state['phase'] = 'timeout'
                return
            if state['phase'] == 'timeout':
                if window.busy or len(state['results']) < 2:
                    return
                assert window.store.history()[0]['termination'] == 'timeout'
                assert window.store.history()[0]['rated'] and window.store.profile().games == 2
                assert state['cues'].count('end') == 2
                finish(True, 'All seven controls, increments, clocks in history, paused restore, black POV, real engine, mate pulse/result/analysis and timeout passed')
        except Exception as error:
            finish(False, f'{type(error).__name__}: {error}')

    timer.timeout.connect(tick)
    timer.start()
    return timer
