"""Small immutable triangle-distance field for offline contact fitting.

Parity uses three non-axis-aligned rays. Ambiguous open-mesh samples are
reported; exact final triangle-crossing and visual audits remain required.
"""
import numpy as np

class TriangleField:
    def __init__(self, triangles):
        self.t=np.asarray(triangles,dtype=float)
        a=self.t[:,0];self.e1=self.t[:,1]-a;self.e2=self.t[:,2]-a
        self.normal=np.cross(self.e1,self.e2)
        self.n2=np.einsum('ij,ij->i',self.normal,self.normal)
        self.valid=self.n2>1e-16
        self.t=self.t[self.valid];self.e1=self.e1[self.valid];self.e2=self.e2[self.valid]
        self.normal=self.normal[self.valid];self.n2=self.n2[self.valid]
        self.d00=np.einsum('ij,ij->i',self.e1,self.e1)
        self.d01=np.einsum('ij,ij->i',self.e1,self.e2)
        self.d11=np.einsum('ij,ij->i',self.e2,self.e2)
        self.denom=self.d00*self.d11-self.d01*self.d01
        self.rays=[]
        for ray in [[1,.371,.157],[-.229,1,.419],[.313,-.191,1]]:
            ray=np.asarray(ray,dtype=float);ray/=np.linalg.norm(ray)
            h=np.cross(ray,self.e2);det=np.einsum('ij,ij->i',self.e1,h)
            valid=np.abs(det)>1e-12;inv=np.zeros_like(det);inv[valid]=1/det[valid]
            self.rays.append((ray,h*inv[:,None],inv,valid))

    def query(self, points):
        points=np.asarray(points,dtype=float);out=[];uncertain=[]
        for start in range(0,len(points),384):
            p=points[start:start+384];s=p[:,None,:]-self.t[None,:,0,:]
            d20=np.einsum('nmi,mi->nm',s,self.e1)
            d21=np.einsum('nmi,mi->nm',s,self.e2)
            u=(self.d11*d20-self.d01*d21)/self.denom
            v=(self.d00*d21-self.d01*d20)/self.denom
            plane=np.einsum('nmi,mi->nm',s,self.normal)**2/self.n2
            distance=np.where((u>=0)&(v>=0)&(u+v<=1),plane,np.inf)
            for i,j in [(0,1),(1,2),(2,0)]:
                edge=self.t[:,j]-self.t[:,i];edge2=np.einsum('mi,mi->m',edge,edge)
                rel=p[:,None,:]-self.t[None,:,i,:]
                amount=np.clip(np.einsum('nmi,mi->nm',rel,edge)/edge2,0,1)
                delta=rel-amount[:,:,None]*edge[None,:,:]
                distance=np.minimum(distance,np.einsum('nmi,nmi->nm',delta,delta))
            nearest=np.sqrt(distance.min(1));votes=[]
            q=np.cross(s,self.e1[None,:,:])
            t=np.einsum('nmi,mi->nm',q,self.e2)
            for ray,h,inv,valid in self.rays:
                ru=np.einsum('nmi,mi->nm',s,h)
                rv=np.einsum('nmi,i->nm',q,ray)*inv
                rt=t*inv
                hits=valid&(ru>=-1e-10)&(rv>=-1e-10)&(ru+rv<=1+1e-10)&(rt>1e-8)
                # Shared edges can be hit twice. The oblique rays avoid the
                # ordinary grid degeneracy; inconsistent votes stay visible.
                votes.append((hits.sum(1)%2)==1)
            count=np.sum(votes,axis=0);out.append(nearest*np.where(count>=2,-1,1))
            uncertain.append((count!=0)&(count!=3))
        return np.concatenate(out),np.concatenate(uncertain)

if __name__=='__main__':
    # An independent closed cube has known inside/outside distances.
    v=np.array([[x,y,z]for x in [-.5,.5]for y in [-.5,.5]for z in [-.5,.5]])
    from scipy.spatial import ConvexHull
    f=TriangleField(v[ConvexHull(v).simplices])
    distances,ambiguous=f.query([[0,0,0],[1,0,0],[.6,.6,.5],[-.25,.1,.2]])
    assert np.allclose(distances,[-.5,.5,np.sqrt(.02),-.25],atol=1e-8),distances
    assert not ambiguous.any(),ambiguous
    print('Closed-cube distance and parity checks passed')
