"""Read every stored geofront Heightmap, vectorized screening, no world writes.

Uses the repository's strict Anvil blob reader. NBT payloads unrelated to the
height/status fields are skipped without allocating full voxel palettes.
"""
from pathlib import Path
from collections import Counter
import argparse,json,struct,gzip,zlib,time
import numpy as np
from scipy import ndimage
from transplant_s22_authority import read_region
from inspect_map_assets import decode_modern_section,palette_state

ROOT=Path(__file__).resolve().parents[1]
class Metadata:
    def __init__(self,raw):self.raw=raw;self.at=0;self.result={};self.maps={}
    def number(self,fmt):
        v=struct.unpack_from(fmt,self.raw,self.at)[0];self.at+=struct.calcsize(fmt);return v
    def string(self):
        n=self.number('>H');v=self.raw[self.at:self.at+n].decode('utf8');self.at+=n;return v
    def skip(self,t):
        if 1<=t<=6:self.at+=[0,1,2,4,8,4,8][t]
        elif t==7:
            n=self.number('>i');self.at+=n
        elif t==8:
            n=self.number('>H');self.at+=n
        elif t==9:
            child=self.number('>B');count=self.number('>i')
            if 1<=child<=6:self.at+=count*[0,1,2,4,8,4,8][child]
            else:
                for _ in range(count):self.skip(child)
        elif t==10:
            while True:
                child=self.number('>B')
                if not child:return
                self.string();self.skip(child)
        elif t==11:
            n=self.number('>i');self.at+=n*4
        elif t==12:
            n=self.number('>i');self.at+=n*8
        else:raise ValueError(('Unsupported NBT payload type',t))
    def read(self):
        if self.number('>B')!=10:raise ValueError('Root compound required')
        self.string()
        while self.at<len(self.raw):
            t=self.number('>B')
            if not t:break
            key=self.string()
            if key=='Status'and t==8:
                self.result[key]=self.string()
                if self.result[key]not in('full','minecraft:full'):return self.result,self.maps
            elif key in('xPos','zPos','yPos')and t==3:self.result[key]=self.number('>i')
            elif key=='Heightmaps'and t==10:
                while True:
                    child=self.number('>B')
                    if not child:break
                    name=self.string()
                    if child==12:
                        count=self.number('>i');self.maps[name]=np.frombuffer(self.raw,dtype='>u8',count=count,offset=self.at).astype(np.uint64);self.at+=count*8
                    else:self.skip(child)
            else:self.skip(t)
            if self.maps and all(k in self.result for k in('Status','yPos','xPos','zPos')):break
        return self.result,self.maps
    def value(self,t,all_keys=False):
        if t==1:return self.number('>b')
        if t==3:return self.number('>i')
        if t==8:return self.string()
        if t==12:
            n=self.number('>i');v=np.frombuffer(self.raw,dtype='>i8',count=n,offset=self.at).copy();self.at+=n*8;return v
        if t==9:
            child=self.number('>B');count=self.number('>i');return[self.value(child)for _ in range(count)]
        if t==10:
            result={}
            while True:
                child=self.number('>B')
                if not child:return result
                key=self.string()
                if all_keys or key in('Y','block_states','palette','Name','Properties','data'):
                    result[key]=self.value(child,all_keys=key=='Properties')
                else:self.skip(child)
        self.skip(t);return None
    def sections(self):
        self.at=0;self.number('>B');self.string()
        while self.at<len(self.raw):
            t=self.number('>B')
            if not t:return[]
            key=self.string()
            if key=='sections'and t==9:return self.value(t)
            self.skip(t)
        return[]
