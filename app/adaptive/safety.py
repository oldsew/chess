"""Small legal exchange checks for obvious queen gifts, not an alternative chess engine."""
import chess

VALUES = {chess.PAWN:1,chess.KNIGHT:3,chess.BISHOP:3,chess.ROOK:5,chess.QUEEN:9,chess.KING:0}


def _recapture_gain(board,square,depth):
    if depth <= 0:
        return 0
    captures = [m for m in board.legal_moves if m.to_square == square and board.is_capture(m)]
    if not captures:
        return 0
    cheapest = min(VALUES[board.piece_type_at(m.from_square)] for m in captures)
    best = 0
    for move in captures:
        if VALUES[board.piece_type_at(move.from_square)] != cheapest:
            continue
        victim = board.piece_at(square)
        gain = VALUES[victim.piece_type] if victim else 1
        if move.promotion:
            gain += VALUES[move.promotion]-1
        position = board.copy(stack=False)
        position.push(move)
        best = max(best,gain-_recapture_gain(position,square,depth-1))
    return best


def exchange_profit(board,move):
    victim = board.piece_at(move.to_square)
    gain = VALUES[victim.piece_type] if victim and board.is_capture(move) else 1 if board.is_en_passant(move) else 0
    if move.promotion:
        gain += VALUES[move.promotion]-1
    position = board.copy(stack=False)
    position.push(move)
    return gain-_recapture_gain(position,move.to_square,4)


def queen_gift(board,move):
    color = board.turn
    victim = board.piece_at(move.to_square)
    immediate_gain = VALUES[victim.piece_type] if victim and board.is_capture(move) else 0
    position = board.copy(stack=False)
    position.push(move)
    for square in position.pieces(chess.QUEEN,color):
        if position.attackers(not color,square) and _recapture_gain(position,square,4)-immediate_gain >= 4:
            return True
    return False


def obvious_queen_capture(board,move):
    victim = board.piece_at(move.to_square)
    return bool(victim and victim.piece_type == chess.QUEEN and victim.color != board.turn
                and board.is_capture(move) and exchange_profit(board,move) >= 4)
