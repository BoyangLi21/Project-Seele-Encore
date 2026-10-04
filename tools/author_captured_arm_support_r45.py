"""Fit actual palm and seam-skinned arm surfaces to low-pose support.

Preserves captured trunk, legs, timing and wrist orientation. Changes only
small whole-arm reach/swivel corrections, measured against actual geometry.
Output is private and cannot be promoted without dense/native visual review.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from eva_native_arm_surface_r45 import arm_surfaces, deform


class Pose:
    def __init__(self, doc, frame):
        self.rig = {b['name']: b for b in doc['rig_contract_r44']}
        self.pivots = {n: np.array(b['pivot']) * [-1, 1, 1] / 16 for n, b in self.rig.items()}
        self.rot = {n: R.from_quat([-x, -y, z, w]) for n, (w, x, y, z) in zip(doc['bones'], frame['rotation_wxyz'])}
        self.pos = {n: np.array(frame['bone_position_xyz'].get(n, [0, 0, 0])) * [-1, 1, 1] / 16 for n in self.rig}
        self.pos['root'] = np.array(frame['root_m']) * [-1, 1, 1] * 7
        self.cache = {}

    def matrix(self, name):
        if name not in self.cache:
            q = self.rot[name].as_matrix(); pivot = self.pivots[name]
            m = np.eye(4); m[:3, :3] = q; m[:3, 3] = self.pos[name] + pivot - q @ pivot
            parent = self.rig[name].get('parent')
            self.cache[name] = self.matrix(parent) @ m if parent else m
        return self.cache[name]

    def point(self, name):
        m = self.matrix(name)
        return m[:3, :3] @ self.pivots[name] + m[:3, 3]

    def set_world_rotation(self, name, rotation):
        parent = self.rig[name].get('parent')
        parent_rotation = R.from_matrix(self.matrix(parent)[:3, :3]) if parent else R.identity()
        self.rot[name] = parent_rotation.inv() * rotation
        self.cache.clear()


def swing(first, last):
    a = first / np.linalg.norm(first); b = last / np.linalg.norm(last)
    cross = np.cross(a, b); length = np.linalg.norm(cross)
    if length < 1e-10:
        assert a @ b > 0, 'Antipodal reach must not silently choose a bend plane'
        return R.identity()
    return R.from_rotvec(cross / length * np.arctan2(length, a @ b))


def reconcile_arm_goals(pose,side,joint,target,orientation,pole):
    """Restore world-space wrist/pole intent after local quaternion blending."""
    upper,lower,hand=['arm_'+side,'forearm_'+side,'hand_'+side]
    origin=pose.point(upper);m=pose.matrix(upper)
    middle=m[:3,:3]@joint+m[:3,3];end=pose.point(hand)
    upper_rotation=R.from_matrix(m[:3,:3]);lower_rotation=R.from_matrix(pose.matrix(lower)[:3,:3])
    a,b=np.linalg.norm(middle-origin),np.linalg.norm(end-middle)
    direction=target-origin;distance=np.linalg.norm(direction);direction/=distance
    distance=np.clip(distance,abs(a-b)+1e-6,a+b-1e-6);target=origin+distance*direction
    along=(a*a-b*b+distance*distance)/(2*distance)
    bend=pole-origin;bend-=direction*(bend@direction)
    if np.linalg.norm(bend)<1e-8:
        bend=middle-origin;bend-=direction*(bend@direction)
    bend/=np.linalg.norm(bend)
    wanted=origin+direction*along+bend*np.sqrt(max(0,a*a-along*along))
    pose.set_world_rotation(upper,swing(middle-origin,wanted-origin)*upper_rotation)
    pose.set_world_rotation(lower,swing(end-middle,target-wanted)*lower_rotation)
    offset=joint-pose.pivots[lower]
    pose.pos[lower]=offset-pose.rot[lower].apply(offset);pose.cache.clear()
    pose.set_world_rotation(hand,orientation)


def fit_side(pose, side, joint, surfaces, hand_hull, previous, swivel_limit, shoulder_support):
    upper, lower, hand = ['arm_' + side, 'forearm_' + side, 'hand_' + side]
    clavicle='clavicle_'+side
    chain=(clavicle,upper,lower,hand) if shoulder_support else (upper,lower,hand)
    original_rot = {n: pose.rot[n] for n in chain}
    original_pos = pose.pos[lower].copy()
    origin = pose.point(upper); m = pose.matrix(upper)
    middle = m[:3, :3] @ joint + m[:3, 3]; end = pose.point(hand)
    world_rot = {n: R.from_matrix(pose.matrix(n)[:3, :3]) for n in chain}
    shoulder_axis=np.cross(origin-pose.point(clavicle),[0.,1.,0.])
    shoulder_axis/=np.linalg.norm(shoulder_axis)
    a, b = np.linalg.norm(middle - origin), np.linalg.norm(end - middle)

    def apply(values):
        pose.rot.update(original_rot); pose.pos[lower] = original_pos.copy(); pose.cache.clear()
        if np.linalg.norm(values) < 1e-12:
            return
        if shoulder_support:
            pose.set_world_rotation(clavicle,R.from_rotvec(shoulder_axis*values[2])*world_rot[clavicle])
        current_origin=pose.point(upper);current_upper=pose.matrix(upper)
        current_middle=current_upper[:3,:3]@joint+current_upper[:3,3]
        current_end=pose.point(hand)
        current_rot={n:R.from_matrix(pose.matrix(n)[:3,:3]) for n in (upper,lower)}
        target = end + [0, values[0], 0]
        direction = target - current_origin; distance = np.linalg.norm(direction); direction /= distance
        distance = np.clip(distance, abs(a - b) + 1e-6, a + b - 1e-6)
        target = current_origin + direction * distance
        along = (a * a - b * b + distance * distance) / (2 * distance)
        pole = current_middle - current_origin; pole -= direction * (pole @ direction)
        if np.linalg.norm(pole) < 1e-8:
            pole = np.cross(world_rot[upper].apply([1, 0, 0]), direction)
        pole /= np.linalg.norm(pole)
        pole = R.from_rotvec(direction * values[1]).apply(pole)
        wanted_middle = current_origin + direction * along + pole * np.sqrt(max(0, a * a - along * along))
        pose.set_world_rotation(upper, swing(current_middle-current_origin,wanted_middle-current_origin)*current_rot[upper])
        pose.set_world_rotation(lower, swing(current_end-current_middle,target-wanted_middle)*current_rot[lower])
        offset = joint - pose.pivots[lower]
        pose.pos[lower] = offset - pose.rot[lower].apply(offset); pose.cache.clear()
        pose.set_world_rotation(hand, world_rot[hand])

    def heights(values):
        apply(values)
        matrices = {n: pose.matrix(n) for n in (upper, lower, hand)}
        hand_points = hand_hull @ matrices[hand][:3, :3].T + matrices[hand][:3, 3]
        return np.array([deform(surfaces[n], matrices)[:, 1].min() for n in (upper, lower)] + [hand_points[:, 1].min()])

    count=3 if shoulder_support else 2
    before = heights(np.zeros(count))
    clearance = .012  # Six centimetres at the real 5x render scale.
    if np.min(before) >= clearance:
        chosen = previous*.75 if shoulder_support else np.zeros(count)
        success=bool(np.min(heights(chosen))>=clearance-1e-5)
    else:
        success=False
    if not success:
        def cost(v):
            if shoulder_support:return .5*v[0]**2+2*v[1]**2+.6*v[2]**2+.30*np.sum((v-previous)**2)
            return v[0] ** 2 + .40 * v[1] ** 2 + .02 * np.sum((v - previous) ** 2)
        start=previous.copy() if shoulder_support else np.zeros(count)
        start[0]=min(.60,max(start[0],max(0,clearance-before.min())*2))
        bounds=[(0,.60),(-swivel_limit,swivel_limit)]+([(0,np.radians(10))]if shoulder_support else [])
        result = minimize(cost, start, method='SLSQP', bounds=bounds,
                          constraints=[dict(type='ineq', fun=lambda v: heights(v) - clearance)],
                          options=dict(maxiter=45, ftol=1e-10))
        chosen = result.x
        success = bool(np.min(heights(chosen)) >= clearance - 1e-5)
    after = heights(chosen)
    orientation_error = (world_rot[hand].inv() * R.from_matrix(pose.matrix(hand)[:3, :3])).magnitude()
    return chosen, dict(before_world_minima_m=(before * 5).tolist(), after_world_minima_m=(after * 5).tolist(),
                        wrist_lift_world_m=float(chosen[0] * 5), swivel_degrees=float(np.degrees(chosen[1])),
                        clavicle_elevation_degrees=float(np.degrees(chosen[2]))if shoulder_support else 0,
                        preserved_wrist_orientation_error_radians=float(orientation_error), constraints_passed=success)


def main():
    p = argparse.ArgumentParser()
    for name in ('profile', 'mesh', 'physical', 'support', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--swivel-limit-degrees',type=float,default=17.188733853924695)
    p.add_argument('--shoulder-support',action='store_true')
    args = p.parse_args(); assert 0<args.swivel_limit_degrees<=45
    assert not args.out.exists(); args.out.mkdir(parents=True)
    doc = json.loads(args.profile.read_text('utf8')); assert doc['rig_key'] == 1
    support = json.loads((args.support / 'support_surface.json').read_text('utf8'))
    replay = json.loads((args.support / 'native_arm_replay.json').read_text('utf8'))
    assert support['actual_support_pose_reproduced'] and replay['verified']
    assert hashlib.sha256(args.mesh.read_bytes()).hexdigest() == replay['source_mesh_sha256']
    mesh = json.loads(args.mesh.read_text('utf8'))
    physical = json.loads(args.physical.read_text('utf8'))['models']['1']['bodies']
    joints = {side: np.array(next(r for r in physical if r['name'] == 'forearm_' + side)['joint']).reshape(4, 4)[:3, 3] / .2 for side in ('l', 'r')}
    surfaces = {side: arm_surfaces(mesh, side) for side in ('l', 'r')}
    hulls = {side: np.array(support['hull_vertices'][side]) for side in ('l', 'r')}
    records = []; modified = ('to_prone', 'prone_hold', 'crawl', 'from_prone')
    for clip_name in modified:
        previous = {s: np.zeros(3 if args.shoulder_support else 2) for s in ('l', 'r')}
        for index, frame in enumerate(doc['clips'][clip_name]['frames']):
            pose = Pose(doc, frame)
            for side in ('l', 'r'):
                previous[side], record = fit_side(pose, side, joints[side], surfaces[side], hulls[side], previous[side],np.radians(args.swivel_limit_degrees),args.shoulder_support)
                records.append(dict(clip=clip_name, frame=index, side=side, **record))
            changed=('arm_l','arm_r','forearm_l','forearm_r','hand_l','hand_r')+(('clavicle_l','clavicle_r')if args.shoulder_support else ())
            for name in changed:
                x, y, z, w = pose.rot[name].as_quat()
                frame['rotation_wxyz'][doc['bones'].index(name)] = [float(w), float(-x), float(-y), float(z)]
                frame['bone_position_xyz'][name] = (pose.pos[name] * [-1, 1, 1] * 16).tolist()
            if index % 60 == 0:
                print(clip_name, index, 'failures', sum(not r['constraints_passed'] for r in records), flush=True)
        (args.out / 'authoring_partial.json').write_text(json.dumps(records), encoding='utf8')
    failures = [r for r in records if not r['constraints_passed']]
    doc['actual_hand_support_r45'] = dict(source_profile_sha256=hashlib.sha256(args.profile.read_bytes()).hexdigest(),
                                         changed_clips=list(modified), source='Current DQ palm and native-matched elbow/wrist seam surfaces',
                                         unchanged='Root, torso, legs, original timing and captured wrist orientation',
                                         native_accepted=False, dense_interpolation_checked=False, art_accepted=False)
    (args.out / args.profile.name).write_text(json.dumps(doc, separators=(',', ':')), encoding='utf8')
    (args.out / 'receipt.json').write_text(json.dumps(dict(samples=len(records), failures=len(failures),
        source_files={str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in (args.profile, args.mesh, args.physical)},
        records=records, native_passed=False, artistic_accepted=False, install_allowed=False), indent=2), encoding='utf8')
    if failures:
        (args.out / 'INVALID_PIPELINE.json').write_text(json.dumps(dict(reason='Unresolved real surface support constraints', count=len(failures))), encoding='utf8')
    print('FINISHED', len(records), 'unresolved', len(failures), flush=True)


if __name__ == '__main__':
    main()
