import chess
import chess.engine
import pytest

from app.services.engine import EngineService
from app.services.live import LABELS, LiveEvaluation, PositionIndicator, category


def evaluation(cp=0, mate=None):
    score = chess.engine.Mate(mate) if mate is not None else chess.engine.Cp(cp)
    return LiveEvaluation.from_info(chess.Board(), {'score': chess.engine.PovScore(score, chess.WHITE), 'depth': 10})


@pytest.mark.parametrize('cp,level', [(-300,-3),(-150,-2),(-60,-1),(-30,0),(0,0),(30,0),(60,1),(150,2),(300,3)])
def test_categories_and_white_view(cp, level):
    assert category(cp) == level
    indicator = PositionIndicator()
    assert indicator.update(evaluation(cp), chess.WHITE) == LABELS[level]
    assert indicator.debug['evaluation_white_cp'] == cp
    assert indicator.debug['evaluation_player_cp'] == cp


@pytest.mark.parametrize('cp', [-300,-150,-60,0,60,150,300])
def test_black_inverts_evaluation(cp):
    indicator = PositionIndicator()
    assert indicator.update(evaluation(cp), chess.BLACK) == LABELS[category(-cp)]
    assert indicator.debug['evaluation_player_cp'] == -cp
    assert indicator.debug['evaluation_white_cp'] == cp


def test_hysteresis_stabilizes_both_directions():
    indicator = PositionIndicator()
    for cp in [29,31,40,30,42]:
        indicator.update(evaluation(cp), chess.WHITE)
        assert indicator.level == 0
    indicator.update(evaluation(43), chess.WHITE)
    assert indicator.level == 1
    for cp in [40,30,25,18]:
        indicator.update(evaluation(cp), chess.WHITE)
        assert indicator.level == 1
    indicator.update(evaluation(17), chess.WHITE)
    assert indicator.level == 0
    indicator.update(evaluation(-43), chess.WHITE)
    assert indicator.level == -1
    indicator.update(evaluation(-30), chess.WHITE)
    assert indicator.level == -1 and indicator.debug['hysteresis_held']
    indicator.update(evaluation(-17), chess.WHITE)
    assert indicator.level == 0


@pytest.mark.parametrize('mate,color,good', [(4,True,True),(4,False,False),(-4,True,False),(-4,False,True),(0,True,False),(0,False,True)])
def test_mate_separate_from_numeric_categories(mate,color,good):
    indicator = PositionIndicator()
    value = evaluation(mate=mate)
    text = indicator.update(value,color)
    assert text == ('У вас решающее преимущество' if good else 'Позиция критическая')
    assert value.player_cp(color) is None
    assert indicator.debug['mate_player'] == (mate if color else -mate)
    assert '4' not in text and 'Mate' not in text


def test_real_light_analysis_and_reused_search_share_engine_process():
    engine = EngineService()
    try:
        value = engine.evaluate_live(chess.Board())
        process = engine._engine
        assert value.fen == chess.STARTING_FEN and value.depth > 0
        reported = []
        selection = engine.choose(chess.Board(), 1100, natural_delay=False, on_evaluation=reported.append)
        assert selection.move in chess.Board().legal_moves
        assert engine._engine is process
        assert len(reported) == 1 and reported[0].fen == chess.STARTING_FEN
    finally:
        engine.close()
