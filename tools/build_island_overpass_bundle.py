"""Merge eight disjoint FULL captures into a standard, uninstalled bridge patch.

All 3096 changes must be additions to real captured AIR. Original devices,
APGs, boarding aprons, lamps and wooden structures remain byte-for-byte source
data. Only sparse measured chunks are exported, never rectangle-gap air.
"""
import argparse,json,math
from collections import defaultdict,Counter,deque
from pathlib import Path
import nbtlib
import numpy as np
from export_hakone_station_surface import export
from author_hakone_lakefront import Editor
from audit_mountain_station_access import SupplementedSections,shape_for
from propose_mountain_station_steps import Overlay
from audit_oldcity_surface_station_access import MainlineSweep
from build_gora_protected_transfer import IndependentWalker
from review_underground_station_evidence import strict_walk
from render_hakone_voxel_3d import render
from propose_remaining_surface_island_access import point,FULL

def world_point(s,u,y,w):
    sign=s['side'] if s['axis']=='x' else-s['side']
    cross=s['cross']+w if sign>0 else s['cross']+1-w
    return [u,y,cross]if s['axis']=='x'else[cross,y,u]

def guard_probes(walker,q):
    s=q['spec'];P=s['upper'];end=s['end'];probes=[]
    for u in range(s['start']+1,end):
        feet=P+1+(u-s['start'])/2
        for side in(-.1,1.1,10.1,12.9):probes.append(('stair',world_point(s,u+.5,feet,side)))
    for w in range(13):probes.append(('bridge-back',world_point(s,end+2.2,P+7,w+.5)))
    for w in range(1,10):probes.append(('bridge-front',world_point(s,end+.8,P+7,w+.5)))
    for u in range(end,end+3):probes.append(('island-side',world_point(s,u+.5,P+7,.2)))
    probes.append(('outer-side',world_point(s,end+1.5,P+7,12.2)))
    out=[]
    for label,p in probes:
        hit=walker.body(*p)
        valid=hit is not None and hit.get('kind')=='body_obstruction'and any(k in hit.get('state','')for k in('iron_trapdoor','iron_bars'))
        out.append(dict(edge=label,player=p,obstruction=hit,guard_blocked=valid))
    return out

def attached_components(reader,changes,shapes):
    """Face-contact connectivity of actual collision parts to retained blocks."""
    new={tuple(c['pos']):c['after']for c in changes};cache={}
    def boxes(p):
        if p not in cache:
            bs,_=shape_for(reader.state(*p)or'__unavailable__',shapes,True)
            cache[p]=[np.asarray(b,float)+np.asarray([*p,*p])for b in(bs or[])]
        return cache[p]
    def touch(a,b):
        for k in range(3):
            if abs(a[k+3]-b[k])<1e-7 or abs(b[k+3]-a[k])<1e-7:
                other=[i for i in range(3)if i!=k]
                if all(min(a[i+3],b[i+3])-max(a[i],b[i])>1e-7 for i in other):return True
        return False
    links=defaultdict(set);roots=set()
    for p in new:
        for k in range(3):
            for d in(-1,1):
                q=list(p);q[k]+=d;q=tuple(q)
                if any(touch(a,b)for a in boxes(p)for b in boxes(q)):
                    if q in new:links[p].add(q)
                    else:roots.add(p)
    reached=set(roots);queue=deque(roots)
    while queue:
        for p in links[queue.popleft()]:
            if p not in reached:reached.add(p);queue.append(p)
    return dict(added_blocks=len(new),directly_attached_to_retained_blocks=len(roots),
        attached_via_positive_area_collision_face_contacts=len(reached),unattached=[list(p)for p in sorted(set(new)-reached)])

