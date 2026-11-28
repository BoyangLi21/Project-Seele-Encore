"""Read a nine-channel terrain survey and write guarded, coordinate-mergeable surface overlays."""

import gzip, json, shutil, struct, sys
from pathlib import Path
import numpy as np
import nbtlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dogma_recommission import Works
from mca import World
from private_cleanup import DATA, control, state, unpack
from tokyo3_r66_stage import surface_recipes

reg = Path("dimensions/projectseele/geofront/region")


class Surface(World):
    @staticmethod
    def load_root(root):
        root["sections"] = nbtlib.List[nbtlib.Compound](
            [s for s in root["sections"] if -12 <= int(s["Y"]) <= 24]
        )
        return World.load_root(root)


def read_survey(survey, name):
    with gzip.open(survey / (name + ".raw.gz"), "rb") as f:
        bounds = {
            "air": (48, -660, 545, -175, 40, 240),
            "schoolroad": (-210, -920, 345, -415, 50, 253),
            "valley": (1400, 882, 2600, 1580, -125, 120),
            "house": (2940, 1388, 3099, 1540, -117, 72),
            "south": (-380, 1420, 680, 2210, -127, 256),
        }
        header = struct.unpack(">6i", f.read(24))
        if header != bounds[name]:
            raise ValueError(
                f"{name}: unexpected surveyed rectangle or elevation span {header}"
            )
        x, z, X, Z, y, Y = header
        a = np.full(
            (9, (Z // 16 - z // 16 + 1) * 16, (X // 16 - x // 16 + 1) * 16),
            -2048,
            dtype="i2",
        )
        x = x // 16 * 16
        z = z // 16 * 16
        seen = set()
        while q := f.read(8):
            cx, cz = struct.unpack(">2i", q)
            if (cx, cz) in seen or not (
                x // 16 <= cx <= X // 16 and z // 16 <= cz <= Z // 16
            ):
                raise ValueError((name, "unexpected survey chunk", cx, cz))
            seen.add((cx, cz))
            i, j = cz * 16 - z, cx * 16 - x
            a[:, i : i + 16, j : j + 16] = np.frombuffer(f.read(4608), ">i2").reshape(
                9, 16, 16
            )
    if not seen:
        raise ValueError((name, "empty survey"))
    return x, z, a


def open_overlay(world, out):
    world = world.resolve()
    out = out.resolve()
    if world == out or world in out.parents or out in world.parents:
        raise ValueError("Choose a separate offline output directory")
    stage = out / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    editor = Works(stage, world, out / "receipts")
    editor.reader = Surface(world / reg)
    return editor


def save_overlay(b, live, W, plans=()):
    """Each optional plan is (owner-relative block TSV, xyz origin, fixed scenery flag)."""
    stage = W / "stage"
    rows = {}
    for p, new in b.changes.items():
        old = b.reader.get(*p)
        if new != old or p in b.tags:
            rows[p] = old, new
    regeneration = rows.copy()
    for path, origin, fixed in plans:
        with gzip.open(path, "rt", encoding="utf8") as fp:
            for line in fp:
                x, y, z, before, after = line.rstrip().split("\t")
                p = tuple(v + int(a) for v, a in zip(origin, (x, y, z)))
                if p in rows or before != b.reader.get(*p):
                    raise ValueError(
                        ("overlap or different source", p, before, b.reader.get(*p))
                    )
                rows[p] = before, after
                if fixed:
                    regeneration[p] = before, after
                b.put(*p, after)
    for rx, rz in {(x >> 9, z >> 9) for x, y, z in rows}:
        rel = reg / f"r.{rx}.{rz}.mca"
        (stage / reg).mkdir(exist_ok=True, parents=True)
        shutil.copyfile(live / rel, stage / rel)
    with gzip.open(W / "blocks.tsv.gz", "wt", encoding="utf8") as f:
        for (x, y, z), (old, new) in sorted(rows.items()):
            f.write(f"{x}\t{y}\t{z}\t{old}\t{new}\n")
    print("native rows", len(rows), flush=True)
    b.write()
    (W / "tags.json").write_text(json.dumps(list(b.tags)), "utf8")
    plan = W / "plan"
    plan.mkdir(exist_ok=True)
    with gzip.open(plan / "streetscape.tsv.gz", "wt", encoding="utf8") as f:
        for (x, y, z), (before, after) in sorted(regeneration.items()):
            f.write(f"{x}\t{y}\t{z}\t{before}\t{after}\n")
    extras = W / "cargo"
    changed = surface_recipes(live, plan, extras, control(live))

    def packed(x, y, z):
        return ((x & 0x3FFFFFF) << 38 | (z & 0x3FFFFFF) << 12 | y & 0xFFF) - (
            1 << 64 if x < 0 else 0
        )

    for (cx, cz), updates in changed.items():
        rel = DATA / "city_rigid_generation_r45/surface" / f"{cx}_{cz}.dat"
        tag = nbtlib.load(extras / rel)
        bels = tag["BlockEntities"]
        deleted = [c for c in bels if unpack(c["Pos"]) in updates]
        for c in deleted:
            bels.remove(c)
        add = [p for p in b.tags if (p[0] >> 4, p[2] >> 4) == (cx, cz)]
        for p in add:
            sid = next(i for i, c in enumerate(tag["Palette"]) if state(c) == b.get(*p))
            bels.append(
                nbtlib.Compound(
                    {
                        "Pos": nbtlib.Long(packed(*p)),
                        "StateId": nbtlib.Int(sid),
                        "NBT": b.tags[p],
                    }
                )
            )
        if add or deleted:
            tag.save(extras / rel, gzipped=True)

    files = [
        dict(path=p.relative_to(extras).as_posix())
        for p in sorted(extras.rglob("*.dat"))
    ]
    (W / "data.json").write_text(json.dumps(files, indent=1), "utf8")
    (W / "chunks.json").write_text(json.dumps(sorted(changed)), "utf8")

    return len(rows), len(changed)
