"""Root read-only plan view and curve-clearance candidates, never map edits."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'artifacts/r52_hq_approach_candidate';design=json.loads((out/'CANDIDATE.json').read_text('utf8'))
    samples=json.loads((out/'NATIVE_SAMPLES.json').read_text('utf8'));assert all(r['valid'] for r in samples)
    by_id={r['id']:r for r in design['segments']};points={r['id']:np.asarray(r['points']) for r in samples};findings=[]
    retained=[]
    rp=out/'RETAINED_NATIVE_SAMPLES.json'
    if rp.exists():
        retained=json.loads(rp.read_text('utf8'))
        assert all(r['valid'] for r in retained)
        for r in retained:r['id']='retained::'+r['id'];points[r['id']]=np.asarray(r['points'])
    for i,a in enumerate(samples):
        pa=points[a['id']]
        for b in samples[i+1:]+retained:
            pb=points[b['id']];shared=[]
            for u in (pa[0],pa[-1]):
                for v in (pb[0],pb[-1]):
                    if np.linalg.norm(u-v)<.001:shared.append(u)
            aa=pa[::2];bb=pb[::2]
            if shared:
                aa=aa[np.all(np.asarray([np.linalg.norm(aa-v,axis=1)>14 for v in shared]),axis=0)]
                bb=bb[np.all(np.asarray([np.linalg.norm(bb-v,axis=1)>14 for v in shared]),axis=0)]
            if not len(aa) or not len(bb):continue
            distance,near=cKDTree(bb).query(aa,k=1);idx=int(np.argmin(distance));p,q=aa[idx],bb[near[idx]]
            horizontal=float(np.linalg.norm((p-q)[[0,2]]));height=abs(float(p[1]-q[1]))
            if horizontal<6-1e-5 and height<6-1e-5:
                findings.append(dict(a=a['id'],b=b['id'],retained_rail=b['id'].startswith('retained::'),distance=float(distance[idx]),horizontal=horizontal,height=height,
                    point_a=p.tolist(),point_b=q.tolist(),shared_endpoint=bool(shared),status='REVIEW_NOT_PASSED'))
    fig,axs=plt.subplots(1,2,figsize=(15,8),constrained_layout=True)
    colors={name:('#a0a0a0' if name.startswith('retained::') else '#327899' if name.startswith('u1_') else '#b9742b' if name.startswith('u2_') else '#b6303c') for name in points}
    for name,p in points.items():
        axs[0].plot(p[:,0],p[:,2],color=colors[name],lw=1);axs[1].plot(np.arange(len(p)),p[:,1],color=colors[name],alpha=.5,lw=.7)
    axs[0].add_patch(plt.Rectangle((-90,207),240,240,fill=False,edgecolor='black',ls='--'))
    axs[0].add_patch(plt.Rectangle((-22,466),104,76,fill=False,edgecolor='red',lw=2))
    axs[0].text(30,327,'HQ',ha='center');axs[0].text(30,555,'Original HQ station footprint',ha='center',fontsize=8)
    for f in findings:axs[0].plot(f['point_a'][0],f['point_a'][2],'rx',ms=6)
    axs[0].set_aspect('equal');axs[0].invert_yaxis();axs[0].set_xlabel('X');axs[0].set_ylabel('Z / north upward');axs[0].set_title('Native MTR candidate curves / NOT installed')
    axs[1].set_xlabel('Sample metres along individual segment');axs[1].set_ylabel('Native rail elevation Y');axs[1].set_title('Retained outside level -467 / HQ station -560')
    fig.savefig(out/'NATIVE_CANDIDATE_PLAN.png',dpi=125);plt.close(fig)
    report=dict(world_written=False,native_valid_segments=len(samples),retained_underground_segments=len(retained),maximum_sampled_grade=max(r['maximum_sampled_grade'] for r in samples),
        close_approaches=findings,not_full_train_or_tunnel_acceptance=True,pending=['resolve red-marked crossings/merge domains',
            'compare all retained rails and structures','bounded native tunnel sections','vehicle path/progress provenance'])
    (out/'CURVE_REVIEW.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('close_approaches','pending')}));print('close approaches',len(findings))
    for f in findings:print(f['a'],f['b'],round(f['horizontal'],2),round(f['height'],2),[round(v,1) for v in f['point_a']])


if __name__=='__main__':main()
