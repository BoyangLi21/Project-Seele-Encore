"""Retire the centre span and turn the lower stair landing towards Lilith."""

import gzip
import io
import json

import nbtlib

from dogma_recommission import AIR, AIRS, FLOOR

BRIDGE_Y = -1256
OVERLOOK = (16, BRIDGE_Y + 1, 340)
EDGE = "minecraft:polished_deepslate"
SUBFRAME = "minecraft:deepslate_tiles"
LIGHT = "minecraft:ochre_froglight[axis=y]"
SIDES = {"east": (1, 0), "north": (0, -1), "south": (0, 1), "west": (-1, 0)}


def rail(sides):
    flags = ",".join(f"{name}={str(name in sides).lower()}" for name in SIDES)
    return f"projectseele:nerv_edge_rail[{flags}]"


def upper_gallery(b, cursor):
    manifest = "r52/dogma_interlocks.nbt"
    gate = nbtlib.load(b.world / manifest)
    palette = list(map(str, gate["Palette"]))
    rows = gate["Cells"].reshape(-1, 5).tolist()
    if not 0 <= cursor <= len(rows):
        raise ValueError("Invalid saved emergency gate cursor")
    by_position = {tuple(row[:3]): i for i, row in enumerate(rows)}
    normal = {}
    # The wide, original ring ends at z=287. Both the old balcony tongue and
    # the later inspection bridge are within this strip, above the lower stair.
    for x in range(23, 38):
        for z in range(288, 345):
            for y in range(-1234, -1228):
                normal[x, y, z] = AIR
        normal[x, -1230, 287] = rail({"south"})
    # Two temporary iron columns and one unsupported field block at the right jamb.
    iron = {(8, -1225, 261)}
    for y in range(-1230, -1224):
        iron.update(((8, y, 268), (16, y, 261)))
    for p in iron:
        if b.get(*p) == "minecraft:iron_block":
            normal[p] = AIR

    # Reuse retired phase-two rows for the new retracting guard. This keeps
    # the length and meaning of the saved cursor (including fully open saves).
    spare = iter(
        i
        for i, row in enumerate(rows)
        if 28 <= row[0] <= 34 and row[2] >= 304 and normal.get(tuple(row[:3])) == AIR
    )
    for p, state in normal.items():
        b.put(*p, state)
        i = by_position.get(p)
        if i is not None:
            rows[i][3] = palette.index(AIR)
            if state == AIR:
                rows[i][4] = palette.index(AIR)
    for x in range(23, 38):
        p = x, -1230, 287
        i = by_position.get(p)
        if i is None:
            i = next(spare)
        guard = normal[p]
        if guard not in palette:
            palette.append(guard)
        rows[i] = [*p, palette.index(guard), palette.index(AIR)]
        b.put(*p, AIR if i < cursor else guard)
    if len({tuple(row[:3]) for row in rows}) != len(rows):
        raise ValueError("Overlapping emergency gate rows")
    gate["Palette"] = nbtlib.List[nbtlib.String](palette)
    gate["Cells"] = nbtlib.IntArray([v for row in rows for v in row])
    out = io.BytesIO()
    gate.write(out)
    b.output(manifest, gzip.compress(out.getvalue(), mtime=0))


def lower_gallery(b):
    # Keep the original eight-block landing. A narrower cantilever runs
    # forward, then east, stopping before the feet and beside the EVA lane.
    deck = {(x, z) for x in range(5, 13) for z in range(300, 316)}
    deck.update((x, z) for x in range(5, 12) for z in range(316, 343))
    deck.update((x, z) for x in range(12, 19) for z in range(337, 343))
    stair = {(x, 299) for x in range(5, 10)}
    surface = deck | stair
    for x, z in deck:
        sides = {
            name for name, (dx, dz) in SIDES.items() if (x + dx, z + dz) not in surface
        }
        top = EDGE if sides else FLOOR
        if (x == 6 and z in (313, 326, 339)) or (x, z) == (17, 341):
            top = LIGHT
        b.put(x, BRIDGE_Y, z, top)
        b.put(x, BRIDGE_Y + 1, z, rail(sides) if sides else AIR)
        if sides or z % 8 == 1:
            b.put(x, BRIDGE_Y - 1, z, SUBFRAME)
    for z in range(275, 300):
        y = -1231 - (z - 274)
        b.put(5, y + 1, z, rail({"west"}))
        b.put(9, y + 1, z, rail({"east"}))
    # Three pairs of piles reach the native lake bed. The final short arm cantilevers.
    for z in (319, 329, 340):
        for x in (6, 10):
            for y in range(BRIDGE_Y - 2, -1344, -1):
                state = b.get(x, y, z)
                if state not in AIRS and not state.startswith(
                    ("projectseele:lcl", "minecraft:light[")
                ):
                    break
                b.put(x, y, z, SUBFRAME)
            else:
                raise ValueError(f"No lake bed beneath bridge pile at {x}, {z}")


def gallery(b, cursor=0):
    """Apply to a Works transaction. Supply the world's saved Dogma Cursor."""
    upper_gallery(b, cursor)
    lower_gallery(b)
    x, y, z = OVERLOOK
    travel = "r52/travel.json"
    doc = json.loads((b.world / travel).read_bytes())
    arrival = next(row for row in doc["destinations"] if row["key"] == "lilith")
    pos = [x + 0.5, y, z + 0.5]
    arrival.update(
        label="莉莉丝层 · 折桥观景台",
        yaw=-74,
        position=pos,
        requested_position=pos,
        actual_cells=[
            {"position": [x, y + dy, z], "state": b.get(x, y + dy, z)}
            for dy in (-1, 0, 1)
        ],
    )
    b.output(travel, json.dumps(doc, ensure_ascii=False, indent=1).encode("utf8"))
