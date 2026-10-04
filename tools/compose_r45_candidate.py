"""Offline R45 candidate composition. Never targets an existing world.

Default dry-run stages exact chains and checks the immutable original backup.
Only --apply --candidate artifacts/rebuild_r45/composition_candidates/<NEW>
copies that backup and mutates its new world child. No QA region/progress copy,
native execution, runtime promotion, UN reset, package, or implicit NBT defaults.
"""
from __future__ import annotations
import argparse,copy,gzip,hashlib,importlib.util,itertools,json,os,shutil,sqlite3,sys,uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import nbtlib

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='projectseele.r45.offline-composition.v1'
ART=Path('artifacts/rebuild_r45')
DEFAULT_CATALOG=ART/'integration_sol_followup/offline_composer_v1/catalog.json'
CODEC_REL=ART/'terrain_global_agent/stream_exact_install_r45_v2.py'
ALLOWED_IDS={'landfield_v4','lake_outlet_v5','school_campus_v2','hakone_station_v5','apartment_clinic_components_v1','school_tail_v2','science_sink_tail_v1','science_sink_wall_v2','station_native_sign_nbt_v1','school_derived','station_derived','pool_and_nav_v1','tv_shells_v1','ordinary_metal_doors_v1','airport_control_tower_signs_v1','bookshop_sign_v1','clinic_exam_wash_v1','dead_sea_component_v2','city_topology_v2','canopy_v2','low_ecology_v2'}
ALLOWED_DERIVED_TARGETS={'quality_walk_cases.json','r45_school_hakone_components.json','r45_school_hakone_navigation.json','.projectseele_tv_lifts_r45.json','dimensions/projectseele/geofront/data/projectseele_dead_sea_chamber_r45.dat'}

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(4*1024*1024),b''):digest.update(part)
    return digest.hexdigest()

def read(path):return json.loads(Path(path).read_text('utf8'))

