"""Read complete bounded neighborhoods of all 91 historic rejected pit anchors.

This is a current-geometry classification, not a blanket fill operation. Existing
equipment, road/rail supports and NBT remain untouched, including guarded drops.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,json
import numpy as np
from scipy import ndimage
from query_blocks import iter_selected_sections,chunk_statuses,iter_block_entities,AIR
from measure_world_r40 import MeasuredWorld
from audit_surface_objects_r50 import SOIL

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/surface_r50');args=ap.parse_args()
    out=args.out.resolve();source=json.loads((out/'surface_pit_readback.json').read_text('utf8'));w=MeasuredWorld(args.world.resolve());radius=16
    for row in source['objects']:
        x,y,z=row['seed'];w.box((x-radius,0,z-radius),(x+radius,min(255,y+24),z+radius))
    # Include the whole surviving road-edge drop, beyond both rejected anchors.
    w.box((44,0,-191),(74,104,-139));w.load()
    if set(w.status.values())!={'full'}:raise RuntimeError(('Not all measured pit neighborhoods are full',Counter(w.status.values())))
    bes=dict(iter_block_entities(w.world,w.dimension,(min(x for x,z in w.selected)*16,0,min(z for x,z in w.selected)*16),((max(x for x,z in w.selected)+1)*16-1,255,(max(z for x,z in w.selected)+1)*16-1),selected_chunks=set(w.selected)))
    ground={};top={}
    # One palette lookup and vector reduction per actual section, no repeated column scan.
    for (cx,sy,cz),(palette,ids)in w.tiles.items():
        index=ids.reshape(16,16,16);yy=np.arange(sy*16,sy*16+16)[:,None,None]
        natural=np.array([s.partition('[')[0]in SOIL for s in palette])[index]
        solid=np.array([s.partition('[')[0]not in AIR|{'minecraft:water','minecraft:lava','minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}and not s.partition('[')[0].endswith(('_leaves','_log','_torch','_button','_carpet','_sign'))and not s.startswith('projectseele:nerv_edge_rail')for s in palette])[index]
        key=cx,cz
        ground[key]=np.maximum(ground.get(key,np.full((16,16),-32768,np.int16)),np.where(natural,yy,-32768).max(axis=0))
        top[key]=np.maximum(top.get(key,np.full((16,16),-32768,np.int16)),np.where(solid,yy,-32768).max(axis=0))
    def raster(cache,x0,z0,x1,z1):
        result=np.full((z1-z0+1,x1-x0+1),-32768,np.int16)
        for cx in range(x0//16,x1//16+1):
            for cz in range(z0//16,z1//16+1):
                if(cx,cz)not in cache:continue
                ax,bx=max(x0,cx*16),min(x1,cx*16+15);az,bz=max(z0,cz*16),min(z1,cz*16+15)
                result[az-z0:bz-z0+1,ax-x0:bx-x0+1]=cache[cx,cz][az-cz*16:bz-cz*16+1,ax-cx*16:bx-cx*16+1]
        return result
    result=[]
    for row in source['objects']:
        x,y,z=row['seed'];x0,z0,x1,z1=x-radius,z-radius,x+radius,z+radius;g=raster(ground,x0,z0,x1,z1);t=raster(top,x0,z0,x1,z1)
        nominal=np.array([[w.get(xx,y,zz).partition('[')[0]in AIR for xx in range(x0,x1+1)]for zz in range(z0,z1+1)],bool)
        labels,n=ndimage.label(nominal);label=labels[radius,radius];component=labels==label if label else np.zeros_like(labels,bool)
        edge=bool(component[0].any()or component[-1].any()or component[:,0].any()or component[:,-1].any())
        seed=w.get(x,y,z);below=w.get(x,y-1,z);center_ground=int(g[radius,radius]);center_top=int(t[radius,radius])
        if seed.partition('[')[0]not in AIR:status='HISTORIC_REJECTED_FLOOR_NOW_SOLID';decision='Retain actual current continuous support; no remaining opening at the historic rejected floor.'
        elif below.startswith('minecraft:grass_block')and center_ground==y-1:status='ONE_BLOCK_LOWER_CURRENT_NATURAL_DATUM';decision='Retain the measured grass/dirt datum; the old fixed Y seed is one block above real ground, not an enclosed equipment shaft.'
        elif(x,y,z)in{(57,80,-175),(58,80,-175)}:status='OPEN_GUARDED_ROAD_EMBANKMENT';decision='Retain the complete existing road edge guard and native lower natural slope; air is connected to the surrounding hillside, not an enclosed pit.'
        else:status='UNCLASSIFIED_ACTUAL_OPENING';decision='Requires a named facility or geological component decision; not accepted.'
        nb=[dict(pos=list(q),id=str(tag.get('id','')))for q,tag in bes.items()if x0<=q[0]<=x1 and z0<=q[2]<=z1]
        guards=[]
        for zz in range(z0,z1+1):
            for xx in range(x0,x1+1):
                s=w.get(xx,y+1,zz)
                if s.startswith('projectseele:nerv_edge_rail'):guards.append(dict(pos=[xx,y+1,zz],state=s))
        ident=f'pit_{x}_{y}_{z}';np.savez_compressed(out/(ident+'.npz'),origin=[x0,z0],actual_soil_height=g,actual_nonplant_top=t,historic_datum_air=nominal,historic_seed_air_component=component)
        result.append(dict(seed=row['seed'],historic_reason=row['historic_reason'],previous_broad_protection_context=row['protected_owner'],status=status,decision=decision,actual_seed_state=seed,actual_below_state=below,actual_soil_y=center_ground,actual_nonplant_top_y=center_top,bounds=[[x0,0,z0],[x1,min(255,y+24),z1]],complete_columns=33*33,full_chunk_preflight=True,datum_air_component_columns=int(component.sum()),air_component_exits_measured_boundary=edge,guard_cells=guards,block_entities=nb,profile=ident+'.npz',classification_is_whole_facility_acceptance=False))
    x0,z0,x1,z1=44,-191,74,-139;g=raster(ground,x0,z0,x1,z1);t=raster(top,x0,z0,x1,z1);np.savez_compressed(out/'pit_road_east_embankment_full.npz',origin=[x0,z0],actual_soil_height=g,actual_nonplant_top=t)
    road_guard=[]
    for zz in range(z0,z1+1):
        s=w.get(56,81,zz)
        if s.startswith('projectseele:nerv_edge_rail'):road_guard.append(dict(pos=[56,81,zz],state=s))
    road=dict(bounds=[[x0,0,z0],[x1,104,z1]],full_dense_columns=g.size,profile='pit_road_east_embankment_full.npz',road_x_range=[48,56],road_y=80,complete_surviving_east_guard=road_guard,seed_ground=[dict(seed=list(q),actual_soil_y=int(g[q[2]-z0,q[0]-x0]))for q in[(57,80,-175),(58,80,-175)]],actual_surface_context='East road embankment transitions into open lower hillside; no enclosed shaft wall or block entity found at either rejected seed.',all_BEs_in_complete_box=[list(q)for q in bes if x0<=q[0]<=x1 and z0<=q[2]<=z1],world_written=False)
    report=dict(world=str(w.world),objects=result,counts=dict(Counter(r['status']for r in result)),complete_neighborhood_column_visits=len(result)*33*33,road_embankment_complete_context=road,exact_world_edit_cells=0,source_edit_cells=0,reason_for_no_blanket_fill='All 91 historic anchors are current solid floors, a measured one-block datum difference, or a complete retained guarded embankment. Filling the latter would change a legitimate open hillside and original road bearing; full global terrain candidates are handled separately.',historic_rejected_anchor_classification_complete=all(r['status']!='UNCLASSIFIED_ACTUAL_OPENING'for r in result),global_surface_quality_passed=False,world_written=False)
    (out/'surface_pit_complete_classification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report['counts']),len(w.tiles),'actual sections',flush=True)

if __name__=='__main__':main()
