"""Pending-only exact-triangle source sweep, with bounded continuous curves.

The test uses SAT against each triangle's convex translation prism. Curved
centre lines and direction-changing source heads add certified finite errors.
An overlap is a conservative conflict, never a native or visual acceptance.
"""
import argparse
from collections import defaultdict, OrderedDict
import json
import math
from pathlib import Path
import numpy as np
from build_current_launch_height_hulls import read_mesh, split
from upright_native_anchor_selection_r53 import read, require, sha


def split_at(p, t):
    levels = [p]
    while len(levels[-1]) > 1:
        levels.append(levels[-1][:-1]*(1-t)+levels[-1][1:]*t)
    return np.array([r[0] for r in levels]), np.array([r[-1] for r in levels[::-1]])


def subcurve(p, a, b):
    if b < 1:
        p, _ = split_at(p, b)
    if a > 0:
        _, p = split_at(p, a/b)
    return p


def chords(p, tolerance=.002):
    d = p[-1]-p[0]
    t = np.clip((p-p[0])@d/max(float(d@d), 1e-30), 0, 1)
    error = float(np.linalg.norm(p-(p[0]+t[:, None]*d), axis=1).max())
    if error <= tolerance:
        yield p[0], p[-1], error+1e-6
    else:
        left, right = split(p)
        yield from chords(left, tolerance)
        yield from chords(right, tolerance)


def rod_box(a, b, width):
    z = b-a; length = np.linalg.norm(z); z /= length
    x = np.cross(z, [0, 1, 0])
    if np.linalg.norm(x) < .1:
        x = np.cross(z, [1, 0, 0])
    x /= np.linalg.norm(x); y = np.cross(z, x)
    return (a+b)/2, np.stack([x, y, z], axis=1), np.array([width/2, width/2, length/2])


def seat_boxes(row, request):
    origin = np.asarray(request['rail_bearing']); width = row.get('connector_width_m', .12)
    out = []
    for role, foot in (('main', row), ('diagonal', row.get('secondary_native_seat'))):
        if foot is None:
            continue
        path = [origin, *map(np.asarray, foot.get('connector_via_world', [])), np.asarray(foot['bearing'])]
        first = 0 if role == 'main' else 1
        for n in range(first, len(path)-1):
            out.append((f'{role}/{n}', *rod_box(path[n], path[n+1], width)))
        normal = np.asarray(foot['normal']); side = np.array([0., 1, 0]) if abs(normal[0]) > .5 else np.array([1., 0, 0])
        basis = np.stack([side, np.cross(normal, side), normal], axis=1)
        w = foot.get('native_seat_width_m', row.get('native_seat_width_m', .2))/2
        out.append((f'{role}/finite_native_seat', np.asarray(foot['bearing'])+normal*.025, basis, np.array([w, w, .025])))
    tri = np.asarray(request['actual_rail_weld_triangle']); normal = np.asarray(request['normal'])
    x = tri[1]-tri[0]; x /= np.linalg.norm(x)
    # Exact clipped weld is contained in this finite 16cm box.
    out.append(('actual_finite_weld_enclosure', origin-normal*.015,
                np.stack([x, np.cross(normal, x), normal], axis=1), np.array([.08, .08, .015])))
    return out


