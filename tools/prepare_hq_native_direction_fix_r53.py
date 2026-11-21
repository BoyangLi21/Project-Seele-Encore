"""Correct two native stored-endpoint speed assignments without moving any rail."""
from pathlib import Path
import argparse,copy,hashlib,json,subprocess
from prepare_complete_hq_mtr_member_patch import Parser,patch,map_child


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--world",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);ap.add_argument("--java",type=Path,required=True);ap.add_argument("--classpath",required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    tables={};sources={};operations=[];keys={frozenset(((296,-467,240),(296,-467,212))),frozenset(((304,-467,240),(304,-467,212)))}
    for path in sorted((a.world/"mtr/projectseele/geofront").rglob("*")):
        if not path.is_file():continue
        raw=path.read_bytes();parser=Parser(raw);node=parser.node();d=node.value;member=path.relative_to(a.world).as_posix();sources[member]=sha(raw);kind=member.split("/")[3]
        if kind=="rails" and frozenset(tuple(d[k][axis] for axis in ("x","y","z")) for k in ("position1","position2")) in keys:
            value=copy.deepcopy(d);value["speedLimit1"],value["speedLimit2"]=value["speedLimit2"],value["speedLimit1"];assert sorted((value["speedLimit1"],value["speedLimit2"]))==[0,40]
            trace=[];encoded=patch(node,value,trace)+raw[parser.offset:];parsed=Parser(encoded).node()
            for key in d:
                if key not in ("speedLimit1","speedLimit2"):assert map_child(node,key).raw==map_child(parsed,key).raw
            for folder,data in (("before",raw),("after",encoded)):
                p=out/folder/member;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            operations.append(dict(target_relative_path=member,before_sha256=sha(raw),after_sha256=sha(encoded),precise_fields=trace));d=value
        tables.setdefault(kind,[]).append(dict(member=member,data=d))
    assert len(operations)==2
    native=out/"IN_MEMORY_NATIVE_RECORDS.json";native.write_text(json.dumps(tables,ensure_ascii=False,indent=2)+"\n","utf8")
    output=out/"ACTUAL_NATIVE_SPEED_LIMITS.json";subprocess.run([str(a.java),"-cp",a.classpath,"NativeDirectHQOperatingR53",str(native),str(output)],check=True,capture_output=True)
    operating=json.loads(output.read_text("utf8"));limits=[p["actual_native_limit_kph"] for s in operating["actual_native_operating_paths"] for p in s["actual_native_path"]];assert min(limits)>=40 and max(limits)==160
    directions=operating["actual_native_U2_flat_throat_directions"];assert len(directions)==2 and all(d["actual_passenger_direction_limit_kph"]==40 and d["actual_opposite_forbidden_limit_kph"]==0 for d in directions)
    for member,digest in sources.items():assert sha((a.world/member).read_bytes())==digest
    result=dict(schema="projectseele.r53.native-stored-endpoint-direction-fix.v1",world_written=False,operations=operations,source_members=sources,
                no_center_geometry_or_fixtures_changed=True,no_original_vehicle_or_route_progress_token_changed=True,
                all_original_native_members_except_two_speed_assignments_byte_identical=True,
                actual_native_finite_paths_minimum_speed_kph=min(limits),actual_native_finite_paths_maximum_speed_kph=max(limits),actual_native_U2_flat_throat_directions=directions,native_speed_receipt_sha256=sha(output.read_bytes()),
                root_cause="Redundant direction swap before native Rail reversePositions handling; PathData clamped cached zero limit to1 km/h.",
                pending=["Root atomic two-member installation", "refresh native_transit metadata member hashes", "actual live native trip timing"])
    (out/"PATCH_MANIFEST.json").write_text(json.dumps(result,indent=2)+"\n","utf8");print(json.dumps(dict(two_members=len(operations),actual_native_limits=sorted(set(limits)),geometry_changed=False,world_written=False)))


if __name__=="__main__":main()
