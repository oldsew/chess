Adaptive Chess 0.2.0 — smoother desktop presentation for Windows 10/11 x64.

- 190 ms OutCubic piece movement, capture fades, synchronized castling and promotion crossfades.
- Dragged pieces settle from the pointer into their square instead of replaying the whole move.
- Original ivory/graphite SVG pieces with gradients, subtle bevels and soft shadows.
- Softer last-move, selection, legal-move and check highlights.
- Four quiet bundled WAV cues for moves, captures, check and game end. The existing sound
  toggle controls them; system notification/beep sounds are no longer used for moves.
- Chess rules, adaptive rating/selection, SQLite persistence and game analysis are unchanged.

Download AdaptiveChess-Windows-x64.zip, extract the entire archive, and open
AdaptiveChess/AdaptiveChess.exe. Keep _internal beside the exe; no Python/Qt/Stockfish install is needed.
SHA256SUMS.txt contains the package and complete source archive checksums.

The pipeline tests source and the real packaged executable: play, save/resume, analysis, next
opponent, seven animated transitions, all four Qt-decoded WAVs and mute. UX smoke reports include
screenshots and whether a real audio output was available; decoding does not imply an audible
listening test on a runner without audio hardware. See README.md for build instructions.
