"""Root-authorized independent HQ approach candidate. No world or MTR writes."""
from pathlib import Path
import argparse,copy,json,math
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--original-boundary',type=Path,required=True,help='Frozen current ten HQ rails plus original U2 siding as index10')
    args=ap.parse_args();out=args.out.resolve()
    if out.exists():raise ValueError('New immutable candidate directory required')
    out.mkdir(parents=True)
    old=json.loads((ROOT/'artifacts/r52_hq_approach_candidate/CANDIDATE.json').read_text('utf-8'))
    sampled={r['id']:np.asarray(r['points'])for r in json.loads((ROOT/'artifacts/r52_hq_approach_candidate/NATIVE_TUNNEL_SAMPLES.json').read_text('utf-8'))}
    segments={s['id']:copy.deepcopy(s)for s in old['segments']};routes=copy.deepcopy(old['routes'])
    for s in segments.values():
        if len(s['source_original_indices'])>1:s['source_original_indices']=[max(s['source_original_indices'])]
    def add(name,a,heading,b,opposite_heading,source):
        if name in segments:raise ValueError('Duplicate candidate segment')
        segments[name]=dict(id=name,**{'from':a,'to':b},from_angle=heading,to_angle=opposite_heading,
            shape='TWO_RADII',vertical_radius=100,source_original_indices=[source],root_authorized_independent_track=True)
        return name
    def chain(prefix,rows,source):
        return [add(prefix+str(i),a,h,b,H,source)for i,(a,h,b,H)in enumerate(rows)]
    # Outer210m circle; the first22.5-degree tangency is the nearest exact native
    # tangent after Root's ~64m departure transition. No duplicate24m rail member.
    theta=math.pi/8
    desired=np.array([-274+200*math.sin(theta)+.5,985-200*math.cos(theta)+.5])
    p=sampled['u1_west_descent_0'];y=int(round(p[np.argmin(np.linalg.norm(p[:,[0,2]]-desired,axis=1)),1]))
    first=[round(-274+210*math.sin(theta)),y,round(985-210*math.cos(theta))]
    west_nodes=[([-298,-467,785],'E',[-254,-467,784],'W'),
                ([-254,-467,784],'E',first,'NWW'),
                (first,'SEE',[-64,-480,985],'N'),
                ([-64,-480,985],'S',[-274,-494,1195],'E'),
                ([-274,-494,1195],'W',[-484,-507,985],'S'),
                ([-484,-507,985],'N',[-274,-520,775],'W'),
                ([-274,-520,775],'E',[-240,-542,550],'S'),
                ([-240,-542,550],'N',[-66,-560,480],'W'),
                ([-66,-560,480],'E',[-2,-560,486],'W')]
    routes['original_6']=chain('u1_west_independent6_',west_nodes,6)
    # Keep original2's separate160m loop; extend its own merge east to X320,
    # preserving left/right order against original3's X302->310 centre chain.
    prefix=[n for n in routes['original_2']if n.startswith('u1_east_486_')and not n.endswith('_merge')]
    routes['original_2']=prefix+chain('u1_east_independent2_',[
        ([310,-480,330],'S',[320,-477,370],'N'),
        ([320,-477,370],'S',[320,-477,393],'N'),
        ([320,-477,393],'S',[310,-467,503],'N'),
        ([310,-467,503],'S',[310,-467,533],'N')],2)
    # The platform throat keeps its actual axis until X86. Independent points
    # then peel north and return directly to old4's private branch, never430/518.
    suffix=[n for n in routes['original_4']if n not in ('u2_east_common_approach','u2_east_296_approach')]
    routes['original_4']=chain('u2_east_independent4_',[
        ([62,-560,522],'E',[86,-559,522],'W'),
        ([86,-559,522],'E',[150,-556,512],'W'),
        ([150,-556,512],'E',[366,-547,508],'W'),
        ([366,-547,508],'E',[430,-544,510],'W'),
        ([430,-544,510],'E',[488,-541,514],'W')],4)+suffix
    original_boundary=json.loads(args.original_boundary.read_text('utf-8'))
    assert len(original_boundary)==11
    # The original128m U2 depot is inside the final southwest lake. Root authorized
    # the complete original depot and direct32m throat to move withHQ by-93.
    for i,name in [(0,'u2_siding_hq_original_throat'),(10,'u2_original_siding_translation')]:
        d=original_boundary[i]['data'];a=[d['position1'][k]for k in ('x','y','z')];b=[d['position2'][k]for k in ('x','y','z')];a[1]-=93;b[1]-=93
        routes['original_'+str(i)]=[add(name,a,d['angle1'],b,d['angle2'],i)]
        segments[name].update(shape=d['shape'],vertical_radius=d['verticalRadius'],rigid_original_translation=[0,-93,0])
    used={name for chain in routes.values()for name in chain}
    active=[s for name,s in segments.items()if name in used]
    nodes={tuple(s[k])for s in active for k in('from','to')}
    edge_ids=[tuple(sorted((tuple(s['from']),tuple(s['to']))))for s in active]
    assert len(edge_ids)==len(set(edge_ids)), 'Coincident endpoint pair would overwrite a native rail member'
    for i,chain_ids in routes.items():
        chain_segments=[segments[n]for n in chain_ids]
        assert all(a['to']==b['from']for a,b in zip(chain_segments,chain_segments[1:])),i
        source_index=int(i.split('_')[1])
        assert all(s['source_original_indices']==[source_index]for s in chain_segments),i
    report=dict(schema='projectseele.complete-hq-independent-candidate.v1',world_written=False,status='native_geometry_and_current_structure_review_pending',
      root_decision='Original8/3/5 retain centre chains; original6/2/4 use minus normal10; preserve original direction/speed.',
      replaces_original_rail_indices=list(range(11)),routes=routes,segments=active,
      preserved_original_limits=True,new_shared_internal_physical_segments=False,
      original_fixed_external_endpoints=[[-298,-467,785],[296,-467,212],[304,-467,212],[310,-467,533]],
      original_U2_siding_and_throat_translation=[0,-93,0],
      first_west_native_tangent=dict(point=first,angle_degrees=22.5,source_circle_metres=200*theta,
        note='Nearest discrete native tangent after requested approximately64m separation transition; actual throat sweep must be checked.'),
      allowed_inherited_junction_domains=[dict(name='west_original_station_throat',port=[-298,-467,785],path_metres=104),
        dict(name='HQ_west_platform_approaches',platform_ports=[[-2,-560,486],[-2,-560,494]],last_metres=64),
        dict(name='east_research_original_station_throat',port=[310,-467,533],flat_from=[310,-467,503],control=[320,-477,393],reason='Root approved complete bogie clearance: finish climb before original protected stock bed, last30m on originalaxis. Earlier science threshold preserved.'),
        dict(name='HQ_east_original_platform_throat',port=[62,-560,522],until_x=86),
        dict(name='old_science_pair_private_branches',existing_centre_spacing=8,actual_vehicle_width=2)],
      constraints=['No station demolition; report structural contacts outside exact inherited old-track bed.',
        'The four-metre native setting envelope is construction screening; exact2m-wide vehicles/10m cars require native bogie geometry at close approaches.',
        'Do not install before original40 progress/route next-stop and current whole-tunnel verification.'])
    (out/'CANDIDATE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'out':str(out),'new_rails':len(active),'routes':{k:len(v)for k,v in routes.items()},'world_written':False,'west_first_tangent':first}))


if __name__=='__main__':main()
