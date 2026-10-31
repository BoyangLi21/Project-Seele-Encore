"""Compose complete road widths, finite rooms and terrain into current arrays.

Unknown devices are never treated as paving. This offline composer emits their
conflicts for explicit design correction and never gates running gameplay.
"""
import argparse,copy,gzip,json,os,struct
from collections import defaultdict
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from prepare_hakone_main_terrain import sample_grid
from plan_ashi_landscape_r54 import NATURAL,SOIL
from plan_hakone_main_districts import ROAD_MATERIALS
from complete_hakone_transport_surface import station_boxes
from query_blocks import AIR,iter_block_entities
from hakone_earthworks import road_blocks


def lower_buildings(a,e,moves):
    changes={};record=[]
    for m in moves:
        x,y,z,X,Y,Z=m['before'];dy=m['dy'];ny=y+dy
        # Include the complete eaves and chimney above the catalog's roof line.
        box=[x-5,y,z-5,X+5,Y+8,Z+5]
        cells={(xx,yy,zz):e.state(xx,yy,zz)for xx in range(box[0],box[3]+1)for zz in range(box[2],box[5]+1)for yy in range(y,Y+9)}
        devices=dict(iter_block_entities(a.world,'projectseele:geofront',tuple(box[:3]),tuple(box[3:])))
        for xx in range(box[0],box[3]+1):
            for zz in range(box[2],box[5]+1):
                e.fill(xx,ny,zz,xx,Y+8,zz,'minecraft:air')
        for (xx,yy,zz),s in cells.items():e.put(xx,yy+dy,zz,s)
        for pos,tag in devices.items():
            changes.setdefault(pos,{})['Before']=copy.deepcopy(tag)
            q=(pos[0],pos[1]+dy,pos[2]);new=copy.deepcopy(tag);new['y']=nbtlib.Int(q[1])
            changes.setdefault(q,{})['After']=new
        record.append(dict(**m,devices=len(devices),complete_bounds=box))
    if changes:nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([nbtlib.Compound(v)for v in changes.values()])}).save(a.out/'block-entities.dat',gzipped=True)
    (a.out/'building-moves.json').write_text(json.dumps(record,indent=2),'utf8')
    e.save();e.regions.clear()


