"""Prepare finite founded piers under the reviewed lake-crossing tube floor."""
from pathlib import Path
import argparse, json, math, hashlib
import numpy as np
from query_blocks import read_box, iter_block_entities, AIR


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--world",type=Path,required=True);a=ap.parse_args();base=a.candidate_directory.resolve()
    mask=np.load(base/"COMPLETE_CIVIL_CANDIDATE/POSITIVE_MASK_EXACT_STATES.npz");names=list(mask["states"]);ghost={tuple(q):str(names[i]) for q,i in zip(mask["positions"].tolist(),mask["after"])}
    geometry=json.loads((base/"NATIVE_GEOMETRY.json").read_text("utf8"));report=json.loads((base/"COMPLETE_CIVIL_CANDIDATE/REPORT.json").read_text("utf8"));lake=np.load(report["exact_known_lake_source"]);origin=lake["origin"];after=lake["after"];palette=list(lake["palette"]);positive=lake["positive_edit_mask"]
    starts=[]
    for r in geometry:
        if r["id"] not in {"direct_original_6_1","direct_original_8_1"}:continue
        step=max(1,int(round(16*len(r["points"])/r["native_length"])))
        for v in r["points"][step//2::step]:
            x,y,z=map(math.floor,v);y-=2
            if -180<=x<=-145 and -535<=y<=-504 and 550<=z<=625:starts.append(dict(curve=r["id"],pos=[x,y,z]))
    cells={};piers=[];inherited_bearings=[];soil={"minecraft:stone","minecraft:deepslate","minecraft:dirt","minecraft:gravel","minecraft:black_concrete"}
    for start in starts:
        x,y,z=start["pos"];lo=(x-1,y-64,z-1);hi=(x+1,y,z+1);current=read_box(a.world,"projectseele:geofront",lo,hi)
        def get(q):return ghost.get(q,current[q])
        if all(get((xx,yy,zz)).partition("[")[0] in soil for xx in range(x-1,x+2) for zz in range(z-1,z+2) for yy in (y-1,y-2,y-3)):
            inherited_bearings.append(dict(start,bearing_layers=3,full_three_by_three=True,measured_source_states=sorted({current[xx,yy,zz] for xx in range(x-1,x+2) for zz in range(z-1,z+2) for yy in (y-1,y-2,y-3)}),final_ghost_states=sorted({get((xx,yy,zz)) for xx in range(x-1,x+2) for zz in range(z-1,z+2) for yy in (y-1,y-2,y-3)})))
            continue
        bearing=None
        for yy in range(y-1,y-65,-1):
            if all(current[xx,yyy,zz].partition("[")[0] in soil for xx in range(x-1,x+2) for zz in range(z-1,z+2) for yyy in (yy,yy-1,yy-2) if yyy>=lo[1]):bearing=yy;break
        assert bearing is not None,("No actual founded lake bearing",start)
        selected=[]
        for xx in range(x-1,x+2):
            for zz in range(z-1,z+2):
                for yy in range(bearing+1,y+1):
                    q=xx,yy,zz;s=get(q)
                    if s.partition("[")[0] in soil or s.startswith("projectseele:nerv_"):continue
                    assert s.startswith("minecraft:water") or s in AIR,("Foreign source under authorized tube floor",q,s)
                    d=np.asarray(q)-origin;dx,dy,dz=map(int,d)
                    assert all(d>=0) and dy<after.shape[0] and dz<after.shape[1] and dx<after.shape[2]
                    assert positive[dy,dz,dx] and str(palette[int(after[dy,dz,dx])])==current[q],("Known original lake producer under pier",q,current[q])
                    r=dict(pos=list(q),before=current[q],after="projectseele:nerv_structural_panel",before_nbt=None,after_nbt=None,owner="Root_direct_HQ_lake_tube_founded_16m_support",curve=start["curve"])
                    if q in ghost and ghost[q]!=current[q]:r["merge_before"]=ghost[q]
                    cells[q]=r;selected.append(q)
        if selected:
            assert not list(iter_block_entities(a.world,"projectseele:geofront",lo,hi))
            piers.append(dict(start,bearing_y=bearing,soil_layers=3,cells=len(selected)))
    result=dict(schema="projectseele.direct-hq-wet-bearing-r53.v1",world_written=False,piers=piers,inherited_measured_bearings=inherited_bearings,cells=list(cells.values()),
                current_exact_state_NBT_preconditions=True,known_original_lake_producer_mask=True,
                ghost_masks_to_merge=report["positive_mask_sha256"],pending=["Root merge and native actual train/visual inspection"])
    path=base/"WET_FOUNDED_SUPPORT_CANDIDATE.json";assert not path.exists();path.write_text(json.dumps(result,indent=2)+"\n","utf8")
    print(json.dumps(dict(piers=len(piers),cells=len(cells),world_written=False)))


if __name__=="__main__":main()
