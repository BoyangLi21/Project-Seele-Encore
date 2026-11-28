"""Prepare exact, identity-preserving translations of the two parked GeoFront game aircraft."""

import json

import nbtlib
from geofront_field_grounds import STANDS
from map_pipeline.install.entity_moves import ENTITIES, translated, prepare
from transplant_s22_authority import read_region, parse_chunk

PARKING = "nerv_airport_r21.json"


def prepare_aircraft(world, candidate, stage):
    parking = json.loads((world / PARKING).read_text("utf8"))
    keys = [f"r21/nerv/pyramid_fighter{i}" for i in range(2)]
    configured = {s["key"]: s for s in parking["vehicles"] if s["key"] in keys}
    if set(configured) != set(keys):
        raise ValueError("The pyramid aircraft parking slots are missing")
    rows = []
    for path in (world / ENTITIES).glob("*.mca"):
        if not path.stat().st_size:
            continue
        for blob in read_region(path)[1]:
            if not blob:
                continue
            for ent in parse_chunk(blob).get("Entities", []):
                if str(
                    ent["id"]
                ) != "superbwarfare:j_16" or "seele_r21_nerv_aircraft" not in ent.get(
                    "Tags", []
                ):
                    continue
                xyz = [float(v) for v in ent["Pos"]]
                if any(
                    sum((a - b) ** 2 for a, b in zip(v["position"], xyz)) <= 12**2
                    for v in configured.values()
                ):
                    rows.append(ent)
    used = set()
    moves = []
    for key, target in zip(keys, STANDS):
        spec = configured[key]
        nearby = [
            ent
            for ent in rows
            if sum((a - float(b)) ** 2 for a, b in zip(spec["position"], ent["Pos"]))
            <= 12**2
        ]
        if len(nearby) != 1:
            raise ValueError(("Parked aircraft absent or ambiguous", key, len(nearby)))
        old = nearby[0]
        uid = tuple(map(int, old["UUID"]))
        if uid in used:
            raise ValueError("Two aircraft parking slots matched the same UUID")
        used.add(uid)
        delta = nbtlib.List[nbtlib.Double](
            [a - float(b) for a, b in zip(target, old["Pos"])]
        )
        new = translated(old, delta)
        moves.append(nbtlib.Compound({"Before": old, "After": new, "Delta": delta}))
        spec["position"] = list(target)
    candidate.mkdir(exist_ok=True, parents=True)
    stage.mkdir(exist_ok=True, parents=True)
    packet = "aircraft-moves.nbt"
    nbtlib.File({"Moves": nbtlib.List[nbtlib.Compound](moves)}).save(
        candidate / packet, gzipped=True
    )
    (stage / PARKING).write_text(
        json.dumps(parking, ensure_ascii=False, indent=2) + "\n", "utf8"
    )
    unused, verified = prepare(candidate, world, stage, {"entity_moves": packet})
    return verified
