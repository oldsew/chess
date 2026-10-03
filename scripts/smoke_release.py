from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def smoke(command: list[str], output: Path):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="adaptive-chess-smoke-") as temp:
        variables = os.environ.copy()
        variables["ADAPTIVE_CHESS_DATA_DIR"] = temp
        # Qt offscreen still constructs and paints the actual MainWindow.
        variables["QT_QPA_PLATFORM"] = "offscreen"
        for stage, resume, complete in [("first-run", False, False), ("resume", True, False), ("completion", False, True), ("polish", False, False), ("gameplay", False, False), ('learning',False,False), ('learning-resume',True,False), ('visual-100',False,False), ('visual-125',False,False), ('visual-150',False,False)]:
            report = output / f"{stage}.json"
            if report.exists():
                report.unlink()
            args = [*command, "--smoke-test", str(report.resolve())]
            if resume:
                args.append("--smoke-resume")
            if complete:
                args.append("--smoke-complete")
            if stage == "polish":
                args.append("--smoke-polish")
            if stage == 'gameplay':
                args.append('--smoke-gameplay')
                variables['ADAPTIVE_CHESS_DATA_DIR'] = str(Path(temp) / 'gameplay')
            if stage.startswith('learning'):
                args.append('--smoke-learning')
                variables['ADAPTIVE_CHESS_DATA_DIR'] = str(Path(temp) / 'learning')
            if stage.startswith('visual'):
                args.append('--smoke-visual')
                variables['QT_SCALE_FACTOR'] = str(int(stage.split('-')[1])/100)
                variables['ADAPTIVE_CHESS_DATA_DIR'] = str(Path(temp) / stage)
            try:
                process = subprocess.run(args, env=variables, timeout=100, capture_output=True, text=True)
                (output / f"{stage}.stderr.txt").write_text(process.stderr, encoding="utf-8")
                if process.returncode or not report.is_file():
                    raise RuntimeError(f"{stage}: exit={process.returncode}; {process.stderr[-3000:]}")
                result = json.loads(report.read_text(encoding="utf-8"))
                checks = ["success", "window_visible", "engine_closed"]
                checks += ["mute_verified"] if stage == "polish" else ["database_created", "settings_created"]
                assert all(result.get(key) for key in checks), result
                print(stage, result["message"])
            finally:
                log = Path(temp) / "logs/app.log"
                if log.exists():
                    (output / "app.log").write_bytes(log.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/smoke"))
    args = parser.parse_args()
    smoke([str(args.executable.resolve())] if args.executable else [sys.executable, "main.py"], args.output)
