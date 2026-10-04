"""Static saved5 crew vs208 volumes/authored motion; no NPC/world/model writes."""
from __future__ import annotations
import argparse,json,sys,math
from pathlib import Path
sys.dont_write_bytecode=True
import numpy as np,nbtlib
from numpy.polynomial import Polynomial as P
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha
from verify_main_r20 import entities

def intersects(a,b):return all(a[k]<b[k+3]and a[k+3]>b[k]for k in range(3))
def ease(a,b,mid):
    if mid<=a:return P([0])
    if mid>=b:return P([1])
    t=(P([0,1])-a)/(b-a);return t*t*t*(t*(t*6-15)+10)
def translations(c):
    motion=c['motion'];breaks=[0.,1.]
    if motion=='translation_only_with_exact_facet_pad':breaks=[0.,.23,.25,.88,1.]
    elif motion=='telescoping_translation':breaks=sorted(set(breaks+c['opening_interval']))
    result=[]
    for a,b in zip(breaks,breaks[1:]):
        mid=(a+b)/2
        if motion=='translation_only_with_exact_facet_pad':
            n=c['normal'];q=[P([0])for _ in range(3)]
            for k in range(3):q[k]=n[k]*2.1*ease(0,.25,mid)+(c['outboard_m']*ease(.23,.88,mid)if k==0 else P([0]))
        elif motion=='telescoping_translation':q=[x*ease(*c['opening_interval'],mid)for x in c['translation_open_local']]
        else:q=[P([0])for _ in range(3)]
        result.append((a,b,q))
    return result
def real_roots(poly,a,b):return [float(r.real)for r in poly.roots()if abs(r.imag)<1e-7 and a+1e-8<r.real<b-1e-8]
def collision_ranges(box,actor,segments):
    found=[]
    for a,b,q in segments:
        tests=[q[k]-(actor[k+3]-box[k])for k in range(3)]+[q[k]-(actor[k]-box[k+3])for k in range(3)]
        pts=sorted(set([a,b]+[r for f in tests for r in real_roots(f,a,b)]))
        for lo,hi in zip(pts,pts[1:]):
            t=(lo+hi)/2
            if all(tests[k](t)<-1e-9 and tests[k+3](t)>1e-9 for k in range(3)):found.append([lo,hi])
    return found

