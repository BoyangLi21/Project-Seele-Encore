"""Move the remote air shaft's surface door down to the plain, in a stopped world.

Changes the gate record of remote_airshaft_surface in ROOT_MECHANICAL_OWNER.json (frame height, the eight support
cells, panels that stow downward under the ground instead of upward), writes its collision table for the new door
layer and moves the door entity with it. The runtime only accepts a door whose entity stands exactly on the
declared frame with the declared hatch, so the three are changed together or not at all.

The door's closed cells are ground hatch covers (grass on top) instead of barriers, and the frame stands 1 cm
under the door layer's top, so that the closed door is the cover blocks alone and none of its steel shows.

Run it after the block rows of the same change have been written: the new support cells must already be structural
panels and the new door layer must already be closed with cover blocks. The files it replaces are copied to --out
first. The world then needs a jar that has the cover block (projectseele:nerv_ground_hatch).

    python tools/lower_air_shaft_door.py --world <save> --out <new backup folder> [--door-layer 26]
"""
import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

import nbtlib

from install_r53_carrier_trays import stopped_world
from write_deep_cells import decode, read_chunk, write_chunk

GATE = 'remote_airshaft_surface'
OWNER = 'ROOT_MECHANICAL_OWNER.json'
REGION = 'dimensions/projectseele/geofront/region'
ENTITIES = 'dimensions/projectseele/geofront/entities'
SUPPORT = 'projectseele:nerv_structural_panel'
COVER = 'projectseele:nerv_ground_hatch'
BEAM_BOTTOM = -1.99          # with the frame 1 cm under a block top, the beam seats land on one


def bearing_points(centre_x, centre_z, hatch, sign):
    """The eight beam seats of a declared hatch, as NervSiloHatchGeometryR52.bearingPoints gives them."""
    opening_x, opening_z = hatch['opening_x'], hatch['opening_z']
    panel = (opening_x + 1) / 8
    case_outer = opening_x / 2 + .9 + panel + .3
    reach = opening_z / 2 + (2.6 if sign < 0 else .6)
    return [(side, end, centre_x + side * x, centre_z + end * reach)
            for side in (-1, 1) for end in (-1, 1) for x in (opening_x / 2 + .6, case_outer - .3)]


