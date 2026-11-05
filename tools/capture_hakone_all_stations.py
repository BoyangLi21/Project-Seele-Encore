"""Capture exact saved sections at station-specific depths without opening the game.

The section format is deliberately independent of the surface editor's -128
lower bound. Missing chunks remain unavailable. Absent sections in a confirmed
FULL chunk are represented as implicit air and recorded separately. This is a
read-only snapshot, not an installation candidate or an access completion claim.
"""
import argparse
import copy
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import nbtlib
import numpy as np
from shapely.geometry import shape
from inspect_map_assets import region_chunks, decode_modern_section, palette_state
from query_blocks import dimension_dir
from install_r53_carrier_trays import stopped_world
from native_transit_additions import inventory, assert_preserved


def sites(programme):
    result=[]
    for i,row in enumerate(programme['stations']):
        b=row['bounds']
        box=[math.floor(b[0])-16,max(-1344,math.floor(b[1])-16),math.floor(b[2])-16,
             math.ceil(b[3])+16,min(319,math.ceil(b[4])+16),math.ceil(b[5])+16]
        result.append(dict(id=f'native-{i:02d}',kind='existing',name=row['name'],bounds=box,
                           station_bounds=b,native_id=row['native_id']))
    for i,row in enumerate(programme['geographic_stations']):
        x,z=row['track_centre_xz'];l,t,r,b=shape(row['reserved_geometry']).bounds
        box=[math.floor(min(l,x-80)),-128,math.floor(min(t,z-80)),
             math.ceil(max(r,x+80)),319,math.ceil(max(b,z+80))]
        result.append(dict(id=f'geographic-{i:02d}',kind='geographic',name=row['name'],bounds=box,
                           track_centre_xz=[x,z],reference_terrain_y=row['reference_terrain_y']))
    for i,row in enumerate(programme['unassigned_platform_review']):
        b=row['bounds'];box=[math.floor(b[0])-32,math.floor(b[1])-20,math.floor(b[2])-32,
                            math.ceil(b[3])+32,math.ceil(b[4])+20,math.ceil(b[5])+32]
        result.append(dict(id=f'operational-{i:02d}',kind='unassigned operational point',name=row['name'],
                           bounds=box,native_id=row['native_id'],purpose_verified=False))
    return result


