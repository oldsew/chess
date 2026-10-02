from __future__ import annotations

import logging
from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    result = Signal(int, str, object)
    error = Signal(int, str, str)
    progress = Signal(int, int)


class Worker(QRunnable):
    def __init__(self, token, kind, function):
        super().__init__()
        self.token, self.kind, self.function = token, kind, function
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.function(self.signals.progress.emit)
            self.signals.result.emit(self.token, self.kind, result)
        except InterruptedError:
            self.signals.error.emit(self.token, self.kind, "Операция отменена")
        except Exception as error:
            logging.getLogger(__name__).exception("Background %s failed", self.kind)
            self.signals.error.emit(self.token, self.kind, str(error))
