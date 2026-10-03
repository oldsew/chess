"""Causal offline teaching: compare legal continuations, tactics and both resulting positions."""
from __future__ import annotations

import chess

from app.config.settings import TUNING
from app.services.material import VALUES
from app.services.position_features import (NAMES,ACCUSATIVE,CENTER,compare,features,piece_label,trace,tactical_motifs)

CFG=TUNING['explainer']
TITLES={'material_loss':'Потеря фигуры','pawn_loss':'Потеря пешки','bad_exchange':'Невыгодный размен',
        'fork':'Вилка','pin':'Связка','double_attack':'Двойное нападение','discovered_attack':'Вскрытое нападение',
        'overloaded_defender':'Перегруженный защитник','missed_capture':'Упущенное взятие','missed_mate':'Упущен мат в один',
        'missed_check':'Упущен выигрыш с шахом','missed_material':'Упущен выигрыш материала','opponent_activity':'Активность соперника',
        'missed_forced_mate':'Упущена матовая атака','allowed_mate':'Допущена матовая атака',
        'hanging_piece':'Фигура остаётся под боем','central_break':'Пешечный удар с темпом','blocked_piece':'Ограниченная фигура',
        'king_safety':'Ослаблена защита короля','castling_rights':'Потеря возможности рокировки',
        'pawn_structure':'Ухудшение пешечной структуры','passed_pawn':'Проходная пешка соперника',
        'weak_square':'Слабая клетка','center_control':'Уступлен центр','development':'Потеря времени на развитие',
        'mobility':'Снижение активности','won_to_equal':'Упущено преимущество','equal_to_worse':'Уступлена инициатива',
        'analysis_conflict':'Оценки требуют уточнения','unresolved':'Причина не установлена'}
TACTIC_NAMES={'fork':'вилку','pin':'связку','double_attack':'двойное нападение','discovered_attack':'вскрытое нападение',
              'overloaded_defender':'отвлечение перегруженного защитника'}
ATTEMPTS=['material','attack_maps','mobility','king_safety','development','pawn_structure','center_control','tactical_motifs','pv']


def square_names(squares):return ', '.join(chess.square_name(s) for s in squares)


def _line(board, data, color, first=None):
    moves=(data or {}).get('analysis_pv_uci') or (data or {}).get('pv_uci') or []
    line=trace(board,([first.uci()] if first else [])+moves[:TUNING['coaching']['analysis_pv_plies']-(1 if first else 0)],color)
    line['valid'] = line['valid'] and (data or {}).get('analysis_pv_valid',True)
    return line


def _reply(line):
    return line['san'][1] if len(line['san'])>1 else 'в этой позиции'


def _capture_sentence(line, color):
    lost=[e for e in line['events'] if e['color']==color]
    if not lost:return ''
    event=max(lost,key=lambda e:VALUES[e['victim']])
    prefix=' → '.join(line['san'][:event['ply']])
    return f"В варианте {prefix} соперник берёт {ACCUSATIVE[event['victim']]} на {chess.square_name(event['square'])}."


def _central_tempo(line,color):
    if len(line['moves'])<2:return None
    move=line['moves'][1];position=line['states'][2]
    if position.piece_at(move.to_square)!=chess.Piece(chess.PAWN,not color) or move.to_square not in CENTER:return None
    targets=[s for s in position.attacks(move.to_square) if position.piece_at(s) and
             position.piece_at(s).color==color and position.piece_type_at(s)!=chess.PAWN]
    if targets:return {'move':move.uci(),'san':line['san'][1],'square':move.to_square,'targets':targets}
    return None


def _blocked(before,played,alt,delta):
    for item in delta['activity']:
        if item['gain']<CFG['piece_mobility_gain']:continue
        if item['piece']==chess.BISHOP and item['actual']<=2:
            board=before.copy(stack=False);board.push(played)
            square=item['actual_square'];pawn_blocks=[]
            for df,dr in [(1,1),(1,-1),(-1,1),(-1,-1)]:
                f,r=chess.square_file(square)+df,chess.square_rank(square)+dr
                if 0<=f<8 and 0<=r<8:
                    s=chess.square(f,r)
                    if board.piece_at(s)==chess.Piece(chess.PAWN,before.turn):pawn_blocks.append(s)
            if pawn_blocks:return {**item,'blockers':pawn_blocks}
    return None


