from __future__ import annotations

import json
import chess
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QSpinBox, QSplitter, QListWidget, QHBoxLayout, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPushButton)

from app.config.settings import DEFAULT_SETTINGS
from app.ui.board import THEMES, ChessBoard
from app.services.clocks import TIME_CONTROLS


class SettingsDialog(QDialog):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        form = QFormLayout(self)
        self.fields = {}
        combos = {"theme": list(THEMES), "player_color": ["Белые", "Чёрные", "Случайно"], "time_control": [c.key for c in TIME_CONTROLS]}
        labels = {"theme": "Доска", "sound": "Звуки игры", "legal_highlights": "Допустимые ходы",
                  "player_color": "Мой цвет", "show_bot_rating": "Уровень соперника после партии",
                  "analysis_depth": "Глубина анализа (с лимитом времени)", "developer_mode": "Режим разработчика",
                  "time_control": "Контроль для новой партии", "animations": "Анимации"}
        for key in DEFAULT_SETTINGS:
            if key in combos:
                field = QComboBox()
                field.addItems(combos[key])
                field.setCurrentText(values[key])
            elif key == "analysis_depth":
                field = QSpinBox()
                field.setRange(12, 22)
                field.setValue(values[key])
            else:
                field = QCheckBox()
                field.setChecked(values[key])
            self.fields[key] = field
            form.addRow(labels[key], field)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return {key: widget.currentText() if isinstance(widget, QComboBox) else
                widget.value() if isinstance(widget, QSpinBox) else widget.isChecked()
                for key, widget in self.fields.items()}


class RatingChart(QWidget):
    def __init__(self, ratings):
        super().__init__()
        self.ratings = ratings
        self.setMinimumHeight(150)
        self.setAccessibleName("Изменение рейтинга во времени")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor("#9daabd"))
        if not self.ratings:
            p.drawText(self.rect(), Qt.AlignCenter, "График появится после первой партии")
            return
        low, high = min(self.ratings) - 30, max(self.ratings) + 30
        p.drawText(5, 18, str(round(high)))
        p.drawText(5, self.height() - 5, str(round(low)))
        p.setPen(QPen(QColor("#66cfbf"), 2))
        def point(i, rating):
            from PySide6.QtCore import QPointF
            return QPointF(48 + i * (self.width() - 65) / max(1, len(self.ratings) - 1),
                           15 + (high - rating) / (high - low) * (self.height() - 35))
        for i in range(1, len(self.ratings)):
            p.drawLine(point(i - 1, self.ratings[i - 1]), point(i, self.ratings[i]))
        for i, value in enumerate(self.ratings):
            p.drawEllipse(point(i, value), 3, 3)


