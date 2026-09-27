"""Remove only new edge-rail pieces intersecting four registered CIWS bases."""
from pathlib import Path
import argparse,json
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'
WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW';OUT=ART/'equipment_clearance'


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    equipment=json.loads((ART/'native_spatial/fixed_weapon_exemptions.json').read_text('utf8'))['equipment']
    w=MeasuredWorld(WORLD);before=MeasuredWorld(ART/'source_world_backup')
    for e in equipment:
        lo=tuple(int(v//1)-1 for v in e['lo']);hi=tuple(int(v//1)+1 for v in e['hi']);w.box(lo,hi);before.box(lo,hi)
    w.load();before.load();shapes={v.canonical_state(k):b for k,b in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();rows=[]
    for e in equipment:
        lo=e['lo'];hi=e['hi']
        for x in range(int(lo[0]//1)-1,int(hi[0]//1)+2):
            for y in range(int(lo[1]//1)-1,int(hi[1]//1)+2):
                for z in range(int(lo[2]//1)-1,int(hi[2]//1)+2):
                    q=(x,y,z);old=w.block(q)
                    if not old or not old.startswith('projectseele:nerv_edge_rail['):continue
                    overlap=any(all(min(q[i]+b[i+3],hi[i])-max(q[i]+b[i],lo[i])>1e-7 for i in range(3)) for b in shapes[old])
                    if not overlap:continue
                    assert before.block(q) in AIR,('Not a new R41 rail',q,before.block(q))
                    p.match((*q,*q),old,'minecraft:air','r41/registered_weapon_base_clearance');rows.append(dict(pos=q,weapon=e['uuid'],before=old))
    p.meta.update(removed=rows,equipment=equipment,reason='Native weapon volume and actual high-angle photo show new stair-edge rails crowding the base. Preserve all four weapons and the surrounding public stair rails; no actor/progress fields are changed.')
    p.save_plan('fixed_weapon_base_clearance')
    if apply:p.apply('fixed_weapon_base_clearance')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8');print('Removed new overlapping rail pieces',len(rows))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
