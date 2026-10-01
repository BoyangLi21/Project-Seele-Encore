"""Full-width Hakone road: founded valley viaduct, mountain tunnel and public ports.

Read-only authoring through the shared exact-state/full-NBT reader. The road
leaves the original mature tree at -779/300 intact and joins the existing
Tokyo west north/south street at z308. No entity, rail or world writes.
"""
from pathlib import Path
from collections import Counter,deque
import argparse,gzip,hashlib,json,math
import numpy as np
from scipy.spatial import cKDTree
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
ART=ROOT/'artifacts/rebuild_r44/surface_network'
SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt','minecraft:podzol','minecraft:gravel','minecraft:sand','minecraft:andesite','minecraft:diorite','minecraft:granite','minecraft:clay'}
SMALL={'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:snow','minecraft:dandelion','minecraft:poppy','minecraft:azure_bluet','minecraft:oxeye_daisy','minecraft:cornflower','minecraft:allium'}
PAVING={'minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone','minecraft:gray_concrete','minecraft:polished_blackstone_slab','minecraft:quartz_slab','minecraft:smooth_stone_slab','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}
GUARD='minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'
X0,X1=-1138,-748

def centre(x):
    t=min(1,max(0,(x+1080)/180));return 300+round(8*(3*t*t-2*t*t*t))

def half_width(x):return 7 if x<-900 else 6

def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args();out=args.output
    assert not out.exists(),'Keep earlier complete plans and failures; use a new named epoch'
    profiles_path=ART/'road_complete_authority_stage3.columns.npz';a=np.load(profiles_path)
    profiles={tuple(map(int,q)):(round(float(f)*2),int(g)) for q,f,g in zip(a['coordinates'],a['actual_feet'],a['flags']) if not np.isnan(f)}
    assert profiles[-1120,300]==(210,31) and profiles[-760,308]==(194,31)
    w=MeasuredWorld(WORLD);lo,hi=(X0-4,30,280),(X1+4,148,338);w.box(lo,hi);w.load()
    assert set(w.status.values())=={'full'},dict(Counter(w.status.values()))
    bes=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    shapes={canonical_state(s):v for s,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    proposed={};held={};structural=set();soil={};sections=[];piers=[];banks=[]
    def old(q):return w.block(q)
    def current(q):return proposed.get(q,(old(q),''))[0]
    def put(q,state,reason,allow=PAVING|SOIL|SMALL|AIR):
        q=tuple(q);before=old(q);name=(before or '').split('[')[0]
        if before is None or q in bes or name not in allow:
            held[q]=dict(pos=q,state=before,full_nbt=bes[q].snbt() if q in bes else None,reason=reason);return False
        if before!=state:proposed[q]=(state,reason)
        elif q in proposed:del proposed[q]
        return True
    def top(x,z):
        q=x,z
        if q not in soil:
            ys=[y for y in range(lo[1],hi[1]+1) if (w.get(x,y,z) or '').split('[')[0] in SOIL]
            soil[q]=max(ys) if ys else None
        return soil[q]
    def grade(x,dz=0):
        value=round(2*(105-8*min(1,max(0,(x+1120)/360))))
        if x<-1120:
            actual=profiles.get((X0,300+dz))
            if actual:value=round(actual[0]+(210-actual[0])*(x-X0)/(-1120-X0))
        return value
    # Every road column has a real bearing or a deck connected to founded piers.
    for x in range(X0,X1+1):
        zc=centre(x);h2=grade(x);feet=h2/2;fy=(h2-1)//2
        tops=[top(x,z) for z in range(zc-7,zc+8)]
        assert all(q is not None for q in tops),(x,'Unknown geology')
        tunnel=-872<=x<=-786
        span=min(tops)<fy-5 and not tunnel
        sections.append(dict(x=x,z=zc,height2=h2,kind='mountain_tunnel' if tunnel else 'valley_viaduct' if span else 'grounded_approach',natural_surface_range=[min(tops),max(tops)]))
        # The positive-Z bend has a one-metre paved inner shoulder: diagonal
        # transitions retain the entire thirteen-metre usable road width.
        for dz in range(-half_width(x),half_width(x)+1):
            z=zc+dz;local=grade(x,dz);f=local/2;y=(local-1)//2
            # The centre dash and edge lines use the same thickness as asphalt.
            marking=abs(dz)==4 or (dz==0 and (x-X0)%12<5)
            surface='minecraft:white_concrete' if marking else 'minecraft:black_concrete'
            if abs(dz)>=5:surface='minecraft:smooth_stone'
            if local%2:surface=('projectseele:road_marking_slab' if marking else 'projectseele:road_asphalt_slab')+'[type=bottom,waterlogged=false]' if abs(dz)<5 else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
            put((x,y,z),surface,'Two public lanes, edge lines and two metre pedestrian sidewalks on the measured endpoint grade')
            for yy in range(math.ceil(f),math.ceil(f+7)):
                if current((x,yy,z)) in AIR:continue
                put((x,yy,z),'minecraft:air','Complete seven metre vehicle and pedestrian bore; natural excavation only, existing trees/devices preserved',SOIL|SMALL|AIR|PAVING)
            if span:
                put((x,y-1,z),'minecraft:light_gray_concrete','Continuous full-width structural bridge deck, never an unsupported road sheet')
                structural.add((x,y-1,z))
            else:
                ground=top(x,z)
                if ground<y:
                    for yy in range(ground+1,y):
                        put((x,yy,z),'minecraft:stone','Approach formation joins every road column to its measured natural bearing')
                        structural.add((x,yy,z))
            if tunnel:
                ceiling=math.ceil(feet+7)
                put((x,ceiling,z),'minecraft:light_gray_concrete','Sealed full-width tunnel crown with at least seven metres of actual clearance')
                if abs(dz)==5 and (x+872)%12==0:put((x,ceiling,z),'minecraft:sea_lantern','Recessed tunnel lighting above the verified full-width clear envelope')
        if span:
            for dz in (-3,3):
                for yy in (fy-2,fy-3):
                    put((x,yy,zc+dz),'minecraft:gray_concrete','Twin continuous box girders carry the valley deck without damming the valley')
                    structural.add((x,yy,zc+dz))
        # A continuous edge coping supports either roadside guard or tunnel wall.
        for side in (-1,1):
            z=zc+(half_width(x)+1)*side
            junction=profiles.get((x,z))
            if junction and junction[1]&7==7 and abs(junction[0]/2-feet)<=.501:continue
            for yy in (fy-1,fy):
                put((x,yy,z),'minecraft:light_gray_concrete','Continuous edge coping is attached to the whole bridge or natural approach')
                structural.add((x,yy,z))
            if tunnel:
                for yy in range(math.floor(feet),math.ceil(feet+8)):
                    put((x,yy,z),'minecraft:gray_concrete','Complete tunnel side lining, connected to deck and crown')
            else:
                for yy in (math.floor(feet),math.floor(feet)+1):put((x,yy,z),GUARD,'Continuous vehicle and pedestrian barrier outside both clear sidewalks')
                # Shallow approach banks tie to existing hillside without filling the deep valley.
                if not span:
                    for distance in range(1,9):
                        zz=z+distance*side;ground=top(x,zz)
                        if ground is None:continue
                        bank=fy-math.ceil(distance/2)
                        if ground>=bank or bank-ground>6:continue
                        for yy in range(ground+1,bank):
                            if (old((x,yy,zz)) or '').split('[')[0] not in SOIL|SMALL|AIR:break
                            put((x,yy,zz),'minecraft:dirt','Local one-to-two graded approach bank; existing mature trees and water remain outside the bank')
                        q=(x,bank,zz)
                        if (old(q) or '').split('[')[0] in SOIL|SMALL|AIR:
                            put(q,'minecraft:grass_block[snowy=false]','Grass shoulder meets the real hillside rather than a vertical floating road edge');banks.append(q)
    # Paired concrete piers and complete headstocks every twenty-four metres.
    # Each footing is recessed into measured solid natural rock, not a height-map estimate.
    span_sections=[s for s in sections if s['kind']=='valley_viaduct']
    span_x={s['x'] for s in span_sections};supports=sorted({min(span_x),max(span_x)}|{x for x in span_x if (x-X0)%24==0}) if span_x else []
    for x in supports:
        zc=centre(x);fy=(grade(x)-1)//2;head=fy-4
        for xx in range(x-1,x+2):
            for z in range(zc-half_width(x)-1,zc+half_width(x)+2):
                for yy in range(head,fy-1):
                    put((xx,yy,z),'minecraft:light_gray_concrete','Complete pier headstock connects both box girders and the full pedestrian width');structural.add((xx,yy,z))
        for dz in (-5,5):
            foundations=[]
            for xx in range(x-1,x+2):
                for zz in range(zc+dz-1,zc+dz+2):
                    g=top(xx,zz);assert g is not None,(x,zz,g,head)
                    bearing=min(g,head-1);foundations.append(bearing)
                    if any((old((xx,yy,zz)) or '').split('[')[0] not in SOIL for yy in (bearing-1,bearing)):
                        held[xx,bearing,zz]=dict(pos=[xx,bearing,zz],reason='Pier footing lacks two measured continuous solid natural strata');continue
                    for yy in range(bearing-1,head):
                        put((xx,yy,zz),'minecraft:light_gray_concrete','Exact pier and two-stratum recessed footing carry the entire valley bridge to actual geology',SOIL|AIR|SMALL|{'minecraft:water'})
                        structural.add((xx,yy,zz))
            piers.append(dict(x=x,z=zc+dz,top=head,measured_natural_bearing=min(foundations),width=3,depth=3))
    # The first and last tunnel bays are connected portal collars, retaining
    # their actual hill around the bore; a raw cuboid trench is not substituted.
    for x in (-872,-871,-786,-785):
        zc=centre(x);feet=grade(x)/2;floor=(grade(x)-1)//2;roof=math.ceil(feet+8)
        for z in range(zc-8,zc+9):
            for yy in (roof-1,roof):put((x,yy,z),'minecraft:smooth_stone','Complete two-course mountain tunnel portal collar tied into original hillside')
        for dz in (-8,8):
            for yy in range(floor,roof+1):put((x,yy,zc+dz),'minecraft:smooth_stone','Portal jamb and retaining cheek meet the excavated mountain shoulder')
    # Viaduct lighting remains outside the thirteen metre carriage/sidewalk envelope.
    for s in sections:
        if s['kind']=='mountain_tunnel' or (s['x']-X0)%36:continue
        x,zc,feet=s['x'],s['z'],s['height2']/2
        for side in (-1,1):
            z=zc+(half_width(x)+1)*side
            junction=profiles.get((x,z))
            if junction and junction[1]&7==7 and abs(junction[0]/2-feet)<=.501:continue
            for yy in range(math.floor(feet)+2,math.floor(feet)+7):put((x,yy,z),GUARD,'Road lighting column continues from its founded edge coping outside public clear width')
            put((x,math.floor(feet)+7,z),'minecraft:sea_lantern','Even bridge and approach lighting above vehicle clearance')
    # Registered flat MTR modules are straight, two blocks wide and level.
    # Their native .9375 collision top is kept exact; it is never rounded to
    # the road's half-block grid. Each side also has a two-metre fixed bypass.
    moving_cells=[];pedestrian_cells=[];divider_cells=[]
    for x in range(-890,-783):
        zc=308;core=-872<=x<=-786
        for side in (-1,1):
            for adz in range(5,10):
                dz=side*adz;z=zc+dz;equipment=core and adz in (6,7);divider=core and adz==5
                for y in range(99,106):
                    put((x,y,z),'minecraft:air','Full native moving-walk side bay and fixed bypass; existing trees and devices remain protected')
                surface='minecraft:smooth_stone'
                if equipment:
                    # East-facing left is the smaller-Z member for either flow.
                    left=(side<0 and adz==7) or (side>0 and adz==6)
                    surface=f'mtr:escalator_step[direction={str(side<0).lower()},facing=east,orientation=flat,side={"left" if left else "right"},status=true]'
                put((x,98,z),surface,'Straight level native two-metre MTR walk or fixed two-metre companion bypass')
                g=top(x,z)
                for y in range(min(g+1,98),98):
                    put((x,y,z),'minecraft:stone','Moving-walk side bay and landing have actual continuous bearing')
                    structural.add((x,y,z))
                if divider:
                    for y in (99,100):put((x,y,z),GUARD,'Continuous physical separator keeps the public moving walk clear of both vehicle lanes')
                    divider_cells.append([x,98,z]);continue
                entry=dict(pos=[x,z],height2=198,native_feet=98.9375 if equipment else 99.0,carriage=False,source_id='r44/hakone_tokyo_tunnel_moving_walk' if equipment else 'r44/hakone_tokyo_tunnel_fixed_bypass',role='moving_walk' if equipment else 'fixed_pedestrian_bypass')
                pedestrian_cells.append(entry)
                if equipment:moving_cells.append(dict(pos=[x,98,z],state=surface,direction='east' if side<0 else 'west',native_feet=98.9375))
        if core:
            for z in range(zc-10,zc+11):
                put((x,106,z),'minecraft:light_gray_concrete','Complete widened tunnel crown preserves the original hill and covers both fixed and moving pedestrian lanes')
                if abs(z-zc)==8 and (x+872)%12==0:put((x,106,z),'minecraft:sea_lantern','Continuous recessed light over the fixed bypass and automatic walk')
            for dz in (-10,10):
                g=top(x,zc+dz)
                for y in range(min(g+1,98),107):put((x,y,zc+dz),'minecraft:gray_concrete','Founded outer side-bay lining connects to deck and full tunnel crown')
        else:
            for dz in (-10,10):
                for y in (98,99,100):put((x,y,zc+dz),'minecraft:smooth_stone' if y==98 else GUARD,'Full-width landing edge is founded and guarded outside all pedestrian lanes')
    # Ten metre west buffering joins the half-block road to Y99. The east
    # landing turns both fixed bypasses into the original two-metre sidewalks
    # before a three-step half-block descent, preserving trees at Z300/317.
    for x in range(-894,-890):
        feet=99.5 if x<-890 else 99.0
        for side in (-1,1):
            for adz in (5,6):
                z=308+side*adz;y=math.floor(feet-.001)
                put((x,y,z),'minecraft:smooth_stone' if feet%1==0 else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]','West fixed approach platform makes the moving-walk transition continuous')
                for yy in range(math.ceil(feet),math.ceil(feet+6)):put((x,yy,z),'minecraft:air','West pedestrian approach full headroom')
                pedestrian_cells.append(dict(pos=[x,z],height2=round(2*feet),native_feet=feet,carriage=False,source_id='r44/hakone_tokyo_tunnel_walk_landing',role='fixed_pedestrian_landing'))
    for x in range(-783,-775):
        feet=98.5 if x<=-782 else 98.0 if x<=-780 else grade(x)/2
        for side in (-1,1):
            for adz in (5,6):
                z=308+side*adz;y=math.floor(feet-.001)
                put((x,y,z),'minecraft:smooth_stone' if feet%1==0 else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]','East fixed short steps join the level walk to the original road grade')
                for yy in range(math.ceil(feet),math.ceil(feet+6)):put((x,yy,z),'minecraft:air','East landing and fixed short-step clearance')
                pedestrian_cells.append(dict(pos=[x,z],height2=round(2*feet),native_feet=feet,carriage=False,source_id='r44/hakone_tokyo_tunnel_walk_landing',role='fixed_pedestrian_landing'))
    for x in (-872,-871,-786,-785):
        for z in range(297,320):
            for y in (106,107):put((x,y,z),'minecraft:smooth_stone','Widened complete portal collar encloses both two-metre moving walks and fixed bypasses')
        for z in (297,319):
            g=top(x,z)
            for y in range(min(g+1,98),108):put((x,y,z),'minecraft:smooth_stone','Widened portal jamb has continuous actual bearing and ties to the complete tunnel crown')
    failures=[];unknown=Counter()
    def boxes(state):
        if state in AIR or (state or '').split('[')[0] in SMALL:return []
        shape=shapes.get(state)
        if shape is None:unknown[state]+=1
        return shape
    columns=[]
    for s in sections:
        x,zc=s['x'],s['z']
        for dz in range(-half_width(x),half_width(x)+1):
            z=zc+dz
            if abs(dz)>=5 and -894<=x<=-776:continue
            h2=grade(x,dz);feet=h2/2;y=(h2-1)//2;q=(x,y,z);shape=boxes(current(q))
            if shape is None or not any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(y+b[4]-feet)<.01 for b in shape):failures.append(dict(pos=q,reason='Road foot plane is not its exact native collision shape'))
            for yy in range(math.floor(feet),math.ceil(feet+6)):
                bs=boxes(current((x,yy,z)))
                if bs is None or any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and yy+b[1]<feet+6 and yy+b[4]>feet+.001 for b in (bs or [])):
                    failures.append(dict(pos=[x,yy,z],reason='Full-width six metre clearance blocked/unknown'))
            columns.append(dict(pos=[x,z],height2=h2,carriage=abs(dz)<=4,source_id='r44/hakone_tokyo_valley_tunnel_link',before_height2=profiles.get((x,z),(None,))[0]))
    for entry in pedestrian_cells:
        x,z=entry['pos'];feet=entry['native_feet'];y=math.floor(feet-.001);shape=boxes(current((x,y,z)))
        if shape is None or not any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(y+b[4]-feet)<.001 for b in shape):failures.append(dict(pos=[x,y,z],reason='Native automatic/fixed walkway collision top differs from its actual platform datum'))
        for yy in range(math.floor(feet),math.ceil(feet+1.8)):
            for box in boxes(current((x,yy,z))) or []:
                if yy+box[4]>feet+.001 and yy+box[1]<feet+1.8:failures.append(dict(pos=[x,yy,z],reason='Native automatic/fixed walkway player clearance blocked'))
        columns.append(entry)
    # Entire proposed solid bridge frame must connect to a pier footing or actual geology.
    live={q for q in structural if current(q) and current(q).split('[')[0] in SOIL|{'minecraft:light_gray_concrete','minecraft:gray_concrete'}}
    seeds={q for q in live if any((current((q[0]+dx,q[1]+dy,q[2]+dz)) or '').split('[')[0] in SOIL for dx,dy,dz in ((0,-1,0),(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)))}
    reached=set(seeds);todo=deque(seeds)
    while todo:
        x,y,z=todo.popleft()
        for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            q=x+dx,y+dy,z+dz
            if q in live and q not in reached:reached.add(q);todo.append(q)
    if live-reached:failures.append(dict(reason='Structural bridge frame disconnected from actual geology/footings',cells=len(live-reached),example=min(live-reached)))
    native_path=ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json';native=json.loads(native_path.read_text('utf8'))
    rail=[(c['id'],p) for c in native['curves'] if c['mode']=='TRAIN' for p in c['points'] if lo[0]-4<=p[0]<=hi[0]+4 and lo[2]-4<=p[2]<=hi[2]+4]
    conflicts=[]
    for q in proposed:
        for cid,p in rail:
            if abs(q[0]+.5-p[0])<4 and abs(q[2]+.5-p[2])<4 and p[1]-3<q[1]+1 and p[1]+8>q[1]:conflicts.append(dict(pos=q,curve=cid));break
    if conflicts:failures.append(dict(reason='Real 7x7 train envelope conflicts with new component',hits=conflicts))
    swept_bend_samples=0
    for a,b in zip(sections,sections[1:]):
        if a['z']==b['z']:continue
        for dz in range(-6,7):
            feet=max(grade(a['x'],dz),grade(b['x'],dz))/2
            for i in range(17):
                t=i/16;xx=a['x']+.5+t;zz=a['z']+dz+.5+(b['z']-a['z'])*t;swept_bend_samples+=1
                low=(xx-.3,feet+.001,zz-.3);high=(xx+.3,feet+1.8,zz+.3)
                for bx in range(math.floor(low[0]),math.floor(high[0])+1):
                    for by in range(math.floor(low[1]),math.floor(high[1])+1):
                        for bz in range(math.floor(low[2]),math.floor(high[2])+1):
                            for box in boxes(current((bx,by,bz))) or []:
                                if bx+box[0]<high[0] and bx+box[3]>low[0] and by+box[1]<high[1] and by+box[4]>low[1] and bz+box[2]<high[2] and bz+box[5]>low[2]:
                                    failures.append(dict(pos=[bx,by,bz],reason='Native shape clips the player footprint across an integer-centre bend',lane=dz,at=[xx,feet,zz]))
    out.mkdir(parents=True)
    rows=[dict(pos=q,before=old(q),after=s,before_nbt=None,after_nbt=None,owner='r44/hakone_tokyo_valley_tunnel_link',reason=r) for q,(s,r) in sorted(proposed.items())]
    for name,inv in [('forward',False),('inverse',True)]:
        with gzip.open(out/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for row in rows:
                value=dict(row)
                if inv:value['before'],value['after']=row['after'],row['before']
                f.write(json.dumps(value)+'\n')
    (out/'road_authority.json').write_text(json.dumps(dict(columns=columns,world_written=False),indent=2),'utf8')
    reservations=[dict(bounds=[s['x'],math.floor(s['height2']/2)-4,s['z']-(12 if -894<=s['x']<=-776 else half_width(s['x'])+2),s['x'],math.ceil(s['height2']/2)+9,s['z']+(12 if -894<=s['x']<=-776 else half_width(s['x'])+2)],layer='surface',owner='r44/hakone_tokyo_valley_tunnel_link') for s in sections]
    (out/'ecology_reservations.json').write_text(json.dumps(dict(reservations=reservations,preserve_natural_valley_below_deck=True,required_before_full_ecology_author=True),indent=2),'utf8')
    (out/'moving_walk_contract.json').write_text(json.dumps(dict(native_flat_cells=moving_cells,fixed_pedestrian_columns=pedestrian_cells,physical_dividers=divider_cells,
        moving_length=87,moving_width_each=2,static_bypass_width_each=2,north_side_flow='east',south_side_flow='west',native_step_block_y=98,native_step_feet=98.9375,
        fixed_bypass_feet=99,handrails_present=False,west_buffer_metres=12,east_buffer_and_short_steps_metres=10,
        native_state_motion_passed=False,native_player_transport_passed=False,client_visual_passed=False,
        required='Root must test actual MTR transport direction and boarding/disembarking, both two-metre lanes and fixed bypasses. Static collision is not belt motion proof.'),indent=2),'utf8')
    cases=[]
    for dz in range(-6,7):
        path=[]
        for s in sections:
            x=s['x'];offset=dz;feet=grade(x,dz)/2
            if abs(dz)>=5 and -886<=x<=-785:
                offset=(8 if abs(dz)==5 else 9)*(1 if dz>0 else -1);feet=99
            elif abs(dz)>=5 and -894<=x<-886:feet=99.5 if x<-890 else 99
            elif abs(dz)>=5 and x==-784:feet=99
            elif abs(dz)>=5 and -783<=x<=-776:feet=98.5 if x<=-782 else 98 if x<=-780 else grade(x)/2
            path.append([x+.5,feet,s['z']+offset+.5])
            if abs(dz)>=5 and x==-887:
                outside=(8 if abs(dz)==5 else 9)*(1 if dz>0 else -1)
                path.append([x+.5,99,s['z']+outside+.5])
            if abs(dz)>=5 and x==-785:
                outside=(8 if abs(dz)==5 else 9)*(1 if dz>0 else -1)
                path.extend([[-784.5,99,s['z']+outside+.5],[-784.5,99,s['z']+dz+.5]])
        for direction in ('east','west'):cases.append(dict(id=f'r44/hakone_tokyo_link/column{dz}/{direction}',path=path if direction=='east' else path[::-1],six_metre_vehicle_clearance=abs(dz)<=4,native_client_passed=False))
    (out/'native_full_width_cases.json').write_text(json.dumps(cases),'utf8')
    report=dict(world=str(WORLD),survey_bounds=[lo,hi],authority='Explicit global city road reconstruction; measured existing Hakone and Tokyo public street ports, original engineering',
        anchors=[[-1120,105,300],[-760,97,308]],mature_tree_preserved=[-779,102,300],complete_width=13,paved_width_with_bend_shoulders=15,carriage_width=9,sidewalk_width_each=2,tunnel_total_clear_bays_width=19,sections=sections,
        piers=piers,graded_bank_cells=len(banks),planned_changed_cells=len(rows),full_road_columns=len(columns),held=list(held.values()),static_failures=failures,unknown_collision_shapes=dict(unknown),
        complete_component_ready=not held and not failures,full_frame_cells=len(live),frame_connected_to_geology_cells=len(reached),virtual_rail_conflicts=conflicts,
        native_shape_player_bend_sweep_samples=swept_bend_samples,
        source_road_profiles_sha256=hashlib.sha256(profiles_path.read_bytes()).hexdigest(),native_rail_snapshot_sha256=hashlib.sha256(native_path.read_bytes()).hexdigest(),
        world_written=False,native_full_width_walk_passed=False,native_vehicle_passed=False,visual_passed=False,
        visual_intent='Two public lanes and marked edges, continuous two metre sidewalks, paired founded concrete box-girder viaduct across the untouched valley, graded approaches, lit mountain tunnel preserving the ridge, intact mature tree and real town junctions. No flood filling or narrow centre-line substitute.')
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(output=str(out.resolve()),changed=len(rows),columns=len(columns),piers=len(piers),held=len(held),failures=len(failures),unknown=dict(unknown),ready=report['complete_component_ready'])),flush=True)

if __name__=='__main__':main()
