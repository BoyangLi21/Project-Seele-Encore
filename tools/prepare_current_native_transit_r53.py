"""Read actual installed MTR bytes and prepare exact derived-only metadata patch."""
from pathlib import Path
from collections import Counter
import argparse,copy,hashlib,json,subprocess,zipfile
from prepare_complete_hq_mtr_member_patch import Parser

ROOT=Path(__file__).resolve().parents[1]


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--world",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--mtr",type=Path,required=True);ap.add_argument("--java",type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    world=a.world.resolve();folder=world/"mtr/projectseele/geofront";tables={};source={};rails=[]
    with zipfile.ZipFile(out/"ACTUAL_INSTALLED_MTR_READONLY.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for kind in ("stations","platforms","routes","sidings","depots","rails"):
            tables[kind]=[]
            for path in sorted((folder/kind).rglob("*")):
                if not path.is_file():continue
                raw=path.read_bytes();member=path.relative_to(world).as_posix();source[member]=sha(raw);record=Parser(raw).node().value;tables[kind].append(record);archive.writestr("current/"+member,raw)
                if kind=="rails":rails.append((path.name,record))
    assert [len(tables[k]) for k in ("stations","platforms","routes","sidings","depots")]==[20,38,6,6,6]
    jdk=a.java.resolve().parent;classes=out/"native_classes";classes.mkdir();classpath=str(a.mtr.resolve());javafile=ROOT/"tools/NativeInstalledMTRCurvesR53.java"
    subprocess.run([str(jdk/"javac.exe"),"-encoding","UTF-8","-cp",classpath,"-d",str(classes),str(javafile)],check=True,capture_output=True)
    output=out/"ACTUAL_NATIVE_CURVES.json"
    subprocess.run([str(a.java),"-Xmx512m","-cp",str(classes)+";"+classpath,"NativeInstalledMTRCurvesR53",str(out/"ACTUAL_INSTALLED_MTR_READONLY.zip"),str(output),".5"],check=True,capture_output=True)
    curves=json.loads(output.read_text("utf8"));assert len(curves)==len(rails) and all(c["valid"] for c in curves)
    byid={c["id"]:c for c in curves};assert set(byid)=={n for n,d in rails}
    target=world/"native_transit_r28.json";before=target.read_bytes();old=json.loads(before);result=copy.deepcopy(old)
    for kind in ("stations","platforms","routes","sidings","depots"):
        assert {r["id"] for r in tables[kind]}=={r["id"] for r in old[kind]},("Original guide object identities",kind)
    result.update(tables);result["curves"]=[dict(id=name,mode=d["transportMode"],kind="platform" if d["isPlatform"] else "siding" if d["isSiding"] else "rail",points=byid[name]["points"]) for name,d in rails]
    result["depot_paths"]=[dict(depot=d["id"],name=d["name"],path=d.get("path",[])) for d in tables["depots"]]
    result["r53_derived_provenance"]=dict(source="Actual installed MessagePack member bytes through pinned native Rail constructor and RailMath",member_sha256=source,sampling_metres=.5,mtr_sha256=sha(a.mtr.read_bytes()),native_curve_sha256=sha(output.read_bytes()),native_ride_verified=False)
    encoded=(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf8");(out/"before_native_transit_r28.json").write_bytes(before);(out/"native_transit_r28.json").write_bytes(encoded)
    all_trains=[v["id"] for s in tables["sidings"] for v in s["vehicles"]];assert len(all_trains)==len(set(all_trains))==40
    geofront_platforms=[p for p in tables["platforms"] if p["position1"]["y"]<0];hq=[p for p in geofront_platforms if p["position1"]["y"]==-560]
    assert len(hq)==3 and all(p["position1"]["y"]>=-473 for p in geofront_platforms if p not in hq)
    # No live DB member, train token or World file was touched during preparation.
    for member,digest in source.items():assert sha((world/member).read_bytes())==digest
    assert target.read_bytes()==before
    report=dict(schema="projectseele.r53.actual-native-transit-derived-only.v1",world_written=False,derived_only=True,
                target_relative_path="native_transit_r28.json",before_sha256=sha(before),after_sha256=sha(encoded),source_members=source,
                source_native_rail_count=len(rails),all_installed_curves_native_canonicalized=True,native_curve_sha256=sha(output.read_bytes()),
                original_guide_station_platform_route_depot_siding_id_sets_preserved=True,original40_train_ids_preserved=True,
                HQ_only_3_platforms_below_geofront_ground=True,other_geo_platforms_y_values=sorted({p["position1"]["y"] for p in geofront_platforms if p not in hq}),retained_other_metadata_keys=sorted(set(old)-set(tables)-{"curves","depot_paths"}),
                actual_native_platform_y_counts=dict(Counter(p["position1"]["y"] for p in tables["platforms"])),
                exact_inverse_file="before_native_transit_r28.json",exact_forward_file="native_transit_r28.json",world_or_native_DB_written=False,
                pending=["Root exact derived-only installation with world lock", "navigation rebuild bound to this current native geometry", "this-round actual train operation and native riding/visual checks"])
    (out/"PATCH_MANIFEST.json").write_text(json.dumps(report,indent=2)+"\n","utf8");print(json.dumps({k:v for k,v in report.items() if k in ("source_native_rail_count","actual_native_platform_y_counts","before_sha256","after_sha256","world_written")}),flush=True)


if __name__=="__main__":main()
