"""Exact rigid shoe mesh + captured final bones; saved-world full-cube floor readback."""
from pathlib import Path
import argparse, hashlib, json, sys, zipfile
import numpy as np
from query_blocks import iter_selected_sections, AIR

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run',type=Path,required=True)
parser.add_argument('--jar',type=Path,required=True)
args=parser.parse_args();run=args.run.resolve();spec=json.loads((run/'launch.json').read_text('utf8'))
world=Path(spec['world']).resolve();assert world.name=='SEELE_FIRST_BATTLE_REVIEW_R10' and 'WORLD_R52' not in str(world)
digest=lambda data:hashlib.sha256(data).hexdigest()
jar_hash=digest(args.jar.read_bytes());assert jar_hash==spec['staged_jar']['sha256']
poses=[json.loads(line) for line in (run/'poses.jsonl').read_text('utf8').splitlines()]
frames=[json.loads(line) for line in (run/'frames.jsonl').read_text('utf8').splitlines()]
frame_lookup={(r['variant'],r['age']):r['file'] for r in frames}
parts={};asset_receipt=[]
with zipfile.ZipFile(args.jar) as archive:
    for variant in (0,1,2):
        member=f'assets/projectseele/mesh/eva_unit0{variant}.mesh.json';raw=archive.read(member);mesh=json.loads(raw)
        witness={r['actual_foot_witness']['mesh_sha256'] for r in poses if r['variant']==variant}
        assert witness=={digest(raw)},'Loaded actual resource differs from frozen member'
        for side in ('l','r'):
            name='foot_'+side;assert name not in mesh.get('jointSkins',{}),'Weighted shoe needs exact skin evaluation'
            part=mesh['parts'][name];vertices=np.asarray(part['vertices'],np.float64).reshape(-1,mesh['stride'])[:,:3]
            points=(vertices+part['pivot'])*[-1,1,1]/16
            parts[variant,side]=np.c_[points,np.ones(len(points))]
            asset_receipt.append(dict(variant=variant,side=side,member=member,sha256=digest(raw),actual_vertex_count=len(points),rigid_no_joint_skin=True))
