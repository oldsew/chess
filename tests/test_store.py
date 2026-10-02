import chess
from app.adaptive.metrics import Performance
from app.adaptive.rating import PlayerProfile
from app.database.store import Store
from app.services.game import GameState
from app.services.session import Session


def test_game_survives_database_restart(tmp_path):
    path=tmp_path/'chess.sqlite3'
    store=Store(path)
    session=Session(store)
    game=session.start(chess.BLACK)
    session.play(chess.Move.from_uci('e2e4'))
    game_id=game.database_id
    store.close()
    store=Store(path)
    loaded=store.unfinished()
    assert loaded.database_id==game_id
    assert loaded.player_color==chess.BLACK
    assert loaded.board.fen()==game.board.fen()
    assert len(loaded.board.move_stack)==1
    store.close()


def test_analysis_rating_atomic_and_idempotent(tmp_path):
    store=Store(tmp_path/'db.sqlite3')
    game=GameState()
    game.resign()
    store.save_game(game)
    profile=PlayerProfile(rating=1020,games=1)
    metrics=Performance(82,30,1,0,0,moves=15)
    assert store.pending_analysis()==game.database_id
    assert store.finish_analysis(game,[],metrics,profile)
    assert not store.finish_analysis(game,[],metrics,PlayerProfile(rating=1100))
    assert store.profile().rating==1020
    assert store.pending_analysis() is None
    row=store.history()[0]
    assert row['pgn'].endswith('0-1')
    assert row['accuracy']==82
    assert len(store.evidence())==1
    store.close()


def test_transaction_rolls_back_both_profile_and_game(tmp_path):
    import pytest
    store=Store(tmp_path/'db.sqlite3')
    game=GameState(result='0-1')
    store.save_game(game)
    store.connection.execute("CREATE TRIGGER fail_profile BEFORE INSERT ON profile BEGIN SELECT RAISE(ABORT,'failure'); END")
    with pytest.raises(Exception):
        store.finish_analysis(game,[],Performance(90,20,0,0,0),PlayerProfile(rating=1200))
    assert not store.history()[0]['rated']
    assert store.profile().rating==1000
    store.close()


def test_concurrent_analysis_only_updates_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    path=tmp_path/'db.sqlite3'
    store=Store(path)
    game=GameState(result='0-1')
    store.save_game(game)
    store.close()
    barrier=threading.Barrier(2)
    def complete(rating):
        connection=Store(path)
        barrier.wait(timeout=5)
        try:
            return connection.finish_analysis(game,[],Performance(90,20,0,0,0),PlayerProfile(rating=rating,games=1))
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(complete,[1020,1040]))
    assert sorted(outcomes)==[False,True]
    store=Store(path)
    assert store.profile().rating in [1020,1040]
    assert store.profile().games==1
    store.close()