def prism_hits(triangles, start, end, box, error=0.):
    """Vector SAT: convex hull(triangle+start,triangle+end) versus an OBB."""
    _, centre, basis, half = box
    half = half+error
    t = (triangles+start-centre)@basis
    travel = (end-start)@basis
    # Clip the translation parameter separately for each actual triangle.
    # A 600m chord must not turn every nearby source facet into a 600m prism.
    lower, upper = t.min(axis=1), t.max(axis=1)
    begin, finish = np.zeros(len(t)), np.ones(len(t))
    valid = np.ones(len(t), bool)
    for axis in range(3):
        delta = travel[axis]
        if abs(delta) < 1e-14:
            valid &= (upper[:, axis] >= -half[axis]) & (lower[:, axis] <= half[axis])
        else:
            a = (-half[axis]-upper[:, axis])/delta
            b = (half[axis]-lower[:, axis])/delta
            begin = np.maximum(begin, np.minimum(a, b))
            finish = np.minimum(finish, np.maximum(a, b))
    ids = np.flatnonzero(valid & (begin <= finish))
    if not len(ids):
        return ids
    t = t[ids]+begin[ids, None, None]*travel
    travel = (finish[ids]-begin[ids])[:, None]*travel
    edges = np.roll(t, -1, axis=1)-t
    keep = np.ones(len(ids), bool)
    axes = [np.cross(edges[:, 0], edges[:, 1])]
    axes += [np.cross(edges[:, i], travel) for i in range(3)]
    axes += [np.cross(edges[:, i], unit) for i in range(3) for unit in np.eye(3)]
    axes += [np.cross(travel, unit) for unit in np.eye(3)]
    for axis in axes:
        values = np.einsum('nvc,nc->nv', t, axis)
        delta = np.einsum('nc,nc->n', axis, travel); radius = np.abs(axis)@half
        lower = values.min(1)+np.minimum(0, delta); upper = values.max(1)+np.maximum(0, delta)
        keep &= (upper >= -radius-1e-10) & (lower <= radius+1e-10)
        if not keep.any():
            break
    return ids[keep]


def clipped_translation(start, end, source_low, source_high, low, high, error):
    """Root interval capable of intersecting this finite box, using real bounds."""
    delta = end-start; begin, finish = 0., 1.
    for axis in range(3):
        lower = low[axis]-source_high[axis]-error
        upper = high[axis]-source_low[axis]+error
        if abs(delta[axis]) < 1e-14:
            if start[axis] < lower or start[axis] > upper:
                return None
        else:
            a, b = (lower-start[axis])/delta[axis], (upper-start[axis])/delta[axis]
            begin, finish = max(begin, min(a, b)), min(finish, max(a, b))
            if begin > finish:
                return None
    return start+begin*delta, start+finish*delta


