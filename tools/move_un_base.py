"""Move the whole UN base as one rigid block, on a stopped world: chunks, entities, data, MTR, then the offset.

Every touched file is copied to the output folder first. The offset is a whole number of chunks and
sections, so sections move intact. The stages run in the order the code's own checks demand: the
FacilitySites offset is written last, or the hangar doors would be rebuilt beside their real entities.
Run the MTR stage's depot regeneration through plan_rail_corridor.py after the `mtr` stage.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

import nbtlib

from install_r53_carrier_trays import stopped_world
from prepare_mtr_member_patch_r52 import Parser
from write_deep_cells import clear_light, read_chunk, write_chunk

DX, DY, DZ = -2400, -144, 7536
CDX, CSY, CDZ = DX // 16, DY // 16, DZ // 16
X0, X1, Z0, Z1 = 6208, 6895, -7088, -5945
DIM = 'dimensions/projectseele/geofront'
JSON_FILES = ('r52/travel.json', 'regional_boarding_gates.json', 'r44_public_station_gates.json', 'nerv_staff_r15.json', 'ROOT_MECHANICAL_OWNER.json',
              'r07_installations.json', 'regional_plan.json', 'un01_annex_r20.json', 'un_hangars_r31.json', 'facility_lighting_r30.json')
NATURAL_TARGET = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air', 'minecraft:water', 'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block',
                  'minecraft:gravel', 'minecraft:sand', 'minecraft:seagrass', 'minecraft:tall_seagrass', 'minecraft:kelp', 'minecraft:kelp_plant', 'minecraft:coarse_dirt',
                  'minecraft:grass', 'minecraft:tall_grass', 'minecraft:fern', 'minecraft:deepslate', 'minecraft:bedrock', 'minecraft:clay', 'minecraft:sandstone', 'minecraft:snow')


def inside(x, z):
    return X0 <= x <= X1 and Z0 <= z <= Z1


def unpack(value):
    x = value >> 38
    z = (value >> 12) & 0x3FFFFFF
    y = value & 0xFFF
    return x, y - (1 << 12) if y >= (1 << 11) else y, z - (1 << 26) if z >= (1 << 25) else z


def pack(x, y, z):
    return ((x & 0x3FFFFFF) << 38 | (z & 0x3FFFFFF) << 12 | (y & 0xFFF)) - (1 << 64 if x & 0x2000000 else 0)


def moved_long(value):
    x, y, z = unpack(int(value))
    return pack(x + DX, y + DY, z + DZ)


def region_of(folder, cx, cz):
    return folder / f'r.{cx >> 5}.{cz >> 5}.mca'


class Regions:
    """Region files held in memory, each copied to the backup folder before its first change."""
    def __init__(self, folder, backup):
        self.folder, self.backup, self.buffers = Path(folder), Path(backup), {}
        self.backup.mkdir(parents=True, exist_ok=True)

    def get(self, cx, cz):
        path = region_of(self.folder, cx, cz)
        if path not in self.buffers:
            if path.exists():
                shutil.copy2(path, self.backup / path.name)
                self.buffers[path] = bytearray(path.read_bytes())
            else:
                self.buffers[path] = bytearray(8192)
        return self.buffers[path]

    def read(self, cx, cz):
        buffer = self.get(cx, cz)
        i = 4 * ((cx & 31) + (cz & 31) * 32)
        if not int.from_bytes(buffer[i:i + 3], 'big'):
            return None
        return read_chunk(buffer, cx, cz)[3]

    def write(self, cx, cz, root):
        buffer = self.get(cx, cz)
        i = 4 * ((cx & 31) + (cz & 31) * 32)
        write_chunk(buffer, i, int.from_bytes(buffer[i:i + 3], 'big'), buffer[i + 3], root)

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        for path, buffer in self.buffers.items():
            swap = path.with_name(path.name + '.swap')
            swap.write_bytes(buffer)
            swap.replace(path)


def source_chunks():
    return [(cx, cz) for cx in range(X0 >> 4, (X1 >> 4) + 1) for cz in range(Z0 >> 4, (Z1 >> 4) + 1)]


def moved_chunk(root, top_biomes):
    """The same chunk, one offset away; sections shift whole and the world's lowest ones drop off."""
    root['xPos'] = nbtlib.Int(int(root['xPos']) + CDX)
    root['zPos'] = nbtlib.Int(int(root['zPos']) + CDZ)
    sections = {int(s['Y']): s for s in root['sections']}
    low, high = min(sections), max(sections)
    fresh = []
    for y in range(low, high + 1):
        source = y - CSY
        if source in sections:
            section = sections[source]
            section['Y'] = nbtlib.Byte(y)
        else:
            section = nbtlib.Compound({'Y': nbtlib.Byte(y), 'biomes': top_biomes(sections), 'block_states': nbtlib.Compound({'palette': nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'Name': nbtlib.String('minecraft:air')})])})})
        fresh.append(section)
    root['sections'] = nbtlib.List[nbtlib.Compound](fresh)
    for entity in root.get('block_entities', []):
        entity['x'] = nbtlib.Int(int(entity['x']) + DX)
        entity['y'] = nbtlib.Int(int(entity['y']) + DY)
        entity['z'] = nbtlib.Int(int(entity['z']) + DZ)
        if 'PlatformCentre' in entity:
            entity['PlatformCentre'] = nbtlib.Long(moved_long(entity['PlatformCentre']))
    for key in ('block_ticks', 'fluid_ticks'):
        for tick in root.get(key, []):
            tick['x'] = nbtlib.Int(int(tick['x']) + DX)
            tick['y'] = nbtlib.Int(int(tick['y']) + DY)
            tick['z'] = nbtlib.Int(int(tick['z']) + DZ)
    if 'PostProcessing' in root:
        lists = list(root['PostProcessing'])
        root['PostProcessing'] = nbtlib.List[nbtlib.List]([nbtlib.List[nbtlib.Short]([]) for _ in lists])
    if 'Heightmaps' in root:
        del root['Heightmaps']
    root['structures'] = nbtlib.Compound({'References': nbtlib.Compound(), 'starts': nbtlib.Compound()})
    clear_light(root)
    return root


