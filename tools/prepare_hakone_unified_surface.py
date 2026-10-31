"""Cold, reversible reconciliation of saved terrain and commissioned structures.

The saved block arrays are the source of truth. Terrain may change around a
finite structure, but no entity, device, native transport record or tunnel is
recreated. The resulting atlas is also used by future terrain generation.
"""
import argparse,json,os,shutil,gzip,struct
from pathlib import Path
from collections import defaultdict,deque
import numpy as np
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from prepare_hakone_main_terrain import sample_grid
from plan_ashi_landscape_r54 import SOIL,NATURAL
from plan_hakone_main_districts import ROAD_MATERIALS
from hakone_earthworks import grade_ground,road_blocks
from query_blocks import AIR

def parcels(gis):
    original=json.loads((gis.parent/'world_quality_r02/surface_layout.json').read_text('utf8'))['kept_plots']
    rows={}
    for r in original:
        if 'storeys'not in r:continue
        x,X,z,Z=r['bounds'];y=r['floor'];rows[r['id']]=[x,y,z,X,y+r['storeys']*5+9,Z]
    for file in('main-district-current-ready-v2/neighbourhood.json','valley-integration-v12/valley-buildings.json'):
        data=json.loads((gis/file).read_text('utf8'))
        if isinstance(data,dict):data=data['buildings']
        for r in data:
            s=r['site'];x,z=s['centre'];hx,hz=s['half'];hx,hz=(hz,hx)if s['rotation']%2 else(hx,hz);y=s['floor']
            key=r.get('id',f'valley/{x}/{z}')
            rows[key]=[x-hx,y,z-hz,x+hx,y+s['floors']*5+9,z+hz]
    for file in('neighbourhood.json','retained-neighbourhood.json'):
        for r in json.loads((gis/'city-south-streets-v3'/file).read_text('utf8')):rows[r['id']]=r['bounds']
    rows['tokyo_south/02-07']=[-497,100,863,-455,128,905]
    return rows

def main(a):
    if a.phase=='prepare':prepare(a)
    else:terrain(a)

