"""Measure a corridor-following north relocation without opening a live save."""
import argparse, gzip, json
from pathlib import Path
import numpy as np
from shapely.geometry import shape, box, LineString, mapping
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from author_kamonomiya_station import ALLOWED, OPEN
from author_itabashi_station import dump


def run(a):
    a.out.mkdir(exist_ok=False);e=Editor(a.source)
    features=json.loads(gzip.decompress(a.features.read_bytes()))['features'];rows=[]
    area=box(3360,290,3536,496)
    for i,f in enumerate(features):
        if f['properties'].get('source_layer')not in('RailCL','WA','RvrCL','WStrL'):continue
        g=shape(f['geometry'])
        if g.intersects(area):rows.append(dict(feature_index=i,properties=f['properties'],geometry=f['geometry']))
    dump(a.out/'nearby-reference.json',rows)
    jr=unary_union([shape(q['geometry'])for q in rows if q['properties'].get('source_layer')=='RailCL'and q['properties'].get('vt_rtcode')=='JR'])
    wet=unary_union([shape(q['geometry'])for q in rows if q['properties'].get('source_layer')in('WA','RvrCL','WStrL')])
    with np.load(a.source/'measured.npz')as f:x,z,X,Z=map(int,f['bounds']);ground=f['top']
    with np.load(a.authority/'network.npz')as f:ax,az,_,_=map(int,f['bounds']);old=f['walk']
    outlines=[dict(id='platform',bounds=[3448,-81,317,3453,-65,367]),
              dict(id='north bridge',bounds=[3450,-72,339,3512,-67,343]),
              dict(id='east stair',bounds=[3508,-81,344,3512,-65,362]),
              dict(id='east hall',bounds=[3501,-81,363,3519,-70,379])]
    results=[]
    for part in outlines:
        l,y,t,r,Y,b=part['bounds'];foot=box(l,t,r+1,b+1);public=[];foreign=[];g=[];unknown=[]
        for px in range(l,r+1):
            for pz in range(t,b+1):
                if not(x<=px<=X and z<=pz<=Z):unknown.append([px,pz]);continue
                if old[pz-az,px-ax]:public.append([px,pz])
                g.append(int(ground[pz-z,px-x]))
                for py in range(y,Y+1):
                    st=e.state(px,py,pz,True)
                    if st.split('[')[0]not in ALLOWED:foreign.append([px,py,pz,st])
        results.append(dict(**part,unknown_columns=unknown,old_public_columns=public,protected_cells=foreign,
                            ground_range=[min(g),max(g)]if g else None,
                            minimum_reference_jr_distance=foot.distance(jr),water_area_overlap=foot.intersection(wet).area,
                            bank_buffer_area_overlap=foot.intersection(wet.buffer(3)).area))
    bridge_axis=LineString([(3450,341.5),(3520,341.5)])
    crossings=[]
    for q in rows:
        if q['properties'].get('source_layer')=='RailCL'and q['properties'].get('vt_rtcode')=='JR':
            g=shape(q['geometry']).intersection(bridge_axis)
            if not g.is_empty:crossings.append(dict(feature_index=q['feature_index'],properties=q['properties'],geometry=mapping(g)))
    dump(a.out/'measurements.json',dict(original_station_centre=[3446.443,411.8685],candidate_centre=[3446.5,342.5],
         shift_distance=float(np.linalg.norm(np.array([3446.443,411.8685])-[3446.5,342.5])),parts=results,
         bridge_crossing_JR_references=crossings,world_written=False))
    for q in results:print(q['id'],'unknown',len(q['unknown_columns']),'public',len(q['old_public_columns']),'protected',len(q['protected_cells']),'ground',q['ground_range'],'JRdist',round(q['minimum_reference_jr_distance'],3),'bank area',round(q['bank_buffer_area_overlap'],3),flush=True)
    print('JR bridge reference crossings',[(q['feature_index'],q['geometry']['coordinates'])for q in crossings],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','authority','features','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
