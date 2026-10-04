"""Root-only fresh v5 composition, with exact retired/migrated BE preimages.

Dry-run writes reports only. --apply creates one new candidate from immutable
v4_01; it never opens a QA save or takes a global Java/process guard.
The sealed core is the existing composer plus two small admission hooks.
"""
from __future__ import annotations
import argparse,copy,hashlib,importlib.util,json,os,sqlite3,sys
from contextlib import contextmanager
from pathlib import Path
sys.dont_write_bytecode=True
import nbtlib
from review_exported_be_validity_r45 import validate,classification,state_key

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r45'
OWN=ART/'pyramid_components_sol_v1/v5_combined_entry_v2'
CATALOG=OWN/'catalog.json'
SOURCE=ART/'composition_candidates/R45_source_candidate_20261003_v4_01/world'
SCHEMA='projectseele.r45.offline-composition.v5-source1736'
IDS={'registered_stairs243','middle_waiting354','retired_fixture_be8','route_sign_be1','device_physical25'}
FILES={'spatial_contract_r21.json','.projectseele_command_sliding_doors_r01.json'}
IDENTITY='dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text('utf8'))
def load_core(catalog):
    entry=catalog['core'];p=ROOT/entry['path']
    if p.resolve()!=OWN/'core/compose_v5_core.py' or sha(p)!=entry['sha256']:raise RuntimeError('Frozen composer core changed')
    spec=importlib.util.spec_from_file_location('r45_v5_frozen_core',p);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    core.ROOT=ROOT;core.SCHEMA=SCHEMA;core.ALLOWED_IDS=IDS;core.ALLOWED_DERIVED_TARGETS=FILES
    class Policy(core.Policy):
        def __init__(self):
            super().__init__(ROOT);self.source=SOURCE;self.reports=OWN/'runs'
    core.Policy=Policy;core.check_source=check_source
    core.validate_cell_contract=validate_cell_contract
    core.validate_projected_chunk=validate_projected_chunk
    return core

def inventory(world):return {p.relative_to(world).as_posix():sha(p) for p in sorted(world.rglob('*')) if p.is_file()}
def check_source(policy,catalog):
    baseline=read(policy.input(catalog['baseline']))
    if Path(baseline['source_world']).resolve()!=SOURCE.resolve() or policy.source.resolve()!=SOURCE.resolve():raise RuntimeError('Only immutable v4_01 is admitted')
    files={r['relative']:r['sha256'] for r in baseline['files']}
    if len(files)!=1736 or len(baseline['files'])!=1736 or sum((SOURCE/p).stat().st_size for p in files)!=520513536:raise RuntimeError('Wrong full1736 baseline')
    if inventory(SOURCE)!=files:raise RuntimeError('Full immutable source inventory/hash changed')
    level=nbtlib.load(SOURCE/'level.dat')['Data'];uid=nbtlib.load(SOURCE/IDENTITY)['data']['WorldUUID']
    if int(level['WorldGenSettings']['seed'])!=catalog['seed'] or str(uid)!=catalog['world_uuid']:raise RuntimeError('Source UUID/seed drift')
    return files

def contract_context(policy,catalog):
    # All resources are checked by bytes; there is no textual-source acceptance.
    traits=read(policy.input(catalog['native_state_contract']))
    export=read(policy.input(catalog['native_be_valid_blocks']));types=validate(export)
    probes={}
    for row in export.get('exact_state_probes',[]):
        if row.get('complete'):
            key=row['be_id'],state_key(row['state'])
            if key in probes and probes[key]!=row['is_valid']:raise RuntimeError('Conflicting exact native BE probe')
            probes[key]=row['is_valid']
    codec=load_core(catalog).load_codec(policy,catalog)
    repairs={}
    for row in read(policy.input(catalog['reviewed_be_repairs'])):
        key=tuple(row['pos'])
        if key in repairs:raise RuntimeError('Duplicate reviewed repair coordinate')
        repairs[key]=codec.cell(row,catalog['dimension'])
    if len(repairs)!=9:raise RuntimeError('Only frozen eight removals and one migration are admitted')
    context=traits,types,probes,repairs,codec
    validate_replacements(SOURCE,policy,catalog,context)
    return context

