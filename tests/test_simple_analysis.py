import copy
import json
import re

import chess
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from app.services.coaching import build_coaching
from app.services.game import GameState
from app.services.simple_analysis import describe_move, present_simple
from app.ui.dialogs import AnalysisDialog
from test_coaching import LOSS_FEN, info, loss_notes
from test_explanatory_analysis import CASES, mirror_uci

TECHNICAL = re.compile(r'\b(?:Stockfish|CPL|PV|MultiPV)\b|[+-]\d+\.\d+|\b[BNRQK][a-h][1-8]|материал|связк|вилк|темп',re.I)


def row_with_notes(notes=None,color=True):
    board=chess.Board(LOSS_FEN)
    move=chess.Move.from_uci('d1d4')
    if not color:board=board.mirror();move=chess.Move.from_uci(mirror_uci(move.uci()))
    game=GameState(board=board,player_color=color);game.play(move)
    return {'result':'0-1' if color else '1-0','accuracy':30.,'player_color':color,'pgn':game.pgn(),
            'analysis':json.dumps([{'ply':1,'san':board.root().san(move),'best_san':'Qd2' if color else 'Qd7',
                                   'category':'Грубая ошибка','cpl':1000,'before_cp':400,'after_cp':-600,
                                   'coaching':notes}])}


@pytest.mark.parametrize('color',[True,False])
@pytest.mark.parametrize('kind,fen,played,response,best,cp,after,material',CASES)
def test_simple_explanation_retains_cause_without_notation_or_engine_numbers(color,kind,fen,played,response,best,cp,after,material):
    board=chess.Board(fen)
    if not color:
        board=board.mirror();played=mirror_uci(played)
        response=' '.join(mirror_uci(u) for u in response.split())
        best=' '.join(mirror_uci(u) for u in best.split())
    move=chess.Move.from_uci(played)
    notes=build_coaching(board,move,info(cp,best,color),info(after,response,color),[info(cp,best,color)],color)
    original=copy.deepcopy(notes);original_fen=board.fen()
    simple=present_simple(board,move,notes['explanation'])
    assert simple['kind']==kind and simple['confidence']=='high'
    assert all(simple[key] for key in ('why','consequence','recommendation','principle'))
    assert not TECHNICAL.search(' '.join(simple[k] for k in ('why','consequence','recommendation','principle')))
    assert len(simple['key_squares'])<=2
    assert simple['recommended_uci']==best.split()[0]
    assert chess.square_name(chess.Move.from_uci(best.split()[0]).from_square) in simple['recommendation']
    assert chess.square_name(chess.Move.from_uci(best.split()[0]).to_square) in simple['recommendation']
    assert board.fen()==original_fen and notes==original


@pytest.mark.parametrize('fen,uci,words',[
    (chess.STARTING_FEN,'a2a4',['Пешка','a2','a4']),
    (chess.STARTING_FEN,'g1f3',['Конь','g1','f3']),
    ('rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2','f1c4',['Слон','f1','c4']),
    ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','e1g1',['Рокировка','e1','g1','h1','f1']),
    ('r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1','e8c8',['Рокировка','e8','c8','a8','d8']),
    ('7k/8/8/3pP3/8/8/8/6K1 w - d6 0 1','e5d6',['Пешка','e5','d6','забирает пешку с d5']),
    ('7k/P7/8/8/8/8/8/6K1 w - - 0 1','a7a8n',['Пешка','a7','a8','превращается в коня']),
])
def test_human_move_names_origin_destination_and_special_moves(fen,uci,words):
    value=describe_move(chess.Board(fen),chess.Move.from_uci(uci))
    assert all(word in value for word in words)
    assert not TECHNICAL.search(value)


def test_positional_simple_explanation_names_obstructed_piece_and_teaching_principle():
    board=chess.Board();move=chess.Move.from_uci('a2a3')
    notes=build_coaching(board,move,info(80,'e2e4'),info(-10,'e7e5 g1f3 b8c6 e2e3 g8f6 f1b5'),
                         [info(80,'e2e4 e7e5 g1f3 b8c6 f1c4 g8f6')],True)
    value=present_simple(board,move,notes['explanation'])
    assert value['kind']=='blocked_piece' and value['confidence']=='medium'
    assert 'слон' in value['why'] and 'пешк' in value['why']
    assert 'Пешка с e2 идёт на e4' in value['recommendation']
    assert 'дорог' in value['principle']


