"""Small reproducible PGN corpus used by source and frozen-executable checks."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import time

import chess

from app.services.game import GameState
from app.services.position_features import trace

GAMES = [
    ('queen_loss','r5k1/5ppp/8/4p3/8/8/PP3PPP/3Q2K1 w - - 0 1',['d1d4']),
    ('fork','4k3/8/8/8/5n2/8/PP3PPP/2RQ2K1 w - - 0 1',['d1d4']),
    ('pawn_loss','6k1/8/8/3p4/4P3/8/PP3PPP/5BK1 w - - 0 1',['a2a3']),
    ('bad_exchange','6k1/5ppp/4p3/3b4/8/8/5PPP/3R2K1 w - - 0 1',['d1d5']),
    ('fools_mate',chess.STARTING_FEN,['f2f3','e7e5','g2g4','d8h4']),
    ('quiet_opening',chess.STARTING_FEN,['e2e4','a7a6','d2d4','a6a5','g1f3','h7h6','f1c4','h6h5','e1g1']),
]


def run_corpus(engine,progress=None):
    """Run production final analysis, sharing the existing serialized engine service."""
    started=time.monotonic();records=[];categories=Counter();confidences=Counter()
    process=None
    for index,(name,fen,ucis) in enumerate(GAMES):
        for color in (True,False):
            root=chess.Board(fen)
            moves=[chess.Move.from_uci(u) for u in ucis]
            if not color:
                root=root.mirror()
                moves=[chess.Move(chess.square_mirror(m.from_square),chess.square_mirror(m.to_square),m.promotion) for m in moves]
            game=GameState(board=root,player_color=color)
            for move in moves:game.play(move)
            original=game.pgn(),game.board.fen()
            rows,metrics=engine.analyse_game(game.board,color,16)
            assert (game.pgn(),game.board.fen())==original,'Analysis mutated the actual game'
            assert metrics.moves==len(rows)
            if process is None:process=engine._engine
            assert engine._engine is process,'Corpus unexpectedly restarted Stockfish'
            explanations=[]
            for row in rows:
                if not row.coaching:continue
                notes=row.coaching;value=notes['explanation'];comparison=notes['comparison']
                assert comparison['equal_depth'],comparison
                before=game.board.root()
                for played in game.board.move_stack[:row.ply-1]:before.push(played)
                for variant in notes['alternatives']:
                    line=trace(before,variant['analysis_pv_uci'],color)
                    assert line['valid']
                    assert 6<=len(line['moves'])<=10 or line['terminal'],variant
                    assert len(variant['pv_uci'])<=6
                categories[value['reason_type']]+=1;confidences[value['confidence']]+=1
                explanations.append(asdict(row))
            records.append({'name':name,'player_color':color,'pgn':game.pgn(),
                            'metrics':asdict(metrics),'analysed_moves':len(rows),'explanations':explanations})
            if progress:progress(index*2+int(not color)+1,len(GAMES)*2)
    assert sum(categories.values())>=8,'Too few teachable errors in corpus'
    assert confidences['high']>=2,'Material/mate verification failed'
    return {'games':records,'game_count':len(records),'elapsed_seconds':round(time.monotonic()-started,3),
            'reason_categories':dict(categories),'confidence_counts':dict(confidences),
            'single_engine_process':True,'pgn_unchanged':True,'equal_depth_verified':True}
