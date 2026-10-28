"""Plan native retries for still-incomplete GeoFront background LOD tiles."""
import argparse,json,lzma,sqlite3,struct
from pathlib import Path

def main():
 p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('tiles',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 raw=json.loads(a.tiles.read_text('utf-8-sig'));tiles=raw['all'] if isinstance(raw,dict) else raw
 database=a.world/'dimensions/projectseele/geofront/data/DistantHorizons.sqlite';remaining=[];reasons=[]
 with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as sql:
  for x,z in tiles:
   row=sql.execute('select Mapping,ColumnGenerationStep,CompressionMode from FullData where DetailLevel=0 and PosX=? and PosZ=?',(x,z)).fetchone()
   reason=None
   if row is None:reason='missing tile'
   else:
    if row[2]!=3:raise ValueError('Unexpected pinned DH compression format')
    mapping=lzma.LZMADecompressor().decompress(row[0]);generation=lzma.LZMADecompressor().decompress(row[1])
    count=struct.unpack_from('>I',mapping)[0];offset=4;states=[]
    for _ in range(count):
     size=struct.unpack_from('>H',mapping,offset)[0];offset+=2;states.append(mapping[offset:offset+size].decode('utf8').split('_DH-BSW_',1)[1]);offset+=size
    if states and all(s=='AIR' for s in states):reason='whole height incorrectly empty'
    elif 0 in generation:reason='native callback left incomplete columns'
   if reason:remaining.append([x,z]);reasons.append(dict(tile=[x,z],reason=reason))
 a.output.mkdir(parents=True,exist_ok=True)
 (a.output/'tiles.json').write_text(json.dumps(remaining),'utf8');(a.output/'mode.txt').write_text('INTERNAL_SERVER','ascii');(a.output/'workers.txt').write_text('4','ascii')
 (a.output/'plan.json').write_text(json.dumps(dict(checked=len(tiles),remaining=len(remaining),reasons=reasons,cache_written=False),indent=2),'utf8')
 print(dict(checked=len(tiles),remaining=len(remaining)))
if __name__=='__main__':main()
