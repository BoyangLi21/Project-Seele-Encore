"""Complete saved R50 Heightmap region seams and attach finite owner context.

Reads only existing audit NPZ/JSON files. It never opens or writes a world.
Screened columns are evidence for classification, not a terrain quality pass.
"""
from pathlib import Path
from collections import Counter
import argparse,json
import numpy as np
from scipy import ndimage

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/surface_r50/global_heightmaps');args=ap.parse_args()
    out=args.out.resolve();report=json.loads((out/'global_screen.json').read_text('utf8'))
    maps={}
    for p in out.glob('r.*.*.npz'):
        rx,rz=map(int,p.stem.split('.')[1:]);d=np.load(p)
        maps[rx,rz]={k:d[k]for k in ('height','known','ocean_floor')}
    # Discard only a previous seam-screen output, leaving the original local IDs stable.
    objects=[o for o in report['objects']if not o['id'].startswith('heightmap/seam/')]
    pairs=[];positive=0
    for (rx,rz),a in sorted(maps.items()):
        positive+=int(np.count_nonzero(a['known']&(a['height']>=0)))
        for direction,delta in [('east',(1,0)),('south',(0,1))]:
            b=maps.get((rx+delta[0],rz+delta[1]))
            if b is None:continue
            if direction=='east':ha,hb=a['height'][:,-1],b['height'][:,0];ka,kb=a['known'][:,-1],b['known'][:,0]
            else:ha,hb=a['height'][-1,:],b['height'][0,:];ka,kb=a['known'][-1,:],b['known'][0,:]
            valid=ka&kb&(ha>=0)&(hb>=0);mask=valid&(np.abs(ha.astype(int)-hb.astype(int))>=8)
            pairs.append(dict(region=[rx,rz],neighbor=[rx+delta[0],rz+delta[1]],direction=direction,known_positive_pairs=int(valid.sum()),flagged_pairs=int(mask.sum())))
            labels,n=ndimage.label(mask);slices=ndimage.find_objects(labels)
            for i,s in enumerate(slices,1):
                if s is None:continue
                lo,hi=s[0].start,s[0].stop-1
                if direction=='east':bounds=[[rx*512+511,0,rz*512+lo],[rx*512+512,319,rz*512+hi]]
                else:bounds=[[rx*512+lo,0,rz*512+511],[rx*512+hi,319,rz*512+512]]
                examples=[]
                for j in range(lo,hi+1,max(1,(hi-lo+1)//10)):
                    if direction=='east':examples.append([rx*512+511,int(ha[j]),rz*512+j,int(hb[j])])
                    else:examples.append([rx*512+j,int(ha[j]),rz*512+511,int(hb[j])])
                objects.append(dict(id=f'heightmap/seam/{rx}/{rz}/{direction}/{i}',kind='REGION_SEAM_HEIGHTMAP_JUMP_8',bounds=bounds,candidate_columns=int(mask[lo:hi+1].sum()),examples=examples[:10],status='HEIGHTMAP_SCREEN_ONLY_STRUCTURE_WATER_TREE_OR_GEOLOGICAL_CLASSIFICATION_REQUIRED'))
        # A one-column collar makes four-neighbor depression checks complete at seams.
        h=np.full((514,514),-32768,dtype=np.int16);k=np.zeros((514,514),bool);h[1:-1,1:-1]=a['height'];k[1:-1,1:-1]=a['known']
        for dx,dz,dest,src in [(-1,0,(slice(1,-1),0),(slice(None),-1)),(1,0,(slice(1,-1),-1),(slice(None),0)),(0,-1,(0,slice(1,-1)),(-1,slice(None))),(0,1,(-1,slice(1,-1)),(0,slice(None)))]:
            b=maps.get((rx+dx,rz+dz))
            if b is not None:h[dest]=b['height'][src];k[dest]=b['known'][src]
        v=k&(h>=0);ring=np.stack([h[1:-1,:-2],h[1:-1,2:],h[:-2,1:-1],h[2:,1:-1]])
        valid=v[1:-1,1:-1]&v[1:-1,:-2]&v[1:-1,2:]&v[:-2,1:-1]&v[2:,1:-1]
        pit=valid&(ring.min(axis=0)-a['height']>=8);pit[1:-1,1:-1]=False
        for z,x in np.argwhere(pit):
            objects.append(dict(id=f'heightmap/seam/{rx}/{rz}/pit/{x}/{z}',kind='REGION_SEAM_ISOLATED_DEPRESSION_8',bounds=[[rx*512+int(x),0,rz*512+int(z)]]*2,candidate_columns=1,examples=[[rx*512+int(x),int(a['height'][z,x]),rz*512+int(z)]],status='HEIGHTMAP_SCREEN_ONLY_STRUCTURE_WATER_TREE_OR_GEOLOGICAL_CLASSIFICATION_REQUIRED'))
    inventory=json.loads((out.parent/'surface_object_inventory.json').read_text('utf8'))['objects']
    # Broad districts, rails' bounding rectangles and launch reserve are context only.
    finite=[o for o in inventory if o.get('bounds')and o['kind']not in {'district','airport','gateway','eva_plant'}and not o['kind'].startswith('native_curve/')]
    for o in objects:
        x0,_,z0=o['bounds'][0];x1,_,z1=o['bounds'][1]
        overlap=[];inside=[]
        for owner in finite:
            b=owner['bounds']
            if len(b)==6:b=[b[:3],b[3:]]
            if len(b)==4:b=[[b[0],0,b[2]],[b[1],319,b[3]]]
            if x0<=b[1][0]and x1>=b[0][0]and z0<=b[1][2]and z1>=b[0][2]:
                overlap.append(owner['id'])
                if b[0][0]<=x0<=x1<=b[1][0]and b[0][2]<=z0<=z1<=b[1][2]:inside.append(owner['id'])
        o['finite_owner_xz_overlap']=overlap;o['fully_inside_finite_owner_xz']=inside
        o['owner_context_is_quality_acceptance']=False
    report.update(objects=objects,region_boundary_pairs_not_yet_screened=False,region_boundary_pairs=pairs,known_positive_surface_columns=positive,stored_full_columns_attempted=report['counts']['full']*256)
    report['counts']['heightmap_screen_objects']=len(objects);report['object_kinds']=dict(Counter(o['kind']for o in objects))
    report['completion_scope']='All actual stored FULL chunks and all neighboring saved-region positive-surface pairs. Protochunks and zero-length placeholders are explicitly excluded; no chunk generated.'
    (out/'global_screen.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    envelope=out.parent/'stored_surface_envelope.json';old=json.loads(envelope.read_text('utf8'))
    old['regions']=[dict(region=r['region'],world_xz_bounds=[r['region'][0]*512,r['region'][1]*512,r['region'][0]*512+511,r['region'][1]*512+511],occupied_chunk_slots=r['stored'],full_chunk_slots=r['full'],proto_chunk_slots=r['proto'],empty_zero_length_placeholder=r.get('empty_zero_length_placeholder',False),classification='STORAGE_ENVELOPE_ONLY_NOT_QUALITY_ACCEPTANCE')for r in report['regions']]
    old.update(stored_chunk_slots=report['counts']['stored'],actual_stored_chunk_slots=report['counts']['stored'],full_chunk_slots=report['counts']['full'],proto_chunk_slots=report['counts']['proto'],empty_region_placeholders=report['counts']['empty_region_files'],earlier_182035_count_superseded=True,count_correction='Zero-length region placeholders have zero occupied slots, not 1024.')
    envelope.write_text(json.dumps(old,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(counts=report['counts'],object_kinds=report['object_kinds'],positive_columns=positive,region_pairs=len(pairs),world_written=False)))

if __name__=='__main__':main()
