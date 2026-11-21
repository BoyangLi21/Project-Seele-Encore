"""Root-only corner reservoir refinement against a frozen exact survey.

The rotated engineered basin submerges only the southwest pyramid corner.
Original rooms/shell, roads, equipment and distant natural lake are untouched.
"""
import argparse, json, msvcrt
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import regional_voxels as vox
from r52_spatial_plan import BASE
from prepare_terminal_move_r52 import runs
from survey_r52_original_complex import measure
from query_blocks import iter_block_entities
from extend_world_depth_r52 import acquire_world_lock


def smooth(v):
    q=np.clip(v,0,1);return q*q*(3-2*q)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    folder=BASE/'final_map_audit/corner_reservoir';source=np.load(folder/'CURRENT.npz')
    before=source['states'];lo=tuple(map(int,source['origin']));names=list(map(str,source['palette']))
    hi=(lo[0]+before.shape[2]-1,lo[1]+before.shape[0]-1,lo[2]+before.shape[1]-1)
    for state in ('minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]',
                  'minecraft:water[level=0]','minecraft:air','minecraft:black_concrete',
                  'projectseele:nerv_floor_panel','minecraft:sea_lantern'):
        if state not in names:names.append(state)
    ids={s:i for i,s in enumerate(names)}
    yy,zz,xx=np.ogrid[:before.shape[0],:before.shape[1],:before.shape[2]]
    x,y,z=xx+lo[0],yy+lo[1],zz+lo[2];u=x+z;v=x-z
    lake=(u>=25)&(u<=395)&(v>=-620)&(v<=-400)
    outer=(u>=17)&(u<=403)&(v>=-628)&(v<=-392)
    rim=outer&~lake
    old=(x>=-300)&(x<=-31)&(z>=246)&(z<=408)
    pyramid=np.broadcast_to(np.maximum(abs(x-30),abs(z-327))<=np.minimum(120,np.ceil((-384-y)*120/174))+1,before.shape)
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:dirt',
        'minecraft:grass_block','minecraft:water','minecraft:gravel','minecraft:sand','minecraft:clay',
        'minecraft:coarse_dirt','minecraft:podzol','minecraft:grass','minecraft:fern','minecraft:azure_bluet'}
    natural_ids=[i for i,s in enumerate(names) if s.split('[')[0] in natural]
    old_surface=(old & (y>=-510)&(y<=-467))
    owned_material=(np.isin(before,[ids['minecraft:black_concrete'],ids['projectseele:nerv_floor_panel']])
                    & np.broadcast_to(old_surface,before.shape))
    allowed=np.isin(before,natural_ids)|owned_material
    edited_domain=np.broadcast_to((old|outer)&(y>=-510)&(y<=-467),before.shape)&~pyramid
    assert np.all(allowed[edited_domain]),'Basin/rim touches an unrelated authored object'
    ground=-478+3.5*np.sin(x/137)*np.cos(z/193)+2.4*np.sin((x+z)/67)
    for gx,gz,h,r in ((420,830,29,310),(-230,1030,17,390),(720,330,11,290)):
        ground+=h*np.exp(-((x-gx)**2+(z-gz)**2)/(r*r))
    distance=np.hypot(np.maximum(np.maximum(-90-x,x-160),0),np.maximum(np.maximum(96-z,z-447),0))
    campus=1-smooth(distance/64);ground=np.floor(ground*(1-campus)-467*campus+.5).astype(int)
    # A level pedestrian rim joins the existing campus height through a
    # shallow planted embankment, not a sheer square earth cut.
    edge_distance=np.maximum.reduce([np.broadcast_to(17-u,ground.shape),np.broadcast_to(u-403,ground.shape),
        np.broadcast_to(-628-v,ground.shape),np.broadcast_to(v+392,ground.shape),np.zeros(ground.shape)]) / np.sqrt(2)
    bank=(-468)*(1-smooth(edge_distance/12))+ground*smooth(edge_distance/12)
    after=before.copy()
    for iy,wy in enumerate(range(lo[1],hi[1]+1)):
        restoring=np.broadcast_to((old&~outer)[0],before.shape[1:])&~pyramid[iy]&allowed[iy]
        target=np.where(wy>bank[0],ids['minecraft:air'],np.where(wy==np.floor(bank[0]),
            ids['minecraft:grass_block[snowy=false]'],np.where(wy>=bank[0]-3,ids['minecraft:dirt'],ids['minecraft:stone'])))
        if -510<=wy<=-467:after[iy][restoring]=target[restoring]
        area=np.broadcast_to(lake[0],before.shape[1:])&~pyramid[iy]
        if -510<=wy<=-467:
            state='minecraft:air' if wy>-473 else 'minecraft:water[level=0]' if wy>-509 else 'minecraft:black_concrete'
            after[iy][area]=ids[state]
        perimeter=np.broadcast_to((lake&((u<=26)|(u>=394)|(v<=-619)|(v>=-401)))[0],before.shape[1:])&~pyramid[iy]
        if -510<=wy<=-468:after[iy][perimeter]=ids['projectseele:nerv_floor_panel' if wy==-468 else 'minecraft:black_concrete']
        walkway=np.broadcast_to(rim[0],before.shape[1:])&~pyramid[iy]
        if -510<=wy<=-467:
            after[iy][walkway]=ids['minecraft:air' if wy>-468 else 'projectseele:nerv_floor_panel' if wy==-468 else 'minecraft:stone']
        if wy==-469:
            lights=perimeter&np.broadcast_to(((u%32==0)|(v%32==0))[0],before.shape[1:])
            after[iy][lights]=ids['minecraft:sea_lantern']
    # The protected pyramid volume is deliberately larger than its stepped
    # shell. Seal only the basin-side water cells at that interface: never
    # fill interior rooms or assume a protected mask itself is watertight.
    water_ids=[i for i,s in enumerate(names) if s.split('[')[0]=='minecraft:water']
    air_ids=[i for i,s in enumerate(names) if s in ('minecraft:air','minecraft:cave_air','minecraft:void_air')]
    def leaks(data):
        wet=np.isin(data,water_ids);free=np.isin(data,air_ids);bad=np.zeros_like(wet);outside=np.zeros_like(wet)
        for delta in ((0,0,1),(0,0,-1),(0,1,0),(0,-1,0),(-1,0,0)):
            a=tuple(slice(max(0,-v),min(n,n-v)) for n,v in zip(data.shape,delta))
            b=tuple(slice(max(0,v),min(n,n+v)) for n,v in zip(data.shape,delta))
            hit=wet[a]&free[b];bad[a]|=hit;outside[a]|=hit&~pyramid[b]
        return bad,outside
    seals,outside=leaks(after)
    assert not outside.any(),'An unclassified water containment breach is outside the pyramid interface'
    assert not np.any(seals&pyramid),'Never fill the retained original pyramid'
    after[seals]=ids['minecraft:black_concrete']
    assert not leaks(after)[0].any(),'Basin water still has an open side or bottom face'
    assert np.array_equal(before[pyramid],after[pyramid]),'Pyramid whole volume altered'
    change=before!=after
    assert np.all(allowed[change]),'Unowned changed cell'
    water_ids=[i for i,s in enumerate(names) if s.split('[')[0]=='minecraft:water']
    changed_water=np.isin(after,water_ids)&change
    assert not np.any(changed_water&~np.broadcast_to(lake,before.shape))
    assert not np.any(np.isin(after,water_ids)&np.broadcast_to((old|outer)&~lake,before.shape)&~pyramid), 'Old water outside final basin remains'
    # Exact corner relationship at waterline: three corners and four face
    # midpoints are on land; the southwest corner alone is in the basin.
    radius=int(np.ceil((-384+473)*120/174))+1
    points={'northwest':(30-radius,327-radius),'northeast':(30+radius,327-radius),
            'southeast':(30+radius,327+radius),'southwest':(30-radius,327+radius),
            'north':(30,327-radius),'east':(30+radius,327),'south':(30,327+radius),'west':(30-radius,327)}
    inside=lambda p:25<=sum(p)<=395 and -620<=p[0]-p[1]<=-400
    relation={k:inside(p) for k,p in points.items()}
    assert [k for k,vv in relation.items() if vv]==['southwest'],relation
    tags=dict(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
    for (px,py,pz),tag in tags.items():assert not change[py-lo[1],pz-lo[2],px-lo[0]],('Device touched',px,py,pz)
    fig,axes=plt.subplots(1,2,figsize=(14,8),layout='constrained')
    for ax,data,title in zip(axes,[before,after],['Current saved waterline','Proposed: southwest corner only']):
        iy=-473-lo[1];rgb=np.ones((*data.shape[1:],3))*[.42,.48,.38]
        layer=data[iy];rgb[np.isin(layer,water_ids)]=[.10,.36,.48]
        rgb[pyramid[iy]]=[.12,.15,.17]
        rgb[layer==ids['minecraft:black_concrete']]=[.18,.20,.21]
        rgb[layer==ids['projectseele:nerv_floor_panel']]=[.50,.55,.54]
        ax.imshow(rgb,extent=[lo[0]-.5,hi[0]+.5,hi[2]+.5,lo[2]-.5],interpolation='nearest')
        ax.set(title=title,xlabel='X',ylabel='Z (north upward)');ax.set_aspect('equal')
        for name,(px,pz) in points.items():ax.plot(px,pz,'o',ms=3,color='orange' if relation[name] else 'white')
    fig.savefig(folder/'CORNER_PLAN.png',dpi=150);plt.close(fig)
    np.savez_compressed(folder/'PROPOSED.npz',origin=lo,states=after,palette=names)
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=folder;vox.DIM='projectseele:geofront'
    p=vox.Painter(vertical_bounds=(-960,320));n=runs(p,lo,before,after,names,'R52_single_corner_artificial_reservoir')
    p.meta.update(root_author=True,waterline=-473,basin_floor=-509,world_pyramid_volume_preserved=True,
        polygon_xz=[[-297.5,322.5],[-187.5,212.5],[-2.5,397.5],[-112.5,507.5]],
        only_submerged_corner='southwest',roads_and_devices_untouched=True)
    target=p.save_plan('single_southwest_corner')
    report=dict(world_written=False,changed_cells=n,corner_relationship=relation,devices_untouched=len(tags),
        original_pyramid_preserved=True,distant_natural_lake_untouched=True,native_art_acceptance=False,
        basin_side_interface_seal_cells=int(seals.sum()),water_side_and_bottom_air_breaches=0)
    if args.apply:
        assert not list(target.glob('applied_*')),'Do not replay'
        current,pal=measure(lo,hi);assert np.array_equal(np.array(names)[before],np.array(pal)[current])
        lock=acquire_world_lock()
        try:report.update(world_written=True,receipt=p.apply('single_southwest_corner',session_lock=lock))
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (target/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
