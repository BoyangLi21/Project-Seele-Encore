"""Offline Gora footbridge candidate; never reads or writes a live save.

Preserves native train geometry and station devices. Existing walking and the
new bridge are checked against an oriented, closed-door visible vehicle sweep.
The exported model is mathematical evidence, not live rendered acceptance.
"""
import argparse,json,math
from collections import Counter
from pathlib import Path
import nbtlib
import numpy as np
from map_pipeline.station_sections import StationSections
from audit_mountain_station_access import Nav,SupplementedSections,shape_for
from propose_mountain_station_steps import Overlay
from export_hakone_station_surface import export
from author_hakone_lakefront import Editor
from render_hakone_voxel_3d import render
from audit_hakone_station_walks import Walker
from review_underground_station_evidence import strict_walk

AIR='minecraft:air'
STONE='minecraft:stone_bricks'
SLAB='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
FLOOR='minecraft:smooth_stone'
BOX=[888,45,608,1018,72,688]
GOALS={'rail_platform':[934,56,650],'funicular_waiting':[918,56,650],
       'hall':[950,56,643],'entrance':[959,56,643],
       'street':[971,54,649],'bus_forecourt':[989,52,658]}

class Combined:
    def __init__(self,context,supplement,fresh):
        self.old=SupplementedSections(context,supplement);self.fresh=StationSections(fresh)
    def state(self,x,y,z):
        state=self.fresh.state(x,y,z)
        return self.old.state(x,y,z)if state is None else state
    def box(self,b):
        blocks,palette=self.old.box(b);fresh,names=self.fresh.box(b)
        ids={s:i for i,s in enumerate(palette)};codes=[]
        for s in names:
            if s not in ids:ids[s]=len(palette);palette.append(s)
            codes.append(ids[s])
        mask=fresh!=0;blocks[mask]=np.asarray(codes,np.uint16)[fresh[mask]]
        return blocks,palette

class TrainSweep:
    def __init__(self,snapshot,model):
        lo,hi=model['geometry_bounds']
        assert np.allclose(lo,[-1.5,.5625,-4.625]) and np.allclose(hi,[1.5,3.6875,4.625])
        self.half_width=1.5+.15;self.half_length=4.625+.15
        # Include the track underbody and a conservative vertical reserve.
        self.bottom=-.25;self.top=4.0
        points=[];tangents=[];self.curve_ids=[]
        for row in snapshot['curves']:
            p=np.asarray(row['points'],float)
            if row['mode']!='TRAIN' or not np.any((p[:,0]>BOX[0]-12)&(p[:,0]<BOX[3]+12)&(p[:,2]>BOX[2]-12)&(p[:,2]<BOX[5]+12)):continue
            self.curve_ids.append(row['id'])
            for a,b in zip(p,p[1:]):
                d=b-a;length=np.linalg.norm(d[[0,2]])
                if length<1e-8:continue
                count=math.ceil(length/.25)
                for t in np.linspace(0,1,count+1):
                    points.append(a+t*d);tangents.append(d[[0,2]]/length)
        self.p=np.asarray(points);self.t=np.asarray(tangents)
        self.n=np.column_stack((-self.t[:,1],self.t[:,0]))
        self.ax=self.half_length*np.abs(self.t[:,0])+self.half_width*np.abs(self.n[:,0])
        self.az=self.half_length*np.abs(self.t[:,1])+self.half_width*np.abs(self.n[:,1])
        self.buckets={}
        for i,(p,ax,az)in enumerate(zip(self.p,self.ax,self.az)):
            for bx in range(math.floor((p[0]-ax-1)/8),math.floor((p[0]+ax+1)/8)+1):
                for bz in range(math.floor((p[2]-az-1)/8),math.floor((p[2]+az+1)/8)+1):self.buckets.setdefault((bx,bz),[]).append(i)
        self.buckets={k:np.asarray(v,np.int32)for k,v in self.buckets.items()}
    def intersects(self,x,z,hx,hz,y,Y):
        idx=self.buckets.get((math.floor(x/8),math.floor(z/8)))
        if idx is None:return False
        p=self.p[idx];t=self.t[idx];n=self.n[idx];dx=x-p[:,0];dz=z-p[:,2]
        overlap=(y<p[:,1]+self.top-1e-7)&(Y>p[:,1]+self.bottom+1e-7)
        overlap&=(np.abs(dx)<self.ax[idx]+hx)&(np.abs(dz)<self.az[idx]+hz)
        overlap&=np.abs(dx*t[:,0]+dz*t[:,1])<self.half_length+hx*np.abs(t[:,0])+hz*np.abs(t[:,1])
        overlap&=np.abs(dx*n[:,0]+dz*n[:,1])<self.half_width+hx*np.abs(n[:,0])+hz*np.abs(n[:,1])
        return bool(overlap.any())
    def info(self):
        return dict(curve_ids=self.curve_ids,poses=len(self.p),maximum_pose_spacing=.25,
                    vehicle_visible_width=3,vehicle_visible_length=9.25,horizontal_margin=.15,
                    occupied_y_relative_to_rail=[self.bottom,self.top],model_closed_doors=True,
                    swept_shape='oriented rectangles, four separating axes versus each player/block AABB',
                    route_end_caps_included=True,current_model_and_open_doors_runtime_check_pending=True)

