"""Restore exact original crossing roads after v11, including their transverse traffic."""
from pathlib import Path
import argparse,gzip,json,math,hashlib
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from plan_hakone_tokyo_link_r44 import half_width,GUARD

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
BASE=ROOT/'artifacts/rebuild_r44/surface_network/hakone_tokyo_link_ready_v11'

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
    arrays=np.load(ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz')
    oldprofiles={tuple(map(int,q)):(float(f),int(g)) for q,f,g in zip(arrays['coordinates'],arrays['actual_feet'],arrays['flags'])}
    sections={s['x']:s for s in json.loads((BASE/'audit.json').read_text('utf8'))['sections']}
    columns=[]
    for x in range(-1138,-747):
        for side in (-1,1):
            z=sections[x]['z']+(half_width(x)+1)*side;profile=oldprofiles.get((x,z))
            if profile and profile[1]&7==7 and abs(profile[0]-sections[x]['height2']/2)<=.501:columns.append((x,z))
    with gzip.open(BASE/'forward.jsonl.gz','rt',encoding='utf8') as stream:source={tuple(r['pos']):r for r in map(json.loads,stream)}
    selected={q:r for q,r in source.items() if q[::2] in columns and (r['after']==GUARD or r['after']=='minecraft:light_gray_concrete')}
    w=MeasuredWorld(WORLD)
    for x,y,z in selected:w.around((x,y,z),1)
    w.load();tags={}
    for q in selected:
        for at,nbt in iter_block_entities(WORLD,'projectseele:geofront',q,q,selected_chunks={(q[0]//16,q[2]//16)}):tags[at]=nbt
    rows=[];held=[]
    for q,r in sorted(selected.items()):
        if w.block(q)!=r['after'] or q in tags:held.append(dict(pos=q,state=w.block(q),nbt=tags[q].snbt() if q in tags else None));continue
        rows.append(dict(pos=q,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'],owner='r44/hakone_tokyo_junction_restore',reason='Existing exact public crossing roadway has priority over the new longitudinal bridge roadside barrier; preserve both traffic directions'))
    a.output.mkdir(parents=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for row in rows:
                value=dict(row)
                if inverse:value['before'],value['after']=row['after'],row['before'];value['before_nbt'],value['after_nbt']=row['after_nbt'],row['before_nbt']
                f.write(json.dumps(value)+'\n')
    cases=[]
    for x in range(-764,-755):
        for direction in ['north','south']:
            path=[[x+.5,97,z+.5] for z in range(290,327)]
            cases.append(dict(id=f'r44/tokyo_west_original_cross_street/x{x}/{direction}',path=path if direction=='south' else path[::-1],required_vehicle_height=6,native_passed=False))
    (a.output/'native_original_crossing_cases.json').write_text(json.dumps(cases),'utf8')
    audit=dict(world=str(WORLD),source=str(BASE),source_forward_sha256=hashlib.sha256((BASE/'forward.jsonl.gz').read_bytes()).hexdigest(),old_public_columns=columns,
        changed_cells=len(rows),held=held,ready=not held,world_written=False,native_transverse_vehicle_passed=False,visual_passed=False,
        initial_detection_gap='Original v11 verified all new-road longitudinal columns and bends, but did not include the transverse existing Tokyo street. New guard rows blocked its original N/S traffic.',
        template_fixed='Future author skips all exact existing public roadway columns at the guard/coping/lamp positions when their real floor is within half a block of the new road datum.')
    (a.output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf8');print('Junctions',len(columns),'exact cells',len(rows),'held',len(held),'ready',not held,flush=True)

if __name__=='__main__':main()
