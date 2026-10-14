"""Root bank-three civil envelope from all three actual full assemblies.

Foot platform yaw and relative two-foot-axis pitch are separate mechanisms.
No world writes. Prior rejected rectangular-envelope evidence is retained.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import gzip,struct,json,hashlib,math,argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.spatial import ConvexHull
from query_blocks import iter_selected_sections,chunk_statuses
from r52_spatial_plan import BASE

ROOT=Path(__file__).resolve().parents[1];OUT=BASE/'bank3_outlet_v2';WORLD=BASE/'WORLD_R52'
SOLES={0:.224014043808,1:.223975896835,2:.183567047119}


def cloud(variant):
    path=ROOT/f'.Codex/r52_launch_cloud/unit{variant}_full_parts.bin.gz';raw=gzip.decompress(path.read_bytes());at=0
    def integer():
        nonlocal at
        v=struct.unpack_from('>i',raw,at)[0];at+=4;return v
    def utf():
        nonlocal at
        n=struct.unpack_from('>H',raw,at)[0];at+=2;s=raw[at:at+n].decode();at+=n;return s
    assert integer()==0x52353243 and integer()==variant;parts=[]
    for i in range(integer()):
        name= utf();source=utf();n=integer();points=np.frombuffer(raw,dtype='>f4',count=n*3,offset=at).astype(float).reshape(-1,3);at+=n*12
        parts.append(points)
    assert at==len(raw)
    points=np.concatenate(parts);h=ConvexHull(points);return points[h.vertices]-[0,0,SOLES[variant]],hashlib.sha256(path.read_bytes()).hexdigest()


def rotation(yaw,pitch):
    c,s=math.cos(yaw),math.sin(yaw);C,S=math.cos(pitch),math.sin(pitch)
    return np.array([[c,0,s],[0,1,0],[-s,0,c]])@np.array([[1,0,0],[0,C,-S],[0,S,C]])@np.diag([-1.,1.,-1.])


def part(name,lane,kind,points):
    h=ConvexHull(points);v=points[h.vertices];eq=h.equations
    # Keep source quantization error + at least 1m engineering clearance.
    return dict(id=name,lane=lane,kind=kind,equations=eq,bounds=[v.min(0)-3.1,v.max(0)+3.1])


def contains(p,xyz,lining=0):
    eq=p['equations'];normal=eq[:,:3];off=eq[:,3]
    # Support-function bound includes full voxel cube and 1.01m clearance.
    limits=-off+1.01+.5*np.abs(normal).sum(1)+lining
    result=np.ones(len(xyz),bool)
    for start in range(0,len(eq),20):
        active=np.flatnonzero(result)
        if not len(active):break
        result[active]&=np.all(xyz[active]@normal[start:start+20].T<=limits[start:start+20],axis=1)
    return result


def design(layout='near'):
    parts=[];routes=[]
    for lane,x in enumerate((-11.5,30.5,72.5)):
        variant=2-lane;local,source=cloud(variant);sole=SOLES[variant]
        if layout=='final':
            roots=np.array([[x,-646.,-781.5],[x,-556.,-781.5],[x-1200.,-516.,1150.5],[x-1200.,72.,1150.5]])
        elif layout=='parallel':
            # All three launch rails have the SAME direction and height.
            # Avoid the converging fan that overlapped along the long bore.
            roots=np.array([[x,-646.,-448.5],[x,-556.,-448.5],[x-1200.,-516.,1150.5],[x-1200.,105.,1150.5]])
        elif layout=='terrace':
            roots=np.array([[x,-646.,-448.5],[x,-562.+10*lane,-448.5],[-1774.5,-536.+24*lane,1380.5+38*lane],[-1774.5,(115.,108.,104.)[lane],1380.5+38*lane]])
        elif layout=='far':
            # At the rural south edge of Hakone the three tracks can stay
            # parallel and clear the retained bank observation galleries.
            roots=np.array([[x,-646.,-448.5],[x,-576.+10*lane,-448.5],[-1741.5+42*lane,-536.+10*lane,1450.5],[-1741.5+42*lane,105.,1450.5]])
        else:
            roots=np.array([[x,-646.,-448.5],[x,-636.+42*lane,-448.5],[-1919.5,-580.+30*lane,570.5+48*lane],[-1919.5,105.,570.5+48*lane]])
        feet=roots-[0,0,sole];bank,start,end,surface=feet;d=end-start;length=np.linalg.norm(d);yaw=math.atan2(d[0],d[2]);pitch=math.acos(d[1]/length)
        upright=local@rotation(0,0).T;tilted=local@rotation(yaw,pitch).T
        parts.append(part(f'lane{lane}_initial_vertical',lane,'vertical',np.concatenate([upright+bank,upright+start])))
        swept=np.concatenate([local@rotation(yaw*t,pitch*t).T for t in np.linspace(0,1,361)])
        parts.append(part(f'lane{lane}_bearing_in',lane,'bearing',swept+start))
        parts.append(part(f'lane{lane}_incline',lane,'incline',np.concatenate([tilted+start,tilted+end])))
        parts.append(part(f'lane{lane}_bearing_out',lane,'bearing',swept+end))
        parts.append(part(f'lane{lane}_surface_vertical',lane,'vertical',np.concatenate([upright+end,upright+surface])))
        routes.append(dict(lane=lane,variant=variant,body_roots=roots.tolist(),foot_nodes=feet.tolist(),source_sha256=source,
                           platform_yaw_degrees=math.degrees(yaw),relative_pitch_degrees=math.degrees(pitch),incline_metres=length,
                           bearing_motion='yawed whole support frame plus relative pitch about original two-foot axis; reverse at exit',
                           actual_sole_z=sole))
    return parts,routes


def main():
    global OUT
    ap=argparse.ArgumentParser();ap.add_argument('--layout',choices=('near','far','terrace','parallel','final'),default='near');args=ap.parse_args()
    if args.layout=='far':OUT=BASE/'bank3_outlet_v3'
    if args.layout=='terrace':OUT=BASE/'bank3_outlet_v4'
    if args.layout=='parallel':OUT=BASE/'bank3_outlet_parallel'
    if args.layout=='final':OUT=BASE/'bank3_outlet_final'
    OUT.mkdir(exist_ok=True);parts,routes=design(args.layout);selected=defaultdict(set);members=defaultdict(list)
    for i,p in enumerate(parts):
        low,high=(np.floor(v/16).astype(int)for v in p['bounds'])
        for cx in range(low[0],high[0]+1):
            for cz in range(low[2],high[2]+1):
                for sy in range(low[1],high[1]+1):
                    centre=np.array([cx*16+8,sy*16+8,cz*16+8]);eq=p['equations']
                    if not np.all(eq[:,:3]@centre+eq[:,3]<=3.1+8*np.abs(eq[:,:3]).sum(1)):continue
                    selected[cx,cz].add(sy);members[cx,cz,sy].append(i)
    states=chunk_statuses(WORLD,'projectseele:geofront',selected);missing={str(k):v for k,v in states.items()if v!='full'}
    if missing:
        (OUT/'NATIVE_GENERATION_REQUIRED.json').write_text(json.dumps(dict(world_written=False,missing=missing,all_selected_chunks=[list(k)for k in selected],routes=routes),indent=2),'utf8')
        selected={k:v for k,v in selected.items()if states[k]=='full'}
    local=np.array([[x+.5,y+.5,z+.5]for y in range(16)for z in range(16)for x in range(16)])
    palette=['minecraft:air'];ids={palette[0]:0};records=[];counts=defaultdict(int);ranges={};overlap=0
    for cx,cz,sy,names,old in iter_selected_sections(WORLD,'projectseele:geofront',selected):
        idx=members.get((cx,cz,sy),[])
        if not idx:continue
        xyz=local+[cx*16,sy*16,cz*16];core=np.zeros(4096,bool);shell=core.copy();lanes=np.zeros(4096,np.uint8)
        for k in idx:
            hit=contains(parts[k],xyz);core|=hit;shell|=contains(parts[k],xyz,2);lanes[hit]|=1<<parts[k]['lane']
        if not shell.any():continue
        overlap+=int(np.count_nonzero((lanes!=0)&((lanes&(lanes-1))!=0)))
        for state in names:
            if state not in ids:ids[state]=len(palette);palette.append(state)
        values=np.array([ids[s]for s in names],np.uint16)[old]
        for value in np.unique(values[shell]):
            state=palette[int(value)]
            if not state.startswith(('projectseele:','mtr:','minecraft:barrier')):continue
            match=xyz[shell&(values==value)];counts[state]+=len(match)
            lo=match.min(0);hi=match.max(0)
            if state in ranges:lo=np.minimum(lo,ranges[state][0]);hi=np.maximum(hi,ranges[state][1])
            ranges[state]=[lo.tolist(),hi.tolist()]
        records.append((cx,cz,sy,values,core,shell,lanes))
    np.savez_compressed(OUT/'SECTION_SOURCE.npz',section_keys=np.array([r[:3]for r in records],np.int32),before=np.array([r[3]for r in records],np.uint16),core=np.array([r[4]for r in records]),shell=np.array([r[5]for r in records]),lanes=np.array([r[6]for r in records]),palette=palette)
    report=dict(world_written=False,playable=False,source_measurement_complete=not missing,missing_chunks=len(missing),routes=routes,sections=len(records),core_cells=int(sum(r[4].sum()for r in records)),outer_cells=int(sum(r[5].sum()for r in records)),overlapping_lane_cells=overlap,nonnatural_counts=counts,nonnatural_ranges=ranges,
                basis='Per-variant original full assembly convex envelope, source geometric fidelity unchanged; no entity proxy boxes or ignored physical collisions',native_full_triangle_acceptance_pending=True)
    (OUT/'DESIGN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items()if k not in ('routes','nonnatural_ranges')}),flush=True)


if __name__=='__main__':main()
