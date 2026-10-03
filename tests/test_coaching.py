from dataclasses import asdict
import json

import chess
import chess.engine
import pytest

from app.services.coaching import Variation, build_coaching, format_evaluation
from app.services.engine import EngineService
from app.services.game import GameState
from app.ui.dialogs import AnalysisDialog

LOSS_FEN = 'r5k1/5ppp/8/4p3/8/8/PP3PPP/3Q2K1 w - - 0 1'


def info(cp, pv, color=chess.WHITE, mate=None):
    return {'score':chess.engine.PovScore(chess.engine.Mate(mate) if mate is not None else chess.engine.Cp(cp),color),
            'pv':[chess.Move.from_uci(m) for m in pv.split()], 'depth':16}


def loss_notes():
    before = chess.Board(LOSS_FEN)
    return build_coaching(before,chess.Move.from_uci('d1d4'), info(400,'d1d2'),
                          info(-600,'e5d4 g1f1 a8c8 f1e1 c8c2'),
                          [info(400,'d1d2 a8c8 d2d3'),info(380,'d1e2 a8c8 e2d3'),info(350,'d1f3 a8c8 f3d3')],chess.WHITE)


def test_short_pv_is_legal_and_never_more_than_six_plies():
    board = chess.Board()
    value = Variation.from_info(board,info(84,'e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6'),chess.WHITE)
    assert len(value.pv_uci) == 6
    assert value.pv_san == '1. e4  1… e5  2. Nf3  2… Nc6  3. Bb5  3… a6'
    assert value.san == 'e4' and value.depth == 16
    assert format_evaluation(value.evaluation_cp) == '+0.84'
    for uci in value.pv_uci:
        board.push_uci(uci)


def test_piece_loss_is_supported_by_actual_legal_line():
    notes = loss_notes()
    assert len(notes['alternatives']) == 3
    assert notes['reason'] == 'material_loss' and notes['confidence'] == 'legal_pv_material'
    assert 'ферзя' in notes['advice'] and 'показанном' in notes['advice']
    assert notes['evidence'][0]['played_line_material_change'] == -9
    assert notes['evidence'][0]['best_line_material_change'] == 0


def test_missed_capture_proved_by_recommended_line():
    before = chess.Board('6k1/5ppp/8/8/3q4/8/PP3PPP/3Q2K1 w - - 0 1')
    notes = build_coaching(before,chess.Move.from_uci('d1e2'),info(800,'d1d4'),
                          info(0,'g8h8 e2e3 h8g8'),
                          [info(800,'d1d4 g8h8 d4e3')],chess.WHITE)
    assert notes['reason'] == 'missed_capture'
    assert 'выгодное взятие' in notes['advice']


@pytest.mark.parametrize('mate', [1,4])
def test_missed_mate_is_separate_from_cp(mate):
    board = chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
    notes = build_coaching(board,chess.Move.from_uci('g6h6'),info(0,'g6g7',mate=mate),
                          info(500,'h8g8'),[info(0,'g6g7',mate=1)],chess.WHITE)
    assert notes['reason'] == 'missed_mate'
    assert notes['before_cp'] is None and notes['mate_before'] == mate
    assert 'мат сразу' in notes['advice']
    assert format_evaluation(None,mate,True) == 'Форсированный мат'


def test_lost_forced_mate_and_allowed_enemy_mate():
    board = chess.Board(LOSS_FEN)
    alternatives = [info(100,'d1d2 a8c8 d2d3',mate=5)]
    notes = build_coaching(board,chess.Move.from_uci('d1d4'),info(0,'d1d2',mate=5),
                          info(-600,'e5d4 g1f1 a8c8'),alternatives,chess.WHITE)
    assert notes['reason'] == 'missed_forced_mate'
    notes = build_coaching(board,chess.Move.from_uci('d1d4'),info(100,'d1d2'),
                          info(0,'e5d4 g1f1 a8c8',mate=-5),[info(100,'d1d2 a8c8 d2d3')],chess.WHITE)
    assert notes['reason'] == 'allowed_mate'
    assert 'форсированную' in notes['advice'] and notes['after_cp'] is None


