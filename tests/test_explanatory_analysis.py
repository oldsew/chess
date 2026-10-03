"""Known causes and counterexamples: assert chess evidence, not literary templates."""
import json

import chess
import pytest

from app.config.settings import TUNING
from app.services.coaching import Variation, build_coaching
from app.services.engine import EngineService
from app.services.position_features import features, hanging, tactical_motifs, trace
from app.services.game import GameState
from app.ui.dialogs import AnalysisDialog
from test_coaching import LOSS_FEN, info, loss_notes


CASES = [
    ('fork','4k3/8/8/8/5n2/8/PP3PPP/2RQ2K1 w - - 0 1','d1d2',
     'f4e2 g1f1 e2c1 d2c1','c1c4 f4e2 g1f1 e8e7',100,-200,-2),
    ('pin','5bk1/8/8/8/3pp3/2N5/PP3PPP/3QK3 w - - 0 1','d1d2',
     'f8b4 f2f3 d4c3 b2c3','c3e4 f8b4 e1f1 g8h8',100,-200,-2),
    ('pawn_loss','6k1/8/8/3p4/4P3/8/PP3PPP/5BK1 w - - 0 1','a2a3',
     'd5e4 f1c4 g8h8 c4d5','e4d5 g8h8 f1c4 h8g8',150,-100,-1),
    ('bad_exchange','6k1/5ppp/4p3/3b4/8/8/PP3PPP/3R2K1 w - - 0 1','d1d5',
     'e6d5 g1f1 g8h8','d1e1 g8h8 e1e3',0,-200,-2),
    ('discovered_attack','r5k1/5ppp/8/b7/8/8/1P3KPP/R7 w - - 0 1','b2b3',
     'a5b6 f2f1 a8a1 f1e2','a1b1 a5b6 f2f1 a8a2',100,-500,-5),
    ('overloaded_defender','r2r2k1/5ppp/8/3R4/8/8/1P3PPP/R2Q2K1 w - - 0 1','b2b3',
     'a8a1 d1a1 d8d5 a1b1','a1c1 d8d5 d1d5 a8e8',100,-500,-5),
    ('double_attack','7k/8/8/8/q7/8/1P4PP/3R2K1 w - - 0 1','b2b3',
     'a4d4 g1f1 d4d1 f1f2','d1e1 a4d4 g1f1 d4c4',100,-500,-5),
]


def mirror_uci(uci):
    m=chess.Move.from_uci(uci)
    return chess.Move(chess.square_mirror(m.from_square),chess.square_mirror(m.to_square),m.promotion).uci()


@pytest.mark.parametrize('color',[chess.WHITE,chess.BLACK])
@pytest.mark.parametrize('kind,fen,played,response,best,cp,after,material',CASES)
def test_known_loss_cause_is_backed_by_legal_continuation(color,kind,fen,played,response,best,cp,after,material):
    board=chess.Board(fen)
    if not color:
        board=board.mirror();played=mirror_uci(played)
        response=' '.join(mirror_uci(u) for u in response.split())
        best=' '.join(mirror_uci(u) for u in best.split())
    original=board.fen(),list(board.move_stack)
    notes=build_coaching(board,chess.Move.from_uci(played),info(cp,best,color),
                         info(after,response,color),[info(cp,best,color)],color)
    value=notes['explanation']
    assert value['reason_type']==kind and value['confidence']=='high'
    assert value['material_delta']==material
    assert value['key_squares'] and len(value['highlights'])==2
    assert value['opponent_pv'][0]==response.split()[0]
    assert value['alternatives'][0]['feature_deltas']['best_material_delta']>material
    if kind in ('fork','pin','discovered_attack','overloaded_defender','double_attack'):
        assert value['factors']['detected_tactic']['verified_capture']
    assert (board.fen(),board.move_stack)==original


