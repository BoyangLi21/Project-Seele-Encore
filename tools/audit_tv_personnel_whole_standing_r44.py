"""Read-only full authored worker surface coverage, including neighbour shapes."""
from pathlib import Path
import argparse,hashlib,json,math
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from audit_facility_transit_r44 import Geometry
from audit_tv_cage_space_r44 import motion

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/hangar_machinery'

def intersects(boxes,body):
    return np.all((boxes[:,1]>body[0]+1e-6)&(boxes[:,0]<body[1]-1e-6),axis=1)

def uncovered(foot,boxes):
    """Exact rectangle union coverage, rather than accepting one thin rail."""
    low,high=np.asarray(foot[0]),np.asarray(foot[1])
    if not len(boxes):return float(np.prod(high-low))
    rect=boxes[:,[0,1]][:,:,[0,2]].copy();rect[:,0]=np.maximum(rect[:,0],low);rect[:,1]=np.minimum(rect[:,1],high)
    rect=rect[np.all(rect[:,1]>rect[:,0],axis=1)]
    xs=np.unique(np.r_[low[0],high[0],rect[:,:,0].ravel()]);zs=np.unique(np.r_[low[1],high[1],rect[:,:,1].ravel()])
    area=0.
    for a,b in zip(xs[:-1],xs[1:]):
        for c,d in zip(zs[:-1],zs[1:]):
            p=np.array([(a+b)/2,(c+d)/2])
            if not np.any(np.all((rect[:,0]<=p)&(rect[:,1]>=p),axis=1)):area+=(b-a)*(d-c)
    return float(area)

def grid(first,last,step=.10):
    return np.linspace(first,last,max(2,math.ceil((last-first)/step)+1))

