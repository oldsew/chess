"""Presentation regressions: reversed moves, branch review, semantic color and teaching facts."""
import json

import chess
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.services.analysis_explainer import explain
from app.services.game import GameState
from app.services.live import PositionIndicator
from app.ui.board import ChessBoard
from app.ui.dialogs import AnalysisDialog
from app.ui.style import ADVANTAGE_COLORS, show_advantage, fit_window
from app.ui.transitions import MoveTransition
from app.ui.window import MainWindow
from test_coaching import info, loss_notes, LOSS_FEN
from test_live import evaluation

CASES = [
    (chess.STARTING_FEN,'e2e4',None,1,False),
    ('4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1','e4d5',chess.D5,1,False),
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1','e5d6',chess.D5,1,False),
    ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','e1g1',None,2,False),
    ('r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1','e8c8',None,2,False),
    ('7k/P7/8/8/8/8/8/7K w - - 0 1','a7a8q',None,1,True),
    ('r6k/1P6/8/8/8/8/8/7K w - - 0 1','b7a8n',chess.A8,1,True),
]


@pytest.mark.parametrize('fen,uci,captured,count,promotion',CASES)
def test_historical_transition_in_both_directions(qtbot,fen,uci,captured,count,promotion):
    before = chess.Board(fen)
    after = before.copy();after.push_uci(uci)
    board = ChessBoard();qtbot.addWidget(board);board.resize(480,480);board.show()
    for start,target,reverse in [(before,after,False),(after,before,True)]:
        board.set_position(start)
        board.set_position(target,animate=True,celebrate=False)
        transition = board.transition
        assert transition and transition.reverse == reverse
        assert len(transition.motions) == count
        assert transition.captured_square == captured
        assert bool(transition.motions[0].promoted_piece) == promotion
        assert transition.motions[0].origin == (chess.Move.from_uci(uci).to_square if reverse else chess.Move.from_uci(uci).from_square)
        if promotion and reverse:
            assert transition.motions[0].piece.piece_type != chess.PAWN
            assert transition.motions[0].promoted_piece.piece_type == chess.PAWN
        board.animation.pause();board.animation.setCurrentTime(20)
        early = board.grab().toImage()
        if captured:
            assert board.capture_opacity < .1 if reverse else board.capture_opacity > .9
        board.animation.setCurrentTime(210)
        if reverse and promotion:
            assert board.promotion_blend==1
        if captured:
            assert board.capture_opacity > .95 if reverse else board.capture_opacity < .05
        assert board.grab().toImage() != early
        assert board.board.fen() == target.fen() and board.board.move_stack == target.move_stack
        assert not board.presenting_end


def test_unrelated_branches_are_controlled_snapshots(qtbot):
    first = chess.Board();first.push_uci('e2e4')
    other = chess.Board();other.push_uci('d2d4')
    assert MoveTransition.between(first,other) is None
    board=ChessBoard();qtbot.addWidget(board)
    board.set_position(first);board.set_position(other,animate=True,celebrate=False)
    assert not board.animating and board.board.fen()==other.fen()


def test_rapid_history_navigation_retains_game_pgn_clocks_and_latest(qtbot,tmp_path,monkeypatch):
    w=MainWindow(tmp_path);qtbot.addWidget(w)
    w.board.animations_enabled=True  # Test motion even on runners with Windows reduced motion.
    w.show()
    monkeypatch.setattr(w,'advance',lambda:None)
    w.session.start(chess.WHITE)
    for uci in ['e2e4','d7d5','e4d5','d8d5','b1c3','d5e5']:
        w.session.play(chess.Move.from_uci(uci))
    w.refresh();original=w.game.pgn(),w.game.board.fen()
    for _ in range(5):
        for _ in range(6):w.previous_position()
        for _ in range(6):w.next_position()
    assert w.board.animating and not w.board.transition.reverse
    assert (w.game.pgn(),w.game.board.fen())==original
    qtbot.waitUntil(lambda:not w.board.animating,timeout=2000)
    assert w.board.board.fen()==original[1]
    w.previous_position();w.previous_position();w.current_position()
    assert not w.navigator.viewing and w.board.board.fen()==original[1]
    assert not w.board.animating  # Return across multiple plies is an intentional immediate skip.
    w.close()


