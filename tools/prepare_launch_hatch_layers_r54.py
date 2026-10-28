"""Prepare three additional real hatches per bank 1/3 lane; never write a world."""
import argparse
import copy
import gzip
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.Codex' / 'map-deps'))
from query_blocks import read_box, iter_block_entities


def prepare(world, output, installed_patch=None):
    owner = json.loads((world / 'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    gates = {g['resource']: g for g in owner['gates']}
    layers, patch, scopes = [], {}, []
    original = {}
    if installed_patch:
        previous = json.loads(installed_patch.read_text('utf8'))
        previous_manifest = json.loads((installed_patch.parent / 'installation_manifest.json').read_text('utf8'))
        actual = {}
        for scope in previous_manifest['scopes']:
            box = scope['measured_box']
            actual.update(read_box(world, 'projectseele:geofront', tuple(box[:3]), tuple(box[3:])))
        for cell in previous:
            pos = tuple(cell['pos'])
            if actual[pos] != cell['after']:
                raise ValueError(f'Installed cell changed at {pos}: {actual[pos]}')
            original[pos] = cell['before']
            patch[pos] = dict(cell, before=actual[pos], after=cell['before'])
    allowed = {'minecraft:air', 'minecraft:cave_air', 'minecraft:stone',
               'minecraft:deepslate[axis=y]', 'projectseele:nerv_shaft_panel',
               'projectseele:nerv_machine_edge'}
    # Bounds of the unchanged source frame, cassettes, moving leaf envelope,
    # and four grounded cassette beams, in hatch metres.
    pockets = [(-17.4, -1.3, -17.15, 17.25, 1, 17.15),
               (-20.7, -.35, -17.395, -16.05, 5.695, 17.3),
               (16.05, -.35, -17.395, 20.7, 5.695, 17.3),
               (-20.4, 0, -16.5, 20.4, 5.38, 16.5)]
    for side in (-1, 1):
        for end in (-1, 1):
            pockets.append((15.8 if side > 0 else -20.7, -2.02,
                            15.8 if end > 0 else -16.4,
                            20.7 if side > 0 else -15.8, -.35,
                            16.4 if end > 0 else -15.8))
    for bank in (1, 3):
        for lane in range(3):
            # Fit complete cassette pockets between the existing rail seats.
            heights = ((-825.98, -706.98, -587.98) if bank == 1 else
                       (119.02, 135.02, 151.02) if lane == 0 else
                       (124.02, 140.02, 156.02))
            parent = f'bank_{bank}_{"upper" if bank == 1 else "surface"}_lane_{lane}'
            source = gates[parent]
            ref = source['collision_steps']
            rows = json.loads(gzip.decompress((world / ref['cells_file']).read_bytes())) if isinstance(ref, dict) else ref
            x, source_y, z = source['frame']['position']
            for index, y in enumerate(heights, 1):
                dy = round(y - source_y)
                name = f'bank_{bank}_layer_{index}_lane_{lane}'
                lo = (math.floor(x - 22), math.floor(y - 4), math.floor(z - 18))
                hi = (math.ceil(x + 22), math.ceil(y + 6), math.ceil(z + 18))
                before = read_box(world, 'projectseele:geofront', lo, hi)
                if list(iter_block_entities(world, 'projectseele:geofront', lo, hi)):
                    raise ValueError(f'Authored hatch pocket contains a block entity: {name}')
                desired = {}
                for a, b, c, d, e, f in pockets:
                    for px in range(math.floor(x + a), math.ceil(x + d)):
                        for py in range(math.floor(y + b), math.ceil(y + e)):
                            for pz in range(math.floor(z + c), math.ceil(z + f)):
                                desired[(px, py, pz)] = 'minecraft:air'
                collision = copy.deepcopy(rows)
                for row in collision:
                    for cell in row:
                        cell['position'][1] += dy
                        desired[tuple(cell['position'])] = cell['closed']
                supports = copy.deepcopy(source['supports'])
                for support in supports:
                    support['position'][1] += dy
                    support['source_contact']['y'] += dy
                    desired[tuple(support['position'])] = support['state']
                for pos, state in desired.items():
                    old = before[pos]
                    if original.get(pos, old) not in allowed:
                        raise ValueError(f'Unexpected existing machinery at {pos}: {old}')
                    if old == state:
                        patch.pop(pos, None)
                        continue
                    change = dict(pos=list(pos), before=old, after=state,
                                  before_nbt=None, after_nbt=None, purpose=name)
                    if pos in patch and pos not in original and (patch[pos]['before'], patch[pos]['after']) != (old, state):
                        raise ValueError(f'Overlapping hatch pockets: {pos}')
                    patch[pos] = change
                layers.append(dict(resource=name, linked_to=parent,
                                   frame=dict(position=[x, y, z], quaternion=[0, 0, 0, 1]),
                                   collision_steps=collision, supports=supports))
                scopes.append(dict(gate=name, parent=parent, frame=[x, y, z],
                                   measured_box=[*lo, *hi]))
    output.mkdir(parents=True, exist_ok=True)
    forward = list(patch.values())
    inverse = [dict(row, before=row['after'], after=row['before']) for row in forward]
    documents = {'launch_hatch_layers_r54.json': layers,
                 'forwardPatch.json': forward,
                 'inversePatch.json': inverse,
                 'positiveEditMask.json': [row['pos'] for row in forward],
                 'installation_manifest.json': dict(world=str(world), dimension='projectseele:geofront',
                     added_gates=len(layers), static_cells=len(forward), scopes=scopes,
                     copy_to_world=['launch_hatch_layers_r54.json'],
                     existing_metadata_changed=[], runtime_data_changed=[])}
    for name, data in documents.items():
        (output / name).write_text(json.dumps(data, separators=(',', ':')) + '\n', 'utf8')
    print(f'Prepared {len(layers)} hatch layers and {len(forward)} reversible cells in {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--installed-patch', type=Path)
    args = parser.parse_args()
    prepare(args.world, args.output, args.installed_patch)
