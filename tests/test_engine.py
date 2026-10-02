import chess
import pytest
from app.services.engine import EngineService


@pytest.fixture
def engine():
    service=EngineService()
    yield service
    service.close()


def test_real_engine_returns_legal_candidates_and_stops(engine):
    result=engine.choose(chess.Board(),1100,natural_delay=False)
    assert result.move in chess.Board().legal_moves
    assert len(result.candidates)==8
    process=engine._engine
    engine.close()
    assert process.returncode.result(timeout=5)==0


def test_real_analysis_in_both_player_perspectives(engine):
    board=chess.Board()
    for uci in ['e2e4','e7e5','g1f3','b8c6']:
        board.push_uci(uci)
    for color in [True,False]:
        moves,metrics=engine.analyse_game(board,color,12)
        assert len(moves)==2 and metrics.moves==2
        assert all(m.cpl>=0 for m in moves)
        assert all(m.best_san and m.before_label for m in moves)


def test_engine_recovers_after_external_process_exit(engine):
    engine.choose(chess.Board(),1100,False)
    engine._engine.quit()
    result=engine.choose(chess.Board(),1100,False)
    assert result.move in chess.Board().legal_moves


def test_missing_engine_has_clear_error(tmp_path):
    service=EngineService(tmp_path/'absent')
    with pytest.raises(FileNotFoundError,match='Stockfish'):
        service.choose(chess.Board(),1100,False)
    service.close()
