"""Finite seventeen-door fixed-control proposal, exact full preimages and no world writes."""
from __future__ import annotations
import argparse, copy, gzip, hashlib, json, math, sys
from pathlib import Path
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import iter_block_entities, AIR
from prepare_school_hakone_native_r45 import ActualGeometry

ROOT=Path(__file__).resolve().parents[1]
NORMAL={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf8')
def jsonl(p,rows):
    with gzip.open(p,'wt',encoding='utf8')as stream:
        for row in rows:stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')

def main(args):
    world,out=args.world.resolve(),args.out.resolve()
    assert world.name=='world' and world.parent.parent.name=='composition_candidates' and not out.exists()
    marker_path=world/'.projectseele_command_sliding_doors_r01.json';raw_marker=marker_path.read_bytes();marker=json.loads(raw_marker)
    assert len(marker['doors'])==17 and len({r['id']for r in marker['doors']})==17
    assert {tuple(r['lower'])for r in marker['excludedOriginalDoors']}=={(24,-423,254),(24,-418,254)}
    measured=MeasuredWorld(world)
    for door in marker['doors']:measured.around(door['lower'],9)
    regions=world/'dimensions/projectseele/geofront/region';region_paths={regions/f'r.{x//32}.{z//32}.mca'for x,z in measured.selected}
    before_regions={str(p):sha(p)for p in region_paths};measured.load();assert all(v=='full'for v in measured.status.values())
    tags=dict(iter_block_entities(world,'projectseele:geofront',(-20,-445,225),(80,-400,380),selected_chunks=set(measured.selected)))
    shapes={s:b for s,b in read(world/'native_collision_shapes.json').items()};traits=read(world/'native_state_traits_r44.json')
    geometry=ActualGeometry(measured)
    occupied_buttons={tuple(q):r['id']for r in marker['doors']for q in r['buttons']}
    all_apertures={tuple(q)for r in marker['doors']for q in r['aperture']}
    def full(q):
        tag=tags.get(tuple(q));return dict(pos=list(q),state=measured.block(q),full_nbt=None if tag is None else tag.snbt())
    def operator(q,face,door,side,lowest_delta=-1):
        dx,dz=NORMAL[face];lx,lz=-dz,dx;options=[]
        for distance in (1,1.5,2,2.5):
            for lateral in (0,-.5,.5,-1,1):
                x,z=q[0]+.5+dx*distance+lx*lateral,q[2]+.5+dz*distance+lz*lateral
                heights={q[1]-1,q[1]-2,q[1]-3}
                for Y in range(q[1]-4,q[1]+1):
                    at=(math.floor(x),Y,math.floor(z));boxes=geometry.boxes(at)
                    if boxes is None:continue
                    for b in boxes:
                        if at[0]+b[0]<=x<=at[0]+b[3] and at[2]+b[2]<=z<=at[2]+b[5]:heights.add(Y+b[4])
                for feet in heights:
                    point=[x,feet,z];reach=math.dist([x,feet+1.62,z],[q[0]+.5,q[1]+.5,q[2]+.5])
                    nx,nz=NORMAL[door['facing']]
                    same_side=(x-door['lower'][0]-.5)*nx*side+(z-door['lower'][2]-.5)*nz*side>=.3
                    if same_side and door['lower'][1]+lowest_delta<=feet<=door['lower'][1]+1 and reach<=4 and geometry.standing(point)=='STATIC_STANDING':options.append((reach,abs(lateral),point))
        return min(options,key=lambda r:(r[0],r[1],r[2]))[2]if options else None
    operations={};resolved=[];unresolved=[];after=copy.deepcopy(marker);native=[];used=set()
    for door in after['doors']:
        x,y,z=door['lower'];dx,dz=NORMAL[door['facing']];lx,lz=(1,0)if door['axis']=='x'else(0,1)
        chosen=[];contract=[]
        for side in (-1,1):
            face=next(k for k,v in NORMAL.items()if v==(dx*side,dz*side));choices=[]
            # These original side-wall buttons are inside the real raised
            # corridor. S42's remote normal-facing jambs remain aliases; a
            # normal-only search placed the primary below the actual doorway.
            side_frame = {(16,1): ((23,-408,269),(22,-408,269),(24.5,-409,269.5),"east"),
                          (17,1): ((33,-408,269),(34,-408,269),(32.5,-409,269.5),"west")}.get((door["id"],side))
            if side_frame is not None:
                q,support,point,input_face=side_frame
                expected=f"minecraft:stone_button[face=wall,facing={input_face},powered=false]"
                if (measured.block(q).replace("powered=true","powered=false")!=expected
                        or measured.block(support)!="minecraft:black_concrete"
                        or q in tags or support in tags or q in used
                        or occupied_buttons.get(q,door["id"])!=door["id"]
                        or geometry.standing(point)!="STATIC_STANDING"):
                    raise RuntimeError("Actual same-level side-frame control changed: "+str(q))
                choices.append(((-1,0,False,q),q,measured.block(q),measured.block(q),support,list(point),True))
            # The original owner installed a fixed lintel at height2. It is
            # outside the complete moving 3x2 mask, including its centre.
            # Excluding it missed actual fixed inputs on four normal sides.
            for lateral in (-2,2,-3,3,-4,4,0,-1,1):
                for height in (1,2,0):
                    support=(x+lx*lateral,y+height,z+lz*lateral);q=(support[0]+dx*side,support[1],support[2]+dz*side)
                    s=measured.block(q);back=measured.block(support)
                    if q in tags or support in tags or q in used or q in all_apertures or support in all_apertures:continue
                    if occupied_buttons.get(q,door['id'])!=door['id']:continue
                    # Fixed native full-cube frame only. Never create a backing
                    # in air, remove furniture, overwrite a ladder or move a BE.
                    if back not in {'minecraft:iron_block','minecraft:black_concrete','minecraft:white_concrete','projectseele:nerv_structural_panel','projectseele:nerv_wall_panel'}:continue
                    if shapes.get(back)!=[[0.0,0.0,0.0,1.0,1.0,1.0]]:continue
                    wanted=f'minecraft:stone_button[face=wall,facing={face},powered=false]'
                    is_button='ButtonBlock'in traits.get(s,{}).get('runtime_class','')
                    if is_button and properties(s).get('face')=='wall' and properties(s).get('facing')==face:wanted=s
                    if s not in AIR and s!=wanted:continue
                    point=operator(q,face,door,side)
                    if point is None:continue
                    reuse=is_button and s==wanted
                    # Prefer keeping a reachable original input, then a frame
                    # closest to the original aperture; no geometry guessing.
                    score=(0 if reuse and q in occupied_buttons else 1 if reuse else 2,abs(lateral),height!=1,q)
                    choices.append((score,q,s,wanted,support,point,reuse))
            if not choices:
                unresolved.append(dict(id=door['id'],side=side,reason='No known fixed full-cube frame with free exact cell and supported reachable operator; no wall/floor/fixture overwritten'))
                continue
            _,q,s,wanted,support,point,reuse=min(choices)
            face=properties(wanted)["facing"]
            chosen.append(list(q));used.add(q)
            entry=dict(side=side,pos=list(q),facing=face,operator=point,input_before=full(q),fixed_support=full(support),
                       state_after=wanted,reuses_current_button=reuse,exact_native_outline_and_canSurvive='REQUIRED_BEFORE_NATIVE_USE_PASS',native_pass=False)
            contract.append(entry);native.append(dict(id=f"command/{door['id']}/{side}",block=list(q),expected_after=wanted,actual_support=list(support),actor_operator=point,
                capture=['actual state.getShape OUTLINE','actual state.canSurvive with complete fixed support','real ray and reach from actual grounded actor','closed→actual use→whole6-cell open→all3 lanes/actual stairs→occupied→close'],native_pass=False))
            if s!=wanted:operations[q]=dict(pos=list(q),before=s,after=wanted,before_nbt=None,after_nbt=None,owner=f"r45/command-fixed-input/{door['id']}/{side}",reason='Restore explicit actual fixed-frame door control on this normal side; no aperture/frame/floor or other identity altered')
        if len(chosen)==2:
            # Preserve every actual original fixed input as an explicit alias,
            # including originals reached from a measured neighbouring stair.
            original_door=next(r for r in marker['doors']if r['id']==door['id'])
            for old in original_door['buttons']:
                q=tuple(old);s=measured.block(q);p=properties(s or '')
                if list(q)in chosen or 'ButtonBlock'not in traits.get(s,{}).get('runtime_class','') or p.get('face')!='wall':continue
                bx,bz=NORMAL[p['facing']];support=(q[0]-bx,q[1],q[2]-bz)
                signed=(q[0]-x)*dx+(q[2]-z)*dz;side=1 if signed>0 else -1
                if signed==0 or q in tags or support in tags or support in all_apertures or shapes.get(measured.block(support))!=[[0.0,0.0,0.0,1.0,1.0,1.0]]:continue
                point=operator(q,p['facing'],door,side,-3)
                if point is None:continue
                chosen.append(list(q));used.add(q)
                contract.append(dict(side=side,pos=list(q),facing=p['facing'],operator=point,input_before=full(q),fixed_support=full(support),state_after=s,
                    reuses_current_button=True,preserved_original_alias=True,exact_native_outline_and_canSurvive='REQUIRED_BEFORE_NATIVE_USE_PASS',native_pass=False))
                native.append(dict(id=f"command/{door['id']}/original_alias/{len(chosen)}",block=list(q),expected_after=s,actual_support=list(support),actor_operator=point,
                    capture=['actual state.getShape OUTLINE','actual state.canSurvive with complete fixed support','real ray and reach from actual grounded actor','closed→actual use→whole6-cell open'],native_pass=False))
            door['buttons']=chosen;door['fixedInputContractsR45']=contract
            resolved.append(dict(id=door['id'],new_buttons=chosen,old_buttons=next(r['buttons']for r in marker['doors']if r['id']==door['id']),contract=contract))
        else:
            # Do not emit half of a replacement owner contract.
            for c in contract:operations.pop(tuple(c['pos']),None);used.discard(tuple(c['pos']))
    rows=[operations[q]for q in sorted(operations)]
    inverse=[dict(r,pos=r['pos'],before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in rows]
    assert {r['id']for r in after['doors']}=={r['id']for r in marker['doors']} and after['excludedOriginalDoors']==marker['excludedOriginalDoors']
    for r in rows:
        assert tuple(r['pos'])not in tags and measured.block(r['pos'])==r['before'] and r['before']in AIR
        assert tuple(r['pos'])not in all_apertures
    assert {str(p):sha(p)for p in region_paths}==before_regions
    out.mkdir(parents=True);jsonl(out/'forward.jsonl.gz',rows);jsonl(out/'inverse.jsonl.gz',inverse);jsonl(out/'positive_edit_mask.jsonl.gz',[r['pos']for r in rows])
    (out/'command_marker.before.json').write_bytes(raw_marker)
    write(out/'command_marker.after.json',after)
    write(out/'native_fixed_input_requests.json',native)
    write(out/'resolved_fixed_controls.json',resolved);write(out/'unresolved_control_sides.json',unresolved)
    write(out/'complete_door_preimages.json',[dict(id=r['id'],lower=r['lower'],facing=r['facing'],axis=r['axis'],aperture=[full(q)for q in r['aperture']],
        original_registered_inputs=[full(q)for q in r['buttons']])for r in marker['doors']])
    report=dict(world=str(world),static_cells=len(rows),resolved_doors=len(resolved),unresolved_sides=len(unresolved),original17_objects_and_original2_retired_shaft_doors_preserved=True,
        full_before_after_NBT=True,no_backing_wall_or_floor_edit=True,no_current_button_or_fixture_removed=True,preserves_healthy_actual_original_registered_inputs=True,world_written=False,native_pass=False,
        source_regions_sha256=before_regions,marker_file_proposal=dict(relative=marker_path.name,before_sha256=hashlib.sha256(raw_marker).hexdigest(),after_sha256=sha(out/'command_marker.after.json'),
        before_file=str(out/'command_marker.before.json'),after_file=str(out/'command_marker.after.json'),inverse_is_exact_original_bytes=True),
        forward_sha256=sha(out/'forward.jsonl.gz'),inverse_sha256=sha(out/'inverse.jsonl.gz'),native_preconditions='Root exact native outline/canSurvive and actual player sightline before acceptance; unchanged exact old state/NBT before any installation')
    write(out/'proposal.json',report);print(json.dumps({k:v for k,v in report.items()if k not in ('source_regions_sha256','marker_file_proposal')},ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
