import chess
from PySide6.QtCore import Qt

from app.database.store import Store
from app.services.game import GameState
from app.services.material import MaterialSnapshot, material_balance
from app.ui.navigation import PositionNavigator
from app.ui.window import MainWindow


def capture_game():
    game = GameState()
    for uci in ['e2e4','d7d5','e4d5','d8d5','b1c3','d5e5','f1e2','e5c3']:
        game.play(chess.Move.from_uci(uci))
    return game


def test_captured_counts_and_standard_material():
    game = capture_game()
    before = game.pgn()
    snapshot = MaterialSnapshot.from_board(game.board)
    assert snapshot.white_lost == (chess.KNIGHT,chess.PAWN)
    assert snapshot.black_lost == (chess.PAWN,)
    assert snapshot.balance(chess.WHITE) == -3
    assert snapshot.balance(chess.BLACK) == 3
    assert game.pgn() == before


def test_multiple_identical_pieces_ordered_and_no_kings():
    board = chess.Board('4k3/8/8/8/pp6/8/Q7/4K3 w - - 0 1')
    for uci in ['a2a4','e8e7','a4b4']:
        board.push_uci(uci)
    assert MaterialSnapshot.from_board(board).black_lost == (chess.PAWN,chess.PAWN)
    assert chess.KING not in MaterialSnapshot.from_board(board).white_lost


def test_en_passant_and_promotions_are_real_captures_only():
    board = chess.Board('7k/8/8/3pP3/8/8/8/7K w - d6 0 1')
    board.push_uci('e5d6')
    assert MaterialSnapshot.from_board(board).black_lost == (chess.PAWN,)
    board = chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1')
    board.push_uci('a7a8q')
    assert MaterialSnapshot.from_board(board).white_lost == ()
    assert material_balance(board,chess.WHITE) == 9
    board = chess.Board('1r5k/P7/8/8/8/8/8/7K w - - 0 1')
    board.push_uci('a7b8q')
    assert MaterialSnapshot.from_board(board).black_lost == (chess.ROOK,)
    assert MaterialSnapshot.from_board(board).white_lost == ()


def test_history_material_current_and_database_restore(tmp_path):
    game = capture_game()
    nav = PositionNavigator()
    nav.select(2,game.board)
    assert MaterialSnapshot.from_board(nav.position(game.board)).black_lost == ()
    nav.select(3,game.board)
    assert MaterialSnapshot.from_board(nav.position(game.board)).black_lost == (chess.PAWN,)
    nav.current()
    current = MaterialSnapshot.from_board(nav.position(game.board))
    store = Store(tmp_path/'db.sqlite3')
    store.save_game(game)
    store.close()
    store = Store(tmp_path/'db.sqlite3')
    assert MaterialSnapshot.from_board(store.load_game(game.database_id).board) == current
    store.close()


def test_material_strips_follow_display_not_live_game(qtbot,tmp_path,monkeypatch):
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    monkeypatch.setattr(window,'advance',lambda:None)
    game = capture_game()
    window.session.resume(game)
    window.refresh()
    assert window.top_material.snapshot.black_lost == (chess.PAWN,)
    assert window.bottom_material.snapshot.white_lost == (chess.KNIGHT,chess.PAWN)
    window.navigator.select(2,game.board)
    window.refresh()
    assert window.top_material.snapshot.black_lost == ()
    assert window.bottom_material.snapshot.white_lost == ()
    window.current_position()
    assert window.bottom_material.snapshot.white_lost == (chess.KNIGHT,chess.PAWN)
    assert len(game.board.move_stack) == 8
    window.close()
