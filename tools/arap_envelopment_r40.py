"""Private offline surface deformation using libigl's established ARAP solver.

Core library: libigl 2.6.3 (MPL-2.0); no library or private geometry is added to
Minecraft. See https://libigl.github.io/tutorial/#as-rigid-as-possible.
"""
from pathlib import Path
import sys,json
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from scipy.sparse.csgraph import connected_components

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.Codex/geometry-runtime'))
import igl


def fit(a,b):
    ca=a.mean(0);cb=b.mean(0);u,_,vt=np.linalg.svd((a-ca).T@(b-cb));q=vt.T@u.T
    if np.linalg.det(q)<0:vt[-1]*=-1;q=vt.T@u.T
    return ca,cb,R.from_matrix(q)


def sequence(source,target,faces,rig,steps):
    faces=np.asarray(faces,np.int64).reshape(-1,3)
    cross=np.cross(source[faces[:,1]]-source[faces[:,0]],source[faces[:,2]]-source[faces[:,0]])
    faces=faces[np.linalg.norm(cross,axis=1)>1e-9]
    count,component=connected_components(igl.adjacency_matrix(faces),directed=False)
    main=int(np.argmax(np.bincount(component)));active=component==main;ids_main=np.flatnonzero(active)
    remap=np.full(len(source),-1,np.int64);remap[ids_main]=np.arange(len(ids_main))
    solve_faces=remap[faces[np.all(active[faces],axis=1)]]
    labels=np.argmax(np.stack([np.where(rig.ids==i,rig.weights,0).sum(1) for i in range(len(rig.names))],axis=1),axis=1)
    picked=set();groups=[]
    core=np.linalg.norm((rig.vertices-rig.core)*[1,1,.8],axis=1)<10
    for name in ['head','core']+rig.names:
        if name=='root':continue
        ids=np.flatnonzero(core) if name=='core' else np.flatnonzero(labels==rig.names.index(name))
        ids=np.array([i for i in ids if active[i] and i not in picked],int)
        if not len(ids):continue
        if name not in ['head','core']:
            # Small surface rings guide the limb; free intervening vertices
            # retain local edge lengths instead of following per-vertex arcs.
            rank=np.argsort(np.linalg.norm(rig.vertices[ids]-rig.P[name],axis=1));ids=ids[rank[:min(6,len(ids))]]
        picked.update(ids);groups.append((name,ids,*fit(source[ids],target[ids])))
    attachments=[];hand_frames={}
    for c in range(count):
        if c==main:continue
        ids=np.flatnonzero(component==c)
        dominant=int(np.argmax(np.bincount(labels[ids],minlength=len(rig.names))))
        name=rig.names[dominant];pool=np.flatnonzero(active&(labels==dominant))
        if len(pool)<12 and name.startswith('hand_'):
            pool=np.flatnonzero(active&(labels==rig.names.index('forearm_'+name[-1])))
        if len(pool)<12:pool=ids_main
        centre=rig.P[name] if name.startswith('hand_') else rig.vertices[ids].mean(0)
        distance=np.linalg.norm(rig.vertices[pool]-centre,axis=1)
        neighbours=pool[np.argsort(distance)[:min(32,len(pool))]]
        if name.startswith('hand_'):
            # All phalanges in a hand belong to one rigid palm frame. Choosing
            # a separate nearest patch for each tip makes the fingers detach.
            neighbours=hand_frames.setdefault(name,neighbours)
        attachments.append((ids,neighbours))
    pins=np.array(sorted(picked),np.int32);where={int(v):i for i,v in enumerate(pins)}
    data=igl.ARAPData();data.energy=igl.ARAP_ENERGY_TYPE_SPOKES_AND_RIMS;data.max_iter=30
    igl.arap_precomputation(np.asarray(source[ids_main],np.float64),solve_faces,3,np.asarray(remap[pins],np.int32),data)
    previous=np.array(source[ids_main],dtype=np.float64,order='C');frames=[]
    for frame in range(steps):
        t=frame/(steps-1);u=t*t*t*(10+t*(-15+6*t));bc=np.zeros((len(pins),3))
        arc=np.array([0,5,6])*np.sin(np.pi*u)
        for name,ids,a,b,q in groups:
            rotation=Slerp([0,1],R.concatenate([R.identity(),q]))([u])[0]
            route=arc.copy()
            if name.startswith(('leg_','shin_','foot_')):
                route[0]=(-1 if name.endswith('_l') else 1)*7*np.sin(np.pi*u)
            point=rotation.apply(source[ids]-a)+a*(1-u)+b*u+route
            for i,value in zip(ids,point):bc[where[int(i)]]=value
        previous=igl.arap_solve(bc,data,previous)
        if not np.isfinite(previous).all():raise RuntimeError(('Non-finite ARAP frame',frame))
        full=np.empty_like(source);full[ids_main]=previous
        # Mask plates, core pieces, elbow lances and fingers are disconnected
        # solids in this mesh. Their rotations follow nearby tissue frames;
        # an underconstrained independent ARAP solve would let them twist free.
        for ids,neighbours in attachments:
            a,b,q=fit(source[neighbours],full[neighbours]);full[ids]=q.apply(source[ids]-a)+b
        if frame==0:full=source.copy()
        frames.append(full)
    result=np.asarray(frames)
    print(json.dumps(dict(method='libigl ARAP tissue with rigid anatomical attachments',frames=steps,vertices=len(source),soft_vertices=len(ids_main),constraints=len(pins),rigid_components=len(attachments))),flush=True)
    return result,attachments


