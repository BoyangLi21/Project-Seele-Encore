"""Offline delivery proof for Itabashi: water, interfaces, failures and views."""
import argparse, copy, json, math, shutil
from pathlib import Path
import numpy as np
import nbtlib
from shapely.geometry import shape, box, LineString, mapping, Point
from shapely.ops import unary_union, nearest_points
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from author_kamonomiya_station import voxel_box, OPEN
from author_itabashi_station import verify as structure_verify, dump
from check_itabashi_vehicle import verify as vehicle_verify
from render_hakone_voxel_3d import render


def changes(candidate):
    rows = []; chunks = []
    for file in sorted((candidate / 'delta').glob('*.npz')):
        with np.load(file) as f:
            palette = list(map(str, f['palette']))
            for i, (cx, cz) in enumerate(f['coordinates']):
                left, right = map(int, f['ranges'][i:i + 2])
                chunks.append(dict(chunk_x=int(cx), chunk_z=int(cz), changed_cells=right-left))
                for j in range(left, right):
                    at = int(f['indices'][j]); x = int(cx) * 16 + at % 16
                    y = at // 256 - 128; z = int(cz) * 16 + (at % 256) // 16
                    rows.append((x, y, z, palette[int(f['before'][j])], palette[int(f['after'][j])]))
    return rows, chunks


def water_verify(candidate, site, write=True):
    d = json.loads((candidate / 'station-design.json').read_text('utf8')); e = Editor(candidate)
    water = unary_union([shape(q['geometry']) for q in site['nearby_water_interfaces']])
    banks = water.buffer(3); changed, _ = changes(candidate)
    above = []; errors = []; bad = []
    for x, y, z, before, after in changed:
        if banks.intersects(box(x, z, x+1, z+1)):
            if not (3136 <= x <= 3140 and 732 <= z <= 746 and y >= -73):
                bad.append([x, y, z, before, after])
            above.append([x, y, z])
    if bad: errors.append('protected water or bank terrain changed')
    clearance = []
    for z in range(732, 747):
        for x in range(3136, 3141):
            if not banks.intersects(box(x,z,x+1,z+1)): continue
            # Verify source ground and the entire old column below the deck,
            # including water (if present), not only the topmost soil block.
            mismatches = [y for y in range(-128, -73) if e.state(x,y,z) != e.state(x,y,z,True)]
            if mismatches: bad.append([x,z,mismatches]); errors.append('below-bridge source column changed')
            top = max(y for y in range(-90,-70) if e.state(x,y,z,True).split('[')[0] not in OPEN)
            for y in range(top+1,-73):
                if e.state(x,y,z).split('[')[0] not in OPEN: errors.append('bridge channel clearance obstructed')
            clearance.append(dict(x=x,z=z,measured_ground_top=top,reserved_future_water_surface=-77,
                                  underside=-73,clearance_above_water=4,clearance_above_ground_surface=-73-(top+1)))
    abutments = []
    for z in (734,744):
        for x in range(3136,3141):
            distance=water.distance(box(x,z,x+1,z+1))
            if distance <= 3: errors.append('bridge foundation intrudes bank buffer')
            abutments.append(dict(x=x,z=z,cached_water_distance=distance))
    proof=dict(errors=sorted(set(errors)),source_terrain_changes_in_water_or_bank_buffer=bad,
               high_bridge_air_changes_in_buffer=len(above),bridge_air_changed_cells=above,
               abutments=abutments,minimum_abutment_distance=min(q['cached_water_distance']for q in abutments),
               channel_columns=clearance,minimum_channel_clearance_above_future_water=4,
               reserved_future_water_surface=-77,waterway_already_built=False,world_written=False)
    if write: dump(candidate/'water-buffer-review.json',proof)
    if errors: raise ValueError(errors)
    return proof


def components(folder,bounds):
    data,palette=voxel_box(Editor(folder),bounds)
    solid=np.asarray([s.split('[')[0]not in OPEN for s in palette])[data]
    ids,n=label(solid);sizes=np.bincount(ids.ravel());roots=set(map(int,np.unique(ids[0])))
    loose=[]
    for i in range(1,n+1):
        if i in roots:continue
        q=np.argwhere(ids==i);xyz=q[:,[2,0,1]]+np.asarray(bounds[:3])
        boundary=bool(np.any(q[:,1]==0)or np.any(q[:,1]==solid.shape[1]-1)
                      or np.any(q[:,2]==0)or np.any(q[:,2]==solid.shape[2]-1))
        loose.append(dict(id=i,cells=int(sizes[i]),bounds=xyz.min(0).tolist()+xyz.max(0).tolist(),
                          touches_horizontal_capture_boundary=boundary,
                          support_outside_capture_unknown=boundary))
    return dict(components=n,ground_rooted_components=len(roots-{0}),unrooted_components=len(loose),
                unrooted_cells=sum(r['cells']for r in loose),unrooted=loose,
                fully_enclosed_unrooted_components=sum(not q['touches_horizontal_capture_boundary']for q in loose),
                boundary_clipped_components=sum(q['touches_horizontal_capture_boundary']for q in loose))


