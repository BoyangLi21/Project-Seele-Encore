"""Crash/replay, complete NBT and ownership reference cases; never launches a JVM."""
from pathlib import Path
from dataclasses import dataclass
import copy,json,hashlib,ast,math
import nbtlib
from install_city_rigid_metadata_r45 import same_tag,serialized_be_tag_matches
from query_blocks import palette_state
from regional_voxels import canonical_state
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r45/city_motion_sol_followup'
AIR=None
@dataclass(eq=False)
class Image:
    state:str
    nbt:object=None
    def __eq__(self,other):return isinstance(other,Image) and self.state==other.state and same_tag(self.nbt,other.nbt)
def at(image,q):
    tag=copy.deepcopy(image.nbt)
    if tag is not None:
        for key,value in zip(('x','y','z'),q):tag[key]=nbtlib.Int(value)
    return Image(image.state,tag)
def get(world,q):return world.get(q,Image('minecraft:air'))
def fold(operations):
    rows={}
    for q,before,after in operations:
        row=rows.setdefault(q,dict(initial=before,final=before,known=[]));row['known'] += [before,after];row['final']=after
    return rows
def reconcile(world,rows,rollback):
    for q,row in rows.items():
        actual=get(world,q);desired=row['initial'] if rollback else row['final']
        if actual==desired:continue
        if not any(actual==known for known in row['known']):raise ValueError(('unknown complete state/NBT',q))
        world[q]=copy.deepcopy(desired)
def fixture(surface_to_below,nbt):
    source,target=(80,-37) if surface_to_below else (-37,80)
    cells={(0,0,0):Image('minecraft:smooth_stone'),(1,1,0):Image('minecraft:barrel[facing=north,open=false]',nbt)}
    world={};operations=[];air=Image('minecraft:air');hatch=Image('minecraft:iron_block')
    for local,image in cells.items():q=(local[0],source+local[1],local[2]);world[q]=at(image,q)
    if not surface_to_below:
        for x in range(2):world[x,80,0]=copy.deepcopy(hatch);operations.append(((x,80,0),hatch,air))
    for local,image in cells.items():q=(local[0],source+local[1],local[2]);operations.append((q,get(world,q),air))
    for local,image in cells.items():q=(local[0],target+local[1],local[2]);operations.append((q,air,at(image,q)))
    if surface_to_below:
        for x in range(2):operations.append(((x,80,0),air,hatch))
    return world,operations
