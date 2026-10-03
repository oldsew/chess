from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app import __version__
from app.config.settings import data_dir
from app.ui.window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", type=Path)
    parser.add_argument("--smoke-resume", action="store_true")
    parser.add_argument("--smoke-complete", action="store_true")
    parser.add_argument("--smoke-polish", action="store_true")
    parser.add_argument("--smoke-gameplay", action="store_true")
    parser.add_argument("--smoke-learning", action="store_true")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setOrganizationName("AdaptiveChess")
    app.setApplicationName("AdaptiveChess")
    app.setApplicationVersion(__version__)
    try:
        directory = data_dir()
        logs = directory / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(logs / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s %(message)s")
        logging.info("Adaptive Chess %s starting", __version__)
        def exception_hook(kind, value, traceback):
            logging.critical("Unhandled exception", exc_info=(kind, value, traceback))
            QMessageBox.critical(None, "Adaptive Chess", "Произошла ошибка. Партия сохраняется после каждого хода. Подробности в logs/app.log.")
        sys.excepthook = exception_hook
        window = MainWindow(directory)
        window.show()
        if args.smoke_test:
            if args.smoke_learning:
                from app.ui.smoke_learning import attach_learning_smoke
                window.smoke_timer = attach_learning_smoke(app, window, args.smoke_test, args.smoke_resume)
            elif args.smoke_gameplay:
                from app.ui.smoke_gameplay import attach_gameplay_smoke
                window.smoke_timer = attach_gameplay_smoke(app, window, args.smoke_test)
            elif args.smoke_polish:
                from app.ui.smoke_polish import attach_polish_smoke
                window.smoke_timer = attach_polish_smoke(app, window, args.smoke_test)
            else:
                from app.services.smoke import attach_smoke
                window.smoke_timer = attach_smoke(app, window, args.smoke_test, args.smoke_resume, args.smoke_complete)
        return app.exec()
    except Exception:
        logging.exception("Startup failed")
        if args.smoke_test:
            args.smoke_test.write_text('{"success":false,"message":"Startup failed; inspect app.log"}', encoding="utf-8")
        else:
            QMessageBox.critical(None, "Adaptive Chess", "Не удалось запустить приложение. Проверьте доступ к папке пользовательских данных и полноту portable-пакета.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
