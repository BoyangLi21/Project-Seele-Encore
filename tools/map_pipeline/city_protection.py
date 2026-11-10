"""Cold map-edit guard for the whole-city lift of Tokyo-3, read from the installed city topology.

The lift refuses to move while anything foreign sits where a building has to go, and it compares
every street hatch cell with the cover it expects. So three volumes per building are protected:
the hatch layer at street level, the space the building rises into, and the space it sinks into.
Both building lists in the topology count; the second one (Original96Towers) once went unchecked.
"""
from pathlib import Path

import nbtlib

from map_pipeline.launch_protection import LaunchProtection


def unpack(value):
    x = value >> 38
    z = (value >> 12) & 0x3FFFFFF
    y = value & 0xFFF
    return x, y - (1 << 12) if y >= (1 << 11) else y, z - (1 << 26) if z >= (1 << 25) else z


def load(world):
    path = next(Path(world, 'dimensions/projectseele/geofront/data').glob('projectseele_city_rigid_topology_r45_*.dat'), None)
    if path is None:
        raise ValueError('Installed city topology is required for map work')
    data = nbtlib.load(path)['data']
    lists = (('towers', data['Towers']), ('original96', data['LowriseAddonR48']['Original96Towers']))
    boxes, seen = [], set()
    for label, buildings in lists:
        for i, tower in enumerate(buildings):
            x, y, z = unpack(int(tower['Centre']))
            box = tower['Footprint']
            x0, x1, z0, z1 = x + int(box['MinX']), x + int(box['MaxX']), z + int(box['MinZ']), z + int(box['MaxZ'])
            height, low = int(tower['Height']), int(tower['RetractedBaseY'])
            for kind, bounds in (('hatch', (x0, y, z0, x1, y, z1)),
                                 ('raised', (x0, y + 1, z0, x1, y + height + 3, z1)),
                                 ('lowered', (x0, low, z0, x1, low + height + 3, z1))):
                if bounds not in seen:
                    seen.add(bounds)
                    boxes.append((f'city lift {kind} {label}/{i}', bounds))
    return LaunchProtection(boxes, dict(buildings=sum(len(b) for _, b in lists), volumes=len(boxes)))