def unpack(a,min_y):
    bits=10;per=64//bits
    if len(a)!=(256+per-1)//per:raise ValueError(('Heightmap storage does not match actual 992/1024-height dimension',len(a)))
    i=np.arange(256,dtype=np.uint64);values=((a[(i//per).astype(int)]>>((i%per)*bits))&((1<<bits)-1)).astype(np.int16)
    return(values+min_y-1).reshape(16,16)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/surface_r50/global_heightmaps');args=ap.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);region=args.world/'dimensions/projectseele/geofront/region';started=time.monotonic();counts=Counter();records=[];objects=[];unread=[]
    shapes=json.loads((args.world/'native_collision_shapes.json').read_text('utf8'));unknown_states=Counter()
    def derive(raw):
        surface=np.full((16,16),-32768,dtype=np.int16);bed=surface.copy()
        for section in Metadata(raw).sections():
            sy=int(section.get('Y',-43))
            if sy<0:continue
            palette,ids=decode_modern_section(section)
            if not palette:continue
            states=[palette_state(p)for p in palette];motion=[];ground=[]
            for s in states:
                name=s.partition('[')[0];fluid=name in{'minecraft:water','minecraft:lava'}or'waterlogged=true'in s
                solid=bool(shapes.get(s,[]))
                if s not in shapes and name not in{'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:water','minecraft:lava','minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}:
                    unknown_states[s]+=1;solid=True
                motion.append((solid or fluid)and not name.endswith('_leaves'));ground.append(solid and not name.endswith('_leaves'))
            indices=np.asarray(ids,dtype=np.int32).reshape(16,16,16);yy=np.arange(sy*16,sy*16+16)[:,None,None]
            surface=np.maximum(surface,np.where(np.asarray(motion)[indices],yy,-32768).max(axis=0));bed=np.maximum(bed,np.where(np.asarray(ground)[indices],yy,-32768).max(axis=0))
        return surface,bed
    for number,path in enumerate(sorted(region.glob('r.*.*.mca'))):
        rx,rz=map(int,path.stem.split('.')[1:]);height=np.full((512,512),-32768,dtype=np.int16);ocean=height.copy();known=np.zeros((512,512),dtype=bool);status=np.zeros((32,32),dtype=np.uint8);record=dict(region=[rx,rz],stored=0,full=0,proto=0,unread=0)
        if path.stat().st_size==0:
            record['empty_zero_length_placeholder']=True;records.append(record);counts['empty_region_files']+=1;continue
        try:_,blobs=read_region(path)
        except Exception as e:unread.append(dict(file=str(path),reason=str(e)));continue
        for slot,blob in enumerate(blobs):
            if blob is None:continue
            record['stored']+=1;cx=rx*32+slot%32;cz=rz*32+slot//32
            try:
                compression=blob[4];raw=blob[5:4+struct.unpack_from('>I',blob)[0]]
                if compression==2:raw=zlib.decompress(raw)
                elif compression==1:raw=gzip.decompress(raw)
                elif compression!=3:raise ValueError(('Unsupported/external compression',compression))
                data,maps=Metadata(raw).read()
                if data.get('Status')not in('full','minecraft:full'):record['proto']+=1;status[slot//32,slot%32]=1;continue
                if data.get('xPos',cx)!=cx or data.get('zPos',cz)!=cz:raise ValueError('Header/actual chunk coordinate mismatch')
                min_y=data.get('yPos',-42)*16
                key='MOTION_BLOCKING_NO_LEAVES'if'MOTION_BLOCKING_NO_LEAVES'in maps else'WORLD_SURFACE'
                derived=key not in maps or'OCEAN_FLOOR'not in maps
                if derived:h,bed=derive(raw);counts['full_without_saved_maps_reconstructed']+=1
                else:h=unpack(maps[key],min_y);bed=unpack(maps['OCEAN_FLOOR'],min_y)
                zz=(slot//32)*16;xx=(slot%32)*16
                height[zz:zz+16,xx:xx+16]=h;ocean[zz:zz+16,xx:xx+16]=bed;known[zz:zz+16,xx:xx+16]=True;status[slot//32,slot%32]=2;record['full']+=1
            except Exception as e:record['unread']+=1;status[slot//32,slot%32]=3;unread.append(dict(chunk=[cx,cz],file=path.name,reason=str(e)))
        np.savez_compressed(out/f'r.{rx}.{rz}.npz',height=height,ocean_floor=ocean,known=known,status=status,origin=[rx*512,rz*512])
        visible=known&(height>=0);dx=np.abs(np.diff(height.astype(int),axis=1));dz=np.abs(np.diff(height.astype(int),axis=0));edge=np.zeros_like(known)
        edge[:,:-1]|=(dx>=8)&visible[:,:-1]&visible[:,1:];edge[:-1]|=(dz>=8)&visible[:-1]&visible[1:]
        ring=np.stack([height[1:-1,:-2],height[1:-1,2:],height[:-2,1:-1],height[2:,1:-1]],axis=0);valid_ring=visible[1:-1,1:-1]&visible[1:-1,:-2]&visible[1:-1,2:]&visible[:-2,1:-1]&visible[2:,1:-1]
        pits=np.zeros_like(known);pits[1:-1,1:-1]=valid_ring&(ring.min(axis=0)-height[1:-1,1:-1]>=8)
        masks={'ADJACENT_HEIGHTMAP_JUMP_8':edge,'ISOLATED_HEIGHTMAP_DEPRESSION_8':pits}
        for kind,mask in masks.items():
            labels,n=ndimage.label(mask,structure=np.ones((3,3),int));slices=ndimage.find_objects(labels);sizes=np.bincount(labels.ravel())
            for index,slice_ in enumerate(slices,1):
                if slice_ is None or sizes[index]<3 and kind.startswith('ADJACENT'):continue
                yy,xx=slice_;positions=np.argwhere(labels[yy,xx]==index);positions[:,0]+=yy.start;positions[:,1]+=xx.start;sample=positions[::max(1,len(positions)//10)][:10]
                points=[[int(rx*512+x),int(height[z,x]),int(rz*512+z)]for z,x in sample]
                objects.append(dict(id=f'heightmap/{rx}/{rz}/{kind}/{index}',kind=kind,bounds=[[rx*512+xx.start,0,rz*512+yy.start],[rx*512+xx.stop-1,319,rz*512+yy.stop-1]],candidate_columns=int(sizes[index]),examples=points,status='HEIGHTMAP_SCREEN_ONLY_STRUCTURE_WATER_TREE_OR_GEOLOGICAL_CLASSIFICATION_REQUIRED'))
        records.append(record);counts.update({k:record[k]for k in('stored','full','proto','unread')})
        if number%20==0:print('Heightmap region',number+1,'stored',counts['stored'],'full',counts['full'],'seconds',round(time.monotonic()-started,1),flush=True)
    report=dict(world=str(args.world.resolve()),reader='Strict repository region reader; saved Heightmaps vector unpack. Only FULL chunks with absent maps use selective positive-Y section palette/index reconstruction, no block iteration or writes.',regions=records,counts=dict(counts),actual_full_surface_columns=counts['full']*256,objects=objects,unread=unread,reconstructed_predicate_unknown_states=dict(unknown_states),reconstruction_caveat='Cached native collision shapes provide known motion predicates; unknown states are conservatively solid and recorded, never counted as quality passes.',region_boundary_pairs_not_yet_screened=True,all_storage_regions_attempted=True,global_terrain_quality_passed=False,world_written=False)
    (out/'global_screen.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('Complete stored Heightmap first screen',dict(counts),'objects',len(objects),'seconds',round(time.monotonic()-started,1),flush=True)
if __name__=='__main__':main()
