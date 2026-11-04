"""Separate the two native ropeway loops vertically and rebuild finite access.

This edits a current captured candidate only. Original neighbours, furnishings,
inventories and scheduled vehicles remain intact. Eight native node blocks
follow the independently prepared seven-metre eastern terminal translation.
"""
import argparse,copy,json,math,os,shutil
from pathlib import Path
from collections import Counter
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL,PLANTS
from verify_hakone_network_candidate import PAVEMENT
from hakone_earthworks import road_blocks
from repair_hakone_underbridge_clearance import save,health
from verify_hakone_cable_station import CabinReserve,journeys
from map_pipeline.rail_civil_geometry import block_top
from map_pipeline.native_geometry_patch import expected
from map_pipeline.launch_protection import load,check_candidate
from install_r53_carrier_trays import stopped_world

STONE='minecraft:stone_bricks';PAVE='minecraft:smooth_stone';SLAB='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
CONCRETE='minecraft:light_gray_concrete';GLASS='minecraft:light_gray_stained_glass'
BARS_X='minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'
BARS_Z='minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]'

def build(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);bounds=cap['bounds_xz'];x,z,X,Z=bounds
    if bounds!=[112,656,351,943]or cap['actors']or cap['unavailable_chunks']:raise ValueError('Current FULL actor-free station capture required')
    with np.load(a.authority/'network.npz')as f:g={k:f[k]for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[ar].copy()if k!='bounds'else np.array(bounds))for k,v in g.items()};old={k:v.copy()for k,v in d.items()};del g
    a.out.mkdir(exist_ok=False)
    for name in('source','delta','plan'):(a.out/name).mkdir()
    for f in(a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    shutil.copy2(a.profiles/'native-curves.json',a.out/'plan/native-curves.json')
    shutil.copy2(a.authority/'catalog.json',a.out/'plan/catalog.json')
    for name in('buildings.json','footways.json'):save(a.out/'plan'/name,[])
    shutil.copytree(a.native_candidate/'native-geometry',a.out/'native-geometry')
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices=dict(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    e=Editor(a.out);catalog=json.loads((a.authority/'catalog.json').read_text('utf8'));guard=load(world);guard_cache={}
    curves=json.loads((a.profiles/'native-curves.json').read_text('utf8'));reserve=CabinReserve(curves,[250,804,300,854])
    proposed={};reasons={};node_moves=json.loads((a.profiles/'proposal.json').read_text('utf8'))['moves'];node_positions=set()
    def put(px,y,pz,state,kind):
        p=int(px),int(y),int(pz);proposed[p]=state;reasons[p]=kind
    def fill(box,state,kind):
        xx,yy,zz,XX,YY,ZZ=box
        for px in range(xx,XX+1):
            for pz in range(zz,ZZ+1):
                for y in range(yy,YY+1):put(px,y,pz,state,kind)
    def current(p):return proposed.get(p,e.state(*p))
    # Retain the lower concourse and its two shops. Replace only the old stair
    # that climbed through the western cabin path, closing its original void.
    fill([263,179,830,265,179,842],PAVE,'restored lower concourse aisle')
    fill([263,180,830,265,182,842],'minecraft:air','retired unsafe original stair')
    fill([263,183,830,265,184,842],STONE,'closed original stair opening')
    fill([263,185,830,265,185,842],PAVE,'continuous western platform outside cabin slots')
    # A narrow northern annex accommodates two stacked dog-leg staircases.
    # It stops four metres short of the original northern inhabited parcel.
    for px in range(259,286):
        for pz in range(809,817):
            soil_y=next(y for y in range(178,100,-1)if e.state(px,y,pz).split('[')[0]in SOIL)
            fill([px,min(175,soil_y+1),pz,px,178,pz],STONE,'annex foundation tied to measured ridge')
    fill([259,179,809,285,179,816],PAVE,'annex lower floor')
    fill([259,180,809,285,199,816],'minecraft:air','stair annex interior')
    for y in(185,192):fill([259,y,809,285,y,816],PAVE,'annex landing floor')
    for xx in(259,285):fill([xx,180,809,xx,199,816],CONCRETE,'annex outer wall')
    fill([259,180,809,285,199,809],CONCRETE,'annex north retaining facade')
    for yy in(181,187,194):
        fill([261,yy,809,283,yy+2,809],GLASS,'annex north glazing')
        for xx in(259,285):fill([xx,yy,811,xx,yy+2,814],GLASS,'annex side glazing')
    # Three-wide doorway on each floor joins the original hall. The eastern
    # upper floor is new and continues above the west terminal's clear roof.
    for base in(179,185,192):fill([261,base+1,817,263,base+3,817],'minecraft:air','annex station connection')
    stair_treads=[]
    def tread(px,pz,standing_y,width_axis):
        h=math.ceil(standing_y)-1;state=SLAB if standing_y%1 else PAVE
        for cross in range(-1,2):
            xx,zz=(px,pz+cross)if width_axis=='z'else(px+cross,pz)
            put(xx,h-1,zz,STONE,'continuous stair stringer');put(xx,h,zz,state,'half-step stair tread')
            for yy in range(h+1,math.ceil(standing_y+2.5)):put(xx,yy,zz,'minecraft:air','stair headroom')
            stair_treads.append([xx,h,zz])
    for base,rise in((179,6),(185,7)):
        steps=rise;mid_stand=base+1+rise/2
        for k in range(steps):
            xx=270-steps+k;tread(xx,811,base+1+(k+1)*.5,'z')
            xx=269-k;tread(xx,815,mid_stand+(k+1)*.5,'z')
        h=math.ceil(mid_stand)-1;state=SLAB if mid_stand%1 else PAVE
        fill([270,h-1,810,272,h-1,816],STONE,'turning landing bearing')
        fill([270,h,810,272,h,816],state,'three-wide turning landing')
        fill([270,h+1,810,272,math.ceil(mid_stand+2.5)-1,816],'minecraft:air','turning landing headroom')
        # Solid central spine and bars keep both opposing flights separate.
        fill([263,base+1,813,269,base+rise,813],CONCRETE,'stair spine')
        fill([273,h,810,273,h+2,816],CONCRETE,'midlanding outside parapet')
    # The east terminal is seven metres above the west terminal. Its main deck
    # doubles as the west hall roof, with all native sweep slots cut afterwards.
    footprint={(px,pz)for px in range(259,286)for pz in range(816,845)}
    footprint|={(px,pz)for px in range(286,295)for pz in range(821,838)}
    for px,pz in footprint:
        for yy in range(191,201):
            if current((px,yy,pz)).startswith('mtr:'):continue
            put(px,yy,pz,'minecraft:air','retired roof and new upper terminal interior')
        put(px,192,pz,PAVE,'eastern terminal floor')
        put(px,200,pz,CONCRETE,'continuous terminal roof')
        # Keep the eastern platform extension independently grounded; its
        # bearings are outside both cable paths and original neighbouring home.
        if px>=286 and pz in(827,837):
            for yy in range(179,192):put(px,yy,pz,CONCRETE,'eastern terminal edge girder')
    for yy in range(193,200):
        for px in range(260,285):
            for pz in(817,843):put(px,yy,pz,GLASS if 194<=yy<=197 else CONCRETE,'eastern terminal enclosure')
        for pz in range(818,843):
            for px in(260,284):
                if px==284 and 821<=pz<=837:continue
                put(px,yy,pz,GLASS if 194<=yy<=197 else CONCRETE,'eastern terminal enclosure')
    # Connect the upper annex after installing the upper main enclosure.
    fill([261,193,817,263,195,817],'minecraft:air','upper annex station doorway')
    fill([259,200,809,285,200,816],CONCRETE,'annex roof')
    # The original side-wall piers remain tied to a continuous perimeter beam
    # below the new west-hall roof. Clearance openings are trimmed afterwards.
    for px in(260,284):fill([px,191,817,px,191,843],CONCRETE,'retained wall piers tied to roof ring')
    for pz in(817,843):fill([260,191,pz,284,191,pz],CONCRETE,'roof perimeter ring')
    # Finite east support piers terminate in retained soil, never on an old
    # floating paving remnant or inside either ropeway's swept volume.
    for px,pz in((292,827),(292,837),(286,837)):
        soil_y=next(y for y in range(178,150,-1)if e.state(px,y,pz).split('[')[0]in SOIL)
        for yy in range(soil_y+1,192):put(px,yy,pz,CONCRETE,'east platform grounded pier')
    # Keep original native node states, changing only the declared eight Y
    # coordinates. Native connections and full owner tokens are patched apart.
    for row in node_moves:
        p,q=map(tuple,(row['before'],row['after']));s=e.state(*p)
        if not s.startswith('mtr:cable_car_node_')or e.state(*q).split('[')[0]not in AIR:raise ValueError(('Native node move precondition',p,q))
        node_positions|={p,q};put(*p,'minecraft:air','declared east native node source');put(*q,s,'declared east native node destination')
        put(q[0],q[1]+1,q[2],CONCRETE,'native east guide overhead bearing to roof')
    for pz in(825,833):fill([258,192,pz,259,192,pz],CONCRETE,'western guide edge bearing tied to terminal roof')
    # Resolve full-block platform/roof/wall clashes against the actual cabin
    # envelope. Floor slots use bottom slabs, retaining a continuous bearing.
    clearance_box=[256,180,809,296,201,845]
    for px in range(256,297):
        for pz in range(809,846):
            for yy in range(180,202):
                p=px,yy,pz;s=current(p)
                if s.split('[')[0]in AIR|{'minecraft:light'}or s.startswith('mtr:'):continue
                if not reserve.block(p,s):continue
                if not((259<=px<=285 and 816<=pz<=844)or(286<=px<=294 and 821<=pz<=837)):
                    raise ValueError(('Cabin hits retained neighbouring object',p,s))
                if yy in(185,192)and not reserve.block(p,SLAB):put(*p,SLAB,'recessed cabin sweep floor')
                else:put(*p,'minecraft:air','continuous native cabin clearance')
    # Existing ceiling lights that occupied the cabin path are recessed into
    # the new structural ceiling, retaining the station lighting programme.
    for px in range(259,286):
        for pz in range(816,845):
            if e.state(px,190,pz)=='minecraft:sea_lantern':put(px,190,pz,'minecraft:air','retired old ceiling light position')
    for p,s in list(proposed.items()):
        if e.state(*p)=='minecraft:sea_lantern'and s!='minecraft:sea_lantern':
            target=192 if not reserve.block((p[0],192,p[2]),'minecraft:sea_lantern')else 200
            put(p[0],target,p[2],'minecraft:sea_lantern','relocated recessed station light')
    # Guard the exposed outer edges of the upper eastern boarding wing.
    for px in range(285,295):
        for yy in(193,194):put(px,yy,837,CONCRETE if yy==193 else BARS_X,'east terrace outer guardrail')
    for pz in range(821,837):
        for yy in(193,194):
            if not reserve.block((294,yy,pz),CONCRETE):put(294,yy,pz,CONCRETE if yy==193 else BARS_Z,'east terminal edge beside cable openings')
    fragments=json.loads((a.profiles.parent/'south-ropeway-station-survey-v1/finite-floating-road-fragments.json').read_text('utf8'))
    for row in fragments:
        p=tuple(row['pos']);j,i=p[2]-z,p[0]-x
        if e.state(*p)!=row['state']or row['state'].split('[')[0]not in PAVEMENT:raise ValueError(('Old fragment changed',p))
        if old['walk'][j,i]and abs(old['grade2'][j,i]/2-p[1])<4:raise ValueError(('Fragment belongs to retained route',p))
        if p not in proposed:put(*p,'minecraft:air','finite disconnected obsolete road fragment')
    # Finite stairwell guardrails: outside the six-metre-clear public landings.
    for base in(185,192):
        for px in range(263,270):
            if current((px,base,810)).split('[')[0]in AIR:put(px,base+1,809,BARS_X,'stairwell north guard')
    # Retire only the abandoned northern path into the previously closed wall.
    # Its original house forecourt and all real streets retain their grades.
    retired=np.zeros(d['walk'].shape,bool)
    for px in range(259,286):
        for pz in range(809,817):
            j,i=pz-z,px-x
            if old['walk'][j,i]:
                if old['road'][j,i]or old['grade2'][j,i]>=360:raise ValueError(('Annex conflicts with retained street',px,pz))
                retired[j,i]=True
    for key in('walk','road','marking','tunnel'):d[key][retired]=False
    # Preserve every complete device and all original furnishings. Only known
    # station structural materials can be changed inside the finite envelope.
    ordinary=AIR|SOIL|PAVEMENT|PLANTS|{STONE,CONCRETE,GLASS,'minecraft:white_concrete','minecraft:yellow_concrete','minecraft:light','minecraft:glass_pane','minecraft:iron_bars','minecraft:polished_andesite','minecraft:sea_lantern'}
    edits=[]
    for p,s in proposed.items():
        before=e.state(*p)
        if before==s:continue
        if p in devices:raise ValueError(('Original device changed',p))
        key=p[0]//16,p[2]//16
        if key not in guard_cache:guard_cache[key]=guard.chunk_mask(*key)
        if guard_cache[key][p[1]+128,p[2]%16,p[0]%16]:raise ValueError(('Launch protection',p))
        for row in catalog:
            b=row['occupied_bounds']
            if all(b[k]<=p[k]<=b[k+3]for k in range(3)):raise ValueError(('Neighbouring parcel changed',row['id'],p))
        if before.split('[')[0]not in ordinary and p not in node_positions:raise ValueError(('Original furnishing/unknown structure',p,before))
        if s.split('[')[0]not in AIR and not s.startswith('mtr:')and reserve.block(p,s):raise ValueError(('New cabin obstruction',p,s))
        e.put(*p,s);edits.append(dict(pos=list(p),before=before,after=s,kind=reasons[p]))
    patches=e.save();e.regions.clear();e=Editor(a.out)
    d['old_ground']=old['ground'].copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    np.savez_compressed(a.out/'finite-authority.npz',bounds=bounds,retired=retired,editable=retired,before_grade2=old['grade2'],before_walk=old['walk'])
    goals={'street':[278,179,853],'concourse':[272,180,840],'west north platform':[264,186,821],'west south platform':[264,186,837],'east north platform':[282,193,820],'east south platform':[286,193,835]}
    report=journeys(e,reserve,goals,[256,174,806,296,198,861]);errors=report['errors']
    before=Counter();after=Counter()
    for j,i in np.argwhere(old['walk']&~retired):
        h,slab=road_blocks(old['grade2'][j,i]);p=int(x+i),int(z+j);aa=health(e,p,int(h),slab,bool(old['road'][j,i]),True);bb=health(e,p,int(h),slab,bool(old['road'][j,i]))
        for k,name in enumerate(('floor','headroom')):
            before[name]+=not aa[k];after[name]+=not bb[k]
            if aa[k]and not bb[k]:errors.append(['retained public defect',name,*p])
    for p in devices:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['device changed',*p])
    for row in node_moves:
        p,q=map(tuple,(row['before'],row['after']))
        if e.state(*q)!=e.state(*p,original=True)or e.state(*p).startswith('mtr:'):errors.append(['native block migration mismatch',p,q])
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=bounds,regions=patches,cells=sum(r['cells']for r in patches),world_written=False,preserve_native_members=True,native_geometry_patch='native-geometry/operations.json'))
    _,native_proof=expected(a.out)
    result=dict(errors=errors,cells=sum(r['cells']for r in patches),devices_preserved=len(devices),native_nodes_lifted=len(node_moves),native_geometry_requires_verified_migration=True,native=native_proof,retired_obsolete_path_columns=int(retired.sum()),retained_public_before=dict(before),retained_public_after=dict(after),whole_map_complete=False)
    for name,data in [('functional-check.json',result),('independent-check.json',result),('cable-station-access-check.json',report),('street-journeys.json',report['journeys']),('station-edits.json',edits),('station-design.json',dict(goals=goals,clearance_box=clearance_box,native_lift=7,levels=[179,185,192],roof=200,stair_treads=stair_treads)),('launch-protection.json',check_candidate(guard,a.out))]:save(a.out/name,data)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Station candidate did not pass')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','profiles','native-candidate','out'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
