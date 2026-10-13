"""Fit two smooth target corrections against every exact body3 skin hull."""
from pathlib import Path
import argparse, copy, hashlib, json
import numpy as np
from scipy.optimize import minimize


def quintic(x):
    x = np.clip(x, 0, 1)
    return x*x*x*(10+x*(-15+6*x))


parser = argparse.ArgumentParser(description=__doc__)
for name in ('clip', 'hull-cache', 'out'):
    parser.add_argument('--'+name, type=Path, required=True)
args = parser.parse_args()
raw = args.clip.read_bytes(); clip = json.loads(raw)
cache = np.load(args.hull_cache)
assert str(cache['source_sha256']) == hashlib.sha256(raw).hexdigest()
points = [cache['vertices'][a:b] for a,b in zip(cache['offsets'][:-1], cache['offsets'][1:])]
frames = np.arange(len(points)); times = frames/clip['fps']
basis = np.array([quintic((times-a)/(b-a))*(1-quintic((times-c)/(d-c)))
                 for a,b,c,d in [(13.9,14.25,15.25,15.7), (15.6,16,16.9,17.3)]]).T
active = np.where(basis.max(1)>0)[0]
eye = np.array(clip['camera']['position'])[active]
target = np.array(clip['camera']['target'])[active]
distance = np.linalg.norm(target-eye,axis=1)
forward = (target-eye)/distance[:,None]
right = np.cross(forward,[0,1,0]); right /= np.linalg.norm(right,axis=1)[:,None]
up = np.cross(right,forward)
weights = basis[active]
lengths = np.array([len(points[i]) for i in active])
owners = np.repeat(np.arange(len(active)), lengths)
vertices = np.concatenate([points[i] for i in active])
tangent = np.tan(np.radians(np.array(clip['camera']['fov'])[active])/2)


def evaluate(values):
    shifts = weights @ values.reshape(2,2)
    direction = forward + right*shifts[:,0,None] + up*shifts[:,1,None]
    direction /= np.linalg.norm(direction,axis=1)[:,None]
    rr = np.cross(direction,[0,1,0]); rr /= np.linalg.norm(rr,axis=1)[:,None]
    uu = np.cross(rr,direction)
    rel = vertices-eye[owners]
    z = np.einsum('ij,ij->i',rel,direction[owners])
    h = np.abs(np.einsum('ij,ij->i',rel,rr[owners])/z/tangent[owners]/(16/9))
    v = np.abs(np.einsum('ij,ij->i',rel,uu[owners])/z/tangent[owners])
    hh = np.maximum.reduceat(h,np.r_[0,np.cumsum(lengths)[:-1]])
    vv = np.maximum.reduceat(v,np.r_[0,np.cumsum(lengths)[:-1]])
    zz = np.minimum.reduceat(z,np.r_[0,np.cumsum(lengths)[:-1]])
    return direction, hh, vv, zz


result = minimize(lambda value: float(value@value), np.zeros(4), method='SLSQP',
                  bounds=[(-.08,.08)]*4,
                  constraints=[{'type':'ineq','fun':lambda value: np.r_[.875-evaluate(value)[1],
                      .775-evaluate(value)[2],evaluate(value)[3]-1.01]}],
                  options={'ftol':1e-12,'maxiter':150})
direction, hh, vv, zz = evaluate(result.x)
# The objective can stop at a feasible non-optimal point. Accept only measured
# safety, and retain the solver status rather than reporting solver success.
assert hh.max()<.88 and vv.max()<.78 and zz.min()>1.01, (result.message,hh.max(),vv.max())
candidate = copy.deepcopy(clip)
for frame,new,dist in zip(active,direction,distance):
    candidate['camera']['target'][frame] = (np.array(clip['camera']['position'][frame])+new*dist).tolist()
assert all(candidate[role]==clip[role] for role in ('eva','angel'))
args.out.mkdir(parents=True,exist_ok=True)
output = args.out/'first_battle_r52_body3_camera2.json'
assert not output.exists()
output.write_text(json.dumps(candidate,separators=(',',':')),'utf8')
report = dict(source_sha256=hashlib.sha256(raw).hexdigest(),
              candidate_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
              optimizer=dict(success=bool(result.success),message=result.message,iterations=result.nit),
              angular_coefficients=result.x.reshape(2,2).tolist(),
              altered_frame_range=[int(active[0]),int(active[-1])],
              maximum_horizontal_ndc=float(hh.max()),maximum_vertical_ndc=float(vv.max()),
              actors_exactly_unchanged=True,camera_positions_unchanged=True,fov_unchanged=True,
              scope='Two authored C2 target envelopes; every exact 60fps selected skin hull constrained. Full independent camera audit still required.',
              native_verified=False,user_accepted=False)
(args.out/'CAMERA_REVISION_REPORT.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps(report,indent=2),flush=True)