class SafeNav(Nav):
    def __init__(self,reader,shapes,sweep):self.sweep=sweep;super().__init__(reader,BOX,shapes,True)
    def body(self,x,y,z):
        if self.sweep.intersects(x,z,.3,.3,y,y+1.8):return {'kind':'running-train-reservation'}
        return super().body(x,y,z)

class IndependentWalker(Walker):
    def __init__(self,reader,shapes,sweep):self.reader=reader;self.shapes=shapes;self.sweep=sweep;self.cache={}
    def boxes(self,x,y,z):
        p=x,y,z
        if p not in self.cache:
            state=self.reader.state(*p)
            boxes,_=shape_for(state or'__unavailable__',self.shapes,True)
            self.cache[p]=state,boxes
        return self.cache[p]
    def body(self,x,y,z):
        if self.sweep.intersects(x,z,.3,.3,y,y+1.8):return {'kind':'running-train-reservation'}
        return super().body(x,y,z)

def bar(axis):
    return 'minecraft:iron_bars[east='+str(axis=='x').lower()+',north='+str(axis=='z').lower()+',south='+str(axis=='z').lower()+',waterlogged=false,west='+str(axis=='x').lower()+']'

def design(reader,shapes):
    proposed={};purpose={};supports=[];deck=[]
    def get(x,y,z):return proposed.get((x,y,z),reader.state(x,y,z))
    def put(x,y,z,state,why):
        original=reader.state(x,y,z)
        if original is None:raise ValueError('Uncaptured construction cell '+str((x,y,z)))
        if original==state:proposed.pop((x,y,z),None);purpose.pop((x,y,z),None)
        else:proposed[x,y,z]=state;purpose[x,y,z]=why
    def fill_to(x,z,top):
        bearing=reader.state(x,55,z);bs,_=shape_for(bearing,shapes,True)
        if bs!=[[0.,0.,0.,1.,1.,1.]]:raise ValueError('Unverified existing foundation '+str((x,z,bearing)))
        supports.append(dict(x=x,z=z,base_y=55,base_state=bearing,top_y=top))
        for y in range(56,top+1):
            state=get(x,y,z)
            if state==AIR:put(x,y,z,STONE,'continuous-supported-stair-or-abutment')
            elif state not in (STONE,'minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:dark_oak_log[axis=y]'):
                raise ValueError('Existing component would be covered '+str((x,y,z,state)))
    # Both flights climb north, inside existing paved station space. The west
    # flight is west of the marked road, and north of the funicular connection.
    for lo in (914,934):
        for z in range(636,651):
            feet=56+(650-z)/2;top=math.ceil(feet)-1
            for x in range(lo,lo+3):
                fill_to(x,z,math.floor(feet)-1)
                if feet%1:
                    state=get(x,top,z)
                    if state not in (AIR,'minecraft:light_gray_concrete'):raise ValueError('Unexpected half tread '+str((x,top,z,state)))
                    put(x,top,z,SLAB,'half-step-tread')
                # Remove only measured canopy material in the required headroom.
                # The next half-step lifts the player before horizontal motion.
                # Keep that transition headroom over this tread as well.
                for y in range(math.ceil(feet),math.ceil(feet+2.3)):
                    state=get(x,y,z)
                    if state in ('minecraft:light_gray_concrete','minecraft:gray_concrete'):put(x,y,z,AIR,'canopy-opening-for-stair-headroom')
                    elif state!=AIR:raise ValueError('Existing non-canopy obstruction '+str((x,y,z,state)))
                deck.append((x,feet,z))
            # Side cappings keep iron guards supported also at half-level rows.
            if z<649 and z>636:
                for x in (lo,lo+2):
                    if feet%1:put(x,math.floor(feet),z,STONE,'solid-side-capping-under-guard')
                    put(x,math.ceil(feet),z,bar('z'),'stair-guard')
        for z in (634,635):
            for x in range(lo,lo+3):fill_to(x,z,62)
    # Deep transverse girders rest on two complete three-wide masonry abutments.
    # The roadway and operational rail beneath remain open, with no central pier.
    for x in range(914,937):
        for z in range(634,637):
            for y in (60,61):
                if 917<=x<=933:
                    state=get(x,y,z)
                    if state==AIR:put(x,y,z,'minecraft:iron_block','two-block-deep-bridge-girder')
                    elif state!='minecraft:light_gray_concrete':raise ValueError('Unexpected bridge soffit '+str((x,y,z,state)))
            if get(x,62,z)==AIR:put(x,62,z,FLOOR,'bridge-deck')
            elif get(x,62,z)!=STONE:raise ValueError('Bridge deck collision')
            deck.append((x,63,z))
    for x in range(914,937):
        for z in (634,636):
            if z==636 and(x in range(914,917)or x in range(934,937)):continue
            put(x,63,z,bar('x'),'bridge-edge-guard')
    # Close the two outer side edges of the landings without blocking the mouths.
    for x in(914,936):
        put(x,63,635,bar('z'),'bridge-end-guard')
    # Set every actual planar railing connection, including bridge corners.
    for (x,y,z),state in list(proposed.items()):
        if not state.startswith('minecraft:iron_bars'):continue
        props=[]
        for name,dx,dz in [('east',1,0),('north',0,-1),('south',0,1),('west',-1,0)]:
            other=get(x+dx,y,z+dz)
            props.append((name,str(other.startswith('minecraft:iron_bars')).lower()))
        props.append(('waterlogged','false'))
        put(x,y,z,'minecraft:iron_bars['+','.join(k+'='+v for k,v in sorted(props))+']',purpose[x,y,z])
    changes=[dict(pos=list(p),before=reader.state(*p),after=s,purpose=purpose[p])for p,s in sorted(proposed.items())]
    return changes,supports,deck

