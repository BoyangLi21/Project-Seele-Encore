"""Apply the reviewed immutable final bank-three plan without recalculating it."""
import gzip,json,hashlib
from pathlib import Path
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from query_blocks import iter_selected_sections

out=BASE/'bank3_outlet_final';stage='final_parallel_full_assembly_civil';folder=out/stage
report=json.loads((folder/'PLAN.json').read_text('utf8'))
assert not report['world_written'] and not list(folder.glob('applied_*'))
assert report['source_sha256']==hashlib.sha256((out/'SECTION_SOURCE.npz').read_bytes()).hexdigest()
vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
with gzip.open(folder/'ops.json.gz','rt',encoding='utf8')as f:operations=json.load(f)
for r in operations:
    assert r['mode']=='exact' and r['owner'].startswith('R52_')
    p.exact(tuple(r['box']),r['extra'][0],r['state'],r['owner'])
del operations
p.meta=json.loads((folder/'places.json').read_text('utf8'));receipt=p.apply(stage)
data=np.load(folder/'EXPECTED.npz');names=list(map(str,data['palette']));ids={s:i for i,s in enumerate(names)}
selected={};lookup={}
for i,(cx,cz,sy) in enumerate(data['section_keys']):selected.setdefault((int(cx),int(cz)),set()).add(int(sy));lookup[int(cx),int(cz),int(sy)]=i
seen=set()
for cx,cz,sy,pal,values in iter_selected_sections(vox.WORLD,vox.DIM,selected):
    i=lookup[cx,cz,sy];actual=np.array([ids[s]for s in pal],np.uint16)[values]
    assert np.array_equal(actual,data['after'][i]),('Readback mismatch',cx,cz,sy);seen.add(i)
assert len(seen)==len(lookup)
report.update(world_written=True,receipt=receipt,all_sections_exact_readback=True)
(folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print('FINAL_BANK3_ALL_SECTIONS_VERIFIED',len(seen),flush=True)