def stage_chunks(world, out):
    regions = Regions(world / DIM / 'region', out / 'region')
    moved, skipped, blocked = 0, Counter(), Counter()

    def top_biomes(sections):
        return sections[max(sections)]['biomes']

    where = []
    for cx, cz in source_chunks():
        source = regions.read(cx, cz)
        if source is None or str(source.get('Status', '')).removeprefix('minecraft:') != 'full':
            continue        # chunks that do not move leave their target untouched
        target = regions.read(cx + CDX, cz + CDZ)
        if target is not None:
            for section in target['sections']:
                states = section.get('block_states')
                for entry in (states['palette'] if states is not None else ()):
                    name = str(entry['Name'])
                    if name not in NATURAL_TARGET and not name.endswith(('_leaves', '_log')):
                        blocked[name] += 1
                        where.append((cx + CDX, cz + CDZ))
    if blocked:
        raise SystemExit(f'Target chunks hold built blocks: {blocked.most_common(12)} in chunks {sorted(set(where))[:30]}')
    for cx, cz in source_chunks():
        root = regions.read(cx, cz)
        if root is None or str(root.get('Status', '')).removeprefix('minecraft:') != 'full':
            skipped['not full'] += 1
            continue
        regions.write(cx + CDX, cz + CDZ, moved_chunk(root, top_biomes))
        moved += 1
    regions.save()
    print(json.dumps(dict(stage='chunks', moved=moved, skipped=dict(skipped))))


def shifted_entity(entity):
    pos = entity['Pos']
    entity['Pos'] = nbtlib.List[nbtlib.Double]([nbtlib.Double(float(pos[0]) + DX), nbtlib.Double(float(pos[1]) + DY), nbtlib.Double(float(pos[2]) + DZ)])
    data = entity.get('ForgeData')
    if data is not None and 'UNHomeX' in data:
        data['UNHomeX'] = type(data['UNHomeX'])(float(data['UNHomeX']) + DX)
        data['UNHomeY'] = type(data['UNHomeY'])(float(data['UNHomeY']) + DY)
        data['UNHomeZ'] = type(data['UNHomeZ'])(float(data['UNHomeZ']) + DZ)
    if 'StaffStation' in entity:
        entity['StaffStation'] = nbtlib.Long(moved_long(entity['StaffStation']))
    for key in list(entity):
        for offset, axis in ((DX, 'X'), (DY, 'Y'), (DZ, 'Z')):
            if (key.startswith(('FieldStart', 'FieldEscape', 'FieldLanding')) or key.startswith('CanonicalTranslation')) and key.endswith(axis):
                entity[key] = type(entity[key])(float(entity[key]) + offset)
    return entity


