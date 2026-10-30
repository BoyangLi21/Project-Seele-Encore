"""Prepare continuous surveyed valley terrain, half-step roads and river beds."""
import argparse,gzip,json,shutil,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from prepare_hakone_main_terrain import sample_grid,smooth,MIN_Y,MAX_Y
from prepare_hakone_lake_basin import distance_from
from plan_ashi_landscape_r54 import NATURAL
from plan_hakone_main_districts import ROAD_MATERIALS
from hakone_earthworks import road_blocks


def prepare(a):
    if a.out.exists():raise ValueError('Use a fresh uninstalled valley candidate')
    (a.out/'source').mkdir(parents=True);(a.out/'delta').mkdir()
    capture=json.loads((a.source/'capture.json').read_text('utf8'));bounds=capture['bounds_xz'];x0,z0,x1,z1=bounds
    if capture['unavailable_chunks']:raise ValueError('Native terrain must be complete before corridor construction')
    for file in(a.source/'source').glob('*.npz'):shutil.copy2(file,a.out/'source'/file.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json');shutil.copy2(a.source/'measured.npz',a.out/'measured.npz')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=['Valley terrain preparation incomplete'])))
    with np.load(a.source/'measured.npz')as f:m={k:f[k]for k in f.files}
    shape=m['top'].shape;zz,xx=np.mgrid[z0:z1+1,x0:x1+1];yy=np.arange(-128,320)[:,None,None]
    with np.load(a.gis/'terrain-design.npz')as f:grid={k:f[k]for k in('x','z','height_y','sea','inland_water')}
    height=sample_grid(grid,'height_y',xx,zz);sea=sample_grid(grid,'sea',xx,zz,True)
    legacy=np.zeros(shape,bool);legacy_y=np.zeros(shape,np.int16)
    with np.load('F:/eva/artifacts/world_quality_r02/road_surfaces.npz')as f:
        origin=f['origin'];mask=f['mask'];h=f['height2'];left,top=max(x0,int(origin[0])),max(z0,int(origin[1]));right,bottom=min(x1+1,int(origin[0])+mask.shape[1]),min(z1+1,int(origin[1])+mask.shape[0])
        if right>left and bottom>top:
            src=np.s_[top-origin[1]:bottom-origin[1],left-origin[0]:right-origin[0]];dst=np.s_[top-z0:bottom-z0,left-x0:right-x0]
            legacy[dst]=mask[src];legacy_y[dst]=h[src]//2-1
    protected=np.zeros(shape,bool)
    for file in sorted((a.out/'source').glob('*.npz')):
        with np.load(file)as f:coords=f['coordinates'];blocks=f['blocks'];names=list(map(str,f['palette']))
        natural=np.asarray([s.split('[')[0]in NATURAL for s in names]);oldroad=np.asarray([s.split('[')[0]in ROAD_MATERIALS for s in names])
        for (cx,cz),b in zip(coords,blocks):
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16]
            allowed=natural[b]|(oldroad[b]&legacy[area][None,:,:]&(yy>=legacy_y[area]-2)&(yy<=legacy_y[area]+8))
            lower=np.minimum(m['top'][area],height[area])-4
            upper=np.maximum(m['highest'][area],height[area]+5)
            protected[area]=((~allowed)&(yy>=lower)&(yy<=upper)).any(0)
    protected|=m['actors']
    # Keep the newly commissioned Gora interchange and every old inhabited
    # component. Valley work changes natural ground, not device identities.
    protected[(zz>=578)&(zz<=699)&(xx>=900)&(xx<=1023)]=True
    held=np.asarray(Image.fromarray(protected).filter(ImageFilter.MaxFilter(9)),bool)
    lake=np.zeros(shape,bool)
    if getattr(a,'preserve_lake',False):
        with np.load(a.gis/'lake-basin-mask.npz')as f:water_grid={k:f[k]for k in ('x','z','lake')}
        lake=sample_grid(water_grid,'lake',xx,zz,True)
        held=held|lake
    border=np.minimum.reduce([xx-x0,x1-xx,zz-z0,z1-zz]);blend=smooth(np.minimum(distance_from(held,32),border)/32)
    target=np.rint(m['top']+(height-m['top'])*blend).astype(np.int16);target=np.clip(target,-120,305)
    features=json.load(gzip.open(a.gis/'features.world.geojson.gz','rt',encoding='utf8'))['features']
    def blank():return Image.new('L',(shape[1],shape[0]))
    roadim,walkim,markim,riverim,bridgeim=blank(),blank(),blank(),blank(),blank();streets=[];rivers=[];tunnels=[]
    for f in features:
        p=f['properties'];g=f['geometry'];kind=p['source_layer']
        if g['type']!='LineString'or kind not in('RdCL','RvrCL'):continue
        points=g['coordinates']
        if not any(x0-16<=x<=x1+16 and z0-16<=z<=z1+16 for x,z in points):continue
        local=[(round(x-x0),round(z-z0))for x,z in points];code=int(p['vt_code'])
        if kind=='RvrCL':
            ImageDraw.Draw(riverim).line(local,fill=1,width=3);rivers.append(points);continue
        pedestrian=code in(2721,2731);tunnel=code in(2704,2714);bridge=code in(2703,2713)
        width=0 if pedestrian else 7 if p.get('vt_rdctg')in('国道','都道府県道')else 3
        record=dict(points=points,width=width,tunnel=tunnel,bridge=bridge,code=code)
        streets.append(record)
        if tunnel:tunnels.append(record);continue
        ImageDraw.Draw(walkim).line(local,fill=1,width=3 if pedestrian else width+4)
        if width:ImageDraw.Draw(roadim).line(local,fill=1,width=width)
        if width>=7:ImageDraw.Draw(markim).line(local,fill=1,width=1)
        if bridge:ImageDraw.Draw(bridgeim).line(local,fill=1,width=width+4)
    road=np.asarray(roadim,bool)&~held;walk=(np.asarray(walkim,bool)|road)&~held
    river=np.asarray(riverim,bool)&~held;bridge=(np.asarray(bridgeim,bool)|(walk&river))&walk
    marking=np.asarray(markim,bool)&road
    road2=np.rint(height*2).astype(np.int16)
    # Game-adapted grades are half-block increments, including intersections.
    for iteration in range(512):
        changed=0
        for dst,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),(np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            active=walk[dst]&walk[src]&(road2[dst]>road2[src]+1);changed+=int(active.sum());road2[dst][active]=road2[src][active]+1
        if not changed:break
    else:raise ValueError('Half-step road grades did not converge')
    target[walk]=road2[walk]//2
    water_y=np.rint(height-1).astype(np.int16);water_y[sea]=-82
    wet=(river|sea)&~held&~walk
    target[wet]=np.minimum(target[wet],water_y[wet]-2)
    target[river&~walk&~held]=water_y[river&~walk&~held]-2
    # Feather road cut/fill shoulders back into the surveyed mountain slope.
    roadnear=np.asarray(Image.fromarray(walk).filter(ImageFilter.MaxFilter(9)),bool)&~held
    shoulder=roadnear&~walk&~wet
    for _ in range(4):
        for dst,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),(np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            use=shoulder[dst]&roadnear[src];target[dst][use]=np.clip(target[dst][use],target[src][use]-2,target[src][use]+2)
    surfaces=['minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:water[level=0]',
              'minecraft:black_concrete','minecraft:smooth_stone','minecraft:white_concrete',
              'projectseele:road_asphalt_slab[type=bottom,waterlogged=false]','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]',
              'projectseele:road_marking_slab[type=bottom,waterlogged=false]','minecraft:gravel']
    rows=[];total=0
    for number,file in enumerate(sorted((a.out/'source').glob('*.npz'))):
        with np.load(file)as f:coords=f['coordinates'];blocks=f['blocks'];palette=list(map(str,f['palette']))
        ids={s:i for i,s in enumerate(palette)}
        for s in surfaces:
            if s not in ids:ids[s]=len(palette);palette.append(s)
        codes=np.array([ids[s]for s in surfaces],np.uint16);atlist=[];before=[];after=[];ranges=[0];chosen=[]
        for (cx,cz),old in zip(coords,blocks):
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16];h=target[area]
            lower=np.minimum(m['top'][area],h)-3;upper=np.maximum(m['highest'][area],h+5)
            band=(~held[area])[None,:,:]&(yy>=lower)&(yy<=upper)
            proposed=np.where(yy>h,0,np.where(yy==h,3,np.where(yy>=h-3,2,1))).astype(np.uint16)
            proposed[wet[area][None,:,:]&(yy>h)&(yy<=water_y[area])]=4
            w=walk[area];r=road[area];y,odd=road_blocks(road2[area])
            # Finished top is y+1 for a full block and y+.5 for a bottom slab.
            topcode=np.where(r,np.where(marking[area]&(xx[area]%9<5),7,5),6)
            topcode=np.where(odd,np.where(topcode==5,8,np.where(topcode==7,10,9)),topcode)
            proposed=np.where(w[None,:,:]&(yy==y),topcode[None,:,:],proposed)
            proposed=np.where(w[None,:,:]&(yy>y)&(yy<=y+5),0,proposed)
            # Bridges retain the river void underneath their structural deck.
            br=bridge[area]
            proposed=np.where(br[None,:,:]&(yy==y-1),1,proposed)
            proposed=np.where(br[None,:,:]&(yy<y-1)&(yy>=water_y[area]-1),np.where(yy<=water_y[area],4,0),proposed)
            replacement=codes[proposed];offsets=np.flatnonzero((band&(old!=replacement)).ravel()).astype(np.uint32)
            if not len(offsets):continue
            chosen.append((cx,cz));atlist.append(offsets);before.append(old.ravel()[offsets]);after.append(replacement.ravel()[offsets]);ranges.append(ranges[-1]+len(offsets))
        if chosen:
            np.savez_compressed(a.out/'delta'/file.name,coordinates=np.array(chosen,np.int32),ranges=np.array(ranges,np.int64),indices=np.concatenate(atlist),before=np.concatenate(before),after=np.concatenate(after),palette=np.array(palette))
            rows.append(dict(path='delta/'+file.name,cells=ranges[-1]));total+=ranges[-1]
        print('Prepared valley',number+1,'regions;',total,'cells',flush=True)
    blockedroad=np.asarray(walkim,bool)&held
    np.savez_compressed(a.out/'valley-surface.npz',bounds=bounds,target=target,road2=road2,road=road,walk=walk,river=river,wet=wet,water_y=water_y,held=held,protected=protected,bridge=bridge,blocked_road=blockedroad)
    report=dict(world=capture['world'],bounds_xz=bounds,regions=rows,cells=total,world_written=False,streets=streets,rivers=rivers,
                native_transit_installed=False,progress_files_written=[],pending=['railway earthworks','station neighbourhoods','retained road crossings','cold installation and LOD'])
    (a.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=['Station/corridor composition still pending'],road_grade_halfsteps=1,original_objects_preserved=True)),'utf8')
    print(json.dumps(dict(cells=total,roads=len(streets),rivers=len(rivers),held_road_cells=int(blockedroad.sum()))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--preserve-lake',action='store_true',help='Keep the already installed full lake basin; compose shore infrastructure separately')
    for name in('gis','source','out'):p.add_argument('--'+name,type=Path,required=True)
    prepare(p.parse_args())