def durable(path,value):
    path=Path(path);temp=path.with_name(path.name+'.partial')
    with temp.open('w',encoding='utf8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)

class Hold(RuntimeError):pass

@contextmanager
def exclusive_new_world(world):
    # New candidate only: the original session.lock is never opened for writing.
    with (world/'session.lock').open('x+b') as handle:
        handle.write('☃'.encode('utf8'));handle.flush();os.fsync(handle.fileno());handle.seek(0)
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

class Policy:
    def __init__(self,repo=ROOT):
        self.repo=Path(repo).resolve();self.art=self.repo/ART
        self.source=self.art/'source_world_backup'
        self.candidates=self.art/'composition_candidates'
        self.reports=self.art/'integration_sol_followup/offline_composer_v1/runs'

    def new_candidate(self,path):
        p=Path(path).resolve()
        if p.parent!=self.candidates.resolve() or not p.name or p.name in {'.','..'}:
            raise Hold('Candidate must be one NEW direct child of '+str(self.candidates))
        if p.exists():raise Hold('Existing candidate/world is preserved: '+str(p))
        if p.is_relative_to(self.source.resolve()) or p.is_relative_to((self.repo/'run/saves').resolve()):raise Hold('Protected world target')
        return p

    def new_report(self,path):
        p=Path(path).resolve()
        if p.parent!=self.reports.resolve() or p.exists():raise Hold('Report must be a NEW direct child of '+str(self.reports))
        return p

    def input(self,entry):
        p=Path(entry['path']);p=p if p.is_absolute() else self.repo/p;p=p.resolve()
        if not p.is_relative_to(self.repo) or not p.is_file() or sha(p)!=entry['sha256']:
            raise Hold('Frozen input SHA/path mismatch: '+str(p))
        return p

    @staticmethod
    def relative(value):
        p=Path(value)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.suffix=='.mca' or any(x in {'region','entities','playerdata','advancements','stats','mtr','poi'} for x in p.parts) or p.name in {'level.dat','level.dat_old','uuid.dat','session.lock'}:
            raise Hold('Forbidden progress/unsafe derived target '+str(p))
        return p

def load_codec(policy,catalog):
    path=policy.input(catalog['codec'])
    if path!=(policy.repo/CODEC_REL).resolve():raise Hold('Unrecognized shared codec')
    sys.path.insert(0,str(policy.repo/'tools'))
    spec=importlib.util.spec_from_file_location('r45_exact_composition_codec',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def check_source(policy,catalog):
    baseline_path=policy.input(catalog['baseline']);baseline=read(baseline_path)
    if Path(baseline['backup']).resolve()!=policy.source.resolve():raise Hold('Only immutable source_world_backup is a composition base')
    files=baseline['files'];actual={p.relative_to(policy.source).as_posix():p for p in policy.source.rglob('*') if p.is_file()}
    if set(files)!=set(actual):raise Hold('Source file inventory differs from frozen baseline')
    for name,digest in files.items():
        p=actual[name]
        if p.resolve()!=policy.source.resolve()/Path(name) or sha(p)!=digest:raise Hold('Original full source file changed: '+name)
    level=nbtlib.load(policy.source/'level.dat')['Data']
    data=nbtlib.load(policy.source/catalog['identity_file'])['data']
    if int(level['WorldGenSettings']['seed'])!=catalog['seed'] or str(data['WorldUUID'])!=catalog['world_uuid']:
        raise Hold('Original world UUID/seed mismatch')
    return files

def selected_components(catalog,requested):
    items={r['id']:r for r in catalog['components']}
    if len(items)!=len(catalog['components']) or set(items)-ALLOWED_IDS:raise Hold('Duplicate/unclassified component ID')
    selected=set(catalog['default_components'] if requested is None else requested)
    if selected-set(items):raise Hold('Unknown requested components: '+str(selected-set(items)))
    while True:
        old=set(selected)
        for key in old:selected.update(items[key].get('depends_on',[]))
        if selected-set(items):raise Hold('Unknown dependency')
        if old==selected:break
    held=[dict(id=k,reason=items[k]['deferred_reason']) for k in selected if items[k].get('deferred_reason')]
    if held:raise Hold('Explicitly deferred components cannot be installed: '+json.dumps(held))
    result=[r for r in catalog['components'] if r['id'] in selected]
    seen=set()
    for row in result:
        if set(row.get('depends_on',[]))-seen:raise Hold('Dependency order error: '+row['id'])
        if row.get('classification')!='CLASSIFIED_CANDIDATE_NOT_NATIVE':raise Hold('Component lacks candidate-only classification')
        seen.add(row['id'])
    return result

def row_stream(path):
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',encoding='utf8') as stream:
        for line in stream:
            if line.strip():yield json.loads(line)

def stage_cells(policy,catalog,components,report,codec,db):
    traits=read(policy.input(catalog['native_state_contract']))
    db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA temp_store=FILE')
    db.executescript('CREATE TABLE cells(rx,rz,cx,cz,sy,off,b TEXT,a TEXT,bn TEXT,an TEXT,owner TEXT,component TEXT,PRIMARY KEY(cx,cz,sy,off)) WITHOUT ROWID; CREATE INDEX region_cells ON cells(rx,rz,cx,cz,sy,off);')
    conflicts=[];stats=[]
    for component in components:
        count=chains=0;owners=Counter()
        for patch in component.get('patches',[]):
            f=policy.input(patch['forward']);i=policy.input(patch['inverse']);n=0
            for n,(r,reverse) in enumerate(itertools.zip_longest(row_stream(f),row_stream(i)),1):
                if r is None or reverse is None or not codec.inverse_pair(r,reverse):raise Hold('Full inverse mismatch '+component['id']+' row '+str(n))
                rx,rz,cx,cz,sy,off,b,a,bn,an,owner=codec.cell(r,catalog['dimension'])
                if not owner or owner=='human' or not any(owner.startswith(prefix) for prefix in component['owner_prefixes']):raise Hold('Unknown/HOLD/human owner '+owner)
                for state,tag in [(b,bn),(a,an)]:
                    if state not in traits or bool(traits[state]['has_block_entity'])!=(tag is not None):raise Hold('Missing exact native registry/complete BE contract: '+state)
                key=cx,cz,sy,off;old=db.execute('SELECT a,an FROM cells WHERE cx=? AND cz=? AND sy=? AND off=?',key).fetchone()
                if old is None:db.execute('INSERT INTO cells VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(rx,rz,cx,cz,sy,off,b,a,bn,an,owner,component['id']))
                elif old==(b,bn):
                    db.execute('UPDATE cells SET a=?,an=?,owner=?,component=? WHERE cx=? AND cz=? AND sy=? AND off=?',(a,an,owner,component['id'],*key));chains+=1
                else:
                    if len(conflicts)<100:conflicts.append(dict(component=component['id'],owner=owner,pos=r['pos'],prior_after=list(old),next_before=[b,bn],reason='NONCONTIGUOUS_FULL_STATE_NBT_CHAIN'))
                count+=1;owners[owner]+=1
                if count%20000==0:db.commit()
            if n!=patch['rows']:raise Hold('Frozen row count differs: '+str(f))
        db.commit();stats.append(dict(id=component['id'],input_rows=count,exact_overlap_chains=chains,whole_owner_objects=len(owners),candidate_only=True))
    durable(report/'conflicts.json',dict(conflicts=conflicts,all_whole_components_held=bool(conflicts)))
    if conflicts:db.close();raise Hold('Coordinate chain conflicts; no source or candidate writes')
    states={v:i for i,(v,) in enumerate(db.execute('SELECT b AS s FROM cells UNION SELECT a FROM cells'))};reverse={v:k for k,v in states.items()}
    regions=[];errors=[]
    # Central query_blocks-backed codec performs exact complete state/NBT reads.
    for rx,rz in db.execute('SELECT DISTINCT rx,rz FROM cells ORDER BY rx,rz'):
        path=codec.q.dimension_dir(policy.source,catalog['dimension'])/'region'/f'r.{rx}.{rz}.mca'
        if not path.is_file():errors.append(dict(region=[rx,rz],reason='MISSING_OR_UNKNOWN_REGION'));continue
        before=sha(path);stamps,blobs=codec.read_region(path)
        for cx,cz in db.execute('SELECT DISTINCT cx,cz FROM cells WHERE rx=? AND rz=?',(rx,rz)):
            slot=(cx&31)+(cz&31)*32;blob=blobs[slot]
            if blob is None:errors.append(dict(chunk=[cx,cz],reason='MISSING_FULL_CHUNK'));continue
            changes=[(sy,off,states[b],states[a],bn,an) for sy,off,b,a,bn,an in db.execute('SELECT sy,off,b,a,bn,an FROM cells WHERE cx=? AND cz=? ORDER BY sy,off',(cx,cz))]
            root=codec.parse_chunk(blob)
            try:
                required_sy={r[0] for r in changes};sections={int(r['Y']) for r in root.get('sections',[])}
                if required_sy-sections:raise RuntimeError('Missing complete source section/biome NBT; do not invent it')
                codec.validate_chunk(root,changes,reverse)
            except RuntimeError as exc:
                if len(errors)<100:
                    actual_tags=codec.block_tags(root)
                    errors.append(dict(chunk=[cx,cz],reason=str(exc),whole_owners=sorted({r[0] for r in db.execute('SELECT DISTINCT owner FROM cells WHERE cx=? AND cz=?',(cx,cz))}),complete_actual_BE=[dict(pos=list(q),full_snbt=t.snbt()) for q,t in actual_tags.items()],expected_rows_sample=[dict(sy=sy,offset=off,before=reverse[b],after=reverse[a],before_full_nbt=bn,after_full_nbt=an) for sy,off,b,a,bn,an in changes[:40]]))
        if sha(path)!=before:raise Hold('Source changed during preflight')
        regions.append(dict(region=[rx,rz],source_path=str(path),source_sha256=before,cells=db.execute('SELECT count(*) FROM cells WHERE rx=? AND rz=?',(rx,rz)).fetchone()[0]))
    durable(report/'conflicts.json',dict(conflicts=errors,all_whole_components_held=bool(errors),preflight='SOURCE_EXACT_BEFORE_ONLY; no already-after guessing'))
    if errors:db.close();raise Hold('Original source full before/NBT conflicts; no candidate created')
    with gzip.open(report/'inverse.jsonl.gz','wt',encoding='utf8') as stream:
        for cx,cz,sy,off,b,a,bn,an,owner,component in db.execute('SELECT cx,cz,sy,off,b,a,bn,an,owner,component FROM cells ORDER BY cx,cz,sy,off'):
            p=[cx*16+(off&15),sy*16+(off>>8),cz*16+((off>>4)&15)]
            stream.write(json.dumps(dict(pos=p,before=a,after=b,before_nbt=an,after_nbt=bn,owner=owner,component=component),ensure_ascii=False,separators=(',',':'))+'\n')
    with (report/'inverse.jsonl.gz').open('r+b') as stream:os.fsync(stream.fileno())
    return db,states,reverse,regions,stats

def stage_files(policy,catalog,components,source_files):
    allowed=set(catalog['allowed_file_targets']);chain={}
    for component in components:
        for op in component.get('files',[]):
            relative=policy.relative(op['target']).as_posix()
            if relative not in allowed or relative not in ALLOWED_DERIVED_TARGETS:raise Hold('Derived target not in classified frozen whitelist '+relative)
            if '/data/' in relative and op.get('kind')!='NEW_OWNER_MARKER':raise Hold('Existing SavedData/archives need their own explicit WAL migration; no generic overwrite')
            p=policy.input(op['after']);actual=chain[relative]['after_sha256'] if relative in chain else source_files.get(relative)
            if not p.is_relative_to(policy.art) or p.is_relative_to(policy.source.resolve()):raise Hold('Derived payload must be a classified artifact, never a QA/source progress-file copy')
            if op.get('kind')=='NEW_OWNER_MARKER' and (op['before_sha256'] is not None or actual is not None):raise Hold('New owner marker must be absent, never overwrite existing SavedData')
            if actual!=op['before_sha256']:raise Hold('Derived full before chain mismatch '+relative)
            if relative not in chain:chain[relative]=dict(target=relative,before_sha256=actual)
            chain[relative].update(after_sha256=op['after']['sha256'],payload=str(p),component=component['id'],kind=op['kind'])
    return list(chain.values())

def apply_candidate(policy,catalog,source_files,components,db,states,reverse,regions,file_ops,report,destination,codec):
    destination=policy.new_candidate(destination);destination.parent.mkdir(parents=True,exist_ok=True);destination.mkdir()
    world=destination/'world';world.mkdir();journal=destination/'inverse';journal.mkdir();receipt=dict(status='INCOMPLETE_CANDIDATE_NOT_NATIVE_NOT_RELEASE',world=str(world),original_source=str(policy.source),world_uuid=catalog['world_uuid'],seed=catalog['seed'],regions=[],files=[],source_written=False,new_candidate_written=True,native_pass=False,art_pass=False,UN_initialized=False,runtime_promoted=False)
    durable(destination/'composition.json',receipt)
    lock=exclusive_new_world(world);locked=False
    try:
        lock.__enter__();locked=True
        # Source bytes only. No review-world directory or region copy is possible.
        for relative,digest in source_files.items():
            if Path(relative).name=='session.lock':continue
            source=policy.source/relative;target=world/relative;target.parent.mkdir(parents=True,exist_ok=True)
            with source.open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,4*1024*1024);dst.flush();os.fsync(dst.fileno())
            if sha(source)!=digest or sha(target)!=digest:raise Hold('Source/copy epoch drift '+relative)
        region_targets=set()
        for record in regions:
            rx,rz=record['region'];relative=Path(record['source_path']).relative_to(policy.source);target=world/relative;region_targets.add(relative.as_posix());inverse=journal/relative;inverse.parent.mkdir(parents=True,exist_ok=True)
            if sha(target)!=record['source_sha256']:raise Hold('New candidate before changed')
            codec.durable_file_copy(target,inverse,record['source_sha256']);stamps,blobs=codec.read_region(inverse);slots=set();guards=[]
            for cx,cz in db.execute('SELECT DISTINCT cx,cz FROM cells WHERE rx=? AND rz=? ORDER BY cx,cz',(rx,rz)):
                slot=(cx&31)+(cz&31)*32;changes=[(sy,off,states[b],states[a],bn,an) for sy,off,b,a,bn,an in db.execute('SELECT sy,off,b,a,bn,an FROM cells WHERE cx=? AND cz=? ORDER BY sy,off',(cx,cz))]
                root=codec.parse_chunk(blobs[slot]);guard=codec.mutate_chunk(root,changes,reverse,True);blobs[slot]=codec.chunk_blob(root);slots.add(slot);guards.append((slot,changes,guard,True))
            partial=target.with_name(target.name+'.composition-partial');codec.atomic_replace(partial,codec.build_region(stamps,blobs));codec.preserve_region(inverse,partial,slots,guards)
            serialized=codec.read_region(partial)[1]
            for slot,changes,_,_ in guards:codec.validate_chunk(codec.parse_chunk(serialized[slot]),changes,reverse,after=True)
            after_sha=sha(partial);entry=dict(target=relative.as_posix(),before_sha256=record['source_sha256'],after_sha256=after_sha,inverse_file=str(inverse.relative_to(destination)),cells=record['cells'],derived_relight=True)
            receipt['regions'].append(entry);durable(destination/'composition.json',receipt);os.replace(partial,target)
            if sha(target)!=after_sha:raise Hold('Actual committed region readback differs')
        file_targets=set()
        for op in file_ops:
            relative=op['target'];file_targets.add(relative);target=world/relative;actual=sha(target) if target.exists() else None
            if actual!=op['before_sha256']:raise Hold('Candidate derived before changed '+relative)
            backup=None
            if target.exists():
                backup=journal/relative;backup.parent.mkdir(parents=True,exist_ok=True);codec.durable_file_copy(target,backup,actual)
            target.parent.mkdir(parents=True,exist_ok=True);partial=target.with_name(target.name+'.composition-partial');codec.durable_file_copy(Path(op['payload']),partial,op['after_sha256'])
            entry=dict(target=relative,before_sha256=actual,after_sha256=op['after_sha256'],inverse_file=str(backup.relative_to(destination)) if backup else None,inverse_remove_only_new_hash=backup is None)
            receipt['files'].append(entry);durable(destination/'composition.json',receipt);os.replace(partial,target)
            if sha(target)!=op['after_sha256']:raise Hold('Actual derived/marker readback differs '+relative)
        preserved=[]
        for relative,digest in source_files.items():
            if Path(relative).name=='session.lock' or relative in region_targets or relative in file_targets:continue
            if sha(world/relative)!=digest:raise Hold('Unlisted original progress/file mutated '+relative)
            preserved.append(relative)
        check_source(policy,catalog)
        for r in [*receipt['regions'],*receipt['files']]:
            if sha(world/r['target'])!=r['after_sha256']:raise Hold('Written whitelist bytes changed before completion '+r['target'])
        receipt.update(status='OFFLINE_PARTIAL_CANDIDATE_NOT_NATIVE_NOT_RELEASE',original_unlisted_files_byte_preserved=len(preserved),selected_components=[r['id'] for r in components],omitted_or_deferred_components=[r['id'] for r in catalog['components'] if r not in components],report=str(report),full_inverse_jsonl=str(report/'inverse.jsonl.gz'))
        durable(destination/'composition.json',receipt);return receipt
    except BaseException as exc:
        receipt.update(status='FAILED_CANDIDATE_PRESERVED_NOT_RELEASE',error=str(exc));durable(destination/'composition.json',receipt);raise
    finally:
        if locked:lock.__exit__(None,None,None)

def run(catalog_path,policy,report,requested=None,destination=None):
    catalog_path=Path(catalog_path)
    seal=catalog_path.with_suffix(catalog_path.suffix+'.sha256')
    if not seal.is_file() or seal.read_text('ascii').strip()!=sha(catalog_path):raise Hold('Frozen catalog seal changed/missing')
    catalog=read(catalog_path)
    if catalog.get('schema')!=SCHEMA or catalog.get('source')!='artifacts/rebuild_r45/source_world_backup':raise Hold('Unrecognized source/schema')
    if catalog.get('dimension')!='projectseele:geofront':raise Hold('Only exact classified GeoFront inputs')
    if destination is not None:policy.new_candidate(destination)
    report=policy.new_report(report);report.parent.mkdir(parents=True,exist_ok=True);report.mkdir()
    db=None
    try:
        for item in catalog.get('epochs',[]):policy.input(item)
        components=selected_components(catalog,requested);source_files=check_source(policy,catalog);codec=load_codec(policy,catalog)
        # Even file-only conflicts stop before expensive row staging or copying.
        file_ops=stage_files(policy,catalog,components,source_files)
        db=sqlite3.connect(report/'cells.sqlite')
        db,states,reverse,regions,stats=stage_cells(policy,catalog,components,report,codec,db)
        # Recheck every SHA after staging; do not infer a stale plan remains valid.
        for item in [catalog['baseline'],catalog['codec'],catalog['native_state_contract'],*catalog.get('epochs',[])]:policy.input(item)
        for c in components:
            for p in c.get('patches',[]):policy.input(p['forward']);policy.input(p['inverse'])
            for p in c.get('files',[]):policy.input(p['after'])
        result=dict(status='DRY_RUN_EXACT_BEFORE_CANDIDATE_ONLY',world_written=False,source_written=False,catalog_sha256=sha(catalog_path),source_uuid=catalog['world_uuid'],source_seed=catalog['seed'],components=stats,regions=regions,file_operations=file_ops,omitted_or_deferred=[dict(id=r['id'],reason=r.get('deferred_reason','NOT_SELECTED')) for r in catalog['components'] if r not in components],native_pass=False,art_pass=False,UN_initialized=False)
        durable(report/'preflight.json',result)
        if destination is not None:
            check_source(policy,catalog);result=apply_candidate(policy,catalog,source_files,components,db,states,reverse,regions,file_ops,report,destination,codec)
        return result
    except BaseException as exc:
        durable(report/'failure.json',dict(status='HOLD_NOT_RELEASE',error=str(exc),source_written=False,new_candidate_may_be_incomplete=destination is not None))
        if not (report/'conflicts.json').exists():durable(report/'conflicts.json',dict(conflicts=[dict(reason=str(exc))],all_whole_components_held=True))
        raise
    finally:
        if db is not None:db.close()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--catalog',type=Path,default=ROOT/DEFAULT_CATALOG);ap.add_argument('--components',help='Comma-separated classified IDs; dependencies included');ap.add_argument('--report',type=Path);ap.add_argument('--apply',action='store_true');ap.add_argument('--candidate',type=Path)
    args=ap.parse_args();policy=Policy();name=uuid.uuid4().hex[:12];report=args.report or policy.reports/name
    if args.apply and args.candidate is None:ap.error('--apply requires an explicitly named NEW --candidate')
    if args.candidate is not None and not args.apply:ap.error('--candidate is accepted only with --apply; dry-run never creates a world')
    try:
        result=run(args.catalog,policy,report,args.components.split(',') if args.components else None,args.candidate if args.apply else None)
        print(json.dumps(dict(status=result['status'],report=str(report),candidate=str(args.candidate) if args.apply else None,native_pass=False,art_pass=False),ensure_ascii=False))
    except (Hold,RuntimeError,ValueError,OSError) as exc:print('HOLD: '+str(exc),file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
