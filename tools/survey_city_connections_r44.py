"""Full corridor/bank/virtual-rail surveys from explicit existing public-road anchors."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,math
import numpy as np
from scipy.spatial import cKDTree
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/surface_network/city_connection_full_surveys'
PROFILES=ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz'
ROUTES=[('tokyo_harbour_short',(250,520),(280,520)),('hakone_tokyo_middle',(-1120,512),(-760,512)),('hakone_tokyo_north',(-1120,300),(-760,300))]
NATURAL={'minecraft:grass_block','minecraft:dirt','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:podzol','minecraft:stone','minecraft:sand','minecraft:water','minecraft:snow','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}


def main():
    assert not OUT.exists(),'Preserve the earlier complete corridor survey as its own epoch'
    OUT.mkdir(parents=True)
    a=np.load(PROFILES);profiles={tuple(map(int,p)):(float(h),int(f)) for p,h,f in zip(a['coordinates'],a['actual_feet'],a['flags'])}
    snapshot=ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json';native=json.loads(snapshot.read_text('utf8'))
    rails=np.asarray([p for c in native['curves'] if c['mode']=='TRAIN' for p in c['points'] if p[1]>=0],float)
    tree=cKDTree(np.floor(rails[:,[0,2]]));shapes=json.loads((WORLD/'native_collision_shapes.json').read_text('utf8'))
    reports=[]
    for identity,start,end in ROUTES:
        first,last=profiles[start],profiles[end]
        assert first[1]&27==27 and last[1]&27==27,(identity,'Anchor is not an existing exact-datum 6m road carriage column')
        x0,x1=sorted((start[0],end[0]));z=start[1];assert end[1]==z
        lo=(x0-12,35,z-18);hi=(x1+12,310,z+18)
        w=MeasuredWorld(WORLD);w.box(lo,hi);w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
        cols=[];count=Counter();conflicts=[];unknown=[];held=[];soil_tops=[];per_slice=[]
        for x in range(x0-6,x1+7):
            h2=round(2*(first[0]+(last[0]-first[0])*min(1,max(0,(x-x0)/max(1,x1-x0)))))
            floor=h2/2
            section=Counter()
            for zz in range(z-6,z+7):
                count['proposed_columns']+=1
                grass=[y for y in range(35,311) if (w.get(x,y,zz) or '').partition('[')[0]=='minecraft:grass_block']
                soil=max(grass) if grass else None;soil_tops.append(soil)
                if soil is None:unknown.append(dict(pos=[x,zz],reason='No natural grass surface in complete y35..310 survey; authored fill/rock/water or missing chunk needs component ownership'))
                count['cut_columns' if soil is not None and soil+1>floor else 'fill_or_bridge_columns']+=1
                section['maximum_cut']=max(section['maximum_cut'],max(0,(soil+1-floor) if soil is not None else 0))
                section['maximum_fill_or_span']=max(section['maximum_fill_or_span'],max(0,(floor-soil-1) if soil is not None else 0))
                clear=True
                for y in range(math.floor(floor-.001),math.ceil(floor+6)):
                    q=(x,y,zz);state=w.block(q)
                    if state is None:unknown.append(dict(pos=q,reason='Chunk/column is not measured FULL'));clear=False;continue
                    if q in tags:held.append(dict(pos=q,state=state,full_nbt=tags[q].snbt(),reason='Full BE preserved in any new road floor/cut/clearance'));clear=False
                    name=state.partition('[')[0]
                    if name in AIR or name in NATURAL:continue
                    # Existing anchor/approach paving can belong to the known
                    # road authority; any other structure remains a full object.
                    if y<floor and (x,zz) in profiles:continue
                    held.append(dict(pos=q,state=state,reason='Existing vegetation/structure or ballast is not an owned editable corridor component'));clear=False
                exact=[i for i in tree.query_ball_point([x,zz],4.25) if abs(math.floor(rails[i,0])-x)<=3 and abs(math.floor(rails[i,2])-zz)<=3]
                bad=[i for i in exact if rails[i,1]-3<floor+6-.001 and rails[i,1]+8>floor-1]
                if bad:conflicts.append(dict(pos=[x,floor,zz],rail_y=[float(rails[bad,1].min()),float(rails[bad,1].max())],scope='Actual 7x7 native train footprint / railY-3 underside..railY+8 body'));clear=False
                cols.append(dict(pos=[x,zz],height2=h2,grass_y=soil,existing_road=profiles.get((x,zz)),unresolved_object=not clear))
            per_slice.append(dict(x=x,feet=floor,**section))
        reports.append(dict(id=identity,anchors=[list(start),list(end)],anchor_measured_feet=[first[0],last[0]],proposed_width=13,carriage_width=9,sidewalk_width_each=2,
            authority='Explicit global city-connection reconstruction authorization and two existing measured public road anchors. No permission inferred from air or a standing surface.',
            survey_bounds=[lo,hi],counts=dict(count),known_soil_range=[min(v for v in soil_tops if v is not None),max(v for v in soil_tops if v is not None)],
            full_width_sections=per_slice,columns=cols,held_cells=held,unknown_columns=unknown,native_rail_conflicts=conflicts,
            full_bes_in_surrounding_banks=[dict(pos=p,state=w.block(p),full_nbt=t.snbt()) for p,t in tags.items()],
            proposed_half_block_grade_max=max(abs(p['feet']-q['feet']) for p,q in zip(per_slice,per_slice[1:])),
            world_written=False,construction_plan_complete=False,whole_component_bearing_passed=False,native_player_vehicle_passed=False,visual_passed=False))
        print(identity,'columns',count['proposed_columns'],'held',len(held),'unknown',len(unknown),'rail conflicts',len(conflicts),'soil',reports[-1]['known_soil_range'],flush=True)
    report=dict(road_profiles=str(PROFILES),road_profiles_sha256=hashlib.sha256(PROFILES.read_bytes()).hexdigest(),native_rails_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),routes=reports,
        world_written=False,interpretation='These are measured engineering alternatives, not demolition masks or completed road quality. All unknown authored ballast/pier/tree components and BE have to be resolved before exact full-NBT forward/inverse construction.')
    (OUT/'surveys.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()