def test_historical_mate_never_replays_result_pulse(qtbot):
    before=chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
    after=before.copy();after.push_uci('g6g7')
    b=ChessBoard();qtbot.addWidget(b);b.set_position(before)
    b.set_position(after,animate=True,celebrate=False)
    assert b.animating and not b.presenting_end
    qtbot.waitUntil(lambda:not b.animating,timeout=1500)
    assert not b.presenting_end and not b.mate_animation.currentTime()


def test_material_explanation_recommends_preservation_with_evidence():
    notes=loss_notes();value=notes['explanation']
    assert value['confidence']=='high' and value['material_delta']==-9
    assert value['chosen_recommendation']=='d1d2'
    assert 'сохраняет материал' in value['recommendation']
    assert value['pv']==notes['alternatives'][0]['pv_uci']
    assert len(value['highlights'])==2


def test_low_confidence_explains_observed_development_without_inventing_error():
    from app.services.coaching import build_coaching
    b=chess.Board()
    notes=build_coaching(b,chess.Move.from_uci('a2a3'),info(100,'g1f3'),
                         info(0,'e7e5 g1f3 b8c6'),[info(100,'g1f3 e7e5 e2e4')],True)
    value=notes['explanation']
    assert value['confidence']=='low' and value['detected_motif']=='development'
    assert 'исходной горизонтали' in value['recommendation']
    assert 'короля' not in value['reason'] and 'структур' not in value['reason']


@pytest.mark.parametrize('color',[True,False])
def test_factual_center_idea_is_color_independent(color):
    b=chess.Board() if color else chess.Board().mirror()
    played=chess.Move.from_uci('a2a3' if color else 'a7a6')
    best=chess.Move.from_uci('e2e4' if color else 'e7e5')
    value=explain(b,played,{'confidence':'fallback','alternatives':[{'uci':best.uci(),'san':b.san(best),'pv_uci':[best.uci()],'mate':None}]},color)
    assert value['confidence']=='low' and value['detected_motif']=='center'
    assert chess.square_name(best.to_square) in value['recommendation']


def test_open_file_is_factual_and_invalid_recommendation_is_not_used():
    b=chess.Board('6k1/5ppp/8/8/8/8/PP3PPP/3R2K1 w - - 0 1')
    notes={'confidence':'fallback','alternatives':[{'uci':'d1e1','san':'Re1','pv_uci':['d1e1'],'mate':None}]}
    value=explain(b,chess.Move.from_uci('d1d2'),notes,True)
    assert value['detected_motif']=='open_file' and 'нет пешек' in value['recommendation']
    notes['alternatives'][0]['uci']='d1e2'
    value=explain(b,chess.Move.from_uci('d1d2'),notes,True)
    assert value['chosen_recommendation'] is None and len(value['highlights'])==1


@pytest.mark.parametrize('cp',[-300,-150,-60,0,60,150,300])
def test_colors_match_stable_categories_and_player_color(cp):
    label=QLabel();indicator=PositionIndicator()
    indicator.update(evaluation(cp),chess.BLACK)
    show_advantage(label,indicator)
    assert ADVANTAGE_COLORS[indicator.level] in label.styleSheet()
    assert indicator.text # Text remains the actual meaning, not just color.


