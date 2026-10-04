"""Exact Source v12 -> NEW candidate591 TV surrounds/roof; root alone applies."""
from pathlib import Path
import argparse,copy,importlib.util,json,sqlite3,sys,uuid
sys.dont_write_bytecode=True
import nbtlib
import compose_r45_candidate_v5 as shared

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
OWN=ART/'lifts_doors_lifecycle_sol_v2/tv_door_lift_construction_v1/root_v12_entry_v2'
SOURCE=ART/'composition_candidates/R45_source_candidate_20261004_v12_01/world'
CATALOG=OWN/'catalog.json';ID='tv_command17_cabin7_finish591'
SCHEMA='projectseele.r45.tv-current-v12-exact591.v1'
sha=shared.sha;read=shared.read;inventory=shared.inventory
def load(catalog):
    p=ROOT/catalog['core']['path']
    if sha(p)!=catalog['core']['sha256']:raise RuntimeError('Existing exact composer changed')
    spec=importlib.util.spec_from_file_location('r45_tv_existing_core',p);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    core.ROOT=ROOT;core.SCHEMA=SCHEMA;core.ALLOWED_IDS={ID};core.ALLOWED_DERIVED_TARGETS={'.projectseele_command_sliding_doors_r01.json'}
    class Policy(core.Policy):
        def __init__(self):super().__init__(ROOT);self.source=SOURCE;self.reports=OWN/'runs'
        def new_candidate(self,p):
            p=Path(p).resolve()
            if not p.name.startswith('R45_source_candidate_') or p==SOURCE.parent:raise RuntimeError('Only a NEW explicitly named Source candidate')
            return super().new_candidate(p)
    core.Policy=Policy;core.check_source=check_source;core.validate_cell_contract=cell_contract
    return core
def check_source(policy,catalog):
    baseline=read(policy.input(catalog['baseline']));parent=read(policy.input(catalog['actual_root_v12_receipt']));files=baseline['files']
    if Path(parent['world']).resolve()!=SOURCE.resolve() or parent['phase']!='COMPLETE' or files!=parent['full_after_inventory'] or len(files)!=1739 or inventory(SOURCE)!=files:raise RuntimeError('Full actual v12 Source inventory changed')
    if int(nbtlib.load(SOURCE/'level.dat')['Data']['WorldGenSettings']['seed'])!=catalog['seed'] or str(nbtlib.load(SOURCE/catalog['identity_file'])['data']['WorldUUID'])!=catalog['world_uuid']:raise RuntimeError('Original UUID/seed changed')
    return files
def cell_contract(policy,catalog,component,row,b,a,bn,an):
    expected=read(policy.input(catalog['exact_rows']))
    if component['id']!=ID or expected.get(';'.join(map(str,row['pos'])))!=row or len(expected)!=591:raise RuntimeError('Only frozen actual591 whole-state rows allowed')
    traits=read(policy.input(catalog['native_state_contract']))
    if bn is not None or an is not None or any(s not in traits or traits[s]['has_block_entity']for s in(b,a)):raise RuntimeError('This appearance component cannot add/remove any BE')
