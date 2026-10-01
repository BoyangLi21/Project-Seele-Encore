"""Private SAT audit of the actual six carrier ram render transforms.

Uses the exact source mount/stroke/rise order. No resource or world writes.
The cage and carrier sources are explicitly hashed; bounds only reject work,
and positive findings require real triangle/box SAT intersection.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from author_tv_shoulder_installation_r44 import prism_hits_triangle
from build_tv_shoulder_shells_r44 import box_vertices

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44/hangar_machinery'


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resource', type=Path, default=BASE / 'tv_cage_whole_candidate_v4/tv_shoulder_shells_r44.json')
    parser.add_argument('--out', type=Path, default=BASE / 'mounted_carrier_rams_v4_review')
    parser.add_argument('--operations',type=Path)
    args = parser.parse_args()
    carrier_path = ROOT / 'src/main/resources/assets/projectseele/mesh/tv_facilities_r16.json'
    render_path = ROOT / 'src/main/java/com/projectseele/client/render/TvFacilityMeshes.java'
    cage = json.loads(args.resource.read_text('utf8'))
    carrier = json.loads(carrier_path.read_text('utf8'))
    ram = np.array(carrier['parts']['carrier_ram_unit']).reshape(-1, 3, carrier['stride'])[:, :, :3]
    assert np.all((ram[:, :, 2] >= 0) & (ram[:, :, 2] <= 1))
    rows, continuous = [], []
    for variant in range(3):
        parts, boxes = [], []
        for component in cage['components']:
            if component['motion'] != 'fixed' or component.get('variant', variant) != variant:
                continue
            for box in cage['collision_parts'].get(component['part'], []):
                parts.append(component['part']); boxes.append(box)
        boxes = np.array(boxes)
        if args.operations:
            native=json.loads((BASE/'tv_personnel_deck_native_v1/native_union_readback/full_native_collision_shapes.json').read_text())
            native.update(json.loads((BASE/'tv_personnel_guard_native_v1/native_union_readback/native64.json').read_text()))
            origin=np.array([-11.5+42*variant,-442.96,-239.5]);extra=[]
            for op in json.loads(args.operations.read_text('utf8')):
                if not origin[0]-21<=op['position'][0]<=origin[0]+21:continue
                states={op['after']}
                if 'personnel_entry_gate' in op['role']:states.add(op['after'].replace('open=false','open=true'))
                for state in states:
                    for b in native[state]:extra.append(np.array(b).reshape(2,3)+op['position']-origin);parts.append('native_owner/'+str(op['position'])+'/'+state)
            boxes=np.concatenate((boxes,np.array(extra)))
        mounts = np.array(carrier['carrier_actuator_mounts'][str(variant)], dtype=np.float32)
        for phase, first, last in [('rise0_to_.8', (0., 0.), (.8, 0.)),
                                    ('rise.8_to1', (.8, 0.), (1., 0.)),
                                    ('release0_to1', (1., 0.), (1., 1.))]:
            for mount_index, mount in enumerate(mounts):
                ends = []
                for rise, release in (first, last):
                    stroke = min(6 * (1 - smooth((rise - .80) / .20)) + 4 * release,
                                 min(float(m[3] - m[2] - .28) for m in mounts))
                    x, y, start, end = map(float, mount)
                    triangles = ram.copy()
                    triangles[:, :, 2] *= end - start - stroke
                    triangles += [x, y - 64 * (1 - rise) + .96, start + stroke]
                    ends.append(triangles)
                both = np.concatenate(ends)
                lo, hi = both.min((0, 1)), both.max((0, 1))
                candidates = np.flatnonzero(np.all((boxes[:, 1] > lo) & (boxes[:, 0] < hi), axis=1))
                continuous.append({'variant': variant, 'phase': phase, 'mount_index': mount_index,
                                   'continuous_swept_bounds': [lo.tolist(), hi.tolist()],
                                   'fixed_part_bounds_hits': [parts[int(i)] for i in candidates]})
        phases = [('DRAINING_FILLING_RISE', float(r), 0.) for r in np.linspace(0, 1, 121)]
        phases += [('LAUNCH_CLEAR', 1., float(release)) for release in np.linspace(0, 1, 121)]
        for name, rise, release in phases:
            stroke = min(6 * (1 - smooth((rise - .80) / .20)) + 4 * release,
                         min(float(m[3] - m[2] - .28) for m in mounts))
            for mount_index, mount in enumerate(mounts):
                x, y, start, end = map(float, mount)
                triangles = ram.copy()
                triangles[:, :, 2] *= end - start - stroke
                triangles += [x, y - 64 * (1 - rise) + .96, start + stroke]
                lo, hi = triangles.min((0, 1)), triangles.max((0, 1))
                candidates = np.flatnonzero(np.all((boxes[:, 1] >= lo) & (boxes[:, 0] <= hi), axis=1))
                tlo, thi = triangles.min(1), triangles.max(1)
                for box_index in candidates:
                    box = boxes[box_index]
                    indices = np.flatnonzero(np.all((thi >= box[0]) & (tlo <= box[1]), axis=1))
                    vertices = box_vertices(box)
                    hits = [int(i) for i in indices if prism_hits_triangle(vertices, triangles[i], .003)]
                    if hits:
                        rows.append({'variant': variant, 'phase': name, 'rise': rise, 'release': release,
                                     'mount_index': mount_index, 'mount': mount.tolist(), 'pad_stroke': float(stroke),
                                     'fixed_part': parts[box_index], 'fixed_box_local': box.tolist(),
                                     'triangle_hits': len(hits), 'actual_first_triangle_local': triangles[hits[0]].tolist()})
    report = {'cage_sha256': hashlib.sha256(args.resource.read_bytes()).hexdigest(),
              'native_operations_sha256': hashlib.sha256(args.operations.read_bytes()).hexdigest() if args.operations else None,
              'carrier_sha256': hashlib.sha256(carrier_path.read_bytes()).hexdigest(),
              'render_source_sha256': hashlib.sha256(render_path.read_bytes()).hexdigest(),
              'six_mounts_per_variant': True, 'state_count_per_mount': 242, 'findings': rows,
              'continuous_endpoint_sweeps': continuous,
              'continuous_bound_positive_count': sum(bool(q['fixed_part_bounds_hits']) for q in continuous),
              'continuous_proof': 'Each vertex y increases with rise. z=start+stroke+(end-start-stroke)*unitVertexZ; unitVertexZ lies in [0,1] and stroke is monotonic within each interval, so every coordinate stays inside the endpoint union. All54 interval bounds are tested against fixed component boxes. Bounds with zero intersections prove the entire continuous path; positive bounds alone would remain unknown until exact refinement.',
              'transform': 'pose.translate(0,-64*(1-rise),0); stroke=min(all6mount end-start-.28,6*(1-ramp(rise,.80,1))+4*release); pose.translate(x,y,start+stroke); pose.scale(1,1,end-start-stroke). Carrier actor feet are .96m above fixed gantry origin. Render is before super.render/applyRotations, so no body yaw applied.',
              'world_write_performed': False, 'resource_write_performed': False, 'native_passed': False,
              'scope': 'Exact actual-render mount transforms vs current fixed cage primitives. Rise is used in actual wet-bay DRAINING/FILLING. Does not substitute for submitted native ram witness, moving cage states or all travel positions.'}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'contract.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps({'findings': len(rows), 'first': rows[:2], 'report': str(args.out / 'contract.json')}))


if __name__ == '__main__':
    main()
