"""Original ACCAD marker/FK evidence before any EVA retarget or IK."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/combat/locomotion_sequence_v2'
OUT=ROOT/'artifacts/rebuild_r44/combat/raw_low_state_semantics'
OUT.mkdir(exist_ok=True)
card=json.loads((BASE/'source_card.json').read_text('utf8'))
choices={'crouch':[140,240,350,402],'to_prone':[21,60,80,100,120,142],
         'from_prone':[16,35,55,75,85],'stand':[25,40,60,80],
         'lie_hold':[0,30,60,93],'crawl':[0,62,124,248,372],'crawl_back':[0,80,240,400,480]}
extra=json.loads((OUT/'additional_low_state_sources.json').read_text('utf8'))
extra_labels={'Male2_A9_Lie.bvh':'lie_hold','Male2_A11_Crawl.bvh':'crawl','Male2_A12_CrawlBackwards.bvh':'crawl_back'}
for row in extra:
    label=extra_labels[row['file']]
    card['segments'].append(dict(label=label,source_file=str(Path(card['segments'][0]['source_file']).parent/row['file']),source_sha256=row['source_sha256']))
cal=np.load(BASE/'source/calibration_stand.npz',allow_pickle=False);cal_names=[str(n) for n in cal['names']];cal_idx={n:i for i,n in enumerate(cal_names)}
cal_right=cal['positions'][0,cal_idx['RightUpLeg']]-cal['positions'][0,cal_idx['LeftUpLeg']];cal_right[1]=0;cal_right/=np.linalg.norm(cal_right)
cal_front=np.cross([0.,1.,0.],cal_right)
receipt=[]
for segment in card['segments']:
    label=segment['label']
    if label not in choices:continue
    path=BASE/'source'/(label+'.npz') if label not in extra_labels.values() else OUT/(Path(segment['source_file']).stem+'.npz')
    data=np.load(path,allow_pickle=False)
    names=[str(n) for n in data['names']];idx={n:i for i,n in enumerate(names)}
    # One proper source-to-Z-up coordinate change; original points are not
    # lowered or retargeted. Hips' horizontal travel remains real mocap data.
    first=data['positions'][choices[label][0]];right=first[idx['RightUpLeg']]-first[idx['LeftUpLeg']];right[1]=0;right/=np.linalg.norm(right)
    up=np.array([0.,1.,0.]);forward=np.cross(up,right);basis=np.vstack((right,forward,up))
    assert abs(np.linalg.det(basis)-1)<1e-8
    origin=first[idx['Hips']].copy();origin[1]=0
    figure=plt.figure(figsize=(3.8*len(choices[label]),7.6),layout='constrained')
    for column,frame in enumerate(choices[label]):
        points=(data['positions'][frame]-origin)@basis.T/100
        root=points[idx['Hips']];heights={n:float(points[idx[n],2]) for n in ('Hips','Spine','Spine1','Head','LeftForeArm','RightForeArm','LeftHand','RightHand','LeftFoot','RightFoot')}
        anterior={n:(R.from_quat(data['rotations'][frame,idx[n]])*R.from_quat(cal['rotations'][0,cal_idx[n]]).inv()).apply(cal_front) for n in ('Hips','Spine1','Head')}
        for row,(elev,azim) in enumerate(((15,-70),(8,0))):
            ax=figure.add_subplot(2,len(choices[label]),row*len(choices[label])+column+1,projection='3d')
            for i,parent in enumerate(data['parents']):
                if parent<0 or names[i]=='ToSpine':continue
                p,q=points[int(parent)],points[i]
                colour='#1c72a1' if 'Left' in names[i] else '#bf6043' if 'Right' in names[i] else '#383e48'
                ax.plot([p[0],q[0]],[p[1],q[1]],[p[2],q[2]],color=colour,lw=3)
            ax.scatter(points[:,0],points[:,1],points[:,2],s=10,c='#242d38')
            for n,normal in anterior.items():
                point=points[idx[n]];direction=basis@normal
                ax.quiver(*point,*(direction*.2),color='#98233d',linewidth=1.4)
            xx,yy=np.meshgrid(np.linspace(root[0]-.7,root[0]+.7,2),np.linspace(root[1]-1.,root[1]+1.,2))
            ax.plot_surface(xx,yy,np.zeros_like(xx),color='#aec4a3',alpha=.25)
            ax.set(xlim=(root[0]-.7,root[0]+.7),ylim=(root[1]-1.,root[1]+1.),zlim=(0,1.8))
            ax.set_box_aspect((1.4,2,1.8));ax.view_init(elev=elev,azim=azim);ax.set_xlabel('X (m)');ax.set_ylabel('Y (m)');ax.set_zlabel('height (m)')
            ax.set_title(f"Original F{frame} / {frame/float(data['fps']):.3f}s\nhips {heights['Hips']:.2f}m, chest {heights['Spine1']:.2f}m",fontsize=10)
        receipt.append(dict(take=label,source_file=segment['source_file'],source_sha256=segment['source_sha256'],original_frame=frame,original_seconds=frame/float(data['fps']),actual_source_joint_heights_metres=heights,anterior_dot_world_up={n:float(v[1]) for n,v in anterior.items()}))
    figure.suptitle(Path(segment['source_file']).name+' | Original captured BVH FK, not EVA / not original video; no fingers',fontsize=14)
    figure.savefig(OUT/(label+'_raw_marker_frames.png'),dpi=120)
    plt.close(figure)
(OUT/'raw_low_state_semantics.json').write_text(json.dumps(dict(samples=receipt,
    original_capture_kind='Licensed ACCAD performer BVH joint trajectories; these images render actual raw skeletal points, not source video pixels',
    source_url=card['source_url'],source_license=card['source_license'],finger_capture=False,
    official_catalog_url='https://accad.osu.edu/sites/accad.osu.edu/files/ACCAD_mocap_Data_Male_2.pdf',
    interpretation='Official A8 is explicitly not completely flat: only a transition. Independent A9 Lie down is anterior/face-down with chest normal dot world-up approximately -0.995, while head is raised to look ahead. A11 transfers support to elbows/forearms during actual forward prone crawling. A source wrist point near floor does not mean palms exclusively carry prone support.'),indent=2),'utf8')
print('Saved exact raw human marker frames and heights')
