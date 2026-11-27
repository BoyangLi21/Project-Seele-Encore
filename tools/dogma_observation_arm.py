"""Place the lower inspection arm and register the portion operated by the emergency gates."""

from dogma_recommission import AIR, AIRS, FLOOR
from dogma_lilith_gallery import EDGE, SUBFRAME, LIGHT, SIDES, rail, BRIDGE_Y
import nbtlib, gzip, io

# Turn on the near side of the body. This arm is clear of the original upper ring.
LANDING = (17, BRIDGE_Y + 1, 331)
END = (37, BRIDGE_Y + 1, 331)


def lower_arm(b, previous, cursor):
    # Remove only the superseded 752 deck and piles, using the unmodified lake bed and LCL.
    for x in range(5, 19):
        for z in range(316, 343):
            for y in range(-1344, BRIDGE_Y + 2):
                p = x, y, z
                s = b.get(*p)
                if s in (EDGE, SUBFRAME, FLOOR, LIGHT) or "nerv_edge_rail" in s:
                    b.put(*p, previous.get(*p))
    deck = {(x, z) for x in range(5, 13) for z in range(300, 316)}
    deck.update((x, z) for x in range(5, 12) for z in range(316, 335))
    deck.update((x, z) for x in range(12, 40) for z in range(329, 335))
    neighbors = deck | {(x, 299) for x in range(5, 10)}
    moving = {}
    for x, z in sorted(deck):
        sides = {
            k for k, (dx, dz) in SIDES.items() if (x + dx, z + dz) not in neighbors
        }
        top = EDGE if sides else FLOOR
        if (x == 6 and z in (313, 325, 333)) or (x in (16, 26, 37) and z == 333):
            top = LIGHT
        states = {BRIDGE_Y: top, BRIDGE_Y + 1: rail(sides) if sides else AIR}
        if sides or z % 8 == 1 or (x >= 12 and x % 7 == 4):
            states[BRIDGE_Y - 1] = SUBFRAME
        for y, s in states.items():
            p = x, y, z
            b.put(*p, s)
            if x >= 20 and s != AIR:
                moving[p] = (s, AIR)
        if x == 19:
            # The outer edge closes before the cantilever enters the chassis route.
            moving[x, BRIDGE_Y + 1, z] = (states[BRIDGE_Y + 1], rail(sides | {"east"}))
    for z in (319, 331):
        for x in (6, 10):
            for y in range(BRIDGE_Y - 2, -1345, -1):
                s = b.get(x, y, z)
                if s not in AIRS and not s.startswith(
                    ("projectseele:lcl", "minecraft:light[")
                ):
                    break
                b.put(x, y, z, SUBFRAME)
    fn = "r52/dogma_interlocks.nbt"
    g = nbtlib.load(b.world / fn)
    palette = list(map(str, g["Palette"]))
    rows = g["Cells"].reshape(-1, 5).tolist()
    # Recycle retired high bridge rows (always air). Every historic cursor keeps its physical meaning.
    space = [
        i
        for i, row in enumerate(rows)
        if row[3] == row[4]
        and palette[row[3]] == AIR
        and 28 <= row[0] <= 34
        and row[2] >= 304
    ]
    if len(space) < len(moving):
        raise ValueError("Insufficient released phase-two rows")
    for i, (p, states) in zip(space, sorted(moving.items())):
        for s in states:
            if s not in palette:
                palette.append(s)
        rows[i] = [*p, *(palette.index(s) for s in states)]
        b.put(*p, states[int(i < cursor)])
    assert len(set(tuple(row[:3]) for row in rows)) == len(rows)
    g["Palette"] = nbtlib.List[nbtlib.String](palette)
    g["Cells"] = nbtlib.IntArray([v for row in rows for v in row])
    out = io.BytesIO()
    g.write(out)
    b.output(fn, gzip.compress(out.getvalue(), mtime=0))
    b.reports["retractable_lateral_arm"] = {
        "moving_cells": len(moving),
        "end": END,
        "all_state_arrival": LANDING,
    }
