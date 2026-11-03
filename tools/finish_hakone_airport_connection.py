"""Clear the retained airport doorway and audit the final composed connection.

Only an offline candidate is edited. Existing terminal floor, tactile paving,
canopy, signs, station and runway remain original; publication uses the shared
cold-world installer after recipe replay and independent corridor checks.
"""
import argparse
import json
import os
import shutil
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.launch_earthworks import ground
from map_pipeline.corridors import alignment
from map_pipeline.launch_protection import load, check_candidate
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT


def street_details(e,candidate):
    spec=json.loads((candidate/'authored-design.json').read_text('utf8'))['streets'][0]
    curve,s=alignment(spec)
    with np.load(candidate/'earthworks'/(spec['id']+'.npz'))as f:d={k:f[k]for k in f.files}
    bx,bz,_,_=map(int,d['bounds']);floor,slab=road_blocks(d['grade2'])
    near=int(np.argmin(np.linalg.norm(curve[:,[0,2]]-[740,1025],axis=1)))
    tangent=curve[near+1,[0,2]]-curve[near-1,[0,2]];tangent/=np.linalg.norm(tangent)
    normal=np.array([-tangent[1],tangent[0]]);crossing=[]
    for x in range(732,749):
        for z in range(1017,1036):
            j,i=z-bz,x-bx;offset=np.array([x,z])-curve[near,[0,2]]
            if not d['road'][j,i] or abs(offset@tangent)>3 or abs(offset@normal)>3.5:continue
            if int(np.floor(offset@normal+.5))%2:continue
            y=int(floor[j,i]);state='projectseele:road_marking_slab[type=bottom,waterlogged=false]'if slab[j,i]else'minecraft:white_concrete'
            if e.state(x,y,z)!=state:e.put(x,y,z,state);crossing.append([x,y,z])
    lamps=[]
    for station in (15,45,float(s[-1]-82),float(s[-1]-40)):
        k=int(np.argmin(abs(s-station)));t=curve[k+1,[0,2]]-curve[k-1,[0,2]];t/=np.linalg.norm(t)
        n=np.array([-t[1],t[0]])
        for side in (1,-1):
            x,z=map(int,np.rint(curve[k,[0,2]]+side*7.5*n));j,i=z-bz,x-bx
            if d['walk'][j,i]:continue
            road_y=int(floor[j,i]);base=None
            for y in range(road_y+1,road_y-3,-1):
                if e.state(x,y,z).split('[')[0]not in SOIL:continue
                if all(e.state(x,h,z).split('[')[0]in AIR for h in range(y+1,y+7)):
                    base=y;break
            if base is None:continue
            e.put(x,base+1,z,'minecraft:polished_deepslate')
            for y in range(base+2,base+6):e.put(x,y,z,'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')
            e.put(x,base+6,z,'minecraft:sea_lantern');lamps.append([x,base+1,z]);break
    return dict(crossing_marking_cells=crossing,lamps=lamps,clear_pavement_obstructed=False)


