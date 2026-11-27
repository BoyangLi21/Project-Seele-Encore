"""Author the two surveyed emergency gate states on an offline copy of the GeoFront dimension."""

from collections import defaultdict
from pathlib import Path
import json
import os
import shutil
import nbtlib
from map_buildings.mca import World, AIR as AIRS
from write_deep_cells import (
    REGION,
    read_chunk,
    write_chunk,
    clear_light,
    decode,
    encode,
    sign_entity,
)

AIR = "minecraft:air"
FLOOR = "projectseele:nerv_floor_panel"
WALL = "projectseele:nerv_structural_panel"
LCL = "projectseele:lcl[level=0]"


def mc(s):
    return s if ":" in s else "minecraft:" + s


class Works:
    def __init__(self, world, previous, out):
        self.world, self.out = world, out
        self.reader = World(world / REGION)
        self.old = World(previous / REGION)
        self.changes = {}
        self.tags = {}
        self.outputs = []
        self.gates = {}
        self.reports = {}
        self.out.mkdir(parents=True, exist_ok=True)

    def get(self, x, y, z):
        p = x, y, z
        return self.changes[p] if p in self.changes else self.reader.get(*p)

    def put(self, x, y, z, s):
        if s is None:
            raise ValueError((x, y, z))
        self.changes[x, y, z] = mc(s)

    def box(self, x, y, z, X, Y, Z, s):
        for a in range(x, X + 1):
            for b in range(y, Y + 1):
                for c in range(z, Z + 1):
                    self.put(a, b, c, s)

    def sign(self, x, y, z, face, *lines):
        s = f"minecraft:warped_wall_sign[facing={face},waterlogged=false]"
        self.put(x, y, z, s)
        self.tags[x, y, z] = sign_entity(
            dict(pos=[x, y, z], front=lines, color="white", glow=True), s
        )

    def gate(self, p, normal, phase, emergency=None):
        before = self.reader.get(*p) if emergency is None else emergency
        if normal == before:
            return
        if self.reader.block_entity(*p):
            raise ValueError(("active device in gate", p))
        self.put(*p, normal)
        self.gates[p] = (phase, mc(normal), mc(before))

    def output(self, name, data):
        path = self.world / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.outputs.append(name)

    def write(self):
        groups = defaultdict(lambda: defaultdict(dict))
        for (x, y, z), s in self.changes.items():
            if self.reader.get(x, y, z) == s and (x, y, z) not in self.tags:
                continue
            groups[x >> 9, z >> 9][x >> 4, z >> 4][x, y, z] = s
        for (rx, rz), chunks in groups.items():
            rel = Path(REGION) / f"r.{rx}.{rz}.mca"
            path = self.world / rel
            backup = self.out / "baseline" / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(path, backup)
            buf = bytearray(path.read_bytes())
            for (cx, cz), rows in chunks.items():
                i, loc, count, root = read_chunk(buf, cx, cz)
                if not root["block_entities"]:
                    root["block_entities"] = nbtlib.List[nbtlib.Compound]()
                prev = {
                    (int(e["x"]), int(e["y"]), int(e["z"])): e
                    for e in root["block_entities"]
                }
                by_y = defaultdict(dict)
                for p, s in rows.items():
                    by_y[p[1] >> 4][p] = s
                secs = {int(s["Y"]): s for s in root["sections"]}
                for cy, edits in by_y.items():
                    sec = secs[cy]["block_states"]
                    idx, pal = decode(sec)
                    lookup = {v: j for j, v in enumerate(pal)}
                    for p, s in edits.items():
                        if s not in lookup:
                            lookup[s] = len(pal)
                            pal.append(s)
                        x, y, z = p
                        idx[(y % 16) * 256 + (z % 16) * 16 + x % 16] = lookup[s]
                        if p in prev and (
                            p in self.tags
                            or self.reader.get(*p).split("[")[0] != s.split("[")[0]
                        ):
                            root["block_entities"].remove(prev[p])
                        if p in self.tags:
                            tag = self.tags[p]
                            tag.update({k: nbtlib.Int(v) for k, v in zip("xyz", p)})
                            root["block_entities"].append(tag)
                    encode(sec, idx, pal)
                clear_light(root)
                root.pop("Heightmaps", None)
                write_chunk(buf, i, loc, count, root)
            temp = path.with_suffix(".new")
            temp.write_bytes(buf)
            os.replace(temp, path)
            self.outputs.append(str(rel))
        self.reports["changed_cells"] = sum(
            len(v) for reg in groups.values() for v in reg.values()
        )
        (self.out / "files.json").write_text(json.dumps(self.outputs), "utf8")
        (self.out / "report.json").write_text(
            json.dumps(self.reports, ensure_ascii=False, indent=2), "utf8"
        )


