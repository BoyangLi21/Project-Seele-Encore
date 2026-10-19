"""Repaint measured launch-chamber walls without changing their solid volume."""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,msvcrt
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities


def protected_cells(world):
    protected={}
    def visit(value):
        if isinstance(value,dict):
            if isinstance(value.get('position'),list) and isinstance(value.get('state'),str):
                key=tuple(value['position'])
                if len(key)==3:protected[key]=value['state']
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(json.loads((world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8')))
    return protected


def restore_contacts(world,out):
    rows=json.loads(gzip.decompress((out/'EXACT_DELTA.json.gz').read_bytes()));protected=protected_cells(world)
    restore=[r for r in rows if tuple(r['pos'])in protected]
    assert all(r['old']==protected[tuple(r['pos'])]for r in restore)
    vox.WORLD=world;vox.DIM='projectseele:geofront';vox.OUT=out
    painter=vox.Painter(vertical_bounds=(-1440,320))
    for r in restore:painter.exact((*r['pos'],*r['pos']),r['new'],r['old'],'retain_original_mechanical_contact')
    painter.apply('restore_declared_supports')
    (out/'SUPPORT_RESTORE.json.gz').write_bytes(gzip.compress(json.dumps(restore).encode()))
    print('Restored original mechanical contact identities:',len(restore))


def verify(world,out):
    rows=json.loads(gzip.decompress((out/'EXACT_DELTA.json.gz').read_bytes()))
    restoration=out/'SUPPORT_RESTORE.json.gz'
    restored=json.loads(gzip.decompress(restoration.read_bytes()))if restoration.exists()else[]
    returned={tuple(r['pos']):r['old']for r in restored}
    with (world/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        actual=read_box(world,'projectseele:geofront',(-32,-1029,-7),(92,-951,144))
        for r in rows:
            p=tuple(r['pos']);expected=returned.get(p,r['new'])
            if actual[p]!=expected:raise ValueError(f'Installed finish differs at {p}: {actual[p]} != {expected}')
        for p,state in protected_cells(world).items():
            if p in actual and actual[p]!=state:raise ValueError(f'Declared contact differs at {p}')
    report=dict(verified=True,original_cells_checked=len(rows),restored_contacts=len(restored),
                net_finish_cells=len(rows)-len(restored),declared_contacts_preserved=True,
                delta_sha256=hashlib.sha256((out/'EXACT_DELTA.json.gz').read_bytes()).hexdigest(),
                restoration_sha256=hashlib.sha256(restoration.read_bytes()).hexdigest()if restored else None)
    (out/'FINAL_READBACK.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))


def run(world,out,apply=False):
    lo=(-32,-1029,-7);hi=(92,-951,144)
    allowed={'projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel'}
    out.mkdir(parents=True,exist_ok=True)
    exact=out/'EXACT_DELTA.json.gz'
    if not apply:
        states=read_box(world,'projectseele:geofront',lo,hi)
        tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));rows=[];protected=protected_cells(world)
        for (x,y,z),state in states.items():
            if state not in allowed:continue
            if (x,y,z)in protected:continue
            if (x,y,z)in tags:raise ValueError('A plain wall unexpectedly owns a block entity')
            # Matching plate coordinates across a full wall face, without filling openings.
            horizontal=z if x in (-32,-31,-30,-29,5,13,47,55,89,90,91,92)else x
            target=f'projectseele:nerv_launch_armor[column={horizontal%8},row={(y+1030)%16}]'
            rows.append({'pos':[x,y,z],'old':state,'new':target})
        exact.write_bytes(gzip.compress(json.dumps(rows,separators=(',',':')).encode()))
        report=dict(source_world=str(world),bounds=[lo,hi],changed_cells=len(rows),
                    old_states=dict(collections.Counter(r['old']for r in rows)),
                    collision='full cube before and after',openings_filled=0,block_entities_changed=0,
                    routing_changed=False,progress_changed=False)
        (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report));return
    rows=json.loads(gzip.decompress(exact.read_bytes()))
    with (world/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        actual=read_box(world,'projectseele:geofront',lo,hi)
        for r in rows:
            if actual[tuple(r['pos'])]!=r['old']:raise ValueError(f'Changed source {r["pos"]}')
        vox.WORLD=world;vox.DIM='projectseele:geofront';vox.OUT=out
        painter=vox.Painter(vertical_bounds=(-1440,320))
        for r in rows:painter.exact((*r['pos'],*r['pos']),r['old'],r['new'],'launch_chamber_finish_only')
        painter.apply('launch_chamber_armor',session_lock=lock)
        actual=read_box(world,'projectseele:geofront',lo,hi)
        assert all(actual[tuple(r['pos'])]==r['new']for r in rows)
    (out/'INSTALLED.json').write_text(json.dumps(dict(verified=True,changed_cells=len(rows),delta_sha256=hashlib.sha256(exact.read_bytes()).hexdigest()),indent=2),'utf8')
    print(f'Installed and read back {len(rows)} existing wall cells; no new solid volume')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('out',type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--restore-contacts',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args()
    if a.verify:verify(a.world,a.out)
    elif a.restore_contacts:restore_contacts(a.world,a.out)
    else:run(a.world,a.out,a.apply)
