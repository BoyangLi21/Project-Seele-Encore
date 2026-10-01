"""Retire complete R23 service cabinets outside real public station landings.

Ownership comes from the exact original station-detail generator and its
station contract. Saved collision-free furniture tops are not public floors.
This writes candidates only; root alone applies the exact reversible changes.
"""
from pathlib import Path
import copy, hashlib, json
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / 'run/saves/SEELE_FIELD_R44_REVIEW'
ART = ROOT / 'artifacts/rebuild_r44/facility_transit_r44'
OUT = ART / 'station_service_components_v1'


def main():
    assert not OUT.exists(), 'Do not overwrite frozen candidates'
    original = ROOT / 'artifacts/access_r22/transit/civil/station_contract.json'
    records = json.loads(original.read_text('utf8'))['stations']
    audit = json.loads((ART / 'station_signs_current_20261001/full_sign_audit.json').read_text('utf8'))
    bad = {tuple(b['position']): b for b in audit['boards'] if b['reader'] is None}
    w = MeasuredWorld(WORLD)
    components = []
    for r in records:
        x, y, z = r['center']; h = r['half']
        def at(u, yy, side):
            return (x+u, yy, z+side) if r['horizontal'] else (x+side, yy, z+u)
        for side in (-1, 1):
            u = -h+4
            plaque = at(u+1, y+3, side*16)
            assert plaque in bad, ('Original retired end no longer in independently measured unreadable set', plaque)
            cells = [at(a, y+1, side*b) for a in range(u, u+4) for b in (15, 16)]
            components.append({'station': r['station'], 'line': r['line'], 'plaque': plaque,
                'whole_cabinet': cells, 'source_offset': [-h+4, y+1, side*15],
                'reason': 'Original end service bay has no supported passenger reading approach; complete cabinet and plaque retired'})
            for q in [plaque, *cells]: w.around(q, 3)
    assert len(components) == 28
    w.load(); v.WORLD, v.OUT = WORLD, OUT
    p, inverse = v.Painter(), v.Painter()
    preserved = {}; retired = []
    for item in components:
        points = [item['plaque'], *item['whole_cabinet']]
        lo = tuple(min(q[i] for q in points)-1 for i in range(3))
        hi = tuple(max(q[i] for q in points)+1 for i in range(3))
        tags = dict(iter_block_entities(WORLD, v.DIM, lo, hi))
        q = item['plaque']; tag = tags.get(q)
        assert tag is not None and str(tag.get('Row0')) == '非常按钮 / 消防箱', (q, tag)
        assert str(tag.get('Station')) == item['station'] and str(tag.get('Row2')) == '出口与换乘 → 楼梯'
        for cell in points:
            state = w.block(cell)
            expected = 'projectseele:nerv_direction_panel' if cell == q else 'projectseele:nerv_storage_panel'
            assert state is not None and state.partition('[')[0] == expected, (cell, state, expected)
            assert cell == q or cell not in tags, ('Other complete device in cabinet', cell)
            p.match((*cell, *cell), state, 'minecraft:air', 'r44/retire_complete_invalid_station_service_end')
            inverse.match((*cell, *cell), 'minecraft:air', state, 'inverse/r44/retired_station_service_end')
        inverse.block_entities[q] = copy.deepcopy(tag)
        retired.append({'position': q, 'snbt': tag.snbt()})
        preserved.update({k: t.snbt() for k, t in tags.items() if k != q})
    # Retained service/waiting-room plaques describe the actual place. Their
    # old generic left/right arrows were not derived from passenger routes.
    labels = []
    for b in audit['boards']:
        q = tuple(b['position'])
        if q in {c['plaque'] for c in components}: continue
        tag = nbtlib.parse_nbt(b['nbt'])
        old = str(tag.get('Row0', ''))
        if old == '非常按钮 / 消防箱': rows = ['消防设备', '请勿遮挡', '紧急情况联系站务']
        elif old == '候车室 / 优先席': rows = ['候车室 / 优先席', '请先下后上', '乘车方向见站台信息牌']
        else: continue
        current = dict(iter_block_entities(WORLD, v.DIM, q, q)).get(q)
        assert current is not None and current.snbt() == tag.snbt()
        new = copy.deepcopy(current)
        for i, text in enumerate(rows): new['Row'+str(i)] = nbtlib.String(text)
        p.update_block_entity(q, b['state'], current, new, 'r44/place_label_without_unmeasured_exit_arrow')
        inverse.update_block_entity(q, b['state'], new, current, 'inverse/r44/original_place_label')
        labels.append({'position': q, 'state': b['state'], 'before': current.snbt(), 'after': new.snbt()})
    OUT.mkdir(parents=True)
    report = {'components': components, 'retired_cells': 28*9, 'retired_complete_be': retired,
        'preserved_nearby_be': [{'position': q, 'snbt': t} for q,t in sorted(preserved.items())],
        'retained_place_labels': labels, 'producer': 'tools/detail_stations_r23.py',
        'producer_sha256': hashlib.sha256((ROOT/'tools/detail_stations_r23.py').read_bytes()).hexdigest(),
        'original_contract_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
        'world_written': False, 'scope': 'Complete failed service-end retirement and exact place labels; station exit/transfer navigation still requires measured route signs',
        'native_pass': False, 'visual_pass': False}
    p.meta.update(report); inverse.meta.update({'complete_inverse': True})
    p.save_plan('retire_whole_invalid_service_ends_and_false_arrows')
    inverse.save_plan('inverse_retired_service_components')
    (OUT/'contract.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print('Complete service-end candidates', len(components), 'cells', report['retired_cells'], 'retained labels', len(labels))


if __name__ == '__main__': main()
