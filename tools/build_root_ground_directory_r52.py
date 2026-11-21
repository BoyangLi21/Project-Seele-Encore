"""Root's actual nine-route graph. Design until all native bindings commission.

The grid is one shared partition for ground/air reservations, not multiple
overlapping aliases. Real track/support cells are installed separately.
"""
import json,math
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from r52_spatial_plan import BASE
from plan_bank3_exact_geometry_r52 import cloud,SOLES
from pathlib import Path

root=Path(__file__).resolve().parents[1];out=BASE/'runtime_directory';out.mkdir(exist_ok=True)
source=json.loads((root/'artifacts/r52_original_owner_candidate_20261010/THREE_ORIGINAL_BAYS_MECHANICAL_CANDIDATE.json').read_text('utf8'))
units=[dict(variant=u['variant'],lane=2-u['variant'],eva=u['eva'],plug=u['plug'])for u in source['units']]
nodes=[];legs=[];routes=[];ports=[];resources={};bindings={};profiles=[];node_map={};upright=[0.,1.,0.,0.];identity=[0.,0.,0.,1.];grid=32
def resource(id,kind):
    resources.setdefault(id,dict(id=id,kind=kind,component=id));return id
def space_keys(low,high):
    result=[];a=np.floor(np.asarray(low)/grid).astype(int);b=np.floor((np.asarray(high)-1e-8)/grid).astype(int)
    for x in range(a[0],b[0]+1):
        for y in range(a[1],b[1]+1):
            for z in range(a[2],b[2]+1):
                id=f'space/c{x}_{y}_{z}';resource(id,'SPACE');bindings[id]=dict(resource=id,component=id,spaces=[[x*grid,y*grid,z*grid,(x+1)*grid,(y+1)*grid,(z+1)*grid]]);result.append(id)
    return result
def node(id,pos,role='PATH',bank=0,lane=0,variant=-1,yaw=0):
    q=Rotation.from_euler('y',yaw).as_quat().tolist();r=dict(id=id,dimension='projectseele:geofront',role=role,foot_frame=dict(translation=list(map(float,pos)),quaternion_xyzw=q))
    if role=='BANK':r.update(bank=bank,lane=lane)
    if role=='BAY':r.update(variant=variant)
    nodes.append(r);node_map[id]=r;return id
def relative(pitch):return(Rotation.from_euler('x',pitch)*Rotation.from_quat(upright)).as_quat().tolist()
def leg(id,a,b,motion,ticks,q0,q1,doors,geometry):
    na,nb=node_map[a]['foot_frame'],node_map[b]['foot_frame'];p0,p1=map(np.asarray,(na['translation'],nb['translation']))
    nr=Slerp([0,1],Rotation.from_quat([na['quaternion_xyzw'],nb['quaternion_xyzw']]))
    er=Slerp([0,1],Rotation.from_quat([q0,q1]));occ=set();boxes=[]
    count=max(19,math.ceil(np.linalg.norm(p1-p0)/12)+1)
    for t in np.linspace(0,1,count):
        position=p0*(1-t)+p1*t
        if motion=='ORIGINAL_UPRIGHT_TRANSFER':
            distance=np.linalg.norm((p1-p0)[[0,2]])*t;d=max(0,min(160,distance-27.5));rounded=lambda q:q*.5-6/(2*math.pi)*math.sin(math.pi*q/6)
            h=(rounded(d)if d<6 else 154-rounded(160-d)if d>154 else d-3)/154
            position[1]=p0[1]+(p1[1]-p0[1])*h
        pts=(nr(t)*er(t)).apply(geometry)+position;lo=pts.min(0)-1.01;hi=pts.max(0)+1.01
        occ.update(space_keys(lo,hi));boxes.append([*lo.tolist(),*hi.tolist()])
    if motion=='VERTICAL'and node_map[b]['role']=='EXIT':
        # Root-approved real 42-tick ejection keeps the completion lease
        # while the original body rises and its independent carrier lowers.
        pts=(nr(1)*er(1)).apply(geometry)+p1
        low=pts.min(0)-[1.01,65.01,1.01];high=pts.max(0)+[1.01,101.04606775,1.01]
        occ.update(space_keys(low,high));boxes.append([*low.tolist(),*high.tolist()])
    rail=resource('rail/'+id,'RAIL');support=resource('support/'+id,'SUPPORT')
    door_ids=[resource(d,'DOOR')for d in doors]
    r=dict(id=id,**{'from':a,'to':b},motion=motion,ticks=ticks,eva_from_xyzw=q0,eva_to_xyzw=q1,rails=[rail],doors=door_ids,support=support,occupancy=sorted(occ));legs.append(r)
    if motion=='ORIGINAL_UPRIGHT_TRANSFER':r['ramp_profile']=dict(flat_before=27.5,slope_run=160,blend=6)
    reverse=dict(r,id=id+'/reverse',**{'from':b,'to':a},eva_from_xyzw=q1,eva_to_xyzw=q0);legs.append(reverse)
    if motion=='ORIGINAL_UPRIGHT_TRANSFER':reverse['ramp_profile']=dict(flat_before=16.5,slope_run=160,blend=6)
    profiles.append(dict(leg=id,foot_from=na,foot_to=nb,body_from=q0,body_to=q1,actual_full_assembly_sample_bounds=boxes,physical_rail_binding_pending=True))
    return id
