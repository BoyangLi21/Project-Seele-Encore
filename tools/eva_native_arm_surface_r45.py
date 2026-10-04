"""Replay the current original arm's automatic seam weights for contact authoring.

Only the existing elbow/wrist seams are reconstructed, retaining the actual
part vertices. Every use must first compare against native emitted surfaces.
"""
import numpy as np
from scipy.spatial import cKDTree
from rebind_anatomical_hand_r45 import dq_pose


def arm_surfaces(mesh, side):
    names = ['arm_' + side, 'forearm_' + side, 'hand_' + side]
    raw = {n: np.array(mesh['parts'][n]['vertices']).reshape(-1, mesh['stride'])[:, :3]
           + mesh['parts'][n]['pivot'] for n in names}
    result = {n: dict(points=raw[n].copy(), influences={n: np.ones(len(raw[n]))}) for n in names}
    for upper, lower in zip(names, names[1:]):
        tree = cKDTree(raw[lower])
        seam = []
        for point in raw[upper]:
            ids = tree.query_ball_point(point, .002)
            if not ids:
                continue
            centre = (point + raw[lower][min(ids)]) * .5
            if not any(np.dot(p - centre, p - centre) < .002 ** 2 for p in seam):
                seam.append(centre)
        if len(seam) < 3:
            continue
        tree = cKDTree(np.array(seam))
        for name, other in ((upper, lower), (lower, upper)):
            distance, nearest = tree.query(raw[name])
            t = np.maximum(0, 1 - distance / 6)
            weights = .5 * t * t * (3 - 2 * t)
            exact = distance < .002
            weights[exact] = .5
            rest = raw[name].copy()
            rest[exact] = np.array(seam)[nearest[exact]]
            part = result[name]
            own = part['influences'][name]
            taken = np.minimum(own, weights)
            own -= taken
            part['influences'][other] = part['influences'].get(other, 0) + taken
            # Mirrors mergeJointSkin's rest buffer ownership at the second seam.
            part['points'] = rest
    for part in result.values():
        part['points'] *= [-1 / 16, 1 / 16, 1 / 16]
    return result


def deform(part, matrices):
    names = list(part['influences'])
    weights = np.array([part['influences'][n] for n in names]).T
    return dq_pose(part['points'], weights, [matrices[n] for n in names])
