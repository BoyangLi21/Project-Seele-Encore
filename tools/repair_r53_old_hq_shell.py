"""Retire measured old above-ground HQ components outside the migrated HQ."""
from pathlib import Path
from collections import deque,Counter
import argparse,json,numpy as np
import survey_r52_original_complex as survey
from survey_facility_target import role_of
from query_blocks import iter_block_entities
import regional_voxels as vox
from prepare_continuous_upright_civil_r52 import cuboids

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--world',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--complaint',type=str)
    parser.add_argument('--box',type=str,help='Measured extended R50 box: x0,y0,z0,x1,y1,z1')
    args=parser.parse_args();base=args.base;target=args.world or base/'CANDIDATE'
    source=base.parent/'map_complete_20261013'
    with np.load(source/'survey/headquarters_and_original_station.npz') as f:
        origin=f['origin'];old=f['states'];palette=f['palette'].tolist()
    with np.load(source/'pyramid_component/owner_mask.npz') as f:owned=f['owned']
    if args.box:
        bounds=tuple(map(int,args.box.split(',')));assert len(bounds)==6
        lo,hi=bounds[:3],bounds[3:]
        survey.WORLD=base/'R50_RESTORE/server/SEELE_R50_WORLD';old,palette=survey.measure(lo,hi)
        origin=np.asarray(lo)
        yy,zz,xx=np.ogrid[:old.shape[0],:old.shape[1],:old.shape[2]]
        y,z,x=yy+lo[1],zz+lo[2],xx+lo[0]
        def source_owner(y):
            radius=np.minimum(120,np.ceil((-292-y)*120/174))
            return np.broadcast_to((y>=-470)&(y<=-292)&(np.maximum(abs(x-30),abs(z-327))<=radius+1)&~((x>=126)&(x<=134)&(z>=269)&(z<=277)),old.shape)
        owned=source_owner(y).copy();active=source_owner(y+93).copy()
    else:
        active=np.zeros_like(owned);active[:-93]=owned[93:]
    lo=tuple(map(int,origin));hi=(lo[0]+old.shape[2]-1,lo[1]+old.shape[0]-1,lo[2]+old.shape[1]-1)
    survey.WORLD=base/'WORLD';frozen,frozen_names=survey.measure(lo,hi)
    survey.WORLD=target;current,names=survey.measure(lo,hi)
    lookup={n:i for i,n in enumerate(names)}
    old_to_now=np.asarray([lookup.get(n,65535) for n in palette],np.uint16)
    frozen_to_now=np.asarray([lookup.get(n,65535) for n in frozen_names],np.uint16)
    art=np.asarray([role_of(n) not in ('air','natural','fluid') and not n.startswith('mtr:')
                    and not n.startswith(('minecraft:rail[','minecraft:powered_rail[')) for n in palette])
    candidate=(current==old_to_now[old])&(current==frozen_to_now[frozen])&art[old]&~owned
    candidate &= ~active
    yy,zz,xx=np.ogrid[:old.shape[0],:old.shape[1],:old.shape[2]]
    y,z,x=yy+lo[1],zz+lo[2],xx+lo[0]
    candidate &= (y>=-466)
    candidate &= ~((x>=126)&(x<=134)&(z>=269)&(z<=277))
    devices=list(iter_block_entities(target,survey.DIM,lo,hi));derived=[]
    for pos,tag in devices:
        if str(tag['id'])=='projectseele:station_departure_board' and bool(tag.get('Wayfinding',0)):
            derived.append((pos,tag));continue
        px,py,pz=pos;ox,oy,oz=np.asarray(pos)-origin
        candidate[max(0,oy-6):oy+7,max(0,oz-6):oz+7,max(0,ox-6):ox+7]=False
    chosen=np.zeros_like(candidate);reports=[]
    points=[tuple(map(int,args.complaint.split(',')))] if args.complaint else [(153,-462,399),(114,-445,208),(137,-433,270)]
    for point in points:
        q=np.asarray(point)-origin;seed=(int(q[1]),int(q[2]),int(q[0]))
        if not candidate[seed]:raise RuntimeError(('Reported source not detected',point,names[int(current[seed])]))
        if chosen[seed]:continue
        queue=deque([seed]);chosen[seed]=True;cells=[];cropped=False
        while queue:
            q=queue.popleft();cells.append(q)
            for axis in range(3):
                for sign in (-1,1):
                    p=list(q);p[axis]+=sign
                    if not 0<=p[axis]<candidate.shape[axis]:cropped=True;continue
                    p=tuple(p)
                    if candidate[p] and not chosen[p]:chosen[p]=True;queue.append(p)
        a=np.asarray(cells);minimum=a.min(0);maximum=a.max(0)
        reports.append(dict(cells=len(cells),bounds=[[lo[0]+int(minimum[2]),lo[1]+int(minimum[0]),lo[2]+int(minimum[1])],
          [lo[0]+int(maximum[2]),lo[1]+int(maximum[0]),lo[2]+int(maximum[1])]],source_boundary_contact=cropped))
    retired_devices=[]
    for pos,tag in derived:
        ox,oy,oz=np.asarray(pos)-origin
        below=chosen[max(0,oy-5):oy+1,max(0,oz-2):oz+3,max(0,ox-2):ox+3]
        if chosen[oy,oz,ox] or below.any():chosen[oy,oz,ox]=True;retired_devices.append(dict(pos=list(pos),nbt=tag.snbt()))
    assert not any(chosen[p[1]-lo[1],p[2]-lo[2],p[0]-lo[0]] and not any(tuple(d['pos'])==p for d in retired_devices) for p,t in devices)
    out=base/'old-hq-shell-retirement'/target.name
    if args.complaint:out=out/('complaint_'+args.complaint.replace(',','_'))
    out.mkdir(parents=True,exist_ok=True)
    counts=Counter(names[int(k)] for k in current[chosen]);after=current.copy();after[chosen]=lookup['minecraft:air']
    report=dict(components=reports,cells=int(chosen.sum()),materials=dict(counts),retired_wayfinding=retired_devices,
                protected_migrated_hq=True,protected_original_surface_lift=True,complaints_detected_in_frozen_source=True)
    (out/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='retired_wayfinding'},ensure_ascii=False),flush=True)
    if args.apply:
        assert not any(r['source_boundary_contact'] for r in reports),'Resolve complete component boundary first'
        vox.WORLD=target;vox.DIM=survey.DIM;vox.OUT=out;painter=vox.Painter(vertical_bounds=(-1440,320))
        cuboids(painter,lo,current,after,names,'retired_original_above_ground_hq_shell')
        painter.meta.update(report)
        assert not list((out/'complete_original_components').glob('applied_*'))
        painter.apply('complete_original_components')
        actual,actual_names=survey.measure(lo,hi)
        remap=np.asarray([lookup.get(n,65535) for n in actual_names],np.uint16)
        assert np.array_equal(remap[actual],after)
        print('Complete retired HQ components applied and read back')

if __name__=='__main__':main()
