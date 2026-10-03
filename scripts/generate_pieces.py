"""Original ivory/graphite chess set. Qt-compatible vector layers, without filters or 3D."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'resources/pieces'
# A shared turned foot and neck vocabulary makes every silhouette part of one quiet set.
SHAPES = {
    'pawn': '''<path d="M26 39 Q22 38 24 35 Q36 32 48 35 Q50 38 46 39 C42 42 42 48 46 52 L50 58 H22 L26 52 C30 48 30 42 26 39 Z"/>
      <ellipse cx="36" cy="26" rx="11.5" ry="11" fill="url(#sphere)"/>
      <path d="M28 21 Q31 17 37 17 M27 36 Q36 39 45 36 M30 42 Q34 46 28 52 M26 56 Q36 59 46 56" fill="none" stroke="url(#rim)"/>
      <path d="M42 41 Q40 47 46 53" fill="none" stroke="url(#shade)" stroke-width="2"/>''',
    'rook': '''<path d="M16 14 H25 V22 H31 V14 H41 V22 H47 V14 H56 V30 Q53 33 49 34 L49 49 Q49 53 53 58 H19 Q23 53 23 49 V34 Q19 33 16 30 Z"/>
      <path d="M17 28 Q36 31 55 28 L53 34 Q36 38 19 34 Z"/>
      <path d="M20 16 V26 M27 38 V49 Q27 52 24 55 M22 56 Q36 60 50 56" fill="none" stroke="url(#rim)"/>
      <path d="M45 38 V49 Q45 53 48 55" fill="none" stroke="url(#shade)" stroke-width="2"/>''',
    'knight': '''<path d="M19 58 C20 48 26 42 34 38 L40 35 Q36 28 29 28 L23 34 Q19 36 15 32 L11 28 Q10 26 13 23 L25 15 L27 9 Q28 7 31 11 L37 15 C49 14 58 24 60 37 C61 47 55 54 52 58 Z"/>
      <path d="M36 19 C47 19 54 28 55 38 Q56 47 48 54" fill="none" stroke="url(#shade)" stroke-width="4"/>
      <path d="M29 18 Q45 16 52 30 M27 46 Q32 40 38 39 M26 26 L31 23 M24 56 Q37 60 49 56" fill="none" stroke="url(#rim)"/>
      <path d="M39 22 L43 26 M43 29 L47 33 M46 36 L49 40" fill="none" stroke="url(#rim)" stroke-opacity=".5"/>
      <circle cx="31" cy="23" r="1.9" fill="url(#ink)" stroke="none"/>
      <path d="M13 28 Q17 30 20 28" fill="none" stroke-width=".8"/>''',
    'bishop': '''<path d="M36 11 C30 16 19 22 19 29 C19 35 26 39 30 40 C30 46 26 53 21 58 H51 C46 53 42 46 42 40 C46 39 53 35 53 29 C53 22 42 16 36 11 Z"/>
      <circle cx="36" cy="10" r="3.5" fill="url(#sphere)"/>
      <path d="M32 18 L40 29" fill="none" stroke="url(#ink)" stroke-width="3"/>
      <path d="M26 23 Q22 29 27 33 M25 36 Q36 40 47 36 M30 44 Q31 49 25 54" fill="none" stroke="url(#rim)"/>
      <path d="M26 40 Q36 43 46 40 L46 44 Q36 47 26 44 Z"/>
      <path d="M25 56 Q36 60 47 56" fill="none" stroke="url(#rim)"/>''',
    'queen': '''<path d="M15 22 L25 30 L28 19 L33 27 L36 13 L39 27 L44 19 L47 30 L57 22 L49 39 Q44 43 45 49 Q46 54 53 58 H19 Q26 54 27 49 Q28 43 23 39 Z"/>
      <circle cx="36" cy="10" r="3.5" fill="url(#sphere)"/>
      <circle cx="15" cy="19" r="3.7" fill="url(#sphere)"/><circle cx="28" cy="16" r="3" fill="url(#sphere)"/>
      <circle cx="44" cy="16" r="3" fill="url(#sphere)"/><circle cx="57" cy="19" r="3.7" fill="url(#sphere)"/>
      <path d="M23 37 Q36 42 49 37 L47 43 Q36 47 25 43 Z"/>
      <path d="M23 29 L27 35 M27 40 Q36 43 45 40 M30 47 Q30 51 25 55 M24 56 Q36 60 48 56" fill="none" stroke="url(#rim)"/>
      <path d="M43 46 Q42 51 47 54" fill="none" stroke="url(#shade)" stroke-width="2"/>''',
    'king': '''<path d="M33 5 H39 V12 H46 V18 H39 V25 H33 V18 H26 V12 H33 Z"/>
      <path d="M36 27 C27 20 17 23 17 31 C17 37 24 41 28 45 Q31 51 20 58 H52 Q41 51 44 45 C48 41 55 37 55 31 C55 23 45 20 36 27 Z"/>
      <path d="M24 42 Q36 47 48 42 L46 48 Q36 52 26 48 Z"/>
      <path d="M35 7 V14 H28 M23 28 Q20 33 28 39 M27 45 Q36 48 44 45 M30 51 L26 55 M24 56 Q36 60 48 56" fill="none" stroke="url(#rim)"/>
      <path d="M48 28 Q52 33 44 40" fill="none" stroke="url(#shade)" stroke-width="2"/>''',
}
BASE = '''<path d="M22 58 Q36 56 50 58 L53 62 Q36 67 19 62 Z"/>
  <path d="M22 64 Q36 67 50 64 Q52 67 58 71 Q36 79 14 71 Q20 67 22 64 Z"/>
  <path d="M18 70 Q36 77 54 70 L58 73 Q36 81 14 73 Z"/>
  <path d="M23 60 Q36 63 49 60 M24 66 Q36 71 49 66 M19 73 Q36 78 53 73" fill="none" stroke="url(#rim)" stroke-width="1"/>
  <path d="M23 64 Q36 68 49 64" fill="none" stroke="url(#shade)" stroke-width="1"/>'''


def generate():
    for color in ['white', 'black']:
        white = color == 'white'
        palette = ['#fffaf0', '#f1e7d4', '#c9bda7', '#e2d6c0'] if white else ['#71736f', '#444743', '#20231f', '#42463e']
        outline = '#807361' if white else '#191d17'
        rim = '#fffef8' if white else '#c4c8bb'
        sphere = ['#fffdf6', '#eee1cb', '#beb097'] if white else ['#92958a', '#4b5046', '#23271f']
        defs = f'''<defs>
  <linearGradient id="body" x1="12" y1="10" x2="61" y2="74" gradientUnits="userSpaceOnUse">
    <stop stop-color="{palette[0]}"/><stop offset=".34" stop-color="{palette[1]}"/>
    <stop offset=".78" stop-color="{palette[2]}"/><stop offset="1" stop-color="{palette[3]}"/>
  </linearGradient>
  <radialGradient id="sphere" cx=".32" cy=".24" r=".83">
    <stop stop-color="{sphere[0]}"/><stop offset=".56" stop-color="{sphere[1]}"/><stop offset="1" stop-color="{sphere[2]}"/>
  </radialGradient>
  <linearGradient id="rim" x1="0" y1="0" x2=".8" y2="1">
    <stop stop-color="{rim}" stop-opacity=".7"/><stop offset="1" stop-color="{rim}" stop-opacity=".16"/>
  </linearGradient>
  <linearGradient id="shade"><stop stop-color="{outline}" stop-opacity=".5"/><stop offset="1" stop-color="{outline}" stop-opacity=".15"/></linearGradient>
  <linearGradient id="ink"><stop stop-color="{outline}"/><stop offset="1" stop-color="{outline}"/></linearGradient>
  <radialGradient id="shadow"><stop stop-color="#181c13" stop-opacity=".24"/><stop offset="1" stop-color="#181c13" stop-opacity="0"/></radialGradient>
</defs>'''
        for name, shapes in SHAPES.items():
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 82">
{defs}
<ellipse cx="37" cy="76" rx="29" ry="4.5" fill="url(#shadow)"/>
<g fill="url(#body)" stroke="{outline}" stroke-width="1.05" stroke-linejoin="round" stroke-linecap="round">
{shapes}
{BASE}
</g>
</svg>
'''
            (ROOT / f'{color}-{name}.svg').write_text(svg, encoding='utf-8')


if __name__ == '__main__':
    generate()
