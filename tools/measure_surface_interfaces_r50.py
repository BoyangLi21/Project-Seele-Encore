"""Current dense readback of cached whole surface interface candidates; no edits."""
from pathlib import Path
import argparse,json,time
from collections import defaultdict,Counter
import numpy as np
from query_blocks import iter_selected_sections,AIR

ROOT=Path(__file__).resolve().parents[1]
SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:sandstone','minecraft:clay','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:deepslate','minecraft:tuff','minecraft:andesite','minecraft:diorite','minecraft:granite','minecraft:bedrock','minecraft:calcite'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/surface_r50');args=ap.parse_args()
    out=args.out.resolve();source=json.loads((out/'cached_terrain_interface_objects.json').read_text('utf8'));selected=defaultdict(set)
    for row in source['objects']:
        x0,z0,x1,z1=row['xz_bounds']
        for cx in range((x0-8)//16,(x1+8)//16+1):
            for cz in range((z0-8)//16,(z1+8)//16+1):selected[cx,cz].update(range(0,16))
    tiles={};known=set();started=time.monotonic()
    for cx,cz,sy,palette,indices in iter_selected_sections(args.world,'projectseele:geofront',selected,skip_unfinished=True):
        if(cx,cz)not in tiles:tiles[cx,cz]=np.full((16,16),-32768,dtype=np.int16)
        known.add((cx,cz));mask=np.asarray([s.partition('[')[0]in SOIL for s in palette])[indices].reshape(16,16,16)
        height=np.where(mask,np.arange(sy*16,sy*16+16)[:,None,None],-32768).max(axis=0)
        tiles[cx,cz]=np.maximum(tiles[cx,cz],height)
    result=[]
    for row in source['objects']:
        x0,z0,x1,z1=row['xz_bounds'];x0-=8;z0-=8;x1+=8;z1+=8
        height=np.full((z1-z0+1,x1-x0+1),-32768,dtype=np.int16)
        for cx in range(x0//16,x1//16+1):
            for cz in range(z0//16,z1//16+1):
                if(cx,cz)not in tiles:continue
                ax,bx=max(x0,cx*16),min(x1,cx*16+15);az,bz=max(z0,cz*16),min(z1,cz*16+15)
                height[az-z0:bz-z0+1,ax-x0:bx-x0+1]=tiles[cx,cz][az-cz*16:bz-cz*16+1,ax-cx*16:bx-cx*16+1]
        valid=height>-32768;unknown=int((~valid).sum());samples=[];cache_changed=0;steep_events=0
        for e in row['events']:
            a,b=e['from_pos'],e['to_pos'];ha,hb=int(height[a[2]-z0,a[0]-x0]),int(height[b[2]-z0,b[0]-x0]);actual=abs(ha-hb)if ha>-32768 and hb>-32768 else None
            if ha!=a[1]or hb!=b[1]:cache_changed+=1
            if actual is not None and actual>=24:steep_events+=1
            samples.append(dict(cached=e,actual_soil_y=[ha,hb],actual_difference=actual))
        dx=np.abs(np.diff(height.astype(int),axis=1));dz=np.abs(np.diff(height.astype(int),axis=0))
        steep_x=(dx>=8)&valid[:,:-1]&valid[:,1:];steep_z=(dz>=8)&valid[:-1]&valid[1:]
        abrupt=[]
        for zz,xx in np.argwhere(steep_x)[:40]:abrupt.append(dict(pos=[int(xx+x0),int(height[zz,xx]),int(zz+z0)],axis='x',rise=int(dx[zz,xx])))
        for zz,xx in np.argwhere(steep_z)[:40]:abrupt.append(dict(pos=[int(xx+x0),int(height[zz,xx]),int(zz+z0)],axis='z',rise=int(dz[zz,xx])))
        name=row['id'].replace('/','_');np.savez_compressed(out/(name+'.npz'),origin=[x0,z0],actual_soil_height=height,valid=valid)
        result.append(dict(id=row['id'],bounds=[[x0,0,z0],[x1,255,z1]],dense_soil_columns=int(valid.sum()),unmeasured_or_no_natural_soil_columns=unknown,
            soil_min=None if not valid.any()else int(height[valid].min()),soil_max=None if not valid.any()else int(height[valid].max()),cached_event_count=len(row['events']),changed_from_old_cached_heights=cache_changed,
            current_cached_interfaces_over_24=steep_events,actual_adjacent_soil_jumps_over_8=int(steep_x.sum()+steep_z.sum()),abrupt_examples=abrupt,cached_event_actual_comparison=samples,
            status='UNMEASURED_OR_NO_POSITIVE_SOIL_REQUIRES_WATER_AND_CHUNK_STATUS'if not valid.any() else 'CURRENT_INTERFACE_REQUIRES_GEOLOGICAL_OR_CONSTRUCTION_OWNER_REVIEW'if abrupt or steep_events else 'OLD_COARSE_ANOMALY_NOT_REPRODUCED_IN_CURRENT_DENSE_SOIL',
            current_voxel_source=str(args.world.resolve()),current_surface_or_full_facility_quality_passed=False,world_written=False))
    (out/'dense_terrain_interface_readback.json').write_text(json.dumps(dict(world=str(args.world.resolve()),objects=result,actual_current_dense_columns=sum(r['dense_soil_columns']for r in result),counts=dict(Counter(r['status']for r in result)),full_stored_world_terrain_scanned=False,world_written=False),ensure_ascii=False,indent=2),'utf8')
    print('Dense current interface objects',len(result),'columns',sum(r['dense_soil_columns']for r in result),'seconds',round(time.monotonic()-started,1),dict(Counter(r['status']for r in result)),flush=True)
if __name__=='__main__':main()
