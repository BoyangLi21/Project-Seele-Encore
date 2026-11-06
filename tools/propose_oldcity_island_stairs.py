"""One compact central-island stair, using exact existing offline station cells.

The centre lane descends to the lower concourse. Original boarding aprons and
APGs remain in place; thin metal parapets leave both aprons passable. This is an
uninstalled proposal, not an actual-world patch or whole-station acceptance.
"""
import argparse,json,math
from collections import Counter
from pathlib import Path
import numpy as np
import nbtlib
from audit_oldcity_surface_station_access import MainlineSweep,StationNav,SupplementedSections
from build_gora_protected_transfer import IndependentWalker
from audit_mountain_station_access import shape_for
from propose_mountain_station_steps import Overlay
from review_underground_station_evidence import strict_walk
from render_hakone_voxel_3d import render
from export_hakone_station_surface import export
from author_hakone_lakefront import Editor

AIR='minecraft:air';BRICK='minecraft:stone_bricks';SLAB='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
ALLOWED_SOLIDS={'minecraft:light_gray_concrete','projectseele:period_station_floor','projectseele:station_tactile_warning'}
FULL=[[0.,0.,0.,1.,1.,1.]]

def make(reader,shapes):
    proposed={};purposes={};supports=[]
    def get(x,y,z):return proposed.get((x,y,z),reader.state(x,y,z))
    def put(x,y,z,s,why):
        before=reader.state(x,y,z)
        if before is None:raise ValueError('Uncaptured '+str((x,y,z)))
        if before==s:proposed.pop((x,y,z),None);purposes.pop((x,y,z),None)
        else:proposed[x,y,z]=s;purposes[x,y,z]=why
    for x in range(-150,-121):
        feet=81+(x+150)/2
        for z in(-173,-172,-171):
            bearing=reader.state(x,80,z);boxes,_=shape_for(bearing,shapes,True)
            if boxes!=FULL:raise ValueError('Unverified base '+str((x,z,bearing)))
            top=math.floor(feet)-1 if z==-172 else math.ceil(feet)-1
            supports.append(dict(x=x,z=z,base_y=80,top_y=top))
            for y in range(81,top+1):
                s=get(x,y,z)
                if s==AIR:put(x,y,z,BRICK,'continuous-stair-and-side-foundation')
                elif s not in ALLOWED_SOLIDS:raise ValueError('Foundation hits existing component '+str((x,y,z,s)))
        if feet%1:
            y=math.floor(feet);s=get(x,y,-172)
            if s!=AIR and s not in ALLOWED_SOLIDS:raise ValueError('Unexpected tread '+str((x,y,s)))
            put(x,y,-172,SLAB,'half-step-centre-tread')
        for y in range(math.ceil(feet),math.ceil(feet+2.3)):
            s=get(x,y,-172)
            if s in ALLOWED_SOLIDS:put(x,y,-172,AIR,'one-block-wide-stair-headroom')
            elif s!=AIR:raise ValueError('Headroom touches original device '+str((x,y,s)))
        # Each rail is placed against the inner boundary of its original apron
        # cell. The APG and tactile bearing below the apron stay unchanged.
        if x>-150 and feet<95:
            y=math.ceil(feet)
            for z,facing in[(-173,'north'),(-171,'south')]:
                s=get(x,y,z)
                if s==AIR:
                    state=f'minecraft:iron_trapdoor[facing={facing},half=bottom,open=true,powered=false,waterlogged=false]'
                    if state not in shapes:raise ValueError('Metal rail has no recorded collision shape')
                    put(x,y,z,state,'thin-fixed-metal-parapet')
                elif s not in ALLOWED_SOLIDS:raise ValueError('Guard touches original component '+str((x,y,z,s)))
    openings=[]
    for x in range(-150,-121):
        boxes,_=shape_for(get(x,94,-172),shapes,True)
        if boxes==FULL:continue
        openings.append(x)
        for z,facing in[(-173,'north'),(-171,'south')]:
            state=f'minecraft:iron_trapdoor[facing={facing},half=bottom,open=true,powered=false,waterlogged=false]'
            if get(x,95,z)not in(AIR,state):raise ValueError('Upper apron guard touches original component')
            put(x,95,z,state,'upper-platform-stair-opening-guard')
    # The far end of the shaft also needs a barrier at the upper deck level.
    # It spans between the two apron guards; it is above the stair headroom.
    first=min(openings)
    put(first,95,-172,'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]','upper-platform-opening-end-guard')
    changes=[dict(pos=list(p),before=reader.state(*p),after=s,purpose=purposes[p])for p,s in sorted(proposed.items())]
    return changes,supports

