from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

import chess

from app.config.settings import TUNING
from app.adaptive.safety import obvious_queen_capture, queen_gift


@dataclass
class BehaviorProfile:
    skill_level: int
    inaccuracy_probability: float
    mistake_probability: float
    blunder_probability: float
    max_allowed_cpl: float
    candidate_move_temperature: float
    search_time: float
    multipv: int
    positional_bias: float

    @classmethod
    def for_rating(cls,elo:float):
        points = TUNING['profiles']
        elo = max(points[0]['elo'],min(points[-1]['elo'],elo))
        low,high = points[0],points[-1]
        for a,b in zip(points,points[1:]):
            if a['elo'] <= elo <= b['elo']:
                low,high = a,b
                break
        t = (elo-low['elo'])/(high['elo']-low['elo'])
        values = {key:low[key]+t*(high[key]-low[key]) for key in cls.__dataclass_fields__}
        for key in ['skill_level','multipv']:
            values[key] = round(values[key])
        return cls(**values)


@dataclass
class Candidate:
    move: chess.Move
    score: int
    mate: int | None = None


@dataclass
class Selection:
    move: chess.Move
    candidates: list[dict]
    profile: dict
    complexity: str
    delay: float
    selected_cpl: int = 0
    selected_rank: int = 1
    unique_best: bool = False


def select_move(board:chess.Board,candidates:list[Candidate],rating:float,rng:random.Random|None=None) -> Selection:
    rng = rng or random.Random()
    legal = sorted((c for c in candidates if c.move in board.legal_moves),key=lambda c:c.score,reverse=True)
    if not legal:
        raise ValueError('No legal engine candidates')
    profile = BehaviorProfile.for_rating(rating)
    best = legal[0].score
    immediate_mates = []
    for c in legal:
        position = board.copy(stack=False)
        position.push(c.move)
        if position.is_checkmate():
            immediate_mates.append(c.move)
    phase = 'endgame' if len(board.piece_map()) <= 12 else 'opening' if board.fullmove_number <= 10 else 'middlegame'
    spread = best-min(c.score for c in legal)
    complexity = 'complex' if board.is_check() or spread > 150 else 'simple' if len(legal) <= 2 or phase == 'opening' else 'normal'
    ceiling = profile.max_allowed_cpl
    cfg = TUNING['selection']
    if sum(best-c.score <= cfg['close_candidate_cp'] for c in legal) >= cfg['close_candidate_count']:
        low,high = cfg['close_narrowing_range']
        fraction = max(0,min(1,(rating-low)/(high-low)))
        ceiling += fraction * (min(ceiling,cfg['close_narrow_ceiling_cp'])-ceiling)
    winning_mate = any(c.mate is not None and c.mate > 0 for c in legal)
    safe_mate = any(c.mate is None or c.mate > 0 for c in legal)
    allowed,reasons = [],[]
    for c in legal:
        reason = None
        if best-c.score > ceiling:
            reason = 'cpl_ceiling'
        if immediate_mates:
            reason = None if c.move in immediate_mates else 'mate_in_one_available'
        elif winning_mate:
            reason = reason if c.mate is not None and c.mate > 0 else 'preserve_forced_mate'
        elif c.mate is not None and c.mate <= 0 and safe_mate:
            reason = 'avoid_forced_mate'
        if not reason and not immediate_mates and not (c.mate is not None and c.mate > 0) and queen_gift(board,c.move):
            reason = 'obvious_queen_gift'
        allowed.append(reason is None)
        reasons.append(reason)
    free_queens = [i for i,c in enumerate(legal) if allowed[i] and obvious_queen_capture(board,c.move)]
    if free_queens and not immediate_mates and not winning_mate:
        for i in range(len(legal)):
            if allowed[i] and i not in free_queens:
                allowed[i],reasons[i] = False,'obvious_queen_capture_available'
    # These are probability masses, not multipliers on the already-dominant best-move weight.
    masses = [max(0,1-profile.inaccuracy_probability-profile.mistake_probability-profile.blunder_probability),
              profile.inaccuracy_probability,profile.mistake_probability,profile.blunder_probability]
    limits = TUNING['selection']['bands_cp']
    bands = [sum(max(0,best-c.score) > limit for limit in limits) for c in legal]
    weights = [0.]*len(legal)
    for band,mass in enumerate(masses):
        indices = [i for i in range(len(legal)) if allowed[i] and bands[i] == band]
        local = []
        for i in indices:
            c = legal[i]
            loss = max(0,best-c.score)
            temperature = profile.candidate_move_temperature * (1.15 if complexity == 'complex' else 1)
            quiet = not board.is_capture(c.move) and not board.gives_check(c.move)
            plausible = 1+profile.positional_bias if quiet and loss > 25 else 1
            local.append(math.exp(-loss/max(1,temperature))*plausible)
        total = sum(local)
        if total:
            for i,w in zip(indices,local):
                weights[i] = mass*w/total
    total = sum(weights)
    if not total:
        # Forced material losses can make every queen unsafe; retain the strongest legal escape.
        fallback = max((c.score for i,c in enumerate(legal) if allowed[i]),default=best)
        weights = [float(c.score == fallback and (allowed[i] or not any(allowed))) for i,c in enumerate(legal)]
        total = sum(weights)
    probabilities = [w/total for w in weights]
    chosen_index = rng.choices(range(len(legal)),weights=probabilities,k=1)[0]
    chosen = legal[chosen_index]
    debug = [{'move':board.san(c.move),'uci':c.move.uci(),'evaluation':c.score,'mate':c.mate,
              'cpl':max(0,best-c.score),'probability':p,'rank':i+1,
              'band':['normal','inaccuracy','mistake','blunder'][bands[i]],'rejected_reason':reasons[i]}
             for i,(c,p) in enumerate(zip(legal,probabilities))]
    unique = len(legal) > 1 and best-legal[1].score >= TUNING['selection']['unique_best_gap_cp']
    return Selection(chosen.move,debug,asdict(profile),complexity,rng.uniform(*TUNING['think_times'][complexity]),
                     max(0,best-chosen.score),chosen_index+1,unique)
