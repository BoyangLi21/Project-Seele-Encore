"""Conservative car envelopes over captured native MTR curves, offline only."""
from itertools import product
import numpy as np


def car_poses(points, bounds, bogies=(-2.5, 2.5), native_distances=None):
    p=np.asarray(points,float)
    segment=np.linalg.norm(np.diff(p,axis=0),axis=1)
    if not len(segment) or segment.max()>.65:raise ValueError('Native curve samples too sparse')
    along=np.r_[0,np.cumsum(segment)] if native_distances is None else np.asarray(native_distances,float)
    if len(along)!=len(p) or np.any(np.diff(along)<=0):raise ValueError('Invalid native distances')
    local=np.asarray(list(product(*zip(*bounds))),float)
    poses=[]
    for s in along:
        if s+min(bogies)<0 or s+max(bogies)>along[-1]:continue
        q=np.array([[np.interp(s+b,along,p[:,i])for i in range(3)]for b in bogies])
        centre=q.mean(0);forward=q[1]-q[0];forward/=np.linalg.norm(forward)
        right=np.cross([0.,1.,0.],forward);right/=np.linalg.norm(right)
        up=np.cross(forward,right)
        poses.append(centre+local[:,0,None]*right+local[:,1,None]*up+local[:,2,None]*forward)
    return poses


def car_sweep(points, bounds, bogies=(-2.5, 2.5), padding=.35, native_distances=None):
    """Union successive eight-corner boxes, including the interval between poses.

    Input points must come from the native RailMath consumer, at <= .5 blocks.
    The padding covers interpolation/rotation between adjacent native samples.
    Endpoints use a larger orientation-independent cap because the adjacent
    segment is not part of this input. This cannot certify a tight station end.
    """
    p=np.asarray(points,float)
    local=np.asarray(list(product(*zip(*bounds))),float)
    poses=car_poses(points,bounds,bogies,native_distances);rows=[]
    for a,b in zip(poses,poses[1:]):
        q=np.vstack((a,b));rows.append(np.r_[q.min(0)-padding,q.max(0)+padding])
    radius=float(np.linalg.norm(local,axis=1).max())+max(abs(b)for b in bogies)+padding
    for q in (p[0],p[-1]):rows.append(np.r_[q-radius,q+radius])
    return np.asarray(rows)


def swept_voxels(poses, crop, padding=.35):
    """Conservative convex interval hulls, avoiding the empty AABB corners.

    A voxel is discarded only when a supporting plane separates it from the
    inflated interval hull. The result may retain marginal contacts; it never
    authorizes removing a rail or device solely because its cell is returned.
    """
    from scipy.spatial import ConvexHull
    result=set();crop=np.asarray(crop).reshape(2,3)
    for a,b in zip(poses,poses[1:]):
        q=np.vstack((a,b));lo=np.maximum(np.floor(q.min(0)-padding).astype(int),crop[0])
        hi=np.minimum(np.ceil(q.max(0)+padding).astype(int),crop[1]+1)
        if np.any(lo>=hi):continue
        v=np.stack(np.meshgrid(*[np.arange(l,h)for l,h in zip(lo,hi)],indexing='ij'),axis=-1).reshape(-1,3)
        planes=ConvexHull(q).equations;n=planes[:,:3];offset=planes[:,3]
        separated=(v+.5)@n.T+offset > np.abs(n).sum(1)*.5+padding
        result.update(map(tuple,v[~separated.any(1)]))
    return result


def intersects(boxes, x, y, z):
    """Voxel occupied volume versus closed envelope, excluding face-only touch."""
    q=np.asarray([x,y,z],float)
    return bool(np.any(np.all(boxes[:,:3]<q+1-1e-8,axis=1)&np.all(boxes[:,3:]>q+1e-8,axis=1)))
