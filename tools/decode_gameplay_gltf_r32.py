"""Decode authored glTF animation to measured world joints for the existing retargeter."""
from pathlib import Path
import json
import struct
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'external-assets/incoming/mocap/quaternius-ual2-standard/Universal Animation Library 2[Standard]/Unreal-Godot/UAL2_Standard.glb'
STANDARD = ROOT / 'external-assets/incoming/mocap/quaternius-ual-standard/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
OUT = ROOT / 'artifacts/combat_sortie_r32/gameplay_sources'

def decode(clip_name, fps=60, source=None, out=None):
    source=Path(source) if source is not None else STANDARD if clip_name.startswith('Jump_') else SOURCE
    data = source.read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20+length])
    binary_start = 20+length+8
    binary = data[binary_start:]
    def accessor(index):
        a = doc['accessors'][index]; v = doc['bufferViews'][a['bufferView']]
        width = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
        if a['componentType'] != 5126:
            raise ValueError('Expected floating animation data')
        offset = v.get('byteOffset', 0)+a.get('byteOffset', 0)
        stride = v.get('byteStride', width*4)
        return np.ndarray((a['count'], width), dtype='<f4', buffer=binary,
                          offset=offset, strides=(stride, 4)).copy()
    animation = next(a for a in doc['animations'] if a['name'] == clip_name) if clip_name is not None else {'channels':[]}
    channels = []
    for c in animation['channels']:
        s = animation['samplers'][c['sampler']]
        channels.append((c['target']['node'], c['target']['path'], accessor(s['input'])[:, 0],
                         accessor(s['output']), s.get('interpolation', 'LINEAR')))
    duration = max((float(c[2][-1]) for c in channels),default=0)
    times = np.linspace(0, duration, round(duration*fps)+1)
    parents = [-1]*len(doc['nodes'])
    for i, node in enumerate(doc['nodes']):
        for child in node.get('children', []): parents[child] = i
    alias = {'pelvis': 'Hip', 'spine_01': 'LowerSpine', 'spine_03': 'Chest', 'neck_01': 'Neck', 'Head': 'Head','head':'Head','head_leaf':'Head_End'}
    for side in ['l', 'r']:
        for bone_prefix, name in [('upperarm', 'Shoulder'), ('lowerarm', 'Forearm'), ('hand', 'Hand'), ('thigh', 'Thigh'), ('calf', 'Shin'), ('foot', 'Foot'), ('ball', 'Toe'), ('ball_leaf', 'Toe_End'), ('middle_01', 'Finger2'), ('thumb_01', 'Finger0')]:
            alias[bone_prefix+'_'+side] = side.upper()+name
    names = [alias.get(n.get('name'), n.get('name', str(i))) for i, n in enumerate(doc['nodes'])]
    synthetic_head_end='Head_End' not in names
    if synthetic_head_end:names.append('Head_End')
    positions, rotations = [], []
    for at in times:
        trs = [{k: np.array(node.get(k, default), float) for k, default in
                [('translation', [0, 0, 0]), ('rotation', [0, 0, 0, 1]), ('scale', [1, 1, 1])]}
               for node in doc['nodes']]
        for node, path, ts, values, interpolation in channels:
            i = int(np.clip(np.searchsorted(ts, at, side='right')-1, 0, len(ts)-1)); j = min(i+1, len(ts)-1)
            u = float(np.clip((at-ts[i])/max(1e-8, ts[j]-ts[i]), 0, 1))
            if interpolation == 'STEP' or i == j: value = values[i]
            elif interpolation == 'LINEAR':
                value = Slerp([0, 1], Rotation.from_quat(values[[i, j]]))([u])[0].as_quat() if path == 'rotation' else values[i]*(1-u)+values[j]*u
            else: raise ValueError('Unsupported animation interpolation '+interpolation)
            trs[node][path] = value
        cache = {}
        def world(i):
            if i in cache: return cache[i]
            t = trs[i]; matrix = np.eye(4)
            if 'matrix' in doc['nodes'][i]:
                assert not any(c[0]==i for c in channels),'Animated matrix nodes require explicit decomposition'
                matrix=np.asarray(doc['nodes'][i]['matrix']).reshape(4,4).T
            else:
                matrix[:3, :3] = Rotation.from_quat(t['rotation']).as_matrix() @ np.diag(t['scale'])
                matrix[:3, 3] = t['translation']
            if parents[i] >= 0: matrix = world(parents[i]) @ matrix
            cache[i] = matrix; return matrix
        points, qs = [], []
        for i in range(len(doc['nodes'])):
            m = world(i); points.append(m[:3, 3]); axes = m[:3, :3]/np.maximum(1e-9, np.linalg.norm(m[:3, :3], axis=0))
            qs.append(Rotation.from_matrix(axes).as_quat())
        h = names.index('Head'); pelvis = names.index('Hip')
        head_length = max(.05, np.linalg.norm(points[h]-points[pelvis])*.25)
        neck = names.index('Neck'); up = points[h]-points[neck]; up /= max(1e-8, np.linalg.norm(up))
        if synthetic_head_end:points.append(points[h]+up*head_length);qs.append(qs[h])
        positions.append(points); rotations.append(qs)
    output=Path(out) if out is not None else OUT
    output.mkdir(parents=True, exist_ok=True)
    target = output / ((clip_name or 'REST_BIND')+'.npz')
    np.savez_compressed(target, names=np.asarray(names), positions=np.asarray(positions), rotations=np.asarray(rotations), fps=fps, source=str(source), source_clip=clip_name)
    return target

if __name__ == '__main__':
    for clip in ['A_TPose', 'Jump_Start', 'Jump_Loop', 'Jump_Land', 'Melee_Hook', 'Melee_Hook_Rec']:
        print(decode(clip))
