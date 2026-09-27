"""Select every old public path whose full player sweep touches a changed collider."""
from pathlib import Path
import json,copy
import numpy as np
import compose_world_r40 as receipts
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r42';WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW'


def main():
    receipts.ART=ART;receipts.REVIEW=WORLD;receipts.OUT=ART/'world_composition';receipts.SOURCE=ART/'source_world_backup'
    _,cells,_,conflicts=receipts.inventory();assert not conflicts
    shapes={canonical_state(k):v for k,v in json.loads((WORLD/'native_collision_shapes.json').read_text()).items()}
    changed=[]
    for q,(before,after) in cells.items():
        old=shapes.get(before,[] if before.endswith(':air') else None);new=shapes.get(after,[] if after.endswith(':air') else None)
        if old==new and old is not None:continue
        for box in (old or [])+(new or []):
            changed.append([q[0]+box[0]-.300001,q[1]+box[1]-1.800001,q[2]+box[2]-.300001,q[0]+box[3]+.300001,q[1]+box[4]+.000001,q[2]+box[5]+.300001])
    boxes=np.asarray(changed);old=json.loads((ART/'source_world_backup/quality_walk_cases.json').read_text());selected=[]
    for case in old:
        route=case.get('path',[case.get('start'),case.get('end')])
        if any(p is None for p in route):continue
        for start,end in zip(route,route[1:]):
            lo=np.minimum(start,end);hi=np.maximum(start,end)
            if len(boxes) and np.any(np.all(hi>=boxes[:,:3],1)&np.all(lo<=boxes[:,3:],1)):
                selected.append(case);break
    current=json.loads((WORLD/'r42_walk_cases.json').read_text());combined={c['id']:c for c in current}
    for c in selected:combined.setdefault(c['id'],c)
    rows=list(combined.values());(WORLD/'r42_walk_cases.json').write_text(json.dumps(rows,ensure_ascii=False),'utf8')
    (ART/'affected_path_inventory.json').write_text(json.dumps(dict(old_paths=len(old),changed_collision_boxes=len(changed),selected=len(selected),total_cases=len(rows),cases=rows),ensure_ascii=False,indent=2),'utf8')
    print('Selected',len(selected),'old paths by full 3D player sweep; total',len(rows))


if __name__=='__main__':main()
