"""Editable Unit-01 body study and an independent game-JSON round trip.

Blender background script. Inputs are read-only; outputs stay in the R40 lab.
The hip/thigh/knee shell is rigid in the actual runtime too. Automatic wrist,
neck and ankle seam skins are not used to judge this hip-focused round trip.
"""
from pathlib import Path
import sys, json, copy, hashlib, math, argparse
import bpy
from mathutils import Matrix, Vector, Quaternion

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_eva_motion_lab_3d import load_geo, target_to_blender, make_collection
from build_eva_motion_lab_armature import build_armature, build_weighted_mesh, make_clip_action, geometry_bind_rotations

OUT = ROOT / 'artifacts/world_combat_r40/body_lab'
PACK = ROOT / 'run/resourcepacks/eva_real_model/assets/projectseele'
GEO = PACK / 'geo/eva_unit01.geo.json'
MESH = PACK / 'mesh/eva_unit01.mesh.json'
PROFILE = ROOT / 'run/projectseele-local-maps/eva_gameplay_r32_1.json'
parser=argparse.ArgumentParser()
parser.add_argument('--profile',type=Path,default=PROFILE)
parser.add_argument('--out',type=Path,default=OUT)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
PROFILE=args.profile.resolve();OUT=args.out.resolve()
BASIS = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
FOCUS = ('root', 'torso_lower', 'torso_upper', 'leg_l', 'leg_r', 'shin_l', 'shin_r', 'foot_l', 'foot_r')


def reset():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def clay():
    mat = bpy.data.materials.new('Neutral body diagnostic clay')
    mat.use_nodes = True
    shader = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if shader is None:
        shader = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    shader.inputs['Base Color'].default_value = (.45, .48, .5, 1)
    shader.inputs['Roughness'].default_value = .65
    return mat


def scene_from(motion):
    reset()
    collection = make_collection('R40_HIP_DIAGNOSIS')
    bones, pivots, parents = load_geo(GEO)
    master, arm = build_armature(bones, pivots, parents, collection, 5 / 16)
    mesh = build_weighted_mesh(MESH, arm, master, collection, clay())
    arm.animation_data_create()
    actions = {}
    for name in motion['clips']:
        actions[name] = make_clip_action(arm, motion, name, [b['name'] for b in bones], pivots, parents, geometry_bind_rotations(bones))
    arm['source_mesh_sha256'] = hashlib.sha256(MESH.read_bytes()).hexdigest()
    arm['diagnostic_scope'] = 'Actual rigid pelvis/thigh/knee shells; runtime automatic seam skins outside this scope'
    bpy.context.scene.render.fps = 60
    return arm, mesh, actions, bones, pivots, parents


def set_action(arm, action, frame):
    arm.animation_data.action = action
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()


def deformation(arm):
    return {b.name: b.matrix @ b.bone.matrix_local.inverted() for b in arm.pose.bones}


def export_game_motion(arm, actions, motion, bones, pivots, parents):
    exported = {'schema': 2, 'sample_rate': 60, 'bones': [b['name'] for b in bones], 'clips': {}}
    witnesses = {}
    for name, clip in motion['clips'].items():
        rows, expected = [], []
        for f in range(len(clip['frames'])):
            set_action(arm, actions[name], f + 1)
            world = deformation(arm)
            rotations, positions = [], {}
            expected.append({n: [list(row) for row in world[n]] for n in FOCUS})
            for n in exported['bones']:
                local = world[parents[n]].inverted() @ world[n] if n in parents else world[n]
                r = BASIS.inverted() @ local.to_3x3() @ BASIS
                q = r.to_quaternion().normalized()
                rotations.append([q.w, -q.x, -q.y, q.z])
                p = target_to_blender(pivots[n])
                t = local.translation - p + local.to_3x3() @ p
                runtime = BASIS.inverted() @ t
                positions[n] = [-runtime.x, runtime.y, runtime.z]
            root = [v / 112 for v in positions.pop('root')]
            rows.append({'rotation_wxyz': rotations, 'bone_position_xyz': positions,
                         'root_m': root, 'foot_contact': clip['frames'][f].get('foot_contact', [False, False])})
        exported['clips'][name] = dict(duration_seconds=clip['duration_seconds'], loop=False, frames=rows)
        witnesses[name] = expected
    return exported, witnesses


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = json.loads(PROFILE.read_text())
    motion = {'bones': original['bones'], 'clips': {n: copy.deepcopy(original['clips'][n])
              for n in ['r32_guard', 'r32_jab', 'r32_cross', 'r32_heavy']}}
    identity = {'rotation_wxyz': [[1, 0, 0, 0] for _ in motion['bones']],
                'bone_position_xyz': {}, 'root_m': [0, 0, 0], 'foot_contact': [True, True]}
    for side in ('l', 'r'):
        for axis, degrees in [('x', 30), ('x', 60), ('x', 90), ('z', 45)]:
            frame = copy.deepcopy(identity)
            angle = math.radians(degrees) * (-1 if axis == 'x' else 1 if side == 'l' else -1)
            q = Quaternion((1, 0, 0) if axis == 'x' else (0, 0, 1), angle)
            frame['rotation_wxyz'][motion['bones'].index('leg_' + side)] = [q.w, q.x, q.y, q.z]
            motion['clips'][f'hip_{side}_{axis}{degrees}'] = dict(duration_seconds=.1, loop=False, frames=[frame, frame])
    motion['clips']['neutral'] = dict(duration_seconds=.1, loop=False, frames=[identity, identity])
    (OUT / 'source_motion.json').write_text(json.dumps(motion, separators=(',', ':')))
    arm, mesh, actions, bones, pivots, parents = scene_from(motion)
    exported, witnesses = export_game_motion(arm, actions, motion, bones, pivots, parents)
    (OUT / 'exported_motion.json').write_text(json.dumps(exported, separators=(',', ':')))
    (OUT / 'source_witness.json').write_text(json.dumps(witnesses, separators=(',', ':')))
    set_action(arm, actions['r32_jab'], 46)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'unit01_source.blend'))
    # Destroy the authoring scene and read the serialized game data, never reuse
    # its matrices as the candidate. The expected matrices remain independent.
    serialized = json.loads((OUT / 'exported_motion.json').read_text())
    arm, mesh, actions, bones, pivots, parents = scene_from(serialized)
    maximum = 0.0
    samples = 0
    worst = None
    for name, expected in witnesses.items():
        for f, frame in enumerate(expected):
            set_action(arm, actions[name], f + 1)
            actual = deformation(arm)
            for n in FOCUS:
                old = Matrix(frame[n])
                pivot = target_to_blender(pivots[n])
                for v in (pivot, pivot + Vector((1, 0, 0)), pivot + Vector((0, 1, 0)), pivot + Vector((0, 0, 1))):
                    error = ((old @ v) - (actual[n] @ v)).length * 5 / 16
                    if error > maximum:
                        maximum, worst = error, [name, f, n]
                    samples += 1
    set_action(arm, actions['r32_jab'], 46)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'unit01_reimport.blend'))
    result = dict(samples=samples, maximum_position_error_blocks=maximum, worst=worst,
                  passed=maximum < .01, source_profile=str(PROFILE),
                  source_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [PROFILE, GEO, MESH]},
                  visual_status='NOT_REVIEWED', scope='pelvis and rigid leg shells; not a full runtime skinning equivalence claim')
    (OUT / 'roundtrip.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    if not result['passed']:
        raise RuntimeError('Body export/reimport exceeded .01 block positional tolerance')


if __name__ == '__main__':
    main()
