"""Retire the whole unused south flange; preserve the real middle lift lobby."""
from __future__ import annotations
import argparse,collections,copy,gzip,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha,jsonl
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from prepare_school_hakone_native_r45 import ActualGeometry
from prepare_b2_stair_component_r45 import full_body_status
from verify_main_r20 import entities

RAIL='projectseele:nerv_edge_rail[east=false,north=false,south=true,west=false]'
CIVIL={'projectseele:nerv_floor_panel','projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:clear_glass'}

def main(out):
    out=out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    expected={r['relative']:r['sha256']for r in read(BASELINE)['files']};assert len(expected)==1736
    def inventory():
        files={p.relative_to(WORLD).as_posix():sha(p)for p in WORLD.rglob('*')if p.is_file()};assert files==expected;return files
    before=inventory();m=MeasuredWorld(WORLD);m.box((87,-447,-58),(116,-385,-32));m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(87,-447,-58),(116,-385,-32)));original=ActualGeometry(m);assert RAIL in original.shapes
    contract=read(WORLD/'spatial_contract_r21.json');section=next(r for r in contract['sections']if r['id']=='factory_middle')
    assert section['floor']==-395 and [89,113,-49,-42]in section['rects']and [95,113,-275,-42]in section['rects']
    changes={}
    for x in range(90,114):
        for y in range(-396,-387):
            q=x,y,-42;old=m.block(q);assert q not in tags and old in CIVIL,(q,old)
            changes[q]=dict(pos=list(q),before=old,after='minecraft:air',before_nbt=None,after_nbt=None,owner='r45/middle_lift_lobby/retire_complete_unused_south_flange')
    for x in range(90,113):
        q=x,-394,-43;assert m.block(q)in AIR and q not in tags and original.boxes((x,-395,-43))==[[0.,0.,0.,1.,1.,1.]]
        changes[q]=dict(pos=list(q),before=m.block(q),after=RAIL,before_nbt=None,after_nbt=None,owner='r45/middle_lift_lobby/supported_open_waiting_boundary')
    assert len(changes)==239
    # The real entry, outside input and delivered measured handoff stay north
    # of the edited boundary. The old wall is not used as design authority.
    protected={(x,y,z)for x in range(89,100)for y in range(-447,-363)for z in range(-56,-44)}
    assert not set(changes)&protected
    occupied=[]
    for uid,tag in entities(WORLD).items():
        if 'Pos'not in tag:continue
        x,y,z=map(float,tag['Pos'])
        if 89.7<=x<=114.3 and -397<=y<=-386 and -42.3<=z<=-40.7:occupied.append(dict(UUID=list(uid),full_nbt=tag.snbt()))
    assert not occupied,'Preserve saved people/vehicles before retiring their bearing'
    posts=read(WORLD/'nerv_staff_r15.json')['stations'];assert not [r for r in posts if 89.7<=r['feet'][0]<=114.3 and -397<=r['feet'][1]<=-386 and -42.3<=r['feet'][2]<=-40.7]
    walk=read(WORLD/'quality_walk_cases.json');endpoint_conflicts=[]
    for row in walk:
        points=row.get('path')or[row.get('start'),row.get('end')]
        if any(p is not None and 89.7<=p[0]<=114.3 and -397<=p[1]<=-390 and -42.3<=p[2]<=-40.7 for p in points):endpoint_conflicts.append(row)
    assert not endpoint_conflicts,'Original registered target must receive an explicit successor'
    class Image:
        world=WORLD
        def block(self,q):return changes.get(tuple(q),{}).get('after',m.block(q))
        def get(self,x,y,z):return self.block(tuple(map(math.floor,(x,y,z))))
    candidate=ActualGeometry(Image());approaches=[]
    for x in range(90,113):
        p=[x+.5,-394,-42.5];a=[x+.5,-394,-40.5]
        assert candidate.standing(p)=='STATIC_STANDING'and full_body_status(candidate,p)=='CLEAR'
        assert full_body_status(candidate,p,a)=='BODY_OBSTRUCTION','No opening onto the lower cavern'
        approaches.append(dict(edge_foot=p,candidate_supported=True,candidate_full_body_CLEAR=True,outward_full_body_blocked=True,native_press=False))
    # Entire two rows behind the boundary remain clear, including every side.
    corridor=[]
    for x in range(90,113):
        for z in(-45,-44,-43):
            p=[x+.5,-394,z+.5];status=full_body_status(candidate,p);assert status=='CLEAR',(p,status)
            corridor.append(dict(feet=p,full_body=status,floor_state=m.block((x,-395,z))))
    assert m.block((105,-391,-42))=='projectseele:clear_glass'and Image().block((105,-391,-42))=='minecraft:air'
    after_contract=copy.deepcopy(contract);changed=next(r for r in after_contract['sections']if r['id']=='factory_middle')
    changed['rects']=[[95,113,-275,-43],[89,113,-49,-43],[86,113,-271,-259]]
    changed['south_end_role']='Complete lift waiting area; original call/entry north-west, south supported observation boundary, no door to empty cavern'
    changed['supported_overlooks']=[dict(x=[90,112],z=-43,feet=-394,rail_state=RAIL,through_route=False)]
    after=inventory();assert before==after;out.mkdir();forward=[changes[q]for q in sorted(changes)];inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in forward]
    for name,rows in [('forward.jsonl.gz',forward),('inverse.jsonl.gz',inverse),('positive_edit_mask.jsonl.gz',[r['pos']for r in forward])]:jsonl(out/name,rows)
    jsonl(out/'whole_component_before_state_NBT.jsonl.gz',[dict(pos=[x,y,z],state=m.block((x,y,z)),full_nbt=tags[x,y,z].snbt()if(x,y,z)in tags else None)for x in range(88,115)for y in range(-397,-386)for z in range(-51,-40)])
    jsonl(out/'source1736_before_after.jsonl.gz',[dict(relative=k,before_sha256=v,after_sha256=after[k])for k,v in sorted(before.items())])
    write(out/'all23_full_boundary_and69_waiting_cells.json',dict(boundary=approaches,waiting=corridor));write(out/'original_BE_full_NBT_retained.json',[dict(pos=q,full_nbt=t.snbt())for q,t in tags.items()])
    (out/'spatial_contract_r21.before.json').write_bytes((WORLD/'spatial_contract_r21.json').read_bytes());write(out/'spatial_contract_r21.after.json',after_contract)
    write(out/'static_metadata_reversible_proposal.json',dict(target='spatial_contract_r21.json',before_sha256=sha(WORLD/'spatial_contract_r21.json'),before_file=str(out/'spatial_contract_r21.before.json'),after_file=str(out/'spatial_contract_r21.after.json'),after_sha256=sha(out/'spatial_contract_r21.after.json'),derivative_navigation_installed=False))
    write(out/'report.json',dict(source_world=str(WORLD),source1736_SHA_unchanged=True,complete_flange_removed216=True,supported_boundary23=True,changes239=True,user_complaint_point_before='projectseele:clear_glass',user_complaint_point_after='minecraft:air',actual_same_floor_targets='Existing compact lift call/arrival and western crew circulation retained; no same-level destination or saved actor/registered endpoint beyond south flange',
        complete_original_lift_capture_threshold_input_handoff_untouched=True,saved_actors_posts_and_registered_walk_endpoints_untouched=True,all_BE_full_NBT_preserved=True,new69_waiting_body_cells_CLEAR=True,all23_boundary_outward_body_sweeps_blocked=True,
        rationale='Purpose-based lobby contraction and entire over-tall gable retirement after user visual obstruction complaint. Existing old wall/template is not treated as proof of suitability.',native_walk_or_visual_accepted=False,installed=False,world_written=False,Java_Gradle_MC_started=False,model_changed=False,forward_sha256=sha(out/'forward.jsonl.gz'),inverse_sha256=sha(out/'inverse.jsonl.gz')))
    print('Prepared whole middle lift waiting flange239 and reversible semantic contract; no world/source/model writes.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
