"""Root-only exact v8 -> NEW v9 copy and six-cell ID15 stair completion.

Default stages offline reports only. Reuses the frozen composer and exact codec;
no existing source, QA save, City job, model or actor/progress edit is possible.
"""
from pathlib import Path
from contextlib import contextmanager
import argparse,copy,importlib.util,json,os,sqlite3,sys,uuid
sys.dont_write_bytecode=True
import nbtlib
import compose_r45_candidate_v5 as shared

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
OWN=ART/'lifts_doors_lifecycle_sol_v2/command15_v9_root_entry_v1'
SOURCE=ART/'composition_candidates/R45_source_candidate_20261004_v8_01/world'
DEST=ART/'composition_candidates/R45_source_candidate_20261004_v9_01'
CATALOG=OWN/'catalog.json';ID='command15_throat6'
SCHEMA='projectseele.r45.command15-v8-to-v9-six-exact-cells.v1'
sha=shared.sha;read=shared.read;inventory=shared.inventory

def load(catalog):
    entry=catalog['core'];p=ROOT/entry['path']
    if p!=ART/'pyramid_components_sol_v1/v5_combined_entry_v2/core/compose_v5_core.py'or sha(p)!=entry['sha256']:raise RuntimeError('Frozen existing composer changed')
    spec=importlib.util.spec_from_file_location('r45_command15_existing_core',p);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    core.ROOT=ROOT;core.SCHEMA=SCHEMA;core.ALLOWED_IDS={ID};core.ALLOWED_DERIVED_TARGETS=set()
    class Policy(core.Policy):
        def __init__(self):super().__init__(ROOT);self.source=SOURCE;self.reports=OWN/'runs'
        def new_candidate(self,p):
            if Path(p).resolve()!=DEST.resolve():raise RuntimeError('Only the explicitly NEW v9 candidate is permitted')
            return super().new_candidate(p)
    core.Policy=Policy;core.check_source=check_source;core.validate_cell_contract=cell_contract
    return core

def check_source(policy,catalog):
    baseline=read(policy.input(catalog['baseline']));parent=read(policy.input(catalog['actual_root_v8_receipt']))
    if Path(baseline['source_world']).resolve()!=SOURCE.resolve()or Path(parent['world']).resolve()!=SOURCE.resolve()or parent['phase']!='COMPLETE':raise RuntimeError('Wrong actual v8 source/receipt')
    files={r['relative']:r['sha256']for r in baseline['files']}
    if len(files)!=1736 or files!=parent['full_after_inventory']or inventory(SOURCE)!=files:raise RuntimeError('Full actual v8 source inventory/hash changed')
    level=nbtlib.load(SOURCE/'level.dat')['Data'];uid=nbtlib.load(SOURCE/catalog['identity_file'])['data']['WorldUUID']
    if int(level['WorldGenSettings']['seed'])!=catalog['seed']or str(uid)!=catalog['world_uuid']:raise RuntimeError('Original world UUID/seed changed')
    return files

def cell_contract(policy,catalog,component,row,b,a,bn,an):
    core=load(catalog);expected={tuple(r['pos']):r for r in core.row_stream(policy.input(catalog['exact_forward6']))}
    if component['id']!=ID or expected.get(tuple(row['pos']))!=row or len(expected)!=6:raise RuntimeError('Only the frozen exact six full preimages are permitted')
    traits=read(policy.input(catalog['native_state_contract']))
    if bn is not None or an is not None or any(s not in traits or traits[s]['has_block_entity']for s in(b,a)):raise RuntimeError('Six-cell repair cannot add/remove/change a BE')

