from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path

import chess
import chess.engine

from app.adaptive.metrics import MoveAnalysis, Performance, centipawn_loss, classify, score_cp
from app.adaptive.selector import BehaviorProfile, Candidate, Selection, select_move
from app.config.settings import TUNING, engine_path
from app.config.gameplay import GAMEPLAY
from app.services.live import LiveEvaluation
from app.services.coaching import build_coaching

log = logging.getLogger(__name__)


class EngineService:
    """One serialized UCI process. All calls are executed by a background worker."""
    def __init__(self, path: Path | None = None):
        self.path = path or engine_path()
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.RLock()
        self.cancelled = threading.Event()

    def _get(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            if not self.path.is_file():
                raise FileNotFoundError("Stockfish не найден. Используйте полный portable-пакет приложения.")
            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}
            self._engine = chess.engine.SimpleEngine.popen_uci(str(self.path), timeout=15, **kwargs)
            self._engine.configure({"Threads": 1, "Hash": 64})
            log.info("Stockfish started: %s", self._engine.id.get("name"))
        return self._engine

    def _configure(self, options):
        try:
            self._get().configure(options)
        except (chess.engine.EngineError, TimeoutError):
            log.exception("Stockfish configuration failed; restarting once")
            self._stop()
            self._get().configure(options)

    def _analyse(self, board, limit, **kwargs):
        try:
            return self._get().analyse(board, limit, **kwargs)
        except (chess.engine.EngineError, TimeoutError):
            log.exception("Stockfish failed; restarting once")
            self._stop()
            return self._get().analyse(board, limit, **kwargs)

    def choose(self, board: chess.Board, rating: float, natural_delay=True, on_evaluation=None) -> Selection:
        with self._lock:
            started = time.monotonic()
            profile = BehaviorProfile.for_rating(rating)
            self._configure({"Skill Level": profile.skill_level, "UCI_LimitStrength": False})
            infos = self._analyse(board, chess.engine.Limit(time=profile.search_time),
                                  multipv=min(profile.multipv, board.legal_moves.count()))
            if on_evaluation and infos:
                on_evaluation(LiveEvaluation.from_info(board, infos[0]))
            candidates = [Candidate(info["pv"][0], score_cp(info["score"], board.turn),
                                    info["score"].pov(board.turn).mate()) for info in infos if info.get("pv")]
            selected = select_move(board, candidates, rating)
            selected.profile['actual_multipv'] = len(infos)
            selected.profile['search_depth'] = infos[0].get('depth',0) if infos else 0
            if natural_delay:
                self.cancelled.wait(max(0, selected.delay - (time.monotonic() - started)))
            if self.cancelled.is_set():
                raise InterruptedError("Операция отменена")
            return selected

    def evaluate_live(self, board: chess.Board) -> LiveEvaluation:
        with self._lock:
            if self.cancelled.is_set():
                raise InterruptedError('Оценка отменена')
            self._configure({"Skill Level": 20, "UCI_LimitStrength": False})
            cfg = GAMEPLAY['position_indicator']
            info = self._analyse(board, chess.engine.Limit(depth=cfg['depth'], time=cfg['time_limit']))
            return LiveEvaluation.from_info(board, info)

    def analyse_game(self, final_board: chess.Board, player_color: bool, depth: int,
                     progress=None) -> tuple[list[MoveAnalysis], Performance]:
        with self._lock:
            self._configure({"Skill Level": 20, "UCI_LimitStrength": False})
            board = final_board.root()
            results = []
            for ply, move in enumerate(final_board.move_stack, 1):
                if self.cancelled.is_set():
                    raise InterruptedError("Анализ отменён")
                if board.turn == player_color:
                    limit = chess.engine.Limit(depth=depth, time=TUNING["analysis_time"])
                    before = self._analyse(board, limit)
                    san = board.san(move)
                    best = board.san(before["pv"][0])
                    before_cp = score_cp(before["score"], player_color)
                    before_label = str(before["score"].pov(player_color))
                    root = board.copy()
                    board.push(move)
                    after = self._analyse(board, limit)
                    after_cp = score_cp(after["score"], player_color)
                    loss = centipawn_loss(before_cp, after_cp)
                    coaching = None
                    # Keep the base analysis/rating metrics unchanged; extend only teachable errors.
                    best_position = root.copy(stack=False)
                    best_position.push(before["pv"][0])
                    if loss > TUNING['coaching']['min_cpl'] or (best_position.is_checkmate() and not board.is_checkmate()):
                        if self.cancelled.is_set():
                            raise InterruptedError("Анализ отменён")
                        cfg = TUNING['coaching']
                        alternatives = self._analyse(root, chess.engine.Limit(depth=min(22, depth + cfg['extra_depth']), time=cfg['time_limit']),
                                                     multipv=min(cfg['multipv'],root.legal_moves.count()))
                        coaching = build_coaching(root,move,before,after,alternatives,player_color)
                    results.append(MoveAnalysis(ply, san, best, before_cp, after_cp, loss, classify(loss),
                                                before_label, str(after["score"].pov(player_color)),coaching))
                else:
                    board.push(move)
                if progress:
                    progress(ply, len(final_board.move_stack))
            return results, Performance.from_moves(results)

    def _stop(self):
        if self._engine:
            try:
                self._engine.quit()
            except Exception:
                self._engine.close()
            self._engine = None

    def close(self):
        self.cancelled.set()
        with self._lock:
            self._stop()
        log.info("Stockfish stopped")
