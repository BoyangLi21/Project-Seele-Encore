"""Export exact saved GeoFront columns for bounded native DH cache import.

This is a derived-data export. It neither changes blocks nor reconstructs a
surface from a heightmap. Native DH resolves block/biome wrappers and builds
its parent hierarchy after import.
"""
import argparse,gzip,json,lzma,sqlite3,struct,time
from pathlib import Path
import numpy as np
from query_blocks import iter_lod_source_chunks


def export_tile(world,tile,destination):
    tx,tz=tile;chunks={(tx*4+x,tz*4+z)for x in range(4)for z in range(4)}
    pairs=[];lookup={}
    def pair(biome,state):
        key=(biome,state)
        if key not in lookup:lookup[key]=len(pairs);pairs.append(key)
        return lookup[key]
    values=np.full((64,64,1665),0xffffffff,dtype=np.uint32)
    present=set();unlit=[]
    for cx,cz,sections,lit in iter_lod_source_chunks(world,'projectseele:geofront',chunks):
        present.add((cx,cz))
        if not lit:unlit.append([cx,cz])
        x,z=(cx-tx*4)*16,(cz-tz*4)*16;seen=set()
        for sy,palette,ids,light,bp,bi in sections:
            if not -84<=sy<20:continue
            seen.add(sy)
            remap=np.asarray([[pair(b,s)for s in palette]for b in bp],dtype=np.uint32)
            bi=bi.reshape(4,4,4).repeat(4,0).repeat(4,1).repeat(4,2).ravel()
            exact=remap[bi,ids]|(light.astype(np.uint32)<<24)
            values[x:x+16,z:z+16,(sy+84)*16:(sy+85)*16]=exact.reshape(16,16,16).transpose(2,1,0)
        # Empty sections must be explicit; missing data is never guessed as air.
        if seen!=set(range(-84,20)):raise ValueError(f'Missing source sections {(cx,cz)}: {set(range(-84,20))-seen}')
        top_biomes=[pairs[int(v)&0xffffff][0]for v in values[x:x+16,z:z+16,1663].ravel()]
        values[x:x+16,z:z+16,1664]=np.asarray([pair(b,'minecraft:air')for b in top_biomes],dtype=np.uint32).reshape(16,16)
    if present!=chunks:raise ValueError(f'Missing source chunks {chunks-present}')
    header=json.dumps(dict(tile=tile,min_y=-1344,height=1664,pairs=pairs,
                          source_unlit_chunks=unlit)).encode('utf8')
    out=destination/f'{tx}_{tz}.columns.gz'
    with gzip.open(out,'wb',compresslevel=3)as stream:
        stream.write(struct.pack('>I',len(header)));stream.write(header)
        for column in values.reshape(4096,1665):
            starts=np.r_[0,np.flatnonzero(column[1:]!=column[:-1])+1]
            ends=np.r_[starts[1:],1665];codes=column[starts].astype(np.uint64)
            spans=(codes&0xffffff)|((ends-starts).astype(np.uint64)<<32)|(starts.astype(np.uint64)<<44)|((codes>>24)<<60)
            stream.write(struct.pack('>H',len(spans)));stream.write(spans[::-1].astype('>u8').tobytes())
    return dict(tile=tile,bytes=out.stat().st_size,states=len(pairs),unlit_chunks=unlit)


def verify_import(world,directory):
    """Compare every imported vertical geometry span with the saved source."""
    database=world/'dimensions/projectseele/geofront/data/DistantHorizons.sqlite'
    native_palette_path=directory/'native-palette.json'
    native_palette=json.loads(native_palette_path.read_text('utf8'))if native_palette_path.exists()else{}
    def serial(pair):
        biome,state=pair
        if state in ('minecraft:air','minecraft:cave_air','minecraft:void_air'):state='AIR'
        elif state in native_palette:state=native_palette[state]
        elif '[' in state:
            name,properties=state[:-1].split('[',1)
            state=name+'_STATE_'+''.join('{'+p.replace('=',':')+'}'for p in sorted(properties.split(',')))
        else:state+='_STATE_'
        return biome+'_DH-BSW_'+state
    def read_mapping(data):
        raw=lzma.LZMADecompressor().decompress(data);count=struct.unpack_from('>I',raw)[0];offset=4;result=[]
        for _ in range(count):
            length=struct.unpack_from('>H',raw,offset)[0];offset+=2
            entry=raw[offset:offset+length].decode('utf8');offset+=length
            for air in ('air','cave_air','void_air'):
                entry=entry.replace('_DH-BSW_minecraft:'+air+'_STATE_','_DH-BSW_AIR')
            result.append(entry)
        return result
    def geometry(values,mapping):
        result=[]
        for v in values:
            item=(mapping[v&0x7fffffff],(v>>44)&4095,(v>>32)&4095)
            if result and result[-1][0]==item[0] and item[1]+item[2]==result[-1][1]:
                previous=result.pop();item=(item[0],item[1],item[2]+previous[2])
            result.append(item)
        return result
    checked=0;tiles=0
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)as sql:
        for file in sorted(directory.glob('*.columns.gz')):
            with gzip.open(file,'rb')as stream:
                header=json.loads(stream.read(struct.unpack('>I',stream.read(4))[0]));tx,tz=header['tile'];source_map=list(map(serial,header['pairs']))
                row=sql.execute('select Data,Mapping from FullData where DetailLevel=0 and PosX=? and PosZ=?',(tx,tz)).fetchone()
                if row is None:raise ValueError(f'Missing imported tile {(tx,tz)}')
                native=lzma.LZMADecompressor().decompress(row[0]);native_map=read_mapping(row[1]);offset=0
                for column in range(4096):
                    count=struct.unpack('>H',stream.read(2))[0];source=struct.unpack('>'+str(count)+'Q',stream.read(count*8))
                    count=struct.unpack_from('>H',native,offset)[0];offset+=2
                    actual=struct.unpack_from('>'+str(count)+'Q',native,offset);offset+=count*8
                    expected_spans=geometry(source,source_map);actual_spans=geometry(actual,native_map)
                    if expected_spans!=actual_spans:
                        mismatch=next((i for i,(a,b) in enumerate(zip(expected_spans,actual_spans)) if a!=b),
                                      min(len(expected_spans),len(actual_spans)))
                        raise ValueError(f'Geometry differs {(tx,tz,column)} at span {mismatch}: '
                                         f'expected {expected_spans[mismatch:mismatch+2]}, '
                                         f'actual {actual_spans[mismatch:mismatch+2]}')
                    checked+=1
            tiles+=1
    return dict(verified=True,tiles=tiles,exact_columns_checked=checked,compared='full-height block and biome spans; lighting kept separate',world_written=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('tiles',type=Path);p.add_argument('out',type=Path);p.add_argument('--verify-import',action='store_true');a=p.parse_args()
    if a.verify_import:
        result=verify_import(a.world,a.out);(a.out/'verified.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(result));raise SystemExit
    tiles=json.loads(a.tiles.read_text('utf8'))['tiles'];a.out.mkdir(parents=True,exist_ok=True)
    report=[];start=time.time()
    for tile in tiles:
        report.append(export_tile(a.world,tile,a.out))
        (a.out/'progress.json').write_text(json.dumps(dict(completed=len(report),total=len(tiles),elapsed=round(time.time()-start),tiles=report)),'utf8')
        if len(report)%10==0:print(f'{len(report)}/{len(tiles)} in {time.time()-start:.1f}s',flush=True)
    print('Export complete; actual world unchanged',flush=True)
