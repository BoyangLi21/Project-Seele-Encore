"""Exact crossing segments and triangle-plane excursions; source evidence only."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from r52_motion_core import selected,read,UNIT,MIRROR
from audit_finisher_leg_clearance_r52 import intersections

def crossing(a,b,tri):
    d=b-a;e1=tri[1]-tri[0];e2=tri[2]-tri[0];h=np.cross(d,e2);det=e1@h
    if abs(det)<1e-9:return None
    s=a-tri[0];u=(s@h)/det;q=np.cross(s,e1);v=(q@d)/det;t=(e2@q)/det
    if 1e-6<u and 1e-6<v and u+v<1-1e-6 and 1e-6<t<1-1e-6:return a+t*d
    return None

parser=argparse.ArgumentParser(description=__doc__)
for n in ('body','assets','angel-rig','clip','out'):parser.add_argument('--'+n,type=Path,required=True)
parser.add_argument('--frames',type=int,nargs='+',required=True);a=parser.parse_args();a.out.mkdir(parents=True,exist_ok=True)
_,hero,angel=selected(a.body,a.assets,a.angel_rig);clip=read(a.clip);parts=['arm_l','forearm_l','hand_l','arm_r','forearm_r','hand_r'];limits=np.cumsum([0]+[len(hero.parts[n])//3 for n in parts]);rows=[]
for frame in a.frames:
    h=hero.decode(clip['eva']['frames'][frame],clip['eva']['bones']);p=angel.decode(clip['angel']['frames'][frame],clip['angel']['bones'])
    hh=(h.surface(parts)*MIRROR*UNIT+np.array(clip['eva']['root_blocks'][frame])).reshape(-1,3,3);ee=(p.surface()*UNIT+np.array(clip['angel']['root_blocks'][frame])).reshape(-1,3,3)
    hits=intersections(hh,ee);facts=[]
    for hit in hits:
        hi,ei=hit['hero_triangle'],hit['angel_triangle'];ht,et=hh[hi],ee[ei];points=[]
        part_index=int(np.searchsorted(limits,hi,side='right')-1);part=parts[part_index];local_triangle=hi-limits[part_index]
        hero_influence=part
        if part in ('hand_l','hand_r'):
            influence=hero.hand_mesh['jointSkins'][part]['influences'];hero_influence=max(influence,key=lambda n:float(np.mean(influence[n][local_triangle*3:local_triangle*3+3])))
        enemy_influences={}
        for vertex in angel.inverse[ei*3:ei*3+3]:
            for bone,weight in zip(angel.ids[vertex],angel.weights[vertex]):enemy_influences[angel.names[int(bone)]]=enemy_influences.get(angel.names[int(bone)],0)+float(weight)
        for first,second in ((ht,et),(et,ht)):
            for edge in range(3):
                q=crossing(first[edge],first[(edge+1)%3],second)
                if q is not None and not any(np.linalg.norm(q-old)<1e-7 for old in points):points.append(q)
        normal=np.cross(et[1]-et[0],et[2]-et[0]);normal/=np.linalg.norm(normal);distance=(ht-et[0])@normal
        facts.append(dict(hero_part=part,hero_dominant_skin_influence=hero_influence,angel_dominant_skin_influence=max(enemy_influences,key=enemy_influences.get),hero_triangle=hi,angel_triangle=ei,
            hero_triangle_world=ht.tolist(),angel_triangle_world=et.tolist(),crossing_points_world=[q.tolist() for q in points],
            maximum_crossing_segment_blocks=max((float(np.linalg.norm(x-y)) for x in points for y in points),default=0),
            hero_vertex_signed_distances_to_angel_triangle_plane_blocks=distance.tolist(),
            smaller_plane_straddle_blocks=float(min(max(distance.max(),0),max(-distance.min(),0)))))
    row=dict(frame=frame,seconds=frame/60,pair_count=len(facts),maximum_crossing_segment_blocks=max((f['maximum_crossing_segment_blocks'] for f in facts),default=0),maximum_smaller_plane_straddle_blocks=max((f['smaller_plane_straddle_blocks'] for f in facts),default=0),pairs=facts)
    rows.append(row);print({k:v for k,v in row.items() if k!='pairs'},flush=True)
report=dict(clip_sha256=hashlib.sha256(a.clip.read_bytes()).hexdigest(),measurement='Exact selected actual posed triangle surfaces. Crossing chord endpoints and signed triangle-plane excursions in world blocks.',
    limits='Crossing chord length is the geometric surface intersection length, not closed-volume penetration depth. Plane straddle is a plane excursion proxy, not a watertight-volume depth. No native/perceptual or allowable-contact acceptance inferred.',samples=rows,native_verified=False,user_accepted=False)
(a.out/'EXACT_CROSSING_SEGMENTS.json').write_text(json.dumps(report,indent=2),'utf8')
