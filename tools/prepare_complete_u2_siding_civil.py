"""Prepare Root-authorized U2 depot tunnel and 3m staff handoff; no WORLD writes."""
from pathlib import Path
import argparse,gzip,json,hashlib
from collections import Counter
from query_blocks import read_box,iter_block_entities

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    if a.out.exists():raise ValueError('Use a fresh candidate directory')
    a.out.mkdir(parents=True)
    lo=(-166,-563,517);hi=(-13,-554,532)
    actual=read_box(a.world,'projectseele:geofront',lo,hi)
    guard=read_box(a.world,'projectseele:geofront',(-12,-559,527),(-12,-559,529))
    bes=list(iter_block_entities(a.world,'projectseele:geofront',lo,(-12,-554,532)))
    if bes:raise ValueError('Unexpected block entity in approved tunnel/three-guard footprint')
    desired={};owners={}
    for x in range(lo[0],hi[0]+1):
        for y in range(lo[1],hi[1]+1):
            for z in range(lo[2],hi[2]+1):
                q=x,y,z
                # Bed, two-meter north lining, three-meter south lining and
                # west buffer are one declared underground structural component.
                solid=x==-166 or z<=518 or z>=530 or y<=-562 or y==-554
                state='projectseele:nerv_structural_panel'if solid else'minecraft:air';owner='u2_depot_complete_shell'if solid else'u2_depot_declared_train_or_staff_clearance'
                if y==-561:
                    state='projectseele:nerv_structural_panel';owner='u2_depot_continuous_bed'
                    if x>=-165 and 521<=z<=523:state='minecraft:gravel';owner='u2_depot_original_axis_ballast'
                if x>=-165 and 527<=z<=529 and y==-560:state='minecraft:smooth_stone';owner='u2_depot_three_metre_staff_floor'
                if x>=-165 and z==526 and y==-559:state='projectseele:nerv_edge_rail[east=false,north=true,south=false,west=false]';owner='u2_depot_rail_staff_boundary'
                if x>=-165 and z in [520,528]and y==-554 and (x+160)%12 in [0,1,2]:state='projectseele:nerv_strip_light[lit=true]';owner='u2_depot_embedded_roof_light'
                desired[q]=state;owners[q]=owner
    for z in [527,528,529]:
        q=-12,-559,z;expected='projectseele:nerv_edge_rail[east=false,north=false,south=false,west=true]'
        if guard[q]!=expected:raise ValueError(('HQ original west staff boundary changed',q,guard[q]))
        desired[q]='minecraft:air';owners[q]='u2_staff_handoff_to_original_HQ_platform';actual[q]=guard[q]
    foreign=[dict(pos=list(q),state=s)for q,s in actual.items()if q[0]<=-13 and s!='minecraft:stone']
    if foreign:raise ValueError(('Unapproved target state; no blanket excavation',foreign[:10]))
    rows=[dict(pos=list(q),before=actual[q],after=desired[q],before_nbt=None,after_nbt=None,owner=owners[q])for q in sorted(desired)]
    with gzip.open(a.out/'COMPLETE_SOURCE_AND_TARGET.jsonl.gz','wt',encoding='utf-8')as f:
        for row in rows:f.write(json.dumps(row)+'\n')
    with gzip.open(a.out/'EXACT_CHANGES.jsonl.gz','wt',encoding='utf-8')as f:
        for row in rows:
            if row['before']!=row['after']:f.write(json.dumps(row)+'\n')
    with gzip.open(a.out/'EXACT_INVERSE.jsonl.gz','wt',encoding='utf-8')as f:
        for row in reversed(rows):
            if row['before']!=row['after']:f.write(json.dumps(dict(row,before=row['after'],after=row['before']))+'\n')
    report=dict(schema='projectseele.complete-map.U2-siding-civil.candidate.v1',world_written=False,authorization='Root explicit U2 full component -93 and tunnel X[-166,-13] Y[-563,-554] Z[517,532], walkZ527..529 foot-559, three westHQ edge-rail openings; original APG/rail-side guards/boards protected',source_world=str(a.world.resolve()),bounds=[lo,hi],exact_changed_cells=sum(r['before']!=r['after']for r in rows),complete_component_cells=len(rows),after_states=dict(Counter(desired.values())),original_mtr_siding='DF5FECA5A69869EA',native_rail_axis_y=-560,staff_floor_y=-560,staff_feet_y=-559,staff_width_z=[527,529],rail_clear_cavity_z=[519,525],rail_clear_cavity_y=[-560,-555],staff_handoff_three_cells=[[-12,-559,z]for z in [527,528,529]],source_BEs=0,protected_hq='Every HQ cell X>=-12 except the three precise declared edge-rail cells; original Z524 APG, Z526 rail-side guard, high station board remain byte/state untouched',player_width_height_test='Three-metre full-width floor with 5m clear height, level into proven existing HQ floor; no crossing live track',limits=['Original source railbed retirement and lake terrain handled by separate complete owner masks','MTR64 member installation is separate and must be coordinated with physical tunnel completion','Native model whole-car/actual visual check must precede final delivery'])
    report['exact_changes_sha256']=hashlib.sha256((a.out/'EXACT_CHANGES.jsonl.gz').read_bytes()).hexdigest()
    (a.out/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({k:report[k]for k in ['world_written','exact_changed_cells','complete_component_cells','bounds','source_BEs']},ensure_ascii=False))

if __name__=='__main__':main()
