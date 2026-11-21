"""Measure existing named arrivals after the explicit current component moves."""
from pathlib import Path
import argparse,hashlib,json,math,re
from query_blocks import read_box,AIR
from r52_spatial_plan import Frame

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    base=a.base.resolve();world=base/'WORLD';plan=json.loads((base/'ROOT_SPATIAL_PLAN.json').read_text('utf-8'))
    assert world==Path('D:/eva/artifacts/map_complete_20261013/WORLD').resolve() and not a.out.resolve().is_relative_to(world)
    text=(ROOT/'src/main/java/com/projectseele/visual/SeeleTravelCommandsR43.java').read_text('utf-8')
    rows=[]
    for key,label,x,y,z,yaw in re.findall(r'new Destination\("([a-z0-9_]+)","([^"]+)",new Vec3\(([-.0-9]+),([-.0-9]+),([-.0-9]+)\),([-.0-9]+)\)',text):
        point=[float(x),float(y),float(z)];component={'command':'pyramid','station':'pyramid','dogma':'terminal','observation':'hangar'}.get(key,key)
        if component in plan['components']:
            frame=Frame(**plan['components'][component]);point=list(frame.point(point));yaw=(float(yaw)+frame.turn)%360
        if key=='hanger_station':label='原实验区车站'
        rows.append(dict(key=key,label=label,component=component,entry_id='original/'+key,position=point,yaw=float(yaw)))
    rows += [dict(key=k,label=label,component=component,entry_id='current/'+k,position=p,yaw=yaw) for k,label,component,p,yaw in [
        ('hangar','新机库登机廊','hangar',[30.5,-1014,354.5],180),
        ('seele','SEELE 会议室门外','pyramid',[14.5,-456,316.5],90),
        ('office','司令办公室前厅','pyramid',[28.5,-434,312.5],0),
        ('transport_shaft','地下运输大井前庭','airshaft',[-1120.5,-475,-612.5],180),
    ]]
    assert len(rows)==len({r['key'] for r in rows})
    shapes=json.loads((world/'native_collision_shapes.json').read_text('utf-8'))
    shape_root=ROOT/'.Codex/map_complete_20261013/route_audit/prelaunch_world_current'
    for name in ('CURRENT_PRODUCTION_SUPPLEMENTAL_SHAPES.json','CURRENT_PRODUCTION_REBASED_SHAPES.json','GATE14_RESOLVED_PRODUCTION_SHAPES.json'):
        d=json.loads((shape_root/name).read_text('utf-8'));shapes.update({s:r['native_boxes'] for s,r in d['rows'].items()})
    def boxes(s):return [] if s.split('[')[0] in AIR or s.startswith('minecraft:light[') else shapes.get(s)
    def clear(s):
        b=boxes(s);return b is not None and not any(q[0]<.81 and q[3]>.19 and q[2]<.81 and q[5]>.19 and q[4]>.001 for q in b)
    issues=[]
    for row in rows:
        original=row['position'];x,y,z=map(math.floor,original);lo=x-2,y-3,z-2;hi=x+2,y+3,z+2
        states=read_box(world,'projectseele:geofront',lo,hi);choices=[]
        for px in range(x-2,x+3):
            for py in range(y-2,y+3):
                for pz in range(z-2,z+3):
                    values=[states.get((px,py+dy,pz),'UNMEASURED') for dy in (-1,0,1)];floor=boxes(values[0])
                    supported=floor is not None and all(any(q[0]<=dx<=q[3] and q[2]<=dz<=q[5] and .999<=q[4]<=1.001 for q in floor) for dx in (.2,.5,.8) for dz in (.2,.5,.8))
                    if supported and clear(values[1]) and clear(values[2]):
                        point=[px+.5,py,pz+.5];cost=sum((point[i]-original[i])**2*(4 if i==1 else 1) for i in range(3));choices.append((cost,point,values))
        if not choices:issues.append(dict(key=row['key'],requested=original,reason='No complete measured native arrival footprint in the named existing entrance'));continue
        _,point,values=min(choices);row['requested_position']=original;row['position']=point
        row['actual_cells']=[dict(position=[math.floor(point[0]),int(point[1])+dy,math.floor(point[2])],state=s) for dy,s in zip((-1,0,1),values)]
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    doc=dict(schema='projectseele.r52.travel-directory.v1',map_author='root',dimension='projectseele:geofront',installed=False,complete_replacement=True,epoch=plan['epoch'],directory_fingerprint='FINAL_BUNDLE_REQUIRED',destinations=rows,issues=issues,measured=not issues,native_verified=False)
    (out/'TRAVEL_CANDIDATE.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(destinations=len(rows),measured=len(rows)-len(issues),issues=issues,world_written=False),ensure_ascii=False))
    assert not issues
if __name__=='__main__':main()