def _select_reason(before,played,alt,data,notes,actual_line,best_line,delta,motifs,color):
    """Rank evidence by consequence, then comparison of concrete positional differences."""
    san=before.san(played);best_san=before.san(alt)
    score=data.get('evaluation_cp');after=notes.get('after_cp')
    gap=score-after if score is not None and after is not None else None
    supported=gap is not None and gap>CFG['minimum_feature_gap_cp']
    position=before.copy(stack=False);position.push(alt)
    if position.is_checkmate() and not actual_line['states'][1].is_checkmate():
        return 'missed_mate','high',f'{san} упускает немедленное окончание партии: {best_san} ставит мат. У короля нет законного ответа на шах.',[alt.to_square],{'mate':True}
    if (notes.get('reason')=='allowed_mate' or
        notes.get('reason')=='missed_forced_mate' and data.get('mate_winning')):
        kind=notes['reason']
        text=(f'{san} допускает матовую последовательность соперника после {_reply(actual_line)}.' if kind=='allowed_mate' else
              f'{san} упускает найденную матовую атаку; {best_san} сохраняет форсированный мат.')
        return kind,'high',text,[actual_line['final'].king(color)],{'mate':True}
    if score is not None and after is not None and score<=after:
        return 'analysis_conflict','low',(f'При сопоставимом анализе преимущество {best_san} над {san} не подтверждено. '
                                        'Не следует приписывать этому ходу непроверенную тактическую или стратегическую ошибку.'),[],{}
    material_a,material_b=delta['material_delta'],delta['best_material_delta']
    material_gap=material_b-material_a
    legacy=notes.get('comparison',{}).get('legacy_or_fixture',False)
    enough=(legacy or (len(actual_line['moves'])>=TUNING['coaching']['min_explanation_plies'] or actual_line['terminal']) and
                      (len(best_line['moves'])>=TUNING['coaching']['min_explanation_plies'] or best_line['terminal']))
    material_supported=(supported and (legacy or notes.get('comparison',{}).get('equal_depth'))
                        and material_gap>=1 and gap>=material_gap*100*CFG['material_score_ratio'] and
                        actual_line['valid'] and best_line['valid'] and enough)
    lost=[e for e in actual_line['events'] if e['color']==color]
    if material_supported and material_a<0 and lost:
        proved=[m for m in motifs if m.get('verified_capture')]
        if proved:
            motif=min(proved,key=lambda m:m['ply'])
            targets=', '.join(piece_label(actual_line['states'][motif['ply']],s) for s in motif['targets'])
            text=f"После {san} ответ {motif['san']} создаёт {TACTIC_NAMES[motif['type']]}: под угрозой {targets}. "
            text+=_capture_sentence(actual_line,color)
            return motif['type'],'high',text,motif['targets'],motif
        if before.is_capture(played):
            gained=sum(VALUES[e['victim']] for e in actual_line['events'] if e['color']!=color)
            given=sum(VALUES[e['victim']] for e in lost)
            text=(f'После {san} размен оказывается невыгодным: в показанной линии вы отдаёте материал стоимостью {given} '
                  f'за {gained}. '+_capture_sentence(actual_line,color))
            return 'bad_exchange','high',text,[e['square'] for e in lost],{'given':given,'received':gained}
        event=max(lost,key=lambda e:VALUES[e['victim']])
        kind='pawn_loss' if event['victim']==chess.PAWN else 'material_loss'
        return kind,'high',f'{san} позволяет сопернику выиграть материал. '+_capture_sentence(actual_line,color),[event['square']],event
    if material_supported and material_b>0 and material_b>material_a and before.is_capture(alt) and not before.is_capture(played):
        target=before.piece_at(alt.to_square)
        label=ACCUSATIVE[target.piece_type] if target else 'пешку на проходе'
        return 'missed_capture','high',f'{san} упускает выгодное взятие {best_san}: можно забрать {label} на {chess.square_name(alt.to_square)}. В проверенной линии размены сохраняют выигрыш материала.',[alt.to_square],{}
    if material_supported and material_b>=3 and material_a>=0:
        won=[e for e in best_line['events'] if e['color']!=color]
        kind='missed_check' if position.is_check() and not actual_line['states'][1].is_check() else 'missed_material'
        text=(f'{san} упускает выигрыш материала в линии {best_san}: '
              + ('шах вынуждает соперника отвечать на угрозу королю. ' if kind=='missed_check' else '')
              + f"Проверенное продолжение {' → '.join(best_line['san'][:6])} улучшает материальный баланс на {material_b}.")
        return kind,'high',text,[e['square'] for e in won],{'captures':won}
    # A legal capture threat is useful even when a short PV cannot prove an uncompensated loss.
    threats=delta['removed_capture_threats']
    if threats and supported:
        threat=max(threats,key=lambda h:VALUES[h['piece']])
        text=(f"После {san} {NAMES[threat['piece']]} на {chess.square_name(threat['square'])} остаётся под боем: "
              f"соперник может сыграть {threat['san']}. Короткая линия не доказывает отсутствие компенсации, но рекомендуемый ход устраняет именно эту угрозу.")
        return 'hanging_piece','medium',text,[threat['square']],threat
    tempo=_central_tempo(actual_line,color)
    if tempo and supported:
        alt_position=best_line['states'][1]
        attacked=[s for s in tempo['targets'] if alt_position.piece_at(s) and alt_position.piece_at(s).color==color]
        better_tempo=_central_tempo(best_line,color)
        if (delta['center_control_delta']>=1 or not attacked) and (not better_tempo or not set(tempo['targets'])&set(better_tempo['targets'])):
            labels=', '.join(piece_label(actual_line['states'][2],s) for s in tempo['targets'])
            return 'central_break','medium',(f'{san} позволяет {_reply(actual_line)} с темпом: центральная пешка нападает на {labels}. '
                                           f'После {best_san} такая же атака не возникает в показанном продолжении.'),tempo['targets'],tempo
    # Losing rights is factual; attach it to the evaluated comparison, not every king/rook move.
    if supported and delta['actual']['castling']<delta['best']['castling'] and before.fullmove_number<=CFG['opening_max_move']:
        return 'castling_rights','medium',f'{san} лишает вас возможности рокировки, которую {best_san} сохраняет. В показанной линии соперник отвечает {_reply(actual_line)}.',[before.king(color)],{}
    if (supported and delta['king_safety_delta']>=CFG['king_danger_gain'] and
        len(delta['actual']['shield'])<len(delta['best']['shield']) and before.pieces(chess.QUEEN,not color)):
        exposed=sorted(set(delta['best']['shield'])-set(delta['actual']['shield']))
        return 'king_safety','medium',(f'{san} уменьшает пешечное прикрытие короля: не хватает защиты на {square_names(exposed)}. '
                                      f'После вашего хода больше клеток рядом с королём доступно атакам соперника; {best_san} сохраняет прикрытие. Продолжение соперника: {_reply(actual_line)}.'),exposed,{}
    if supported and delta['actual']['pawn_structure']>delta['best']['pawn_structure']:
        doubled=delta['actual']['pawns']['doubled'];isolated=delta['actual']['pawns']['isolated']
        weak=doubled or isolated
        label='сдвоенные' if doubled else 'изолированные'
        return 'pawn_structure','medium',(f'{san} оставляет {label} пешки на {square_names(weak)}; {best_san} избегает такого ухудшения структуры. '
                                          f'Соперник получает продолжение {_reply(actual_line)}. Эти пешки требуют защиты фигурами.'),weak,{}
    passed=set(delta['end_opponent_actual']['pawns']['passed'])-set(delta['end_opponent_best']['pawns']['passed'])
    if supported and passed:
        return 'passed_pawn','medium',(f'После {san} в линии {_reply(actual_line)} у соперника появляется проходная пешка на {square_names(sorted(passed))}: '
                                      f'на соседних вертикалях впереди неё нет ваших пешек. {best_san} не допускает её в сравниваемом варианте.'),sorted(passed),{}
    weak=set(delta['best']['pawns']['control'])-set(delta['actual']['pawns']['control'])
    outposts=[s for s,p in actual_line['final'].piece_map().items() if p.color!=color and p.piece_type==chess.KNIGHT and s in weak]
    if supported and outposts:
        return 'weak_square','medium',f'{san} уступает пешечный контроль клеток {square_names(outposts)}. В линии соперник занимает их конём; {best_san} сохраняет контроль пешками и мешает такому вторжению.',outposts,{}
    blocked=_blocked(before,played,alt,delta)
    if supported and blocked:
        return 'blocked_piece','medium',(f"После {san} слон {chess.square_name(blocked['actual_square'])} остаётся закрыт своими пешками "
                                         f"на {square_names(blocked['blockers'])}: доступно лишь {blocked['actual']} ходов вместо {blocked['best']} после {best_san}. "
                                         f"Соперник тем временем получает {_reply(actual_line)}."),[blocked['actual_square'],*blocked['blockers']],blocked
    if supported and delta['center_control_delta']>=CFG['center_gain']:
        squares=sorted(set(delta['best']['center_squares'])-set(delta['actual']['center_squares']))
        return 'center_control','medium',(f'{san} уступает контроль центральных клеток {square_names(squares)} по сравнению с {best_san}. '
                                         f'Соперник получает {_reply(actual_line)}; ваш пешечный контроль и число возможностей давления на центр ниже.'),squares,{}
    if supported and delta['development_delta']>=1 and before.fullmove_number<=CFG['opening_max_move']:
        remaining=delta['actual']['undeveloped']
        return 'development','medium',(f'{san} тратит ход, оставляя на исходных клетках {square_names(remaining)}. '
                                      f'В ответ соперник получает {_reply(actual_line)}. {best_san} выводит ещё одну фигуру в игру; ваш ход не развивает новую фигуру.'),remaining,{}
    if supported and delta['mobility_delta']>=CFG['mobility_gain'] and delta['activity']:
        item=delta['activity'][0]
        return 'mobility','medium',(f"После {san} {NAMES[item['piece']]} {chess.square_name(item['actual_square'])} имеет {item['actual']} доступных ходов "
                                   f"против {item['best']} в варианте {best_san}. Продолжение соперника: {_reply(actual_line)}; "
                                   'рекомендация сохраняет активность этой фигуры.'),[item['actual_square']],item
    if supported and score>=CFG['winning_cp'] and abs(after)<=CFG['equal_cp']:
        return 'won_to_equal','medium',f'{san} упускает преимущество: после {_reply(actual_line)} и показанных ответов соперник выравнивает игру. {best_san} сохраняет выигрышные возможности в сравниваемом продолжении.',[],{}
    if supported and abs(score)<=CFG['equal_cp'] and after<=-CFG['worse_cp']:
        return 'equal_to_worse','medium',f'{san} передаёт инициативу сопернику после {_reply(actual_line)}; равновесие сохраняется в варианте {best_san}. Конкретный тактический выигрыш в доступной линии не установлен.',[],{}
    enemy_a,enemy_b=delta['end_opponent_actual']['mobility'],delta['end_opponent_best']['mobility']
    if supported and enemy_a-enemy_b>=CFG['mobility_gain']:
        return 'opponent_activity','medium',(f'В продолжении после {san} свобода фигур соперника выше: {enemy_a} доступных ходов '
                                            f'против {enemy_b} после {best_san} на одинаковом горизонте. Начало линии: {_reply(actual_line)}. '
                                            'Это подтверждённое отличие позиций; единственная тактическая причина не найдена.'),[],{}
    return 'unresolved','low',(f'В проверенном продолжении после {san} соперник выбирает {_reply(actual_line)}. '
                              'Сравнение материала, угроз, свободы фигур, короля, пешек, развития и центра не выделило надёжную единственную причину. '
                              'Разберите показанные ответы: приписывать им конкретную стратегическую историю было бы неточно.'),[],{}


