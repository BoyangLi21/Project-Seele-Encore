"""Measured continuous east GeoFront ridges/valley ghost; no world write path."""
from pathlib import Path
import argparse,gzip,json,math,hashlib,shutil
import numpy as np
from scipy.ndimage import distance_transform_edt
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from plan_new_city_blocks_r44 import SOIL,SMALL

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def smooth(t):t=np.clip(t,0,1);return t*t*(3-2*t)


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    x0,x1,z0,z1=720,1080,560,940;w=MeasuredWorld(WORLD);w.box((x0-8,-530,z0-8),(x1+8,-350,z1+8));w.load()
    shape=(z1-z0+1,x1-x0+1);tops=np.full(shape,-32768,np.int16);wood=np.zeros(shape,bool);foreign=np.zeros(shape,bool)
    for (cx,sy,cz),(pal,ids) in w.tiles.items():
        ax,bx=max(x0,cx*16),min(x1,cx*16+15);az,bz=max(z0,cz*16),min(z1,cz*16+15)
        if ax>bx or az>bz:continue
        names=[s.split('[')[0] for s in pal];local=ids.reshape(16,16,16)[:,az-cz*16:bz-cz*16+1,ax-cx*16:bx-cx*16+1];dest=(slice(az-z0,bz-z0+1),slice(ax-x0,bx-x0+1));yy=np.arange(16)[:,None,None]+sy*16
        tops[dest]=np.maximum(tops[dest],np.where(np.array([n in SOIL for n in names])[local],yy,-32768).max(0));wood[dest]|=np.array([n.endswith(('_log','_leaves')) for n in names])[local].any(0);foreign[dest]|=np.array([not n.startswith('minecraft:') for n in names])[local].any(0)
    X,Z=np.meshgrid(np.arange(x0,x1+1),np.arange(z0,z1+1));full=np.array([w.status.get((x//16,z//16))=='full' for z in range(z0,z1+1) for x in range(x0,x1+1)]).reshape(shape)
    provider_path=WORLD/'datapacks/tv_world_preview/data/projectseele/dimension/geofront.json';provider=json.loads(provider_path.read_text('utf8'));volumes=provider['generator']['biome_source']['protected_volumes'];protection=np.zeros(shape,bool)
    for x,y,z,A,Y,C in volumes:
        if Y<-520 or y>-350:continue
        protection|=(X>=x-24)&(X<=A+24)&(Z>=z-24)&(Z<=C+24)
    radial=np.hypot(X-30,Z-296);central=radial<650
    edge=np.minimum.reduce([X-x0,x1-X,Z-z0,z1-Z]);t=(X-x0)/(x1-x0)
    north_axis=630+.42*(X-x0)+18*np.sin((X-x0)/90);south_axis=850+.10*(X-x0)+12*np.sin((X+35)/75)
    first=(24+44*t)*np.exp(-((Z-north_axis)/82)**2);second=(18+32*t)*np.exp(-((Z-south_axis)/70)**2)
    # Trees grow on the landform; their fixed-position clearance must not
    # bend an entire ridge into a crater. A touched tree fails the exact
    # material check below until its whole component has a relocation plan.
    distance=distance_transform_edt(~(foreign|protection|central|(~full)))
    rise=np.maximum(first,second)*smooth(edge/100)*smooth((distance-16)/40)
    ceilings=-478+np.floor(502*np.sqrt(np.maximum(0,1-np.clip((radial-600)/1200,0,1)**2)))
    target=np.minimum(tops+np.rint(rise).astype(np.int16),ceilings.astype(np.int16)-24)
    eligible=full&(tops>-32768)&(~foreign)&(~protection)&(~central)&(radial<1776)&(target>tops)
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x0,-530,z0),(x1,-350,z1),selected_chunks=set(w.selected)))
    # The two whole ridges share one immutable height field. Sector files are
    # ordinary exact construction transactions, not ecology queue slices.
    manifests=[];held=[];total=0
    for sector,start in enumerate(range(x0,x1+1,48)):
        end=min(x1,start+47);folder=a.output/f'sector_{sector:02d}';folder.mkdir();count=0
        with gzip.open(folder/'forward.jsonl.gz','wt',encoding='utf8') as forward,gzip.open(folder/'inverse.jsonl.gz','wt',encoding='utf8') as inverse:
            for zz in range(z0,z1+1):
                for xx in range(start,end+1):
                    j,i=zz-z0,xx-x0
                    if not eligible[j,i]:continue
                    before_y=int(tops[j,i]);after_y=int(target[j,i]);column=[];bad=[]
                    for yy in range(before_y,after_y+1):
                        q=(xx,yy,zz);old=w.block(q);name=(old or '').split('[')[0]
                        if old is None or q in tags or name not in SOIL|SMALL|AIR:bad.append(dict(pos=q,state=old));continue
                        state='minecraft:grass_block[snowy=false]' if yy==after_y else 'minecraft:dirt' if yy>=after_y-3 else 'minecraft:stone'
                        if old!=state:column.append(dict(pos=q,before=old,after=state,before_nbt=None,after_nbt=None,owner='r44/geofront/east_continuous_ranges',reason='Measured continuous ridge/valley landform; full original soil, woods, infrastructure, central view disc and spherical roof boundary protected'))
                    if bad:held.extend(bad);continue
                    for row in column:
                        forward.write(json.dumps(row)+'\n');back=dict(row,before=row['after'],after=row['before']);inverse.write(json.dumps(back)+'\n');count+=1
        total+=count;manifests.append(dict(sector=sector,bounds=[start,-530,z0,end,-350,z1],changed_cells=count,forward=str((folder/'forward.jsonl.gz').resolve()),inverse=str((folder/'inverse.jsonl.gz').resolve()),forward_sha256=hashlib.sha256((folder/'forward.jsonl.gz').read_bytes()).hexdigest()))
    np.savez_compressed(a.output/'whole_heightfield.npz',origin=[x0,z0],before=tops,after=target,eligible=eligible,wood=wood,foreign=foreign,protection=protection,ceilings=ceilings)
    sources=[Path(__file__),ROOT/'tools/measure_world_r40.py',ROOT/'tools/query_blocks.py',ROOT/'tools/regional_voxels.py',ROOT/'tools/information_fixture_guard_r44.py',ROOT/'src/main/java/com/projectseele/world/TvWorldPreviewTerrain.java',ROOT/'src/main/java/com/projectseele/world/GeoFrontBoundedChunkGenerator.java',provider_path];snapshot=a.output/'source_inputs';snapshot.mkdir();epochs=[]
    for i,f in enumerate(sources):
        copy=snapshot/(str(i)+'_'+f.name);shutil.copy2(f,copy);epochs.append(dict(path=str(copy.resolve()),original_path=str(f.resolve()),sha256=hashlib.sha256(copy.read_bytes()).hexdigest(),immutable_snapshot=True))
    result=dict(world=str(WORLD),whole_sector_bounds=[x0,-530,z0,x1,-350,z1],changed_cells=total,sectors=manifests,held=held,source_epochs=epochs,continuous_heightfield=True,
        maximum_rise=int((target-tops)[eligible].max()) if eligible.any() else 0,existing_wood_columns_preserved=int(wood.sum()),exact_existing_fullNBT_untouched=True,
        spherical_boundary='CurrentTVpreview radius1800/centre30,296/roof function and24m air margin; no shell/roof/floor lowering',central_low_view_disc_radius=650,
        source_tv_reference='Root inspected TV GeoFront frame and Chronicle03pp19–20: low HQ/lake, layered right/opposite-lake rising hills, upper-cap cavity. Pixel-scale to game metres is engineering inference.',
        reference_urls=['https://static.wikia.nocookie.net/evangelion/images/d/da/GeoFront_%28NGE%29.png/revision/latest?cb=20120714071340','https://static.wikia.nocookie.net/evangelion/images/3/33/GeoFront_Nerv_HQ_Eva_Chronicle.png/revision/latest?cb=20230815223912'],
        source_future_generation_proposed='Root translates the same joint ridge/valley field and protection/wood collars into futureTvWorldPreviewTerrain.ground; currentJava is unchanged',
        world_written=False,native_passed=False,visual_passed=False,root_apply_ready=False,requires=['Root independently checks whole actual3D terrain, native virtual rails/launch/airspace and all sector exactBefore/fullinverse before any construction.','The original675tree/source repair obligations remain separate; no legacy tree was moved or removed here.','Apply whole correlated landform, not selected attractive sectors; native/shader/fullterrain audit must precede release.'])
    (a.output/'terrain_contract.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print('Continuous TV-context terrain',total,'cells',len(manifests),'sectors','maxrise',result['maximum_rise'],'holds',len(held),'world unchanged',flush=True)


if __name__=='__main__':main()
