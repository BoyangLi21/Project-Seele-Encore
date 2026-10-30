"""Prepare native MTR ropeway loops along the cached surveyed mountain corridor."""
import argparse,json,math
from pathlib import Path
import numpy as np

ANGLES=['E','SEE','SE','SSE','S','SSW','SW','SWW','W','NWW','NW','NNW','N','NNE','NE','NEE']


def plan(a):
    with np.load(a.gis/'lake-stations-source/measured.npz')as d:
        top=d['highest'];x0,z0,*_=d['bounds']
    def high(x,z):return int(top[z-z0,x-x0])+20
    rails=[];lines=[];stations=[]
    car=dict(id='ngong_ping_360_normal_red_lht',length=2,width=2,bogie1=0,bogie2=0,padding1=0,padding2=0)
    def add(key,points,platform_segments,platform_order):
        # Explicit horizontal tangents at station platforms and turning points
        # keep the native renderer/path engine responsible for curved geometry.
        for i,(p,q)in enumerate(zip(points,points[1:])):
            rails.append(dict(id=f'{key}-{i}',**{'from':p[:3],'to':q[:3]},from_angle=p[3],to_angle=ANGLES[(ANGLES.index(q[3])+8)%16],
                              mode='CABLE_CAR',kind='platform'if i in platform_segments else'rail',speed=12,reverse_speed=12,vertical_radius=30))
        start=points[0];end=[start[0]-8,start[1],start[2]]
        rails.append(dict(id=key+'-depot',**{'from':end,'to':start[:3]},from_angle='E',to_angle='W',mode='CABLE_CAR',kind='siding'))
        lines.append(dict(id=key,name='箱根索道 '+('桃源台—姥子—大涌谷'if key=='HRW'else'大涌谷—早云山'),mode='CABLE_CAR',
                          platforms=[f'{key}-{i}'for i in platform_order],siding=key+'-depot',cars=[car],frequency=6,repeat=True,dwell=6000))
    west=[[-296,120,1006,'E'],[-289,120,1006,'E'],[-275,120,1006,'E'],
          [-244,high(-244,977),977,'NE'],[-164,high(-164,918),918,'NEE'],[-98,high(-98,871),871,'NE'],
          [-33,151,822,'E'],[-15,151,822,'E'],[60,high(60,822),822,'E'],[150,high(150,824),824,'E'],
          [258,191,825,'E'],[268,191,825,'E'],[276,191,829,'S'],[268,191,833,'W'],[258,191,833,'W'],
          [150,high(150,830),830,'W'],[60,high(60,828),828,'W'],[-15,151,828,'W'],[-33,151,828,'W'],
          [-98,high(-98,877),877,'SW'],[-164,high(-164,924),924,'SWW'],[-244,high(-244,983),983,'SW'],
          [-275,120,1012,'W'],[-289,120,1012,'W'],[-296,120,1012,'W'],[-300,120,1009,'N'],[-296,120,1006,'E']]
    add('HRW',west,{1,6,10,13,17,22},[1,6,10,13,17,22])
    east=[[275,191,823,'E'],[281,191,823,'E'],[291,191,823,'E'],[405,high(405,802),802,'NEE'],[533,high(533,781),781,'NEE'],
          [631,122,762,'E'],[643,122,762,'E'],[650,122,766,'S'],[643,122,770,'W'],[631,122,770,'W'],
          [533,high(533,789),789,'SWW'],[405,high(405,810),810,'SWW'],[291,191,831,'W'],[281,191,831,'W'],
          [275,191,831,'W'],[271,191,827,'N'],[275,191,823,'E']]
    add('HRE',east,{1,5,8,12},[1,5,8,12])
    for key,name,box in [('togendai','桃源台',[-310,96,994,-260,130,1038]),('ubako','姥子',[-38,135,813,-5,160,835]),
                         ('owakudani','大涌谷',[252,175,813,299,200,851]),('sounzan','早雲山',[628,99,744,681,130,800])]:
        stations.append(dict(id=key,name=name,min=box[:3],max=box[3:],color=0xC65245))
    # Native CABLE_CAR rails sag between supports. Subdivide long surveyed
    # spans using the first native XY curve, then place supports above the
    # measured ridge/roof profile. Do not cut cable-shaped trenches in terrain.
    seed=a.gis/'ropeway-native/coarse-track-samples.json'
    if seed.exists():
        samples={r['id']:r['points']for r in json.loads(seed.read_text('utf8'))};refined=[]
        def direction(dx,dz):return ANGLES[round(math.atan2(dz,dx)/(math.pi/8))%16]
        for r in rails:
            points=samples[r['id']]
            for key in ('from','to'):
                x,y,z=r[key]
                if not any(s['min'][0]<=x<=s['max'][0]and s['min'][2]<=z<=s['max'][2]for s in stations):
                    r[key]=[x,max(y,int(top[z-z0-16:z-z0+17,x-x0-16:x-x0+17].max())+26),z]
            if math.hypot(points[0][0]-r['from'][0],points[0][2]-r['from'][2])>math.hypot(points[-1][0]-r['from'][0],points[-1][2]-r['from'][2]):points=points[::-1]
            if r['kind']!='rail'or len(points)<=34:refined.append(r);continue
            n=math.ceil(len(points)/26);vertices=[(r['from'],r['from_angle'])]
            for i in range(1,n):
                index=round((len(points)-1)*i/n);p=points[index];x,z=round(p[0]),round(p[2]);dx=points[min(index+2,len(points)-1)][0]-points[max(0,index-2)][0];dz=points[min(index+2,len(points)-1)][2]-points[max(0,index-2)][2]
                surface=int(top[z-z0-16:z-z0+17,x-x0-16:x-x0+17].max())
                height=max(round(r['from'][1]+(r['to'][1]-r['from'][1])*i/n),surface+26)
                vertices.append(([x,height,z],direction(dx,dz)))
            vertices.append((r['to'],ANGLES[(ANGLES.index(r['to_angle'])+8)%16]))
            for i,((p,pa),(q,qa))in enumerate(zip(vertices,vertices[1:])):
                refined.append(dict(r,id=r['id']+'s'+str(i),**{'from':p,'to':q},from_angle=pa,to_angle=ANGLES[(ANGLES.index(qa)+8)%16]))
        rails=refined
    result=dict(stations=stations,rails=rails,lines=lines,warmup_seconds=120,source='Cached GSI ropeway alignment; native platform approaches adapted to measured station halls')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Prepared',len(rails),'native segments and two connecting ropeway services')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--gis',type=Path,required=True);p.add_argument('--out',type=Path,required=True);plan(p.parse_args())
