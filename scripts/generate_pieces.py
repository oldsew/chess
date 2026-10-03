"""Original ivory/graphite SVG artwork; gradients and layered shadows need no SVG filters."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'resources/pieces'
# Sculpted silhouettes share a turned pedestal; highlights follow the surface, not the square.
SHAPES = {
    'pawn': '''<circle cx="36" cy="20" r="10" fill="url(#sphere)"/>
      <path d="M30 30 Q36 32 42 30 L44 34 Q39 41 41 48 Q42 53 48 59 H24 Q30 53 31 48 Q33 41 28 34 Z"/>
      <path d="M30 34 Q36 36 42 34 M28 57 Q36 59 44 57" fill="none" stroke="url(#rim)"/>''',
    'rook': '''<path d="M21 12 H28 V19 H33 V12 H39 V19 H44 V12 H51 V28 Q48 31 45 33 L46 53 L51 59 H21 L26 53 L27 33 Q24 31 21 28 Z"/>
      <path d="M23 28 Q36 32 49 28 M28 35 V50 M28 54 Q36 56 44 54" fill="none" stroke="url(#rim)"/>''',
    'knight': '''<path d="M22 59 Q24 48 33 43 L42 38 Q37 30 29 28 L23 33 L15 30 L14 24 L29 13 L29 7 L38 13 Q52 15 55 30 Q59 45 51 59 Z"/>
      <path d="M31 17 Q45 16 50 29 Q54 42 47 53 M24 27 L32 22 M30 49 Q36 45 42 43" fill="none" stroke="url(#rim)"/>
      <circle cx="33" cy="22" r="1.8" fill="url(#ink)" stroke="none"/>
      <path d="M16 27 L21 27" fill="none"/>''',
    'bishop': '''<path d="M36 9 Q21 20 23 29 Q24 35 32 37 Q32 46 28 51 L23 59 H49 L44 51 Q40 46 40 37 Q48 35 49 29 Q51 20 36 9 Z"/>
      <circle cx="36" cy="8" r="3.2" fill="url(#sphere)"/>
      <path d="M32 18 L40 28" fill="none" stroke="url(#ink)" stroke-width="2.3"/>
      <path d="M28 31 Q31 34 35 34 M31 41 Q36 43 41 41 M28 55 Q36 57 44 55" fill="none" stroke="url(#rim)"/>''',
    'queen': '''<path d="M21 22 L29 30 L36 17 L43 30 L51 22 L46 41 Q42 45 44 52 L50 59 H22 L28 52 Q30 45 26 41 Z"/>
      <circle cx="20" cy="19" r="3.7" fill="url(#sphere)"/>
      <circle cx="36" cy="13" r="4.1" fill="url(#sphere)"/>
      <circle cx="52" cy="19" r="3.7" fill="url(#sphere)"/>
      <path d="M27 39 Q36 42 45 39 M29 45 Q36 47 43 45 M28 55 Q36 57 44 55" fill="none" stroke="url(#rim)"/>''',
    'king': '''<path d="M33 5 H39 V12 H46 V18 H39 V26 H33 V18 H26 V12 H33 Z"/>
      <path d="M36 27 Q26 20 21 27 Q16 33 27 42 Q30 47 28 52 L22 59 H50 L44 52 Q42 47 45 42 Q56 33 51 27 Q46 20 36 27 Z"/>
      <path d="M24 29 Q22 34 29 39 M28 42 Q36 45 44 42 M28 55 Q36 57 44 55" fill="none" stroke="url(#rim)"/>''',
}
BASE = '''<path d="M24 58 Q36 56 48 58 L51 62 Q36 66 21 62 Z"/>
  <path d="M23 63 Q36 65 49 63 L53 68 Q36 73 19 68 Z"/>
  <path d="M21 68 Q36 71 51 68 L55 73 Q36 78 17 73 Z"/>
  <path d="M24 60 Q35 62 48 60 M23 66 Q36 69 49 66 M21 72 Q36 75 51 72" fill="none" stroke="url(#rim)" stroke-width="1"/>'''

for color in ['white', 'black']:
    white = color == 'white'
    palette = ['#fffef8', '#f5ecd9', '#c7bba5', '#ebe0cb'] if white else ['#626e7c', '#303c4c', '#151d29', '#424d5b']
    outline = '#756c5b' if white else '#121a24'
    rim = '#fffcf2' if white else '#a9b5c5'
    sphere = ['#fffefb', '#eee2ce', '#bdaf95'] if white else ['#788492', '#354252', '#141d29']
    defs = f'''<defs>
      <linearGradient id="body" x1="17" y1="20" x2="56" y2="28" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="{palette[0]}"/><stop offset=".3" stop-color="{palette[1]}"/>
        <stop offset=".78" stop-color="{palette[2]}"/><stop offset="1" stop-color="{palette[3]}"/>
      </linearGradient>
      <radialGradient id="sphere" cx=".32" cy=".25" r=".8">
        <stop stop-color="{sphere[0]}"/><stop offset=".55" stop-color="{sphere[1]}"/><stop offset="1" stop-color="{sphere[2]}"/>
      </radialGradient>
      <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1">
        <stop stop-color="{rim}" stop-opacity=".8"/><stop offset="1" stop-color="{rim}" stop-opacity=".12"/>
      </linearGradient>
      <linearGradient id="ink"><stop stop-color="{outline}"/><stop offset="1" stop-color="{outline}"/></linearGradient>
      <radialGradient id="shadow"><stop stop-color="#0c1420" stop-opacity=".3"/><stop offset="1" stop-color="#0c1420" stop-opacity="0"/></radialGradient>
    </defs>'''
    for name, shapes in SHAPES.items():
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 82">
{defs}
<ellipse cx="37" cy="76" rx="27" ry="5.5" fill="url(#shadow)"/>
<g fill="url(#body)" stroke="{outline}" stroke-width="1.15" stroke-linejoin="round" stroke-linecap="round">
{shapes}{BASE}
</g></svg>'''
        (ROOT / f'{color}-{name}.svg').write_text(svg, encoding='utf-8')
