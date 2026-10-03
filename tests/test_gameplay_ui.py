import threading

import chess
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QSignalSpy

from app.adaptive.metrics import Performance
from app.services.clocks import time_control
from app.services.game import GameState
from app.services.live import LiveEvaluation
from app.services.session import Session
from app.ui.board import ChessBoard
from app.ui.navigation import PositionNavigator
from app.ui.window import MainWindow
from test_clocks import Now


@pytest.fixture
def board(qtbot):
    widget = ChessBoard()
    qtbot.addWidget(widget)
    widget.resize(600, 600)
    widget.interactive = True
    widget.show()
    return widget


def click(qtbot, widget, square):
    qtbot.mouseClick(widget, Qt.LeftButton, pos=widget.square_rect(square).center().toPoint())


def test_repeat_click_removes_selection_and_all_markers(qtbot, board):
    original = board.grab().toImage()
    click(qtbot, board, chess.G1)
    assert board.selected == chess.G1
    assert board.grab().toImage() != original
    click(qtbot, board, chess.G1)
    assert board.selected is None
    assert board.grab().toImage() == original


def test_switch_selection_and_click_to_move_after_deselect(qtbot, board):
    click(qtbot, board, chess.G1)
    click(qtbot, board, chess.B1)
    assert board.selected == chess.B1
    click(qtbot, board, chess.B1)
    assert board.selected is None
    moves = QSignalSpy(board.move_requested)
    click(qtbot, board, chess.C3)
    assert moves.count() == 0
    click(qtbot, board, chess.B1)
    click(qtbot, board, chess.C3)
    assert moves.count() == 1 and moves.at(0) == [chess.B1,chess.C3]


