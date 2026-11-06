"""Build a standard array candidate from a complete, cold-captured source.

The source must contain all surface sections of the five changed chunks. It is
never supplemented with fabricated air. This command does not access the world.
"""
import argparse,json,copy
from collections import defaultdict,Counter
from pathlib import Path
import nbtlib
import numpy as np
from export_hakone_station_surface import export
from author_hakone_lakefront import Editor
from map_pipeline.station_sections import StationSections
from audit_mountain_station_access import Nav
from propose_mountain_station_steps import Overlay

def run(a):
    proposal=json.loads(a.proposal.read_text('utf8'));changes=proposal['changes']
    if len(changes)!=45 or Counter(r['station']for r in changes)!=Counter(ubako=18,sounzan=18,togendai=9):
        raise ValueError('Unexpected approved station-step scope')
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'slices').mkdir();(a.out/'source').mkdir();(a.out/'delta').mkdir()
    groups=[('ubako',[-16,816,-1,831]),('sounzan',[640,768,655,783]),('togendai',[-320,992,-305,1039])]
    source_rows=defaultdict(list);captures=[];devices=[];actors=[]
    for name,bounds in groups:
        part=a.out/'slices'/name;export(a.source,bounds,part)
        capture=json.loads((part/'capture.json').read_text('utf8'));captures.append(capture);actors+=capture['actors']
        devices+=list(nbtlib.load(part/'captured-devices.dat')['Devices'])
        for file in (part/'source').glob('*.npz'):
            with np.load(file)as f:source_rows[file.name].append({k:f[k]for k in f.files})
    for name,rows in source_rows.items():
        names=[];ids={};blocks=[];coords=[]
        for row in rows:
            remap=[]
            for state in map(str,row['palette']):
                if state not in ids:ids[state]=len(names);names.append(state)
                remap.append(ids[state])
            blocks.append(np.asarray(remap,np.uint16)[row['blocks']]);coords.append(row['coordinates'])
        coordinates=np.concatenate(coords)
        if len(set(map(tuple,coordinates)))!=len(coordinates):raise ValueError('Duplicate exported chunk')
        np.savez_compressed(a.out/'source'/name,coordinates=coordinates,blocks=np.concatenate(blocks),palette=np.asarray(names))
    protected={tuple(int(t[k])for k in('x','y','z'))for t in devices}
    e=Editor(a.out)
    for row in changes:
        p=row['pos'];state=e.state(*p,original=True)
        if state!=row['before'] or state!='minecraft:smooth_stone':raise ValueError('Changed cold source '+str((p,state)))
        if tuple(p)in protected:raise ValueError('Existing device host')
        if row['after']!='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]':raise ValueError('Unexpected step material')
        if e.state(p[0],p[1]-1,p[2])!=row['bearing']:raise ValueError('Changed bearing')
        e.put(*p,row['after'])
    regions=e.save()
    if sum(r['cells']for r in regions)!=45:raise ValueError('Unexpected delta count')
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](devices)}).save(a.out/'captured-devices.dat',gzipped=True)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
    bounds=[-320,768,655,1039]
    capture=dict(world=captures[0]['world'],bounds_xz=bounds,
        source_files=['source/'+name for name in sorted(source_rows)],chunk_statuses={'full':5},
        measured_chunks=sorted({tuple(p)for row in source_rows.values()for part in row for p in part['coordinates'].tolist()}),
        actors=actors,unavailable_chunks=[],sparse_source_only=True,unlisted_chunks_not_captured=True,
        exact_station_source=str(a.source),world_written=False)
    (a.out/'capture.json').write_text(json.dumps(capture,ensure_ascii=False,indent=2),'utf8')
    (a.out/'step-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),'utf8')
    # Repeat the access proof against the cold source for its five exact chunks,
    # retaining the previous wider current snapshot only for unchanged context.
    old=StationSections(Path(proposal['source']));fresh=StationSections(a.source)
    class Joined:
        def state(self,x,y,z):
            state=fresh.state(x,y,z)
            return old.state(x,y,z)if state is None else state
        def box(self,b):
            blocks,palette=old.box(b);new,names=fresh.box(b);ids={s:i for i,s in enumerate(palette)};remap=[]
            for state in names:
                if state not in ids:ids[state]=len(palette);palette.append(state)
                remap.append(ids[state])
            mask=new!=0;blocks[mask]=np.asarray(remap,np.uint16)[new[mask]]
            return blocks,palette
    before=Joined();after=Overlay(before,changes)
    review=json.loads(a.review.read_text('utf8'));shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    proofs=[];errors=[]
    for spec in review['stations']:
        if spec['id']not in {'ubako','sounzan','togendai'}:continue
        passes=[]
        for label,reader in [('before',before),('after',after)]:
            nav=Nav(reader,spec['bounds'],shapes,True);goals,count=nav.routes(spec['goals'],spec['start'])
            passes.append(dict(phase=label,reachable_nodes=count,goals=goals))
        required={'ubako':['ropeway_boarding'],'sounzan':['ropeway_boarding','viewing_terrace'],
                  'togendai':['restaurant','boat_hall','pontoon','ropeway_boarding']}[spec['id']]
        for name in required:
            goal=next(g for g in passes[-1]['goals']if g['name']==name)
            if not goal['reachable']:errors.append([spec['id'],name,'still unreachable'])
        proofs.append(dict(station=spec['id'],passes=passes))
    manifest=dict(world=capture['world'],kind='measured-mountain-station-step-repair',bounds_xz=bounds,
        regions=regions,cells=45,station_cells=dict(Counter(r['station']for r in changes)),
        changed_chunks=capture['measured_chunks'],device_changes=0,actor_changes=0,native_changes=0,
        geometry='Existing full stone riser top changed to bottom slab; all original foundation blocks preserved.',
        world_written=False,production_recipe_replay_pending=True,source_snapshot=str(a.source))
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,changed_cells=45,
        station_cells=manifest['station_cells'],existing_devices=len(devices),existing_actors=len(actors),
        device_changes=0,actor_changes=0,native_changes=0,maximum_local_riser=.5,
        before_after_routes=proofs,world_written=False,current_native_collision_export_pending=True,
        live_passenger_validation_pending=True),ensure_ascii=False,indent=2),'utf8')
    print('Prepared standard station step candidate:',45,'cells;',len(devices),'preserved devices;',len(actors),'preserved actors; errors',errors,flush=True)
    if errors:raise ValueError('Candidate access proof failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','proposal','review','metadata','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
