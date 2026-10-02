from __future__ import annotations

import json
import logging
import random
from pathlib import Path

import chess
from PySide6.QtCore import QThreadPool, QTimer, Qt, Slot
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout, QInputDialog,
    QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from app.config.settings import Settings
from app.database.store import Store
from app.services.engine import EngineService
from app.services.session import Session
from app.ui.board import ChessBoard
from app.ui.dialogs import AnalysisDialog, SettingsDialog, StatisticsDialog
from app.ui.workers import Worker

log = logging.getLogger(__name__)
STYLE = """
QWidget { background: #171e29; color: #e6ecf4; font-family: 'Segoe UI'; font-size: 14px; }
QLabel#title { font-size: 25px; font-weight: 600; }
QLabel#subtitle { color: #9daabd; }
QPushButton { background: #293647; border: 1px solid #39495f; padding: 10px 16px; border-radius: 6px; }
QPushButton:hover { background: #36485e; }
QPushButton:disabled { color: #657388; background: #202a38; }
QPushButton#primary { background: #287d74; border-color: #41a99b; }
QComboBox, QSpinBox { padding: 7px; background: #293647; border: 1px solid #39495f; }
QListWidget, QTextEdit, QTableWidget { background: #1e2836; border: 1px solid #334154; padding: 5px; }
QHeaderView::section { background: #293647; padding: 6px; border: 1px solid #39495f; }
QSplitter::handle { background: #171e29; }
"""


