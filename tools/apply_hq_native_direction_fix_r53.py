"""Root-only atomic two-member native speed-direction correction."""
from pathlib import Path
import argparse,json,hashlib,msvcrt
import extend_world_depth_r52 as extension
from apply_s20_approved_semantic_repairs import atomic_replace


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--world",type=Path,required=True);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--apply",action="store_true");a=ap.parse_args();world=a.world.resolve();folder=a.candidate_directory.resolve();m=json.loads((folder/"PATCH_MANIFEST.json").read_text("utf8"))
    assert len(m["operations"])==2 and m["no_center_geometry_or_fixtures_changed"] and m["actual_native_finite_paths_minimum_speed_kph"]==40
    assert all(r["actual_passenger_direction_limit_kph"]==40 and r["actual_opposite_forbidden_limit_kph"]==0 for r in m["actual_native_U2_flat_throat_directions"])
    files=[]
    for r in m["operations"]:
        rel=Path(r["target_relative_path"]);target=(world/rel).resolve();assert target.is_relative_to((world/"mtr/projectseele/geofront/rails").resolve())
        old=(folder/"before"/rel).read_bytes();new=(folder/"after"/rel).read_bytes();assert sha(old)==r["before_sha256"] and sha(new)==r["after_sha256"];files.append((target,old,new))
    for member,digest in m["source_members"].items():assert sha((world/member).read_bytes())==digest
    print(json.dumps(dict(world_written=False,native_members=2,actual_native_forward_kph=40,forbidden_reverse_kph=0,all_finite_path_limits_minimum_kph=40)),flush=True)
    if not a.apply:return
    assert not(folder/"APPLIED.json").exists();extension.WORLD=world;lock=extension.acquire_world_lock();written=[]
    try:
        for member,digest in m["source_members"].items():assert sha((world/member).read_bytes())==digest
        for target,old,new in files:
            assert target.read_bytes()==old;atomic_replace(target,new);written.append((target,old));assert target.read_bytes()==new
        changed={target.relative_to(world).as_posix():sha(new) for target,old,new in files}
        for member,digest in m["source_members"].items():assert sha((world/member).read_bytes())==changed.get(member,digest)
        receipt=dict(world_written=True,native_only=True,changed_members=changed,center_geometry_or_fixtures_changed=False,all_original40_train_saved_token_bytes_unchanged=True,
                     every_other_native_member_byte_identical=len(m["source_members"])-2,native_actual_passenger_direction_kph=40,native_actual_opposite_direction_kph=0,
                     pending=["refresh derived current metadata source hashes","this-round actual trip timing and native visual checks"])
        (folder/"APPLIED.json").write_text(json.dumps(receipt,indent=2)+"\n","utf8")
    except BaseException:
        for target,old in reversed(written):atomic_replace(target,old)
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=="__main__":main()
