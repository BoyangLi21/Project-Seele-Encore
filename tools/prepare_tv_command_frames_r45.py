"""Finite TV11 door surrounds and TV12 cabin roof recipe; never writes a world."""
from pathlib import Path
import argparse,copy,gzip,hashlib,json,math,sys
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from prepare_school_hakone_native_r45 import ActualGeometry

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
WORLD=ART/'composition_candidates/R45_source_candidate_20261004_v12_01/world'
OUT=ART/'lifts_doors_lifecycle_sol_v2/tv_door_lift_construction_v1/complete_frames_and_roofs_v2_v12'
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf8')
def main():
    assert not OUT.exists();OUT.mkdir()
    receipt=WORLD.parent/'composition_city_navigation_readback.json';actual=read(receipt);assert actual['phase']=='COMPLETE'
    marker_path=WORLD/'.projectseele_command_sliding_doors_r01.json';marker=read(marker_path)
    inputs=read(ART/'lifts_doors_lifecycle_sol_v2/command17_native_v11_v4/command17_cases141.UNBOUND.json')
    cars=read(ART/'tv_lifts_doors_sol_followup/all7_current_car_presence.json')
    m=MeasuredWorld(WORLD)
    for d in marker['doors']:m.around(d['lower'],7)
    for car in cars:
        assert len(car['candidate_cars'])==1
        m.around(car['candidate_cars'][0]['centre'],car['radius']+3)
    m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-390,-590,-300),(170,110,785),selected_chunks=set(m.selected)))
    g=ActualGeometry(m);rows={};skipped=[];components=[]
    apertures={tuple(p)for d in marker['doors']for p in d['aperture']}
    buttons={tuple(c['pos'])for d in marker['doors']for c in d['fixedInputContractsR45']}
    forbidden=apertures|buttons
    path_boxes=[]
    for c in inputs['cases']:
        points=c.get('path',[])
        if not points:points=[c['staging']]
        for a,b in zip(points,points[1:]+points[-1:]):
            path_boxes.append(([min(a[k],b[k])-(.3 if k!=1 else 0)for k in range(3)],
                               [max(a[k],b[k])+(.3 if k!=1 else 1.8)for k in range(3)]))
    def full(q):
        t=tags.get(q);return dict(pos=list(q),state=m.block(q),full_nbt=None if t is None else t.snbt())
    def intersects(q,b):return all(q[k]<b[1][k]and q[k]+1>b[0][k]for k in range(3))
    def put(q,after,owner,reason,allow_cap=False):
        before=m.block(q);assert before is not None
        if q in forbidden or q in tags:skipped.append(dict(pos=list(q),reason='Actual input/aperture/full BE preserved',owner=owner));return
        if before==after:return
        boxes=g.boxes(q);new=g.shapes.get(after)
        assert new==[[0,0,0,1,1,1]],('Actual cached target is not full cube',after,new)
        if boxes!=new:
            if not(allow_cap and boxes==[] and not any(intersects(q,b)for b in path_boxes)):
                skipped.append(dict(pos=list(q),reason='Preserve original shaped/empty route interface',owner=owner));return
        if q in rows:assert rows[q]['after']==after;rows[q]['owners'].append(owner);return
        rows[q]=dict(pos=list(q),before=before,after=after,before_nbt=None,after_nbt=None,owners=[owner],owner=owner,reason=reason)
    for d in marker['doors']:
        x,y,z=d['lower'];ax,az=(1,0)if d['axis']=='x'else(0,1);mask=[]
        for k in(-2,2):
            for h in range(2):
                q=x+k*ax,y+h,z+k*az;mask.append(q);put(q,'projectseele:nerv_machine_hazard',f"command/{d['id']}/fixed_hazard_surround",'TV11 R07 red/black fixed security-door surround; original full-solid jamb only')
        for k in range(-2,3):
            q=x+k*ax,y+2,z+k*az;mask.append(q)
            put(q,'minecraft:sea_lantern'if k==0 else'projectseele:nerv_machine_edge',f"command/{d['id']}/header_and_fixed_light",'Complete supported header/cap outside original3x2 opening; existing whole-cube light behind fixed button',allow_cap=True)
        for k in(-1,0,1):
            q=x+k*ax,y-1,z+k*az;mask.append(q);put(q,'projectseele:nerv_structural_panel',f"command/{d['id']}/metal_sill",'TV11 metallic sill; exact old full-solid bearing shape retained')
        components.append(dict(kind='command_door',id=d['id'],lower=d['lower'],axis=d['axis'],complete_mask=[full(q)for q in mask],aperture=[full(tuple(q))for q in d['aperture']],input_positions=d['buttons'],requested_high_detail_root_geometry='Thin twin leaf central split, large R-number, deep inset panel, flush wall pockets, fine fixed bezel; all outside exact collision/route envelope'))
    for car in cars:
        c=car['candidate_cars'][0];x,y,z=c['centre'];r=car['radius'];Y=y+car['height']-2;mask=[]
        for X in range(x-r,x+r+1):
            for Z in range(z-r,z+r+1):
                q=X,Y,Z;mask.append(q);put(q,'projectseele:nerv_machine_edge',car['lift']+'/whole_cabin_ceiling_grid','TV12 dark ceiling grid adaptation; all original full-solid roof cells/height preserved')
        components.append(dict(kind='vertical_cabin_roof',id=car['lift'],actual_car=c['centre'],complete_mask=[full(q)for q in mask],preserved_floor_y=y-1,preserved_roof_y=Y,requested_high_detail_root_geometry='TV12 utility: recessed grid and4 small red lights within existing ceiling; TV22 personnel: quieter ceiling, thin purple waist-band. No hoist/cable canonical claim.'))
    assert not(set(rows)&set(tags))and not(set(rows)&forbidden)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
            for q,r in sorted(rows.items()):
                v=copy.deepcopy(r)
                if inverse:v['before'],v['after']=r['after'],r['before']
                f.write(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n')
    after=copy.deepcopy(marker)
    updated=[]
    for d in after['doors']:
        for c in d['fixedInputContractsR45']:
            q=tuple(c['fixed_support']['pos'])
            if q in rows:
                assert c['fixed_support']['state']==rows[q]['before']and c['fixed_support']['full_nbt']is None
                c['fixed_support']['state']=rows[q]['after'];updated.append(dict(door_id=d['id'],button=c['pos'],support=list(q)))
    (OUT/'command_marker.before.json').write_bytes(marker_path.read_bytes());write(OUT/'command_marker.after.json',after)
    write(OUT/'complete_component_before.json',components);write(OUT/'skipped_actual_interfaces.json',skipped)
    metadata=dict(target=marker_path.name,before=ref(OUT/'command_marker.before.json'),after=ref(OUT/'command_marker.after.json'),unchanged_all39_actual_inputs=True,updated_support_records=updated)
    write(OUT/'metadata_reversible_proposal.json',metadata)
    write(OUT/'report.json',dict(source_world=str(WORLD),actual_source_readback=ref(receipt),source_inventory_count=len(actual['full_after_inventory']),commands=17,cabins=7,static_rows=len(rows),roof_rows=sum('/whole_cabin_ceiling_grid'in r['owner']for r in rows.values()),door_rows=sum(r['owner'].startswith('command/')for r in rows.values()),preserved_BEs=len(tags),source_written=False,native_or_visual_pass=False,all_same_class_expanded=True,all102_paths_geometry_unchanged_or_added_caps_outside_full_player_sweeps=True,all_apertures_inputs_progress_identity_unchanged=True,root_model_geometry_not_installed=True,forward=ref(OUT/'forward.jsonl.gz'),inverse=ref(OUT/'inverse.jsonl.gz'),metadata=ref(OUT/'metadata_reversible_proposal.json')))
    print(json.dumps(read(OUT/'report.json'),ensure_ascii=False))
if __name__=='__main__':main()
