"""Exact triangle proximity plus explicit three-ray parity using spatial indexes.

Authoring dependency only: trimesh5.1.1/rtree1.4.1 in .tools/geometry_python.
The weapon is neither remeshed nor reduced. Open-mesh ambiguity remains
visible, and strict final triangle-crossing tests remain a separate check.
"""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.tools/geometry_python'))
import trimesh
from trimesh.ray.ray_triangle import RayMeshIntersector

class AcceleratedTriangleField:
    def __init__(self,triangles):
        t=np.asarray(triangles,float)
        n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);t=t[np.einsum('ij,ij->i',n,n)>1e-16]
        self.mesh=trimesh.Trimesh(vertices=t.reshape(-1,3),faces=np.arange(len(t)*3).reshape(-1,3),process=False)
        self.ray=RayMeshIntersector(self.mesh)
        self.directions=np.asarray([[1,.371,.157],[-.229,1,.419],[.313,-.191,1]],float)
        self.directions/=np.linalg.norm(self.directions,axis=1,keepdims=True)

    def query(self,points):
        points=np.asarray(points,float);distances=[];ambiguous=[]
        for start in range(0,len(points),384):
            batch=points[start:start+384]
            _,distance,_=trimesh.proximity.closest_point(self.mesh,batch)
            votes=[]
            for direction in self.directions:
                locations,rays,_=self.ray.intersects_location(batch,np.broadcast_to(direction,batch.shape),multiple_hits=True)
                if len(rays):
                    forward=(locations-batch[rays])@direction>1e-8
                    counts=np.bincount(rays[forward],minlength=len(batch))
                else:counts=np.zeros(len(batch),int)
                votes.append(counts%2==1)
            total=np.sum(votes,axis=0)
            distances.append(distance*np.where(total>=2,-1,1));ambiguous.append((total!=0)&(total!=3))
        return np.concatenate(distances),np.concatenate(ambiguous)