def stage_entities(world, out):
    regions = Regions(world / DIM / 'entities', out / 'entities')
    arrivals, moved, kinds = {}, 0, Counter()
    for cx, cz in source_chunks():
        root = regions.read(cx, cz)
        if root is None or not len(root.get('Entities', [])):
            continue
        stay = []
        for entity in root['Entities']:
            pos = entity['Pos']
            if inside(float(pos[0]), float(pos[2])):
                shifted_entity(entity)
                key = (int(float(entity['Pos'][0])) >> 4, int(float(entity['Pos'][2])) >> 4)
                arrivals.setdefault(key, []).append(entity)
                moved += 1
                kinds[str(entity['id'])] += 1
            else:
                stay.append(entity)
        root['Entities'] = nbtlib.List[nbtlib.Compound](stay)
        regions.write(cx, cz, root)
    for (cx, cz), entities in arrivals.items():
        root = regions.read(cx, cz)
        if root is None:
            root = nbtlib.File({'DataVersion': nbtlib.Int(3465), 'Position': nbtlib.IntArray([cx, cz]), 'Entities': nbtlib.List[nbtlib.Compound]([])})
        if len(root['Entities']):
            raise SystemExit(f'Target entity chunk {cx},{cz} is not empty')
        root['Entities'] = nbtlib.List[nbtlib.Compound](entities)
        regions.write(cx, cz, root)
    regions.save()
    print(json.dumps(dict(stage='entities', moved=moved, kinds=kinds.most_common(30))))


def shifted_triple(values, start=0):
    values[start] += DX
    values[start + 1] += DY
    values[start + 2] += DZ


def shift_json(node, tally):
    """Move every coordinate triple inside the old footprint; identifiers stay as they are."""
    number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if isinstance(node, dict):
        for value in node.values():
            shift_json(value, tally)
    elif isinstance(node, list):
        if len(node) >= 3 and all(number(v) for v in node[:3]) and inside(node[0], node[2]):
            shifted_triple(node)
            if len(node) == 6 and all(number(v) for v in node[3:]) and inside(node[3], node[5]):
                shifted_triple(node, 3)
            tally['triples'] += 1
        else:
            for value in node:
                shift_json(value, tally)


def stage_data(world, out):
    (out / 'json').mkdir(parents=True, exist_ok=True)
    report = {}
    for name in JSON_FILES:
        path = world / name
        backup = out / 'json' / name.replace('/', '__')
        shutil.copy2(path, backup)
        value = json.loads(path.read_text('utf8'))
        tally = Counter()
        shift_json(value, tally)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')
        report[name] = tally['triples']
    data = world / DIM / 'data'
    (out / 'saved').mkdir(parents=True, exist_ok=True)
    shutil.copy2(data / 'projectseele_un_locations_r22.dat', out / 'saved')
    located = nbtlib.load(data / 'projectseele_un_locations_r22.dat')
    for key in list(located['data']):
        located['data'][key] = nbtlib.Long(moved_long(located['data'][key]))
    located.save(data / 'projectseele_un_locations_r22.dat', gzipped=True)
    shutil.copy2(data / 'projectseele_un_airlift_r29.dat', out / 'saved')
    airlift = nbtlib.load(data / 'projectseele_un_airlift_r29.dat')
    if len(airlift['data']['Jobs']):
        raise SystemExit('An air transport is in progress')
    for key in ('CartPos0', 'CartPos1'):
        airlift['data'][key] = nbtlib.Long(moved_long(airlift['data'][key]))
    airlift.save(data / 'projectseele_un_airlift_r29.dat', gzipped=True)
    chunks = Counter()
    for path, label in ((data / 'superbwarfare_chunk_pos.dat', 'dim'), (world / 'data/superbwarfare_chunk_pos.dat', 'overworld')):
        if not path.exists():
            continue
        shutil.copy2(path, out / 'saved' / (label + '-' + path.name))
        table = nbtlib.load(path)
        for row in table['data']['Pos']:
            if (X0 >> 4) <= int(row['X']) <= (X1 >> 4) and (Z0 >> 4) <= int(row['Z']) <= (Z1 >> 4):
                row['X'] = nbtlib.Int(int(row['X']) + CDX)
                row['Z'] = nbtlib.Int(int(row['Z']) + CDZ)
                chunks[label] += 1
        table.save(path, gzipped=True)
    print(json.dumps(dict(stage='data', json=report, sbw_chunks=dict(chunks))))


