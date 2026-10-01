"""Whole measured parcels, retaining/drainage and period facades; exact ghost only."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math,hashlib
import nbtlib
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from plan_new_city_blocks_r44 import SOIL,SMALL,PAVING
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def main():
    p=argparse.ArgumentParser();p.add_argument('city',type=Path);p.add_argument('output',type=Path);p.add_argument('--installed-baseline',type=Path);p.add_argument('--water-margin-audit',type=Path);p.add_argument('--only-building');a=p.parse_args();assert not a.output.exists()
    district=json.loads((a.city/'new_district.json').read_text('utf8'));base_rows=[json.loads(s) for s in gzip.open(a.city/'forward.jsonl.gz','rt',encoding='utf8')]
    owned={tuple(r['pos']):r for r in base_rows};old_base={}
    if a.installed_baseline:
        old_base={tuple(r['pos']):r for r in map(json.loads,gzip.open(a.installed_baseline/'forward.jsonl.gz','rt',encoding='utf8'))};owned=dict(old_base,**{})|owned
    x0,x1,z0,z1=district['bounds'];w=MeasuredWorld(WORLD);w.box((x0-16,40,z0-16),(x1+16,220,z1+16));w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x0-16,40,z0-16),(x1+16,220,z1+16),selected_chunks=set(w.selected)))
    installed=bool(a.installed_baseline);target={} if installed else {tuple(r['pos']):(r['after'],r.get('after_nbt'),r['owner'],r['reason']) for r in base_rows}
    held=[];court_columns=[];parcels=[];shape_cases=json.loads((ROOT/'artifacts/rebuild_r44/city_expansion/rain_detail_assets_v3/shape_contract.json').read_text('utf8'))['cases']
    known_signs={q for q,r in owned.items() if '_wall_sign[' in r['after']};ground={};wetland_preserved=[]
    roads={tuple(c['pos']):c['native_feet'] for c in json.loads((a.city/'road_authority.json').read_text('utf8'))['columns']}
    oldroads=np.load(ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz');q=oldroads['coordinates'];flags=oldroads['flags']
    selected=(q[:,0]>=x0-16)&(q[:,0]<=x1+16)&(q[:,1]>=z0-16)&(q[:,1]<=z1+16)&((flags&7)==7)
    roads.update({tuple(map(int,c)):float(y) for c,y in zip(q[selected],oldroads['actual_feet'][selected])})
    # The actual sports access is a school public route, not garden soil.
    # Preserve every authored width column, not just its marked centreline.
    for r in base_rows:
        if r['owner']=='r44/tv_school/sports_access' and r['after'].split('[')[0] in PAVING:
            roads[r['pos'][0],r['pos'][2]]=r['pos'][1]+1
    campus_courts=[]
    if any(b['kind']=='tv_school' for b in district['buildings']):
        for b in district['buildings']:
            x,z,X,Z=b['bounds'];hx,hy,hz=b['actual_street_handoff']
            if b.get('facing','south')=='south':campus_courts.append((b['id'],x-3,Z+1,X+3,max(Z+1,int(hz)),b['floor']))
    def state(q):return target[q][0] if q in target else w.block(q)
    def natural(x,z):
        if (x,z) not in ground:
            soil=max([y for y in range(40,191) if (w.get(x,y,z) or '').split('[')[0] in SOIL],default=None)
            water=max([y for y in range(40,191) if (w.get(x,y,z) or '').split('[')[0]=='minecraft:water'],default=None)
            ground[x,z]=None if soil is None or (water is not None and water>=soil) else soil
        return ground[x,z]
    def put(q,st,owner,reason,nbt=None):
        q=tuple(q);actual=w.block(q);name=(actual or '').split('[')[0]
        if q in known_signs and st in AIR and nbt is None:return
        if actual is None or (q in tags and q not in known_signs) or (q not in owned and name not in SOIL|SMALL|PAVING|AIR):held.append(dict(pos=q,state=actual,reason=reason));return
        st=canonical_state(st)
        if st==actual and (tags[q].snbt() if q in tags else None)==nbt:target.pop(q,None)
        else:target[q]=(st,nbt,owner,reason)
    def fill(box,st,owner,reason):
        x,y,z,X,Y,Z=box
        for yy in range(y,Y+1):
            for zz in range(z,Z+1):
                for xx in range(x,X+1):put((xx,yy,zz),st,owner,reason)
    def panel_text(q,lines,owner):
        old=tags.get(q);old_snbt=old.snbt() if old is not None else target.get(q,(None,None))[1]
        assert old_snbt is not None,(q,'Existing or exact source-generated facade sign must have full native NBT')
        tag=nbtlib.parse_nbt(old_snbt)
        first=json.loads(str(tag['front_text']['messages'][0])).get('text','')
        if first.isdigit():lines=[first,'住戸','','']
        messages=nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps(dict(text=s),ensure_ascii=False,separators=(',',':'))) for s in lines])
        for face in ['front_text','back_text']:tag[face]['messages']=messages
        put(q,owned[q]['after'],owner,'Replace every engineering placeholder with the actual house number/shop/clinic name; preserve full remaining native sign NBT',tag.snbt())
    for number,b in enumerate(district['buildings'],1):
        if a.only_building and b['id'].split('/')[-1] not in a.only_building.split(','):continue
        owner=b['id'];x,z,X,Z=b['bounds'];f=b['floor'];roof=b['roof'];facing=b.get('facing','south');cx=(x+X)//2;cz=(z+Z)//2;hx,hy,hz=b['actual_street_handoff']
        # The whole frontage is a continuous room outside the building. Its
        # width does not collapse to the old three-column door trench.
        if facing=='south':court=(x-3,Z+1,X+3,max(Z+1,int(hz)))
        elif facing=='north':court=(x-3,min(z-1,int(hz)),X+3,z-1)
        elif facing=='east':court=(X+1,z-3,max(X+1,int(hx)),Z+3)
        else:raise ValueError(facing)
        ax,az,bx,bz=court;profiles=[]
        for xx in range(ax,bx+1):
            for zz in range(az,bz+1):
                if (xx,zz) in roads:continue
                g=natural(xx,zz)
                if g is None:
                    # A root-verified existing concrete approach is already
                    # founded; do not mistake its removed grass for unknown.
                    if any((xx,yy,zz) in owned for yy in range(f-6,f+1)):g=f-3
                    else:
                        watery=[yy for yy in range(40,191) if (w.get(xx,yy,zz) or '').split('[')[0]=='minecraft:water']
                        if watery:
                            wetland_preserved.append(dict(pos=[xx,zz],water_top=max(watery),owner=owner,role='Actual natural water margin retained outside existing full authored entrance bridge/road. No invented bearing or fluid filling.'));continue
                        held.append(dict(pos=[xx,f,zz],reason='Whole courtyard lacks measured natural bearing or prior exact authored footing'));continue
                profiles.append(dict(pos=[xx,zz],natural_ground_y=g,new_floor_y=f,cut_fill=f-g))
                if abs(f-g)>8:held.append(dict(pos=[xx,f,zz],reason='Whole frontage exceeds restrained eight-metre site earthworks bound',ground=g));continue
                for yy in range(min(g+1,f-2),f):put((xx,yy,zz),'minecraft:stone',owner,'Full courtyard formation reaches the actual measured natural ground')
                sideways=abs(xx-cx) if facing in ['south','north'] else abs(zz-cz);setback=abs(zz-(z if facing=='north' else Z)) if facing in ['south','north'] else abs(xx-X)
                landscaped='minecraft:grass_block[snowy=false]' if setback>6 and sideways>3 else 'minecraft:smooth_stone'
                put((xx,f,zz),landscaped,owner,'Complete property-width founded front garden, with wide real entrance stoop and pedestrian spine; no isolated narrow dirt trench')
                for yy in range(f+1,max(f+6,g+2)):put((xx,yy,zz),'minecraft:air',owner,'Complete front court headroom and measured shallow earth cut')
                court_columns.append(dict(pos=[xx,zz],native_feet=f+1,owner=owner,role='whole occupied frontage'))
        # Retaining returns stand at the actual outer parcel edge. Each wall
        # retains the measured neighbouring soil; bare cut faces are replaced
        # structurally, while the public frontage stays at its real street Y.
        edge=[]
        if facing in ['south','north']:
            edge=[(ax,zz) for zz in range(az,bz+1)]+[(bx,zz) for zz in range(az,bz+1)]
        else:edge=[(xx,az) for xx in range(ax,bx+1)]+[(xx,bz) for xx in range(ax,bx+1)]
        retaining=[]
        for xx,zz in edge:
            if (xx,zz) in roads:continue
            neighbour=(xx-1,zz) if xx==ax and facing!='east' else (xx+1,zz) if xx==bx and facing!='east' else (xx,zz-1) if zz==az else (xx,zz+1)
            if any(identity!=owner and ya==f and xa<=neighbour[0]<=xb and za<=neighbour[1]<=zb for identity,xa,za,xb,zb,ya in campus_courts):continue
            g=natural(*neighbour)
            if g is None:continue
            high=max(f, g)
            for yy in range(min(f-2,g),high+1):put((xx,yy,zz),'minecraft:stone_bricks',owner,'Full founded retaining return matched to the measured neighbouring natural soil')
            put((xx,high+1,zz),'minecraft:stone_brick_slab[type=bottom,waterlogged=false]',owner,'Low masonry retaining cap with an actual supported half-block silhouette')
            retaining.append(dict(pos=[xx,zz],retained_soil_y=g,wall_top_y=high+1.5))
        # The side/rear garden terrace follows the measured relief rather
        # than giving the player a four-metre dirt slot beside the doorway.
        terraces=[]
        for xx in range(x-3,X+4):
            for zz in range(z-3,Z+4):
                if x<=xx<=X and z<=zz<=Z or ax<=xx<=bx and az<=zz<=bz or (xx,zz) in roads:continue
                g=natural(xx,zz)
                if g is None:continue
                distance=max(x-xx,xx-X,z-zz,zz-Z);level=round(f+(g-f)*min(1,distance/3))
                for yy in range(min(g+1,level-2),level):put((xx,yy,zz),'minecraft:dirt',owner,'Complete founded planted side/rear terrace, not a floating decoration over a cut')
                put((xx,level,zz),'minecraft:grass_block[snowy=false]',owner,'Measured graded side/rear terrace merges back into retained soil within the whole parcel')
                for yy in range(level+1,max(level+3,g+2)):put((xx,yy,zz),'minecraft:air',owner,'Remove the complete measured terrace cut rather than covering a raw soil wall with objects')
                terraces.append(dict(pos=[xx,zz],before_ground=g,after_ground=level))
        # Narrow eaves and supported downpipes cover all four facade normals.
        roofEdge=X-(2*(b['storeys']-1) if b['kind']=='apartment' and X-x<13 else 0)
        if roofEdge<X:
            fill((roofEdge+1,roof,z,X,roof,Z),'minecraft:air',owner,'Retire the unsupported full original overhang; top roof follows the actual final setback body and leaves true open terraces')
        for normal,positions in [('north',[(xx,z-1) for xx in range(x,roofEdge+1)]),('south',[(xx,Z+1) for xx in range(x,roofEdge+1)]),
            ('west',[(x-1,zz) for zz in range(z,Z+1)]),('east',[(roofEdge+1,zz) for zz in range(z,Z+1)])]:
            toward={'north':'south','south':'north','east':'west','west':'east'}[normal]
            delta={'north':(0,1),'south':(0,-1),'west':(1,0),'east':(-1,0)}[normal]
            solid_wall={'minecraft:smooth_sandstone','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:stone_bricks','minecraft:light_gray_terracotta'}
            for xx,zz in positions:
                if (state((xx+delta[0],roof-1,zz+delta[1])) or '').split('[')[0] in solid_wall:put((xx,roof-1,zz),'projectseele:city_rain_gutter[facing='+toward+',outlet=false]',owner,'Whole actual supported eaves gutter skips the real L-shaped void instead of floating over its courtyard')
            continuous=[q for q in positions[1:-1] if all((state((q[0]+delta[0],yy,q[1]+delta[1])) or '').split('[')[0] in solid_wall for yy in range(f+1,roof))]
            if continuous:
                xx,zz=continuous[0]
                for yy in range(f+1,roof-1):put((xx,yy,zz),'projectseele:city_rain_pipe[facing='+toward+']',owner,'Continuous quarter-metre downpipe is backed by a measured solid facade at every segment; no full-cube hidden collision')
                put((xx,roof-1,zz),'projectseele:city_rain_gutter[facing='+toward+',outlet=true]',owner,'Actual gutter outlet joins the downpipe continuously, with matching quarter-metre connector geometry')
                if (xx,zz) not in roads and (ax<=xx<=bx and az<=zz<=bz):
                    put((xx,f,zz),'minecraft:iron_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]',owner,'Flush visible courtyard drain grille receives the actual supported downpipe and preserves the exact walking floor')
        # Real street-facing plinths, window reveals and roof edge material
        # vary by use. All stay on the facade boundary, off public floor cells.
        material='minecraft:stone_bricks' if b['kind'] in ['small_inn','compact_home'] else 'minecraft:light_gray_terracotta' if b['kind']=='apartment' else 'minecraft:light_gray_concrete'
        for yy in [f+1]:
            for xx in range(x,X+1):
                for zz in [z,Z]:
                    if (state((xx,yy,zz)) or '').split('[')[0] not in AIR and 'door[' not in (state((xx,yy,zz)) or ''):put((xx,yy,zz),material,owner,'Period masonry/tile facade plinth respects every actual door opening and real L-shaped void')
            for zz in range(z,Z+1):
                for xx in [x,X]:
                    if (state((xx,yy,zz)) or '').split('[')[0] not in AIR and 'door[' not in (state((xx,yy,zz)) or ''):put((xx,yy,zz),material,owner,'Supported distinct side-wall plinth, matched to the building use')
        # Signs keep real names/address and erase owner ids/implementation text.
        street='北町' if district['id']=='tokyo_north' else '霧里北' if district['id']=='kirisato_north' else '西町'
        use={'compact_home':[street+'一丁目',str(number)+'-1','',''],
            'local_shop':[b['label'],'日用品・食料品','西町 '+str(number)+'番',''],
            'clinic':[b['label'],'内科・家庭医','西町 '+str(number)+'番',''],
            'small_inn':[b['label'],'宿泊・受付','西町 '+str(number)+'番',''],
            'apartment':[b['label'],'住戸 101–301','西町 '+str(number)+'番',''],
            'civic':[b['label'],'集会・読書室','西町 '+str(number)+'番','']}
        for q in known_signs:
            if owned[q]['owner']==owner:panel_text(q,[line.replace('西町',street) for line in use.get(b['kind'],[b['label'],'','',''])],owner)
        # Compact enclosed roof hatches replace the repeated oversized boxes
        # while retaining the same actual public/maintenance roof journeys.
        if b['kind'] in ['local_shop','civic','clinic'] and 'Accessible flat roof' in b.get('roof_role',''):
            for xx in range(x+1,min(X-1,x+10)+1):
                for zz in range(z+1,min(Z-1,z+13)+1):
                    for yy in range(roof+1,roof+5):put((xx,yy,zz),'minecraft:air',owner,'Retire the entire oversized roof stair enclosure before the compact supported replacement')
                    if '_stairs[' not in (state((xx,roof,zz)) or ''):put((xx,roof,zz),'minecraft:smooth_stone',owner,'Whole retained roof surface closes redundant old stair-core apertures')
            last=b['storeys']-1;north=last%2==0;sx=x+(3 if north else 7);sz=z+(10 if north else 4);direction=-1 if north else 1
            for i in range(5):
                yy=f+last*5+i+1;zz=sz+direction*i
                if yy+3>=roof:
                    for cxp in range(sx-1,sx+2):
                        if yy<roof:put((cxp,roof,zz),'minecraft:air',owner,'Exact actual final-flight head aperture retained through the weather roof')
            hx0,hx1=sx-2,sx+2;hz0,hz1=z+(4 if north else 3),z+10
            for xx in [hx0,hx1]:fill((xx,roof+1,hz0,xx,roof+2,hz1),'minecraft:light_gray_concrete',owner,'Compact roof hatch side wall has exact supporting roof and flight clearance')
            for zz in [hz0,hz1]:fill((hx0,roof+1,zz,hx1,roof+2,zz),'minecraft:light_gray_concrete',owner,'Compact roof hatch return wall preserves actual entry hierarchy')
            fill((hx0,roof+3,hz0,hx1,roof+3,hz1),'minecraft:smooth_stone',owner,'Small supported roof hatch cover replaces the generic oversized upper box')
            exitZ=hz0 if north else hz1;heading='north' if north else 'south'
            for dy,half in [(1,'lower'),(2,'upper')]:put((sx,roof+dy,exitZ),f'projectseele:city_personnel_door[facing={heading},half={half},hinge=left,open=false,powered=false]',owner,'Full real compact roof hatch door at the retained native stair/roof handoff')
        parcels.append(dict(building=owner,whole_forecourt_bounds=[ax,f,az,bx,f+5,bz],bearing_profiles=profiles,retaining_returns=retaining,whole_side_rear_terraces=terraces,world_written=False))
    if a.water_margin_audit:
        prior_audit=json.loads(a.water_margin_audit.read_text('utf8'));islands=set()
        for e in prior_audit['failures']:
            assert e['kind']=='WHOLE_FRONT_COURT_NOT_CONNECTED_TO_ACTUAL_ENTRY',e
            assert any((w.get(xx+dx,yy,zz+dz) or '').split('[')[0]=='minecraft:water' for xx,zz in e['detached'] for dx in range(-3,4) for dz in range(-3,4) for yy in range(60,75)),('Detached court component must border measured native water',e)
            islands.update(map(tuple,e['detached']))
        for q in list(target):
            if (q[0],q[2]) in islands and q not in owned:target.pop(q)
        court_columns=[c for c in court_columns if tuple(c['pos']) not in islands]
        wetland_preserved.extend(dict(pos=q,role='Actual natural dry bank isolated by preserved water; retire uninstalled paving/fill and retain measured native shore, outside every original door/road/floor route') for q in sorted(islands))
        district['preserved_margin_audit_file']=str(a.water_margin_audit.resolve())
    rows=[dict(pos=q,before=w.block(q),after=s,before_nbt=tags[q].snbt() if q in tags else None,after_nbt=nbt,owner=o,reason=r) for q,(s,nbt,o,r) in sorted(target.items())]
    a.output.mkdir(parents=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for row in rows:
                r=dict(row)
                if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
                f.write(json.dumps(r,ensure_ascii=False)+'\n')
    (a.output/'new_district.json').write_text(json.dumps(district,ensure_ascii=False,indent=2),'utf8')
    cases=json.loads((a.city/'native_cases.json').read_text('utf8'));(a.output/'native_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8')
    (a.output/'road_authority.json').write_text((a.city/'road_authority.json').read_text('utf8'),'utf8')
    prior=json.loads((a.city/'ecology_reservations.json').read_text('utf8'));prior['reservations'].extend(dict(bounds=r['whole_forecourt_bounds'],owner=r['building'],role='Whole entrance court/retaining edges/drainage protection') for r in parcels)
    prior['reservations'].extend(dict(bounds=[b['bounds'][0]-4,b['floor']-10,b['bounds'][1]-4,b['bounds'][2]+4,b['roof']+7,b['bounds'][3]+4],owner=b['id'],role='Complete graded parcel/real roof/eaves/downpipes') for b in district['buildings'])
    (a.output/'ecology_reservations.json').write_text(json.dumps(prior,indent=2),'utf8')
    (a.output/'source_shape_candidates.json').write_text(json.dumps(dict(cases=shape_cases,native_verified=False),indent=2),'utf8')
    if (a.city/'architecture_components.json').exists():
        (a.output/'architecture_components.json').write_text((a.city/'architecture_components.json').read_text('utf8'),'utf8')
    (a.output/'parcel_components.json').write_text(json.dumps(dict(parcels=parcels,full_court_columns=court_columns,actual_natural_water_margins_preserved=wetland_preserved,world_written=False),indent=2),'utf8')
    if installed:
        foundation_source=a.installed_baseline/'foundation_profiles.json'
        (a.output/'delta_provenance.json').write_text(json.dumps(dict(installed=str(a.installed_baseline.resolve()),functional_seams=str(a.city.resolve()),foundation_source=str(foundation_source),
            actual_world_only=True,whole_city_reapply_allowed=False,world_written=False),indent=2),'utf8')
    (a.output/'audit.json').write_text(json.dumps(dict(new_buildings=len(district['buildings']),new_floor_planes=len(district['floors']),changed_cells=len(rows),held=held,rail_conflicts=[],world_written=False,ready=False,native_passed=False,visual_passed=False,
        correction_basis='Root native shader rejected all six frontages/landscape/engineering signs. Complete measured parcels and actual weather-roof/facade roles are rebuilt before small original pipe/eaves details.'),ensure_ascii=False,indent=2),'utf8')
    print('Whole city parcels',district['id'],len(rows),'cells','held',len(held),'courtyard',len(court_columns),'world unchanged',flush=True)


if __name__=='__main__':main()