def compose(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    for f in(a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    d=load_grid(a.plan/'network.npz');catalog=json.loads((a.plan/'catalog.json').read_text('utf8'));moves=json.loads((a.plan/'building-moves.json').read_text('utf8'))
    e=Editor(a.out);lower_buildings(a,e,moves)
    occupied=defaultdict(list)
    boxes=[r['occupied_bounds']for r in catalog]+json.loads((a.plan/'station-volumes.json').read_text('utf8'))+[[-110,25,-155,225,180,15],[-425,20,690,-285,180,830],[350,63,-177,1350,123,86]]
    for x,y,z,X,Y,Z in boxes:
        margin=0 if (x,z,X,Z)in[(-110,-155,225,15),(-425,690,-285,830)]else 2
        box=[x-margin,y-1,z-margin,X+margin,Y+8,Z+margin]
        for cx in range(box[0]//16,box[3]//16+1):
            for cz in range(box[2]//16,box[5]//16+1):occupied[cx,cz].append(box)
    # Complete native beds, with each elevation retained separately where
    # several railways cross. Their route identities never change here.
    beds=defaultdict(dict);curves=json.loads((a.plan/'native-curves.json').read_text('utf8'))
    for curve in curves['trains']:
        for px,py,pz in curve['points']:
            x,y,z=map(int,np.floor([px,py,pz]))
            if not -120<y<310:continue
            for X in range(x-2,x+3):
                for Z in range(z-2,z+3):beds[X//16,Z//16].setdefault((X,Z),set()).add(y)
    legacy=load_grid(a.gis.parent/'world_rebuild_r20/transit/civil/road_contract.npz')
    ox,oz=map(int,legacy['origin']);legacy['bounds']=[ox,oz,ox+legacy['mask'].shape[1]-1,oz+legacy['mask'].shape[0]-1]
    errors=[];counts=defaultdict(int);changed=set();yy=np.arange(-128,320)[:,None,None]
    before_missing=defaultdict(int);after_missing=defaultdict(int)
    editable_roads={'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:smooth_stone',
        'minecraft:smooth_stone_slab','minecraft:yellow_concrete','minecraft:yellow_terracotta','minecraft:polished_blackstone_slab',
        'minecraft:stone_bricks','minecraft:stone_brick_stairs','minecraft:stone_brick_slab',
        'projectseele:road_asphalt_slab','projectseele:road_marking_slab','minecraft:polished_deepslate','minecraft:blackstone_slab','projectseele:nerv_floor_panel'}
    road_decor=editable_roads|{'minecraft:sea_lantern','minecraft:iron_bars','minecraft:stone_brick_wall','minecraft:polished_andesite'}
    for f in sorted((a.out/'source').glob('*.npz')):
        rx,rz=map(int,f.stem.split('.')[1:]);X,Z=np.meshgrid(np.arange(rx*512,rx*512+512),np.arange(rz*512,rz*512+512))
        inside=(X>=d['bounds'][0])&(X<=d['bounds'][2])&(Z>=d['bounds'][1])&(Z<=d['bounds'][3])
        hasrail=any(cx//32==rx and cz//32==rz for cx,cz in beds)
        if not inside.any()and not hasrail:continue
        r=e.region(rx*512,rz*512)
        def code(s):
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
            return r['ids'][s]
        air,stone,dirt,grass,asphalt,paving,stripe,aslab,pslab,sslab,bed=[code(s)for s in(
            'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]',
            'minecraft:black_concrete','minecraft:smooth_stone','minecraft:white_concrete',
            'projectseele:road_asphalt_slab[type=bottom,waterlogged=false]','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]',
            'projectseele:road_marking_slab[type=bottom,waterlogged=false]','minecraft:light_gray_concrete')]
        bare=[s.split('[')[0]for s in r['names']]
        flowers={'minecraft:'+s for s in ('dandelion','poppy','blue_orchid','allium','azure_bluet','red_tulip','orange_tulip','white_tulip','pink_tulip','oxeye_daisy','cornflower','lily_of_the_valley')}
        natural=np.array([s in NATURAL|flowers for s in bare]);soil=np.array([s in SOIL for s in bare]);empty=np.array([s in AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern'}for s in bare]);water=np.array([s=='minecraft:water'for s in bare])
        pave=np.array([s in editable_roads for s in bare]);decor=np.array([s in road_decor for s in bare]);allowed=natural|pave
        rail_material=np.array([s=='minecraft:light_gray_concrete'for s in bare])
        for (cx,cz),old,v in zip(r['coords'],r['before'],r['after']):
            cx,cz=int(cx),int(cz);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            inside=(xx>=d['bounds'][0])&(xx<=d['bounds'][2])&(zz>=d['bounds'][1])&(zz<=d['bounds'][3])
            walk=sampled(d,'walk',xx,zz).astype(bool)&inside;road=sampled(d,'road',xx,zz).astype(bool)&inside;core=sampled(d,'core',xx,zz).astype(bool)&inside
            grade=sampled(d,'grade2',xx,zz);rh,slab=road_blocks(grade)
            protect=np.zeros(v.shape,bool)
            rooms=np.zeros(v.shape,bool)
            for x,y,z,X,Y,Z in occupied[cx,cz]:protect|=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&(yy>=y)&(yy<=Y)
            rooms[:]=protect
            rail_y=np.full((16,16),32767,np.int16)
            for (x,z),ys in beds[cx,cz].items():
                for y in ys:
                    protect[max(0,y-3+128):min(448,y+8+128),z%16,x%16]=True
                    if abs(y-int(rh[z%16,x%16]))<abs(int(rail_y[z%16,x%16])-int(rh[z%16,x%16])):rail_y[z%16,x%16]=y
            # The railway owns its actual deck and devices. Empty clearance and
            # geological soil below it are not protected structural solids.
            railspace=protect&~rooms
            protect=rooms|(railspace&~natural[v]&~pave[v])
            # Replaced legacy street decks include their own lamps/guardrails,
            # not just two vertical pixels around the asphalt surface.
            oldmask=sampled(legacy,'mask',xx,zz).astype(bool)
            lh=(sampled(legacy,'height2',xx,zz,30000)-1)//2
            replaced=((xx>=-832)&(xx<=1023)&(zz>=-640)&(zz<=1023))|((xx>=896)&(xx<=2431)&(zz>=512)&(zz<=1407))
            retired=oldmask&replaced&~walk&~core&(yy>=lh-2)&(yy<=lh+10)&decor[v]&~protect
            if 'retired_fragments'in d:
                fragments=sampled(d,'retired_fragments',xx,zz).astype(bool)&~walk
                previous=sampled(d,'old_ground',xx,zz)
                retired|=fragments&(yy>=previous-3)&(yy<=previous+8)&decor[v]&~protect
            counts['retired_legacy_cells']+=int(retired.sum());v[retired]=air
            top=np.where(soil[v],yy,-129).max(0);h=sampled(d,'ground',xx,zz).astype(np.int16)
            radius=np.hypot(xx-30,zz-296);t=np.clip((radius-600)/1200,0,1)
            bottom=np.where(radius<1800,np.maximum(-128,-478+np.floor(502*np.sqrt(np.maximum(0,1-t*t)))+18),-128).astype(np.int16)
            h=np.maximum(h,bottom)
            # Finite authored rooms replace the old lowest-to-highest foreign
            # column rule; a lamp above a valley no longer freezes a soil pillar.
            affected=(h!=sampled(d,'old_ground',xx,zz))|retired.any(0)|walk
            active=inside&affected&~sampled(d,'tunnel',xx,zz).astype(bool)&(h!=top)&~water[v].any(0)
            band=active&natural[v]&(yy>=np.maximum(bottom,np.minimum(h,top)-3))&~protect
            # Uncatalogued constructions retain a small local backing/void;
            # never the whole column up to another unrelated overhead object.
            unknown=(~natural[v])&~pave[v]&~protect
            guard=unknown.copy()
            for dy in(1,2):guard[dy:]|=unknown[:-dy];guard[:-dy]|=unknown[dy:]
            band&=~guard
            target=np.where(yy>h,air,np.where(yy==h,grass,np.where(yy>=h-3,dirt,stone)))
            counts['terrain_cells']+=int((band&(v!=target)).sum());v[band]=np.broadcast_to(target,v.shape)[band]
            if walk.any():
                z,x=np.mgrid[:16,:16]
                before_missing['floor']+=int((walk&~pave[old[rh+128,z,x]]).sum())
                # Reserved AIR beneath an overhead railway is still a valid
                # street. Only actual retained solids/devices can obstruct it.
                body=(yy>rh)&(yy<=rh+2)
                railway_floor=(rh<=rail_y-1)&(rail_y<32767)
                floor_protection=rooms|(protect&~railway_floor)
                floor_allowed=allowed[v]|rail_material[v]
                obstruction=walk&(((~allowed[v]|(protect&~empty[v]))&body).any(0)
                    |((~floor_allowed|floor_protection)&~pave[v]&(yy==rh)).any(0))
                already=walk&(pave[v[rh+128,z,x]]|rail_material[v[rh+128,z,x]])&empty[v[rh+129,z,x]]&empty[v[rh+130,z,x]]
                obstruction&=~already
                for iz,ix in np.argwhere(obstruction):
                    y=int(rh[iz,ix]);states=[r['names'][v[Y+128,iz,ix]]for Y in range(y,y+4)]
                    errors.append(['road-object',int(xx[iz,ix]),y,int(zz[iz,ix]),states])
                safe=walk&~obstruction
                envelope=safe&(yy>=np.maximum(bottom,np.minimum(top,rh)-2))&(yy<=np.maximum(top,rh)+5)&allowed[v]&~protect
                v[envelope&(yy>rh)]=air
                wetcol=water[v].any(0)
                v[envelope&(yy<rh)&(~wetcol|(yy==rh-1))&~water[v]]=stone
                material=np.where(road,np.where(slab,aslab,asphalt),np.where(slab,pslab,paving))
                marking=sampled(d,'marking',xx,zz).astype(bool)if 'marking'in d else np.zeros((16,16),bool)
                material=np.where(marking,np.where(slab,sslab,stripe),material)
                # Keep the engineered core's existing crossings and lane marks.
                retain=core&pave[old[rh+128,z,x]]
                material[retain]=old[rh+128,z,x][retain]
                floor=safe&(yy==rh)&~floor_protection;v[floor]=np.broadcast_to(material,v.shape)[floor]
                counts['road_columns']+=int(safe.sum())
                after_missing['floor']+=int((walk&~pave[v[rh+128,z,x]]).sum())
            # Existing operational rails get a continuous narrow structural bed.
            # Station rooms retain their detailed native platform construction.
            for(x,z),ys in beds[cx,cz].items():
                for y in ys:
                    iz,ix=z%16,x%16;Y=y-1
                    if any(b[0]<=x<=b[3]and b[2]<=z<=b[5]and b[1]<=Y<=b[4]for b in occupied[cx,cz]):continue
                    if empty[v[Y+128,iz,ix]]:
                        v[Y+128,iz,ix]=bed;counts['native_bed_cells']+=1
            if np.any(v!=old):changed.add((cx,cz))
        e.save();e.regions.clear();print('Composed complete network',f.name,dict(counts),flush=True)
    regions=e.save();manifest=dict(world=str(a.world),regions=regions,cells=sum(r['cells']for r in regions),bounds_xz=list(map(int,d['bounds'])),world_written=False,counts=dict(counts))
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,full_width_before=dict(before_missing),full_width_after=dict(after_missing),visual_verified=False),indent=2),'utf8')
    (a.out/'transport-changed-chunks.json').write_text(json.dumps(sorted(changed)),'utf8')
    (a.out/'catalog.json').write_bytes((a.plan/'catalog.json').read_bytes())
    print('Prepared cells',manifest['cells'],'road object conflicts',len(errors),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('gis','source','plan','out','world'):p.add_argument('--'+n,type=Path,required=True)
    compose(p.parse_args())
