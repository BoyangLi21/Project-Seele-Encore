"""Install an already reviewed private clip and its matching bundle hash."""
import argparse
import hashlib
import json
import msvcrt
import os
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace(path, data):
    temporary = path.with_name(path.name+".r53-tmp")
    if temporary.exists():
        raise ValueError(f"Unfinished previous write: {temporary}")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--client", type=Path, required=True)
    ap.add_argument("--world", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--verification", type=Path, required=True)
    ap.add_argument("--expected-before", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    candidate = args.candidate.read_bytes()
    verification = json.loads(args.verification.read_text())
    if verification["clip_sha256"] != digest(candidate):
        raise ValueError("Native review belongs to a different clip")
    if verification["max_rotation_error_degrees"] > .05 or verification["max_final_hand_overwrite_degrees"] > .001:
        raise ValueError("Native verification failed")
    directory = args.client/"projectseele-local-maps"
    target = directory/"first_battle_r44.json"
    manifest = directory/"combat_bundle_r44.json"
    before = target.read_bytes()
    original_manifest = manifest.read_bytes()
    contract = json.loads(original_manifest)
    if digest(before) != args.expected_before or contract["files"][target.name] != digest(before):
        raise ValueError("Current delivered clip/bundle changed since review")
    old, new = json.loads(before), json.loads(candidate)
    for field in ("fps", "duration_ticks", "angel", "camera"):
        if old[field] != new[field]:
            raise ValueError(f"Unreviewed scene change: {field}")
    if old["eva"]["root_blocks"] != new["eva"]["root_blocks"]:
        raise ValueError("Unreviewed world root change")
    # A complete named backup is required; never overwrite a previous receipt.
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/target.name).write_bytes(before)
    (args.out/manifest.name).write_bytes(original_manifest)
    contract["files"][target.name] = digest(candidate)
    contract["bundle_id"] += "-paired-contacts-r53-20261020"
    updated_manifest = json.dumps(contract, ensure_ascii=False, indent=2).encode("utf-8")
    with (args.world/"session.lock").open("r+b") as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            try:
                replace(target, candidate)
                replace(manifest, updated_manifest)
                if target.read_bytes() != candidate or manifest.read_bytes() != updated_manifest:
                    raise ValueError("Delivered file readback differs")
                # Every other bundle member must still match its old declaration.
                for name, expected in contract["files"].items():
                    if digest((directory/name).read_bytes()) != expected:
                        raise ValueError(f"Bundle member failed readback: {name}")
            except BaseException:
                replace(target, before)
                replace(manifest, original_manifest)
                raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    receipt = {
        "client": str(args.client.resolve()), "world": str(args.world.resolve()),
        "before_sha256": digest(before), "after_sha256": digest(target.read_bytes()),
        "manifest_before_sha256": digest(original_manifest),
        "manifest_after_sha256": digest(manifest.read_bytes()),
        "bundle_members_verified": len(contract["files"]),
        "world_changes": [], "player_entity_task_transport_changes": [],
        "verification": verification,
    }
    (args.out/"RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