def verify(core,policy,catalog,candidate,save=False):
    candidate=Path(candidate).resolve()
    if candidate!=DEST.resolve():raise RuntimeError('Readback is limited to this v9 candidate')
    receipt=read(candidate/'composition.json');world=candidate/'world';original=check_source(policy,catalog)
    if receipt['original_source']!=str(SOURCE)or receipt['selected_components']!=[ID]or receipt['files']or len(receipt['regions'])!=1:raise RuntimeError('Wrong/incomplete six-cell composition receipt')
    staged=Path(receipt['report']).resolve()
    if staged.parent!=policy.reports.resolve():raise RuntimeError('Foreign staged report')
    codec=core.load_codec(policy,catalog);db=sqlite3.connect('file:'+str(staged/'cells.sqlite')+'?mode=ro',uri=True)
    expected={}
    for row in core.row_stream(policy.input(catalog['exact_forward6'])):
        c=codec.cell(row,catalog['dimension']);expected[c[2:6]]=(*c[6:],ID)
    actual={(cx,cz,sy,off):(b,a,bn,an,owner,component)for cx,cz,sy,off,b,a,bn,an,owner,component in db.execute('SELECT cx,cz,sy,off,b,a,bn,an,owner,component FROM cells')}
    if actual!=expected:db.close();raise RuntimeError('Staged full six-cell rows differ from the original frozen candidate')
    region=receipt['regions'][0];old_path=candidate/region['inverse_file'];new_path=world/region['target']
    if region['target']!='dimensions/projectseele/geofront/region/r.0.0.mca'or region['cells']!=6 or sha(old_path)!=original[region['target']]or sha(old_path)!=region['before_sha256']or sha(new_path)!=region['after_sha256']:raise RuntimeError('Wrong original/inverse/after region epoch')
    states={s:i for i,(s,)in enumerate(db.execute('SELECT b FROM cells UNION SELECT a FROM cells'))};reverse={i:s for s,i in states.items()};old=codec.read_region(old_path)[1];new=codec.read_region(new_path)[1]
    counts=dict(rows=0,touched_chunks=0,before_BE=0,after_BE=0);touched=set()
    for cx,cz in db.execute('SELECT DISTINCT cx,cz FROM cells'):
        slot=(cx&31)+(cz&31)*32;touched.add(slot);changes=[(sy,off,states[b],states[a],bn,an)for sy,off,b,a,bn,an in db.execute('SELECT sy,off,b,a,bn,an FROM cells WHERE cx=? AND cz=? ORDER BY sy,off',(cx,cz))]
        before=codec.parse_chunk(old[slot]);after=codec.parse_chunk(new[slot]);codec.validate_chunk(before,changes,reverse);codec.validate_chunk(after,changes,reverse,after=True)
        if codec.chunk_guard_hash(before,changes,True)!=codec.chunk_guard_hash(after,changes,True)or codec.block_tags(before)!=codec.block_tags(after):raise RuntimeError('Unrelated full chunk/BE NBT changed')
        counts['rows']+=len(changes);counts['touched_chunks']+=1;counts['before_BE']+=len(codec.block_tags(before));counts['after_BE']+=len(codec.block_tags(after))
    db.close()
    if any(old[i]!=new[i]for i in range(1024)if i not in touched)or counts['rows']!=6 or counts['touched_chunks']!=1:raise RuntimeError('Untouched complete compressed chunk bytes changed')
    files=inventory(world)
    if set(files)!=set(original):raise RuntimeError('Source file additions/removals')
    for p,h in original.items():
        wanted=region['after_sha256']if p==region['target']else h
        if p!='session.lock'and files[p]!=wanted:raise RuntimeError('Original complete progress/metadata/file changed: '+p)
    # Complete504 component, 37 inputs, 102 owned aperture cells and two markers
    # are read through the same central codec as the actual changed region.
    guards=read(policy.input(catalog['complete_component_guards']))
    cached={}
    for r in guards:
        x,y,z=r['pos'];rx,rz=x//512,z//512;key=rx,rz
        if key not in cached:cached[key]=codec.read_region(codec.q.dimension_dir(world,catalog['dimension'])/'region'/f'r.{rx}.{rz}.mca')[1]
        root=codec.parse_chunk(cached[key][((x//16)&31)+((z//16)&31)*32]);sec=codec.measured_section(root,y//16);state='minecraft:air'if sec is None else sec[0][int(sec[1][((y&15)<<8)|((z&15)<<4)|(x&15)])]
        tag=codec.block_tags(root).get((x,y,z));want=None if r['full_nbt']is None else nbtlib.parse_nbt(r['full_nbt'])
        if state!=r['state']or tag!=want:raise RuntimeError('Complete preserved or after guard differs: '+str((x,y,z)))
    report=dict(schema='projectseele.command15-v9-exact-readback.v1',world=str(world),original_source=str(SOURCE),source1736_unchanged=True,full_after_inventory=files,counts=counts,complete_component37_inputs102_apertures_verified=True,all_original_actor_player_task_MTR_progress_and_two_metadata_byte_preserved=True,lighting_derived_in_changed_chunk=bool(region['derived_relight']),new_static_component_native=False,old165_inherited_by_geometry_proof_only=True,BE17_relog_inherited_by_separate_receipt=True,full_lifecycle_pass=False,installed_into_user_world=False,world_written_by_readback=False)
    if save:core.durable(candidate/'composition_v9_readback.json',report)
    else:
        recorded=read(candidate/'composition_v9_readback.json')
        if recorded['full_after_inventory']!=files:raise RuntimeError('Candidate changed since original Root readback')
    return report

@contextmanager
def locked(world):
    with(world/'session.lock').open('r+b')as f:
        import msvcrt
        msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        try:yield
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def rollback(core,policy,catalog,candidate,apply):
    actual=verify(core,policy,catalog,candidate);receipt=read(candidate/'composition.json');region=receipt['regions'][0]
    if apply:
        with locked(candidate/'world'):
            current=inventory(candidate/'world')
            if any(current[p]!=h for p,h in actual['full_after_inventory'].items()if p!='session.lock'):raise RuntimeError('Gameplay/file progress changed; whole-MCA rollback is forbidden')
            codec=core.load_codec(policy,catalog);codec.atomic_replace(candidate/'world'/region['target'],(candidate/region['inverse_file']).read_bytes())
        original=check_source(policy,catalog);now=inventory(candidate/'world')
        if any(now[p]!=h for p,h in original.items()if p!='session.lock'):raise RuntimeError('Root rollback readback failed')
        core.durable(candidate/'rollback_actual.json',dict(restored=True,source_written=False,whole_before_MCA_recovered=True,no_progress_after_install_permitted=True))
    return dict(rollback_ready=True,applied=apply,source_written=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');p.add_argument('--candidate',type=Path);p.add_argument('--report',type=Path);p.add_argument('--readback',action='store_true');p.add_argument('--rollback',action='store_true');a=p.parse_args()
    catalog=read(CATALOG)
    if CATALOG.with_suffix('.json.sha256').read_text('ascii').strip()!=sha(CATALOG):raise RuntimeError('Catalog seal changed')
    core=load(catalog);policy=core.Policy()
    for item in[catalog['core'],catalog['baseline'],catalog['actual_root_v8_receipt'],catalog['complete_component_guards'],*catalog['epochs']]:policy.input(item)
    if a.readback or a.rollback:
        if not a.candidate or a.report or a.readback and(a.rollback or a.apply):p.error('Readback/rollback require one candidate')
        result=rollback(core,policy,catalog,a.candidate.resolve(),a.apply)if a.rollback else verify(core,policy,catalog,a.candidate)
    else:
        if a.apply!=(a.candidate is not None):p.error('--apply needs the explicitly new v9 --candidate')
        result=core.run(CATALOG,policy,a.report or policy.reports/('root_'+uuid.uuid4().hex[:12]),None,a.candidate if a.apply else None)
        if a.apply:result=verify(core,policy,catalog,a.candidate,save=True)
    print(json.dumps({k:v for k,v in result.items()if k not in{'full_after_inventory','regions','components','file_operations'}},ensure_ascii=True,indent=2))
if __name__=='__main__':
    try:main()
    except(RuntimeError,ValueError,OSError)as exc:print('HOLD: '+str(exc),file=sys.stderr);raise SystemExit(2)
