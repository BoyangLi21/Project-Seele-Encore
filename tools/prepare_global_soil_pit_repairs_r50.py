"""Finite repairs for measured single-column deep soil pockets across the save.

Only existing 5x5 measured natural frames with an AIR-only centre above the old
soil, no BE, no registered vehicle/traffic/structure sweep are admitted. Actual
water, foliage, caves below the old top and large caldera relief are retained.
This emits reversible candidates and complete finite source; never writes world.
"""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from audit_surface_objects_r50 import SOIL,R50_KEEP
from prepare_facilities_r48 import Author

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text('utf8'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);args=ap.parse_args();world=args.world.resolve();base=ROOT/'artifacts/rebuild_r49/surface_r50';out=base/'global_depressions/isolated_soil_pit_candidates';out.mkdir(parents=True,exist_ok=True)
    audit=load(base/'global_depressions/actual_global_depression_readback.json');rows=[r for r in audit['rows']if r['status'].startswith('ACTUAL_ISOLATED_NATURAL')];inventory=load(base/'surface_object_inventory.json')['objects'];native=load(world/'native_transit_r28.json')['curves'];w=MeasuredWorld(world);prepared=[]
    for r in rows:
        x,y,z=r['seed'];g=r['actual_soil_height_5x5'];old=g[2][2];target=min(g[1][2],g[3][2],g[2][1],g[2][3])-1;low=max(0,min(min(row)for row in g)-4);high=min(319,max(max(row)for row in r['actual_nonleaf_solid_top_5x5'])+4);w.box((x-2,low,z-2),(x+2,high,z+2));prepared.append((r,x,z,old,target,low,high))
    w.load();assert set(w.status.values())=={'full'}
    bes=dict(iter_block_entities(world,w.dimension,(min(x-2 for r,x,z,o,t,l,h in prepared),0,min(z-2 for r,x,z,o,t,l,h in prepared)),(max(x+2 for r,x,z,o,t,l,h in prepared),319,max(z+2 for r,x,z,o,t,l,h in prepared)),selected_chunks=set(w.selected)))
    def nearest_curve(points,x,z):
        nearest=1e30;closest_y=None
        for a,b in zip(points,points[1:]):
            dx=b[0]-a[0];dz=b[2]-a[2];length=dx*dx+dz*dz;t=0 if length==0 else min(1,max(0,((x-a[0])*dx+(z-a[2])*dz)/length));px=a[0]+t*dx;pz=a[2]+t*dz;distance=math.hypot(x-px,z-pz)
            if distance<nearest:nearest=distance;closest_y=a[1]+t*(b[1]-a[1])
        return nearest,closest_y
    decision=[];desired={};source={};admitted=[]
    for r,x,z,old,target,low,high in prepared:
        reasons=[];frame=(x-2,low,z-2,x+2,high,z+2)
        for name,box in R50_KEEP:
            if name in{'city100_dynamic_reserve','launch_surface_sweeps'}:continue
            if frame[0]<=box[3]and frame[3]>=box[0]and frame[2]<=box[5]and frame[5]>=box[2]and frame[1]<=box[4]and frame[4]>=box[1]:reasons.append(name)
        if math.hypot(x-1630,z-685)<=122:reasons.append('new_marine_basin_full_sweep')
        for owner in inventory:
            if owner.get('position'):
                p=owner['position']
                if math.hypot(x-p[0],z-p[2])<=32 and low<=p[1]+24 and high>=p[1]-24:reasons.append('original_equipment/'+owner['id'])
        for curve in native:
            distance,yy=nearest_curve(curve['points'],x+.5,z+.5)
            if yy is not None and distance<=10 and low<=yy+12 and high>=yy-12:reasons.append('current_native_'+curve['mode']+'/'+str(curve['id']))
        if any(x-2<=q[0]<=x+2 and z-2<=q[2]<=z+2 and low<=q[1]<=high for q in bes):reasons.append('current_full_BE')
        altered=[dict(pos=[x,yy,z],state=w.get(x,yy,z))for yy in range(old+1,target+1)if w.get(x,yy,z).partition('[')[0]not in AIR]
        if altered:reasons.append('actual_water_plant_or_foreign_body_in_fill_column')
        if any(w.get(x,yy,z).partition('[')[0]not in SOIL for yy in range(max(0,old-3),old+1)):reasons.append('old_topsoil_not_complete_natural_support')
        result=dict(id=r['id'],seed=r['seed'],bounds=[list(frame[:3]),list(frame[3:])],old_soil_y=old,target_soil_y=target,original_four_neighbor_drop=r['min_four_neighbor_soil_drop'],blocks_above_old_soil=altered,protected_reasons=reasons,status='FINITE_SINGLE_COLUMN_FOOT_PIT_CANDIDATE'if not reasons else'CURRENT_WATER_PLANT_OR_TRAFFIC_CONTEXT_RETAINED',historical_generator_bug_proven=False)
        decision.append(result)
        if reasons:continue
        for yy in range(max(0,old-3),target+1):
            q=x,yy,z;after='minecraft:grass_block[snowy=false]'if yy==target else'minecraft:dirt'if yy>=target-3 else'minecraft:stone'
            desired[q]=(after,'Close measured one-column deep foot trap only to lowest four-neighbor soil minus one; preserve underlying geology and all neighboring relief.',None)
        for xx in range(x-2,x+3):
            for zz in range(z-2,z+3):
                for yy in range(low,high+1):
                    q=xx,yy,zz;current=w.get(*q);tag=bes.get(q);nbt=None if tag is None else tag.snbt();value=desired.get(q);after=current if value is None else value[0];after_nbt=nbt if value is None else None
                    item=dict(pos=list(q),before=current,after=after,before_nbt=nbt,after_nbt=after_nbt,owner='M40_global_single_column_soil_pits',reason='Complete actual five-by-five soil/air boundary and centre terminal state; protects finite repair from later source replay.',source_only=current==after and nbt==after_nbt)
                    if q in source:assert source[q]['before']==current and source[q]['before_nbt']==nbt,('Actual overlapping pit frames differ',q)
                    source[q]=item
        admitted.append(result)
    author=Author(world,out);author.s={q:w.get(*q)for q in desired};author.t={q:bes[q]for q in desired if q in bes};author.emit('M40_global_single_column_soil_pits',desired,admitted)
    # Overlay final centre changes across overlapping measured source frames once.
    for q,item in source.items():
        if q in desired:item['after']=desired[q][0];item['after_nbt']=None;item['source_only']=item['before']==item['after']and item['before_nbt']is None
    with gzip.open(out/'complete_generation_source.jsonl.gz','wt',encoding='utf8')as f:
        for q in sorted(source):f.write(json.dumps(source[q],ensure_ascii=False)+'\n')
    author.all=source;author.recipe();(out/'metadata_patch.json').write_text(json.dumps(dict(schema=50,operations=[],world_written=False),indent=2),'utf8')
    report=dict(world=str(world),measured_natural_pocket_candidates=len(rows),admitted_finite_pit_components=len(admitted),decisions=decision,counts=dict(Counter(r['status']for r in decision)),physical_change_cells=author.components[0]['rows'],complete_generation_source_cells=len(source),world_written=False,native_verified=False,visual_acceptance=False,design='Bounded game-terrain safety grading for isolated one-column pockets; does not assert native noise corruption or original-TV hole dimensions. Large ridges, cliffs, water and cave volume below each original soil surface remain.')
    (out/'decision_and_source_contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');contract=out/'M40_global_single_column_soil_pits/contract.json';d=load(contract);d.update(schema='projectseele.r50.global-soil-pocket-candidate.v1',authorization='User R50 item 40 reasonable full surface anomaly repair; Root sole world writer.');contract.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:report[k]for k in('admitted_finite_pit_components','counts','physical_change_cells','complete_generation_source_cells','world_written')}),flush=True)

if __name__=='__main__':main()
