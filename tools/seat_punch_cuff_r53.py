"""Prepare punch sockets and seat only the forearm-owned natural-hand cuff rim.

Reads the installed JAR; writes a separate candidate tree and asset-entries.json.
Required runtime source identities are updated, with held-hand predecessors kept.
"""
import argparse
import copy
import hashlib
import json
import os
import zipfile
from pathlib import Path

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import numpy as np

PREFIX = 'assets/projectseele/'
FLIP = np.array([-1., 1., 1.])


def section(points, y):
    segments = []
    for triangle in points.reshape(-1, 3, 3):
        hits = []
        for a, b in zip(triangle, np.roll(triangle, -1, axis=0)):
            if abs(b[1]-a[1]) > 1e-12 and (a[1]-y)*(b[1]-y) <= 0:
                hits.append(a+(b-a)*((y-a[1])/(b[1]-a[1])))
        if len(hits) == 2 and np.linalg.norm(hits[0]-hits[1]) > 1e-10:
            segments.append(hits)
    segments = np.asarray(segments)
    flat = segments.reshape(-1, 3)
    centre = (flat.min(0)+flat.max(0))/2
    # The rear armour fin is an open section separate from the closed sleeve.
    # Both socket and far rim use the actual closed sleeve, not the fin bounds.
    remaining = set(range(len(segments)))
    loops = []
    while remaining:
        component = {remaining.pop()}
        changed = True
        while changed:
            changed = False
            tips = segments[list(component)].reshape(-1, 3)
            for i in list(remaining):
                if np.min(np.linalg.norm(segments[i, :, None]-tips[None, :], axis=2)) < 1e-6:
                    component.add(i); remaining.remove(i); changed = True
        values = segments[list(component)].reshape(-1, 3)
        degrees = np.sum(np.linalg.norm(values[:, None]-values[None, :], axis=2) < 1e-6, axis=1)
        if np.all(degrees == 2):
            loops.append(values)
    if len(loops) != 1:
        raise ValueError('Expected exactly one closed source wrist sleeve')
    sleeve = loops[0]
    sleeve_centre = (sleeve.min(0)+sleeve.max(0))/2
    return sleeve_centre, sleeve_centre, .12


