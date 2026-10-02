# Third-party software and licenses

Adaptive Chess and its original SVG artwork are distributed under GPL-3.0 (see LICENSE).

- python-chess / chess: GPL-3.0 or later; https://github.com/niklasf/python-chess
- Stockfish 17.1: GPL-3.0; https://github.com/official-stockfish/Stockfish/tree/sf_17.1
  The package retains the complete official upstream release, including source and Copying.txt,
  under `_internal/engines/upstream`. Pinned download URLs and SHA256 are recorded by the fetch script.
- PySide6, Shiboken6 and Qt: used under LGPL-3.0; dynamic Qt libraries are retained in the
  portable package and can be replaced by compatible versions. License texts are included in
  THIRD_PARTY_LICENSES. Corresponding source: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/
  Qt source: https://download.qt.io/archive/qt/6.8/6.8.3/single/
- Python: PSF license; https://www.python.org/downloads/release/python-31214/
- PyInstaller: GPL-2.0 with bootloader exception permitting bundled application distribution.

The source archive contains the application source and build scripts. Engine source is also
included alongside the bundled engine, and scripts/fetch_stockfish.py reproduces the pinned
upstream download with TLS and checksum verification. Do not remove notices or licensing
files when redistributing. See the upstream projects for their full license terms.
