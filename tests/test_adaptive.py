import chess
import chess.engine
import pytest
from app.adaptive.metrics import centipawn_loss, classify, move_accuracy, score_cp, Performance
from app.adaptive.rating import PlayerProfile, RatingEvidence, update_rating


@pytest.mark.parametrize('loss,category', [(0,'Отличный'),(15,'Отличный'),(16,'Хороший'),(40,'Хороший'),(41,'Неточность'),(90,'Неточность'),(91,'Ошибка'),(200,'Ошибка'),(201,'Грубая ошибка')])
def test_classification(loss, category):
    assert classify(loss) == category


def test_cpl_and_mate_perspective():
    assert centipawn_loss(50,-100) == 150
    assert centipawn_loss(-50,100) == 0
    score=chess.engine.PovScore(chess.engine.Mate(2),chess.WHITE)
    assert score_cp(score,chess.WHITE)>90000
    assert score_cp(score,chess.BLACK)<-90000
    assert centipawn_loss(score_cp(score,True),20)>90000


def test_accuracy_is_nonlinear_bounded_and_monotonic():
    values=[move_accuracy(c) for c in [0,10,50,100,200,600]]
    assert values[0]==100
    assert all(a>b for a,b in zip(values,values[1:]))
    assert values[1]>95 and values[-1]<1
    assert all(0<=v<=100 for v in values)


def evidence(score,accuracy=92,cpl=20,mistakes=0,blunders=0):
    return RatingEvidence(score,accuracy,cpl,mistakes,blunders,30)


def test_scenario_a_good_winning_streak_increases_strength():
    profile=PlayerProfile()
    history=[]
    for _ in range(6):
        e=evidence(1)
        updated=update_rating(profile,profile.target,e,history)
        assert 0<updated.rating-profile.rating<=80
        history.append(e)
        profile=updated
    assert profile.target>1300 and profile.offset>100
    assert profile.confidence>0


def test_scenario_b_good_loss_does_not_drop_sharply():
    p=PlayerProfile()
    updated=update_rating(p,1150,evidence(0,88,30),[])
    assert updated.rating>=p.rating-5


def test_scenario_c_five_hopeless_losses_ease_next_opponent():
    profile=PlayerProfile()
    initial=profile.target
    history=[]
    for _ in range(5):
        e=evidence(0,40,180,8,4)
        profile=update_rating(profile,profile.target,e,history)
        history.append(e)
    assert profile.target<initial and profile.offset<100
    assert profile.offset>=50


def test_poor_lucky_win_grants_little_rating():
    p=PlayerProfile()
    updated=update_rating(p,1100,evidence(1,48,150,4,3),[])
    assert 0<=updated.rating-p.rating<=8


@pytest.mark.parametrize('games,cap',[(0,80),(5,50),(20,25)])
def test_calibration_caps(games,cap):
    p=PlayerProfile(games=games)
    updated=update_rating(p,1200,evidence(1,100,0),[])
    assert abs(updated.rating-p.rating)<=cap


def test_recent_quality_and_errors_influence_rating():
    p=PlayerProfile(games=20)
    e=evidence(0.5,80,30)
    good=update_rating(p,1100,e,[evidence(1)]*9)
    poor=update_rating(p,1100,e,[evidence(0,40,180,8,4)]*9)
    assert good.rating>poor.rating
    mistakes=update_rating(p,1100,evidence(0.5,80,30,10,8),[])
    clean=update_rating(p,1100,e,[])
    assert clean.rating>mistakes.rating


def test_offset_and_rating_remain_bounded():
    p=PlayerProfile(rating=400,offset=50)
    e=evidence(0,20,400,10,10)
    updated=update_rating(p,450,e,[e]*10)
    assert updated.rating>=400 and updated.offset>=50


def test_zero_move_resignation_has_no_rating_evidence():
    p=PlayerProfile()
    updated=update_rating(p,1100,RatingEvidence.create(0,Performance(0,0,0,0,0)),[])
    assert updated.rating==p.rating and updated.confidence==0
