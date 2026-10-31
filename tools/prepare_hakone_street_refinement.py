"""Prepare a refinement baseline from the already-installed, read-back map patch."""
import argparse,json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from query_blocks import AIR

def prepare(a):
    receipt=json.loads((a.installed/'installation-20261031/installation.json').read_text('utf8'))
    if receipt['status']!='installed':raise ValueError('The predecessor must be installed')
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir()
    kept=json.loads((a.installed/'ground-fit-v6/retained-parcels.json').read_text('utf8'))
    catalog={}
    for rel in ('main-district-current-ready-v2/neighbourhood.json','valley-integration-v12/valley-buildings.json',
                'city-south-streets-v3/neighbourhood.json','city-south-streets-v3/retained-neighbourhood.json'):
        rows=json.loads((a.gis/rel).read_text('utf8'))
        if isinstance(rows,dict):rows=rows['buildings']
        for row in rows:
            site=row.get('site');key=row.get('id')
            if site:
                x,z=site['centre'];key=key or f'valley/{x}/{z}'
            if key in kept:catalog[key]=dict(row,template='valley'if rel.startswith('valley')else'district'if 'site'in row else'city')
    for key,box in kept.items():
        if key not in catalog:catalog[key]=dict(id=key,template='retained',bounds=box)
    regions={}
    for key,row in catalog.items():
        x,y,z,X,Y,Z=kept[key];row['id']=key;row['occupied_bounds']=kept[key]
        for rx in range((x-20)//512,(X+20)//512+1):
            for rz in range((z-20)//512,(Z+20)//512+1):regions.setdefault((rx,rz),set()).add(key)
    editor=Editor(a.installed/'ready-v1');written=[]
    for n,(rx,rz)in enumerate(sorted(regions)):
        path=a.installed/'ready-v1/source'/f'r.{rx}.{rz}.npz'
        if not path.exists():continue
        region=editor.region(rx*512,rz*512)
        np.savez_compressed(a.out/'source'/path.name,coordinates=region['coords'],blocks=region['after'],palette=region['names'])
        written.append(path.name);editor.regions.clear()
        print('Current installed source',n+1,'/',len(regions),path.name,flush=True)
    (a.out/'catalog.json').write_text(json.dumps(list(catalog.values()),ensure_ascii=False,indent=2),'utf8')
    (a.out/'manifest.json').write_text(json.dumps(dict(world=receipt['world'],source_installation=str(a.installed/'installation-20261031/installation.json'),
        source_kind='Source plus installed predecessor changes; installer must match every edited current block',
        regions=[],cells=0,world_written=False,occupied_buildings=len(catalog),source_files=written),indent=2),'utf8')
    editor=Editor(a.out);rows=[]
    for key,row in catalog.items():
        x,y,z,X,Y,Z=kept[key];doors=[]
        for zz in range(z,Z+1):
            for xx in range(x,X+1):
                if xx not in (x,X)and zz not in (z,Z):continue
                state=editor.state(xx,y+1,zz)
                if '_door['in state and 'half=lower'in state:doors.append([xx,y+1,zz,state])
        soil={'minecraft:dirt','minecraft:grass_block','minecraft:stone','minecraft:andesite','minecraft:granite','minecraft:diorite'}
        buried=[]
        for xx,zz in [(xx,zz)for xx in range(x-2,X+3)for zz in(z-2,Z+2)]+[(xx,zz)for xx in(x-2,X+2)for zz in range(z-1,Z+2)]:
            if any(editor.state(xx,yy,zz).split('[')[0]in soil for yy in range(y+1,y+4)):buried.append([xx,zz])
        roof=[]
        if row.get('site')and row['site']['floors']>0:
            roof_y=y+row['site']['floors']*5
            for xx in range(x+1,X):
                for zz in range(z+1,Z):
                    if editor.state(xx,roof_y,zz).split('[')[0]in AIR:roof.append([xx,roof_y,zz])
        rows.append(dict(id=key,doors=doors,buried_perimeter_columns=buried,roof_openings=roof))
        # Keep only neighboring regions hot for the small footprint reads.
        if len(editor.regions)>4:editor.regions.clear()
    (a.out/'before-findings.json').write_text(json.dumps(rows,ensure_ascii=False),'utf8')
    print(json.dumps(dict(buildings=len(rows),no_detected_doors=sum(not r['doors']for r in rows),
        buried_frontages=sum(bool(r['buried_perimeter_columns'])for r in rows),
        roof_openings=sum(len(r['roof_openings'])for r in rows))),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('gis','installed','out'):p.add_argument('--'+n,type=Path,required=True)
    prepare(p.parse_args())
