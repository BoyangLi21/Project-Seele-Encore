"""Bake the supplied FBX and COLLADA surfaces into the private single-player scenery resource."""

from dataclasses import dataclass
import gzip
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}


def unit(v):
    return v / np.maximum(1e-12, np.linalg.norm(v, axis=-1, keepdims=True))


@dataclass
class Surface:
    points: np.ndarray
    normals: np.ndarray
    colours: np.ndarray
    faces: np.ndarray

    def section(self, mask):
        faces = self.faces[mask]
        used, inverse = np.unique(faces, return_inverse=True)
        return Surface(
            self.points[used],
            self.normals[used],
            self.colours[used],
            inverse.reshape(-1, 3),
        )

    def transform(self, frame, anchor, origin):
        points = (self.points - origin) @ frame.T + anchor
        normals = unit(self.normals @ np.linalg.inv(frame))
        return Surface(points, normals, self.colours, self.faces)

    def simplify(self, spacing):
        # Average coincident samples from the original surface, retaining fine facial relief and UV shading.
        _, idx = np.unique(
            np.round(self.points / spacing).astype(np.int32),
            axis=0,
            return_inverse=True,
        )
        idx = idx.ravel()
        counts = np.bincount(idx)

        def average(values):
            return np.stack(
                [np.bincount(idx, weights=v) / counts for v in values.T], axis=1
            )

        faces = idx[self.faces]
        faces = faces[np.all(faces != np.roll(faces, 1, axis=1), axis=1)]
        return Surface(
            average(self.points),
            unit(average(self.normals)),
            average(self.colours),
            faces,
        )


def sculpture_source(dae):
    out = []
    root = ET.parse(dae)
    for index, mesh in enumerate(root.findall(".//c:geometry/c:mesh", NS)):

        def field(name):
            source = mesh.find(f"c:source[@id='meshId{index}-{name}']", NS)
            stride = int(source.find("c:technique_common/c:accessor", NS).get("stride"))
            return np.fromstring(
                source.find("c:float_array", NS).text, sep=" "
            ).reshape(-1, stride)

        points, normals, uv = field("positions"), field("normals"), field("tex0")
        poly = mesh.find("c:polylist", NS)
        assert all(i.get("offset") == "0" for i in poly.findall("c:input", NS))
        assert np.all(np.fromstring(poly.find("c:vcount", NS).text, sep=" ") == 3)
        faces = np.fromstring(
            poly.find("c:p", NS).text, dtype=np.int32, sep=" "
        ).reshape(-1, 3)
        name = ["evoTool11", "PM3D_Sphere3D1", "PM3D_Sphere3D2"][index]

        def sample(channel):
            image = np.asarray(
                Image.open(
                    next(dae.parent.rglob(name + "_" + channel + ".jpg"))
                ).convert("RGB")
            )
            h, w = image.shape[:2]
            return image[
                ((1 - uv[:, 1]) * h).astype(int) % h, (uv[:, 0] * w).astype(int) % w
            ].astype(float)

        colours = sample("albedo")
        if index == 0:
            colours *= 0.48 + 0.52 * sample("AO") / 255
        out.append(Surface(points, normals, colours, faces))
    return out


def tube(path, radii, colour, sides=12):
    centres = np.asarray(path)
    tangent = unit(np.gradient(centres, axis=0))
    # Parallel transport avoids triangular twists through the tight bends of the rib cage.
    ref = np.eye(3)[np.argmin(np.abs(tangent[0]))]
    points, normals, faces = [], [], []
    for i, (p, t, radius) in enumerate(zip(centres, tangent, radii)):
        ref = unit(ref - np.dot(ref, t) * t)
        normal = np.cos(np.arange(sides)[:, None] * math.tau / sides) * ref
        normal += np.sin(np.arange(sides)[:, None] * math.tau / sides) * np.cross(
            t, ref
        )
        points.extend(p + radius * normal)
        normals.extend(normal)
        if i:
            for j in range(sides):
                a = (i - 1) * sides + j
                b = (i - 1) * sides + (j + 1) % sides
                faces.extend([(a, b, a + sides), (b, b + sides, a + sides)])
    colours = [colour.copy() for _ in points]
    for station in (0, len(centres) - 1):
        facing = tangent[station] * (-1 if station == 0 else 1)
        ring = (
            np.array(points[station * sides : (station + 1) * sides]) - centres[station]
        )
        outer = len(points)
        for scale, tone in [
            (1.0, [212, 182, 137]),
            (0.68, [232, 204, 164]),
            (0.48, [150, 100, 66]),
        ]:
            points.extend(centres[station] + scale * ring)
            normals.extend([facing] * sides)
            colours.extend(
                np.asarray(tone) * (1 + 0.07 * np.sin(np.arange(sides) * 2.1)[:, None])
            )
        middle = len(points)
        points.append(centres[station])
        normals.append(facing)
        colours.append([126, 78, 60])
        for k in range(sides):
            a = outer + k
            b = outer + (k + 1) % sides
            cap = [
                (a, b, b + sides),
                (a, b + sides, a + sides),
                (a + sides, b + sides, b + 2 * sides),
                (a + sides, b + 2 * sides, a + 2 * sides),
                (a + 2 * sides, b + 2 * sides, middle),
            ]
            if station == 0:
                cap = [(c, b, a) for a, b, c in cap]
            faces.extend(cap)
    return Surface(
        np.asarray(points), np.asarray(normals), np.asarray(colours), np.asarray(faces)
    )


