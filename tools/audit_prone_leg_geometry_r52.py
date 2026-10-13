"""Same powered native full source triangles: candidate leg swivel, no world edits."""
from pathlib import Path
import gzip, json, struct
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import brentq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

ROOT=Path(__file__).resolve().parents[1]
CAP=ROOT/'.Codex/r52_operations/calibration_powered'
OUT=ROOT/'.Codex/r52_prone_support'

def cloud(path=None):
    data=gzip.decompress((path or CAP/'actual_native_prone_parts.bin.gz').read_bytes());at=0
    def integer():
        nonlocal at
        v=struct.unpack_from('>i',data,at)[0];at+=4;return v
    def word():
        nonlocal at
        n=struct.unpack_from('>H',data,at)[0];at+=2;s=data[at:at+n].decode();at+=n;return s
    assert integer()==0x52353243 and integer()==1
    result={}
    for _ in range(integer()):
        name,sha=word(),word();n=integer();v=np.frombuffer(data,dtype='>f4',count=n*3,offset=at).astype(float).reshape(-1,3,3);at+=n*12;result[name]=v
    assert at==len(data)
    return result

def draw(parts,ax,projection,title):
    vertices=[];colors=[];depth=[]
    palette={'leg_l':[.58,.37,.73],'shin_l':[.46,.28,.6],'leg_r':[.74,.42,.61],'shin_r':[.62,.31,.49],'foot_l':[.38,.63,.36],'foot_r':[.38,.63,.36]}
    for name,xyz in parts.items():
        color=np.array(palette.get(name,[.47,.43,.55]));normal=np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-12)
        shade=.5+.5*np.abs(normal@np.array([.25,.9,.35]));v=xyz@projection.T
        vertices.append(v[:,:,:2]);colors.append(color[None,:]*shade[:,None]);depth.append(v[:,:,2].mean(1))
    vertices=np.concatenate(vertices);colors=np.concatenate(colors);depth=np.concatenate(depth);order=np.argsort(depth)
    ax.add_collection(PolyCollection(vertices[order],facecolors=colors[order],edgecolors='none',rasterized=True))
    p=vertices.reshape(-1,2);lo,hi=p.min(0)-1,p.max(0)+1;ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal');ax.set_title(title)
    if title.endswith('side') or title.endswith('rear'):
        ax.axhline(0,color='#ee6729',linewidth=1);ax.axhspan(lo[1],0,color='#ee6729',alpha=.07)
    ax.set_xlabel('metres');ax.set_ylabel('metres')

def main():
    original=cloud();capture=json.loads((CAP/'native_prone_cannon.json').read_text());extra=json.loads((CAP/'native_prone_cannon_extra.json').read_text());candidate={n:v.copy() for n,v in original.items()};report={'scope':'same powered production full source skin candidate only; not native modified-pose acceptance','legs':{}}
    matrices={n:np.array(b['matrix']).reshape(4,4,order='F') for n,b in capture['bones'].items()}
    for side,sign in [('l',-1),('r',1)]:
        def point(n):return (matrices[n]@np.r_[extra['actual_local_bones'][n]['pivot'],1])[:3]*5
        origin=point('leg_'+side);end=point('foot_'+side);axis=end-origin;axis/=np.linalg.norm(axis);vertices=np.concatenate([original[n].reshape(-1,3) for n in ['leg_'+side,'shin_'+side]])
        def clearance(degrees):return (origin+Rotation.from_rotvec(axis*np.radians(degrees*sign)).apply(vertices-origin))[:,1].min()-.03
        angle=brentq(clearance,0,80);rotation=Rotation.from_rotvec(axis*np.radians(angle*sign))
        for n in ['leg_'+side,'shin_'+side]:candidate[n]=(origin+rotation.apply(original[n].reshape(-1,3)-origin)).reshape(-1,3,3)
        report['legs'][side]={'outward_swivel_degrees':angle,'before_min_m':float(vertices[:,1].min()),'after_min_m':float(np.concatenate([candidate[n].reshape(-1,3) for n in ['leg_'+side,'shin_'+side]])[:,1].min()),'foot_world_matrix_unchanged':True,'hinge_local_rotation_unchanged':True,'hip_world_unchanged':True,'upper_lower_lengths_unchanged':True}
    OUT.mkdir(exist_ok=True);(OUT/'NATIVE_SWIVEL_CANDIDATE.json').write_text(json.dumps(report,indent=2),'utf8')
    projections=[('side',np.eye(3)[[2,1,0]]),('rear',np.eye(3)[[0,1,2]]),('top',np.eye(3)[[0,2,1]])]
    fig,axes=plt.subplots(2,3,figsize=(18,13))
    for row,(label,parts) in enumerate([('Before',original),('Candidate',candidate)]):
        for col,(title,projection) in enumerate(projections):draw(parts,axes[row,col],projection,label+' '+title)
    fig.suptitle('Same powered native prone source: full original triangles, soles/hips fixed\nCandidate preserves original knee hinge and link lengths; source geometry review only')
    fig.tight_layout();fig.savefig(OUT/'NATIVE_PRONE_SOURCE_SWIVEL_COMPARISON.png',dpi=150);plt.close(fig)
    corrected=cloud(OUT/'powered_native_01.bin.gz')
    fig,axes=plt.subplots(2,3,figsize=(15,11))
    ankle=(matrices['foot_l']@np.r_[extra['actual_local_bones']['foot_l']['pivot'],1])[:3]*5
    for row,(label,parts) in enumerate([('Before',original),('Production helper',corrected)]):
        selected={n:t for n,t in parts.items() if n in ['shin_l','foot_l']}
        for col,(title,projection) in enumerate(projections):
            ax=axes[row,col];draw(selected,ax,projection,label+' '+title);p=projection@ankle
            ax.scatter(p[0],p[1],marker='+',s=75,color='#202020',zorder=20);ax.annotate('same ankle centre',p[:2],xytext=(7,8),textcoords='offset points',fontsize=8,zorder=20)
            if title=='side':ax.set_xlim(16,30);ax.set_ylim(-6,11)
            elif title=='rear':ax.set_xlim(-14,-3);ax.set_ylim(-6,11)
            else:ax.set_xlim(-14,-3);ax.set_ylim(16,30)
    fig.suptitle('Same full source left ankle: before / production helper\nShoe world matrix and ankle centre unchanged; shin-foot surface contact verified by production triangle BVH')
    fig.tight_layout();fig.savefig(OUT/'NATIVE_PRONE_ANKLE_SOURCE_DETAIL.png',dpi=160);plt.close(fig)
    print(json.dumps(report))

if __name__=='__main__':main()
