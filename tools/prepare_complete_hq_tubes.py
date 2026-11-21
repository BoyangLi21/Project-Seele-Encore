"""Prepare complete independent MTR tube union, exact measured candidate only."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
from collections import defaultdict,Counter
import argparse,json,gzip,hashlib,math
import numpy as np
from scipy.spatial import cKDTree
from query_blocks import iter_selected_sections,chunk_statuses,iter_block_entities,AIR

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--world',type=Path,required=True);ap.add_argument('--candidate-directory',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--retiring-formation',type=Path);ap.add_argument('--native-records',type=Path);ap.add_argument('--hq-eaves',type=Path);a=ap.parse_args()
    if a.out.exists():raise ValueError('Fresh output directory required')
    a.out.mkdir(parents=True);read=lambda p:json.loads(p.read_text('utf-8'))
    samples=read(a.candidate_directory/'NATIVE_GEOMETRY.json');records=read(a.native_records or a.candidate_directory/'ORIGINAL_NATIVE_RECORDS.json')
    old={}
    with gzip.open(a.retiring_formation or a.candidate_directory/'COMPLETE_11_OLD_RAIL_FORMATION.jsonl.gz','rt',encoding='utf-8')as f:
        for line in f:
            r=json.loads(line);old[tuple(r['pos'])]=r
    own=np.load(a.world.parent/'hq_station_component/OWNERSHIP.npz');origin=own['origin'].copy();origin[1]-=93;hq=own['owned'];shape=np.array(hq.shape)[[2,0,1]]
    eaves={tuple(r['target'])for r in read(a.hq_eaves or a.candidate_directory/'HQ_COMPLETE_EAVES_MASK.json')}
    def hq_owned(q):
        if q in eaves:return True
        x,y,z=q[0]-origin[0],q[1]-origin[1],q[2]-origin[2]
        return bool(0<=x<shape[0]and 0<=y<shape[1]and 0<=z<shape[2]and hq[y,z,x])
    retained=[]
    for r in records['stations']:
        d=r['data']
        if d['id']==9166787716217601435 or d['position1']['y']>=0:continue
        lo=[d['position1'][k]for k in ['x','y','z']];hi=[d['position2'][k]for k in ['x','y','z']];lo[1]=min(-490,lo[1]);retained.append((r['member'],lo,hi))
    def protection(q):
        if hq_owned(q):return 'original_HQ_complete_owner'
        x,y,z=q
        if -166<=x<=-13 and -563<=y<=-554 and 517<=z<=532:return 'Root_applied_complete_U2_stock_staff_tunnel'
        if 324<=x<=332 and -490<=y<=-460 and 443<=z<=612:return 'original_science_east_corridor_complete_component'
        if 321<=x<=336 and y==-467 and any(abs(z-c)<=1 for c in (462,517,572)):return 'original_science_lab_thresholds'
        for name,lo,hi in retained:
            if all(lo[k]<=q[k]<=hi[k]for k in range(3)):return name
        return None
    # Union sections sampled from exact RailMath horizontal normals. Dense points
    # and lateral0.1m sampling include the whole bore, not only its centerline.
    roles={};owners=defaultdict(set);protected=defaultdict(set);floor_distance={};lights=set()
    for r in samples:
        if r['id'].startswith('platform_')or r['id']in ['u2_original_siding_translation','u2_siding_hq_original_throat']:continue
        p=np.array(r['points']);delta=np.gradient(p[:,[0,2]],axis=0);norm=np.linalg.norm(delta,axis=1);assert np.all(norm>0)
        normal=np.column_stack((-delta[:,1],delta[:,0]))/norm[:,None]
        for width,role,ys in [(4.13,'lining',range(-2,8)),(3.13,'bore',range(0,7))]:
            sides=np.arange(-width,width+.01,.1);q=np.repeat(p[:,None,:],len(sides),axis=1)
            q[:,:,[0,2]]+=normal[:,None,:]*sides[None,:,None]
            columns=np.unique(np.floor(q).astype(int).reshape(-1,3),axis=0)
            for x,y,z in columns:
                for dy in ys:
                    t=int(x),int(y+dy),int(z);hold=protection(t)
                    if hold:protected[hold].add(t);continue
                    if roles.get(t)!='bore':roles[t]=role
                    owners[t].add(r['id'])
        # Preserve a complete, continuous ballast floor beneath each native axis.
        sides=np.arange(-2.15,2.16,.1);q=np.repeat(p[:,None,:],len(sides),axis=1);q[:,:,[0,2]]+=normal[:,None,:]*sides[None,:,None]
        for x,y,z in np.unique(np.floor(q).astype(int).reshape(-1,3),axis=0):
            t=int(x),int(y-1),int(z)
            if t in roles and roles[t]!='bore':floor_distance[t]=True
        step=max(1,round(16/.25))
        for v in p[step//2::step]:
            x,y,z=np.floor(v).astype(int);lights.add((int(x),int(y+7),int(z)))
        print(r['id'],len(roles),flush=True)
    # Three original rail chains/platforms lie within preserved station and U2
    # component domains, hence their protected terminal spaces remain unchanged.
    selected=defaultdict(set);bysection=defaultdict(list);points=sorted(roles)
    for i,(x,y,z)in enumerate(points):selected[x//16,z//16].add(y//16);bysection[x//16,z//16,y//16].append(i)
    status=chunk_statuses(a.world,'projectseele:geofront',selected);assert set(status.values())=={'full'}
    states=['minecraft:air'];sid={states[0]:0};before=np.zeros(len(points),np.int32)
    for x,z,y,pal,idx in iter_selected_sections(a.world,'projectseele:geofront',selected):
        mapping=[]
        for s in pal:
            if s not in sid:sid[s]=len(states);states.append(s)
            mapping.append(sid[s])
        for i in bysection[x,z,y]:
            xx,yy,zz=points[i];before[i]=mapping[int(idx[((yy&15)<<8)|((zz&15)<<4)|(xx&15)])]
    low=tuple(min(q[k]for q in points)for k in range(3));high=tuple(max(q[k]for q in points)for k in range(3));bes=dict(iter_block_entities(a.world,'projectseele:geofront',low,high,selected_chunks=set(selected)))
    ground=AIR|{'minecraft:stone','minecraft:deepslate','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:clay','minecraft:water','minecraft:coarse_dirt','minecraft:tuff','minecraft:andesite','minecraft:diorite','minecraft:granite','minecraft:grass','minecraft:fern','minecraft:tall_grass','minecraft:seagrass','minecraft:light'}
    rows=[];held=[];counts=Counter()
    for i,q in enumerate(points):
        s=states[int(before[i])];base=s.partition('[')[0];o=old.get(q);why=None
        if q in bes:why='BLOCK_ENTITY_UNDER_PROPOSED_TUBE'
        elif base.endswith(('_log','_leaves')):why='COMPLETE_TREE_TRANSLATION_REQUIRED'
        elif base not in ground:
            if not(o and o['state']==s and o['status']=='EXACT_RETIRING_SOURCE_FORMATION'):why='UNKNOWN_OR_RETAINED_AUTHORED_STRUCTURE'
        target='minecraft:air'if roles[q]=='bore'else'minecraft:gravel'if q in floor_distance else'projectseele:nerv_strip_light[lit=true]'if q in lights else'projectseele:nerv_wall_panel'
        row=dict(pos=list(q),before=s,after=target,role=roles[q],curves=sorted(owners[q]),before_nbt=None if q not in bes else bes[q].snbt(),after_nbt=None,owner='complete_independent_HQ_MTR_tube')
        if why:row['hold']=why;held.append(row);counts[why]+=1
        else:rows.append(row)
    with gzip.open(a.out/'COMPLETE_ADMITTED_SOURCE_TARGET.jsonl.gz','wt',encoding='utf-8')as f:
        for r in rows:f.write(json.dumps(r)+'\n')
    with gzip.open(a.out/'EXACT_ADMITTED_CHANGES.jsonl.gz','wt',encoding='utf-8')as f:
        for r in rows:
            if r['before']!=r['after']:f.write(json.dumps(r)+'\n')
    with gzip.open(a.out/'EXACT_ADMITTED_INVERSE.jsonl.gz','wt',encoding='utf-8')as f:
        for r in reversed(rows):
            if r['before']!=r['after']:f.write(json.dumps(dict(r,before=r['after'],after=r['before']))+'\n')
    (a.out/'HOLDS.json').write_text(json.dumps(held,ensure_ascii=False,indent=2)+'\n','utf-8')
    report=dict(world_written=False,candidate_sha256=hashlib.sha256((a.candidate_directory/'CANDIDATE.json').read_bytes()).hexdigest(),native_geometry_sha256=hashlib.sha256((a.candidate_directory/'NATIVE_GEOMETRY.json').read_bytes()).hexdigest(),total_tube_cells=len(points),admitted_source_cells=len(rows),admitted_changes=sum(r['before']!=r['after']for r in rows),holds=len(held),holds_by_type=dict(counts),protected_counts={k:len(v)for k,v in protected.items()},retained_station_domains=[dict(member=n,lo=l,hi=h)for n,l,h in retained],geometric_contract='Pinned MTR native RailMath <=.253m samples, horizontal normal, radius3 clear7 high andradius4 structural[-2,+7]; extra.13m lateral conservative margin. All bores union before any lining, original fullHQ owner and original station domains protected. U2 siding/throat have separate full staff-tunnel candidate.',installation_ready=not held,limits=['Holds make this candidate incomplete; do not install a partial tunnel and claim completion.','Protected station-domain passages require full-car collision checking, protection does not prove clearance.','Complete original rail formation retirement and exterior terrain/lake restoration are separate receipts.'])
    (a.out/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8');print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