def pack_msg(value, out):
    import struct
    if value is None:
        out.append(0xc0)
    elif value is True:
        out.append(0xc3)
    elif value is False:
        out.append(0xc2)
    elif isinstance(value, float):
        out.append(0xcb)
        out.extend(struct.pack('>d', value))
    elif isinstance(value, int):
        if 0 <= value < 128:
            out.append(value)
        elif -32 <= value < 0:
            out.extend(struct.pack('>b', value))
        elif -2 ** 31 <= value < 2 ** 31:
            out.append(0xd2)
            out.extend(struct.pack('>i', value))
        else:
            out.append(0xd3)
            out.extend(struct.pack('>q', value))
    elif isinstance(value, str):
        data = value.encode('utf8')
        if len(data) < 32:
            out.append(0xa0 | len(data))
        elif len(data) < 256:
            out.extend((0xd9, len(data)))
        else:
            out.append(0xda)
            out.extend(struct.pack('>H', len(data)))
        out.extend(data)
    elif isinstance(value, list):
        if len(value) < 16:
            out.append(0x90 | len(value))
        else:
            out.append(0xdc)
            out.extend(struct.pack('>H', len(value)))
        for item in value:
            pack_msg(item, out)
    elif isinstance(value, dict):
        if len(value) < 16:
            out.append(0x80 | len(value))
        else:
            out.append(0xde)
            out.extend(struct.pack('>H', len(value)))
        for key, item in value.items():
            pack_msg(key, out)
            pack_msg(item, out)
    else:
        raise TypeError(type(value))


def dumps(value):
    out = bytearray()
    pack_msg(value, out)
    return bytes(out)


def shifted_position(position):
    return {'x': position['x'] + DX, 'y': position['y'] + DY, 'z': position['z'] + DZ}


def rail_name(a, b):
    """MTR names a rail after its ends in signed coordinate order, as 64-bit two's complement hex."""
    ends = sorted((tuple(a[k] for k in 'xyz'), tuple(b[k] for k in 'xyz')))
    return '-'.join(f'{v & 0xFFFFFFFFFFFFFFFF:016X}' for end in ends for v in end)


def stage_mtr(world, out):
    root = world / 'mtr/projectseele/geofront'
    backup = out / 'mtr'
    moved = Counter()
    for path in [p for p in (root / 'rails').rglob('*') if p.is_file()]:
        rail = Parser(path.read_bytes()).node().value
        one, two = inside(rail['position1']['x'], rail['position1']['z']), inside(rail['position2']['x'], rail['position2']['z'])
        if one != two:
            raise SystemExit(f'Rail crosses the base edge: {path.name}')
        if not one:
            continue
        keep = backup / 'rails' / path.parent.name
        keep.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, keep / path.name)
        rail['position1'], rail['position2'] = shifted_position(rail['position1']), shifted_position(rail['position2'])
        name = rail_name(rail['position1'], rail['position2'])
        target = root / 'rails' / name[-2:] / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(dumps(rail))
        path.unlink()
        moved['rails'] += 1
    for kind in ('platforms', 'stations'):
        for path in [p for p in (root / kind).rglob('*') if p.is_file()]:
            member = Parser(path.read_bytes()).node().value
            if not inside(member['position1']['x'], member['position1']['z']):
                continue
            keep = backup / kind / path.parent.name
            keep.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, keep / path.name)
            member['position1'], member['position2'] = shifted_position(member['position1']), shifted_position(member['position2'])
            path.write_bytes(dumps(member))
            moved[kind] += 1
    print(json.dumps(dict(stage='mtr', moved=dict(moved))))


def stage_sites(world, out):
    path = world / DIM / 'data/projectseele_facility_sites.dat'
    (out / 'saved').mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, out / 'saved' / path.name)
    sites = nbtlib.load(path)
    if 'UN_BASE' in sites['data']['Offsets']:
        raise SystemExit('UN_BASE is already set')
    sites['data']['Offsets']['UN_BASE'] = nbtlib.IntArray([DX, DY, DZ])
    sites.save(path, gzipped=True)
    print(json.dumps(dict(stage='sites', offsets={k: list(map(int, v)) for k, v in sites['data']['Offsets'].items()})))


STAGES = dict(chunks=stage_chunks, entities=stage_entities, data=stage_data, mtr=stage_mtr, sites=stage_sites)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('stage', choices=tuple(STAGES))
    arguments = parser.parse_args()
    with stopped_world(arguments.world):
        STAGES[arguments.stage](arguments.world, arguments.out)
