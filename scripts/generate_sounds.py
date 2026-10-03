"""Original short, quiet wood/felt cues; deterministic PCM audio with no external assets."""
from __future__ import annotations

import math
from pathlib import Path
import random
import struct
import wave

ROOT = Path(__file__).resolve().parents[1] / 'resources/sounds'
SAMPLE_RATE = 44100
# Each component is (start seconds, frequency, duration, relative amplitude).
CUES = {
    'move': (0.12, [(0, 520, .09, .65), (.008, 890, .075, .18)]),
    'capture': (0.17, [(0, 310, .12, .7), (.025, 670, .10, .25)]),
    'check': (0.23, [(0, 740, .12, .45), (.085, 990, .12, .35)]),
    'end': (0.36, [(0, 520, .18, .4), (.09, 650, .18, .3), (.17, 780, .16, .3)]),
}


def generate():
    ROOT.mkdir(parents=True, exist_ok=True)
    for index, (name, (duration, tones)) in enumerate(CUES.items()):
        rng = random.Random(420 + index)
        samples = []
        previous_noise = 0.0
        for i in range(round(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            value = 0.0
            for start, frequency, length, amplitude in tones:
                local = t - start
                if 0 <= local <= length:
                    attack = min(1, local / .004)
                    release = min(1, (length - local) / .02)
                    envelope = attack * release * math.exp(-local * 35)
                    value += amplitude * envelope * (math.sin(2 * math.pi * frequency * local) + .15 * math.sin(2 * math.pi * frequency * 2.13 * local))
            previous_noise = .7 * previous_noise + .3 * rng.uniform(-1, 1)
            noise = previous_noise * .18 * min(1, t / .003) * math.exp(-t * 80)
            # Conservative -15 dBFS peak before QSoundEffect's additional volume reduction.
            samples.append(round(max(-1, min(1, (value + noise) * .18)) * 32767))
        with wave.open(str(ROOT / f'{name}.wav'), 'wb') as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(SAMPLE_RATE)
            file.writeframes(struct.pack(f'<{len(samples)}h', *samples))


if __name__ == '__main__':
    generate()
