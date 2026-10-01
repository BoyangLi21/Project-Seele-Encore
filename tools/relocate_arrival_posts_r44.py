"""Root-applicable exact relocation of the existing arrival guard and roster.

The CLI only reads the world and writes a forward/inverse review plan. Original
UUID, identity registration, health, roles, equipment and every other NBT field
are preserved. The optional apply_root function is for the sole coordinator.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import msvcrt
from datetime import datetime
from pathlib import Path

import nbtlib
from apply_s20_approved_semantic_repairs import atomic_replace
from audit_facility_transit_r44 import Geometry
from measure_world_r40 import MeasuredWorld
from transplant_s22_authority import read_region, parse_chunk, build_region, chunk_blob
from verify_main_r20 import entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/arrival_posts_v2"
ID = "guard/arrival"
FEET, YAW = (-391, -466, 736), -90.


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    if list(out.glob("applied_*/receipt.json")):
        raise RuntimeError("Applied relocation is immutable; select a new output revision")
    out.mkdir(parents=True, exist_ok=True)
    w = MeasuredWorld(world)
    w.box((-395, -467, 732), (-385, -463, 739))
    w.load()
    geometry = Geometry(w)
    if geometry.standing(FEET)["status"] != "STATIC_STANDING":
        raise RuntimeError("Guard's fixed station has no actual bearing/headroom")
    visitor = (-389, -466, 736)
    if geometry.standing(visitor)["status"] != "STATIC_STANDING":
        raise RuntimeError("Guard's two-metre visitor approach is obstructed")
    # Interaction passes over the existing one-metre counter at eye level,
    # without depending on a roster change to move an existing living actor.
    for x in (-391, -390, -389):
        state = w.get(x, -465, 736)
        boxes = geometry.boxes(state)
        if boxes is None or any(b[1] < .75 and b[4] > .5 for b in boxes):
            raise RuntimeError(("Blocked actual eye-level interaction sightline", x, state))
    all_entities = entities(world)
    found = [(uid, e) for uid, e in all_entities.items() if str(e.get("StaffId", "")) == ID]
    if len(found) != 1:
        raise RuntimeError(("Original arrival staff identity not unique", len(found)))
    uid, old = found[0]
    if old.get("Passengers") or bool(old.get("HadPendingStaffTask", False)):
        raise RuntimeError("Do not relocate an occupied actor or interrupt an active staff task")
    old = copy.deepcopy(old)
    new = copy.deepcopy(old)
    new["Pos"] = nbtlib.List[nbtlib.Double]([FEET[0] + .5, FEET[1], FEET[2] + .5])
    new["Motion"] = nbtlib.List[nbtlib.Double]([0., 0., 0.])
    new["Rotation"] = nbtlib.List[nbtlib.Float]([YAW, 0.])
    packed = ((FEET[0] & 0x3ffffff) << 38) | ((FEET[2] & 0x3ffffff) << 12) | (FEET[1] & 4095)
    new["StaffStation"] = nbtlib.Long(packed - (1 << 64) if packed >= (1 << 63) else packed)
    new["StaffStationYaw"] = nbtlib.Float(YAW)
    changed_keys = [k for k in old if old[k] != new[k]]
    assert set(changed_keys) <= {"Pos", "Motion", "Rotation", "StaffStation", "StaffStationYaw"}
    assert old["UUID"] == new["UUID"]
    roster_path = world / "nerv_staff_r15.json"
    before_bytes = roster_path.read_bytes()
    roster = json.loads(before_bytes.decode("utf8"))
    before_roster = copy.deepcopy(roster)
    posts = [s for s in roster["stations"] if s["id"] == ID]
    assert len(posts) == 1
    posts[0].update(feet=list(FEET), yaw=YAW, room="r44_arrival_service_guard")
    identity = world / "dimensions/projectseele/geofront/data/projectseele_staff_r15.dat"
    if not identity.is_file():
        identity = world / "data/projectseele_staff_r15.dat"
    if not identity.is_file():
        raise RuntimeError("No authoritative staff UUID registry")
    registered = nbtlib.load(identity)["data"]["Members"][ID]
    if tuple(map(int, registered)) != uid:
        raise RuntimeError("SavedData staff identity differs from existing actor")
    forward = {"world": str(world), "id": ID, "uuid": list(uid), "before_snbt": old.snbt(), "after_snbt": new.snbt(),
        "roster_file": "nerv_staff_r15.json", "roster_before_sha256": hashlib.sha256(before_bytes).hexdigest(),
        "roster_before": before_roster, "roster_after": roster, "identity_file": str(identity.relative_to(world)), "identity_sha256": digest(identity),
        "changed_entity_keys": changed_keys, "other_actor_count": len(all_entities) - 1,
        "position": list(map(float, new["Pos"])), "visitor_position": [-388.5, -466, 736.5],
        "native": {k: "UNVERIFIED" for k in ("actual_dialogue", "photo_fixed_floor", "reload", "installed_copy")}}
    inverse = copy.deepcopy(forward)
    inverse["before_snbt"], inverse["after_snbt"] = forward["after_snbt"], forward["before_snbt"]
    inverse["roster_before"], inverse["roster_after"] = forward["roster_after"], forward["roster_before"]
    inverse["roster_before_sha256"] = hashlib.sha256(json.dumps(roster, ensure_ascii=False, indent=2).encode("utf8")).hexdigest()
    (out / "forward.json").write_text(json.dumps(forward, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "inverse.json").write_text(json.dumps(inverse, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "roster_before.bytes").write_bytes(before_bytes)
    print("Arrival existing guard:", uid, "to", forward["position"], "keys", changed_keys, flush=True)
    return forward


def apply_root(forward, out=OUT):
    """Called only by root while Minecraft is stopped; full NBT preconditions."""
    world, out = Path(forward["world"]), Path(out)
    with (world / "session.lock").open("r+b") as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        uid = tuple(forward["uuid"])
        original = entities(world)
        old, new = nbtlib.parse_nbt(forward["before_snbt"]), nbtlib.parse_nbt(forward["after_snbt"])
        assert original[uid] == old, "Original complete actor NBT changed; refresh plan after MC closes"
        roster_path = world / forward["roster_file"]
        assert digest(roster_path) == forward["roster_before_sha256"], "Roster changed; regenerate instead of replacing concurrent posts"
        identity = world / forward["identity_file"]
        assert digest(identity) == forward["identity_sha256"]
        directory = world / "dimensions/projectseele/geofront/entities"
        regions, before_files = {}, {}
        def location(actor):
            x, z = math.floor(float(actor["Pos"][0])) // 16, math.floor(float(actor["Pos"][2])) // 16
            path, slot = directory / f"r.{x // 32}.{z // 32}.mca", (z % 32) * 32 + x % 32
            if path not in regions:
                assert path.is_file(), "Existing target entity region is required"
                before_files[path] = path.read_bytes()
                regions[path] = read_region(path)
            timestamps, blobs = regions[path]
            root = parse_chunk(blobs[slot]) if blobs[slot] else nbtlib.File({"DataVersion": copy.deepcopy(source_version), "Position": nbtlib.IntArray([x, z]), "Entities": nbtlib.List[nbtlib.Compound]()})
            return path, slot, root
        # A live original actor necessarily has its entity chunk. Its native
        # version is authoritative when the target chunk has no entities yet.
        sx, sz = math.floor(float(old["Pos"][0])) // 16, math.floor(float(old["Pos"][2])) // 16
        source_blob = read_region(directory / f"r.{sx // 32}.{sz // 32}.mca")[1][(sz % 32) * 32 + sx % 32]
        assert source_blob
        source_version = parse_chunk(source_blob)["DataVersion"]
        source, ss, a = location(old)
        rows = [e for e in a["Entities"] if tuple(map(int, e.get("UUID", []))) == uid]
        assert len(rows) == 1 and rows[0] == old
        a["Entities"].remove(rows[0])
        regions[source][1][ss] = chunk_blob(a)
        target, ts, b = location(new)
        assert not any(tuple(map(int, e.get("UUID", []))) == uid for e in b["Entities"])
        b["Entities"].append(copy.deepcopy(new))
        regions[target][1][ts] = chunk_blob(b)
        folder = out / ("applied_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        folder.mkdir(parents=True)
        roster_before = roster_path.read_bytes()
        (folder / "roster_before.bytes").write_bytes(roster_before)
        for path, data in before_files.items():
            (folder / path.name).write_bytes(data)
        try:
            for path, (timestamps, blobs) in regions.items():
                atomic_replace(path, build_region(timestamps, blobs))
            atomic_replace(roster_path, json.dumps(forward["roster_after"], ensure_ascii=False, indent=2).encode("utf8"))
            after = entities(world)
            assert original.keys() == after.keys() and after[uid] == new
            assert all(e == after[k] for k, e in original.items() if k != uid)
            assert digest(identity) == forward["identity_sha256"]
        except BaseException:
            for path, data in before_files.items():
                atomic_replace(path, data)
            atomic_replace(roster_path, roster_before)
            raise
        receipt = {"world": str(world), "uuid": uid, "other_actors_unchanged": len(original) - 1,
            "identity_unchanged": True, "blocks_changed": 0, "position": list(map(float, new["Pos"])), "verified_full_NBT": True}
        (folder / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf8")
        print(receipt, flush=True)
        return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, default=WORLD)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    plan(a.world, a.out)
