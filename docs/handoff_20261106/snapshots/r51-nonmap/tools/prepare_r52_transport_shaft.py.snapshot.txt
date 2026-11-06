"""Root remote heavy-aircraft shaft and supported underground mouth.

The 164m clear opening is sized from the actual R16 aircraft and original EVA
payload. Static construction does not commission a transport or door job.
"""
import argparse,json,uuid,hashlib,msvcrt
from pathlib import Path
import numpy as np
from scipy.ndimage import label
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from prepare_continuous_upright_civil_r52 import cuboids


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    base=args.base.resolve();world=base/'WORLD';survey.WORLD=extension.WORLD=world
    assert(base/'BASELINE.json').exists()
    source=Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele/mesh/tv_facilities_r16.json'
    assert hashlib.sha256(source.read_bytes()).hexdigest()=='f78e9c72ba6c3901ee55ab9f377832a0a8a3421c190dc5cbda96f9789d4f2cfe'
    out=base/'air_transport_shaft';plan=out/'remote_164m_aircraft_shaft';assert not list(plan.glob('applied_*')),'Already installed'
    data=np.load(out/'SOURCE_EXTENDED.npz');before=data['states'];lo=tuple(map(int,data['origin']));names=list(map(str,data['palette']));hi=(lo[0]+before.shape[2]-1,lo[1]+before.shape[0]-1,lo[2]+before.shape[1]-1)
    for s in ('minecraft:air','minecraft:barrier','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:nerv_floor_panel','projectseele:nerv_machine_edge','projectseele:nerv_strip_light[lit=true]'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};after=before.copy();cx,cz=-1120,-720;minx,maxx=cx-82,cx+81;minz,maxz=cz-82,cz+81
    def sl(box):
        x,y,z,X,Y,Z=box;assert lo[0]<=x<=X<=hi[0]and lo[1]<=y<=Y<=hi[1]and lo[2]<=z<=Z<=hi[2],box
        return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
    def fill(box,state):after[sl(box)]=ids[state]
    # A full founded casing crosses the rock and the cavern. Its lower floor
    # matches the existing airport's measured -476 datum; no floating frame.
    fill((minx-3,-480,minz-3,maxx+3,67,maxz+3),'projectseele:nerv_shaft_panel')
    fill((minx,-475,minz,maxx,270,maxz),'minecraft:air')
    fill((minx-3,-479,minz-3,maxx+3,-477,maxz+3),'projectseele:nerv_structural_panel')
    fill((minx,-476,minz,maxx,-476,maxz),'projectseele:nerv_floor_panel')
    # Explicit lower SOUTH doorway and a complete header/side-wall bearing.
    fill((minx,-475,maxz+1,maxx,-294,-609),'minecraft:air')
    fill((minx-3,-294,maxz+1,maxx+3,-290,maxz+6),'projectseele:nerv_structural_panel')
    for x in (minx-3,maxx+1):fill((x,-479,maxz+1,x+2,-294,maxz+6),'projectseele:nerv_machine_edge')
    # The forecourt follows the exact measured natural floor, no generic
    # external platform at the legacy receiver elevation.
    soil_ids=[i for i,s in enumerate(names)if s.split('[')[0]in('minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:sand')]
    ys=np.arange(lo[1],hi[1]+1)[:,None,None];soil=np.isin(before,soil_ids)
    ground=np.max(np.where(soil&(ys< -350),ys,-32768),axis=0)
    surface=np.max(np.where(soil&(ys>0),ys,-32768),axis=0)
    for x in range(minx,maxx+1):
        for z in range(maxz+1,-609+1):
            old=int(ground[z-lo[2],x-lo[0]]);assert old>-480
            t=min(1,max(0,(z-(maxz+8))/18));top=round(-476*(1-t)+old*t)
            fill((x,min(-480,old-3),z,x,top,z),'projectseele:nerv_structural_panel')
            fill((x,top,z,x,top,z),'projectseele:nerv_floor_panel')
            fill((x,top+1,z,x,-294,z),'minecraft:air')
    # Side-stack pockets have a continuous foundation in actual terrain.
    # Their operating recess stays below a concrete retaining edge where the
    # natural hillside is higher than the hatch datum.
    outer=(cx-106,cx+105,cz-87,cz+86)
    for x in range(outer[0],outer[1]+1):
        for z in range(outer[2],outer[3]+1):
            if minx<=x<=maxx and minz<=z<=maxz:continue
            old=int(surface[z-lo[2],x-lo[0]]);assert old>0
            fill((x,min(old-2,63),z,x,67,z),'projectseele:nerv_structural_panel')
            fill((x,68,z,x,112,z),'minecraft:air')
            border=x in(outer[0],outer[1])or z in(outer[2],outer[3])
            if border and old>=68:fill((x,68,z,x,old,z),'projectseele:nerv_wall_panel')
    # Flush rail-like casing ribs and lights match the other NERV shafts.
    for x in (minx-1,maxx+1):
        for z in (minz+7,maxz-7):
            fill((x,-475,z,x,65,z),'projectseele:nerv_machine_edge')
            for y in range(-460,66,24):fill((x,y,z,x,y+2,z),'projectseele:nerv_strip_light[lit=true]')
    # Closed collision material is installed now; matching actual visuals are
    # a declared commissioning step, never a readiness claim from these cells.
    fill((minx,68,minz,maxx,68,maxz),'minecraft:barrier')
    fill((minx,-475,maxz+2,maxx,-295,maxz+3),'minecraft:barrier')
    # Keep complete trees instead of leaving cut logs or detached canopies.
    wood=np.isin(before,[i for i,s in enumerate(names)if '_log['in s or '_leaves['in s])
    labels,count=label(wood);hit=np.unique(labels[(before!=after)&wood]);trees=[]
    for n in hit:
        if n==0:continue
        yy,zz,xx=np.where(labels==n)
        assert xx.min()>0 and xx.max()<before.shape[2]-1 and zz.min()>0 and zz.max()<before.shape[1]-1,('Touched tree leaves survey',int(n))
        after[yy,zz,xx]=ids['minecraft:air'];trees.append(dict(cells=len(xx),bounds=[[int(xx.min()+lo[0]),int(yy.min()+lo[1]),int(zz.min()+lo[2])],[int(xx.max()+lo[0]),int(yy.max()+lo[1]),int(zz.max()+lo[2])]]))
    changed=before!=after;old_states={names[int(v)]for v in np.unique(before[changed])}
    assert all(s.startswith('minecraft:')and not any(k in s for k in ('concrete','barrier','bricks','planks','glass','rail'))for s in old_states),old_states
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));assert not tags
    current,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal],np.uint16)[current],before)
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-1344,320))
    n=cuboids(p,lo,before,after,names,'current_remote_ground_to_cavern_aircraft_shaft')
    doors=[dict(id='remote_airshaft_surface',kind='SILO',visual_uuid=str(uuid.uuid5(uuid.NAMESPACE_URL,'projectseele:r52:remote_airshaft_surface')),frame=[cx,68.01,cz],opening_x=164,opening_z=164,collision_box=[minx,68,minz,maxx,68,maxz]),
           dict(id='remote_airshaft_south',kind='HANGAR',visual_uuid=str(uuid.uuid5(uuid.NAMESPACE_URL,'projectseele:r52:remote_airshaft_south')),frame=[cx,-475,maxz+4],width=164,height=181,collision_box=[minx,-475,maxz+2,maxx,-295,maxz+3])]
    p.meta.update(root_author=True,doors=doors,clear_shaft=[minx,-475,minz,maxx,270,maxz],native_aircraft_source='R16 actual body+fourrotors+cradle, full original EVA source',playable=False)
    plan=p.save_plan('remote_164m_aircraft_shaft');report=dict(world_written=False,changed_cells=n,centre_xz=[cx,cz],clear_width=164,clear_depth=164,underground_plane_root_y=-330,
        underground_floor_y=-476,surface_seal_y=68,doors=doors,complete_retired_tree_components=trees,
        source_contains_no_old_construction_or_devices=True,pending=['physical hatch/casing render and door commissioning','full aircraft/cargo continuous native route','native civil appearance'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');np.savez_compressed(plan/'SECTION_X.npz',origin=lo,palette=names,before=before[:,:,cx-lo[0]],after=after[:,:,cx-lo[0]])
    print(json.dumps({k:v for k,v in report.items()if k not in('doors','complete_retired_tree_components')}),flush=True)
    if args.apply:
        lock=extension.acquire_world_lock()
        try:
            receipt=p.apply('remote_164m_aircraft_shaft',session_lock=lock);actual,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal],np.uint16)[actual],after)
            report.update(world_written=True,receipt=receipt,whole_shaft_exact_readback=True);(plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
