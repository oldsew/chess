Adaptive Chess 0.5.1 — a quieter desktop interface, substantial pieces and clearer teaching.

- Neutral teaching fallback: when short engine evaluations disagree, recommendations no longer
  claim a higher score. Observable board geometry does not assert an unproved contribution to evaluation.
- Original Staunton-inspired SVG set with wider turned bases and bodies, stronger crowns,
  warm ivory and graphite surfaces, soft gradients, ambient shading and restrained highlights.
  All twelve vectors remain lightweight, filter-free and bundled in the portable package.
- Unified neutral graphite/warm-grey UI, gently raised buttons with hover/pressed/disabled
  states, consistent panels and clocks. Live position text gains seven semantic color levels;
  the existing user perspective and hysteresis determine both words and colors.
- Adjacent history positions animate forward and backward over 250 ms, including captured
  pieces returning, en passant, both castling pieces and promotion. Rapid input safely replaces
  the current transition. Multi-ply jumps and returning to the latest position remain immediate.
  Reviewing a historical mate never repeats the result pulse. PGN and actual clocks never rewind.
- Offline analysis separates what happened from why the recommended move is better. Material
  and mate explanations reuse existing legal PV evidence. Development, center, open-file and
  check ideas state observable board facts; unknown causes remain neutral. No extra engine/API
  calls, no mandatory LLM, and no additional dependency.
- Selecting a significant mistake shows the position before it with two restrained arrows.
  Short recommendation lines animate in both directions; returning to the actual played
  position never edits PGN. Old saved analyses remain readable, with ideas reconstructed where
  prior PV evidence is available. Developer Mode includes explanation type, confidence,
  detected motif, material delta, chosen recommendation, PV and factors.
- Small-window layout keeps clocks and history controls visible. Setup/move rows and teaching
  content scroll as needed. Extra captions hide at low height. All three DPI smoke processes
  check a 1366x768 physical workspace at 100%, 125% and 150%, with screenshots as evidence.
- Adaptive rating/behavior profiles, selection, final engine calculations, clock/session logic,
  SQLite data and custom WAV sounds are retained unchanged. No schema migration or data reset.

Validation: 204 regression tests, plus ten actual-executable smoke stages, including the seven
existing gameplay/restore/engine/audio/learning stages and three DPI/visual stages. Each new
stage observes intermediate frames for fourteen forward/backward transitions, verifies rapid
navigation, semantic colors, before-move highlights, both-color explanations and read-only PV
review. The release contains Windows portable, corresponding source and SHA256SUMS.txt.

Extract the entire AdaptiveChess-Windows-x64.zip and open AdaptiveChess/AdaptiveChess.exe.
Keep _internal beside the executable. No Python/Qt/Stockfish install is needed.

Known limits: teaching intentionally favors verified short-line facts over speculative strategy.
Long descriptions and move rows use scrolling at high DPI. Automated offscreen rendering checks
layout, resources and behavior, not subjective beauty or physical monitor appearance. Audio
resources, decoding and mute are verified; physical Windows listening is a separate manual check.
The displayed level remains an internal Adaptive Chess Rating, not certified FIDE/online Elo.
