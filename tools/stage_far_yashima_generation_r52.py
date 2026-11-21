"""Native terrain only for the explicit far ridge; reuses the stopped fixture."""
import json,hashlib
from pathlib import Path
from r52_spatial_plan import BASE
from query_blocks import chunk_statuses

out=BASE/'native_generation/far_yashima';assert not out.exists();out.mkdir()
spec=json.loads((BASE/'native_generation/STAGED.json').read_text('utf8'));world=BASE/'WORLD_R52';fixture=Path(spec['fixture'])
survey=json.loads((BASE/'far_yashima/SURVEY.json').read_text('utf8'));requested=set(map(tuple,survey['missing_chunks']))
statuses=chunk_statuses(world,'projectseele:geofront',requested);targets={q:s for q,s in statuses.items()if s!='full'}
regions={((x+dx)//32,(z+dz)//32)for x,z in targets for dx in(-2,2)for dz in(-2,2)};before={}
for rx,rz in regions:
    rel=f'dimensions/projectseele/geofront/region/r.{rx}.{rz}.mca';source=world/rel;target=fixture/rel
    if source.exists():
        raw=source.read_bytes();before[rel]=hashlib.sha256(raw).hexdigest();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    else:assert not target.exists(),('Unexpected fixture region',rel)
spec.update(targets=[dict(x=x,z=z,status=s)for(x,z),s in sorted(targets.items())],region_source_sha256=before,source_level_sha256=hashlib.sha256((world/'level.dat').read_bytes()).hexdigest(),job='Explicit far Yashima ridge actual native terrain',world_written=False)
(out/'STAGED.json').write_text(json.dumps(spec,indent=2),'utf8');print('Native far-ridge targets',len(targets),'source regions',len(regions),flush=True)