def prepare(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    for file in(a.source/'source').glob('*.npz'):os.link(file,a.out/'source'/file.name)
    for file in(a.base/'delta').glob('*.npz'):shutil.copy2(file,a.out/'delta'/file.name)
    measured=load_grid(a.source/'measured.npz');bounds=list(map(int,measured['bounds']));x0,z0,x1,z1=bounds
    atlas=load_grid(a.atlas/'surface-atlas.npz');rows=parcels(a.gis)
    city=load_grid(a.gis/'city-south-streets-v3/surface.npz')
    mainroad=load_grid(a.gis/'main-district-integration-v1/coupled-grading.npz')
    legacy=load_grid(a.gis/'main-district-integration-v1/district-plan.npz')
    oldroad=load_grid(a.gis.parent/'world_rebuild_r20/transit/civil/road_contract.npz')
    ox,oz=map(int,oldroad['origin']);oldroad['bounds']=[ox,oz,ox+oldroad['mask'].shape[1]-1,oz+oldroad['mask'].shape[0]-1]
    stations=json.loads((a.gis.parent/'access_r22/transit/civil/station_contract.json').read_text('utf8'))['stations']
    stationboxes=[]
    for r in stations:
        x,y,z=r['center'];h=r['half'];dx,dz=(h+2,20)if r['horizontal']else(20,h+2)
        stationboxes.append([x-dx,r['ground'],z-dz,x+dx,y+14,z+dz])
    bychunk=defaultdict(list)
    for box in list(rows.values())+stationboxes:
        x,y,z,X,Y,Z=box
        for cx in range(x//16,X//16+1):
            for cz in range(z//16,Z//16+1):bychunk[cx,cz].append(box)
    editor=Editor(a.out);anchor=np.full(atlas['height_y'].shape,-32768,np.int16)
    columns={};retired=0;plot_hits=defaultdict(int);yy=np.arange(-128,320)[:,None,None]
    for n,file in enumerate(sorted((a.out/'source').glob('*.npz'))):
        rx,rz=map(int,file.stem.split('.')[1:]);r=editor.region(rx*512,rz*512)
        def code(s):
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
            return r['ids'][s]
        air=code('minecraft:air');grass=code('minecraft:grass_block[snowy=false]');dirt=code('minecraft:dirt')
        names=[s.split('[')[0]for s in r['names']];paved=np.array([s in ROAD_MATERIALS for s in names]);soil=np.array([s in SOIL for s in names]);empty=np.array([s in AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass'}for s in names])
        concrete=np.array([s=='minecraft:light_gray_concrete'for s in names])
        for (cx,cz),b in zip(r['coords'],r['after']):
            cx,cz=int(cx),int(cz);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            lots=np.zeros((16,16),bool)
            for x,y,z,X,Y,Z in bychunk[cx,cz]:lots|=(xx>=x-2)&(xx<=X+2)&(zz>=z-2)&(zz<=Z+2)
            keep=sampled(mainroad,'walk',xx,zz).astype(bool)
            core=(xx>=-194)&(xx<=254)&(zz>=-4)&(zz<=444)
            corepaved=sampled(city,'paved',xx,zz)|sampled(city,'frame',xx,zz)|sampled(city,'paths',xx,zz)
            keep[core]=corepaved[core]
            # The fixed old city rectangle accidentally retained fragments of
            # both the retired roads and the later, clipped GIS strokes.
            oldmask=sampled(oldroad,'mask',xx,zz).astype(bool)|sampled(legacy,'legacy',xx,zz).astype(bool)|core
            area=(xx>=-832)&(xx<=1023)&(zz>=-640)&(zz<=1023)
            launch=(xx>=-110)&(xx<=225)&(zz<=15)
            retire=oldmask&area&~keep&~lots&~launch
            h=sampled(legacy,'legacy_y',xx,zz,14999)
            oh=(sampled(oldroad,'height2',xx,zz,30000)-1)//2
            band=(abs(yy-h)<=2)|(abs(yy-oh)<=2)|(core&(yy>=76)&(yy<=86))
            change=retire&band&paved[b]
            # Never replace a road material being used as a device backing.
            nonpave=np.array([s not in NATURAL|ROAD_MATERIALS for s in names])[b]
            near=np.zeros_like(change)
            for dy in range(1,4):near[:-dy]|=nonpave[dy:]
            change&=~near
            retired+=int(change.sum());b[change]=air
            top=np.where(soil[b],yy,-129).max(0)
            high=np.where(~empty[b],yy,-129).max(0)
            zlocal,xlocal=np.mgrid[:16,:16]
            # Exposed, small concrete stump components can be distinguished
            # from live decks, stations, walls and lamps by their complete top.
            ct=concrete[b[np.maximum(high+128,0),zlocal,xlocal]]&~lots&(high>top+3)
            for iz,ix in np.argwhere(ct):
                ys=np.flatnonzero(concrete[b[:,iz,ix]]&(np.arange(-128,320)>=max(32,top[iz,ix])))
                if len(ys)>=4:columns[int(xx[iz,ix]),int(zz[iz,ix])]=[int(v)-128 for v in ys]
            expos=paved[b]&empty[np.roll(b,-1,axis=0)]&empty[np.roll(b,-2,axis=0)]&(yy>=32)&(yy<=top+5)
            floor=np.where(expos,yy,-32768).max(0)
            valid=(xx>=atlas['x'][0])&(xx<=atlas['x'][-1])&(zz>=atlas['z'][0])&(zz<=atlas['z'][-1])&((xx-atlas['x'][0])%2==0)&((zz-atlas['z'][0])%2==0)&(floor!=-32768)
            iz,ix=np.nonzero(valid);az=(zz[iz,ix]-atlas['z'][0])//2;ax=(xx[iz,ix]-atlas['x'][0])//2
            anchor[az,ax]=floor[iz,ix]
        editor.save();editor.regions.clear();print('Surface ownership',n+1,'/',len(list((a.out/'source').glob('*.npz'))),flush=True)
    stumps=[];remaining=set(columns)
    while remaining:
        start=remaining.pop();todo=[start];group=[start]
        while todo:
            x,z=todo.pop()
            for q in((x-1,z),(x+1,z),(x,z-1),(x,z+1)):
                if q in remaining:remaining.remove(q);todo.append(q);group.append(q)
        xs,zs=zip(*group)
        if max(xs)-min(xs)>3 or max(zs)-min(zs)>3 or len(group)>16:continue
        stumps.append(dict(bounds=[min(xs),min(zs),max(xs),max(zs)],cells=sum(len(columns[q])for q in group)))
        for x,z in group:
            for y in columns[x,z]:editor.put(x,y,z,'minecraft:air')
        editor.save();editor.regions.clear()
    np.savez_compressed(a.out/'ground-anchors.npz',x=atlas['x'],z=atlas['z'],height=anchor)
    (a.out/'parcels.json').write_text(json.dumps(rows),'utf8')
    regions=editor.save();report=json.loads((a.base/'manifest.json').read_text('utf8'))
    report.update(regions=regions,cells=sum(r['cells']for r in regions),retired_road_cells=retired,retired_stumps=stumps,bounds_xz=bounds)
    (a.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Retired road cells',retired,'detached supports',len(stumps),flush=True)

def terrain(a):
    a.out.mkdir(exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    for file in(a.source/'source').glob('*.npz'):os.link(file,a.out/'source'/file.name)
    for file in(a.base/'delta').glob('*.npz'):shutil.copy2(file,a.out/'delta'/file.name)
    manifest=json.loads((a.base/'manifest.json').read_text('utf8'))
    atlas=load_grid(a.atlas/'surface-atlas.npz');measured=load_grid(a.source/'measured.npz')
    seams=[load_grid(a.seams/'gora-seam.npz'),load_grid(a.atlas/'shore-seam.npz')]
    occupied=defaultdict(list)
    retained_boxes=list(json.loads((a.atlas/'retained-parcels.json').read_text('utf8')).values())
    retained_boxes.append([-110,32,-120,225,160,15])
    for box in retained_boxes:
        x,y,z,X,Y,Z=box
        for cx in range(x//16,X//16+1):
            for cz in range(z//16,Z//16+1):occupied[cx,cz].append(box)
    original_piers=json.loads((a.gis.parent/'world_rebuild_r20/transit/civil/viaduct_stations_and_streets/places.json').read_text('utf8'))['piers']
    confirmed=[];restore=[]
    for s in manifest['retired_stumps']:
        b=s['bounds'];known=any(b[0]>=x-1 and b[2]<=x+1 and b[1]>=z-1 and b[3]<=z+1 for x,y,z in original_piers)
        (confirmed if known else restore).append(s)
    # A detached shape alone is insufficient provenance for deletion. Restore
    # decorative or unclassified pieces; retire only declared old bridge piers.
    byregion=defaultdict(list)
    for s in restore:
        b=s['bounds']
        for rx in range(b[0]//512,b[2]//512+1):
            for rz in range(b[1]//512,b[3]//512+1):byregion[rx,rz].append(b)
    e=Editor(a.out);yy=np.arange(-128,320)[:,None,None];errors=[];changed_roads=0
    mx,mz,_,_=map(int,measured['bounds']);sources=sorted((a.out/'source').glob('*.npz'))
    for number,file in enumerate(sources):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        names=r['names'];ids=r['ids']
        def code(s):
            if s not in ids:ids[s]=len(names);names.append(s)
            return ids[s]
        air,stone,dirt,grass,gravel,water,asphalt,paving,stripe,aslab,pslab,sslab=[code(s)for s in(
            'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:gravel','minecraft:water[level=0]',
            'minecraft:black_concrete','minecraft:smooth_stone','minecraft:white_concrete',
            'projectseele:road_asphalt_slab[type=bottom,waterlogged=false]','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]',
            'projectseele:road_marking_slab[type=bottom,waterlogged=false]')]
        natural=np.array([s.split('[')[0]in NATURAL for s in names]);soil=np.array([s.split('[')[0]in SOIL for s in names])
        empty=np.array([s.split('[')[0]in AIR for s in names]);paved=np.array([s.split('[')[0]in ROAD_MATERIALS for s in names])
        concrete=np.array([s=='minecraft:light_gray_concrete'for s in names])
        for (cx,cz),before,b in zip(r['coords'],r['before'],r['after']):
            cx,cz=int(cx),int(cz);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            for x,z,X,Z in byregion[rx,rz]:
                m=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&concrete[before]&empty[b]
                b[m]=before[m]
            top=np.where(soil[b],yy,-129).max(0)
            h=sample_grid(atlas,'height_y',xx,zz)
            distance=np.maximum.reduce([atlas['x'][0]-xx,xx-atlas['x'][-1],atlas['z'][0]-zz,zz-atlas['z'][-1],np.zeros((16,16),int)])
            blend=np.clip(distance/256,0,1);blend=blend*blend*(3-2*blend)
            h=np.rint(h*(1-blend)+top*blend).astype(np.int16)
            wet=sample_grid(atlas,'water',xx,zz,True).astype(np.int16);wet[distance>0]=-32768
            for s in seams:
                x,z,X,Z=s['bounds'];within=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)
                h[within]=sampled(s,'target',xx,zz)[within]
            # The original underground dome and its complete rock/armour cover
            # are not part of a surface grading patch.
            radius=np.hypot(xx-30,zz-296);t=np.clip((radius-600)/1200,0,1)
            ceiling=-478+np.floor(502*np.sqrt(np.maximum(0,1-t*t)))
            bottom=np.where(radius<1800,np.maximum(-128,ceiling+18),-128).astype(int)
            h=np.maximum(h,bottom)
            foreign=(~natural[b])&(yy>=bottom)
            lo=np.where(foreign,yy,320).min(0)-1;hi=np.where(foreign,yy,-129).max(0)+4
            volume=(yy>=lo)&(yy<=hi)
            lower=np.maximum(bottom,np.minimum(top,h)-3)
            oldwater=np.array([s.split('[')[0]=='minecraft:water'for s in names])[b]
            obsolete_water=(oldwater&(yy>np.maximum(h+3,wet))).any(0)
            active=(h!=top)|obsolete_water
            band=(yy>=lower)&natural[b]&(distance<256)&active
            # Retain the AIR of actual buildings/tunnels. Unlike the old
            # whole-column exclusion this does not retain stray soil above them.
            band&=~(empty[b]&volume&(yy<=h))
            # Timber and leaf blocks can also belong to an authored building.
            band&=~(volume&~soil[b]&~empty[b]&~oldwater)
            for x,y,z,X,Y,Z in occupied[cx,cz]:
                band&=~((xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&(yy>=y)&(yy<=Y))
            for s in seams:band&=~sampled(s,'fixed',xx,zz).astype(bool)
            proposal=np.where(yy>h,np.where(yy<=wet,water,air),np.where(yy==h,np.where(wet>h,gravel,grass),np.where(yy>=h-3,dirt,stone))).astype(np.uint16)
            b[band]=proposal[band]
            for s in seams:
                walk=sampled(s,'walk',xx,zz).astype(bool)&~sampled(s,'plots',xx,zz).astype(bool)&~sampled(s,'fixed',xx,zz).astype(bool)
                grade=sampled(s,'grade2',xx,zz);road=sampled(s,'road',xx,zz).astype(bool);rh,slab=road_blocks(grade)
                oldh=sampled(s,'old_target',xx,zz)
                envelope=walk&(yy>=np.minimum(oldh,rh)-2)&(yy<=np.maximum(oldh,rh)+5)
                allowed=natural[b]|paved[b]
                collision=(envelope&~allowed&(yy>rh)&(yy<=rh+3)).any(0)
                for iz,ix in np.argwhere(walk&collision):errors.append(['retained-object-on-regraded-road',int(xx[iz,ix]),int(rh[iz,ix]),int(zz[iz,ix])])
                safe=walk&~collision
                retire=envelope&paved[b]&safe&(yy>rh);b[retire]=air
                clear=safe&(yy>rh)&(yy<=rh+4)&allowed;b[clear]=air
                b[safe&(yy==rh-1)&allowed]=stone
                material=np.where(road,np.where(slab,aslab,asphalt),np.where(slab,pslab,paving))
                floor=safe&(yy==rh)&allowed;b[floor]=np.broadcast_to(material,b.shape)[floor]
                changed_roads+=int(safe.sum())
        e.save();e.regions.clear();print('Unified terrain',number+1,'/',len(sources),flush=True)
    regions=e.save();manifest.update(regions=regions,cells=sum(r['cells']for r in regions),retired_stumps=confirmed,
        restored_unclassified_components=len(restore),regraded_road_columns=changed_roads,terrain_atlas=str(a.atlas),world_written=False)
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors+[['pending','device/footing/recipe composition']],visual_verified=False),indent=2),'utf8')
    print('Prepared terrain cells',manifest['cells'],'road conflicts',len(errors),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--phase',choices=['prepare','terrain'],required=True)
    for name in('source','base','atlas','gis','out','seams'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
