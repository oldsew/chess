Adaptive Chess 0.3.0 — clocks, position review and calmer game feedback for Windows 10/11 x64.

- Seven time controls: unlimited, 30+0, 15+10, 10+5, 5+3, 3+2 and 1+0. Monotonic clocks,
  increments, timeout results and paused save/resume; the last chosen control is remembered.
- Previous/next/current-position navigation and clickable halfmoves. Viewing never changes
  the real board or PGN, pauses clocks, accepts moves or asks Stockfish to play historical positions.
- Lightweight position feedback from the existing Stockfish process, always from the player's
  perspective, with stable categories and separate mate feedback. Developer Mode exposes details.
- Click a selected piece again to deselect it; switching pieces and dragging still work.
- 250 ms OutCubic movement and a gentle 650 ms checkmate pulse before the result screen.
  The animation setting and Windows reduced-motion preference are respected.
- History now includes time control and termination reason. Existing SQLite data migrates
  automatically without deleting games, resetting ratings or rewriting rating history.
- Existing SVG pieces, bundled custom sounds, adaptive rating/selection and final analysis retained.
  No new dependency or system beep was added.

Download AdaptiveChess-Windows-x64.zip, extract the entire archive, and open
AdaptiveChess/AdaptiveChess.exe. Keep _internal beside the exe; no Python/Qt/Stockfish install is needed.
AdaptiveChess_Source.zip includes application and corresponding Stockfish sources.
SHA256SUMS.txt contains both archive checksums.

The Windows pipeline runs all 133 tests and five smoke stages against the actual executable:
play/restart/analysis, all time presets and increments, clocks during review, paused restore,
black-player evaluation, mate presentation/result ordering, timeout, seven movement scenarios,
all four Qt-decoded audio files and mute. Smoke reports contain screenshots and audio-device status.
Automated offscreen checks do not replace human visual review or listening on a physical Windows PC.
