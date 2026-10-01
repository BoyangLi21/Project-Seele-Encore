"""Whole occupied front courts and graded residential edges; exact ghost only.

The positive authority is the 14 authored building parcels and their actual
street handoffs. Existing buildings, roads, inventories and tree columns are
retained. Native route success alone does not close these outdoor parcels.
"""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,gzip,json,math,hashlib
import shutil
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
SOURCE=ROOT/'artifacts/rebuild_r44/city_expansion/kirisato_full_service_garden_v13'
SOIL={'minecraft:'+n for n in ['grass_block','dirt','coarse_dirt','rooted_dirt','stone','gravel','sand','clay','sandstone','mud']}
PLANTS={'minecraft:'+n for n in ['grass','tall_grass','fern','large_fern','dandelion','poppy']}


def rect_distance(x,z,box):
    a,b,c,d=box
    return math.hypot(max(a-x,0,x-c),max(b-z,0,z-d))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);a=parser.parse_args()
    assert not a.output.exists();a.output.mkdir(parents=True)
    district=json.loads((SOURCE/'new_district.json').read_text('utf8'));buildings=district['buildings']
    road=json.loads((SOURCE/'road_authority.json').read_text('utf8'))['columns']
    protected_road={tuple(r['pos']) for r in road}
    # These are original installed, explicit full-width approach components,
    # not centreline-based guesses of new construction permission.
    retained_approaches=[]
    for b in buildings:
        facing=b.get('facing','north')
        for x,z in b['approach_columns']:
            for dd in [-1,0,1]:
                q=(x,z+dd) if facing=='east' else (x+dd,z)
                if q in protected_road:continue
                retained_approaches.append(dict(pos=list(q),native_feet=float(b['floor']+1),height2=2*(b['floor']+1),source_id=b['id']+'/retained_installed_three_metre_approach'))
                protected_road.add(q)
    road+=retained_approaches
    parcels=[];claims=defaultdict(list)
    for b in buildings:
        x,z,X,Z=b['bounds'];hx,hy,hz=b['actual_street_handoff'];dx,dy,dz=b['door']
        facing=b.get('facing')
        if not facing:
            facing='north' if dz==z else 'south' if dz==Z else 'west' if dx==x else 'east' if dx==X else None
        assert facing,(b['id'],b['door'],b['bounds'])
        assert abs(hy-(b['floor']+1))<.01,('Court must preserve the actual street datum',b['id'],hy,b['floor'])
        if facing=='north':court=[min(x-3,hx-3),min(z-12,hz),max(X+3,hx+3),z-1]
        elif facing=='south':court=[min(x-3,hx-3),Z+1,max(X+3,hx+3),max(Z+12,hz)]
        elif facing=='west':court=[min(x-12,hx),min(z-3,hz-3),x-1,max(Z+3,hz+3)]
        else:court=[X+1,min(z-3,hz-3),max(X+12,hx),max(Z+3,hz+3)]
        court=list(map(int,court));side=[x-3,z-3,X+3,Z+3]
        parcel=dict(id=b['id'],floor=b['floor'],footprint=b['bounds'],front=court,side_apron=side,facing=facing)
        parcels.append(parcel)
        lo=[min(court[0],side[0])-18,min(court[1],side[1])-18];hi=[max(court[2],side[2])+18,max(court[3],side[3])+18]
        for zz in range(lo[1],hi[1]+1):
            for xx in range(lo[0],hi[0]+1):
                if any(q['bounds'][0]<=xx<=q['bounds'][2] and q['bounds'][1]<=zz<=q['bounds'][3] for q in buildings):continue
                front=rect_distance(xx,zz,court);around=rect_distance(xx,zz,side)
                distance=min(front,around)
                if distance>=18:continue
                t=min(1,distance/18);weight=1-t*t*(3-2*t)
                claims[xx,zz].append((weight,b['floor'],b['id'],front==0,around==0))
    legacy_road_path=ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz'
    legacy_roads=[]
    if legacy_road_path.exists():
        authority=np.load(legacy_road_path);coords=authority['coordinates'];flags=authority['flags']
        x0=min(q[0] for q in claims);x1=max(q[0] for q in claims);z0=min(q[1] for q in claims);z1=max(q[1] for q in claims)
        mask=(coords[:,0]>=x0)&(coords[:,0]<=x1)&(coords[:,1]>=z0)&(coords[:,1]<=z1)&((flags&7)==7)
        for q,feet in zip(coords[mask],authority['actual_feet'][mask]):
            q=tuple(map(int,q))
            if q in claims and q not in protected_road:
                legacy_roads.append(dict(pos=list(q),native_feet=float(feet),height2=round(float(feet)*2),source_id='retained_complete_prior_road_authority'))
                protected_road.add(q)
    parcel_by_id={p['id']:p for p in parcels}
    w=MeasuredWorld(WORLD)
    for x,z in claims:w.box((x,45,z),(x,130,z))
    w.load();lo=(min(x for x,z in claims),45,min(z for x,z in claims));hi=(max(x for x,z in claims),130,max(z for x,z in claims))
    prior=[json.loads(s) for s in gzip.open(SOURCE/'forward.jsonl.gz','rt',encoding='utf8')]
    returns={tuple(r['pos']):r for r in prior if r['owner'].endswith('/service3') and 'retaining' in r['reason'].lower()}
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    be_columns={(x,z) for x,y,z in tags};rows=[];columns=[];held=[];counts=Counter();classified=[];water_cells=[];wet_court_columns=[];wet_decks=[]
    for (cx,sy,cz),(palette,ids) in w.tiles.items():
        data=ids.reshape(16,16,16);mask=np.array([s.split('[')[0]=='minecraft:water' for s in palette])[data]
        for iy,iz,ix in zip(*np.where(mask)):
            x,z=cx*16+int(ix),cz*16+int(iz);y=sy*16+int(iy)
            if (x,z) in claims and 45<=y<=130:water_cells.append(dict(pos=[x,y,z],state=w.block((x,y,z))))
    native={canonical_state(s):v for s,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    legacy_checks=[]
    for r in legacy_roads+retained_approaches:
        x,z=r['pos'];feet=r['native_feet'];supported=False;clear=True;unknown=[]
        for y in range(math.floor(feet)-2,math.ceil(feet+1.8)):
            st=w.block((x,y,z));bs=native.get(canonical_state(st)) if st else None
            if st and st.split('[')[0] in AIR|{'minecraft:light'}:bs=[]
            if bs is None:unknown.append(dict(pos=[x,y,z],state=st));continue
            supported=supported or any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(y+b[4]-feet)<.001 for b in bs)
            if any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and y+b[1]<feet+1.8 and y+b[4]>feet+.001 for b in bs):clear=False
        check=dict(pos=[x,feet,z],supported=supported,clear=clear,unknown=unknown);legacy_checks.append(check)
        if not supported or not clear or unknown:held.append(dict(reason='Prior road authority does not match current native support/headroom; retained unchanged pending classification',road=check))
    for (x,z),owners in sorted(claims.items()):
        if (x,z) in protected_road:counts['retained_road_columns']+=1;continue
        if (x,z) in be_columns:counts['retained_block_entity_columns']+=1;continue
        profile=[w.block((x,y,z)) for y in range(45,131)]
        if any(v is None for v in profile):held.append(dict(pos=[x,z],reason='Unknown column'));continue
        names=[v.split('[')[0] for v in profile]
        actual_water=[45+i for i,n in enumerate(names) if n=='minecraft:water']
        if any(n.endswith(('_log','_leaves')) for n in names):
            counts['retained_tree_columns']+=1
            classified.append(dict(pos=[x,z],purpose='Retained tree column needs the complete tree and surrounding grade checked together',public_claim=any(r[3] or r[4] for r in owners),owners=[r[2] for r in owners]))
            continue
        ys=[45+i for i,n in enumerate(names) if n in SOIL]
        if not ys:held.append(dict(pos=[x,z],reason='No measured soil bearing'));continue
        old=max(ys);hard=[r for r in owners if r[3] or r[4]]
        transition=False;feet=None
        if hard and max(r[1] for r in hard)-min(r[1] for r in hard)>.01:
            identities={r[2].split('/')[-1] for r in hard}
            if identities=={'shop','clinic'} and -2857<=x<=-2855 and -1185<=z<=-1165:
                # The two actual entry datums differ by two metres. The full
                # three-metre alley descends in four half-metre landings;
                # neither adjoining building floor is silently overwritten.
                transition=True;feet=74-.5*max(0,min(4,(z+1182)//5+1))
            else:held.append(dict(pos=[x,z],reason='Two public parcel datums conflict',owners=hard));continue
        best=max(owners,key=lambda r:r[0]);weight,floor,owner,front,side=best
        target=math.ceil(feet)-1 if transition else floor if hard else math.floor(old+(floor-old)*weight+.5)
        if not hard and actual_water:counts['retained_outer_water_columns']+=1;continue
        if abs(target-old)>14 and not (not hard and target>=floor+5 and abs(target-old)<=16):
            held.append(dict(pos=[x,z],reason='Large grade requires a designed terrace/retaining section',before=old,target=target));continue
        # The whole front parcel needs a continuous grade, not a concrete
        # square from the facade all the way to a distant street. Existing
        # authorized street connectors stay intact. Keep a three-metre walk
        # around the block and a five-metre entrance apron; the rest is lawn.
        public=bool(hard)
        paved=transition or any(r[4] for r in hard)
        for r in hard:
            if not r[3]:continue
            p=parcel_by_id[r[2]];bx,bz,bX,bZ=p['footprint']
            depth={'north':bz-z,'south':z-bZ,'west':bx-x,'east':x-bX}[p['facing']]
            paved=paved or depth<=5
        exposed_water=bool(actual_water and max(actual_water)>=old)
        if exposed_water and not paved:
            wet_court_columns.append(dict(pos=[x,z],owners=[r[2] for r in owners],soil_feet=old+1,water_surface=max(actual_water)+1,
                retired_uninstalled_claim='Flat public lawn over existing pond. Actual water remains a positive landscape component, never landfill.'))
            counts['retained_complete_public_water_columns']+=1;continue
        if exposed_water:
            wet_decks.append(dict(pos=[x,z],feet=target+1,water_surface=max(actual_water)+1,owner=owner,
                purpose='Five-metre timber apron span over actual pond; dry-bank abutments and whole shore support/guard plan required before installation.'))
        changed=[];obstacles=[]
        for y in range(min(old,target)-3,max(old,target+3)+1):
            q=(x,y,z);before=w.block(q);name=before.split('[')[0]
            if name=='minecraft:water':continue
            if exposed_water:
                # Water-bearing apron cells are bridge decks, not filled
                # soil. Preserve the whole measured under-deck volume.
                if y==target:after='minecraft:oak_planks'
                elif y==target-1:after='minecraft:oak_log[axis=x]'
                else:continue
                if before!=after:changed.append(dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner=owner+'/whole_pond_apron_span',reason='Timber apron deck/continuous cross-beam above retained actual water; complete dry abutments remain a separate construction obligation'))
                continue
            previous_return=returns.get(q)
            if previous_return is not None:
                assert before==previous_return['after'],('Old complete retaining return changed independently',q)
                after='minecraft:air' if y>target else 'minecraft:smooth_stone' if y==target else before
                classified.append(dict(pos=q,purpose='Old retaining return repurposed after the full surrounding grade: buried foundation retained, obsolete above-grade wall retired',before=before,after=after))
                if before!=after:changed.append(dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner=owner+'/retaining_return_regrade',reason='Exact complete known retaining component, now inside a continuous full court grade'))
                continue
            if name=='projectseele:city_rain_pipe':
                classified.append(dict(pos=q,purpose='Retained complete roof drainage; its measured thin geometry is a fixture exclusion, not a missing public floor',state=before));continue
            if name not in SOIL|AIR|PLANTS|{'minecraft:water'}:
                if y>target and y<target+3:obstacles.append(dict(pos=q,state=before))
                continue
            if y>target:after='minecraft:air'
            elif y==target:after='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]' if transition and feet%1 else 'minecraft:smooth_stone' if paved else 'minecraft:grass_block[snowy=false]'
            elif y>=target-3:after='minecraft:dirt'
            else:after='minecraft:stone'
            if before!=after:changed.append(dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner=owner+'/whole_living_parcel',reason='Complete authored front court and side apron, or continuous graded edge; existing road/building/tree/BE columns retained'))
        if obstacles and hard:
            held.append(dict(pos=[x,z],reason='Retained authored component needs whole-component decision',obstacles=obstacles));continue
        rows+=changed;columns.append(dict(pos=[x,z],before_ground=old,target_ground=target,feet=feet if transition else target+1,role='supported_pond_apron_deck' if exposed_water else 'shop_clinic_three_metre_step_alley' if transition else 'public_court_or_apron' if paved else 'graded_living_lawn' if public else 'graded_garden_edge',owner=owner,changed_cells=len(changed)))
    assert len({tuple(r['pos']) for r in rows})==len(rows)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for row in rows:
                r=dict(row)
                if inverse:r['before'],r['after']=row['after'],row['before']
                f.write(json.dumps(r,ensure_ascii=False)+'\n')
    report=dict(source=str(SOURCE),world=str(WORLD),parcels=parcels,columns=columns,held=held,classified_components=classified,counts=dict(counts),changed_cells=len(rows),world_written=False,root_apply_ready=False,visual_passed=False,native_passed=False,
        next='Resolve every retained component and large-grade terrace; inspect complete terrain/section views and all court widths, then add lighting, drainage and actual domestic street fixtures. This is a classified full-parcel draft, not a completed city.',producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (a.output/'parcel_ground_plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    (a.output/'complete_current_water_landscape.json').write_text(json.dumps(dict(measured_actual_water_cells=water_cells,retained_public_water_columns=wet_court_columns,supported_apron_deck_columns=wet_decks,
        clipped_component_extent='Every actual water voxel within all fourteen complete parcel claims is recorded; external connected water remains unchanged. The declared margins are survey boundaries, not invented water endpoints.',
        all_measured_water_unchanged=not any(r['before'].startswith('minecraft:water') for r in rows),world_written=False,shore_geometry_complete=False),ensure_ascii=False,indent=2),'utf8')
    (a.output/'legacy_road_current_preflight.json').write_text(json.dumps(dict(source=str(legacy_road_path),checks=legacy_checks,retained_columns=len(legacy_roads)),indent=2),'utf8')
    for name in ['new_district.json','native_cases.json']:shutil.copy2(SOURCE/name,a.output/name)
    (a.output/'road_authority.json').write_text(json.dumps(dict(columns=road+legacy_roads,world_written=False),indent=2),'utf8')
    fixture_columns={tuple(r['pos'][::2]) for r in classified if 'roof drainage' in r.get('purpose','')}
    courts=[dict(pos=r['pos'],native_feet=r['feet'],owner=r['owner'],purpose=r['role']) for r in columns if not r['role'].startswith('graded_') and tuple(r['pos']) not in fixture_columns]
    (a.output/'parcel_components.json').write_text(json.dumps(dict(parcels=parcels,full_court_columns=courts,fixture_exclusion_columns=sorted(fixture_columns),world_written=False),indent=2),'utf8')
    print('Whole parcels',len(parcels),'columns',len(columns),'cells',len(rows),'unresolved columns',len(held),'NO WORLD WRITE',flush=True)


if __name__=='__main__':main()
