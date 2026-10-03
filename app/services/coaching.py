"""Offline, evidence-based teaching notes. Claims refer to legal engine lines, never speculation."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import chess

from app.services.material import VALUES, captured_piece, material_balance
from app.config.settings import TUNING

PIECES = {chess.PAWN: 'пешку', chess.KNIGHT: 'коня', chess.BISHOP: 'слона', chess.ROOK: 'ладью', chess.QUEEN: 'ферзя'}


@dataclass
class Variation:
    san: str
    uci: str
    evaluation_cp: int | None
    mate: int | None
    mate_winning: bool | None
    pv_uci: list[str]
    pv_san: str
    depth: int

    @classmethod
    def from_info(cls, board, info, color):
        position = board.copy()
        moves, labels = [], []
        for move in info.get('pv', [])[:TUNING['coaching']['pv_plies']]:
            if move not in position.legal_moves:
                break
            prefix = f'{position.fullmove_number}.' if position.turn else f'{position.fullmove_number}…'
            san = position.san(move)
            if position.turn or not labels:
                labels.append(f'{prefix} {san}')
            else:
                labels[-1] += f' {san}'
            moves.append(move.uci())
            position.push(move)
        if not moves:
            return None
        first = chess.Move.from_uci(moves[0])
        score = info['score'].pov(color)
        mate = score.mate()
        return cls(board.san(first), moves[0], score.score(), mate,
                   score.score(mate_score=100000) > 0 if mate is not None else None,
                   moves, '  '.join(labels), info.get('depth', 0))


def format_evaluation(cp, mate=None, mate_winning=None):
    if mate is not None:
        return 'Форсированный мат' if mate_winning else 'Матовая угроза'
    return '—' if cp is None else f'{cp / 100:+.2f}'


def _line_facts(board, moves, color):
    position = board.copy(stack=False)
    lost = []
    for uci in moves:
        move = chess.Move.from_uci(uci)
        if move not in position.legal_moves:
            return None
        piece = captured_piece(position,move)
        if piece and piece.color == color:
            lost.append(piece.piece_type)
        position.push(move)
    return material_balance(position,color),lost,position


def build_coaching(before, move, before_info, after_info, alternatives_info, color):
    after = before.copy(stack=False)
    after.push(move)
    alternatives = []
    for info in alternatives_info:
        line = Variation.from_info(before,info,color)
        if line and line.uci not in [v.uci for v in alternatives]:
            alternatives.append(line)
    response = Variation.from_info(after,after_info,color)
    before_score,after_score = before_info['score'].pov(color),after_info['score'].pov(color)
    before_mate,after_mate = before_score.mate(),after_score.mate()
    before_winning = before_score.score(mate_score=100000) > 0
    after_winning = after_score.score(mate_score=100000) > 0
    preferred = ' или '.join(v.san for v in alternatives[:2]) or before.san(move)
    advice = f'Этот ход ухудшает оценку позиции. Stockfish предпочитает {preferred}. Точную причину по короткой линии надёжно определить не удалось.'
    reason = None
    confidence = 'fallback'
    evidence = []
    if alternatives:
        best = alternatives[0]
        best_position = before.copy(stack=False)
        best_position.push_uci(best.uci)
        if best_position.is_checkmate() and not after.is_checkmate():
            reason,advice,confidence = 'missed_mate',f'Вы могли поставить мат сразу ходом {best.san}.','verified_mate'
        elif before_mate is not None and before_winning and (after_mate is None or not after_winning):
            reason,advice,confidence = 'missed_forced_mate',f'Вы упустили форсированную матовую атаку. Stockfish рекомендует {preferred}.','engine_mate'
        elif after_mate is not None and not after_winning and (before_mate is None or before_winning):
            reason,advice,confidence = 'allowed_mate','Этот ход допускает форсированную матовую последовательность соперника. Сравните её с рекомендуемой защитой.','engine_mate'
        elif before_mate is None and after_mate is None:
            base = material_balance(before,color)
            # Include the played move so exchanges/captures are compared from the same root.
            actual = _line_facts(before,[move.uci()] + (response.pv_uci if response else []),color)
            better = _line_facts(before,best.pv_uci,color)
            if (actual and better and response and len(best.pv_uci) >= 3 and len(response.pv_uci) >= 3
                    and best.evaluation_cp is not None and after_score.score() is not None
                    and best.evaluation_cp - after_score.score() > TUNING['coaching']['min_cpl']):
                actual_delta,better_delta = actual[0]-base,better[0]-base
                evidence = [{'played_line_material_change':actual_delta,'best_line_material_change':better_delta}]
                # Equal exchanges and sacrifices with compensation visible in this line don't claim a loss.
                score_gap = best.evaluation_cp-after_score.score()
                material_gap = max(abs(actual_delta),abs(better_delta-actual_delta))
                supported = score_gap >= material_gap*100*TUNING['coaching']['material_confidence_ratio']
                if supported and actual_delta <= -1 and better_delta > actual_delta and actual[1]:
                    piece = max(actual[1],key=lambda p:VALUES[p])
                    if -actual_delta >= VALUES[piece] > 0:
                        reason = 'pawn_loss' if piece == chess.PAWN else 'material_loss'
                        advice = f'В показанном ответе Stockfish соперник выигрывает {PIECES[piece]}; материальный баланс меняется на {actual_delta:+d}. Сравните с ходом {best.san}.'
                        confidence = 'legal_pv_material'
                elif supported and better_delta >= 1 and better_delta > actual_delta:
                    best_move = chess.Move.from_uci(best.uci)
                    if before.is_capture(best_move) and not before.is_capture(move):
                        reason = 'missed_capture'
                        advice = f'Вы упустили выгодное взятие {best.san}. В показанной линии материальный баланс улучшается на {better_delta:+d}.'
                        confidence = 'legal_pv_material'
                    elif better_delta >= 3:
                        reason = 'missed_material'
                        advice = f'Вместо этого Stockfish предлагает {best.san}: в показанном варианте можно выиграть материал ({better_delta:+d}).'
                        confidence = 'legal_pv_material'
    if confidence == 'fallback':
        # No evidence means no king-safety/pawn-structure stories or guessed tactical labels.
        reason = None
    notes = {'version':2,'root_fen':before.fen(),'played_fen':after.fen(),
            'alternatives':[asdict(v) for v in alternatives],
            'response':asdict(response) if response else None,'reason':reason,'confidence':confidence,
            'advice':advice,'evidence':evidence,'mate_before':before_mate,'mate_after':after_mate,
            'before_cp':before_score.score(),'after_cp':after_score.score(),
            'before_mate_winning':before_winning if before_mate is not None else None,
            'after_mate_winning':after_winning if after_mate is not None else None}
    from app.services.analysis_explainer import explain
    notes['explanation'] = explain(before, move, notes, color)
    return notes
