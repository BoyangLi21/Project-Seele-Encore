"""Bind unchanged body binaries to exact reverse-corner resource head meshes.

No WORLD reads or writes. Native export comparison remains Root's final check.
"""
import argparse
import copy
import gzip
import json
from pathlib import Path
import shutil
import struct
import numpy as np
from build_current_launch_height_hulls import read_mesh
from upright_native_anchor_selection_r53 import read, require, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original-assembly', 'association', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Fresh immutable source directory required')
    association = read(args.association)
    model_file = ROOT/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json'
    transfer_file = model_file.with_name('outer_head_transfer_r53.json')
    model, transfer = read(model_file), read(transfer_file)
    require(sha(model_file) == association['new_model_sha256'] and sha(transfer_file) == association['new_head_transfer_sha256'],
            'Explicit current reverse-corner resources required')
    require(association['runner_parts_exactly_equal'] and association['head_transfer_parts_and_overrides_exactly_equal'],
            'Captured profile reuse needs exact unchanged local head geometry')
    old_export = read(args.original_assembly/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json')
    parts = {p['name']: p for p in model['parts']}
    overlays = transfer['parts']+transfer['socket_overrides']
    for p in overlays:
        parts.pop(p['name'], None)
    parts.update({p['name']: p for p in overlays})
    old_heads = read_mesh(args.original_assembly/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz')
    for name, p in parts.items():
        if p['frame'] != 'ROOT':
            require(np.array_equal(np.array(p['triangles_rgb']).reshape(-1, 6)[:, :3].reshape(-1, 3, 3), old_heads[name][1]),
                    'Any changed moving vertex requires a fresh tangent certificate')
    args.output.mkdir(parents=True)
    sources = {str(model_file): sha(model_file), str(transfer_file): sha(transfer_file)}
    for v in range(3):
        name = f'ACTUAL_FIXED_ASSEMBLY.variant{v}.bin.gz'
        source, target = args.original_assembly/name, args.output/name
        require(old_export['sources_sha256'][str(source.resolve())] == sha(source), 'Original current body binary differs')
        shutil.copy2(source, target); sources[str(target.resolve())] = sha(target)
    target = args.output/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz'
    with gzip.open(target, 'wb') as out:
        out.write(struct.pack('>i', len(parts)))
        for name, p in parts.items():
            for value in (name, p['role']):
                raw = value.encode('utf8'); out.write(struct.pack('>H', len(raw))); out.write(raw)
            xyz = np.array(p['triangles_rgb']).reshape(-1, 6)[:, :3]
            out.write(struct.pack('>i', xyz.size)); out.write(xyz.astype('>f8').tobytes())
    sources[str(target.resolve())] = sha(target)
    export = copy.deepcopy(old_export)
    export.update(head_source_sha256=sha(transfer_file), sources_sha256=sources,
        head_templates=[dict(name=name, frame=p['frame'], role=p['role'], triangles=len(p['triangles_rgb'])//18) for name, p in parts.items()],
        rigid_reverse_diagonal_resource_association_sha256=sha(args.association),
        unchanged_original_body_binaries=True, actual_resource_derived_head_source=True,
        native_new_export_comparison_pending=True, world_written=False)
    (args.output/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json').write_text(json.dumps(export, indent=2)+'\n', encoding='utf8')
    cones = read(args.original_assembly/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json')
    cones.update(head_source_sha256=sha(transfer_file), actual_moving_vertices_exactly_unchanged=True,
                 rigid_corner_association_sha256=sha(args.association))
    (args.output/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json').write_text(json.dumps(cones, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(output=str(args.output), exact_unchanged_fixed_variants=3, head_parts=len(parts),
                         model_sha256=sha(model_file), head_transfer_sha256=sha(transfer_file))), flush=True)


if __name__ == '__main__':
    main()
