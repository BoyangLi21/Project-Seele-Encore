"""Assemble rendered review frames into a labelled MP4.

python make_review_video.py --ffmpeg ffmpeg.exe --spec review.json

review.json (UTF-8):
{"out": "...mp4", "fps": 30, "grid": "",            # "" = side by side, "2x2" for four views
 "title": "...", "views": [{"dir": "...", "label": "..."}],
 "segments": [[start_s, end_s, "label"], ...]}

Labels go through UTF-8 text files (drawtext textfile=) so Chinese survives
the Windows command line.
"""

import argparse
import json
import os
import subprocess
import tempfile

FONT = "C\\:/Windows/Fonts/msyh.ttc"


def text_file(tmp, text):
    fd, path = tempfile.mkstemp(suffix=".txt", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path.replace("\\", "/").replace(":", "\\:")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ffmpeg", required=True)
    ap.add_argument("--spec", required=True)
    a = ap.parse_args()
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    fps = spec.get("fps", 30)
    tmp = tempfile.mkdtemp(prefix="review_text_")
    cmd = [a.ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    parts = []
    for i, v in enumerate(spec["views"]):
        cmd += ["-framerate", str(fps), "-i", v["dir"].rstrip("/") + "/f%05d.png"]
        parts.append(f"[{i}:v]drawtext=fontfile='{FONT}':textfile='{text_file(tmp, v['label'])}':x=20:y=h-46:"
                     f"fontsize=26:fontcolor=white:box=1:boxcolor=black@0.45:boxborderw=8[v{i}]")
    n = len(spec["views"])
    if n == 1:
        stack = "[v0]null[s]"
    elif spec.get("grid") == "2x2" and n == 4:
        stack = "[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[s]"
    else:
        stack = "".join(f"[v{i}]" for i in range(n)) + f"hstack=inputs={n}[s]"
    tail = []
    if spec.get("title"):
        tail.append(f"drawtext=fontfile='{FONT}':textfile='{text_file(tmp, spec['title'])}':x=20:y=18:fontsize=30:"
                    f"fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=10")
    for s0, s1, label in spec.get("segments", []):
        tail.append(f"drawtext=fontfile='{FONT}':textfile='{text_file(tmp, label)}':x=(w-text_w)/2:y=70:"
                    f"fontsize=36:fontcolor=yellow:box=1:boxcolor=black@0.5:boxborderw=10:"
                    f"enable='between(t,{s0},{s1})'")
    graph = ";".join(parts + [stack]) + (";[s]" + ",".join(tail) + "[o]" if tail else "")
    cmd += ["-filter_complex", graph, "-map", "[o]" if tail else "[s]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "20", "-preset", "medium", "-movflags", "+faststart", spec["out"]]
    subprocess.run(cmd, check=True)
    print("wrote", spec["out"])


if __name__ == "__main__":
    main()