class SourceSweep:
    """One immutable actual-source cache shared by candidate selection and QA."""
    def __init__(self, assembly, design_file, mounts_root_local=None):
        self.assembly, self.design_file = assembly, design_file
        self.export, design = read(assembly/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json'), read(design_file)
        require(self.export['root_design_sha256'] == sha(design_file), 'Current complete assembly/design mismatch')
        files = [assembly/f'ACTUAL_FIXED_ASSEMBLY.variant{v}.bin.gz' for v in range(3)]
        files += [assembly/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz', assembly/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json']
        self.source_sha256 = {str(p.resolve()): sha(p) for p in files}
        declared = {str(Path(p).resolve()): digest for p, digest in self.export['sources_sha256'].items()}
        require(all(declared.get(str(p.resolve())) == self.source_sha256[str(p.resolve())] for p in files[:-1]),
                'Actual binary source differs from its current complete export')
        model_file = Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json'
        transfer_file = model_file.with_name('outer_head_transfer_r53.json')
        if mounts_root_local is None:
            require(sha(transfer_file) == self.export['head_source_sha256'], 'Current transfer/export dependency differs')
            require(read(transfer_file)['outer_source_sha256'] == sha(model_file), 'Current capture mount source differs')
            mounts_root_local = read(model_file)['mounts_root_local']
        self.mounts_world = {side: np.asarray(mounts_root_local[index])*np.array([-1, 1, -1])
                             for index, side in enumerate((-1, 1))}
        self.legs = {r['id']: r for r in design['legs'] if 'centre_curve' in r}
        cone_doc = read(assembly/'CURRENT_HEAD_CONTINUOUS_TANGENT_CONES.json')
        require(cone_doc['root_design_sha256'] == sha(design_file), 'Current head direction certificate required')
        self.cones = defaultdict(list)
        for r in cone_doc['cones']:
            controls = np.asarray(self.legs[r['leg']]['centre_curve']['segments'][r['segment']]['controls'])
            part = subcurve(controls, *r['geometric_bezier_parameter'])
            self.cones[r['leg']].append((r, part, part.min(0), part.max(0)))
        templates = {r['name']: r for r in self.export['head_templates']}
        heads = read_mesh(assembly/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz')
        root_parts, moving = [], {-1: [], 1: []}
        for name, (_, mesh) in heads.items():
            frame = templates[name]['frame']
            if frame == 'ROOT':
                root_parts.append(mesh*np.array([-1, 1, -1]))
            else:
                moving[-1 if frame == 'RUNNER_NEG' else 1].append(mesh)
        root_mesh = np.concatenate(root_parts)
        self.moving = {side: np.concatenate(v) for side, v in moving.items()}
        self.head_radius = {side: float(np.linalg.norm(mesh-np.array([0, .35, 0]), axis=2).max())
                            for side, mesh in self.moving.items()}
        self.fixed, self.bounds, self.offset, self.names = {}, {}, {}, {}
        for v in range(3):
            parts = read_mesh(assembly/f'ACTUAL_FIXED_ASSEMBLY.variant{v}.bin.gz')
            o = self.export['variants'][v]['root_relative_to_actual_foot_midpoint']['translation']
            self.offset[v] = np.array([o['x'], o['y'], o['z']])
            mesh = np.concatenate([*[m for _, m in parts.values()], root_mesh+self.offset[v]])
            self.fixed[v] = mesh
            self.bounds[v] = (mesh.min(1), mesh.max(1), mesh.min((0, 1)), mesh.max((0, 1)))
            self.names[v] = np.concatenate([*[np.full(len(m), name, dtype=object) for name, (_, m) in parts.items()],
                                            np.full(len(root_mesh), 'actual_ROOT_head_templates', dtype=object)])
        self.curves = {key: list(ch for s in leg['centre_curve']['segments'] for ch in chords(np.asarray(s['controls'])))
                       for key, leg in self.legs.items()}
        self.posed_cache = OrderedDict()

    @staticmethod
    def box_bounds(box):
        _, centre, basis, half = box
        extent = np.abs(basis)@half
        return centre-extent, centre+extent

    def check_boxes(self, leg, boxes, heads=True):
        v = int(leg[4]); findings = []; pair_count = 0
        fmin, fmax, global_min, global_max = self.bounds[v]
        for box in boxes:
            low, high = self.box_bounds(box)
            for start, end, error in self.curves[leg]:
                clipped = clipped_translation(start, end, global_min, global_max, low, high, error)
                if clipped is None:
                    continue
                start, end = clipped
                ids = np.flatnonzero(np.all(fmax+np.maximum(start, end)+error >= low, axis=1)
                                     & np.all(fmin+np.minimum(start, end)-error <= high, axis=1))
                if not len(ids):
                    continue
                pair_count += len(ids)
                hit = prism_hits(self.fixed[v][ids], start, end, box, error)
                if len(hit):
                    hit_ids = ids[hit[:8]]
                    findings.append(dict(part='actual_fixed_complete_assembly', bracket_part=box[0],
                        source_triangle_ids=hit_ids.tolist(), source_parts=self.names[v][hit_ids].tolist(),
                        bounded_curve_error_m=error, continuous_chord=[start.tolist(), end.tolist()]))
                    return findings, pair_count
            if not heads:
                continue
            for cone, part, part_low, part_high in self.cones[leg]:
                for side, mesh in self.moving.items():
                    origin = self.mounts_world[side]+self.offset[v]
                    radius = self.head_radius[side]+cone['position_error_m']+1e-8
                    if np.any(part_high+origin+radius < low) or np.any(part_low+origin-radius > high):
                        continue
                    key = (leg, cone['segment'], tuple(cone['geometric_bezier_parameter']), side)
                    if key not in self.posed_cache:
                        d = np.asarray(cone['direction']); u = np.array([-1., 0, 0])
                        x = u-d*(u@d); x /= np.linalg.norm(x); y = np.cross(d, x)
                        posed = mesh[:, :, 0, None]*x+(mesh[:, :, 1, None]-.35)*y+mesh[:, :, 2, None]*d+origin
                        self.posed_cache[key] = (posed, posed.min(1), posed.max(1), posed.min((0, 1)), posed.max((0, 1)))
                        if len(self.posed_cache) > 24:
                            self.posed_cache.popitem(last=False)
                    self.posed_cache.move_to_end(key)
                    posed, mlo, mhi, pmin, pmax = self.posed_cache[key]
                    for start, end, curve_error in chords(part):
                        error = curve_error+cone['position_error_m']+1e-8
                        clipped = clipped_translation(start, end, pmin, pmax, low, high, error)
                        if clipped is None:
                            continue
                        start, end = clipped
                        ids = np.flatnonzero(np.all(mhi+np.maximum(start, end)+error >= low, axis=1)
                                             & np.all(mlo+np.minimum(start, end)-error <= high, axis=1))
                        if not len(ids):
                            continue
                        pair_count += len(ids)
                        hit = prism_hits(posed[ids], start, end, box, error)
                        if len(hit):
                            findings.append(dict(part=f'actual_directional_heads/{side}', bracket_part=box[0],
                                source_triangle_ids=ids[hit[:8]].tolist(), bound_m=error,
                                segment=cone['segment'], geometric_parameter=cone['geometric_bezier_parameter']))
                            return findings, pair_count
        return findings, pair_count

    def check(self, row, request):
        return self.check_boxes(request['leg'], seat_boxes(row, request))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('seats', 'preserved', 'sockets', 'assembly', 'design', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); require(not a.output.exists(), 'Fresh report required')
    table, prior, sockets, export, design = map(read, (a.seats, a.preserved, a.sockets,
        a.assembly/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json', a.design))
    require(export['root_design_sha256'] == sha(a.design), 'Current complete assembly/design mismatch')
    require(table['socket_requests_sha256'] == sha(a.sockets), 'Candidate/socket mismatch')
    preserved = {r['socket_id'] for r in prior['seats']}
    requests = {r['socket_id']: r for r in sockets['sockets']}
    added = [r for r in table['seats'] if r['socket_id'] not in preserved]
    sweep = SourceSweep(a.assembly, a.design)
    results = []
    for count, row in enumerate(added, 1):
        q = requests[row['socket_id']]
        findings, pair_count = sweep.check(row, q)
        results.append(dict(socket_id=row['socket_id'], continuous_triangle_pairs=pair_count, conflicts=findings,
                            continuous_complete_source_clear=not findings))
        if count % 10 == 0:
            print(f'local complete source {count}/{len(added)} conflicts={sum(bool(r["conflicts"]) for r in results)}', flush=True)
            a.output.parent.mkdir(parents=True, exist_ok=True)
            a.output.with_suffix('.PROGRESS.json').write_text(json.dumps(results), 'utf8')
    result = dict(world_written=False, game_started=False, native_admission=False,
                  source_clear=all(r['continuous_complete_source_clear'] for r in results),
                  checked_new_seats=len(added), preserved_seats_not_retested=len(preserved), results=results,
                  seats_sha256=sha(a.seats), socket_requests_sha256=sha(a.sockets), assembly_export_sha256=sha(a.assembly/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json'),
                  actual_binary_and_cone_sha256=sweep.source_sha256, source_generator_sha256=sha(Path(__file__)),
                  design_sha256=sha(a.design), method='All exact current fixed source triangles including LOCK_DEPTH11 seated closed plug and ROOT head parts; continuous triangle translation-prism SAT with Bezier chord convex-hull bound <=2mm. All real directional head templates use current certified tangent cones with explicit displacement error. Only added brackets and neighbouring route intervals are tested.')
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(result, indent=2)+'\n', 'utf8')
    print(json.dumps(dict(checked=len(added), conflicts=sum(bool(r['conflicts']) for r in results))), flush=True)


if __name__ == '__main__':
    main()