def verify(core,policy,catalog,candidate,save=False):
    candidate=Path(candidate).resolve()
    if candidate.parent!=(ART/'composition_candidates').resolve():raise RuntimeError('Foreign candidate readback')
    receipt=read(candidate/'composition.json');world=candidate/'world';original=check_source(policy,catalog)
    if receipt['original_source']!=str(SOURCE) or receipt['selected_components']!=[ID] or len(receipt['regions'])!=4 or len(receipt['files'])!=1:raise RuntimeError('Wrong exact591+one-support-metadata composition')
    staged=Path(receipt['report']).resolve()
    if staged.parent!=policy.reports.resolve():raise RuntimeError('Foreign stage')
    codec=core.load_codec(policy,catalog);db=sqlite3.connect('file:'+str(staged/'cells.sqlite')+'?mode=ro',uri=True);rows=read(policy.input(catalog['exact_rows']));wanted={}
    for row in rows.values():
        c=codec.cell(row,catalog['dimension']);wanted[c[2:6]]=(*c[6:],ID)
    actual={(cx,cz,sy,off):(b,a,bn,an,owner,comp)for cx,cz,sy,off,b,a,bn,an,owner,comp in db.execute('SELECT cx,cz,sy,off,b,a,bn,an,owner,component FROM cells')}
    if wanted!=actual:raise RuntimeError('Stage591 full preimages differ')
    states={s:i for i,(s,)in enumerate(db.execute('SELECT b FROM cells UNION SELECT a FROM cells'))};reverse={i:s for s,i in states.items()};counts=dict(rows=0,chunks=0,all_original_BE=0)
    for r in receipt['regions']:
        old_path=candidate/r['inverse_file'];new_path=world/r['target']
        if sha(old_path)!=original[r['target']] or sha(new_path)!=r['after_sha256']:raise RuntimeError('Wrong inverse/current region bytes')
        old=codec.read_region(old_path)[1];new=codec.read_region(new_path)[1];touched=set();rx,rz=[int(v)for v in Path(r['target']).name.split('.')[1:3]]
        for cx,cz in db.execute('SELECT DISTINCT cx,cz FROM cells WHERE rx=? AND rz=?',(rx,rz)):
            slot=(cx&31)+(cz&31)*32;touched.add(slot);changes=[(sy,off,states[b],states[a],bn,an)for sy,off,b,a,bn,an in db.execute('SELECT sy,off,b,a,bn,an FROM cells WHERE cx=? AND cz=? ORDER BY sy,off',(cx,cz))]
            before=codec.parse_chunk(old[slot]);after=codec.parse_chunk(new[slot]);codec.validate_chunk(before,changes,reverse);codec.validate_chunk(after,changes,reverse,after=True)
            if codec.block_tags(before)!=codec.block_tags(after) or codec.chunk_guard_hash(before,changes,True)!=codec.chunk_guard_hash(after,changes,True):raise RuntimeError('Unrelated full BE/chunk NBT changed')
            counts['rows']+=len(changes);counts['chunks']+=1;counts['all_original_BE']+=len(codec.block_tags(before))
        if any(old[i]!=new[i]for i in range(1024)if i not in touched):raise RuntimeError('Unchanged compressed chunk bytes mutated')
    db.close();files=inventory(world);allowed={r['target']:r['after_sha256']for r in receipt['regions']+receipt['files']}
    if set(files)!=set(original) or counts['rows']!=591 or counts['chunks']!=20:raise RuntimeError('Full Source file count/component count changed')
    if any(files[k]!=allowed.get(k,h)for k,h in original.items()if k!='session.lock'):raise RuntimeError('Player/actor/task/MTR/navigation/unrelated file bytes changed')
    meta=read(policy.input(catalog['metadata_contract']));target=meta['target']
    if sha(world/target)!=meta['after']['sha256'] or sha(SOURCE/target)!=meta['before']['sha256']:raise RuntimeError('Actual fixed-support metadata not installed')
    report=dict(schema=SCHEMA,phase='COMPLETE_STATIC_NOT_ART_NOT_NATIVE',world=str(world),original_source=str(SOURCE),source1739_unchanged=True,full_after_inventory=files,counts=counts,all_actual39_inputs102_apertures_and_identity_preserved=True,all_player_actor_task_MTR_and_nav_files_byte_preserved=True,appearance_model_geometry_installed=False,native_or_visual_pass=False,world_written_by_readback=False)
    if save:core.durable(candidate/'composition_tv_finish_readback.json',report)
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path);p.add_argument('--execute-root',action='store_true');p.add_argument('--readback',action='store_true');p.add_argument('--report',type=Path);a=p.parse_args();catalog=read(CATALOG)
    if CATALOG.with_suffix('.json.sha256').read_text('ascii').strip()!=sha(CATALOG):raise RuntimeError('Frozen catalog changed')
    core=load(catalog);policy=core.Policy()
    if a.readback:
        assert a.candidate and not a.execute_root and not a.report;result=verify(core,policy,catalog,a.candidate)
    else:
        if a.execute_root!=(a.candidate is not None):p.error('--candidate requires explicit --execute-root')
        result=core.run(CATALOG,policy,a.report or policy.reports/('root_'+uuid.uuid4().hex[:12]),None,a.candidate if a.execute_root else None)
        if a.execute_root:result=verify(core,policy,catalog,a.candidate,save=True)
    print(json.dumps({k:v for k,v in result.items()if k not in{'full_after_inventory','regions','components','file_operations'}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
