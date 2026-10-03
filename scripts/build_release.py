"""Build native portable package, validate that package, then create final archives."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def prepare_notices(package: Path):
    notices = package / 'THIRD_PARTY_LICENSES'
    notices.mkdir(exist_ok=True)
    for name in ['PySide6', 'PySide6-Essentials', 'PySide6-Addons', 'shiboken6', 'chess', 'PyInstaller']:
        distribution = importlib.metadata.distribution(name)
        output = notices / name
        output.mkdir(exist_ok=True)
        for item in distribution.files or []:
            if any(part.lower() in ['licenses', 'license', 'copying'] or part.lower().startswith(('license.', 'copying.')) for part in item.parts):
                file = Path(distribution.locate_file(item))
                if file.is_file():
                    relative = '/'.join(item.parts).replace('..', '_')
                    target = output / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, target)
    python_license = Path(sys.base_prefix) / ('LICENSE.txt' if sys.platform == 'win32' else 'LICENSE')
    if python_license.is_file():
        shutil.copy2(python_license, notices / 'PYTHON-LICENSE.txt')
    # PySide6 wheels do not all contain standalone license texts. Fetch authoritative pinned texts.
    import urllib.request
    for name, url in [
        ('FFmpeg-LGPL-2.1.txt', 'https://raw.githubusercontent.com/FFmpeg/FFmpeg/n7.1/COPYING.LGPLv2.1'),
        ('LGPL-3.0.txt', 'https://raw.githubusercontent.com/qt/qtbase/v6.8.3/LICENSES/LGPL-3.0-only.txt'),
        ('GPL-3.0.txt', 'https://raw.githubusercontent.com/qt/qtbase/v6.8.3/LICENSES/GPL-3.0-only.txt'),
        ('Qt-GPL-exception-1.0.txt', 'https://raw.githubusercontent.com/qt/qtbase/v6.8.3/LICENSES/Qt-GPL-exception-1.0.txt'),
    ]:
        target = notices / name
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
        if len(data) < 100:
            raise RuntimeError(f'Invalid license response: {name}')
        target.write_bytes(data)
    shutil.copy2(ROOT / 'README.md', package / 'README.md')
    shutil.copy2(ROOT / 'LICENSE', package / 'LICENSE')
    shutil.copy2(ROOT / 'NOTICE.md', package / 'NOTICE.md')


def source_archive(path: Path):
    run('git', 'archive', '--format=zip', f'--output={path}', 'HEAD')
    # Include corresponding Stockfish release/source so the source package is self-contained.
    with zipfile.ZipFile(path, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
        for file in (ROOT / 'engines/upstream').rglob('*'):
            if file.is_file():
                archive.write(file, file.relative_to(ROOT).as_posix())
        archive.write(ROOT / 'engines/PROVENANCE.txt', 'engines/PROVENANCE.txt')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    if not args.skip_build:
        run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', 'AdaptiveChess.spec')
    package = ROOT / 'dist/AdaptiveChess'
    exe = package / ('AdaptiveChess.exe' if sys.platform == 'win32' else 'AdaptiveChess')
    if not exe.is_file():
        raise RuntimeError(f'Missing native executable: {exe}')
    prepare_notices(package)
    artifacts = ROOT / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    run(sys.executable, 'scripts/smoke_release.py', '--executable', str(exe), '--output', str(artifacts / 'release-smoke'))
    platform_name = 'Windows-x64' if sys.platform == 'win32' else 'Linux-x64'
    release = Path(shutil.make_archive(str(artifacts / f'AdaptiveChess-{platform_name}'), 'zip', ROOT / 'dist', 'AdaptiveChess'))
    source = artifacts / 'AdaptiveChess_Source.zip'
    source_archive(source)
    checksums = '\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in [release, source]) + '\n'
    (artifacts / 'SHA256SUMS.txt').write_text(checksums, encoding='utf-8')
    print(checksums)


if __name__ == '__main__':
    main()