def smooth_normals(points):
    tri = points.reshape(-1, 3, 3)
    face = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])
    if np.any(np.linalg.norm(face, axis=1) < 1e-12):
        raise ValueError('Cuff contains a degenerate triangle')
    _, ids = np.unique(np.round(points, 7), axis=0, return_inverse=True)
    sums = np.zeros((ids.max()+1, 3))
    np.add.at(sums, ids, np.repeat(face, 3, axis=0))
    n = sums[ids]
    return n/np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-12)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    entries = {}
    with zipfile.ZipFile(args.jar) as jar:
        def read(relative):
            return json.loads(jar.read(PREFIX+relative))

        def write(relative, value):
            path = args.out/'resources'/PREFIX/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode('utf8')
            path.write_bytes(data)
            entries[PREFIX+relative] = str(path.resolve())
            return data

        binding = read('eva/eva_original_mesh_geometry_r52_sources.json')
        current = copy.deepcopy(binding['resources'])
        previous = binding.setdefault('held_hand_surface_predecessors', [])
        if current not in previous:
            previous.insert(0, current)
        surface = read('eva/source_surface_r53.json')
        for rig in (0, 1, 2, 4):
            stem = 'eva_un01' if rig == 4 else f'eva_unit0{rig}'
            suffix = '_anatomical_hands_r53' if rig == 4 else '_anatomical_hands_r45'
            relative = 'mesh/'+stem+suffix+'.mesh.json'
            hand_mesh = read(relative)
            body = read('mesh/'+stem+'.mesh.json')
            original_body = copy.deepcopy(body) if rig == 4 else None
            bones = {b['name']: b for b in read('geo/'+stem+'.geo.json')['minecraft:geometry'][0]['bones']}
            sockets = {}
            for side in ('l', 'r'):
                name, forearm = 'hand_'+side, 'forearm_'+side
                part, skin = hand_mesh['parts'][name], hand_mesh['jointSkins'][name]
                old_part, old_skin = copy.deepcopy(part), copy.deepcopy(skin)
                raw = np.asarray(part['vertices']).reshape(-1, 8).copy()
                cuff_count = part.get('handSurfaceLayoutR53', {}).get('cuff_vertex_count', 288)
                if cuff_count != 288:
                    raise ValueError('Unexpected authored cuff topology')
                start = len(raw)-cuff_count
                far = np.flatnonzero(np.asarray(skin['influences'][forearm]) == 1)
                if len(far) != 144 or np.any(far < start):
                    raise ValueError('Unexpected forearm-owned cuff membership')
                if np.any((np.asarray(skin['influences'][forearm]) != 0) & (np.asarray(skin['influences'][forearm]) != 1)):
                    raise ValueError('Cuff forearm weights must be binary')
                points = (raw[:, :3]+part['pivot'])*FLIP/16
                wrist = np.asarray(bones[name]['pivot'])*FLIP/16
                real_elbow = bones.get('r30_elbow_socket_'+side)
                elbow = np.asarray(real_elbow['pivot'])*FLIP/16 if real_elbow else np.array([-23.489652 if side == 'l' else 23.489652, 123.435069, 7.737214])/16
                fp = body['parts'][forearm]
                forearm_points = (np.asarray(fp['vertices']).reshape(-1, 8)[:, :3]+fp['pivot'])*FLIP/16
                depth, rise = (2, 1) if rig == 4 else (6, 3)
                axis_centre, centre, radius = section(forearm_points, wrist[1]+depth/16)
                socket = elbow+(axis_centre-elbow)*((wrist[1]+rise/16-elbow[1])/(axis_centre[1]-elbow[1]))
                sockets[side] = socket.tolist()
                offset = points[far]-points[far].mean(0)
                offset[:, 1] = 0
                length = np.linalg.norm(offset, axis=1)
                if np.any(length < 1e-8):
                    raise ValueError('Invalid source cuff radial direction')
                points[far] = centre+offset/length[:, None]*np.minimum(length, radius)[:, None]
                raw[far, :3] = points[far]*FLIP*16-part['pivot']
                normals = smooth_normals(points[start:])*FLIP
                # Preserve the existing winding convention and every near-rim normal.
                if np.median(np.sum(normals*raw[start:, 5:8], axis=1)) < 0:
                    normals = -normals
                raw[far, 5:8] = normals[far-start]
                part['vertices'] = raw.reshape(-1).tolist()
                far_set = set(far.tolist())
                correction = skin['contactCorrectiveR45']
                rows = []
                for row in correction['vertex_index_position_normal_delta']:
                    if int(row[0]) in far_set:
                        if np.max(np.abs(row[1:4])) > 1e-7:
                            raise ValueError('Far cuff unexpectedly has a fist position corrective')
                        # Its authored bind normal now follows the seated sleeve.
                        continue
                    rows.append(row)
                correction['vertex_index_position_normal_delta'] = rows
                before = np.asarray(old_part['vertices']).reshape(-1, 8)
                unchanged = np.ones(len(raw), dtype=bool); unchanged[far] = False
                if not np.array_equal(raw[unchanged], before[unchanged]) or not np.array_equal(raw[:, 3:5], before[:, 3:5]):
                    raise ValueError('Non-far vertex or UV changed')
                for key in ('influences', 'inverseBindColumnMajor'):
                    if skin[key] != old_skin[key]:
                        raise ValueError('Skin binding changed')
                if rig == 4:
                    if body['parts'][name] != old_part or body['jointSkins'][name] != old_skin:
                        raise ValueError('Unit04 full mesh and separate hand source differ')
                    body['parts'][name] = copy.deepcopy(part)
                    body['jointSkins'][name] = copy.deepcopy(skin)
                print(f'rig {rig} {side}: 144 far vertices; section +{depth}px; socket +{rise}px; radius <= {radius:.6f}')
            data = write(relative, hand_mesh)
            write(f'hand_rigs/unit0{rig}/punch_socket_r53.json', {'rig': rig, 'sockets_native_bind': sockets})
            if rig < 3:
                binding['resources'][relative] = hashlib.sha256(data).hexdigest()
            else:
                for name in body['parts']:
                    if not name.startswith('hand_') and (body['parts'][name] != original_body['parts'][name] or body['jointSkins'][name] != original_body['jointSkins'][name]):
                        raise ValueError('Unit04 non-hand body changed')
                data = write('mesh/eva_un01.mesh.json', body)
                surface['models']['eva_un01']['resources']['mesh'] = hashlib.sha256(data).hexdigest()
        write('eva/eva_original_mesh_geometry_r52_sources.json', binding)
        write('eva/source_surface_r53.json', surface)
    (args.out/'asset-entries.json').write_text(json.dumps(entries, indent=2), encoding='utf8')
    with zipfile.ZipFile(args.out/'punch-socket-resources.zip', 'w', zipfile.ZIP_DEFLATED) as overlay:
        for name, path in entries.items():
            overlay.write(path, name)
    print(f'Prepared {len(entries)} resource entries; candidate only.')


if __name__ == '__main__':
    main()
