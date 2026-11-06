"""Offline NERV Port terrace entrance: measured opening plus supported stairs."""
import argparse,json,math
from pathlib import Path
import nbtlib
from export_hakone_station_surface import export
from author_hakone_lakefront import Editor
from audit_mountain_station_access import SupplementedSections,shape_for
from audit_oldcity_surface_station_access import MainlineSweep,StationNav
from build_gora_protected_transfer import IndependentWalker
from propose_mountain_station_steps import Overlay
from review_underground_station_evidence import strict_walk
from render_hakone_voxel_3d import render

SLAB='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
BAR='minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]'
OLD_RAIL='projectseele:nerv_edge_rail[east=false,north=true,south=false,west=false]'
STONE='minecraft:stone_bricks'

def run(a):
    export(a.fresh,[1120,448,1135,463],a.out);ed=Editor(a.out)
    capture=json.loads((a.out/'capture.json').read_text('utf8'))
    devices={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']}
    base=SupplementedSections(a.context,a.fresh);shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    native=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    previous=json.loads(a.review.read_text('utf8'));box=previous['bounds'];sweep=MainlineSweep(native,model,box)
    proposed={};columns=[];errors=[];openings=[]
    def put(x,y,z,state,why):
        pos=(x,y,z);old=base.state(*pos)
        if pos in devices:raise ValueError('Protected device '+str(pos))
        if old==state:return
        if old!='minecraft:air':raise ValueError('Unapproved existing block alteration '+str((pos,old)))
        proposed[pos]=(state,why)
    def support(x,top,z,kind):
        y=top-1
        while True:
            old=base.state(x,y,z);bs,_=shape_for(old or'__unavailable__',shapes,True)
            if bs is None:raise ValueError('Unknown foundation')
            if any(b==[0.,0.,0.,1.,1.,1.]for b in bs):break
            if top-y>16:raise ValueError('Deep unexpected support')
            put(x,y,z,STONE,'continuous foundation');y-=1
        columns.append(dict(x=x,z=z,kind=kind,base_y=y,base_state=base.state(x,y,z),top_y=top,continuous_new_y=list(range(y+1,top))))
    for x in range(1129,1132):
        p=(x,71,454)
        if base.state(*p)!=OLD_RAIL or p in devices:raise ValueError('Entrance rail differs or has block entity')
        proposed[p]=('minecraft:air','intentional three-wide entrance opening in static safety rail')
        openings.append(dict(pos=list(p),before=OLD_RAIL,after='minecraft:air'))
    for z,feet in[(453,70.5),(452,70),(451,69.5)]:
        floor=math.ceil(feet)-1
        for x in range(1129,1132):
            support(x,floor,z,'tread');put(x,floor,z,SLAB if feet%1 else'minecraft:smooth_stone','half-rise entrance stair')
        for x in(1128,1132):
            ry=math.ceil(feet);support(x,ry-1,z,'side stringer')
            put(x,ry-1,z,STONE,'bearing below guard');put(x,ry,z,BAR,'continuous side fall guard')
    changes=[dict(pos=list(p),before=base.state(*p),after=s,purpose=why)for p,(s,why)in sorted(proposed.items())]
    for q in changes:
        if ed.state(*q['pos'])!=q['before']:raise ValueError('Fresh source mismatch')
        ed.put(*q['pos'],q['after'])
    regions=ed.save();after=Overlay(base,changes)
    goals={'retained_stair_foot':[1129,71,459]}
    for x in range(1129,1132):
        goals['terrace_mouth_'+str(x)]=[x,71,454]
        goals['lowest_half_step_'+str(x)]=[x,69.5,451]
        goals['ground_landing_'+str(x)]=[x,69,450]
    goals.update(public_walk_west=[1132,69,436],public_walk_middle=[1136,69,437],public_walk_east=[1140,69,437])
    for q in previous['platform_deck_samples']:
        if q.get('goal'):goals[q['key']]=q['goal']
    phases=[]
    for phase,reader in[('before',base),('after',after)]:
        nav=StationNav(reader,box,shapes,sweep);rows,count=nav.routes(goals,'retained_stair_foot');w=IndependentWalker(reader,shapes,sweep);proofs=[]
        for q in rows:
            row=dict(key=q['name'],requested=q['requested'],reachable=q['reachable'],measured=q['measured_goal'])
            if q['reachable']:
                row.update(path=q['path'],forward=strict_walk(w,q['path']),reverse=strict_walk(w,list(reversed(q['path']))))
                row['strict_pass']=all(row[d]['kind']=='strict_static_clear'for d in('forward','reverse'))
            proofs.append(row)
        phases.append(dict(phase=phase,reachable_nodes=count,goals=proofs))
    before={q['key']:q for q in phases[0]['goals']};aft={q['key']:q for q in phases[1]['goals']}
    if any(before[k]['reachable']for k in goals if k.startswith('public_walk')):errors.append('Existing public route already exists')
    if not all(q.get('strict_pass')for q in aft.values()):errors.append('After route failed')
    w=IndependentWalker(after,shapes,sweep);guards=[]
    for z,feet in[(453,70.5),(452,70),(451,69.5)]:
        for x,side in[(1128.8,'west'),(1132.2,'east')]:
            pos=[x,feet,z+.5];hit=w.body(*pos);guards.append(dict(pos=pos,side=side,hit=hit))
            if hit is None or hit['kind']!='body_obstruction':errors.append('Missing stair side guard')
    for x,side in[(1128.8,'west mouth junction'),(1132.2,'east mouth junction')]:
        pos=[x,71,454.2];hit=w.body(*pos);guards.append(dict(pos=pos,side=side,hit=hit))
        if hit is None or hit['kind']!='body_obstruction':errors.append('Mouth guard junction gap')
    negative=[]
    for label,patch,path in[
        ('missing_half_step',[dict(pos=[1130,69,451],after='minecraft:air')],[[1130.5,69.5,451.5]]),
        ('blocked_headroom',[dict(pos=[1130,71,451],after=STONE)],[[1130.5,69.5,451.5]]),
        ('original_rail_reclosed',[dict(pos=q['pos'],after=q['before'])for q in openings],aft['public_walk_middle']['path'])]:
        p=strict_walk(IndependentWalker(Overlay(after,patch),shapes,sweep),path);reject=p['kind']!='strict_static_clear'
        negative.append(dict(case=label,rejected=reject,result=p))
        if not reject:errors.append('Negative test failed')
    pos=[1128.8,70,452.5];removed=IndependentWalker(Overlay(after,[dict(pos=[1128,70,452],after='minecraft:air')]),shapes,sweep).body(*pos)
    reject=w.body(*pos)is not None and removed is None
    negative.append(dict(case='side_guard_removed',rejected=reject,intact_hit=w.body(*pos),removed_hit=removed))
    if not reject:errors.append('Removed guard test failed')
    intrusions=[]
    for q in changes:
        x,y,z=q['pos'];bs,_=shape_for(q['after'],shapes,True)
        if bs is None:errors.append('Unknown new shape');continue
        for bb in bs:
            if sweep.intersects(x+(bb[0]+bb[3])/2,z+(bb[2]+bb[5])/2,(bb[3]-bb[0])/2,(bb[5]-bb[2])/2,y+bb[1],y+bb[4]):intrusions.append(q);break
    if intrusions:errors.append('Train envelope intrusion')
    bounds=[min(q['pos'][i]for q in changes)for i in range(3)]+[max(q['pos'][i]for q in changes)for i in range(3)]
    report=dict(errors=errors,changed_cells=len(changes),new_air_cells=sum(q['before']=='minecraft:air'for q in changes),
        old_safety_rail_opening=openings,old_modified_count=len(openings),support_columns=columns,guard_probes=guards,
        before_after_paths=phases,negative_tests=negative,vehicle_intrusions=intrusions,train_reservation=sweep.info(),
        preserved_devices=len(devices),preserved_actors=len(capture['actors']),world_written=False,
        dynamic_gate_bypass=False,ordinary_doors_conditionally_open=True,
        unverified=['current native collision export','live passenger boarding and gates','public footway beyond the captured station frontage'])
    manifest=dict(world=capture['world'],kind='nerv-port-terrace-street-entrance',bounds_xz=capture['bounds_xz'],bounds_3d=bounds,
        regions=regions,cells=len(changes),changed_chunks=[[70,28]],source_snapshot=str(a.fresh),device_changes=0,actor_changes=0,native_changes=0,
        functional_errors=errors,world_written=False,production_recipe_replay_pending=True)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
    for file,data in[('manifest.json',manifest),('functional-check.json',report),('changes.json',changes)]:
        (a.out/file).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    for phase,r in[('before',base),('after',after)]:render(r,[1124,65,446,1136,77,460],a.out/(phase+'.png'),'NERV港口站·高台与外侧步道接入 '+phase)
    print('NERV port:',len(changes),'cells;',len(openings),'old rail openings;',len(aft),'bidir destinations; errors',errors,flush=True)
    if errors:raise ValueError('Candidate needs revision')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('fresh','context','metadata','native','models','review','out'):p.add_argument('--'+k,type=Path,required=True)
    run(p.parse_args())
