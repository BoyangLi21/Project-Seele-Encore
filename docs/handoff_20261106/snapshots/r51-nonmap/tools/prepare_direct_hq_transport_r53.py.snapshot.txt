"""Prepare direct native rail paths and original forty-train progress, never WORLD."""
from pathlib import Path
import argparse, copy, hashlib, json, shutil
from prepare_complete_hq_mtr_member_patch import Parser, patch, map_child, sha, MARKER


def pt(q):
    return tuple(q[k] for k in ("x", "y", "z")) if isinstance(q, dict) else tuple(q)


def edge(a, b): return tuple(sorted((pt(a), pt(b))))
def pos(q): return dict(zip(("x", "y", "z"), q))


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--express-policy-out",type=Path)
    a=ap.parse_args();sourcebase=a.candidate_directory.resolve();out=sourcebase
    if a.express_policy_out:
        out=a.express_policy_out.resolve();out.mkdir(parents=True,exist_ok=False)
        for name in ("CANDIDATE.json","CURRENT_NATIVE_RECORDS.json","CURRENT_NATIVE_PROBE.json","CURRENT_ORDERED_BOUNDARY.json","CURRENT_MTR_READONLY.zip"):
            shutil.copy2(sourcebase/name,out/name)
    read=lambda name:json.loads((sourcebase/name).read_text("utf8"))
    candidate, original, probe, boundary=(read(n) for n in ("CANDIDATE.json","CURRENT_NATIVE_RECORDS.json","CURRENT_NATIVE_PROBE.json","CURRENT_ORDERED_BOUNDARY.json"))
    assert not (out/"PROPOSAL.json").exists()
    segments={s["id"]:s for s in probe["candidate_native_segments"]}
    domains=candidate["complete_chain_replacements"]
    oldedge={edge(row["data"]["position1"],row["data"]["position2"]):i for i,row in enumerate(boundary)}
    oldgroup={i:d for d in domains for i in d["old_boundary_indices"]}
    def transform(path):
        changed=[]; mapping={}; spans=[];i=0
        while i<len(path):
            old=path[i]; index=oldedge.get(edge(old["startPosition"],old["endPosition"]))
            if index not in oldgroup:
                mapping[i]=[len(changed)];changed.append(copy.deepcopy(old));i+=1;continue
            d=oldgroup[index]; reverse=pt(old["startPosition"])==tuple(d["to_position"])
            assert pt(old["startPosition"])==tuple(d["to_position"] if reverse else d["from_position"]),(i,d["id"],"partial semantic chain")
            indices=list(reversed(d["old_boundary_indices"])) if reverse else d["old_boundary_indices"]
            count=len(indices);assert i+count<=len(path)
            assert [oldedge.get(edge(p["startPosition"],p["endPosition"])) for p in path[i:i+count]]==indices,(i,d["id"],"broken complete old chain")
            names=list(reversed(d["new_segment_ids"])) if reverse else d["new_segment_ids"]
            targets=[];template=path[i+count-1]
            for j,name in enumerate(names):
                s=segments[name];q=copy.deepcopy(template)
                q.update(startPosition=pos(s["to"] if reverse else s["from"]),endPosition=pos(s["from"] if reverse else s["to"]),
                         startAngle=s["to_angle"] if reverse else s["from_angle"],endAngle=s["from_angle"] if reverse else s["to_angle"],shape=s["shape"],verticalRadius=s["vertical_radius"])
                if j<len(names)-1:q.update(savedRailBaseId=0,dwellTime=0)
                targets.append(len(changed));changed.append(q)
            spans.append(dict(old_start=i,old_end=i+count,new_indices=targets,domain=d["id"],reverse=reverse))
            for k in range(i,i+count):mapping[k]=targets
            i+=count
        return changed,mapping,spans
    proposed=copy.deepcopy(original)
    blocks=[];signals={};speed_changes=[]
    if a.express_policy_out:
        oldcolors={c for row in original["rails"] for c in row["data"].get("signalColors",[])}
        for i,pair in enumerate((("original_6","original_8"),("original_2","original_3"),("original_4","original_5"))):
            color=0x534510+i
            assert color not in oldcolors
            members=[n for group in pair for n in candidate["routes"][group]]
            for n in members:signals[n]=color
            blocks.append(dict(color=color,hex_color=f"{color:06X}",shared=[candidate["routes"][pair[0]][0]],adjacent=[candidate["routes"][pair[1]][0]],members=members,reason="Native shared original station throat and conservative whole-consist opposing admission"))
    removed={boundary[i]["member"] for i in oldgroup}
    proposed["rails"]=[r for r in proposed["rails"] if r["member"] not in removed]
    for s in segments.values():
        template=boundary[s["source_original_indices"][0]]["data"];d=copy.deepcopy(template)
        d.update(position1=pos(s["from"]),position2=pos(s["to"]),angle1=s["from_angle"],angle2=s["to_angle"],shape=s["shape"],verticalRadius=s["vertical_radius"])
        # Rail owns reversePositions and compares it with PathData's traversal.
        # Limits belong to the stored from/to endpoints; do not swap them again.
        if a.express_policy_out:
            limit=40 if s["from"][1]==s["to"][1] else 160
            oldlimits=[d["speedLimit1"],d["speedLimit2"]]
            for key in ("speedLimit1","speedLimit2"):
                if d[key]>0:d[key]=limit
            d["signalColors"]=d.get("signalColors",[])+[signals[s["id"]]]
            speed_changes.append(dict(segment=s["id"],old_speed_limits_kph=oldlimits,speed_limits_kph=[d["speedLimit1"],d["speedLimit2"]],platform_throat=s["from"][1]==s["to"][1]))
        proposed["rails"].append(dict(member="UNINSTALLED_CANDIDATE/rails/"+s["id"],data=d))
    for row in proposed["depots"]:row["data"]["path"]=transform(row["data"]["path"])[0]
    for row in proposed["sidings"]:
        for key in ("pathSidingToMainRoute","pathMainRouteToSiding"):row["data"][key]=transform(row["data"][key])[0]
    original_vehicles={str(v["id"]):v for row in original["sidings"] for v in row["data"]["vehicles"]}
    plans=[]
    by_newedge={edge(s["from"],s["to"]):s for s in segments.values()}
    for siding in probe["sidings"]:
        for v in siding["vehicles"]:
            path,mapping,spans=transform(v["path"]); prefix=0
            for p in path:
                s=by_newedge.get(edge(p["startPosition"],p["endPosition"]))
                length=s["native_rail_length"] if s else p["native_rail_length"]
                if s:p["candidate_segment_id"]=s["id"]
                p.update(startDistance=prefix,endDistance=1.7976931348623157e308 if p.get("endDistance",0)>1e300 else prefix+length,native_rail_length=length)
                if p["endDistance"]<1e300:prefix+=length
            oi=v["native_current_path_index"]; old=v["path"][oi];targets=mapping[oi]
            span=next((s for s in spans if s["old_start"]<=oi<s["old_end"]),None)
            if span:
                start=v["path"][span["old_start"]]["startDistance"];end=v["path"][span["old_end"]-1]["endDistance"]
                fraction=(v["railProgress"]-start)/(end-start)
                mapped=path[targets[0]]["startDistance"]+fraction*(path[targets[-1]]["endDistance"]-path[targets[0]]["startDistance"])
                policy="Same full old approach traversal fraction, original stop and all other train state preserved"
            else:
                mapped=path[targets[0]]["startDistance"]+v["native_local_distance"];policy="Unchanged rail exact native local distance and world position"
            ato,manual=(mapping[int(v[k])][-1] for k in ("nextStoppingIndexAto","nextStoppingIndexManual"))
            affected=mapped!=v["railProgress"] or ato!=v["nextStoppingIndexAto"] or manual!=v["nextStoppingIndexManual"]
            plans.append(dict(vehicle_id=str(v["id"]),siding_id=siding["id"],affected=affected,policy=policy,old_progress=v["railProgress"],railProgress=mapped,
                              old_next_ato=v["nextStoppingIndexAto"],old_next_manual=v["nextStoppingIndexManual"],nextStoppingIndexAto=ato,nextStoppingIndexManual=manual,
                              changed_original_rail_index=old.get("changed_original_rail_index") if span else None,
                              old_native_progress_position=v["native_progress_position"],old_native_head_position=v["native_head_position"],new_expected_path=path,
                              preserved_state={k:value for k,value in original_vehicles[str(v["id"])].items() if k not in ("railProgress","nextStoppingIndexAto","nextStoppingIndexManual")},
                              logical_next_stop={k:v["path"][int(v["nextStoppingIndexAto"])][k] for k in ("savedRailBaseId","stopIndex","dwellTime")},
                              logical_next_stop_manual={k:v["path"][int(v["nextStoppingIndexManual"])][k] for k in ("savedRailBaseId","stopIndex","dwellTime")}))
    plan_by_id={p["vehicle_id"]:p for p in plans}
    for row in proposed["sidings"]:
        for v in row["data"]["vehicles"]:
            p=plan_by_id[str(v["id"])]
            for k in ("railProgress","nextStoppingIndexAto","nextStoppingIndexManual"):v[k]=p[k]
    proposal=dict(schema="projectseele.direct-hq-native-migration-r53.v1",installed=False,world_written=False,candidate_sha256=sha((out/"CANDIDATE.json").read_bytes()),
                  all_vehicles=plans,blocks=blocks,removed_old_members=sorted(removed),speed_policy_changes=speed_changes,
                  operating_diff="Complete 160/210m descent loops retired; actual station, depot and siding identities unchanged; same full-approach saved traversal fraction."+(" Moving rails60->160kph, retained flat platform throats60->40kph; original zero forbidden direction and saved4e-6 acceleration/deceleration preserved. Three independent paired native signal blocks." if a.express_policy_out else ""))
    (out/"PROPOSAL.json").write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+"\n","utf8")
    (out/"IN_MEMORY_NATIVE_RECORDS.json").write_text(json.dumps(proposed,ensure_ascii=False,indent=2)+"\n","utf8")
    print(json.dumps(dict(original_vehicle_ids=len(plans),remapped=sum(p["affected"] for p in plans),removed_rails=len(removed),new_rails=len(segments),world_written=False)))


if __name__=="__main__":main()
