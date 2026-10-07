"""Read supplied Tripo FBX in Blender; never modify the supplied rig or surface."""
from pathlib import Path
import argparse
import json
import sys
import bpy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(args.source.glob('unit*/*.fbx')):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(path))
        rigs = []
        for obj in bpy.data.objects:
            if obj.type != 'ARMATURE':
                continue
            rigs.append(dict(name=obj.name, matrix_world=[list(row) for row in obj.matrix_world],
                             bones=[dict(name=b.name, parent=b.parent.name if b.parent else None,
                                         head=list(b.head_local), tail=list(b.tail_local),
                                         deform=b.use_deform) for b in obj.data.bones]))
        meshes = []
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            weights = {g.index: dict(name=g.name, vertices=0) for g in obj.vertex_groups}
            weighted = 0
            for v in obj.data.vertices:
                positive = [g for g in v.groups if g.weight > 0.00001]
                weighted += bool(positive)
                for g in positive:
                    weights[g.group]['vertices'] += 1
            meshes.append(dict(name=obj.name, vertices=len(obj.data.vertices),
                               faces=len(obj.data.polygons),
                               triangles=sum(len(p.vertices)-2 for p in obj.data.polygons),
                               dimensions=list(obj.dimensions), weighted_vertices=weighted,
                               vertex_groups=list(weights.values()),
                               armature_modifiers=[dict(name=m.name, rig=m.object.name if m.object else None)
                                                   for m in obj.modifiers if m.type == 'ARMATURE'],
                               materials=[m.name if m else None for m in obj.data.materials]))
        animations = [dict(name=a.name, frames=list(a.frame_range)) for a in bpy.data.actions]
        report = dict(source=str(path), rigs=rigs, meshes=meshes, animations=animations,
                      images=[dict(name=i.name, path=i.filepath, size=list(i.size)) for i in bpy.data.images])
        target = args.out / (path.parent.name + '_inspection.json')
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        summary = dict(unit=path.parent.name, rigs=len(rigs), bones=sum(len(r['bones']) for r in rigs),
                       meshes=len(meshes), weighted_vertices=sum(m['weighted_vertices'] for m in meshes),
                       total_vertices=sum(m['vertices'] for m in meshes), animations=len(animations), report=str(target))
        print(json.dumps(summary))
        results.append(summary)
    (args.out / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
