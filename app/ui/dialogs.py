from __future__ import annotations

import json
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPushButton)

from app.config.settings import DEFAULT_SETTINGS
from app.ui.board import THEMES, ChessBoard


class SettingsDialog(QDialog):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        form = QFormLayout(self)
        self.fields = {}
        combos = {"theme": list(THEMES), "player_color": ["Белые", "Чёрные", "Случайно"]}
        labels = {"theme": "Доска", "sound": "Звуки игры", "legal_highlights": "Допустимые ходы",
                  "player_color": "Мой цвет", "show_bot_rating": "Уровень соперника после партии",
                  "analysis_depth": "Глубина анализа (с лимитом времени)", "developer_mode": "Режим разработчика"}
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
        self.setWindowTitle("Разбор партии")
        self.resize(980, 700)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Результат: {row['result']} · Точность: {row['accuracy']:.1f}% · Средняя потеря: {row['average_cpl']:.1f} cp"))
        self.moves = json.loads(row["analysis"] or "[]")
        table = QTableWidget(len(self.moves), 7)
        table.setHorizontalHeaderLabels(["Ход", "Факт", "Оценка до", "Оценка после", "Категория", "Лучший", "CPL"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        for i, m in enumerate(self.moves):
            values = [str((m["ply"] + 1) // 2), m["san"], m.get("before_label", str(m["before_cp"])),
                      m.get("after_label", str(m["after_cp"])), m["category"], m["best_san"], str(m["cpl"])]
            for j, value in enumerate(values):
                table.setItem(i, j, QTableWidgetItem(value))
        layout.addWidget(table)
        self.board = ChessBoard()
        self.board.setMinimumSize(300, 300)
        self.board.orientation = bool(row["player_color"])
        from app.services.game import GameState
        self.game = GameState.from_pgn(row["pgn"])
        self.board.set_position(self.game.board)
        layout.addWidget(self.board)
        table.cellClicked.connect(self.show_position)

    def show_position(self, row, column):
        position = self.game.board.root()
        for move in self.game.board.move_stack[:self.moves[row]["ply"]]:
            position.push(move)
        self.board.set_position(position)