def collision_plan(reader,shapes,out):
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(1500,710),'#f4f5f0');d=ImageDraw.Draw(im)
    f=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',23);s=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
    d.text((25,12),'第三新东京中央·岛台楼梯口实际碰撞断面（X=-122.5）',fill='#243b33',font=f)
    ox,oy,scale=90,615,65;low,hi=90,98
    for z in range(-177,-166):
        for y in range(low,hi):
            state=reader.state(-123,y,z);boxes,_=shape_for(state or'__unavailable__',shapes,True)
            if boxes is None:continue
            for b in boxes:
                if not b[0]<=.5<b[3]:continue
                colour='#b2b8ad'
                if 'trapdoor'in state:colour='#298aac'
                elif 'mtr:apg'in state:colour='#677e8f'
                elif 'slab'in state:colour='#daa85b'
                d.rectangle((ox+(z+b[2]+177)*scale,oy-(y+b[4]-low)*scale,ox+(z+b[5]+177)*scale,oy-(y+b[1]-low)*scale),fill=colour,outline='#58695e')
    for z in range(-177,-165):d.text((ox+(z+177)*scale-15,oy+10),str(z),fill='#354c40',font=s)
    for y in range(low,hi+1):d.text((ox-35,oy-(y-low)*scale-8),str(y),fill='#354c40',font=s)
    d.text((930,100),'保留两侧原生 APG 与站台边缘',fill='#354c40',font=s)
    d.text((930,140),'保留两侧盲道与登车走廊',fill='#354c40',font=s)
    d.text((930,180),'中央通道净宽 1 m',fill='#354c40',font=s)
    d.text((930,220),'薄金属护栏厚 3/16 m',fill='#354c40',font=s)
    d.text((930,260),'两侧 APG 至护栏净宽 1.5625 m',fill='#354c40',font=s)
    d.text((930,300),'浅黄：中央半级踏步；蓝色：护栏',fill='#354c40',font=s)
    im.save(out)

