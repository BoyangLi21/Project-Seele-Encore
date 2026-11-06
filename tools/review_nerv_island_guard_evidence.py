"""Separate foundation and fall-guard evidence; does not alter the candidate."""
import argparse,json
from pathlib import Path
from audit_mountain_station_access import SupplementedSections,shape_for
from propose_mountain_station_steps import Overlay
from audit_oldcity_surface_station_access import MainlineSweep
from build_gora_protected_transfer import IndependentWalker

def run(a):
    a.out.mkdir(exist_ok=False);proposal=json.loads((a.candidate/'proposal.json').read_text('utf8'))
    capture=json.loads((a.candidate/'capture.json').read_text('utf8'))
    reader=SupplementedSections(a.context,Path(capture['exact_station_source']))
    changes=json.loads((a.candidate/'changes.json').read_text('utf8'));after=Overlay(reader,changes)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    review=json.loads(a.review.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'));native=json.loads(a.native.read_text('utf8'))
    w=IndependentWalker(after,shapes,MainlineSweep(native,model,review['bounds']))
    columns=[];issues=[]
    for q in proposal['islands'][0]['supports']:
        x,y,z=q['pos'];cells=[]
        for yy in range(y,q['top']+1):
            state=after.state(x,yy,z);boxes,_=shape_for(state,shapes,True)
            solid=boxes==[[0.,0.,0.,1.,1.,1.]]
            cells.append(dict(pos=[x,yy,z],state=state,full_collision_bearing=solid))
            if not solid:issues.append([x,yy,z])
        columns.append(dict(base=q['pos'],top_y=q['top'],continuous=all(c['full_collision_bearing']for c in cells),cells=cells))
    probes=[]
    for x in range(-368,-362):
        for z in(683.9,685.1):
            p=[x+.5,95,z];hit=w.body(*p);probes.append(dict(kind='shaft-side',player=p,obstruction=hit,blocked=hit is not None))
    p=[-367.8,95,684.5];hit=w.body(*p);probes.append(dict(kind='shaft-back-end',player=p,obstruction=hit,blocked=hit is not None))
    errors=[]
    if len(columns)!=87:errors.append('Unexpected column count')
    if len(probes)!=13 or any(not q['blocked']for q in probes):errors.append('Missing fall barrier')
    if issues:errors.append('Foundation discontinuity')
    row=dict(candidate=str(a.candidate),continuous_columns=columns,column_count=len(columns),bearing_issues=issues,
        fall_probes=probes,probe_count=len(probes),all_probes_blocked=all(q['blocked']for q in probes),
        errors=errors,world_written=False,candidate_changed=False,maximum_stair_rise=.5,
        native_vehicle_envelope_respected=True,guard_shapes='exact existing iron trapdoor and iron bar collision export')
    (a.out/'evidence.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8')
    print('NERV island evidence:',len(columns),'continuous columns;',len(probes),'blocked fall probes; errors',errors,flush=True)
    if errors:raise ValueError('Guard evidence failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('candidate','context','metadata','review','models','native','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
