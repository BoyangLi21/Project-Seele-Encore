"""Whole unchanged old generator trees inside the installed 7x7 native rail envelope."""
from pathlib import Path
import json,gzip,math
import numpy as np
from scipy.spatial import cKDTree
from classify_legacy_trees_r44 import spec,point
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';ART=ROOT/'artifacts/rebuild_r44/ecology/legacy_tree_components'

def main():
    source=json.loads((ART/'reserved_three_dimensional_relationships.json').read_text('utf8'));groups=[r for r in source['objects'] if r['status']=='NATIVE_RAILWAY_3D_ENVELOPE_REVIEW']
    needed={tuple(q) for r in groups for q in r['roots']};templates={}
    for gx in range(-131,132):
        for gz in range(-115,152):
            t=spec(gx,gz)
            if t is not None and tuple(t['root']) in needed:templates[tuple(t['root'])]=t
    native=json.loads((ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json').read_text());points=[];owners=[]
    for curve in native['curves']:
        if curve['mode']=='TRAIN':points.extend(curve['points']);owners.extend([curve['id']]*len(curve['points']))
    rail=np.array(points,float);xy=np.floor(rail[:,[0,2]]);tree=cKDTree(xy);rows=[];records=[];held=[]
    for r in groups:
        mask=set().union(*(templates[tuple(q)]['mask'] for q in r['roots']));hits=[]
        for packed in mask:
            x,y,z=point(packed)
            for i in tree.query_ball_point([x,z],4.25):
                xx,yy,zz=rail[i]
                if abs(math.floor(xx)-x)<=3 and abs(math.floor(zz)-z)<=3 and yy-3<y+1 and yy+8>y:
                    hits.append(dict(pos=[x,y,z],curve=owners[i],native_point=list(rail[i])));break
        record=dict(id=r['id'],roots=r['roots'],bounds=r['bounds'],exact_member_cells=len(mask),exact_swept_member_intersections=len(hits),examples=hits[:8],status='BOUNDING_ONLY_NO_EXACT_MEMBER_CONFLICT')
        if hits:
            w=MeasuredWorld(WORLD);lo,hi=r['bounds'];w.box(lo,hi);w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
            failures=[];actual={}
            for root in r['roots']:
                template=templates[tuple(root)]
                for packed in template['mask']:
                    q=point(packed);state=w.block(q);actual[q]=state
                    if state is None or q in tags or (packed in template['logs'] and state!=template['log']+'[axis=y]') or (packed in template['leaves'] and not (state.startswith('minecraft:oak_leaves[') and 'persistent=true' in state and 'waterlogged=false' in state)):failures.append(dict(pos=q,state=state,has_nbt=q in tags))
            if failures:record.update(status='PRESERVE_CHANGED_COMPLETE_COMPONENT',failures=failures);held.append(record)
            else:
                record['status']='RETIRE_COMPLETE_VERIFIED_OLD_TREE_COLLIDING_WITH_NATIVE_RAIL'
                rows.extend(dict(pos=q,before=state,after='minecraft:air',before_nbt=None,after_nbt=None,owner=r['id'],reason='Retire the whole unchanged old 14-grid generator tree that enters the installed native train envelope; rail, machine and user state remain unchanged') for q,state in actual.items())
        records.append(record)
    folder=ART/'native_rail_conflict_retirement';folder.mkdir(exist_ok=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(folder/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in rows:
                value=dict(row)
                if inverse:value['before'],value['after']=row['after'],row['before']
                stream.write(json.dumps(value)+'\n')
    report=dict(objects=records,changed_cells=len(rows),held=held,world_written=False,rail_runtime_files_changed=False,source_virtual_envelope='Installed R43 native curves, integer 7x7 footprint, railY-3..railY+8; exact tree members after whole template/NBT verification')
    (folder/'audit.json').write_text(json.dumps(report,indent=2));print('full tree conflict retirement',len(rows),'cells','held',len(held),[(r['id'],r['exact_swept_member_intersections']) for r in records],flush=True)

if __name__=='__main__':main()
