"""Reconcile authored expansions missing from the inherited R20/R02 road arrays."""
from pathlib import Path
import json,gzip,hashlib
from collections import Counter

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/surface_network'
SOURCES=[(ROOT/'artifacts/world_expansion_r07/port_road/ops.json.gz',{'r07/port_road/paving','r07/port_road/marking'},'r07_port_road'),
    (ROOT/'artifacts/first_battle_world_r10/world_art/interception_avenue/ops.json.gz',{'r10/intercept_avenue/pavement','r10/intercept_avenue/carriageway','r10/intercept_avenue/edge_line','r10/intercept_avenue/road_marking','r10/intercept_avenue/city_connection','r10/intercept_avenue/pedestrian_crossing'},'r10_interception_avenue'),
    (ROOT/'artifacts/world_expansion_r07/base_architecture/ops.json.gz',{'r07/base/main_road'},'r07_un_main_road')]

def main():
    columns={};sources=[]
    for path,owners,identity in SOURCES:
        with gzip.open(path,'rt',encoding='utf8') as stream:ops=json.load(stream)
        selected=[]
        for op in ops:
            if op['owner'] not in owners or op['state'].partition('[')[0] in {'minecraft:air','minecraft:gray_concrete'} and op['box'][1]!=op['box'][4]:continue
            x0,y,z0,x1,Y,z1=op['box']
            if y!=Y or op['state']=='minecraft:air':continue
            h2=2*y+(1 if 'type=bottom' in op['state'] else 2)
            name=op['state'].partition('[')[0]
            carriage=name in {'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:polished_blackstone_slab','projectseele:road_asphalt_slab','projectseele:road_marking_slab'} or identity=='r07_un_main_road'
            for x in range(x0,x1+1):
                for z in range(z0,z1+1):columns[x,z]=dict(pos=[x,z],height2=h2,carriage=carriage,source_id=identity,source_owner=op['owner'])
            selected.append(op['owner'])
        sources.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_id=identity,selected_op_count=len(selected)))
    records=list(columns.values());report=dict(columns=records,sources=sources,world_written=False,authority_only=True,quality_passed=False,
        ownership_transfers=[dict(id='r21_nerv_airport_over_old_road',bounds=[350,-177,1350,86],old_nominal_feet=81,new_operational_datum=73,
            source='tools/build_nerv_airport_r21.py / exact deployed nerv_un_airports',scope='Aircraft apron, terminal and passenger gallery have their own owner/clearance QA; do not restore superseded streets through them')],
        interpretation='These are explicit authored road surfaces outside the inherited masks. They enlarge the denominator without conferring native/collision/visual passes; full actual readback is mandatory.')
    OUT.mkdir(exist_ok=True);(OUT/'road_authority_additions.json').write_text(json.dumps(report,ensure_ascii=False),'utf8');print('road expansion columns',len(records),dict(Counter(r['source_id'] for r in records)),flush=True)

if __name__=='__main__':main()
