from __future__ import annotations

import json
import chess
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QSpinBox, QSplitter, QListWidget, QHBoxLayout, QHeaderView, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPushButton, QTextEdit)

from app.config.settings import DEFAULT_SETTINGS
from app.ui.board import THEMES, ChessBoard
from app.services.clocks import TIME_CONTROLS
from app.ui.style import STYLE
from app.ui.motion import system_motion_enabled


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
        p.setPen(QColor("#aaa9a1"))
        if not self.ratings:
            p.drawText(self.rect(), Qt.AlignCenter, "График появится после первой партии")
            return
        low, high = min(self.ratings) - 30, max(self.ratings) + 30
        p.drawText(5, 18, str(round(high)))
        p.drawText(5, self.height() - 5, str(round(low)))
        p.setPen(QPen(QColor("#a8bc91"), 2))
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


class VariationList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideNone)
        self.setMinimumHeight(185)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fit_rows()

    def fit_rows(self):
        for row in range(self.count()):
            item = self.item(row)
            bounds = self.fontMetrics().boundingRect(QRect(0,0,max(80,self.viewport().width()-20),1000),Qt.TextWordWrap,item.text())
            item.setSizeHint(QSize(0,bounds.height()+12))


class AnalysisDialog(QDialog):
    def __init__(self, row, parent=None):
        super().__init__(parent)
        from app.services.game import GameState
        self.setWindowTitle("Разбор партии")
        self.setStyleSheet(STYLE)
        self.resize(1040, 700)
        developer = bool(parent and getattr(parent, 'settings', None) and parent.settings.values['developer_mode'])
        layout = QVBoxLayout(self)
        self.moves = json.loads(row["analysis"] or "[]")
        self.game = GameState.from_pgn(row["pgn"],player_color=bool(row["player_color"]))
        layout.addWidget(QLabel(f"Результат: {row['result']} · Точность: {row['accuracy']:.1f}%"))
        self.table = QTableWidget(len(self.moves), 7)
        self.table.setHorizontalHeaderLabels(["Ход", "Ваш ход", "До", "После", "Категория", "Лучший", "Потеря"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setMaximumHeight(145)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
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
        self.board.theme = parent.board.theme if parent and hasattr(parent, 'board') else 'Сланец'
        self.board.animations_enabled = system_motion_enabled() and (not parent or not hasattr(parent,'settings') or parent.settings.values['animations'])
        self.board.set_position(self.game.board)
        split.addWidget(self.board)
        panel = QWidget()
        panel.setObjectName('coachPanel')
        side = QVBoxLayout(panel)
        side.setContentsMargins(12, 10, 12, 10)
        side.setSpacing(6)
        def heading(text):
            label = QLabel(text)
            label.setObjectName('sectionTitle')
            side.addWidget(label)
        self.played_label = QLabel('Выберите ход в списке')
        self.played_label.setWordWrap(True)
        self.played_label.setObjectName('playedMove')
        heading('Ваш ход')
        side.addWidget(self.played_label)
        heading('Что произошло')
        self.summary = QLabel('Доска показывает фактическую партию.')
        self.summary.setObjectName('coachSummary')
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.PlainText)
        side.addWidget(self.summary)
        self.variations = VariationList()
        heading('Почему это лучше')
        self.recommendation = QLabel('')
        self.recommendation.setObjectName('recommendation')
        self.recommendation.setWordWrap(True)
        self.recommendation.setTextFormat(Qt.PlainText)
        side.addWidget(self.recommendation)
        heading('Лучше было · нажмите вариант для просмотра')
        side.addWidget(self.variations,1)
        self.response_label = QLabel('')
        self.response_label.setWordWrap(True)
        self.response_label.setTextFormat(Qt.PlainText)
        side.addWidget(self.response_label)
        self.advice_heading = QLabel('Совет')
        self.advice_heading.setObjectName('sectionTitle')
        side.addWidget(self.advice_heading)
        self.advice = QLabel('')
        self.advice.setWordWrap(True)
        self.advice.setTextFormat(Qt.PlainText)
        self.advice.setObjectName('coachAdvice')
        side.addWidget(self.advice)
        self.explanation_debug = QTextEdit()
        self.explanation_debug.setReadOnly(True)
        self.explanation_debug.setMinimumHeight(110)
        self.explanation_debug.setMaximumHeight(160)
        self.explanation_debug.setVisible(developer)
        side.addWidget(self.explanation_debug)
        controls = QHBoxLayout()
        self.previous = QPushButton('←')
        self.next = QPushButton('→')
        self.previous.clicked.connect(lambda:self.step_variation(-1))
        self.next.clicked.connect(lambda:self.step_variation(1))
        controls.addWidget(self.previous)
        controls.addWidget(self.next)
        self.line_status = QLabel('Фактическая партия')
        self.line_status.setWordWrap(True)
        self.actual_button = QPushButton('К фактической партии')
        self.actual_button.clicked.connect(self.return_to_actual)
        wrapper = QWidget()
        wrapper.setMinimumWidth(365)
        wrapper.setMaximumWidth(490)
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(0,0,0,0)
        scroll = QScrollArea()
        self.coach_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        outer.addWidget(scroll,1)
        outer.addLayout(controls)
        outer.addWidget(self.line_status)
        outer.addWidget(self.actual_button)
        split.addWidget(wrapper)
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
        self.showing_before = False
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
        reason = {'material_loss':'Потеря материала','pawn_loss':'Потеря пешки','missed_capture':'Пропущенное взятие',
                  'missed_material':'Упущена возможность выиграть материал','missed_mate':'Пропущен мат в один',
                  'missed_forced_mate':'Упущен форсированный мат','allowed_mate':'Матовая угроза'}.get(coaching.get('reason'))
        self.response_label.setText('Ответ Stockfish: ' + coaching['response']['pv_san'] if coaching.get('response') else '')
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
        self.variations.fit_rows()
        self.variations.blockSignals(False)
        self.advice.setText(coaching.get('advice') or (f"Stockfish предпочитает {move['best_san']}. Для этого сохранённого разбора подробные варианты отсутствуют."
                                                    if move['cpl'] > 40 else 'Этот ход не требует подробного разбора.'))
        explanation = coaching.get('explanation')
        if not explanation and self.alternatives:
            from app.services.analysis_explainer import explain
            explanation = explain(self.root_position,self.game.board.move_stack[move['ply']-1],coaching,self.game.player_color)
        self.recommendation.setText(explanation['recommendation'] if explanation else
                                    'Для этого сохранённого разбора объяснение идеи не записано.')
        if explanation:
            self.summary.setText(explanation['title']+'\n'+explanation['reason'])
        elif reason:
            self.summary.setText(reason + '\n' + self.summary.text())
        self.advice.setVisible(not explanation)
        self.advice_heading.setVisible(not explanation)
        self.coach_scroll.verticalScrollBar().setValue(0)
        self.summary.setProperty('severity','error' if move['cpl'] > 40 else 'good')
        self.summary.style().unpolish(self.summary)
        self.summary.style().polish(self.summary)
        self.explanation_debug.setPlainText(json.dumps(explanation or {},ensure_ascii=False,indent=2))
        self.line_moves = []
        self.showing_before = bool(self.alternatives)
        if self.showing_before:
            self.board.annotations = [(h['from'],h['to'],h['role']) for h in (explanation or {}).get('highlights',[])]
            self.board.set_position(self.root_position)
            self.line_status.setText('До вашего хода · красная стрелка — ваш ход, зелёная — рекомендация')
            self.update_line_controls()
        else:
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
        self.showing_before = False
        self.board.annotations = []
        # Choosing another branch is a controlled skip to its common root, then one animated move.
        self.board.set_position(self.root_position)
        self.render_line()

    def render_line(self):
        position = self.root_position.copy()
        for move in self.line_moves[:self.line_cursor]:
            position.push(move)
        self.board.set_position(position,animate=True,celebrate=False)
        self.line_status.setText(f'Рекомендуемый вариант · полуход {self.line_cursor} из {len(self.line_moves)}')
        self.update_line_controls()

    def step_variation(self,delta):
        if self.line_moves:
            self.line_cursor = max(0,min(len(self.line_moves),self.line_cursor+delta))
            self.render_line()

    def return_to_actual(self):
        self.line_moves = []
        self.showing_before = False
        self.board.annotations = []
        position = self.game.board.root()
        ply = self.moves[self.selected_row]['ply'] if self.selected_row is not None else len(self.game.board.move_stack)
        for move in self.game.board.move_stack[:ply]:
            position.push(move)
        self.board.set_position(position,animate=True,celebrate=False)
        self.line_status.setText('Фактическая партия')
        self.variations.blockSignals(True)
        self.variations.setCurrentRow(-1)
        self.variations.blockSignals(False)
        self.update_line_controls()

    def update_line_controls(self):
        self.previous.setEnabled(bool(self.line_moves) and self.line_cursor > 0)
        self.next.setEnabled(bool(self.line_moves) and self.line_cursor < len(self.line_moves))
        self.actual_button.setEnabled(bool(self.line_moves) or self.showing_before)
