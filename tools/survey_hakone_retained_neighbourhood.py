"""Survey complete current parcels and original path ownership in a FULL capture."""
import argparse,copy,json
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from author_hakone_district_blocks import Frontage
from map_pipeline.launch_earthworks import ground
from prepare_hakone_main_terrain import sample_grid
from query_blocks import iter_block_entities
from install_r53_carrier_trays import stopped_world

def survey(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));x,z,X,Z=cap['bounds_xz']
    if cap['unavailable_chunks']:raise ValueError('Complete current FULL capture required')
    a.out.mkdir(exist_ok=False,parents=True)
    with np.load(a.terrain)as f:gis={k:f[k]for k in ('x','z','height_y')}
    zz,xx=np.mgrid[z:Z+1,x:X+1]
    np.savez_compressed(a.out/'surface.npz',bounds=[x,z,X,Z],old_ground=ground(Editor(a.source),[x,z,X,Z]),surveyed=sample_grid(gis,'height_y',xx,zz))
    with stopped_world(Path(cap['world'])):tags=dict(iter_block_entities(Path(cap['world']),'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](copy.deepcopy(list(tags.values())))}).save(a.out/'captured-devices.dat',gzipped=True)
    legacy=json.loads(a.legacy_paths.read_text('utf8'))['approaches'];rows=[]
    for row in json.loads((a.authority/'catalog.json').read_text('utf8')):
        if row.get('id')not in a.parcel:continue
        r=copy.deepcopy(row);s=r['site'];c=Frontage(s);hx,hz=s['half']
        p=c.point(-hx-2,-2,-hz-2);q=c.point(hx+2,s['floors']*5+15,hz+3)
        box=list(map(int,[*np.minimum(p,q),*np.maximum(p,q)]))
        if not(x<=box[0]<=box[3]<=X and z<=box[2]<=box[5]<=Z):raise ValueError(('Parcel capture incomplete',r['id']))
        if any(all(box[k]<=actor['pos'][k]<=box[k+3]for k in range(3))for actor in cap['actors']):raise ValueError('Explicit actor preservation needed')
        r.update(payload_bounds=box,surveyed_floor=s['floor'],use=r.get('label',''))
        r['approach'][1]=s['floor']+1
        r['devices']=[list(p)for p in tags if all(box[k]<=p[k]<=box[k+3]for k in range(3))]
        paths=[p for p in legacy if p and p[0][0]==r['approach'][0]and p[0][2]==r['approach'][2]]
        expected=2 if r.get('kind')=='station'else 1
        if len(paths)!=expected:raise ValueError(('Original approach ownership ambiguous',r['id'],len(paths)))
        r['footway']=sum(paths,[]);r['original_approach_paths']=paths;rows.append(r)
    if len(rows)!=len(set(a.parcel)):raise ValueError('Selected parcel missing from catalog')
    (a.out/'buildings.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
    print('Surveyed',len(rows),'complete retained parcels and',len(tags),'current devices',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','authority','legacy-paths','terrain','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--parcel',action='append',required=True);survey(p.parse_args())
