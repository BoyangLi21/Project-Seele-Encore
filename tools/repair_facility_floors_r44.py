"""Plan the complete declared low plant floor and a working access gallery.

No world-writing CLI is exposed. The root coordinator is the only applicator.
The original R20 north platform has measured continuous bearing at Y=-444;
only its missing wearing surface is restored. Wet cages, moving pallets and
launch columns remain independent negative edit masks.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
from collections import Counter, deque
from pathlib import Path

import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "run/saves/SEELE_FIELD_R44_REVIEW"
OUT = ROOT / "artifacts/rebuild_r44/facility_transit_r44/low_plant_moving_walks"
FLOOR = "projectseele:nerv_floor_panel"
STRUCT = "projectseele:nerv_structural_panel"
WALL = "projectseele:nerv_wall_panel"
GLASS = "projectseele:clear_glass"
LIGHT = "projectseele:nerv_ceiling_light[hanging=true,lit=true]"
FRAME = "projectseele:nerv_machine_edge"
Y = -442


def plan(world=WORLD, out=OUT):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("complete_low_plant/applied_*/receipt.json")):
        raise RuntimeError("Stage already applied; use --out for a new revision or a separate final readback audit")
    w = MeasuredWorld(world)
    lo, hi = (-45, -468, -294), (113, -435, -32)
    w.box(lo, hi)
    w.load()
    tags = {q: copy.deepcopy(t) for q, t in iter_block_entities(world, v.DIM, lo, hi)}
    p = v.Painter()
    inverse = v.Painter()
    changes, held = {}, []
    retained_bearing = []

    # The masks are declared in the R20 factory template and retained facility
    # manifests. None is inferred from an empty voxel or a visual background.
    gallery = {(x, z) for x in range(-43, 108) for z in range(-292, -275)}
    access = {(x, z) for x in range(99, 108) for z in range(-276, -48)}
    mask = gallery | access
    ports = {(x, -49) for x in range(100, 107)}
    # The lower side aprons remain service areas outside the wet-vessel shells.
    ports |= {(x, -276) for x in range(-41, -35)}
    masks = [(cx - 20, -443, -267, cx + 20, -362, -213) for cx in (-12, 30, 72)]
    masks += [(cx - 20, -446, -56, cx + 20, 100, -16) for cx in (-12, 30, 72)]
    masks += [(89, -446, -56, 98, -364, -48), (-370, -470, 743, -350, 100, 759)]
    for box in masks:
        p.protect(box, "r44/retained_mechanical_owner")

    def protected(q):
        return any(all(box[i] <= q[i] <= box[i + 3] for i in range(3)) for box in masks)

    def pillar(x, z):
        # R20's fixed portal supports bear the hoist/roof. Their complete
        # three-by-three columns stay in the room, even when they split a view.
        return any(abs(x - px) <= 1 and abs(z - pz) <= 1
                   for px in (-34, 9, 51, 94) for pz in (-282, -250, -216))

    allowed = AIR | {FLOOR, STRUCT, WALL, GLASS, FRAME, "projectseele:nerv_wall_datum",
                     "minecraft:polished_deepslate", "minecraft:light_gray_stained_glass",
                     "minecraft:polished_basalt", "minecraft:sea_lantern",
                     "projectseele:nerv_strip_light", "minecraft:light_gray_concrete",
                     "projectseele:nerv_ceiling_light",
                     "projectseele:nerv_edge_rail", "minecraft:iron_bars"}
    def put(q, state, why):
        before = w.block(q)
        if before is None:
            raise RuntimeError(("Unmeasured", q))
        if before == state:
            if q in changes and changes[q][1] == "full_width_clearance":
                changes.pop(q)
            return
        if protected(q) or q in tags or before.startswith(("mtr:", "movingelevators:")):
            held.append({"position": q, "state": before, "desired": state,
                         "reason": "Complete NBT or mechanical negative mask"})
            return
        if before.partition("[")[0] not in allowed:
            raise RuntimeError(("Unexpected owner/material", q, before, why))
        if q in changes and changes[q][0] != state:
            if changes[q][1] != "full_width_clearance" and not (
                    changes[q][1] == "continuous_declared_finished_floor"
                    and why == "two_way_horizontal_mod_walk"):
                raise RuntimeError(("Conflicting component writes", q))
        changes[q] = (state, why)

    for x, z in sorted(mask):
        if pillar(x, z):
            continue
        rim = any((x + dx, z + dz) not in mask for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if (x, z) in gallery:
            base = w.get(x, Y - 2, z)
            if base != STRUCT:
                # The existing apron edge may already carry a supported floor,
                # but an absent or unknown foundation does not permit filling.
                if w.get(x, Y - 1, z) not in {FLOOR, "minecraft:polished_deepslate"}:
                    raise RuntimeError(("Declared slab has no measured bearing", (x, Y - 2, z), base))
        else:
            q = (x, Y - 2, z)
            if w.block(q) in AIR:
                put(q, STRUCT, "new_gallery_under_slab")
            elif w.block(q) is None:
                raise RuntimeError(("Unknown foundation", q))
            else:
                retained_bearing.append({"position": q, "state": w.block(q)})
        put((x, Y - 1, z), FLOOR, "continuous_declared_finished_floor")
        for y in range(Y, Y + 5):
            after = "minecraft:air"
            if rim and (x, z) not in ports:
                after = STRUCT if y == Y else WALL
                if Y + 1 <= y <= Y + 3 and (x + z) % 12 not in (0, 1):
                    after = GLASS
            put((x, y, z), after, "closed_envelope" if rim else "full_width_clearance")
        put((x, Y + 5, z), STRUCT, "continuous_pressure_roof")
        if not rim and ((x % 12 == 0 and z == -287) or (x == 103 and z % 12 == 0)):
            put((x, Y + 4, z), LIGHT, "ceiling_lighting")

    # This current fixed wall is the documented lower foyer/service-gallery
    # handoff, outside the lift doors/call hardware and the train APG strip.
    for x in range(100, 107):
        for y in range(Y, Y + 4):
            put((x, y, -49), "minecraft:air", "complete_foyer_service_port")
        for z in (-48, -47):
            if w.get(x, Y - 1, z) != FLOOR:
                raise RuntimeError(("Existing foyer floor changed", (x, Y - 1, z)))
            for y in (Y, Y + 1):
                if w.get(x, y, z).partition("[")[0] not in AIR:
                    raise RuntimeError(("Foyer operating path obstructed", (x, y, z)))

    # Existing bearing structure under the new access is independent of the
    # moving machinery. Tie the fixed deck to the retained full low raft using
    # sparse piers; known portal columns are preserved at their original axes.
    for z in range(-264, -60, 24):
        for x in (99, 107):
            for y in range(-467, Y - 2):
                q = (x, y, z)
                if w.block(q) in AIR:
                    put(q, STRUCT, "fixed_deck_pier")
                elif w.block(q) is None:
                    raise RuntimeError(("Unknown pier bearing", q))
                else:
                    retained_bearing.append({"position": q, "state": w.block(q)})

    moving_walks = []
    # Both MTR belts have their full two-cell width and independent pedestrian
    # bypass. Flat MTR sections deliberately have no handrail blocks. The six-
    # and ten-metre end buffers put the step-off before a turn or station wall.
    for first_x, direction, heading in ((100, True, "northbound"), (104, False, "southbound")):
        for z in range(-270, -58):
            for lane, side in ((0, "left"), (1, "right")):
                state = ("mtr:escalator_step[direction=" + str(direction).lower()
                         + ",facing=north,orientation=flat,side=" + side + ",status=true]")
                put((first_x + lane, Y - 1, z), state, "two_way_horizontal_mod_walk")
        moving_walks.append({"id": heading, "lower": [first_x, Y - 1, -270],
                             "upper": [first_x + 1, Y - 1, -59], "clear_width": 2,
                             "clear_height": 4, "flat_handrails": False,
                             "north_buffer": [-276, -271], "south_buffer": [-58, -49],
                             "status": "UNVERIFIED native animation, passenger transport and two-lane step-off"})

    walks = []
    for lane in (-1, 0, 1):
        path = [[104.5 + lane, Y, -46.5], [104.5 + lane, Y, -286.5], [-39.5, Y, -286.5]]
        walks += [{"id": f"r44/low_plant/full_width/{lane}", "path": path},
                  {"id": f"r44/low_plant/full_width/{lane}/return", "path": path[::-1]}]
    for x, z in ((-40, -289), (-40, -278), (104, -289), (104, -278)):
        path = [[104.5, Y, -46.5], [104.5, Y, -286.5], [x + .5, Y, -286.5], [x + .5, Y, z + .5]]
        walks += [{"id": f"r44/low_plant/corner/{x}/{z}", "path": path},
                  {"id": f"r44/low_plant/corner/{x}/{z}/return", "path": path[::-1]}]
    for belt in moving_walks:
        for lane in (0, 1):
            x = belt["lower"][0] + lane + .5
            path = [[x, Y, -55.5], [x, Y, -273.5]]
            if belt["id"] == "southbound":
                path.reverse()
            walks.append({"id": f"r44/low_plant/mod_walk/{belt['id']}/lane{lane}",
                          "path": path, "native_device": "MTR horizontal moving walk",
                          "requires_real_passenger_transport": True})

    v.WORLD, v.OUT = world, out
    for q, (after, why) in sorted(changes.items()):
        before = w.block(q)
        p.match((*q, *q), before, after, "r44/low_plant/" + why)
        inverse.match((*q, *q), after, before, "inverse/r44/low_plant/" + why)
    ownership = {"component": "Declared north low-plant service floor and connected fixed service gallery",
                 "north_slab": [-43, Y - 2, -292, 107, Y + 5, -276],
                 "access_gallery": [99, Y - 2, -276, 107, Y + 5, -49],
                 "source": "plan_factory_r20.py declared bearing slab; R25 blind eastern corridor retired, new route reaches a real platform",
                 "retired_design": "Unconnected lower blind corridor, superseded by one closed complete foyer-to-service-floor route",
                 "negative_edit_masks": masks, "preserved_fixed_portal_columns": True,
                 "held": held, "walk_nodes": walks, "changes": len(changes),
                 "horizontal_moving_walks": moving_walks,
                 "retained_bearing": retained_bearing,
                 "material_counts": dict(Counter(w.block(q) for q in changes)),
                 "validation": {k: "UNVERIFIED" for k in ("native_walk", "lift_operation", "visual", "reload", "final_installed_copy")},
                 "reference": {"TV": "Industrial NERV vessel/control separation; this complete service gallery is original engineering interpretation",
                               "station": "https://www.jreast.co.jp/estation/stations/900.html",
                               "wayfinding": "https://www.mlit.go.jp/common/001255403.pdf"}}
    from audit_facility_transit_r44 import Geometry
    class Overlay:
        def __init__(self):
            self.world = world
        def get(self, x, y, z):
            q = tuple(map(math.floor, (x, y, z)))
            return changes[q][0] if q in changes else w.block(q)
    candidate = Geometry(Overlay())
    expected = {(x, z) for x, z in mask if not pillar(x, z)
                and ((x, z) in ports or all((x + dx, z + dz) in mask
                     for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))))}
    standing = {q for q in expected if candidate.standing((q[0], Y, q[1]))["status"] == "STATIC_STANDING"}
    root = (104, -50)
    if root not in standing:
        raise RuntimeError(("Candidate handoff has no measured support/clearance", root))
    reached, queue = {root}, deque([root])
    while queue:
        x, z = queue.popleft()
        for q in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if q in standing and q not in reached:
                reached.add(q)
                queue.append(q)
    bad = sorted(expected - reached)
    static = {"expected_interior_cells": len(expected), "native_shape_standing_cells": len(standing),
              "connected_from_foyer": len(reached), "disconnected_or_obstructed": bad,
              "unknown_shapes": sorted(candidate.unknown),
              "scope": "Read-only candidate overlay and saved native shapes; not a live native walk or lift result"}
    ownership["candidate_static_geometry"] = static
    (out / "candidate_static_geometry.json").write_text(json.dumps(static, indent=2), encoding="utf8")
    if bad or candidate.unknown:
        raise RuntimeError(("Candidate complete floor failed", len(bad), sorted(candidate.unknown)))
    p.meta.update(ownership)
    p.save_plan("complete_low_plant")
    inverse.meta.update({"forward": "complete_low_plant", "cells": len(changes)})
    inverse.save_plan("inverse_complete_low_plant")
    (out / "contract.json").write_text(json.dumps(ownership, ensure_ascii=False, indent=2), encoding="utf8")
    (out / "preserved_block_entities.json").write_text(json.dumps([
        {"position": q, "nbt": t.snbt()} for q, t in sorted(tags.items())], ensure_ascii=False, indent=2), encoding="utf8")
    (out / "native_cases.json").write_text(json.dumps(walks, indent=2), encoding="utf8")
    print("Planned complete low plant:", len(changes), "exact cells;", len(held), "protected;", len(walks), "native paths", flush=True)
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    plan(args.world, args.out)
