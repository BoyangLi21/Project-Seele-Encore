"""Root-only atomic current World/HQ native-member installation.

Without --apply only a reviewable finite plan is written outside WORLD.
"""
from pathlib import Path
from collections import defaultdict
import argparse,json,hashlib,msvcrt
import numpy as np
import regional_voxels as vox
import extend_world_depth_r52 as extension
from apply_complete_hq_transport_network import measured_sections
from prepare_continuous_upright_civil_r52 import cuboids
from apply_s20_approved_semantic_repairs import atomic_replace


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--base",type=Path,required=True);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--apply",action="store_true");a=ap.parse_args()
    base=a.base.resolve();world=base/"WORLD";candidate=a.candidate_directory.resolve();final=candidate/"FINAL_CANDIDATE";out=base/"direct_HQ_transport_r53";stage="complete_direct_HQ_and_forty_original_trains"
    report=json.loads((final/"REPORT.json").read_text("utf8"));assert report["static_ready_for_Root_apply"] and report["actual_source_body_bogie_contact_count"]==0
    assert report["lake_watertight"]["six_face_water_to_air_contacts"]==0 and report["original_APG_guard_BEs_not_selected"]
    assert sha(final/"POSITIVE_MASK_EXACT_STATES.npz")==report["exact_states_mask_sha256"]
    member=Path(report["native_member_patch"]);assert sha(member)==report["native_member_patch_sha256"];manifest=json.loads(member.read_text("utf8"))
    assert sha(candidate/"express_policy/NATIVE_BINARY_VERIFICATION.json")==report["native_binary_verification_sha256"]
    assert not(out/"APPLIED.json").exists()
    mask=np.load(final/"POSITIVE_MASK_EXACT_STATES.npz");names=["UNSELECTED"]+list(mask["states"]);raw=defaultdict(list)
    for q,old,new in zip(mask["positions"],mask["before"],mask["after"]):
        x,y,z=map(int,q);raw[x//16,z//16,y//16].append((((y&15)<<8)|((z&15)<<4)|(x&15),int(old)+1,int(new)+1))
    groups={key:np.asarray(rows,np.uint16) for key,rows in raw.items()};del raw
    measured_sections(world,groups,names,1)
    files=[]
    for row in manifest["operations"]:
        rel=Path(row["target_relative_path"]);path=(world/rel).resolve();assert path.is_relative_to((world/"mtr/projectseele/geofront").resolve())
        old=path.read_bytes() if path.exists() else None
        assert (old is None if row["action"]=="create" else old is not None and hashlib.sha256(old).hexdigest()==row["before_sha256"])
        new=None if row["action"]=="delete" else (member.parent/"after"/rel).read_bytes()
        assert new is None or hashlib.sha256(new).hexdigest()==row["after_sha256"]
        files.append((path,old,new))
    for row in manifest["protected_original_members"]:assert sha(world/row["member"])==row["sha256"]
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM="projectseele:geofront";painter=vox.Painter(vertical_bounds=(-1344,320));changed=0
    for (cx,cz,sy),g in sorted(groups.items()):
        old=np.zeros(4096,np.uint16);new=old.copy();old[g[:,0]]=g[:,1];new[g[:,0]]=g[:,2]
        changed+=cuboids(painter,(cx*16,sy*16,cz*16),old.reshape(16,16,16),new.reshape(16,16,16),names,"Root_direct_HQ_complete_retirement_and_sealed_lake_interface")
    assert changed==report["changed_cells"]
    painter.meta.update(root_author=True,candidate=str(candidate),source_report_sha256=sha(final/"REPORT.json"),original40_train_saved_state_preserved=True,
                        original_station_APG_guards_preserved=True,lake_source_mask_verified=True,actual_source_cube_contacts=0,playable=False)
    folder=painter.save_plan(stage);print(json.dumps(dict(civil_changes=changed,member_actions=manifest["counts"],world_written=False)),flush=True)
    if not a.apply:return
    assert not list(folder.glob("applied_*"));lock=extension.acquire_world_lock();geometry=None;written=[]
    try:
        measured_sections(world,groups,names,1);backup=folder/"native_before";backup.mkdir()
        for path,old,new in files:
            assert (path.read_bytes() if path.exists() else None)==old
            if old is not None:q=backup/path.relative_to(world);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(old)
        geometry=painter.apply(stage,session_lock=lock)
        for path,old,new in files:
            assert (path.read_bytes() if path.exists() else None)==old;path.parent.mkdir(parents=True,exist_ok=True)
            if new is None:path.unlink()
            else:atomic_replace(path,new)
            written.append((path,old))
        measured_sections(world,groups,names,2)
        for path,old,new in files:assert (path.read_bytes() if path.exists() else None)==new
        for row in manifest["protected_original_members"]:assert sha(world/row["member"])==row["sha256"]
        result=dict(world_written=True,geometry=geometry,complete_selected_cells_read_back=report["complete_selected_cells"],native_member_actions=manifest["counts"],
                    protected_native_members_byte_identical=len(manifest["protected_original_members"]),all_original40_train_ids_other_saved_token_fields_preserved=True,
                    native_geometry_candidate_sha256=report["source_geometry_sha256"],final_report_sha256=sha(final/"REPORT.json"),
                    lake_watertight=report["lake_watertight"],finite_native_clearance_cells=report["finite_clearance_cells"],original_progress_policy="same full changed approach traversal fraction, exact unchanged local distance and head positions",
                    pending=report["pending"][1:],playable=False)
        (out/"APPLIED.json").write_text(json.dumps(result,indent=2)+"\n","utf8");print("Root direct HQ complete source/cell/member readback passed.",flush=True)
    except BaseException:
        for path,old in reversed(written):
            if old is None:path.unlink(missing_ok=True)
            else:atomic_replace(path,old)
        if geometry is not None:
            applied=list(folder.glob("applied_*"));assert len(applied)==1
            for p in (applied[0]/"before").glob("r.*.mca"):atomic_replace(world/"dimensions/projectseele/geofront/region"/p.name,p.read_bytes())
            (applied[0]/"ROLLED_BACK.json").write_text('{"reason":"direct HQ native member or current World readback failed"}',"utf8")
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=="__main__":main()
