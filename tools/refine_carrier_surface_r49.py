"""Preserve the supplied crane's proportions and attach cable to real steel.

The R48 export stretched three axes differently and remapped height through
six bands. This revision uses one uniform scale for the exposed structure;
only excess under-floor trolley depth is cropped. Original UV/PBR is retained.
"""
from pathlib import Path
import argparse
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'artifacts/rebuild_r48/tripo_pipeline/carrier'
    raw = np.load(source/'lod0_geometry.npz')
    old = np.load(source/'game_geometry.npz')
    src = raw['vertices'].astype(float)
    faces = raw['triangles']
    labels = old['labels'].copy()
    uv = raw['uv'].copy()
    uv[:, :, 1] = 1-uv[:, :, 1]
    origin = np.array([.04, .08, 0])
    scale = 62.0
    vertices = (src-origin)*scale
    vertices[:, 1] = np.maximum(vertices[:, 1], -2.2)
    tri = vertices[faces]
    cross = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])
    length = np.linalg.norm(cross, axis=1)
    keep = length > 1e-8
    face_normals = cross/np.maximum(length[:, None], 1e-8)
    normals = raw['normals'].astype(float)
    normals /= np.maximum(np.linalg.norm(normals, axis=2, keepdims=True), 1e-8)
    cropped = np.any(src[faces, 1] < .08-2.2/scale, axis=1)
    normals[cropped] = face_normals[cropped, None, :]
    encoded = np.concatenate([tri, uv, normals], axis=2)
    parts = {label:np.round(encoded[(labels == label)&keep], 6).ravel().tolist()
             for label in sorted(set(labels))}
    # Select an actual point on the supplied right rear upright, not the old
    # invented (0,47,9.3) endpoint suspended away from any crane surface.
    body_ids = np.unique(faces[labels == 'body'])
    candidates = body_ids[(src[body_ids, 1] > .5)&(src[body_ids, 2] > .08)]
    desired = np.array([.21, .76, .18])
    mount_id = candidates[np.argmin(np.linalg.norm(src[candidates]-desired, axis=1))]
    anchors = dict(service_platform=((np.array([-.171, .590, .045])-origin)*scale).tolist(),
                   power_reel=vertices[mount_id].tolist())
    doc = dict(format_version=1, stride=8, units='blocks',
               texture='projectseele:textures/entity/tripo_carrier_r48.png',
               source='User supplied crane; uniform exposed structure with original UV/PBR; under-floor base cropped',
               parts=parts, anchors=anchors, triangles=int(keep.sum()),
               bounds=[vertices[faces[keep]].min((0,1)).tolist(), vertices[faces[keep]].max((0,1)).tolist()],
               r49_uniform_structure=dict(scale=scale, source_origin=origin.tolist(),
                                           cut_below_floor=-2.2, cable_anchor_source_vertex=int(mount_id)))
    target = args.assets/'mesh/tripo_carrier_r48.json'
    target.write_text(json.dumps(doc, separators=(',', ':')), encoding='utf-8')
    np.savez_compressed(args.out/'game_geometry.npz', vertices=vertices, triangles=faces[keep],
                        labels=labels[keep], uv=uv[keep], normals=normals[keep])
    # Export the true fully-folded sweep for the existing shared clearance contract.
    folded = vertices[faces[keep]].copy()
    hinge = np.asarray(anchors['service_platform'])
    platform = labels[keep] == 'service_platform'
    delta = folded[platform]-hinge
    folded[platform] = np.stack([delta[:,:,1],-delta[:,:,0],delta[:,:,2]],axis=2)+hinge
    bounds = [folded.min((0,1)).tolist(), folded.max((0,1)).tolist()]
    report = dict(uniform_scale=scale, original_topology_UV_PBR_retained=True,
                  unwarped_main_structure=True, cut_buried_depth=-2.2,
                  actual_power_anchor=anchors['power_reel'], folded_bounds=bounds,
                  folded_width=bounds[1][0]-bounds[0][0], folded_depth=bounds[1][2]-bounds[0][2],
                  native_verified=False, art_accepted=False)
    if report['folded_width'] >= 31 or report['folded_depth'] >= 31:
        raise ValueError('Complete supplied carrier cannot enter original shaft')
    (args.out/'REPORT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
