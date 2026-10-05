"""Physical viaducts, complete station access and restored streets for R20.

Rail heights come exclusively from native MTR curves. Ground streets have
their own continuous datum and are never cut to make room for rolling stock.
"""
from collections import defaultdict
from pathlib import Path
import argparse,json,math
import numpy as np
import nbtlib
import regional_voxels as vox
from quality_roads import envelopes
from plan_transit_r20 import CN,xyz
from build_station_boards_r19 import packed

OUT=vox.ROOT/'artifacts/world_rebuild_r20/transit/civil'
SOURCE=vox.ROOT/'artifacts/world_rebuild_r20/transit'
AIR='minecraft:air';DECK='minecraft:light_gray_concrete';STEEL='projectseele:nerv_machine_edge';FLOOR='minecraft:smooth_stone';DARK='minecraft:gray_concrete';GLASS='minecraft:light_gray_stained_glass';LIGHT='projectseele:nerv_strip_light'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def arrays(p):
    with np.load(p) as a:return {k:a[k] for k in a.files}
def ff(p,box,state,owner):p.fill(*map(int,box),state,owner,'owned')
def grouped(columns):
    rows=defaultdict(list)
    for (x,z),value in columns.items():rows[z,value].append(x)
    for (z,value),xs in sorted(rows.items()):
        xs.sort();a=b=xs[0]
        for x in xs[1:]:
            if x==b+1:b=x
            else:yield a,b,z,value;a=b=x
        yield a,b,z,value

def roads(p,terrain,old):
    root=vox.ROOT/'artifacts/world_quality_r02';a=arrays(root/'road_surfaces.npz');mask=a['mask'];origin=a['origin'];desired=(terrain['height'].astype(np.int32)+1)*2
    fixed=np.full(mask.shape,30000,np.int32);plan=load(root/'road_plan.json');ox,oz=map(int,origin)
    # Retained doors and the old ground-floor station entrances are fixed.
    pins=[e['pos'] for e in plan['entrances']]
    for q in plan['station_paths']:
        x,z=q['points'][0];ix,iz=round(x)-ox,round(z)-oz
        if 0<=ix<mask.shape[1] and 0<=iz<mask.shape[0]:pins.append([x,float(a['height2'][iz,ix])/2,z])
    for x,y,z in pins:
        ix,iz=math.floor(x)-ox,math.floor(z)-oz
        for dz in (-1,0,1):
            for dx in (-1,0,1):
                if 0<=iz+dz<mask.shape[0] and 0<=ix+dx<mask.shape[1] and mask[iz+dz,ix+dx]:fixed[iz+dz,ix+dx]=round(y*2)
    upper=envelopes(mask,fixed);lower=-envelopes(mask,np.where(fixed<20000,-fixed,30000));target=envelopes(mask,np.minimum(np.maximum(desired,lower),upper)).astype(np.int16)
    assert np.all(target[mask&(fixed<20000)]==fixed[mask&(fixed<20000)])
    for dz,dx in ((0,1),(1,0),(1,1),(1,-1)):
        x0,x1=max(0,-dx),min(mask.shape[1],mask.shape[1]-dx);m=mask[:mask.shape[0]-dz,x0:x1]&mask[dz:,x0+dx:x1+dx]
        assert np.all(abs(target[:mask.shape[0]-dz,x0:x1][m]-target[dz:,x0+dx:x1+dx][m])<=1)
    cols={}
    for z,x in np.argwhere(mask):
        h=int(target[z,x]);kind=2 if a['stripe'][z,x] else 1 if a['carriage'][z,x] else 0;cols[int(x+ox),int(z+oz)]=(h,kind)
    for x,X,z,(h,kind) in grouped(cols):
        y=(h-1)//2;state=[FLOOR,'minecraft:black_concrete','minecraft:white_concrete'][kind]
        if h%2:state=['minecraft:smooth_stone_slab','minecraft:polished_blackstone_slab','minecraft:quartz_slab'][kind]+'[type=bottom,waterlogged=false]'
        ff(p,(x,y-4,z,X,y-1,z),'minecraft:stone','r20/road_formation');ff(p,(x,y,z,X,y,z),state,'r20/road_surface');ff(p,(x,y+1,z,X,y+5,z),AIR,'r20/road_clearance')
    np.savez_compressed(OUT/'road_contract.npz',height2=target,mask=mask,carriage=a['carriage'],stripe=a['stripe'],origin=origin)
    p.meta['road_columns']=len(cols);return target,mask,origin

