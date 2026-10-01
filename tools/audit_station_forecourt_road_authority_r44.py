"""Recover whole source-authored station forecourts omitted from road-only masks."""
from pathlib import Path
from collections import Counter
import argparse,gzip,hashlib,json,math
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
ART=ROOT/'artifacts/rebuild_r44';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
    source=ROOT/'artifacts/access_r22/transit/civil/two_line_stations_and_viaducts/ops.json.gz'
    contract=ROOT/'artifacts/access_r22/transit/civil/station_contract.json'
    desired={'3659484649089170800','-3388587481325067738','3559976582378878399'}
    stations=json.loads(contract.read_text('utf8'))['stations']
    with gzip.open(source,'rt',encoding='utf8') as f:ops=json.load(f)
    selected=[]
    for pid in sorted(desired):
        s=next(s for s in stations if any('/'+pid+'/' in w['id'] for w in s['walks']))
        candidates=[o for o in ops if o['owner']=='r22/station/'+pid and o['box'][1]==o['box'][4]==s['ground'] and o['state']=='minecraft:smooth_stone']
        assert len(candidates)==1,(pid,len(candidates));selected.append((pid,s,candidates[0]))
    w=MeasuredWorld(WORLD)
    for pid,s,o in selected:
        x,y,z,X,Y,Z=o['box'];w.box((x,y-1,z),(X,y+3,Z))
    w.load();shapes={canonical_state(k):v for k,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    columns=[];records=[]
    for pid,s,o in selected:
        x,y,z,X,Y,Z=o['box'];tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x,y-1,z),(X,y+3,Z),selected_chunks=set(w.selected)))
        floor_states=Counter();issues=[];clear=0
        for xx in range(x,X+1):
            for zz in range(z,Z+1):
                state=w.get(xx,y,zz);floor_states[str(state)]+=1;bs=shapes.get(state)
                floor=bs is not None and any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(b[4]-1)<.001 for b in bs)
                blocked=[]
                for yy in (y+1,y+2):
                    st=w.get(xx,yy,zz);boxes=[] if st in AIR else shapes.get(st)
                    if boxes is None or any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and yy+b[1]<y+2.8 and yy+b[4]>y+1.001 for b in boxes):blocked.append(dict(pos=[xx,yy,zz],state=st,unknown_shape=boxes is None))
                if floor and not blocked:clear+=1
                else:issues.append(dict(pos=[xx,y+1,zz],source_floor_present=floor,blocking_or_unknown=blocked,owner='Current station equipment/full floor state must remain in complete station QA, not excluded as a road pass'))
                columns.append(dict(pos=[xx,zz],height2=2*(y+1),native_feet=y+1,carriage=False,source_id='r22/public_station_forecourt/'+pid,
                    source_owner=o['owner'],current_native_source_floor=floor,current_clear_player=not blocked))
        records.append(dict(platform=pid,station=s['station'],whole_original_positive_floor_op=o,columns=(X-x+1)*(Z-z+1),
            actual_floor_states=dict(floor_states),native_static_clear_columns=clear,occupied_or_unknown_columns=issues,
            full_nbt=[dict(pos=q,snbt=t.snbt()) for q,t in tags.items()],existing_actual_street_entrances=[q for q in s['walks'] if '/ground_access_' in q['id']],
            road_mask_reconciliation='Whole original public plinth supplements inherited carriageway masks. Historical road islands within this plinth belong to the station ground component; they are not permission to create roads through equipment or count current clearance as native operation PASS.'))
    a.output.mkdir(parents=True)
    result=dict(columns=columns,sources=[dict(path=str(p),sha256=sha(p)) for p in [source,contract]],objects=records,world_written=False,
        quality_passed=False,native_operation_passed=False,visual_passed=False,denominator_only=True)
    (a.output/'road_authority.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Whole sourced forecourts',len(records),'columns',len(columns),'clear',sum(r['native_static_clear_columns'] for r in records),'unexcluded equipment/unknown',sum(len(r['occupied_or_unknown_columns']) for r in records))


if __name__=='__main__':main()
