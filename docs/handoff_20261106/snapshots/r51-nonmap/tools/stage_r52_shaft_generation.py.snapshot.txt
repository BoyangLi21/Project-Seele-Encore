"""Reuse the stopped native fixture for the Root remote aircraft shaft."""
import json,hashlib,shutil
from pathlib import Path
import numpy as np
from r52_spatial_plan import BASE
from query_blocks import chunk_statuses

out=BASE/'native_generation/airshaft';assert not out.exists();out.mkdir()
world=BASE/'WORLD_R52';base=BASE/'native_generation';spec=json.loads((base/'STAGED.json').read_text('utf8'))
assert json.loads((base/'RUN_RESULT.json').read_text('utf8'))['exit_code']==0
fixture=Path(spec['fixture']);requested={(x,z)for x in range(-1220//16,-1020//16+1)for z in range(-820//16,-620//16+1)}
# Explicit access from the existing airport apron to the southern UG mouth;
# only future terrain is completed, no new landscape or flight permission.
nodes=[(-640,-270),(-840,-480),(-1120,-580),(-1120,-720)]
for a,b in zip(nodes,nodes[1:]):
    for point in np.linspace(a,b,max(2,int(np.linalg.norm(np.subtract(a,b))/8))+1):
        x,z=point
        requested|={(cx,cz)for cx in range(int(np.floor((x-80)/16)),int(np.floor((x+80)/16))+1)for cz in range(int(np.floor((z-70)/16)),int(np.floor((z+70)/16))+1)}
statuses=chunk_statuses(world,'projectseele:geofront',requested);targets={q:s for q,s in statuses.items()if s!='full'}
context={(x+dx,z+dz)for x,z in targets for dx in range(-2,3)for dz in range(-2,3)};regions={(x//32,z//32)for x,z in context};before={}
for rx,rz in regions:
    rel=f'dimensions/projectseele/geofront/region/r.{rx}.{rz}.mca';source=world/rel;target=fixture/rel
    if source.is_file():
        raw=source.read_bytes();before[rel]=hashlib.sha256(raw).hexdigest();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    else:assert not target.exists(),'Fixture extra region not in source needs explicit review'
spec.update(targets=[dict(x=x,z=z,status=s)for(x,z),s in sorted(targets.items())],region_source_sha256=before,
            source_level_sha256=hashlib.sha256((world/'level.dat').read_bytes()).hexdigest(),job='Remote transport shaft and actual future access terrain',
            root_shaft_centre=[-1120,-720],root_access_xz=nodes,world_written=False)
(out/'STAGED.json').write_text(json.dumps(spec,indent=2),'utf8');print('Native shaft job targets',len(targets),'source regions',len(regions),flush=True)
