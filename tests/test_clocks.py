import json
import sqlite3
from dataclasses import asdict

import chess
import pytest

from app.adaptive.rating import PlayerProfile
from app.database.store import Store
from app.services.clocks import ChessClock, TIME_CONTROLS, TimeControl, time_control
from app.services.game import GameState
from app.services.session import Session
from app.ui.clocks import format_time


class Now:
    def __init__(self):
        self.value = 1000.

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


@pytest.mark.parametrize('control', TIME_CONTROLS, ids=lambda c: c.key)
def test_presets_start_switch_and_increment(control):
    now = Now()
    clock = ChessClock(control, now)
    assert not clock.running
    clock.start(chess.WHITE)
    now.advance(4)
    expected = None if not control.timed else control.initial_seconds - 4
    assert clock.remaining(chess.WHITE) == expected
    assert clock.remaining(chess.BLACK) == control.initial_seconds
    assert clock.complete_move(chess.WHITE)
    assert clock.active == chess.BLACK
    if control.timed:
        assert clock.remaining(chess.WHITE) == expected + control.increment
    now.advance(2)
    assert clock.complete_move(chess.BLACK)
    assert clock.active == chess.WHITE
    assert clock.remaining(chess.BLACK) == (control.initial_seconds - 2 + control.increment if control.timed else None)


def test_clock_independent_of_ui_updates_never_negative_or_revived_by_increment():
    now = Now()
    clock = ChessClock(time_control('1+0'), now)
    clock.start(chess.BLACK)
    now.advance(200)
    assert clock.flagged() is chess.BLACK
    assert clock.remaining(chess.BLACK) == 0
    assert not clock.complete_move(chess.BLACK)
    assert clock.remaining(chess.BLACK) == 0
    assert '-' not in format_time(clock.remaining(chess.BLACK))


@pytest.mark.parametrize('color', [chess.WHITE, chess.BLACK])
def test_timeout_rejects_late_move_and_persists_reason(tmp_path, color):
    now = Now()
    store = Store(tmp_path / 'db.sqlite3')
    session = Session(store, now)
    game = session.start(color, time_control('1+0'))
    if color == chess.BLACK:
        session.play(chess.Move.from_uci('e2e4'))
    before = game.board.fen(), game.board.move_stack[:]
    now.advance(61)
    assert not session.play(next(iter(game.board.legal_moves)))
    assert (game.board.fen(), game.board.move_stack) == before
    assert game.result == ('0-1' if color else '1-0')
    assert game.termination == 'timeout'
    assert not session.clock.running
    assert session.clock.remaining(color) == 0
    loaded = store.load_game(game.database_id)
    assert loaded.termination == 'timeout'
    assert loaded.clock_state['state'] == 'finished'
    assert 'time forfeit' in loaded.pgn()
    store.close()


def test_timeout_with_bare_king_is_draw(tmp_path):
    now = Now()
    store = Store(tmp_path / 'db.sqlite3')
    game = GameState(board=chess.Board('7k/8/8/8/8/8/8/KQ6 w - - 0 1'), time_control=time_control('1+0'))
    session = Session(store, now)
    session.resume(game)
    now.advance(60)
    assert session.check_timeout()
    assert game.result == '1/2-1/2' and game.termination == 'timeout'
    store.close()


def test_save_restore_and_no_time_spent_when_closed(tmp_path):
    now = Now()
    path = tmp_path / 'db.sqlite3'
    store = Store(path)
    session = Session(store, now)
    game = session.start(chess.BLACK, time_control('3+2'))
    now.advance(5)
    session.play(chess.Move.from_uci('e2e4'))
    now.advance(7)
    session.pause()
    snapshot = game.clock_state.copy()
    assert snapshot['white_seconds'] == 177
    assert snapshot['black_seconds'] == 173
    assert snapshot['active_color'] == 'black'
    assert snapshot['state'] == 'paused'
    assert snapshot['initial_seconds'] == 180 and snapshot['increment'] == 2
    store.close()
    now.advance(86400)
    store = Store(path)
    loaded = store.unfinished()
    assert loaded.clock_state == snapshot
    restored = ChessClock.restore(loaded.time_control, snapshot, now)
    now.advance(500)
    assert restored.remaining(chess.BLACK) == 173 and not restored.running
    resumed = Session(store, now)
    resumed.resume(loaded)
    assert resumed.clock.remaining(chess.BLACK) == 173
    assert resumed.clock.remaining(chess.WHITE) == 177
    now.advance(10)
    assert resumed.clock.remaining(chess.BLACK) == 163
    resumed.save()
    assert store.load_game(loaded.database_id).clock_state['black_seconds'] == 163
    assert loaded.elapsed_seconds == 22
    store.close()


def test_live_autosave_snapshot_does_not_pause_or_double_charge(tmp_path):
    now = Now()
    store = Store(tmp_path / 'db.sqlite3')
    session = Session(store, now)
    game = session.start(chess.WHITE, time_control('5+3'))
    now.advance(2)
    session.save()
    now.advance(3)
    session.save()
    assert session.clock.running and session.clock.remaining(chess.WHITE) == 295
    assert game.elapsed_seconds == 5
    assert store.unfinished().clock_state['white_seconds'] == 295
    store.close()


def test_custom_control_and_validation():
    custom = TimeControl('7+4', '7+4', 420, 4, 'blitz')
    assert TimeControl(**custom.as_dict()) == custom
    assert custom.pgn_value == '420+4'
    for initial, increment in [(0, 0), (-1, 0), (float('inf'), 0), (60, -1), (60, float('nan'))]:
        with pytest.raises(ValueError):
            TimeControl(initial_seconds=initial, increment=increment)


def test_additive_legacy_migration_preserves_pgn_profile_and_rating(tmp_path):
    path = tmp_path / 'old.sqlite3'
    store = Store(path)
    session = Session(store)
    game = session.start(chess.WHITE)
    session.play(chess.Move.from_uci('e2e4'))
    original_pgn = game.pgn()
    profile = PlayerProfile(rating=1432, games=19)
    store.connection.execute('INSERT INTO profile VALUES(1,?)', (json.dumps(asdict(profile)),))
    store.connection.execute('UPDATE games SET rating_after=1440, rated=1 WHERE id=?', (game.database_id,))
    store.connection.commit()
    for column in ['time_control', 'clock_state', 'termination']:
        store.connection.execute(f'ALTER TABLE games DROP COLUMN {column}')
    store.connection.commit()
    store.close()
    store = Store(path)
    row = store.history()[0]
    assert row['pgn'] == original_pgn and row['rated'] == 1 and row['rating_after'] == 1440
    assert store.profile() == profile
    loaded = store.load_game(game.database_id)
    assert loaded.time_control == TimeControl() and loaded.clock_state is None
    resumed = Session(store)
    resumed.resume(loaded)
    assert resumed.clock.remaining(chess.WHITE) is None
    assert loaded.pgn() == original_pgn
    store.close()
