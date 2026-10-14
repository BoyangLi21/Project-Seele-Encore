"""Prepare Root's explicit moved-headquarters bindings without writing its world.

The door source is the complete inherited r01 receipt. Only its coordinate
fields are translated; states, identities, input contracts and NBT are kept.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


def move(point: list, delta: list[int]) -> list:
    if len(point) != 3 or any(not isinstance(value, (int, float)) for value in point):
        raise ValueError("An exact coordinate triple is required")
    return [point[axis] + delta[axis] for axis in range(3)]


def prepare(source: dict, delta: list[int], epoch: int, fingerprint: str) -> tuple[dict, dict]:
    if epoch <= 0 or len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        raise ValueError("Actual claimed epoch and fingerprint required")
    if delta != [0, -93, 0]:
        raise ValueError("Root's approved headquarters translation [0,-93,0] required")
    document = copy.deepcopy(source)
    ids = {row["id"] for row in document["doors"]}
    if ids != set(range(19)) - {5, 14} or len(document["doors"]) != 17:
        raise ValueError("The inherited complete 17-door owner is required")
    for door in document["doors"]:
        door["lower"] = move(door["lower"], delta)
        for field in ("aperture", "buttons"):
            door[field] = [move(point, delta) for point in door[field]]
        contracts = door["fixedInputContractsR45"]
        if len(contracts) != len(door["buttons"]) or {row["side"] for row in contracts} != {-1, 1}:
            raise ValueError("Every inherited fixed-input contract and both door sides required")
        for contract in contracts:
            for field in ("pos", "operator"):
                contract[field] = move(contract[field], delta)
            for field in ("input_before", "fixed_support"):
                contract[field]["pos"] = move(contract[field]["pos"], delta)
    for retired in document["excludedOriginalDoors"]:
        retired["lower"] = move(retired["lower"], delta)
    document.update(schema="projectseele.r52.headquarters-command-doors.v1",
                    dimension="projectseele:geofront", component="headquarters",
                    epoch=epoch, directory_fingerprint=fingerprint,
                    headquarters_translation=delta)
    encoded = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    frame = dict(schema="projectseele.r52.headquarters-frame.v1",
                 dimension="projectseele:geofront", component="headquarters", installed=True,
                 epoch=epoch, directory_fingerprint=fingerprint, translation=delta,
                 command_door_manifest="r52/headquarters_command_doors.json",
                 command_door_sha256=hashlib.sha256(encoded).hexdigest())
    return frame, document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True, help="Read-only inherited world")
    parser.add_argument("--out", type=Path, required=True, help="Draft destination outside the world")
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--directory-fingerprint", required=True)
    parser.add_argument("--translation", type=int, nargs=3, required=True)
    args = parser.parse_args()
    world, out = args.world.resolve(), args.out.resolve()
    if out == world or world in out.parents:
        raise ValueError("This helper never writes a world; choose an external draft directory")
    source_file = world / ".projectseele_command_sliding_doors_r01.json"
    frame, doors = prepare(json.loads(source_file.read_text(encoding="utf-8-sig")),
                           args.translation, args.epoch, args.directory_fingerprint)
    destination = out / "r52"
    destination.mkdir(parents=True, exist_ok=True)
    for filename, document in (("headquarters_command_doors.json", doors), ("headquarters.json", frame)):
        (destination / filename).write_bytes((json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    receipt = dict(world_written=False, source=str(source_file),
                   source_sha256=hashlib.sha256(source_file.read_bytes()).hexdigest(),
                   doors=17, fixed_inputs=sum(len(row["buttons"]) for row in doors["doors"]), translation=args.translation,
                   epoch=args.epoch, directory_fingerprint=args.directory_fingerprint,
                   command_door_sha256=frame["command_door_sha256"])
    (out / "HEADQUARTERS_BINDING_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
