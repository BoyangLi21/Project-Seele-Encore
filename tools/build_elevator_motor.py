"""Synthesize the quiet traction motor for the native passenger elevators."""
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np

RATE = 48000


def main():
    # All frequencies complete a whole number of cycles over the eight-second loop.
    t = np.arange(8 * RATE) / RATE
    phase = 2 * np.pi * t
    shaft = 52 * phase + 0.14 * np.sin(0.5 * phase)
    hum = 0.11 * np.sin(shaft) + 0.09 * np.sin(shaft * 2) + 0.048 * np.sin(shaft * 4)
    whirr = 0.024 * np.sin(shaft * 8 + 0.25 * np.sin(3 * phase))
    samples = (hum + whirr) * (0.95 + 0.05 * np.cos(0.75 * phase))
    out = Path(__file__).resolve().parents[1] / "src/main/resources/assets/projectseele/sounds/elevator_motor.ogg"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-f", "f32le",
                    "-ar", str(RATE), "-ac", "1", "-i", "-", "-c:a", "libvorbis", "-q:a", "5",
                    str(out)], input=samples.astype("<f4").tobytes(), check=True)


if __name__ == "__main__":
    main()
