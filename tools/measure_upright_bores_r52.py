"""Root continuous-bore measurement from complete, clipped triangle hulls.

No world writes. Convex Bezier control hulls enclose the entire curve, rather
than relying on a few animation frames. One-metre height bands preserve the
real upright silhouette. Straight vertical sweeps use the exact union of
height-band projections, because every part traverses that same column.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse, hashlib, json, time
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from query_blocks import chunk_statuses, iter_selected_sections
from plan_bank3_exact_geometry_r52 import part, contains

ROOT=Path(__file__).resolve().parents[1]
BASE=None
OUT=None


def split(p):
    rows=[np.asarray(p)]
    while len(rows[-1])>1:rows.append((rows[-1][:-1]+rows[-1][1:])/2)
    return np.array([r[0] for r in rows]),np.array([r[-1] for r in rows[::-1]])


def pieces(p,depth):
    if depth==0:return [p]
    a,b=split(p);return pieces(a,depth-1)+pieces(b,depth-1)


def make_parts(directory,hulls,only_legs=(),height_range=None):
    output=[]
    for leg in directory['legs']:
        if leg['id'].endswith('/reverse') or 'centre_curve' not in leg:continue
        if only_legs and leg['id'] not in only_legs:continue
        variant=int(leg['id'][4]);bands=hulls['variants'][variant]['height_slices_1m']
        if height_range is not None:
            bands=[b for b in bands if b['height_band_m'][0]<height_range[1] and b['height_band_m'][1]>height_range[0]]
            assert bands, 'Requested actual height bands are empty'
        for number,s in enumerate(leg['centre_curve']['segments']):
            controls=np.array(s['controls']);vertical=len(controls)==2 and np.linalg.norm((controls[1]-controls[0])[[0,2]])<1e-8
            if vertical:
                polygon=np.concatenate([b['actual_clipped_XZ_convex_hull_m'] for b in bands if b.get('actual_clipped_XZ_convex_hull_m')])
                polygon=polygon[ConvexHull(polygon).vertices]
                low=min(b['height_band_m'][0] for b in bands)
                high=max(b['height_band_m'][1] for b in bands)
                sections=[(polygon,low,high)]
            else:
                sections=[]
                for band in bands:
                    polygon=np.array(band.get('actual_clipped_XZ_convex_hull_m',[]))
                    if len(polygon)<3:continue
                    low,high=band['height_band_m']
                    if high-low<1e-8:continue
                    sections.append((polygon,low,high))
            for sub,curve in enumerate(pieces(controls,2) if len(controls)==6 else [controls]):
                for band,(polygon,low,high) in enumerate(sections):
                    body=np.concatenate([np.column_stack((polygon[:,0],np.full(len(polygon),y),polygon[:,1])) for y in (low,high)])
                    points=(curve[:,None,:]+body[None,:,:]).reshape(-1,3)
                    shape=part(f'{leg["id"]}/{number}/{sub}/{band}',2-variant,'upright_control_hull',points)
                    shape.update(leg=leg['id'],variant=variant,bank=int(leg['id'].split('/')[1][-1]),segment=number)
                    output.append(shape)
    return output


def main():
    global OUT, BASE
    ap=argparse.ArgumentParser();ap.add_argument('--measure',action='store_true')
    ap.add_argument('--base',type=Path,required=True,help='Explicit current authoring base, never the rejected R52 after-state')
    ap.add_argument('--hulls',type=Path,required=True,help='Explicit final complete source hull export; withdrawn inner-capture file is forbidden')
    ap.add_argument('--directory',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--only-leg',action='append',default=[])
    ap.add_argument('--height-range',type=float,nargs=2,help='Explicit partial assembly band survey, never full-body acceptance')
    args=ap.parse_args()
    BASE=args.base.resolve()
    world=BASE/'WORLD'
    assert world.is_dir() and (BASE/'ROOT_SPATIAL_PLAN.json').is_file()
    accepted=json.loads((BASE/'ROOT_SPATIAL_PLAN.json').read_text('utf8'))
    assert accepted['map_author']=='root' and accepted['epoch']==53
    assert accepted['bank_foot_y']==-1030 and accepted['bay_foot_y']==-1062
    assert accepted['delivery_scope']['id']=='scope124'
    OUT=args.output.resolve()
    assert OUT.is_relative_to(BASE.resolve()),'Root candidate output required'
    OUT.mkdir(parents=True,exist_ok=True)
    assert not args.measure or not (OUT/'MEASURED_SOURCE.npz').exists(),'Keep the prior actual source survey; choose a fresh output directory'
    directory_path=args.directory.resolve()
    hull_path=args.hulls.resolve()
    assert hull_path.name!='UPRIGHT_TRIANGLE_HEIGHT_HULLS_WITH_CAPTURE.json','Four inner launch rails were proven to intersect the carrier; use reviewed outer-capture source'
    directory=json.loads(directory_path.read_text('utf8'));hulls=json.loads(hull_path.read_text('utf8'))
    assert hulls['root_design_sha256']==hashlib.sha256(directory_path.read_bytes()).hexdigest(),'Hull directions and route design differ'
    if args.height_range:assert args.height_range[0]<args.height_range[1]
    shapes=make_parts(directory,hulls,args.only_leg,args.height_range);members=defaultdict(list);selected=defaultdict(set)
    for i,p in enumerate(shapes):
        low,high=[np.floor(v/16).astype(int) for v in p['bounds']];eq=p['equations']
        # Vectorize finite chunk broadphase instead of Python loops over the
        # several-kilometre diagonal's enclosing rectangle.
        grid=np.indices(tuple(high-low+1)).reshape(3,-1).T+low
        active=np.arange(len(grid));centres=grid*16+8
        for start in range(0,len(eq),16):
            e=eq[start:start+16]
            good=np.all(centres[active]@e[:,:3].T+e[:,3]<=3.1+8*np.abs(e[:,:3]).sum(1),axis=1)
            active=active[good]
            if not len(active):break
        for cx,sy,cz in grid[active]:
            key=(int(cx),int(cz),int(sy));members[key].append(i);selected[key[:2]].add(key[2])
    report=dict(world_written=False,clearance_passed=False,parts=len(shapes),chunks=len(selected),sections=len(members),
        directory_sha256=hashlib.sha256(directory_path.read_bytes()).hexdigest(),
        hulls_sha256=hashlib.sha256(hull_path.read_bytes()).hexdigest(),
        measured_legs=args.only_leg or 'all_actual_forward_continuous_legs',
        measured_height_range_m=args.height_range,
        minimum_engineering_clearance_m=1.01,lining_m=2,
        policy='Real complete assembly height-band convex hulls translated by entire Bezier control hulls; fixed upright posture; no old turn-radius chambers.')
    (OUT/'SHAPE_PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)
    if not args.measure:return
    statuses=chunk_statuses(world,'projectseele:geofront',selected)
    missing={str(k):v for k,v in statuses.items() if v!='full'}
    if missing:
        (OUT/'MISSING_CHUNKS.json').write_text(json.dumps(missing,indent=2),'utf8')
        raise ValueError(f'{len(missing)} selected chunks are not FULL')
    palette=['minecraft:air'];ids={palette[0]:0};rows=[];started=time.monotonic();local=np.indices((16,16,16)).reshape(3,-1).T[:,[2,0,1]]+.5
    overlap=0
    for count,(cx,cz,sy,pal,old) in enumerate(iter_selected_sections(world,'projectseele:geofront',selected),1):
        mapping=[]
        for name in pal:
            if name not in ids:ids[name]=len(palette);palette.append(name)
            mapping.append(ids[name])
        xyz=local+[cx*16,sy*16,cz*16];core=np.zeros(4096,bool);shell=np.zeros(4096,bool);lanes=np.zeros((3,4096),bool)
        banks=np.zeros(4096,np.uint8)
        for i in members[cx,cz,sy]:
            p=shapes[i];inside=contains(p,xyz);outside=contains(p,xyz,2)
            core|=inside;shell|=outside;lanes[p['lane']]|=inside;banks[outside]|=1<<(p['bank']-1)
        # Overlapping endpoint spaces may be intentional shared big banks;
        # record them for divider review, never silently erase partitions.
        overlap+=int((lanes.sum(axis=0)>1).sum())
        rows.append(((cx,cz,sy),np.asarray(mapping,np.uint16)[old],core,shell,banks))
        if count%500==0:print('bore sections',count,'/',len(members),'seconds',round(time.monotonic()-started,1),flush=True)
    np.savez_compressed(OUT/'MEASURED_SOURCE.npz',section_keys=np.array([r[0] for r in rows],np.int32),
        before=np.array([r[1] for r in rows],np.uint16),core=np.array([r[2] for r in rows]),
        shell=np.array([r[3] for r in rows]),banks=np.array([r[4] for r in rows]),palette=palette)
    report.update(measured=True,core_cells=sum(int(r[2].sum()) for r in rows),
        shell_cells=sum(int(r[3].sum()) for r in rows),multiple_lane_core_cells=overlap,seconds=time.monotonic()-started)
    (OUT/'MEASURED_REPORT.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
