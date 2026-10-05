"""Read original low-rise component domains/endpoints only; never write a world."""
from pathlib import Path
from collections import Counter
import gzip
import json
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / 'artifacts/rebuild_r48/construction/SEELE_R48_WORLD'
DATA = WORLD / 'dimensions/projectseele/geofront/data'
OUT = ROOT / 'artifacts/rebuild_r48/city/c03_lowrise_group'


def unpack(value):
    value = int(value) & ((1 << 64) - 1)
    def signed(v, bits):
        return v - (1 << bits) if v & (1 << (bits - 1)) else v
    return [signed(value >> 38, 26), signed(value & 4095, 12), signed((value >> 12) & 67108863, 26)]


def main():
    topology = nbtlib.load(DATA / 'projectseele_city_rigid_topology_r45_8246338109520.dat')['data']
    towers = []
    for i, tag in enumerate(topology['Towers']):
        c = unpack(tag['Centre'])
        towers.append(dict(index=i, kind=str(tag['Kind']), centre=c, height=int(tag['Height']),
                           retracted_y=int(tag['RetractedBaseY']), footprint={k: int(v) for k, v in tag['Footprint'].items()}))
    components = [dict(id=f'legacy_launch_control_{x}_{z}', centre=[x, 80, z],
                       xz=[x-7, z-7, x+7, z+7], height=26, source='ThirdTokyoSurfaceBuilder.buildLaunchControlBlock')
                  for x in (-10, 70) for z in (180, 260)]
    components += [dict(id='legacy_recovery_room_and_two_pressure_corridors', centre=[30, 80, 190],
                        xz=[13, 158, 46, 201], height=8, source='Tokyo3RecoveryConsole.build')]
    components += [dict(id=f'legacy_substation_{x}_{z}', centre=[x, 80, z],
                        xz=[x-12, z-12, x+12, z+12], height=6, source='ThirdTokyoSurfaceBuilder.buildSubstation')
                   for x, z in ((30, 140), (110, 220))]
    # Old whole-city 312 translation and current real generated endpoints.
    # Read the interval of current *base* endpoints plus the complete original component height.
    bases = [t['retracted_y'] for t in towers if t['kind'] == 'generated']
    windows = [('original_surface', 80, 80), ('legacy_312_below_surface', -232, -232),
               ('retired_s22_surface', 68, 68), ('retired_s22_312_below_surface', -244, -244),
               ('current_generated_endpoint_interval', min(bases), 19)]
    w = MeasuredWorld(WORLD)
    for c in components:
        x, z, X, Z = c['xz']
        for _, a, b in windows:
            w.box((x, a, z), (X, b+c['height'], Z))
    w.load()
    OUT.mkdir(parents=True, exist_ok=True)
    result = dict(schema='projectseele.r48.c03-lowrise-component-domains.v1', source_world=str(WORLD),
                  world_written=False, region_read_scope='7 explicit source-component footprints; 3 vertical endpoint domains',
                  selected_chunks=[list(k) for k in sorted(w.selected)],
                  selected_sections=sum(len(v) for v in w.selected.values()),
                  chunk_statuses={f'{x},{z}': v for (x, z), v in w.status.items()},
                  topology=str(DATA / 'projectseele_city_rigid_topology_r45_8246338109520.dat'),
                  topology_towers=towers, minimum_registered_height=min(t['height'] for t in towers),
                  generated_endpoint_base_range=[min(bases), max(bases)], components=[])
    tags = dict(iter_block_entities(WORLD, 'projectseele:geofront',
                                   (-18, min(-232, min(bases)), 128), (122, 106, 267),
                                   selected_chunks=set(w.selected)))
    full_be = []
    for c in components:
        x, z, X, Z = c['xz']; records = []
        for name, a, b in windows:
            counts = Counter(); by_y = Counter(); missing = 0; nonair = 0; be = []
            path = OUT / f"{c['id']}_{name}_nonair_preimage.jsonl.gz"
            with gzip.open(path, 'wt', encoding='utf8') as handle:
                for yy in range(a, b+c['height']+1):
                    for zz in range(z, Z+1):
                        for xx in range(x, X+1):
                            state = w.get(xx, yy, zz)
                            if state is None:
                                missing += 1; continue
                            if state.partition('[')[0] in AIR:
                                continue
                            nonair += 1; counts[state] += 1; by_y[yy] += 1
                            row = dict(pos=[xx, yy, zz], state=state)
                            if (xx, yy, zz) in tags:
                                row['full_original_nbt'] = tags[xx, yy, zz].snbt()
                                be.append(row); full_be.append(row)
                            handle.write(json.dumps(row, ensure_ascii=False)+'\n')
            records.append(dict(domain=name, box=[x, a, z, X, b+c['height'], Z],
                                nonair=nonair, unknown=missing, block_entities=len(be),
                                by_y={str(y): v for y, v in sorted(by_y.items())},
                                full_state_census=dict(counts), full_nonair_preimage=str(path)))
        c['endpoint_domain_reads'] = records
        c['declared_tower_owners_overlapping_xz'] = [t['index'] for t in towers
            if t['centre'][0]+t['footprint']['MaxX'] >= x and t['centre'][0]+t['footprint']['MinX'] <= X
            and t['centre'][2]+t['footprint']['MaxZ'] >= z and t['centre'][2]+t['footprint']['MinZ'] <= Z]
        result['components'].append(c)
    result['full_original_block_entity_nbt'] = full_be
    (OUT / 'readback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(dict(selected_chunks=len(w.selected), selected_sections=result['selected_sections'],
                          minimum_registered_height=result['minimum_registered_height'],
                          base_range=result['generated_endpoint_base_range'],
                          components=[dict(id=c['id'], owners=c['declared_tower_owners_overlapping_xz'],
                                           counts=[(r['domain'],r['nonair'],r['unknown'],r['block_entities'])
                                                   for r in c['endpoint_domain_reads']]) for c in result['components']]), indent=2))


if __name__ == '__main__':
    main()
