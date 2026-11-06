"""Add a supported 3-wide stair from retained West City hall to current street.

All new cells must be AIR in the fresh offline capture. Original station,
terrain, road, equipment and the installed island bridge remain untouched.
"""
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
RAIL='minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'
STONE='minecraft:stone_bricks'

def run(a):
    export(a.fresh,[-704,208,-689,223],a.out)
    capture=json.loads((a.out/'capture.json').read_text('utf8'));ed=Editor(a.out)
    devices={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']}
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    shape_aliases=json.loads((a.installed_bridge/'functional-check.json').read_text('utf8'))['shape_aliases']
    for q in shape_aliases:
        if q['state']not in shapes:shapes[q['state']]=shapes[q['same_collision_class_and_properties_as']]
    source=SupplementedSections(a.context,a.fresh)
    installed=json.loads((a.installed_bridge/'changes.json').read_text('utf8'))
    base=Overlay(source,installed)
    native=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    previous=json.loads(a.review.read_text('utf8'));box=previous['bounds'];sweep=MainlineSweep(native,model,box)
    proposed={};columns=[];errors=[]
    def put(x,y,z,state):
        p=(x,y,z);old=base.state(*p)
        if old==state:return
        if old!='minecraft:air':raise ValueError('Original structure would change '+str((p,old,state)))
        if p in devices:raise ValueError('Device would change')
        if p in proposed and proposed[p]!=state:raise ValueError('New geometry overlap '+str(p))
        proposed[p]=state
    def bearing(x,y,z):
        state=base.state(x,y,z)
        if state is None:raise ValueError('Uncaptured support '+str((x,y,z)))
        boxes,_=shape_for(state,shapes,True)
        if boxes is None:raise ValueError('Unknown support shape '+state)
        return any(b==[0.,0.,0.,1.,1.,1.]for b in boxes)
    def support(x,floor,z,kind):
        foot=floor-1
        while not bearing(x,foot,z):
            if floor-foot>30:raise ValueError('Foundation exceeds bounded search')
            put(x,foot,z,STONE);foot-=1
        columns.append(dict(x=x,z=z,kind=kind,base_y=foot,base_state=base.state(x,foot,z),top_y=floor,
            new_contiguous_support_y=list(range(foot+1,floor))))
    # Existing hall feet97 at x=-695, then seven half-block risers.
    for k in range(1,8):
        x=-695-k;feet=97+k*.5
        floor=math.ceil(feet)-1
        for z in range(212,215):
            support(x,floor,z,'tread');put(x,floor,z,SLAB if feet%1 else'minecraft:smooth_stone')
        for z in(211,215):
            rail_y=math.ceil(feet)
            support(x,rail_y-1,z,'guard_stringer');put(x,rail_y-1,z,STONE);put(x,rail_y,z,RAIL)
    # The existing sidewalk surfaces are retained; four hidden AIR cells under
    # those three landing columns receive bearing rather than leaving floats.
    for z in range(212,215):support(-703,100,z,'retained_street_landing')
    changes=[dict(pos=list(p),before=base.state(*p),after=s)for p,s in sorted(proposed.items())]
    for q in changes:
        if ed.state(*q['pos'])!=q['before']:raise ValueError('Fresh source mismatch')
        ed.put(*q['pos'],q['after'])
    regions=ed.save();after=Overlay(base,changes)
    goals={'retained_hall':[-693,97,169]}
    for z in range(212,215):
        goals['stair_foot_'+str(z)]=[-695,97,z]
        goals['stair_head_'+str(z)]=[-702,100.5,z]
        goals['street_'+str(z)]=[-703,100.5 if z==212 else 101,z]
    goals['old_north_entrance']=[-698,97,169]
    goals['street_east_network']=[-657,95,169]
    for q in previous['platform_deck_samples']:
        if q.get('goal'):goals[q['key']]=q['goal']
    proofs=[]
    for phase,reader in[('before',base),('after',after)]:
        nav=StationNav(reader,box,shapes,sweep);rows,count=nav.routes(goals,'retained_hall');w=IndependentWalker(reader,shapes,sweep)
        measured=[]
        for row in rows:
            q=dict(key=row['name'],requested=row['requested'],measured_goal=row['measured_goal'],reachable=row['reachable'])
            if row['reachable']:
                q.update(path=row['path'],forward=strict_walk(w,row['path']),reverse=strict_walk(w,list(reversed(row['path']))))
                q['strict_pass']=all(q[d]['kind']=='strict_static_clear'for d in('forward','reverse'))
            measured.append(q)
        proofs.append(dict(phase=phase,reachable_nodes=count,goals=measured))
    before={q['key']:q for q in proofs[0]['goals']};aft={q['key']:q for q in proofs[1]['goals']}
    if any(before[k]['reachable']for k in goals if k.startswith('street_')):errors.append('Existing safe street route exists')
    for k,q in aft.items():
        if k!='old_north_entrance'and not q.get('strict_pass'):errors.append('After path failed '+k)
    if aft['old_north_entrance']['reachable']:errors.append('Obsolete anchor unexpectedly altered')
    w=IndependentWalker(after,shapes,sweep);guards=[]
    for k in range(1,8):
        x=-695-k;feet=97+k*.5
        # Iron bars occupy the middle 2/16 of their block. Probe beyond the
        # collision threshold while a .6-wide foot still overlaps the tread.
        for side,z in[('north',211.8),('south',215.2)]:
            p=[x+.5,feet,z];hit=w.body(*p);guards.append(dict(pos=p,side=side,hit=hit))
            if hit is None or hit['kind']!='body_obstruction':errors.append('Missing fall guard '+str(p))
    intrusions=[]
    for c in changes:
        x,y,z=c['pos'];bs,_=shape_for(c['after'],shapes,True)
        if bs is None:errors.append('Unknown new shape');continue
        for bb in bs:
            if sweep.intersects(x+(bb[0]+bb[3])/2,z+(bb[2]+bb[5])/2,(bb[3]-bb[0])/2,(bb[5]-bb[2])/2,y+bb[1],y+bb[4]):intrusions.append(c);break
    if intrusions:errors.append('Train envelope intrusion')
    negatives=[]
    for label,patch,p in[
        ('missing_half_step',dict(pos=[-698,98,213],after='minecraft:air'),[-697.5,98.5,213.5]),
        ('blocked_headroom',dict(pos=[-698,100,213],after=STONE),[-697.5,98.5,213.5])]:
        result=strict_walk(IndependentWalker(Overlay(after,[patch]),shapes,sweep),[p]);reject=result['kind']!='strict_static_clear'
        negatives.append(dict(case=label,rejected=reject,result=result))
        if not reject:errors.append('Fault injection not rejected')
    guard_pos=[-696.5,98,211.8]
    removed=IndependentWalker(Overlay(after,[dict(pos=[-697,98,211],after='minecraft:air')]),shapes,sweep).body(*guard_pos)
    detected=w.body(*guard_pos)is not None and removed is None
    negatives.append(dict(case='removed_fall_guard',rejected=detected,intact_hit=w.body(*guard_pos),removed_hit=removed))
    if not detected:errors.append('Removed guard negative case not rejected')
    bounds=[min(c['pos'][i]for c in changes)for i in range(3)]+[max(c['pos'][i]for c in changes)for i in range(3)]
    check=dict(errors=errors,changed_cells=len(changes),all_before_air=True,preserved_devices=len(devices),preserved_actors=len(capture['actors']),
        before_after_paths=proofs,support_columns=columns,support_column_count=len(columns),fall_guard_probes=guards,
        inherited_installed_bridge_shape_aliases=shape_aliases,
        negative_tests=negatives,vehicle_intrusions=intrusions,train_reservation=sweep.info(),world_written=False,
        existing_island_bridge_layer=str(a.installed_bridge),source_exact_fresh=str(a.fresh),
        current_native_shapes_and_live_gate_boarding_validation_pending=True,original_terrain_and_structures_unchanged=True)
    manifest=dict(world=capture['world'],kind='west-station-street-stair',bounds_xz=capture['bounds_xz'],bounds_3d=bounds,
        regions=regions,cells=len(changes),changed_chunks=[[-44,13]],source_snapshot=str(a.fresh),device_changes=0,actor_changes=0,native_changes=0,
        functional_errors=errors,world_written=False,production_recipe_replay_pending=True)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
    for file,data in[('manifest.json',manifest),('functional-check.json',check),('changes.json',changes)]:
        (a.out/file).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    old=next(q for q in previous['anchors']if q['key']=='entry_5')
    metadata=dict(original_id=old['old_id'],old_path=old['old_path'],new_path=list(reversed(aft['street_213']['path'])),
        reason='Original start has AIR bearing; new three-wide supported stairs connect to current street without changing old blocks.',
        installed=False,authority_modified=False,depends_on_candidate=str(a.out),original_anchor_remains_unmodified=True)
    (a.out/'metadata-candidate.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),'utf8')
    for phase,reader in[('before',base),('after',after)]:render(reader,[-707,90,207,-692,105,219],a.out/(phase+'.png'),'西部城区站·站厅至当前街道人行道 '+phase)
    print('West street stair',len(changes),'cells;',len(columns),'supports;',len(guards),'guards; errors',errors,flush=True)
    if errors:raise ValueError('Candidate not ready')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('fresh','context','installed-bridge','metadata','native','models','review','out'):p.add_argument('--'+k,type=Path,required=True)
    run(p.parse_args())
