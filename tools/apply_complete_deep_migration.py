"""Root-only composition of measured deep components, native lifts and actors.

Prepares by default. Application is one locked geometry/metadata transaction,
with exact before states, original identities, backups and post-write readback.
"""
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import json
import msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from prepare_continuous_upright_civil_r52 import cuboids
from prepare_complete_deep_components import SHIFT
from prepare_complete_lift_followups import prepare_capability_merge
from prepare_pyramid_move_r52 import encoded
from query_blocks import iter_block_entities, read_box
from move_component_actors_r52 import prepare_actor_files, descendants, identity
from verify_main_r20 import entities
from apply_s20_approved_semantic_repairs import atomic_replace

DIM='projectseele:geofront'
STAGE='complete_deep_components_and_original_two_lifts'


def inside(p,lo,shape):
    x,y,z=np.asarray(p,dtype=int)-lo
    return 0<=y<shape[0] and 0<=z<shape[1] and 0<=x<shape[2]


def index(p,lo):
    x,y,z=np.asarray(p,dtype=int)-lo
    return (y,z,x)


def metadata(base,world,lift_metadata):
    before_actors=entities(world)
    actual={identity(t):t for t in before_actors.values()}
    assert len(actual)==678
    hd=json.loads((base/'hangar_component/devices_and_actors.json').read_text('utf8'))
    td=json.loads((base/'terminal_move/complete_terminal_translation/PLAN.json').read_text('utf8'))
    owned={r['uuid'] for r in hd['actors']}|{r['uuid'] for r in td['actor_receipt']['moves']}
    passengers=set()
    for uid in owned:passengers.update(identity(t) for t in list(descendants(actual[uid]))[1:])
    roots=owned-passengers
    expected={u:actual[u].snbt() for u in roots}
    pending,actor_report=prepare_actor_files(world,{u:SHIFT for u in roots},expected)
    cap=prepare_capability_merge(world,lift_metadata);pending[cap['path']]=cap['after']
    roster_path=world/'nerv_staff_r15.json';roster=json.loads(roster_path.read_text('utf8'))
    staff={str(actual[u]['StaffId']) for u in roots if str(actual[u]['id'])=='projectseele:nerv_staff'}
    for row in roster['stations']:
        if row['id'] in staff:row['feet']=list(SHIFT.block(row['feet']))
    pending[roster_path]=(json.dumps(roster,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    storage_path=world/'r50_yashima_recovery_storage.json';storage=json.loads(storage_path.read_text('utf8'))
    for row in storage['recovery_storage']:
        assert row['position'][1]==-677 and row['operation_layer_y']==-678
        for key in ('position','crew_stand_candidate','original_parked_eva'):row[key]=list(SHIFT.point(row[key]))
        row['operation_layer_y']-=384
    pending[storage_path]=(json.dumps(storage,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    site_path=world/'tv_encounter_sites_r45.json';site=json.loads(site_path.read_text('utf8'))
    # Explicit recovery-storage references, never recursively translate site
    # coordinates: the distant battlefield has its separate accepted design.
    recovery=[]
    def storage_refs(v,path=()):
        if isinstance(v,dict):
            for k,w in v.items():
                if k=='recovery_storage' and isinstance(w,list):
                    for i,entry in enumerate(w):
                        assert entry['position'] in ([50,-677,328],[52,-677,328])
                        entry['position']=list(SHIFT.block(entry['position']))
                        recovery.append('/'.join(map(str,path+(k,i,'position'))))
                else:storage_refs(w,path+(k,))
        elif isinstance(v,list):
            for i,w in enumerate(v):storage_refs(w,path+(i,))
    storage_refs(site)
    assert len(recovery)==2,'Two existing encounter storage references must be migrated'
    if recovery:pending[site_path]=(json.dumps(site,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    # Native player inventory, attributes and all progress remain unmodified.
    core=[]
    for p in (base/'deep_components_384').glob('*.npz'):
        q=np.load(p);core.append((q['origin'],q['owned']))
    def owned_position(p):return any(inside(np.floor(p),o,m.shape) and m[index(np.floor(p),o)] for o,m in core)
    player_changes=[]
    def move_player(tag,label):
        changed=False
        if str(tag.get('Dimension',''))==DIM and owned_position(list(map(float,tag['Pos']))):
            assert 'RootVehicle' not in tag,'Mounted saved player needs complete original graph handling'
            tag['Pos']=nbtlib.List[nbtlib.Double]([nbtlib.Double(v) for v in SHIFT.point(list(map(float,tag['Pos'])))])
            changed=True;player_changes.append(label+'#Pos')
        if str(tag.get('SpawnDimension',''))==DIM and 'SpawnY' in tag:
            point=[int(tag[k]) for k in ('SpawnX','SpawnY','SpawnZ')]
            if owned_position(point):tag['SpawnY']=nbtlib.Int(point[1]-384);changed=True;player_changes.append(label+'#SpawnY')
        return changed
    for p in (world/'playerdata').glob('*.dat'):
        tag=nbtlib.load(p)
        if move_player(tag,str(p.relative_to(world))):pending[p]=encoded(tag)
    p=world/'level.dat';tag=nbtlib.load(p)
    if 'Player' in tag['Data'] and move_player(tag['Data']['Player'],'level.dat#Player'):pending[p]=encoded(tag)
    return pending,dict(actors=actor_report,player_changes=player_changes,storage_refs=recovery,
        native_changed_groups=cap['changed_groups'],all_actor_before={u:t.snbt() for u,t in actual.items()},moved_uuids=sorted(owned))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--lift-civil',type=Path,required=True);ap.add_argument('--lift-metadata',type=Path,required=True)
    ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    base=args.base.resolve();world=base/'WORLD';out=base/'deep_components_384'
    assert not (out/'APPLIED.json').exists()
    survey.WORLD=extension.WORLD=vox.WORLD=world;vox.OUT=out;vox.DIM=DIM
    patch=json.loads(gzip.decompress((args.lift_civil/'FULL_COMPOSED_STATES.json.gz').read_bytes()))
    ownership=json.loads((args.lift_civil/'OWNERSHIP.json').read_text('utf8'))
    arrays=[]
    for file in sorted(out.glob('*.npz')):
        d=np.load(file);names=list(map(str,d['palette']))
        for part,origin in (('source','origin'),('destination','destination_origin')):
            arrays.append(dict(name=file.stem+'_'+part,lo=d[origin],before=d[part+'_before'],after=d[part+'_after'].copy(),names=names.copy(),owned=d['owned']))
    outside=[];overrides=[]
    for row in patch:
        pos=row['pos'];matched=False
        for a in arrays:
            if not inside(pos,a['lo'],a['before'].shape):continue
            assert not matched,'Component envelopes must not overlap';matched=True
            idx=index(pos,a['lo']);names=a['names']
            assert names[int(a['before'][idx])]==row['before'],('Civil/core measured disagreement',pos)
            old_after=names[int(a['after'][idx])]
            if old_after!=row['after'] and a['owned'][idx]:
                # New shafts cross the explicitly retired former component;
                # relocated rooms beyond the new shaft bottoms stay complete.
                assert a['name'].endswith('_source') and any(all(b[0][k]<=pos[k]<=b[1][k] for k in range(3)) for b in ownership['shaft_exclusions_in_core_destination']),('Unexpected composition conflict',a['name'],pos,old_after,row['after'])
                overrides.append(dict(pos=pos,retirement=old_after,shaft=row['after']))
            if row['after'] not in names:names.append(row['after'])
            a['after'][idx]=names.index(row['after'])
        if not matched:outside.append(row)
    painter=vox.Painter(vertical_bounds=(-1344,320))
    for a in arrays:cuboids(painter,a['lo'],a['before'],a['after'],a['names'],a['name'])
    for row in outside:
        if row['before']!=row['after']:painter.exact((*row['pos'],*row['pos']),row['before'],row['after'],row['owner'])
    be=json.loads((out/'BLOCK_ENTITY_MOVES.json').read_text('utf8'))
    controlled=json.loads((args.lift_civil/'CONTROLLED_BE_INTERFACE.json').read_text('utf8'))['operations']
    for r in controlled:
        be.append(dict(source=r['source'],target=r['target'],before_snbt=r['before_nbt'],after_snbt=r['after_nbt'],state=r['state']))
    assert len({tuple(r['source']) for r in be})==len(be)==28
    for r in be:painter.block_entities[tuple(r['target'])]=nbtlib.parse_nbt(r['after_snbt'])
    painter.meta.update(root_author=True,deep_dy=-384,preserve_original_actor_uuids=True,original_two_main_lifts=True,
        original_office_preserved=True,component_source=str(out/'PLAN.json'),native_civil=str(args.lift_civil),playable=False)
    folder=painter.save_plan(STAGE)
    (folder/'COMPOSED_SHAFT_OVER_RETIREMENT.json').write_text(json.dumps(overrides,indent=2),'utf8')
    print(json.dumps(dict(operations=len(painter.ops),block_entities=len(be),explicit_new_shaft_retirement_overrides=len(overrides),world_written=False)),flush=True)
    if not args.apply:return
    assert not list(folder.glob('applied_*')),'Existing receipt requires inspection, never blind replay'
    lock=extension.acquire_world_lock();backups={};geometry=None
    try:
        # All original devices must still match under the world lock.
        for r in be:
            p=tuple(r['source']);q=tuple(r['target'])
            old=dict(iter_block_entities(world,DIM,p,p));dest=dict(iter_block_entities(world,DIM,q,q))
            assert old[p].snbt()==r['before_snbt'] and q not in dest
        pending,meta=metadata(base,world,args.lift_metadata)
        for p in pending:backups[p]=p.read_bytes()
        backup=folder/'metadata_before';backup.mkdir()
        for p,raw in backups.items():
            q=backup/p.relative_to(world);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(raw)
        geometry=painter.apply(STAGE,session_lock=lock)
        for p,raw in pending.items():
            assert p.read_bytes()==backups[p];atomic_replace(p,raw)
        for a in arrays:
            lo=a['lo'];hi=lo+np.array(a['after'].shape)[[2,0,1]]-1
            data,palette=survey.measure(tuple(lo),tuple(hi))
            ids={s:i for i,s in enumerate(a['names'])}
            actual=np.array([ids[s] for s in palette],np.uint16)[data]
            assert np.array_equal(actual,a['after']),('Complete component readback mismatch',a['name'])
        after_actors={identity(t):t for t in entities(world).values()}
        assert set(after_actors)==set(meta['all_actor_before']) and len(after_actors)==678
        moved=set(meta['moved_uuids'])
        from facility_frame_nbt_r52 import actor_in_frame
        for uid,old in meta['all_actor_before'].items():
            expected=actor_in_frame(nbtlib.parse_nbt(old),SHIFT).snbt() if uid in moved else old
            assert after_actors[uid].snbt()==expected,('Actor identity or progress changed',uid)
        for r in be:
            p=tuple(r['source']);q=tuple(r['target'])
            assert p not in dict(iter_block_entities(world,DIM,p,p))
            assert dict(iter_block_entities(world,DIM,q,q))[q].snbt()==r['after_snbt']
        for p,raw in pending.items():assert p.read_bytes()==raw
        meta.pop('all_actor_before')
        result=dict(world_written=True,playable=False,dy=-384,geometry=geometry,metadata=meta,all_678_original_ids_and_progress_preserved=True,
            complete_source_and_target_exact_readback=True,all_28_typed_devices_exact_readback=True,
            pending=['final runtime/command/navigation binding','complete launch civil/mechanisms','native riding and visual review'])
        (out/'APPLIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
        print('Deep component, actor and two-main-lift migration read back exactly.',flush=True)
    except BaseException:
        for p,raw in backups.items():atomic_replace(p,raw)
        if geometry is not None:
            applied=list(folder.glob('applied_*'));assert len(applied)==1
            for p in (applied[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/p.name,p.read_bytes())
            (applied[0]/'ROLLED_BACK.json').write_text('{"reason":"composite metadata or readback failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