def section(reader,changes,sweep,shapes,out):
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(1600,1050),'#f3f4f0');d=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',22);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
    positions={tuple(q['pos'])for q in changes};panels=[('跨线桥：Z=635.5',0,635.5,910,938,52,67),('西侧半级楼梯：X=915.5',2,915.5,632,653,53,67)]
    for j,(title,axis,fixed,lo,hi,low,high)in enumerate(panels):
        ox=65;oy=490+j*510;scale=min(1470/(hi-lo),420/(high-low))
        d.text((30,j*510+15),title,fill='#223c33',font=font)
        for h in range(lo,hi):
            for y in range(low,high):
                x,z=(h,math.floor(fixed))if axis==0 else(math.floor(fixed),h)
                state=reader.state(x,y,z)
                boxes,_=shape_for(state or'__unavailable__',shapes,True)
                if boxes is None:continue
                for b in boxes:
                    k=2 if axis==0 else 0
                    if not b[k]<=fixed-math.floor(fixed)<b[k+3]:continue
                    colour='#3a92b5'if(x,y,z)in positions else'#abb0a5'
                    d.rectangle((ox+(h+b[axis]-lo)*scale,oy-(y+b[4]-low)*scale,ox+(h+b[axis+3]-lo)*scale,oy-(y+b[1]-low)*scale),fill=colour,outline='#59685c')
        if axis==0:
            # Exact straight-mainline vehicle and conservative vertical envelope.
            d.rectangle((ox+(929-lo)*scale,oy-(58.6875-low)*scale,ox+(932-lo)*scale,oy-(55.5625-low)*scale),fill='#d99473',outline='#864929',width=2)
            d.text((ox+(927-lo)*scale,oy-(59.8-low)*scale),'静态车体顶 58.6875 / 桥底 60',fill='#864929',font=small)
        for y in range(low,high+1):d.text((ox-35,oy-(y-low)*scale-9),str(y),fill='#435d50',font=small)
        for h in range(lo,hi+1,2):d.text((ox+(h-lo)*scale-12,oy+8),str(h),fill='#435d50',font=small)
    im.save(out)

