"""Separate retired R03 plot strips from actual occupied building envelopes."""
from pathlib import Path
import json,hashlib,copy
from collections import Counter
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/city_buildings'

def main():
    source=ROOT/'artifacts/repair_r43/facility_catalogue/authored_ownership.json';owners=json.loads(source.read_text('utf8'))
    receipt=json.loads((WORLD/'regional_quality_r03_structures.json').read_text('utf8'));records=[]
    assert receipt['receipt']['verified']
    for b in owners['buildings']:
        if b['id'] not in receipt['cropped']:continue
        edge=receipt['cropped'][b['id']];lo,hi=b['planned_bounds'];w=MeasuredWorld(WORLD);w.box(lo,hi);w.load()
        strip=[(x,lo[1],z) for x in range(edge+1,hi[0]+1) for z in range(lo[2],hi[2]+1)]
        ground_states=Counter(w.block(q) for q in strip)
        assert all(w.block(q).partition('[')[0] in {'minecraft:grass_block','minecraft:smooth_stone'} for q in strip)
        assert all(w.get(x,lo[1]+1,z) in AIR and w.get(x,lo[1]+2,z) in AIR for x,_,z in strip)
        facade=[]
        for feet in b['planned_floor_feet']:
            row=[w.get(edge,feet,z) for z in range(lo[2],hi[2]+1)]
            assert all(s is not None and s not in AIR for s in row)
            facade.append(dict(feet_y=feet,states=sorted(set(row)),cells=len(row)))
        historic=copy.deepcopy(b['planned_bounds']);b['historic_plot_bounds']=historic;b['planned_bounds'][1][0]=edge
        b['actual_building_bounds']=copy.deepcopy(b['planned_bounds']);b['authority_revision']='R44 actual envelope from R03 retired-wing receipt plus complete current east facade and exterior grass measurement'
        records.append(dict(id=b['id'],historic_plot_bounds=historic,actual_building_bounds=b['planned_bounds'],
            classified_exterior_ground_cells=len(strip),ground_states=dict(ground_states),facades=facade,construction_required=False,
            interpretation='R43 incorrectly classified retired east-wing grass/old exterior paving outside the actual closed X152 facade as occupied first-storey floor'))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'actual_authored_ownership.json').write_text(json.dumps(owners,ensure_ascii=False,indent=2),'utf8')
    (OUT/'retired_plot_strips.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),historical_receipt=receipt,objects=records,world_changed=False),ensure_ascii=False,indent=2),'utf8')
    print('Verified actual envelopes',len(records),'exterior ground cells',sum(r['classified_exterior_ground_cells'] for r in records),flush=True)

if __name__=='__main__':main()
