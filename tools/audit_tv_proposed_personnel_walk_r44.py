"""Composite planned native floor/door shapes with actual world and cage.

Read-only virtual clearance, not a fabricated native walking receipt. Highest
support uses the complete .6m footprint and neighbouring extended shapes.
"""
from pathlib import Path
import argparse, json, math, hashlib
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from audit_tv_cage_space_r44 import motion

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44/hangar_machinery'


def intersects(boxes, body):
    return np.all((boxes[:, 1] > body[0] + 1e-6) & (boxes[:, 0] < body[1] - 1e-6), axis=1)


def main(layout, cage, out, boundaries=None, inspection=False):
    layout, cage, out = Path(layout), Path(cage), Path(out)
    if out.exists(): raise ValueError('Fresh virtual audit epoch required')
    d = json.loads(layout.read_text()); c = json.loads(cage.read_text())
    native_path = BASE / 'tv_personnel_deck_native_v1/native_union_readback/full_native_collision_shapes.json'
    native = json.loads(native_path.read_text()); changed = {tuple(q['position']): q['after'] for q in d['floor_cells']}
    if boundaries is not None:
        guard_native=BASE/'tv_personnel_guard_native_v1/native_union_readback/native64.json'
        native.update(json.loads(guard_native.read_text()))
        for row in json.loads(Path(boundaries).read_text()):changed[tuple(row['position'])]=row['after']
    for gate in d['entry_gate_pairs']:
        for i, p in enumerate(gate['lower_positions']):
            for half in ('lower', 'upper'):
                q = (p[0], p[1] + (half == 'upper'), p[2])
                hinge = 'right' if i == 0 else 'left'
                changed[q] = f'projectseele:city_personnel_door[facing={gate["facing"]},half={half},hinge={hinge},open=true,powered=false]'
    w = MeasuredWorld(ROOT / 'run/saves/SEELE_FIELD_R44_REVIEW')
    for q in changed: w.around(q, 3)
    w.load(); world_boxes, world_owners = [], []
    xs = range(-33, 95); ys = range(-397, -386); zs = range(-270, -240)
    for x in xs:
        for y in ys:
            for z in zs:
                q = (x, y, z)
                if (x // 16, z // 16) not in w.selected or y // 16 not in w.selected[x // 16, z // 16]: continue
                state = changed.get(q, w.block(q))
                if state is None: raise ValueError(('Unknown measured owner', q))
                if state.partition('[')[0] in AIR | {'minecraft:light', 'projectseele:lcl', 'minecraft:water'}: continue
                if state not in native: raise ValueError(('Missing actual native shape', state))
                for box in native[state]:
                    world_boxes.append(np.array(box).reshape(2, 3) + q); world_owners.append({'position': q, 'state': state})
    world_boxes = np.array(world_boxes); reports = []
    routes=[]
    for route in d['complete_entry_and_return_cases']:
        if route['id'].endswith('/return'): continue
        for lateral in (-.5,0.,.5):
            points=[]
            is02=route['id'].startswith('tv_operator/2/1/')
            for i,p in enumerate(route['waypoints_for_native_refinement']):
                q=list(p)
                if is02:q[2 if i<7 else 0]+=lateral
                else:q[0]+=lateral
                points.append(q)
            routes.append(route | {'id':route['id']+'/lateral_'+str(lateral),'waypoints_for_native_refinement':points})
    if inspection:
        for variant in range(3):
            ox=-11.5+42*variant
            for side in (-1,1):
                special=variant==2 and side==1
                z=-253. if special else -255.
                xstaff=11.5 if special else 15.5
                xgreen=9.75 if special else 12.5
                start=[ox+side*xstaff,-392 if special else -392.6,z]
                points=[start,[ox+side*(10.5 if special else 14.35),-392.1 if special else -392.6,z],
                        [ox+side*xgreen,-392.1 if special else -392.6,z],[ox+side*xgreen,-391.4,-251.]]
                for lateral in (-.35,0.,.35) if special else (-.5,0.,.5):
                    path=[[p[0]+lateral,*p[1:]] for p in points]
                    routes.append({'id':f'tv_inspection/{variant}/{side}/entry/lateral_{lateral}',
                                   'waypoints_for_native_refinement':path,'use_actual_asset_floor_support':True})
    for route in routes:
        _, variant, side, *_ = route['id'].split('/'); variant, side = int(variant), int(side)
        origin = np.array([-11.5 + variant * 42, -442.96, -239.5])
        waypoints = route['waypoints_for_native_refinement']
        for opening in (0., 1.):
            asset_boxes, asset_owners = [], []
            for component in c['components']:
                if component.get('variant', variant) != variant or component['part'].startswith('thin_side_rails'): continue
                q = np.array(c['collision_parts'][component['part']]) + origin + motion(component, opening)
                asset_boxes.extend(q); asset_owners.extend([component['part']] * len(q))
            asset_boxes = np.array(asset_boxes); asset_owners = np.array(asset_owners)
            failures, samples = [], []
            for a, b in zip(waypoints, waypoints[1:]):
                a, b = np.array(a), np.array(b); steps = max(2, math.ceil(np.linalg.norm((b - a)[[0, 2]]) / .10))
                for t in np.linspace(0, 1, steps + 1):
                    p = a * (1 - t) + b * t
                    floor_boxes=np.concatenate((world_boxes,asset_boxes)) if route.get('use_actual_asset_floor_support') else world_boxes
                    support = (floor_boxes[:, 1, 0] > p[0] - .3) & (floor_boxes[:, 0, 0] < p[0] + .3) & (floor_boxes[:, 1, 2] > p[2] - .3) & (floor_boxes[:, 0, 2] < p[2] + .3)
                    # Candidate standing slab is sought near the intended
                    # deck, never on top of an overhead doorway/guard.
                    support &= (floor_boxes[:, 1, 1] <= p[1] + .65) & (floor_boxes[:, 1, 1] >= p[1] - .65)
                    if not support.any(): failures.append({'point': p.tolist(), 'reason': 'NO_DECLARED_FOOTPRINT_SUPPORT'}); continue
                    feet = float(floor_boxes[support, 1, 1].max()); body = np.array([[p[0] - .3, feet, p[2] - .3], [p[0] + .3, feet + 1.8, p[2] + .3]])
                    asset_hit = np.flatnonzero(intersects(asset_boxes, body)); world_hit = np.flatnonzero(intersects(world_boxes, body))
                    samples.append({'position': [float(p[0]), feet, float(p[2])], 'full_body': body.tolist()})
                    if len(asset_hit) or len(world_hit):
                        failures.append({'position': samples[-1]['position'], 'asset_parts': sorted(set(map(str, asset_owners[asset_hit]))),
                                         'world_cells': [world_owners[int(i)] for i in world_hit[:5]]})
            reports.append({'route': route['id'], 'opening': opening, 'samples': len(samples), 'failures': failures,
                            'actual_supported_positions': samples})
    out.mkdir(parents=True)
    report = {'layout_sha256': hashlib.sha256(layout.read_bytes()).hexdigest(), 'cage_sha256': hashlib.sha256(cage.read_bytes()).hexdigest(),
              'native_shapes_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(), 'routes': reports,
              'scope': 'Virtual opened paired city doors, optional exact installed native guard64 and registered native grating over current world + complete candidate cage collider; .6m width and1.8m head, three lateral paths. Body triangles, whole floor outside sampled paths, runtime door/admission and actual native walking remain separate.',
              'native_passed': False, 'apply_allowed': False, 'world_write_performed': False}
    (out / 'contract.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps([{'route': q['route'], 'opening': q['opening'], 'failed_samples': len(q['failures']), 'first': q['failures'][:1]} for q in reports]))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--layout', required=True, type=Path); p.add_argument('--cage', required=True, type=Path); p.add_argument('--out', required=True, type=Path)
    p.add_argument('--boundaries',type=Path)
    p.add_argument('--inspection',action='store_true')
    args = p.parse_args(); main(args.layout, args.cage, args.out,args.boundaries,args.inspection)
