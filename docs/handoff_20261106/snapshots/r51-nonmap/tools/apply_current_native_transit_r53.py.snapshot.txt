"""Root-only exact derived transit metadata install; MTR bytes stay identical."""
from pathlib import Path
import argparse,json,hashlib,msvcrt
import extend_world_depth_r52 as extension
from apply_s20_approved_semantic_repairs import atomic_replace


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--world",type=Path,required=True);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--apply",action="store_true");a=ap.parse_args()
    world=a.world.resolve();folder=a.candidate_directory.resolve();manifest=json.loads((folder/"PATCH_MANIFEST.json").read_text("utf8"));assert manifest["derived_only"] and manifest["target_relative_path"]=="native_transit_r28.json"
    target=world/manifest["target_relative_path"];before=(folder/manifest["exact_inverse_file"]).read_bytes();after=(folder/manifest["exact_forward_file"]).read_bytes()
    assert sha(before)==manifest["before_sha256"] and sha(after)==manifest["after_sha256"]
    def current():
        for member,digest in manifest["source_members"].items():assert sha((world/member).read_bytes())==digest,member
    assert target.read_bytes()==before;current();print(json.dumps(dict(derived_only=True,source_rails=manifest["source_native_rail_count"],before_sha256=sha(before),after_sha256=sha(after),world_written=False)),flush=True)
    if not a.apply:return
    assert not(folder/"APPLIED.json").exists();extension.WORLD=world;lock=extension.acquire_world_lock()
    try:
        assert target.read_bytes()==before;current();atomic_replace(target,after);assert target.read_bytes()==after;current()
        receipt=dict(world_written=True,derived_only=True,exact_forward_sha256=sha(after),exact_inverse_sha256=sha(before),MTR_native_member_bytes_unchanged=len(manifest["source_members"]),original_route_station_platform_depot_siding_id_sets_preserved=True,original40_train_ids_other_saved_tokens_unchanged=True,native_ride_verified=False)
        (folder/"APPLIED.json").write_text(json.dumps(receipt,indent=2)+"\n","utf8")
    except BaseException:
        if target.read_bytes()==after:atomic_replace(target,before)
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=="__main__":main()
