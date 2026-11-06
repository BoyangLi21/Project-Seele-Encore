"""Root-approved eighteen-cell genuine source-car clearance patch, read only."""
from pathlib import Path
from collections import defaultdict
import argparse,json,hashlib
from query_blocks import iter_selected_sections,iter_block_entities


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--world",type=Path,required=True);a=ap.parse_args();base=a.candidate_directory.resolve()
    contacts=json.loads((base/"ACTUAL_SOURCE_CUBE_CONTACT_FRAMES.json").read_text("utf8"));types=defaultdict(set)
    for r in contacts:types[tuple(r["pos"])].add(r["part"])
    assert len(types)<=18
    selected=defaultdict(set);groups=defaultdict(list)
    for x,y,z in types:selected[x//16,z//16].add(y//16);groups[x//16,z//16,y//16].append((x,y,z))
    actual={}
    for cx,cz,sy,palette,indices in iter_selected_sections(a.world,"projectseele:geofront",selected):
        for x,y,z in groups[cx,cz,sy]:actual[x,y,z]=palette[int(indices[((y&15)<<8)|((z&15)<<4)|(x&15)])]
    lo=tuple(min(q[k] for q in types) for k in range(3));hi=tuple(max(q[k] for q in types) for k in range(3));bes={q:t.snbt() for q,t in iter_block_entities(a.world,"projectseele:geofront",lo,hi,selected_chunks=set(selected)) if q in types};assert not bes
    rows=[]
    for q,parts in sorted(types.items()):
        current=actual[q]
        if parts=={"bogie"}:
            target="minecraft:smooth_stone_slab[type=bottom,waterlogged=false]";why="new_ballast_native_real_wheel_corner_clearance";assert current in {"minecraft:stone","minecraft:gravel","minecraft:air","projectseele:nerv_wall_panel"},(q,current)
        elif current=="minecraft:smooth_stone" or q==(-278,-467,787) and current=="minecraft:stone":target="minecraft:smooth_stone_slab[type=bottom,waterlogged=false]";why="retained_west_platform_side_full_footprint_bearing_with_half_step"
        else:
            assert current in {"minecraft:stone","minecraft:dirt"} and q[0]==-278 and q[2]==787 and q[1] in (-466,-465),(q,current)
            target="minecraft:air";why="actual_car_head_side_soil_clearance_original_bearing_below_retained"
        rows.append(dict(pos=list(q),before=current,after=target,before_nbt=None,after_nbt=None,owner="Root_direct_HQ_actual_source_car_clearance",reason=why))
    result=dict(schema="projectseele.direct-hq-finite-native-clearance-r53.v1",world_written=False,cells=rows,
                selected_original_APG_or_BEs=0,original_station_horizontal_footprint_preserved=True,all_original_guard_cells_unselected=True,
                root_plan_sha256=hashlib.sha256((a.world.parent/"ROOT_SPATIAL_PLAN.json").read_bytes()).hexdigest(),pending=["fresh exact cube half-slab collision check","Root merge and apply","native riding and visual review"])
    path=base/"FINITE_CLEARANCE_CANDIDATE.json";assert not path.exists();path.write_text(json.dumps(result,indent=2)+"\n","utf8");print(json.dumps(dict(cells=len(rows),before_states=sorted(set(actual.values())),world_written=False)))


if __name__=="__main__":main()
