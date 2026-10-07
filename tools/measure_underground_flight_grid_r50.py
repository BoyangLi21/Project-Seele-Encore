"""Read-only broad GeoFront flight/pickup screening from actual stored voxels.

Positive-Y Heightmaps are deliberately not used. Only complete stored chunks
are decoded, current geometry is never edited, and unknown areas stay blocked.
"""
from pathlib import Path
from collections import Counter
import argparse,json,struct,gzip,zlib,time
import numpy as np
from scipy import ndimage
from transplant_s22_authority import read_region
from scan_all_surface_heightmaps_r50 import Metadata
from inspect_map_assets import decode_modern_section,palette_state

ROOT=Path(__file__).resolve().parents[1]
SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:sandstone','minecraft:clay','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:deepslate','minecraft:tuff','minecraft:andesite','minecraft:diorite','minecraft:granite','minecraft:calcite'}
EMPTY={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r50/underground_airlift/cavern_grid');args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    x0,z0,x1,z1=-1312,-1008,1375,1615;shape=(z1-z0+1,x1-x0+1);known=np.zeros(shape,bool);blocked=np.ones(shape,bool);ground=np.full(shape,-32768,np.int16);counts=Counter();unread=[];began=time.monotonic()
    region=args.world/'dimensions/projectseele/geofront/region'
    for rx in range(x0//512,x1//512+1):
        for rz in range(z0//512,z1//512+1):
            p=region/f'r.{rx}.{rz}.mca'
            if not p.exists()or p.stat().st_size==0:continue
            try:_,blobs=read_region(p)
            except Exception as error:unread.append(dict(region=[rx,rz],error=str(error)));continue
            for slot,blob in enumerate(blobs):
                if blob is None:continue
                cx=rx*32+slot%32;cz=rz*32+slot//32;ax,az=cx*16,cz*16
                if ax<x0 or ax>x1 or az<z0 or az>z1:continue
                try:
                    raw=blob[5:4+struct.unpack_from('>I',blob)[0]];compression=blob[4]
                    if compression==2:raw=zlib.decompress(raw)
                    elif compression==1:raw=gzip.decompress(raw)
                    elif compression!=3:raise ValueError('Unsupported/external chunk compression')
                    meta,_=Metadata(raw).read();status=meta.get('Status','')
                    if status not in('full','minecraft:full'):counts['stored_proto']+=1;continue
                    b=np.zeros((16,16),bool);g=np.full((16,16),-32768,np.int16)
                    for s in Metadata(raw).sections():
                        sy=int(s.get('Y',-43))
                        if sy<-35 or sy>-15:continue
                        pal,ids=decode_modern_section(s)
                        if not pal:continue
                        names=[str(e.get('Name','minecraft:air'))for e in pal];index=np.asarray(ids,np.int32).reshape(16,16,16);yy=np.arange(sy*16,sy*16+16)
                        lo,hi=max(-410,sy*16),min(-237,sy*16+15)
                        if lo<=hi:b|=np.asarray([n not in EMPTY for n in names])[index[lo-sy*16:hi-sy*16+1]].any(axis=0)
                        earth=np.asarray([n in SOIL for n in names])[index];g=np.maximum(g,np.where(earth,yy[:,None,None],-32768).max(axis=0))
                    zz,xx=az-z0,ax-x0;known[zz:zz+16,xx:xx+16]=True;blocked[zz:zz+16,xx:xx+16]=b;ground[zz:zz+16,xx:xx+16]=g;counts['full_chunks']+=1
                except Exception as error:unread.append(dict(chunk=[cx,cz],error=str(error)));counts['unread']+=1
            print('GF voxel region',rx,rz,'full',counts['full_chunks'],'sec',round(time.monotonic()-began,1),flush=True)
    # The 192x192 all-yaw planning envelope contains the true144x114 aircraft
    # and a conservative captured-cargo column; actual posed GJK remains mandatory.
    forbidden=(~known)|blocked;safe=ndimage.maximum_filter(forbidden.astype(np.uint8),size=193,mode='constant',cval=1)==0
    labels,num=ndimage.label(safe);airport_label=int(labels[-270-z0,-440-x0]);component=(labels==airport_label)if airport_label else np.zeros_like(safe)
    nodes=[]
    for z in range(-816,1425,192):
        for x in range(-1120,1185,192):
            if component[z-z0,x-x0]and -510<=ground[z-z0,x-x0]<=-410:nodes.append([x,-260,z])
    np.savez_compressed(out/'actual_cavern_air_band.npz',origin=[x0,z0],known_full=known,blocked_any_y_minus410_to_minus237=blocked,highest_soil_in_read_band=ground,all_yaw_planning_clear=safe,airport_connected=component)
    report=dict(world=str(args.world.resolve()),bounds=[[x0,-560,z0],[x1,-237,z1]],counts=dict(counts),known_columns=int(known.sum()),nonair_flight_columns=int((known&blocked).sum()),all_yaw_planning_clear_columns=int(safe.sum()),airport_connected_columns=int(component.sum()),airport_component=airport_label,coarse_nodes=nodes,unread=unread,quality_acceptance=False,world_written=False,Java_started=False,new_chunks_generated=False,
        predicate='Conservative actual whole vertical aircraft/payload planning band Y-410..-237,193x193 all-yaw envelope. Any unknown/proto/nonAIR blocks; actual frozen compound and every runtime step still checked.',limitations='A failed broad-band cell may still admit a measured thinner posed corridor. No topology across a blocked/unknown cell is claimed; no negative-Y room is inferred to be the main cavern.')
    (out/'actual_cavern_air_band_readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:report[k]for k in('counts','known_columns','airport_connected_columns','airport_component')}),'coarse nodes',len(nodes),flush=True)

if __name__=='__main__':main()
