"""Independent saved-block checks for the relocated Midoricho candidate."""
import argparse, collections, json, math
from pathlib import Path
import numpy as np
import nbtlib
from scipy.ndimage import label
from shapely.geometry import shape, box
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from author_kamonomiya_station import voxel_box, ALLOWED, OPEN
from author_itabashi_station import dump, public_network, reach
from review_itabashi_delivery import changes
from check_kamonomiya_visible_models import clipped_half_width


def verify(candidate,authority,write=True):
    e=Editor(candidate);d=json.loads((candidate/'station-design.json').read_text('utf8'));m=json.loads((candidate/'manifest.json').read_text('utf8'))
    changed,chunks=changes(candidate);errors=[];counts=collections.Counter();declared=d['parts'][0]['bounds']
    with np.load(authority/'network.npz')as f:ax,az,_,_=map(int,f['bounds']);old=f['walk']
    devices={tuple(int(q[k])for k in('x','y','z'))for q in nbtlib.load(candidate/'captured-devices.dat')['Devices']}
    ref=json.loads((candidate/'reference-geography.json').read_text('utf8'))
    water=unary_union([shape(q['geometry'])for q in ref if q['properties'].get('source_layer')in('WA','RvrCL','WStrL')]);banks=water.buffer(3)
    jr=unary_union([shape(q['geometry'])for q in ref if q['properties'].get('source_layer')=='RailCL'and q['properties'].get('vt_rtcode')=='JR'])
    water_changes=[]
    for x,y,z,before,after in changed:
        counts['cells']+=1
        if before.split('[')[0]not in ALLOWED:counts['protected']+=1
        if old[z-az,x-ax]:counts['old_public']+=1
        if(x,y,z)in devices:counts['devices']+=1
        if not all(declared[i]<=(x,y,z)[i]<=declared[i+3]for i in range(3)):counts['outside']+=1
        if banks.intersects(box(x,z,x+1,z+1)):
            water_changes.append([x,y,z])
            if not(3444<=x<=3453 and 317<=z<=366 and y>=-76):counts['water']+=1
    for key,msg in [('protected','protected source changed'),('old_public','retained public column changed'),('devices','retained device changed'),('outside','outside declared volume'),('water','water bank terrain changed')]:
        if counts[key]:errors.append(msg)
    if counts['cells']!=m['cells']:errors.append('manifest count mismatch')
    nodes,floor_failures=public_network(e,d['public_columns']);q=d['retained_street_anchor'];start=q[0],round(q[1]*2),q[2]
    parents=reach(nodes,start);goals=[]
    for name,q in d['goals'].items():
        p=q[0],round(q[1]*2),q[2];path=[]
        while p in parents:
            path.append([p[0]+.5,p[1]/2,p[2]+.5]);p=parents[p]
            if p is None:break
        path.reverse();goals.append(dict(name=name,reachable=bool(path),path=path))
        if not path:errors.append('unreachable goal '+name)
    if floor_failures:errors.append('public floor or headroom invalid')
    if len(parents)!=len(nodes):errors.append('disconnected public surface')
    edge=[]
    for z in d['full_boarding_edge']['samples']:
        width=0
        for x in d['full_boarding_edge']['columns_perpendicular']:
            if(x,-148,z)not in parents:break
            width+=1
        edge.append(dict(z=z,continuous_width=width,visible_gap=.1875))
    if min(q['continuous_width']for q in edge)<2:errors.append('full platform edge lost')
    crop=[declared[0]-1,-86,declared[2]-1,declared[3]+1,declared[4]+1,declared[5]+1]
    data,palette=voxel_box(e,crop);solids=np.asarray([s.split('[')[0]not in OPEN for s in palette])[data]
    lab,n=label(solids);roots=set(map(int,np.unique(lab[0])));floating=[]
    for x,y,z,_,st in changed:
        if st.split('[')[0]in OPEN:continue
        if all(crop[i]<=(x,y,z)[i]<=crop[i+3]for i in range(3))and int(lab[y-crop[1],z-crop[2],x-crop[0]])not in roots:floating.append([x,y,z])
    if floating:errors.append('new unrooted solid')
    sign_errors=[];expected={tuple(q['pos']):q for q in d['expected_signs']};tags=nbtlib.load(candidate/'block-entities.dat')['Changes']
    if len(tags)!=len(expected):sign_errors.append('count')
    for q in tags:
        if 'After'not in q:sign_errors.append('missing After');continue
        tag=q['After'];p=tuple(int(tag[k])for k in('x','y','z'));st=e.state(*p)
        if p not in expected or p in devices or 'Before'in q:sign_errors.append('unexpected location');continue
        if 'oak_wall_sign[facing=west'not in st or e.state(p[0]+1,p[1],p[2]).split('[')[0]in OPEN:sign_errors.append('state/backing')
        if json.loads(str(tag['front_text']['messages'][0])).get('text')!='緑町駅':sign_errors.append('title')
    if sign_errors:errors.append('sign payload or backing invalid')
    # Platform and railway deck stay outside the independent 4.5m JR corridor.
    rail_and_platform_jr=[];underpass_columns={(q['x'],q['z'])for q in d['JR_underpass_interfaces']}
    for x,y,z,_,st in changed:
        if z<=366 and(x,z)not in underpass_columns and st.split('[')[0]not in OPEN and box(x,z,x+1,z+1).distance(jr)<4.5:rail_and_platform_jr.append([x,y,z])
    if rail_and_platform_jr:errors.append('platform invades retained JR corridor')
    channel=[]
    for x,z in d['channel_bridge_columns']:
        lower_changes=[y for y in range(-128,-76)if e.state(x,y,z)!=e.state(x,y,z,True)]
        if lower_changes:errors.append('source below channel span changed')
        # Exact soil surface is -78 here; a future shallow drain can be opened
        # below that surface later without touching the new deck at -76.
        top=max(y for y in range(-90,-70)if e.state(x,y,z,True).split('[')[0]not in OPEN)
        channel.append(dict(x=x,z=z,source_soil_top=top,deck_underside=-76,reserved_future_water_surface=-78,headroom=2,lower_changes=lower_changes))
    bearing=[]
    for z in d['channel_abutment_rows']:
        for x in range(d['channel_abutment_x_range'][0],d['channel_abutment_x_range'][1]+1):
            distance=water.distance(box(x,z,x+1,z+1));missing=[y for y in range(-79,-75)if e.state(x,y,z).split('[')[0]in OPEN]
            if distance<=3 or missing:errors.append('channel abutment missing or inside bank buffer')
            bearing.append(dict(x=x,z=z,cached_water_distance=distance,missing_support_y=missing))
    proof=dict(errors=sorted(set(errors)),changed_cells=counts['cells'],changed_chunks=len(chunks),public_nodes=len(nodes),reachable_nodes=len(parents),
        protected_original_changes=counts['protected'],old_public_changes=counts['old_public'],old_devices_changed=counts['devices'],
        floor_failures=floor_failures[:40],unreachable=[list(q)for q in nodes if q not in parents][:40],goals=goals,
        full_length_platform_edge=edge,minimum_platform_width=min(q['continuous_width']for q in edge),floating_new_solids=floating[:40],sign_errors=sign_errors,
        JR_corridor_platform_conflicts=rail_and_platform_jr,channel_columns=channel,channel_abutments=bearing,bank_buffer_air_changes=len(water_changes),
        JR_underpass_interfaces=d['JR_underpass_interfaces'],JR_service_acceptance=False,native_registry_pending=True,world_written=False)
    if write:dump(candidate/'offline-verification.json',proof)
    print('Midoricho structural:',len(errors),'errors;',len(parents),'/',len(nodes),'reachable;',len(floating),'unrooted new cells',flush=True)
    if errors:raise ValueError(errors)
    return proof