def bone_rack(turn, broken):
    pieces = []
    colour = np.array([187, 162, 120])
    for index in range(12):
        z = index * 0.76 - 4.3
        width = 1.4 + 1.3 * math.sin(0.25 + 2.55 * index / 12)
        for sign in (-1, 1):
            if (index, sign) in broken:
                continue
            a = np.linspace(-0.20, 2.75 if (index + sign) % 5 else 1.63, 14)
            path = np.stack(
                [
                    sign * width * np.sin(a),
                    width * 0.72 * (1 - np.cos(a)),
                    z + 0.37 * np.sin(a),
                ],
                axis=-1,
            )
            pieces.append(
                tube(path, 0.12 + 0.14 * np.sin(np.linspace(0.15, 2.9, len(a))), colour)
            )
        # Each vertebral body has a waist and transverse processes attached at the same joint.
        path = [[0, 0.06, z + dz] for dz in [-0.41, -0.28, 0, 0.28, 0.41]]
        pieces.append(tube(path, [0.27, 0.43, 0.33, 0.43, 0.27], colour * 0.85))
        path = [[-0.65, 0.08, z], [0, -0.12, z], [0.65, 0.08, z]]
        pieces.append(tube(path, [0.10, 0.25, 0.10], colour))
    angle = math.radians(turn)
    return pieces, np.array(
        [
            [math.cos(angle), 0, -math.sin(angle)],
            [0, 1, 0],
            [math.sin(angle), 0, math.cos(angle)],
        ]
    )


def anatomical_sections(dae, audit=None):
    from dogma_sculpture_caps import clip, principal_fragment

    body, left, right = sculpture_source(dae)
    # Simplify before cutting. The exact interpolated boundary vertices must survive the bake.
    skull = clip(body.simplify(0.021), (0, 1, 0.8), 0.75, "neck / head", audit)
    torso = clip(body.simplify(0.034), (0, -1, -0.8), -0.75, "neck / trunk", audit)
    torso = clip(torso, (0, 1, 0), -2.62, "lumbar", audit)
    torso = clip(torso, (-1, 0, 0), -0.95, "right shoulder", audit)
    arm = clip(body.simplify(0.032), (-1, 0, 0), 0.79, "left shoulder", audit)
    arm = clip(arm, (0, -1, 0), 0.4, "proximal arm", audit)
    arm = clip(arm, (0, 1, 0), -3.8, "distal arm", audit)
    leg = clip(body.simplify(0.041), (0, -1, 0), 3.7, "upper thigh", audit)
    leg = clip(leg, (1, 0, 0), 0.04, "medial thigh", audit)
    return (
        skull,
        [eye.simplify(0.008) for eye in (left, right)],
        torso,
        principal_fragment(arm),
        principal_fragment(leg),
    )


