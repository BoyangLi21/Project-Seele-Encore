"""Root reads actual native-curve tunnel cells before any civil write.

Cross sections follow MTR RailAction: a horizontal normal at each actual rail
sample, then vertical clearance. The complete moved station is protected.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json,hashlib
from pathlib import Path
import numpy as np
from query_blocks import iter_selected_sections,iter_block_entities,chunk_statuses
from r52_spatial_plan import BASE

ROOT=Path(__file__).resolve().parents[1]


def station(p):
    x,y,z=p
    return (-12<=x<=72 and 475<=z<=537 and -583<=y<=-548) or (24<=x<=36 and 447<=z<=474 and -563<=y<=-548)


def main():
    out=BASE/'hq_tunnels';out.mkdir(exist_ok=True)
    sample_path=ROOT/'artifacts/r52_hq_approach_candidate/NATIVE_TUNNEL_SAMPLES.json'
    samples=json.loads(sample_path.read_text('utf8'))
    retained=json.loads((ROOT/'artifacts/r52_hq_rail_boundary/HQ_PROTECTION_MANIFEST.json').read_text('utf8'))['protected_stations']
    preserved=[]
    for row in retained:
        d=row['data'];a=d['position1'];b=d['position2']
        if a['y']<0:preserved.append((d['name'],(a['x'],min(a['y'],-490),a['z'],b['x'],b['y'],b['z'])))
    def retained_station(p):
        x,y,z=p
        return next((name for name,(a,b,c,A,B,C)in preserved if a<=x<=A and b<=y<=B and c<=z<=C),None)
    retained_boundary_contacts={}
    by_chunk={};roles={};owners={}
    # Union all bore interiors first; adjoining authored branches may share a
    # junction chamber, so a later wall must never refill an earlier bore.
    for row in samples:
        if row['id'].startswith('platform_'):continue
        a=np.asarray(row['points']);delta=np.diff(a[:,[0,2]],axis=0);delta=np.vstack([delta,delta[-1]])
        norm=np.linalg.norm(delta,axis=1);assert np.all(norm>0)
        lateral=np.column_stack([-delta[:,1],delta[:,0]])/norm[:,None]
        for width,role in ((3,'bore'),(4,'envelope')):
            for side in np.arange(-width,width+.05,.1):
                q=a.copy();q[:,0]+=lateral[:,0]*side;q[:,2]+=lateral[:,1]*side
                columns=np.unique(np.floor(q).astype(np.int32),axis=0)
                for x,y,z in columns:
                    for dy in (range(0,7)if role=='bore'else range(-2,8)):
                        p=(int(x),int(y+dy),int(z))
                        if station(p):continue
                        retained_name=retained_station(p)
                        if retained_name:
                            retained_boundary_contacts.setdefault(retained_name,set()).add(row['id'])
                            continue
                        previous=roles.get(p)
                        if previous!='bore':roles[p]=role
                        owners.setdefault(p,set()).add(row['id'])
    points=sorted(roles);selected={}
    for x,y,z in points:selected.setdefault((x//16,z//16),set()).add(y//16)
    world=BASE/'WORLD_R52';status=chunk_statuses(world,'projectseele:geofront',selected)
    assert set(status.values())=={'full'},'Unfinished native chunk in exact railway corridor'
    sections={}
    for i,(x,y,z)in enumerate(points):sections.setdefault((x//16,z//16,y//16),[]).append(i)
    names=['minecraft:air'];ids={names[0]:0};values=np.zeros(len(points),np.uint16)
    for cx,cz,sy,palette,indices in iter_selected_sections(world,'projectseele:geofront',selected):
        mapping=[]
        for s in palette:
            if s not in ids:ids[s]=len(names);names.append(s)
            mapping.append(ids[s])
        for i in sections.get((cx,cz,sy),[]):
            x,y,z=points[i];values[i]=mapping[int(indices[(y%16)*256+(z%16)*16+x%16])]
    natural={'minecraft:air','minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]',
             'minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:gravel','minecraft:water[level=0]'}
    conflicts=[];counts={}
    for i,p in enumerate(points):
        s=names[int(values[i])]
        if s not in natural:
            counts[s]=counts.get(s,0)+1
            if len(conflicts)<300:conflicts.append(dict(pos=p,state=s,role=roles[p],segments=sorted(owners[p])))
    report=dict(world_written=False,exact_cells=len(points),chunks=len(selected),source='actual MTR RailMath samples at <=0.1m',
        sample_sha256=hashlib.sha256(sample_path.read_bytes()).hexdigest(),
        retained_station_boundary_contacts={k:sorted(v)for k,v in retained_boundary_contacts.items()},
        protected_complete_original_station=True,nonnatural_count=sum(counts.values()),nonnatural_states=counts,
        first_nonnatural_cells=conflicts,not_clearance_or_construction_acceptance=True)
    np.savez_compressed(out/'CORRIDOR_SOURCE.npz',points=np.asarray(points,np.int32),before=values,palette=names,
                        bore=np.asarray([roles[p]=='bore'for p in points],bool))
    (out/'MEASUREMENT.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='first_nonnatural_cells'}),flush=True)


if __name__=='__main__':main()
