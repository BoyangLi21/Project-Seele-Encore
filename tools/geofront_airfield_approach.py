"""Regrade the existing south fork from the second command forecourt onto the north apron."""

from geofront_field_grounds import (
    AIR,
    AIRS,
    DIRT,
    GRASS,
    STONE,
    SOIL,
    PAVEMENTS,
    PAVING,
    WHITE,
    TRIM,
    LAMP,
    change,
    plant,
)
from terminal_park_paths import ROUTES
from collections import Counter, defaultdict
import numpy as np
from scipy.ndimage import label
from scipy.spatial import cKDTree


def center(z):
    points = (*ROUTES[2][1][:-1], (225, 474, -461), (225, 478, -461))
    for (x0, z0, _), (x1, z1, _) in zip(points, points[1:]):
        if z <= z1:
            return round(x0 + (x1 - x0) * (z - z0) / (z1 - z0))
    return 225


def grade(z):
    """Road height in half-blocks; meet the existing forecourt and the upper apron."""
    return -939 + round(17 * max(0, min(1, (z - 405) / 68)))


def finish(b):
    for y in range(-470, -465):
        for z in range(374, 396):
            other = 790 - z
            # Front ring is centred on the canopy and five-wide entrance floor at Z395.
            # Mirror only frame, glazing and the opening using the intact north half.
            for x in (221, 222, 223, 224):
                src = b.get(x, y, z)
                dst = b.get(x, y, other)
                if src == dst:
                    continue
                allowed = {"minecraft:gray_stained_glass", WHITE, AIR}
                if not {src, dst} <= allowed:
                    raise ValueError(("facade", x, y, z, src, dst))
                change(b, x, y, other, src)
    for z in range(403, 479):
        mid = center(z)
        g = grade(z)
        floor = g // 2
        half = min(5, 4 + (z - 403) // 4)
        for x in range(mid - half - 9, mid + half + 10):
            d = abs(x - mid) - half
            if (
                z >= 474
                and d > 0
                and abs(x - (218 + round((min(z, 478) - 460) * 7 / 18))) > 4
            ):
                continue
            if z < 409 and d > 0:
                continue
            # Read terrain or the old upper road. Devices and walls demarcate the site.
            current = None
            for y in range(-457, -487, -1):
                state = b.get(x, y, z)
                if state in AIRS or plant(state):
                    continue
                if state in SOIL | PAVEMENTS | {LAMP, WHITE} or "slab[" in state:
                    current = y
                break
            if current is None:
                if d <= 0:
                    raise ValueError(("obstruction", x, z, y, state))
                continue
            if d > 0 and (
                state not in SOIL
                and not (
                    z >= 451
                    and state in (PAVING, WHITE, TRIM)
                    or z >= 451
                    and "slab[" in state
                )
            ):
                continue
            target = (
                floor if d <= 0 else round(floor + (current - floor) * min(1, d / 9))
            )
            if d > 0 and z >= 474:
                target = -461
            if d > 0 and current == target and state in SOIL:
                continue
            # Protect gallery/track air underneath existing hard surfaces; support new fill on its old top.
            for h in range(min(current, target), max(current, target) + 1):
                old = b.get(x, h, z)
                if (
                    old not in SOIL | PAVEMENTS | AIRS | {WHITE, LAMP}
                    and not plant(old)
                    and "slab[" not in old
                ):
                    raise ValueError(("protected", x, h, z, old))
                if h > target:
                    change(b, x, h, z, AIR)
                elif h < target:
                    change(b, x, h, z, DIRT if d > 0 else STONE)
            cap = (
                (WHITE if d == 0 and z < 474 else PAVING)
                if d <= 0 or z >= 474
                else GRASS
            )
            change(b, x, target, z, cap)
            if g % 2 and d <= 0:
                slab = "smooth_quartz_slab" if cap == WHITE else "smooth_stone_slab"
                change(
                    b,
                    x,
                    target + 1,
                    z,
                    "minecraft:" + slab + "[type=bottom,waterlogged=false]",
                )
            # Remove any left-over plant or suspended original ramp tread above the new driving surface.
            if d <= 0:
                for h in range(target + 1 + int(bool(g % 2)), target + 6):
                    old = b.get(x, h, z)
                    if old in AIRS:
                        continue
                    if (
                        plant(old)
                        or old in PAVEMENTS | {WHITE, DIRT, GRASS}
                        or "slab[" in old
                    ):
                        change(b, x, h, z, AIR)
                    else:
                        raise ValueError(("headroom", x, h, z, old))


def distance(x, z):
    return min(
        np.hypot(max(140 - x, 0, x - 288), max(474 - z, 0, z - 545)),
        np.hypot(max(146 - x, 0, x - 174), max(474 - z, 0, z - 1068)),
    )


def vegetation(world):
    cells = {}
    roots = defaultdict(set)
    for cz in range(26, 70):
        for cx in range(5, 21):
            if distance(cx * 16 + 8, cz * 16 + 8) > 62:
                continue
            chunk = world.chunk(cx, cz)
            if not chunk:
                continue
            for sy, (ids, pal) in chunk[0].items():
                if sy not in range(-32, -24):
                    continue
                for j, s in enumerate(pal):
                    if "_leaves[" not in s and "_log[" not in s:
                        continue
                    species = s.split(":")[1].split("_leaves")[0].split("_log")[0]
                    log = "_log[" in s
                    for off in np.flatnonzero(ids == j).tolist():
                        x, y, z = (
                            cx * 16 + off % 16,
                            sy * 16 + off // 256,
                            cz * 16 + (off // 16) % 16,
                        )
                        cells[x, y, z] = (species, log)
                        if log and world.get(x, y - 1, z) in SOIL:
                            roots[species].add((x, z))
    return cells, roots


def repair_trees(b, prev):
    old, roots = vegetation(prev)
    cur, now = vegetation(b.reader)
    trees = defaultdict(list)
    orphan = set()
    for species in {v[0] for v in old.values()} | {v[0] for v in cur.values()}:
        trunks = sorted(roots[species] | now[species])
        coords = [
            p for p in old.keys() | cur.keys() if (old.get(p) or cur[p])[0] == species
        ]
        if not coords:
            continue
        if not trunks:
            orphan.update(p for p in coords if p in cur)
            continue
        dists, ix = cKDTree(trunks).query(np.array(coords)[:, [0, 2]])
        for p, dist, i in zip(coords, dists, ix):
            if dist <= 9:
                trees[(species, *trunks[i])].append(p)
            elif p in cur:
                orphan.add(p)
    report = Counter()
    for (sp, x, z), pts in trees.items():
        if distance(x, z) > 39:
            continue
        removed = [p for p in pts if p in old and p not in cur]
        present = [p for p in pts if p in cur]
        if not present:
            continue
        rooted = (x, z) in now[sp]
        if not removed and rooted:
            continue
        # Complete a tree only when the standing trunk still meets the soil and the crown clears the graded strip.
        restore = (
            rooted
            and min(distance(a, c) for a, y, c in pts) > 7
            and all(b.get(*p) in AIRS for p in removed)
        )
        if restore:
            for p in removed:
                change(b, *p, prev.get(*p))
            report["restored trees"] += 1
            report["restored wood/leaves"] += len(removed)
        else:
            for p in present:
                change(b, *p, AIR)
            report["removed damaged crowns/stems"] += 1
            report["removed wood/leaves"] += len(present)
    for p in orphan:
        if distance(p[0], p[2]) <= 38:
            change(b, *p, AIR)
            report["unattached wood/leaves"] += 1
    return report


def repair(builder, pre_airfield_world):
    """Repair the measured R757 map using tree ownership from the pre-runway survey."""
    report = repair_trees(builder, pre_airfield_world)
    finish(builder)
    # Check physical attachment in three dimensions even when an adjacent tree owns the column.
    wood, _ = vegetation(builder.reader)
    for pos, state in builder.changes.items():
        if "_leaves[" in state or "_log[" in state:
            species = state.split(":")[1].split("_leaves")[0].split("_log")[0]
            wood[pos] = (species, "_log[" in state)
        else:
            wood.pop(pos, None)
    if not wood:
        return report
    coords = np.array(list(wood), dtype=np.int32)
    low = coords.min(0)
    indices = tuple((coords - low).T)
    volume = np.zeros(coords.max(0) - low + 1, dtype=bool)
    volume[indices] = True
    components, _ = label(volume, np.ones((3, 3, 3), np.uint8))
    ids = components[indices]
    grounded = {
        int(k)
        for ((x, y, z), (_, log)), k in zip(wood.items(), ids)
        if log and builder.get(x, y - 1, z) in SOIL
    }
    for pos, component in zip(wood, ids):
        if component not in grounded and distance(pos[0], pos[2]) <= 38:
            change(builder, *pos, AIR)
            report["detached remainder"] += 1
    return report
