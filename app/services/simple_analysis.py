"""Beginner-facing presentation of existing evidence. No evaluation, engine calls or PGN edits."""
from __future__ import annotations

import chess

from app.services.position_features import ACCUSATIVE, NAMES, trace
from app.services.material import VALUES

PRINCIPLES = {
    'material_loss':'Перед ходом проверь, сможет ли соперник забрать твою фигуру и чем ты сможешь ответить.',
    'pawn_loss':'Не оставляй пешку без защиты, если соперник может её забрать без потерь.',
    'fork':'Проверяй, не сможет ли одна фигура соперника напасть сразу на две твои фигуры.',
    'double_attack':'Проверяй не только угрозу одной фигуре, но и вторую угрозу того же хода.',
    'pin':'Фигура, которая прикрывает короля или другую важную фигуру, не всегда может уйти в безопасное место.',
    'discovered_attack':'Когда фигура уходит, она может открыть дорогу для другой фигуры — проверь, что стоит за ней.',
    'overloaded_defender':'Одна фигура не всегда может защитить сразу две другие: после её ухода одна останется без помощи.',
    'bad_exchange':'Прежде чем что-то забрать, проверь, какую твою фигуру соперник заберёт в ответ.',
    'hanging_piece':'Если фигуру атакуют, проверь, можно ли её защитить, увести или забрать нападающую фигуру.',
    'missed_capture':'Перед спокойным ходом посмотри, нет ли у соперника фигуры, которую можно выгодно забрать.',
    'missed_material':'Смотри не только на ближайший ответ, но и на то, что получится после него.',
    'missed_check':'Нападение на короля заставляет соперника защищаться и иногда даёт возможность забрать другую фигуру.',
    'missed_mate':'Если можешь напасть на короля, проверь, есть ли у него хоть один способ спастись.',
    'missed_forced_mate':'Когда король соперника плохо защищён, ищи ходы, после которых ему придётся всё время защищаться.',
    'allowed_mate':'Перед ходом проверь, не сможет ли соперник напасть на твоего короля так, что защититься будет невозможно.',
    'central_break':'Проверяй, не сможет ли пешка соперника оттеснить твою фигуру и заставить её ходить ещё раз.',
    'blocked_piece':'Старайся давать фигурам дорогу: фигура за своими пешками пока не помогает остальным.',
    'development':'В начале партии выводи в игру разные фигуры, чтобы они могли помогать друг другу.',
    'mobility':'Держи фигуры там, откуда у них есть выбор полезных ходов.',
    'opponent_activity':'Не оставляй сопернику всю свободу действий: старайся, чтобы твои фигуры тоже участвовали в игре.',
    'king_safety':'Пешки рядом с королём помогают его защищать; двигая их, проверяй, какие дороги ты открываешь сопернику.',
    'castling_rights':'Если хочешь сделать рокировку, не двигай заранее короля и нужную ладью: после этого такой ход уже невозможен.',
    'pawn_structure':'Старайся располагать пешки так, чтобы они могли защищать друг друга.',
    'passed_pawn':'Не оставляй без внимания пешку соперника, которой твои пешки уже не могут преградить путь.',
    'weak_square':'Следи за местами, где соперник может поставить фигуру и откуда её трудно прогнать.',
    'center_control':'Фигурам полезно влиять на середину доски: оттуда легче помогать на разных участках.',
    'won_to_equal':'Даже когда твоя позиция лучше, проверяй ответ соперника перед каждым ходом.',
    'equal_to_worse':'В спокойной позиции тоже проверяй, какую возможность твой ход даёт сопернику.',
}
DATIVE = {chess.PAWN:'пешке',chess.KNIGHT:'коню',chess.BISHOP:'слону',chess.ROOK:'ладье',chess.QUEEN:'ферзю',chess.KING:'королю'}


def legal_move(board, value):
    try:
        move = chess.Move.from_uci(value)
        return move if move in board.legal_moves else None
    except (ValueError, TypeError):
        return None


