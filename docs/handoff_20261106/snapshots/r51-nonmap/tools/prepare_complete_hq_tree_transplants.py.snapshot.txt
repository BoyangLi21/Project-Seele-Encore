"""Whole measured tree components displaced by explicit HQ railway tubes; candidate only."""
from pathlib import Path
from collections import Counter
import argparse,json,gzip,hashlib
import numpy as np
from scipy.ndimage import label,generate_binary_structure
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--world',type=Path,required=True);ap.add_argument('--tubes',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    if a.out.exists():raise ValueError('Fresh output required')
    a.out.mkdir(parents=True);survey.WORLD=a.world
    holds=json.loads((a.tubes/'HOLDS.json').read_text('utf-8'));seeds=np.array([r['pos']for r in holds if r['hold']=='COMPLETE_TREE_TRANSLATION_REQUIRED'])
    lo=seeds.min(0)-[24,24,24];hi=seeds.max(0)+[24,24,24];s,pal=survey.measure(tuple(lo),tuple(hi));tree_ids=[i for i,n in enumerate(pal)if n.partition('[')[0].endswith(('_log','_leaves'))];vegetation=np.isin(s,tree_ids);components,n=label(vegetation,generate_binary_structure(3,1));ijk=(seeds-lo)[:,[1,2,0]];wanted=np.unique(components[tuple(ijk.T)]);assert 0 not in wanted
    trees=[];source_cells=set();source_changes=[];fragments=[]
    for c in wanted:
        q=np.argwhere(components==c);assert not np.any((q==0)|(q==np.array(s.shape)-1)),'Incomplete bounded tree component'
        ps=q[:,[2,0,1]]+lo;values=s[tuple(q.T)];names=np.array([pal[int(v)]for v in values]);logs=np.array([n.partition('[')[0].endswith('_log')for n in names])
        if not logs.any():
            fragments.append(dict(component=int(c),cells=len(ps),logs=0,source_bounds=[ps.min(0).tolist(),ps.max(0).tolist()],decision='Root authorized whole pre-existing rootless canopy retirement; no partial leaf pruning or historical vegetation revival'))
            for p,state in zip(ps,names):source_cells.add(tuple(map(int,p)));source_changes.append(dict(pos=p.tolist(),before=str(state),after='minecraft:air',owner='complete_preexisting_rootless_canopy_retirement',before_nbt=None,after_nbt=None))
            continue
        logset={tuple(map(int,p))for p in ps[logs]};roots=np.array([p for p in ps[logs]if tuple(map(int,p-[0,1,0]))not in logset]);bearings=[]
        for root in roots:
            b=root-[0,1,0];ix=(b-lo)[[1,2,0]];state=pal[int(s[tuple(ix)])];bearings.append(dict(pos=b.tolist(),state=state))
            assert state.partition('[')[0]in ['minecraft:grass_block','minecraft:dirt','minecraft:coarse_dirt','minecraft:podzol','minecraft:rooted_dirt'],('Tree root has authored/unknown bearing',c,root.tolist(),state)
        assert int(logs.sum())>=5 and len(ps)>=150,('Historical partial tree needs Root whole-fragment disposition',int(c),int(logs.sum()),len(ps))
        for p,state in zip(ps,names):source_cells.add(tuple(map(int,p)));source_changes.append(dict(pos=p.tolist(),before=str(state),after='minecraft:air',owner='complete_original_tree_transplant_source',before_nbt=None,after_nbt=None))
        trees.append(dict(component=int(c),positions=ps,states=names,roots=roots,source_bearings=bearings))
    source_be=[(p,t)for p,t in iter_block_entities(a.world,'projectseele:geofront',tuple(lo),tuple(hi))if p in source_cells];assert not source_be
    # Explicit outdoor meadow search away from new lake/HQ/labs. Every target
    # tree voxel must already be air; every root bears on existing native soil.
    dlo=np.array([520,-500,240]);dhi=np.array([920,-400,640]);dst,dp=survey.measure(tuple(dlo),tuple(dhi));air=np.array([n=='minecraft:air'for n in dp]);soil=np.array([n.partition('[')[0]in ['minecraft:grass_block','minecraft:dirt','minecraft:coarse_dirt','minecraft:podzol','minecraft:rooted_dirt']for n in dp]);ground=np.max(np.where(soil[dst],np.arange(dst.shape[0])[:,None,None]+dlo[1],-9999),axis=0)
    occupied=np.zeros(dst.shape[1:],bool);changes=list(source_changes);report=[];rng=np.random.default_rng(53101364);candidates=[(x+int(rng.integers(-3,4)),z+int(rng.integers(-3,4)))for z in range(260,621,14)for x in range(540,901,14)];rng.shuffle(candidates)
    for tree in trees:
        ps=tree['positions'];anchor=tree['roots'][0];placed=False
        for x,z in candidates:
            y=int(ground[z-dlo[2],x-dlo[0]])+1
            if y<-490:continue
            shift=np.array([x,y,z])-anchor;target=ps+shift;L=target.min(0);H=target.max(0)
            if np.any(L<dlo)or np.any(H>dhi):continue
            left,bottom=L[[0,2]]-dlo[[0,2]]-3;right,top=H[[0,2]]-dlo[[0,2]]+4
            if left<0 or bottom<0 or right>occupied.shape[1]or top>occupied.shape[0]or occupied[bottom:top,left:right].any():continue
            ii=(target-dlo)[:,[1,2,0]]
            if not air[dst[tuple(ii.T)]].all():continue
            rb=tree['roots']+shift-[0,1,0];ri=(rb-dlo)[:,[1,2,0]]
            if not soil[dst[tuple(ri.T)]].all():continue
            # A three-cell soil bearing below each root excludes grass floating
            # above air or a building roof falsely labelled as forest ground.
            supported=True
            for b in rb:
                for depth in [1,2]:
                    t=b-[0,depth,0];j=(t-dlo)[[1,2,0]];name=dp[int(dst[tuple(j)])].partition('[')[0]
                    if name not in ['minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt','minecraft:podzol','minecraft:rooted_dirt']:supported=False
            if not supported:continue
            for p,state in zip(target,tree['states']):changes.append(dict(pos=p.tolist(),before='minecraft:air',after=str(state),owner='complete_original_tree_transplant_target',before_nbt=None,after_nbt=None))
            occupied[bottom:top,left:right]=True;placed=True;report.append(dict(component=tree['component'],cells=len(ps),logs=sum(n.partition('[')[0].endswith('_log')for n in tree['states']),offset=shift.tolist(),source_bounds=[ps.min(0).tolist(),ps.max(0).tolist()],target_bounds=[L.tolist(),H.tolist()],source_bearings=tree['source_bearings'],target_root_bearings=rb.tolist()));break
        assert placed,('No complete air-and-soil meadow placement',tree['component'])
    targets={tuple(r['pos'])for r in changes if r['owner'].endswith('_target')};assert not any(p in targets for p,t in iter_block_entities(a.world,'projectseele:geofront',tuple(dlo),tuple(dhi)))
    for n,rows in [('EXACT_CHANGES.jsonl.gz',changes),('EXACT_INVERSE.jsonl.gz',[dict(r,before=r['after'],after=r['before'])for r in reversed(changes)])]:
        with gzip.open(a.out/n,'wt',encoding='utf-8')as f:
            for r in rows:f.write(json.dumps(r)+'\n')
    info=dict(world_written=False,source_tube_holds_sha256=hashlib.sha256((a.tubes/'HOLDS.json').read_bytes()).hexdigest(),root_authorization='Whole-tree translation only; no cutting leaves/stumps; current explicit HQ new railway component',components=report,rootless_fragments_retired_whole=fragments,complete_source_tree_cells=len(source_changes),exact_source_plus_target_cells=len(changes),source_block_entities=0,target_block_entities=0,source_survey=[lo.tolist(),hi.tolist()],target_survey=[dlo.tolist(),dhi.tolist()],limits=['Tree target voxels are exact current air and rooted on existing three-cell native soil; final combined tube/lake/terrain candidate still must certify no changed target reuse.','No terrain flattening, no generated replacement trees, no foliage state or component shape changes.'])
    (a.out/'REPORT.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n','utf-8');print(json.dumps({'trees':len(report),'source_cells':len(source_changes),'changes':len(changes),'world_written':False}))

if __name__=='__main__':main()