def finish(source, out, world):
    for name in ('functional-check.json', 'independent-check.json', 'tunnel-check.json'):
        if json.loads((source/name).read_text('utf8'))['errors']:
            raise ValueError('Unverified input '+name)
    out.mkdir(parents=True, exist_ok=False)
    (out/'source').mkdir()
    for file in (source/'source').glob('*.npz'):
        os.link(file, out/'source'/file.name)
    for name in ('delta', 'earthworks', 'plan'):
        shutil.copytree(source/name, out/name)
    for name in ('manifest.json', 'authored-design.json', 'functional-check.json'):
        shutil.copy2(source/name, out/name)
    e=Editor(out); cleared=[];paved_corners=[]
    for x in range(738,743):
        state=e.state(x,80,1042)
        if state.split('[')[0]in SOIL:
            e.put(x,80,1042,'minecraft:smooth_stone');paved_corners.append([x,80,1042,state])
        elif state.split('[')[0]not in PAVEMENT:raise ValueError('Unexpected approach corner floor')
        for y in range(81,89):
            state=e.state(x,y,1042)
            if state.split('[')[0]in SOIL|PLANTS:
                e.put(x,y,1042,'minecraft:air');cleared.append([x,y,1042,state])
            elif y<=83 and state.split('[')[0]not in AIR|{'minecraft:light'}:raise ValueError('Approach corner blocked')
    for x in range(737,744):
        for z in range(1043,1056):
            floor=e.state(x,80,z)
            if not (floor.startswith('projectseele:station_tactile_') or floor=='projectseele:nerv_floor_panel'):
                raise ValueError(('Unexpected retained entrance floor',x,z,floor))
            for y in range(81,89):
                state=e.state(x,y,z)
                if state.split('[')[0] in SOIL|PLANTS:
                    e.put(x,y,z,'minecraft:air');cleared.append([x,y,z,state])
                elif y<=83 and state.split('[')[0] not in AIR|{'minecraft:light'}:
                    raise ValueError(('Retained entrance obstruction',x,y,z,state))
    # The shallow approach grading may extend beneath the retained apron.
    # Restore its original finite bearing courses, rather than leaving native
    # floor panels suspended above an excavated natural-soil pocket.
    restored=[]
    for x in range(635,846):
        for z in range(1043,1128):
            if e.state(x,80,z,True).split('[')[0]in SOIL|PLANTS|AIR:continue
            for y in range(77,80):
                original=e.state(x,y,z,True)
                if e.state(x,y,z)!=original:
                    e.put(x,y,z,original);restored.append([x,y,z])
    details=street_details(e,out)
    patches=e.save()
    with np.load(out/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    gx,gz,_,_=map(int,d['bounds'])
    h=ground(e,[737,1042,743,1055])
    for x,_,z,_ in cleared+paved_corners:d['ground'][z-gz,x-gx]=h[z-1042,x-737]
    for x,_,z in details['crossing_marking_cells']:d['marking'][z-gz,x-gx]=True
    if restored:
        bounds=[min(p[0]for p in restored),min(p[2]for p in restored),max(p[0]for p in restored),max(p[2]for p in restored)]
        support_ground=ground(e,bounds)
        for x,_,z in restored:d['ground'][z-gz,x-gx]=support_ground[z-bounds[1],x-bounds[0]]
    np.savez_compressed(out/'plan/network.npz',**d)
    manifest=json.loads((out/'manifest.json').read_text('utf8'))
    manifest.update(regions=patches,cells=sum(r['cells']for r in patches),
                    airport_street_details=details,
                    airport_entrance=dict(natural_cells_cleared=len(cleared),floor_preserved=True,
                                          approach_corners_paved=len(paved_corners),original_bearing_cells_restored=len(restored),
                                          scope=[737,80,1042,743,88,1055]))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (out/'entrance-clearance.json').write_text(json.dumps(dict(cleared=cleared,paved_corners=paved_corners,
        restored_bearing_cells=restored,world_written=False),indent=2),'utf8')
    (out/'street-details.json').write_text(json.dumps(details,indent=2),'utf8')
    (out/'launch-protection.json').write_text(json.dumps(check_candidate(load(world),out),indent=2),'utf8')
    return verify(out)


def verify(candidate):
    e=Editor(candidate);errors=[];kept=0
    bearings=0
    for x in range(635,846):
        for z in range(1043,1128):
            if e.state(x,80,z,True).split('[')[0]in SOIL|PLANTS|AIR:continue
            for y in range(77,80):
                if e.state(x,y,z)!=e.state(x,y,z,True):errors.append(['terminal bearing changed',x,y,z])
                bearings+=1
    entrance_paving=PAVEMENT|{'projectseele:station_tactile_path','projectseele:station_tactile_warning'}
    for x in range(738,743):
        for z in range(1030,1056):
            state=e.state(x,80,z)
            if state.split('[')[0]not in entrance_paving:errors.append(['entrance floor',x,z,state])
            for y in range(81,84):
                if e.state(x,y,z).split('[')[0]not in AIR|{'minecraft:light'}:errors.append(['entrance headroom',x,y,z])
            if z>=1043:
                if state!=e.state(x,80,z,True):errors.append(['original floor changed',x,z])
                kept+=1
    curves=json.loads((candidate/'plan/native-curves.json').read_text('utf8'))
    rail=np.asarray([p for row in curves['trains']for p in row['points']],float)
    railtree=cKDTree(rail[:,[0,2]])
    changed=0
    for path in (candidate/'delta').glob('*.npz'):
        with np.load(path)as f:
            names=list(map(str,f['palette']));bare=[n.split('[')[0]for n in names]
            for i,(cx,cz)in enumerate(f['coordinates']):
                lo,hi=f['ranges'][i:i+2];at=f['indices'][lo:hi].astype(np.int64)
                q=np.column_stack((int(cx)*16+at%16,at//256-128,int(cz)*16+(at//16)%16))
                before=f['before'][lo:hi];changed+=len(q)
                for (x,y,z),old in zip(q,before):
                    if 475<=x<=895 and 1130<=z<=1505 and y==80:errors.append(['apron floor changed',int(x),int(y),int(z)])
                    if 664<=x<=816 and 1170<=z<=1210 and 80<=y<=110:errors.append(['station changed',int(x),int(y),int(z)])
                    if 400<=x<=510 and 1140<=z<=1200 and 70<=y<=105 and bare[old]not in SOIL|PLANTS|AIR:
                        errors.append(['rail bridge or footing changed',int(x),int(y),int(z),names[old]])
                    if 635<=x<=845 and 1040<=z<=1127 and 79<=y<=105 and bare[old]not in SOIL|PLANTS|AIR:
                        errors.append(['terminal object changed',int(x),int(y),int(z),names[old]])
                near=railtree.query_ball_point(q[:,[0,2]],4)
                for pos,ids in zip(q,near):
                    if ids and np.any((rail[ids,1]-3<=pos[1])&(pos[1]<=rail[ids,1]+8)):
                        errors.append(['native rail envelope changed',*map(int,pos)])
    covers=[];ridge_changes=0
    for path in (candidate/'earthworks').glob('*.npz'):
        with np.load(path)as f:d={k:f[k]for k in f.files}
        if not d['tunnel'].any():continue
        actual=ground(e,list(map(int,d['bounds'])));floor,_=road_blocks(d['grade2'])
        cover=actual-floor-int(d['clearance'])-2
        covers.extend(map(int,cover[d['tunnel']]))
        ridge_changes+=int(((actual!=d['old'])&d['tunnel']).sum())
        if np.any(d['tunnel']&(cover<0)):errors.append(['final composed tunnel roof exposed'])
    report=dict(errors=errors,changed_cells=changed,entrance_width=5,entrance_length=26,
                original_terminal_bearing_cells_checked=bearings,
                original_entrance_floor_columns_checked=kept,final_minimum_tunnel_cover=min(covers),
                tunnel_surface_columns_changed_by_later_composition=ridge_changes,
                native_rail_station_apron_terminal_preserved=not errors,
                actual_game_visual_acceptance=False,whole_map_complete=False)
    (candidate/'airport-connection-check.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report if len(errors)<8 else dict(errors=len(errors),examples=errors[:8])),flush=True)
    if errors:raise ValueError('Airport connection failed final composed audit')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--source',type=Path);p.add_argument('--out',type=Path)
    p.add_argument('--world',type=Path);p.add_argument('--verify',type=Path)
    a=p.parse_args()
    if a.verify:verify(a.verify)
    else:
        if not all((a.source,a.out,a.world)):p.error('Supply source, out and world')
        finish(a.source,a.out,a.world)
