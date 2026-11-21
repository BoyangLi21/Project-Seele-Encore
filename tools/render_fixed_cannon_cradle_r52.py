"""Read-only proposal views using complete source triangles; not native installation acceptance."""
import sys,json,numpy as np
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import calibrate_yashima_cannon_r52 as cal
def main():
    c=json.loads((cal.OUT/'STATION_CANDIDATE.json').read_text());r=cal.ROOT/'.Codex/r52_operations/cradle_candidate';q=Rotation.from_quat(c['mesh_frame']['quaternion_xyzw']).as_matrix()
    gun,_,_=cal.triangles('positron_cannon_payload_r50.mesh.json');v=gun.reshape(-1,3).astype(float);lo,hi=v.min(0),v.max(0);centre=(lo+hi)/2;centre[1]=lo[1];gun=(gun-centre)/16;gun[:,:,0]*=-1;gun=np.array(c['mesh_frame']['translation'])+gun@q.T*8;parts=[(gun,np.array([.40,.48,.58]))]
    production=(r/'cradle_production_raised.bin.gz').is_file();cradle=r/('cradle_production_raised.bin.gz' if production else 'cradle_raised.bin.gz')
    for name,t in cal.read_cloud(cradle).items():parts.append((t,np.array([.65,.38,.12]) if name.startswith('saddle') else np.array([.28,.46,.49])))
    for name,t in cal.read_cloud(r/'hatch_fully_open.bin.gz').items():parts.append((t,np.array([.31,.32,.28]) if name.startswith('cassette') else np.array([.48,.52,.44])))
    fwd=np.array([-np.sin(np.radians(c['prone_yaw'])),0,np.cos(np.radians(c['prone_yaw']))]);right=np.cross(fwd,[0,1,0]);body=np.column_stack((right,[0,1,0],-fwd));offset=np.array(c['prone_position'])-np.array(c['raised_position'])
    for name,t in cal.read_cloud(cal.OUT/'fitted/actual_native_prone_parts.bin.gz').items():parts.append((offset+t@body.T,np.array([.48,.30,.69])))
    fig,axes=plt.subplots(1,3,figsize=(18,8));projections=[('Top / original gun + two real supports',np.eye(3)[[0,2,1]]),('Side / floor 160, deck 174.02',np.eye(3)[[2,1,0]]),('Perspective',Rotation.from_euler('zyx',[30,-55,20],degrees=True).as_matrix())]
    for ax,(title,projection) in zip(axes,projections):
        verts=[];colors=[];depth=[]
        for t,color in parts:
            n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12);shade=.6+.4*np.abs(n@np.array([.2,-.3,.9327]));p=t@projection.T;verts.append(p[:,:,:2]);depth.append(p[:,:,2].mean(1));colors.append(color*shade[:,None])
        verts=np.concatenate(verts);colors=np.concatenate(colors);depth=np.concatenate(depth);order=np.argsort(depth);ax.add_collection(PolyCollection(verts[order],facecolors=colors[order],edgecolors='none',rasterized=True));bounds=verts.reshape(-1,2);lo,hi=bounds.min(0)-2,bounds.max(0)+2;ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal');ax.set_title(title,fontsize=10)
        if title.startswith('Side'):ax.axhline(-14,color='#725f48',ls='--',label='floor160');ax.axhline(.02,color='#555555',ls=':',label='deck174.02');ax.legend(fontsize=8,loc='lower left')
    fig.suptitle(('Compiled production cradle source' if production else 'Independent cradle candidate')+': original contact faces, same gun rise / no second clock\nActual 39 x 53 hatch fully open; exact approved prone source; source audit, not native acceptance');fig.tight_layout();fig.savefig(r/('CRADLE_PRODUCTION_SOURCE_REVIEW.png' if production else 'CRADLE_SOURCE_REVIEW.png'),dpi=140)
if __name__=='__main__':main()