def main(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    baseline=read(BASELINE);expected={r['relative']:r['sha256']for r in baseline['files']};assert len(expected)==1736
    def inventory():
        assert {p.relative_to(WORLD).as_posix()for p in WORLD.rglob('*')if p.is_file()}==set(expected)
        data={k:sha(WORLD/k)for k in expected};assert data==expected;return data
    before=inventory();metadata=read(WORLD/'r44_tv_personnel_platforms.json');meshpath=ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json';meshsha=sha(meshpath);assert meshsha=='2a789960d2649118b12505be8d6c93888ed8e1cabe6beaef0c20f498b12551a3';mesh=read(meshpath)
    saved=read(ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/boarding417_semantics_v4/saved_current_staff_and_training_pilot_full_NBT_and_bearing.json');current=entities(WORLD);assert len(saved)==5
    registry=ROOT/'src/main/java/com/projectseele/registry/ModEntities.java';reg=registry.read_text('utf8');assert '.sized(0.6F, 1.8F)'in reg and '.sized(.6F,1.8F)'in reg
    # Actual registered float dimensions at standing pose, not the visual skin.
    width,height=float(np.float32(.6)),float(np.float32(1.8));results=[]
    for row in saved:
        tag=current[tuple(row['uuid'])];assert tag.snbt()==row['complete_saved_nbt'];pos=list(map(float,tag['Pos']));x,y,z=pos
        actor=[x-width/2,y,z-width/2,x+width/2,y+height,z+width/2]
        vols=[dict(index=i,**r)for i,r in enumerate(metadata['operator_volumes'])if intersects(actor,r['bounds'])]
        collisions=[];runtime_fullstroke=[]
        for variant,cx in enumerate((-11.5,30.5,72.5)):
            anchor=[cx,-442.96,-239.5];local=[actor[k]-anchor[k%3]for k in range(6)]
            for comp in mesh['components']:
                if comp.get('variant',variant)!=variant or comp['part'].startswith('thin_side_rails'):continue
                segments=translations(comp);allboxes=np.asarray(mesh['collision_parts'][comp['part']],dtype=float)
                shift_min=[];shift_max=[]
                for k in range(3):
                    values=[float(q[k](t))for a,b,q in segments for t in [a,b]+real_roots(q[k].deriv(),a,b)]
                    shift_min.append(min(values));shift_max.append(max(values))
                for n,pair in enumerate(allboxes):
                    box=[*pair[0],*pair[1]]
                    if comp['motion']!='fixed':
                        first=[float(segments[0][2][k](0))for k in range(3)];last=[float(segments[-1][2][k](1))for k in range(3)]
                        sweep=[box[k]+min(first[k],last[k])-.045 for k in range(3)]+[box[k+3]+max(first[k],last[k])+.045 for k in range(3)]
                        if intersects(sweep,local):runtime_fullstroke.append(dict(variant=variant,part=comp['part'],collision_box_index=n,source_runtime_endpoint_union_inflated0p045=sweep,native_pass=False))
                    envelope=[box[k]+shift_min[k]for k in range(3)]+[box[k+3]+shift_max[k]for k in range(3)]
                    if not intersects(envelope,local):continue
                    ranges=collision_ranges(box,local,segments)
                    if ranges:collisions.append(dict(variant=variant,part=comp['part'],motion=comp['motion'],collision_box_index=n,exact_authored_local_box=box,opening_intervals=ranges,
                        actual_closed_progress_intervals=[[1-hi,1-lo]for lo,hi in ranges],native_runtime_pass=False))
        results.append(dict(uuid=row['uuid'],id=row['id'],position=pos,staff_id=str(tag.get('StaffId','')),no_AI=bool(int(tag.get('NoAI',0))),training_stage=int(tag.get('TrainingStage',-1)),
            route=str(tag.get('ForgeData',{}).get('SeelePilotRouteR30','')),full_saved_NBT=tag.snbt(),registered_standing_AABB=actor,actual_runtime_AABB_unverified=True,
            crew_fault_predicate_includes_living_alive_non_spectator=True,inside_operator_volumes=vols,operator_volume_blocks_prepare_fault=bool(vols),
            authored_collision_motion_intersections=collisions,will_block_actual_canMove_if_live_actor_and_scope_are_same=bool(collisions),
            exact_source_canMove_full0_to1_endpoint_union_inflate_hits=runtime_fullstroke,
            world_position_station_task_or_collision_changed=False))
    assert sha(meshpath)==meshsha and inventory()==before
    out.mkdir(parents=True);write(out/'all5_saved_default_crew_operator_volumes_and_authored_motion.json',results)
    sources=['world/TvPersonnelPlatformInterlockR44','world/TvCageCollisionR44','world/NervCarrierVisuals','world/EvaLogisticsDirector','world/TrainingPilotDirector','world/NervStaffDialogue','world/StaffCommandBookR24','world/NervStaffDirector','entity/NervStaffEntity','entity/TrainingPilotEntity','entity/StaffNavigationR26','entity/EvaDorsalMechanism']
    write(out/'source_receipt.json',dict(metadata_sha256=sha(WORLD/'r44_tv_personnel_platforms.json'),model_sha256=meshsha,registry_sha256=sha(registry),
        sources=[dict(path=str(ROOT/f'src/main/java/com/projectseele/{s}.java'),sha256=sha(ROOT/f'src/main/java/com/projectseele/{s}.java'))for s in sources],
        exact_motion_math='Authored collision AABBs + translation() + quintic smooth() split at native motion interval boundaries; polynomial inequality roots, no invented collider',
        declared_runtime_gantry_anchor=[[-11.5,-442.96,-239.5],[30.5,-442.96,-239.5],[72.5,-442.96,-239.5]],
        actual_live_no_save_gantry_NPC_pose_and_collision_unverified=True,complete1736_before_after_SHA_equal=True,world_written=False,Java_Gradle_MC_started=False))
    report=dict(saved_crew=5,inside_operator208=sum(bool(r['inside_operator_volumes'])for r in results),intersects_authored_any_component_motion_or_fixed_support=sum(bool(r['authored_collision_motion_intersections'])for r in results),
        source_canMove_full_stroke_inflated_predicate_hits=sum(bool(r['exact_source_canMove_full0_to1_endpoint_union_inflate_hits'])for r in results),
        result_summary=[dict(id=r['id'],staff_id=r['staff_id'],position=r['position'],operator_overlap=len(r['inside_operator_volumes']),parts=sorted({c['part']for c in r['authored_collision_motion_intersections']}))for r in results],
        actual_live_prepare_or_evacuation_pass=False,world_written=False,native_started=False)
    write(out/'report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args())
