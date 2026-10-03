"""Local board comparisons and legal-PV tactics. Descriptive evidence, never a new evaluator."""
from __future__ import annotations

import chess

from app.services.material import VALUES, captured_piece, material_balance

CENTER = (chess.D4, chess.E4, chess.D5, chess.E5)
NAMES = {chess.PAWN:'пешка',chess.KNIGHT:'конь',chess.BISHOP:'слон',chess.ROOK:'ладья',chess.QUEEN:'ферзь',chess.KING:'король'}
ACCUSATIVE = {chess.PAWN:'пешку',chess.KNIGHT:'коня',chess.BISHOP:'слона',chess.ROOK:'ладью',chess.QUEEN:'ферзя',chess.KING:'короля'}


def piece_label(board, square):
    piece = board.piece_at(square)
    return f'{NAMES[piece.piece_type]} {chess.square_name(square)}' if piece else chess.square_name(square)


def legal_for(board, color):
    position = board.copy(stack=False)
    if position.turn != color:
        position.ep_square = None
    position.turn = color
    return position, [m for m in position.legal_moves if position.piece_type_at(m.to_square) != chess.KING]


def exchange_gain(board, square, remaining=3):
    if remaining == 0:
        return 0
    gains = [0]
    for move in board.legal_moves:
        if move.to_square == square and board.is_capture(move):
            victim = captured_piece(board, move)
            after = board.copy(stack=False);after.push(move)
            gains.append(VALUES.get(victim.piece_type,0)-exchange_gain(after,square,remaining-1))
    return max(gains)


def hanging(board, color):
    enemy, moves = legal_for(board, not color)
    found = []
    for move in moves:
        victim = captured_piece(enemy,move)
        if victim and victim.color == color:
            after = enemy.copy(stack=False);after.push(move)
            profit = VALUES[victim.piece_type]-exchange_gain(after,move.to_square)
            if profit > 0:
                square = move.to_square + (-8 if enemy.turn else 8) if enemy.is_en_passant(move) else move.to_square
                found.append({'square':square,'piece':victim.piece_type,'attacker':move.from_square,
                              'capture':move.uci(),'san':enemy.san(move),'exchange_profit':profit,
                              'defenders':sorted(board.attackers(color,square))})
    return found


def pawn_features(board, color):
    pawns = sorted(board.pieces(chess.PAWN,color))
    files = {chess.square_file(s) for s in pawns}
    doubled = [s for s in pawns if len([p for p in pawns if chess.square_file(p)==chess.square_file(s)])>1]
    isolated = [s for s in pawns if chess.square_file(s)-1 not in files and chess.square_file(s)+1 not in files]
    passed = [s for s in pawns if not any(abs(chess.square_file(p)-chess.square_file(s))<=1 and
              (chess.square_rank(p)>chess.square_rank(s) if color else chess.square_rank(p)<chess.square_rank(s))
              for p in board.pieces(chess.PAWN,not color))]
    control = set()
    for s in pawns:control.update(board.attacks(s))
    return {'doubled':doubled,'isolated':isolated,'passed':passed,'control':sorted(control)}


def features(board, color):
    position,moves = legal_for(board,color)
    mobility = {s:0 for s,p in board.piece_map().items() if p.color==color and p.piece_type not in (chess.KING,chess.PAWN)}
    for move in moves:
        if move.from_square in mobility:mobility[move.from_square]+=1
    home = 0 if color else 7
    undeveloped = [s for s,t in [(chess.square(1,home),chess.KNIGHT),(chess.square(6,home),chess.KNIGHT),
                                (chess.square(2,home),chess.BISHOP),(chess.square(5,home),chess.BISHOP)]
                   if board.piece_at(s)==chess.Piece(t,color)]
    king = board.king(color)
    ring = set(board.attacks(king)) if king is not None else set()
    enemy_ring = sorted(s for s in ring if board.is_attacked_by(not color,s))
    shield = []
    home_king = king is not None and chess.square_rank(king) in ([0,1] if color else [6,7])
    if home_king:
        rank = chess.square_rank(king)+(1 if color else -1)
        shield = [chess.square(f,rank) for f in range(max(0,chess.square_file(king)-1),min(8,chess.square_file(king)+2))
                  if board.piece_at(chess.square(f,rank))==chess.Piece(chess.PAWN,color)]
    pawn = pawn_features(board,color)
    center = sorted(s for s in CENTER if board.is_attacked_by(color,s))
    center_pawns = sorted(s for s in CENTER if board.piece_at(s)==chess.Piece(chess.PAWN,color))
    pins = sorted(s for s,p in board.piece_map().items() if p.color==color and p.piece_type!=chess.KING and board.is_pinned(color,s))
    return {'material':material_balance(board,color),'mobility':sum(mobility.values()),'piece_mobility':mobility,
            'center_control':len(center)+len(center_pawns),'center_squares':center,'center_pawns':center_pawns,
            'development':4-len(undeveloped),'undeveloped':undeveloped,
            'king_danger':len(enemy_ring)+(3-len(shield) if home_king else 0),'king_ring_attacked':enemy_ring,
            'shield':shield,'castling':int(board.has_kingside_castling_rights(color))+int(board.has_queenside_castling_rights(color)),
            'pawn_structure':len(pawn['isolated'])+len(pawn['doubled']), 'pawns':pawn,'pins':pins,
            'hanging':hanging(board,color)}


