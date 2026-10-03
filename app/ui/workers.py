from __future__ import annotations

import logging
import threading
from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    result = Signal(int, str, object)
    error = Signal(int, str, str)
    progress = Signal(int, int)
    live = Signal(int, object)


class Worker(QRunnable):
    def __init__(self, token, kind, function, report_live=False):
        super().__init__()
        self.token, self.kind, self.function = token, kind, function
        self.signals = WorkerSignals()
        self.report_live = report_live
        self.cancelled = threading.Event()

    def run(self):
        try:
            if self.cancelled.is_set():
                raise InterruptedError('Операция отменена')
            if self.report_live:
                result = self.function(self.signals.progress.emit, lambda value: self.signals.live.emit(self.token, value))
            else:
                result = self.function(self.signals.progress.emit)
            self.signals.result.emit(self.token, self.kind, result)
        except InterruptedError:
            self.signals.error.emit(self.token, self.kind, "Операция отменена")
        except Exception as error:
            logging.getLogger(__name__).exception("Background %s failed", self.kind)
            self.signals.error.emit(self.token, self.kind, str(error))
