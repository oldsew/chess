Adaptive Chess 0.4.0 — material visibility, offline teaching and gentler adaptive opponents.

- Compact SVG strips show each side's actual captured pieces and the player's material balance.
  Historical review and save/resume reconstruct them from moves, including en passant and promotion.
- Refined original ivory/graphite set: coherent turned bases, smoother silhouettes, clearer details,
  quiet gradients and highlights. No filters, real 3D or additional dependency.
- Significant mistakes receive three local Stockfish MultiPV alternatives and short legal lines,
  the opponent's continuation, and an evidence-based teaching note. Recommendations can be reviewed
  on the analysis board and returned to the actual game without changing PGN or live state.
  Uncertain causes use neutral text; mate transitions are separate from ordinary numerical loss.
- Low-strength profiles use wider MultiPV and explicit probability masses for natural inaccuracies
  and errors. Profiles interpolate continuously. Obvious queen gifts, free queen captures and mates
  retain safeguards. The player rating, target strength and behavioral parameters stay distinct.
- Lower ratings receive gentler offsets. Two hopeless losses first ease the opponent and cap further
  rating decline. Existing profiles and rating history are retained without resets or schema changes.
- Developer Mode shows candidate CPL/probability/rank, actual search settings, bot CPL distribution,
  average/median, error counts and unique-best-move frequency. Diagnostics are local JSON; no telemetry.
- Clocks, controls, paused recovery, navigation, live feedback, custom sounds, 250 ms movement,
  650 ms mate presentation, good-move analysis and atomic rating persistence retained.

Download AdaptiveChess-Windows-x64.zip, extract the entire archive, and open
AdaptiveChess/AdaptiveChess.exe. Keep _internal beside the exe; no Python/Qt/Stockfish install is needed.
AdaptiveChess_Source.zip includes application and corresponding Stockfish sources.
SHA256SUMS.txt contains both archive checksums.

The Windows pipeline runs all 172 tests and seven smoke stages against the real executable,
including capture/history/restart, material and clock restoration, both-color offline coaching,
read-only PV navigation, and deterministic strength comparisons, alongside existing gameplay,
clock, mate, SVG and audio regression checks. Audio decoding/mute and available playback backends
are checked; physical Windows listening and human Elo calibration are separate checks.
The displayed level remains an internal Adaptive Chess Rating, not certified FIDE/online Elo.
