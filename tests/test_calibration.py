import json
import random

import chess
import pytest

from app.adaptive.rating import PlayerProfile, RatingEvidence, update_rating
from app.adaptive.selector import BehaviorProfile, Candidate, select_move
from app.adaptive.safety import exchange_profit
from app.services.calibration import GameCalibration
from app.services.game import GameState


def candidates():
    return [Candidate(chess.Move.from_uci(uci),score) for uci,score in
            zip(['e2e4','d2d4','g1f3','c2c4','b1c3','a2a3','h2h3','b2b3'],[100,95,80,50,20,-20,-70,-120])]


def sample(rating,count=1000):
    board = chess.Board()
    rng = random.Random(832)
    result = [select_move(board,candidates(),rating,rng) for _ in range(count)]
    return {'average_cpl':sum(r.selected_cpl for r in result)/count,
            'top_two':sum(r.selected_rank <= 2 for r in result)/count,
            'inaccuracy_or_worse':sum(r.selected_cpl > 50 for r in result)/count}


def test_weak_profile_regular_inaccuracies_and_strong_profile_top_two():
    weak,strong = sample(900),sample(2200)
    assert weak['average_cpl'] > strong['average_cpl']+50
    assert weak['inaccuracy_or_worse'] > .5
    assert strong['top_two'] > .85 and weak['top_two'] < .35


def test_seed_is_deterministic_and_profiles_continuous():
    def sequence():
        rng = random.Random(42)
        return [select_move(chess.Board(),candidates(),900,rng).move for _ in range(30)]
    assert sequence() == sequence()
    for boundary in [600,800,1000,1200,1400,1600]:
        a,b = BehaviorProfile.for_rating(boundary-.1),BehaviorProfile.for_rating(boundary+.1)
        assert abs(a.inaccuracy_probability-b.inaccuracy_probability) < .001
        assert abs(a.candidate_move_temperature-b.candidate_move_temperature) < .1
        assert a.multipv == b.multipv
    assert BehaviorProfile.for_rating(900).multipv > BehaviorProfile.for_rating(2200).multipv


def test_weak_profile_cannot_select_obvious_queen_gift_even_with_close_engine_score():
    board = chess.Board('r5k1/5ppp/8/4p3/8/8/PP3PPP/3Q2K1 w - - 0 1')
    moves = [Candidate(chess.Move.from_uci(uci),cp) for uci,cp in [('d1d2',100),('d1e2',80),('d1d4',70)]]
    assert exchange_profit(board,chess.Move.from_uci('d1d4')) == -9
    for seed in range(100):
        chosen = select_move(board,moves,700,random.Random(seed))
        assert chosen.move.uci() != 'd1d4'
        rejected = next(c for c in chosen.candidates if c['uci'] == 'd1d4')
        assert rejected['probability'] == 0 and rejected['rejected_reason'] == 'obvious_queen_gift'


def test_obvious_free_queen_capture_is_not_ignored():
    board = chess.Board('6k1/5ppp/8/8/3q4/8/PP3PPP/3Q2K1 w - - 0 1')
    moves = [Candidate(chess.Move.from_uci(uci),cp) for uci,cp in [('d1e2',100),('g1h1',80),('d1d4',70)]]
    for seed in range(100):
        assert select_move(board,moves,600,random.Random(seed)).move.uci() == 'd1d4'


def test_forced_move_is_found_less_often_by_weak_profile_without_forcing_absurdity():
    board = chess.Board()
    moves = [Candidate(chess.Move.from_uci(uci),cp) for uci,cp in [('e2e4',100),('d2d4',-10),('g1f3',-60),('c2c4',-90)]]
    weak = select_move(board,moves,900,random.Random(3))
    strong = select_move(board,moves,2200,random.Random(3))
    assert weak.unique_best and strong.unique_best
    assert weak.candidates[0]['probability'] < .5
    assert strong.candidates[0]['probability'] == 1


@pytest.mark.parametrize('rating,expected',[(400,40),(600,45),(800,50),(832,53.2),(900,60),(1000,70),(1200,90),(1400,100),(2200,100)])
def test_offset_is_lower_for_low_rating_with_no_stored_profile_reset(rating,expected):
    profile = PlayerProfile(rating=rating,offset=100)
    assert profile.difficulty_offset == pytest.approx(expected)
    assert profile.target == pytest.approx(rating+expected)
    assert profile.rating == rating and profile.offset == 100


def test_hopeless_streak_reduces_offset_before_large_rating_drop():
    profile = PlayerProfile(rating=900,games=20)
    loss = RatingEvidence(0,40,180,8,4,30)
    updated = update_rating(profile,profile.target,loss,[loss])
    assert profile.rating-updated.rating <= 8
    assert updated.difficulty_offset <= profile.difficulty_offset-10
    assert updated.offset == profile.offset-10
    # No evidence from an immediate resignation: don't manufacture a hopeless streak.
    empty = RatingEvidence(0,0,0,0,0,0)
    zero = update_rating(profile,profile.target,empty,[loss])
    assert zero.rating == profile.rating and zero.offset == profile.offset


def test_calibration_records_are_local_durable_and_do_not_change_pgn(tmp_path):
    game = GameState(player_color=chess.BLACK)
    record = GameCalibration(tmp_path,game)
    chosen = select_move(game.board,candidates(),900,random.Random(42))
    game.play(chosen.move)
    before = game.pgn()
    record.record(game,chosen)
    record.record(game,chosen)
    assert len(record.records) == 1 and game.pgn() == before
    restored = GameCalibration(tmp_path,game)
    assert restored.summary() == record.summary()
    assert restored.summary()['moves'] == 1
    data = json.loads(record.path.read_text())
    assert data['moves'][0]['target_bot_rating'] == game.bot_rating
    assert data['summary']['ranks'][str(chosen.selected_rank) if chosen.selected_rank <= 3 else 'lower'] == 1


def test_distribution_median_and_unique_best_diagnostics(tmp_path):
    record = GameCalibration(tmp_path,GameState())
    record.records = [{'ply':i,'cpl':cpl,'rank':rank,'unique_best':unique} for i,(cpl,rank,unique) in enumerate(
                      [(0,1,True),(40,2,False),(80,3,False),(130,4,True),(220,5,False),(300,6,False)])]
    summary = record.summary()
    assert all(v == 1 for v in summary['distribution'].values())
    assert summary['median_cpl'] == 105 and summary['average_cpl'] == pytest.approx(770/6)
    assert summary['unique_best_positions'] == 2 and summary['unique_best_found'] == 1
    assert summary['ranks'] == {'1':1,'2':1,'3':1,'lower':3}
    assert summary['inaccuracies'] == 1 and summary['mistakes'] == 1 and summary['blunders'] == 2


def test_corrupt_optional_diagnostics_do_not_break_game(tmp_path):
    game = GameState(database_id=1)
    record = GameCalibration(tmp_path,game)
    record.path.parent.mkdir(parents=True)
    for payload in ['broken','[]','{"schema":1,"game_id":1,"moves":[null]}']:
        record.path.write_text(payload)
        loaded = GameCalibration(tmp_path,game)
        assert loaded.records == [] and loaded.summary()['moves'] == 0