def validate_replacements(world,policy,catalog,context):
    _,types,probes,_,codec=context;records=read(policy.input(catalog['replacement_BE8']))
    if len(records)!=8 or len({tuple(r['position'])for r in records})!=8:raise RuntimeError('Eight complete actual replacement fixture records required')
    regions={}
    for record in records:
        x,y,z=record['position'];key=x//512,z//512
        if key not in regions:regions[key]=codec.read_region(codec.q.dimension_dir(world,catalog['dimension'])/'region'/f'r.{key[0]}.{key[1]}.mca')[1]
        root=codec.parse_chunk(regions[key][((x//16)&31)+((z//16)&31)*32]);sec=codec.measured_section(root,y//16);off=((y&15)<<8)|((z&15)<<4)|(x&15)
        actual='minecraft:air'if sec is None else sec[0][int(sec[1][off])]
        if actual!=record['state'] or codec.block_tags(root).get((x,y,z))!=nbtlib.parse_nbt(record['full_nbt']):raise RuntimeError('Corresponding replacement fixture full state/NBT differs '+str((x,y,z)))
        if not classification(record,types,probes).startswith('VALID_RUNTIME_'):raise RuntimeError('Actual replacement BE relation unresolved')

def validate_cell_contract(policy,catalog,component,row,b,a,bn,an):
    # The frozen nine FULL delta rows are the only invalid-before exceptions.
    # Neither a component name nor an owner prefix grants a generic BE waiver.
    context=getattr(policy,'v5_contract',None)
    if context is None:context=policy.v5_contract=contract_context(policy,catalog)
    traits,types,probes,repairs,codec=context
    if b not in traits or a not in traits:raise RuntimeError('Missing actual full-state trait')
    is_repair=component['id'] in {'retired_fixture_be8','route_sign_be1'}
    if is_repair:
        if repairs.get(tuple(row['pos']))!=codec.cell(row,catalog['dimension']):raise RuntimeError('Repair differs from frozen complete preimage/inverse/owner')
        if b!=a or bn is None:raise RuntimeError('Reviewed BE repair must preserve actual block state and original full tag')
        tag=nbtlib.parse_nbt(bn)
        if classification({'state':b,'be_id':str(tag['id'])},types,probes)!='RUNTIME_TYPE_MISMATCH':raise RuntimeError('Before relation is not the actual registry-proven mismatch')
        if component['id']=='retired_fixture_be8' and an is not None:raise RuntimeError('Retired fixture correction must remove only old tag')
        if component['id']=='route_sign_be1' and an is None:raise RuntimeError('Route sign migration must keep its real native BE')
    elif bool(traits[b]['has_block_entity'])!=(bn is not None):raise RuntimeError('Invalid before relation outside reviewed nine')
    if bool(traits[a]['has_block_entity'])!=(an is not None):raise RuntimeError('After full state/BE presence mismatch')
    if an is not None:
        tag=nbtlib.parse_nbt(an)
        if not classification({'state':a,'be_id':str(tag['id'])},types,probes).startswith('VALID_RUNTIME_'):raise RuntimeError('After BE registry relation not actually valid')

def validate_after_chunk(root,context,codec):
    _,types,probes,_,_=context
    for pos,tag in codec.block_tags(root).items():
        sec=codec.measured_section(root,pos[1]//16)
        off=((pos[1]&15)<<8)|((pos[2]&15)<<4)|(pos[0]&15)
        state='minecraft:air' if sec is None else sec[0][int(sec[1][off])]
        verdict=classification({'state':state,'be_id':str(tag['id'])},types,probes)
        if not verdict.startswith('VALID_RUNTIME_'):raise RuntimeError('After unrelated/full BE relation unresolved '+str(pos)+' '+verdict)

def validate_projected_chunk(policy,catalog,root,changes,states,codec):
    projected=copy.deepcopy(root)
    codec.mutate_chunk(projected,changes,states,True)
    validate_after_chunk(projected,policy.v5_contract,codec)

def verify_candidate(core,policy,catalog,destination,write_receipt=False):
    destination=destination.resolve()
    if destination.parent!=policy.candidates.resolve() or destination==SOURCE.parent:raise RuntimeError('Only named fresh composition candidate can be inspected')
    receipt=read(destination/'composition.json');world=destination/'world'
    if receipt['original_source']!=str(SOURCE) or set(receipt['selected_components'])!=IDS:raise RuntimeError('Incomplete/wrong v5 composition scope')
    original=check_source(policy,catalog);changed={r['target']:r for r in [*receipt['regions'],*receipt['files']]}
    actual=inventory(world)
    if set(actual)!=set(original):raise RuntimeError('Candidate file additions/removals outside exact original inventory')
    for name,digest in actual.items():
        expected=changed[name]['after_sha256'] if name in changed else original[name]
        if name!='session.lock' and digest!=expected:raise RuntimeError('Candidate full file drift '+name)
    context=contract_context(policy,catalog);codec=context[-1];validate_replacements(world,policy,catalog,context)
    staged=Path(receipt['report']).resolve()
    if staged.parent!=policy.reports.resolve():raise RuntimeError('Staged report outside frozen own runs directory')
    db=sqlite3.connect('file:'+str(staged/'cells.sqlite')+'?mode=ro',uri=True)
    expected={}
    for component in catalog['components']:
        for patch in component.get('patches',[]):
            for row in core.row_stream(policy.input(patch['forward'])):
                cell=codec.cell(row,catalog['dimension']);expected[(cell[2],cell[3],cell[4],cell[5])]=(*cell[6:],component['id'])
    observed={(cx,cz,sy,off):(b,a,bn,an,owner,component)for cx,cz,sy,off,b,a,bn,an,owner,component in db.execute('SELECT cx,cz,sy,off,b,a,bn,an,owner,component FROM cells')}
    if expected!=observed:db.close();raise RuntimeError('Staged coordinates/full state/NBT differ from sealed original inputs')
    all_states={v:i for i,(v,) in enumerate(db.execute('SELECT b AS s FROM cells UNION SELECT a FROM cells'))};reverse={v:k for k,v in all_states.items()}
    counts={'rows':0,'before_BE':0,'after_BE':0,'unrelated_BE_preserved':0,'touched_chunks':0}
    try:
        for region in receipt['regions']:
            inverse=destination/region['inverse_file'];target=world/region['target']
            if sha(inverse)!=region['before_sha256'] or sha(target)!=region['after_sha256']:raise RuntimeError('Before/after region epoch changed')
            old=codec.read_region(inverse)[1];new=codec.read_region(target)[1];rx,rz=map(int,Path(target).stem.split('.')[1:]);touched=set()
            for cx,cz in db.execute('SELECT DISTINCT cx,cz FROM cells WHERE rx=? AND rz=?',(rx,rz)):
                slot=(cx&31)+(cz&31)*32;touched.add(slot);changes=[(sy,off,all_states[b],all_states[a],bn,an) for sy,off,b,a,bn,an in db.execute('SELECT sy,off,b,a,bn,an FROM cells WHERE cx=? AND cz=? ORDER BY sy,off',(cx,cz))]
                before=codec.parse_chunk(old[slot]);after=codec.parse_chunk(new[slot]);codec.validate_chunk(before,changes,reverse);codec.validate_chunk(after,changes,reverse,after=True)
                if codec.chunk_guard_hash(before,changes,True)!=codec.chunk_guard_hash(after,changes,True):raise RuntimeError('Full unrelated chunk NBT changed')
                validate_after_chunk(after,context,codec)
                old_tags=codec.block_tags(before);new_tags=codec.block_tags(after);changed_pos={(cx*16+(off&15),sy*16+(off>>8),cz*16+((off>>4)&15)) for sy,off,*_ in changes}
                counts['before_BE']+=len(old_tags);counts['after_BE']+=len(new_tags);counts['unrelated_BE_preserved']+=sum(p not in changed_pos for p in old_tags);counts['touched_chunks']+=1;counts['rows']+=len(changes)
            if any(old[s]!=new[s] for s in range(1024) if s not in touched):raise RuntimeError('Untouched complete compressed chunk bytes changed')
    finally:db.close()
    if counts['rows']!=631 or counts['before_BE']-counts['after_BE']!=8:raise RuntimeError('Exact combined631 / eight-only record removal failed')
    report=dict(schema='projectseele.v5-exact-readback.v1',candidate=str(destination),world=str(world),catalog_sha256=sha(CATALOG),source1736_unchanged=True,full_after_inventory=actual,counts=counts,actual_replacement_fixtures8_full_state_NBT_preserved=True,static_files=list(sorted(FILES)),world_written_by_this_readback=False,installed_into_user_world=False,native_new_structure_pass=False,visual_accepted=False,old_lift90_24_implementation_inheritance_only=True)
    if write_receipt:core.durable(destination/'composition_v5_readback.json',report)
    else:
        frozen=read(destination/'composition_v5_readback.json')
        if frozen['full_after_inventory']!=actual or frozen['catalog_sha256']!=sha(CATALOG):raise RuntimeError('Candidate changed after actual root readback')
    return report

@contextmanager
def locked_world(world):
    # Existing lock only; it is not changed. No global Java guard is taken.
    with (world/'session.lock').open('r+b') as handle:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            try:yield
            finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:yield
            finally:fcntl.flock(handle,fcntl.LOCK_UN)

def rollback(core,policy,catalog,destination,apply):
    verified=verify_candidate(core,policy,catalog,destination)
    receipt=read(destination/'composition.json');world=destination/'world';restores=[]
    for row in [*receipt['regions'],*receipt['files']]:
        backup=destination/row['inverse_file']
        if sha(backup)!=row['before_sha256']:raise RuntimeError('Full inverse backup changed')
        restores.append((row['target'],backup))
    if apply:
        with locked_world(world):
            # The complete readback above rejects any world/gameplay progress.
            # Compare all non-lock files again while holding the existing lock.
            for name,digest in verified['full_after_inventory'].items():
                if name!='session.lock' and sha(world/name)!=digest:raise RuntimeError('World changed before rollback lock')
            codec=contract_context(policy,catalog)[-1]
            for name,backup in restores:codec.atomic_replace(world/name,backup.read_bytes())
        expected=check_source(policy,catalog);actual=inventory(world)
        if any(actual[n]!=s for n,s in expected.items() if n!='session.lock') or set(actual)!=set(expected):raise RuntimeError('Exact full source rollback readback failed')
        core.durable(destination/'rollback_actual.json',dict(restored=True,source_written=False,new_candidate_only=True,session_lock_preserved=True,old_source_invalid_BE_restored_for_exact_inverse=True,not_release=True))
    return dict(rollback_ready=True,applied=apply,targets=len(restores),world=str(world))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path);parser.add_argument('--report',type=Path)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--readback',action='store_true');parser.add_argument('--rollback',action='store_true')
    args=parser.parse_args();catalog=read(CATALOG)
    if CATALOG.with_suffix('.json.sha256').read_text('ascii').strip()!=sha(CATALOG):raise RuntimeError('Catalog seal changed')
    core=load_core(catalog);policy=core.Policy()
    for entry in [catalog['core'],catalog['baseline'],catalog['native_state_contract'],catalog['native_be_valid_blocks'],catalog['reviewed_be_repairs'],catalog['replacement_BE8'],*catalog['epochs']]:policy.input(entry)
    if args.readback or args.rollback:
        if args.candidate is None or args.report is not None or args.readback and args.rollback:parser.error('Readback/rollback requires exactly one candidate')
        if args.readback and args.apply:parser.error('Readback never writes worlds')
        result=rollback(core,policy,catalog,args.candidate.resolve(),args.apply) if args.rollback else verify_candidate(core,policy,catalog,args.candidate.resolve())
    else:
        if args.apply!=(args.candidate is not None):parser.error('--apply requires one explicitly NEW --candidate')
        import uuid
        report=args.report or policy.reports/('root_'+uuid.uuid4().hex[:12])
        result=core.run(CATALOG,policy,report,None,args.candidate if args.apply else None)
        if args.apply:result=verify_candidate(core,policy,catalog,args.candidate.resolve(),write_receipt=True)
    print(json.dumps({k:v for k,v in result.items() if k not in {'full_after_inventory','regions','components','file_operations'}},ensure_ascii=True,indent=2))
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (RuntimeError,ValueError,OSError) as exc:print('HOLD: '+str(exc),file=sys.stderr);raise SystemExit(2)
