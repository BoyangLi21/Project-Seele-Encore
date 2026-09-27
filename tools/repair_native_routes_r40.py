"""Close R40 whole-catalogue failures against measured, named passenger ports."""
from pathlib import Path
import argparse, json, hashlib, shutil
import regional_voxels as v
from measure_world_r40 import MeasuredWorld, WORLD, ROOT
from query_blocks import iter_block_entities

OUT=ROOT/'artifacts/world_combat_r40/native_route_repairs'


def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT
    w=MeasuredWorld()
    w.box((145,-443,-27),(156,-437,-23))
    w.box((88,-394,-264),(92,-391,-260))
    w.box((63,-462,306),(69,-456,311))
    w.load();p=v.Painter();changes={}
    def put(q,after,reason,allowed):
        old=w.block(q)
        if old==after:return
        if old is None or old.partition('[')[0] not in allowed:
            raise RuntimeError(('Unexpected port state',q,old))
        changes[q]=(after,reason)
    shell={'minecraft:air','projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:clear_glass'}
    for x in range(148,154):
        for y in range(-442,-438):
            put((x,y,-25),'minecraft:air','hangar_station/south_passenger_port',shell)
        put((x,-438,-25),'projectseele:nerv_structural_panel','hangar_station/south_header',shell)
    # The historic observation-hall route ends at this one isolated glass
    # block, not at a room wall. It has no adjacent glass enclosure or device.
    put((90,-393,-262),'minecraft:air','observation/isolated_mid_path_glass',{'projectseele:clear_glass'})
    # The new junction mistook a flush light (empty native collision) for an
    # obstruction and constructed a post through its real lift approach.
    for x in range(65,68):
        for y in range(-461,-458):
            put((x,y,309),'minecraft:air','east_lift/open_registered_approach',shell)
    tags={}
    for lo,hi in [((145,-443,-27),(156,-437,-23)),((88,-394,-264),(92,-391,-260)),((63,-462,306),(69,-456,311))]:
        tags.update(iter_block_entities(WORLD,v.DIM,lo,hi))
    assert not set(tags).intersection(changes),'A device occupies the proposed opening'
    for q,(after,reason) in sorted(changes.items()):
        p.match((*q,*q),w.block(q),after,'r40/native_routes/'+reason)
    p.meta.update(source='full_walk_raw.json: 9954 native paths, 34 failures',
                  preserved=['original lift car, fixed call button and controller','floor-level lighting','south station shell above the passenger header'],
                  defects=['registered entrance sealed by a ceiling-range heuristic','thin lamp misclassified as nonwalkable','isolated glass fragment at legacy observation destination'])
    p.save_plan('passenger_ports')
    if apply:p.apply('passenger_ports')
    path=WORLD/'quality_walk_cases.json';raw=path.read_bytes();cases=json.loads(raw)
    shortcut=[[-359.5,-466,726.5],[-359.5,-466,735.5],[-335.5,-466,735.5],[-335.5,-466,777.5],[-330.5,-466,777.5]]
    revisions=[]
    for case in cases:
        if case['id'] not in ('r22/gateway_shortcut','r22/gateway_shortcut/return'):continue
        target=shortcut if not case['id'].endswith('/return') else list(reversed(shortcut))
        if case['path']==target:continue
        revisions.append(dict(id=case['id'],before=case['path'],after=target,
                              reason='Same destinations via the real new east concourse opening at Z=735; the old line crossed its facade'))
        case['path']=target
    if apply and revisions:
        OUT.mkdir(parents=True,exist_ok=True)
        backup=OUT/('walk_cases_before_'+hashlib.sha256(raw).hexdigest()[:12]+'.json')
        if not backup.exists():backup.write_bytes(raw)
        path.write_text(json.dumps(cases,ensure_ascii=False),encoding='utf8')
    (OUT/'route_revisions.json').write_text(json.dumps(revisions,ensure_ascii=False,indent=2),encoding='utf8')
    print('Port cells',len(changes),'route revisions',len(revisions))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
