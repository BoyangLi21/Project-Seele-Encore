"""Rebuild GeoFront LOD inputs from every saved tile; never invent missing edge chunks."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,json,os,struct,time,sys
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
sys.path.append(str(Path(__file__).resolve().parents[1]/'.Codex/map-deps'))
from export_r53_lod_source import export_tile
from export_patch_lod_r54 import stopped_world

def inventory(world):
    tiles={}
    for region in (world/'dimensions/projectseele/geofront/region').glob('r.*.*.mca'):
        with region.open('rb') as stream:header=stream.read(4096)
        if not header:continue
        if len(header)!=4096:raise ValueError('Truncated region header: '+str(region))
        rx,rz=map(int,region.stem.split('.')[1:])
        for index in range(1024):
            if struct.unpack_from('>I',header,index*4)[0]>>8:
                cx,cz=rx*32+index%32,rz*32+index//32
                tiles.setdefault((cx//4,cz//4),[]).append((cx,cz))
    return tiles

def export(job):
    world,tile,out=job
    try:return export_tile(world,tile,out,allow_partial=True)
    except Exception as error:
        if str(error).startswith('No saved source chunks in tile '):
            return dict(tile=tile,skipped='No FULL saved chunks; existing distant background is retained')
        return dict(tile=tile,error=str(error))

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('output',type=Path);p.add_argument('--workers',type=int,default=8);a=p.parse_args()
    if not 1<=a.workers<=8:p.error('Use 1..8 workers')
    a.output.mkdir(parents=True,exist_ok=True);columns=a.output/'columns';columns.mkdir(exist_ok=True)
    if any(columns.iterdir()):raise ValueError('Use a fresh export directory')
    start=time.monotonic();rows=[];failed=[];skipped=[]
    with stopped_world(a.world):
        tiles=inventory(a.world)
        (a.output/'source.json').write_text(json.dumps(dict(world=str(a.world),tiles=len(tiles),chunks=sum(map(len,tiles.values())),partial_tiles=sum(len(v)<16 for v in tiles.values()),scope='Every saved GeoFront tile including UN. Missing edge chunks remain absent, not air.')),'utf8')
        with ProcessPoolExecutor(max_workers=a.workers) as pool:
            futures=[pool.submit(export,(a.world,t,columns)) for t in sorted(tiles)]
            for f in as_completed(futures):
                r=f.result();(failed if 'error' in r else skipped if 'skipped' in r else rows).append(r)
                n=len(rows)+len(failed)+len(skipped)
                if n%100==0 or n==len(tiles):
                    progress=dict(completed=len(rows),failed=len(failed),skipped=len(skipped),total=len(tiles),seconds=round(time.monotonic()-start))
                    (a.output/'progress.json').write_text(json.dumps(progress),'utf8');print(progress,flush=True)
    report=dict(completed=len(rows),failed=failed,skipped=skipped,total=len(tiles),seconds=round(time.monotonic()-start),done=not failed,world_written=False)
    (a.output/'export.json').write_text(json.dumps(report,indent=2),'utf8')
    (a.output/'tiles.json').write_text(json.dumps(sorted(rows,key=lambda r:r['tile'])),'utf8')
    if failed:raise SystemExit('Some saved tiles could not be exported; inspect export.json before import')
if __name__=='__main__':main()
