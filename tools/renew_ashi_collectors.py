"""Build native half-block contact geometry from the same FBX triangles as the lake reflectors."""

from collections import Counter
import numpy as np
from scipy.ndimage import binary_fill_holes
from dogma_sculpture_mesh import COLLECTOR_POSES, collectors
from dogma_recommission import AIR, AIRS

WATER = "minecraft:water[level=0]"
FLOOR = "minecraft:smooth_stone"


def octants(pieces):
    """Rasterize each triangle into intersecting half-cells via the separating-axis theorem."""
    faces = np.vstack([p.points[p.faces] for p in pieces]) * 2
    base = np.floor(faces.min(axis=(0, 1)) / 2).astype(int) - 1
    faces -= base * 2
    size = 2 * (np.ceil(faces.max(axis=(0, 1)) / 2).astype(int) + 1)
    shell = np.zeros(size, dtype=bool)
    axes = np.eye(3)
    for triangle in faces:
        lo = np.floor(triangle.min(axis=0)).astype(int)
        hi = np.floor(triangle.max(axis=0)).astype(int)
        cells = np.indices(hi - lo + 1).reshape(3, -1).T + lo
        if len(cells) > 1:
            edges = np.roll(triangle, -1, axis=0) - triangle
            tests = np.vstack(
                (
                    np.cross(edges[0], edges[1]),
                    np.cross(edges[:, None, :], axes).reshape(-1, 3),
                )
            )
            tests = tests[np.any(np.abs(tests) > 1e-9, axis=1)]
            radius = 0.5 * np.abs(tests).sum(axis=1) + 1e-8
            vertices = triangle @ tests.T
            centres = (cells + 0.5) @ tests.T
            cells = cells[
                np.all(
                    (centres >= vertices.min(axis=0) - radius)
                    & (centres <= vertices.max(axis=0) + radius),
                    axis=1,
                )
            ]
        shell[tuple(cells.T)] = True
    solid = binary_fill_holes(shell)
    block = np.zeros(size // 2, dtype=np.uint8)
    for bit in range(8):
        block |= (
            solid[(bit & 1) :: 2, ((bit >> 1) & 1) :: 2, ((bit >> 2) & 1) :: 2].astype(
                np.uint8
            )
            << bit
        )
    return base, block


def walkway(points):
    for (x, z), (xx, zz) in zip(points, points[1:]):
        n = max(abs(x - xx), abs(z - zz))
        for k in range(n + 1):
            yield round(x + (xx - x) * k / n), round(z + (zz - z) * k / n)


def clear_old_quays(b):
    old = [(-479, 1018), (-452, 1027), (-425, 1035)]
    cells = set()
    for x, z in old:
        cells.update(
            (x + i, z + j)
            for i in range(-11, 12)
            for j in range(-6, 7)
            if abs(i) + abs(j) <= 15
        )
    for x, z in walkway([(-452, 1003), (-479, 1012), (-452, 1021), (-425, 1029)]):
        cells.update((x + i, z + j) for i in (-1, 0, 1) for j in (-1, 0, 1))
    for x, z in cells:
        if b.get(x, 100, z) in (FLOOR, "minecraft:polished_andesite"):
            b.put(x, 100, z, AIR)
        for y in range(99, 56, -1):
            if b.get(x, y, z) not in (
                "minecraft:polished_andesite",
                "minecraft:stone_bricks",
            ):
                break
            b.put(x, y, z, WATER)


def commission(b, harvester):
    clear_old_quays(b)
    report = []
    for pose, pieces in zip(COLLECTOR_POSES, collectors(harvester)):
        base, masks = octants(pieces)
        counts = Counter()
        for pos in np.argwhere(masks):
            x, y, z = (pos + base).tolist()
            original = b.get(x, y, z)
            wet = original.startswith("minecraft:water")
            if original not in AIRS and not wet:
                if "collector_structure" in original:
                    wet = "waterlogged=true" in original
                else:
                    raise ValueError(
                        ("collector intersects terrain or pier", x, y, z, original)
                    )
            mask = int(masks[tuple(pos)])
            b.put(
                x,
                y,
                z,
                f"projectseele:collector_structure[octants={mask},waterlogged={str(wet).lower()}]",
            )
            counts["cells"] += 1
            counts["partial"] += mask < 255
            counts["submerged"] += wet
        report.append(
            dict(
                pose=pose,
                bounds=[base.tolist(), (base + np.array(masks.shape) - 1).tolist()],
                **counts,
            )
        )
    # Gallery follows the shore side of all three footings. The short finger piers end
    # at the solid rim and do not cross the rocker or the rotating blade.
    path = list(walkway([(-452, 1002), (-452, 1004), (-493, 1004), (-493, 1008)]))
    path += list(walkway([(-452, 1004), (-433, 1020), (-433, 1024)]))
    path += list(walkway([(-433, 1020), (-369, 1012), (-369, 1017)]))
    deck = {(x + i, z + j) for x, z in path for i in (-1, 0, 1) for j in (-1, 0, 1)}
    for x, z in deck:
        if b.get(x, 100, z) in AIRS:
            b.put(x, 100, z, FLOOR)
    for x, z, angle in COLLECTOR_POSES:
        # Continue from the gallery up to the actual mesh, following its occupancy
        # in this row. Contact plates bridge the final half-block beneath the rim.
        start = {-493: 1008, -433: 1024, -369: 1017}[x]
        for cx in range(x - 1, x + 2):
            for cz in range(start, z):
                if "collector_structure" in b.get(cx, 100, cz):
                    break
                if b.get(cx, 100, cz) in AIRS:
                    b.put(cx, 100, cz, FLOOR)
    for i, (x, z) in enumerate(dict.fromkeys(path)):
        if i % 12 == 0:
            for y in range(99, 55, -1):
                if "water" not in b.get(x, y, z) or "collector_structure" in b.get(
                    x, y, z
                ):
                    break
                b.put(x, y, z, "polished_andesite")
    b.reports["lake_collectors"] = report
    return report
