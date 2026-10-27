"""Connect the original detachable back shell without cutting or replacing faces."""
import numpy as np


def connect(mesh, bones):
    part = mesh['parts']['torso_upper']
    vertices = np.asarray(part['vertices']).reshape(-1, 3, 8)
    xyz = vertices[:, :, :3] + part['pivot']
    # The preserved source has disconnected armour pieces. Select the central
    # upper-back shell by its actual connected topology, never by clipping faces.
    owners = {}
    neighbours = [set() for _ in xyz]
    for face, tri in enumerate(xyz):
        for point in tri:
            key = tuple(point.round(6))
            for other in owners.get(key, ()):
                neighbours[face].add(other)
                neighbours[other].add(face)
            owners.setdefault(key, []).append(face)
    unseen = set(range(len(xyz)))
    shells = []
    while unseen:
        todo = [unseen.pop()]
        component = []
        while todo:
            face = todo.pop()
            component.append(face)
            for other in neighbours[face] & unseen:
                unseen.remove(other)
                todo.append(other)
        points = xyz[component].reshape(-1, 3)
        lo, hi = points.min(0), points.max(0)
        if lo[0] < -8 and hi[0] > 8 and lo[1] > 145 and hi[1] > 170 and lo[2] > 0:
            shells.append(sorted(component))
    if len(shells) != 1 or len(shells[0]) != 96:
        raise ValueError('The complete original central back shell was not found')
    selected = shells[0]
    panel = xyz[selected]
    # Preserve the service insertion rake. Its intersection with the source
    # shell is the mouth; neither the old UN01 centre nor a new round hole is used.
    origin = np.asarray(bones['entry_plug']['pivot'])
    outward = np.array([0., np.cos(np.deg2rad(20)), np.sin(np.deg2rad(20))])
    intersections = []
    for tri in panel:
        a, b, c = tri
        e1, e2 = b - a, c - a
        h = np.cross(outward, e2)
        det = e1 @ h
        if abs(det) < 1e-8:
            continue
        delta = origin - a
        u = delta @ h / det
        q = np.cross(delta, e1)
        v = outward @ q / det
        distance = e2 @ q / det
        if u >= -1e-7 and v >= -1e-7 and u + v <= 1 + 1e-7 and distance > 0:
            intersections.append(distance)
    if not intersections:
        raise ValueError('The measured source socket does not reach its back shell')
    centre = origin + outward * min(intersections)
    points = np.unique(panel.reshape(-1, 3), axis=0)
    edge = points[points[:, 0] >= points[:, 0].max() - .001]
    hinge = edge.mean(0)
    axis = np.array([0., outward[2], -outward[1]])
    profile = dict(centre=centre.tolist(), outward=outward.tolist(), hinge=hinge.tolist(),
                   hinge_axis=axis.tolist(), open_angle_degrees=105)
    keep = np.array([i for i in range(len(vertices)) if i not in set(selected)])
    part['vertices'] = vertices[keep].ravel().tolist()
    mesh['parts']['dorsal_cover'] = dict(pivot=part['pivot'], vertices=vertices[selected].ravel().tolist())
    skin = mesh['jointSkins']['torso_upper']
    for bone, weights in skin['influences'].items():
        skin['influences'][bone] = np.asarray(weights).reshape(-1, 3)[keep].ravel().tolist()
    mesh['jointSkins']['dorsal_cover'] = dict(influences={'dorsal_cover': [1.] * (len(selected) * 3)},
        inverseBindColumnMajor={'dorsal_cover': np.eye(4).ravel().tolist()})
    # The source also has a six-triangle rear neck plate behind the outer shell.
    # It is the inner hatch of the same lid. Reassign its complete original
    # faces along existing edges; retaining a fixed second skin blocks the plug.
    inner = mesh['parts']['torso_lower']
    inner_vertices = np.asarray(inner['vertices']).reshape(-1, 3, 8)
    inner_xyz = inner_vertices[:, :, :3] + inner['pivot']
    inner_faces = np.flatnonzero((inner_xyz[:, :, 1].min(1) >= 156) &
        (inner_xyz[:, :, 1].max(1) < 168) & (inner_xyz[:, :, 2].min(1) >= 4) &
        (abs(inner_xyz[:, :, 0]).max(1) < 7.1))
    if len(inner_faces) != 6:
        raise ValueError('The complete source inner neck hatch was not found')
    inner_keep = np.array([i for i in range(len(inner_vertices)) if i not in set(inner_faces)])
    inner['vertices'] = inner_vertices[inner_keep].ravel().tolist()
    transferred = inner_vertices[inner_faces].copy()
    transferred[:, :, :3] += np.asarray(inner['pivot']) - part['pivot']
    mesh['parts']['dorsal_cover']['vertices'].extend(transferred.ravel().tolist())
    mesh['jointSkins']['dorsal_cover']['influences']['dorsal_cover'].extend([1.] * 18)
    for bone, weights in mesh['jointSkins']['torso_lower']['influences'].items():
        mesh['jointSkins']['torso_lower']['influences'][bone] = np.asarray(weights).reshape(-1, 3)[inner_keep].ravel().tolist()
    for name in ('entry_plug', 'plug_hatch_l', 'plug_hatch_r', 'dorsal_liner'):
        bones[name]['pivot'] = centre.tolist()
    bones['dorsal_cover']['pivot'] = hinge.tolist()
    mesh['r53_source_dorsal'] = dict(source_part='torso_upper', source_faces=selected,
        inner_source_part='torso_lower', inner_source_faces=inner_faces.tolist(),
        centre=centre.tolist(), hinge=hinge.tolist(), preserved_faces=True)
    support = {}
    for name, item in mesh['parts'].items():
        p = np.unique((np.asarray(item['vertices']).reshape(-1, 8)[:, :3] + item['pivot']) * [-1, 1, 1], axis=0)
        support[name] = p.tolist()
    hulls = [(np.r_[np.asarray(p).min(0), np.asarray(p).max(0)] * 5 / 16).tolist() for p in support.values()]
    return profile, support, hulls


def power_profile(mesh):
    part = mesh['parts']['torso_lower']
    points = np.asarray(part['vertices']).reshape(-1, 8)[:, :3] + part['pivot']
    cover = mesh['parts']['dorsal_cover']
    bottom = (np.asarray(cover['vertices']).reshape(-1, 8)[:, :3] + cover['pivot'])[:, 1].min()
    candidates = np.flatnonzero((abs(points[:, 0]) < .001) & (points[:, 1] < bottom - 3) & (points[:, 1] > bottom - 6))
    if not len(candidates):
        raise ValueError('No source armour point below the moving back shell')
    index = candidates[np.argmax(points[candidates, 2])]
    if mesh['jointSkins']['torso_lower']['influences']['torso_upper'][index] < 1 - 1e-8:
        raise ValueError('Power connector point must follow the actual rigid upper torso')
    mount = points[index] * [-1, 1, 1]
    tail = mount + [0, 0, 2.2 * 16 / 5]
    return dict(origin_native_model_pixels=mount.tolist(), cable_tail_native_model_pixels=tail.tolist(),
                cable_tangent_native=[0, 0, 1], source_armour_point_r53=True)


def same_surface(before, after):
    def triangles(mesh):
        result = []
        for part in mesh['parts'].values():
            values = np.asarray(part['vertices']).reshape(-1, 3, 8).copy()
            values[:, :, :3] += part['pivot']
            result.extend(tuple(v.round(11).ravel()) for v in values)
        return sorted(result)
    return triangles(before) == triangles(after)