def test_recommendation_animation_before_position_and_return(qtbot):
    game=GameState(board=chess.Board(LOSS_FEN));game.play(chess.Move.from_uci('d1d4'))
    notes=loss_notes()
    row={'result':'0-1','accuracy':30.,'player_color':True,'pgn':game.pgn(),
         'analysis':json.dumps([{'ply':1,'san':'Qd4','best_san':'Qd2','category':'Грубая ошибка','cpl':1000,
                                'before_cp':400,'after_cp':-600,'coaching':notes}])}
    dialog=AnalysisDialog(row);qtbot.addWidget(dialog);dialog.show()
    dialog.board.animations_enabled=True
    assert dialog.showing_before and dialog.board.board.fen()==game.board.root().fen()
    assert len(dialog.board.annotations)==2 and dialog.actual_button.isEnabled()
    actual=dialog.game.pgn()
    dialog.variations.setCurrentRow(0)
    assert dialog.board.animating and not dialog.board.interactive
    dialog.step_variation(1);dialog.step_variation(-1)
    assert dialog.board.transition.reverse
    dialog.return_to_actual()
    assert dialog.board.board.fen()==game.board.fen() and dialog.game.pgn()==actual
    assert not dialog.board.annotations


@pytest.mark.parametrize('width,height',[(1366,768),(1092,614),(910,512)])
def test_small_laptop_layout_preserves_clock_navigation_and_board(qtbot,tmp_path,width,height):
    w=MainWindow(tmp_path);qtbot.addWidget(w);w.show();w.resize(width,height)
    qtbot.wait(30)
    assert w.width()<=width and w.height()<=height
    assert min(w.board.width(),w.board.height())>=300
    for widget in [w.player_clock,w.bot_clock,w.previous_button,w.current_button,w.save_button]:
        rect=widget.rect();origin=widget.mapTo(w,rect.topLeft())
        assert origin.y()+rect.height()<=w.height()
    w.close()


def test_explanation_of_missed_capture_uses_material_evidence():
    from app.services.coaching import build_coaching
    b=chess.Board('6k1/5ppp/8/8/3q4/8/PP3PPP/3Q2K1 w - - 0 1')
    notes=build_coaching(b,chess.Move.from_uci('d1e2'),info(800,'d1d4'),
                         info(0,'g8h8 e2e3 h8g8'),[info(800,'d1d4 g8h8 d4e3')],True)
    value=notes['explanation']
    assert value['confidence']=='high' and value['reason_type']=='missed_capture'
    assert 'выиграть материал' in value['recommendation'] and '+9' in value['recommendation']


def test_mate_explanation_is_separate_and_recommends_verified_finish():
    from app.services.coaching import build_coaching
    b=chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
    notes=build_coaching(b,chess.Move.from_uci('g6h6'),info(0,'g6g7',mate=1),
                         info(500,'h8g8'),[info(0,'g6g7',mate=1)],True)
    value=notes['explanation']
    assert value['confidence']=='high' and value['detected_motif']=='mate'
    assert 'сразу ставит мат' in value['recommendation'] and 'нет законного ответа' in value['recommendation']


def test_analysis_respects_system_reduced_motion(qtbot,monkeypatch):
    monkeypatch.setattr('app.ui.dialogs.system_motion_enabled',lambda:False)
    game=GameState()
    dialog=AnalysisDialog({'analysis':'[]','pgn':game.pgn(),'player_color':True,'result':'*','accuracy':0.})
    qtbot.addWidget(dialog)
    assert not dialog.board.animations_enabled
    after=chess.Board();after.push_uci('e2e4')
    dialog.board.set_position(after,animate=True,celebrate=False)
    assert not dialog.board.animating and dialog.board.board.fen()==after.fen()


@pytest.mark.parametrize('width,height',[(1366,768),(1092,614),(910,512)])
def test_initial_window_size_fits_logical_monitor_space(qtbot,tmp_path,monkeypatch,width,height):
    from types import SimpleNamespace
    from PySide6.QtCore import QRect
    w=MainWindow(tmp_path);qtbot.addWidget(w)
    monkeypatch.setattr(w,'screen',lambda:SimpleNamespace(availableGeometry=lambda:QRect(0,0,width,height)))
    fit_window(w,1080,750);w.show()
    qtbot.wait(30)
    assert w.width()<width and w.height()<height
    assert min(w.board.width(),w.board.height())>=300
    w.close()