def test_unsupported_saved_analysis_does_not_invent_a_cause_but_translates_best_move():
    board=chess.Board(LOSS_FEN);move=chess.Move.from_uci('d1d4')
    value=present_simple(board,move,{},legacy_best='Qd2')
    assert value['confidence']=='low' and value['kind']=='unresolved'
    assert value['recommended_uci']=='d1d2'
    assert 'Ферзь с d1 идёт на d2' in value['recommendation']
    assert 'может забрать' not in value['consequence']
    assert not TECHNICAL.search(value['recommendation'])


def test_compensating_alternative_does_not_claim_the_pawn_cannot_be_captured():
    board=chess.Board('6k1/5p2/8/3p4/4P3/8/PP3PPP/5BK1 w - - 0 1')
    played=chess.Move.from_uci('a2a3')
    notes=build_coaching(board,played,info(100,'f2f4'),info(-100,'d5e4 f1c4 g8h8'),
                         [info(100,'f2f4 d5e4 f1c4 g8h8 c4f7 h8g7')],True)
    # Both continuations lose e4; the alternative wins a pawn back.
    value=notes['explanation'];assert value['reason_type']=='pawn_loss'
    simple=present_simple(board,played,value)
    assert 'избежишь этой потери' not in simple['recommendation']
    assert 'в ответ' in simple['recommendation']


def test_bad_alternative_is_not_presented_as_mate_defence():
    board=chess.Board();move=chess.Move.from_uci('g2g4')
    explanation={'reason_type':'allowed_mate','confidence':'high','chosen_recommendation':'f2f3'}
    simple=present_simple(board,move,explanation,selected_info={'mate':-2,'mate_winning':False})
    assert 'не исправляет' in simple['recommendation']


def test_simple_mode_is_default_and_all_engine_values_are_hidden(qtbot):
    dialog=AnalysisDialog(row_with_notes(loss_notes()));qtbot.addWidget(dialog);dialog.show()
    assert not dialog.detailed and dialog.simple_button.isChecked()
    assert dialog.mode_label.text()=='Простое объяснение'
    assert dialog.simple_panel.isVisible() and not dialog.professional_panel.isVisible()
    assert not dialog.variations.isVisible() and not dialog.response_label.isVisible()
    assert not dialog.explanation_debug.isVisible() and not dialog.line_controls.isVisible()
    assert all(dialog.table.isColumnHidden(c) for c in (2,3,5,6))
    assert 'Ферзь с d1 идёт на d4' in dialog.table.item(0,1).text()
    assert dialog.result_label.text()=='Поражение'
    assert not TECHNICAL.search(' '.join(label.text() for label in dialog.simple_labels.values()))
    assert dialog.simple_headings['why'].text()=='Почему это плохо'
    assert dialog.simple_headings['principle'].text()=='Главная мысль'
    assert dialog.other_button.isVisible() and not dialog.simple_variations.isVisible()
    assert len(dialog.board.annotations)==2 and len(dialog.board.tactical_highlights)<=2


def test_disclosure_and_mode_switch_preserve_selected_branch_position_and_pgn(qtbot):
    dialog=AnalysisDialog(row_with_notes(loss_notes()));qtbot.addWidget(dialog);dialog.show()
    pgn=dialog.game.pgn()
    qtbot.mouseClick(dialog.preview_button,Qt.LeftButton)
    original=dialog.board.board.fen(),dialog.line_cursor,dialog.selected_row,dialog.selected_alternative
    qtbot.mouseClick(dialog.details_toggle,Qt.LeftButton)
    assert dialog.detailed and dialog.professional_panel.isVisible()
    assert all(not dialog.table.isColumnHidden(c) for c in (2,3,5,6))
    assert dialog.table.item(0,1).text()=='Qd4'
    assert dialog.line_controls.isVisible() and dialog.variations.isVisible()
    assert dialog.table.item(0,2).text()=='+4.00'
    dialog.simple_button.click()
    assert not dialog.detailed
    assert (dialog.board.board.fen(),dialog.line_cursor,dialog.selected_row,dialog.selected_alternative)==original
    assert dialog.game.pgn()==pgn


