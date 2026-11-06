"""Prepare the three-port Lake Ashi native boat circulation."""
import argparse,json
from pathlib import Path
from plan_hakone_ropeway import ANGLES


def plan(a):
    # The loop uses measured open water. The native rail engine supplies the
    # actual curves; the author checks those samples against the installed lake.
    points=[[-270,1086,'W'],[-306,1086,'W'],[-405,1120,'SW'],[-370,1190,'SE'],
            [-290,1275,'SSE'],[-285,1370,'S'],[-210,1490,'SSE'],[-160,1580,'SSE'],
            [-110,1720,'S'],[-100,1880,'SSE'],[50,2050,'SE'],[200,2200,'SE'],[335,2275,'S'],
            [363,2317,'NE'],[391,2289,'NE'],[403,2240,'N'],[350,2180,'NNW'],[330,2100,'NNE'],
            [400,2040,'NEE'],[476,2058,'NE'],[491,2043,'N'],[491,2015,'N'],[475,1980,'NW'],
            [400,2010,'W'],[200,1950,'NWW'],[10,1780,'NNW'],[-110,1590,'NNW'],
            [-185,1480,'NNW'],[-255,1370,'N'],[-260,1280,'N'],[-300,1180,'N'],
            [-250,1130,'NNE'],[-250,1098,'NWW'],[-270,1086,'W']]
    # Shared tangent corrections at wide open-water bends preserve continuous native curves.
    for index,az in {6:'SE',12:'S',16:'NW',18:'SEE',23:'SW',27:'NW',31:'NEE'}.items():points[index][2]=az
    platforms={0:'togendai-boat',13:'hakonemachi-boat',20:'motohakone-boat'}
    rails=[]
    for i,(p,q)in enumerate(zip(points,points[1:])):
        rails.append(dict(id=platforms.get(i,f'HA-{i}'),**{'from':[p[0],99,p[1]],'to':[q[0],99,q[1]]},
                          from_angle=p[2],to_angle=ANGLES[(ANGLES.index(q[2])+8)%16],mode='BOAT',
                          kind='platform'if i in platforms else'rail',speed=24,reverse_speed=24))
    rails.extend([dict(id='HA-siding',**{'from':[-231,99,1076],'to':[-251,99,1076]},from_angle='W',to_angle='E',kind='siding',mode='BOAT'),
                  dict(id='HA-lead',**{'from':[-251,99,1076],'to':[-270,99,1086]},from_angle='W',to_angle='E',kind='rail',mode='BOAT',speed=12)])
    stations=[dict(id=key,name=name,min=[x-30,96,z-30],max=[x+30,118,z+30],color=0x307B9E)
              for key,name,x,z in [('hakonemachi','箱根町港',389,2327),('motohakone','元箱根港',510,2029),('togendai_port','桃源台港',-286,1083)]]
    car=dict(id='dark_oak_boat_medium_two_level',length=5,width=2,bogie1=-1,bogie2=1,padding1=0,padding2=0)
    result=dict(stations=stations,rails=rails,lines=[dict(id='HA',name='芦之湖 桃源台—箱根町—元箱根',mode='BOAT',
            platforms=list(platforms.values())+['togendai-boat'],siding='HA-siding',cars=[car],frequency=8,repeat=True,dwell=12000)],
            warmup_seconds=1200,source='GSI water geometry; official three-port connection; OSM terminal locations cross-checked with GSI piers')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Prepared native three-port boat loop:',len(rails),'segments')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);plan(p.parse_args())
