"""Connect the retained lower South Ward concourse to the surface street.

An enclosed sixteen-flight staircase replaces the disconnected buried western
road remnants. Original station rooms, devices, rails and actors stay intact.
"""
import argparse,json,os,shutil
from pathlib import Path
from collections import Counter
import numpy as np
import nbtlib
from scipy.ndimage import label,binary_dilation
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL,PLANTS
from verify_hakone_network_candidate import PAVEMENT
from hakone_earthworks import road_blocks
from repair_hakone_underbridge_clearance import save,health
from repair_hakone_fixture_bearings import reserves,conflict
from map_pipeline.launch_protection import load,check_candidate
from install_r53_carrier_trays import stopped_world
from verify_hakone_station_connection import verify as verify_access
from prepare_hakone_city_cross import packed


def build(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);bounds=cap['bounds_xz'];x,z,X,Z=bounds
    if bounds!=[112,656,351,943] or cap['actors'] or cap['unavailable_chunks']:raise ValueError('Requires measured full South Ward station capture')
    with np.load(a.authority/'network.npz')as f:g={k:f[k]for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[ar].copy()if k!='bounds'else np.array(bounds))for k,v in g.items()};del g
    old={k:v.copy() for k,v in d.items()}
    with np.load(a.source/'measured.npz')as f:soil=f['top']
    buried=d['walk']&(d['grade2']<300)&(soil-d['grade2']/2>12)
    groups,n=label(buried,np.ones((3,3),int));chosen={int(groups[Z0-z,X0-x])for X0,Z0 in [(152,765),(156,805),(156,830)]}
    if 0 in chosen:raise ValueError('Reviewed old western approach no longer exists')
    retired=np.isin(groups,list(chosen));jj,ii=np.nonzero(retired)
    if len(ii)!=250 or ii.min()+x<150 or ii.max()+x>157 or jj.min()+z<708 or jj.max()+z>836:raise ValueError('Retirement differs from finite western approach survey')
    if any(retired[k].any()for k in (0,-1))or retired[:,[0,-1]].any():raise ValueError('Cannot retire a cropped route')
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'))
    for row in catalog:
        p=row.get('approach',row.get('door'))
        if p and x<=p[0]<=X and z<=p[2]<=Z:
            i,j=round(p[0])-x,round(p[2])-z
            if retired[max(0,j-3):j+4,max(0,i-3):i+4].any() and p[1]<150:raise ValueError(('Retired approach serves a catalogued low destination',row['id']))
    a.out.mkdir(exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    shutil.copy2(a.authority/'native-curves.json',a.out/'plan/native-curves.json')
    save(a.out/'plan/catalog.json',catalog);save(a.out/'plan/footways.json',[])
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices=dict(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    e=Editor(a.out);guard=load(world);env=reserves(a.authority,bounds);proposals={};reason={};retirement_cells=[]
    def put(px,y,pz,state,kind):
        p=(int(px),int(y),int(pz));proposals[p]=state;reason[p]=kind
    def fill(box,state,kind):
        xx,yy,zz,XX,YY,ZZ=box
        for px in range(xx,XX+1):
            for pz in range(zz,ZZ+1):
                for y in range(yy,YY+1):put(px,y,pz,state,kind)
    # Restore only the measured old street layer and its small air clearance;
    # retain every station room, roof and all higher surface neighbourhoods.
    for j,i in np.argwhere(retired):
        px,pz=int(i+x),int(j+z);h,_=road_blocks(d['grade2'][j,i]);h=int(h)
        for y in range(h-1,h+5):
            s=e.state(px,y,pz);bare=s.split('[')[0]
            if bare not in AIR|SOIL|PAVEMENT|{'minecraft:light'}:raise ValueError(('Buried approach contains retained object',px,y,pz,s))
            if bare in PAVEMENT or bare in AIR|{'minecraft:light'}:
                put(px,y,pz,'minecraft:stone','retired superseded western road');retirement_cells.append([px,y,pz])
    for key in ('walk','road','marking','tunnel'):d[key][retired]=False
    # Main reinforced enclosure. Its large vertical interior is separated by
    # a solid central core and alternating supported flights and landings.
    fill([149,79,759,159,165,777],'minecraft:light_gray_concrete','enclosed station stairwell')
    fill([150,81,760,158,164,776],'minecraft:air','stairwell interior')
    fill([153,80,763,155,160,772],'minecraft:light_gray_concrete','continuous central stair core')
    fill([150,80,760,158,80,776],'projectseele:period_station_floor','lower concourse landing')
    steps=[];landings=[]
    for flight in range(16):
        base=80+flight*5;ascending_south=flight%2==0;xa,xb=(150,152)if ascending_south else(156,158)
        for k in range(10):
            pz=763+k if ascending_south else 772-k;y=base+k//2+1
            fill([xa,y-1,pz,xb,y-1,pz],'minecraft:stone_bricks','continuous stair stringer')
            tread='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if k%2==0 else'minecraft:smooth_stone'
            fill([xa,y,pz,xb,y,pz],tread,'half-step concourse access flight')
            steps.extend((px,y,pz)for px in range(xa,xb+1))
        zlo,zhi=(773,776)if ascending_south else(760,762);level=base+5
        fill([150,level,zlo,158,level,zhi],'projectseele:period_station_floor','turning landing');landings.append([150,level,zlo,158,level,zhi])
        put(149 if ascending_south else 159,level+3,(zlo+zhi)//2,'minecraft:sea_lantern','embedded landing light')
    # At the surface, a western corridor passes the open final stair flight.
    fill([150,160,763,155,160,776],'projectseele:period_station_floor','surface lobby floor')
    fill([156,160,773,158,160,776],'projectseele:period_station_floor','surface lobby floor')
    # Guard the open stairwell on the upper lobby. Its only entry is the
    # northern landing at the matching height, with no shortcut over a drop.
    fill([155,161,764,155,162,773],'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]','upper stairwell guardrail')
    fill([156,161,773,158,162,773],'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]','upper stairwell guardrail')
    # Three-metre clear lower passage joins the existing station floor at X163.
    fill([159,79,759,162,84,763],'minecraft:light_gray_concrete','lined station connection')
    fill([159,80,760,162,80,762],'projectseele:period_station_floor','station passage floor')
    fill([159,81,760,163,83,762],'minecraft:air','station passage clearance')
    put(161,84,761,'minecraft:sea_lantern','recessed passage light')
    # Surface entrance: a restrained glazed concrete headhouse and green band.
    fill([150,161,777,152,163,777],'minecraft:air','surface entrance opening')
    for px in (149,159):fill([px,162,762,px,163,774],'projectseele:clear_glass','headhouse glazing')
    fill([154,162,777,157,163,777],'projectseele:clear_glass','front glazing')
    fill([149,164,777,159,164,777],'minecraft:green_concrete','station entrance band')
    fill([148,165,758,160,165,778],'minecraft:light_gray_concrete','entrance canopy')
    sign_pos=(154,164,778)
    put(*sign_pos,'minecraft:oak_wall_sign[facing=south,waterlogged=false]','station entrance identification')
    # Keep the current road and its half-height sidewalk. Only the new approach
    # apron is laid between it and the headhouse.
    for px in range(150,153):
        for pz in range(778,786):
            for y in range(158,160):put(px,y,pz,'minecraft:stone','apron bearing')
            state='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if pz==785 else'minecraft:smooth_stone'
            put(px,160,pz,state,'headhouse approach')
            for y in (161,162,163):put(px,y,pz,'minecraft:air','approach pedestrian clearance')
    # Reject unknown structures and native devices before any candidate write.
    ordinary=AIR|SOIL|PAVEMENT|PLANTS|{'minecraft:light','minecraft:light_gray_concrete'}
    for p,state in proposals.items():
        current=e.state(*p)
        if state==current:continue
        if p in devices or guard.chunk_mask(p[0]//16,p[2]//16)[p[1]+128,p[2]%16,p[0]%16]:raise ValueError(('Native device or launch volume',p,current))
        if current.split('[')[0] not in ordinary:raise ValueError(('Retained structure in access footprint',p,current,reason[p]))
        if conflict(p,env):raise ValueError(('Native transport reserve',p,conflict(p,env)))
        for row in catalog:
            b=row['occupied_bounds']
            if all(b[k]<=p[k]<=b[k+3]for k in range(3)):raise ValueError(('Existing parcel changed',row['id'],p))
        j,i=p[2]-z,p[0]-x
        if old['walk'][j,i] and not retired[j,i]:
            h,_=road_blocks(old['grade2'][j,i]);h=int(h)
            if h-2<=p[1]<=h+(4 if old['road'][j,i]else 2):raise ValueError(('Retained street bearing or body changed',p))
        e.put(*p,state)
    patches=e.save();e.regions.clear();e=Editor(a.out)
    def sign_text(lines,colour):
        return nbtlib.Compound({'color':nbtlib.String(colour),'has_glowing_text':nbtlib.Byte(1),'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':line},ensure_ascii=False))for line in lines])})
    sign=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(sign_pos[0]),'y':nbtlib.Int(sign_pos[1]),'z':nbtlib.Int(sign_pos[2]),'is_waxed':nbtlib.Byte(1),
        'front_text':sign_text(['南部地区','地下駅入口','CONCOURSE','TOKYO-3'],'white'),'back_text':sign_text(['','','',''],'black')})
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'Pos':nbtlib.Long(packed(sign_pos)),'After':sign})])}).save(a.out/'block-entities.dat',gzipped=True)
    # Add only actually walkable surface lobby/apron cells to the 2D network.
    # The stacked underground path has its own full 3D acceptance record.
    for px in range(150,159):
        for pz in range(760,786):
            s=e.state(px,160,pz)
            if s.split('[')[0] not in PAVEMENT|{'projectseele:period_station_floor'}:continue
            if any(e.state(px,y,pz).split('[')[0] not in AIR for y in (161,162)):continue
            j,i=pz-z,px-x
            if old['walk'][j,i] and not retired[j,i]:continue
            d['walk'][j,i]=True;d['road'][j,i]=False;d['marking'][j,i]=False;d['tunnel'][j,i]=False;d['grade2'][j,i]=319 if 'type=bottom'in s else 320
    d['old_ground']=d['ground'].copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    np.savez_compressed(a.out/'retired-western-approach.npz',bounds=bounds,retired=retired,grade2=old['grade2'],road=old['road'])
    station=dict(id='south-ward-surface-concourse-access',kind='station',station_id='南部车站地面联络口',approach=[151,160.5,786],platform=[164,80,761],maximum_step_height=.5,destination_type='existing lower concourse',occupied_bounds=[148,79,758,163,165,778])
    save(a.out/'plan/buildings.json',[station]);save(a.out/'access-design.json',dict(station=station,flights=16,vertical_rise=80,flight_rise=5,step_rise=.5,clear_width=3,landings=landings,retired_columns=int(retired.sum()),retirement_cells=retirement_cells,shaft=[149,79,759,159,165,777],native_geometry_unchanged=True))
    errors=[];before=Counter();after=Counter()
    for j,i in np.argwhere(old['walk']):
        h,slab=road_blocks(old['grade2'][j,i]);p=int(i+x),int(j+z);a0=health(e,p,int(h),slab,bool(old['road'][j,i]),True)
        if retired[j,i]:continue
        b0=health(e,p,int(h),slab,bool(old['road'][j,i]))
        for k,name in enumerate(('floor','headroom')):
            before[name]+=not a0[k];after[name]+=not b0[k]
            if a0[k] and not b0[k]:errors.append(['retained public regression',name,*p])
    new_public=0
    for j,i in np.argwhere(d['walk']&(~old['walk']|retired)):
        h,slab=road_blocks(d['grade2'][j,i]);p=int(i+x),int(j+z);new_public+=1
        if not all(health(e,p,int(h),slab,False)):errors.append(['new surface access obstructed',*p])
    for px,y,pz in steps:
        if e.state(px,y-1,pz)!='minecraft:stone_bricks':errors.append(['stair lacks continuous bearing',px,y,pz])
        if any(e.state(px,Y,pz).split('[')[0]not in AIR for Y in (y+1,y+2)):errors.append(['stair headroom',px,y,pz])
    for p in devices:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['device altered',*p])
    if nbtlib.load(a.out/'block-entities.dat')['Changes'][0]['After']!=sign:errors.append(['new station sign NBT changed'])
    for j,i in np.argwhere(retired & ~d['walk']):
        h,_=road_blocks(old['grade2'][j,i])
        px,pz,h=int(i+x),int(j+z),int(h)
        # A new solid shaft wall can use a material also accepted as pavement;
        # only a remaining clear standing surface is a legacy road remnant.
        if (px,h,pz)not in steps and e.state(px,h,pz).split('[')[0]in PAVEMENT and all(e.state(px,Y,pz).split('[')[0]in AIR for Y in (h+1,h+2)):
            errors.append(['retired pavement persists',px,pz])
    result=verify_access(a.out);errors.extend(result['errors'])
    for journey in result['stations']:
        route=journey['path']
        if any(abs(p[1]-q[1])>.5 for p,q in zip(route,route[1:])):errors.append(['access still requires a whole-block jump'])
    report=dict(errors=errors,cells=sum(p['cells']for p in patches),retired_disconnected_road_columns=int(retired.sum()),new_surface_access_columns=new_public,flights=16,step_cells_checked=len(steps),devices_unchanged=len(devices),retained_public_before=dict(before),retained_public_after=dict(after),station_to_surface_connected=not result['errors'],native_geometry_unchanged=True,whole_map_complete=False)
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=bounds,regions=patches,cells=report['cells'],preserve_native_members=True,world_written=False))
    save(a.out/'functional-check.json',report);save(a.out/'independent-check.json',report);save(a.out/'launch-protection.json',check_candidate(guard,a.out));print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('South station access verification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','authority','out'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
