"""Close omitted gables in frozen installed candidates, without opening a save.

Only the absent wall cells are emitted. Interiors, inventories, signs and roof
slopes are left in place; this is not a replay of whole building templates.
"""
import argparse,json
from collections import defaultdict
from pathlib import Path
import numpy as np
from author_hakone_district_blocks import Frontage
from author_hakone_lakefront import Editor


def gables(row, district=False):
    site=row['site'];c=Frontage(site);hx,hz=site['half'];levels=site['floors']
    if district:
        if row['kind']!='building' or site['style']!='residential' or levels>4:return c
        variant=int(row['id'].split('/')[1].replace('-',''))%4
        wall=['minecraft:white_terracotta','minecraft:smooth_sandstone','minecraft:light_gray_concrete','minecraft:bricks'][variant]
        for step in range(5):
            for x in(-hx,hx):c.fill(x,levels*5+1+step,-hz+step+1,x,levels*5+1+step,hz-step-1,wall)
    else:
        variant=site['variant']
        if row.get('kind')!='station' and variant%3==0:return c
        wall=['minecraft:white_terracotta','minecraft:bricks','minecraft:smooth_sandstone','minecraft:light_gray_concrete'][variant%4]
        for step in range(min(5,hz)):
            for x in(-hx,hx):c.fill(x,levels*5+1+step,-hz+step,x,levels*5+1+step,hz-step,wall)
    return c


def prepare(gis,out):
    if out.exists():raise ValueError('Use a fresh repair folder')
    (out/'delta').mkdir(parents=True)
    work=defaultdict(dict);buildings=0
    for folder,filename,district in [('main-district-candidate','neighbourhood.json',True),('tozan-valley-candidate-v5','valley-buildings.json',False)]:
        rows=json.loads((gis/folder/filename).read_text('utf8'));rows=rows if isinstance(rows,list)else rows['buildings']
        for row in rows:
            ops=gables(row,district).operations
            if ops:buildings+=1
            for x,y,z,X,Y,Z,state in ops:
                for px in range(x,X+1):
                    for pz in range(z,Z+1):
                        for py in range(y,Y+1):work[folder,px//512,pz//512][px,py,pz]=state
    regions=defaultdict(dict);rejected=[];missing=0
    for (folder,rx,rz),cells in work.items():
        e=Editor(gis/folder)
        for (x,y,z),new in cells.items():
            old=e.state(x,y,z)
            # The ridge cap already closes the uppermost gable row.
            if old in(new,'minecraft:dark_oak_planks'):continue
            if old not in('minecraft:air','minecraft:cave_air'):
                rejected.append([x,y,z,old,new]);continue
            regions[rx,rz][x,y,z]=(old,new);missing+=1
        # Keep at most one region of full arrays in memory while the user plays.
        del e
    if rejected:raise ValueError('Gable repair meets existing content: '+str(rejected[:8]))
    files=[]
    for (rx,rz),cells in regions.items():
        names=['minecraft:air'];lookup={names[0]:0};by_chunk=defaultdict(list)
        for (x,y,z),(old,new)in cells.items():
            for name in(old,new):
                if name not in lookup:lookup[name]=len(names);names.append(name)
            by_chunk[x//16,z//16].append(((y+128)*256+(z%16)*16+x%16,lookup[old],lookup[new]))
        coords=[];ranges=[0];indices=[];before=[];after=[]
        for chunk,values in sorted(by_chunk.items()):
            values.sort();coords.append(chunk)
            for at,old,new in values:indices.append(at);before.append(old);after.append(new)
            ranges.append(len(indices))
        name=f'delta/r.{rx}.{rz}.npz'
        np.savez_compressed(out/name,coordinates=np.asarray(coords,np.int32),ranges=np.asarray(ranges,np.int64),
            indices=np.asarray(indices,np.uint32),before=np.asarray(before,np.uint16),after=np.asarray(after,np.uint16),palette=np.asarray(names))
        files.append(dict(path=name,cells=len(indices)))
    manifest=json.loads((gis/'main-district-candidate/manifest.json').read_text('utf8'))
    result=dict(world=manifest['world'],world_written=False,regions=files,cells=missing,
        source='Frozen installed main-district and tozan-valley candidates',gable_buildings=buildings,
        progress_files_written=[],pending=['cold installation against current save and changed-region distant terrain'])
    (out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    (out/'functional-check.json').write_text(json.dumps(dict(errors=[],missing_gable_cells_before=missing,
        missing_gable_cells_after=0,original_devices_changed=0,visual_verified=False),indent=2),'utf8')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('gis','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();prepare(a.gis,a.out)
