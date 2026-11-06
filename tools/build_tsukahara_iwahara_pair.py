"""Author two finite diagonal stations and one clear-span pedestrian access."""
import argparse,copy,json,math,shutil
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
import nbtlib
from shapely.geometry import Point,LineString,box,shape
from shapely.ops import unary_union
from shapely.prepared import prep
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR
from prepare_hakone_city_cross import packed
from evaluate_tsukahara_iwahara_geometry import envelope,point

ALLOWED=SOIL|AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=lambda x:x.item()),'utf8')

def main(a):
    a.out.mkdir(exist_ok=False);shutil.copytree(a.source/'source',a.out/'source');(a.out/'delta').mkdir()
    for name in('capture.json','measured.npz','captured-devices.dat'):shutil.copy2(a.source/name,a.out/name)
    capture=json.loads((a.source/'capture.json').read_text('utf8'));x0,z0,X,Z=capture['bounds_xz'];e=Editor(a.out)
    top=np.load(a.source/'measured.npz')['top'];devices={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.source/'captured-devices.dat')['Devices']}
    with np.load(a.authority/'network.npz')as f:
        ax,az,*_=f['bounds'];public=f['walk'][z0-az:Z-az+1,x0-ax:X-ax+1];oldgrade=f['grade2'][z0-az:Z-az+1,x0-ax:X-ax+1]
    evidence=json.loads((a.geometry/'site-evidence.json').read_text('utf8'));edges=json.loads(a.edges.read_text('utf8'));v=next(v for v in edges['variants']if v['variant']==a.variant)
    access=json.loads(a.access.read_text('utf8'))
    if any(not p['path_xz']for p in access['paths']):raise ValueError('Missing real street approach')
    samples={s['id']:s for s in json.loads((a.geometry/'native-samples.json').read_text('utf8'))};native={r['id']:r for r in json.loads((a.geometry/'native-input.json').read_text('utf8'))['segments']}
    features={f['index']:f for s in evidence['stations']for f in s['nearby_gis']};water=unary_union([shape(f['geometry'])for f in features.values()if f['properties']['source_layer']in('WA','RvrCL','WStrL')]).buffer(3);wet_query=prep(water)
    complete_line=LineString(np.concatenate([np.asarray(samples[k]['points'])[:,[0,2]]if i==0 else np.asarray(samples[k]['points'])[1:,[0,2]]for i,k in enumerate(v['native_segments'])]));sweep_query=prep(envelope(complete_line))
    changes={};owners={};public_columns={};bridge=next(p['bridge']for p in access['paths']if p['bridge']);protected_new=[];water_cache={}
    def wet(x,z):
        if(x,z)not in water_cache:water_cache[x,z]=wet_query.intersects(box(x,z,x+1,z+1))
        return water_cache[x,z]
    def bridge_volume(x,y,z):return 2729<=x<=2744 and -687<=z<=-683 and y>=-73
    def put(x,y,z,state,owner):
        if not x0<=x<=X or not z0<=z<=Z:raise ValueError('Outside full source '+str((x,y,z)))
        before=e.state(x,y,z,True)
        if e.state(x,y,z)==state:return
        if before.split('[')[0]not in ALLOWED or(x,y,z)in devices:raise ValueError('Protected original object '+str((x,y,z,before,owner)))
        if public[z-z0,x-x0]:raise ValueError('Existing public column would change '+str((x,y,z,owner)))
        if wet(x,z)and not bridge_volume(x,y,z):raise ValueError('Water reserve would be occupied '+str((x,y,z,owner)))
        e.put(x,y,z,state);changes[x,y,z]=(before,state);owners[x,y,z]=owner
    def surface(x,z,g2,owner,bridge_deck=False):
        if public[z-z0,x-x0]:
            public_columns[x,z]=int(oldgrade[z-z0,x-x0]);return
        floor=(g2+1)//2;ground=int(top[z-z0,x-x0])
        if bridge_deck:
            if floor!=-72:raise ValueError('Bridge deck grade mismatch')
            put(x,-73,z,'minecraft:polished_deepslate','bridge_continuous_beam')
        else:
            if abs(floor-ground)>6:raise ValueError('Unbounded earthwork '+str((x,z,floor,ground)))
            for y in range(min(ground-1,floor-1),floor):put(x,y,z,'minecraft:stone_bricks',owner+'_foundation')
        state='minecraft:smooth_stone'if g2%2==0 else'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
        put(x,floor,z,state,owner+'_floor');public_columns[x,z]=g2
        for y in range(floor+1,max(floor+3,ground)+1):put(x,y,z,'minecraft:air',owner+'_headroom')
    # Only the paired platform/link bed is built. The complete sampled northern
    # and southern transitions stay reservations for the later civil phase.
    built_ids=v['native_segments'][1:4]
    built_line=LineString(np.concatenate([np.asarray(samples[k]['points'])[:,[0,2]]if i==0 else np.asarray(samples[k]['points'])[1:,[0,2]]for i,k in enumerate(built_ids)]));bed=prep(built_line.buffer(1.55,cap_style=2));l,b,r,t=built_line.buffer(1.55).bounds
    bed_columns=[]
    for x in range(math.floor(l),math.ceil(r)):
        for z in range(math.floor(b),math.ceil(t)):
            if not bed.contains(Point(x+.5,z+.5)):continue
            for y in range(min(int(top[z-z0,x-x0])-1,-76),-75):put(x,y,z,'minecraft:stone','paired_railbed_foundation')
            put(x,-75,z,'minecraft:gravel','paired_railbed_ballast');bed_columns.append([x,z])
    stations=[];sign_payload=[];expected_signs=[]
    for s in v['stations']:
        if s['water_buffer_intersections']or s['original_object_conflicts']:raise ValueError('Rejected platform geometry')
        for x,z in s['platform_columns']:surface(x,z,-148,'platform')
        platform_set=set(map(tuple,s['platform_columns']))
        for x,z in platform_set:
            if (x+1,z)not in platform_set and(x,z-1)not in platform_set:
                put(x,-74,z,'minecraft:yellow_concrete','platform_edge_warning')
        stations.append(dict(name=s['name'],rail_id=s['rail_id'],native_rail=native[s['rail_id']],platform_columns=s['platform_columns'],rail_y=-74,
            native_length=s['platform_native_length'],actual_visible_consist_length=18.25,capacity_cars=2,end_margin=s['end_margin'],doorway_candidates=s['doorway_candidates']))
    # First resolve all widened footway grades, so adjacent half steps share a
    # coherent surface; existing street columns retain their precise grades.
    path_columns={};paths=[]
    for p in access['paths']:
        path=copy.deepcopy(p['path_xz'])
        if p['bridge']:
            # Reach the open end of the bridge, not the side of its guard rail.
            first=path.index([2746,-689]);last=path.index([2744,-685])
            path=path[:first+1]+[[2746,z]for z in range(-688,-684)]+[[2745,-685],[2744,-685]]+path[last+1:]
        g2s=[];bridge_indices=[i for i,(x,z)in enumerate(path)if 2729<=x<=2744 and z==-685]if p['bridge']else[]
        for i,(x,z)in enumerate(path):
            if bridge_indices:
                first,last=min(bridge_indices),max(bridge_indices)
                if i<first:g=-148+min(4,max(0,math.ceil((i-(first-12))/3)))
                elif i<=last:g=-144
                else:g=-144-min(2,math.ceil((i-last)/4))
            else:g=-148+min(2,max(0,math.ceil((i-(len(path)-9))/4)))
            g2s.append(g)
            for dx in(-1,0,1):
                for dz in(-1,0,1):
                    q=x+dx,z+dz
                    if q in public_columns and q not in path_columns and public_columns[q]!=g and q in set(map(tuple,next(s['platform_columns']for s in stations if s['name']==p['name']))):raise ValueError('Approach slope enters level platform')
                    path_columns[q]=max(path_columns.get(q,-999),g)
        paths.append(dict(name=p['name'],centreline=[[x+.5,g/2+1,z+.5]for(x,z),g in zip(path,g2s)],street_target=p['target']))
    for(x,z),g in path_columns.items():surface(x,z,g,'station_access',bridge_deck=2729<=x<=2744 and -686<=z<=-684)
    # Both bridge shoulders are continuous steel-coloured beams. Their four
    # bank supports are strictly outside the GIS water reserve; no pier enters it.
    bridge_supports=[]
    for z in(-687,-683):
        for x in range(2729,2745):
            put(x,-73,z,'minecraft:polished_deepslate','bridge_side_beam')
            put(x,-72,z,'minecraft:polished_deepslate','bridge_side_chord')
            for y in(-71,-70):put(x,y,z,'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]','bridge_guard')
        for x in(2729,2744):
            if wet(x,z):raise ValueError('Bridge pier in protected water band')
            ground=int(top[z-z0,x-x0]);bridge_supports.append([x,ground-1,z,x,-74,z])
            for y in range(ground-1,-73):put(x,y,z,'minecraft:stone_bricks','bridge_bank_support')
    # Small platform canopies are anchored at the back, leaving the full
    # boarding edge and approach landing clear. Their roofs do not overhang rail.
    canopies=[]
    for s in stations:
        pts=np.asarray(samples[s['rail_id']]['points'])[:,[0,2]];c=(pts[0]+pts[-1])/2;u=pts[-1]-pts[0];u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
        cells=set(map(tuple,s['platform_columns']));roof=[];posts=[]
        for x,z in cells:
            along,across=(np.array([x+.5,z+.5])-c)@u,(np.array([x+.5,z+.5])-c)@n
            if abs(along)<=10 and 4.8<=across<=8:
                put(x,-69,z,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]','platform_canopy_roof');roof.append([x,z])
        for along in(-8,0,8):
            options=[(abs((np.array([x+.5,z+.5])-c)@u-along),x,z)for x,z in cells if 6.8<((np.array([x+.5,z+.5])-c)@n)<8 and[x,z]in roof and(x,z)not in path_columns]
            if not options:raise ValueError('No safe rear canopy post')
            _,x,z=min(options);posts.append([x,z])
            for y in range(-73,-69):put(x,y,z,'minecraft:polished_andesite','platform_canopy_post')
            put(x,-69,z,'minecraft:sea_lantern','platform_canopy_lamp')
        canopies.append(dict(name=s['name'],roof=roof,posts=posts))
        x,z=posts[1];x+=1;y=-71
        put(x,y,z,'minecraft:oak_wall_sign[facing=east,waterlogged=false]','station_name_sign')
        words=[s['name'],'TSUKAHARA'if s['name']=='塚原駅'else'IWAHARA','大雄山線','乗場 / 2両']
        face=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([json.dumps({'text':s},ensure_ascii=False)for s in words]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
        tag=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(x),'y':nbtlib.Int(y),'z':nbtlib.Int(z),'front_text':face,'back_text':copy.deepcopy(face),'is_waxed':nbtlib.Byte(1)})
        sign_payload.append(nbtlib.Compound({'Pos':nbtlib.Long(packed((x,y,z))),'After':tag}));expected_signs.append(dict(pos=[x,y,z],name=s['name'],facing='east'))
    # Audit exact ownership before serialising standard deltas.
    changes={p:(old,e.state(*p))for p,(old,_)in changes.items()if old!=e.state(*p)}
    regions=e.save();write(a.out/'exact-edits.json',[dict(pos=list(p),before=old,after=new,owner=owners[p])for p,(old,new)in sorted(changes.items())])
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](sign_payload)}).save(a.out/'block-entities.dat',gzipped=True)
    nbtlib.File({'Actors':nbtlib.List[nbtlib.Compound]([])}).save(a.out/'captured-actors.dat',gzipped=True)
    write(a.out/'station-design.json',dict(variant=a.variant,stations=stations,paths=paths,public_columns=[[x,z,g]for(x,z),g in sorted(public_columns.items())],bridge=bridge,bridge_supports=bridge_supports,canopies=canopies,expected_signs=expected_signs,rail_bed_columns=bed_columns,
        water_reference_is_reservation_not_claim_of_current_water=True,platform_visible_gap_sample_report=str(a.edges),source_snapshot=str(a.source),authority=str(a.authority),existing_native_source=str(a.native_source),native_member_baseline=604,world_written=False))
    write(a.out/'native-station-plan.json',dict(platforms=[dict(name=s['name'],rail=native[s['rail_id']],capacity_cars=2,vehicle='e44_mini_cab_3',consist_lengths=[9,9])for s in stations],rails=[native[k]for k in built_ids],reserved_approaches=[native[v['native_segments'][i]]for i in(0,4)],source_math_samples=str(a.geometry/'native-samples.json'),native_write_performed=False,registered=False,through_service_complete=False))
    write(a.out/'native-math-samples.json',[samples[k]for k in v['native_segments']])
    write(a.out/'manifest.json',dict(world=capture['world'],kind='paired_diagonal_stations_with_retained_watercourse_clearspan_access',regions=regions,cells=sum(r['cells']for r in regions),changed_chunks=[list(p)for p in sorted({(x//16,z//16)for x,y,z in changes})],bounds_xz=capture['bounds_xz'],device_changes=len(sign_payload),original_device_changes=0,actor_changes=0,retained_devices=len(devices),native_changes=0,jar_changes=0,world_written=False,production_recipe_replay_pending=True,complete_operating_service=False))
    write(a.out/'functional-check.json',dict(errors=['Independent saved candidate verification pending'],world_written=False))
    print('Saved paired station candidate:',len(changes),'cells;',len(public_columns),'public columns;',len(devices),'original devices preserved',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','geometry','edges','access','native-source','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--variant',required=True);main(p.parse_args())
