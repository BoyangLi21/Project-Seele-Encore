"""Token-preserving before/after patch for current HQ MessagePack records."""
from pathlib import Path
import argparse, copy, json, zipfile
from prepare_complete_hq_mtr_member_patch import Parser, patch, map_child, sha, MARKER


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--candidate-directory",type=Path,required=True);a=ap.parse_args()
    base=a.candidate_directory.resolve();out=base/"member_patch";out.mkdir(exist_ok=False)
    read=lambda name:json.loads((base/name).read_text("utf8"))
    current,target,candidate,proof,proposal=(read(n) for n in ("CURRENT_NATIVE_RECORDS.json","IN_MEMORY_NATIVE_RECORDS.json","CANDIDATE.json","NATIVE_JSON_VERIFICATION.json","PROPOSAL.json"))
    assert proof["vehicles_exact_original_identity_and_saved_state"]==40 and proof["native_reassembly_matches_expected_paths"]
    names={r["segment_id"]:MARKER+r["native_relative_path"] for r in proof["candidate_native_rail_member_names"]}
    segments={s["id"]:s for s in candidate["segments"]};boundary=read("CURRENT_ORDERED_BOUNDARY.json")
    nodes={};raws={};tails={};
    with zipfile.ZipFile(base/"CURRENT_MTR_READONLY.zip") as z:
        for name in z.namelist():
            member=name[name.index(MARKER):];raw=z.read(name);parser=Parser(raw);node=parser.node()
            nodes[member]=node;raws[member]=raw;tails[member]=raw[parser.offset:]
    targets={r["member"]:r["data"] for rows in target.values() for r in rows if not r["member"].startswith("UNINSTALLED")}
    for r in target["rails"]:
        if r["member"].startswith("UNINSTALLED"):targets[names[r["member"].split("/")[-1]]]=r["data"]
    operations=[];protected=[]
    def encode_array(old,new):
        result=[]
        whitelist={"startPosition","endPosition","startAngle","endAngle","shape","verticalRadius","savedRailBaseId","dwellTime"}
        for v in new:
            exact=next((c for c in old.children if c.value==v),None)
            if exact:result.append(exact.raw);continue
            template=next(c for c in old.children if all(c.value[k]==value for k,value in v.items() if k not in whitelist))
            trace=[];encoded=patch(template,v,trace);parsed=Parser(encoded).node()
            for k in template.value:
                if k not in whitelist:assert map_child(template,k).raw==map_child(parsed,k).raw
            result.append(encoded)
        return result
    def emit(member,before,after,trace):
        action="delete" if after is None else "create" if before is None else "modify"
        for folder,raw in (("before",before),("after",after)):
            if raw is not None:p=out/folder/member;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        operations.append(dict(action=action,target_relative_path=member,before_sha256=None if before is None else sha(before),after_sha256=None if after is None else sha(after),precise_changed_fields=trace))
    for member,node in nodes.items():
        if member not in targets:emit(member,raws[member],None,[dict(operation="retire whole old approach rail")]);continue
        v=targets[member]
        if node.value==v:protected.append(dict(member=member,sha256=sha(raws[member])));continue
        kind=member.split(MARKER)[1].split("/")[0];trace=[];overrides={}
        for key in (["path"] if kind=="depots" else ["pathSidingToMainRoute","pathMainRouteToSiding"] if kind=="sidings" else []):
            old=map_child(node,key)
            if old.value!=v[key]:overrides[key]=encode_array(old,v[key])
        encoded=patch(node,v,trace,array_overrides=overrides)+tails[member];parser=Parser(encoded);parsed=parser.node()
        assert parsed.value==v and encoded[parser.offset:]==tails[member]
        allowed={"position1","position2","angle1","angle2","shape","verticalRadius","speedLimit1","speedLimit2","signalColors"} if kind=="rails" else {"path"} if kind=="depots" else {"pathSidingToMainRoute","pathMainRouteToSiding","vehicles"}
        for key in node.value:
            if key not in allowed:assert map_child(node,key).raw==map_child(parsed,key).raw
        if kind=="sidings":
            for old,new in zip(map_child(node,"vehicles").children,map_child(parsed,"vehicles").children):
                assert old.value["id"]==new.value["id"]
                for key in old.value:
                    if key not in {"railProgress","nextStoppingIndexAto","nextStoppingIndexManual"}:assert map_child(old,key).raw==map_child(new,key).raw
        emit(member,raws[member],encoded,trace)
    for name,s in segments.items():
        member=names[name]
        if member in nodes:continue
        template=boundary[s["source_original_indices"][0]]["member"];node=nodes[template];trace=[]
        encoded=patch(node,targets[member],trace)+tails[template];parsed=Parser(encoded).node()
        allowed={"position1","position2","angle1","angle2","shape","verticalRadius","speedLimit1","speedLimit2","signalColors"}
        for key in node.value:
            if key not in allowed:assert map_child(node,key).raw==map_child(parsed,key).raw
        emit(member,None,encoded,trace)
    manifest=dict(schema="projectseele.direct-hq-member-patch-r53.v1",world_written=False,installed=False,archive=str(base/"CURRENT_MTR_READONLY.zip"),
                  operations=operations,protected_original_members=protected,target_counts={k:len(v) for k,v in target.items()},
                  counts={a:sum(r["action"]==a for r in operations) for a in ("modify","delete","create")},
                  candidate_sha256=sha((base/"CANDIDATE.json").read_bytes()),native_json_receipt_sha256=sha((base/"NATIVE_JSON_VERIFICATION.json").read_bytes()),
                  all_other_train_token_fields_identical=True,all_station_platform_depot_siding_route_ids_preserved=True,
                  complete_old_to_new_mapping=candidate["complete_chain_replacements"],pending=["native binary reassembly", "full geometry and Root installation", "actual riding and visual check"])
    (out/"PATCH_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n","utf8")
    print(json.dumps(dict(counts=manifest["counts"],protected=len(protected),world_written=False)))


if __name__=="__main__":main()