def interfaces(candidate,authority,site):
    d=json.loads((candidate/'station-design.json').read_text('utf8'));e=Editor(candidate)
    rail=LineString([(3102.5,799.5),(3150.5,799.5)])
    # Two landing references are selected on actual connected non-JR vectors.
    # Long straight leads stay outside the platform and precede later curves.
    planned=[dict(side='west',native_port=[3102,-77,799],straight_lead_end=[3090,-77,799],
                  reference=[3052.472,770.79],feature_indices=[62252,61336,61335,47313,47312],
                  towards='風祭・箱根湯本'),
             dict(side='east',native_port=[3150,-77,799],straight_lead_end=[3162,-77,799],
                  reference=[3190.731,812.469],feature_indices=[62254,62263],towards='小田原')]
    for p in planned:
        start=np.asarray([p['native_port'][0]+.5,p['native_port'][2]+.5]);end=np.asarray(p['reference'])
        p['horizontal_distance']=float(np.linalg.norm(end-start));p['straight_lead_metres']=12
        p['reference_soil_y']=int(max(y for y in range(-90,-65)if e.state(int(end[0]),y,int(end[1]),True).split('[')[0]not in OPEN))
        p['possible_reference_rail_y']=p['reference_soil_y']+1
        p['minimum_average_grade_if_these_levels_are_used']=abs(p['possible_reference_rail_y']+77)/p['horizontal_distance']
        p['reserved_interface_rail_y']=-77
        p['reference_bed_cut_or_fill_at_reserved_level']=-78-p['reference_soil_y']
        p['flat_station_level_continuation_possible_at_reference_point']=True
        p['curves_and_vertical_profile_final']=False;p['construction_allowed']=False
    nearby=site['cached_rail_evidence'];jr=unary_union([shape(q['geometry'])for q in nearby if q['properties'].get('vt_rtcode')=='JR'])
    region=box(*[d['parts'][0]['bounds'][k]for k in(0,2,3,5)]).buffer(1)
    existing=[]
    for mode,rows in json.loads((authority/'native-curves.json').read_text('utf8')).items():
        for q in rows:
            if not q.get('points'):continue
            v=np.asarray(q['points']);line=LineString(v[:,[0,2]])
            if line.buffer(4).intersects(region)and v[:,1].max()>=-84 and v[:,1].min()<=-65:
                existing.append(dict(id=q['id'],mode=mode))
    references=[]
    for q in nearby:
        g=shape(q['geometry'])
        if g.distance(rail)<50:
            references.append(dict(feature_index=q['feature_index'],properties=q['properties'],geometry=q['geometry'],distance_to_platform=g.distance(rail)))
    # The JR elevated corridor crosses the future HT connection just east of
    # this station. Its relative level is not an absolute bridge deck height.
    ht=unary_union([shape(q['geometry'])for q in nearby if q['properties'].get('vt_rtcode')=='JR以外'])
    crossings=ht.intersection(jr)
    crossing_record=mapping(crossings)
    centre=np.asarray(site['reference']['track_centre_xz'])
    result=dict(station='箱根板橋駅',reference_centre=centre.tolist(),native_centre=[3126.5,799.5],
                centre_shift=float(np.linalg.norm(centre-[3126.5,799.5])),reference_axis_degrees=site['axis_degrees'],
                native_axis_degrees=0,local_geographic_adaptation=True,one_to_one_restoration_claimed=False,
                adaptation_reason='Local straight platform for reliable voxel boarding; both ends retain the non-JR corridor',
                platform_length=48,current_consist='HT two e44_mini_cab_3 cars, nominal 2 x 9 m',
                reference_railway_classification='station section, single-track non-JR approaches; no extra JR platform inferred',
                stage_three_interfaces=planned,retained_reference_rails=references,
                nearest_parallel_or_crossing_jr_distance_to_platform=jr.distance(rail),
                future_ht_jr_reference_crossings=crossing_record,
                jr_bridge_reference_level_order=1,absolute_jr_deck_y_unknown=True,
                stage_three_constraints=['Preserve 12 m straight lead at both platform ends before bending toward cached axes',
                    'Retain separate elevated JR corridor east of the station; confirm absolute crossing heights and vehicle clearances',
                    'Validate native transition curves, realistic grades and full rigid-vehicle passage before through service',
                    'Construct cached drain later beneath the already supported pedestrian bridge; preserve its terrain and bank strip now'],
                retained_native_curve_conflicts=existing,through_service_complete=False,world_written=False)
    dump(candidate/'stage-three-interfaces.json',result)
    if existing:raise ValueError('Retained native curve overlaps candidate')
    return result


