"""End-to-end smoke scenario used against the packaged executable, not a mock engine."""
from __future__ import annotations

import json
import time
from pathlib import Path

import chess
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent


def attach_smoke(app, window, report_path: Path, resume: bool, complete: bool = False):
    started = time.monotonic()
    state = {"started": False, "player_moves": 0, "initial_plies": 0, "completing": False, "verified_analysis": False}
    timer = QTimer(window)
    timer.setInterval(80)

    def finish(success, message):
        timer.stop()
        report = {"success": success, "message": message, "resume": resume, "completion": complete, "analysis_verified": state["verified_analysis"],
                  "plies": len(window.game.board.move_stack) if window.game else 0,
                  "window_visible": window.isVisible(), "database_created": (window.directory / "chess.sqlite3").is_file(),
                  "settings_created": (window.directory / "settings.json").is_file()}
        # The process must quit and terminate its engine before the external runner accepts the report.
        window.close()
        report["engine_closed"] = window.engine._engine is None
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        app.exit(0 if success else 1)

    def tick():
        try:
            if time.monotonic() - started > 75:
                finish(False, "Timed out waiting for real engine replies")
                return
            if not state["started"]:
                if window.busy:
                    return
                assert window.isVisible()
                if resume or complete:
                    saved = window.store.unfinished()
                    assert saved and len(saved.board.move_stack) >= 6, "Saved game missing"
                    assert window.settings.values["theme"] == "Лес", "Settings did not survive restart"
                    window.resume_game()
                else:
                    window.settings.values["theme"] = "Лес"
                    window.settings.values["sound"] = False
                    window.settings.save()
                    window.apply_settings()
                    window._start_game(chess.WHITE)
                state["started"] = True
                state["initial_plies"] = len(window.game.board.move_stack)
                return
            if window.busy:
                return
            if complete:
                if not state["completing"]:
                    window.session.resign()
                    state["completing"] = True
                    window.advance()
                    return
                if not state["verified_analysis"]:
                    row = window.store.history()[0]
                    assert row["rated"] == 1 and row["analysis"] and row["accuracy"] is not None
                    profile = window.store.profile()
                    assert profile.games == 1 and profile.confidence > 0
                    window.show_analysis(window.game.database_id)
                    window.show_statistics()
                    assert len(window.dialogs) >= 3, "Result, analysis and statistics screens did not open"
                    state["verified_analysis"] = True
                    window._start_game(chess.BLACK)
                    assert window.game.bot_rating == profile.target
                    return
                assert len(window.game.board.move_stack) == 1, "Next adaptive opponent did not play"
                finish(True, "Finished game, real analysis, result/review/statistics screens, atomic rating update and next opponent passed")
                return
            if window.game.result != "*":
                finish(False, "Unexpected early game termination")
                return
            if state["player_moves"] >= (1 if resume else 3):
                assert len(window.game.board.move_stack) >= state["initial_plies"] + 2 * state["player_moves"]
                finish(True, "Board input, legal player moves, real Stockfish replies, autosave, settings and restart passed")
                return
            if window.board.interactive:
                move = next(m for m in window.game.board.legal_moves if not m.promotion)
                for square in [move.from_square, move.to_square]:
                    pos = window.board.square_rect(square).center()
                    press = QMouseEvent(QMouseEvent.MouseButtonPress, pos, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
                    release = QMouseEvent(QMouseEvent.MouseButtonRelease, pos, pos, Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
                    app.sendEvent(window.board, press)
                    app.sendEvent(window.board, release)
                state["player_moves"] += 1
        except Exception as error:
            finish(False, f"{type(error).__name__}: {error}")

    timer.timeout.connect(tick)
    timer.start()
    return timer
