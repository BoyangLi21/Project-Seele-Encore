"""Every authored grip frame, exact edge intersections with conservative radius bins."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
from scipy.spatial import cKDTree
from calibrated_arm_r49 import axial_twist
from r52_motion_core import selected,read,UNIT,MIRROR
from audit_finisher_leg_clearance_r52 import segment_hit,intersections


def exact_pairs(hero,enemy):
    amin,amax=enemy.min(1),enemy.max(1);centres=enemy.mean(1)
    radii=np.linalg.norm(enemy-centres[:,None,:],axis=2).max(1)
    hc=hero.mean(1);hr=np.linalg.norm(hero-hc[:,None,:],axis=2).max(1)
    neighbours=[[] for _ in hero]
    edges=np.r_[0,np.power(2.,np.arange(-5,8)),np.inf]
    for lo,hi in zip(edges[:-1],edges[1:]):
        ids=np.flatnonzero((radii>=lo)&(radii<hi))
        if not len(ids):continue
        lists=cKDTree(centres[ids]).query_ball_point(hc,hr+radii[ids].max()+1e-8)
        for i,values in enumerate(lists):
            if values:neighbours[i].extend(ids[values])
    hits=[]
    for i,tri in enumerate(hero):
        if not neighbours[i]:continue
        indices=np.asarray(neighbours[i],dtype=int)
        mask=np.all(amax[indices]>=tri.min(0),axis=1)&np.all(amin[indices]<=tri.max(0),axis=1)
        indices=indices[mask];other=enemy[indices]
        if not len(other):continue
        found=np.zeros(len(other),bool)
        for j in range(3):found|=segment_hit(tri[j],tri[(j+1)%3],other)
        for j in np.flatnonzero(~found):
            e=other[j]
            if any(segment_hit(e[k],e[(k+1)%3],tri[None])[0] for k in range(3)):found[j]=True
        hits.extend((i,int(indices[j])) for j in np.flatnonzero(found))
    return hits


parser=argparse.ArgumentParser(description=__doc__)
for name in ('body','assets','angel-rig','clip','out'):
    parser.add_argument('--'+name,type=Path,required=True)
parser.add_argument('--start',type=int,default=342);parser.add_argument('--end',type=int,default=749)
parser.add_argument('--step',type=int,default=1);parser.add_argument('--parity',action='store_true')
parser.add_argument('--renderer-welds',action='store_true')
parser.add_argument('--groups',nargs='+',choices=('head','torso','legs','arms'),default=['head','torso','legs','arms'])
args=parser.parse_args();_,hero,angel=selected(args.body,args.assets,args.angel_rig);clip=read(args.clip)
runtime_welds=None
if args.renderer_welds:
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.codex'))
    from r52_runtime_weld_model import install
    runtime_welds=install(hero)
groups={'head':['head'],'torso':['torso_lower','torso_upper','neck'],'legs':['leg_l','shin_l','foot_l','leg_r','shin_r','foot_r'],
        'arms':['arm_l','forearm_l','hand_l','arm_r','forearm_r','hand_r']}
groups={name:parts for name,parts in groups.items() if name in args.groups}
rows=[];report=dict(clip_sha256=hashlib.sha256(args.clip.read_bytes()).hexdigest(),frames=[args.start,args.end],step=args.step,samples=rows,
    checked_groups=list(groups),broadphase='Disjoint actual triangle radius bins. Sphere neighbourhood radii remain conservative; identical exact AABB and edge tests decide intersections.',
    scope='Every indicated authored60fps sample. Does not qualify between-frame swept clearance or native/art acceptance.',native_verified=False,user_accepted=False)
report['renderer_fallback_welds']=runtime_welds
for frame in range(args.start,args.end+1,args.step):
    started=time.perf_counter();h=hero.decode(clip['eva']['frames'][frame],clip['eva']['bones']);a=angel.decode(clip['angel']['frames'][frame],clip['angel']['bones'])
    hr=np.array(clip['eva']['root_blocks'][frame]);ar=np.array(clip['angel']['root_blocks'][frame]);enemy=(a.surface()*UNIT+ar).reshape(-1,3,3)
    row=dict(frame=frame,seconds=frame/60,groups={},hero_upper_axial_degrees={s:float(np.degrees(abs(axial_twist(h.q['arm_'+s],hero.elbows[s]-hero.P['arm_'+s])))) for s in ('l','r')},
             minimum_actual_angel_skin_y_blocks=float(enemy[:,:,1].min()))
    for name,parts in groups.items():
        chosen=[n for n in parts if n in hero.parts]
        surface=(h.surface(chosen)*MIRROR*UNIT+hr).reshape(-1,3,3)
        pairs=exact_pairs(surface,enemy);row['groups'][name]=dict(pairs=len(pairs),hits=pairs[:12])
        bounds=np.cumsum([0]+[len(hero.parts[n])//3 for n in chosen])
        row['groups'][name]['hero_part_pairs']={part:sum(int(bounds[i]<=p[0]<bounds[i+1]) for p in pairs) for i,part in enumerate(chosen)}
        if args.parity:
            reference={(r['hero_triangle'],r['angel_triangle']) for r in intersections(surface,enemy)}
            assert set(pairs)==reference,(frame,name,len(pairs),len(reference));row['groups'][name]['old_exact_algorithm_pair_set_equal']=True
    rows.append(row)
    if frame%12==0 or any(g['pairs'] for g in row['groups'].values()) or frame==args.end:
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2),'utf8')
        print(frame,{name:g['pairs'] for name,g in row['groups'].items()},'seconds',round(time.perf_counter()-started,3),flush=True)
report['failed_frames']=[r['frame'] for r in rows if any(g['pairs'] for g in r['groups'].values())]
report['all_indicated_frames_clear']=not report['failed_frames']
report['left_arm_failed_frames']=[r['frame'] for r in rows if any(r['groups'].get('arms',{}).get('hero_part_pairs',{}).get(p,0) for p in ('arm_l','forearm_l','hand_l'))]
report['left_arm_clear_suffix_start_frame']=max(report['left_arm_failed_frames'])+args.step if report['left_arm_failed_frames'] else args.start
args.out.write_text(json.dumps(report,indent=2),'utf8')