def describe_move(board, move):
    """Translate a legal move, including special moves, without requiring SAN knowledge."""
    if move not in board.legal_moves:
        return 'Этот ход недоступен в показанной позиции.'
    piece = board.piece_at(move.from_square)
    start, end = chess.square_name(move.from_square), chess.square_name(move.to_square)
    if board.is_castling(move):
        rank = '1' if piece.color else '8'
        kingside = board.is_kingside_castling(move)
        return (f'Рокировка — король с {start} идёт на {end}, '
                f"а ладья с {'h' if kingside else 'a'}{rank} — на {'f' if kingside else 'd'}{rank}.")
    text = f'{NAMES[piece.piece_type].capitalize()} с {start} идёт на {end}'
    if board.is_en_passant(move):
        square = move.to_square + (-8 if piece.color else 8)
        text += f' и забирает пешку с {chess.square_name(square)}'
    elif board.is_capture(move):
        victim = board.piece_at(move.to_square)
        text += f' и забирает {ACCUSATIVE[victim.piece_type]} соперника'
    if move.promotion:
        text += ' и превращается в ' + {chess.QUEEN:'ферзя',chess.ROOK:'ладью',chess.BISHOP:'слона',chess.KNIGHT:'коня'}[move.promotion]
    return text + '.'


def _victim(line, color):
    lost = [e for e in line['events'] if e['color'] == color]
    return max(lost, key=lambda e: VALUES[e['victim']]) if lost else None


def _loss_text(event):
    pronoun = 'твою' if event['victim'] in (chess.PAWN,chess.ROOK) else 'твоего'
    return f"Соперник может забрать {pronoun} {ACCUSATIVE[event['victim']]} на {chess.square_name(event['square'])}."


