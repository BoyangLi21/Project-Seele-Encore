"""Root-only exact city delta replay with immutable inputs and full NBT checks."""
from pathlib import Path
from collections import defaultdict
import argparse
import gzip
import hashlib
import json

import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from release_combat_r36 import guard

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    assert args.name.replace("_", "").isalnum()
    guard()
    contract = json.loads(args.contract.read_text(encoding="utf8"))
    plan = Path(contract["plan"])
    assert contract["root_may_apply_to_single_review_world"] and contract["static_full_component_passed"]
    assert contract["exact_current_preconditions_passed"] and not contract["exact_errors"]
    frozen = []
    for name, row in contract["files"].items():
        path = Path(row["path"])
        assert path.is_file() and sha(path) == row["sha256"], ("Frozen file changed", name)
        frozen.append(name)
    epochs = contract.get("source_epochs", [])
    for row in epochs:
        path = Path(row["path"])
        assert row.get("immutable_snapshot") and path.is_file() and sha(path) == row["sha256"], ("Immutable source epoch changed", path)
    retained_path = plan / "retained_full_block_entities.json"
    retained_epoch = next((Path(row["path"]) for row in epochs if Path(row.get("original_path", "")).resolve() == retained_path.resolve()), None)
    if retained_epoch is None:
        assert any(Path(row["path"]).resolve() == retained_path.resolve() for row in contract["files"].values()), "Retained NBT file not bound by frozen contract"
        retained_epoch = retained_path
    retained = json.loads(retained_epoch.read_text(encoding="utf8"))
    forward = [json.loads(line) for line in gzip.open(plan / "forward.jsonl.gz", "rt", encoding="utf8")]
    inverse = [json.loads(line) for line in gzip.open(plan / "inverse.jsonl.gz", "rt", encoding="utf8")]
    assert len(forward) == len(inverse) == len({tuple(r["pos"]) for r in forward})
    by_inverse = {tuple(r["pos"]): r for r in inverse}
    world = MeasuredWorld(WORLD)
    for row in forward:
        point = tuple(row["pos"])
        back = by_inverse[point]
        assert (row["before"], row["after"], row.get("before_nbt"), row.get("after_nbt")) == (back["after"], back["before"], back.get("after_nbt"), back.get("before_nbt")), point
        world.box(point, point)
    for row in retained:
        world.box(tuple(row["pos"]), tuple(row["pos"]))
    world.load()
    all_positions = [r["pos"] for r in forward] + [r["pos"] for r in retained]
    lo = tuple(min(p[i] for p in all_positions) for i in range(3))
    hi = tuple(max(p[i] for p in all_positions) for i in range(3))
    tags = dict(iter_block_entities(WORLD, v.DIM, lo, hi, selected_chunks=set(world.selected)))
    before_tags = {str(q): t.snbt() for q, t in tags.items()}
    for row in retained:
        assert before_tags.get(str(tuple(row["pos"]))) == row["full_snbt"], ("Retained full component NBT changed", row["pos"])
    errors = []
    groups = defaultdict(list)
    for row in forward:
        point = tuple(row["pos"])
        nbt = tags[point].snbt() if point in tags else None
        if world.block(point) != row["before"] or nbt != row.get("before_nbt"):
            errors.append(dict(pos=point, expected=row["before"], actual=world.block(point), nbt_matches=nbt == row.get("before_nbt")))
        # This installer deliberately handles static no-BE deltas only.
        assert row.get("before_nbt") is None and row.get("after_nbt") is None, ("Use full-NBT component installer", point)
        x, y, z = point
        groups[(x//16, y, z, row["before"], row["after"], row["owner"])].append(x)
    out = plan / "root_install"
    out.mkdir(exist_ok=True)
    proof = dict(contract=str(args.contract.resolve()), contract_sha256=sha(args.contract), verified_frozen_files=len(frozen),
                 verified_immutable_source_epochs=len(epochs), retained_contract_full_block_entities=len(retained),
                 cells=len(forward), selected_chunks=len(world.selected), retained_full_block_entities=len(tags),
                 current_precondition_errors=errors, complete_inverse_verified=True, world_written=False,
                 native_passed=False, art_passed=False)
    (out / "root_preflight.json").write_text(json.dumps(proof, indent=2), encoding="utf8")
    assert not errors, errors[:8]
    print(json.dumps({k: proof[k] for k in ("verified_frozen_files", "cells", "selected_chunks", "retained_full_block_entities")}))
    if not args.apply:
        return
    assert not list((out / args.name).glob("applied_*/receipt.json")), "Already applied; never replay a delta"
    (out / "retained_full_block_entities_before.json").write_text(json.dumps(before_tags, ensure_ascii=False, indent=2), encoding="utf8")
    v.WORLD, v.OUT = WORLD, out
    painter = v.Painter()
    for (_, y, z, before, after, owner), xs in sorted(groups.items()):
        xs.sort();start = previous = xs[0]
        for x in xs[1:] + [xs[-1]+2]:
            if x != previous+1:
                painter.match((start,y,z,previous,y,z), before, after, owner)
                start = x
            previous = x
    painter.meta.update(proof)
    painter.apply(args.name)
    after_tags = {str(q): t.snbt() for q,t in iter_block_entities(WORLD,v.DIM,lo,hi,selected_chunks=set(world.selected))}
    assert before_tags == after_tags, "Unchanged full block-entity content mismatch"
    verify = MeasuredWorld(WORLD)
    verify.selected = world.selected.copy();verify.load()
    bad = [row["pos"] for row in forward if verify.block(row["pos"]) != row["after"]]
    assert not bad, bad[:8]
    proof.update(world_written=True, actual_cells_read_back=len(forward), retained_full_block_entities_equal=True)
    (out / "root_actual_readback.json").write_text(json.dumps(proof, indent=2), encoding="utf8")
    print("Complete exact delta and all local full block entities read back; native/art still pending")


if __name__ == "__main__":
    main()
