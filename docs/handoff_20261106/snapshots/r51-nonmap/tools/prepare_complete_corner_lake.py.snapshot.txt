"""Root's single-corner engineered reservoir, exact candidate only by default.

The complete measured pyramid ownership volume is immutable. The co-oriented
square leaves the compact first launch bank on land and contains a finite
portion of both faces adjoining the southwest corner.
"""
from pathlib import Path
import argparse
import json
import msvcrt
import numpy as np
from scipy.ndimage import binary_dilation,distance_transform_edt,label,generate_binary_structure
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--rail-ownership',type=Path,required=True)
    ap.add_argument('--survey',type=Path,required=True);ap.add_argument('--rail-retirement-receipt',type=Path);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    base=args.base.resolve();world=base/'WORLD';out=base/'southwest_square_lake';out.mkdir(exist_ok=True)
    data=np.load(args.survey);before=data['states'];lo=data['origin'];names=list(map(str,data['palette']))
    hi=lo+np.asarray(before.shape)[[2,0,1]]-1;ids={s:i for i,s in enumerate(names)}
    def code(s):
        if s not in ids:ids[s]=len(names);names.append(s)
        return ids[s]
    air=code('minecraft:air');water=code('minecraft:water[level=0]');stone=code('minecraft:stone');dirt=code('minecraft:dirt');grass=code('minecraft:grass_block[snowy=false]')
    shell=code('minecraft:black_concrete');paving=code('projectseele:nerv_floor_panel');edge=code('projectseele:nerv_machine_edge');lamp=code('projectseele:nerv_strip_light[lit=true]')
    y,z,x=np.ogrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1,lo[0]:hi[0]+1]
    # User confirmed two co-oriented squares, southwest corner, and bank 1
    # remaining on its original vertical axis. Relative rotation is forbidden.
    u=x;v=z;U=6;V=623
    inside2=np.broadcast_to(((u>=U-275)&(u<=U)&(v>=V-275)&(v<=V))[0],before.shape[1:])
    dist_inside=np.minimum.reduce([np.broadcast_to((u-(U-275))[0],inside2.shape),np.broadcast_to((U-u)[0],inside2.shape),np.broadcast_to((v-(V-275))[0],inside2.shape),np.broadcast_to((V-v)[0],inside2.shape)])
    outside=np.maximum(-dist_inside,0);rim2=(outside<=8)&~inside2
    grading2=outside<=20
    floor2=(-473-np.minimum(50,24+np.maximum(0,np.floor(dist_inside*1.2)))).astype(int)
    source=np.load(base/'survey/headquarters_and_original_station.npz');owned=np.load(base/'pyramid_component/owner_mask.npz')['owned']
    so=source['origin']+np.array([0,-93,0]);protected=np.zeros(before.shape,bool)
    al=np.maximum(lo,so);ah=np.minimum(hi+1,so+np.asarray(owned.shape)[[2,0,1]])
    def sl(a,b,o):return np.s_[a[1]-o[1]:b[1]-o[1],a[2]-o[2]:b[2]-o[2],a[0]-o[0]:b[0]-o[0]]
    protected[sl(al,ah,lo)]=owned[sl(al,ah,so)]
    station=np.load(base/'hq_station_component/SOURCE.npz');station_owner=np.load(base/'hq_station_component/OWNERSHIP.npz')['owned']
    sto=station['origin']+np.array([0,-93,0]);sa=np.maximum(lo,sto);sb=np.minimum(hi+1,sto+np.asarray(station_owner.shape)[[2,0,1]])
    protected[sl(sa,sb,lo)] |= station_owner[sl(sa,sb,sto)]
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:water','minecraft:tuff','minecraft:gravel','minecraft:sand','minecraft:clay','minecraft:coarse_dirt','minecraft:podzol','minecraft:grass','minecraft:fern','minecraft:azure_bluet','minecraft:poppy','minecraft:dandelion'}
    allowed=np.isin(before,[i for i,n in enumerate(names) if n.split('[')[0] in natural])
    old_walk=np.broadcast_to((x>=-153)&(x<=-28)&(z>=29)&(z<=133)&(y>=-484)&(y<=-467),before.shape)&(before==code('minecraft:smooth_stone'))&~protected
    allowed|=old_walk
    original_stem=np.broadcast_to((x>=-152)&(x<=-148)&(z<=28)&(y>=-484)&(y<=-475),before.shape)&(before==code('minecraft:smooth_stone'))
    allowed|=original_stem
    rail_rows=json.loads(args.rail_ownership.read_text('utf8'));retired_rail=np.zeros(before.shape,bool)
    for row in rail_rows:
        xx,yy,zz=row['pos'];ix,iy,iz=xx-lo[0],yy-lo[1],zz-lo[2]
        if not (0<=iy<before.shape[0] and 0<=iz<before.shape[1] and 0<=ix<before.shape[2]):continue
        if names[int(before[iy,iz,ix])]==row['state']:
            assert not protected[iy,iz,ix]
            allowed[iy,iz,ix]=True;retired_rail[iy,iz,ix]=True
        else:assert allowed[iy,iz,ix],'Retired track cell changed to another authored component'
    vegetation=np.isin(before,[i for i,n in enumerate(names) if n.split('[')[0].endswith(('_log','_leaves'))])
    components,total=label(vegetation,generate_binary_structure(3,1))
    tree_ids=np.unique(components[:,inside2|rim2]);tree_ids=tree_ids[tree_ids!=0]
    tree_retire=np.isin(components,tree_ids)&vegetation
    assert not any((tree_retire[0].any(),tree_retire[-1].any(),tree_retire[:,0].any(),tree_retire[:,-1].any(),tree_retire[:,:,0].any(),tree_retire[:,:,-1].any())),'Whole tree extends beyond survey'
    assert not (tree_retire&protected).any()
    allowed|=tree_retire
    original_trees=[]
    for k in tree_ids:
        loc=np.argwhere(components==k);values=before[tuple(loc.T)]
        logs=np.array([names[int(v)].split('[')[0].endswith('_log') for v in values])
        original_trees.append((int(k),loc[:,[2,0,1]]+lo,values,logs))
    del components
    # The blend margin contains the retained first-bank shell and the edge
    # of a whole original tree. Preserve their columns, including empty cells.
    grading2 &= ~np.any(~allowed&~protected,axis=0)
    soil=np.isin(before,[i for i,n in enumerate(names) if n.split('[')[0] in {'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:tuff','minecraft:gravel','minecraft:sand'}])
    ground=np.max(np.where(soil,y,-9999),axis=0)
    missing=ground<-1000
    if missing.any():
        nearest=distance_transform_edt(missing,return_distances=False,return_indices=True)
        ground[missing]=ground[tuple(nearest[:,missing])]
    # A shallow basin liner grants no right to replace the station/tunnels
    # farther below it. Embankments only fill to their actual soil bearing.
    basin_edit=inside2[None,:,:]&(y>=floor2[None,:,:]-2)&(y<=-452)
    rim_edit=rim2[None,:,:]&(y>=np.minimum(-468,ground)[None,:,:]-3)&(y<=-452)
    active=np.broadcast_to(basin_edit|rim_edit,before.shape)&~protected
    if not allowed[active].all():
        q=np.argwhere(active&~allowed)
        rows=[dict(pos=(p[[2,0,1]]+lo).tolist(),state=names[int(before[tuple(p)])]) for p in q]
        (out/'CURRENT_UNKNOWN_COMPONENTS.json').write_text(json.dumps(rows,indent=2),'utf8')
        print(json.dumps(dict(unknown_cells=len(rows),bounds=[np.min(q[:,[2,0,1]]+lo,axis=0).tolist(),np.max(q[:,[2,0,1]]+lo,axis=0).tolist()],sample=rows[:10])),flush=True)
    assert allowed[active].all(),('Unknown component in explicit basin domain',{names[int(i)] for i in np.unique(before[active&~allowed])})
    # The original nearby natural lake is a complete measured component.
    # Restore its former bowl to rolling dry ground before making the distant
    # natural lake. Keeping fragments beside this basin would make a third lake.
    old_r=(((x+310)/310.)**2+((z-340)/200.)**2+.075*np.sin((x+z)/47.)+.045*np.cos(z/37.))[0]
    reclaim2=(old_r<1.3)&~inside2&~rim2
    trees=np.any(vegetation&~tree_retire,axis=0)
    authored_columns=np.any(~allowed&~protected,axis=0)&~trees
    raw_ground=-478+3.5*np.sin(x/137)*np.cos(z/193)+2.4*np.sin((x+z)/67)
    for gx,gz,h,r in ((420,830,29,310),(-230,1030,17,390),(720,330,11,290)):
        raw_ground+=h*np.exp(-((x-gx)**2+(z-gz)**2)/(r*r))
    def smooth(q):q=np.clip(q,0,1);return q*q*(3-2*q)
    campus=1-smooth(np.hypot(np.maximum(np.maximum(-90-x,x-160),0),np.maximum(np.maximum(96-z,z-447),0))/64)
    raw_ground=(raw_ground*(1-campus)-467*campus)[0]
    blend_edge=smooth((old_r-1.05)/.25)
    restored_ground=np.floor(raw_ground*(1-blend_edge)+ground*blend_edge+.5).astype(int)
    preserve_distance=distance_transform_edt(~(trees|authored_columns))
    preserve_blend=smooth(preserve_distance/12)
    restored_ground=np.floor(restored_ground*preserve_blend+ground*(1-preserve_blend)+.5).astype(int)
    reclaim2 &= ~authored_columns&~trees
    desired_ground=np.where(reclaim2,restored_ground,ground)
    blend=np.clip((outside-8)/12,0,1);blend=blend*blend*(3-2*blend)
    terrain=np.floor(-468*(1-blend)+desired_ground*blend+.5).astype(int)
    after=before.copy();after[tree_retire]=air
    for iy,wy in enumerate(range(int(lo[1]),int(hi[1])+1)):
        editable=allowed[iy]&~protected[iy]
        retiring=old_walk[iy]&~inside2
        restored=np.where(wy>ground,air,np.where(wy==ground,grass,np.where(wy>=ground-3,dirt,stone)))
        after[iy,retiring]=restored[retiring]
        if wy<-555:continue
        reclaimed=reclaim2&editable
        desired=np.where(wy>restored_ground,air,np.where(wy==restored_ground,grass,np.where(wy>=restored_ground-3,dirt,stone)))
        after[iy,reclaimed]=desired[reclaimed]
        drain=(old_r<1.3)&~inside2&(before[iy]==water)&~protected[iy]&~authored_columns
        after[iy,drain]=desired[drain]
        land=grading2&~inside2&editable&(wy>=np.minimum(terrain,ground)-3)
        desired=np.where(wy>terrain,air,np.where(wy==terrain,grass,np.where(wy>=terrain-3,dirt,stone)))
        after[iy,land]=desired[land]
        wet=inside2&editable&(wy>=floor2-2)
        desired=np.where(wy>-473,air,np.where(wy>floor2,water,np.where(wy>=floor2-2,shell,stone)))
        after[iy,wet]=desired[wet]
        rim=rim2&editable&(wy>=np.minimum(-468,ground)-3)
        if wy>-468:after[iy,rim]=air
        if wy==-468:after[iy,rim]=paving
        if wy==-469:
            stripes=rim&(((np.floor((u[0]-U)/24).astype(int)%2==0)&(outside<1.5)))
            after[iy,stripes]=lamp
    # Exact basin-side seals prevent fluids entering retained rooms. This is
    # an external liner; never write a cell of the original pyramid volume.
    air_ids=[i for i,n in enumerate(names) if n in ('minecraft:air','minecraft:cave_air','minecraft:void_air')]
    seals=np.zeros(before.shape,bool)
    for dy,dz,dx in ((0,0,1),(0,0,-1),(0,1,0),(0,-1,0),(-1,0,0)):
        aa=tuple(slice(max(0,-q),min(n,n-q)) for n,q in zip(after.shape,(dy,dz,dx)))
        bb=tuple(slice(max(0,q),min(n,n+q)) for n,q in zip(after.shape,(dy,dz,dx)))
        leak=(after[aa]==water)&np.isin(after[bb],air_ids)&np.broadcast_to(inside2[None,:,:],after.shape)[aa]&~protected[aa]
        bad=leak&~protected[bb]
        if bad.any():
            offset=np.array([max(0,-dy),max(0,-dz),max(0,-dx)])
            positions=(np.argwhere(bad)+offset)[:,[2,0,1]]+lo
            raise AssertionError(('Basin shell has an unclassified open face',(dy,dz,dx),len(positions),positions[:12].tolist()))
        seals[aa]|=leak
    assert not (seals&protected).any()
    after[seals]=shell
    # Retire only the old inspection L and reconnect its original northern
    # stem to the existing campus south of the new first-bank surface apron.
    path=[(-150,-482,28),(-150,-481,10),(-72,-474,-2),(-50,-469,72),(-39,-467,124),(-26,-466,161)]
    walk={}
    for p,q in zip(path,path[1:]):
        p=np.asarray(p,float);q=np.asarray(q,float)
        for t in np.linspace(0,1,int(np.linalg.norm((q-p)[[0,2]])*4)+2):
            centre=p*(1-t)+q*t
            for xx in range(round(centre[0])-2,round(centre[0])+3):
                for zz in range(round(centre[2])-2,round(centre[2])+3):
                    walk[xx,zz]=round(float(centre[1])*2)/2
    walk_block=code('minecraft:smooth_stone');slab=code('minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    for (xx,zz),foot in walk.items():
        ix,iz=xx-lo[0],zz-lo[2];fy=int(np.floor(foot)) if foot%1 else int(foot)-1
        assert not inside2[iz,ix],('Inspection route cuts water',xx,zz)
        for yy in range(min(fy-2,int(ground[iz,ix])),int(np.ceil(foot))+4):
            iy=yy-lo[1]
            assert not protected[iy,iz,ix] and allowed[iy,iz,ix],('Unowned inspection interface',xx,yy,zz,names[int(before[iy,iz,ix])])
            after[iy,iz,ix]=stone if yy<fy else (slab if foot%1 else walk_block) if yy==fy else air
    guards=0
    gi=-467-lo[1]
    for iz,ix in np.argwhere(rim2&~protected[gi]&~protected[gi-1]):
        sides={}
        for name,dz,dx in (('north',-1,0),('east',0,1),('south',1,0),('west',0,-1)):
            zz,xx=iz+dz,ix+dx
            sides[name]=0<=zz<inside2.shape[0] and 0<=xx<inside2.shape[1] and bool(inside2[zz,xx])
        if not any(sides.values()):continue
        assert after[gi-1,iz,ix]==paving and after[gi,iz,ix]==air,('Rim rail lacks its own continuous bearing',int(ix+lo[0]),int(iz+lo[2]),names[int(after[gi-1,iz,ix])],names[int(after[gi,iz,ix])])
        state='projectseele:nerv_edge_rail['+','.join(f'{n}={str(sides[n]).lower()}' for n in sorted(sides))+']'
        after[gi,iz,ix]=code(state);guards+=1
    for dy,dz,dx in ((0,0,1),(0,0,-1),(0,1,0),(0,-1,0),(-1,0,0)):
        aa=tuple(slice(max(0,-q),min(n,n-q)) for n,q in zip(after.shape,(dy,dz,dx)))
        bb=tuple(slice(max(0,q),min(n,n+q)) for n,q in zip(after.shape,(dy,dz,dx)))
        leak=(after[aa]==water)&np.isin(after[bb],air_ids)&np.broadcast_to(inside2[None,:,:],after.shape)[aa]&~protected[aa]
        assert not leak.any(),'Final walk or guard stage reopened the basin liner'
    assert np.array_equal(before[protected],after[protected])
    # Reuse complete original crowns and trunks in an explicit grove in the
    # reclaimed old lake meadow. Tiny pre-existing stump/crown fragments are
    # retired whole; they are not replanted as floating or headless trees.
    transplants=[];fragments=[];occupied=np.zeros(inside2.shape,bool)
    grove_rng=np.random.default_rng(531013)
    meadow_candidates=[(xx+int(grove_rng.integers(-8,9)),zz+int(grove_rng.integers(-8,9)))
        for zz in range(180,331,28) for xx in range(-558,-249,28)]
    grove_rng.shuffle(meadow_candidates)
    for component,positions,values,logs in original_trees:
        if int(logs.sum())<5 or len(positions)<150:
            fragments.append(dict(component=component,cells=len(positions),logs=int(logs.sum()),reason='pre-existing disconnected vegetation fragment'))
            continue
        root_y=int(positions[logs,1].min());base_logs=positions[logs&(positions[:,1]==root_y)]
        anchor=base_logs[0];placed=False
        for tx,tz in meadow_candidates:
            ix,iz=tx-lo[0],tz-lo[2]
            if not reclaim2[iz,ix] or occupied[iz,ix]:continue
            floor=int(restored_ground[iz,ix]);offset=np.array([tx-anchor[0],floor+1-root_y,tz-anchor[2]])
            target=positions+offset
            aa=target.min(0);bb=target.max(0)
            if (aa<lo).any() or (bb>hi).any():continue
            x0,z0=aa[[0,2]]-lo[[0,2]]-3;x1,z1=bb[[0,2]]-lo[[0,2]]+4
            if occupied[z0:z1,x0:x1].any() or not reclaim2[z0:z1,x0:x1].all():continue
            ijk=(target-lo)[:,[1,2,0]]
            if not np.all(after[tuple(ijk.T)]==air):continue
            if protected[:,z0:z1,x0:x1].any() or not allowed[:,z0:z1,x0:x1].all():continue
            # Native root bearings remain real soil, never floating trunks.
            for root in base_logs+offset:
                rx,rz=root[[0,2]]-lo[[0,2]]
                for yy in range(int(restored_ground[rz,rx])-2,int(root[1])):
                    after[yy-lo[1],rz,rx]=grass if yy==root[1]-1 else dirt
            after[tuple(ijk.T)]=values
            assert np.array_equal(after[tuple(ijk.T)],values)
            occupied[z0:z1,x0:x1]=True;placed=True
            transplants.append(dict(component=component,cells=len(positions),offset=offset.tolist(),source_bounds=[positions.min(0).tolist(),positions.max(0).tolist()],destination_bounds=[aa.tolist(),bb.tolist()]))
            break
        assert placed,('No exact rooted meadow placement for whole original tree',component)
    assert allowed[before!=after].all()
    old_water_outside=np.isin(after,[i for i,n in enumerate(names) if n.startswith('minecraft:water[')])&np.broadcast_to(((old_r<1.3)&~inside2)[None,:,:],after.shape)&~protected
    assert not old_water_outside.any(),'Old lake source water remains beside the new reservoir'
    survey.WORLD=extension.WORLD=world
    for (xx,yy,zz),tag in iter_block_entities(world,'projectseele:geofront',tuple(lo),tuple(hi)):
        assert before[yy-lo[1],zz-lo[2],xx-lo[0]]==after[yy-lo[1],zz-lo[2],xx-lo[0]],('Original device altered',xx,yy,zz,str(tag['id']))
    # Geometric role checks use the actual preserved ownership slice.
    iy=-473-lo[1];body=protected[iy]
    bxz=np.argwhere(body)[:,[1,0]]+lo[[0,2]]
    waterline_shell=[(-31,266),(91,266),(-31,388),(91,388)]
    corner_inside=[bool(inside2[zz-lo[2],xx-lo[0]]) if lo[0]<=xx<=hi[0] and lo[2]<=zz<=hi[2] else False for xx,zz in waterline_shell]
    assert corner_inside==[False,False,True,False]
    apron=(x[0]>=-34)&(x[0]<=96)&(z[0]>=100)&(z[0]<=149)
    assert not np.any((inside2|rim2)&np.broadcast_to(apron,inside2.shape)),'Lake/rim overlaps first-bank apron'
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';paint=vox.Painter(vertical_bounds=(-1344,320))
    changed=cuboids(paint,tuple(lo),before,after,names,'user_confirmed_southwest_square_reservoir_and_inspection_walk')
    report=dict(world_written=False,playable=False,changed_cells=changed,square_side=275,rotation_degrees=0,corner='southwest',
        water_y=-473,rim_floor_y=-468,max_floor_y=-523,corner_inside=corner_inside,preserved_pyramid_and_station_cells=int(protected.sum()),
        external_seal_cells=int(seals.sum()),retired_old_inspection_cells=int(old_walk.sum()),replacement_walk=path,
        reclaimed_old_lake_columns=int(reclaim2.sum()),original_whole_trees_transplanted=transplants,retired_original_tree_fragments=fragments,
        retired_rail_cells_in_survey=int(retired_rail.sum()),rail_ownership=str(args.rail_ownership),
        bearing_verified_inner_rim_guards=guards,native_fluid_review_pending=True,native_visual_review_pending=True)
    paint.meta.update(report,root_author=True)
    folder=paint.save_plan('cooriented_southwest_square_reservoir')
    np.savez_compressed(folder/'EXACT_BEFORE_AFTER.npz',origin=lo,palette=names,before=before,after=after,positive_edit_mask=before!=after,protected=protected)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(14,7),layout='constrained')
    for ax,arr,title in zip(axes,(before,after),('Measured construction: waterline Y=-473','User-confirmed co-oriented square: SW corner')):
        layer=arr[-473-lo[1]];rgb=np.full((*layer.shape,3),[.45,.49,.40])
        rgb[layer==water]=[.10,.42,.52];rgb[layer==shell]=[.20,.23,.25];rgb[body]=[.09,.12,.14]
        ax.imshow(rgb,extent=[lo[0],hi[0]+1,hi[2]+1,lo[2]],interpolation='nearest')
        ax.contour(np.arange(lo[0],hi[0]+1),np.arange(lo[2],hi[2]+1),rim2,levels=[.5],colors=['#c8cdd0'],linewidths=.8)
        ax.plot([p[0] for p in path],[p[2] for p in path],color='#d6b975',lw=1.5,label='Inspection walk')
        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((-34,100),130,49,fill=False,edgecolor='#d06b53',lw=1.5,label='Bank 1 apron'))
        ax.set(title=title,xlabel='X',ylabel='Z / north upward');ax.set_aspect('equal');ax.legend(fontsize=8)
    fig.savefig(folder/'WATERLINE_PLAN.png',dpi=140);plt.close(fig)
    print(json.dumps({k:v for k,v in report.items() if k not in ('original_whole_trees_transplanted','retired_original_tree_fragments')}
        |dict(transplanted_whole_tree_components=len(transplants),retired_fragment_components=len(fragments))),flush=True)
    if args.apply:
        assert args.rail_retirement_receipt is not None and json.loads(args.rail_retirement_receipt.read_text('utf8'))['world_written'],'Apply complete original rail retirement before landscaping'
        assert not list(folder.glob('applied_*'))
        actual,pal=survey.measure(tuple(lo),tuple(hi));assert np.array_equal(np.asarray([ids[n] for n in pal],np.uint16)[actual],before)
        lock=extension.acquire_world_lock()
        try:
            report['receipt']=paint.apply('cooriented_southwest_square_reservoir',session_lock=lock)
            report.update(world_written=True,whole_difference_readback=True)
            (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
