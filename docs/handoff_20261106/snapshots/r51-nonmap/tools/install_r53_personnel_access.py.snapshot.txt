"""Install the reviewed finite lift proposal into the sole R53 repair copy.

Exact block/NBT preconditions and native group state are checked under one
world lock. All geometry and metadata changes have an inverse. No actors,
players, missions or transport databases are edited, and native acceptance is
recorded separately from static installation readiness.
"""
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import io
import json
import msvcrt
import nbtlib
import regional_voxels as vox
from query_blocks import iter_block_entities
from apply_s20_approved_semantic_repairs import atomic_replace


def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',required=True,type=Path)
    ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    base=args.base.resolve();world=base/'CANDIDATE';proposal=base/'personnel-access-proposal';out=base/'personnel-access-install'
    assert world.resolve().parent==base and world.name=='CANDIDATE'
    review=json.loads((proposal/'REVIEW.json').read_text('utf8'));audit=json.loads((proposal/'OFFLINE_AUDIT.json').read_text('utf8'))
    assert not review['holds']
    for key in ('walk_failures','whole_hall_failures','low_motion_core_new_solid_overlaps','actors_in_new_solid','unknown_shapes'):
        assert not audit[key],('Offline gate not passed',key)
    delta=json.loads(gzip.decompress((proposal/'EXACT_BLOCK_PROPOSAL.json.gz').read_bytes()))
    device_rows=json.loads((proposal/'DEVICE_PROPOSAL.json').read_text('utf8'))
    native=json.loads((proposal/'NATIVE_GROUP_PROPOSAL.json').read_text('utf8'))
    old_manifest=json.loads((proposal/'personnel_lifts_BEFORE.json').read_text('utf8'))
    manifest=json.loads((proposal/'personnel_lifts_PROPOSAL.json').read_text('utf8'))
    assert not manifest['ready'] and manifest['epoch']==old_manifest['epoch']
    # The existing accepted command-room core and original stair footprints
    # are outside this authored edit, not approximated by centre-line checks.
    for row in delta:
        x,y,z=row['pos']
        assert not(6<=x<=52 and -538<=y<=-481 and 262<=z<=365),'Accepted command-room core changed'
        assert not(64<=x<=69 and -560<=y<=-450 and 360<=z<=369),'Original folding stair zone changed'
        assert not('smooth_quartz_stairs[' in row['before']),'Original quartz stair changed'
    vox.WORLD=world;vox.DIM='projectseele:geofront';vox.OUT=out
    painter=vox.Painter(vertical_bounds=(-1344,320))
    rows=sorted(delta,key=lambda r:(r['pos'][1],r['pos'][2],r['pos'][0]));run=[]
    def flush():
        if not run:return
        a,z=run[0],run[-1];painter.exact((*a['pos'],*z['pos']),a['before'],a['after'],a['owner']);run.clear()
    for row in rows:
        if run:
            last=run[-1]
            if row['pos'][0]!=last['pos'][0]+1 or row['pos'][1:]!=last['pos'][1:] or any(row[k]!=last[k] for k in ('before','after','owner')):flush()
        run.append(row)
    flush()
    changes={tuple(r['pos']):r for r in delta}
    for row in device_rows:
        p=tuple(row['pos']);assert p in changes,'A same-state device needs explicit NBT-only preconditions'
        painter.block_entities[p]=nbtlib.parse_nbt(row['after_nbt'])
    painter.meta.update(source='Original R53 CANDIDATE; measured two-lift and access reconstruction',
        accepted_core_and_stairs_preserved=True,native_progress_preserved=True,
        native_testing_pending=True,art_and_wayfinding_pending=True)
    out.mkdir(exist_ok=True);assert not(out/'INSTALLED.json').exists(),'Already installed; inspect the receipt instead of replaying'
    stage='original_two_lifts_and_personnel_access/attempt_02'
    assert not list((out/stage).glob('applied_*')),'This attempt already ran; inspect its rollback or completion'
    from information_fixture_guard_r44 import retained_faces
    for faces in retained_faces(painter,world,vox.DIM).values():
        for point,owner in faces.items():
            if point in changes:
                row=changes[point]
                assert row['after'].split('[')[0] in {'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'},('Retained information face',point,owner)
    painter.save_plan(stage)
    if not args.apply:
        print('Exact installation prepared; world not written');return
    paths=[world/'dimensions/projectseele/geofront/data/capabilities.dat',world/'personnel_lifts_r52.json',world/'ROOT_ASSEMBLY_BUNDLE.json',
           world/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat']
    lock=(world/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    before={};geometry_installed=False
    try:
        before={p:p.read_bytes() for p in paths}
        assert json.loads(before[paths[1]])==old_manifest,'Personnel metadata changed after review'
        caps=nbtlib.load(paths[0]);groups=caps['data']['movingelevators:elevator_groups'];unrelated=copy.deepcopy(groups)
        for row in native:
            source,target=row['source_key'],row['target_key']
            assert source in groups and groups[source].snbt()==row['source_nbt'] and target not in groups
            groups[target]=nbtlib.parse_nbt(row['target_nbt']);del groups[source]
        for key,value in unrelated.items():
            if key not in {r['source_key'] for r in native}:assert groups[key]==value
        # Check exact source/destination NBT, including all car controls.
        positions=[tuple(r['pos']) for r in delta]
        positions += [tuple(r['pos']) for r in device_rows]
        lo=tuple(min(p[k] for p in positions) for k in range(3));hi=tuple(max(p[k] for p in positions) for k in range(3))
        current=dict(iter_block_entities(world,vox.DIM,lo,hi))
        for row in delta:
            p=tuple(row['pos'])
            assert (current[p].snbt() if p in current else None)==row['before_nbt'],('Source NBT changed',p)
        for row in device_rows:
            p=tuple(row['pos']);assert (current[p].snbt() if p in current else None)==row['before_nbt'],('Destination NBT changed',p)
        for p,raw in before.items():(out/('before_'+p.name)).write_bytes(raw)
        # Ready means the static native installation can be read by runtime
        # guards. It is not a gameplay or art-acceptance completion flag.
        manifest['ready']=True;manifest_bytes=encoded(manifest)
        bundle=json.loads(before[paths[2]]);assert bundle['personnel_lifts']['file']=='personnel_lifts_r52.json'
        bundle['personnel_lifts']['sha256']=hashlib.sha256(manifest_bytes).hexdigest()
        stream=io.BytesIO();caps.write(stream);caps_bytes=gzip.compress(stream.getvalue(),mtime=0)
        from rebind_r53_personnel_installation import rebind
        runtime_path,runtime_bytes,_=rebind(world,before[paths[2]],encoded(bundle));assert runtime_path==paths[3]
        painter.apply(stage,session_lock=lock);geometry_installed=True
        pending={paths[0]:caps_bytes,paths[1]:manifest_bytes,paths[2]:encoded(bundle),paths[3]:runtime_bytes}
        for p,raw in pending.items():atomic_replace(p,raw)
        for p,raw in pending.items():assert p.read_bytes()==raw,'Metadata readback differs'
        checked=nbtlib.load(paths[0])['data']['movingelevators:elevator_groups']
        for row in native:assert checked[row['target_key']].snbt()==row['target_nbt'] and row['source_key'] not in checked
        (out/'INSTALLED.json').write_bytes(encoded(dict(world=str(world),static_installed=True,
            native_testing_pending=True,changed_cells=len(delta),native_groups=2,
            actors_players_missions_transport_progress_written=False,
            moving_cage_and_stationary_car_preserved=True,accepted_core_stairs_preserved=True,
            navigation_rebuild_pending=True)))
        print('Installed into CANDIDATE; exact blocks, full device NBT and native motion state read back. Native gameplay checks pending.')
    except BaseException:
        if geometry_installed:
            receipts=list((out/stage).glob('applied_*'));assert len(receipts)==1
            region=world/'dimensions/projectseele/geofront/region'
            for p in (receipts[0]/'before').glob('r.*.mca'):atomic_replace(region/p.name,p.read_bytes())
        for p,raw in before.items():atomic_replace(p,raw)
        raise
    finally:lock.close()


if __name__=='__main__':main()