def capture(args):
    explicit=getattr(args,'sites',None)
    if explicit:
        rows=json.loads(explicit.read_text('utf8'))
        for row in rows:
            b=row['bounds']
            if len(b)!=6 or any(not isinstance(v,int)for v in b)or any(b[i]>b[i+3]for i in range(3))or b[1]<-1344 or b[4]>319:raise ValueError('Invalid bounded station capture')
    else:
        programme=json.loads(args.programme.read_text('utf8'));rows=sites(programme)
    args.out.mkdir(parents=True,exist_ok=False);(args.out/'sections').mkdir()
    selected=defaultdict(set)
    for row in rows:
        x,y,z,X,Y,Z=row['bounds'];chunks=[]
        for cx in range(x//16,X//16+1):
            for cz in range(z//16,Z//16+1):
                selected[cx,cz].update(range(y//16,Y//16+1));chunks.append((cx,cz))
        row['requested_chunks']=chunks
    groups=defaultdict(set)
    for cx,cz in selected:groups[cx//32,cz//32].add((cx,cz))
    statuses={p:'missing'for p in selected};diagnostics=[];regions=[];devices=[];actors=[]
    native_expected=inventory(args.native)
    with stopped_world(args.world):
        assert_preserved(args.world,native_expected)
        dim=dimension_dir(args.world,'projectseele:geofront')
        for (rx,rz),wanted in sorted(groups.items()):
            names=['minecraft:air'];ids={names[0]:0};coordinates=[];values=[];present=[]
            file=dim/'region'/f'r.{rx}.{rz}.mca'
            bounds=(min(p[0]for p in wanted),max(p[0]for p in wanted),min(p[1]for p in wanted),max(p[1]for p in wanted))
            chunks=region_chunks(file,bounds,wanted,diagnostics=diagnostics)if file.is_file()else []
            for cx,cz,chunk in chunks:
                status=str(chunk.get('Status','')).removeprefix('minecraft:');statuses[cx,cz]=status
                if status!='full':continue
                decoded={}
                for section in chunk.get('sections',[]):
                    sy=int(section['Y'])
                    if sy not in selected[cx,cz]:continue
                    if sy in decoded:raise ValueError('Duplicate saved section')
                    states=section.get('block_states',{})
                    count=len(states.get('palette',[]))
                    if count>1:
                        per=64//max(4,(count-1).bit_length())
                        if len(states.get('data',[]))*per<4096:raise ValueError('Truncated saved station palette indices')
                    palette,indices=decode_modern_section(section)
                    if not palette:raise ValueError(f'Saved section lacks block palette: {(cx,sy,cz)}')
                    remap=[]
                    for p in palette:
                        name=palette_state(p)
                        if name not in ids:ids[name]=len(names);names.append(name)
                        remap.append(ids[name])
                    if len(names)>65535:raise ValueError('Region palette exceeds uint16')
                    decoded[sy]=np.asarray(remap,np.uint16)[np.asarray(indices,np.int32)].reshape(16,16,16)
                for sy in sorted(selected[cx,cz]):
                    coordinates.append((cx,sy,cz));present.append(sy in decoded)
                    values.append(decoded.get(sy,np.zeros((16,16,16),np.uint16)))
                for tag in chunk.get('block_entities',[]):
                    if int(tag['y'])//16 in selected[cx,cz]:devices.append(copy.deepcopy(tag))
            if coordinates:
                name=f'r.{rx}.{rz}.npz'
                np.savez_compressed(args.out/'sections'/name,coordinates=np.asarray(coordinates,np.int32),
                    blocks=np.asarray(values,np.uint16),palette=np.asarray(names),present=np.asarray(present,bool))
                regions.append(dict(file=name,sections=len(coordinates),implicit_air_sections=sum(not p for p in present)))
            entity_file=dim/'entities'/f'r.{rx}.{rz}.mca'
            if entity_file.is_file() and entity_file.stat().st_size:
                for cx,cz,chunk in region_chunks(entity_file,bounds,wanted,diagnostics=diagnostics):
                    for actor in chunk.get('Entities',[]):
                        p=list(map(float,actor.get('Pos',[])))
                        if len(p)==3 and math.floor(p[1])//16 in selected[cx,cz]:actors.append(copy.deepcopy(actor))
            print(f'Station snapshot region {rx},{rz}: {len(coordinates)} sections',flush=True)
        assert_preserved(args.world,native_expected)
    for row in rows:
        cs=row['requested_chunks'];row['chunk_statuses']=dict(Counter(statuses[tuple(p)]for p in cs))
        row['unavailable_chunks']=[[*p,statuses[tuple(p)]]for p in cs if statuses[tuple(p)]!='full']
        row['all_requested_chunks_full']=not row['unavailable_chunks']
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](devices)}).save(args.out/'devices.dat',gzipped=True)
    nbtlib.File({'Actors':nbtlib.List[nbtlib.Compound](actors)}).save(args.out/'actors.dat',gzipped=True)
    report=dict(world=str(args.world),programme=str(explicit or args.programme),native_reference=str(args.native),
        sites=rows,regions=regions,chunk_statuses=dict(Counter(statuses.values())),
        captured_sections=sum(r['sections']for r in regions),devices=len(devices),actors=len(actors),
        diagnostics=diagnostics,world_written=False,station_access_verified=False,
        native_members_exact=True,deep_native_stations=sum(r['kind']=='existing'and r['bounds'][1]<-128 for r in rows))
    (args.out/'capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Station snapshot:',len(rows),'sites;',report['chunk_statuses'],';',report['captured_sections'],'sections;',len(diagnostics),'decode issues.',flush=True)
    if diagnostics:raise ValueError('Snapshot contains decode diagnostics; review before using')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('world','native','out'):p.add_argument('--'+name,type=Path,required=True)
    scope=p.add_mutually_exclusive_group(required=True);scope.add_argument('--programme',type=Path);scope.add_argument('--sites',type=Path,help='Explicit measured [x,y,z,X,Y,Z] boxes; no automatic expansion.')
    capture(p.parse_args())
