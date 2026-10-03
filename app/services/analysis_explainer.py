"""Local teaching from legal board facts and existing PV evidence. No engine/API calls."""
from __future__ import annotations

import chess

NAMES = {chess.PAWN: 'пешка', chess.KNIGHT: 'конь', chess.BISHOP: 'слон',
         chess.ROOK: 'ладья', chess.QUEEN: 'ферзь', chess.KING: 'король'}
TITLES = {'material_loss': 'Потеря материала', 'pawn_loss': 'Потеря пешки',
          'missed_capture': 'Упущено выгодное взятие', 'missed_material': 'Упущен выигрыш материала',
          'missed_mate': 'Упущен мат в один', 'missed_forced_mate': 'Упущена матовая атака',
          'allowed_mate': 'Допущена матовая атака'}


def explain(before, played, notes, color):
    """Return structured prose, evidence and at most two board arrows, from one root."""
    reason_type = notes.get('reason')
    proven = notes.get('confidence') != 'fallback' and reason_type in TITLES
    alternatives = notes.get('alternatives', [])
    best = alternatives[0] if alternatives else None
    highlights = [{'from': played.from_square, 'to': played.to_square, 'role': 'played'}]
    confidence = 'high' if proven else 'low'
    factors = list(notes.get('evidence', []))
    motif = reason_type if proven else 'evaluation_only'
    reason = notes.get('advice', '') if proven else (
        'В показанном анализе этот ход снижает оценку с вашей стороны. '
        'Короткое продолжение не позволяет надёжно назвать конкретную причину.')
    recommendation = 'Для этого разбора проверенного рекомендуемого продолжения нет.'
    chosen = None
    if best:
        chosen = best['uci']
        candidate = chess.Move.from_uci(chosen)
        if candidate in before.legal_moves:
            highlights.append({'from': candidate.from_square, 'to': candidate.to_square, 'role': 'recommended'})
            position = before.copy(stack=False)
            piece = position.piece_at(candidate.from_square)
            position.push(candidate)
            recommendation = (f"{best['san']} сохраняет более высокую оценку в показанном продолжении. "
                              'Просмотрите линию и сравните ответы соперника; точная идея пока не установлена.')
            if position.is_checkmate():
                recommendation, motif = f"{best['san']} сразу ставит мат: у короля нет законного ответа на шах.", 'mate'
                confidence = 'high'
            elif best.get('mate') is not None and best.get('mate_winning'):
                recommendation, motif = f"{best['san']} сохраняет форсированную матовую атаку, найденную Stockfish.", 'forced_mate'
                confidence = 'high'
            elif proven and reason_type in ('material_loss', 'pawn_loss', 'allowed_mate'):
                if reason_type == 'allowed_mate':
                    recommendation = (f"{best['san']} избегает показанной форсированной матовой последовательности соперника."
                                      if best.get('mate') is None else
                                      f"{best['san']} — рекомендуемая защита Stockfish. Матовая угроза остаётся; сравните найденные линии.")
                else:
                    data = notes['evidence'][0]
                    recommendation = (f"{best['san']} сохраняет материал в показанной линии "
                                      f"({data['best_line_material_change']:+d} против {data['played_line_material_change']:+d} "
                                      'после вашего хода). Это сравнение вариантов, а не гарантия ответа соперника.')
            elif proven and reason_type in ('missed_capture', 'missed_material'):
                data = notes['evidence'][0]
                recommendation = (f"{best['san']} использует возможность выиграть материал: показанная линия "
                                  f"улучшает материальный баланс на {data['best_line_material_change']:+d}.")
            else:
                # These describe observable geometry, not an invented cause of the evaluation.
                idea = None
                home_rank = 0 if color else 7
                if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(candidate.from_square) == home_rank:
                    idea, motif = f"Ход выводит фигуру ({NAMES[piece.piece_type]}) с исходной горизонтали.", 'development'
                elif piece.piece_type == chess.ROOK and not any(
                        position.piece_at(s) and position.piece_at(s).piece_type == chess.PAWN
                        for s in chess.SquareSet(chess.BB_FILES[chess.square_file(candidate.to_square)])):
                    idea, motif = 'Ладья занимает открытую вертикаль: на ней нет пешек обеих сторон.', 'open_file'
                elif piece.piece_type == chess.PAWN and candidate.to_square in (chess.D4, chess.E4, chess.D5, chess.E5):
                    idea, motif = f'Пешка занимает центральную клетку {chess.square_name(candidate.to_square)}.', 'center'
                if idea:
                    recommendation = f"{best['san']}: {idea} Это видимая идея хода; преимущество варианта подтверждает оценка Stockfish."
                    # Confidence in a board fact must not upgrade an unproven explanation of the error.
                    factors.append({'recommended_move_feature': motif, 'square': chess.square_name(candidate.to_square)})
                elif position.is_check():
                    recommendation = f"{best['san']} даёт шах и требует ответа на угрозу королю. Дальнейшая идея видна в показанной линии."
                    motif = 'check'
                    factors.append({'recommended_move_feature': 'check'})
        else:
            chosen = None
    material_delta = notes.get('evidence', [{}])[0].get('played_line_material_change') if notes.get('evidence') else None
    return {'title': TITLES.get(reason_type, 'Изменение оценки'), 'reason': reason,
            'recommendation': recommendation, 'confidence': confidence, 'reason_type': reason_type or 'evaluation_only',
            'idea_confidence': 'medium' if motif in ('development','open_file','center','check') else confidence,
            'detected_motif': motif,
            'material_delta': material_delta, 'chosen_recommendation': chosen,
            'pv': best.get('pv_uci', []) if best else [], 'factors': factors, 'highlights': highlights}
