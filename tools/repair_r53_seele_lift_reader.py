"""Turn the existing SEELE lift reader toward its existing landing aisle.

Keep its exact location, complete NBT and controller identity. Only the facing
in the world and the same installed manifest changes; runtime migration alters
only the installation bundle digest, never jobs, actors or lift progress.
"""
import argparse
import copy
import gzip
import hashlib
import json
import msvcrt
from pathlib import Path

from apply_s20_approved_semantic_repairs import atomic_replace
from query_blocks import read_box,iter_block_entities
from repair_r53_long_stair_guard import install as install_cells
from rebind_r53_personnel_installation import rebind

POS=(31,-456,316)
BEFORE='projectseele:nerv_access_reader[facing=north]'
AFTER='projectseele:nerv_access_reader[facing=west]'
LIFT='s23-commander-office-x28-z321-v1'
DIM='projectseele:geofront'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def revised_manifest(raw):
    doc=json.loads(raw);before=copy.deepcopy(doc)
    floor=next(f for lift in doc['lifts'] if lift['id']==LIFT for f in lift['floors'] if f['cabin']==[28,-457,321])
    call=next(c for c in floor['calls'] if tuple(c['position'])==POS)
    assert call['state']==BEFORE and call['facing']=='north'
    assert call['kind']=='seele_reader'
    call['state']=AFTER;call['facing']='west'
    restored=copy.deepcopy(doc)
    old=next(c for l in restored['lifts'] if l['id']==LIFT for f in l['floors'] if f['cabin']==[28,-457,321] for c in f['calls'] if tuple(c['position'])==POS)
    old['state']=BEFORE;old['facing']='north';assert restored==before
    return json.dumps(doc,ensure_ascii=False,separators=(',',':')).encode('utf8')


def plan(frozen, review, output):
    evidence=json.loads(review.read_text('utf8'))
    assert evidence['decision']=='turn_existing_seele_lift_reader_west' and tuple(evidence['pos'])==POS
    cells=read_box(frozen,DIM,(29,-458,314),(33,-454,318))
    tags=dict(iter_block_entities(frozen,DIM,POS,POS))
    assert cells[POS]==BEFORE and str(tags[POS]['id'])=='projectseele:nerv_access_reader'
    assert int(tags[POS]['Clearance'])==3 and not bool(tags[POS]['Linked'])
    assert cells[31,-456,315]=='minecraft:black_concrete','Original face is not blocked'
    assert cells[32,-456,316]=='minecraft:black_concrete','Existing fixed backing changed'
    assert cells[30,-458,316]=='projectseele:nerv_floor_panel'
    assert cells[30,-457,316]==cells[30,-456,316]=='minecraft:air'
    row=dict(pos=POS,before=BEFORE,after=AFTER,before_nbt=tags[POS].snbt(),after_nbt=tags[POS].snbt(),
        reason='existing_elevator_reader_faces_its_landing_instead_of_black_partition')
    output.mkdir(parents=True,exist_ok=False)
    for name,data in [('EXACT_DELTA.json.gz',[row]),('INVERSE_DELTA.json.gz',[dict(row,before=AFTER,after=BEFORE)]),('POSITIVE_EDIT_MASK.json.gz',[POS])]:
        (output/name).write_bytes(gzip.compress(json.dumps(data).encode(),mtime=0))
    raw=(frozen/'personnel_lifts_r52.json').read_bytes();new=revised_manifest(raw)
    (output/'manifest-before.json').write_bytes(raw);(output/'manifest-after.json').write_bytes(new)
    (output/'PLAN.json').write_text(json.dumps(dict(changed_cells=1,position_unchanged=True,complete_nbt_unchanged=True,
        controller_and_clearance_unchanged=True,review_sha256=sha(review.read_bytes()),manifest_before_sha256=sha(raw),manifest_after_sha256=sha(new)),indent=2),'utf8')


def install(world, output):
    if (output/'CONFIG_INSTALLED.json').exists():raise ValueError('Already installed; inspect receipt')
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        manifest=world/'personnel_lifts_r52.json';bundle=world/'ROOT_ASSEMBLY_BUNDLE.json'
        before=manifest.read_bytes();after=(output/'manifest-after.json').read_bytes()
        assert before==(output/'manifest-before.json').read_bytes()
        old_bundle=bundle.read_bytes();doc=json.loads(old_bundle)
        assert doc['personnel_lifts']['file']=='personnel_lifts_r52.json'
        assert doc['personnel_lifts']['sha256']==sha(before)
        doc['personnel_lifts']['sha256']=sha(after)
        new_bundle=json.dumps(doc,ensure_ascii=False,indent=2).encode('utf8')
        runtime,raw,changed=rebind(world,old_bundle,new_bundle)
        for name,data in [('bundle-before.json',old_bundle),('bundle-after.json',new_bundle),('runtime-before.dat',runtime.read_bytes()),('runtime-after.dat',raw)]:
            (output/name).write_bytes(data)
    install_cells(world,output)
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        assert manifest.read_bytes()==before and bundle.read_bytes()==old_bundle
        assert runtime.read_bytes()==(output/'runtime-before.dat').read_bytes()
        atomic_replace(manifest,after);atomic_replace(bundle,new_bundle);atomic_replace(runtime,raw)
        assert manifest.read_bytes()==after and bundle.read_bytes()==new_bundle and runtime.read_bytes()==raw
    (output/'CONFIG_INSTALLED.json').write_text(json.dumps(dict(changed_runtime_configuration_paths=changed,
        manifest_sha256=sha(after),bundle_sha256=sha(new_bundle),jobs_actors_and_lift_progress_unchanged=True),indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frozen',type=Path);p.add_argument('--review',type=Path)
    p.add_argument('--world',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--install',action='store_true')
    a=p.parse_args();install(a.world,a.output) if a.install else plan(a.frozen,a.review,a.output)