rows=[];selected={}
for p in poses:
    item=dict(variant=p['variant'],age=p['age'],server_tick=p['server_tick'],key=p['key'],stance=p['stance'],
        root_position=p['position'],model_to_world_y=p['model_to_world'][13],move=p['rifleMoveBlend'],run=p['rifleRunBlend'],gait=p['rifleGaitPhase'],
        input_forward=p['pilot_server_forward_input'],camera_view=p['camera_view'],native_file=frame_lookup.get((p['variant'],p['age'])),sides={})
    base=np.asarray(p['model_to_world']).reshape(4,4,order='F')
    for side in ('l','r'):
        name='foot_'+side;matrix=base@np.asarray(p['final_rendered_model_bones'][name]).reshape(4,4,order='F')
        vertices=parts[p['variant'],side]@matrix.T;index=int(vertices[:,1].argmin());low=vertices[index,:3]
        x,z=int(np.floor(low[0])),int(np.floor(low[2]));selected.setdefault((x//16,z//16),set()).update((-4,-3))
        item['sides'][side]=dict(minimum_y=float(low[1]),lowest_world=low.tolist(),actual_vertex_index=index,
            native_toe_fk=p['actual_foot_witness']['final_bone_fk_world'][side],actual_bone_pivot=p['actual_world_bone_pivots'][name],
            source_plant=p['actual_foot_witness']['support_r44'][side+'source_plant'],column=[x,z])
    rows.append(item)
sections={}
for cx,cz,sy,palette,indices in iter_selected_sections(world,'minecraft:overworld',selected):
    sections[cx,cz,sy]=(palette,indices)
white_shapes=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/native_collision_shapes_candidate6/native_collision_shapes.json')
assert json.loads(white_shapes.read_text('utf8'))['minecraft:white_concrete']==[[0,0,0,1,1,1]],'Native white-concrete full-cube evidence required'
native_shapes=json.loads(white_shapes.read_text('utf8'))
cube={'minecraft:gray_concrete','minecraft:white_concrete','minecraft:grass_block','minecraft:dirt','minecraft:bedrock','minecraft:stone'}
for row in rows:
    for value in row['sides'].values():
        x,z=value['column'];states=[];floor=None;unresolved=None
        for y in range(-33,-65,-1):
            section=sections.get((x//16,z//16,y//16))
            if section is None:unresolved='missing saved section';break
            palette,indices=section;state=palette[int(indices[((y%16)<<8)|((z%16)<<4)|(x%16)])];states.append([y,state])
            if state in AIR:continue
            name=state.split('[',1)[0]
            if name in cube:floor=float(y+1)
            else:
                boxes=native_shapes.get(state)
                if boxes is None:unresolved='collision shape not independently decoded: '+state;break
                wx,wz=value['lowest_world'][0]-x,value['lowest_world'][2]-z
                hits=[float(box[4]) for box in boxes if box[0]-1e-7<=wx<=box[3]+1e-7 and box[2]-1e-7<=wz<=box[5]+1e-7]
                if not hits:continue
                floor=float(y+max(hits))
            value.update(saved_collision_block=[x,y,z],saved_collision_state=state,saved_collision_top_y=floor,sole_clearance_blocks=value['minimum_y']-floor)
            if name in cube:value['saved_full_cube_top_y']=floor
            break
        value['saved_column_trace']=states;value['floor_unresolved']=unresolved or (None if floor is not None else 'no full-cube floor in saved range')
summary=[]
for variant in (0,1,2):
    for state,predicate in [('initial_idle',lambda r:r['age']<30),('walk',lambda r:35<=r['age']<75),('run',lambda r:80<=r['age']<120),('stopped_idle',lambda r:175<=r['age']<185),('prone_steady',lambda r:r['stance']>2.99)]:
        chosen=[r for r in rows if r['variant']==variant and predicate(r)]
        data=dict(variant=variant,state=state,rows=len(chosen),root_y_range=[min(r['root_position'][1] for r in chosen),max(r['root_position'][1] for r in chosen)] if chosen else None,sides={})
        for side in ('l','r'):
            vals=[r['sides'][side]['sole_clearance_blocks'] for r in chosen if 'sole_clearance_blocks' in r['sides'][side]]
            data['sides'][side]=dict(known_floor_rows=len(vals),clearance_min_max=[min(vals),max(vals)] if vals else None)
        supporting=[min(r['sides'][s]['sole_clearance_blocks'] for s in ('l','r')) for r in chosen if all('sole_clearance_blocks' in r['sides'][s] for s in ('l','r'))]
        data['lower_shoe_clearance_min_max']=[min(supporting),max(supporting)] if supporting else None
        summary.append(data)
region_files={world/'region'/f'r.{cx//32}.{cz//32}.mca' for cx,cz in selected}
report=dict(frozen_jar_sha256=jar_hash,world=str(world),saved_world_read_only=True,asset_receipt=asset_receipt,pose_rows=len(rows),summary=summary,rows=rows,
    native_white_concrete_shape_evidence=dict(path=str(white_shapes),sha256=digest(white_shapes.read_bytes()),boxes=[[0,0,0,1,1,1]]),
    saved_regions={str(p):digest(p.read_bytes()) for p in region_files if p.exists()},gpu_output_sampled=False,native_world_ray_sampled=False,native_visual_acceptance=False,
    limits='Exact frozen rigid-shoe vertices transformed by actual same-frame final rendered bone and model-to-world matrices. Pre-shader geometry reconstruction, NOT GPU output capture. Collision tops reconstructed from unchanged saved native fixture full-cube states, NOT a per-frame native ray trace. Missing/unknown collision shapes stay unresolved; toe and bone pivot never substitute for minimum shoe vertex.')
(run/'ACTUAL_FINAL_SHOE_BOUNDS_AND_SAVED_FLOORS.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps(dict(pose_rows=len(rows),summary=summary),indent=2))