def run(a):
    reports=[json.loads(p.read_text('utf8'))for p in sorted(a.proposals.glob('native-*.json'))]
    if any(r['errors']for r in reports):raise ValueError('Proposal unresolved')
    changes=[c for r in reports for c in r['changes']]
    if len(changes)!=3096 or any(c['before']!='minecraft:air'for c in changes):raise ValueError('Unexpected addition-only bridge scope')
    a.out.mkdir(exist_ok=False);(a.out/'slices').mkdir();(a.out/'source').mkdir();(a.out/'delta').mkdir()
    sites=json.loads((a.proposals/'capture-sites.json').read_text('utf8'));groups=defaultdict(list);captures=[];devices=[];actors=[]
    for site in sites:
        x,y,z,X,Y,Z=site['bounds'];part=a.out/'slices'/site['id'];export(a.fresh,[x,z,X,Z],part)
        cap=json.loads((part/'capture.json').read_text('utf8'));captures.append(cap);actors+=cap['actors'];devices+=list(nbtlib.load(part/'captured-devices.dat')['Devices'])
        for f in(part/'source').glob('*.npz'):
            with np.load(f)as p:groups[f.name].append({k:p[k]for k in p.files})
    all_chunks=[]
    for name,parts in groups.items():
        palette=[];ids={};blocks=[];coords=[]
        for row in parts:
            codes=[]
            for s in map(str,row['palette']):
                if s not in ids:ids[s]=len(palette);palette.append(s)
                codes.append(ids[s])
            blocks.append(np.asarray(codes,np.uint16)[row['blocks']]);coords.append(row['coordinates'])
        coordinates=np.concatenate(coords)
        if len(set(map(tuple,coordinates)))!=len(coordinates):raise ValueError('Repeated source chunk')
        all_chunks+=coordinates.tolist()
        np.savez_compressed(a.out/'source'/name,coordinates=coordinates,blocks=np.concatenate(blocks),palette=np.asarray(palette))
    protected={tuple(int(d[k])for k in('x','y','z'))for d in devices}
    if len(protected)!=len(devices):raise ValueError('Duplicated block entities in merged source')
    editor=Editor(a.out)
    for c in changes:
        if editor.state(*c['pos'])!=c['before']:raise ValueError('Fresh source is no longer air '+str(c['pos']))
        if tuple(c['pos'])in protected:raise ValueError('Original device at proposed bridge')
        editor.put(*c['pos'],c['after'])
    regions=editor.save()
    if sum(r['cells']for r in regions)!=3096:raise ValueError('Delta mismatch')
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](devices)}).save(a.out/'captured-devices.dat',gzipped=True)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
    bounds=[min(p[0]for p in all_chunks)*16,min(p[1]for p in all_chunks)*16,max(p[0]for p in all_chunks)*16+15,max(p[1]for p in all_chunks)*16+15]
    capture=dict(world=captures[0]['world'],bounds_xz=bounds,source_files=['source/'+name for name in sorted(groups)],
        chunk_statuses={'full':len(all_chunks)},measured_chunks=sorted(all_chunks),actors=actors,unavailable_chunks=[],
        sparse_source_only=True,unlisted_chunks_not_captured=True,exact_station_source=str(a.fresh),world_written=False)
    (a.out/'capture.json').write_text(json.dumps(capture,ensure_ascii=False,indent=2),'utf8')
    source=SupplementedSections(a.context,a.supplement)
    # Add the new FULL chunks over the old whole-station contexts without any
    # fabricated gap cells; the supplied station reader keeps unknown distinct.
    fresh=SupplementedSections(a.context,a.fresh)
    class Combined:
        def state(self,x,y,z):
            v=fresh.extra.state(x,y,z)
            return source.state(x,y,z)if v is None else v
        def box(self,b):
            arr,pal=source.box(b);new,names=fresh.extra.box(b);ids={s:i for i,s in enumerate(pal)};codes=[]
            for state in names:
                if state not in ids:ids[state]=len(pal);pal.append(state)
                codes.append(ids[state])
            mask=new!=0;arr[mask]=np.asarray(codes,np.uint16)[new[mask]];return arr,pal
    before=Combined();after=Overlay(before,changes)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'));aliases=reports[0]['shape_aliases']
    for q in aliases:
        if q['state']not in shapes:shapes[q['state']]=shapes[q['same_collision_class_and_properties_as']]
    native=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    checks=[];errors=[];columns=[];all_probes=[];views=[]
    for report in reports:
        baseline=json.loads((a.review/(report['site']+'.json')).read_text('utf8'));sweep=MainlineSweep(native,model,baseline['bounds']);walker=IndependentWalker(after,shapes,sweep)
        paths=[]
        for q in report['goals']:
            p=dict(goal=q['goal'],forward=strict_walk(walker,q['path']),reverse=strict_walk(walker,list(reversed(q['path']))))
            if any(p[d]['kind']!='strict_static_clear'for d in('forward','reverse')):errors.append([report['site'],q['goal'],'fresh path failed'])
            paths.append(p)
        intrusion=[]
        for c in report['changes']:
            x,y,z=c['pos'];boxes,_=shape_for(c['after'],shapes,True)
            if boxes is None:errors.append('Unknown new collision');continue
            for b in boxes:
                if sweep.intersects(x+(b[0]+b[3])/2,z+(b[2]+b[5])/2,(b[3]-b[0])/2,(b[5]-b[2])/2,y+b[1],y+b[4]):intrusion.append(c);break
        if intrusion:errors.append([report['site'],'visible vehicle intrusion'])
        for q in report['islands']:
            unique={(tuple(c['pos']),c['top'])for c in q['supports']};col_rows=[]
            for pos,top in sorted(unique):
                x,y,z=pos;cells=[]
                for yy in range(y,top+1):
                    state=after.state(x,yy,z);boxes,_=shape_for(state,shapes,True);solid=boxes==FULL
                    if not solid:errors.append([q['spec']['id'],'broken column',[x,yy,z]])
                    cells.append(dict(pos=[x,yy,z],state=state,full_collision_bearing=solid))
                col_rows.append(dict(base=list(pos),top_y=top,cells=cells,continuous=all(c['full_collision_bearing']for c in cells)))
            columns.append(dict(island=q['spec']['id'],columns=col_rows,column_count=len(col_rows)))
            probes=guard_probes(walker,q)
            if any(not p['guard_blocked']for p in probes):errors.append([q['spec']['id'],'guard probe failed'])
            all_probes.append(dict(island=q['spec']['id'],probes=probes,count=len(probes)))
            points=[r['pos']for r in q['changes']];b=[min(p[k]for p in points)for k in range(3)]+[max(p[k]for p in points)for k in range(3)]
            crop=[b[0]-4,q['spec']['upper']-2,b[2]-4,b[3]+4,b[4]+4,b[5]+4]
            views.append(render(after,crop,a.out/'views'/(q['spec']['id']+'.png'),report['station']+'·保留原结构的跨线岛台桥'))
        checks.append(dict(station=report['station'],site=report['site'],fresh_paths=paths,vehicle_intrusions=intrusion,
            original_apron_proofs=report['boarding_apron_proofs'],train_sweep=sweep.info()))
    contact=attached_components(after,changes,shapes)
    if contact['unattached']:errors.append('Added collision component not attached to retained structure')
    manifest=dict(world=capture['world'],kind='eight-retained-structure-island-overpasses',bounds_xz=bounds,
        regions=regions,cells=3096,island_cells=dict(Counter(c['island']for c in changes)),changed_chunks=sorted(all_chunks),
        source_snapshot=str(a.fresh),functional_errors=errors,device_changes=0,actor_changes=0,native_changes=0,
        original_blocks_modified=0,world_written=False,production_recipe_replay_pending=True)
    check=dict(errors=errors,stations=checks,bearing_columns=columns,guard_probes=all_probes,
        collision_attachment=contact,preserved_devices=len(devices),preserved_actors=len(actors),
        current_source_before_all_air=True,original_blocks_modified=0,vehicle_minimum_visible_soffit_gap=1.212410281251489,
        shape_aliases=aliases,current_native_collision_and_rendered_model_validation_pending=True,
        live_boarding_and_dynamic_gates_pending=True,world_written=False,installed=False)
    for name,value in [('manifest.json',manifest),('functional-check.json',check),('changes.json',changes),('views.json',views)]:
        (a.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    print('Overpass bundle: 3096 additions;',len(all_chunks),'FULL chunks;',len(devices),'devices retained;',sum(len(q['fresh_paths'])for q in checks),'bidirectional paths; errors',str(errors)[:350],flush=True)
    if errors:raise ValueError('Overpass candidate not ready')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('proposals','fresh','context','supplement','metadata','native','models','review','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
