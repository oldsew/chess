import random
import chess
from app.adaptive.selector import Candidate, BehaviorProfile, select_move


def test_profiles_are_interpolated_separately_from_skill():
    low=BehaviorProfile.for_rating(400)
    high=BehaviorProfile.for_rating(2200)
    middle=BehaviorProfile.for_rating(1300)
    assert low.candidate_move_temperature>middle.candidate_move_temperature>high.candidate_move_temperature
    assert low.skill_level==high.skill_level


def test_disastrous_candidate_has_zero_probability():
    board=chess.Board()
    candidates=[Candidate(chess.Move.from_uci(m),s) for m,s in [('e2e4',40),('d2d4',35),('g1f3',25),('c2c4',10),('a2a4',-600)]]
    for i in range(20):
        result=select_move(board,candidates,400,random.Random(i))
        assert result.move!=chess.Move.from_uci('a2a4')
        assert abs(sum(c['probability'] for c in result.candidates)-1)<1e-8
        assert result.move in board.legal_moves


def test_mate_in_one_never_declined():
    board=chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
    result=select_move(board,[Candidate(chess.Move.from_uci('g6g7'),99999,1),Candidate(chess.Move.from_uci('g6h6'),99990,3)],400)
    board.push(result.move)
    assert board.is_checkmate()


def test_forced_loss_avoided_if_safe_move_exists():
    board=chess.Board()
    result=select_move(board,[Candidate(chess.Move.from_uci('e2e4'),20),Candidate(chess.Move.from_uci('a2a3'),-99999,-2)],400)
    assert result.move==chess.Move.from_uci('e2e4')


def test_higher_rating_prefers_best_more_often():
    board=chess.Board()
    candidates=[Candidate(chess.Move.from_uci('e2e4'),50),Candidate(chess.Move.from_uci('d2d4'),25)]
    low=select_move(board,candidates,400,random.Random(2))
    high=select_move(board,candidates,2500,random.Random(2))
    assert high.candidates[0]['probability']>low.candidates[0]['probability']