def test_drag_preselected_piece_still_works_on_second_press(qtbot, board):
    click(qtbot, board, chess.E2)
    origin, target = board.square_rect(chess.E2).center(), board.square_rect(chess.E4).center()
    qtbot.mousePress(board, Qt.LeftButton, pos=origin.toPoint())
    board.mouseMoveEvent(QMouseEvent(QMouseEvent.MouseMove, target, target, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    moves = QSignalSpy(board.move_requested)
    qtbot.mouseRelease(board, Qt.LeftButton, pos=target.toPoint())
    assert moves.count() == 1 and moves.at(0) == [chess.E2,chess.E4]


def test_navigation_keeps_real_board_and_pgn_then_returns_to_latest():
    game = GameState()
    for uci in ['e2e4','e7e5','g1f3']:
        game.play(chess.Move.from_uci(uci))
    original = game.board.fen(), game.pgn(), game.board.move_stack[:]
    nav = PositionNavigator()
    nav.back(game.board)
    assert nav.ply == 2 and len(nav.position(game.board).move_stack) == 2
    nav.back(game.board)
    assert nav.ply == 1
    nav.forward(game.board)
    assert nav.ply == 2
    assert (game.board.fen(), game.pgn(), game.board.move_stack) == original
    game.play(chess.Move.from_uci('b8c6'))
    assert len(nav.position(game.board).move_stack) == 2
    nav.current()
    assert not nav.viewing and len(nav.position(game.board).move_stack) == 4
    nav.back(game.board)
    nav.forward(game.board)
    assert not nav.viewing
    nav.select(-100,game.board)
    assert len(nav.position(game.board).move_stack) == 0


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    widget = MainWindow(tmp_path)
    qtbot.addWidget(widget)
    widget.settings.values['sound'] = False
    monkeypatch.setattr(widget, 'advance', lambda: None)
    widget.show()
    return widget


def test_history_ui_blocks_input_resignation_and_keeps_clocks_running(qtbot, window, monkeypatch):
    now = Now()
    window.session = Session(window.store, now)
    window.session.start(chess.WHITE,time_control('3+2'))
    window.session.play(chess.Move.from_uci('e2e4'))
    window.session.play(chess.Move.from_uci('e7e5'))
    window.refresh()
    original = window.game.board.fen(),window.game.pgn()
    window.previous_position()
    assert window.navigator.ply == 1 and not window.board.interactive
    assert not window.resign_button.isEnabled()
    assert not window.position_label.isVisible()
    assert 'Просмотр партии' in window.status_label.text()
    assert window.move_list.currentRow() == 0
    click(qtbot,window.board,chess.G1)
    assert window.board.selected is None
    window.human_move(chess.G1,chess.F3)
    monkeypatch.setattr('PySide6.QtWidgets.QMessageBox.question', lambda *args: pytest.fail('Cannot resign in history'))
    window.resign()
    assert (window.game.board.fen(),window.game.pgn()) == original
    before = window.session.clock.remaining(chess.WHITE)
    now.advance(10)
    window.tick_clocks()
    assert window.session.clock.remaining(chess.WHITE) == before-10
    window.next_position()
    assert not window.navigator.viewing and window.board.interactive
    assert window.board.board.fen() == window.game.board.fen()
    window.select_position(window.move_list.item(0))
    assert window.navigator.ply == 1
    window.current_position()
    assert not window.navigator.viewing


def test_bot_reply_during_history_keeps_cursor_and_latest_position(window):
    window.session.start(chess.WHITE)
    window.session.play(chess.Move.from_uci('e2e4'))
    window.refresh()
    window.previous_position()
    window.commit_move(chess.Move.from_uci('e7e5'))
    assert window.navigator.ply == 0
    assert window.board.board.fen() == chess.STARTING_FEN
    assert len(window.game.board.move_stack) == 2
    window.current_position()
    assert window.board.board.fen() == window.game.board.fen()


def test_stale_live_scores_and_scores_after_game_end_are_ignored(window):
    window.session.start(chess.BLACK)
    window.refresh()
    value = LiveEvaluation(chess.STARTING_FEN,250,None,None,10,'+250')
    window.on_live(window.token,value)
    assert window.indicator.debug['evaluation_player_cp'] == -250
    text = window.indicator.text
    window.on_live(window.token-1,LiveEvaluation(chess.STARTING_FEN,-250,None,None,10,'-250'))
    assert window.indicator.text == text
    window.session.play(chess.Move.from_uci('e2e4'))
    window.on_live(window.token,value)
    assert window.indicator.text == text
    window.session.resign()
    window.on_live(window.token,LiveEvaluation(window.game.board.fen(),-250,None,None,10,'-250'))
    assert window.indicator.text == text


@pytest.mark.parametrize('animations', [True,False])
def test_mate_result_waits_for_effect_without_changing_outcome(qtbot,window,monkeypatch,animations):
    window.board.animations_enabled = animations
    game = GameState(board=chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1'))
    window.session.resume(game)
    window.refresh()
    shown = []
    monkeypatch.setattr(window,'show_result',lambda *args: shown.append((args,window.board.presenting_end)))
    window.commit_move(chess.Move.from_uci('g6g7'))
    assert game.result == '1-0' and game.termination == 'checkmate'
    assert not window.session.clock.running
    committed_pgn = game.pgn()
    window.analysis_game = game
    window.on_result(window.token,'analysis',([],Performance(100,0,0,0,0)))
    if animations:
        assert window.board.presenting_end and not shown
        qtbot.waitUntil(lambda: window.board.mate_progress > .1,timeout=1500)
        assert not window.board.animating and not shown
        early = window.board.grab().toImage()
        qtbot.waitUntil(lambda: window.board.mate_progress > .4,timeout=1000)
        assert window.board.grab().toImage() != early
        qtbot.waitUntil(lambda: bool(shown),timeout=1500)
    else:
        assert shown and not window.board.animating
    assert shown[0][1] is False
    assert game.pgn() == committed_pgn
    assert window.store.history()[0]['result'] == '1-0'
    assert window.store.history()[0]['termination'] == 'checkmate'
    assert window.store.profile().games == 1


def test_timeout_invalidates_pending_bot_reply(window):
    now = Now()
    window.session = Session(window.store,now)
    window.session.start(chess.BLACK,time_control('1+0'))
    window.refresh()
    token = window.token
    now.advance(61)
    window.tick_clocks()
    assert window.game.result == '0-1' and window.game.termination == 'timeout'
    # A reply queued by Stockfish before the flag must not be accepted afterwards.
    window.on_result(token,'move',object())
    assert not window.game.board.move_stack
    assert window.bot_clock.time.text() == '0:00.0'
    assert window.status_label.text() == 'Победа по времени'
