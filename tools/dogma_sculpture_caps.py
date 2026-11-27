"""Cut each sculpture with actual planes, closing each newly exposed contour in that plane."""

import math

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union


def _bone_island(polygon):
    # A pole of inaccessibility keeps the entire cortical ring inside concave or slender sections.
    circle = shapely.maximum_inscribed_circle(
        polygon, tolerance=max(0.0001, math.sqrt(polygon.area) * 0.012)
    )
    (cx, cy), rim = circle.coords
    radius = math.dist((cx, cy), rim)
    theta = np.arange(32) * math.tau / 32
    lobe = 1 + 0.14 * np.cos(3 * theta + 0.45) + 0.075 * np.sin(5 * theta)
    dx = radius * 0.56 * lobe * np.cos(theta)
    dy = radius * 0.40 * lobe * np.sin(theta)
    outer = Polygon(np.column_stack([cx + dx, cy + dy]))
    marrow = Polygon(np.column_stack([cx + 0.46 * dx, cy + 0.46 * dy]))
    return outer, marrow


def _colours(uv, material):
    x, y = uv.T
    if material == "muscle":
        # Close parallel fibre bundles curve around septa instead of reading as a flat red disk.
        fibre = 0.5 + 0.5 * np.sin(48 * x + 9 * np.sin(5 * y + 1.3 * x) + 11 * y)
        septa = np.maximum(0, np.cos(23 * x - 13 * y + 2 * np.sin(6 * y)) - 0.68)
        return (
            np.array([112, 43, 41])
            + fibre[:, None] * [43, 18, 13]
            + septa[:, None] * [58, 62, 52]
        )
    if material == "bone":
        mottling = 0.5 + 0.5 * np.sin(71 * x + 3 * np.sin(35 * y)) * np.cos(46 * y)
        return np.array([195, 161, 115]) + mottling[:, None] * [39, 40, 38]
    marrow = 0.5 + 0.5 * np.sin(x * 108) * np.sin(y * 84)
    return np.array([109, 61, 46]) + marrow[:, None] * [47, 30, 18]


def _triangulate(region, spacing):
    if region.is_empty or region.area < 1e-13:
        return np.empty((0, 3, 2))
    x0, y0, x1, y1 = region.bounds
    triangles = []
    for x in np.arange(x0, x1, spacing):
        for y in np.arange(y0, y1, spacing):
            tile = region.intersection(box(x, y, x + spacing, y + spacing))
            if tile.is_empty or tile.area < 1e-14:
                continue
            faces = shapely.constrained_delaunay_triangles(tile)
            for tri in faces.geoms:
                if tri.area > 1e-15:
                    triangles.append(np.asarray(tri.exterior.coords)[:3])
    return np.asarray(triangles).reshape(-1, 3, 2)


