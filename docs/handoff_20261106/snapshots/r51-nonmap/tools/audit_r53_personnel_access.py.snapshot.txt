"""Independent bounded readback of the uninstalled R53 lift access proposal.

Uses saved native collision shapes, measured motion cores and current native
actors. This is an offline gate, not a substitute for running the native lifts.
"""
from pathlib import Path
import argparse
import gzip
import json
import math
import numpy as np
from query_blocks import read_box,AIR
from verify_main_r20 import entities


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True)
    args=ap.parse_args();b=args.base;world=b/'CANDIDATE';out=b/'personnel-access-proposal'
    delta=json.loads(gzip.decompress((out/'EXACT_BLOCK_PROPOSAL.json.gz').read_bytes()))
    changes={tuple(r['pos']):r for r in delta};after={p:r['after'] for p,r in changes.items()}
    manifest=json.loads((out/'personnel_lifts_PROPOSAL.json').read_text('utf8'))
    review=json.loads((out/'REVIEW.json').read_text('utf8'))
    shapes=json.loads((world/'native_collision_shapes.json').read_text('utf8'));unknown=set()
    # FacilityStripLightR47 extends Block and overrides only state definition;
    # its source-verified native collision is the default full cube.
    shapes.setdefault('projectseele:nerv_strip_light[lit=true]',[[0,0,0,1,1,1]])
    def shape(s):
        if s in AIR:return []
        if s not in shapes:unknown.add(s);return [[0,0,0,1,1,1]]
        return shapes[s]
    opened={tuple(d['pos']) for l in manifest['lifts'] for f in l['floors'] for k in ('landing_doors','cabin_doors') for d in f[k]}
    walks=[];cache={};failures=[]
    def final(p):return after.get(p,cache.get(p,'__UNREAD__'))
    def stand(p):
        x,y,z=p;by=math.floor(y);support=False
        for fy in (by-1,by):
            support |= any(v[0]<=.2 and v[3]>=.8 and v[2]<=.2 and v[5]>=.8 and abs(fy+v[4]-y)<.001 for v in shape(final((x,fy,z))))
        for yy in range(by,math.ceil(y+1.8)):
            q=x,yy,z
            if q in opened:continue
            if any(v[0]<.8 and v[3]>.2 and v[2]<.8 and v[5]>.2 and yy+v[1]<y+1.8-.001 and yy+v[4]>y+.001 for v in shape(final(q))):return False
        return support
    for index,path in enumerate(review['lobby_paths']):
        pts=path['ends'];width=path['width'];feet=set()
        if path['owner']=='s20-command-rear-x12-z253-v4' and path['y']==-502:
            pts=[[-42,-502,259],[-1,-502,259],[-1,-502,252],[11,-502,252],[11,-502,259],[12,-502,260]]
        for start,end in zip(pts,pts[1:]):
            assert start[1]==end[1]
            x0,y,z0=start;x1,_,z1=end
            if x0!=x1 and z0!=z1:
                # The last measured original handoff has a short corner.
                steps=[(x0,z0),(x1,z0),(x1,z1)]
            else:steps=[(x0,z0),(x1,z1)]
            for (ax,az),(bx,bz) in zip(steps,steps[1:]):
                if ax==bx:
                    for z in range(min(az,bz),max(az,bz)+1):
                        for x in range(ax-(width-1)//2,ax+width//2+1):feet.add((x,y,z))
                else:
                    for x in range(min(ax,bx),max(ax,bx)+1):
                        for z in range(az-(width-1)//2,az+width//2+1):feet.add((x,y,z))
        if path.get('bands'):
            feet={(x,path['y'],z) for x0,x1,z0,z1 in path['bands'] for x in range(x0,x1+1) for z in range(z0,z1+1)}
        if path.get('endpoint_step'):
            feet={(x,y+path['endpoint_step'] if z==pts[-1][2] else y,z) for x,y,z in feet}
        lo=tuple(math.floor(min(p[k] for p in feet))-(1 if k==1 else 0) for k in range(3))
        hi=tuple(math.ceil(max(p[k] for p in feet))+(2 if k==1 else 0) for k in range(3));cache.update(read_box(world,'projectseele:geofront',lo,hi))
        bad=[p for p in sorted(feet) if not stand(p)]
        walks.append(dict(index=index,owner=path['owner'],y=path['y'],checked=len(feet),failed=len(bad)))
        failures += [dict(kind='full_width_walk',path=index,pos=p,states=[final((p[0],yy,p[2])) for yy in (p[1]-1,p[1],p[1]+1)]) for p in bad]
    # Every authored hall floor and port, including intersections and edges,
    # is checked in addition to the routes into retained original circulation.
    hall_cells=[tuple(p) for p in review['whole_hall_walk_cells']]
    for y in sorted({p[1] for p in hall_cells}):
        feet=[p for p in hall_cells if p[1]==y]
        lo=(min(p[0] for p in feet),y-1,min(p[2] for p in feet));hi=(max(p[0] for p in feet),y+2,max(p[2] for p in feet))
        cache.update(read_box(world,'projectseele:geofront',lo,hi))
    hall_failures=[p for p in hall_cells if not stand(p)]
    # Envelope evidence is exact for the low bank sections; all reworked
    # branch curves start more than 80 blocks above these new launch floors.
    solid={p for p,s in after.items() if shape(s) and p[1]<=-960}
    overlaps=set();source_base=b.parent/'map_complete_20261013'
    for relative in ('phased_routes/final68_measurement/combined/MEASURED_SOURCE.npz',
                     'phased_routes/reverse_head_edges_measurement/MEASURED_SOURCE.npz'):
        with np.load(source_base/relative) as data:
            keys={tuple(map(int,k)):i for i,k in enumerate(data['section_keys'])};core=data['core']
            for x,y,z in solid:
                i=keys.get((x//16,z//16,y//16))
                if i is not None and core[i,((y&15)*16+(z&15))*16+(x&15)]:overlaps.add((x,y,z))
    # Current actor positions are checked against newly occupied cells. Their
    # identities, positions and progress are not rewritten by this proposal.
    actors=[]
    for tag in entities(world).values():
        p=tuple(map(float,tag['Pos']));q=tuple(math.floor(n) for n in p)
        if q in after and shape(after[q]):actors.append(dict(type=str(tag['id']),pos=p,new_state=after[q]))
    report=dict(world_written=False,walks=walks,walk_failures=failures,whole_hall_checked=len(hall_cells),whole_hall_failures=hall_failures,
        low_motion_core_new_solid_overlaps=[dict(pos=p,state=after[p],owner=changes[p]['owner']) for p in sorted(overlaps)],
        actors_in_new_solid=actors,unknown_shapes=sorted(unknown),
        native_lift_movement_and_complete_live_geometry_still_required=True)
    (out/'OFFLINE_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(walk_cells=sum(r['checked'] for r in walks),walk_failures=len(failures),
        whole_hall_checked=len(hall_cells),whole_hall_failures=len(hall_failures),low_motion_core_new_solid_overlaps=len(overlaps),actors_in_new_solid=len(actors),unknown_shapes=sorted(unknown)),ensure_ascii=False))
    print('First walk failures:',failures[:8])
    print('First mechanical overlaps:',report['low_motion_core_new_solid_overlaps'][:5])


if __name__=='__main__':main()
