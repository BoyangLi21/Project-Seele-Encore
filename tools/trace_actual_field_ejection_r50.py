"""Read-only finite landing/70-tick swept-envelope trace of the saved original EVA capsule."""
import json,math,itertools
from pathlib import Path
import numpy as np
import nbtlib
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'artifacts/rebuild_r49/native_qa/worlds/SEELE_R49_QA'
OUT=ROOT/'artifacts/rebuild_r50/native_client/ejection_preflight'
AIR={'minecraft:air','minecraft:cave_air','minecraft:void_air'}

def main():
    player=nbtlib.load(WORLD/'playerdata/76a86ddf-0aef-4b82-99e9-41d080e8ed30.dat')
    unit=player['RootVehicle']['Entity'];plug=unit['Passengers'][0]
    foot=np.array([float(x)for x in unit['Pos']]);start=np.array([float(x)for x in plug['Pos']])
    quat=[float(plug[k])for k in ['PoseQX','PoseQY','PoseQZ','PoseQW']];x,y,z,qw=quat
    R=np.array([[1-2*(y*y+z*z),2*(x*y-z*qw),2*(x*z+y*qw)],
                [2*(x*y+z*qw),1-2*(x*x+z*z),2*(y*z-x*qw)],
                [2*(x*z-y*qw),2*(y*z+x*qw),1-2*(x*x+y*y)]])
    corners=np.array(list(itertools.product([-1.2,1.2],[-1.2,1.2],[-.15,10.15])))@R.T
    minimum,maximum=corners.min(axis=0),corners.max(axis=0)
    rear=np.array([math.sin(math.radians(float(unit['Rotation'][0]))),0,-math.cos(math.radians(float(unit['Rotation'][0])))])
    relative=np.array([float(plug['LockedSocketToPlug'+k])for k in ['TX','TY','TZ']])
    socket=start-R@relative;escape=socket+rear*17.4+np.array([0,10.2,0]);probe=foot+rear*22
    world=MeasuredWorld(WORLD)
    lo=(math.floor(probe[0])-20,math.floor(foot[1])-133,math.floor(probe[2])-20)
    hi=(math.ceil(probe[0])+20,math.ceil(max(escape[1]+18,foot[1]+24)),math.ceil(probe[2])+20)
    world.box(lo,hi);world.box(tuple(map(math.floor,start-8)),tuple(map(math.ceil,start+np.array([8,18,8]))));world.load()
    shapes=json.loads((WORLD/'native_collision_shapes.json').read_text(encoding='utf-8-sig'))
    def bounds(p):return p+minimum+.04,p+maximum-.04
    def blocks(L,H):
        for xx in range(math.floor(L[0]),math.floor(H[0])+1):
            for yy in range(math.floor(L[1]),math.floor(H[1])+1):
                for zz in range(math.floor(L[2]),math.floor(H[2])+1):
                    s=world.get(xx,yy,zz)
                    if s is None:yield None,None,{'pos':[xx,yy,zz],'reason':'unread_section'};continue
                    if s not in AIR and s not in shapes:yield None,None,{'pos':[xx,yy,zz],'state':s,'reason':'unknown_native_shape'};continue
                    for b in shapes.get(s,[]):yield np.array(b[:3])+[xx,yy,zz],np.array(b[3:])+[xx,yy,zz],{'pos':[xx,yy,zz],'state':s}
    def volume(L,H,l,h):return float(np.maximum(0,np.minimum(H,h)-np.maximum(L,l)).prod())
    def landing(x,z):
        rejected=[]
        for y in range(math.floor(foot[1])+18,math.floor(foot[1])-129,-1):
            s=world.get(x,y,z)
            if s is None:return None,{'reason':'unread_column','pos':[x,y,z]}
            if not any(b==[0.,0.,0.,1.,1.,1.]for b in shapes.get(s,[])):continue
            floor_state=s
            a,h=world.get(x,y+1,z),world.get(x,y+2,z)
            if a.startswith(('minecraft:water','minecraft:lava'))or h.startswith(('minecraft:water','minecraft:lava'))or shapes.get(a,[])or shapes.get(h,[]):
                rejected.append({'floor':[x,y,z],'reason':'above_or_head_collision','above':a,'head':h});continue
            p=np.array([x+.5,y+1.04-minimum[1],z+.5]);L,H=bounds(p);bad=None
            for l,h,record in blocks(L,H):
                if l is None or volume(L,H,l,h)>0:bad=dict(record,reason=record.get('reason','capsule_landing_native_solid'));break
            if bad is None:
                for xx in range(math.floor(L[0]),math.floor(H[0])+1):
                    for yy in range(math.floor(L[1]),math.floor(H[1])+1):
                        for zz in range(math.floor(L[2]),math.floor(H[2])+1):
                            s=world.get(xx,yy,zz)
                            if 'waterlogged=true'in s or s.startswith(('minecraft:water','minecraft:lava')):bad={'reason':'capsule_landing_fluid','pos':[xx,yy,zz],'state':s};break
            if bad:rejected.append(dict(floor=[x,y,z],first_rejection=bad));continue
            return p,{'floor':[x,y,z],'floor_state':floor_state,'prior_rejections':rejected}
        return None,{'reason':'no_clear_landing_in_single_column','floor_rejections':rejected}
    def smooth(t):return t*t*(3-2*t)
    def route(end):
        PL,PH=bounds(start)
        for tick in range(1,71):
            t=tick/70
            if t<=.38:p=start+(escape-start)*smooth(t/.38)
            else:
                u=smooth((t-.38)/.62);p=escape+(end-escape)*u+np.array([0,math.sin(math.pi*u)*8,0])
            L,H=bounds(p)
            for l,h,record in blocks(L,H):
                if l is None:return dict(record,tick=tick,reason=record['reason'])
                if volume(L,H,l,h)>volume(PL,PH,l,h)+1e-4:return dict(record,tick=tick,reason='increasing_capsule_native_solid_overlap',bounds=[L.tolist(),H.tolist()])
            PL,PH=L,H
        return None
    x,z=math.floor(probe[0]),math.floor(probe[2]);records=[]
    offsets=[(0,0)]+[(dx,dz)for radius in [4,8,12]for dx,dz in [(radius,0),(-radius,0),(0,radius),(0,-radius),(radius,radius),(radius,-radius),(-radius,radius),(-radius,-radius)]]
    for dx,dz in offsets:
        end,detail=landing(x+dx,z+dz);bad=None if end is None else route(end)
        records.append(dict(offset=[dx,dz],column=[x+dx,z+dz],landing=None if end is None else end.tolist(),landing_check=detail,arc_first_rejection=bad,static_complete_arc=end is not None and bad is None))
    OUT.mkdir(parents=True,exist_ok=True)
    report=dict(source_player=str(WORLD/'playerdata/76a86ddf-0aef-4b82-99e9-41d080e8ed30.dat'),foot=foot.tolist(),start=start.tolist(),quaternion=quat,socket=socket.tolist(),escape=escape.tolist(),probe=probe.tolist(),
                source_column_only_old_algorithm=True,finite_candidates=len(records),candidates=records,world_written=False,native_run=False,
                scope='Exact saved pose and actual FULL blocks/cached native collision-shape arrays; native chunk-now/entity occupancy not simulated, so a static clear arc is only a candidate, never gameplay pass')
    (OUT/'finite_landing_and_arc_trace.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Finite candidates',len(records),'landings',sum(r['landing']is not None for r in records),'static arcs',sum(r['static_complete_arc']for r in records))
    for r in records:
        print(r['column'],'landing',r['landing'],'arc',r['arc_first_rejection'],'first landing rejection',str(r['landing_check'])[:220])

if __name__=='__main__':main()