def test_fallback_does_not_invent_king_safety_or_pawn_stories():
    board = chess.Board()
    notes = build_coaching(board,chess.Move.from_uci('a2a3'),info(100,'e2e4'),
                          info(0,'e7e5 g1f3 b8c6'),[info(100,'e2e4 e7e5 g1f3')],chess.WHITE)
    assert notes['reason'] is None and notes['confidence'] == 'fallback'
    assert 'не удалось' in notes['advice']
    assert 'короля' not in notes['advice'] and 'структур' not in notes['advice']


def test_short_or_invalid_line_cannot_claim_material_loss():
    board = chess.Board(LOSS_FEN)
    notes = build_coaching(board,chess.Move.from_uci('d1d4'),info(400,'d1d2'),
                          info(-600,'e5d4 a1a8'),[info(400,'d1d2 a8c8 d2d3')],chess.WHITE)
    assert notes['reason'] is None and notes['confidence'] == 'fallback'


def test_equal_exchange_has_no_false_piece_loss():
    board = chess.Board('6k1/5ppp/8/8/3q4/8/PP3PPP/3Q2K1 w - - 0 1')
    # The played queen captures a queen; this is a gain, not a claimed loss of our queen.
    notes = build_coaching(board,chess.Move.from_uci('d1d4'),info(100,'d1e2'),
                          info(0,'g8h8 d4e3 h8g8'),[info(100,'d1e2 g8h8 e2e3')],chess.WHITE)
    assert notes['confidence'] == 'fallback' and notes['reason'] is None


@pytest.mark.parametrize('color', [chess.WHITE,chess.BLACK])
def test_real_multipv_analysis_and_player_perspective(color):
    board = chess.Board(LOSS_FEN)
    move = chess.Move.from_uci('d1d4')
    if color == chess.BLACK:
        board = board.mirror()
        move = chess.Move(chess.square_mirror(move.from_square),chess.square_mirror(move.to_square))
    board.push(move)
    engine = EngineService()
    try:
        moves,metrics = engine.analyse_game(board,color,16)
        assert len(moves) == 1 and metrics.moves == 1
        notes = moves[0].coaching
        assert notes and len(notes['alternatives']) == 3
        assert notes['alternatives'][0]['evaluation_cp'] > notes['after_cp']
        assert notes['reason'] == 'material_loss'
        for alternative in notes['alternatives']:
            position = board.root()
            assert 1 <= len(alternative['pv_uci']) <= 6
            for uci in alternative['pv_uci']:
                position.push_uci(uci)
    finally:
        engine.close()


def test_analysis_ui_variation_is_read_only_and_returns_to_actual(qtbot):
    game = GameState(board=chess.Board(LOSS_FEN))
    game.play(chess.Move.from_uci('d1d4'))
    notes = loss_notes()
    row = {'result':'0-1','accuracy':30.,'average_cpl':1000.,'player_color':True,'pgn':game.pgn(),
           'analysis':json.dumps([{'ply':1,'san':'Qd4','best_san':'Qd2','category':'Грубая ошибка','cpl':1000,
                                  'before_cp':400,'after_cp':-600,'before_label':'+400','after_label':'-600','coaching':notes}])}
    dialog = AnalysisDialog(row)
    qtbot.addWidget(dialog)
    dialog.show()
    actual = dialog.game.pgn()
    assert dialog.variations.count() == 3 and 'ферзя' in dialog.advice.text()
    dialog.variations.setCurrentRow(0)
    assert dialog.board.board.peek().uci() == 'd1d2'
    dialog.step_variation(1)
    assert len(dialog.board.board.move_stack) == 2
    dialog.step_variation(-1)
    assert dialog.game.pgn() == actual and not dialog.board.interactive
    dialog.return_to_actual()
    assert dialog.board.board.fen() == game.board.fen()
    assert dialog.game.pgn() == actual