def run(a):
    if a.fresh_source:export(a.fresh_source,[-160,-176,-113,-161],a.out)
    else:a.out.mkdir(exist_ok=False)
    reader=SupplementedSections(a.source,a.fresh_source)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    baseline=json.loads(a.review.read_text('utf8'));snap=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    sweep=MainlineSweep(snap,model,baseline['bounds']);changes,supports=make(reader,shapes);after=Overlay(reader,changes)
    protected={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.source/'devices.dat')['Devices']}
    if a.fresh_source:protected|={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.fresh_source/'devices.dat')['Devices']}
    if any(tuple(q['pos'])in protected for q in changes):raise ValueError('Device touched')
    bad_native=[q for q in changes if q['before'].startswith(('mtr:','projectseele:station_tactile_warning'))]
    if bad_native:raise ValueError('Native edge or original tactile apron touched')
    nav=StationNav(after,baseline['bounds'],shapes,sweep)
    goals={q['key']:q['goal']for q in baseline['measurements']}
    goals['new_lower_entry']=[-150,81,-172];goals['new_upper_landing']=[-122,95,-172]
    routes,count=nav.routes(goals,baseline['selected_graph_root']);walker=IndependentWalker(after,shapes,sweep)
    errors=[];proofs=[]
    for row in routes:
        if not row['reachable']:errors.append('Unreachable '+row['name']);continue
        proof=dict(goal=row['name'],forward=strict_walk(walker,row['path']),reverse=strict_walk(walker,list(reversed(row['path']))),path=row['path'])
        if any(proof[d]['kind']!='strict_static_clear'for d in('forward','reverse')):errors.append('Independent sweep failed '+row['name'])
        proofs.append(proof)
    intrusion=[]
    for row in changes:
        x,y,z=row['pos'];boxes,_=shape_for(row['after'],shapes,True)
        if boxes is None:errors.append('Unknown new collision shape');continue
        for b in boxes:
            if sweep.intersects(x+(b[0]+b[3])/2,z+(b[2]+b[5])/2,(b[3]-b[0])/2,(b[5]-b[2])/2,y+b[1],y+b[4]):intrusion.append(row);break
    if intrusion:errors.append('Added structure enters running train envelope')
    apron=[]
    for z in(-173,-171):
        path=[[x+.5,95,z+.5]for x in range(-180,-59)]
        apron.append(dict(z=z,forward=strict_walk(walker,path),reverse=strict_walk(walker,list(reversed(path)))))
    if any(q[d]['kind']!='strict_static_clear'for q in apron for d in('forward','reverse')):errors.append('Original boarding apron interrupted')
    support_issues=[]
    for q in supports:
        for y in range(q['base_y'],q['top_y']+1):
            boxes,_=shape_for(after.state(q['x'],y,q['z']),shapes,True)
            if boxes!=FULL:support_issues.append([q['x'],y,q['z']])
    if support_issues:errors.append('Discontinuous support')
    guard_probes=[]
    for x in range(-128,-122):
        for z in(-172.1,-170.9):
            obstruction=walker.body(x+.5,95,z)
            guard_probes.append(dict(player=[x+.5,95,z],obstruction=obstruction))
            if not obstruction:errors.append('Upper shaft side unguarded')
    end_blocked=walker.body(-127.8,95,-171.5)
    if not end_blocked:errors.append('Upper shaft end unguarded')
    negative=[]
    for name,change,point in[
        ('missing_stair_tread',dict(pos=[-140,85,-172],after=AIR),[-139.5,86,-171.5]),
        ('blocked_stair_headroom',dict(pos=[-140,87,-172],after=BRICK),[-139.5,86,-171.5])]:
        proof=strict_walk(IndependentWalker(Overlay(after,[change]),shapes,sweep),[point])
        negative.append(dict(case=name,result=proof,rejected=proof['kind']!='strict_static_clear'))
        if proof['kind']=='strict_static_clear':errors.append('Fault injection not detected')
    report=dict(kind='third-tokyo-central-island-stair-proposal',changes=changes,changed_cells=len(changes),errors=errors,
        bounds=[-150,81,-173,-122,95,-171],changed_chunks=sorted({(q['pos'][0]//16,q['pos'][2]//16)for q in changes}),
        full_source_required_y=[-128,319],continuous_support_columns=supports,train_intrusions=intrusion,
        support_issues=support_issues,upper_shaft_guard_probes=guard_probes,upper_end_guard_probe=end_blocked,negative_tests=negative,
        all_goal_proofs=proofs,original_boarding_apron_proofs=apron,reachable_nodes=count,
        native_platforms_and_apgs_modified=0,original_tactile_aprons_modified=0,device_changes=0,
        stair_core_width=1,original_apron_clear_width_with_metal_guard=1.5625,maximum_step=.5,
        preserved_upper_sign_post=[-121,95,-172],preserved_station_departure_boards=True,
        model_source=str(a.models),full_source_export_pending=not bool(a.fresh_source),world_written=False,installed=False,
        current_native_collision_and_guard_state_runtime_validation_pending=True)
    (a.out/'proposal.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    if a.fresh_source:
        capture=json.loads((a.out/'capture.json').read_text('utf8'));editor=Editor(a.out)
        for row in changes:
            if editor.state(*row['pos'])!=row['before']:raise ValueError('Fresh source before state mismatch')
            editor.put(*row['pos'],row['after'])
        regions=editor.save()
        if sum(q['cells']for q in regions)!=len(changes):raise ValueError('Unexpected delta scope')
        nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
        (a.out/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),'utf8')
        manifest=dict(world=capture['world'],kind='central-station-island-stair',bounds_xz=capture['bounds_xz'],
            bounds_3d=report['bounds'],regions=regions,cells=len(changes),changed_chunks=report['changed_chunks'],
            source_snapshot=str(a.fresh_source),functional_errors=errors,device_changes=0,actor_changes=0,
            native_changes=0,world_written=False,production_recipe_replay_pending=True)
        (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
        (a.out/'functional-check.json').write_text(json.dumps({k:v for k,v in report.items()if k!='changes'},ensure_ascii=False,indent=2),'utf8')
    render(reader,[-155,78,-177,-117,100,-167],a.out/'before.png','第三新东京中央·原岛台与下层站厅')
    render(after,[-155,78,-177,-117,100,-167],a.out/'after.png','第三新东京中央·窄芯楼梯与原岛台通道')
    collision_plan(after,shapes,a.out/'collision-plan.png')
    print('Island stair:',len(changes),'cells;',len(proofs),'goals; errors',errors,flush=True)
    if errors:raise ValueError('Proposal is not yet installable')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','metadata','review','native','models','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--fresh-source',type=Path)
    run(p.parse_args())