def present_simple(before, played, explanation, selected_uci=None, legacy_best=None, bad=True, selected_info=None):
    """Four short teaching blocks, derived from the selected comparison and legal continuation."""
    alternatives = explanation.get('alternatives', [])
    selected = next((a for a in alternatives if a['uci'] == selected_uci), None)
    if selected is None and selected_uci is None:
        selected = alternatives[0] if alternatives else None
    selected = selected or {}
    kind = selected.get('reason_type', explanation.get('reason_type', 'unresolved'))
    confidence = selected.get('confidence', explanation.get('confidence', 'low'))
    delta, motif = selected.get('feature_deltas', {}), selected.get('motif') or {}
    color = before.turn
    line = trace(before, [played.uci(), *explanation.get('opponent_pv', [])], color)
    if not line['valid']:
        kind,confidence = 'unresolved','low'
    event = _victim(line, color)
    why = 'По сохранённым данным точную причину ошибки пока нельзя объяснить уверенно.'
    consequence = 'Не стоит считать потерю фигуры или угрозу королю доказанной без проверенного продолжения.'
    benefit = ('Это вариант для сравнения; уверенно объяснить, какую проблему он исправляет, пока нельзя.' if selected else
               'Подробные причины выбора этого хода в старом разборе не сохранены.')
    key_squares = selected.get('key_squares', explanation.get('key_squares', []))[:2]

    if kind in ('material_loss','pawn_loss') and event:
        attacker = line['states'][event['ply']-1].piece_at(event['attacker'])
        why = (f"Этот ход позволяет {DATIVE[attacker.piece_type]} соперника забрать {ACCUSATIVE[event['victim']]} на {chess.square_name(event['square'])}."
               if attacker else 'Этот ход оставляет фигуру там, где соперник может её забрать.')
        consequence = _loss_text(event) + ' В этом продолжении потеря не окупается ответными взятиями.'
        best_line = trace(before, selected.get('pv',[]), color)
        if any(e['color']==color and e['victim']==event['victim'] for e in best_line['events']):
            returned = [e for e in best_line['events'] if e['color']!=color]
            benefit = ('В найденном продолжении ты можешь забрать '+ACCUSATIVE[returned[0]['victim']]+' соперника в ответ.'
                       if returned else 'В этом продолжении итог после взятий для тебя лучше, хотя потеря тоже возможна.')
        else:benefit = 'Так ты избежишь этой потери в найденном продолжении.'
        key_squares = [event['square']]
    elif kind in ('fork','double_attack') and event:
        position = line['states'][min(motif.get('ply',1),len(line['states'])-1)]
        targets = [position.piece_at(s) for s in motif.get('targets',[]) if position.piece_at(s)]
        names = [ACCUSATIVE[p.piece_type] for p in targets]
        why = 'Ты позволяешь одной фигуре соперника напасть сразу на ' + (', '.join(names[:-1])+' и '+names[-1] if len(names)>1 else 'две твои фигуры') + '.'
        consequence = _loss_text(event) + (' Пока ты защищаешь короля, другая фигура остаётся под угрозой.' if any(p.piece_type==chess.KING for p in targets) else 'Одновременно справиться с обеими угрозами в найденном продолжении не получается.')
        benefit = 'Этот ход избегает показанного двойного нападения и потери фигуры.'
        attack = legal_move(line['states'][1], motif.get('move'))
        key_squares = [event['square'], attack.from_square] if attack else [event['square']]
    elif kind == 'pin' and event:
        position = line['states'][min(motif.get('ply',1),len(line['states'])-1)]
        targets = [position.piece_at(s) for s in motif.get('targets',[]) if position.piece_at(s)]
        protector = NAMES[targets[0].piece_type].capitalize() if targets else 'Твоя фигура'
        protected = ACCUSATIVE[targets[-1].piece_type] if len(targets)>1 else 'другую фигуру'
        why = (protector+' прикрывает короля. Увести защитника нельзя: тогда король останется под ударом.' if motif.get('absolute') else
               protector+' прикрывает '+protected+'. Если убрать защитника, соперник сможет забрать '+protected+'.')
        consequence = _loss_text(event) + ' Прикрывающей фигуре трудно уйти, не открыв другую угрозу.'
        benefit = 'Так фигура не попадает в показанную ловушку.'
    elif kind == 'discovered_attack' and event:
        why = 'Когда соперник передвигает одну фигуру, он открывает дорогу другой. На этой дороге оказывается твоя фигура.'
        prior = line['states'][max(0,min(motif.get('ply',1)-1,len(line['states'])-1))]
        opened = prior.piece_at(motif.get('attacker',-1)) if motif.get('attacker') is not None else None
        uncovering = legal_move(prior,motif.get('move'))
        blocker = prior.piece_at(uncovering.from_square) if uncovering else None
        if opened and blocker:
            relative = 'которая закрывала' if blocker.piece_type in (chess.PAWN,chess.ROOK) else 'который закрывал'
            pronoun = 'твою' if event['victim'] in (chess.PAWN,chess.ROOK) else 'твоего'
            why = ('Соперник уводит '+ACCUSATIVE[blocker.piece_type]+', '+relative+' дорогу '+DATIVE[opened.piece_type]+'. '
                   +NAMES[opened.piece_type].capitalize()+' получает возможность забрать '+pronoun+' '+ACCUSATIVE[event['victim']]+'.')
        consequence = _loss_text(event)
        benefit = 'Этот ход не оставляет фигуру на дороге показанного нападения.'
    elif kind == 'overloaded_defender' and event:
        why = 'Одна твоя фигура должна защищать сразу две другие. Соперник заставляет её переключиться на одну из них.'
        defender = line['states'][min(1,len(line['states'])-1)].piece_at(motif['attacker']) if motif.get('attacker') is not None else None
        if defender:why = NAMES[defender.piece_type].capitalize()+' защищает сразу две фигуры. Соперник заставляет защитника переключиться на одну из них.'
        consequence = _loss_text(event) + ' После ухода защитника ей некому помочь.'
        benefit = 'Этот ход избегает показанной потери и не требует от одного защитника справиться с обеими угрозами.'
    elif kind == 'bad_exchange' and event:
        taken = next((e for e in line['events'] if e['ply']==1 and e['color']!=color),None)
        why = ('Ты забираешь '+ACCUSATIVE[taken['victim']]+', но в ответ теряешь '+ACCUSATIVE[event['victim']]+'. '
               +NAMES[event['victim']].capitalize()+' обычно ценнее.' if taken and VALUES[event['victim']]>VALUES[taken['victim']] else
               'Ты забираешь фигуру соперника, но в ответ отдаёшь больше, чем получаешь.')
        consequence = _loss_text(event) + ' После взаимных взятий у тебя остаётся меньше ценных фигур.'
        benefit = 'Так ты избежишь показанного невыгодного обмена фигурами.'
    elif kind == 'hanging_piece' and motif:
        why = 'После этого хода одну из твоих фигур можно забрать.'
        threat = {'victim':motif['piece'],'square':motif['square']}
        consequence = _loss_text(threat) + ' Не установлено, сможешь ли ты получить что-то полезное в ответ.'
        benefit = 'Этот ход убирает именно эту возможность взятия.'
    elif kind in ('missed_capture','missed_check','missed_material'):
        why = 'Ты пропускаешь возможность забрать фигуру или пешку соперника и сохранить выигрыш после его ответа.'
        if kind == 'missed_check':
            why = 'Ты пропускаешь нападение на короля, после которого можно забрать другую фигуру соперника.'
        consequence = 'Соперник избегает потери, которая была возможна при более сильном ходе.'
        benefit = 'В найденном продолжении этот ход позволяет забрать фигуру или пешку и не отдать равноценную взамен.'
    elif kind in ('missed_mate','missed_forced_mate'):
        why = 'Ты мог закончить партию победой сразу, но оставил сопернику возможность продолжить игру.' if kind=='missed_mate' else 'Ты пропустил последовательность нападений на короля, которая приводит к победе.'
        consequence = 'Король соперника получает возможность избежать показанного проигрыша.'
        benefit = 'После этого хода королю соперника уже не спастись — это мат.' if kind=='missed_mate' else 'Этот ход начинает найденную последовательность, после которой короля соперника нельзя спасти.'
    elif kind == 'allowed_mate':
        why = 'Ты даёшь сопернику возможность напасть на твоего короля так, что защитить его будет невозможно.'
        consequence = 'В найденном продолжении соперник ставит мат — король под ударом, а безопасного ответа нет. Партия заканчивается поражением.'
        benefit = 'Этот ход не даёт сопернику закончить партию показанным нападением на короля.'
    elif kind == 'central_break':
        why = 'Соперник может продвинуть пешку в середину доски и одновременно напасть на твою фигуру.'
        consequence = 'Тебе придётся отвечать на нападение, пока соперник занимает удобное место в центре.'
        benefit = 'После этого хода такое же нападение пешкой не возникает в найденном продолжении.'
    elif kind == 'blocked_piece':
        blocked = next((a for a in delta.get('activity',[]) if a['piece']==chess.BISHOP and a['actual']<=2), {})
        square = chess.square_name(blocked['actual_square']) if blocked else ''
        why = f'Твой слон {square} остаётся за своими пешками. Они мешают ему выйти и помогать другим фигурам.'
        consequence = 'У слона меньше мест, куда он может пойти, чем после рекомендуемого хода.'
        benefit = 'Этот ход открывает слону дорогу и даёт ему больше возможностей помогать в игре.'
    elif kind == 'development':
        why = 'Ты тратишь ход, но не выводишь новую фигуру в игру. Часть фигур всё ещё стоит там, где начинала партию.'
        consequence = 'Соперник получает ход, а у тебя меньше фигур готово помогать друг другу, чем после рекомендуемого хода.'
        benefit = 'Так ещё одна фигура выходит со своего начального места и начинает участвовать в игре.'
    elif kind in ('mobility','opponent_activity'):
        why = 'После этого хода твоим фигурам теснее, чем после рекомендуемого.' if kind=='mobility' else 'В найденном продолжении у фигур соперника больше свободы, чем после рекомендуемого хода.'
        consequence = 'Твоей фигуре доступно меньше мест, куда она может пойти.' if kind=='mobility' else 'Сопернику легче выбирать, куда направить свои фигуры.'
        benefit = 'Этот ход даёт твоей фигуре больше свободы.' if kind=='mobility' else 'Этот ход оставляет сопернику меньше свободы в найденном продолжении.'
    elif kind == 'king_safety':
        why = 'После этого хода рядом с твоим королём остаётся меньше пешек, которые его прикрывают.'
        consequence = 'Соперник может нападать на большее число клеток рядом с королём.'
        benefit = 'Этот ход сохраняет пешки, которые прикрывают короля.'
    elif kind == 'castling_rights':
        why = 'После движения короля или ладьи теряется возможность рокировки — совместного хода этих двух фигур.'
        consequence = 'Позже ты уже не сможешь перенести короля в сторону с помощью этой рокировки.'
        benefit = 'Этот ход сохраняет возможность рокировки на будущее.'
    elif kind == 'pawn_structure':
        why = 'После этого хода пешки хуже защищают друг друга, чем после рекомендуемого.'
        consequence = 'Другим фигурам приходится помогать пешкам, которым не хватает соседней защиты.'
        benefit = 'Этот ход сохраняет более удобное расположение пешек для взаимной защиты.'
    elif kind == 'passed_pawn':
        why = 'У соперника появляется пешка, которой твои пешки впереди и по соседству уже не могут преградить путь.'
        consequence = 'Она может двигаться к последнему ряду, где станет другой фигурой. Останавливать её придётся фигурами.'
        benefit = 'В найденном продолжении этот ход не даёт появиться такой пешке.'
    elif kind == 'weak_square':
        why = 'Ты оставляешь удобное место для коня соперника и теряешь возможность прогнать его пешкой.'
        consequence = 'В найденном продолжении соперник ставит там коня, которому твои пешки уже не угрожают.'
        benefit = 'Так твои пешки продолжают угрожать этому месту и мешают коню устроиться там.'
    elif kind == 'center_control':
        why = 'Твои фигуры и пешки меньше влияют на середину доски, чем после рекомендуемого хода.'
        consequence = 'У тебя меньше возможностей мешать сопернику занимать центральные клетки.'
        benefit = 'Так ты можешь угрожать большему числу клеток в середине доски.'
    elif kind in ('won_to_equal','equal_to_worse'):
        why = 'Ты позволяешь сопернику исправить положение, хотя до этого у тебя были лучшие возможности.' if kind=='won_to_equal' else 'Ты даёшь сопернику более удобную игру в позиции, где шансы были примерно равны.'
        consequence = 'Твоё преимущество исчезает в найденном продолжении.' if kind=='won_to_equal' else 'После ответа соперника тебе становится труднее сохранять равные шансы на победу.'
        benefit = 'Этот ход сохраняет более удобное положение в найденном продолжении.'
    elif kind == 'analysis_conflict':
        why = 'Более внимательная проверка не подтвердила, что предложенный ход лучше твоего.'
        consequence = 'Нельзя уверенно говорить, что твой ход ведёт к потере фигуры или другой конкретной проблеме.'
        benefit = 'Это вариант для сравнения, а не доказанное исправление ошибки.'
    elif not bad:
        kind = 'good'
        why = 'В этом разборе ход не отмечен как ошибка.'
        consequence = 'Проверенной проблемы, которую нужно исправить, здесь не показано.'
        benefit = 'Это другой допустимый ход, а не обязательное исправление.'

    if kind=='allowed_mate' and selected_info and selected_info.get('mate') is not None and not selected_info.get('mate_winning'):
        benefit = 'В этом варианте королю тоже не удаётся спастись. Это не исправляет найденную проблему.'
    chosen = legal_move(before, selected.get('uci') or explanation.get('chosen_recommendation'))
    if chosen is None and legacy_best:
        try:chosen = before.parse_san(legacy_best)
        except (ValueError,TypeError):pass
    recommendation = describe_move(before, chosen) + ' ' + benefit if chosen else 'Проверенный лучший ход для этой позиции не сохранён.'
    alternative_fact = ''
    if chosen and kind not in ('unresolved','analysis_conflict'):
        after = before.copy(stack=False);after.push(chosen)
        mover = after.piece_at(chosen.to_square)
        for fact in selected.get('distinguishing_features',[]):
            if fact['type']=='pressure' and mover.piece_type!=chess.KING:
                targets = [s for s in fact['squares'][:2] if after.piece_at(s)]
                alternative_fact = (f'С этого места {NAMES[mover.piece_type]} также нападает на '+
                    ' и '.join(ACCUSATIVE[after.piece_type_at(s)]+' соперника на '+chess.square_name(s) for s in targets)+'.') if targets else ''
                if alternative_fact:break
            if fact['type']=='pawn_control':
                alternative_fact = 'Ещё эта пешка мешает сопернику занять клетки '+', '.join(chess.square_name(s) for s in fact['squares'][:2])+'.'
                break
    return {'kind':kind,'confidence':confidence,'why':why,'consequence':consequence,
            'recommendation':recommendation,'principle':PRINCIPLES.get(kind,PRINCIPLES['material_loss']),
            'move_description':describe_move(before,played),'recommended_uci':chosen.uci() if chosen else None,
            'key_squares':list(dict.fromkeys(key_squares))[:2],'alternative_fact':alternative_fact}
