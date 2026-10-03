from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path

import chess
from PySide6.QtCore import QThreadPool, QTimer, Qt, Slot
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QInputDialog,
    QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QListWidgetItem)

from app.config.settings import Settings
from app.database.store import Store
from app.services.engine import EngineService
from app.services.session import Session
from app.ui.board import ChessBoard
from app.ui.dialogs import AnalysisDialog, SettingsDialog, StatisticsDialog
from app.ui.workers import Worker
from app.ui.sounds import SoundPlayer, move_cue
from app.services.clocks import TIME_CONTROLS, time_control
from app.services.live import PositionIndicator
from app.config.gameplay import GAMEPLAY
from app.ui.navigation import PositionNavigator
from app.ui.clocks import ClockPanel
from app.ui.motion import system_motion_enabled

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
QFrame#clockPanel { background: #202c3a; border: 1px solid #35455a; border-radius: 7px; }
QFrame#clockPanel[active="true"] { background: #243e40; border-color: #60b6a8; }
QLabel#clockOwner { color: #aebccd; font-size: 12px; background: transparent; }
QLabel#clockTime { font-size: 25px; font-weight: 600; background: transparent; }
QLabel#positionIndicator { color: #bdd5ce; padding: 7px 0; font-size: 13px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, directory: Path, engine: EngineService | None = None):
        super().__init__()
        self.setWindowTitle("Adaptive Chess")
        self.resize(1080, 750)
        self.directory = directory
        self.settings = Settings(directory)
        self.sounds = SoundPlayer(self)
        self.store = Store(directory / "chess.sqlite3")
        self.session = Session(self.store)
        self.navigator = PositionNavigator()
        self.indicator = PositionIndicator()
        self._pending_result = None
        self._end_notified = None
        self._last_clock_save = time.monotonic()
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
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(GAMEPLAY['clock_refresh_ms'])
        self.clock_timer.timeout.connect(self.tick_clocks)
        self.clock_timer.start()
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
        self.board.previous_requested.connect(self.previous_position)
        self.board.next_requested.connect(self.next_position)
        self.board.presentation_finished.connect(self.presentation_finished)
        splitter.addWidget(self.board)
        side = QWidget()
        side.setMinimumWidth(250)
        side.setMaximumWidth(340)
        side_layout = QVBoxLayout(side)
        self.status_label = QLabel("Начните первую партию")
        self.status_label.setWordWrap(True)
        side_layout.addWidget(self.status_label)
        self.bot_clock = ClockPanel('Компьютер')
        self.player_clock = ClockPanel('Вы')
        side_layout.addWidget(self.bot_clock)
        side_layout.addWidget(self.player_clock)
        self.position_label = QLabel(self.indicator.text)
        self.position_label.setObjectName('positionIndicator')
        self.position_label.setWordWrap(True)
        side_layout.addWidget(self.position_label)
        side_layout.addWidget(QLabel('Новая партия · цвет и время'))
        self.color_combo = QComboBox()
        self.color_combo.setAccessibleName('Цвет для новой партии')
        self.color_combo.addItems(["Белые", "Чёрные", "Случайно"])
        side_layout.addWidget(self.color_combo)
        self.time_combo = QComboBox()
        self.time_combo.setAccessibleName('Контроль времени для новой партии')
        for control in TIME_CONTROLS:
            self.time_combo.addItem(control.label, control.key)
        self.time_combo.currentIndexChanged.connect(self.select_time_control)
        side_layout.addWidget(self.time_combo)
        self.control_label = QLabel('Без времени')
        self.control_label.setObjectName('subtitle')
        side_layout.addWidget(self.control_label)
        side_layout.addWidget(QLabel("Ходы партии"))
        self.move_list = QListWidget()
        self.move_list.itemClicked.connect(self.select_position)
        side_layout.addWidget(self.move_list, 1)
        navigation = QHBoxLayout()
        self.previous_button = QPushButton('←')
        self.previous_button.setToolTip('Предыдущий ход (Left на доске)')
        self.previous_button.clicked.connect(self.previous_position)
        self.next_button = QPushButton('→')
        self.next_button.setToolTip('Следующий ход (Right на доске)')
        self.next_button.clicked.connect(self.next_position)
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.next_button)
        side_layout.addLayout(navigation)
        self.current_button = QPushButton('К текущей позиции')
        self.current_button.clicked.connect(self.current_position)
        side_layout.addWidget(self.current_button)
        actions = QHBoxLayout()
        self.save_button = QPushButton("Сохранить")
        self.save_button.setToolTip('Сохранить текущую партию и часы')
        self.save_button.clicked.connect(self.save_game)
        actions.addWidget(self.save_button)
        self.resign_button = QPushButton("Сдаться")
        self.resign_button.clicked.connect(self.resign)
        actions.addWidget(self.resign_button)
        side_layout.addLayout(actions)
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
        self.sounds.set_enabled(values["sound"])
        self.board.animations_enabled = values['animations'] and system_motion_enabled()
        self.board.theme = values["theme"]
        self.board.highlight_legal = values["legal_highlights"]
        self.color_combo.setCurrentText(values["player_color"])
        self.time_combo.setCurrentIndex(max(0, self.time_combo.findData(values['time_control'])))
        self.debug.setVisible(values["developer_mode"])
        self.board.update()

    def _present(self, dialog):
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        self.dialogs.append(dialog)
        dialog.destroyed.connect(lambda: self.dialogs.remove(dialog) if dialog in self.dialogs else None)
        dialog.show()

    def select_time_control(self):
        self.settings.values['time_control'] = self.time_combo.currentData()
        self.update_clocks()

    def update_clocks(self):
        clock = self.session.clock
        color = self.game.player_color if self.game else self.color_combo.currentText() != 'Чёрные'
        control = self.game.time_control if self.game else time_control(self.time_combo.currentData())
        active = self.game and self.game.result == '*' and clock and clock.running
        own = clock.remaining(color) if clock else control.initial_seconds
        bot = clock.remaining(not color) if clock else control.initial_seconds
        self.player_clock.show_clock('Вы · ' + ('Белые' if color else 'Чёрные'), own, bool(active and clock.active == color))
        self.bot_clock.show_clock('Компьютер · ' + ('Чёрные' if color else 'Белые'), bot, bool(active and clock.active != color))
        self.control_label.setText(control.short_label)

    def tick_clocks(self):
        if self.closing:
            return
        if self.game:
            expired = self.session.check_timeout()
            if expired or (self.game.termination == 'timeout' and self.game.result != '*' and self._end_notified != self.game.database_id):
                self.handle_timeout()
            if self.game.result == '*' and self.game.time_control.timed and time.monotonic() - self._last_clock_save >= GAMEPLAY['clock_autosave_seconds']:
                self.session.save()
                self._last_clock_save = time.monotonic()
        self.update_clocks()

    def refresh(self, *, animate_move=False):
        active = self.game is not None and self.game.result == '*'
        viewing = self.navigator.viewing
        end_effect = self.board.presenting_end
        self.board.interactive = bool(active and not self.busy and not viewing and self.game.board.turn == self.game.player_color)
        self.new_button.setEnabled(not self.busy and not end_effect)
        self.resume_button.setEnabled(not self.busy and not end_effect and self.store.unfinished() is not None)
        self.resign_button.setEnabled(active and not self.busy and not viewing)
        self.save_button.setEnabled(active)
        self.color_combo.setEnabled(not self.busy)
        self.time_combo.setEnabled(not self.busy)
        total = len(self.game.board.move_stack) if self.game else 0
        ply = self.navigator.ply if viewing else total
        self.previous_button.setEnabled(ply > 0 and not end_effect)
        self.next_button.setEnabled(viewing and not end_effect)
        self.current_button.setEnabled(viewing and not end_effect)
        self.position_label.setVisible(not viewing)
        self.position_label.setText(self.indicator.text if active else 'Партия завершена' if self.game else self.indicator.text)
        if self.game:
            self.board.player_color = self.game.player_color
            self.board.orientation = self.game.player_color
            self.board.set_position(self.navigator.position(self.game.board), animate=animate_move and not viewing)
            position = self.game.board.root()
            self.move_list.blockSignals(True)
            self.move_list.clear()
            for index, move in enumerate(self.game.board.move_stack, 1):
                prefix = f'{position.fullmove_number}.' if position.turn else f'{position.fullmove_number}…'
                item = QListWidgetItem(f'{prefix}  {position.san(move)}')
                item.setData(Qt.UserRole, index)
                self.move_list.addItem(item)
                position.push(move)
            self.move_list.setCurrentRow(ply - 1)
            self.move_list.blockSignals(False)
            if not viewing:
                self.move_list.scrollToBottom()
            if viewing:
                description = 'начальная позиция' if ply == 0 else f'ход {(ply + 1) // 2}' + ('…' if ply % 2 == 0 else '') + f' из {(total + 1) // 2}'
                self.status_label.setText('Просмотр партии — ' + description)
            elif not self.busy:
                if active:
                    self.status_label.setText(('Ваш ход' if self.game.board.turn == self.game.player_color else 'Ход компьютера') +
                                              (' · Шах' if self.game.board.is_check() else ''))
                else:
                    self.status_label.setText(self.result_title(self.game))
        self.update_clocks()
        self.update_debug()

    def previous_position(self):
        if self.game and not self.board.presenting_end:
            self.navigator.back(self.game.board)
            self.refresh()
            self.board.setFocus()

    def next_position(self):
        if self.game and not self.board.presenting_end:
            self.navigator.forward(self.game.board)
            self.refresh()
            self.board.setFocus()

    def current_position(self):
        self.navigator.current()
        self.refresh()
        self.board.setFocus()

    def select_position(self, item):
        if self.game and not self.board.presenting_end:
            self.navigator.select(item.data(Qt.UserRole), self.game.board)
            self.refresh()
            self.board.setFocus()

    def invalidate_worker(self):
        self.token += 1
        if self.worker:
            self.worker.cancelled.set()
        self.engine.cancelled.set()

    def handle_timeout(self):
        if self._end_notified == self.game.database_id:
            return
        self._end_notified = self.game.database_id
        self.invalidate_worker()
        self.busy = False
        self.navigator.current()
        self.sounds.set_enabled(self.settings.values['sound'])
        self.sounds.play('end')
        self.refresh()
        self.advance()

    def result_title(self, game):
        score = game.player_score()
        if game.termination == 'timeout':
            return 'Ничья по времени · недостаточно материала' if score == .5 else 'Победа по времени' if score == 1 else 'Поражение по времени'
        if game.termination == 'checkmate':
            return 'Победа · Мат' if score == 1 else 'Поражение · Мат'
        return 'Победа' if score == 1 else 'Ничья' if score == .5 else 'Поражение'

    def update_debug(self):
        if not self.settings.values["developer_mode"]:
            return
        profile = self.store.profile()
        data = {"player_rating": profile.rating, "rating_confidence": profile.confidence,
                "target_bot_rating": self.game.bot_rating if self.game else profile.target,
                "difficulty_offset": profile.offset, "Stockfish": {"Threads": 1, "Hash": 64, "MultiPV": 8}}
        data["position_indicator"] = self.indicator.debug
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
        if self.session.check_timeout():
            self.handle_timeout()
            return
        self.invalidate_worker()
        self.navigator.current()
        self.indicator = PositionIndicator()
        self._pending_result = None
        self._end_notified = None
        self.session.start(color, time_control(self.time_combo.currentData()))
        self.settings.values['time_control'] = self.time_combo.currentData()
        self.settings.save()
        self.last_selection = None
        self.retry_button.hide()
        self.refresh()
        self.advance()

    @Slot()
    def resume_game(self):
        if self.busy:
            return
        try:
            if self.session.check_timeout():
                self.handle_timeout()
                return
            game = self.store.unfinished()
            if game:
                self.invalidate_worker()
                self.navigator.current()
                self.indicator = PositionIndicator()
                self._pending_result = None
                self._end_notified = None
                self.session.resume(game)
                self.refresh()
                self.advance()
        except Exception as error:
            self.show_error(str(error))

    @Slot(int, int)
    def human_move(self, origin, target):
        if not self.board.interactive or not self.game or self.navigator.viewing:
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
            before = self.game.board.copy(stack=False)
            if not self.session.play(move):
                self.handle_timeout()
                return
            self.invalidate_worker()
            if self.game.result != '*':
                self._end_notified = self.game.database_id
                self.navigator.current()
            self.sounds.set_enabled(self.settings.values["sound"])
            self.sounds.play(move_cue(before, self.game.board, move, self.game.result))
            self.refresh(animate_move=True)
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
            self.submit('move', lambda progress, live: self.engine.choose(position, rating, on_evaluation=live), report_live=True)
        else:
            position = self.game.board.copy()
            self.submit('live', lambda progress: self.engine.evaluate_live(position))

    def submit(self, kind, function, *, report_live=False):
        if self.worker:
            self.worker.cancelled.set()
        self.busy = kind != 'live'
        self.token += 1
        if kind != 'live':
            self.status_label.setText('Компьютер думает…' if kind == 'move' else 'Анализ партии…')
            self.retry_button.hide()
        def perform(progress, live=None):
            self.engine.cancelled.clear()
            return function(progress, live) if report_live else function(progress)
        self.worker = Worker(self.token, kind, perform, report_live)
        self.worker.signals.result.connect(self.on_result)
        self.worker.signals.error.connect(self.on_error)
        self.worker.signals.progress.connect(self.on_progress)
        self.worker.signals.live.connect(self.on_live)
        self.refresh()
        self.pool.start(self.worker)

    @Slot(int, object)
    def on_live(self, token, value):
        if token != self.token or self.closing or not self.game or self.game.result != '*' or value.fen != self.game.board.fen():
            return
        self.indicator.update(value, self.game.player_color)
        if not self.navigator.viewing:
            self.position_label.setText(self.indicator.text)
        self.update_debug()

    def presentation_finished(self):
        if self.closing:
            return
        self.refresh()
        if self._pending_result:
            game, profile, metrics = self._pending_result
            self._pending_result = None
            self.show_result(game, profile, metrics)

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
        if kind == 'live':
            self.on_live(token, value)
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
                if self.game and self.analysis_game.database_id == self.game.database_id and (self.board.animating or self.board.presenting_end):
                    self._pending_result = (self.analysis_game, profile, metrics)
                else:
                    self.show_result(self.analysis_game, profile, metrics)
                if self.store.pending_analysis():
                    QTimer.singleShot(0, self.recover_pending)
            except Exception as error:
                log.exception("Analysis persistence failed")
                self.show_error(str(error))
                self.retry_button.show()

    @Slot(int, str, str)
    def on_error(self, token, kind, message):
        if token != self.token or self.closing:
            return
        if kind == 'live':
            self.position_label.setText('Положение пока не оценено')
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
        result = self.result_title(game)
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
        if self.game and not self.busy and not self.navigator.viewing and self.game.result == "*":
            if QMessageBox.question(self, "Завершить партию", "Вы хотите сдаться?") == QMessageBox.Yes and self.game.result == '*' and not self.busy:
                self.invalidate_worker()
                self.session.resign()
                self._end_notified = self.game.database_id
                self.sounds.set_enabled(self.settings.values["sound"])
                self.sounds.play("end")
                self.refresh()
                self.advance()

    def save_game(self):
        try:
            self.session.save()
            if self.game and self.game.termination == 'timeout' and self.game.result != '*':
                self.handle_timeout()
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
        table = QTableWidget(len(games), 10)
        table.setHorizontalHeaderLabels(["Дата", "Цвет", "Результат", "До", "После", "Соперник", "Точность", "Время", "Контроль", "Завершение"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        for i, game in enumerate(games):
            values = [game["timestamp"][:16].replace("T", " "), "Белые" if game["player_color"] else "Чёрные",
                      game["result"], f"{game['rating_before']:.0f}", f"{game['rating_after']:.0f}" if game["rated"] else "—",
                      f"{game['bot_rating']:.0f}", f"{game['accuracy']:.1f}%" if game["rated"] else "—", f"{game['duration'] / 60:.1f} мин",
                      json.loads(game['time_control'])['key'] if game['time_control'] and json.loads(game['time_control'])['key'] != 'none' else 'Без времени',
                      {'checkmate': 'Мат', 'resignation': 'Сдача', 'timeout': 'Время', 'draw': 'Ничья', 'stalemate': 'Пат',
                       'insufficient_material': 'Недостаток материала', 'threefold_repetition': 'Повторение', 'fifty_moves': '50 ходов'}.get(game['termination'], 'Ничья' if game['result'] == '1/2-1/2' else '—')]
            for j, value in enumerate(values):
                table.setItem(i, j, QTableWidgetItem(value))
        table.cellDoubleClicked.connect(lambda row, col: self.show_analysis(games[row]["id"]))
        layout.addWidget(table)
        self._present(dialog)

    def closeEvent(self, event):
        if self.closing:
            event.accept()
            return
        self.closing = True
        self.clock_timer.stop()
        try:
            self.session.pause()
        except Exception:
            log.exception("Shutdown clock save failed")
        self.invalidate_worker()
        self.board.animation.stop()
        self.board.mate_animation.stop()
        self.sounds.stop()
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
