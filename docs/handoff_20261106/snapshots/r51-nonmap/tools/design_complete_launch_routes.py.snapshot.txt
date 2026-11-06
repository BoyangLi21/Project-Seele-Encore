"""Current Root nine-route design. No world write or readiness declaration.

Three adjacent banks are fed by the original ramp. GeoFront exits directly
above bank 1; bank 2 connects north to the original surface wells; bank 3
fans north before its three separated northwest inclines to Hakone.
"""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse
import hashlib
import json
import math
import numpy as np
from scipy.spatial import cKDTree
from build_continuous_upright_directory_r52 import segment,corner,sample,verify_segments,reversed_curve


ROOT=Path(__file__).resolve().parents[1]
SOLE=(.224014043808,.223975896835,.183567047119)
IDENTITY=[0.,0.,0.,1.]
UPRIGHT=[0.,1.,0.,0.]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);args=ap.parse_args()
    base=args.base.resolve();out=base/'phased_routes';out.mkdir(exist_ok=True)
    ascent_path=base/'monotone_launch_candidate/MONOTONE_ASCENT_CANDIDATE.json'
    ascents=json.loads(ascent_path.read_text('utf8'))
    assert ascents['proposed_additional_hangar_terminal_bank_dy']==-384
    accepted=json.loads((base/'ROOT_SPATIAL_PLAN.json').read_text('utf8'))
    assert accepted['bank_foot_y']==-1030 and accepted['bay_foot_y']==-1062
    source_path=ROOT/'artifacts/r52_original_owner_candidate_20261010/THREE_ORIGINAL_BAYS_MECHANICAL_CANDIDATE.json'
    source=json.loads(source_path.read_text('utf8'))
    units=[dict(variant=u['variant'],lane=2-u['variant'],eva=u['eva'],plug=u['plug']) for u in source['units']]
    nodes={};legs={};resources={};spaces={};routes=[];ports=[];curves={};reports=[]
    def res(key,kind):
        resources[key]=dict(id=key,kind=kind,component=key)
        return key
    def node(key,p,role,**kw):
        nodes[key]=dict(id=key,dimension='projectseele:geofront',role=role,
            foot_frame=dict(translation=list(map(float,p)),quaternion_xyzw=IDENTITY),**kw)
        return key
    def reserve(points):
        keys=set()
        for q in points:
            low=np.floor((q+[-18,-7,-18])/32).astype(int)
            high=np.floor((q+[18,63,18])/32).astype(int)
            for x in range(low[0],high[0]+1):
                for y in range(low[1],high[1]+1):
                    for z in range(low[2],high[2]+1):
                        key=res(f'space/c{x}_{y}_{z}','SPACE');keys.add(key)
                        spaces[key]=dict(resource=key,component=key,spaces=[[int(x*32),int(y*32),int(z*32),int((x+1)*32),int((y+1)*32),int((z+1)*32)]])
        return sorted(keys)
    def add_leg(key,a,b,motion,doors,pieces=None,ramp=None):
        p0=np.array(nodes[a]['foot_frame']['translation']);p1=np.array(nodes[b]['foot_frame']['translation'])
        length=verify_segments(pieces) if pieces else float(np.linalg.norm(p1-p0))
        if pieces:
            points=np.concatenate([sample(s['controls'],max(3,math.ceil(np.linalg.norm(np.ptp(s['controls'],axis=0))*1.5)+1)) for s in pieces])
            derivatives=np.concatenate([sample((len(s['controls'])-1)*np.diff(s['controls'],axis=0),513) for s in pieces])
            transverse=np.sum(derivatives[:,1:]**2,axis=1)/np.sum(derivatives**2,axis=1)
            assert transverse.min()>=.01,('Degenerate original outer-guide frame',key,float(transverse.min()))
            curves[key]=points
        else:
            points=np.linspace(p0,p1,math.ceil(length)+1)
        leg=dict(id=key,**{'from':a,'to':b},motion=motion,ticks=max(2,math.ceil(length/180*20)),
            eva_from_xyzw=UPRIGHT,eva_to_xyzw=UPRIGHT,rails=[res('rail/'+key,'RAIL')],
            support=res('support/'+key,'SUPPORT'),doors=[res(d,'DOOR') for d in doors],occupancy=reserve(points))
        if pieces:leg['centre_curve']=dict(segments=pieces)
        if ramp:leg['ramp_profile']=ramp
        legs[key]=leg
        reverse=dict(leg,id=key+'/reverse',**{'from':b,'to':a})
        if pieces:reverse['centre_curve']=dict(segments=reversed_curve(pieces))
        if ramp:reverse['ramp_profile']=dict(flat_before=16.5,slope_run=160,blend=6)
        legs[reverse['id']]=reverse
        reports.append(dict(leg=key,length_m=length,minimum_outer_frame_projection2=None if not pieces else float(transverse.min())))
        return key
    for u in units:
        v=u['variant'];lane=u['lane'];x=(72.5,30.5,-11.5)[v];sole=SOLE[v];pre=f'unit{v}'
        bay=node(pre+'/bay',[x,-1062,328.5-sole],'BAY',variant=v)
        banks=[node(pre+f'/bank{b}',[x,-1030,z-sole],'BANK',bank=b,lane=lane) for b,z in enumerate((124.5,76.5,28.5),1)]
        common=[add_leg(pre+'/original_incline',bay,banks[0],'ORIGINAL_UPRIGHT_TRANSFER',[f'bay_{v}_front'],ramp=dict(flat_before=27.5,slope_run=160,blend=6))]
        transfers=[add_leg(pre+f'/bank{j+1}_to_{j+2}',banks[j],banks[j+1],'TRACKED_BANK_TRANSFER',[f'bank_{j+1}_rear_lane_{lane}']) for j in range(2)]
        for bank in (1,2,3):
            start=np.array(nodes[banks[bank-1]]['foot_frame']['translation'])
            case=next(c for c in ascents['cases'] if c['variant']==v and c['bank']==bank)
            assert np.array_equal(start,case['foot_start'])
            finish=np.array(case['foot_end']);pieces=case['centre_curve']['segments']
            assert all(np.all(np.diff(s['controls'],axis=0)[:,1]>0) for s in pieces)
            assert np.array_equal(np.array(pieces[0]['controls'][1])[[0,2]],start[[0,2]])
            if bank==1:
                doors=[f'bank_1_upper_lane_{lane}',f'bank_1_surface_lane_{lane}']
            elif bank==2:
                doors=[f'bank_2_upper_lane_{lane}']+[f'bank_2_retained_{j}_lane_{lane}' for j in (1,2,3)]+[f'bank_2_surface_lane_{lane}']
            else:
                doors=[f'bank_3_upper_lane_{lane}',f'bank_3_surface_lane_{lane}']
            end=node(pre+f'/exit{bank}/surface',finish,'EXIT')
            key=add_leg(pre+f'/exit{bank}/upright_continuous',banks[bank-1],end,'VERTICAL' if bank==1 else 'LAUNCH_INCLINE',doors,pieces=pieces)
            path=common+transfers[:bank-1]+[key];port=pre+f'/exit{bank}/port'
            depart=pre+f'/departure/{bank}';recover=pre+f'/recovery/{bank}'
            route=dict(id=depart,variant=v,bank=bank,lane=lane,region='GEOFRONT' if bank==1 else 'SURFACE',port=port,legs=path,
                motion_profile=dict(type='continuous_upright',cruise_mps=180.,acceleration_mps2=120.,deceleration_mps2=120.,ready_node=banks[bank-1],
                    phase_version=1,prelaunch=dict(cruise_mps=4.,acceleration_mps2=2.,deceleration_mps2=2.)))
            routes.extend([route,dict(route,id=recover,reverse_of=depart,legs=[k+'/reverse' for k in reversed(path)])])
            ports.append(dict(id=port,region=route['region'],node=end,reverse_routes={str(v):recover}))
    for v in range(3):res(f'bay_{v}_service_pit','DOOR')
    # This delivery includes launch, hangar and airlift. The combat equipment
    # is explicitly deferred and must not create an unsatisfied door binding.
    for key in ('remote_airshaft_surface','remote_airshaft_south'):res(key,'DOOR')
    doc=dict(schema='projectseele.r52.route-directory.v2',bank_roles_version=1,
        bank_roles=[dict(bank=1,intent='geofront'),dict(bank=2,intent='surface'),dict(bank=3,intent='hakone')],
        map_author='root',status='design',epoch=53,units=units,nodes=list(nodes.values()),resources=list(resources.values()),
        legs=list(legs.values()),routes=routes,ports=ports,runtime=dict(bindings=list(spaces.values()),
        departure_defaults=[dict(variant=v,geofront=f'unit{v}/departure/1',surface=f'unit{v}/departure/2',hakone=f'unit{v}/departure/3') for v in range(3)]))
    path=out/'PHASED_MONOTONE_DESIGN.json';path.write_text(json.dumps(doc,separators=(',',':')),'utf8')
    # A zero result proves separation for this deliberately enlarged moving
    # AABB sample envelope. A positive is only a candidate requiring exact
    # clipped triangle sweep analysis, never permission to thin the model.
    candidates=[];keys=list(curves)
    for i,key in enumerate(keys):
        a=curves[key]
        for other in keys[i+1:]:
            b=curves[other];scaled=b/np.array([32.,66.,32.]);tree=cKDTree(scaled)
            pairs=tree.query_ball_point(a/np.array([32.,66.,32.]),r=1,p=np.inf)
            hits=[j for j,p in enumerate(pairs) if p]
            if hits:candidates.append(dict(a=key,b=other,sample_pairs=sum(len(pairs[j]) for j in hits),first=[a[hits[0]].tolist(),b[pairs[hits[0]][0]].tolist()]))
    report=dict(world_written=False,commissioned=False,design_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source_identity_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),ascent_geometry_sha256=hashlib.sha256(ascent_path.read_bytes()).hexdigest(),legs=reports,
        conservative_independent_ascent_aabb_candidates=candidates,
        pending=['exact continuous model and steel sweeps','destination terrain and ports','civil construction','native runtime and visual review'])
    (out/'ROOT_DESIGN_REPORT.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(dict(directory=str(path),nodes=len(nodes),legs=len(legs),routes=len(routes),aabb_candidates=candidates)),flush=True)


if __name__=='__main__':main()
