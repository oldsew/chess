from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path

from app.adaptive.metrics import MoveAnalysis, Performance
from app.adaptive.rating import PlayerProfile, RatingEvidence
from app.services.game import GameState

log = logging.getLogger(__name__)


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.executescript('''
        CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS games (
          id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
          player_color INTEGER NOT NULL, result TEXT NOT NULL, rating_before REAL NOT NULL,
          rating_after REAL, bot_rating REAL NOT NULL, pgn TEXT NOT NULL,
          accuracy REAL, average_cpl REAL, inaccuracies INTEGER, mistakes INTEGER, blunders INTEGER,
          duration REAL NOT NULL, analysis TEXT, performance TEXT, score REAL,
          rated INTEGER NOT NULL DEFAULT 0
        );
        ''')
        self.connection.commit()

    def profile(self) -> PlayerProfile:
        row = self.connection.execute("SELECT data FROM profile WHERE id=1").fetchone()
        return PlayerProfile(**json.loads(row[0])) if row else PlayerProfile()

    def save_game(self, game: GameState):
        values = (game.started_at, int(game.player_color), game.result, game.rating_before,
                  game.bot_rating, game.pgn(), game.elapsed_seconds)
        with self.connection:
            if game.database_id is None:
                cursor = self.connection.execute(
                    "INSERT INTO games(timestamp,player_color,result,rating_before,bot_rating,pgn,duration) VALUES(?,?,?,?,?,?,?)", values)
                game.database_id = cursor.lastrowid
            else:
                self.connection.execute(
                    "UPDATE games SET timestamp=?,player_color=?,result=?,rating_before=?,bot_rating=?,pgn=?,duration=? WHERE id=?",
                    (*values, game.database_id))

    def load_game(self, game_id: int) -> GameState:
        row = self.connection.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
        if not row:
            raise ValueError("Партия не найдена")
        return GameState.from_pgn(row["pgn"], player_color=bool(row["player_color"]),
                                  bot_rating=row["bot_rating"], rating_before=row["rating_before"],
                                  started_at=row["timestamp"], elapsed_seconds=row["duration"], database_id=row["id"])

    def unfinished(self) -> GameState | None:
        row = self.connection.execute("SELECT id FROM games WHERE result='*' ORDER BY id DESC LIMIT 1").fetchone()
        return self.load_game(row[0]) if row else None

    def pending_analysis(self) -> int | None:
        row = self.connection.execute("SELECT id FROM games WHERE result!='*' AND rated=0 ORDER BY id LIMIT 1").fetchone()
        return row[0] if row else None

    def history(self) -> list[dict]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM games ORDER BY id DESC")]

    def evidence(self) -> list[RatingEvidence]:
        rows = self.connection.execute("SELECT performance,score FROM games WHERE rated=1 ORDER BY id DESC LIMIT 10").fetchall()
        return [RatingEvidence.create(row["score"], Performance(**json.loads(row["performance"]))) for row in reversed(rows)]

    def finish_analysis(self, game: GameState, moves: list[MoveAnalysis], metrics: Performance,
                        profile: PlayerProfile) -> bool:
        # Analysis and rating are committed atomically, preventing double updates after a crash/retry.
        with self.connection:
            row = self.connection.execute("SELECT rated FROM games WHERE id=?", (game.database_id,)).fetchone()
            if row is None:
                raise ValueError("Game was not saved")
            if row[0]:
                return False
            self.connection.execute('''UPDATE games SET rating_after=?,accuracy=?,average_cpl=?,inaccuracies=?,
                mistakes=?,blunders=?,analysis=?,performance=?,score=?,rated=1 WHERE id=?''',
                (profile.rating, metrics.accuracy, metrics.average_cpl, metrics.inaccuracies, metrics.mistakes,
                 metrics.blunders, json.dumps([asdict(m) for m in moves], ensure_ascii=False),
                 json.dumps(metrics.as_dict()), game.player_score(), game.database_id))
            self.connection.execute("INSERT OR REPLACE INTO profile(id,data) VALUES(1,?)", (json.dumps(asdict(profile)),))
        log.info("Rating %.1f -> %.1f", game.rating_before, profile.rating)
        return True

    def close(self):
        self.connection.close()