def test_simple_alternatives_are_below_primary_and_sync_text_and_two_arrows(qtbot):
    notes=loss_notes();dialog=AnalysisDialog(row_with_notes(notes));qtbot.addWidget(dialog);dialog.show()
    dialog.other_button.click()
    assert dialog.simple_variations.isVisible() and dialog.simple_variations.count()==2
    for row in (0,1):
        dialog.simple_variations.setCurrentRow(row)
        choice=dialog.alternatives[row+1]
        assert dialog.simple_presentation['recommended_uci']==choice['uci']
        assert len(dialog.board.annotations)==2
        move=chess.Move.from_uci(choice['uci'])
        assert (move.from_square,move.to_square,'recommended') in dialog.board.annotations
        assert dialog.simple_labels['recommendation'].text()==dialog.simple_presentation['recommendation']
        assert len(dialog.board.tactical_highlights)<=2
    dialog.return_to_actual()
    assert not dialog.board.annotations and not dialog.board.tactical_highlights


def test_mode_switch_does_not_reveal_developer_fields_to_ordinary_user(qtbot):
    dialog=AnalysisDialog(row_with_notes(loss_notes()));qtbot.addWidget(dialog);dialog.show()
    dialog.set_detailed(True)
    assert not dialog.explanation_debug.isVisible()
    dialog.set_detailed(False)
    assert not dialog.explanation_debug.isVisible()


def test_legacy_and_empty_history_open_in_simple_mode_without_an_engine(qtbot):
    legacy=AnalysisDialog(row_with_notes());qtbot.addWidget(legacy);legacy.show()
    assert not legacy.detailed and legacy.simple_presentation['confidence']=='low'
    assert 'Ферзь с d1 идёт на d2' in legacy.simple_labels['recommendation'].text()
    empty=AnalysisDialog({'analysis':'[]','pgn':GameState().pgn(),'player_color':True,'result':'*','accuracy':0.})
    qtbot.addWidget(empty);empty.show()
    assert not empty.detailed and not empty.preview_button.isEnabled()
    assert not empty.other_button.isVisible()


def test_mismatched_saved_evidence_is_not_used_for_beginner_claims(qtbot):
    notes=loss_notes();notes['root_fen']=chess.STARTING_FEN
    dialog=AnalysisDialog(row_with_notes(notes));qtbot.addWidget(dialog);dialog.show()
    assert not dialog.alternatives and not dialog.current_explanation
    assert dialog.simple_presentation['kind']=='unresolved'
    assert not dialog.board.annotations


def test_developer_mode_still_starts_simple_and_reveals_debug_only_with_details(qtbot):
    from types import SimpleNamespace
    parent=QDialog();qtbot.addWidget(parent)
    parent.settings=SimpleNamespace(values={'developer_mode':True,'animations':True})
    dialog=AnalysisDialog(row_with_notes(loss_notes()),parent);qtbot.addWidget(dialog);dialog.show()
    assert not dialog.detailed and not dialog.explanation_debug.isVisible()
    dialog.set_detailed(True)
    assert dialog.explanation_debug.isVisible()
    data=json.loads(dialog.explanation_debug.toPlainText())
    assert 'material_delta' in data['factors'] and 'PV' in data['factors']
    dialog.set_detailed(False)
    assert not dialog.explanation_debug.isVisible()


def test_good_move_does_not_receive_a_false_bad_move_heading(qtbot):
    game=GameState();game.play(chess.Move.from_uci('e2e4'))
    row={'result':'*','accuracy':100.,'player_color':True,'pgn':game.pgn(),
         'analysis':json.dumps([{'ply':1,'san':'e4','best_san':'e4','category':'Отличный','cpl':0,
                                'before_cp':40,'after_cp':40,'coaching':None}])}
    dialog=AnalysisDialog(row);qtbot.addWidget(dialog);dialog.show()
    assert dialog.simple_presentation['kind']=='good'
    assert dialog.simple_headings['why'].text()=='Что получилось'
    assert 'не отмечен как ошибка' in dialog.simple_labels['why'].text()