def test_positional_error_has_comparative_evidence_without_material_loss():
    board=chess.Board()
    notes=build_coaching(board,chess.Move.from_uci('a2a3'),info(80,'e2e4'),
                         info(-10,'e7e5 g1f3 b8c6 e2e3 g8f6 f1b5'),
                         [info(80,'e2e4 e7e5 g1f3 b8c6 f1c4 g8f6')],True)
    value=notes['explanation'];delta=value['alternatives'][0]['feature_deltas']
    assert value['reason_type']=='blocked_piece' and value['confidence']=='medium'
    assert delta['material_delta']==delta['best_material_delta']==0
    assert delta['actual']['piece_mobility'][chess.F1]==0
    assert delta['best']['piece_mobility'][chess.F1]==5
    assert chess.F1 in value['key_squares']


def test_missed_capture_and_mate_explain_real_opportunities():
    board=chess.Board('6k1/5ppp/8/8/3q4/8/PP3PPP/3Q2K1 w - - 0 1')
    value=build_coaching(board,chess.Move.from_uci('d1e2'),info(800,'d1d4'),
                         info(0,'g8h8 e2e3 h8g8'),[info(800,'d1d4 g8h8 d4e3')],True)['explanation']
    assert value['reason_type']=='missed_capture'
    assert value['alternatives'][0]['feature_deltas']['best_material_delta']==9
    board=chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
    value=build_coaching(board,chess.Move.from_uci('g6h6'),info(0,'g6g7',mate=1),
                         info(500,'h8g8'),[info(0,'g6g7',mate=1)],True)['explanation']
    assert value['reason_type']=='missed_mate' and value['confidence']=='high'
    board.push_uci(value['chosen_recommendation']);assert board.is_checkmate()


def test_analysis_keeps_ten_plies_separate_from_six_plies_for_display():
    pv='e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7'
    variation=Variation.from_info(chess.Board(),info(80,pv),True)
    assert len(variation.pv_uci)==6 and len(variation.analysis_pv_uci)==10
    assert variation.analysis_pv_valid
    assert variation.analysis_pv_uci[:6]==variation.pv_uci


def test_invalid_prefix_and_short_unmatched_lines_do_not_prove_a_loss():
    board=chess.Board(LOSS_FEN);played=chess.Move.from_uci('d1d4')
    notes=build_coaching(board,played,info(400,'d1d2'),info(-600,'e5d4 g1f1 a8c8 a1a8'),
                         [info(400,'d1d2 a8c8 d2d3')],True)
    assert not notes['response']['analysis_pv_valid']
    assert notes['explanation']['confidence']!='high'
    notes=build_coaching(board,played,info(400,'d1d2'),info(-600,'e5d4 g1f1 a8c8'),
                         [info(400,'d1d2 a8c8 d2d3')],True,{'equal_depth':True})
    assert notes['explanation']['confidence']!='high'


def test_preexisting_pin_is_not_attributed_to_unrelated_reply():
    board=chess.Board('6k1/8/8/8/1b6/2N5/PP3PPP/3QK3 b - - 0 1')
    line=trace(board,['g8h8'],True)
    assert line['valid']
    assert not [m for m in tactical_motifs(line,True) if m['type']=='pin']


def test_pinned_knight_does_not_supply_illegal_capture_evidence():
    board=chess.Board('4r1k1/8/8/8/5q2/8/P3N3/4K3 b - - 0 1')
    assert board.is_pinned(True,chess.E2)
    assert not any(h['capture']=='e2f4' for h in hanging(board,False))


def test_king_with_no_pawn_shield_is_not_safer_than_one_with_one_pawn():
    with_pawn=chess.Board('6k1/8/8/8/8/8/6P1/6K1 w - - 0 1')
    without=with_pawn.copy();without.remove_piece_at(chess.G2)
    assert features(without,True)['king_danger']>features(with_pawn,True)['king_danger']


def test_fallback_records_all_attempted_checks_and_keeps_uncertain_language():
    board=chess.Board(LOSS_FEN)
    notes=build_coaching(board,chess.Move.from_uci('d1d4'),info(400,'d1d2'),
                         info(-600,'e5d4 g1f1 a8c8'),[info(-700,'d1d2 a8c8 d2d3')],True)
    value=notes['explanation']
    assert value['fallback'] and value['confidence']=='low'
    assert set(value['checks_attempted'])=={'material','attack_maps','mobility','king_safety','development',
                                            'pawn_structure','center_control','tactical_motifs','pv'}
    assert value['reason_type']=='analysis_conflict'


