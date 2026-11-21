"""Root continuous EVA access around the actual shield well, on a founded shoulder."""
import argparse,copy,json,math,hashlib
from pathlib import Path
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities

def line(points,step=2):
    result=[]
    for a,b in zip(points,points[1:]):
        a,b=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
        result.extend((a*(1-t)+b*t).tolist()for t in np.linspace(0,1,math.ceil(np.linalg.norm(b-a)/step)+1)if not result or np.linalg.norm(a*(1-t)+b*t-result[-1])>1e-7)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];out=BASE/'far_yashima_access';stage='continuous_shield_service_shoulder';assert not list((out/stage).glob('applied_*'))
    waypoints=[[-1188.5,175,-1463.5],[-1158.5,175,-1463.5],[-1158.5,175,-1403.5],[-1213.5,175,-1359.5]]
    path=line(waypoints);lo=(-1230,150,-1481);hi=(-1141,176,-1342);a,names=measure(lo,hi)
    for s in('minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:air'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};b=a.copy();zz,xx=np.mgrid[lo[2]:hi[2]+1,lo[0]:hi[0]+1];q=np.stack((xx+.5,zz+.5),axis=-1);dist=np.full(xx.shape,np.inf)
    for aa,bb in zip(waypoints,waypoints[1:]):
        p0=np.asarray(aa)[[0,2]];v=np.asarray(bb)[[0,2]]-p0;t=np.clip(np.sum((q-p0)*v,axis=-1)/(v@v),0,1);dist=np.minimum(dist,np.linalg.norm(q-p0-t[...,None]*v,axis=-1))
    natural={ids[s]for s in('minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]')};ground=np.full(xx.shape,-999)
    for i,y in enumerate(range(lo[1],hi[1]+1)):ground=np.where(np.isin(a[i],list(natural)),y,ground)
    columns=0
    for z,x in np.argwhere(dist<16):
        # Keep the actual installed shield foundation and every other device.
        if any(names[int(v)].startswith('projectseele:')for v in np.unique(a[:,z,x])):continue
        assert ground[z,x]>=lo[1]+2
        t=np.clip((16-dist[z,x])/8,0,1);t=t*t*(3-2*t);target=round(ground[z,x]*(1-t)+174*t)
        if target<=ground[z,x]:continue
        g=int(ground[z,x]);b[g-2-lo[1]:target-1-lo[1],z,x]=ids['minecraft:stone'];b[target-1-lo[1]:target-lo[1],z,x]=ids['minecraft:dirt'];b[target-lo[1],z,x]=ids['minecraft:grass_block[snowy=false]'];columns+=1
    assert not list(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
    for p in path:
        x,z=math.floor(p[0]),math.floor(p[2]);patch=b[174-lo[1],z-lo[2]-6:z-lo[2]+7,x-lo[0]-6:x-lo[0]+7]
        assert patch.shape==(13,13)and all(names[int(v)]in('minecraft:grass_block[snowy=false]','projectseele:nerv_floor_panel')for v in np.unique(patch)),p
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';paint=vox.Painter(vertical_bounds=(-960,320));n=runs(paint,lo,a,b,names,'R52_founded_natural_EVA_service_path')
    paint.meta.update(root_author=True,centre_waypoints=waypoints,core_radius=8,transition_radius=16);folder=paint.save_plan(stage)
    candidate=json.loads((root/'.Codex/r52_operations/calibration_powered/STATION_CANDIDATE.json').read_text('utf8'))
    route1=line([[-1331.5,175,-1412.5],candidate['prone_position']]);route0=line([[-1226.5,175,-1488.5],waypoints[0]])
    site=dict(id='r52/far_yashima_lilith_projection',hero=candidate['prone_position'],cover=waypoints[-1],angel=[30.5,114,348.5],yaw=candidate['prone_yaw'],requires_retracted_city=False,geometry_validated=False,model_ready=True,model_scale=4,visibility='remote_actual_entity_v1',attack_range=2600,primary_unit=1,support_port=[-1341.5,175,-1399.5],support_port_validated=True,
        landings={'0':dict(point=[-1226.5,175,-1488.5],receiver_id='yashima_delivery_unit0'),'1':dict(point=[-1331.5,175,-1412.5],receiver_id='yashima_delivery_unit1')},eva_access_routes={'0':route0,'1':route1},cover_after_supply_route=path,equipment_approach={'0':waypoints[0]},shield_wait_port=waypoints[-1],route_arrival_radius=.9,native_verified=False,user_accepted=False)
    old=json.loads((vox.WORLD/'tv_encounter_sites_r45.json').read_text('utf8'))['sites']['ramiel'];controls=copy.deepcopy(old['yashima_controls'])
    def power(p):return[p[0]-1362,p[1]+71,p[2]-1874]
    for key in('grid_switches','power_pylons'):controls[key]=[power(p)for p in controls[key]]
    for row in controls['console_buttons']:row['pos']=power(row['pos'])
    for r in controls['supply_racks']:
        v=r['unit'];offset=(-1301,65,-1942)if v==0 else(-1418,4,-1826)
        r['position']=[r['position'][i]+offset[i]for i in range(3)]
        r['footprint']=[[p[i]+offset[i]for i in range(3)]for p in r['footprint']]
    controls['equipment_approach']=[dict(unit=0,position=waypoints[0],original_native_pickup_range=24)];site['yashima_controls']=controls
    (out/'ROOT_SITE_CANDIDATE.json').write_text(json.dumps(site,ensure_ascii=False,indent=2),'utf8');(out/'CANNON_ACCESS_ROUTE.json').write_text(json.dumps(route1),'utf8')
    report=dict(world_written=False,changed_cells=n,graded_columns=columns,routes={'unit0_to_original_shield':len(route0),'unit0_to_cover':len(path),'unit1_to_cannon':len(route1)},actual_13_by_13_contact_patch_verified=True,native_acceptance=False)
    if args.apply:
        report['application']=paint.apply(stage);actual,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal])[actual],b);report.update(world_written=True,whole_exact_readback=True)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()
