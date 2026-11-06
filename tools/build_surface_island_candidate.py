"""Package one verified island proposal against a fresh FULL offline capture."""
import argparse,json,math
from pathlib import Path
import nbtlib
from export_hakone_station_surface import export
from author_hakone_lakefront import Editor
from audit_oldcity_surface_station_access import MainlineSweep,SupplementedSections
from build_gora_protected_transfer import IndependentWalker
from propose_mountain_station_steps import Overlay
from audit_mountain_station_access import shape_for
from review_underground_station_evidence import strict_walk
from render_hakone_voxel_3d import render

def run(a):
    proposal=json.loads(a.proposal.read_text('utf8'))
    if proposal['errors']:raise ValueError('Proposal has unresolved errors')
    chunks=proposal['full_chunks_needed'];cx=min(p[0]for p in chunks);cX=max(p[0]for p in chunks);cz=min(p[1]for p in chunks);cZ=max(p[1]for p in chunks)
    export(a.fresh,[cx*16,cz*16,cX*16+15,cZ*16+15],a.out)
    editor=Editor(a.out);changes=proposal['changes']
    devices={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']}
    for c in changes:
        if editor.state(*c['pos'])!=c['before']:raise ValueError('Fresh before mismatch '+str(c['pos']))
        if tuple(c['pos'])in devices:raise ValueError('Protected block entity')
        editor.put(*c['pos'],c['after'])
    regions=editor.save()
    if sum(q['cells']for q in regions)!=len(changes):raise ValueError('Changed-cell count mismatch')
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
    reader=SupplementedSections(a.context,a.fresh);after=Overlay(reader,changes)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    for row in proposal['shape_aliases']:
        if row['state']not in shapes:shapes[row['state']]=shapes[row['same_collision_class_and_properties_as']]
    baseline=json.loads(a.review.read_text('utf8'));snap=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    sweep=MainlineSweep(snap,model,baseline['bounds']);walker=IndependentWalker(after,shapes,sweep)
    proofs=[];errors=[]
    for row in proposal['goals']:
        proof=dict(goal=row['goal'],forward=strict_walk(walker,row['path']),reverse=strict_walk(walker,list(reversed(row['path']))))
        if any(proof[d]['kind']!='strict_static_clear'for d in('forward','reverse')):errors.append('Fresh path failed '+row['goal'])
        proofs.append(proof)
    intrusions=[]
    for c in changes:
        x,y,z=c['pos'];boxes,_=shape_for(c['after'],shapes,True)
        if boxes is None:errors.append('Unknown collision');continue
        for b in boxes:
            if sweep.intersects(x+(b[0]+b[3])/2,z+(b[2]+b[5])/2,(b[3]-b[0])/2,(b[5]-b[2])/2,y+b[1],y+b[4]):intrusions.append(c);break
    if intrusions:errors.append('Vehicle envelope intrusion')
    tread=next(c for c in changes if c['after']=='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    x,y,z=tread['pos'];p=[x+.5,y+.5,z+.5];negatives=[]
    for name,patch in[
        ('missing_half_step',dict(pos=[x,y,z],after='minecraft:air')),
        ('blocked_step_headroom',dict(pos=[x,y+2,z],after='minecraft:stone_bricks'))]:
        proof=strict_walk(IndependentWalker(Overlay(after,[patch]),shapes,sweep),[p])
        negatives.append(dict(case=name,result=proof,rejected=proof['kind']!='strict_static_clear'))
        if proof['kind']=='strict_static_clear':errors.append('Injected fault not rejected')
    capture=json.loads((a.out/'capture.json').read_text('utf8'))
    manifest=dict(world=capture['world'],kind='measured-surface-station-island-stair',bounds_xz=capture['bounds_xz'],bounds_3d=proposal['bounds'],
        regions=regions,cells=len(changes),changed_chunks=chunks,source_snapshot=str(a.fresh),functional_errors=errors,
        device_changes=0,actor_changes=0,native_changes=0,world_written=False,production_recipe_replay_pending=True)
    check=dict(errors=errors,changed_cells=len(changes),before_states_all_exact=True,fresh_path_proofs=proofs,negative_tests=negatives,
        vehicle_intrusions=intrusions,train_reservation=sweep.info(),preserved_devices=len(devices),preserved_actors=len(capture['actors']),
        shape_aliases=proposal['shape_aliases'],world_written=False,installed=False,current_native_collision_and_live_boarding_pending=True)
    for filename,data in [('manifest.json',manifest),('functional-check.json',check),('changes.json',changes),('proposal.json',proposal)]:
        (a.out/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    names=sorted({c['after']for c in changes if'trapdoor'in c['after']or'iron_bars'in c['after']})
    (a.out/'railing-collision-shapes.json').write_text(json.dumps({s:shapes[s]for s in names},indent=2),'utf8')
    b=proposal['bounds'];crop=[b[0]-5,b[1]-3,b[2]-5,b[3]+5,b[4]+5,b[5]+5]
    for phase,e in [('before',reader),('after',after)]:render(e,crop,a.out/(phase+'.png'),proposal['station']+'·岛台接入 '+phase)
    print('Packaged',proposal['station'],len(changes),'cells;',len(devices),'devices kept;',len(proofs),'fresh bidirectional routes; errors',errors,flush=True)
    if errors:raise ValueError('Candidate needs revision')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('proposal','fresh','context','metadata','review','native','models','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
