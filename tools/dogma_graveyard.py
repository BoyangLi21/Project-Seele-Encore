"""Sample SmileyMan10000's Y-up COLLADA body into five submerged, partially preserved casts."""

import xml.etree.ElementTree as ET
import math
import numpy as np
from dogma_recommission import LCL


def graveyard(b, model):
    ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
    geom = ET.parse(model).find(".//c:geometry/c:mesh", ns)
    source = geom.find("c:source[@id='meshId0-positions']/c:float_array", ns)
    verts = np.fromstring(source.text, sep=" ").reshape(-1, 3)
    poly = geom.find("c:polylist", ns)
    inputs = poly.findall("c:input", ns)
    stride = 1 + max(int(i.get("offset")) for i in inputs)
    offset = next(int(i.get("offset")) for i in inputs if i.get("semantic") == "VERTEX")
    faces = (
        np.fromstring(poly.find("c:p", ns).text, sep=" ", dtype=int)
        .reshape(-1, stride)[:, offset]
        .reshape(-1, 3)
    )
    sample = np.vstack([verts, verts[faces].mean(1)])
    sample[:, 1] = (sample[:, 1] - verts[:, 1].min()) / np.ptp(verts[:, 1])
    scale = 1 / np.ptp(verts[:, 1])
    sample[:, 0] *= scale
    sample[:, 2] = (sample[:, 2] - np.median(verts[:, 2])) * scale
    # A continuous retaining lip separates the basin from the raised gallery and the plant.
    for x in range(-83, -35):
        for z in range(127, 187):
            edge = x in (-83, -36) or z in (127, 186)
            b.box(x, -1247, z, x, -1237, z, "polished_deepslate" if edge else LCL)
    pieces = []
    for i, (cx, cz, angle, length, start, end) in enumerate(
        [
            (-70, 145, 12, 34, 0.24, 1),
            (-49, 145, -29, 31, 0.42, 1),
            (-68, 169, -41, 33, 0.04, 0.81),
            (-50, 174, 21, 30, 0.31, 0.92),
            (-76, 179, 73, 28, 0.79, 1),
        ]
    ):
        X, H, Z = sample.T
        mask = (H >= start) & (H <= end)
        if i % 2 == 0:
            mask &= ~((X > 0.055) & (H < 0.72))
        else:
            mask &= ~((X < -0.04) & (H < 0.58))
        a = math.radians(angle)
        x = X[mask] * length
        z = (H[mask] - (start + end) / 2) * length
        points = np.rint(
            np.column_stack(
                [
                    cx + x * math.cos(a) - z * math.sin(a),
                    -1243 - Z[mask] * length + 0.085 * z,
                    cz + z * math.cos(a) + x * math.sin(a),
                ]
            )
        ).astype(int)
        points = np.unique(points, axis=0)
        stored = 0
        for X, Y, Z in points.tolist():
            if -82 <= X <= -37 and 128 <= Z <= 185 and -1246 <= Y <= -1238:
                mat = (
                    "smooth_quartz"
                    if Y >= -1242
                    else ("calcite" if (X + 2 * Z) % 7 else "bone_block[axis=z]")
                )
                b.put(X, Y, Z, mat)
                stored += 1
        pieces.append(stored)
    for x in (-81, -59, -37):
        for z in (129, 184):
            b.put(x, -1246, z, "ochre_froglight[axis=y]")
    b.reports["sculpture_parts"] = pieces
