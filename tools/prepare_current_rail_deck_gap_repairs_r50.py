"""Close measured isolated side-bed holes in actual current native TRAIN rails.

Uses the original R20 formation contract (three solid blocks below the rail),
four real concrete bed neighbors, existing rail identity and AIR-only holes.
Never fills the road/geology below a bridge or changes rails/vehicles/clearance.
"""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from prepare_facilities_r48 import Author

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text('utf8'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);args=ap.parse_args();world=args.world.resolve();base=ROOT/'artifacts/rebuild_r49/surface_r50';out=base/'global_depressions/current_rail_deck_gap_candidates';out.mkdir(parents=True,exist_ok=True)
    context=load(base/'global_depressions/deck_gap_current_transit_context.json');actual={r['id']:r for r in load(base/'global_depressions/actual_global_depression_readback.json')['rows']};by_seed={tuple(r['seed']):r for r in actual.values()};rows=[c for c in context if c['nearest_train_distance']<=4.1];assert len(rows)==21
    w=MeasuredWorld(world);prepared=[]
    for c in rows:
        r=by_seed[tuple(c['seed'])];x,y,z=c['seed'];four=r['top_materials'][1:];concrete=[p['pos'][1]for p in four if p['state']=='minecraft:light_gray_concrete']
        current_bed=[yy for yy in concrete if .5<=c['nearest_train_y']-yy<=3.2]
        target=min(current_bed)if current_bed else None;low=0 if target is None else target-5;high=min(319,max(p['pos'][1]for p in four)+5);w.box((x-2,low,z-2),(x+2,high,z+2));prepared.append((c,r,x,z,target,low,high))
    w.load();assert set(w.status.values())=={'full'};bes=dict(iter_block_entities(world,w.dimension,(min(x-2 for c,r,x,z,t,l,h in prepared),0,min(z-2 for c,r,x,z,t,l,h in prepared)),(max(x+2 for c,r,x,z,t,l,h in prepared),319,max(z+2 for c,r,x,z,t,l,h in prepared)),selected_chunks=set(w.selected)))
    desired={};source={};decisions=[];admitted=[]
    for c,r,x,z,target,low,high in prepared:
        reasons=[];concrete=[p for p in r['top_materials'][1:]if p['state']=='minecraft:light_gray_concrete']
        if len(concrete)<3:reasons.append('fewer_than_three_actual_concrete_bed_neighbors')
        if len([p for p in concrete if .5<=c['nearest_train_y']-p['pos'][1]<=3.2])<2:reasons.append('fewer_than_two_neighbors_at_current_native_bed_datum')
        if target is None or target>=c['nearest_train_y']+.15 or c['nearest_train_y']-target>3.2:reasons.append('outside_current_train_underfloor_bed_datum')
        if r['finite_owner_context']:reasons.append('finite_other_owner_requires_full_component_review')
        if any(x-2<=q[0]<=x+2 and z-2<=q[2]<=z+2 and low<=q[1]<=high for q in bes):reasons.append('full_BE_in_actual_frame')
        if target is not None:
            if any(w.get(x,yy,z).partition('[')[0]not in AIR for yy in range(target-2,target+1)):reasons.append('bed_hole_is_not_three_continuous_AIR_cells')
            if any(w.get(x,yy,z)not in AIR and w.get(x,yy,z).partition('[')[0]not in AIR for yy in range(target+1,math.ceil(c['nearest_train_y'])+4)):reasons.append('current_car_body_space_not_AIR')
        decision=dict(id=r['id'],seed=c['seed'],native_current_train_id=c['train_id'],native_axis_distance=c['nearest_train_distance'],native_axis_y=c['nearest_train_y'],target_bed_top_y=target,actual_neighbor_beds=concrete,complete_bounds=[[x-2,low,z-2],[x+2,high,z+2]],reasons=reasons,status='CURRENT_NATIVE_RAIL_ISOLATED_SIDE_BED_GAP_CANDIDATE'if not reasons else'LIVE_OR_FOREIGN_STRUCTURE_RETAINED_PENDING_COMPONENT_DECISION',new_rail_or_vehicle_created=False)
        decisions.append(decision)
        if reasons:continue
        for yy in range(target-2,target+1):desired[x,yy,z]=('minecraft:light_gray_concrete','Restore only original three-thick current native rail side-bed at an unguarded isolated AIR hole; no support/pier removal, no native car-space or lower-road fill.',None)
        for xx in range(x-2,x+3):
            for zz in range(z-2,z+3):
                for yy in range(low,high+1):
                    q=xx,yy,zz;current=w.get(*q);tag=bes.get(q);nbt=None if tag is None else tag.snbt();after=desired[q][0]if q in desired else current
                    source[q]=dict(pos=list(q),before=current,after=after,before_nbt=nbt,after_nbt=None if q in desired else nbt,owner='M40_current_native_rail_deck_gaps',reason='Complete actual five-by-five current bridge bed and car-space frame; exact gap terminal state only, current native identity and surrounding beam/pier/water remain.',source_only=current==after)
        admitted.append(decision)
    author=Author(world,out);author.s={q:w.get(*q)for q in desired};author.t={q:bes[q]for q in desired if q in bes};author.emit('M40_current_native_rail_side_bed_gaps',desired,admitted)
    for q,r in source.items():
        if q in desired:r['after']=desired[q][0];r['after_nbt']=None;r['source_only']=r['before']==r['after']
    with gzip.open(out/'complete_generation_source.jsonl.gz','wt',encoding='utf8')as f:
        for q in sorted(source):f.write(json.dumps(source[q],ensure_ascii=False)+'\n')
    author.all=source;author.recipe();(out/'metadata_patch.json').write_text(json.dumps(dict(schema=50,operations=[],world_written=False),indent=2),'utf8')
    report=dict(world=str(world),actual_current_train_gap_frames=21,admitted_components=len(admitted),decisions=decisions,counts=dict(Counter(r['status']for r in decisions)),physical_cells=author.components[0]['rows'],complete_generation_cells=len(source),original_contract='tools/build_transit_civil_r20.py and tools/finish_native_rail_envelopes_r20.py: existing current native TRAIN formation deck y-3..y-1, seven-wide body; actual four neighboring beds and native axis provide local terminal datum.',no_new_tracks_vehicles_or_inventory=True,world_written=False,native_verified=False,visual_acceptance=False)
    (out/'decision_and_source_contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');contract=out/'M40_current_native_rail_side_bed_gaps/contract.json';d=load(contract);d.update(schema='projectseele.r50.current-rail-bed-gap-candidate.v1',authorization='User R50 item 40 full surface anomaly repair with current transport preservation; Root sole world writer.');contract.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:report[k]for k in('actual_current_train_gap_frames','admitted_components','physical_cells','complete_generation_cells','counts','world_written')}),flush=True)

if __name__=='__main__':main()
