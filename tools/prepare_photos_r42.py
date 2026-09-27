"""Native visual coverage of all live stations and the revised NERV interiors."""
from pathlib import Path
import argparse,json,math

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW';OUT=ROOT/'artifacts/rebuild_r42/photos'


def main(group='all'):
    OUT.mkdir(parents=True,exist_ok=True);views=[]
    def add(name,at,target,required):
        dx=target[0]-at[0];dy=target[1]-at[1]-1.62;dz=target[2]-at[2]
        views.append(dict(file='r42_'+name+'.png',position=at,yaw=math.degrees(math.atan2(-dx,dz)),pitch=-math.degrees(math.atan2(dy,math.hypot(dx,dz))),warmupTicks=190,requiredSections=required))
    if group in ('all','interiors'):
        views.extend(json.loads((ROOT/'artifacts/rebuild_r42/wall_art_cameras.json').read_text('utf8')))
        views[0]['position']=[20.5,-417,266];views[0]['yaw']=180;views[0]['pitch']=-math.degrees(math.atan2(.88,8))
        add('upper_lift_closed_flanks',[90.5,-369,-60.5],[93,-368,-53],[[90,-369,-55],[96,-367,-55],[92,-370,-58]])
        add('command_seating',[37.5,-420,290.5],[31,-419,288],[[31,-422,288],[33,-420,291],[30,-419,285]])
        for r in json.loads((ROOT/'artifacts/spatial_repair_r41/photos/itinerary.json').read_text('utf8')):
            if 'reported_' in r['file']:
                row=dict(r,file=r['file'].replace('r41_','r42_'));views.append(row)
    if group in ('all','stations','entrances'):
        original=json.loads((ROOT/'artifacts/world_combat_r40/final_photos/station_manifest.json').read_text('utf8'))
        platforms={p['id']:p for p in json.loads((ROOT/'artifacts/world_combat_r40/stations/actual_platforms.json').read_text('utf8'))['platforms']}
        seen=set();manifest=[]
        for row in original:
            if row['station'] in seen:continue
            seen.add(row['station']);p=platforms[row['platform']];at=row['position'];centre=p['centre'];required=[list(map(math.floor,centre)),[math.floor(at[0]),math.floor(at[1]),math.floor(at[2])]]
            for end in p['ends']:
                q=list(map(math.floor,centre));q[0 if p['axis']=='x' else 2]=end;q[1]+=8;required.append(q)
            item=dict(file=f'r42_station_{len(manifest):02d}.png',position=at,yaw=row['yaw'],pitch=5,warmupTicks=210,requiredSections=required)
            views.append(item);manifest.append(dict(item,station=row['station'],platform=row['platform']))
        (OUT/'station_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
        entries=json.loads((ROOT/'artifacts/rebuild_r42/station_entrances/contract.json').read_text('utf8'))['placements']
        for i,row in enumerate(entries):
            if i not in (0,1,4,8,12,16,20,23):continue
            q=row['board'];n={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[row['face']]
            at=[row['reader'][0]+n[0]*3,row['reader'][1],row['reader'][2]+n[1]*3]
            add(f'entrance_{i:02d}',at,[q[0]+.5,q[1]+1,q[2]+.5],[q,[q[0],q[1]-2,q[2]],[q[0],q[1]+2,q[2]]])
    if group=='entrances':views=[row for row in views if '_entrance_' in row['file']]
    # A cold arrival at the distant residential terminus needs the surrounding
    # station columns to load as well as the nearby board's own section.
    if group=='entrances':views[0]['warmupTicks']=650
    # Embeddium legitimately never compiles sections behind this camera.
    # Retain visible target geometry checks, rather than waiting on an unseen
    # opposite platform end forever (or accepting a timed-out blank picture).
    for row in views:
        yaw=math.radians(row['yaw']);at=row['position'];forward=(-math.sin(yaw),math.cos(yaw))
        visible=[]
        for q in row['requiredSections']:
            dx=q[0]+.5-at[0];dz=q[2]+.5-at[2];distance=math.hypot(dx,dz)
            if distance<2.5 or (dx*forward[0]+dz*forward[1])>distance*.4:visible.append(q)
        assert visible,('Camera lacks a visible geometry witness',row['file'])
        row['requiredSections']=visible
    from measure_world_r40 import MeasuredWorld
    w=MeasuredWorld(WORLD)
    for row in views:w.around(row['position'],2)
    w.load();shapes=json.loads((WORLD/'native_collision_shapes.json').read_text('utf8'));invalid=[]
    for row in views:
        at=row['position'];eye=(at[0],at[1]+1.62,at[2]);cell=tuple(math.floor(v) for v in eye);state=w.block(cell)
        boxes=shapes.get(state,[] if state=='minecraft:air' else [[0,0,0,1,1,1]])
        if any(all(cell[i]+b[i]<=eye[i]<=cell[i]+b[i+3] for i in range(3)) for b in boxes):invalid.append((row['file'],cell,state))
    assert not invalid,('Camera preflight rejected solid geometry',invalid)
    (WORLD/'r30_photo_views.json').write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8')
    (OUT/f'{group}_itinerary.json').write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8')
    spec=json.loads((ROOT/'.Codex/client-r42-art-after.json').read_text('utf8'))
    spec['command']=[x for x in spec['command'] if not x.startswith('-Dprojectseele.photoRenderDistance=')]
    spec['command'][1:1]=['-Dprojectseele.photoRenderDistance=14']
    (ROOT/f'.Codex/client-r42-{group}-photos.json').write_text(json.dumps(spec),'utf8')
    print('Prepared',len(views),'native cameras',group)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',choices=['all','interiors','stations','entrances'],default='all');main(p.parse_args().group)
