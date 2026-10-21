"""Export the supplied carrier with rigid mechanical fitting, retaining its UVs.

Run with Blender 3.6 in background mode, passing --source, --texture and --output
after ``--``. The output is private user-supplied content, never a public asset.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np

SOURCE_SHA = 'a51093f2bcf82d864d0ad1517a3a9a815fa0729dab87c08cdc12ff79e34c8941'
TEXTURE_SHA = 'f283dc0f0ae44d9198650a4046870c41992c92575b7b2364e6bcf97fee332972'
TOES = {'toe_l': [2096, 2386, 2441, 2445], 'toe_r': [3666, 3687, 3754, 3757]}
JAWS = {'clamp_lower_l': (2843, -2.7), 'clamp_lower_r': (4466, 4.1),
        'clamp_upper_l': (3216, -2.7), 'clamp_upper_r': (5057, 4.7)}
SCALE = 57.0
Y_OFFSET = -4.0078125
TOE_PIVOT = np.array([0, -.111328125, -9.115])
PEDAL_OFFSET = np.array([0, -.75, 10.0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--texture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    assert hashlib.sha256(args.source.read_bytes()).hexdigest() == SOURCE_SHA
    assert hashlib.sha256(args.texture.read_bytes()).hexdigest() == TEXTURE_SHA
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(args.source))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    assert len(objects) == 1
    obj = objects[0];mesh = obj.data
    mesh.calc_loop_triangles();mesh.calc_normals_split()
    positions = np.array([obj.matrix_world @ v.co for v in mesh.vertices])
    triangles = np.array([t.vertices for t in mesh.loop_triangles], dtype=np.int32)
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    normals = np.array([[normal_matrix @ mesh.loops[i].normal for i in t.loops]
                        for t in mesh.loop_triangles])
    uv = np.array([[mesh.uv_layers.active.data[i].uv[:] for i in t.loops]
                   for t in mesh.loop_triangles])
    assert len(triangles) == 8727
    parents = np.arange(len(positions))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]];i = parents[i]
        return i
    for a,b,c in triangles:
        a,b,c = root(a),root(b),root(c);parents[b] = a;parents[c] = a
    components = np.array([root(t[0]) for t in triangles])
    assert len(np.unique(components)) == 137
    xyz = positions[triangles][:,:,[0,2,1]] * SCALE
    xyz[:,:,1] += Y_OFFSET
    normals = normals[:,:,[0,2,1]]
    normals /= np.linalg.norm(normals,axis=2,keepdims=True)
    groups = np.array(['body'] * len(triangles),dtype=object)
    component_report = []
    for component in np.unique(components):
        indices = components == component
        points = xyz[indices]
        if points[:,:,1].max() <= .9:
            groups[indices] = 'deck'
        if component in [2146,4017]:
            xyz[indices,:,1] -= .17
        if component == 1199:
            # Uniformly size the lower brace to the measured heel clearance;
            # no surface is cut out or simplified.
            pivot = np.array([0,-1.03,13.179])
            xyz[indices] = (xyz[indices]-pivot)*.65+pivot
            groups[indices] = 'deck'
        for name, ids in TOES.items():
            if component in ids:
                groups[indices] = name
                # This is a standing pedal with a heel rest, not a rising
                # front restraint. Preserve its authored orientation.
                xyz[indices] += PEDAL_OFFSET
        for name,(selected,offset) in JAWS.items():
            if component == selected:
                groups[indices] = name;xyz[indices,:,0] += offset
        if groups[indices][0] == 'body' and xyz[indices,:,2].min() < 7.7:
            groups[indices] = 'retract_spine' if component == 5182 else 'retract_body'
        component_report.append({'id':int(component),'part':str(groups[indices][0]),
                                 'triangles':int(indices.sum())})
    # The source-to-game axis permutation reverses handedness. Reverse faces
    # along with their UVs and split normals, then use Minecraft's V direction.
    xyz = xyz[:,[0,2,1],:];normals = normals[:,[0,2,1],:]
    uv = uv[:,[0,2,1],:];uv[:,:,1] = 1-uv[:,:,1]
    encoded = np.concatenate([xyz,uv,normals],axis=2).astype(np.float32)
    parts = {str(name):encoded[groups==name].reshape(-1).tolist()
             for name in np.unique(groups)}
    source_parts=set(parts)
    def box(name,lo,hi):
        lo=np.array(lo);hi=np.array(hi);rows=[]
        for axis in range(3):
            other=[i for i in range(3) if i!=axis]
            for side in (0,1):
                normal=np.zeros(3);normal[axis]=2*side-1
                corners=[]
                for u,v in [(0,0),(1,0),(1,1),(0,1)]:
                    p=lo.copy();p[axis]=hi[axis] if side else lo[axis]
                    p[other[0]]=hi[other[0]] if u else lo[other[0]]
                    p[other[1]]=hi[other[1]] if v else lo[other[1]]
                    corners.append(np.r_[p,u,v,normal])
                if np.dot(np.cross(corners[1][:3]-corners[0][:3],corners[2][:3]-corners[0][:3]),normal)<0:
                    corners=corners[::-1]
                for indices in [(0,1,2),(0,2,3)]:rows.extend(corners[i] for i in indices)
        parts[name]=np.asarray(rows,dtype=np.float32).reshape(-1).tolist()
    # The relocated jaws run on explicit back-mounted telescoping brackets;
    # they must not become floating details after fitting the armour width.
    for name,(_,offset) in JAWS.items():
        a=xyz[components==JAWS[name][0]].reshape(-1,3)
        centre=a.mean(0);side=-1 if offset<0 else 1
        x=centre[0];y=(a[:,1].min()+a[:,1].max())/2
        source_x=x-offset
        box('retract_mount_'+name[6:],[min(source_x,x+side*4.5)-.3,y-.35,7.4],
            [max(source_x,x+side*4.5)+.3,y+.35,8.1])
        box(name+'_spindle',[x-.3,y-.3,5.25],[x+.3,y+.3,7.85])
    out = args.output;out.mkdir(parents=True,exist_ok=True)
    texture_path = out/'textures/entity/carrier_mk2_r53.png'
    texture_path.parent.mkdir(parents=True,exist_ok=True)
    img = bpy.data.images.load(str(args.texture));img.pack();img.file_format='PNG'
    img.filepath_raw=str(texture_path);img.save()
    document = {'schema':'projectseele.r53.carrier-assembly.v1','stride':8,
                'source_sha256':SOURCE_SHA,'source_triangles':8727,
                'texture':'projectseele:textures/entity/carrier_mk2_r53.png',
                'parts':parts,'materials':{n:'minecraft:textures/block/iron_block.png'
                    for n in parts if n not in source_parts},
                'anchors':{'toe_pivot':(TOE_PIVOT+PEDAL_OFFSET).tolist(),
                    'power_reel':[10.75,13.1,12.8]},
                'fitting':{'scale':SCALE,'y_offset':Y_OFFSET,
                    'lower_brace_uniform_scale':.65,'toe_closed_degrees':0,
                    'pedal_offset':PEDAL_OFFSET.tolist(),
                    'jaw_offsets':{n:v[1] for n,v in JAWS.items()},
                    'parts_are_rigid':True,'source_faces_removed':0,
                    'engineering_triangles':sum(len(v)//24 for n,v in parts.items() if n not in source_parts)},
                'components':component_report}
    asset_path=out/'mesh/carrier_mk2_r53.json';asset_path.parent.mkdir(parents=True,exist_ok=True)
    asset_path.write_text(json.dumps(document,separators=(',',':')),encoding='utf-8')
    manifest={'schema':'projectseele.r53.carrier-selection.v1','resources':{
        str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [asset_path,texture_path]}}
    selection=out/'eva/carrier_assembly_r53_sources.json';selection.parent.mkdir(parents=True,exist_ok=True)
    selection.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'triangles':len(triangles),'components':len(component_report),
                      'parts':{n:len(v)//24 for n,v in parts.items()},
                      'bounds':[xyz.min((0,1)).tolist(),xyz.max((0,1)).tolist()],
                      'texture_size':list(img.size),'resources':manifest['resources']}))


if __name__ == '__main__':
    main()