def _alternative_idea(before,played,alt,data,actual_line,line,delta,primary,color):
    san=before.san(alt);actual_san=before.san(played)
    after=before.copy(stack=False);after.push(alt)
    hints=[];facts=[]
    if after.is_checkmate():return f'{san} сразу ставит мат; {actual_san} оставляет сопернику ответ.', [{'type':'mate'}]
    if data.get('mate') is not None and data.get('mate_winning'):
        hints.append('сохраняет найденную форсированную матовую атаку');facts.append({'type':'forced_mate'})
    if delta['best_material_delta']>delta['material_delta']:
        if delta['best_material_delta']>0:hints.append(f"сохраняет выигрыш материала (+{delta['best_material_delta']}) в этой линии")
        else:hints.append('сохраняет материал, который теряется после вашего хода')
        facts.append({'type':'material','actual':delta['material_delta'],'alternative':delta['best_material_delta']})
    if delta['removed_capture_threats']:
        h=max(delta['removed_capture_threats'],key=lambda h:VALUES[h['piece']])
        hints.append(f"устраняет возможность взять {ACCUSATIVE[h['piece']]} на {chess.square_name(h['square'])} ходом {h['san']}")
        facts.append({'type':'removed_capture','capture':h['capture'],'square':h['square']})
    mover=after.piece_at(alt.to_square)
    defended=sorted(s for s in after.attacks(alt.to_square) if after.piece_at(s) and after.piece_at(s).color==color and after.piece_type_at(s)!=chess.KING)
    targets=sorted(s for s in after.attacks(alt.to_square) if after.piece_at(s) and after.piece_at(s).color!=color and after.piece_type_at(s)!=chess.KING)
    if targets and not after.is_pinned(color,alt.to_square):
        hints.append('создаёт давление на '+', '.join(ACCUSATIVE[after.piece_type_at(s)]+' '+chess.square_name(s) for s in targets[:2]));facts.append({'type':'pressure','squares':targets})
    if delta['development_delta']>0:
        cleared=[s for s in delta['actual']['undeveloped'] if s not in delta['best']['undeveloped']]
        hints.append('включает в игру фигуру с '+square_names(cleared)+' вместо потери времени');facts.append({'type':'development','squares':cleared})
    controlled=sorted(set(delta['best']['center_squares'])-set(delta['actual']['center_squares']))
    if controlled:
        hints.append('сохраняет дополнительный контроль '+square_names(controlled));facts.append({'type':'center','squares':controlled})
    if mover.piece_type==chess.ROOK:
        file=chess.square_file(alt.to_square)
        if not any(chess.square_file(p)==file for c in [True,False] for p in after.pieces(chess.PAWN,c)):
            hints.append(f'даёт ладье открытую вертикаль {chess.FILE_NAMES[file]} вместо ограниченной активности');facts.append({'type':'open_file','file':file})
    if delta['activity']:
        item=delta['activity'][0]
        if item['gain']>=2:
            hints.append(f"даёт фигуре ({NAMES[item['piece']]}) {item['best']} доступных ходов вместо {item['actual']}")
            facts.append({'type':'mobility','square':item['best_square'],'gain':item['gain']})
    if delta['best']['castling']>delta['actual']['castling']:
        hints.append('сохраняет возможность рокировки');facts.append({'type':'castling'})
    if delta['best']['pawn_structure']<delta['actual']['pawn_structure']:
        hints.append('оставляет меньше изолированных или сдвоенных пешек');facts.append({'type':'pawn_structure'})
    # A square-specific protected target distinguishes otherwise similar saving moves.
    if defended:
        hints.append('поддерживает '+', '.join(ACCUSATIVE[after.piece_type_at(s)]+' '+chess.square_name(s) for s in defended[:2]));facts.append({'type':'defence','squares':defended})
    if not hints:
        enemy_a=delta['end_opponent_actual']['mobility'];enemy_b=delta['end_opponent_best']['mobility']
        if enemy_b<enemy_a:
            hints.append(f'ограничивает свободу фигур соперника ({enemy_b} ходов против {enemy_a} в сравниваемом горизонте)')
            facts.append({'type':'opponent_mobility','actual':enemy_a,'alternative':enemy_b})
    text=f"{san} — "+'; '.join(hints[:3])+'.' if hints else f'{san} сохраняет более устойчивый результат в анализируемой линии; проверенной единственной позиционной причины не найдено.'
    if len(line['san'])>1:text+=f" Отличие продолжения: соперник отвечает {line['san'][1]}"+(' → '+line['san'][2] if len(line['san'])>2 else '')+'.'
    return text,facts


