"""Root's TV-plan-aligned square basin candidate. Never changes World by default.

The historical corner basin was a rotated rectangle. The original plan instead
shows an aligned square and a smaller pyramid at one corner. This finite design
also puts the user's X=-30/Z=266 shore point on the east rim. No rail is moved.
"""
from pathlib import Path
import argparse,json,msvcrt
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import deque
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_continuous_upright_civil_r52 import cuboids
from extend_world_depth_r52 import acquire_world_lock

OUT=BASE/'final_map_audit/tv_square_reservoir_nw'
STAGE='aligned_square_northwest_corner'

def smooth(q):
    q=np.clip(q,0,1);return q*q*(3-2*q)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    src=np.load(OUT/'CURRENT.npz');before=src['states'];lo=tuple(map(int,src['origin']));names=list(map(str,src['palette']))
    hi=tuple(lo[i]+before.shape[(2,0,1)[i]]-1 for i in range(3))
    ids={s:i for i,s in enumerate(names)}
    def code(s):
        if s not in ids:ids[s]=len(names);names.append(s)
        return ids[s]
    for s in ('minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:air','minecraft:black_concrete','minecraft:water[level=0]','projectseele:nerv_floor_panel','projectseele:nerv_strip_light[lit=true]'):code(s)
    yy,zz,xx=np.ogrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1,lo[0]:hi[0]+1]
    shape=before.shape;shape2=shape[1:];u=xx+zz;v=xx-zz
    pyr=np.broadcast_to(np.maximum(abs(xx-30),abs(zz-327))<=np.minimum(120,np.ceil((-384-yy)*120/174))+1,shape)
    basin2=np.broadcast_to(((xx>=-285)&(xx<=-31)&(zz>=34)&(zz<=288))[0],shape2)
    outer2=np.broadcast_to(((xx>=-290)&(xx<=-26)&(zz>=29)&(zz<=293))[0],shape2)
    old2=np.broadcast_to(((u>=17)&(u<=403)&(v>=-628)&(v<=-392))[0],shape2)
    d=np.maximum.reduce([np.broadcast_to(-290-xx, (1,*shape2)),np.broadcast_to(xx+26,(1,*shape2)),np.broadcast_to(29-zz,(1,*shape2)),np.broadcast_to(zz-293,(1,*shape2)),np.zeros((1,*shape2))])[0]
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:water','minecraft:gravel','minecraft:sand','minecraft:clay','minecraft:coarse_dirt','minecraft:podzol','minecraft:grass','minecraft:fern','minecraft:azure_bluet','minecraft:poppy','minecraft:dandelion'}
    allowed=np.isin(before,[i for i,s in enumerate(names) if s.split('[')[0] in natural])
    owned_old=np.broadcast_to(old2[None,:,:]&(yy>=-510)&(yy<=-467),shape)&np.isin(before,[code(s) for s in ('minecraft:black_concrete','projectseele:nerv_floor_panel','minecraft:sea_lantern','projectseele:nerv_strip_light[lit=true]')])
    # Exact former inspection-path material is not implicitly declared waste.
    # Its verified ownership/continuity receipt is required before any write.
    walk=((xx>=-153)&(xx<=-28)&(zz>=29)&(zz<=133)&(yy>=-484)&(yy<=-467))
    old_walk=np.broadcast_to(walk,shape)&(before==code('minecraft:smooth_stone'))
    after=before.copy();air=code('minecraft:air')
    trees=np.isin(before,[i for i,s in enumerate(names) if s.split('[')[0].endswith(('_log','_leaves'))])
    positions=set(map(tuple,np.argwhere(trees)));components=[]
    while positions:
        seed=positions.pop();q=deque([seed]);points=[seed]
        while q:
            p=q.popleft()
            for dy in (-1,0,1):
                for dz in (-1,0,1):
                    for dx in (-1,0,1):
                        k=(p[0]+dy,p[1]+dz,p[2]+dx)
                        if k in positions:positions.remove(k);q.append(k);points.append(k)
        components.append(np.asarray(points,int))
    moving=[]
    for pts in components:
        if not np.any((d<18)[pts[:,1],pts[:,2]]):continue
        assert np.all(pts>0) and np.all(pts<np.asarray(shape)-1),'Affected tree is incomplete at measurement edge'
        logs=np.asarray([q for q in pts if names[int(before[tuple(q)])].split('[')[0].endswith('_log')])
        assert len(logs),'Affected foliage has no complete original trunk'
        root=logs[np.argmin(logs[:,0])];moving.append((pts,root,before[tuple(pts.T)].copy()))
        after[tuple(pts.T)]=air
    # Restore only the retired authored basin; surrounding existing natural
    # slopes remain measured inputs. This is landscaping, not a claim to know
    # the old pre-project landscape exactly.
    ground=-478+3.5*np.sin(xx/137)*np.cos(zz/193)+2.4*np.sin((xx+zz)/67)
    for gx,gz,h,r in ((420,830,29,310),(-230,1030,17,390),(720,330,11,290)):ground+=h*np.exp(-((xx-gx)**2+(zz-gz)**2)/(r*r))
    distance=np.hypot(np.maximum(np.maximum(-90-xx,xx-160),0),np.maximum(np.maximum(96-zz,zz-447),0))
    campus=1-smooth(distance/64);ground=np.floor(ground*(1-campus)-467*campus+.5)[0].astype(int)
    top_ids=[i for i,s in enumerate(names) if s.split('[')[0] in ('minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:coarse_dirt','minecraft:podzol','minecraft:gravel')]
    existing=np.max(np.where(np.isin(before,top_ids),np.arange(shape[0])[:,None,None]+lo[1],-9999),axis=0)
    restoration=old2&~outer2
    desired=np.where(restoration,ground,existing)
    blend=smooth(d/18);terrain=np.floor((-468)*(1-blend)+desired*blend+.5).astype(int)
    grading=(d<18)|restoration
    tree_columns=np.any(trees,axis=0)
    for pts,root,values in moving:tree_columns[pts[:,1],pts[:,2]]=False
    grading &= ~tree_columns
    safe=allowed|owned_old|old_walk|trees
    floor2=-473-np.maximum(1,np.floor(36*np.clip(np.minimum.reduce([np.broadcast_to((xx+285)/127,(1,*shape2)),np.broadcast_to((-31-xx)/127,(1,*shape2)),np.broadcast_to((zz-34)/127,(1,*shape2)),np.broadcast_to((288-zz)/127,(1,*shape2))]),0,1))).astype(int)[0]
    for iy,wy in enumerate(range(lo[1],hi[1]+1)):
        land=grading&~basin2&~pyr[iy]&safe[iy]
        wanted=np.where(wy>terrain,air,np.where(wy==terrain,code('minecraft:grass_block[snowy=false]'),np.where(wy>=terrain-3,code('minecraft:dirt'),code('minecraft:stone'))))
        # Existing protected machine ceiling at Y=-474 bears the east walk.
        # Keep every deeper cell of that machine column, including its air.
        preserve_machine=(xx[0]>=-30)&(zz[0]<=142)&(wy<=-474)
        land &= ~np.broadcast_to(preserve_machine,shape2)
        if wy>=-510:after[iy][land]=wanted[land]
        inside=basin2&~pyr[iy]
        if wy>=-510:
            target=np.where(wy>-473,air,np.where(wy>floor2,code('minecraft:water[level=0]'),np.where(wy>=floor2-1,code('minecraft:black_concrete'),code('minecraft:stone'))))
            assert np.all(safe[iy][inside]),('Foreign basin component',wy,{names[int(k)]:int(n)for k,n in zip(*np.unique(before[iy][inside&~safe[iy]],return_counts=True))})
            after[iy][inside]=target[inside]
        rim=outer2&~basin2&~pyr[iy]
        if wy==-468:after[iy][rim]=code('projectseele:nerv_floor_panel')
        if wy==-469:
            lamps=rim&np.broadcast_to(((xx%20==0)&((zz==29)|(zz==293))|((zz%20==0)&((xx==-290)|(xx==-26))))[0],shape2)
            after[iy][lamps]=code('projectseele:nerv_strip_light[lit=true]')
    # Preserve the north approach of the real five-metre inspection walk.
    # Its former L ran through the new basin. The replacement goes around the
    # north/east rim and rejoins the same east grass interface at Z=131.
    stem=np.broadcast_to((xx>=-152)&(xx<=-148)&(zz<=20),shape)
    after[stem]=before[stem]
    walk_tops={}
    for x in range(-150,-21):
        top=-482+np.floor((x+150)*32/128)/2
        for z in range(18,23):walk_tops[x,z]=float(top)
    for z in range(20,134):
        for x in range(-24,-19):walk_tops[x,z]=-466.
    for z in range(129,134):
        for x in range(-28,-19):walk_tops[x,z]=-466.
    # Round the two corners with full width, not a one-cell diagonal cut.
    for z in range(18,23):
        for x in range(-152,-150):walk_tops[x,z]=-482.
    for z in range(18,23):
        for x in range(-24,-19):walk_tops[x,z]=-466.
    for (x,z),top in walk_tops.items():
        ix,iz=x-lo[0],z-lo[2];base=int(np.floor(top));half=top%1!=0
        floor_y=base if half else base-1
        state='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]' if half else 'minecraft:smooth_stone'
        for y in range(floor_y-2,int(np.ceil(top))+4):
            iy=y-lo[1]
            wanted=code(state) if y==floor_y else code('minecraft:stone') if y<floor_y else air
            assert not pyr[iy,iz,ix] and (safe[iy,iz,ix] or before[iy,iz,ix]==wanted),('Protected new walk cell',x,y,z,names[int(before[iy,iz,ix])])
            after[iy,iz,ix]=wanted
        if x<=-32:
            assert names[int(before[-511-lo[1],iz,ix])].split('[')[0] in ('minecraft:stone','minecraft:dirt','minecraft:grass_block'),'Measured continuous ramp foundation required'
            for y in range(-510,floor_y):
                iy=y-lo[1];assert safe[iy,iz,ix] and not pyr[iy,iz,ix],('Ramp foundation touches authored component',x,y,z)
                after[iy,iz,ix]=code('minecraft:stone')
    # The new launch body must retain its original air below Y=-474.
    # Ground the east walkway on finite horizontal steel beams instead of
    # pouring foundations through that protected channel. Each beam has a
    # three-metre embed into a continuously grounded western retaining strip.
    beam=code('projectseele:nerv_structural_panel');foundation_columns=0
    for z in range(18,143):
        iz=z-lo[2]
        for x in range(-34,-31):
            ix=x-lo[0]
            assert names[int(before[-511-lo[1],iz,ix])].split('[')[0] in ('minecraft:stone','minecraft:dirt','minecraft:grass_block'),'Actual western abutment datum must be solid'
            top=min(-469,int(np.floor(walk_tops.get((x,z),-467)))-1)
            for y in range(-510,top+1):
                iy=y-lo[1];assert safe[iy,iz,ix] and not pyr[iy,iz,ix],('Western abutment touches authored component',x,y,z)
                after[iy,iz,ix]=code('minecraft:black_concrete') if x==-32 else code('minecraft:stone')
            foundation_columns+=1
        for x in range(-34,-19):
            for y in (-470,-469):
                iy,ix=y-lo[1],x-lo[0]
                # Never replace an authored road's half-height floor.
                if (x,z) in walk_tops and y>=np.floor(walk_tops[x,z])-1:continue
                assert safe[iy,iz,ix] and not pyr[iy,iz,ix],('Measured beam interferes with authored structure',x,y,z)
                after[iy,iz,ix]=beam
    assert walk_tops[-150,20]==-482 and walk_tops[-28,131]==-466
    max_step=0.
    for (x,z),h in walk_tops.items():
        for q in ((x+1,z),(x,z+1)):
            if q in walk_tops:max_step=max(max_step,abs(h-walk_tops[q]))
    assert max_step<=.5,('Inspection walk half-step continuity',max_step)
    # Relocate complete affected trees onto the retired pool's planted ground.
    # Exact block states and every relative branch/leaf coordinate are retained.
    moves=[];targets=[(x+((zi*11+xi*7)%13)-6,z+((xi*11+zi*5)%17)-8)
        for zi,z in enumerate((330,359,387,416,446,469))
        for xi,x in enumerate((-250,-221,-192,-163,-134,-105))]
    for pts,root,values in moving:
        chosen=None
        for tx,tz in targets:
            ix,iz=tx-lo[0],tz-lo[2]
            if outer2[iz,ix] or not restoration[iz,ix]:continue
            solid=np.flatnonzero(np.isin(after[:,iz,ix],top_ids))
            if not len(solid):continue
            ty=int(solid[-1])+1
            delta=np.asarray([ty,iz,ix])-root;dest=pts+delta
            if np.any(dest<1)or np.any(dest>=np.asarray(shape)-1):continue
            if np.any(after[tuple(dest.T)]!=air) or np.any(pyr[tuple(dest.T)]):continue
            if any(np.linalg.norm(np.asarray([tx,tz])-np.asarray(m['target_root'])[[0,2]])<18 for m in moves):continue
            chosen=(dest,delta,[tx,lo[1]+ty,tz]);break
        assert chosen is not None,'No safe whole-tree destination'
        dest,delta,target=chosen;after[tuple(dest.T)]=values
        assert np.array_equal(after[tuple(dest.T)],values)
        moves.append(dict(source_root=[int(root[2]+lo[0]),int(root[0]+lo[1]),int(root[1]+lo[2])],target_root=target,delta_xyz=[int(delta[2]),int(delta[0]),int(delta[1])],block_count=len(pts)))
    # Water at the protected stepped pyramid is sealed from the basin side.
    wet=after==code('minecraft:water[level=0]');free=np.isin(after,[i for i,s in enumerate(names)if s in ('minecraft:air','minecraft:cave_air','minecraft:void_air')]);seals=np.zeros(shape,bool)
    for dy,dz,dx in ((0,0,1),(0,0,-1),(0,1,0),(0,-1,0),(-1,0,0)):
        delta=(dy,dz,dx);sl=tuple(slice(max(0,-v),min(n,n-v))for n,v in zip(shape,delta));other=tuple(slice(max(0,v),min(n,n+v))for n,v in zip(shape,delta))
        hit=wet[sl]&free[other]
        assert not np.any(hit&~pyr[other]),'Open basin-side/bottom water breach outside protected pyramid'
        seals[sl]|=hit
    assert not np.any(seals&pyr);after[seals]=code('minecraft:black_concrete')
    assert np.array_equal(before[pyr],after[pyr])
    survey=json.loads((OUT/'SURVEY.json').read_text('utf8'))
    for t in survey['devices']:
        x,y,z=t['position'];assert before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]],('Device changed',t['position'],t['id'])
    assert np.all(safe[before!=after]),'Foreign authored material changed'
    # Preserve every currently installed personnel graph cell; old unregistered
    # inspection-path treatment is a separate explicit decision/receipt.
    graph=np.load(BASE/'navigation_rebuild/combined/CURRENT_GRAPH.npz');nodes=graph['coords'][graph['kept']];checked=0
    for x,y,z in nodes:
        for fy in (y-1,y,y+1):
            if lo[0]<=x<=hi[0]and lo[1]<=fy<=hi[1]and lo[2]<=z<=hi[2]:
                checked+=1;assert before[fy-lo[1],z-lo[2],x-lo[0]]==after[fy-lo[1],z-lo[2],x-lo[0]],('Current navigation changed',x,fy,z)
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=OUT;vox.DIM='projectseele:geofront';paint=vox.Painter(vertical_bounds=(-960,320))
    count=cuboids(paint,lo,before,after,names,'R52_TV_aligned_square_corner_reservoir')
    paint.meta.update(root_author=True,waterline=-473,basin_bottom=-509,square_bounds=[[-285,34],[-31,288]],user_shore=[-30,-473,266],pyramid_preserved=True,railways_unchanged=True)
    path=paint.save_plan(STAGE)
    np.savez_compressed(path/'EXPECTED.npz',origin=lo,states=after,palette=names)
    report=dict(world_written=False,changed_cells=count,basin_side_m=254,only_waterline_corner='northwest',waterline=-473,basin_bottom=-509,whole_trees=moves,devices_preserved=len(survey['devices']),navigation_cells_preserved=checked,interface_seals=int(seals.sum()),old_walk_material_changes=int(np.sum(old_walk&(before!=after))),inspection_walk=dict(actual_old_width=5,new_floor_columns=len(walk_tops),north_feet=[-150,-482,20],east_feet=[-28,-466,131],maximum_step=max_step,north_original_approach_preserved=True,route='north_rim_then_east_rim',western_grounded_abutment_columns=foundation_columns,foundation_bottom=-510,actual_solid_datum=-511,east_beam_bounds=[[-34,-470,18],[-20,-469,142]],beam_embed_m=3),independent_source_and_route_readback_pending=True,native_art_accepted=False)
    (path/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
    fig,axes=plt.subplots(1,2,figsize=(14,10),layout='constrained')
    for ax,data,title in zip(axes,(before,after),('Actual current waterline','Candidate aligned square')):
        plane=data[-473-lo[1]];rgb=np.full((*shape2,3),(.38,.45,.33));rgb[plane==code('minecraft:water[level=0]')]=(.09,.30,.40);rgb[pyr[-473-lo[1]]]=(.12,.13,.14);rgb[plane==code('minecraft:black_concrete')]=(.15,.17,.18)
        ax.imshow(rgb,extent=[lo[0],hi[0],hi[2],lo[2]]);ax.set(title=title,xlabel='X',ylabel='Z');ax.scatter([-30],[266],color='orange',s=10)
    fig.savefig(path/'BEFORE_AFTER.png',dpi=140);plt.close(fig)
    if a.apply:
        raise RuntimeError('Not admitted: verify exact retired inspection walk and all current route/native support intersections before Root apply')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