def passages(b):
    # Restore exactly the original hall-side decorations and both layers of its east wall.
    for x in range(79, 96):
        for y in range(-1052, -987):
            for z in range(205, 256):
                b.gate((x, y, z), b.old.get(x, y, z), 0)
    # The movable ground is an earthen lid, continuous with the original terrain contour.
    for x in range(116, 164):
        for z in range(171, 204):
            for y in range(-469, -462):
                p = x, y, z
                s = b.old.get(*p)
                if y == -469 and s in AIRS:
                    continue
                if s == "minecraft:dirt" and b.old.get(x, y + 1, z) in AIRS:
                    s = "minecraft:grass_block[snowy=false]"
                if any(t in s for t in ("leaves", "_log", "flower", "fern", "sapling")):
                    s = AIR
                if b.reader.block_entity(*p):
                    b.put(*p, AIR)
                    continue
                b.gate(p, s, 0)
    # Both intersecting personnel galleries have a common floor and full-height doorway.
    b.box(-16, -1230, 245, -6, -1227, 247, AIR)
    b.box(-16, -1231, 245, -6, -1231, 247, FLOOR)
    # Close the three exposed sides of the old vestibule; keep the side passage at x=15.
    for x in range(15, 46):
        for z in range(239, 258):
            for y in range(-1231, -1199):
                if y in (-1231, -1200) or x in (15, 45) or z == 239:
                    b.gate((x, y, z), b.old.get(x, y, z), 1)
    # Museum-side deck and its old front edge, including the red line under the leaves.
    for x in range(16, 45):
        for z in range(258, 300):
            for y in range(-1232, -1228):
                if z <= 260 and y != -1231:
                    continue
                p = x, y, z
                if not b.reader.block_entity(*p):
                    b.gate(p, b.old.get(*p), 2)
    # The old balcony ended at z=298. From its centre a narrow inspection bridge now
    # approaches the cross, leaving a gap to the body and two uninterrupted expanses of LCL.
    for z in range(298, 345):
        for x in range(28, 35):
            b.gate((x, -1231, z), "polished_deepslate" if x in (28, 34) else FLOOR, 2)
            b.gate(
                (x, -1230, z),
                "iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]"
                if x in (28, 34)
                else AIR,
                2,
            )
        if z % 8 == 0:
            b.gate((31, -1231, z), "sea_lantern", 2)
    for x in range(28, 35):
        b.gate(
            (x, -1230, 344),
            "iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]",
            2,
        )
    # The deck through the moving door must use the current leaf width when released.
    palette = {}
    rows = []
    for p, (phase, closed, opened) in sorted(
        b.gates.items(),
        key=lambda k: (
            k[1][0],
            abs(k[0][0] - (94 if k[1][0] == 0 else 30)),
            k[0][2],
            k[0][1],
        ),
    ):
        for s in (closed, opened):
            palette.setdefault(s, len(palette))
        rows.extend((*p, palette[closed], palette[opened]))
    import io, gzip

    tag = nbtlib.File(
        {"Palette": nbtlib.List[nbtlib.String](palette), "Cells": nbtlib.IntArray(rows)}
    )
    stream = io.BytesIO()
    tag.write(stream)
    b.output("r52/dogma_interlocks.nbt", gzip.compress(stream.getvalue(), mtime=0))
    b.reports["gate_cells"] = {
        phase: sum(e[0] == phase for e in b.gates.values()) for phase in (0, 1, 2)
    }


