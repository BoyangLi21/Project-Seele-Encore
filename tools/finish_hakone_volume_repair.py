"""Finite offline clearance and removal of classified detached leftovers."""
import argparse,json
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from repair_hakone_volume_ownership import contracts
from plan_ashi_landscape_r54 import SOIL,PLANTS,NATURAL
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

def finish(a):
    e=Editor(a.candidate);d=load_grid(a.base/'network.npz');boxes,bychunk,rails,layers=contracts(a.base,a.tunnels)
    decisions=[];selected=defaultdict(set);counts=Counter();airport_columns=defaultdict(list)
    if a.airport_findings:
        for x,y,z,n in json.loads(a.airport_findings.read_text('utf8'))['airport_findings']:
            airport_columns[x//512,z//512].append((x,y,z))
    if a.scan:
        report=json.loads((a.scan/'floating-components.json').read_text('utf8'))
        allowed=(NATURAL|PAVEMENT|{'minecraft:sea_lantern','minecraft:polished_andesite','minecraft:polished_andesite_slab'})-{'projectseele:nerv_floor_panel'}
        for c in report['components']:
            x,y,z,X,Y,Z=c['bounds'];m={s.split('[')[0] for s in c['materials']};action='retained-structure-or-unclassified'
            overlap=any(x<=b[3]+1 and X>=b[0]-1 and z<=b[5]+1 and Z>=b[2]-1 and y<=b[4]+2 and Y>=b[1]-2 for b in boxes)
            if c['unknown']:action='unknown-retained'
            elif y<32:action='underground-retained'
            elif not overlap and m<=allowed:
                xx,zz=np.meshgrid(np.arange(x,X+1),np.arange(z,Z+1));walk=sampled(d,'walk',xx,zz).astype(bool);grade=sampled(d,'grade2',xx,zz)/2
                road=bool((walk&(grade>=y-4)&(grade<=Y+1)).any())
                rail=False;tunnel=False
                for cx in range(x//16,X//16+1):
                    for cz in range(z//16,Z//16+1):
                        rail|=any(x-3<=px<=X+3 and z-3<=pz<=Z+3 and y-8<=py<=Y+5 for px,py,pz in rails[cx,cz])
                        tunnel|=any(x-2<=px<=X+2 and z-2<=pz<=Z+2 and any(y-6<=py<=Y+3 for py in ys) for (px,pz),ys in layers[cx,cz].items())
                if not road and not rail and not tunnel:action='remove-detached-obsolete-surface'
            if action.startswith('remove'):
                for rx,rz,i in c['parts']:selected[rx,rz].add(i)
            decisions.append(dict(id=c['id'],bounds=c['bounds'],cells=c['cells'],action=action))
    files=({f.name for f in (a.candidate/'delta').glob('*.npz')} if not a.components_only else set())|{f'r.{rx}.{rz}.npz' for rx,rz in selected}|{f'r.{rx}.{rz}.npz' for rx,rz in airport_columns}
    yy=np.arange(-128,320)[:,None,None]
    for name in sorted(files):
        rx,rz=map(int,Path(name).stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        if 'minecraft:air' not in r['ids']:r['ids']['minecraft:air']=len(r['names']);r['names'].append('minecraft:air')
        air=r['ids']['minecraft:air'];bare=[s.split('[')[0] for s in r['names']]
        soil=np.array([s in SOIL|PLANTS for s in bare]);pave=np.array([s in PAVEMENT for s in bare])
        for q,v in ([] if a.components_only else zip(r['coords'],r['after'])):
            cx,cz=map(int,q);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            walk=sampled(d,'walk',xx,zz).astype(bool);floor=np.ceil(sampled(d,'grade2',xx,zz)/2).astype(int)
            clear=walk&(yy>floor)&(yy<=floor+4)&soil[v]
            # The established complete-width road already passed the earlier
            # pass. Clear only geology introduced by earthworks, not any door.
            counts['street_clearance_soil']+=int(clear.sum());v[clear]=air
            retire=sampled(d,'retired_fragments',xx,zz).astype(bool)&~walk
            clear=retire&(yy>=48)&pave[v]
            for x,y,z,X,Y,Z in bychunk[cx,cz]:clear&=~((xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&(yy>=y)&(yy<=Y))
            counts['recorded_retired_paving']+=int(clear.sum());v[clear]=air
        # Actual saved apron paving can extend a few cells beyond a catalog
        # rectangle. Its exposed sky, not a chunk-rounded boundary, owns these
        # columns. Keep elevated native track ballast and all non-soil devices.
        for x,y,z in airport_columns[rx,rz]:
            v=r['after'][r['index'][x//16,z//16]]
            for iy in np.flatnonzero(soil[v[y+129:,z%16,x%16]])+y+129:
                height=int(iy)-128
                ballast=bare[v[iy,z%16,x%16]]=='minecraft:gravel' and any(abs(px-x)<=1 and abs(pz-z)<=1 and py==height+1 for px,py,pz in rails[x//16,z//16])
                if not ballast:v[iy,z%16,x%16]=air;counts['actual_apron_soil_removed']+=1
        if selected.get((rx,rz)):
            with np.load(a.scan/name) as s:at=s['indices'][np.isin(s['labels'],list(selected[rx,rz]))].astype(np.int64)
            px=at%512+rx*512;pz=(at//512)%512+rz*512;py=at//(512*512)-128
            for x,y,z in zip(px,py,pz):
                q=int(x)//16,int(z)//16
                if q not in r['index']:raise ValueError('Missing classified source chunk')
                v=r['after'][r['index'][q]]
                if v[y+128,z%16,x%16]!=air:v[y+128,z%16,x%16]=air;counts['detached_cells_removed']+=1
        e.save();e.regions.clear();print('Final finite repairs',name,dict(counts),flush=True)
    rows=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'));m.update(regions=rows,cells=sum(r['cells'] for r in rows),finite_finish=dict(counts))
    (a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    if a.scan:(a.candidate/'floating-decisions.json').write_text(json.dumps(dict(counts=dict(Counter(r['action'] for r in decisions)),components=decisions,removed_cells=counts['detached_cells_removed']),indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ['candidate','base','tunnels','scan','airport-findings']:p.add_argument('--'+n,type=Path)
    p.add_argument('--components-only',action='store_true')
    finish(p.parse_args())
