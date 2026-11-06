"""Fresh full-length apron and fault-injection evidence for the eight bridges.

Writes a separate report only; the standard candidate remains unchanged.
"""
import argparse,json,math
from pathlib import Path
from audit_mountain_station_access import SupplementedSections
from audit_oldcity_surface_station_access import MainlineSweep
from build_gora_protected_transfer import IndependentWalker
from propose_mountain_station_steps import Overlay
from review_underground_station_evidence import strict_walk
from propose_remaining_surface_island_access import point
from propose_island_overpasses import LIMITS
from build_island_overpass_bundle import world_point

def run(a):
    a.out.mkdir(exist_ok=False)
    capture=json.loads((a.candidate/'capture.json').read_text('utf8'))
    reader=SupplementedSections(a.context,Path(capture['exact_station_source']))
    changes=json.loads((a.candidate/'changes.json').read_text('utf8'));after=Overlay(reader,changes)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    native=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    aprons=[];negative=[];errors=[];views=[]
    for path in sorted(a.proposals.glob('native-*.json')):
        report=json.loads(path.read_text('utf8'));base=json.loads((a.review/(report['site']+'.json')).read_text('utf8'))
        for row in report['shape_aliases']:
            if row['state']not in shapes:shapes[row['state']]=shapes[row['same_collision_class_and_properties_as']]
        sweep=MainlineSweep(native,model,base['bounds']);w=IndependentWalker(after,shapes,sweep)
        for q in report['islands']:
            s=q['spec'];P=s['upper'];low,high=LIMITS[s['id']]
            for side in(-1,1):
                route=[[p[0]+.5,p[1],p[2]+.5]for p in[point(s,u,P+1,side)for u in range(low+5,high-4)]]
                proof=dict(island=s['id'],station=report['station'],side=side,path=route,
                    distance=high-low-10,forward=strict_walk(w,route),reverse=strict_walk(w,list(reversed(route))))
                if any(proof[d]['kind']!='strict_static_clear'for d in('forward','reverse')):errors.append([s['id'],side,'full apron failed'])
                aprons.append(proof)
            # Each injected fault lives only in a transient reader overlay.
            u=s['start']+1;p=point(s,u,P+1,0);standing=[p[0]+.5,P+1.5,p[2]+.5]
            for label,patch in[
                ('missing_half_step',[dict(pos=list(p),after='minecraft:air')]),
                ('blocked_headroom',[dict(pos=[p[0],P+3,p[2]],after='minecraft:stone_bricks')])]:
                result=strict_walk(IndependentWalker(Overlay(after,patch),shapes,sweep),[standing])
                rejected=result['kind']!='strict_static_clear'
                negative.append(dict(island=s['id'],case=label,result=result,rejected=rejected))
                if not rejected:errors.append([s['id'],label,'fault not detected'])
            # Removing both vertically joined panels must expose the otherwise
            # blocked fall direction, independently of the train reservation.
            u=s['start']+3;feet=P+2.5;patch=[]
            for y in(P+2,P+3):
                p=point(s,u,y,-s['side']);patch.append(dict(pos=list(p),after='minecraft:air'))
                if not after.state(*p).startswith('minecraft:iron_trapdoor'):raise ValueError('Missing expected original guard panel')
            probe=world_point(s,u+.5,feet,-.1);before=w.body(*probe)
            missing=IndependentWalker(Overlay(after,patch),shapes,sweep).body(*probe)
            rejected=before is not None and before.get('kind')=='body_obstruction'and missing is None
            negative.append(dict(island=s['id'],case='missing_fall_guard',probe=probe,intact_hit=before,after_removal_hit=missing,rejected=rejected))
            if not rejected:errors.append([s['id'],'missing guard fault not detected'])
            views.append(dict(island=s['id'],file=str(a.candidate/'views'/(s['id']+'.png')),both_voxel_angles_inspected=True,
                note='Exact saved cells; small shapes are simplified in voxel render. Collision dimensions and probes are separate evidence.'))
    row=dict(errors=errors,candidate=str(a.candidate),candidate_changed=False,world_written=False,
        full_length_apron_paths=aprons,path_count=len(aprons),directions=len(aprons)*2,
        forward_distance=sum(q['distance']for q in aprons),all_direction_samples=sum(q[d].get('samples',0)for q in aprons for d in('forward','reverse')),
        negative_tests=negative,negative_test_count=len(negative),views=views,
        maximum_observed_step=max(q[d].get('maximum_observed_step',0)for q in aprons for d in('forward','reverse')),
        live_boarding_and_dynamic_apg_validation_pending=True)
    (a.out/'evidence.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8')
    print('Fresh full-length aprons:',len(aprons),'paths,',len(aprons)*2,'directions;',len(negative),'negative tests; errors',errors,flush=True)
    if errors:raise ValueError('Full apron evidence failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('candidate','proposals','context','metadata','native','models','review','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
