"""Compare the complete original registered low-rise cargo at both endpoints, read only."""
from pathlib import Path
from collections import Counter
import gzip
import json
import uuid
import nbtlib
from inspect_c03_lowrise_r48 import WORLD, DATA, OUT, unpack
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities


def state_text(tag):
    value = str(tag['Name'])
    props = tag.get('Properties', {})
    return value + ('['+','.join(f'{k}={props[k]}' for k in sorted(props))+']' if props else '')


def nbt_uuid(values):
    return str(uuid.UUID(int=sum((int(v) & 0xffffffff) << (32*(3-i)) for i, v in enumerate(values))))


def main():
    topology = nbtlib.load(DATA/'projectseele_city_rigid_topology_r45_8246338109520.dat')['data']
    ledger = nbtlib.load(DATA/'projectseele_city_rigid_control_r45_8246338109520.dat')['data']
    journey = nbt_uuid(ledger['Journey'])
    plans = []
    for i, tower in enumerate(topology['Towers']):
        if int(tower['Height']) > 36:
            continue
        path = DATA/'city_rigid_journal_r45'/journey/f'{i}.dat'
        plan = nbtlib.load(path); centre = unpack(plan['Centre'])
        plans.append((i, tower, plan, centre, path))
    w = MeasuredWorld(WORLD)
    for i, tower, plan, c, _ in plans:
        a, b, d, e = (int(plan[k]) for k in ('MinX','MaxX','MinZ','MaxZ'))
        for base in (int(plan['TargetY']), int(plan['RetractedY']), c[1]-312):
            w.box((c[0]+a, base, c[2]+d), (c[0]+b, base+int(plan['Height'])+4, c[2]+e))
    w.load(); OUT.mkdir(parents=True, exist_ok=True)
    result = dict(schema='projectseele.r48.c03-registered-lowrise-readback.v1', source_world=str(WORLD),
                  world_written=False, selected_chunks=len(w.selected), selected_sections=sum(map(len,w.selected.values())),
                  ledger=dict(phase=str(ledger['Phase']),depth=int(ledger['Depth']),target=int(ledger['Target']),
                              queued=int(ledger['Queued']),fault=str(ledger['Fault']),queue_fault=str(ledger['QueueFault']),
                              saved_plans=int(ledger['SavedPlans']),created=int(ledger['Created']),journey=journey),
                  height_selection='all 96 original registered towers with Height<=36', records=[])
    for i, tower, plan, c, path in plans:
        row = dict(index=i,centre=c,height=int(plan['Height']),owner=nbt_uuid(plan['Owner']),
                   journal=str(path),source_y=int(plan['SourceY']),target_y=int(plan['TargetY']),
                   retracted_y=int(plan['RetractedY']),original_cells=len(plan['Cells']),
                   full_original_block_entity_nbt=[dict(local_pos=unpack(cell['Pos']),full_nbt=cell['Data'].snbt())
                                                   for cell in plan['Cells'] if 'Data' in cell],endpoints=[])
        for label, base in [('committed_target',int(plan['TargetY'])),('registered_underground',int(plan['RetractedY'])),
                            ('legacy_312_below_surface',c[1]-312)]:
            correct = 0; missing = 0; expected_nonair = 0; correct_nonair = 0; mismatches = []
            for cell in plan['Cells']:
                x,y,z = unpack(cell['Pos']); q = [c[0]+x, base+y, c[2]+z]
                actual = w.block(q); expected = state_text(cell['State'])
                nonair = str(cell['State']['Name']) not in AIR
                expected_nonair += nonair
                if actual is None: missing += 1
                if actual == expected:
                    correct += 1; correct_nonair += nonair
                else: mismatches.append(dict(pos=q,expected=expected,actual=actual))
            dest = OUT/f'owner_{i}_{label}_state_differences.jsonl.gz'
            with gzip.open(dest,'wt',encoding='utf8') as handle:
                for diff in mismatches: handle.write(json.dumps(diff)+'\n')
            row['endpoints'].append(dict(domain=label,base_y=base,exact_state_equal=correct,
                                         expected_cells=len(plan['Cells']),expected_nonair=expected_nonair,
                                         equal_nonair=correct_nonair,unknown=missing,differences=len(mismatches),full_differences=str(dest)))
        result['records'].append(row)
    (OUT/'registered_lowrise_readback.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(ledger=result['ledger'],selection=len(plans),selected_chunks=len(w.selected),
                          target_state_complete=all(r['endpoints'][0]['differences']==0 for r in result['records']),
                          records=[dict(index=r['index'],centre=r['centre'],height=r['height'],
                                        counts=[(e['domain'],e['equal_nonair'],e['expected_nonair'],e['unknown'],e['differences'])
                                                for e in r['endpoints']]) for r in result['records']]),indent=2))


if __name__=='__main__': main()
