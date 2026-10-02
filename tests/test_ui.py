import chess
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent
from app.ui.board import ChessBoard
from app.ui.window import MainWindow
from app.config.settings import Settings


def test_board_orientation_mapping(qtbot):
    board=ChessBoard()
    qtbot.addWidget(board)
    board.resize(600,600)
    for color in [True,False]:
        board.orientation=color
        for square in chess.SQUARES:
            assert board.square_at(board.square_rect(square).center())==square
    assert board.square_at(QPointF(0,0)) is None
    assert all(r.isValid() for r in board.renderers.values())


def test_click_to_move_and_legal_highlight(qtbot):
    board=ChessBoard()
    qtbot.addWidget(board)
    board.interactive=True
    board.show()
    qtbot.mouseClick(board,Qt.LeftButton,pos=board.square_rect(chess.E2).center().toPoint())
    assert board.selected==chess.E2
    with qtbot.waitSignal(board.move_requested) as received:
        qtbot.mouseClick(board,Qt.LeftButton,pos=board.square_rect(chess.E4).center().toPoint())
    assert received.args==[chess.E2,chess.E4]


def test_drag_drop_emits_correct_squares(qtbot):
    board=ChessBoard()
    qtbot.addWidget(board)
    board.interactive=True
    board.show()
    start,end=board.square_rect(chess.D2).center(),board.square_rect(chess.D4).center()
    qtbot.mousePress(board,Qt.LeftButton,pos=start.toPoint())
    event=QMouseEvent(QMouseEvent.MouseMove,end,end,Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    board.mouseMoveEvent(event)
    with qtbot.waitSignal(board.move_requested) as received:
        qtbot.mouseRelease(board,Qt.LeftButton,pos=end.toPoint())
    assert received.args==[chess.D2,chess.D4]


def test_actual_window_play_persist_resume(qtbot,tmp_path):
    window=MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.settings.values['sound']=False
    window.show()
    window._start_game(chess.WHITE)
    assert not window.debug.isVisible()
    qtbot.mouseClick(window.board,Qt.LeftButton,pos=window.board.square_rect(chess.E2).center().toPoint())
    qtbot.mouseClick(window.board,Qt.LeftButton,pos=window.board.square_rect(chess.E4).center().toPoint())
    qtbot.waitUntil(lambda: not window.busy,timeout=12000)
    assert len(window.game.board.move_stack)==2
    saved_fen=window.game.board.fen()
    window.close()
    restored=MainWindow(tmp_path)
    qtbot.addWidget(restored)
    restored.resume_game()
    assert restored.game.board.fen()==saved_fen
    restored.close()


def test_settings_first_run_and_corrupt_file(tmp_path):
    settings=Settings(tmp_path)
    settings.values['theme']='Лес'
    settings.save()
    assert Settings(tmp_path).values['theme']=='Лес'
    (tmp_path/'settings.json').write_text('broken')
    assert Settings(tmp_path).values['theme']=='Сланец'
