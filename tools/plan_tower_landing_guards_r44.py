"""Exact complete-tower landing fix, preserving actual controls and full user NBT."""
from pathlib import Path
from collections import Counter
import json,gzip,hashlib,shutil
from measure_central_tower_ports_r44 import specs
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/central_towers/landing_guard_repair'
BAR='minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'

def main():
    OUT.mkdir(parents=True,exist_ok=True);failure=OUT.parent/'native_quality/rooms_underground.json.failed.json';frozen=OUT/'rooms_underground.initial_failed.json'
    if failure.exists() and not frozen.exists():shutil.copy2(failure,frozen)
    original=json.loads(frozen.read_text('utf8'));assert len(original['objects'])==93
    current_author=json.loads((OUT.parent/'author_20260930_1540/audit.json').read_text('utf8'));assert current_author['depth']==312
    lots=list(specs());changes={};roles={};records=[];w=MeasuredWorld(WORLD)
    for index,(x,z,height,half) in enumerate(lots):
        native=current_author['buildings'][index];assert (native['x'],native['z'],native['height'])==(x,z,height)
        base=native['base'];left,right,north,south=-half+1,-half+9,-half+2,-half+12;last=(height-3)//6*6;mask={}
        for floor in range(6,last+1,6):
            incomingNorth=((floor//6-1)%2)==0;incoming=-half+(3 if incomingNorth else 7);lip=south-2 if incomingNorth else north+3
            for xx in [left,-half+5]:
                for zz in range(north+3,south-1):mask[x+xx,base+floor,z+zz]=('minecraft:smooth_stone','Support the original longitudinal stairwell railing with its complete floor bearing')
            if floor==last:
                for xx in range(left,right):
                    if abs(xx-incoming)<=1:continue
                    for zz in range(north+3,south-1):mask[x+xx,base+floor,z+zz]=('minecraft:smooth_stone','Finish the unused stair bay at the highest inhabited floor; retain the real incoming descent')
            for xx in range(incoming-1,incoming+2):
                mask[x+xx,base+floor,z+lip]=('minecraft:smooth_stone','Found the transverse closed-end landing lip above the lower flight headroom')
                for y in [base+floor+1,base+floor+2]:mask[x+xx,y,z+lip]=(BAR,'Close the deep wrong-end stairwell lip; the opposite declared descending flight stays open')
        for q,value in mask.items():
            if q in changes and changes[q]!=value:raise RuntimeError('Tower ownership overlap')
            changes[q]=value;roles[q]=index;w.around(q,0)
        records.append(dict(tower=index,base=base,last_floor=last,positive_mask_cells=len(mask),declared_lobby_seed=[x-half+11,base+1,z],immutable_core_touched=False))
    w.load();points=list(changes);lo=tuple(min(q[d] for q in points) for d in range(3));hi=tuple(max(q[d] for q in points) for d in range(3));tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    rows=[];held=[]
    for q,(after,reason) in sorted(changes.items()):
        old=w.block(q)
        if old==after:continue
        if old not in AIR or q in tags:
            held.append(dict(tower=roles[q],pos=q,before=old,full_nbt=tags[q].snbt() if q in tags else None,desired=after,reason='Preserve a user or non-template state; do not force the known AIR landing patch'));continue
        rows.append(dict(pos=q,before=old,after=after,before_nbt=None,after_nbt=None,owner=f'r44/tokyo3_retractable/{roles[q]}',reason=reason))
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in rows:
                value=dict(row)
                if inverse:value['before'],value['after']=row['after'],row['before']
                stream.write(json.dumps(value)+'\n')
    count=Counter(r['kind'] for r in original['failures']);flights=sum(len(o['native_stair_physics']) for o in original['objects']);floors=sum(len(o['complete_floors']) for o in original['objects'])
    report=dict(world=str(WORLD),towers=len(lots),floor_denominator=floors,three_width_flight_denominator=flights,changed_cells=len(rows),held=held,world_written=False,
        initial_failed_sha256=hashlib.sha256(frozen.read_bytes()).hexdigest(),original_failure_kinds=dict(count),
        failure_classification=[dict(kind='MISSING_FLOOR_LOBBY / ISOLATED_FLOOR_CELLS',cause='The arbitrary centre seed was a declared longitudinal iron railing on 713 floors. All floors with a valid original seed connected; move only the test seed to the declared lobby aisle, preserve rails and fixed controls.'),
            dict(kind='NATIVE_WALK_FAILED',cases=flights,cause='All upward flights passed; all downward attempts stopped horizontal movement before gravity settled. Keep the original .32 distance tolerance and perform native Vanilla travel with zero input at the actual reached position.'),
            dict(kind='UNGUARDED_LANDING_VOID',raw_cases=count['UNGUARDED_LANDING_VOID'],declared_descending_edges=flights,true_wrong_lips=flights,true_unused_top_bay_edges=93*6,
                cause='Each upper floor has a deep wrong-end entrance to its incoming bay; the unused bay on the last floor has two open lips. Add supported transverse guards and finish only unused top bay floor. Declared native descent ports remain open and require the native bidirectional flight proof.')],
        records=records,native_rerun_required=True,quality_passed=False,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/main/java/com/projectseele/world/TvTokyo3Architecture.java',ROOT/'src/main/java/com/projectseele/world/Tokyo3BuildingQualityR44.java']})
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print({k:v for k,v in report.items() if k in ['towers','floor_denominator','three_width_flight_denominator','changed_cells']},'held',len(held),flush=True)

if __name__=='__main__':main()