def graveyard(dae):
    skull, eyes, torso, arm, leg = anatomical_sections(dae)

    def pose(heading, inclination, roll, size):
        a, b, c = np.deg2rad([heading, inclination, roll])
        face = np.array([np.cos(a) * np.cos(b), np.sin(b), np.sin(a) * np.cos(b)])
        up = np.array([-np.cos(a) * np.sin(b), np.cos(b), -np.sin(a) * np.sin(b)])
        side = np.cross(up, face)
        return (
            np.column_stack(
                (
                    side * np.cos(c) + up * np.sin(c),
                    up * np.cos(c) - side * np.sin(c),
                    face,
                )
            )
            * size
        )

    # Physical inner faces of the rectangular LCL tank are x=-82/-36 and z=128/186.
    # Keep each specimen together, including its eyes and all independently capped ribs.
    parts = []

    def immerse(group):
        points = np.vstack([surface.points for surface in group])
        low, high = points.min(axis=0), points.max(axis=0)
        offset = np.maximum([0., 0., 0.], np.array([-79.75, -1245.25, 130.25]) - low)
        offset[[0, 2]] -= np.maximum(0., (high + offset)[[0, 2]] - [-38.25, 183.75])
        for surface in group:
            parts.append(Surface(surface.points + offset, surface.normals, surface.colours, surface.faces))

    # Variation in tilt and immersion leaves some eye ridges above the fluid while other specimens
    # and the severed necks remain visible under it from the adjacent raised inspection gallery.
    for x, y, z, angle, tilt, roll, size in [
        (-46, -1236.6, 161, 12, 28, 19, 5.8),
        (-57, -1237.2, 144, -20, 47, -37, 5.5),
        (-72, -1236.7, 164, 25, 59, 34, 6.1),
        (-65, -1237.9, 178, -17, 24, -25, 5.4),
        (-46, -1237.4, 134, 59, 48, 58, 4.9),
        (-77, -1237.3, 138, -28, 62, -56, 5.1),
    ]:
        frame = pose(angle, tilt, roll, size)
        immerse([part.transform(frame, [x, y, z], [0, 0.88, 0.56]) for part in [skull, *eyes]])
    for part, x, y, z, angle, roll, scale, origin in [
        (torso, -62, -1239.4, 153, 78, -36, 4.1, [0, -1.25, 0.1]),
        (torso, -49, -1239.3, 174, 111, 28, 3.5, [0, -1.25, 0.1]),
        (arm, -73, -1239, 148, 15, 18, 3.6, [-1, -2, 0.3]),
        (arm, -59, -1239, 132, -42, 56, 3.6, [-1, -2, 0.3]),
        (leg, -75, -1240, 176, 47, -11, 3.8, [0.6, -5.25, 0.2]),
    ]:
        immerse([part.transform(pose(angle, 58, roll, scale), [x, y, z], origin)])
    for x, y, z, yaw, factor, missing in [
        (-48, -1239.6, 150, 22, 1.20, {(2, 1), (3, 1)}),
        (-65, -1238.4, 168, -40, 1.34, {(4, -1), (7, 1), (9, 1)}),
        (-62, -1239.4, 139, 38, 1.02, {(1, 1), (2, 1), (7, -1)}),
    ]:
        bones, frame = bone_rack(yaw, missing)
        immerse([b.transform(frame * factor, [x, y, z], np.zeros(3)) for b in bones])
    return parts


COLLECTOR_POSES = ((-493, 1040, -18), (-433, 1056, 6), (-369, 1049, 29))
COLLECTOR_SCALE = 24.8


def collectors(harvester):
    with np.load(harvester) as data:
        p, n, f, m = (data[k] for k in ("v", "n", "f", "m"))
    frame = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])
    # FBX materials identify the recessed mirror, frame, rotating mechanism and anchor separately.
    palette = [(107, 102, 95), (190, 183, 169), (173, 202, 214), (116, 122, 124)]
    source = []
    for i, colour in enumerate(palette):
        mesh = Surface(p @ frame.T, n @ frame.T, np.tile(colour, (len(p), 1)), f)
        source.append(mesh.section(m == i))
    for x, z, angle in COLLECTOR_POSES:
        a = math.radians(angle)
        rotation = np.array(
            [[math.cos(a), 0, -math.sin(a)], [0, 1, 0], [math.sin(a), 0, math.cos(a)]]
        )
        # The original circular foundation sits partly in the water alongside the inspection quay.
        yield [
            part.transform(rotation * COLLECTOR_SCALE, [x + 0.5, 100.2, z + 0.5], np.zeros(3))
            for part in source
        ]


def encode(pieces, underground):
    vertices = np.vstack([piece.points for piece in pieces])
    origin = np.floor(vertices.mean(0)).astype(int)
    vertices -= origin
    faces, colours, base = [], [], 0
    light = unit(np.array([0.48, 0.76, -0.44]))
    for piece in pieces:
        n = piece.normals
        shade = 0.54 + 0.40 * np.maximum(0, n @ light) + 0.10 * np.maximum(0, n[:, 1])
        rgb = piece.colours * shade[:, None]
        if underground:
            depth = np.clip((-1236.13 - piece.points[:, 1]) / 6, 0, 1)[:, None]
            rgb = rgb * (1 - depth * 0.32) + depth * np.array([21, 8, 0])
        colours.extend(np.clip(rgb, 0, 255).astype(np.uint32))
        faces.append(piece.faces + base)
        base += len(n)
    rgb = np.asarray(colours, dtype=np.uint32)
    records = np.empty(len(vertices), dtype=[("v", ">f4", 3), ("rgba", ">u4")])
    records["v"] = vertices
    records["rgba"] = rgb[:, 0] << 16 | rgb[:, 1] << 8 | rgb[:, 2]
    indices = np.vstack(faces).astype(">i4")
    header = struct.pack(
        ">3i6f2i",
        *origin,
        *vertices.min(0),
        *vertices.max(0),
        len(vertices),
        indices.size,
    )
    return header + records.tobytes() + indices.tobytes(), (len(vertices), len(indices))


def bake(dae, harvester, output):
    groups = [graveyard(dae), *collectors(harvester)]
    payload = bytearray(struct.pack(">IH", 0x45564131, len(groups)))
    for index, group in enumerate(groups):
        blob, counts = encode(group, index == 0)
        print("graveyard" if index == 0 else f"harvester {index}", counts, flush=True)
        payload.extend(blob)
    output.write_bytes(gzip.compress(payload, compresslevel=5, mtime=0))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["dae", "harvester_npz", "output"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    bake(args.dae, args.harvester_npz, args.output)