def trace(board, uci_moves, color):
    """Replay a bounded PV with SAN/capture evidence and snapshots for causal motif checks."""
    position = board.copy(stack=False)
    states = [position.copy(stack=False)]
    events, moves, san = [], [], []
    valid = True
    for uci in uci_moves:
        try:move = chess.Move.from_uci(uci)
        except ValueError:valid=False;break
        if move not in position.legal_moves:valid=False;break
        victim = captured_piece(position,move)
        label = position.san(move)
        prefix = f'{position.fullmove_number}.' if position.turn else f'{position.fullmove_number}…'
        san.append(prefix+' '+label)
        if victim:
            square = move.to_square + (-8 if position.turn else 8) if position.is_en_passant(move) else move.to_square
            events.append({'ply':len(moves)+1,'victim':victim.piece_type,'color':victim.color,'square':square,
                           'attacker':move.from_square,'destination':move.to_square,'san':label})
        moves.append(move)
        position.push(move);states.append(position.copy(stack=False))
    return {'states':states,'moves':moves,'events':events,'san':san,'pv_uci':[m.uci() for m in moves],
            'valid':valid,'material_delta':material_balance(position,color)-material_balance(board,color),
            'terminal':position.is_game_over(),'final':position}


def tactical_motifs(line, color):
    """Tactics must occur in legal moves. Material corroboration is added by the caller."""
    motifs=[]
    states,moves,events = line['states'],line['moves'],line['events']
    for i,move in enumerate(moves):
        before,after=states[i],states[i+1]
        mover=before.piece_at(move.from_square)
        if not mover or mover.color==color:continue
        # A pawn/knight fork or slider double attack, including a checking attack on the king.
        targets=[]
        for square in after.attacks(move.to_square):
            piece=after.piece_at(square)
            if piece and piece.color==color and (piece.piece_type==chess.KING or VALUES[piece.piece_type]>=3):
                if piece.piece_type==chess.KING or not after.is_pinned(not color,move.to_square):targets.append(square)
        if len(targets)>=2:
            proved=[e for e in events if e['ply']>i+1 and e['color']==color and e['square'] in targets and e['attacker']==move.to_square]
            if proved or after.is_check():
                motifs.append({'type':'fork' if mover.piece_type in (chess.PAWN,chess.KNIGHT) else 'double_attack',
                               'move':move.uci(),'san':before.san(move),'ply':i+1,'attacker':move.to_square,
                               'targets':sorted(targets),'captured':proved,'verified_capture':bool(proved)})
        # Absolute and relative pins along a rook/bishop/queen ray, with a legal attack on the blocker.
        for origin,pinner in after.piece_map().items():
            if pinner.color==color or pinner.piece_type not in (chess.BISHOP,chess.ROOK,chess.QUEEN):continue
            directions=[(1,1),(1,-1),(-1,1),(-1,-1)] if pinner.piece_type==chess.BISHOP else [(1,0),(-1,0),(0,1),(0,-1)]
            if pinner.piece_type==chess.QUEEN:directions+=[(1,1),(1,-1),(-1,1),(-1,-1)]
            for df,dr in directions:
                seen=[];f,r=chess.square_file(origin)+df,chess.square_rank(origin)+dr
                while 0<=f<8 and 0<=r<8 and len(seen)<2:
                    sq=chess.square(f,r)
                    if after.piece_at(sq):seen.append(sq)
                    f+=df;r+=dr
                if len(seen)!=2:continue
                first,last=(after.piece_at(s) for s in seen)
                if first.color!=color or last.color!=color or (last.piece_type!=chess.KING and VALUES[last.piece_type]<=VALUES[first.piece_type]):continue
                enemy,legal=legal_for(after,not color)
                if chess.Move(origin,seen[0]) not in legal:continue
                # Record only newly created pins; old pins aren't attributed to this PV move.
                if (before.piece_at(origin)==pinner and before.piece_at(seen[0])==first
                    and before.piece_at(seen[1])==last
                    and chess.between(origin,seen[1]) & before.occupied == chess.BB_SQUARES[seen[0]]):continue
                later=[e for e in events if e['ply']>i+1 and e['color']==color and e['square']==seen[0]]
                motifs.append({'type':'pin','san':before.san(move),'move':move.uci(),'ply':i+1,'attacker':origin,
                               'targets':seen,'captured':later,'verified_capture':bool(later),'absolute':last.piece_type==chess.KING})
        # A vacated ray exposes a different attacking piece; match a subsequent capture/check.
        for origin,p in after.piece_map().items():
            if p.color==color or origin==move.to_square or p.piece_type not in (chess.BISHOP,chess.ROOK,chess.QUEEN):continue
            newly=set(after.attacks(origin))-set(before.attacks(origin)) if before.piece_at(origin)==p else set()
            for sq in newly:
                victim=after.piece_at(sq)
                if not victim or victim.color!=color:continue
                later=[e for e in events if e['ply']>i+1 and e['color']==color and e['square']==sq and e['attacker']==origin]
                if later or victim.piece_type==chess.KING:
                    motifs.append({'type':'discovered_attack','san':before.san(move),'move':move.uci(),'ply':i+1,
                                   'attacker':origin,'targets':[sq],'captured':later,'verified_capture':bool(later)})
        # Deflect a sole defender by an actual legal recapture, then win its other charge.
        if i+2<len(moves) and before.is_capture(move):
            reply,second=moves[i+1],moves[i+2]
            first_victim=captured_piece(before,move)
            mid=states[i+2];second_victim=captured_piece(mid,second)
            if first_victim and first_victim.color==color and second_victim and second_victim.color==color:
                defender=reply.from_square
                if (reply.to_square==move.to_square and before.attackers(color,move.to_square)==chess.SquareSet([defender])
                    and defender in before.attackers(color,second.to_square) and defender not in mid.attackers(color,second.to_square)):
                    motifs.append({'type':'overloaded_defender','san':before.san(move),'move':move.uci(),'ply':i+1,
                                   'attacker':defender,'targets':[move.to_square,second.to_square],
                                   'verified_capture':True,'captured':[e for e in events if e['ply']==i+3]})
    return motifs


