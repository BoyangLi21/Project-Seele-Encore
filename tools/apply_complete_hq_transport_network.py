"""Root's atomic finite civil/MTR migration for the reviewed 66-member plan.

All other native member tokens remain byte-identical. Geometry is composed in
measured sparse sections, preserving unselected cells and every original actor.
"""
from pathlib import Path
from collections import defaultdict
import argparse,gzip,hashlib,json,msvcrt
import numpy as np
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections,iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids
from apply_s20_approved_semantic_repairs import atomic_replace

DIM='projectseele:geofront'
STAGE='complete_66_HQ_rails_and_original_native_fleet'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def measured_sections(world,groups,names,key):
    ids={s:i for i,s in enumerate(names)};selected=defaultdict(set)
    for cx,cz,sy in groups:selected[cx,cz].add(sy)
    found=set()
    for cx,cz,sy,palette,indices in iter_selected_sections(world,DIM,selected):
        s=(cx,cz,sy);found.add(s);g=groups[s]
        current=np.asarray([ids.get(state,0) for state in palette],np.uint16)[indices[g[:,0]]]
        good=current==g[:,key]
        if not good.all():
            j=int(np.flatnonzero(~good)[0]);n=int(g[j,0]);position=[cx*16+(n&15),sy*16+(n>>8),cz*16+((n>>4)&15)]
            raise AssertionError(('Exact final MTR civil precondition/readback',position,names[int(g[j,key])],names[int(current[j])]))
    assert found==set(groups)
    xs=[k[0] for k in groups];zs=[k[1] for k in groups];ys=[k[2] for k in groups]
    lo=(min(xs)*16,min(ys)*16,min(zs)*16);hi=(max(xs)*16+15,max(ys)*16+15,max(zs)*16+15)
    sets={k:set(map(int,g[:,0])) for k,g in groups.items()}
    for (x,y,z),tag in iter_block_entities(world,DIM,lo,hi,selected_chunks=set(selected)):
        key=x//16,z//16,y//16
        assert key not in sets or ((y&15)<<8)|((z&15)<<4)|(x&15) not in sets[key],('Original device selected',x,y,z)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'HQ_transport_network'
    assert not(out/'APPLIED.json').exists()
    candidate=a.candidate.resolve();civil=candidate/'PHYSICAL_CANDIDATE';member=candidate/'member_patch'
    report=json.loads((civil/'REPORT.json').read_text('utf8'));manifest=json.loads((member/'PATCH_MANIFEST.json').read_text('utf8'))
    assert report['remaining_holds']==0 and report['original_complete_trees_moved']==8
    assert manifest['counts']==dict(modify=8,delete=11,create=66)
    proof=json.loads((candidate/'NATIVE_FULL_CONSIST_CLEARANCE.json').read_text('utf8'))
    assert proof['all_bogie_models_included'] and proof['protected_science_contacts_with_full_consist_box_and_continuous_point6_margin']==0
    assert proof['candidate_sha256']==report['candidate_sha256']
    native=json.loads((candidate/'NATIVE_BINARY_VERIFICATION.json').read_text('utf8'))
    assert native['vehicles_exact_original_identity_and_saved_state']==40 and native['vehicles_remapped']==6
    assert native['unaffected_vehicles_native_head_positions_exact']==34 and native['native_reassembly_matches_expected_paths']
    assert sha((civil/'EXACT_CHANGES.jsonl.gz').read_bytes())==report['exact_changes_sha256']
    for r in report['prerequisites'].values():assert sha(Path(r['receipt']).read_bytes())==r['sha256']
    names=['UNSELECTED'];ids={names[0]:0};raw_groups=defaultdict(list);count=0
    def code(s):
        if s not in ids:ids[s]=len(names);names.append(s)
        return ids[s]
    with gzip.open(civil/'COMPLETE_SOURCE_AND_TARGET.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            row=json.loads(line);x,y,z=row['pos'];assert row['before_nbt'] is None and row['after_nbt'] is None
            raw_groups[x//16,z//16,y//16].append((((y&15)<<8)|((z&15)<<4)|(x&15),code(row['before']),code(row['after'])))
            count+=1
    assert count==report['counts']['complete_cells']==925701
    groups={key:np.asarray(rows,np.uint16) for key,rows in raw_groups.items()};del raw_groups
    for key,g in groups.items():assert len(np.unique(g[:,0]))==len(g)
    measured_sections(world,groups,names,1)
    # Validate every file target before any filesystem mutation, including
    # deletes. Only this one native MTR database is admitted.
    files=[]
    for row in manifest['operations']:
        rel=Path(row['target_relative_path']);path=(world/rel).resolve()
        assert path.is_relative_to((world/'mtr/projectseele/geofront').resolve()) and '..' not in rel.parts
        old=path.read_bytes() if path.exists() else None
        if row['action']=='create':assert old is None
        else:assert old is not None and sha(old)==row['before_sha256']
        new=None if row['action']=='delete' else (member/'after'/rel).read_bytes()
        if new is not None:assert sha(new)==row['after_sha256']
        files.append((path,old,new))
    for row in manifest['protected_original_members']:assert sha((world/row['member']).read_bytes())==row['sha256']
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM=DIM;painter=vox.Painter(vertical_bounds=(-1344,320));changed=0
    for (cx,cz,sy),g in sorted(groups.items()):
        before=np.zeros(4096,np.uint16);after=before.copy();before[g[:,0]]=g[:,1];after[g[:,0]]=g[:,2]
        changed+=cuboids(painter,(cx*16,sy*16,cz*16),before.reshape(16,16,16),after.reshape(16,16,16),names,'current_HQ_66_track_tubes_and_eight_whole_tree_moves')
    assert changed==report['counts']['changes']==890173
    painter.meta.update(root_author=True,candidate=str(candidate),native_member_actions=manifest['counts'],
        preserve_all_original40_vehicle_ids=True,full_bogie_body_coupler_geometry_proof=str(candidate/'NATIVE_FULL_CONSIST_CLEARANCE.json'),
        original_U2_siding_ID_preserved=True,playable=False)
    folder=painter.save_plan(STAGE)
    print(json.dumps(dict(civil_changes=changed,native_members=manifest['counts'],world_written=False)),flush=True)
    if not a.apply:return
    assert not list(folder.glob('applied_*'));lock=extension.acquire_world_lock();geometry=None;written=[]
    try:
        backup=folder/'native_before';backup.mkdir()
        for path,old,new in files:
            assert (path.read_bytes() if path.exists() else None)==old
            if old is not None:
                b=backup/path.relative_to(world);b.parent.mkdir(parents=True,exist_ok=True);b.write_bytes(old)
        geometry=painter.apply(STAGE,session_lock=lock)
        for path,old,new in files:
            assert (path.read_bytes() if path.exists() else None)==old
            path.parent.mkdir(parents=True,exist_ok=True)
            if new is None:path.unlink()
            else:atomic_replace(path,new)
            written.append((path,old))
        measured_sections(world,groups,names,2)
        for path,old,new in files:assert (path.read_bytes() if path.exists() else None)==new
        for row in manifest['protected_original_members']:assert sha((world/row['member']).read_bytes())==row['sha256']
        result=dict(world_written=True,geometry=geometry,complete_cells_read_back=count,native_member_actions=manifest['counts'],
            native_target_counts=manifest['target_counts'],protected_original_members_byte_identical=229,original_vehicle_ids=40,
            remapped_vehicles=6,unaffected_native_head_positions_exact=34,current_full_native_candidate_proof_sha256=sha((candidate/'NATIVE_BINARY_VERIFICATION.json').read_bytes()),
            original_complete_trees_moved=8,playable=False,pending=['actual installed native train run and visual review','final navigation and old metadata retirement'])
        (out/'APPLIED.json').write_text(json.dumps(result,indent=2),'utf8')
        print('Complete HQ railway civil and exact original native member migration verified.',flush=True)
    except BaseException:
        for path,old in reversed(written):
            if old is None:path.unlink(missing_ok=True)
            else:atomic_replace(path,old)
        if geometry is not None:
            applied=list(folder.glob('applied_*'));assert len(applied)==1
            for p in (applied[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/p.name,p.read_bytes())
            (applied[0]/'ROLLED_BACK.json').write_text('{"reason":"native member or civil readback failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
