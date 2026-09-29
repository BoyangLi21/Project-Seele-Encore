"""Every owned building flight: all lanes, headroom and both floor interfaces.

Irregular/decorative groups remain classified separately, never silent passes.
Historical floor heights identify candidate use; actual voxel shapes are read
again from the frozen world. No geometry is inferred as permission to build.
"""
from pathlib import Path
from collections import Counter
import json,gzip,time
from measure_world_r40 import MeasuredWorld,properties
from regional_voxels import canonical_state
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';WORLD=ART/'source_world_backup';OUT=ART/'building_stairs'
DIR={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}

def main():
    OUT.mkdir(exist_ok=True);owners=json.loads((ART/'facility_catalogue/authored_ownership.json').read_text('utf8'))['buildings']
    components={c['id']:c for c in json.loads(gzip.open(ART/'facility_catalogue/physical_components.json.gz','rt',encoding='utf8').read())}
    shapes={canonical_state(s):v for s,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()};missing=set();results=[];cases=[];seen=set();clock=time.monotonic()
    def boxes(state):
        if state is None:return None
        if state.partition('[')[0] in AIR|{'minecraft:light'}:return []
        if state not in shapes:missing.add(state);return None
        return shapes[state]
    for index,building in enumerate(owners):
        stairs=[components[c['id']] for c in building['physical_components'] if c['kind']=='stairs' and c['id'] not in seen]
        if not stairs:continue
        w=MeasuredWorld(WORLD)
        for c in stairs:
            a,b=c['bounds'];w.box((a[0]-2,a[1]-2,a[2]-2),(b[0]+2,b[1]+4,b[2]+2))
        w.load()
        def body(q):
            x,y,z=q;obstructions=[];unknown=[]
            import math
            for xx in range(math.floor(x-.3),math.floor(x+.3)+1):
                for zz in range(math.floor(z-.3),math.floor(z+.3)+1):
                    for yy in range(math.floor(y+.001),math.floor(y+1.799)+1):
                        s=w.get(xx,yy,zz);bs=boxes(s)
                        if bs is None:unknown.append([xx,yy,zz,s]);continue
                        if any(xx+b[0]<x+.3 and xx+b[3]>x-.3 and zz+b[2]<z+.3 and zz+b[5]>z-.3 and yy+b[1]<y+1.799 and yy+b[4]>y+.001 for b in bs):obstructions.append([xx,yy,zz,s])
            floor=w.get(int(x//1),int((y-.001)//1),int(z//1));bs=boxes(floor)
            supported=bs is not None and any(b[0]<=.5<=b[3] and b[2]<=.5<=b[5] and abs(int((y-.001)//1)+b[4]-y)<.01 for b in bs)
            return dict(pos=q,obstructions=obstructions,unknown=unknown,supported=supported,floor=floor)
        for c in stairs:
            seen.add(c['id']);points=c['raw_cells'];meta=dict(id=c['id'],building=building['id'],bounds=c['bounds'],issues=[],status='UNCLASSIFIED')
            stateprops=[properties(r[3]) for r in points];faces={p.get('facing') for p in stateprops};height=c['bounds'][1][1]-c['bounds'][0][1]
            if height==0:meta['classification']='LEVEL_OR_DECORATIVE_STAIR_COMPONENT';results.append(meta);continue
            if len(faces)!=1 or any(p.get('half')!='bottom' or p.get('shape')!='straight' for p in stateprops):meta['classification']='TURNING_OR_MIXED_FLIGHT_REQUIRES_GRAPH_REVIEW';results.append(meta);continue
            base=c['bounds'][0][1]
            if base not in building['planned_floor_feet'] or height!=4:meta['classification']='NONSTANDARD_HEIGHT_REQUIRES_USE_REVIEW';results.append(meta);continue
            dx,dz=DIR[next(iter(faces))];lanes={}
            for r in points:lanes.setdefault(r[0] if dz else r[2],[]).append(r)
            rows=[]
            for lane,points in sorted(lanes.items()):
                points=sorted(points,key=lambda p:p[1]);sequence=len(points)==5 and all(points[i][1]==base+i and (points[i][0]-points[0][0],points[i][2]-points[0][2])==(dx*i,dz*i) for i in range(5))
                if not sequence:meta['issues'].append(dict(kind='incomplete_lane',lane=lane,points=points));continue
                first,last=points[0],points[-1];entry=[first[0]-dx+.5,base,first[2]-dz+.5];exit=[last[0]+dx+.5,base+5,last[2]+dz+.5]
                samples=[body(entry)]+[body([p[0]+.5,p[1]+1,p[2]+.5]) for p in points]+[body(exit)]
                problems=[q for q in samples if q['obstructions'] or q['unknown'] or not q['supported']]
                if problems:meta['issues'].append(dict(kind='lane_clearance_or_bearing',lane=lane,samples=problems))
                rows.append(dict(lane=lane,entry=entry,exit=exit,samples=samples))
                path=[entry]+[[p[0]+.5,p[1]+1,p[2]+.5] for p in points]+[exit]
                cases.extend([dict(id='r43/building_stair/'+c['id']+'/'+str(lane),path=path),dict(id='r43/building_stair/'+c['id']+'/'+str(lane)+'/return',path=path[::-1])])
            meta.update(classification='AUTHORED_FLOOR_CONNECTING_STRAIGHT_FLIGHT',lanes=rows,status='STATIC_FAILURE' if meta['issues'] else 'STATIC_CLEAR_NATIVE_TRAVERSAL_PENDING');results.append(meta)
        if index%20==0:print('Building',index+1,'of',len(owners),'components',len(results),flush=True)
    report=dict(world=str(WORLD),components=results,counts=dict(Counter(r['status'] for r in results)),classifications=dict(Counter(r['classification'] for r in results)),unknown_shapes=sorted(missing),seconds=time.monotonic()-clock,
        scope='All physical stair components linked to193 authored buildings; every lane checked for classified straight five-riser flights. Roof/furniture/turning/nonstandard components remain explicit, not passes. Native traversal and full-floor reachability still required.')
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');(OUT/'cases.json').write_text(json.dumps(cases,ensure_ascii=False),'utf8');print(report['counts'],report['classifications'],'native lane paths',len(cases),flush=True)

if __name__=='__main__':main()
