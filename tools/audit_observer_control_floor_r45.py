"""Whole current observer/control floor readback for a separately named old native photo."""
from __future__ import annotations
import argparse,collections,gzip,json,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha,jsonl
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import iter_block_entities,AIR
from prepare_school_hakone_native_r45 import ActualGeometry

PHOTO=ROOT/'artifacts/rebuild_r45/space_photos/platform_identity_v57/20261003_124055'
FILENAME='personnel_draft12_observation_relation.png'
def main(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    expected={r['relative']:r['sha256']for r in read(BASELINE)['files']};assert len(expected)==1736
    def inventory():
        names={p.relative_to(WORLD).as_posix()for p in WORLD.rglob('*')if p.is_file()};assert names==set(expected)
        actual={k:sha(WORLD/k)for k in sorted(names)};assert actual==expected;return actual
    before=inventory();view=next(r for r in read(PHOTO/'itinerary.json')if r['file']==FILENAME)
    capture=next(r for r in read(PHOTO/'positions.json')if r['file']==FILENAME)
    assert view['position']==[90.5,-367,-271.5]
    # The present -367 control/observer rooms, original R29 merged southern
    # hall and R44 whole frontage are independently named authoring sources.
    # The small upper-transition and restored compact-lift observation room
    # have their original lower -369 datum; do not fill them to -367.
    domains=[dict(id='original_copied_upper_control_band',box=(-33,-287,93,-274),feet=-367),
        dict(id='R44_complete_frontage',box=(-33,-274,93,-267),feet=-367),
        dict(id='R29_named_unified_observation_halls',box=(-33,-226,94,-200),feet=-367),
        dict(id='R21_original_east_observer_spine',box=(94,-287,113,-82),feet=-367),
        dict(id='R21_upper_transition',box=(98,-91,110,-76),feet=-369),
        dict(id='R20_original_compact_upper_observation_room',box=(89,-83,112,-17),feet=-369)]
    m=MeasuredWorld(WORLD);m.box((-36,-376,-291),(116,-357,-14));m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-36,-376,-291),(116,-357,-14),selected_chunks=set(m.selected)))
    g=ActualGeometry(m)
    def full(q):
        q=tuple(q);tag=tags.get(q);return dict(pos=list(q),state=m.block(q),full_nbt=None if tag is None else tag.snbt())
    def supported_top(q):
        boxes=g.boxes(q)
        if boxes is None:return None
        for top in sorted({b[4]for b in boxes},reverse=True):
            if .01<=top<=1 and all(any(b[0]<=x<=b[3]and b[2]<=z<=b[5]and abs(b[4]-top)<.001 for b in boxes)for x in(.25,.5,.75)for z in(.25,.5,.75)):return top
        return None
    def current_point(x,feet,z):
        state=m.block((x,feet,z))or'';p=properties(state)
        if state.partition('[')[0].endswith('_slab') and p.get('type')=='bottom':
            top=supported_top((x,feet,z))
            if top is not None:return [x+.5,feet+top,z+.5]
        top=supported_top((x,feet-1,z))
        return [x+.5,feet if top is None else feet-1+top,z+.5]
    rows=[];lookup={};status=collections.Counter();normal_five_rows=[]
    for d in domains:
        x0,z0,x1,z1=d['box'];feet=d['feet']
        for x in range(x0,x1+1):
            for z in range(z0,z1+1):
                p=current_point(x,feet,z);result=g.standing(p);lower=[]
                if result!='STATIC_STANDING':
                    for y in range(feet-2,feet-6,-1):
                        top=supported_top((x,y,z))
                        if top is None:continue
                        candidate=[x+.5,y+top,z+.5]
                        if g.standing(candidate)=='STATIC_STANDING':lower.append(dict(point=candidate,support=full((x,y,z))));break
                row=dict(domain=d['id'],pos=[x,feet,z],actual_probe_point=p,status=result,
                    complete_current_levels=[full((x,y,z))for y in range(feet-4,feet+3)],complete_lower_supported_surface=lower,
                    native_pass=False,air_or_lower_shape_is_not_room_or_construction_permission=True)
                low_room_frame_top=d['id']=='R21_original_east_observer_spine'and 89<=x<=112 and -84<=z<=-17 and (m.block((x,feet-1,z))or'').partition('[')[0]in{
                    'projectseele:clear_glass','projectseele:nerv_wall_panel','minecraft:gray_stained_glass'}
                row['current_surface_role']='RESTORED_MINUS369_ROOM_WINDOW_OR_WALL_TOP; no upper public floor inferred'if low_room_frame_top else'NAMED_OBSERVER_OR_TRANSITION_FLOOR_REVIEW'
                rows.append(row);status[d['id'],result]+=1
                if result=='STATIC_STANDING'and not low_room_frame_top:lookup[tuple(row['pos'])]=row
    for z in range(-273,-268):
        selected=[lookup.get((x,-367,z))for x in range(-32,93)]
        assert all(selected),('Whole original frontage row absent',z)
        normal_five_rows.append(dict(z=z,columns=125,all_nine_point_native_shape_bearing=True))
    raised=[lookup.get((x,-367,-268))for x in range(-32,93)];assert all(raised)
    assert all(r['actual_probe_point'][1]==-366.5 for r in raised)
    # The right control-platform band seen in the old photograph is read
    # fully, including both inter-booth gaps, every far corner and the front
    # joins. No centre-line-only surrogate or world photo-source guessing.
    right=[r for r in rows if r['domain']=='original_copied_upper_control_band']
    gaps=[]
    for ident,x0,x1 in [('west_centre_gap',-1,19),('centre_east_gap',41,61)]:
        selected=[r for r in right if x0<=r['pos'][0]<=x1 and -284<=r['pos'][2]<=-274]
        assert len(selected)==21*11
        gaps.append(dict(id=ident,bounds=[[x0,-369,-284],[x1,-365,-274]],cells=len(selected),
            full_original_floor_y_minus368_complete=all(g.boxes((r['pos'][0],-368,r['pos'][2]))==[[0.,0.,0.,1.,1.,1.]]for r in selected),
            full_original_foundation_y_minus369_complete=all(g.boxes((r['pos'][0],-369,r['pos'][2]))==[[0.,0.,0.,1.,1.,1.]]for r in selected),
            actual_grounded_cells=sum(r['status']=='STATIC_STANDING'for r in selected),
            all_full_state_NBT=[r['complete_current_levels']for r in selected],source_candidate_repair_proposed=False))
    edge_candidates=[];blocked_boundaries=[]
    for key,row in sorted(lookup.items()):
        x,y,z=key;p=row['actual_probe_point']
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            neighbor=(x+dx,y,z+dz);a=current_point(*neighbor);other=g.standing(a);high=max(p[1],a[1])
            sweep=g.clear([p[0],high,p[2]],target=[a[0],high,a[2]])
            if other=='STATIC_STANDING':
                if sweep!='CLEAR'and(dx,dz)in((1,0),(0,1)):blocked_boundaries.append(dict(a=list(key),b=list(neighbor),a_feet=p,b_feet=a,complete_a=row['complete_current_levels'],
                    complete_b=[full((neighbor[0],Y,neighbor[2]))for Y in range(y-2,y+3)],disposition='Actual physical edge/half-step/openable door requires its own native movement; no automatic deletion'))
                continue
            if g.clear(a)!='CLEAR'or sweep!='CLEAR':continue
            known_lift=(-33<=neighbor[0]<=-25 and -284<=neighbor[2]<=-274)or(89<=neighbor[0]<=99 and -56<=neighbor[2]<=-48)
            high_step=any((m.block((neighbor[0],Y,neighbor[2]))or'').partition('[')[0].endswith(('_stairs','_slab'))for Y in range(y-3,y+2))
            edge_candidates.append(dict(pos=list(key),normal=[dx,0,dz],neighbor=list(neighbor),complete_current=row['complete_current_levels'],
                complete_neighbor=[full((neighbor[0],Y,neighbor[2]))for Y in range(y-5,y+3)],
                disposition='ACTUAL_COMPLETE_NATIVE_LIFT_DOMAIN_PRESERVED'if known_lift else'ACTUAL_MEASURED_STEP_NATIVE_REQUIRED'if high_step else'UNRESOLVED_WHOLE_OBSERVER_EDGE',
                world_written=False,construction_permitted=False,native_pass=False))
    # Connected exact flat/half-step shape graph from the true west-lift port.
    # A step difference is a native requirement, never a synthetic success.
    start=(-29,-367,-285);assert start in lookup
    before_path={start:None};queue=[start]
    for q in queue:
        a=lookup[q]['actual_probe_point']
        for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
            n=q[0]+dx,q[1],q[2]+dz
            if n not in lookup or n in before_path:continue
            b=lookup[n]['actual_probe_point'];high=max(a[1],b[1])
            if abs(a[1]-b[1])<=.5 and g.clear([a[0],high,a[2]],target=[b[0],high,b[2]])=='CLEAR':before_path[n]=q;queue.append(n)
    after=inventory();assert before==after
    out.mkdir(parents=True)
    jsonl(out/'whole_observer_control_floor_columns.jsonl.gz',rows);write(out/'whole_inter_booth_full_NBT_readback.json',gaps)
    write(out/'whole_observer_edge_candidates.json',edge_candidates);write(out/'supported_point_physical_boundaries.json',blocked_boundaries)
    jsonl(out/'complete_source_before_after_sha256.jsonl.gz',[dict(relative=k,before_sha256=before[k],after_sha256=after[k])for k in sorted(before)])
    report=dict(source_world=str(WORLD),native_photo_world='OLD_RUN_R45_REVIEW; not the frozen sourcecandidate',photo=str((PHOTO/FILENAME).resolve()),
        photo_sha256=sha(PHOTO/FILENAME),view=view,actual_capture=capture,complete_source_files=1736,all1736_before_after_SHA_equal=True,
        whole_review_columns=len(rows),domain_status_counts=[dict(domain=d,status=s,count=n)for(d,s),n in sorted(status.items())],
        whole_right_control_band_cells=len(right),two_full_interbooth_gaps=gaps and [{k:v for k,v in r.items()if k!='all_full_state_NBT'}for r in gaps],
        all_five125_column_frontage_rows=normal_five_rows,all125_halfmetre_actual_raised_stand_cells=True,
        true_west_lift_start=list(start),supported_nodes_reachable_in_current_height_graph=len(before_path),
        original_control_band_reachable_nodes=sum(tuple(r['pos'])in before_path for r in right),
        whole_observer_edge_candidates=len(edge_candidates),edge_dispositions=dict(collections.Counter(r['disposition']for r in edge_candidates)),
        unsupported_columns=[dict(pos=r['pos'],status=r['status'],lower=r['complete_lower_supported_surface'])for r in right if r['status']!='STATIC_STANDING'],
        model_or_runtime_Java_edited=False,world_written=False,Java_MC_Gradle_started=False,native_actual_player_step_lift_or_MTR_pass=False,
        screenshot_dark_or_lower_pixels_are_not_missing_floor_proof=True,new_static_repair_proposed=False)
    write(out/'report.json',report);print(json.dumps({k:report[k]for k in ['whole_review_columns','whole_right_control_band_cells','two_full_interbooth_gaps','original_control_band_reachable_nodes','whole_observer_edge_candidates','edge_dispositions','all1736_before_after_SHA_equal','new_static_repair_proposed']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args())
