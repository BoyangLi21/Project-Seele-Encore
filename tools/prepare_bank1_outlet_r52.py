"""Root's foot-bearing bank-one connection to the retained surface columns.

Actual three-rig/full-carrier model profiles size both bearing chambers.
This civil stage does not grant transport or controller readiness.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse,gzip,hashlib,json,struct
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from scipy.ndimage import binary_dilation
from matplotlib.path import Path as Polygon
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';lo=(-31,-655,-112);hi=(91,-407,147)
    before,palette=measure(lo,hi);names=list(palette)
    for s in ('minecraft:air','projectseele:nerv_shaft_panel','projectseele:nerv_machine_edge'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)}
    profile_path=ROOT/'.Codex/r52_full_assembly_geometry/LAUNCH_PROFILE_YZ_MM.bin.gz'
    raw=gzip.decompress(profile_path.read_bytes());count=struct.unpack('>i',raw[:4])[0]
    values=np.frombuffer(raw[4:],dtype='>i4').reshape(count,2)/1000
    # Model basis was already reflected/skinned/scaled. Mechanical yaw0 puts
    # its model Z opposite world Z; the actual paired sole is the rotation base.
    sole=.223975896835;values[:,1]=-values[:,1]+sole
    profile=values[ConvexHull(values).vertices]
    profile=(profile[:,None,:]+np.array([[-1,-1],[-1,1],[1,-1],[1,1]])[None,:,:]).reshape(-1,2)
    profile=profile[ConvexHull(profile).vertices]
    yy,zz=np.mgrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1]
    centres=np.column_stack([yy.ravel()+.5,zz.ravel()+.5]);section=np.zeros(yy.shape,bool)
    angle=-np.arctan2(160,24)
    poses=[(-554,124.5,q)for q in np.linspace(0,angle,181)]+[(-554+24*t,124.5-160*t,angle)for t in np.linspace(0,1,321)]+[(-530,-35.5,q)for q in np.linspace(angle,0,181)]
    for fy,fz,q in poses:
        c,s=np.cos(q),np.sin(q);matrix=np.array([[c,-s],[s,c]])
        section |= Polygon(profile@matrix.T+[fy,fz-sole]).contains_points(centres).reshape(yy.shape)
    # Original bank1 lower well and the old original surface columns keep
    # their exact centre lines. Only the measured connecting plant is new.
    section |= (yy>=-568)&(yy<=-554)&(zz>=109)&(zz<=139)
    section |= (yy>=-530)&(yy<=-409)&(zz>=-52)&(zz<=-20)
    core=np.zeros_like(before,bool);outer=np.zeros_like(before,bool)
    casing=binary_dilation(section,iterations=2)
    for cx in (-12,30,72):
        core[:,:,cx-15-lo[0]:cx+16-lo[0]]=section[:,:,None]
        outer[:,:,cx-17-lo[0]:cx+18-lo[0]]=casing[:,:,None]
    after=before.copy();after[outer]=ids['projectseele:nerv_shaft_panel'];after[core]=ids['minecraft:air']
    # Original lower loading plant and the adjacent compact personnel lift
    # are already commissioned components, not generic tunnel casing.
    lower_bank=np.broadcast_to(((yy<-571)&(zz>=0))[:,:,None],before.shape)
    xs=np.arange(lo[0],hi[0]+1)[None,None,:]
    compact=np.broadcast_to((xs>=89)&(zz[:,:,None]>=-56)&(zz[:,:,None]<=-48),before.shape)
    after[lower_bank|compact]=before[lower_bank|compact]
    # The original copied horizontal pressure stages are real mechanisms.
    # Keep their closed collision plane for explicit controller commissioning.
    barriers=np.isin(before,[i for i,s in enumerate(names)if s=='minecraft:barrier'])
    after[barriers]=before[barriers]
    markers=np.isin(before,[i for i,s in enumerate(names)if s=='minecraft:structure_void'])
    after[markers]=before[markers]
    old_lab=(yy>=-470)&(zz<=-55)
    assert np.array_equal(after[old_lab],before[old_lab]),'Retained original laboratory floor/room would be changed'
    # The bounded new lining may replace geology below the laboratory, but
    # never its existing air volume, foundation material, controls or glazing.
    lower_context=np.broadcast_to(((yy>=-490)&(zz<=-55))[:,:,None],before.shape)&(after!=before)
    assert {names[int(v)]for v in np.unique(before[lower_context])}<={'minecraft:stone'},'Non-geology in the retained laboratory lower context'
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    for (x,y,z),tag in tags.items():assert before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]],('Original device touched',(x,y,z),str(tag['id']))
    changed=before!=after
    allowed={'minecraft:air','minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]',
             'minecraft:deepslate_bricks','projectseele:nerv_machine_panel','projectseele:nerv_structural_panel',
             'projectseele:nerv_machine_edge','projectseele:nerv_wall_panel','projectseele:nerv_strip_light[lit=true]',
             'projectseele:nerv_shaft_panel','minecraft:polished_basalt[axis=y]',
             'minecraft:ladder[facing=south,waterlogged=false]','minecraft:ladder[facing=north,waterlogged=false]',
             'minecraft:black_concrete','minecraft:iron_block','minecraft:void_air',
             'minecraft:sea_lantern','projectseele:nerv_floor_panel','minecraft:light_gray_concrete',
             'minecraft:lodestone'}
    touched={names[int(i)]for i in np.unique(before[changed])}
    if not touched<=allowed:
        for state in touched-allowed:
            y,z,x=np.where(changed&(before==ids[state]));print('UNCLASSIFIED',state,len(y),[int(x.min()+lo[0]),int(y.min()+lo[1]),int(z.min()+lo[2]),int(x.max()+lo[0]),int(y.max()+lo[1]),int(z.max()+lo[2])],flush=True)
        raise AssertionError(('Unclassified old construction in new connection',touched-allowed))
    # The only older basement slab cut is buried below -500. The retained
    # laboratory, floor, furnishings, controls and actors above are untouched;
    # the new double lining replaces the local slab bearing around this bore.
    if 'minecraft:deepslate_bricks'in ids:
        y,z,x=np.where(changed&(before==ids['minecraft:deepslate_bricks']))
        assert not len(y)or int(y.max()+lo[1])<=-500
    vox.WORLD=world;vox.OUT=BASE/'bank1_outlet';vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    n=runs(p,lo,before,after,names,'R52_bank1_foot_bearing_original_surface_connection')
    p.meta.update(root_author=True,body_root_nodes=[[30.5,-646,124.5],[30.5,-554,124.5],[30.5,-530,-35.5],[30.5,81,-35.5]],
        actual_profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),bearing_rotation_axis='actual paired feet',
        original_lab_unchanged=True,original_surface_wells_retained=True,original_closed_pressure_stages_retained=True,
        new_guide_and_controller_commissioning_pending=True,playable=False)
    plan=p.save_plan('bank1_foot_bearing_surface_connection')
    report=dict(world_written=False,playable=False,changed_cells=n,bounds=[lo,hi],original_devices_preserved=len(tags),
        actual_model_profile_points=count,yz_profile_clearance_metres=1,horizontal_clear_width=31,lining_layers=2,
        original_pressure_barrier_cells_preserved=int(barriers.sum()),incline_rise=24,incline_run=160,
        body_root_nodes=p.meta['body_root_nodes'],pending=['all three variant actual swept triangle test','real fixed rails/bearings and stage controllers','native transfer/launch and view'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if args.apply:
        assert not list(plan.glob('applied_*')),'Applied bank1 connection must not be replayed'
        receipt=p.apply('bank1_foot_bearing_surface_connection')
        actual,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal],np.uint16)[actual],after)
        assert {q:t.snbt()for q,t in iter_block_entities(world,'projectseele:geofront',lo,hi)}=={q:t.snbt()for q,t in tags.items()}
        report.update(world_written=True,receipt=receipt,whole_connection_exact_readback=True)
        (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
