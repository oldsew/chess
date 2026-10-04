Adaptive Chess 0.7.0 — post-game explanations for people who know the moves, not the notation.

- Review opens in “Простое объяснение”. Every explained mistake has four short blocks:
  why it is a problem, its concrete consequence, a main suggested move and a reusable
  teaching principle. Moves name the piece, starting square and destination; captures,
  castling, en passant and promotion have human descriptions.
- Beginner text uses the existing verified evidence. It explains which piece can be taken,
  simultaneous threats, a trapped defender, unsafe exchanges, restricted bishops and king
  cover without requiring evaluation, CPL, PV, MultiPV or unexplained tactical labels.
  Uncertain/legacy comparisons retain honest uncertainty rather than inventing a cause.
- “Просто | Подробно” and the expandable “Подробный анализ” keep the professional review
  available with scores, loss, engine continuations and multiple recommendations. The default
  table uses human move descriptions and hides numerical engine columns. Mode changes keep
  the selected move, variation position and original PGN intact.
- One button previews the main recommendation. Other choices are collapsed below the four
  teaching blocks, with human descriptions and distinguishing board facts. Selecting a choice
  synchronizes the text and green arrow. Simple mode highlights at most two relevant squares
  alongside the two existing arrows. Developer JSON stays outside the beginner view.
- Compact beginner move rows leave more room for teaching, and the sidebar scrolls at high
  DPI. All prior read-only variation animations and 100/125/150% layout checks are retained.
  Ratings, move selection, engine analysis, database/clock/history logic, SVGs and WAVs are
  unchanged. No dependency or database migration is added.

Validation: 270 tests, including 33 new beginner-presentation regressions; all eleven
actual-executable smoke stages. The PGN corpus stage now checks the default four blocks,
translated moves, hidden technical values, collapsed alternatives, recommendation preview,
mode/disclosure switching with preserved position, both player colors and unchanged PGN.
All three DPI stages save both beginner and professional screenshots.

Release files: AdaptiveChess-Windows-x64.zip, AdaptiveChess_Source.zip, SHA256SUMS.txt.
Extract the entire Windows ZIP and open AdaptiveChess/AdaptiveChess.exe with _internal beside
it. No Python, Qt or Stockfish installation is needed.

Known limits: simplified explanations describe the same verified engine examples as the
professional view, not every possible defense. Missing older evidence is acknowledged.
Automated Windows checks verify executable behavior and rendering; subjective reading on a
physical display remains useful. The level is an internal Adaptive Chess Rating.
