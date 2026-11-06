"""Clip current rendered steel at each of the 27 actual upright hatch bands."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from prepare_upright_socket_and_port_corrections_r52 import records, clip


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('steel', 'gates', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--interface', type=Path)
    a = p.parse_args(); gates = json.loads(a.gates.read_text('utf8'))['gates']
    ported = [g for g in gates if g.get('silo_hatch', {}).get('upright_guide_ports')]
    assert len(ported) == 27
    # Exact production method NervSiloHatchGeometryR52.uprightGuideSteelPortsR52.
    slots = {(-1, 'head'): [-15.30500001192093, 14.168942955567978, -14.69499998807907, 14.409433785081731],
        (-1, 'web'): [-15.105000001490117, 13.818280923865956, -14.894999998509883, 14.289229369429654],
        (1, 'head'): [14.69499998807907, -15.39105704443201, 15.30500001192093, -15.150566214918328],
        (1, 'web'): [14.894999998509883, -15.74171907613406, 15.105000001490117, -15.270770630570178]}
    factory = {row['resource']: row for row in json.loads(a.interface.read_text('utf8'))['gates']} if a.interface else {}
    bounds, counts = {}, {}
    for part in records(a.steel, 'pieces'):
        if part['component'] not in ('head', 'web'): continue
        xyz = np.array(part['triangles_rgb']).reshape(-1, 6)[:, :3]+part['frame']['translation']
        low, high = xyz.min(0), xyz.max(0)
        for gate in ported:
            variant = int(part['leg'][4])
            if variant != gate['variant']: continue
            origin = np.array(gate['frame']['position'])
            if high[1] < origin[1] or low[1] > origin[1]+5.38 or high[0] < origin[0]-18 or low[0] > origin[0]+18 or high[2] < origin[2]-17 or low[2] > origin[2]+17: continue
            local = xyz-origin
            for tri in local.reshape(-1, 3, 3):
                poly = clip(list(tri), 1, 0, True)
                if poly: poly = clip(poly, 1, 5.38, False)
                if not poly: continue
                points = np.array(poly)[:, [0, 2]]
                key = gate['resource'], -1 if points[:, 0].mean() < 0 else 1, part['component']
                counts[key] = counts.get(key, 0)+1
                if key not in bounds: bounds[key] = [points.min(0), points.max(0)]
                else: bounds[key] = [np.minimum(bounds[key][0], points.min(0)), np.maximum(bounds[key][1], points.max(0))]
    rows = []
    for gate in ported:
        for side in (-1, 1):
            for component in ('head', 'web'):
                key = gate['resource'], side, component
                if key not in bounds:
                    rows.append(dict(resource=gate['resource'], side=side, component=component,
                        actual_rail_facets=0, classification='NO_ACTUAL_STEEL_IN_HATCH_WORKING_BAND',
                        footprint_contained_by_production_slot=True))
                    continue
                lower, upper = bounds[key]
                slot_index = (0 if side == -1 else 2)+(0 if component == 'head' else 1)
                slot = np.array(factory[gate['resource']]['production_upright_guide_slots_xz'][slot_index] if factory else slots[side, component])
                clear = bool(np.all(lower >= slot[:2]-1e-7) and np.all(upper <= slot[2:]+1e-7))
                rows.append(dict(resource=gate['resource'], side=side, component=component,
                    actual_clipped_min_xz=lower.tolist(), actual_clipped_max_xz=upper.tolist(), production_slot_xz=slot.tolist(),
                    actual_rail_facets=count if (count:=counts[key]) else 0, footprint_contained_by_production_slot=clear,
                    minimum_fit_m=float(np.min(np.r_[lower-slot[:2], slot[2:]-upper]))))
    result = dict(world_written=False, native_admission=False, steel_sha256=sha(a.steel), gates_sha256=sha(a.gates),
        production_interface_sha256=sha(a.interface) if a.interface else None,
        source_geometry_method='All real rail triangles clipped at actual hatch local working band 0..5.38m; rigid body frames unchanged',
        hatches=27, checks=len(rows), all_current_steel_fits_ports=all(r['footprint_contained_by_production_slot'] for r in rows), rows=rows)
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print(json.dumps({k: result[k] for k in ('hatches', 'checks', 'all_current_steel_fits_ports')}, indent=2))
    print('first failures', json.dumps([r for r in rows if not r['footprint_contained_by_production_slot']][:2]))


if __name__ == '__main__': main()