for u in units:
    variant=u['variant'];lane=u['lane'];x=[72.5,30.5,-11.5][variant];sole=SOLES[variant];geo,sha=cloud(variant)
    prefix=f'unit{variant}';bay=node(prefix+'/bay',[x,-678,328.5-sole],'BAY',variant=variant)
    bank=[node(prefix+f'/bank{b}',[x,-646,z-sole],'BANK',bank=b,lane=lane)for b,z in enumerate((124.5,-328.5,-781.5),1)]
    common=[leg(prefix+'/original_incline',bay,bank[0],'ORIGINAL_UPRIGHT_TRANSFER',240,upright,upright,[f'bay_{variant}_front'],geo)]
    transfers=[]
    for j in range(2):transfers.append(leg(prefix+f'/bank{j+1}_to_{j+2}',bank[j],bank[j+1],'TRACKED_BANK_TRANSFER',300,upright,upright,[f'bank{j+1}_rear_{lane}'],geo))
    for b in(1,2,3):
        path=common+transfers[:b-1];pre=prefix+f'/exit{b}';port=pre+'/port';region='GEOFRONT'if b==2 else'SURFACE'
        if b==2:
            end=node(pre+'/surface',[x,-472,-328.5-sole],'EXIT')
            path+=[leg(pre+'/vertical',bank[1],end,'VERTICAL',140,upright,upright,[f'bank_2_upper_lane_{lane}',f'bank_2_surface_lane_{lane}'],geo)]
        else:
            if b==1:
                start=np.array([x,-554,124.5-sole]);finish=np.array([x,-530,-35.5-sole]);tip=[x,84,-35.5-sole];yaw=0;pitch=-math.atan2(160,24)
            else:
                start=np.array([x,-556,-781.5-sole]);finish=np.array([x-1200,-516,1150.5-sole]);tip=[x-1200,72,1150.5-sole];delta=finish-start;yaw=math.atan2(delta[0],delta[2]);pitch=math.acos(delta[1]/np.linalg.norm(delta))
            inlet=node(pre+'/bearing_in_upright',start);tilted=node(pre+'/bearing_in_inclined',start,yaw=yaw)
            far=node(pre+'/bearing_out_inclined',finish,yaw=yaw);vertical=node(pre+'/bearing_out_upright',finish);end=node(pre+'/surface',tip,'EXIT');q=relative(pitch)
            path += [leg(pre+'/lower_vertical',bank[b-1],inlet,'VERTICAL',100,upright,upright,[f'bank_{b}_upper_lane_{lane}'],geo),
                     leg(pre+'/turn_in',inlet,tilted,'FOOT_BEARING_TURN',80,upright,q,[],geo),
                     leg(pre+'/incline',tilted,far,'LAUNCH_INCLINE',100 if b==1 else 420,q,q,[],geo),
                     leg(pre+'/turn_out',far,vertical,'FOOT_BEARING_TURN',80,q,upright,[],geo),
                     leg(pre+'/upper_vertical',vertical,end,'VERTICAL',200,upright,upright,([f'bank_1_retained_{s}_lane_{lane}'for s in(1,2,3)]if b==1 else[])+[f'bank_{b}_surface_lane_{lane}'],geo)]
        id=prefix+f'/departure/{b}';back=prefix+f'/recovery/{b}'
        routes.append(dict(id=id,variant=variant,bank=b,lane=lane,region=region,port=port,legs=path))
        routes.append(dict(id=back,variant=variant,bank=b,lane=lane,region=region,port=port,reverse_of=id,legs=[s+'/reverse'for s in reversed(path)]))
        ports.append(dict(id=port,region=region,node=end,reverse_routes={str(variant):back}))
for variant in range(3):resource(f'bay_{variant}_service_pit','DOOR')
for id in('remote_airshaft_surface','remote_airshaft_south'):resource(id,'DOOR')
resource('yashima_cannon_hatch','DOOR')
document=dict(schema='projectseele.r52.route-directory.v1',map_author='root',status='design',epoch=52,units=units,nodes=nodes,resources=list(resources.values()),legs=legs,routes=routes,ports=ports,
              runtime=dict(bindings=list(bindings.values()),departure_defaults=[dict(variant=v,surface=f'unit{v}/departure/1',geofront=f'unit{v}/departure/2',hakone=f'unit{v}/departure/3')for v in range(3)]),
              root_construction_note='Actual installed topology and source-sized nonoverlapping space grid. Track/support/door binding set still incomplete; this document cannot commission movement.')
(out/'GROUND_DESIGN.json').write_text(json.dumps(document,separators=(',',':')),'utf8');(out/'GROUND_RAIL_PROFILES.json').write_text(json.dumps(profiles,separators=(',',':')),'utf8')
print('ROOT_GROUND_DESIGN',len(nodes),'nodes',len(legs),'legs',len(routes),'routes',len(resources),'resources; INCOMPLETE NATIVE BINDINGS',flush=True)
