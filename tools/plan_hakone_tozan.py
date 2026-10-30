"""Author native mountain railway paths from the measured GSI topology."""
import argparse,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import LineString,Point
from plan_hakone_ropeway import ANGLES


def angle(dx,dz):return ANGLES[round(math.atan2(dz,dx)/(math.pi/8))%16]
def opposite(a):return ANGLES[(ANGLES.index(a)+8)%16]
def unit(p,q):
    d=np.asarray(q,float)-p
    return d/np.linalg.norm(d)


def plan(a):
    survey=json.loads((a.gis/'tozan-survey.json').read_text('utf8'))
    stops={s['id']:dict(s)for s in survey['stations']};branches={s['id']:s for s in survey['switchbacks']}
    rails=[];stations=[];seen={};definitions=[]
    def add(key,p,q,aa,ab,kind='rail',speed=24):
        p=list(map(round,p));q=list(map(round,q));pair=tuple(sorted((tuple(p),tuple(q))))
        if p==q:return
        if pair in seen:return seen[pair]
        rails.append(dict(id=key,**{'from':p,'to':q},from_angle=aa,to_angle=ab,kind=kind,mode='TRAIN',speed=speed,reverse_speed=speed,vertical_radius=40))
        seen[pair]=key;return key
    for i,s in enumerate(stops.values()):
        p=np.asarray(s['point'],float);key=s['id'];y=s['rail_y']
        if key in branches:
            b=branches[key];d=unit(b['junction'],p);pa=p-d*24;pb=p
        else:
            prev=survey['sections'][i-1]['points'][-2]if i else[p[0],p[1]-30]
            nxt=survey['sections'][i]['points'][1]if i<len(stops)-1 else[p[0]+30,p[1]-10]
            d=unit(prev,nxt);pa=p-d*12;pb=p+d*12
        if key=='gora':pa=np.array([930,632]);pb=np.array([930,658]);d=np.array([0,1])
        if key=='yumoto':pa=np.array([2203,1123]);pb=np.array([2231,1111]);d=unit(pa,pb)
        # Quantized straight platform endpoints use a native supported angle.
        az=angle(*d);rad=ANGLES.index(az)*math.pi/8;d=np.array([math.cos(rad),math.sin(rad)])
        pa=np.rint(pa);pb=np.rint(pa+d*math.dist(pa,pb))
        s.update(platform_a=pa.tolist(),platform_b=pb.tolist(),direction=d.tolist(),angle=az)
        add(key+'-platform',[pa[0],y,pa[1]],[pb[0],y,pb[1]],az,opposite(az),'platform')
        if key in branches or key=='yumoto':
            end=pb+d*28
            add(key+'-reverse',[pb[0],y,pb[1]],[end[0],y,end[1]],az,opposite(az),'turnback')
        if s['passenger']:
            low=np.minimum(pa,pb)-14;high=np.maximum(pa,pb)+14
            stations.append(dict(id=key,name=s['name'],min=[round(low[0]),y-4,round(low[1])],max=[round(high[0]),y+16,round(high[1])],color=0xBD4939))
    for n,section in enumerate(survey['sections']):
        start,end=stops[section['start']],stops[section['end']]
        raw=LineString(section['points']);controls=section['controls_xyz'];rawlength=raw.length
        pts=[]
        for s,is_start in [(start,True),(end,False)]:
            key=s['id'];p=np.asarray(s['point']);d=np.asarray(s['direction'])
            near=np.asarray(raw.interpolate(min(35,rawlength/3)if is_start else max(0,rawlength-35)).coords[0])
            outward=near-p
            side='platform_b'if np.dot(outward,d)>0 else'platform_a'
            at=np.asarray(s[side]);tangent=s['angle']if side=='platform_b'else opposite(s['angle'])
            if key in branches:
                junction=branches[key]['junction'];j=np.asarray(junction)
                # Both main-line legs share the same physical branch rail.
                add(key+'-branch',[j[0],s['rail_y'],j[1]],[at[0],s['rail_y'],at[1]],s['angle'],opposite(s['angle']))
                at=j;tangent=opposite(s['angle'])
            pts.append((at,s['rail_y'],tangent if is_start else opposite(tangent)))
        begin,finish=pts;d0=raw.project(Point(begin[0]));d1=raw.project(Point(finish[0]))
        middle=[]
        for p in raw.simplify(1.2).coords:
            d=raw.project(Point(p))
            if d0+10<d<d1-10:middle.append(np.asarray(p))
        coords=[begin[0]]+middle+[finish[0]]
        vertices=[]
        for i,p in enumerate(coords):
            if i==0:y,az=begin[1:]
            elif i==len(coords)-1:y,az=finish[1:]
            else:
                az=angle(*(coords[i+1]-coords[i-1]));dist=raw.project(Point(p))
                known=[raw.project(Point(c[0],c[2]))for c in controls]
                y=float(np.interp(dist,known,[c[1]for c in controls]))
            vertices.append(([p[0],y,p[1]],az))
        for i,((p,aa),(q,ab))in enumerate(zip(vertices,vertices[1:])):
            add(f'HT-{n}-{i}',p,q,aa,opposite(ab))
    gora=stops['gora'];p=gora['platform_a'];add('HT-siding',[930,55,586],[930,55,620],'S','N','siding')
    add('HT-depot-lead',[930,55,620],[p[0],55,p[1]],'S','N')
    order=[s['id']+'-platform'for s in stops.values()]
    car=dict(id='e44_mini_cab_3',length=9,width=2.5,bogie1=-2.5,bogie2=2.5,padding1=0,padding2=0)
    lines=[dict(id='HT',name='箱根登山電車 強羅—箱根湯本',platforms=order+order[-2::-1],siding='HT-siding',cars=[car,car],frequency=6,repeat=False,dwell=10000)]
    # The surveyed cable railway is a steep ground railway, not another aerial cable.
    cable=LineString(survey['cable_railway']);p0=np.array([653,766]);p1=np.array([917,653]);d=unit(p0,p1);az=angle(*d)
    cablepoints=[]
    for i,(x,z)in enumerate([p0,p0+d*22,p0+d*55,p0+d*112,p0+d*174,p1-d*23,p1]):
        fraction=float(np.dot(np.array([x,z])-p0,d)/np.dot(p1-p0,d));y=round(104+(55-104)*fraction)
        if i<=1:y=104
        if i>=5:y=55
        cablepoints.append([x,y,z])
    for i,(p,q)in enumerate(zip(cablepoints,cablepoints[1:])):
        add('HC-'+str(i),p,q,az,opposite(az),'platform'if i in(0,5)else'rail',18)
    lead=[p0[0]-d[0]*12,104,p0[1]-d[1]*12]
    add('HC-siding',[p0[0]-d[0]*42,104,p0[1]-d[1]*42],lead,az,opposite(az),'siding')
    add('HC-depot-lead',lead,cablepoints[0],az,opposite(az))
    q=np.asarray(cablepoints[-1]);add('HC-reverse',q,[q[0]+d[0]*12,55,q[2]+d[1]*12],az,opposite(az),'turnback')
    lines.append(dict(id='HC',name='箱根登山ケーブルカー 早雲山—強羅',platforms=['HC-0','HC-5','HC-0'],siding='HC-siding',cars=[car],frequency=8,repeat=False,dwell=10000))
    # The existing Sounzan native station is retained. Its box already encloses
    # the lower-level cable platform; do not create a duplicate station identity.
    for station in stations:
        if station['id']=='gora':station['min'][0]=900;station['max'][2]=685
    # Integer rail nodes need tangent adjustments at these surveyed tight
    # bends. Apply each to every incident rail so node directions stay joined.
    tangents={(1005,53,932):'NE',(1066,50,949):'S',(1278,25,913):'S',
              (1353,19,963):'E',(1610,-10,1121):'S',(1912,-37,1105):'NEE',(2112,-49,1164):'SSE'}
    for rail in rails:
        for endpoint in('from','to'):
            pos=tuple(rail[endpoint]);key=endpoint+'_angle'
            if pos==(1544,4,1066):rail[endpoint][0]=1543
            if pos in tangents:
                desired=tangents[pos];prior=ANGLES.index(rail[key]);index=ANGLES.index(desired)
                if abs((index-prior+8)%16-8)>4:desired=opposite(desired)
                rail[key]=desired
    result=dict(stations=stations,rails=rails,lines=lines,warmup_seconds=120,station_geometry=list(stops.values()),
                source='GSI measured Tozan RailCL with three original switchbacks; adapted playable platforms',
                cable_points=cablepoints,train_asset_note='Installed short native train asset, not an exact Allegra replica')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda v:v.item()),'utf8')
    print(json.dumps(dict(rails=len(rails),stations=len(stations),lines=len(lines),switchbacks=3)))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('gis','out'):p.add_argument('--'+name,type=Path,required=True)
    plan(p.parse_args())