class MainWindow(QMainWindow):
    def __init__(self, directory: Path, engine: EngineService | None = None):
        super().__init__()
        self.setWindowTitle("Adaptive Chess")
        self.resize(1080, 790)
        self.directory = directory
        self.settings = Settings(directory)
        self.store = Store(directory / "chess.sqlite3")
        self.session = Session(self.store)
        self.engine = engine or EngineService()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.busy = False
        self.closing = False
        self.token = 0
        self.worker = None
        self.analysis_game = None
        self.last_selection = None
        self.dialogs = []
        self.setStyleSheet(STYLE)
        self._build_ui()
        self.apply_settings()
        self.refresh()
        QTimer.singleShot(0, self.recover_pending)

    @property
    def game(self):
        return self.session.game

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("Adaptive Chess")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("Чуть сильнее. С каждой партией ближе.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        menu = QHBoxLayout()
        self.new_button = QPushButton("Новая партия")
        self.new_button.setObjectName("primary")
        self.new_button.clicked.connect(self.new_game)
        self.resume_button = QPushButton("Продолжить")
        self.resume_button.clicked.connect(self.resume_game)
        self.history_button = QPushButton("История партий")
        self.history_button.clicked.connect(self.show_history)
        self.stats_button = QPushButton("Статистика")
        self.stats_button.clicked.connect(self.show_statistics)
        self.settings_button = QPushButton("Настройки")
        self.settings_button.clicked.connect(self.show_settings)
        for button in [self.new_button, self.resume_button, self.history_button, self.stats_button, self.settings_button]:
            menu.addWidget(button)
        menu.addStretch()
        layout.addLayout(menu)
        splitter = QSplitter()
        self.board = ChessBoard()
        self.board.move_requested.connect(self.human_move)
        splitter.addWidget(self.board)
        side = QWidget()
        side.setMinimumWidth(250)
        side.setMaximumWidth(340)
        side_layout = QVBoxLayout(side)
        self.status_label = QLabel("Начните первую партию")
        self.status_label.setWordWrap(True)
        side_layout.addWidget(self.status_label)
        side_layout.addWidget(QLabel("Мой цвет"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Белые", "Чёрные", "Случайно"])
        side_layout.addWidget(self.color_combo)
        side_layout.addWidget(QLabel("Ходы партии"))
        self.move_list = QListWidget()
        side_layout.addWidget(self.move_list, 1)
        self.save_button = QPushButton("Сохранить партию")
        self.save_button.clicked.connect(self.save_game)
        side_layout.addWidget(self.save_button)
        self.resign_button = QPushButton("Сдаться")
        self.resign_button.clicked.connect(self.resign)
        side_layout.addWidget(self.resign_button)
        self.retry_button = QPushButton("Повторить операцию")
        self.retry_button.clicked.connect(self.retry)
        self.retry_button.hide()
        side_layout.addWidget(self.retry_button)
        self.debug = QTextEdit()
        self.debug.setReadOnly(True)
        self.debug.setMaximumHeight(220)
        side_layout.addWidget(self.debug)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        layout.addWidget(splitter, 1)
        self.footer = QLabel("Сложность подстраивается автоматически. Первые партии — калибровка.")
        self.footer.setObjectName("subtitle")
        layout.addWidget(self.footer)

    def apply_settings(self):
        values = self.settings.values
        self.board.theme = values["theme"]
        self.board.highlight_legal = values["legal_highlights"]
        self.color_combo.setCurrentText(values["player_color"])
        self.debug.setVisible(values["developer_mode"])
        self.board.update()

    def _present(self, dialog):
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        self.dialogs.append(dialog)
        dialog.destroyed.connect(lambda: self.dialogs.remove(dialog) if dialog in self.dialogs else None)
        dialog.show()

    def refresh(self):
        active = self.game is not None and self.game.result == "*"
        self.board.interactive = active and not self.busy and self.game.board.turn == self.game.player_color
        self.new_button.setEnabled(not self.busy)
        self.resume_button.setEnabled(not self.busy and self.store.unfinished() is not None)
        self.resign_button.setEnabled(active and not self.busy)
        self.save_button.setEnabled(active)
        self.color_combo.setEnabled(not self.busy)
        if self.game:
            self.board.player_color = self.game.player_color
            self.board.orientation = self.game.player_color
            self.board.set_position(self.game.board)
            board = self.game.board.root()
            lines = []
            for move in self.game.board.move_stack:
                san = board.san(move)
                if board.turn:
                    lines.append(f"{board.fullmove_number}.  {san}")
                elif lines:
                    lines[-1] += f"    {san}"
                else:
                    lines.append(f"{board.fullmove_number}...  {san}")
                board.push(move)
            self.move_list.clear()
            self.move_list.addItems(lines)
            self.move_list.scrollToBottom()
            if not self.busy:
                if active:
                    self.status_label.setText(("Ваш ход" if self.game.board.turn == self.game.player_color else "Ход компьютера") +
                                              (" · Шах" if self.game.board.is_check() else ""))
                else:
                    self.status_label.setText(f"Партия завершена: {self.game.result}")
        self.update_debug()

    def update_debug(self):
        if not self.settings.values["developer_mode"]:
            return
        profile = self.store.profile()
        data = {"player_rating": profile.rating, "rating_confidence": profile.confidence,
                "target_bot_rating": self.game.bot_rating if self.game else profile.target,
                "difficulty_offset": profile.offset, "Stockfish": {"Threads": 1, "Hash": 64, "MultiPV": 8}}
        if self.last_selection:
            data.update({"profile": self.last_selection.profile, "candidates": self.last_selection.candidates,
                         "chosen": self.last_selection.move.uci(), "complexity": self.last_selection.complexity})
        self.debug.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))

    @Slot()
    def new_game(self):
        if self.busy:
            return
        if self.game and self.game.result == "*" and self.game.board.move_stack:
            if QMessageBox.question(self, "Новая партия", "Текущая партия сохранена. Начать новую?") != QMessageBox.Yes:
                return
        self._start_game()

    def _start_game(self, color=None):
        if color is None:
            selected = self.color_combo.currentText()
            color = chess.WHITE if selected == "Белые" else chess.BLACK if selected == "Чёрные" else random.choice([True, False])
        self.session.start(color)
        self.last_selection = None
        self.retry_button.hide()
        self.refresh()
        self.advance()

    @Slot()
    def resume_game(self):
        if self.busy:
            return
        try:
            game = self.store.unfinished()
            if game:
                self.session.resume(game)
                self.refresh()
                self.advance()
        except Exception as error:
            self.show_error(str(error))

    @Slot(int, int)
    def human_move(self, origin, target):
        if not self.board.interactive or not self.game:
            return
        moves = [m for m in self.game.board.legal_moves if m.from_square == origin and m.to_square == target]
        if not moves:
            return
        if len(moves) > 1:
            options = {"Ферзь": chess.QUEEN, "Ладья": chess.ROOK, "Слон": chess.BISHOP, "Конь": chess.KNIGHT}
            name, ok = QInputDialog.getItem(self, "Превращение пешки", "Выберите фигуру", list(options), 0, False)
            if not ok:
                return
            move = next(m for m in moves if m.promotion == options[name])
        else:
            move = moves[0]
        self.commit_move(move)

    def commit_move(self, move):
        try:
            self.session.play(move)
            if self.settings.values["sound"]:
                QApplication.beep()
            self.refresh()
            self.advance()
        except Exception as error:
            log.exception("Move/save failed")
            self.show_error(str(error))

    def advance(self):
        if not self.game or self.busy or self.closing:
            return
        if self.game.result != "*":
            self.start_analysis(self.game)
        elif self.game.board.turn != self.game.player_color:
            position, rating = self.game.board.copy(), self.game.bot_rating
            self.submit("move", lambda progress: self.engine.choose(position, rating))

    def submit(self, kind, function):
        self.busy = True
        self.token += 1
        self.status_label.setText("Компьютер думает…" if kind == "move" else "Анализ партии…")
        self.retry_button.hide()
        self.worker = Worker(self.token, kind, function)
        self.worker.signals.result.connect(self.on_result)
        self.worker.signals.error.connect(self.on_error)
        self.worker.signals.progress.connect(self.on_progress)
        self.refresh()
        self.pool.start(self.worker)

    def start_analysis(self, game):
        row = next(g for g in self.store.history() if g["id"] == game.database_id)
        if row["rated"]:
            return
        self.analysis_game = game
        position = game.board.copy()
        color = game.player_color
        depth = self.settings.values["analysis_depth"]
        self.submit("analysis", lambda progress: self.engine.analyse_game(position, color, depth, progress))

    @Slot(int, str, object)
    def on_result(self, token, kind, value):
        if token != self.token or self.closing:
            return
        self.busy = False
        if kind == "move":
            self.last_selection = value
            self.commit_move(value.move)
        else:
            try:
                moves, metrics = value
                profile = self.session.complete(self.analysis_game, moves, metrics)
                self.refresh()
                self.show_result(self.analysis_game, profile, metrics)
            except Exception as error:
                log.exception("Analysis persistence failed")
                self.show_error(str(error))
                self.retry_button.show()

    @Slot(int, str, str)
    def on_error(self, token, kind, message):
        if token != self.token or self.closing:
            return
        self.busy = False
        self.refresh()
        self.status_label.setText("Не удалось выполнить операцию. Партию можно продолжить.")
        self.retry_button.show()
        self.show_error(message)

    @Slot(int, int)
    def on_progress(self, done, total):
        if not self.closing:
            self.status_label.setText(f"Анализ партии: {done} / {total}")

    def show_error(self, message):
        dialog = QMessageBox(QMessageBox.Warning, "Adaptive Chess", message, QMessageBox.Ok, self)
        self._present(dialog)

    def retry(self):
        if self.busy:
            return
        self.engine.cancelled.clear()
        if self.game and self.game.result == "*":
            self.advance()
        elif self.analysis_game:
            self.start_analysis(self.analysis_game)
        else:
            self.recover_pending()

    def recover_pending(self):
        if self.busy or self.closing:
            return
        pending = self.store.pending_analysis()
        if pending:
            try:
                self.start_analysis(self.store.load_game(pending))
            except Exception as error:
                self.show_error(str(error))

    def show_result(self, game, profile, metrics):
        score = game.player_score()
        result = "Победа" if score == 1 else "Ничья" if score == 0.5 else "Поражение"
        dialog = QDialog(self)
        dialog.setWindowTitle("Результат партии")
        dialog.resize(440, 460)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(result))
        text = (f"Ваш уровень до партии: {game.rating_before:.0f}\n"
                f"Точность: {metrics.accuracy:.1f}%\nСредняя потеря: {metrics.average_cpl:.1f} cp\n\n"
                f"Отличных: {metrics.excellent} · Хороших: {metrics.good}\n"
                f"Неточностей: {metrics.inaccuracies}\nОшибок: {metrics.mistakes}\nГрубых ошибок: {metrics.blunders}\n\n"
                f"Изменение уровня: {profile.rating - game.rating_before:+.0f}\nНовый уровень: {profile.rating:.0f}")
        if self.settings.values["show_bot_rating"]:
            text += f"\nСоперник: {game.bot_rating:.0f}\nСледующий соперник: ≈{profile.target:.0f}"
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        button = QPushButton("Разобрать партию")
        button.clicked.connect(lambda: self.show_analysis(game.database_id))
        layout.addWidget(button)
        self._present(dialog)

    def resign(self):
        if self.game and not self.busy and self.game.result == "*":
            if QMessageBox.question(self, "Завершить партию", "Вы хотите сдаться?") == QMessageBox.Yes:
                self.session.resign()
                self.refresh()
                self.advance()

    def save_game(self):
        try:
            self.session.save()
            self.footer.setText("Партия сохранена. После каждого хода также работает автосохранение.")
        except Exception as error:
            log.exception("Database save failed")
            self.show_error(str(error))

    def show_settings(self):
        dialog = SettingsDialog(self.settings.values, self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.settings.values = dialog.values()
                self.settings.save()
                self.apply_settings()
                self.update_debug()
            except OSError as error:
                self.show_error(str(error))

    def show_statistics(self):
        self._present(StatisticsDialog(self.store.profile(), self.store.history(), self))

    def show_analysis(self, game_id):
        row = next(g for g in self.store.history() if g["id"] == game_id)
        if row["rated"]:
            self._present(AnalysisDialog(row, self))
        elif row["result"] != "*" and not self.busy:
            self.start_analysis(self.store.load_game(game_id))

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("История партий · двойной щелчок для разбора")
        dialog.resize(850, 430)
        layout = QVBoxLayout(dialog)
        games = self.store.history()
        table = QTableWidget(len(games), 8)
        table.setHorizontalHeaderLabels(["Дата", "Цвет", "Результат", "До", "После", "Соперник", "Точность", "Время"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        for i, game in enumerate(games):
            values = [game["timestamp"][:16].replace("T", " "), "Белые" if game["player_color"] else "Чёрные",
                      game["result"], f"{game['rating_before']:.0f}", f"{game['rating_after']:.0f}" if game["rated"] else "—",
                      f"{game['bot_rating']:.0f}", f"{game['accuracy']:.1f}%" if game["rated"] else "—", f"{game['duration'] / 60:.1f} мин"]
            for j, value in enumerate(values):
                table.setItem(i, j, QTableWidgetItem(value))
        table.cellDoubleClicked.connect(lambda row, col: self.show_analysis(games[row]["id"]))
        layout.addWidget(table)
        self._present(dialog)

    def closeEvent(self, event):
        self.closing = True
        self.engine.cancelled.set()
        self.pool.waitForDone()
        self.engine.close()
        try:
            self.session.save()
            self.settings.save()
        except Exception:
            log.exception("Shutdown save failed")
        self.store.close()
        for dialog in list(self.dialogs):
            dialog.close()
        event.accept()
