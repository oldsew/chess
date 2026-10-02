"""Download pinned official Stockfish distributions, retaining GPL source and license."""
from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request
import zipfile

RELEASE = "sf_17.1"
ASSETS = {
    "linux": ("stockfish-ubuntu-x86-64.tar", "4dafdd04f71e70755a327b5be258937b281e60ba87bc0a5801399908240d4a73"),
    "windows": ("stockfish-windows-x86-64.zip", "8b5c6ebd90684ea0900729d955eb9a426557b5f88fa05772404ac7bbe8e9b5cb"),
}
ROOT = Path(__file__).resolve().parents[1]


def fetch(platform: str, archive: Path | None = None):
    filename, expected = ASSETS[platform]
    url = f"https://github.com/official-stockfish/Stockfish/releases/download/{RELEASE}/{filename}"
    print(f"Preparing Stockfish 17.1 ({platform})")
    data = archive.read_bytes() if archive else urllib.request.urlopen(url, timeout=120).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("Stockfish archive SHA256 verification failed")
    output = ROOT / "engines" / "upstream"
    output.mkdir(parents=True, exist_ok=True)
    if platform == "windows":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.infolist():
                if not (output / member.filename).resolve().is_relative_to(output.resolve()):
                    raise RuntimeError("Unsafe archive path")
            z.extractall(output)
        binaries = list(output.rglob("stockfish-windows-x86-64.exe"))
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            t.extractall(output, filter="data")
        binaries = list(output.rglob("stockfish-ubuntu-x86-64"))
    if len(binaries) != 1:
        raise RuntimeError(f"Expected exactly one engine executable, found {len(binaries)}")
    target = ROOT / "engines" / ("stockfish.exe" if platform == "windows" else "stockfish")
    shutil.copy2(binaries[0], target)
    if platform == "linux":
        target.chmod(0o755)
    (ROOT / "engines/PROVENANCE.txt").write_text(f"Stockfish 17.1\n{url}\nArchive SHA256: {expected}\nGPL-3.0; complete upstream release and source retained under upstream/.\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=ASSETS, default="windows" if sys.platform == "win32" else "linux")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    fetch(args.platform, args.archive)
