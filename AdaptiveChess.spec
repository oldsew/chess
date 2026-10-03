# PyInstaller onedir build: run on the target OS, never cross-package Linux as Windows.
from pathlib import Path
root = Path(SPECPATH)
datas = [
    (str(root / 'app/config/tuning.json'), 'app/config'),
    (str(root / 'app/config/gameplay.json'), 'app/config'),
    (str(root / 'resources'), 'resources'),
    (str(root / 'engines'), 'engines'),
    (str(root / 'LICENSE'), '.'),
    (str(root / 'NOTICE.md'), '.'),
]
a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=[], datas=datas,
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
                       'PySide6.QtQml', 'PySide6.QtQuick',
                       'pytest', 'pytestqt'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AdaptiveChess',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='AdaptiveChess')