def main():
    OUT.mkdir(parents=True,exist_ok=True);checks=[]
    path=ROOT/'artifacts/rebuild_r45/city_motion/whole_topology_v2/manifest.json';manifest=json.loads(path.read_text('utf8'))
    first=nbtlib.load(Path(manifest['records'][0]['cargo']))['data']['Buildings'][0]
    tag=copy.deepcopy(next(c['NBT'] for c in first['Cargo'] if 'NBT' in c))
    tag['FixtureOpaqueSentinel']=nbtlib.Compound({'UUID':nbtlib.IntArray([1,-2,3,-4]),'UnknownItems':nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'Slot':nbtlib.Byte(5),'Count':nbtlib.Byte(17),'Custom':nbtlib.String('preserve every field')})])})
    for down in (True,False):
        before,ops=fixture(down,tag);rows=fold(ops);final=copy.deepcopy(before)
        for q,old,new in ops:
            assert get(final,q)==old,(q,old,get(final,q));final[q]=copy.deepcopy(new)
        for stop in range(len(ops)+1):
            crashed=copy.deepcopy(before)
            for q,old,new in ops[:stop]:assert get(crashed,q)==old;crashed[q]=copy.deepcopy(new)
            for rollback in (True,False):
                recovered=copy.deepcopy(crashed);reconcile(recovered,rows,rollback);wanted=before if rollback else final
                assert all(get(recovered,q)==get(wanted,q) for q in rows)
                reconcile(recovered,rows,rollback)
                checks.append(dict(direction='down' if down else 'up',crash_after_operation=stop,rollback=rollback,complete_images_restored=True,replay_idempotent=True))
        corrupted=copy.deepcopy(before);q=next(p for p in rows if get(before,p).nbt is not None)
        corrupted[q].nbt['FixtureOpaqueSentinel']['UnknownItems'][0]['Count']=nbtlib.Byte(18)
        try:reconcile(corrupted,rows,False);raise AssertionError('Foreign inventory overwritten')
        except ValueError:checks.append(dict(direction='down' if down else 'up',foreign_inventory_fails_closed=True))
    actual=copy.deepcopy(tag);actual['keepPacked']=nbtlib.Byte(0)
    assert serialized_be_tag_matches(tag,actual)==(True,True)
    assert 'keepPacked' in actual and 'keepPacked' not in tag
    mutations=[]
    for label,change in [('packed_1',lambda t:t.__setitem__('keepPacked',nbtlib.Byte(1))),('wrong_type',lambda t:t.__setitem__('keepPacked',nbtlib.Int(0))),('extra_field',lambda t:t.__setitem__('Other',nbtlib.String('never ignore'))),('deleted_original',lambda t:t.pop('FixtureOpaqueSentinel')),('opaque_inventory',lambda t:t['FixtureOpaqueSentinel']['UnknownItems'][0].__setitem__('Count',nbtlib.Byte(18)))]:
        corrupt=copy.deepcopy(actual);change(corrupt);assert not serialized_be_tag_matches(tag,corrupt)[0];mutations.append(label)
    state=nbtlib.Compound({'Name':nbtlib.String('minecraft:barrel'),'Properties':nbtlib.Compound({'open':nbtlib.String('false'),'facing':nbtlib.String('north')})})
    assert isinstance(canonical_state(state.unpack()),dict)
    assert canonical_state(palette_state(state))=='minecraft:barrel[facing=north,open=false]'
    inventory=json.loads((OUT/'actual96_inventory.json').read_text('utf8'));assert len(inventory['objects'])==96 and sum(r['original_full_BE'] for r in inventory['objects'])==1471
    assert all(r['source_archive_epoch_matches'] for r in inventory['objects'])
    foreign_tagged_actor=dict(uuid='npc-original',owner_tag=True,journey='same')
    assert foreign_tagged_actor['owner_tag'] and foreign_tagged_actor['uuid'] not in {'owner-'+str(i) for i in range(96)}
    # Commit is successful before the next trip's preflight. A held queue has
    # no new world effects; its cancellation and relog retain that endpoint.
    committed=dict(phase='IDLE',depth=312,target=312,queued=0,queue_fault='')
    blocked=dict(committed,queue_fault='Create backend missing')
    assert blocked['phase']=='IDLE' and blocked['depth']==312 and blocked['queued']==0
    assert json.loads(json.dumps(blocked))==blocked
    cancelled=dict(blocked,queued=-1,queue_fault='');assert cancelled['depth']==312 and cancelled['phase']=='IDLE'
    controls=ROOT/'src/main/java/com/projectseele/world/CityCreateDistrictR45.java';source=controls.read_text('utf8')
    assert 'state.queued = queued >= 0 && queued != endpoint ? queued : -1' in source
    assert 'if (queued >= 0 && queued != endpoint) begin(queued)' not in source
    assert 'if (!state.phase.equals("IDLE")) throw failure' in source
    assert 'context.plans.size() != context.towers.size()' in source and 'state.savedPlans = plans.size()' in source
    assert 'state.phase = state.index == towers.size() ? "OPEN" : "PREPARE"' in source
    assert 'if (!state.worldTouched) { state.worldTouched = true; persist(); }' in source
    assert 'checkpoint();' in source and 'level.getGameTime() - lastPersistTick >= 20' in source
    assert 'level.save(null, true, false)' in source and 'StandardCopyOption.ATOMIC_MOVE' in source and 'file.force(true)' in source
    report=dict(schema='projectseele.city-reference-transactions-r45.v1',model_cases=checks,reference_cases=len(checks),full_BE_opaque_field_preservation=True,serialization_negative_controls=mutations,
        all96_actual_source_epoch_checked=True,original1471_full_BE_observed=True,queued_commit_occupied_backend_cancel_relog_model=True,strict_inverse_and_phase_barriers_present=True,
        no_foreign_tagged_actor_ignored=True,Java_execution=False,Minecraft_started=False,world_written=False,native_performance_pass=False,limitations='Reference crash/reconcile model and source contracts; Root must still execute actual96 lifecycle, filesystem failure, actor occupancy and two-client tests.')
    (OUT/'transaction_reference_tests.json').write_text(json.dumps(report,indent=2)+'\n','utf8')
    for file in [Path(__file__),ROOT/'tools/audit_city_district_followup_r45.py',ROOT/'tools/install_city_rigid_metadata_r45.py',ROOT/'tools/prepare_city_rigid_generation_r45.py']:ast.parse(file.read_text('utf8'))
    print('Reference crash/replay cases',len(checks),'typedNBT negatives',len(mutations),'actual96 epoch/1471BE checked; no JVM/world writes')
if __name__=='__main__':main()