def _cap(mesh_class, segments, normal, origin, label, audit):
    tangent = np.eye(3)[np.argmin(abs(normal))]
    tangent -= np.dot(tangent, normal) * normal
    tangent /= np.linalg.norm(tangent)
    basis = np.stack([tangent, np.cross(normal, tangent)])
    coordinates = np.round((np.asarray(segments) - origin) @ basis.T, 8)
    lines = [
        LineString(pair) for pair in coordinates if not np.array_equal(pair[0], pair[1])
    ]
    contours = unary_union(lines)
    closed = list(polygonize(contours))
    if not closed:
        raise ValueError((label, "no closed section contour", len(lines)))
    # Nested lines come from separate sculpted muscle and cartilage shells. A severed body
    # is opaque across their interiors; disjoint limbs remain separate components.
    section = unary_union(closed)
    components = [p for p in shapely.get_parts(section) if p.area > 1e-10]
    raw_area = sum(p.area for p in components)
    dangling = contours.difference(section.buffer(3e-7)).length
    if dangling > 2e-5:
        # The marble scan contains unwelded hairline fins where clustered triangles converge.
        # Give the actual unmatched edge a microscopic closed profile, then triangulate it
        # together with its parent contour. This never bridges distinct anatomical components.
        remainder = contours.difference(section)
        section = unary_union([section, remainder.buffer(2e-6, quad_segs=3)])
        components = [p for p in shapely.get_parts(section) if p.area > 1e-12]
        raw_area = sum(p.area for p in components)
        dangling = contours.difference(section.buffer(3e-7)).length
        if dangling > 2e-5:
            raise ValueError(
                (label, "unclosed boundary outside filled section", dangling)
            )
    coords, colours = [], []
    for component in components:
        bone, marrow = _bone_island(component)
        regions = (
            (component.difference(bone), "muscle"),
            (bone.difference(marrow), "bone"),
            (marrow, "marrow"),
        )
        spacing = max(0.018, math.sqrt(component.area) / 18)
        for region, material in regions:
            tri = _triangulate(region, spacing)
            if len(tri) == 0:
                continue
            a, b = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
            flip = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0] < 0
            tri[flip] = tri[flip][:, [0, 2, 1], :]
            uv = tri.reshape(-1, 2)
            coords.append(uv)
            colours.append(_colours(uv, material))
    uv = np.vstack(coords)
    tri = uv.reshape(-1, 3, 2)
    a, b = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    area = (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum() / 2
    if abs(raw_area - area) > max(1e-8, raw_area * 2e-6):
        raise ValueError((label, "cap coverage", raw_area, area))
    if audit is not None:
        audit.append(
            dict(
                name=label,
                components=len(components),
                contour_area=raw_area,
                filled_area=area,
                dangling_edges=dangling,
                triangles=len(tri),
            )
        )
    joined = np.column_stack([uv, np.vstack(colours)])
    _, first, indices = np.unique(
        np.round(joined, 7), axis=0, return_index=True, return_inverse=True
    )
    points = origin + uv[first] @ basis
    return mesh_class(
        points,
        np.tile(normal, (len(points), 1)),
        joined[first, 2:],
        indices.reshape(-1, 3),
    )


def clip(surface, keep_normal, offset, label, audit=None):
    """Keep dot(point, keep_normal) >= offset, interpolating every crossed original triangle."""
    n = np.asarray(keep_normal, dtype=float)
    distance = surface.points @ n - offset
    inside = distance >= 0
    tri = surface.faces
    signs = inside[tri]
    complete = np.all(signs, axis=1)
    crossing = np.flatnonzero(signs.any(1) & ~complete)
    if not len(crossing):
        return surface.section(complete)
    vertices = [*surface.points]
    normals = [*surface.normals]
    colours = [*surface.colours]
    indices = {}
    faces = []
    segments = []

    def intersect(a, b):
        key = (min(a, b), max(a, b))
        if key not in indices:
            w = distance[a] / (distance[a] - distance[b])
            v = (1 - w) * surface.points[a] + w * surface.points[b]
            # Snap to the cut plane. Adjacent triangles share the same clipped edge vertex.
            v -= n * (v @ n - offset) / (n @ n)
            normal = (1 - w) * surface.normals[a] + w * surface.normals[b]
            indices[key] = len(vertices)
            vertices.append(v)
            normals.append(normal / max(1e-12, np.linalg.norm(normal)))
            colours.append((1 - w) * surface.colours[a] + w * surface.colours[b])
        return indices[key]

    for idx in crossing:
        triangle = tri[idx]
        polygon = []
        cuts = []
        for a, b in zip(triangle, np.roll(triangle, -1)):
            if inside[a]:
                polygon.append(a)
            if inside[a] != inside[b]:
                k = intersect(a, b)
                polygon.append(k)
                cuts.append(vertices[k])
        faces.extend(
            (polygon[0], polygon[i], polygon[i + 1]) for i in range(1, len(polygon) - 1)
        )
        if np.linalg.norm(cuts[0] - cuts[1]) > 1e-10:
            segments.append(cuts)
    hull = type(surface)(
        np.asarray(vertices),
        np.asarray(normals),
        np.asarray(colours),
        np.vstack([tri[complete], np.asarray(faces, dtype=int)]),
    )
    rim = _cap(
        type(surface),
        segments,
        -n / np.linalg.norm(n),
        n * offset / (n @ n),
        label,
        audit,
    )
    indices = np.vstack([hull.faces, rim.faces + len(hull.points)])
    combined = type(surface)(
        np.vstack([hull.points, rim.points]),
        np.vstack([hull.normals, rim.normals]),
        np.vstack([hull.colours, rim.colours]),
        indices,
    )
    return combined.section(np.ones(len(indices), dtype=bool))


def principal_fragment(surface):
    """Several hanging fingers cross the thigh cutoff. Keep only the detached leg itself."""
    _, inverse = np.unique(np.round(surface.points, 6), axis=0, return_inverse=True)
    faces = inverse.reshape(-1)[surface.faces]
    roots = np.arange(int(faces.max()) + 1)
    while True:
        previous = roots.copy()
        lower = roots[faces].min(axis=1)
        for vertices in faces.T:
            np.minimum.at(roots, vertices, lower)
        roots = roots[roots]
        if np.array_equal(previous, roots):
            break
    groups = roots[faces[:, 0]]
    p = surface.points[surface.faces]
    areas = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    weight = np.bincount(groups, weights=areas)
    return surface.section(groups == weight.argmax())
