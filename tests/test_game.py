import chess
import pytest
from app.services.game import GameState


def play(state, *moves):
    for move in moves:
        state.play(chess.Move.from_uci(move))


def test_illegal_move_does_not_change_board():
    game = GameState()
    before = game.board.fen()
    with pytest.raises(ValueError):
        play(game, 'e2e5')
    assert game.board.fen() == before


def test_checkmate_finishes_and_blocks_moves():
    game = GameState()
    play(game, 'f2f3', 'e7e5', 'g2g4', 'd8h4')
    assert game.board.is_checkmate() and game.result == '0-1'
    with pytest.raises(ValueError):
        play(game, 'a2a3')


def test_stalemate():
    game = GameState(board=chess.Board('7k/5K2/8/6Q1/8/8/8/8 w - - 0 1'))
    play(game, 'g5g6')
    assert game.board.is_stalemate() and game.result == '1/2-1/2'


def test_castling():
    game = GameState(board=chess.Board('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'))
    play(game, 'e1g1', 'e8c8')
    assert game.board.piece_at(chess.F1).piece_type == chess.ROOK
    assert game.board.piece_at(chess.D8).piece_type == chess.ROOK


def test_castling_through_check_is_illegal():
    game = GameState(board=chess.Board('k4r2/8/8/8/8/8/8/4K2R w K - 0 1'))
    with pytest.raises(ValueError):
        play(game, 'e1g1')


def test_en_passant():
    game = GameState()
    play(game, 'e2e4', 'a7a6', 'e4e5', 'd7d5', 'e5d6')
    assert game.board.piece_at(chess.D5) is None
    assert game.board.piece_at(chess.D6).piece_type == chess.PAWN


@pytest.mark.parametrize('piece', ['q', 'r', 'b', 'n'])
def test_promotion(piece):
    game = GameState(board=chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1'))
    play(game, 'a7a8' + piece)
    assert game.board.piece_at(chess.A8).symbol().lower() == piece


def test_repetition_claim_automatically_ends_game():
    game = GameState()
    for move in ['g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3', 'g8f6', 'f3g1']:
        play(game, move)
    assert game.result == '1/2-1/2'


def test_fifty_moves_claim():
    game = GameState(board=chess.Board('7k/8/8/8/8/8/8/R6K w - - 98 60'))
    play(game, 'a1a2')
    assert game.result == '1/2-1/2'


def test_insufficient_material():
    game = GameState(board=chess.Board('7k/8/8/8/8/8/1n6/KN6 w - - 0 1'))
    play(game, 'a1b2')
    assert game.result == '1/2-1/2'


def test_pgn_roundtrip_preserves_stack_and_repetition():
    game = GameState(player_color=chess.BLACK)
    play(game, 'g1f3', 'g8f6', 'f3g1', 'f6g8')
    loaded = GameState.from_pgn(game.pgn(), player_color=chess.BLACK)
    assert loaded.board.fen() == game.board.fen()
    assert loaded.board.move_stack == game.board.move_stack
    assert loaded.board.is_repetition(2)


@pytest.mark.parametrize('color,result,score', [(True,'1-0',1),(False,'1-0',0),(True,'0-1',0),(False,'0-1',1),(False,'1/2-1/2',0.5)])
def test_player_result_perspective(color,result,score):
    assert GameState(player_color=color,result=result).player_score() == score
