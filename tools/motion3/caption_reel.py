"""Burn reel labels (labels.json from render_moveset_reel.py) into the frames and encode an MP4.

python caption_reel.py --frames <dir> --ffmpeg ffmpeg.exe --out reel.mp4 [--title "..."] [--font msyh.ttc]
"""

import argparse
import json
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--ffmpeg", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--font", default="C:/Windows/Fonts/msyh.ttc")
    a = ap.parse_args()
    with open(os.path.join(a.frames, "labels.json"), encoding="utf-8") as f:
        meta = json.load(f)
    fps, labels = meta["fps"], meta["labels"]
    big = ImageFont.truetype(a.font, 30)
    small = ImageFont.truetype(a.font, 18)
    work = tempfile.mkdtemp(prefix="caption_")
    frames = sorted(x for x in os.listdir(a.frames) if x.startswith("f") and x.endswith(".png"))
    for k, name in enumerate(frames):
        fi = str(int(name[1:-4]))
        img = Image.open(os.path.join(a.frames, name)).convert("RGB")
        d = ImageDraw.Draw(img)
        text = labels.get(fi, "")
        x, y = 18, img.height - 58
        d.rectangle([x - 10, y - 8, x + d.textlength(text, font=big) + 12, y + 42], fill=(0, 0, 0))
        d.text((x, y), text, font=big, fill=(255, 255, 255))
        if a.title:
            d.text((18, 12), a.title, font=small, fill=(30, 30, 30))
        d.text((img.width - 110, 12), f"{int(fi) / fps:6.2f}s", font=small, fill=(30, 30, 30))
        img.save(os.path.join(work, f"c{k:05d}.png"))
    subprocess.run([a.ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps), "-i",
                    os.path.join(work, "c%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", a.out],
                   check=True)
    print("wrote", a.out, len(frames), "frames")


if __name__ == "__main__":
    main()
