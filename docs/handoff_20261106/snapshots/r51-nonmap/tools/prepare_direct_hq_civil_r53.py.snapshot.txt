"""Exact current-source direct HQ tube union and complete old tube retirement."""
from pathlib import Path
from collections import defaultdict, Counter
import argparse, gzip, hashlib, json, math
import numpy as np
from query_blocks import iter_selected_sections, chunk_statuses, iter_block_entities, read_box, AIR

DIM="projectseele:geofront"


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--world",type=Path,required=True);ap.add_argument("--candidate-directory",type=Path,required=True)
    ap.add_argument("--lake-source",type=Path,required=True);a=ap.parse_args();base=a.candidate_directory.resolve();out=base/"COMPLETE_CIVIL_CANDIDATE";out.mkdir(exist_ok=False)
    candidate=json.loads((base/"CANDIDATE.json").read_text("utf8"));source=base/"CURRENT_RETIRING_OWNED_TUBE.jsonl.gz"
    target={};expected={};owners={};old_count=0
    with gzip.open(source,"rt",encoding="utf8") as f:
        for line in f:
            r=json.loads(line);q=tuple(r["pos"]);target[q]=r["restore"];expected[q]=r["state"];owners[q]="complete_old_160_210_loop_tube_retirement";old_count+=1
    tube=base/"NEW_TUBE_INITIAL";new=[]
    with gzip.open(tube/"COMPLETE_ADMITTED_SOURCE_TARGET.jsonl.gz","rt",encoding="utf8") as f:
        for line in f:new.append(json.loads(line))
    held=json.loads((tube/"HOLDS.json").read_text("utf8"));lake=np.load(a.lake_source)
    origin=lake["origin"];shape=np.asarray(lake["after"].shape)[[2,0,1]];pal=list(lake["palette"]);after=lake["after"];mask=lake["positive_edit_mask"]
    lake_proof=[]
    for r in held:
        q=np.array(r["pos"]);d=q-origin
        assert r["before"]=="minecraft:black_concrete" and r["before_nbt"] is None
        assert np.all(d>=0) and np.all(d<shape)
        x,y,z=map(int,d);assert mask[y,z,x] and str(pal[int(after[y,z,x])])==r["before"],("exact existing lake producer mismatch",r)
        lake_proof.append(dict(pos=r["pos"],actual_state=r["before"],positive_producer_mask=True,owner="user_confirmed_southwest_square_reservoir_and_inspection_walk",target=r["after"]))
        r=dict(r);r.pop("hold");r["owner"]="Root_authorized_watertight_lake_HQ_tube_interface";new.append(r)
    for r in new:
        q=tuple(r["pos"])
        assert r["before_nbt"] is None and r["after_nbt"] is None
        if q in expected:assert expected[q]==r["before"],("current source conflict",q)
        expected[q]=r["before"];target[q]=r["after"];owners[q]=r["owner"]
    points=sorted(target);selected=defaultdict(set);groups=defaultdict(list)
    for i,(x,y,z) in enumerate(points):selected[x//16,z//16].add(y//16);groups[x//16,z//16,y//16].append(i)
    assert set(chunk_statuses(a.world,DIM,selected).values())=={"full"}
    measured={}
    for cx,cz,sy,palette,indices in iter_selected_sections(a.world,DIM,selected):
        for i in groups[cx,cz,sy]:
            x,y,z=points[i];measured[x,y,z]=palette[int(indices[((y&15)<<8)|((z&15)<<4)|(x&15)])]
    assert set(measured)==set(target)
    drifts=[dict(pos=q,expected=expected[q],actual=s) for q,s in measured.items() if s!=expected[q]]
    (out/"CURRENT_SOURCE_DRIFTS.json").write_text(json.dumps(drifts,indent=2)+"\n","utf8")
    assert not drifts,("Current cells changed after exact measurement",len(drifts))
    lo=tuple(min(q[k] for q in points) for k in range(3));hi=tuple(max(q[k] for q in points) for k in range(3))
    bes={q:t.snbt() for q,t in iter_block_entities(a.world,DIM,lo,hi,selected_chunks=set(selected)) if q in target};assert not bes,bes
    # A complete six-face test at the actual water interface catches water-to-air
    # adjacency. The tube bores may connect only to existing dry station throats.
    wet_bore=[tuple(r["pos"]) for r in new if r["role"]=="bore" and (r["before"].startswith("minecraft:water") or r["before"]=="minecraft:black_concrete")]
    leaks=[];watertight=None
    if wet_bore:
        l=tuple(min(q[k] for q in wet_bore)-2 for k in range(3));h=tuple(max(q[k] for q in wet_bore)+2 for k in range(3));near=read_box(a.world,DIM,l,h)
        def get(q):return target.get(q,near.get(q))
        for q in wet_bore:
            assert get(q) in AIR
            for axis in range(3):
                for sign in (-1,1):
                    v=list(q);v[axis]+=sign;v=tuple(v);s=get(v)
                    assert s is not None,("unknown water interface neighbor",v)
                    if s.startswith("minecraft:water") or s.startswith("projectseele:lcl"):leaks.append(dict(bore=q,adjacent=v,state=s))
        watertight=dict(wet_bore_cells=len(wet_bore),six_face_water_to_air_contacts=len(leaks),complete_read_box=[l,h])
    (out/"LAKE_INTERFACE_LEAKS.json").write_text(json.dumps(leaks,indent=2)+"\n","utf8");assert not leaks,("open lake water contact",len(leaks))
    names=sorted(set(measured.values())|set(target.values()));codes={s:i for i,s in enumerate(names)}
    changed=[q for q in points if measured[q]!=target[q]]
    np.savez_compressed(out/"POSITIVE_MASK_EXACT_STATES.npz",positions=np.asarray(points,np.int32),before=np.asarray([codes[measured[q]] for q in points],np.uint16),after=np.asarray([codes[target[q]] for q in points],np.uint16),states=np.asarray(names),positive_edit_mask=np.asarray([measured[q]!=target[q] for q in points],bool))
    for name,which,reverse in (("COMPLETE_SOURCE_AND_TARGET.jsonl.gz",points,False),("EXACT_CHANGES.jsonl.gz",changed,False),("EXACT_INVERSE.jsonl.gz",list(reversed(changed)),True)):
        with gzip.open(out/name,"wt",encoding="utf8") as f:
            for q in which:
                old,newstate=(target[q],measured[q]) if reverse else (measured[q],target[q])
                f.write(json.dumps(dict(pos=q,before=old,after=newstate,before_nbt=None,after_nbt=None,owner=owners[q]))+"\n")
    report=dict(schema="projectseele.direct-hq-civil-r53.v1",world_written=False,installation_ready_for_Root_static_review=True,
                candidate_sha256=sha(base/"CANDIDATE.json"),native_geometry_sha256=sha(base/"NATIVE_GEOMETRY.json"),
                original_loop_cells_reviewed=old_count,new_full_width_tube_cells=len(new),complete_selected_cells=len(points),changes=len(changed),
                all_original_current_state_NBT_preconditions_measured=True,all_selected_BEs=0,positive_mask_sha256=sha(out/"POSITIVE_MASK_EXACT_STATES.npz"),
                protected_station_HQ_component_counts=json.loads((tube/"REPORT.json").read_text("utf8"))["protected_counts"],
                exact_known_lake_source=str(a.lake_source.resolve()),exact_known_lake_source_sha256=sha(a.lake_source),lake_interface_cells=len(lake_proof),lake_watertight=watertight,
                root_plan_sha256=sha(a.world.parent/"ROOT_SPATIAL_PLAN.json"),forward_sha256=sha(out/"EXACT_CHANGES.jsonl.gz"),inverse_sha256=sha(out/"EXACT_INVERSE.jsonl.gz"),
                pending=["native all body/bogie and paired-track geometry", "founded wet-interface support", "Root atomic installation", "actual native train run and visual review"])
    (out/"LAKE_POSITIVE_PRODUCER_PROOF.json").write_text(json.dumps(lake_proof,indent=2)+"\n","utf8")
    (out/"REPORT.json").write_text(json.dumps(report,indent=2)+"\n","utf8");print(json.dumps({k:v for k,v in report.items() if k in ("changes","original_loop_cells_reviewed","new_full_width_tube_cells","complete_selected_cells","lake_watertight","lake_interface_cells")}),flush=True)


if __name__=="__main__":main()
