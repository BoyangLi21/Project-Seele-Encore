"""Measured R53 facility model; reads blocks only through query_blocks.

The saved volumes are evidence, never excavation masks. Cutaways deliberately
hide terrain and roofs; the inventory retains every original block state.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from survey_facility_target import role_of
import export_spatial_twin as mesh

REGIONS = {
    'deep_hangar': ((-55, -1140, 9), (116, -940, 401)),
    'old_hangar': ((-48, -480, -302), (114, -310, 32)),
    'launch_core': ((-35, -1038, -56), (95, 90, 146)),
    'headquarters': ((-95, -570, 207), (155, -382, 447)),
}
COLOURS = {
    'shell': (100, 121, 126, 255), 'floor': (155, 164, 158, 255),
    'machine': (75, 96, 92, 255), 'shaft': (78, 106, 121, 255),
    'structure': (70, 80, 87, 255), 'glass': (107, 182, 192, 170),
    'rail': (215, 165, 72, 255), 'lift': (184, 98, 172, 255),
    'light': (249, 222, 157, 255), 'warning': (232, 156, 55, 255),
    'fixture': (176, 185, 175, 255), 'fluid': (214, 116, 63, 140),
    'other': (122, 127, 132, 255),
}


def material(state):
    role = role_of(state)
    if role in ('air', 'natural'): return None
    if 'elevator' in state: return 'lift'
    if 'one_way_glass' in state or role == 'glass': return 'glass'
    if role == 'fluid': return 'fluid'
    if 'rail' in state or 'girder' in state: return 'rail'
    if 'light' in state or 'lantern' in state: return 'light'
    if 'hazard' in state or 'warning' in state: return 'warning'
    for key in ('floor', 'machine', 'shaft', 'structur'):
        if key in state: return 'structure' if key == 'structur' else key
    if 'panel' in state: return 'shell'
    if role == 'fixture': return 'fixture'
    return 'other'


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf8')


def snapshot(world, out, name):
    lo, hi = REGIONS[name]
    path = out / (name + '.npz')
    if path.exists():
        with np.load(path) as saved:
            assert tuple(saved['origin']) == lo
            return saved['states'], saved['palette'].tolist(), lo, hi
    survey.WORLD = world
    cells, palette = survey.measure(lo, hi)
    np.savez_compressed(path, origin=lo, states=cells, palette=palette)
    devices = [dict(position=p, id=str(tag['id']), nbt=tag.snbt())
               for p, tag in iter_block_entities(world, survey.DIM, lo, hi)]
    save_json(out / (name + '_devices.json'), devices)
    print(name, 'measured', list(cells.shape), 'devices', len(devices), flush=True)
    return cells, palette, lo, hi


def export(cells, palette, lo, hi, out, name, max_y=None, min_y=None):
    categories = list(COLOURS)
    mapping = np.asarray([0 if material(s) is None else categories.index(material(s))+1
                          for s in palette], np.uint8)
    grid = mapping[cells].transpose(2, 0, 1).copy()
    if max_y is not None: grid[:, max(0, max_y+1-lo[1]):, :] = 0
    if min_y is not None: grid[:, :max(0, min_y-lo[1]), :] = 0
    mesh.CATEGORY_NAMES = {i+1: k for i, k in enumerate(categories)}
    mesh.CATEGORY_COLOURS = {i+1: COLOURS[k] for i, k in enumerate(categories)}
    bounds = mesh.Bounds(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
    geometry = mesh.surface_meshes(grid, bounds, 1)
    stats = mesh.write_glb(out / (name+'.glb'), geometry, dict(
        world_coordinates='Minecraft XYZ; Y up; north is -Z', source='R53 CANDIDATE',
        cut_below_y=min_y, cut_above_y=max_y, terrain_hidden=True,
        partial_blocks_shown_as_cells=True, dynamic_entities_not_in_voxel_mesh=True,
        not_native_visual_acceptance=True, no_build_permission=True))
    print(name, 'triangles', sum(r['triangles'] for r in stats.values()), flush=True)
    return dict(file=name+'.glb', bounds=[lo, hi], cut_above_y=max_y,
                cut_below_y=min_y, triangles=sum(r['triangles'] for r in stats.values()))


def semantic_inventory(world):
    owner = json.loads((world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    directory = json.loads((world/'ROOT_RUNTIME_DIRECTORY.json').read_text('utf8'))
    lifts = json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
    units = [dict(variant=u['variant'], bay=u['bay_frame'], dock=u['dock_frame'],
                  boarding=u['boarding'], dismount=u['dismount']) for u in owner['units']]
    lift_rows = [dict(id=l['id'], floors=[dict(label=f['label'], cabin=f['cabin'],
                      exit=f['exit'], restricted=f.get('restricted', False))
                      for f in l['floors']]) for l in lifts['lifts']]
    gates = [dict(id=g['resource'], kind=g['kind'], frame=g['frame'],
                  width=g.get('width'), height=g.get('height')) for g in owner['gates']]
    legs = [{k:l[k] for k in ('id','from','to','motion','ramp_profile','centre_curve') if k in l}
            for l in directory['legs'] if not l['id'].endswith('/reverse')]
    return dict(units=units, lifts=lift_rows, gates=gates, nodes=directory['nodes'], legs=legs,
                bank_roles=directory['bank_roles'], sources=[
                    'ROOT_MECHANICAL_OWNER.json', 'ROOT_RUNTIME_DIRECTORY.json',
                    'personnel_lifts_r52.json'],
                limitation='Runtime declarations retained separately from measured static blocks.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--region', choices=tuple(REGIONS), action='append')
    p.add_argument('--measure-only', action='store_true')
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    world = args.world.resolve()
    source = args.out/'SOURCE.json'
    identity = dict(world=str(world), regions=REGIONS, block_reader='query_blocks',
                    world_written=False, geometry_is_not_construction_permission=True)
    if source.exists(): assert json.loads(source.read_text('utf8'))['world'] == str(world)
    else: save_json(source, identity)
    save_json(args.out/'facility_model.json', semantic_inventory(world))
    for name in args.region or REGIONS:
        cells, palette, lo, hi = snapshot(world, args.out, name)
        if args.measure_only: continue
        products = [export(cells, palette, lo, hi, args.out, name)]
        if name == 'deep_hangar':
            products.append(export(cells, palette, lo, hi, args.out, name+'_boarding_cut', max_y=-1012, min_y=-1075))
            products.append(export(cells, palette, lo, hi, args.out, name+'_bank_cut', max_y=-1025, min_y=-1045))
        if name == 'old_hangar':
            products.append(export(cells, palette, lo, hi, args.out, name+'_ground_cut', max_y=-430))
        if name == 'headquarters':
            products.append(export(cells, palette, lo, hi, args.out, name+'_command_cut', max_y=-513, min_y=-520))
        save_json(args.out/(name+'_models.json'), products)


if __name__ == '__main__': main()
