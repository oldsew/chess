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
        for stage, resume, complete in [("first-run", False, False), ("resume", True, False), ("completion", False, True)]:
            report = output / f"{stage}.json"
            if report.exists():
                report.unlink()
            args = [*command, "--smoke-test", str(report.resolve())]
            if resume:
                args.append("--smoke-resume")
            if complete:
                args.append("--smoke-complete")
            try:
                process = subprocess.run(args, env=variables, timeout=100, capture_output=True, text=True)
                (output / f"{stage}.stderr.txt").write_text(process.stderr, encoding="utf-8")
                if process.returncode or not report.is_file():
                    raise RuntimeError(f"{stage}: exit={process.returncode}; {process.stderr[-3000:]}")
                result = json.loads(report.read_text(encoding="utf-8"))
                assert all(result.get(key) for key in ["success", "window_visible", "database_created", "settings_created", "engine_closed"]), result
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
