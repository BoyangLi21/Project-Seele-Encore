"""Restore the retained west tunnel and its original native moving walks.

The finite feeder joins measured roads at both ends. The obsolete steep spur
is retired; the through ridge road, original native devices and houses stay.
"""
import argparse,json,math,os,shutil
from pathlib import Path
from collections import Counter,deque
import numpy as np
import nbtlib
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import binary_dilation,distance_transform_edt
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL,PLANTS
from verify_hakone_network_candidate import PAVEMENT
from repair_hakone_underbridge_clearance import save,health
from repair_hakone_south_station_streets import journey
from repair_hakone_fixture_bearings import reserves,conflict
from map_pipeline.launch_protection import load,check_candidate
from install_r53_carrier_trays import stopped_world

CONCRETE='minecraft:light_gray_concrete';STONE='minecraft:stone_bricks'
PAVE='minecraft:smooth_stone';SLAB='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
BARS='minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'


def build(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);bounds=cap['bounds_xz'];x,z,X,Z=bounds
    if bounds!=[-1168,240,-689,383]or cap['actors']or cap['unavailable_chunks']:raise ValueError('Current FULL actor-free west tunnel capture required')
    with np.load(a.authority/'network.npz')as f:g={k:f[k]for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[ar].copy()if k!='bounds'else np.array(bounds))for k,v in g.items()};old={k:v.copy()for k,v in d.items()};del g
    a.out.mkdir(exist_ok=False)
    for name in('source','delta','plan'):(a.out/name).mkdir()
    for f in(a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    for name in('catalog.json','native-curves.json'):shutil.copy2(a.authority/name,a.out/'plan'/name)
    for name in('buildings.json','footways.json'):save(a.out/'plan'/name,[])
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices=dict(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    e=Editor(a.out);guard=load(world);guard_cache={};catalog=json.loads((a.authority/'catalog.json').read_text('utf8'));envelopes=reserves(a.authority,bounds)
    proposed={};reasons={};soil_cache={}
    def soil(px,pz):
        if(px,pz)not in soil_cache:soil_cache[px,pz]=next(y for y in range(170,40,-1)if e.state(px,y,pz).split('[')[0]in SOIL)
        return soil_cache[px,pz]
    def put(px,y,pz,state,kind):p=int(px),int(y),int(pz);proposed[p]=state;reasons[p]=kind
    def fill(px,lo,pz,hi,state,kind):
        for y in range(lo,hi+1):put(px,y,pz,state,kind)
    # A gradual branch reaches the existing gallery without forcing vehicles
    # down the obsolete hillside spur's one-half-metre-per-block staircase.
    anchors=np.array([[-1084,310],[-1074,307],[-1060,296],[-1040,291],[-1014,291],[-990,291],[-950,292],[-914,300],[-891,308],[-872,308],[-786,308],[-775,310],[-740,315]],float)
    curve=PchipInterpolator(anchors[:,0],anchors[:,1]);xs=np.arange(-1084,-739);zs=curve(xs)
    level_points=np.array([[-1084,99.5],[-1071,99.5],[-1058,100.5],[-1040,101],[-1014,102],[-990,102],[-950,100.5],[-914,99],[-891,98],[-786,98],[-775,97.5],[-740,97]],float)
    heights=PchipInterpolator(level_points[:,0],level_points[:,1])(xs)
    length=np.r_[0,np.cumsum(np.hypot(np.diff(xs),np.diff(zs)))];slope=np.max(np.abs(np.diff(heights))/np.diff(length))
    if slope>.12:raise ValueError(('Feeder continuous grade too steep',slope))
    roadway={};centre=[];joins=set()
    for px,pz,grade in zip(xs,zs,heights):
        px=int(px);zc=int(round(pz));h2=int(round(grade*2));half=9 if -891<=px<=-775 else 6
        centre.append([px,grade,pz])
        for pzz in range(zc-half,zc+half+1):
            j,i=pzz-z,px-x;native=-872<=px<=-786 and pzz in(301,302,314,315);divider=-872<=px<=-786 and pzz in(303,313)
            if native or divider:continue
            local=h2
            # Original endpoint junction cells are immutable; new width blends
            # into their measured half-step crossfall before the branch forks.
            if old['walk'][j,i]and(px<=-1068 or px>=-741):
                local=int(old['grade2'][j,i]);joins.add((px,pzz))
            road=abs(pzz-zc)<=4
            roadway[px,pzz]=dict(grade2=local,road=road,centre=zc,covered=(-1006<=px<=-929 or -872<=px<=-786))
    # Retire only this dead hillside spur, retaining the separate through ridge
    # road and every catalogue approach. Its successor joins both regional roads.
    retired=np.zeros(d['walk'].shape,bool)
    for px in range(-912,-836):
        main_z=331+(px+900)*.13
        for pz in range(287,340):
            j,i=pz-z,px-x
            if old['walk'][j,i]and abs(pz-main_z)>7 and(px,pz)not in roadway:retired[j,i]=True
    for row in catalog:
        p=row.get('approach',row.get('door'))
        if p and x<=p[0]<=X and z<=p[2]<=Z:
            if retired[max(0,p[2]-z-3):p[2]-z+4,max(0,p[0]-x-3):p[0]-x+4].any():raise ValueError(('Retired spur serves a retained building',row['id']))
    for key in('walk','road','marking','tunnel'):d[key][retired]=False
    for j,i in np.argwhere(retired):
        px,pz=int(i+x),int(j+z);h,_=road_blocks(old['grade2'][j,i]);h=int(h)
        if e.state(px,h,pz).split('[')[0]in PAVEMENT:
            put(px,h,pz,'minecraft:grass_block[snowy=false]','retired disconnected steep spur surface')
            if e.state(px,h-1,pz).split('[')[0]in AIR:fill(px,max(soil(px,pz)+1,h-3),pz,h-1,'minecraft:dirt','retired spur soil contact')
    structural=set();footings=[];native=[]
    span_x={px for(px,pz),r in roadway.items()if px<-891 and not r['covered']and int(road_blocks(r['grade2'])[0])-soil(px,pz)>8}
    # Make each deep-valley section a full-width deck. Neighbouring columns
    # share it even where the old approach bank rises beneath only one lane.
    span_x={q for px in span_x for q in range(px-2,px+3)if -1084<=q<-891}
    for px in range(-872,-785):
        for pz in(301,302,314,315):
            p=px,98,pz;s=e.state(*p)
            if not s.startswith('mtr:escalator_step'):raise ValueError(('Original moving walk missing',p,s))
            native.append(dict(pos=list(p),state=s));fill(px,99,pz,105,'minecraft:air','retained native moving walk headroom')
            for y in(96,97):put(px,y,pz,STONE,'retained moving walk bearing')
    for(px,pz),row in roadway.items():
        j,i=pz-z,px-x;h,slab=road_blocks(row['grade2']);h=int(h)
        if(px,pz)in joins:
            row['road']=row['road']or bool(old['road'][j,i])
            if not all(health(e,(px,pz),h,slab,row['road'])):raise ValueError(('Endpoint is not usable original pavement',px,pz,h))
        pavement=('projectseele:road_marking_slab'if abs(pz-row['centre'])==4 or(pz==row['centre']and px%12<5)else'projectseele:road_asphalt_slab')+'[type=bottom,waterlogged=false]'if slab and row['road']else SLAB if slab else('minecraft:white_concrete'if abs(pz-row['centre'])==4 or(pz==row['centre']and px%12<5)else'minecraft:black_concrete')if row['road']else PAVE
        if(px,pz)in joins and row['road']:pavement='projectseele:road_asphalt_slab[type=bottom,waterlogged=false]'if slab else'minecraft:black_concrete'
        ground=soil(px,pz)
        if h-ground>8 and px not in span_x:raise ValueError(('Covered feeder lacks measured hillside',px,pz,h,ground))
        if px in span_x:
            for yy in(h-2,h-1):put(px,yy,pz,CONCRETE,'full-width valley bridge deck');structural.add((px,yy,pz))
            if abs(pz-row['centre'])<=3:
                put(px,h-3,pz,CONCRETE,'continuous valley bridge box girder');structural.add((px,h-3,pz))
        else:fill(px,min(ground+1,h-2),pz,h-1,STONE,'continuous measured road foundation')
        put(px,h,pz,pavement,'graded complete feeder or restored original gallery')
        top=105 if -872<=px<=-786 else h+6
        fill(px,h+1,pz,top,'minecraft:air','continuous full-width public clearance')
        d['walk'][j,i]=True;d['road'][j,i]=row['road'];d['grade2'][j,i]=row['grade2'];d['tunnel'][j,i]=row['covered'];d['marking'][j,i]='marking'in pavement or pavement=='minecraft:white_concrete'
        if not row['covered']:d['ground'][j,i]=min(int(d['ground'][j,i]),h-1)
    bridge_piers=[]
    if span_x:
        supports=sorted({min(span_x),max(span_x)}|{px for px in span_x if(px-min(span_x))%16==0})
        for px in supports:
            zc=int(round(float(curve(px))));h=int(road_blocks(roadway[px,zc]['grade2'])[0]);cap=h-4
            for xx in range(px-1,px+2):
                for pz in range(zc-6,zc+7):
                    for yy in range(cap,h-1):put(xx,yy,pz,CONCRETE,'bridge crosshead carries full deck');structural.add((xx,yy,pz))
            for side in(-1,1):
                pz=zc+side*4;bases=[]
                for xx in range(px-1,px+2):
                    for zz in range(pz-1,pz+2):
                        footing=next((yy for yy in range(min(soil(xx,zz),cap-1),40,-1)if all(e.state(xx,q,zz).split('[')[0]in SOIL for q in(yy-1,yy))),None)
                        if footing is None:raise ValueError(('Bridge pier lacks two soil courses',xx,zz))
                        bases.append(footing);footings.append([xx,footing-1,zz])
                        for yy in range(footing-1,cap+1):put(xx,yy,zz,CONCRETE,'three-metre pier and recessed footing');structural.add((xx,yy,zz))
                bridge_piers.append(dict(centre=[px,pz],footing=min(bases),top=cap,width=3))
    # Continuous lining for the western hillside crossing and retained gallery.
    # Both mouths have the same full width as their approaches, with no raw cave.
    for px in list(range(-1006,-928))+list(range(-872,-785)):
        zc=int(round(float(curve(px))));old_gallery=px>=-872;half=10 if old_gallery else 7
        h2=196 if old_gallery else int(round(float(PchipInterpolator(level_points[:,0],level_points[:,1])(px))*2));h,_=road_blocks(h2);h=int(h)
        roof=106 if old_gallery else h+7
        for pz in range(zc-half,zc+half+1):
            for y in(roof,roof+1):put(px,y,pz,CONCRETE,'continuous two-course tunnel crown');structural.add((px,y,pz))
            if abs(pz-zc)==half:
                base=min(soil(px,pz)+1,h-2);footings.append([px,base,pz])
                for y in range(base,roof+1):put(px,y,pz,CONCRETE,'founded full tunnel side lining');structural.add((px,y,pz))
        # Recessed lighting does not project below the crown.
        if px%12==0:
            for side in(-1,1):put(px,roof,zc+side*(half-2),'minecraft:sea_lantern','recessed tunnel lighting')
    for px in range(-872,-785):
        for pz in(303,313):
            put(px,98,pz,PAVE,'fixed original separator base')
            for y in(99,100):put(px,y,pz,BARS,'retained moving walkway separator')
            if(px+872)%12==0:
                for y in range(99,107):put(px,y,pz,CONCRETE,'gallery intermediate pier outside carriageway and moving walk');structural.add((px,y,pz))
    # Native modules are actual traffic surfaces, separately checked at their
    # .9375 collision height; generic half-step road authority uses fixed lanes.
    editable=retired.copy()
    for px,pz in roadway:editable[pz-z,px-x]=True
    for row in native:
        px,_,pz=row['pos'];editable[pz-z,px-x]=True
        for key in('walk','road','marking','tunnel'):d[key][pz-z,px-x]=False
    for px in range(-872,-785):
        for pz in(303,313):
            editable[pz-z,px-x]=True
            for key in('walk','road','marking','tunnel'):d[key][pz-z,px-x]=False
    # Only the five surveyed natural remnants lost their bearing when the
    # east approach was cut. Do not generalize this into removal of components.
    for px,pz in[(-764,318),(-764,319),(-763,318),(-762,316),(-762,317)]:
        if e.state(px,104,pz)!='minecraft:grass_block[snowy=false]':raise ValueError('East cut remnant changed')
        put(px,104,pz,'minecraft:air','finite isolated soil cap from east approach')
    if e.state(-922,107,300)!='minecraft:sea_lantern':raise ValueError('Original bridge lamp changed')
    put(-922,107,300,'minecraft:air','original lamp relocated onto founded roadside mast')
    fill(-922,107,305,109,BARS,'roadside lamp mast anchored in measured Y106 soil')
    put(-922,110,305,'minecraft:sea_lantern','retained original lamp on roadside mast')
    if e.state(-1030,110,294)!='minecraft:sea_lantern':raise ValueError('Original western lamp changed')
    for yy in(109,110):put(-1030,yy,294,'minecraft:air','original western lamp moved outside new road')
    for yy in(100,101):put(-1030,yy,298,CONCRETE,'roadside lamp base tied to neighbouring deck')
    fill(-1030,102,298,109,BARS,'original western lamp mast outside public width')
    put(-1030,110,298,'minecraft:sea_lantern','retained western lamp on connected edge mast')
    # Edge rails stand on a short deck extension attached to the sidewalk.
    # Retained routes and the native gallery's entrances stay completely open.
    new_walk=np.zeros(d['walk'].shape,bool)
    for px,pz in roadway:new_walk[pz-z,px-x]=True
    distance,nearest=distance_transform_edt(~new_walk,return_indices=True)
    edge=binary_dilation(new_walk)&~d['walk']
    for j,i in np.argwhere(edge):
        px,pz=int(i+x),int(j+z);J,I=nearest[:,j,i];row=roadway[int(I+x),int(J+z)]
        if row['covered']or -893<=px<=-775:continue
        h,_=road_blocks(row['grade2']);h=int(h)
        if soil(px,pz)>=h-1:continue
        if(px,pz)in joins:continue
        put(px,h-1,pz,CONCRETE,'edge cantilever tied to continuous deck')
        put(px,h,pz,CONCRETE,'edge rail coping')
        for yy in(h+1,h+2):put(px,yy,pz,BARS,'valley-side edge guard outside full public width')
    ordinary=AIR|SOIL|PLANTS|PAVEMENT|{CONCRETE,STONE,'minecraft:gray_concrete','minecraft:iron_bars','minecraft:sea_lantern','minecraft:light'}
    edits=[]
    for p,s in proposed.items():
        before=e.state(*p)
        if before==s:continue
        if p in devices or before.split('[')[0]not in ordinary:raise ValueError(('Retained device or unknown object',p,before))
        key=p[0]//16,p[2]//16
        if key not in guard_cache:guard_cache[key]=guard.chunk_mask(*key)
        if guard_cache[key][p[1]+128,p[2]%16,p[0]%16]or conflict(p,envelopes):raise ValueError(('Protected native transport',p))
        if any(all(b[k]<=p[k]<=b[k+3]for k in range(3))for b in(r['occupied_bounds']for r in catalog)):raise ValueError(('Retained house volume',p))
        j,i=p[2]-z,p[0]-x
        if old['walk'][j,i]and not editable[j,i]:
            h,_=road_blocks(old['grade2'][j,i]);h=int(h)
            if h<=p[1]<=h+(4 if old['road'][j,i]else 2):raise ValueError(('Retained road volume',p))
        e.put(*p,s);edits.append(dict(pos=list(p),before=before,after=s,reason=reasons[p]))
    patches=e.save();e.regions.clear();e=Editor(a.out);errors=[];before=Counter();after=Counter()
    for j,i in np.argwhere(d['walk']):
        px,pz=int(i+x),int(j+z);h,slab=road_blocks(d['grade2'][j,i]);aa=health(e,(px,pz),int(h),slab,bool(d['road'][j,i]))
        if editable[j,i]and not all(aa):errors.append(['new road incomplete',px,pz,list(aa)])
    for j,i in np.argwhere(old['walk']&~editable):
        h,slab=road_blocks(old['grade2'][j,i]);p=int(i+x),int(j+z);aa=health(e,p,int(h),slab,bool(old['road'][j,i]),True);bb=health(e,p,int(h),slab,bool(old['road'][j,i]))
        for k,name in enumerate(('floor','headroom')):
            before[name]+=not aa[k];after[name]+=not bb[k]
            if aa[k]and not bb[k]:errors.append(['retained street regression',name,*p])
    for row in native:
        px,h,pz=row['pos']
        if e.state(px,h,pz)!=row['state']or any(e.state(px,y,pz).split('[')[0]not in AIR|{'minecraft:light'}for y in(99,100,101)):errors.append(['native moving walk blocked',px,pz])
    for p in devices:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['device changed',*p])
    routes=[]
    for name,goal in[('east regional street',(-740,315)),('north fixed bypass',(-830,299)),('south fixed bypass',(-830,317)),('west original moving walk landing',(-880,308))]:
        path=journey(e,d,(-1084,310),goal);routes.append(dict(name=name,path=path))
        if not path:errors.append(['unreachable destination',name,goal])
    d['old_ground']=old['ground'].copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    np.savez_compressed(a.out/'finite-authority.npz',bounds=bounds,retired=retired,editable=editable,before_walk=old['walk'],before_grade2=old['grade2'])
    result=dict(errors=errors,cells=sum(r['cells']for r in patches),native_walkway_modules=len(native),devices_preserved=len(devices),retired_spur_columns=int(retired.sum()),new_or_updated_route_columns=len(roadway),continuous_max_grade=float(slope),bridge_piers=bridge_piers,retained_defects_before=dict(before),retained_defects_after=dict(after),whole_map_complete=False)
    for name,data in [('manifest.json',dict(world=str(world),bounds_xz=bounds,regions=patches,cells=result['cells'],world_written=False,preserve_native_members=True)),('functional-check.json',result),('independent-check.json',result),('street-journeys.json',routes),('tunnel-design.json',dict(centreline=centre,roadway=[dict(pos=list(p),**v)for p,v in roadway.items()],structural=list(map(list,structural)),footings=footings,native=native)),('tunnel-edits.json',edits),('launch-protection.json',check_candidate(guard,a.out))]:save(a.out/name,data)
    print(json.dumps({k:v for k,v in result.items()if k!='errors'}),flush=True)
    print('Errors',len(errors),errors[:12],flush=True)
    if errors:raise ValueError('Finite west tunnel candidate failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','out'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