def run(a):
    a.out.mkdir(exist_ok=False);site=json.loads(a.site.read_text('utf8'))
    structure_verify(a.candidate,a.authority);vehicle_verify(a.candidate);water_verify(a.candidate,site)
    interface=interfaces(a.candidate,a.authority,site)
    d=json.loads((a.candidate/'station-design.json').read_text('utf8'));m=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    x,z,X,Z=m['bounds_xz'];bounds=[x,-128,z,X,319,Z]
    support=dict(before=components(a.source,bounds),after=components(a.candidate,bounds),bounds=bounds)
    dump(a.out/'components.json',support)
    if support['after']['unrooted_cells']>support['before']['unrooted_cells']:
        raise ValueError('New unrooted source component')
    changed,chunks=changes(a.candidate)
    dump(a.out/'changed-chunks.json',dict(chunks=chunks,count=len(chunks),cells=len(changed)))
    neg=a.out/'neg';neg.mkdir();tests=[]
    for name,expected,check in [
        ('floor','public floor or headroom invalid','structure'),
        ('train','visible vehicle sweep intersects station blocks','vehicle'),
        ('protected','protected original block changed','structure'),
        ('support','new solid component lacks ground support','structure'),
        ('sign','sign payload or backing invalid','structure'),
        ('water','protected water or bank terrain changed','water')]:
        folder=neg/name;shutil.copytree(a.candidate,folder);e=Editor(folder)
        if name=='floor':e.put(3138,-77,776,'minecraft:air')
        elif name=='train':e.put(3126,-76,798,'minecraft:glass')
        elif name=='protected':e.put(3165,-76,733,'minecraft:air')
        elif name=='support':e.put(3154,-71,752,'minecraft:gray_concrete')
        elif name=='water':e.put(3138,-78,739,'minecraft:stone_bricks')
        else:
            q=nbtlib.load(folder/'block-entities.dat');del q['Changes'][0]['After'];q.save(folder/'block-entities.dat',gzipped=True)
        if name!='sign':
            rows=e.save();meta=copy.deepcopy(m);meta['regions']=rows;meta['cells']=sum(q['cells']for q in rows);dump(folder/'manifest.json',meta)
        try:
            if check=='structure':structure_verify(folder,a.authority)
            elif check=='vehicle':vehicle_verify(folder)
            else:water_verify(folder,site)
        except ValueError:
            filename={'structure':'offline-verification.json','vehicle':'visible-model-sweep.json','water':'water-buffer-review.json'}[check]
            detected=expected in json.loads((folder/filename).read_text('utf8'))['errors']
        else:detected=False
        if not detected:raise ValueError('Missed negative case '+name)
        tests.append(dict(case=name,expected=expected,detected=True))
    dump(a.out/'negative-cases.json',dict(cases=tests,world_written=False))
    e=Editor(a.candidate)
    render(e,[3096,-81,727,3170,-68,805],a.out/'overview.png','箱根板橋：48格站台、站房、完整跨沟步行接入')
    render(e,[3126,-81,727,3168,-70,768],a.out/'bridge-section.png','步行桥：桥台退离水道缓冲，现地与未来沟渠上方留空')
    render(e,[3099,-81,763,3154,-73,804],a.out/'platform-cut.png','去顶剖切：全长站台通路、站房与地面入口')
    signs=[q['pos']for q in d['expected_signs']]
    dump(a.out/'review.json',dict(candidate=str(a.candidate),cells=m['cells'],changed_chunks=len(chunks),
         sign_positions=signs,public_nodes=len(d['public_columns']),ground_access_columns=len(d['ground_access_columns']),
         multi_level_nodes=len(d['station_multi_level_nodes']),negative_cases_passed=len(tests),
         components='components.json',interfaces=str(a.candidate/'stage-three-interfaces.json'),
         views=['overview.png','bridge-section.png','platform-cut.png'],
         source=str(a.source),authority=str(a.authority),model_visible_sweep='visible-model-sweep.json',
         native_registry_pending=True,production_replay_pending=True,through_service_complete=False,world_written=False))
    print('Itabashi review:',len(chunks),'chunks;',len(tests),'negative cases;',len(signs),'signs; live world untouched',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('candidate','source','authority','site','out'):p.add_argument('--'+key,type=Path,required=True)
    run(p.parse_args())