def station(p,platform,migrations,native,walks,boards):
    olda,oldb=xyz(platform['position1']),xyz(platform['position2']);cx=(olda[0]+oldb[0])//2;cz=(olda[2]+oldb[2])//2;oldy=olda[1];horizontal=olda[2]==oldb[2];length=int(abs(olda[0]-oldb[0])+abs(olda[2]-oldb[2]));half=length//2+10
    changes=[m for m in migrations if m['original']==platform['id']];newy=changes[0]['new'][0][1];paired=len(changes)>1;tracks=[-4,4] if paired else [0];ground=80 if oldy==65 else oldy;name=next((s['name'] for s in native['stations'] if all(min(s['position1'][k],s['position2'][k])<=platform['position1'][k]<=max(s['position1'][k],s['position2'][k]) for k in ('x','y','z'))),'铁路车站')
    line=changes[0]['line'];owner='r20/station/'+str(platform['id']);report=dict(id=platform['id'],station=name,line=line,center=[cx,newy,cz],old_center=[cx,oldy,cz],ground=ground,half=half,horizontal=horizontal,tracks=tracks)
    def at(u,y,v):return (cx+u,y,cz+v) if horizontal else (cx+v,y,cz+u)
    def fill(u,y,v,U,Y,V,s):
        a=at(u,y,v);b=at(U,Y,V);ff(p,(*np.minimum(a,b),*np.maximum(a,b)),s,owner)
    def path(label,a,b):walks.extend([dict(id=owner+'/'+label,start=a,end=b),dict(id=owner+'/'+label+'/return',start=b,end=a)])
    def pos(u,y,v):return [q+.5 if k!=1 else q for k,q in enumerate(at(u,y,v))]
    # One complete structural bay: the old canopy and suspended fixtures go.
    fill(-half,oldy-3,-15,half,max(oldy+16,newy+14),15,AIR)
    fill(-half,ground-3,-15,half,ground-1,15,DECK);fill(-half,ground,-15,half,ground,15,FLOOR)
    fill(-half,newy-3,-15,half,newy-1,15,DECK);fill(-half,newy,-15,half,newy,15,FLOOR)
    if oldy<ground:fill(-half,oldy-3,-15,half,ground-1,15,'minecraft:stone')
    for u in range(-half+2,half,16):
        for v in (-15,15):
            fill(u-1,ground-1,v,u+1,newy-2,v,DECK);fill(u,newy+1,v,u,newy+10,v,STEEL)
        fill(u,newy+10,-14,u+1,newy+10,14,STEEL)
    for v in (-15,15):
        fill(-half,newy+1,v,half,newy+1,v,DARK);fill(-half,newy+2,v,half,newy+3,v,GLASS)
        fill(-half,newy+10,v,half,newy+10,v,STEEL)
    # Light, shallow pitched platform canopies with a glazed centre strip.
    fill(-half,newy+11,-15,half,newy+11,-5,DECK);fill(-half,newy+11,5,half,newy+11,15,DECK);fill(-half,newy+12,-5,half,newy+12,5,GLASS)
    for u in range(-half+5,half-3,9):
        for v in (-9,9):fill(u,newy+10,v,u+3,newy+10,v,LIGHT)
    for v in tracks:
        fill(-half,newy,v-1,half,newy+6,v+1,AIR)
        fill(-half,newy-1,v-1,half,newy-1,v+1,'minecraft:gravel')
        for edge in ((v-2,v+2) if not paired else (v+(2 if v>0 else -2),)):
            facing=('south' if edge<v else 'north') if horizontal else ('east' if edge<v else 'west')
            fill(-half+8,newy,edge,half-8,newy,edge,f'mtr:platform[door_type=none,facing={facing},side=0]')
        for edge in ((v-3,v+3) if not paired else (v+(3 if v>0 else -3),)):fill(-half+8,newy,edge,half-8,newy,edge,'projectseele:station_tactile_warning')
    if paired:
        fill(-half,newy,-2,half,newy+4,2,AIR);fill(-half,newy-1,-2,half,newy-1,2,'minecraft:gravel')
    # Ground passages cross beneath the tracks; two ordinary stair flights
    # reach the outer platforms. All upper floors are cut AFTER construction.
    if newy>ground:
        rise=newy-ground
        for sign in (-1,1):
            v=sign*12;u=-half+6;base=ground;start=pos(u-1,ground+1,v);nodes=[start]
            for i in range(rise):
                if i and i%7==0:
                    fill(u,base,v-2,u+2,base,v+2,FLOOR);fill(u,base+1,v-2,u+2,newy+6,v+2,AIR);nodes.append(pos(u+1,base+1,v));u+=3
                fill(u,base+1,v-2,u,newy+6,v+2,AIR);fill(u,ground,v-2,u,base,v+2,DECK)
                facing='east' if horizontal else 'south';fill(u,base+1,v-2,u,base+1,v+2,f'minecraft:smooth_quartz_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]')
                for side in (v-3,v+3):fill(u,base+2,side,u,base+3,side,GLASS)
                base+=1;u+=1
            fill(u,newy,v-2,u+2,newy,v+2,FLOOR);fill(u,newy+1,v-2,u+2,newy+4,v+2,AIR);nodes.append(pos(u+1,newy+1,v));nodes.append(pos(u+4,newy+1,v))
            for i,(a,b) in enumerate(zip(nodes,nodes[1:])):path('ground_stair_'+str(sign)+'/'+str(i),a,b)
            path('ground_access_'+str(sign),pos(-half+5,ground+1,sign*16),start)
    else:
        for sign in (-1,1):
            fill(-4,newy+1,sign*15,4,newy+5,sign*15,AIR)
    # An overbridge connects the island and outer platforms above the trains.
    u0=half-24
    fill(u0+6,newy+6,-14,u0+10,newy+6,14,FLOOR)
    for edge in (u0+5,u0+11):fill(edge,newy+7,-14,edge,newy+8,14,GLASS)
    for v in (-12,12):
        for i in range(6):
            fill(u0+i,newy+i+1,v-2,u0+i,newy+10,v+2,AIR)
            fill(u0+i,newy,v-2,u0+i,newy+i,v+2,DECK)
            facing='east' if horizontal else 'south';fill(u0+i,newy+i+1,v-2,u0+i,newy+i+1,v+2,f'minecraft:smooth_quartz_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]')
        path('overbridge_stair_'+str(v),pos(u0-1,newy+1,v),pos(u0+7,newy+7,v))
    path('overbridge',pos(u0+8,newy+7,-12),pos(u0+8,newy+7,12))
    for sign in (-1,1):
        path('continuous_platform_'+str(sign),pos(-half+5,newy+1,sign*8),pos(half-5,newy+1,sign*8))
        edge=sign*(6 if paired else 2)
        path('boarding_approach_'+str(sign),pos(0,newy+1,sign*8),pos(0,newy+1,edge))
    # Wall-mounted screens and moulded seating leave generous walking lanes.
    for sign in (-1,1):
        face=('south' if sign<0 else 'north') if horizontal else ('east' if sign<0 else 'west')
        u=half-8;v=sign*14;board=at(u,newy+4,v);support=at(u,newy+4,sign*15);ff(p,(*support,*support),STEEL,owner)
        p.put(*board,f'projectseele:station_departure_board[facing={face}]',owner)
        chosen=min(changes,key=lambda m:abs((m['new'][0][2] if horizontal else m['new'][0][0])-(cz if horizontal else cx)-sign*4));pp=next(x for x in native['platforms'] if x['id']==chosen['id']);centre=tuple((pp['position1'][k]+pp['position2'][k])//2 for k in ('x','y','z'))
        p.block_entities[board]=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(board[0]),'y':nbtlib.Int(board[1]),'z':nbtlib.Int(board[2]),'PlatformCentre':nbtlib.Long(packed(centre)),'Station':nbtlib.String(name),'Route':nbtlib.String(line)})
        boards.append(dict(id=owner+'/'+str(sign),pos=board,platform=centre))
        for u in range(half-16,half-7):
            p.put(*at(u,newy+1,sign*13),f'projectseele:station_seat[facing={face}]',owner)
        # Native wall signs have a full backing member, never a floating post.
        p.sign(*at(-half+2,newy+5,sign*14),[name,line+'  每分钟一班','乘车 →','北京时间'],owner,face)
    p.meta.setdefault('stations',[]).append(report)