def main(asset,layout,operations,out,actual_boundary_outline=False):
    asset,layout,operations,out=map(Path,(asset,layout,operations,out))
    if out.exists():raise ValueError('Fresh output required')
    cage=json.loads(asset.read_text('utf8'));plan=json.loads(layout.read_text('utf8'));ops=json.loads(operations.read_text('utf8'))
    changed={tuple(o['position']):o['after'].replace('open=false','open=true') for o in ops}
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((-36,-400,-274),(103,-383,-238));w.load();g=Geometry(w)
    for p in (BASE/'tv_personnel_deck_native_v1/native_union_readback/full_native_collision_shapes.json',BASE/'tv_personnel_guard_native_v1/native_union_readback/native64.json'):
        g.shapes.update(json.loads(p.read_text('utf8')))
    boxes=[];owners=[];world_states={}
    for x in range(-36,104):
        for y in range(-400,-382):
            for z in range(-274,-237):
                q=(x,y,z);s=changed.get(q,w.block(q))
                if s is None:raise ValueError(('Unknown section',q))
                if s.partition('[')[0] in AIR|{'minecraft:light','projectseele:lcl','minecraft:water'}:continue
                shapes=g.boxes(s)
                if shapes is None:raise ValueError(('Missing native shape',q,s))
                world_states[str(q)]=s
                for b in shapes:boxes.append(np.array(b).reshape(2,3)+q);owners.append({'position':q,'state':s})
    world=np.array(boxes);reports=[]
    for v in range(3):
        origin=np.array([-11.5+42*v,-442.96,-239.5])
        for side in (-1,1):
            special=v==2 and side==1;points={}
            floors=[c for c in plan['floor_cells'] if c['variant']==v and c['side']==side]
            footprint_tiles={(c['position'][0],c['position'][2]) for c in floors}
            for c in floors:
                x,y,z=c['position'];raw=g.boxes(c['after']);target=max(b[4] for b in raw)+y
                # Outer footprint limits include the exact inset55mm guard.
                x0=x+(.3 if (x-1,z) not in footprint_tiles else 0.);x1=x+1-(.3 if (x+1,z) not in footprint_tiles else 0.)
                if special and x==84 and -256<=z<=-247:x1-=.055
                z0=z+(.3 if (x,z-1) not in footprint_tiles else 0.);z1=z+1-(.3 if (x,z+1) not in footprint_tiles else 0.)
                for X in grid(x0,x1):
                    for Z in grid(z0,z1):points[round(X,7),round(Z,7)]=('native_lane',target)
            outer=10.5 if special else 13.95
            for X in grid(8.955+.348,outer-.348):
                for Z in grid(-16.5+.348,-7.5-.348):
                    points[round(origin[0]+side*X,7),round(origin[2]+Z,7)]=('green_inspection',origin[1]+48.96+(Z+20.5)*3.74/13.92)
            for opening in (0.,1.):
                ab=[];ao=[]
                for c in cage['components']:
                    if c.get('variant',v)!=v or c['part'].startswith('thin_side_rails'):continue
                    b=np.array(cage['collision_parts'][c['part']])+origin+motion(c,opening);ab.extend(b);ao.extend([c['part']]*len(b))
                ab=np.array(ab);allboxes=np.concatenate((world,ab));failure=[];stances=[];refinements=[]
                for (X,Z),(role,target) in points.items():
                    near=(allboxes[:,1,0]>X-.3)&(allboxes[:,0,0]<X+.3)&(allboxes[:,1,2]>Z-.3)&(allboxes[:,0,2]<Z+.3)
                    floor=allboxes[near&(allboxes[:,1,1]>=target-.65)&(allboxes[:,1,1]<=target+.30)]
                    if not len(floor):failure.append({'xz':[X,Z],'role':role,'reason':'NO_SUPPORT'});continue
                    feet=float(floor[:,1,1].max());body=np.array([[X-.3,feet,Z-.3],[X+.3,feet+1.8,Z+.3]])
                    foot=np.array([[X-.3,Z-.3],[X+.3,Z+.3]])
                    missing=uncovered(foot,floor[floor[:,1,1]>=feet-.60])
                    wi=np.flatnonzero(intersects(world,body));ai=np.flatnonzero(intersects(ab,body))
                    if actual_boundary_outline and len(wi) and not len(ai) and all('tv_personnel_guard_r44' in owners[int(i)]['state'] for i in wi):
                        # Replace an over-boundary sample by the nearest exact
                        # Minkowski guard face. No floor, guard or main lane
                        # width is altered. Preserve every raw negative.
                        candidates=sorted({float(world[i,0,0]-.3) for i in wi}|{float(world[i,1,0]+.3) for i in wi},key=lambda x:abs(x-X))
                        for adjusted in candidates:
                            if abs(adjusted-X)>.35:continue
                            n=(allboxes[:,1,0]>adjusted-.3)&(allboxes[:,0,0]<adjusted+.3)&(allboxes[:,1,2]>Z-.3)&(allboxes[:,0,2]<Z+.3)
                            fb=allboxes[n&(allboxes[:,1,1]>=target-.65)&(allboxes[:,1,1]<=target+.30)]
                            if not len(fb):continue
                            newfeet=float(fb[:,1,1].max());newbody=np.array([[adjusted-.3,newfeet,Z-.3],[adjusted+.3,newfeet+1.8,Z+.3]])
                            newwi=np.flatnonzero(intersects(world,newbody));newai=np.flatnonzero(intersects(ab,newbody))
                            newmissing=uncovered(np.array([[adjusted-.3,Z-.3],[adjusted+.3,Z+.3]]),fb[fb[:,1,1]>=newfeet-.60])
                            if len(newwi) or len(newai) or newmissing>=.36-1e-7:continue
                            refinements.append({'raw_position':[X,feet,Z],'actual_boundary_position':[adjusted,newfeet,Z],'guard_owners':[owners[int(i)] for i in wi],
                                                'coordinate_shift_m':adjusted-X,'world_geometry_changed':False})
                            X,feet,body,wi,ai,missing=adjusted,newfeet,newbody,newwi,newai,newmissing
                            break
                    stances.append({'role':role,'position':[X,feet,Z],'full_footprint_support_missing_m2':missing})
                    # An open grating is supported by its actual bearing bars.
                    # Keep its true open area; only a wholly unsupported body
                    # footprint is a support failure. Hole-size evidence and
                    # actual native landing/standing remain separate gates.
                    if missing>=.36-1e-7 or len(wi) or len(ai):failure.append({'position':[X,feet,Z],'role':role,'support_missing_m2':missing,'world_hits':[owners[int(i)] for i in wi[:5]],'asset_hits':sorted(set(ao[int(i)] for i in ai))})
                reports.append({'variant':v,'side':side,'opening':opening,'stances':stances,'failures':failure,'actual_boundary_refinements':refinements})
    out.mkdir(parents=True)
    report={'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (asset,layout,operations)},'native_collision_cache_sha256':hashlib.sha256((w.world/'native_collision_shapes.json').read_bytes()).hexdigest(),
            'composed_nonempty_world_sha256':hashlib.sha256(json.dumps(world_states,sort_keys=True).encode()).hexdigest(),'surfaces':reports,'grid_step_max_m':.10,
            'support_proof':'Every0.6m footprint rectangle is partitioned at every intersecting support rectangle boundary. True grating open area remains measured, not filled by invisible collision. A wholly unsupported0.36m2 footprint fails. Support union at most0.60m below actual collision standing height includes extended native neighbouring owners. Maximum hole-width and native landing tests are separate required gates.',
            'scope':'All declared native lane cells and green working-face interiors, exact width extremes and terminal centres, both stable endpoints. Optional actual-boundary mode replaces only native-guard over-boundary samples by the nearest exact0.3m expanded guard face and retains all raw negatives/refinement records. Finite grid is not a proof between all sample centres or a native movement receipt.',
            'world_write':False,'native_passed':False,'art_passed':False,'preapply_ready':False}
    (out/'contract.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({'stances':sum(len(r['stances']) for r in reports),'failures':sum(len(r['failures']) for r in reports),'first':[r['failures'][:1] for r in reports]}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('asset','layout','operations','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--actual-boundary-outline',action='store_true')
    a=p.parse_args();main(a.asset,a.layout,a.operations,a.out,a.actual_boundary_outline)