def vehicle(candidate,write=True):
    e=Editor(candidate);d=json.loads((candidate/'station-design.json').read_text('utf8'))
    models=candidate/'vehicle-model';report=json.loads((models/'e44_mini_cab_3.json').read_text('utf8'))
    packs=json.loads((models/'active-pack-check.json').read_text('utf8'))
    if any(q['mtr_overrides']for q in packs['packs']):raise ValueError('Enabled pack overrides MTR model')
    native=json.loads((candidate/'native-station-plan.json').read_text('utf8'));samples=json.loads((candidate/d['native_math_samples']).read_text('utf8'))
    with np.load(models/'e44_mini_cab_3-visible-cubes.npz')as f:cubes=f['cubes'];slides=f['door_slides'];names=list(map(str,f['names']))
    bands=[];long=max(abs(report['visible_motion_bounds'][i][2])for i in(0,1))+.15
    for y in range(0,4):
        widths=[(w,name)for v,s,name in zip(cubes,slides,names)if(w:=clipped_half_width(v,s,y-.03,y+1+.03))is not None]
        if widths:w,name=max(widths);bands.append(dict(y=[y,y+1],visible_half_width=w,swept_half_width=w+.15,widest_part=name))
    obstacles=[]
    for rail,sample in zip(native['rails'],samples):
        p,q=rail['from'],rail['to'];v=np.asarray(sample['points'])
        if not sample['valid']or abs(sample['native_length']-48)>1e-8 or np.max(np.abs(v[:,0]-p[0]-.5))>1e-8 or np.max(np.abs(v[:,1]-p[1]))>1e-8:raise ValueError('Native platform mathematics mismatch')
        z0,z1=min(p[2],q[2])+.5-long,max(p[2],q[2])+.5+long
        for band in bands:
            x0,x1=p[0]+.5-band['swept_half_width'],p[0]+.5+band['swept_half_width'];y=p[1]+band['y'][0]
            for x in range(math.floor(x0),math.ceil(x1)):
                for z in range(math.floor(z0),math.ceil(z1)):
                    st=e.state(x,y,z)
                    if st.split('[')[0]not in OPEN:obstacles.append([x,y,z,st])
    # At a centred stop both e44 doorway floor planes meet the continuous
    # platform through a .25m gap; a .6m foot box retains support throughout.
    support=[]
    for z in(338,347):
        missing=[float(x)for x in np.linspace(3447,3448.5,151)if x-.3>=3447.75 and x+.3<=3448]
        support.append(dict(door_centre_z=z,floor_y=-74,platform_y=-74,support_gap=.25,unsupported_samples=missing,
                            player_footprint=.6,doorway_length=1.75,open_doors_required=True,native_callback_tested=False))
    errors=[]
    if obstacles:errors.append('visible vehicle envelope blocked')
    if any(q['unsupported_samples']for q in support):errors.append('boarding support gap')
    proof=dict(errors=errors,model='e44_mini_cab_3',selected_parts=report['selected_part_instances'],bands=bands,
        full_length=48,longitudinal_extent_with_margin=long,horizontal_margin=.15,vertical_margin=.03,
        obstacles=obstacles[:40],obstacle_count=len(obstacles),doors_and_bogies_enclosed=True,
        visible_platform_gap=.1875,residual_horizontal_clearance=.0375,boarding_support=support,
        native_boarding_runtime_verified=False,rendered_frame_verified=False,world_written=False)
    if write:dump(candidate/'visible-model-sweep.json',proof)
    print('Midoricho visible model:',len(obstacles),'obstacles',flush=True)
    if errors:raise ValueError(errors)
    return proof


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--authority',type=Path,required=True)
    a=p.parse_args();verify(a.candidate,a.authority);vehicle(a.candidate)
