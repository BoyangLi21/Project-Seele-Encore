"""Detect uniform DH columns that contradict the actual authored cavern roof.

A non-empty LOD column is not proof of geometry coverage. The prior hierarchy
check deliberately remains separate: it only checks parent representation.
"""
from pathlib import Path
import argparse,json,lzma,math,sqlite3,struct
from query_blocks import iter_selected_sections


def audit(world):
    database=world/'dimensions/projectseele/geofront/data/DistantHorizons.sqlite'
    selection={};targets={};tiles=[];present=set();missing_columns=0
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as sql:
        for tx,tz,blob,mode in sql.execute('select PosX,PosZ,Data,CompressionMode from FullData where DetailLevel=0'):
            if math.hypot(tx*64+32-30,tz*64+32-296)>1850:continue
            present.add((tx,tz))
            if mode!=3:raise ValueError('Unsupported DH compression')
            raw=lzma.LZMADecompressor().decompress(blob);offset=0;points=[]
            for index in range(4096):
                count=struct.unpack_from('>H',raw,offset)[0];offset+=2
                x=tx*64+index//64;z=tz*64+index%64
                if count==0 and math.hypot(x-30,z-296)<1798:missing_columns+=1
                if count==1:
                    value=struct.unpack_from('>Q',raw,offset)[0]
                    if ((value>>44)&4095)==0 and ((value>>32)&4095)==1665 and math.hypot(x-30,z-296)<1798:points.append((x,z))
                offset+=count*8
            if not points:continue
            grouped={}
            for x,z in points:grouped.setdefault((x//16,z//16),(x,z))
            for chunk,(x,z) in grouped.items():
                radius=math.hypot(x-30,z-296);t=max(0,(radius-600)/1200)
                roof=-478+math.floor(502*math.sqrt(max(0,1-t*t)))
                # Two different actual states disprove a single full-height span,
                # independently of which local palette ID the LOD uses for air.
                for y in (roof-1,roof+1):
                    selection.setdefault(chunk,set()).add(y//16)
                    targets[x,y,z]=(tx,tz)
            tiles.append(dict(tile=[tx,tz],uniform_columns=len(points),affected_chunks=len(grouped)))
    missing_tiles=[]
    for tx in range((30-1798)//64,(30+1798)//64+1):
        for tz in range((296-1798)//64,(296+1798)//64+1):
            dx=max(tx*64-30,30-(tx*64+63),0)
            dz=max(tz*64-296,296-(tz*64+63),0)
            if dx*dx+dz*dz<1798*1798 and (tx,tz) not in present:missing_tiles.append([tx,tz])
    actual={}
    for cx,cz,sy,palette,ids in iter_selected_sections(world,'projectseele:geofront',selection):
        relevant=[p for p in targets if p[0]//16==cx and p[2]//16==cz and p[1]//16==sy]
        for x,y,z in relevant:actual[x,y,z]=palette[int(ids[(y%16)*256+(z%16)*16+(x%16)])]
    if len(actual)!=len(targets):raise ValueError('Some source sections are missing or unfinished')
    columns={}
    for (x,y,z),state in actual.items():columns.setdefault((x,z),[]).append(state)
    contradicted=[]
    for (x,z),states in columns.items():
        if len(set(states))>1:contradicted.append(dict(point=[x,z],states=states,tile=[x//64,z//64]))
    return dict(source_world=str(world),world_written=False,uniform_tiles=tiles,
                uniform_columns=sum(r['uniform_columns']for r in tiles),native_columns_checked=len(columns),
                contradicted_columns=contradicted,missing_tiles=missing_tiles,missing_columns=missing_columns,
                verified=not contradicted and not missing_tiles and not missing_columns)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('report',type=Path);a=p.parse_args()
    result=audit(a.world);a.report.write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps({k:v for k,v in result.items()if k not in ('uniform_tiles','contradicted_columns')}))
