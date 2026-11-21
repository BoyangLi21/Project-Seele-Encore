"""Export the six-face survey's applied MCA delta as a final worldgen decoration pass."""
import argparse
import gzip
import struct
from collections import defaultdict
from pathlib import Path

import numpy as np


def pack_region(source, destination):
    with np.load(source, allow_pickle=False) as data:
        sections, lengths, rows, names = (data[key] for key in ("sections", "lengths", "rows", "states"))
    used = np.unique(rows[:, 1:])
    palette = [str(names[i]).encode("ascii") for i in used]
    if not 0 < len(palette) <= 255:
        raise ValueError(f"Unexpected state palette in {source}")
    ids = {int(original): index for index, original in enumerate(used)}
    chunks = defaultdict(list)
    cursor = 0
    for (cx, cz, sy), count in zip(sections, lengths, strict=True):
        size = int(count)
        changes = rows[cursor:cursor + size]
        cursor += size
        runs = bytearray()
        for local, old, new in sorted(changes.tolist(), key=lambda r: (r[0] & 255, r[0] >> 8)):
            xz, y = local & 255, local >> 8
            before, after = ids[old], ids[new]
            if (runs and runs[-4] == xz and (runs[-3] & 15) + 1 == y
                    and runs[-2] == before and runs[-1] == after):
                runs[-3] = runs[-3] & 240 | y
            else:
                runs.extend((xz, y * 17, before, after))
        chunks[(int(cz) & 31) * 32 + (int(cx) & 31)].append((int(sy), runs))
    if cursor != len(rows):
        raise ValueError(f"Section counts disagree in {source}")
    payload = bytearray(struct.pack(">H", len(palette)))
    for name in palette:
        payload.extend(struct.pack(">H", len(name)) + name)
    payload.extend(struct.pack(">H", len(chunks)))
    for idx, sections in sorted(chunks.items()):
        payload.extend(struct.pack(">HHB", idx, 0, len(sections)))
        for sy, runs in sorted(sections):
            payload.extend(struct.pack(">bH", sy, len(runs) // 4) + runs)
    destination.write_bytes(gzip.compress(bytes(payload), compresslevel=6, mtime=0))
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    coords = []
    count = 0
    for source in sorted(args.release.glob("r.*.*.delta.npz")):
        _, x, z, _, _ = source.name.split(".")
        coords.append((int(x), int(z)))
        count += pack_region(source, args.output / f"{x}_{z}.bin.gz")
    if not coords:
        raise ValueError("No face repair deltas found")
    members = b"".join(struct.pack(">hh", *pos) for pos in coords)
    (args.output / "index.bin").write_bytes(struct.pack(">IH", 0x534C3634, len(coords)) + members)
    print(f"{count:,} changed blocks in {len(coords)} regions")


if __name__ == "__main__":
    main()
