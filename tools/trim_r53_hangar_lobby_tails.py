"""Shorten the two authored hangar lobbies at their existing lift connections.

The R53 access proposal supplies ownership and exact original fabric. This does
not identify rooms from air, erase a waiting area, or alter the moving cabins.
"""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

from query_blocks import read_box, iter_block_entities, AIR
from repair_r53_reported_landings import apply

DIM='projectseele:geofront'


def plan(world, base, output):
    history=json.loads(gzip.decompress((base/'personnel-access-proposal/EXACT_BLOCK_PROPOSAL.json.gz').read_bytes()))
    inherited={tuple(r['pos']):r for r in history}
    lifts=json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
    protected={tuple(d['pos']) for l in lifts['lifts'] for f in l['floors'] for kind in ('landing_doors','cabin_doors') for d in f[kind]}
    protected.update(tuple(c['position']) for l in lifts['lifts'] for f in l['floors'] for c in f['calls'])
    rows=[];checks=[]
    for y in (-1014,-987):
        for name,x0,x1,old_z,new_z,owner in (
            ('east',49,62,376,374,'r25-east-command-gallery/rear_hangar_lobby'),
            ('west',-46,-37,264,261,'s20-command-rear-x12-z253-v4/west_hangar_lobby')):
            lo=(x0,y-1,new_z);hi=(x1,y+3,old_z)
            cells=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi))
            wanted={};reason={}
            # Move the original complete end frame, including its existing
            # open doorway, to the end of the required three-deep apron.
            for x in range(x0,x1+1):
                for yy in range(y,y+4):
                    q=(x,yy,new_z);source=(x,yy,old_z)
                    wanted[q]=cells[source];reason[q]='shorten_existing_'+name+'_lobby_end_frame'
            for q,state in cells.items():
                if q[2]<=new_z:continue
                old=inherited.get(q)
                if old is None:continue
                assert old['owner'].startswith(owner),(q,old['owner'])
                assert old['before_nbt'] is None and old['after_nbt'] is None,q
                assert state==old['after'],('Lobby fabric changed since authored extension',q,state,old['after'])
                wanted[q]=old['before'];reason[q]='remove_owned_'+name+'_lobby_overrun'
            changed=[]
            for q,after in wanted.items():
                if cells[q]==after:continue
                assert q not in tags and q not in protected,('Keep door/control/device',q)
                rows.append(dict(pos=q,before=cells[q],after=after,before_nbt=None,after_nbt=None,reason=reason[q]))
                changed.append(q)
            # The corridor is already connected to the lift. An extra end cap
            # is not an endpoint to preserve; the native landing remains out
            # of this complete-width retirement footprint.
            checks.append(dict(lobby=name,feet_y=y,old_end_z=old_z,new_end_z=new_z,
                removed_depth=old_z-new_z,changed_cells=len(changed),full_width=[x0,x1],
                ownership=owner,native_doors_and_call_approaches_preserved=True))
    output.mkdir(parents=True,exist_ok=True)
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode(),mtime=0))
    report=dict(world=str(world),changed_cells=len(rows),lobbies=checks,
        reasons=dict(Counter(r['reason'] for r in rows)),installed=False,
        source='Exact R53 authored lobby footprints and current native landing manifest',
        pending=['native view','retired navigation-node removal and route-sign refresh'])
    (output/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True);p.add_argument('--base',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    if a.apply:apply(a.world,a.output)
    else:plan(a.world,a.base,a.output)