def plan(gate, layer):
    """The gate record for a door whose closed layer is `layer`, and its collision cells."""
    x, old_y, z = gate['frame']['position']
    hatch = dict(gate['silo_hatch'], separation_sign=-1, beam_bottom=BEAM_BOTTOM)
    if hatch['opening_x'] < 64 or hatch.get('service_column_ports') or hatch.get('upright_guide_ports'):
        raise SystemExit('Only the large plain hatch of the air shaft is lowered by this tool')
    frame_y = round(layer - .01, 2)
    seat = frame_y + hatch['beam_bottom']
    if abs(seat - round(seat)) > 1e-9:
        raise SystemExit('The beam seats must land on a block top')
    supports = []
    for side, end, px, pz in bearing_points(x, z, hatch, -1):
        supports.append({
            'position': [int(px // 1), int(round(seat)) - 1, int(pz // 1)], 'state': SUPPORT,
            'source_contact': {'x': round(px, 3), 'y': float(round(seat)), 'z': round(pz, 3)},
            'normal': [0.0, 1.0, 0.0], 'half_width_m': .05, 'contact_half_width_m': .05,
            'source_contact_kind': 'native_top_face', 'source_contact_triangle_witnesses': [f'bearing/{side}/{end}#4']})
    new = dict(gate, frame=dict(gate['frame'], position=[x, frame_y, z]), silo_hatch=hatch, supports=supports)
    return new, old_y, frame_y


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--door-layer', type=int, default=26, help='y of the closed door proxy layer; the ground top is one above')
    a = parser.parse_args()
    owner_path = a.world / OWNER
    text = owner_path.read_bytes().decode('utf-8')
    owner = json.loads(text)
    if json.dumps(owner, indent=1, ensure_ascii=False).replace('\n', '\r\n') != text:
        raise SystemExit('The owner file is not in the layout this tool rewrites; nothing changed')
    index = next(i for i, g in enumerate(owner['gates']) if g['resource'] == GATE)
    gate = owner['gates'][index]
    table_path = a.world / gate['collision_steps']['cells_file']
    steps = json.loads(gzip.decompress(table_path.read_bytes()))
    new, old_y, frame_y = plan(gate, a.door_layer)
    new_steps = [[dict(cell, position=[cell['position'][0], a.door_layer, cell['position'][2]], closed=COVER, open='minecraft:air')
                  for cell in step] for step in steps]
    if new == dict(gate, collision_steps=new['collision_steps']) and new_steps == steps:
        raise SystemExit('The door is already on this layer; nothing changed')
    packed = gzip.compress(json.dumps(new_steps, separators=(',', ':')).encode('utf-8'), mtime=0)
    new['collision_steps'] = dict(gate['collision_steps'], sha256=hashlib.sha256(packed).hexdigest())
    owner['gates'][index] = new

    x, _, z = gate['frame']['position']
    entities = a.world / ENTITIES / f'r.{int(x) >> 9}.{int(z) >> 9}.mca'
    with stopped_world(a.world):
        # The blocks the new record names must already be there.
        regions, sections = {}, {}

        def state_at(px, py, pz):
            key = px >> 4, py >> 4, pz >> 4
            if key not in sections:
                # The door is wider than a region file is long: its cells lie in several.
                name = px >> 9, pz >> 9
                if name not in regions:
                    regions[name] = bytearray((a.world / REGION / f'r.{name[0]}.{name[1]}.mca').read_bytes())
                root = read_chunk(regions[name], key[0], key[2])[3]
                found = [s for s in root['sections'] if int(s['Y']) == key[1] and 'block_states' in s]
                sections[key] = decode(found[0]['block_states']) if found else None
            if sections[key] is None:
                return 'minecraft:air'
            ids, palette = sections[key]
            return palette[ids[((py & 15) << 8) | ((pz & 15) << 4) | (px & 15)]]
        wrong = [s['position'] for s in new['supports'] if state_at(*s['position']) != s['state']]
        if wrong:
            raise SystemExit(f'Support cells are not structural panels yet: {wrong[:4]}')
        open_cells = [c['position'] for step in new_steps for c in step if state_at(*c['position']) != c['closed']]
        if open_cells:
            raise SystemExit(f'{len(open_cells)} cells of the new door layer are not cover blocks yet, first {open_cells[0]}')

        buf = bytearray(entities.read_bytes())
        cx, cz = int(x) >> 4, int(z) >> 4
        slot, loc, count, root = read_chunk(buf, cx, cz)
        wanted = [v - (1 << 32) if v >= 1 << 31 else v for v in (int(gate['visual'].replace('-', '')[i:i + 8], 16) for i in range(0, 32, 8))]
        doors = [e for e in root['Entities'] if [int(v) for v in e['UUID']] == wanted]
        if len(doors) != 1:
            raise SystemExit(f'Expected the one door entity {gate["visual"]} in chunk {cx},{cz}, found {len(doors)}')
        door = doors[0]
        declared = door['R52DeclaredHatch']
        if [float(v) for v in door['Pos']] != [float(x), float(old_y), float(z)]:
            raise SystemExit(f'The door entity is not on its declared frame: {list(door["Pos"])}')
        if float(declared['Raw']) != 0 or float(declared['Target']) != 0:
            raise SystemExit('The door is not closed and at rest; nothing changed')
        spec = declared['Spec']
        if float(spec['OpeningX']) != gate['silo_hatch']['opening_x'] or int(spec['OpenTicks']) != gate['silo_hatch']['open_ticks']:
            raise SystemExit('The door entity declares another hatch than the gate record')
        door['Pos'] = nbtlib.List[nbtlib.Double]([nbtlib.Double(x), nbtlib.Double(frame_y), nbtlib.Double(z)])
        spec['SeparationSign'] = nbtlib.Int(-1)
        spec['BeamBottom'] = nbtlib.Double(BEAM_BOTTOM)
        write_chunk(buf, slot, loc, count, root)

        a.out.mkdir(parents=True, exist_ok=False)
        for path in (owner_path, table_path, entities):
            target = a.out / path.relative_to(a.world)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        table_path.write_bytes(packed)
        owner_path.write_bytes(json.dumps(owner, indent=1, ensure_ascii=False).replace('\n', '\r\n').encode('utf-8'))
        entities.write_bytes(buf)
    print(json.dumps({'gate': GATE, 'frame_y': [old_y, frame_y], 'door_layer': a.door_layer, 'closed_cells': COVER,
                      'supports': [s['position'] for s in new['supports']], 'collision_cells': sum(len(s) for s in new_steps),
                      'collision_table_sha256': new['collision_steps']['sha256'], 'backup': str(a.out)}))


if __name__ == '__main__':
    main()
