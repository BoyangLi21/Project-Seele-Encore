"""Measured natural ridge and continuous EVA approaches for the new Hakone ports.

Only this explicit all-natural surface envelope is landscaped. The launch
holes, magazines, receivers and their native mechanisms are separate stages.
"""
from pathlib import Path
import argparse
import hashlib
import json
import msvcrt
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


def smooth(q):q=np.clip(q,0,1);return q*q*(3-2*q)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    base=a.base.resolve();world=base/'WORLD';src=base/'current_design_surveys/hakone_ridge.npz'
    d=np.load(src);before=d['states'];lo=d['origin'];names=list(map(str,d['palette']));hi=lo+np.array(before.shape)[[2,0,1]]-1
    old=np.load(base/'current_design_surveys/hakone_ground.npz')['height'];assert old.min()>lo[1]
    ids={n:i for i,n in enumerate(names)}
    def code(n):
        if n not in ids:ids[n]=len(names);names.append(n)
        return ids[n]
    air=code('minecraft:air');stone=code('minecraft:stone');soil=code('minecraft:dirt');grass=code('minecraft:grass_block[snowy=false]')
    log=code('minecraft:spruce_log[axis=y]');leaf=code('minecraft:spruce_leaves[distance=1,persistent=true,waterlogged=false]')
    natural={'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:water','minecraft:cave_air','minecraft:tuff','minecraft:deepslate','minecraft:deepslate[axis=y]'}
    assert all(n in natural or n.split('[')[0] in natural for n in names[:len(d['palette'])]),'Non-natural ridge source needs explicit ownership'
    z,x=np.mgrid[lo[2]:hi[2]+1,lo[0]:hi[0]+1]
    top=old.astype(float).copy()
    for cx,cz,rx,rz,peak in ((-1300,-1490,270,250,202),(-1250,-1390,235,240,190),
                             (-1310,-1610,220,155,203),(-1370,-1520,180,205,185),
                             (-1250,-1520,180,205,185),(-1130,-1520,180,205,185)):
        r2=((x-cx)/rx)**2+((z-cz)/rz)**2
        bell=np.maximum(0,1-r2)**1.5
        top=np.maximum(top,old+np.maximum(0,peak-old)*bell)
    centre=np.array([-1250.,-1410.]);forward=np.array([30.5,348.5])-centre;forward/=np.linalg.norm(forward);right=np.array([forward[1],-forward[0]])
    u=(x-centre[0])*right[0]+(z-centre[1])*right[1];v=(x-centre[0])*forward[0]+(z-centre[1])*forward[1]
    radius=np.sqrt((u/93)**2+((v+2)/106)**2);bench=1-smooth((radius-1)/.6)
    top=top*(1-bench)+174*bench
    ports=[[-1370.,175.,-1520.5],[-1250.,175.,-1520.5],[-1130.,175.,-1520.5]]
    for px,py,pz in ports:
        r=np.hypot(x-px,z-pz);blend=1-smooth((r-30)/34)
        top=top*(1-blend)+174*blend
    def at(a,b):
        point=centre+right*a+forward*b
        return [round(float(point[0])-.5)+.5,175.,round(float(point[1])-.5)+.5]
    points=dict(unit01_prone_feet=at(0,-60),unit00_shield=at(0,62),cannon_bay_centre=at(0,12),
        command_console=at(-66,-3),personnel_arrival=at(-80,-45),service_rack=at(67,12),unit02_standby=[-1350.5,175.,-1460.5])
    approaches={
        '0':[ports[2],[-1188.5,175.,-1463.5],[-1158.5,175.,-1463.5],[-1158.5,175.,-1403.5],points['unit00_shield']],
        '1':[ports[1],points['unit01_prone_feet']],
        '2':[ports[0],points['unit02_standby']],
    }
    path_distance=np.full(old.shape,np.inf)
    for path in approaches.values():
        for aa,bb in zip(path,path[1:]):
            p=np.asarray(aa)[[0,2]];q=np.asarray(bb)[[0,2]];delta=q-p
            t=np.clip(((x-p[0])*delta[0]+(z-p[1])*delta[1])/(delta@delta),0,1)
            path_distance=np.minimum(path_distance,np.hypot(x-p[0]-t*delta[0],z-p[1]-t*delta[1]))
    blend=1-smooth((path_distance-9)/18);top=top*(1-blend)+174*blend
    margin=np.minimum.reduce([x-lo[0],hi[0]-x,z-lo[2],hi[2]-z])
    edge=smooth((margin-8)/30);top=np.rint(old+(top-old)*edge).astype(int)
    active=top!=old
    assert not active[:8].any() and not active[-8:].any() and not active[:,:8].any() and not active[:,-8:].any()
    after=before.copy()
    for iy,wy in enumerate(range(int(lo[1]),int(hi[1])+1)):
        desired=np.where(wy>top,air,np.where(wy==top,grass,np.where(wy>=top-3,soil,stone)))
        after[iy,active]=desired[active]
    # Authored native spruce groves have real trunks founded in the new soil.
    # Keep a wide clear belt around every machine/arrival/personnel approach.
    trees=[];rng=np.random.default_rng(531013)
    for zz in range(int(lo[2])+26,int(hi[2])-26,17):
        for xx in range(int(lo[0])+26,int(hi[0])-26,17):
            xx+=int(rng.integers(-5,6));zz0=zz+int(rng.integers(-5,6));ix,iz=xx-lo[0],zz0-lo[2]
            if not active[iz,ix] or path_distance[iz,ix]<36 or radius[iz,ix]<1.8:continue
            if any(np.hypot(xx-p[0],zz0-p[2])<55 for p in ports):continue
            patch=top[iz-3:iz+4,ix-3:ix+4]
            if patch.max()-patch.min()>3 or rng.random()>.62:continue
            ground=int(top[iz,ix]);height=int(rng.integers(9,15));foot=ground+1
            assert names[int(after[ground-lo[1],iz,ix])]=='minecraft:grass_block[snowy=false]'
            cells={}
            for dy in range(2,height+1):
                r=max(0,min(3,int((height-dy)/2.7)+(dy%3==0)))
                for dz in range(-r,r+1):
                    for dx in range(-r,r+1):
                        if abs(dx)+abs(dz)>r+1:continue
                        cells[(xx+dx,foot+dy,zz0+dz)]=leaf
            for dy in range(height):cells[(xx,foot+dy,zz0)]=log
            for (tx,ty,tz),state in cells.items():
                assert after[ty-lo[1],tz-lo[2],tx-lo[0]]==air,'New grove touches an original source or another tree'
                after[ty-lo[1],tz-lo[2],tx-lo[0]]=state
            trees.append(dict(root=[xx,foot,zz0],height=height,cells=len(cells)))
    for path in approaches.values():
        for aa,bb in zip(path,path[1:]):
            aa,bb=np.asarray(aa),np.asarray(bb)
            for q in np.linspace(aa,bb,int(np.linalg.norm(bb-aa)*2)+2):
                ix,iz=int(np.floor(q[0]))-lo[0],int(np.floor(q[2]))-lo[2]
                assert np.all(top[iz-6:iz+7,ix-6:ix+7]==174),'EVA route has no continuous 13 m wide soil contact patch'
    survey.WORLD=extension.WORLD=world
    assert not list(iter_block_entities(world,'projectseele:geofront',tuple(lo),tuple(hi)))
    vox.WORLD=world;vox.OUT=base/'complete_hakone_ridge';vox.DIM='projectseele:geofront';stage='natural_ridge_three_ports_and_ground_approaches'
    assert not list((vox.OUT/stage).glob('applied_*'))
    painter=vox.Painter(vertical_bounds=(-1344,320));count=cuboids(painter,tuple(lo),before,after,names,'current_hakone_natural_ridge_and_continuous_EVA_soil')
    report=dict(world_written=False,playable=False,changed_cells=count,bounds=[lo.tolist(),hi.tolist()],source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        native_ground_range=[int(old.min()),int(old.max())],new_ground_range=[int(top.min()),int(top.max())],changed_columns=int(active.sum()),
        platform_floor_y=174,ports=ports,points=points,eva_access_routes=approaches,original_native_edge_exact=True,
        new_rooted_spruce_trees=trees,nearby_identity_or_device_changes=0,
        pending=['actual source-sized ports/receivers/magazine','native terrain/light/art review','current far encounter controls and full motion'])
    painter.meta.update(root_author=True,ports=ports,original_edge_preserved=True,playable=False)
    folder=painter.save_plan(stage);np.savez_compressed(folder/'HEIGHTS.npz',origin=[lo[0],lo[2]],before=old,after=top,active=active)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig=plt.figure(figsize=(13,6));ax=fig.add_subplot(121)
    ax.imshow(top,origin='lower',extent=[lo[0],hi[0],lo[2],hi[2]],cmap='terrain',vmin=40,vmax=200)
    for p in ports:ax.plot(p[0],p[2],'ks',ms=4)
    for path in approaches.values():ax.plot([p[0] for p in path],[p[2] for p in path],color='#e6d096',lw=2)
    ax.set(title='Measured-height candidate / three actual exit ports',xlabel='X',ylabel='Z')
    ax=fig.add_subplot(122,projection='3d');k=6;ax.plot_surface(x[::k,::k],z[::k,::k],top[::k,::k],cmap='terrain',vmin=40,vmax=200,linewidth=0)
    ax.view_init(elev=26,azim=-38);ax.set_zlim(35,230);ax.set_title('Rounded natural ridge with founded operating bench')
    fig.tight_layout();fig.savefig(folder/'RIDGE_PLAN.png',dpi=140);plt.close(fig)
    print(json.dumps({k:v for k,v in report.items() if k not in ('new_rooted_spruce_trees','eva_access_routes')}),len(trees),'rooted trees',flush=True)
    if a.apply:
        actual,pal=survey.measure(tuple(lo),tuple(hi));assert np.array_equal(np.asarray([ids[s] for s in pal],np.uint16)[actual],before)
        lock=extension.acquire_world_lock()
        try:
            report['receipt']=painter.apply(stage,session_lock=lock);report['world_written']=True
            (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