def tanks(b):
    # Seal every wetted side. The wall follows the staircase of the curved tank front,
    # including the exposed side of each turn and the previously open back and end bays.
    curve = lambda x: 102 + round(7 * ((x + 6) / 24) ** 2)
    fluid = {(x, z) for x in range(-29, 18) for z in range(97, curve(x) + 1)}
    wall = {
        (x + dx, z + dz)
        for x, z in fluid
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if (x + dx, z + dz) not in fluid
    }
    for x, z in wall:
        b.box(x, -1230, z, x, -1219, z, "orange_stained_glass")
    # Dry service lock and a single working door into the enclosed inspection area.
    for x in range(-37, 20):
        b.box(x, -1230, 122, x, -1218, 122, "glass")
    for half, y in [("lower", -1230), ("upper", -1229)]:
        b.put(
            -32,
            y,
            122,
            f"dark_oak_door[facing=north,half={half},hinge=left,open=false,powered=false]",
        )
    b.box(-13, -1230, 115, -7, -1230, 117, "polished_blackstone")
    for x in (-12, -11, -9, -8):
        b.put(x, -1229, 115, "cyan_terracotta" if x % 2 else "redstone_lamp[lit=false]")
    b.put(-10, -1229, 116, "lever[face=floor,facing=south,powered=false]")
    b.sign(
        -10,
        -1230,
        118,
        "south",
        "模擬人格プラント",
        "DESTRUDO",
        "拉下 · 失活",
        "复位 · 再生",
    )
    b.reports["glass_tank_perimeter"] = len(wall)


def apartment(b):
    srcx, srcy, srcz = -191, 102, 514
    # Both beds face the pillow, with clear space above it. The blinds are dark at the window.
    b.put(-187, 103, 514, "white_bed[facing=north,occupied=false,part=head]")
    b.put(-187, 103, 515, "white_bed[facing=north,occupied=false,part=foot]")
    b.put(-187, 104, 514, AIR)
    for x in (-190, -189, -188):
        for y in (103, 104):
            b.put(x, y, 520, "black_stained_glass")
    # Build the same room at the lab as a freestanding preserved cell with a surrounding viewing aisle.
    b.box(-32, -1230, 187, -8, -1224, 206, AIR)
    for dx in range(-1, 6):
        for dz in range(-1, 7):
            seam = dx in (-1, 5) or dz in (-1, 6)
            for dy in range(4):
                p = srcx + dx, srcy + dy, srcz + dz
                s = b.get(*p)
                if dy == 0 or dy == 3 or seam:
                    if s in AIRS and (dy == 0 or dy == 3):
                        s = "minecraft:light_gray_concrete"
                b.put(-25 + dx, -1231 + dy, 194 + dz, s)
                tag = source_entity(b.reader, p)
                if tag is not None:
                    b.tags[-25 + dx, -1231 + dy, 194 + dz] = tag
    # Copy the original iron door, its entry button and its 402 plaque on the west jamb.
    for dz in (3, 5):
        p = (srcx - 2, srcy + 2, srcz + dz)
        b.put(-27, -1229, 194 + dz, b.get(*p))
        tag = source_entity(b.reader, p)
        if tag is not None:
            b.tags[-27, -1229, 194 + dz] = tag
    b.sign(-8, -1228, 207, "north", "第１実験室", "綾波レイ / 402", "人工進化研究所")
    b.reports["rei_apartment"] = [srcx, srcy, srcz]


def source_entity(w, p):
    x, y, z = p
    if not w.block_entity(*p):
        return None
    buf = w._region(x >> 9, z >> 9)
    import copy

    root = read_chunk(buf, x >> 4, z >> 4)[3]
    return next(
        (
            copy.deepcopy(e)
            for e in root["block_entities"]
            if tuple(int(e[k]) for k in "xyz") == p
        ),
        None,
    )