def explain(before, played, notes, color):
    actual=_line(before,notes.get('response'),color,played)
    candidates=[]
    motifs=tactical_motifs(actual,color)
    for data in notes.get('alternatives',[]):
        try:move=chess.Move.from_uci(data['uci'])
        except (ValueError,KeyError):continue
        if move not in before.legal_moves:continue
        line=_line(before,data,color)
        delta=compare(before,played,move,actual,line,color)
        kind,confidence,reason,squares,motif=_select_reason(before,played,move,data,notes,actual,line,delta,motifs,color)
        idea,distinguishing=_alternative_idea(before,played,move,data,actual,line,delta,kind,color)
        if kind=='analysis_conflict':idea=f"{before.san(move)}: короткие оценки не подтверждают преимущество этой линии. Сравните конкретные ответы; уверенная причина ошибки не установлена."
        candidates.append({'uci':move.uci(),'san':before.san(move),'idea':idea,'confidence':confidence,
                           'reason_type':kind,'reason':reason,'feature_deltas':delta,'distinguishing_features':distinguishing,
                           'key_squares':[s for s in squares if s is not None],'motif':motif,
                           'pv':line['pv_uci'],'pv_san':' → '.join(line['san'][:6]),'reply_san':_reply(line)})
    primary=candidates[0] if candidates else None
    kind=primary['reason_type'] if primary else 'unresolved'
    confidence=primary['confidence'] if primary else 'low'
    delta=primary['feature_deltas'] if primary else {}
    highlights=[{'from':played.from_square,'to':played.to_square,'role':'played'}]
    if primary:
        move=chess.Move.from_uci(primary['uci']);highlights.append({'from':move.from_square,'to':move.to_square,'role':'recommended'})
    facts={key:delta.get(key) for key in ['material_delta','hanging_piece','king_safety_delta','mobility_delta','center_control_delta','development_delta']}
    facts.update(detected_tactic=primary['motif'] if primary else None,PV=actual['pv_uci'],confidence=confidence,
                 comparison=notes.get('comparison'),checks_attempted=ATTEMPTS)
    # Public legacy aliases are retained for saved analysis compatibility.
    return {'version':2,'title':TITLES[kind],'reason_type':kind,'detected_motif':kind,'confidence':confidence,
            'explanation_confidence':confidence,'idea_confidence':confidence,
            'reason':primary['reason'] if primary else 'Для этого старого разбора не сохранены проверенные линии. Требуется новый анализ партии.',
            'recommendation':primary['idea'] if primary else 'Нет проверенной рекомендации.',
            'opponent_line':' → '.join(actual['san'][1:7]),'opponent_pv':actual['pv_uci'][1:],
            'chosen_recommendation':primary['uci'] if primary else None,'pv':primary['pv'] if primary else [],
            'material_delta':delta.get('material_delta'),'factors':facts,'highlights':highlights,
            'key_squares':primary['key_squares'] if primary else [],'alternatives':candidates,
            'fallback':kind in ('unresolved','analysis_conflict'),'checks_attempted':ATTEMPTS}
