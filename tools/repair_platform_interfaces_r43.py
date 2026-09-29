"""Retire overlapping foyer parts and repair complete boarding/sign assemblies."""
from pathlib import Path
from collections import Counter
import argparse,copy,json
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';WORLD=ROOT/'run/saves/SEELE_FIELD_R43_REVIEW';OUT=ART/'platform_repairs'
NORMAL={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}

def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    OUT.mkdir(exist_ok=True);assert not list(OUT.glob('complete_interfaces/applied_*/receipt.json')),'Already migrated; author a measured follow-up instead'
    audit=json.loads((ART/'platform_interfaces_before/interfaces.json').read_text('utf8'))['platforms']
    catalogue=json.loads((ART/'station_edge_ownership/actual_platforms.json').read_text('utf8'))['platforms'];byid={p['id']:p for p in catalogue}
    mounts=json.loads((ROOT/'artifacts/facility_r30/board_mounts/custom_board_mounts/places.json').read_text('utf8'))['mounts']
    w=MeasuredWorld(WORLD);w.box((110,-445,-56),(136,-431,-40));boxes=[]
    for st in audit:
        for row in st['issues']:
            x,y,z=row['pos'];lo=(x-5,y-2,z-5);hi=(x+5,y+8,z+5);w.box(lo,hi);boxes.append((lo,hi))
    w.load();tags={}
    for lo,hi in boxes:tags.update(iter_block_entities(WORLD,v.DIM,lo,hi))
    tags.update(iter_block_entities(WORLD,v.DIM,(110,-445,-56),(136,-431,-40)))
    changes={};newtags={};decisions=[];cases=[];boardmoves=[]
    def put(q,after,why,allow_tag=False):
        q=tuple(q);before=w.block(q);assert before is not None,(q,'unmeasured')
        assert allow_tag or q not in tags,(q,'protected complete NBT')
        after=v.canonical_state(after)
        if before==after:return
        if q in changes:assert changes[q][0]==after,(q,'conflicting component choices')
        changes[q]=(after,why)
    room={'projectseele:nerv_wall_panel','projectseele:nerv_structural_panel','projectseele:clear_glass','projectseele:nerv_strip_light'}
    # Reuse the western approach and station perimeter, but retire the entire
    # R21 room's overlapping south/east wall and lower ceiling inside the hall.
    obsolete={(x,y,-43) for x in range(113,133) for y in range(-442,-436)}
    obsolete|={(132,y,z) for z in range(-54,-43) for y in range(-442,-436)}
    obsolete|={(x,-437,z) for x in range(113,132) for z in range(-54,-43)}
    obsolete|={(x,y,-42) for x in range(120,132) for y in range(-442,-436)}
    obsolete|={(x,-438,z) for x in range(113,133) for z in range(-54,-42) if w.get(x,-438,z).startswith('projectseele:nerv_ceiling_light[')}
    fixture_updates={}
    for q in sorted(obsolete):
        state=w.block(q)
        if state.startswith('projectseele:nerv_ceiling_light['):
            put(q,'minecraft:air','retire fixture attached to obsolete lower ceiling')
            backing=next((y for y in range(-436,-431) if w.get(q[0],y,q[2]).partition('[')[0] not in AIR|{'minecraft:light'}),None)
            assert backing is not None,(q,'unconfirmed station roof')
            s=w.get(q[0],backing,q[2])
            if not s.startswith('projectseele:nerv_ceiling_light['):
                assert s in {'minecraft:light_gray_concrete','projectseele:nerv_machine_edge','projectseele:nerv_structural_panel'},(q,s)
                upper=(q[0],backing-1,q[2]);assert w.block(upper).partition('[')[0] in AIR or upper in obsolete and w.block(upper).partition('[')[0] in room,(q,upper,w.block(upper))
                fixture_updates[upper]=state
        elif state.partition('[')[0] in room:put(q,'minecraft:air','retire overlapping R21 foyer assembly')
        else:assert state.partition('[')[0] in AIR|{'minecraft:light'} or state.startswith('mtr:'),(q,state,'unclassified overlap')
    for q,state in fixture_updates.items():
        changes.pop(q,None);put(q,state,'reattach fixture to actual station ceiling or beam')
    for x in range(118,133):
        q=(x,-443,-43);assert w.block(q) in {'projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','projectseele:station_tactile_warning'}
        put(q,'projectseele:station_tactile_warning','continuous platform warning strip')
    for x in range(120,132):
        q=(x,-443,-42);assert w.block(q)=='projectseele:nerv_floor_panel'
        put(q,'mtr:platform[door_type=apg,facing=south,side=0]','restore native rail-owned platform strip')
        phase=(x-150-2)%5;door=phase in (0,1);part=1-(phase if door else (x-150)%2)
        for half,y in [('lower',-442),('upper',-441)]:
            at=(x,y,-42);changes.pop(at,None)
            props=f'facing=south,half={half},side={"left" if part==0 else "right"}'
            put(at,f'mtr:apg_door[end=false,{props},unlocked=true]' if door else f'mtr:apg_glass[{props}]','restore complete native paired gate')
            if door:newtags[at]=nbtlib.Compound(dict(id=nbtlib.String('mtr:apg_door'),x=nbtlib.Int(x),y=nbtlib.Int(y),z=nbtlib.Int(-42)))
    # A periodic two-leaf gate must not be sliced in half by the platform end.
    for st in audit:
        axis=0 if byid[st['id']]['axis']=='x' else 2
        for row in st['issues']:
            if row['kind']!='broken_horizontal_gate_pair':continue
            q=tuple(row['pos']);assert q[axis] in byid[st['id']]['ends'],(q,'non-terminal split needs individual component repair')
            for dy in (1,2):
                at=(q[0],q[1]+dy,q[2]);old=w.block(at);props=properties(old)
                assert old.startswith('mtr:apg_door[') and props['half']==('lower' if dy==1 else 'upper')
                assert at not in tags or str(tags[at]['id'])=='mtr:apg_door',(at,'unrelated device NBT')
                put(at,f'mtr:apg_glass[facing={props["facing"]},half={props["half"]},propagate_property=0,side={props["side"]}]','retire incomplete terminal door as fixed end glazing',True)
            decisions.append(dict(kind='complete_terminal_barrier',platform=st['id'],pos=q))
    # Move the complete board + its three-part bracket, never just its legs.
    for st in audit:
        for row in st['issues']:
            if row['kind']!='blocked_or_unsupported_boarding_approach' or not row['states'][1].startswith('projectseele:nerv_sign_post'):continue
            post=tuple(row['approach']);entry=next(m for m in mounts if m.get('kind')=='stanchion' and tuple(m['post'])==post)
            board=tuple(entry['board']);assert board in tags and str(tags[board]['id'])=='projectseele:station_departure_board'
            platform=byid[st['id']];axis=(1,0) if platform['axis']=='x' else (0,1)
            lower=w.get(row['pos'][0],row['pos'][1]+1,row['pos'][2]);normal=NORMAL[properties(lower)['facing']]
            chosen=None
            assembly=[board]+[(post[0],post[1]+i,post[2]) for i in range(3)]
            for sign in (1,-1):
                shift=(axis[0]*sign-normal[0],0,axis[1]*sign-normal[1]);target=[tuple(q[i]+shift[i] for i in range(3)) for q in assembly]
                if any(w.block(q).partition('[')[0] not in AIR|{'minecraft:light'} or q in tags or q in changes for q in target):continue
                foot=target[1];base=w.get(foot[0],foot[1]-1,foot[2])
                if base is None or base.partition('[')[0] in AIR or 'tactile' in base or 'escalator' in base:continue
                # Full panel footprint is three wide and two high; preserve
                # other equipment even though only its anchor has an NBT.
                f=properties(w.block(board))['facing'];nx,nz=NORMAL[f];t=target[0]
                footprint=[(t[0]+d*(1 if nz else 0),t[1]+h,t[2]+d*(1 if nx else 0)) for d in (-1,0,1) for h in (0,1)]
                if any(q not in assembly and w.block(q).partition('[')[0] not in AIR|{'minecraft:light'} for q in footprint):continue
                chosen=(shift,target);break
            assert chosen is not None,(st['station'],board,'No measured complete sign placement')
            shift,target=chosen
            for before,after in zip(assembly,target):
                put(before,'minecraft:air','retire entire obstructing sign assembly',before==board)
                put(after,w.block(before),'relocate intact sign to island interior')
            tag=copy.deepcopy(tags[board]);new=target[0]
            for key,value in zip(('x','y','z'),new):tag[key]=nbtlib.Int(value)
            newtags[new]=tag;boardmoves.append(dict(before=board,after=new,post_before=post,post_after=target[1],preserved_nbt_except_xyz=True,platform=st['id']))
            x,y,z=post;axisx,axisz=axis
            path=[[x+.5-axisx*1.5,y,z+.5-axisz*1.5],[x+.5+axisx*1.5,y,z+.5+axisz*1.5]]
            cases.extend([dict(id=f'r43/boarding/{st["id"]}/clear_apron',path=path),dict(id=f'r43/boarding/{st["id"]}/clear_apron/return',path=path[::-1])])
    for z in (-42.5,-45.5,-49.5):
        path=[[115.5,-442,z],[138.5,-442,z]]
        cases.extend([dict(id=f'r43/hangar_platform/full_width/{z}',path=path),dict(id=f'r43/hangar_platform/full_width/{z}/return',path=path[::-1])])
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    for q,(state,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),state,'r43/platform_interfaces/'+why)
    p.block_entities.update(newtags)
    p.meta.update(retired_component='R21 factory lower and station foyer overlapping the north platform; retain western approach and external station envelope',
        preserved=['Rail track and MTR objects/progress','Existing station outer shell and roof','Native lift/call hardware','All unchanged board NBT and device identities'],
        terminal_barriers=decisions,board_moves=boardmoves,walk_cases=cases,cells=len(changes),validation='Candidate full-assembly patch; native lifecycle and visual review pending')
    p.save_plan('complete_interfaces');(OUT/'cases.json').write_text(json.dumps(cases,indent=2),'utf8')
    if apply:
        path=WORLD/'quality_walk_cases.json';original=path.read_bytes();(OUT/'quality_walk_cases.before.json').write_bytes(original)
        p.apply('complete_interfaces');rows=json.loads(original);moves={tuple(r['before']):r['after'] for r in boardmoves}
        for r in rows:
            if tuple(r.get('readingBoard',[])) in moves:r['readingBoard']=moves[tuple(r['readingBoard'])]
        rows.extend(cases);path.write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')),'utf8')
        (OUT/'r43_walk_cases.before.json').write_bytes((WORLD/'r43_walk_cases.json').read_bytes())
        (WORLD/'r43_walk_cases.json').write_text(json.dumps(cases),'utf8')
        (WORLD/'platform_interfaces_r43.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')
    print('Planned',len(changes),'cells;',len(decisions),'terminal barriers;',len(boardmoves),'complete sign moves;',len(cases),'native cases',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