class StatisticsDialog(QDialog):
    def __init__(self, profile, games, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Статистика")
        self.resize(560, 440)
        layout = QVBoxLayout(self)
        completed = [g for g in games if g["result"] != "*"]
        rated = [g for g in completed if g["rated"]]
        scores = [0.5 if g["result"] == "1/2-1/2" else float((g["result"] == "1-0") == bool(g["player_color"])) for g in completed]
        wins, draws, losses = scores.count(1), scores.count(0.5), scores.count(0)
        avg_accuracy = sum(g["accuracy"] for g in rated) / len(rated) if rated else 0
        avg_cpl = sum(g["average_cpl"] for g in rated) / len(rated) if rated else 0
        layout.addWidget(QLabel(f"Уровень: {profile.rating:.0f} · Максимум: {profile.peak:.0f}"))
        layout.addWidget(QLabel(f"Партий: {len(completed)} · Побед: {wins} · Ничьих: {draws} · Поражений: {losses}"))
        layout.addWidget(QLabel(f"Доля побед: {wins / max(1, len(completed)):.0%} · Средняя точность: {avg_accuracy:.1f}% · CPL: {avg_cpl:.1f}"))
        layout.addWidget(QLabel("Последние 10: " + "  ".join("П" if s == 1 else "Н" if s == 0.5 else "Пор" for s in scores[:10])))
        layout.addWidget(RatingChart([1000] + [g["rating_after"] for g in reversed(rated)]))
        layout.addWidget(QLabel("Уровень — внутренняя оценка приложения, не официальный рейтинг FIDE."))


class AnalysisDialog(QDialog):
    def __init__(self, row, parent=None):
        super().__init__(parent)
        from app.services.game import GameState
        self.setWindowTitle("Разбор партии")
        self.resize(1100, 760)
        layout = QVBoxLayout(self)
        self.moves = json.loads(row["analysis"] or "[]")
        self.game = GameState.from_pgn(row["pgn"],player_color=bool(row["player_color"]))
        layout.addWidget(QLabel(f"Результат: {row['result']} · Точность: {row['accuracy']:.1f}%"))
        self.table = QTableWidget(len(self.moves), 7)
        self.table.setHorizontalHeaderLabels(["Ход", "Ваш ход", "До", "После", "Категория", "Лучший", "Потеря"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setMaximumHeight(175)
        self.table.horizontalHeader().setStretchLastSection(True)
        for i, m in enumerate(self.moves):
            mate = self.has_mate(m)
            values = [str((m["ply"] + 1) // 2),m["san"],self.score(m,'before'),self.score(m,'after'),
                      m["category"],m["best_san"],'Матовый переход' if mate else f"{m['cpl']/100:.2f}"]
            for j, value in enumerate(values):
                self.table.setItem(i,j,QTableWidgetItem(value))
        layout.addWidget(self.table)
        split = QSplitter()
        self.board = ChessBoard()
        self.board.setMinimumSize(330,330)
        self.board.orientation = self.game.player_color
        self.board.set_position(self.game.board)
        split.addWidget(self.board)
        panel = QWidget()
        panel.setMinimumWidth(340)
        panel.setMaximumWidth(480)
        side = QVBoxLayout(panel)
        self.played_label = QLabel('Выберите ход в списке')
        self.played_label.setWordWrap(True)
        self.played_label.setStyleSheet('font-size: 18px; font-weight: 600;')
        side.addWidget(QLabel('Ваш ход'))
        side.addWidget(self.played_label)
        side.addWidget(QLabel('Что произошло'))
        self.summary = QLabel('Доска показывает фактическую партию.')
        self.summary.setWordWrap(True)
        side.addWidget(self.summary)
        side.addWidget(QLabel('Лучшие варианты · нажмите, чтобы посмотреть'))
        self.variations = QListWidget()
        self.variations.setWordWrap(True)
        side.addWidget(self.variations,1)
        side.addWidget(QLabel('Совет'))
        self.advice = QLabel('')
        self.advice.setWordWrap(True)
        self.advice.setTextFormat(Qt.PlainText)
        self.advice.setStyleSheet('color: #bdd5ce; padding: 8px 0;')
        side.addWidget(self.advice)
        controls = QHBoxLayout()
        self.previous = QPushButton('←')
        self.next = QPushButton('→')
        self.previous.clicked.connect(lambda:self.step_variation(-1))
        self.next.clicked.connect(lambda:self.step_variation(1))
        controls.addWidget(self.previous)
        controls.addWidget(self.next)
        side.addLayout(controls)
        self.line_status = QLabel('Фактическая партия')
        self.line_status.setWordWrap(True)
        side.addWidget(self.line_status)
        self.actual_button = QPushButton('К фактической партии')
        self.actual_button.clicked.connect(self.return_to_actual)
        side.addWidget(self.actual_button)
        split.addWidget(panel)
        split.setStretchFactor(0,1)
        layout.addWidget(split,1)
        self.table.cellClicked.connect(self.show_position)
        self.variations.currentRowChanged.connect(self.show_variation)
        self.board.previous_requested.connect(lambda:self.step_variation(-1))
        self.board.next_requested.connect(lambda:self.step_variation(1))
        self.selected_row = None
        self.line_moves = []
        self.line_cursor = 0
        self.alternatives = []
        self.root_position = self.game.board.root()
        self.update_line_controls()
        if self.moves:
            significant = next((i for i,m in enumerate(self.moves) if m.get('coaching')),0)
            self.table.selectRow(significant)
            self.show_position(significant,0)

    @staticmethod
    def has_mate(move):
        return any('#' in move.get(key,'') for key in ['before_label','after_label'])

    @staticmethod
    def score(move,side):
        from app.services.coaching import format_evaluation
        coaching = move.get('coaching')
        if coaching:
            return format_evaluation(coaching[side+'_cp'],coaching['mate_'+side],coaching.get(side+'_mate_winning'))
        label = move.get(side+'_label','')
        if '#' in label:
            return 'Матовая оценка'
        return format_evaluation(move[side+'_cp'])

    def show_position(self,row,column):
        if row < 0 or row >= len(self.moves):
            return
        self.selected_row = row
        move = self.moves[row]
        self.root_position = self.game.board.root()
        for played in self.game.board.move_stack[:move['ply']-1]:
            self.root_position.push(played)
        prefix = f'{self.root_position.fullmove_number}.' if self.root_position.turn else f'{self.root_position.fullmove_number}…'
        self.played_label.setText(f"{prefix} {move['san']} · {move['category']}")
        self.summary.setText(f"Оценка с вашей стороны: {self.score(move,'before')} → {self.score(move,'after')}\n" +
                             ('Матовая тактика: обычная числовая потеря не применяется.' if self.has_mate(move) else f"Потеря оценки: {move['cpl']/100:.2f}"))
        coaching = move.get('coaching') or {}
        self.alternatives = coaching.get('alternatives',[])
        # Saved lines must correspond to this actual position; old analysis remains readable.
        if coaching.get('root_fen') != self.root_position.fen():
            self.alternatives = []
        self.variations.blockSignals(True)
        self.variations.clear()
        from app.services.coaching import format_evaluation
        for i, alternative in enumerate(self.alternatives,1):
            score = format_evaluation(alternative['evaluation_cp'],alternative['mate'],alternative.get('mate_winning'))
            self.variations.addItem(f"{i}. {alternative['san']}    {score}\n{alternative['pv_san']}")
        self.variations.blockSignals(False)
        self.advice.setText(coaching.get('advice') or (f"Stockfish предпочитает {move['best_san']}. Для этого сохранённого разбора подробные варианты отсутствуют."
                                                    if move['cpl'] > 40 else 'Этот ход не требует подробного разбора.'))
        self.return_to_actual()

    def show_variation(self,row):
        if row < 0 or row >= len(self.alternatives):
            return
        position = self.root_position.copy()
        self.line_moves = []
        for uci in self.alternatives[row]['pv_uci']:
            move = chess.Move.from_uci(uci)
            if move not in position.legal_moves:
                break
            self.line_moves.append(move)
            position.push(move)
        self.line_cursor = min(1,len(self.line_moves))
        self.render_line()

    def render_line(self):
        position = self.root_position.copy()
        for move in self.line_moves[:self.line_cursor]:
            position.push(move)
        self.board.set_position(position)
        self.line_status.setText(f'Рекомендуемый вариант · полуход {self.line_cursor} из {len(self.line_moves)}')
        self.update_line_controls()

    def step_variation(self,delta):
        if self.line_moves:
            self.line_cursor = max(0,min(len(self.line_moves),self.line_cursor+delta))
            self.render_line()

    def return_to_actual(self):
        self.line_moves = []
        position = self.game.board.root()
        ply = self.moves[self.selected_row]['ply'] if self.selected_row is not None else len(self.game.board.move_stack)
        for move in self.game.board.move_stack[:ply]:
            position.push(move)
        self.board.set_position(position)
        self.line_status.setText('Фактическая партия')
        self.variations.blockSignals(True)
        self.variations.setCurrentRow(-1)
        self.variations.blockSignals(False)
        self.update_line_controls()

    def update_line_controls(self):
        self.previous.setEnabled(bool(self.line_moves) and self.line_cursor > 0)
        self.next.setEnabled(bool(self.line_moves) and self.line_cursor < len(self.line_moves))
        self.actual_button.setEnabled(bool(self.line_moves))
