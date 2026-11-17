"""Take the old rifle lift station of Tokyo-3 out of a stopped world.

From R64 the four spare-weapon towers hand out the pallet rifle (docs/ARMAMENT_TOWERS_R64.zh.md). The lift station
that did it before stands in the launch row at (120.5, 80, -35.5): one armament station entity over a real shaft
whose mouth is a lid of barriers, 11 by 19, in a pad of NERV floor panels. Retiring it is two steps:

    python tools/retire_rifle_station.py rows   --world <save> --out <rows.json>
        The block rows that turn the lid into floor like the pad round it, for tools/write_deep_cells.py.
        Reads only. The shaft under the lid stays as it is, closed in.

    python tools/retire_rifle_station.py remove --world <save> --out <new backup folder>
        Removes the station entity, after the rows have been written. The entities file is copied to --out first.

`remove` touches one entity and refuses unless everything fits: exactly one armament station at that position, it
carries the rifle, it is not bound to a tower, to an equipment well or to a mission rack, it is stowed, the lid is
already floor, and the world has its spare-weapon towers armed, so that it is not left without a rifle.
"""
import argparse
import json
import math
import shutil
from collections import Counter
from pathlib import Path

import nbtlib

from install_r53_carrier_trays import stopped_world
from write_deep_cells import decode, read_chunk, write_chunk

REGION = 'dimensions/projectseele/geofront/region'
ENTITIES = 'dimensions/projectseele/geofront/entities'
TOWERS_TABLE = 'r64_armament_towers.json'
TOWERS_DATA = 'dimensions/projectseele/geofront/data/projectseele_armament_towers_r64.dat'
STATION = 'projectseele:nerv_armament_station'
POSITION = (120.5, 80.0, -35.5)
RIFLE = 4
STOWED = 0
LID = 'minecraft:barrier'
FLOOR = 'projectseele:nerv_floor_panel'
# The station's surface frame: five either side of its centre block across, nine along.
LID_X = range(115, 126)
LID_Z = range(-45, -26)
LID_Y = 80
# What marks a station that is something else: a tower's, a well's, a mission rack's.
FOREIGN_TAGS = ('R47Vault', 'TvMissionRackUnitR45', 'TvMissionCargoStackR45', 'R64Tower')


class Blocks:
    def __init__(self, world):
        self.dir, self.regions, self.sections = world / REGION, {}, {}

    def state(self, x, y, z):
        key = x >> 4, y >> 4, z >> 4
        if key not in self.sections:
            name = x >> 9, z >> 9
            if name not in self.regions:
                self.regions[name] = bytearray((self.dir / f'r.{name[0]}.{name[1]}.mca').read_bytes())
            root = read_chunk(self.regions[name], key[0], key[2])[3]
            found = [s for s in root['sections'] if int(s['Y']) == key[1] and 'block_states' in s]
            self.sections[key] = decode(found[0]['block_states']) if found else None
        if self.sections[key] is None:
            return 'minecraft:air'
        ids, palette = self.sections[key]
        return str(palette[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]])


def lid_cells():
    return [(x, LID_Y, z) for x in LID_X for z in LID_Z]


def rows(world, out):
    blocks = Blocks(world)
    # The pad's own panel, read from the ring of cells round the lid: the lid becomes the same block.
    ring = Counter(blocks.state(x, LID_Y, z) for x in range(LID_X.start - 1, LID_X.stop + 1) for z in range(LID_Z.start - 1, LID_Z.stop + 1)
                   if x not in LID_X or z not in LID_Z)
    floor, count = ring.most_common(1)[0]
    if not floor.startswith(FLOOR) or count != sum(ring.values()):
        raise SystemExit(f'The pad round the lid is not all floor panels: {dict(ring)}')
    listed, already = [], 0
    for cell in lid_cells():
        state = blocks.state(*cell)
        if state == floor:
            already += 1
        elif state == LID:
            listed.append([*cell, state, floor])
        else:
            raise SystemExit(f'The lid is not what this tool closes: {state} at {cell}')
    if out.exists():
        raise SystemExit(f'{out} is already there')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(listed), 'utf8')
    print(json.dumps({'rows': len(listed), 'already_floor': already, 'floor': floor, 'file': str(out)}))


def remove(world, out):
    table = world / TOWERS_TABLE
    record = world / TOWERS_DATA
    if not table.is_file() or not record.is_file():
        raise SystemExit('This world has no spare-weapon towers yet; the rifle station stays')
    planned = len(json.loads(table.read_text('utf8'))['towers'])
    armed = len(nbtlib.load(str(record))['data']['Stations'])
    if planned < 1 or armed != planned:
        raise SystemExit(f'{armed} of {planned} spare-weapon towers have their station; the rifle station stays')
    cx, cz = math.floor(POSITION[0]) >> 4, math.floor(POSITION[2]) >> 4
    entities = world / ENTITIES / f'r.{cx >> 5}.{cz >> 5}.mca'
    with stopped_world(world):
        blocks = Blocks(world)
        open_lid = [cell for cell in lid_cells() if not blocks.state(*cell).startswith(FLOOR)]
        if open_lid:
            raise SystemExit(f'{len(open_lid)} cells of the lid are not floor yet, first {open_lid[0]}; write the rows first')
        buf = bytearray(entities.read_bytes())
        slot, loc, count, root = read_chunk(buf, cx, cz)
        found = [i for i, e in enumerate(root['Entities'])
                 if str(e['id']) == STATION and [float(v) for v in e['Pos']] == list(POSITION)]
        if not found:
            raise SystemExit('No armament station stands there; nothing changed')
        if len(found) != 1:
            raise SystemExit(f'{len(found)} armament stations stand there; nothing changed')
        station = root['Entities'][found[0]]
        if int(station.get('PayloadR47', RIFLE)) != RIFLE:
            raise SystemExit('The station there does not carry the rifle; nothing changed')
        foreign = [tag for tag in FOREIGN_TAGS if tag in station.get('ForgeData', {})] + (['TowerR64'] if 'TowerR64' in station else [])
        if foreign:
            raise SystemExit(f'The station there belongs to something else ({", ".join(foreign)}); nothing changed')
        if int(station['StationState']) != STOWED or float(station['LiftProgress']) != 0 or float(station['HatchProgress']) != 0:
            raise SystemExit('The station is not stowed; nothing changed')
        if 'Passengers' in station:
            raise SystemExit('Something rides the station; nothing changed')
        uuid = ''.join('%08x' % (int(v) & 0xFFFFFFFF) for v in station['UUID'])
        del root['Entities'][found[0]]
        write_chunk(buf, slot, loc, count, root)

        out.mkdir(parents=True, exist_ok=False)
        target = out / entities.relative_to(world)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entities, target)
        entities.write_bytes(buf)
    print(json.dumps({'removed': STATION, 'uuid': uuid, 'position': list(POSITION), 'towers_armed': armed, 'backup': str(out)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=('rows', 'remove'))
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    (rows if a.step == 'rows' else remove)(a.world, a.out)


if __name__ == '__main__':
    main()
