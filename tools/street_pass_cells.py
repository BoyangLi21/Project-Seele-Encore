"""Lists that keep the street furniture from tripping the giants (R64), from a stopped world.

  python tools/street_pass_cells.py --world <save> --rows <furniture rows.json> [--rows ...]
                                    [--extra tools/street_pass_extra_r64.json] --out <new folder>

--rows are the block rows the furniture was written with (x, y, z, before, after, as tools/write_deep_cells.py
takes them); a cell is taken only while the world still holds the block its row put there, so cells taken out or
built over since are left out. --extra lists columns of other small things a giant should walk through (cells
between y0 and y1 that are not air), such as the bushes and lamps on Sachiel's first-battle route.

Writes into --out (a new folder):
  street_pass_r64.json  The street-pass list for StreetPassR64: the cells and the kinds of block in them. Copy it
                        into the world root; it is read when the server starts. A Unit, an Angel and a
                        mass-production unit then walk through these cells; everything else collides as before.
  battlefield_r21.json  The world's street-fixture table with the furniture added (shown: its block, covered: air,
                        a sign with its text), so that the city hides the furniture once it rests lowered and puts
                        it back before it rises (BattlefieldR21). Copy it over the world's own. Only with a jar that
                        has the cover fix of the same change: older jars hide the fixtures again while a raise waits.
  cover_rows.json       Rows that take the furniture away now, for a world that is lowered with its fixtures hidden
                        (the table's saved state says so), so that the world matches the table. Write them with
                        tools/write_deep_cells.py --allow-block-entities. Empty when the fixtures are shown.
  report.json
Reads only; nothing in the world is changed.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import nbtlib

from write_deep_cells import decode, read_chunk

REGION = 'dimensions/projectseele/geofront/region'
DIMENSION = 'projectseele:geofront'
SCHEMA = 'projectseele.r64.street-pass.v1'
FIXTURES = 'battlefield_r21.json'
FIXTURE_STATE = 'dimensions/projectseele/geofront/data/projectseele_battlefield_r21.dat'
AIR = 'minecraft:air'


class World:
    def __init__(self, root):
        self.dir, self.regions, self.chunks, self.sections = root / REGION, {}, {}, {}

    def chunk(self, cx, cz):
        if (cx, cz) not in self.chunks:
            name = cx >> 5, cz >> 5
            if name not in self.regions:
                path = self.dir / f'r.{name[0]}.{name[1]}.mca'
                self.regions[name] = bytearray(path.read_bytes()) if path.is_file() else None
            self.chunks[cx, cz] = read_chunk(self.regions[name], cx, cz)[3] if self.regions[name] is not None else None
        return self.chunks[cx, cz]

    def state(self, x, y, z):
        key = x >> 4, y >> 4, z >> 4
        if key not in self.sections:
            root = self.chunk(key[0], key[2])
            found = [s for s in root['sections'] if int(s['Y']) == key[1] and 'block_states' in s] if root is not None else []
            self.sections[key] = decode(found[0]['block_states']) if found else None
        if self.sections[key] is None:
            return AIR
        ids, palette = self.sections[key]
        return str(palette[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]])

    def block_entity(self, x, y, z):
        root = self.chunk(x >> 4, z >> 4)
        for entity in (root.get('block_entities', []) if root is not None else []):
            if int(entity['x']) == x and int(entity['y']) == y and int(entity['z']) == z:
                return entity
        return None


def name(state):
    return state.split('[')[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--rows', type=Path, action='append', required=True)
    parser.add_argument('--extra', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    if a.out.exists():
        raise SystemExit(f'{a.out} is already there')
    world = World(a.world)
    fixtures = json.loads((a.world / FIXTURES).read_text('utf8'))
    fixture_cells = {tuple(c[:3]) for c in fixtures['cells']}

    furniture, report = {}, Counter()
    sources = []
    for path in a.rows:
        data = path.read_bytes()
        sources.append({'rows': path.name, 'md5': hashlib.md5(data).hexdigest()})
        for x, y, z, before, after, *rest in json.loads(data):
            if after == AIR or name(after) == AIR:
                continue
            cell = (x, y, z)
            if world.state(*cell) != after:
                report['row no longer in the world'] += 1
                continue
            if cell in fixture_cells:
                report['row on a fixture-table cell (left out)'] += 1
                continue
            furniture[cell] = after
    passing = {cell: state for cell, state in furniture.items() if 'sign' not in name(state)}
    report['furniture cells'] = len(furniture)

    extra = []
    if a.extra:
        for column in json.loads(a.extra.read_text('utf8'))['columns']:
            found = 0
            for y in range(column['y0'], column['y1'] + 1):
                state = world.state(column['x'], y, column['z'])
                if name(state) != AIR:
                    passing[(column['x'], y, column['z'])] = state
                    found += 1
            extra.append(dict(column, cells=found))
            report['extra cells'] += found

    blocks = sorted({name(s) for s in passing.values()})
    cells = [v for cell in sorted(passing) for v in cell]
    a.out.mkdir(parents=True)
    (a.out / 'street_pass_r64.json').write_text(json.dumps({
        'schema': SCHEMA, 'dimension': DIMENSION, 'sources': sources, 'extra': extra,
        'blocks': blocks, 'count': len(passing), 'cells': cells}, separators=(',', ':')), 'utf8')

    # The fixture table with the furniture added: the city hides it while lowered and shows it before a raise.
    added = []
    for (x, y, z), state in sorted(furniture.items()):
        cell = [x, y, z, state, AIR]
        if 'sign' in name(state):
            entity = world.block_entity(x, y, z)
            if entity is None:
                report['sign without its text (left out of the table)'] += 1
                continue
            cell.append(nbtlib.serialize_tag(entity))
        added.append(cell)
    table = dict(fixtures)
    table['cells'] = fixtures['cells'] + added
    table['street_furniture_r64'] = {'cells': len(added), 'sources': sources,
                                     'note': 'batch 511 street furniture: hidden while the city rests lowered (tools/street_pass_cells.py)'}
    (a.out / FIXTURES).write_text(json.dumps(table, indent=2, ensure_ascii=False), 'utf8')

    # A world lowered with its fixtures hidden gets the furniture taken away now, so that it matches the table.
    state = nbtlib.load(str(a.world / FIXTURE_STATE))['data'] if (a.world / FIXTURE_STATE).is_file() else {}
    hidden = bool(int(state.get('Hidden', 0))) and not str(state.get('Job', ''))
    cover = [[x, y, z, s, AIR] for x, y, z, s, _, *rest in added] if hidden else []
    (a.out / 'cover_rows.json').write_text(json.dumps(cover), 'utf8')

    summary = {'street_pass_cells': len(passing), 'blocks': blocks, 'fixture_table_cells': len(table['cells']),
               'furniture_added_to_table': len(added), 'fixtures_hidden_now': hidden, 'cover_rows': len(cover),
               'by_block': dict(Counter(name(s) for s in passing.values()).most_common()), 'notes': dict(report)}
    (a.out / 'report.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False), 'utf8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
