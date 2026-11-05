"""Prepare a small offline stair correction, preserving exact before states.

No live world access or installation. Only known smooth-stone full risers become
bottom slabs; existing foundations, doors, rails and devices remain intact.
"""
import argparse,json,copy
from pathlib import Path
import nbtlib
import numpy as np
from map_pipeline.station_sections import StationSections
from audit_mountain_station_access import Nav

SLAB='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'

class Overlay:
    def __init__(self,reader,changes):self.reader=reader;self.changes={tuple(r['pos']):r['after'] for r in changes}
    def state(self,x,y,z):return self.changes.get((x,y,z),self.reader.state(x,y,z))
    def box(self,bounds):
        blocks,palette=self.reader.box(bounds);ids={s:i for i,s in enumerate(palette)}
        x,y,z,X,Y,Z=bounds
        for (xx,yy,zz),state in self.changes.items():
            if x<=xx<=X and y<=yy<=Y and z<=zz<=Z:
                if state not in ids:ids[state]=len(palette);palette.append(state)
                blocks[yy-y,zz-z,xx-x]=ids[state]
        return blocks,palette

def run(a):
    a.out.mkdir(parents=True,exist_ok=False);reader=StationSections(a.source)
    review=json.loads(a.review.read_text('utf8'));shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    proposals=[]
    for i in range(1,7):
        for x in range(-13,-10):proposals.append(('ubako',[x,139+i,830-2*i]))
        for x in range(646,649):proposals.append(('sounzan',[x,110+i,767+2*i]))
    for z,y in ((1034,104),(1019,109),(1004,114)):
        for x in range(-310,-307):proposals.append(('togendai',[x,y,z]))
    devices={tuple(int(t[k])for k in ('x','y','z'))for t in nbtlib.load(a.source/'devices.dat')['Devices']}
    changes=[]
    for site,p in proposals:
        before=reader.state(*p)
        if before!='minecraft:smooth_stone':raise ValueError('Unexpected full riser: '+str((p,before)))
        if tuple(p)in devices:raise ValueError('Protected device: '+str(p))
        below=reader.state(p[0],p[1]-1,p[2])
        if below not in ('minecraft:stone_bricks','minecraft:smooth_stone'):raise ValueError('Unverified bearing: '+str((p,below)))
        changes.append(dict(station=site,pos=p,before=before,after=SLAB,bearing=below))
    overlay=Overlay(reader,changes);proofs=[]
    for spec in review['stations']:
        if spec['id']not in {'ubako','sounzan','togendai'}:continue
        nav=Nav(overlay,spec['bounds'],shapes,True);goals,count=nav.routes(spec['goals'],spec['start'])
        proofs.append(dict(station=spec['id'],reachable_nodes=count,goals=goals))
        print(spec['id'],count,[(g['name'],g['reachable'])for g in goals],flush=True)
    report=dict(kind='offline-exact-station-step-proposal',changes=changes,changed_cells=len(changes),
        source=str(a.source),existing_device_cells_modified=0,world_written=False,installed=False,
        native_transit_modified=False,doors_modified=False,maximum_riser=.5,
        validation=proofs,current_collision_export_pending=True,production_recipe_replay_pending=True,
        live_passenger_validation_pending=True)
    (a.out/'proposal.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in ('source','review','metadata','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