def test_two_alternatives_explain_different_concrete_features_and_responses():
    value=loss_notes()['explanation'];alternatives=value['alternatives']
    assert len(alternatives)==3
    assert len({json.dumps(a['distinguishing_features'],sort_keys=True) for a in alternatives})==3
    assert len({a['idea'] for a in alternatives})==3
    assert all(a['pv'] and a['reply_san'] and a['idea'] for a in alternatives)


def test_selection_keeps_idea_arrow_and_evidence_in_sync_without_altering_game(qtbot):
    game=GameState(board=chess.Board(LOSS_FEN));game.play(chess.Move.from_uci('d1d4'))
    notes=loss_notes()
    row={'result':'0-1','accuracy':30.,'player_color':True,'pgn':game.pgn(),
         'analysis':json.dumps([{'ply':1,'san':'Qd4','best_san':'Qd2','category':'Грубая ошибка',
                                'cpl':1000,'before_cp':400,'after_cp':-600,'coaching':notes}])}
    dialog=AnalysisDialog(row);qtbot.addWidget(dialog);dialog.show()
    dialog.explanation_debug.show()
    original=dialog.game.pgn()
    for index,alternative in enumerate(notes['explanation']['alternatives']):
        dialog.variations.setCurrentRow(index)
        assert dialog.recommendation.text()==alternative['idea']
        selected=chess.Move.from_uci(alternative['uci'])
        assert any(a[1]==selected.to_square for a in dialog.board.annotations)
        assert dialog.board.tactical_highlights==set(alternative['key_squares'])
        debug=json.loads(dialog.explanation_debug.toPlainText())
        assert debug['selected_variant']['uci']==alternative['uci']
        assert dialog.game.pgn()==original
    dialog.return_to_actual();assert not dialog.board.tactical_highlights


def test_fixed_depth_comparison_does_not_reuse_different_depth_discovery_scores(monkeypatch):
    service=EngineService();calls=[]
    monkeypatch.setattr(service,'_configure',lambda options:None)
    def analyse(board,limit,**kwargs):
        calls.append((board.fen(),limit,kwargs))
        if kwargs.get('multipv'):
            return [info(90,'e2e4',color=True),info(80,'d2d4',color=True)]
        # Enough legal continuation without expanding search. Score follows matched search.
        copy=board.copy();pv=[]
        for _ in range(9):
            move=next(iter(copy.legal_moves));pv.append(move);copy.push(move)
        return {'score':info(50,'')['score'],'pv':pv,'depth':limit.depth}
    monkeypatch.setattr(service,'_analyse',analyse)
    _,alternatives,comparison=service._compare_teaching_moves(chess.Board(),chess.Move.from_uci('a2a3'),16)
    assert comparison['equal_depth'] and len(comparison['samples'])==3
    assert all(limit.depth==16 and limit.time is None for _,limit,kwargs in calls if not kwargs)
    assert all(a['score'].pov(True).score()==50 for a in alternatives)
    assert len(calls)==4


def test_real_engine_matched_comparison_and_long_pvs_both_colors():
    service=EngineService()
    try:
        for color in [True,False]:
            board=chess.Board(LOSS_FEN);played=chess.Move.from_uci('d1d4')
            if not color:board=board.mirror();played=chess.Move.from_uci(mirror_uci(played.uci()))
            board.push(played)
            rows,_=service.analyse_game(board,color,16);notes=rows[0].coaching
            assert notes['comparison']['equal_depth']
            assert all(s['terminal'] or s['depth']==16 for s in notes['comparison']['samples'])
            value=notes['explanation'];assert value['reason_type']=='material_loss' and value['confidence']=='high'
            assert 6<=len(value['opponent_pv'])+1<=10
            for alternative in notes['alternatives']:
                line=trace(board.root(),alternative['analysis_pv_uci'],color)
                assert line['valid'] and (6<=len(line['moves'])<=10 or line['terminal'])
                assert len(alternative['pv_uci'])<=6
    finally:service.close()