def contact_corrective(points,faces,obstacle_vertices,obstacle_faces,attachments):
    """Local tissue response to the actual rendered armour, not one convex blob."""
    faces=np.asarray(faces,np.int64).reshape(-1,3);graph=igl.adjacency_matrix(faces)
    _,component=connected_components(graph,directed=False);main=int(np.argmax(np.bincount(component)))
    ids=np.flatnonzero(component==main);remap=np.full(len(points),-1,np.int64);remap[ids]=np.arange(len(ids))
    local_faces=remap[faces[np.all(component[faces]==main,axis=1)]]
    local_graph=igl.adjacency_matrix(local_faces);result=points.copy();corrected=set();contact_targets={}
    for iteration in range(10):
        soft=result[ids];w=igl.fast_winding_number(obstacle_vertices,obstacle_faces,soft)
        distance,_,nearest=igl.point_mesh_squared_distance(soft,obstacle_vertices,obstacle_faces)
        inside=(np.abs(w)>.5)&(distance>.02**2)
        hits=np.flatnonzero(inside)
        if not len(hits):break
        corrected.update(map(int,ids[hits]))
        directions=nearest[hits]-soft[hits];directions/=np.maximum(np.linalg.norm(directions,axis=1,keepdims=True),1e-9)
        projected=nearest[hits]+directions*.16
        # Intersecting armour pieces form a union. The closest triangle may be
        # an internal face, so its immediate outside is not necessarily free.
        for margin in [.32,.64,1.28,2.56,3.2]:
            blocked=np.abs(igl.fast_winding_number(obstacle_vertices,obstacle_faces,projected))>.5
            if not blocked.any():break
            projected[blocked]=nearest[hits[blocked]]+directions[blocked]*margin
        for at,value in zip(hits,projected):contact_targets[int(at)]=value
        active=np.array(sorted(contact_targets),np.int32);free=np.zeros(len(soft),bool);free[active]=True
        for _ in range(3):free|=np.asarray(local_graph@free.astype(np.int32)).ravel()>0
        pinned=~free;pinned[active]=True;fixed=np.flatnonzero(pinned).astype(np.int32);targets=soft[fixed].copy();lookup={int(v):i for i,v in enumerate(fixed)}
        for at,target in contact_targets.items():targets[lookup[at]]=target
        data=igl.ARAPData();data.energy=igl.ARAP_ENERGY_TYPE_SPOKES_AND_RIMS;data.max_iter=12
        area=np.linalg.norm(np.cross(soft[local_faces[:,1]]-soft[local_faces[:,0]],soft[local_faces[:,2]]-soft[local_faces[:,0]]),axis=1)
        igl.arap_precomputation(soft,local_faces[area>1e-9],3,fixed,data)
        result[ids]=igl.arap_solve(targets,data,soft)
    if corrected:
        for piece,neighbours in attachments:
            a,b,q=fit(points[neighbours],result[neighbours]);result[piece]=q.apply(points[piece]-a)+b
    return result,len(corrected)
