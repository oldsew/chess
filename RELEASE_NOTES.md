Adaptive Chess 0.6.0 — concrete explanations of mistakes and distinct alternative ideas.

- Teachable mistakes now receive a separate comparison of the played move and up to three
  engine recommendations at the same fixed depth (up to 16), sharing the existing background
  Stockfish service. Legal explanatory lines retain 6–10 plies; the UI shows at most six.
  A shorter line is accepted when the game ends. Candidate-discovery scores never substitute
  for matched-depth scores. Short transposition PVs are extended with verified engine moves.
- Explanations compare resulting positions: material, profitable legal capture threats,
  mobility, king cover, castling rights, development, central control, pawn structure and
  passed pawns. Legal-PV tactics identify forks, absolute/relative pins, double and discovered
  attacks, and deflection of an overloaded defender. Equal exchanges, pinned illegal captures,
  old pins, invalid PVs and possible compensation cannot support a confident material claim.
- Mistake review separates why the move was bad, the opponent's concrete continuation,
  the best alternative and other possibilities. Each alternative has its own position evidence
  and response. Choosing it synchronizes the explanation, arrow and key-square highlights.
  Variation review remains read-only and never changes the original PGN or clocks.
- Confidence controls the strength of claims. Neutral fallback follows feature/PV checks;
  conflicting comparable scores explicitly avoid a made-up cause. Mate scores remain separate
  and do not hide a verified tactical material loss. Developer Mode exposes all requested
  feature deltas, detected tactic, full PV, confidence and each achieved comparison depth.
- Existing rating calculations, opponent behavior profiles, move selection, base CPL/accuracy,
  database schema, clocks, history, SVG pieces and custom sounds are retained. No dependency
  added and no user data migration required. Older saved analyses remain readable.

Validation: 237 regression tests and eleven actual-executable smoke stages. The new stage
runs production analysis on twelve reproducible PGN games for both player colors, verifies
matched depths and legal longer PVs, checks that one engine process and the GUI event loop
remain active, and exercises synchronized alternative review in the packaged executable.
Existing tests and all prior gameplay, restart, audio, animation and 100/125/150% DPI smoke
stages remain in the release pipeline. Corpus results and UI screenshots accompany CI evidence.

The release contains AdaptiveChess-Windows-x64.zip, AdaptiveChess_Source.zip and SHA256SUMS.txt.
Extract the entire Windows ZIP and open AdaptiveChess/AdaptiveChess.exe with _internal beside
it. No Python, Qt or Stockfish installation is needed.

Known limits: local feature comparisons explain observable differences, not a guaranteed unique
strategic cause. Engine PVs illustrate strong responses, not every possible defense. Deeper
teaching comparisons add background analysis work only for significant mistakes. Automated
Windows checks cover rendering, resources and behavior; they do not replace physical listening
or subjective review on a monitor. The level remains an internal Adaptive Chess Rating.
