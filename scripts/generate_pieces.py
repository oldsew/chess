"""Original ivory/graphite chess set. Qt-compatible vector layers, without filters or 3D."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'resources/pieces'
# A shared turned foot and neck vocabulary makes every silhouette part of one quiet set.
SHAPES = {
    'pawn': '''<path d="M30 38 C33 42 33 45 32 49 C31 53 28 56 26 58 H46 C44 56 41 53 40 49 C39 45 39 42 42 38 Z"/>
      <path d="M28 37 Q36 40 44 37 L43 40 Q36 43 29 40 Z"/>
      <circle cx="36" cy="28" r="9" fill="url(#sphere)"/>
      <path d="M31 24 C32 22 34 21 37 21 M32 43 C34 48 32 52 30 54" fill="none" stroke="url(#rim)"/>
      <path d="M28 57 Q36 59 44 57" fill="none" stroke="url(#rim)"/>''',
    'rook': '''<path d="M21 13 Q24 12 28 13 V21 H33 V13 H39 V21 H44 V13 Q48 12 51 13 V28 Q48 31 44 33 L45 50 Q45 54 49 58 H23 Q27 54 27 50 L28 33 Q24 31 21 28 Z"/>
      <path d="M22 27 Q36 30 50 27 L49 31 Q36 35 23 31 Z"/>
      <path d="M24 15 V24 M30 36 L29 49 Q29 53 27 55 M28 55 Q36 57 44 55" fill="none" stroke="url(#rim)"/>
      <path d="M43 35 L44 50" fill="none" stroke="url(#shade)" stroke-width="1.7"/>''',
    'knight': '''<path d="M23 58 C24 50 28 45 35 41 L41 37 C39 32 35 29 30 28 L24 33 Q22 34 19 32 L14 29 Q13 27 15 24 L27 16 L29 10 Q30 8 32 11 L37 15 C48 15 55 24 56 36 C58 45 53 51 49 58 Z"/>
      <path d="M35 18 C46 19 51 27 51 37 C52 44 48 49 45 53" fill="none" stroke="url(#shade)" stroke-width="3.2"/>
      <path d="M31 18 C43 17 50 26 51 34 M28 46 Q33 41 38 40 M26 27 L31 24" fill="none" stroke="url(#rim)"/>
      <path d="M39 21 L43 24 M43 27 L46 30 M45 34 L47 37" fill="none" stroke="url(#rim)" stroke-opacity=".55"/>
      <circle cx="32.5" cy="23" r="1.7" fill="url(#ink)" stroke="none"/>
      <path d="M16 28 Q19 29 21 28" fill="none" stroke-width=".8"/>
      <path d="M27 56 Q37 58 47 56" fill="none" stroke="url(#rim)"/>''',
    'bishop': '''<path d="M36 10 C32 14 23 20 23 28 C23 33 27 36 32 38 C32 45 30 51 25 58 H47 C42 51 40 45 40 38 C45 36 49 33 49 28 C49 20 40 14 36 10 Z"/>
      <circle cx="36" cy="9" r="3" fill="url(#sphere)"/>
      <path d="M33 17 L40 28" fill="none" stroke="url(#ink)" stroke-width="2.5"/>
      <path d="M29 20 Q25 25 27 29 M28 34 Q34 37 40 35 M31 42 C33 47 30 52 29 54" fill="none" stroke="url(#rim)"/>
      <path d="M30 38 Q36 40 42 38 L42 41 Q36 43 30 41 Z"/>
      <path d="M28 56 Q36 58 44 56" fill="none" stroke="url(#rim)"/>''',
    'queen': '''<path d="M20 22 L28 29 L31 20 L34 27 L36 13 L38 27 L41 20 L44 29 L52 22 L46 39 C42 44 42 51 49 58 H23 C30 51 30 44 26 39 Z"/>
      <circle cx="36" cy="10" r="3" fill="url(#sphere)"/>
      <circle cx="20" cy="19" r="3.2" fill="url(#sphere)"/>
      <circle cx="31" cy="17" r="2.6" fill="url(#sphere)"/>
      <circle cx="41" cy="17" r="2.6" fill="url(#sphere)"/>
      <circle cx="52" cy="19" r="3.2" fill="url(#sphere)"/>
      <path d="M26 38 Q36 41 46 38 L45 42 Q36 45 27 42 Z"/>
      <path d="M27 30 L30 36 M29 40 Q36 42 43 40 M32 46 Q32 51 29 54 M28 56 Q36 58 44 56" fill="none" stroke="url(#rim)"/>''',
    'king': '''<path d="M33.5 5 H38.5 V12 H45 V17 H38.5 V26 H33.5 V17 H27 V12 H33.5 Z"/>
      <path d="M36 28 C29 21 21 24 21 30 C20 35 25 39 29 43 C32 49 29 54 23 58 H49 C43 54 40 49 43 43 C47 39 52 35 51 30 C51 24 43 21 36 28 Z"/>
      <path d="M28 42 Q36 45 44 42 L43 46 Q36 49 29 46 Z"/>
      <path d="M35 7 V13 H29 M25 28 Q23 32 28 37 M29 44 Q36 46 42 44 M31 49 Q32 52 29 55 M28 56 Q36 58 44 56" fill="none" stroke="url(#rim)"/>''',
}
BASE = '''<path d="M25 58 Q36 56 47 58 L49 61 Q36 65 23 61 Z"/>
  <path d="M25 63 Q36 65 47 63 C48 66 51 68 53 71 Q36 77 19 71 C21 68 24 66 25 63 Z"/>
  <path d="M23 69 Q36 73 49 69 L53 72 Q36 78 19 72 Z"/>
  <path d="M26 60 Q36 62 46 60 M26 65 Q35 68 46 65 M23 72 Q36 75 49 72" fill="none" stroke="url(#rim)" stroke-width=".9"/>
  <path d="M26 63 Q36 66 46 63" fill="none" stroke="url(#shade)" stroke-width=".8"/>'''


def generate():
    for color in ['white', 'black']:
        white = color == 'white'
        palette = ['#fffaf0', '#f1e7d4', '#c9bda7', '#e2d6c0'] if white else ['#687482', '#394656', '#182230', '#3a4858']
        outline = '#807361' if white else '#14202e'
        rim = '#fffef8' if white else '#bdc8d4'
        sphere = ['#fffdf6', '#eee1cb', '#beb097'] if white else ['#82909f', '#435264', '#192534']
        defs = f'''<defs>
  <linearGradient id="body" x1="19" y1="18" x2="57" y2="65" gradientUnits="userSpaceOnUse">
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
  <radialGradient id="shadow"><stop stop-color="#0c1420" stop-opacity=".24"/><stop offset="1" stop-color="#0c1420" stop-opacity="0"/></radialGradient>
</defs>'''
        for name, shapes in SHAPES.items():
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 82">
{defs}
<ellipse cx="37" cy="76" rx="25" ry="4.5" fill="url(#shadow)"/>
<g fill="url(#body)" stroke="{outline}" stroke-width="1.05" stroke-linejoin="round" stroke-linecap="round">
{shapes}
{BASE}
</g>
</svg>
'''
            (ROOT / f'{color}-{name}.svg').write_text(svg, encoding='utf-8')


if __name__ == '__main__':
    generate()