def run(a):
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    source=Combined(a.context,a.context_supplement,a.source)
    sweep=TrainSweep(json.loads(a.native.read_text('utf8')),json.loads(a.model.read_text('utf8')))
    before=SafeNav(source,shapes,sweep);old_routes,old_count=before.routes(GOALS,'rail_platform')
    print('Existing visible-width-safe goals:',[(r['name'],r['reachable'])for r in old_routes],flush=True)
    if next(r['reachable']for r in old_routes if r['name']=='funicular_waiting'):raise ValueError('Existing safe route found; do not construct')
    changes,supports,deck=design(source,shapes);after=Overlay(source,changes)
    nav=SafeNav(after,shapes,sweep);new_routes,new_count=nav.routes(GOALS,'rail_platform')
    errors=[]
    if not all(r['reachable']for r in new_routes):errors.append('Not all station goals reachable')
    intrusion=[];unknown=[]
    for row in changes:
        if row['after']==AIR:continue
        x,y,z=row['pos'];boxes,_=shape_for(row['after'],shapes,True)
        if boxes is None:unknown.append(row);continue
        for b in boxes:
            if sweep.intersects(x+(b[0]+b[3])/2,z+(b[2]+b[5])/2,(b[3]-b[0])/2,(b[5]-b[2])/2,y+b[1],y+b[4]):intrusion.append(row);break
    if intrusion:errors.append('New structure intersects vehicle sweep')
    if unknown:errors.append('New collision shape unknown')
    unsupported=[]
    for row in supports:
        for y in range(56,row['top_y']+1):
            bs,_=shape_for(after.state(row['x'],y,row['z']),shapes,True)
            if bs!=[[0.,0.,0.,1.,1.,1.]]:unsupported.append([row['x'],y,row['z']])
    if unsupported:errors.append('Discontinuous masonry support')
    # Exact reverse sweeps confirm every selected route edge is bidirectionally usable.
    reverse_failures=[]
    for row in new_routes:
        path=row['path']
        for p,q in zip(path,path[1:]):
            n=(int(p[0]-.5),round(p[1]*2),int(p[2]-.5));m=(int(q[0]-.5),round(q[1]*2),int(q[2]-.5))
            if not nav.edge(n,m)or not nav.edge(m,n):reverse_failures.append([n,m])
    if reverse_failures:errors.append('Reverse path sweep failed')
    independent=[]
    walker=IndependentWalker(after,shapes,sweep)
    for row in new_routes:
        if not row['path']:continue
        proofs={d:strict_walk(walker,row['path']if d=='forward'else list(reversed(row['path'])))for d in('forward','reverse')}
        if any(q['kind']!='strict_static_clear'for q in proofs.values()):errors.append('Independent path sampling failed: '+row['name'])
        independent.append(dict(goal=row['name'],**proofs))
    negative=[]
    for label,patch,route in[
        ('bridge-floor-removed',[dict(pos=[925,62,635],after=AIR)],[[925.5,63,635.5]]),
        ('bridge-headroom-blocked',[dict(pos=[925,64,635],after=STONE)],[[925.5,63,635.5]])]:
        proof=strict_walk(IndependentWalker(Overlay(after,patch),shapes,sweep),route)
        negative.append(dict(case=label,result=proof,rejected=proof['kind']!='strict_static_clear'))
        if proof['kind']=='strict_static_clear':errors.append('Injected fault not detected')
    # The east flight uses one old asphalt-edge column. The measured remaining
    # service lane is three blocks wide; prove both its bearing and 3.5m headroom.
    road_issues=[]
    for z in range(634,651):
        for x in range(937,940):
            boxes,_=shape_for(after.state(x,55,z),shapes,True)
            if boxes!=[[0.,0.,0.,1.,1.,1.]]:road_issues.append(dict(pos=[x,55,z],kind='road-bearing'))
            for y in range(56,60):
                boxes,_=shape_for(after.state(x,y,z),shapes,True)
                if boxes is None or any(y+b[1]<59.5 and y+b[4]>56 for b in boxes):road_issues.append(dict(pos=[x,y,z],kind='road-clearance'))
    if road_issues:errors.append('Retained east service lane blocked')
    export(a.source,[912,624,943,655],a.out)
    capture=json.loads((a.out/'capture.json').read_text('utf8'))
    protected={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']}
    if any(tuple(r['pos'])in protected for r in changes):raise ValueError('Protected block entity intersects design')
    e=Editor(a.out)
    for row in changes:
        if e.state(*row['pos'])!=row['before']:raise ValueError('Source before mismatch')
        e.put(*row['pos'],row['after'])
    regions=e.save()
    assert sum(r['cells']for r in regions)==len(changes)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'block-entities.dat',gzipped=True)
    report=dict(errors=errors,train_reservation=sweep.info(),before_routes=old_routes,after_routes=new_routes,
        before_reachable_nodes=old_count,after_reachable_nodes=new_count,changed_cells=len(changes),
        existing_solid_changes=[r for r in changes if r['before']!=AIR],new_structure_train_intrusions=intrusion,
        unknown_new_collision_shapes=unknown,continuous_foundations=supports,unsupported_cells=unsupported,
        reverse_sweep_failures=reverse_failures,independent_path_sampling=independent,negative_tests=negative,
        retained_service_lane=dict(bounds=[937,55,634,939,59,650],width=3,clear_height=3.5,issues=road_issues),
        maximum_required_step=.5,
        bridge_soffit_y=60,main_rail_y=55,visible_train_top_y=58.6875,visible_vehicle_to_soffit_gap=1.3125,
        central_piers=0,abutments_x=[[914,916],[934,936]],girder_depth=2,girder_clear_span=17,
        preserved_devices=len(protected),preserved_actors=len(capture['actors']),
        original_posts_and_walls_unchanged=True,existing_ground_paving_unchanged=True,
        ordinary_doors_assumed_open=True,native_gate_bypass=False,native_changes=0,world_written=False,
        installed=False,current_collision_export_pending=True,live_passenger_and_open_door_validation_pending=True)
    manifest=dict(world=capture['world'],kind='gora-protected-station-transfer-footbridge',bounds_xz=capture['bounds_xz'],
        bounds_3d=[914,56,634,936,63,649],regions=regions,cells=len(changes),changed_chunks=[[57,39],[57,40],[58,39],[58,40]],
        device_changes=0,actor_changes=0,native_changes=0,world_written=False,production_recipe_replay_pending=True,
        source_snapshot=str(a.source),functional_errors=errors)
    for name,data in [('functional-check.json',report),('manifest.json',manifest),('changes.json',changes)]:
        (a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    print('Candidate:',len(changes),'cells; after safe goals',[(r['name'],r['reachable'])for r in new_routes],'; errors',errors,flush=True)
    views=[]
    for phase,reader in [('before',source),('after',after)]:views.append(render(reader,[909,53,630,940,68,657],a.out/'views'/(phase+'.png'),'强罗·跨线安全换乘 '+phase))
    (a.out/'views.json').write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8')
    section(after,changes,sweep,shapes,a.out/'collision-sections.png')
    if errors:raise ValueError('Candidate needs revision; not ready for installation')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('source','context','context-supplement','native','model','metadata','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
