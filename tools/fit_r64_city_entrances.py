"""Build fitted personnel door surrounds for the installed movable city towers."""
import argparse
import json
from pathlib import Path
from uuid import UUID

import nbtlib
from map_buildings.mca import World
from map_pipeline.city_protection import unpack
from write_deep_cells import state_entry

DOOR = 'projectseele:city_personnel_door'
AIR = 'minecraft:air'
NORMAL = {'south': (0, 1), 'north': (0, -1), 'east': (1, 0), 'west': (-1, 0)}


def long_position(point):
    x, y, z = point
    value = (x & 0x3ffffff) << 38 | (z & 0x3ffffff) << 12 | (y & 4095)
    return nbtlib.Long(value if value < 1 << 63 else value - (1 << 64))


def frames(cells):
    states = {unpack(int(cell['Pos'])): cell['State'] for cell in cells}
    def material(point):
        state = states.get(point)
        return str(state['Name']) if state is not None else AIR

    additions = {}
    pairs = 0
    for (x, y, z), state in states.items():
        if str(state['Name']) != DOOR or str(state['Properties']['half']) != 'lower':
            continue
        dx, dz = NORMAL[str(state['Properties']['facing'])]
        tx, tz = abs(dz), abs(dx)
        def at(t, up, setback):
            return x + tx*t - dx*setback, y + up, z + tz*t - dz*setback
        if material(at(1, 0, 0)) != DOOR or material(at(-1, 0, 0)) == DOOR:
            continue
        if any(material(at(t, 1, 0)) != DOOR for t in (0, 1)):
            continue
        pairs += 1
        # This facade has a four-wide recessed opening and a complete wall
        # above it. Other designs, including interior and service doors, differ.
        side = [material(at(t, 0, 1)) for t in (-2, 3)]
        if any('glass' not in s and 'concrete' not in s for s in side):
            continue
        if any(material(at(t, 3, 1)) == AIR for t in (0, 1)):
            continue
        for t in range(-1, 3):
            for up in range(3):
                if t in (0, 1) and up < 2:
                    continue
                for setback in (0, 1):
                    p = at(t, up, setback)
                    if material(p) == AIR:
                        additions[p] = 'minecraft:gray_concrete' if up == 2 or setback == 0 else side[int(t == 2)]
    return pairs, additions


def plan(world, out):
    root = world / 'dimensions/projectseele/geofront'
    data = root / 'data'
    control = nbtlib.load(next(data.glob('projectseele_city_rigid_control_r45_*.dat')))['data']
    if str(control['Phase']) != 'IDLE':
        raise ValueError('Finish city travel before updating its cargo')
    topology = nbtlib.load(next(data.glob('projectseele_city_rigid_topology_r45_*.dat')))['data']['Towers']
    journey = control.get('Journey')
    saved = int(control['SavedPlans'])
    journey_id = str(UUID(bytes=b''.join((int(i) & 0xffffffff).to_bytes(4, 'big') for i in journey))) if journey is not None else ''
    reader = World(root / 'region')
    rows, sites = [], []
    pairs_total = 0
    cargo_dir = Path('dimensions/projectseele/geofront/data/city_rigid_generation_r45/cargo')
    for i, spec in enumerate(topology):
        rel = cargo_dir / f'{i}.dat'
        archive = nbtlib.load(world / rel)
        b = archive['data']['Buildings'][0]
        cells = b['Cargo']
        archived_journey = tuple(b.get('RelocationSnapshotJourney', ()))
        source_journal = journey is not None and tuple(journey) != archived_journey and saved in (96, len(topology)) and i < saved
        if source_journal:
            last = nbtlib.load(data/'city_rigid_journal_r45'/journey_id/f'{i}.dat')
            if str(last['WorldUUID']) != str(control['WorldUUID']) or int(last['Index']) != i:
                raise ValueError(f'Unexpected city journal for building {i}')
            cells = last['Cells']
        pairs, additions = frames(cells)
        pairs_total += pairs
        if not additions:
            continue
        gx, base, gz = unpack(int(spec['Centre']))
        if int(control['Depth']) != 0:
            base = int(spec['RetractedBaseY'])
        foot = spec['Footprint']
        for (x,y,z), new in additions.items():
            if not (foot['MinX'] <= x <= foot['MaxX'] and foot['MinZ'] <= z <= foot['MaxZ'] and 0 < y <= spec['Height']+3):
                raise ValueError(f'Frame outside moving building {i}')
            pos = (gx+x, base+y, gz+z)
            before = reader.get(*pos)
            if before == AIR:
                rows.append([*pos,before,new])
            elif before != new:
                raise ValueError(f'Occupied entrance {pos}: {before}')
        if source_journal:
            cells = nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'Pos':c['Pos'],'State':c['State'],**({'NBT':c['Data']} if 'Data' in c else {})}) for c in cells])
            b['RelocationSnapshotJourney'] = journey
        b['Cargo'] = cells
        for pos, new in sorted(additions.items()):
            cells.append(nbtlib.Compound({'Pos':long_position(pos), 'State':state_entry(new)}))
        target = out/'recipes'/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        archive.save(target)
        sites.append({'tower':i, 'centre':[gx,base,gz], 'frame_cells':len(additions)})
        reader.chunks.clear()
    out.mkdir(parents=True, exist_ok=True)
    (out/'door_rows.json').write_text(json.dumps(rows),'utf8')
    result = dict(towers=len(topology), pairs=pairs_total, frames=len(sites), added=len(rows), sites=sites)
    (out/'doors.json').write_text(json.dumps(result,indent=2),'utf8')
    print({k:v for k,v in result.items() if k!='sites'},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('world',type=Path)
    parser.add_argument('out',type=Path)
    args=parser.parse_args()
    plan(args.world,args.out)
