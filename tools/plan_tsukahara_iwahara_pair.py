"""Measured, offline alternatives for two close diagonal Daiyuzan stations."""
import argparse,gzip,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import shape,Point,LineString,Polygon,box,mapping
from shapely.ops import unary_union
from map_pipeline.station_sections import StationSections
from plan_ashi_landscape_r54 import SOIL,NATURAL

def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def main(a):
    a.out.mkdir(exist_ok=False)
    source=StationSections(a.source);features=json.loads(gzip.decompress((a.features/'features.world.geojson.gz').read_bytes()))['features']
    stations=[]
    for name,c,y in [('塚原駅',[2715.5,-756.5],-74),('岩原駅',[2766.5,-685.5],-75)]:
        site=next(s for s in source.report['sites']if s['name']==name)
        near=[]
        for i,f in enumerate(features):
            if f['properties'].get('source_layer')not in('RailCL','WA','RvrCL','WStrL','RdCL','BldA'):continue
            geom=shape(f['geometry'])
            if geom.distance(Point(c))<100:near.append(dict(index=i,properties=f['properties'],geometry=f['geometry']))
        stations.append(dict(name=name,c=c,y=y,site=site,nearby_gis=near))
    variants=[];segments=[]
    for variant,half in [('diagonal_34m',[12,12]),('diagonal_48m',[17,17]),('reference_curve_49m',[14,20]),('diagonal_34m_flat_long',[12,12]),('diagonal_34m_flat_iwa_shift2',[12,12]),('diagonal_34m_flat_iwa_shift3',[12,12]),('diagonal_flat_iwa_28m',[12,12])]:
        rail=[]
        for i,s in enumerate(stations):
            cx,cz=s['c'];dx,dz=half
            if i==1 and 'iwa_shift'in variant:
                shift=int(variant[-1]);cx-=shift;cz-=shift
            if i==1 and variant=='diagonal_flat_iwa_28m':dx=dz=10
            flat='flat'in variant
            elevation=-74 if flat else s['y']
            fr=[int(cx-.5-dx),elevation,int(cz-.5-dz)];to=[int(cx-.5+dx),elevation,int(cz-.5+dz)]
            row=dict(id=variant+'_platform_'+str(i),**{'from':fr,'to':to},from_angle='SE',to_angle='NW',shape='QUADRATIC',vertical_radius=100)
            rail.append(row);segments.append(row)
        segment=dict(id=variant+'_between',**{'from':rail[0]['to'],'to':rail[1]['from']},from_angle='SE',to_angle='NW',shape='QUADRATIC',vertical_radius=100)
        segments.append(segment)
        north=dict(id=variant+'_north_transition',**{'from':[2697,-74,-815]if flat else[2698,-74,-792],'to':rail[0]['from']},from_angle='S',to_angle='NW',shape='QUADRATIC',vertical_radius=100)
        south=dict(id=variant+'_south_transition',**{'from':rail[1]['to'],'to':[2795,-74 if flat else-76,-644]},from_angle='SE',to_angle='NW',shape='QUADRATIC',vertical_radius=100)
        segments.extend([north,south]);variants.append(dict(id=variant,platform_ids=[r['id']for r in rail],link_id=segment['id'],transition_ids=[north['id'],south['id']]))
    write(a.out/'native-input.json',dict(segments=segments,geometry_only=True,Simulator_started=False))
    with np.load(a.authority/'network.npz')as f:
        x0,z0,*_=map(int,f['bounds']);public=f['walk'];grade=f['grade2'];ground=f['ground']
        for s in stations:
            x,y,z,X,Y,Z=s['site']['bounds'];near=public[z-z0:Z-z0+1,x-x0:X-x0+1];targets=[]
            for iz,ix in np.argwhere(near):
                px,pz=int(ix+x),int(iz+z);g=int(grade[pz-z0,px-x0]);floor=(g+1)//2
                state=source.state(px,floor,pz);body=[source.state(px,h,pz)for h in range(floor+1,floor+4)]
                if any(v not in('minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light')for v in body):continue
                targets.append(dict(xyz=[px+.5,g/2+1,pz+.5],floor_state=state,grade2=g,distance=round(math.hypot(px+.5-s['c'][0],pz+.5-s['c'][1]),3)))
            targets.sort(key=lambda r:r['distance']);selected=[]
            for t in targets:
                if all(math.hypot(t['xyz'][0]-v['xyz'][0],t['xyz'][2]-v['xyz'][2])>=6 for v in selected):selected.append(t)
                if len(selected)==18:break
            s['measured_public_targets']=selected
    write(a.out/'site-evidence.json',dict(stations=stations,variants=variants,source=str(a.source),authority=str(a.authority),features=str(a.features),world_opened=False,world_written=False))
    for s in stations:print(s['name'],'GIS',len(s['nearby_gis']),'paved targets',len(s['measured_public_targets']),str(s['measured_public_targets'][:1])[:300],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','features','out'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
