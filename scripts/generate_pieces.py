"""Generate original, font-independent vector pieces (project artwork under GPL-3.0)."""
from pathlib import Path

SHAPES = {
 'pawn': '<circle cx="30" cy="15" r="7"/><path d="M24 24 Q30 21 36 24 Q32 30 37 39 L41 44 H19 L23 39 Q28 30 24 24 Z"/>',
 'rook': '<path d="M16 10 H22 V16 H27 V10 H33 V16 H38 V10 H44 V24 L39 27 V39 L44 44 H16 L21 39 V27 L16 24 Z"/><path d="M21 27 H39 M21 36 H39" fill="none"/>',
 'knight': '<path d="M17 44 L20 35 L30 27 L24 23 L16 26 L12 20 L24 10 L25 5 L33 11 Q44 17 42 31 L40 44 Z"/><circle cx="27" cy="16" r="1.5" fill="currentColor"/><path d="M24 10 L32 13 M20 35 L34 31" fill="none"/>',
 'bishop': '<path d="M30 6 Q15 19 22 25 Q26 29 25 34 L20 40 L16 44 H44 L40 40 L35 34 Q34 29 38 25 Q45 19 30 6 Z"/><path d="M27 13 L34 22 M23 32 H37" fill="none"/>',
 'queen': '<path d="M18 19 L25 25 L30 13 L35 25 L42 19 L37 35 L41 44 H19 L23 35 Z"/><circle cx="17" cy="15" r="3"/><circle cx="30" cy="9" r="3"/><circle cx="43" cy="15" r="3"/><path d="M23 35 H37" fill="none"/>',
 'king': '<path d="M30 5 V18 M24 10 H36" fill="none" stroke-width="3.5"/><path d="M23 19 Q14 16 16 25 L23 35 L19 44 H41 L37 35 L44 25 Q46 16 37 19 Q30 15 23 19 Z"/><path d="M23 35 H37" fill="none"/>',
}
ROOT = Path(__file__).resolve().parents[1] / 'resources/pieces'
for color, fill, stroke in [('white', '#fffaf0', '#283445'), ('black', '#243041', '#e2e7ef')]:
 for name, shapes in SHAPES.items():
  svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60"><g fill="{fill}" stroke="{stroke}" color="{stroke}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round">{shapes}<path d="M16 45 H44 L46 51 H14 Z"/></g></svg>'
  (ROOT / f'{color}-{name}.svg').write_text(svg, encoding='utf-8')
