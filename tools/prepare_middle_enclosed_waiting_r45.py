"""Whole retracted industrial observation window; source read-only."""
from pathlib import Path
import collections,copy,difflib,gzip,json,math,sys
sys.dont_write_bytecode=True
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha,jsonl
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from prepare_school_hakone_native_r45 import ActualGeometry
from prepare_b2_stair_component_r45 import full_body_status
from verify_main_r20 import entities
OUT=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/middle_lift_waiting_enclosed_v2'
STRUCT='projectseele:nerv_structural_panel';WALL='projectseele:nerv_wall_panel';GLASS='projectseele:clear_glass';FLOOR='projectseele:nerv_floor_panel'
FRAMES=(90,96,104,112)
def window_state(x,y):return STRUCT if x in FRAMES or y==-389 else WALL if y==-394 else GLASS
def main():
    assert not OUT.exists();expected={r['relative']:r['sha256']for r in read(BASELINE)['files']};assert len(expected)==1736
    def inventory():
        actual={p.relative_to(WORLD).as_posix():sha(p)for p in WORLD.rglob('*')if p.is_file()};assert actual==expected;return actual
    before=inventory();m=MeasuredWorld(WORLD);m.box((87,-447,-58),(116,-385,-32));m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(87,-447,-58),(116,-385,-32)));changes={}
    for x in range(90,114):
        for y in range(-396,-387):
            q=x,y,-42;old=m.block(q);assert old in {STRUCT,WALL,GLASS,FLOOR} and q not in tags
            changes[q]=dict(pos=list(q),before=old,after='minecraft:air',before_nbt=None,after_nbt=None,owner='r45/middle_lift_lobby/retire_complete_unused_south_flange')
    for x in range(90,113):
        for y in range(-394,-388):
            q=x,y,-43;assert m.block(q)in AIR and q not in tags;assert m.block((x,-395,-43))==FLOOR and m.block((x,-388,-43))==STRUCT
            changes[q]=dict(pos=list(q),before=m.block(q),after=window_state(x,y),before_nbt=None,after_nbt=None,owner='r45/middle_lift_lobby/enclosed_industrial_observation_boundary')
    assert len(changes)==354
    protected={(x,y,z)for x in range(89,100)for y in range(-447,-363)for z in range(-56,-44)};assert not protected&set(changes)
    assert not [t for t in entities(WORLD).values()if 'Pos'in t and 89.7<=float(t['Pos'][0])<=114.3 and -397<=float(t['Pos'][1])<=-386 and -42.3<=float(t['Pos'][2])<=-40.7]
    assert not [r for r in read(WORLD/'nerv_staff_r15.json')['stations']if 89.7<=r['feet'][0]<=114.3 and -397<=r['feet'][1]<=-386 and -42.3<=r['feet'][2]<=-40.7]
    walk=read(WORLD/'quality_walk_cases.json')
    assert not [r for r in walk if any(p is not None and 89.7<=p[0]<=114.3 and -397<=p[1]<=-390 and -42.3<=p[2]<=-40.7 for p in (r.get('path')or[r.get('start'),r.get('end')]))]
    class Image:
        world=WORLD
        def block(self,q):return changes.get(tuple(q),{}).get('after',m.block(q))
        def get(self,x,y,z):return self.block(tuple(map(math.floor,(x,y,z))))
    old=ActualGeometry(m);new=ActualGeometry(Image());body=[];edges=[]
    for x in range(90,113):
        for z in (-46,-45,-44):
            feet=[x+.5,-394,z+.5];assert old.standing(feet)==new.standing(feet)=='STATIC_STANDING';assert full_body_status(old,feet)==full_body_status(new,feet)=='CLEAR';body.append(dict(feet=feet,original_and_candidate_full0_6x1_8_CLEAR=True,floor_state=m.block((x,-395,z))))
        a=[x+.5,-394,-43.5];b=[x+.5,-394,-40.5];assert full_body_status(new,a,b)=='BODY_OBSTRUCTION';edges.append(dict(start=a,outward=b,candidate_full_body_blocked=True))
    # Same-plane full-width stepping, not merely isolated standing samples.
    sweeps=[]
    for x in range(90,113):
        for z in (-46,-45,-44):
            a=[x+.5,-394,z+.5]
            for dx,dz in ((1,0),(0,1)):
                if x+dx<=112 and z+dz<=-44:
                    b=[x+dx+.5,-394,z+dz+.5];assert full_body_status(new,a,b)=='CLEAR';sweeps.append(dict(start=a,end=b,full_body_CLEAR=True))
    contract=read(WORLD/'spatial_contract_r21.json');after_contract=copy.deepcopy(contract);section=next(r for r in after_contract['sections']if r['id']=='factory_middle')
    assert section['rects']==[[95,113,-275,-42],[89,113,-49,-42],[86,113,-271,-259]]
    section['rects']=[[95,113,-275,-43],[89,113,-49,-43],[86,113,-271,-259]]
    boundary=dict(x=[90,112],z=-43,feet=-394,wall_y=[-394,-389],waist_state=WALL,glass_state=GLASS,frame_state=STRUCT,vertical_frame_x=list(FRAMES),top_seal_y=-389,continuous_roof_y=-388,through_route=False,enclosed=True,clear_waiting_rows_z=[-46,-45,-44])
    section['south_end_role']='Enclosed industrial observation window at supported retracted boundary; real lift call/entry north-west, no south door'
    section['enclosed_observation_boundaries']=[boundary]
    OUT.mkdir();forward=[changes[q]for q in sorted(changes)];inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in forward]
    jsonl(OUT/'forward.jsonl.gz',forward);jsonl(OUT/'inverse.jsonl.gz',inverse);jsonl(OUT/'positive_edit_mask.jsonl.gz',[r['pos']for r in forward])
    jsonl(OUT/'whole_component_before_state_NBT.jsonl.gz',[dict(pos=[x,y,z],state=m.block((x,y,z)),full_nbt=tags[x,y,z].snbt()if(x,y,z)in tags else None)for x in range(88,115)for y in range(-397,-386)for z in range(-51,-40)])
    (OUT/'spatial_contract_r21.before.json').write_bytes((WORLD/'spatial_contract_r21.json').read_bytes());write(OUT/'spatial_contract_r21.after.json',after_contract)
    write(OUT/'static_metadata_reversible_proposal.json',dict(target='spatial_contract_r21.json',before_sha256=sha(WORLD/'spatial_contract_r21.json'),before_file=str(OUT/'spatial_contract_r21.before.json'),after_file=str(OUT/'spatial_contract_r21.after.json'),after_sha256=sha(OUT/'spatial_contract_r21.after.json'),derivative_navigation_installed=False))
    write(OUT/'all69_full_width_and23_boundary_sweeps.json',dict(waiting69=body,neighbor_sweeps=sweeps,outward23=edges,old239_design_rejected=True,new_body_rows_z=[-46,-45,-44]))
    write(OUT/'original_BE_full_NBT_retained.json',[dict(pos=q,full_nbt=t.snbt())for q,t in tags.items()]);inventory()
    patchdir=OUT/'producer_patch';patchdir.mkdir();patches=[]
    p=ROOT/'tools/repair_facility_r21.py';source=p.read_text('utf8');start=" s.hall('factory_middle',[(95,113,-275,-42),(89,113,-49,-42),(86,113,-271,-259)],-395,7,\n        [(91,-394,-49,95,-391,-46),(86,-394,-269,90,-390,-263)])\n";assert source.count(start)==1
    replacement=start.replace('-275,-42','-275,-43').replace('-49,-42','-49,-43')+" # Complete retracted enclosed observation boundary: keep the three\n # original clear rows at Z=-46..-44 and the actual lift handoff at Z=-45.\n for x in range(90,114):\n  for y in range(-396,-387):\n   old=s.palette[s.before[y-LO[1],-42-LO[2],x-LO[0]]]\n   if old in {FLOOR,STRUCT,WALL,GLASS}:s.fill((x,y,-42,x,y,-42),AIR)\n for x in range(90,113):\n  for y in range(-394,-388):\n   state=STRUCT if x in (90,96,104,112) or y==-389 else WALL if y==-394 else GLASS\n   s.fill((x,y,-43,x,y,-43),state)\n s.contract[-1].update(south_end_role='Enclosed industrial observation window; no south door',enclosed_observation_boundaries=[dict(x=[90,112],z=-43,feet=-394,wall_y=[-394,-389],waist_state=WALL,glass_state=GLASS,frame_state=STRUCT,vertical_frame_x=[90,96,104,112],top_seal_y=-389,continuous_roof_y=-388,through_route=False,enclosed=True,clear_waiting_rows_z=[-46,-45,-44])])\n"
    candidate=source.replace(start,replacement);patches.append((p,source,candidate))
    p=ROOT/'tools/audit_spatial_contract_r21.py';source=p.read_text('utf8');needle="  if section['id']=='factory_lower':section['rects']=[[102,114,-290,-54]]\n";assert source.count(needle)==1
    additional="  if section['id']=='factory_middle':\n   section['rects']=[[95,113,-275,-43],[89,113,-49,-43],[86,113,-271,-259]]\n   section['south_end_role']='Enclosed industrial observation window; no south door'\n   section['enclosed_observation_boundaries']=["+repr(boundary)+"]\n"
    patches.append((p,source,source.replace(needle,needle+additional)));text=''
    import ast
    for p,source,candidate in patches:
        ast.parse(candidate);text+=''.join(difflib.unified_diff(source.splitlines(True),candidate.splitlines(True),fromfile='a/'+p.relative_to(ROOT).as_posix(),tofile='b/'+p.relative_to(ROOT).as_posix()))
        (patchdir/(p.stem+'.before.txt')).write_bytes(source.encode('utf8'));(patchdir/(p.stem+'.candidate.txt')).write_bytes(candidate.encode('utf8'))
    (patchdir/'root_middle_lobby_enclosed_producers.patch').write_bytes(text.encode('utf8'))
    write(OUT/'report.json',dict(source_world=str(WORLD),source1736_SHA_unchanged=True,changes354=True,retired_original_flange216=True,new_closed_boundary138=True,new_state_counts=dict(collections.Counter(r['after']for r in forward if r['after']!='minecraft:air')),waist1m_glass4m_lintel1m=True,real3width_clear_69=True,neighbor_full_body_sweeps=len(sweeps),outward_full_body_blocked23=True,original_lift_input_handoff_and_active_device_mask_untouched=True,saved_actors_posts_walk_endpoints_and_complete_BE_untouched=True,no_false_south_door=True,installed=False,world_written=False,model_changed=False,Java_Gradle_MC_started=False,new_native_walk=False,visual_accepted=False,old239_design_rejected=True,forward_sha256=sha(OUT/'forward.jsonl.gz'),inverse_sha256=sha(OUT/'inverse.jsonl.gz')))
    print('Prepared354 enclosed full component with actual3wide69/body112/sweeps; no world writes.',flush=True)
if __name__=='__main__':main()
