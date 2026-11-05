"""Read the actual candidate voxel columns, banks and unchanged surroundings."""
import argparse,json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL,SOIL
from query_blocks import AIR

def verify(C):
    m=json.loads((C/'manifest.json').read_text('utf8'));spec=m['enclosed_water']
    with np.load(C/'water-design.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);wet=d['wet'];bed=int(d['bed']);level=int(d['level']);e=Editor(C);errors=[];cells=columns=0
    yy=np.arange(-128,320)[:,None,None]
    for path in sorted((C/'source').glob('*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        names=np.asarray(r['names']);base=np.asarray([s.split('[')[0]for s in names]);natural=np.asarray([s in NATURAL for s in base])
        for (cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];mask=wet[q];delta=before!=after;cells+=int(delta.sum());columns+=int(mask.sum())
            if np.any(delta&(~mask|~natural[before]|(yy<bed))):errors.append(['unauthorized-cell-change',int(cx),int(cz)])
            if np.any(base[after[bed+128]][mask]!='minecraft:gravel'):errors.append(['missing-supported-bed',int(cx),int(cz)])
            for Y in range(bed+1,level+1):
                if np.any(names[after[Y+128]][mask]!='minecraft:water[level=0]'):errors.append(['water-column-gap',int(cx),int(cz),Y])
            if np.any(base[after[level+129]][mask]!='minecraft:air'):errors.append(['covered-water-surface',int(cx),int(cz)])
            if np.any(np.isin(base[after[bed+127]][mask],list(AIR|{'minecraft:water'}))):errors.append(['unsupported-bed',int(cx),int(cz)])
        e.regions.clear()
    faces=0
    for j,i in np.argwhere(wet):
        for dj,di in ((0,1),(0,-1),(1,0),(-1,0)):
            J,I=j+dj,i+di
            if wet[J,I]:continue
            for Y in range(bed+1,level+1):
                state=e.state(int(x+I),Y,int(z+J)).split('[')[0];faces+=1
                if state in AIR or state=='minecraft:water':errors.append(['open-water-bank',int(x+I),Y,int(z+J),state])
    if cells!=m['cells']or columns!=spec['columns']:errors.append(['incomplete-readback',cells,columns])
    report=dict(errors=errors,changed_cells=cells,water_columns=columns,contained_bank_faces=faces,bed=bed,level=level,
        unaffected_voxel_cells_exact=not any(r[0]=='unauthorized-cell-change'for r in errors),regional_height_field_unchanged=True,
        new_complete_river_claim=False,world_written=False)
    (C/'enclosed-water-check.json').write_text(json.dumps(report,indent=2),'utf8')
    (C/'independent-check.json').write_text(json.dumps(report,indent=2),'utf8')
    p=C/'functional-check.json';d=json.loads(p.read_text('utf8'));d['errors']=errors;d['enclosed_water_verified']=not errors;p.write_text(json.dumps(d,indent=2),'utf8')
    if errors:raise ValueError(errors[:12])
    print(json.dumps(report),flush=True)

def require_verified(C):
    m=json.loads((C/'manifest.json').read_text('utf8'))
    if 'enclosed_water'not in m:return
    r=json.loads((C/'enclosed-water-check.json').read_text('utf8'));ready=json.loads((C/'enclosed-water-release-check.json').read_text('utf8'))
    if r['errors']or r['changed_cells']!=m['cells']or r['water_columns']!=m['enclosed_water']['columns']:raise ValueError('Incomplete enclosed-water proof')
    if not all(ready[k]for k in('production_recipe_replay_passed','no_floating_components','identity_snapshot_ready','exact_voxel_views_reviewed')):raise ValueError('Unfinished enclosed-water release checks')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);verify(p.parse_args().candidate)
