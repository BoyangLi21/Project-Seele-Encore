"""Retire the explicitly reported obsolete observation-lift bottom stop."""
from pathlib import Path
import copy, gzip, hashlib, io, json, msvcrt
import nbtlib
import regional_voxels as vox
from query_blocks import read_box, iter_block_entities
from rebind_r53_personnel_installation import rebind
from apply_s20_approved_semantic_repairs import atomic_replace


def repair_retained_controls(world, out):
    """Keep the original car's remote controls attached to a retained floor."""
    lo, hi = (86, -1014, 363), (93, -983, 371)
    tags = dict(iter_block_entities(world, 'projectseele:geofront', lo, hi))
    changes = []
    for pos, tag in tags.items():
        data = tag.get('data', {})
        if tuple(int(data.get(k, 0)) for k in ('controllerX', 'controllerY', 'controllerZ')) != (86, -1088, 366):
            continue
        after = copy.deepcopy(tag)
        after['data']['controllerY'] = nbtlib.Int(-1014)
        changes.append((pos, tag, after))
    if not changes:
        return 0
    states = read_box(world, 'projectseele:geofront', lo, hi)
    vox.WORLD, vox.DIM, vox.OUT = world, 'projectseele:geofront', out
    painter = vox.Painter(vertical_bounds=(-1440, 320))
    for pos, before, after in changes:
        painter.update_block_entity(pos, states[pos], before, after, 'rebind_retained_observation_car_control')
    lock = (world/'session.lock').open('r+b')
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        painter.apply('retained_car_controls', session_lock=lock)
        actual = dict(iter_block_entities(world, 'projectseele:geofront', lo, hi))
        assert all(actual[pos] == after for pos, _, after in changes)
    finally:
        lock.close()
    return len(changes)

def run(base):
    world=base/'client/saves/SEELE_R53_WORLD'
    out=base/'observation-bottom-retirement';out.mkdir(exist_ok=True)
    manifest_path=world/'personnel_lifts_r52.json'
    bundle_path=world/'ROOT_ASSEMBLY_BUNDLE.json'
    cap_path=world/'dimensions/projectseele/geofront/data/capabilities.dat'
    manifest=json.loads(manifest_path.read_text('utf8'))
    lift=next(l for l in manifest['lifts'] if l['id']=='r25-west-observation')
    old=next((f for f in lift['floors'] if f['cabin'][1]==-1088),None)
    if old is None:
        count=repair_retained_controls(world,out)
        print(f'Obsolete observation stop already retired; rebound controls={count}');return
    caps=nbtlib.load(cap_path);group=caps['data']['movingelevators:elevator_groups']['86;366']['group']
    assert not bool(group['isMoving'])
    assert [(int(y),bool(f['isCageAvailable'])) for y,f in zip(group['floors'],group['floorData'])]==[(-1088,False),(-1014,False),(-987,True)]
    desired={tuple(old['controller']):'projectseele:nerv_shaft_panel'}
    for c in old['calls']:desired[tuple(c['position'])]='projectseele:nerv_wall_panel'
    for d in old['landing_doors']:desired[tuple(d['pos'])]='projectseele:nerv_wall_panel'
    # The declared lower shaft has no remaining destination. Close its entire
    # retired sweep below the retained boarding stop, leaving the actual car.
    for x in range(87,92):
        for z in range(364,369):
            for y in range(-1088,-1015):desired[x,y,z]='projectseele:nerv_shaft_panel'
    desired[-6,-1036,141]='projectseele:nerv_structural_panel'
    lo=(-6,-1088,141);hi=(91,-1016,371)
    states=read_box(world,'projectseele:geofront',lo,hi)
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    vox.WORLD=world;vox.DIM='projectseele:geofront';vox.OUT=out
    painter=vox.Painter(vertical_bounds=(-1440,320));rows=[]
    for p,s in desired.items():
        if states[p]==s:continue
        assert p not in tags or p==tuple(old['controller']),(p,str(tags[p].get('id')))
        painter.exact((*p,*p),states[p],s,'retire_obsolete_observation_bottom_or_restore_reported_floor')
        rows.append(dict(pos=p,before=states[p],after=s,before_nbt=tags[p].snbt() if p in tags else None))
    lift['floors']=[f for f in lift['floors'] if f['cabin'][1]!=-1088]
    pairs=[(int(y),copy.deepcopy(f)) for y,f in zip(group['floors'],group['floorData']) if int(y)!=-1088]
    group['floors']=nbtlib.IntArray([y for y,_ in pairs]);group['floorData']=nbtlib.List[nbtlib.Compound]([f for _,f in pairs])
    encode=lambda v:(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    manifest_raw=encode(manifest);before_bundle=bundle_path.read_bytes();bundle=json.loads(before_bundle)
    bundle['personnel_lifts']['sha256']=hashlib.sha256(manifest_raw).hexdigest();bundle_raw=encode(bundle)
    runtime_path,runtime_raw,_=rebind(world,before_bundle,bundle_raw)
    stream=io.BytesIO();caps.write(stream);cap_raw=gzip.compress(stream.getvalue(),mtime=0)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(encode(rows),mtime=0))
    lock=(world/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        painter.apply('retire_reported_observation_bottom',session_lock=lock)
        for path,raw in ((cap_path,cap_raw),(manifest_path,manifest_raw),(bundle_path,bundle_raw),(runtime_path,runtime_raw)):
            atomic_replace(path,raw);assert path.read_bytes()==raw
        back=read_box(world,'projectseele:geofront',lo,hi)
        assert all(back[tuple(r['pos'])]==r['after'] for r in rows)
    finally:lock.close()
    rebound=repair_retained_controls(world,out)
    report=dict(changed_cells=len(rows),remaining_floors=[y for y,_ in pairs],same_car_at=-987,actual_readback=True)
    report['rebound_retained_car_controls']=rebound
    (out/'INSTALLED.json').write_bytes(encode(report));print(json.dumps(report))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);run(p.parse_args().base)