def main():
    OUT.mkdir(parents=True,exist_ok=True);vox.OUT=OUT;p=vox.Painter();old=load(SOURCE/'native_snapshot.json');native=load(SOURCE/'built1/native_commission.json');plan=load(SOURCE/'native_plan.json');assert native['passed'];terrain=arrays(vox.ROOT/'artifacts/world_quality_r02/terrain_target.npz');ox,oz=map(int,terrain['origin']);nz,nx=terrain['height'].shape
    print('R20 civil inputs loaded',flush=True)
    # Exact retained systems and occupied plots constrain every ground edit.
    # R47: the retired surface cages no longer own the whole north forecourt.
    # Keep the real launch mouths/power pads, not the obsolete80m rail beds.
    for name,box in [('core',(-194,32,-4,254,255,444)),('surface_launches',(-65,32,-84,98,255,-16)),('original_rifle_vault',(109,35,-47,131,125,-25)),('NERV_gateway',(-420,79,700,-292,105,819)),('gateway_lift',(-369,-490,741,-351,100,759)),('public_lift',(122,-448,264,138,100,282))]:p.protect(box,name)
    vaults=vox.WORLD/'r47_equipment_vaults.json'
    if vaults.is_file():
        for well in load(vaults)['vaults']:
            a,b=well['shell_bounds'];p.protect((a[0],a[1],a[2],b[0],max(b[1],125),b[2]),well['id'])
    for b in load(vox.ROOT/'artifacts/world_quality_r02/surface_layout.json')['kept_plots']:
        x,X,z,Z=b['bounds'];p.protect((x,b['floor'],z,X,b['floor']+b.get('storeys',1)*5+6,Z),b['id'])
    # Remove ONLY the old rail-bed strip before restoring its terrain. Station
    # footprints are replaced by explicit architecture later in this plan.
    old_columns={};natural_restore=defaultdict(dict)
    for r in old['curves']:
        if r['mode']!='TRAIN':continue
        for xx,yy,zz in r['points']:
            if yy<0:continue
            x,y,z=math.floor(xx),math.floor(yy),math.floor(zz)
            for dx in range(-3,4):
                for dz in range(-3,4):
                    pos=x+dx,z+dz;old_columns[pos]=min(y,old_columns.get(pos,y))
    for x,X,z,y in grouped(old_columns):
        for state in ('minecraft:gray_concrete','minecraft:polished_deepslate','minecraft:polished_blackstone','minecraft:deepslate_tiles','minecraft:smooth_stone','minecraft:quartz_block','minecraft:iron_block'):
            p.match((x,y-4,z,X,y+7,z),state,AIR,'r20/retire_ground_rail_formation')
    for (x,z),y in old_columns.items():
        if 0<=x-ox<nx and 0<=z-oz<nz:
            h=int(terrain['height'][z-oz,x-ox]);natural_restore[x//16,z//16][x%16,z%16]=h
    for (cx,cz),columns in natural_restore.items():
        heights=np.zeros((16,16),int);active=np.zeros((16,16),bool)
        for (x,z),y in columns.items():heights[z,x]=y;active[z,x]=True
        p.heightfield(cx,cz,heights,active,'r20/restore_ground_under_old_rails',np.zeros((16,16),bool))
    print('Old formation retirement planned',len(old_columns),flush=True);roads(p,terrain,old)
    print('Street continuity planned',p.meta['road_columns'],flush=True)
    walks=[];boards=[]
    for platform in old['platforms']:
        if platform['transportMode']=='TRAIN':station(p,platform,plan['platform_migrations'],native,walks,boards)
    # The union of measured track bodies is carved once after every civil
    # solid; a nearby sloping segment cannot refill another train's envelope.
    deck=defaultdict(set);core=defaultdict(set);supports=[]
    for r in native['curves']:
        if r['mode']!='TRAIN':continue
        points=r['points']
        for i,(xx,yy,zz) in enumerate(points):
            x,y,z=math.floor(xx),math.floor(yy),math.floor(zz)
            for dx in range(-3,4):
                for dz in range(-3,4):deck[x+dx,z+dz].add(y)
            for dx in range(-1,2):
                for dz in range(-1,2):core[x+dx,z+dz].add(y)
            if yy>=0 and i%43==0 and r['kind']=='rail':supports.append((x,y,z))
    for (x,z),ys in deck.items():
        for y in ys:ff(p,(x,y-3,z,x,y-1,z),DECK if y>=0 else 'projectseele:nerv_structural_panel','r20/native_rail_viaduct')
    # Slender piers stop at the ground, with foundations embedded into it.
    road=arrays(OUT/'road_contract.npz')
    support_boxes=[]
    for x,y,z in supports:
        if any(abs(x-q[0])<14 and abs(z-q[2])<14 for q in support_boxes):continue
        h=int(terrain['height'][z-oz,x-ox]) if 0<=x-ox<nx and 0<=z-oz<nz else min(y-14,70)
        onroad=0<=x-ox<nx and 0<=z-oz<nz and bool(road['mask'][z-oz,x-ox])
        if onroad:continue
        ff(p,(x-1,h-3,z-1,x+1,y-4,z+1),DECK,'r20/viaduct_pier');support_boxes.append((x,y,z))
    for (x,z),ys in core.items():
        for y in ys:
            ff(p,(x,y,z,x,y+5,z),AIR,'r20/native_train_body');ff(p,(x,y-1,z,x,y-1,z),'minecraft:gravel','r20/native_ballast')
    p.meta.update(boards=boards,walk_cases=walks,piers=support_boxes,old_rail_columns=len(old_columns),native_tracks=len([r for r in native['curves'] if r['mode']=='TRAIN']),source='Native MTR continuous geometry; real JR platform separation and access hierarchy',grade_separated_from_streets=True)
    p.save_plan('viaduct_stations_and_streets');print('R20 civil plan',len(p.ops),'ops',len(walks),'walk cases',flush=True)
if __name__=='__main__':main()
