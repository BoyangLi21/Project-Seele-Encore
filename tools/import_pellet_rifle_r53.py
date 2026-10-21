"""Stage a complete owner-supplied OBJ rifle; never write the installed pack.

Blender tessellates original polygon loops, preserving each corner's UV and
normal. No decimation, nonuniform scaling, texture repainting or resizing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def triangulate(source, destination):
    import bpy
    import numpy as np
    positions, uv, normals, faces = [], [], [], []
    def index(value, length):
        n = int(value)
        return n - 1 if n > 0 else length + n
    for line in source.read_text('utf8').splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == 'v':
            positions.append(list(map(float, fields[1:4])))
        elif fields[0] == 'vt':
            uv.append(list(map(float, fields[1:3])))
        elif fields[0] == 'vn':
            normals.append(list(map(float, fields[1:4])))
        elif fields[0] == 'f':
            refs = [item.split('/') for item in fields[1:]]
            if any(len(item) != 3 or not all(item) for item in refs):
                raise ValueError('Every source corner must carry position/UV/normal')
            faces.append([tuple(index(v, n) for v, n in zip(item,
                          [len(positions), len(uv), len(normals)])) for item in refs])
    if (len(positions), len(uv), len(normals), len(faces)) != (4745, 7061, 7811, 5004):
        raise ValueError('Unexpected source topology; inspect this asset separately')
    mesh = bpy.data.meshes.new('Exact OBJ polygon loops')
    mesh.from_pydata(positions, [], [[r[0] for r in f] for f in faces])
    mesh.update()
    mesh.calc_loop_triangles()
    corners = [ref for face in faces for ref in face]
    rows, polygon_ids = [], []
    for triangle in mesh.loop_triangles:
        for loop in triangle.loops:
            p, t, n = corners[loop]
            rows.append(positions[p] + uv[t] + normals[n])
        polygon_ids.append(triangle.polygon_index)
    if len(rows) != 9136 * 3 or set(polygon_ids) != set(range(5004)):
        raise ValueError('Tessellation lost source polygons')
    np.savez_compressed(destination, corners=np.asarray(rows),
                        polygon_ids=polygon_ids, positions=positions)


def stage(args):
    import numpy as np
    from PIL import Image
    out, source = args.out, args.source
    out.mkdir(parents=True, exist_ok=False)
    obj = source / 'Evangelion Pellet Rifle.obj'
    raw = out / 'source-corners.npz'
    subprocess.run([str(args.blender), '-b', '-t', '2', '--disable-autoexec',
                    '--python-exit-code', '1', '--python', str(Path(__file__).resolve()),
                    '--', '--triangulate', str(obj), str(raw)], check=True)
    a = np.load(raw)['corners']
    origin = np.asarray(args.origin)
    # Stored Bedrock X is reflected by the runtime. This determinant -1
    # permutation therefore preserves winding in the actual rendered frame.
    basis = np.asarray([[0, 0, 1], [1, 0, 0], [0, -1, 0]])
    values = a.copy()
    values[:, :3] = (a[:, :3] - origin) @ basis.T * args.scale
    values[:, 4] = 1 - a[:, 4]
    values[:, 5:] = a[:, 5:] @ basis.T
    lengths = np.linalg.norm(values[:, 5:], axis=1)
    invalid = lengths < 1e-10
    source_triangles = a[:, :3].reshape(-1, 3, 3)
    source_cross = np.cross(source_triangles[:, 1] - source_triangles[:, 0],
                            source_triangles[:, 2] - source_triangles[:, 0])
    for corner in np.flatnonzero(invalid):
        face = corner // 3
        fallback = source_cross[face]
        if np.linalg.norm(fallback) < 1e-12:
            fallback = a[face*3:face*3+3, 5:].sum(axis=0)
        if np.linalg.norm(fallback) < 1e-12:
            fallback = np.asarray([0., 0., 1.])
        values[corner, 5:] = fallback @ basis.T
    values[:, 5:] /= np.linalg.norm(values[:, 5:], axis=1, keepdims=True)
    if not np.isfinite(values).all():
        raise ValueError('Nonfinite source geometry')
    native = values[:, :3] * [-1, 1, 1]
    triangles = native.reshape(-1, 3, 3)
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normal = (values[:, 5:] * [-1, 1, 1]).reshape(-1, 3, 3).mean(axis=1)
    signed = (cross * normal).sum(axis=1)
    if np.any(signed < -1e-7):
        raise ValueError('Source normals oppose rendered triangle winding')
    with zipfile.ZipFile(args.installed) as installed:
        old = json.loads(installed.read('assets/projectseele/mesh/eva_pallet_smg.mesh.json'))
    assets = out / 'assets/projectseele'
    mesh_path = assets / 'mesh/eva_pallet_smg.mesh.json'
    mesh_path.parent.mkdir(parents=True)
    fingerprints = {p.name: sha(p) for p in sorted(source.iterdir()) if p.is_file()}
    bounds = [values[:, :3].min(axis=0).tolist(), values[:, :3].max(axis=0).tolist()]
    document = dict(format_version=1, stride=8, local_only=True, release_approved=False,
                    source='Owner-supplied Evangelion Pellet Rifle; full source surface',
                    source_sha256=fingerprints, triangle_count=9136,
                    model_height=bounds[1][1]-bounds[0][1],
                    parts={'cannon': dict(pivot=old['parts']['cannon']['pivot'],
                                           vertices=values.round(7).ravel().tolist())})
    mesh_path.write_text(json.dumps(document, separators=(',', ':'), allow_nan=False), 'utf8')
    textures = assets / 'textures/entity'
    textures.mkdir(parents=True)
    prefix = 'Evangelion_Pellet_Rifle_'
    images = {}
    for name in ('albedo', 'normal', 'AO', 'Roughness', 'metallic'):
        with Image.open(source / (prefix + name + '.png')) as im:
            if im.size != (2048, 2048):
                raise ValueError('Unexpected source texture dimensions')
            images[name] = np.asarray(im.convert('RGBA')).copy()
    shutil.copy2(source / (prefix + 'albedo.png'), textures / 'eva_pallet_smg.png')
    n = images['normal']
    if args.normal_y == 'opengl':
        n[:, :, 1] = 255 - n[:, :, 1]
    n[:, :, 2] = images['AO'][:, :, 0]
    n[:, :, 3] = 255
    Image.fromarray(n).save(textures / 'eva_pallet_smg_n.png')
    spec = np.zeros_like(n)
    spec[:, :, 0] = 255 - images['Roughness'][:, :, 0]
    spec[:, :, 1] = np.where(images['metallic'][:, :, 0] >= 128, 255, 10)
    spec[:, :, 3] = 255
    Image.fromarray(spec).save(textures / 'eva_pallet_smg_s.png')
    # Geometric support uses every unique original point. Its extrema under
    # any linear frame are identical to those of the complete triangle mesh.
    points = np.unique(values[:, :3].round(7), axis=0) * [-1, -1, -1] * (5 * .72 / 16)
    cap = values[values[:, 1] <= values[:, 1].min() + .85, :3].mean(axis=0)
    muzzle = cap * [-1, -1, -1] * (5 * .72 / 16)
    def weapon_frame(xyz):
        stored = (np.asarray(xyz) - origin) @ basis.T * args.scale
        return (stored * [-1, -1, -1] * (5 * .72 / 16)).tolist()
    geometry = dict(schema='projectseele.rifle-geometry.r53.v1', mesh_sha256=sha(mesh_path),
                    points=points.tolist(), muzzle=muzzle.tolist(),
                    stock=weapon_frame([11.1, .8, 0]),
                    dominant_pad=weapon_frame([2, -1.7, -.5]),
                    supporting_pad=weapon_frame([-3.4, -.1, 0]),
                    source_origin=origin.tolist(), uniform_scale=args.scale)
    motion = assets / 'motion/rifle_clearance_r10.json'
    motion.parent.mkdir(parents=True)
    motion.write_text(json.dumps(geometry, separators=(',', ':')), 'utf8')
    receipt = dict(source_sha256=fingerprints, polygons=5004, triangles=9136,
                    all_source_polygons_preserved=True, bounds=bounds,
                    source_origin=origin.tolist(), uniform_scale=args.scale,
                    minimum_winding_normal_dot=float(signed.min()),
                    source_zero_normal_corners_reconstructed=int(invalid.sum()),
                    source_degenerate_triangles=int((np.linalg.norm(source_cross, axis=1) < 1e-12).sum()),
                    texture_dimensions=[2048, 2048], normal_source_convention=args.normal_y,
                    albedo_byte_identical=sha(textures/'eva_pallet_smg.png') == fingerprints[prefix+'albedo.png'],
                    pbr_specification='https://shaderlabs.org/wiki/LabPBR_Material_Standard',
                    geometry=geometry | {'points': len(points)},
                    installed=False, native_reviewed=False)
    (out / 'RECEIPT.json').write_text(json.dumps(receipt, indent=2), 'utf8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'source_sha256'}, indent=2))


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    if argv and argv[0] == '--triangulate':
        triangulate(Path(argv[1]), Path(argv[2]))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        for key in ('source', 'out', 'blender', 'installed'):
            parser.add_argument('--' + key, type=Path, required=True)
        parser.add_argument('--scale', type=float, default=5.05)
        parser.add_argument('--origin', type=float, nargs=3, default=[.61, -1.414, 0])
        parser.add_argument('--normal-y', choices=['opengl', 'directx'], required=True)
        stage(parser.parse_args(argv))
