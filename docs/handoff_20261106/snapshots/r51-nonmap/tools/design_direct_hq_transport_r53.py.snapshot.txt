"""Prepare the single direct HQ descent candidate against current native records.

This tool reads MTR files and writes only an immutable review directory.
"""
from pathlib import Path
import argparse, copy, hashlib, json, zipfile
from prepare_complete_hq_mtr_member_patch import Parser

ROOT = Path(__file__).resolve().parents[1]
DIM = "projectseele:geofront"
MARKER = "mtr/projectseele/geofront/"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--world", type=Path, required=True)
    ap.add_argument("--old-design", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    old = json.loads(a.old_design.read_text("utf8"))
    old_segments = {s["id"]: s for s in old["segments"]}
    records, boundary, inputs = {}, [], []
    files = sorted((a.world / MARKER).rglob("*"))
    with zipfile.ZipFile(out / "CURRENT_MTR_READONLY.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for p in files:
            if not p.is_file():
                continue
            member = p.relative_to(a.world).as_posix()
            raw = p.read_bytes()
            d = Parser(raw).node().value
            row = dict(member=member, sha256=hashlib.sha256(raw).hexdigest(), data=d)
            records.setdefault(member.split("/")[3], []).append(row)
            archive.writestr("current/" + member, raw)
            inputs.append({k: row[k] for k in ("member", "sha256")})
    def pos(d, k):
        return [d[k][axis] for axis in ("x", "y", "z")]
    by_edge = {tuple(sorted((tuple(pos(r["data"], "position1")), tuple(pos(r["data"], "position2"))))): r for r in records["rails"]}
    for s in old["segments"]:
        row = by_edge[tuple(sorted((tuple(s["from"]), tuple(s["to"]))))]
        boundary.append(copy.deepcopy(row))
    boundary_index = {tuple(sorted((tuple(pos(row["data"], "position1")), tuple(pos(row["data"], "position2"))))): i for i, row in enumerate(boundary)}
    # Original platforms, depot and siding remain exactly where already installed.
    # Each approach's old complete chain is one semantic replacement domain.
    segments, routes, replacements = [], {}, []
    for original, names in old["routes"].items():
        first, last = old_segments[names[0]], old_segments[names[-1]]
        if original in {"original_0", "original_1", "original_7", "original_9", "original_10"}:
            continue
        rows = {
            "original_6": [([-298,-467,785],"E",[-254,-467,784],"W"), ([-254,-467,784],"E",[-66,-560,486],"W"), ([-66,-560,486],"E",[-2,-560,486],"W")],
            "original_8": [([-298,-467,785],"E",[-274,-467,785],"W"), ([-274,-467,785],"E",[-50,-560,494],"W"), ([-50,-560,494],"E",[-2,-560,494],"W")],
            "original_2": [([62,-560,486],"E",[86,-560,486],"W"), ([86,-560,486],"E",[240,-509,400],"W"), ([240,-509,400],"E",[310,-478,450],"N"), ([310,-478,450],"S",[310,-467,503],"N"), ([310,-467,503],"S",[310,-467,533],"N")],
            "original_3": [([62,-560,494],"E",[86,-560,494],"W"), ([86,-560,494],"E",[240,-509,408],"W"), ([240,-509,408],"E",[310,-478,458],"N"), ([310,-478,458],"S",[310,-467,505],"N"), ([310,-467,505],"S",[310,-467,533],"N")],
            "original_4": [([62,-560,522],"E",[86,-560,522],"W"), ([86,-560,522],"E",[296,-467,240],"S"), ([296,-467,240],"N",[296,-467,212],"S")],
            "original_5": [([62,-560,522],"E",[94,-560,522],"W"), ([94,-560,522],"E",[304,-467,240],"S"), ([304,-467,240],"N",[304,-467,212],"S")],
        }[original]
        newnames=[]
        for j, (start, heading, end, opposite) in enumerate(rows):
            s = copy.deepcopy(first)
            s.update(id="direct_"+original+"_"+str(j), **{"from":start,"to":end}, from_angle=heading, to_angle=opposite, shape="TWO_RADII", vertical_radius=100)
            s.pop("root_authorized_independent_track", None)
            s["source_original_indices"] = [boundary_index[tuple(sorted((tuple(first["from"]), tuple(first["to"]))))]]
            segments.append(s); newnames.append(s["id"])
        routes[original] = newnames
        replacements.append(dict(id=original, old_segment_ids=names, new_segment_ids=newnames,
                                 from_position=first["from"], to_position=last["to"],
                                 old_boundary_indices=[boundary_index[tuple(sorted((tuple(old_segments[n]["from"]), tuple(old_segments[n]["to"]))))] for n in names]))
    candidate = dict(schema="projectseele.direct-hq-transport-r53.v1", map_author="root", world_written=False,
                     source_world=str(a.world.resolve()), source_design=str(a.old_design.resolve()), source_design_sha256=sha(a.old_design),
                     root_plan_sha256=sha(a.world.parent / "ROOT_SPATIAL_PLAN.json"),
                     segments=segments, routes=routes, complete_chain_replacements=replacements,
                     retained_station_siding_platform_ids=True,
                     pending=["native curves", "full bogie/consist source geometry", "current block/NBT screening", "native saved progress reassembly", "Root installation", "actual train and visual check"])
    for name, value in (("CANDIDATE.json", candidate), ("CURRENT_ORDERED_BOUNDARY.json", boundary),
                        ("CURRENT_NATIVE_RECORDS.json", records), ("CURRENT_MEMBER_INPUTS.json", inputs)):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf8")
    print(json.dumps(dict(out=str(out), original_members=len(inputs), changed_approaches=len(segments), world_written=False)))


if __name__ == "__main__":
    main()