def compare(before, played, alternative, actual_line, best_line, color):
    actual=before.copy(stack=False);actual.push(played)
    better=before.copy(stack=False);better.push(alternative)
    own_actual,own_best=features(actual,color),features(better,color)
    enemy_actual,enemy_best=features(actual,not color),features(better,not color)
    # Compare equal horizons, not unrelated terminal PV lengths.
    horizon=min(len(actual_line['moves']),len(best_line['moves']))
    equal_a,equal_b=actual_line['states'][horizon],best_line['states'][horizon]
    end_own_a,end_own_b=features(equal_a,color),features(equal_b,color)
    end_enemy_a,end_enemy_b=features(equal_a,not color),features(equal_b,not color)
    activity=[]
    for origin,piece in before.piece_map().items():
        if piece.color!=color or piece.piece_type not in (chess.KNIGHT,chess.BISHOP,chess.ROOK,chess.QUEEN):continue
        a=played.to_square if played.from_square==origin else origin
        b=alternative.to_square if alternative.from_square==origin else origin
        am,bm=own_actual['piece_mobility'].get(a,0),own_best['piece_mobility'].get(b,0)
        if bm>am:activity.append({'origin':origin,'piece':piece.piece_type,'actual_square':a,'best_square':b,'actual':am,'best':bm,'gain':bm-am})
    removed_threats=[]
    for threat in own_actual['hanging']:
        origin=played.from_square if threat['square']==played.to_square else threat['square']
        corresponding=alternative.to_square if origin==alternative.from_square else origin
        if not any(h['square']==corresponding for h in own_best['hanging']):removed_threats.append(threat)
    return {'actual':own_actual,'best':own_best,'opponent_actual':enemy_actual,'opponent_best':enemy_best,
            'end_actual':end_own_a,'end_best':end_own_b,'end_opponent_actual':end_enemy_a,'end_opponent_best':end_enemy_b,
            'material_delta':actual_line['material_delta'],'best_material_delta':best_line['material_delta'],
            'mobility_delta':own_best['mobility']-own_actual['mobility'],
            'king_safety_delta':own_actual['king_danger']-own_best['king_danger'],
            'center_control_delta':own_best['center_control']-own_actual['center_control'],
            'development_delta':own_best['development']-own_actual['development'],
            'hanging_piece':own_actual['hanging'],'removed_capture_threats':removed_threats,
            'activity':sorted(activity,key=lambda x:-x['gain']),
            'equal_horizon_plies':horizon,'actual_fen':actual.fen(),'best_fen':better.fen()}
