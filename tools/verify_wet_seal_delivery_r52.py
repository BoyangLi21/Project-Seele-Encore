"""Finite delivery checks using explicitly selected actual factory Spec.

Writes a test receipt under .Codex only. Fixture additions are not a final
Root gate manifest, a World/native support PASS, or a published asset.
"""
import argparse, copy, hashlib, json, sys
from pathlib import Path
import nbtlib
from wet_front_seal_manifest_r52 import sealed_front_specs, validate_seal_phase_tables, phase_rows
from prepare_mechanical_native_bindings_r52 import face_bears
from prepare_r52_runtime_deployment_candidate import expected_controllers, java_uuid, validate_legacy_floor_bindings
from query_blocks import iter_selected_sections
from collections import defaultdict
from run_r52_minimal_install_restart import validate_sealed_native_specs
import build_r52_runtime_bundle_candidate as builder
import jsonschema

ROOT=Path(__file__).resolve().parents[1]
B=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
P=ROOT/'.Codex/r52_continuous_route_migration_20261012'
OUT=ROOT/'.Codex/r52_runtime_close/wet_seal_runtime/delivery_checks'
count=0
def read(p):return json.loads(p.read_text(encoding='utf8'))
def need(value,reason):
    global count
    if not value:raise AssertionError(reason)
    count+=1
def reject(action,reason):
    try:action()
    except (ValueError,jsonschema.ValidationError):need(True,reason);return
    raise AssertionError('Accepted negative case: '+reason)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--survey',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    global OUT;OUT=args.out.resolve();need(OUT.is_relative_to((ROOT/'.Codex').resolve()),'Finite diagnostic output only under repository .Codex')
    OUT.mkdir(parents=True,exist_ok=True)
    probe_path=args.probe.resolve()
    gates_path=P/'0262_66F5_FINAL_GATE_PROXY_TABLES/ROOT_GATES_UPRIGHT_FINAL_CANDIDATE.json'
    survey_path=args.survey.resolve()
    design_path=B/'continuous_upright/spread_level_throats/GROUND_CONTINUOUS_DESIGN.json'
    units_path=B/'runtime_directory/units/ROOT_UNITS.json'
    cannon_path=B/'encounter_installation/STATION_DESIGN.json'
    probe=read(probe_path);old=read(gates_path)['gates'];gates=copy.deepcopy(old);index={g['resource']:g for g in gates}
    reject(lambda:sealed_front_specs(old),'Actual historical unsealed42 gates rejected')
    for r in probe['gates']:
        g=index[r['resource']];s=r['actual_spec'];f=s['bottomSeal']
        g['hangar_stack']['floor_seal']=dict(closed_boxes=[[b[k] for k in ('minX','minY','minZ','maxX','maxY','maxZ')] for b in f['closedBoxes']],drop_m=f['dropM'],retreat_local_z_m=f['retreatLocalZ'])
    selected=sealed_front_specs(gates,False)
    for s in selected.values():
        g=s['gate'];supports={tuple(c['position']) for c in g['supports']}
        for a in s['wall_bearings']:
            if tuple(a['at']) not in supports:g['supports'].append(dict(position=a['at'],state='projectseele:nerv_structural_panel'))
        g['collision_steps']=phase_rows(g,gates_path.parent)
    reject(lambda:validate_seal_phase_tables(gates,lambda g:g['collision_steps']),'Actual historical front phase tables omit42 seal cells')
    for s in selected.values():s['gate']['collision_steps'][0].extend(dict(position=list(p),closed='projectseele:nerv_floor_panel',open='minecraft:air') for p in sorted(s['cells']))
    seals=validate_seal_phase_tables(gates,lambda g:g['collision_steps'])
    need(sum(len(s['cells']) for s in seals.values())==42,'Actual V2 closed factory boxes map to42 preserved cells')
    for r in probe['gates']:
        bearings=seals[r['resource']]['wall_bearings'];need(len(bearings)==len(r['native_wall_bearing_requests']),'Same actual factory seat count')
        for a,w in zip(bearings,r['native_wall_bearing_requests']):
            need(max(abs(a['bearing'][i]-w['bearing'][k]) for i,k in enumerate(('x','y','z')))<1e-9 and all(a['normal'][i]==w['normal'][k] for i,k in enumerate(('x','y','z'))),'Derived native face exactly matches actual factory packet')
    schema=read(ROOT/'docs/r52/mechanical-owner.schema.json')
    validator=jsonschema.Draft202012Validator({'$ref':'#/$defs/gate','$defs':schema['$defs']})
    for s in seals.values():
        errors=list(validator.iter_errors(s['gate']));need(not errors,'Actual V2 Spec gate schema error: '+('; '.join(e.message for e in errors[:2])));need(True,'Actual V2 Spec plus candidate table accepted by gate schema')
    bad=copy.deepcopy(gates);next(g for g in bad if g['resource']=='bay_0_front')['hangar_stack']['floor_seal']={'closed_boxes':[],'drop_m':4.2,'retreat_local_z_m':24}
    reject(lambda:sealed_front_specs(bad),'Empty actual seal geometry rejected')
    bad=copy.deepcopy(gates);front=next(g for g in bad if g['resource']=='bay_0_front');front['supports']=[c for c in front['supports'] if c['position']!=seals['bay_0_front']['wall_bearings'][0]['at']]
    reject(lambda:sealed_front_specs(bad),'Missing actual sidewall support declaration rejected')
    front=seals['bay_0_front'];bad=copy.deepcopy(front['gate']);bad['collision_steps'][0][-1]['open']='minecraft:barrier'
    reject(lambda:validate_seal_phase_tables([bad],lambda g:g['collision_steps'],False),'Wrong final seal open state rejected')
    root_units=read(units_path)['units'];all_lcl=set()
    for u in root_units:all_lcl.update(tuple(c['position']) for layer in phase_rows({'collision_steps':u['lcl']},units_path.parent) for c in layer)
    need(not set().union(*(s['cells'] for s in seals.values()))&all_lcl,'Preserved original44-layer LCL units exclude42 seal panels')
    selected_inline=[s['gate'] for s in seals.values()];copied=builder.copy_owner_tables({'gates':selected_inline},gates_path.parent)
    need(copied=={'gates':selected_inline},'Generic bundle recursion preserves entire optional Spec and extra supports')
    ground=read(design_path);aliases={f'bank_{b}_rear_lane_{i}':f'bank{b}_rear_{i}' for b in (1,2) for i in range(3)}
    for r in ground['resources']:r['id']=aliases.get(r['id'],r['id'])
    units=copy.deepcopy(root_units)
    for u in units:u['carrier_controller']=dict(id=java_uuid(f"projectseele:r52:original-carrier:{ground['epoch']}:{u['eva']}"))
    controllers=expected_controllers({'epoch':ground['epoch']},{'ground_guides':{'mode':'continuous_upright'},'units':units,'gates':gates},ground,read(cannon_path))
    need(len(controllers)==52 and len({r['uuid'] for r in controllers})==52,'Three seals keep actual42 doors and52 unique controller UUIDs')
    overlay_path=ROOT/'src/main/resources/assets/projectseele/mesh/legacy_floor_recesses_r52.json';overlay=sha(overlay_path)
    typed=[dict(mechanical_rail=dict(kind='LEGACY_RUNNING_HEAD' if i<9 else 'UPRIGHT_CAPTURED_GUIDEWAY',**({'floor_overlay_sha256':overlay} if i<9 else {}))) for i in range(18)]
    typed_directory={'runtime':{'bindings':typed}};typed_owner={'mechanism_sources':{'mesh/legacy_floor_recesses_r52.json':overlay}}
    validate_legacy_floor_bindings(typed_owner,typed_directory);need(True,'Separate overlay is bound on exact9 Legacy typed rails')
    bad=copy.deepcopy(typed_directory);del bad['runtime']['bindings'][0]['mechanical_rail']['floor_overlay_sha256']
    reject(lambda:validate_legacy_floor_bindings(typed_owner,bad),'Missing independent Legacy overlay binding rejected')
    bad=copy.deepcopy(typed_directory);bad['runtime']['bindings'][9]['mechanical_rail']['floor_overlay_sha256']=overlay
    reject(lambda:validate_legacy_floor_bindings(typed_owner,bad),'Legacy floor overlay cannot attach to upright captured rail')
    binding_schema=read(ROOT/'docs/r52/native-bindings.schema.json');ms=binding_schema['items']['properties']['mechanical_rail']
    legacy_spec=dict(kind='LEGACY_RUNNING_HEAD',leg=next(l['id'] for l in ground['legs'] if l['motion']=='ORIGINAL_UPRIGHT_TRANSFER'),source_sha256=sha(ROOT/'src/main/resources/assets/projectseele/mesh/legacy_running_heads_r52.json'),guide_source_sha256=sha(ROOT/'src/main/resources/assets/projectseele/mesh/foot_guide_rig_r52.json'),floor_overlay_sha256=overlay,controller_uuid=root_units[0]['gantry']['id'])
    sv=jsonschema.Draft202012Validator(dict(ms,**{'$defs':binding_schema['$defs']}));need(not list(sv.iter_errors(legacy_spec)),'Actual Legacy base/guide/overlay Spec schema accepted')
    bad=copy.deepcopy(legacy_spec);del bad['floor_overlay_sha256'];need(bool(list(sv.iter_errors(bad))),'Schema rejects retired base-only Legacy binding')
    n=nbtlib;native=[]
    for s in seals.values():
        g=s['gate'];hs=g['hangar_stack'];f=hs['floor_seal']
        spec=n.Compound(Width=n.Float(g['width']),Height=n.Float(g['height']),OpenTicks=n.Int(hs['open_ticks']),CloseTicks=n.Int(hs['close_ticks']),DepthDirection=n.Int(hs.get('depth_direction',1)),FloorSeal=n.Compound(Version=n.Int(1),DropM=n.Double(f['drop_m']),RetreatLocalZ=n.Double(f['retreat_local_z_m']),ClosedBoxes=n.List[n.List[n.Double]]([n.List[n.Double](box) for box in f['closed_boxes']])))
        tag=n.Compound(R52SideStack=n.Compound(Spec=spec));native.append(dict(uuid=g['visual'],role='hangar_gate',actual_source_nbt=tag.snbt()))
    need(len(validate_sealed_native_specs(native,gates))==3,'Actual final Spec verifier accepts all selected V2 fields and native types')
    missing=copy.deepcopy(native);tag=n.parse_nbt(missing[0]['actual_source_nbt']);del tag['R52SideStack']['Spec']['FloorSeal'];missing[0]['actual_source_nbt']=tag.snbt()
    reject(lambda:validate_sealed_native_specs(missing,gates),'Two boots with equally missing FloorSeal cannot pass selected Spec comparison')
    changed=copy.deepcopy(native);tag=n.parse_nbt(changed[0]['actual_source_nbt']);tag['R52SideStack']['Spec']['FloorSeal']['DropM']=n.Double(4.1);changed[0]['actual_source_nbt']=tag.snbt()
    reject(lambda:validate_sealed_native_specs(changed,gates),'Changed actual seal travel cannot pass cold comparison')
    survey=read(survey_path);shapes=read(B/'WORLD_R52/native_collision_shapes.json');actual=[]
    wanted={tuple(a['at']) for s in seals.values() for a in s['wall_bearings']};selected=defaultdict(set);in_section=defaultdict(set);states={}
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);in_section[x//16,z//16,y//16].add((x,y,z))
    files={B/f'WORLD_R52/dimensions/projectseele/geofront/region/r.{x//512}.{z//512}.mca' for x,y,z in wanted};region_pins={str(p):sha(p) for p in files}
    for cx,cz,sy,palette,ix in iter_selected_sections(B/'WORLD_R52','projectseele:geofront',selected):
        a=ix.reshape(16,16,16)
        for x,y,z in in_section[cx,cz,sy]:states[x,y,z]=palette[int(a[y%16,z%16,x%16])]
    need(len(states)==21 and all(sha(Path(p))==digest for p,digest in region_pins.items()),'Fresh finite21 native cells read from stable actual region bytes')
    historical={(a['resource'],tuple(a['at'])):a for a in survey['bearings']}
    for s in seals.values():
        for a in s['wall_bearings']:
            q=dict(a,contact_half_width_m=.10);state=states[tuple(a['at'])];old=historical.get((a['resource'],tuple(a['at'])))
            actual.append(dict(resource=a['resource'],at=a['at'],bearing=a['bearing'],historical_survey_state=old['actual_state'] if old else None,actual_state=state,face_bears=face_bears(q,shapes.get(state,[]))))
    current={(a['resource'],tuple(a['at'])) for a in actual};retired=[a for a in survey['bearings'] if (a['resource'],tuple(a['at'])) not in current]
    inputs={str(p.resolve()):sha(p) for p in (probe_path,gates_path,survey_path,design_path,units_path,cannon_path,overlay_path,ROOT/'tools/wet_front_seal_manifest_r52.py',ROOT/'tools/prepare_mechanical_native_bindings_r52.py',ROOT/'tools/build_r52_runtime_bundle_candidate.py',ROOT/'tools/prepare_r52_runtime_deployment_candidate.py',ROOT/'tools/run_r52_minimal_install_restart.py',ROOT/'docs/r52/mechanical-owner.schema.json',ROOT/'docs/r52/native-bindings.schema.json',Path(__file__))}
    report=dict(checks_passed=count,world_written=False,production_asset_written=False,native_enabled=False,fixture_only=True,actual_source_tables_have_seal=False,fixture_only_phase_additions=42,fixture_only_support_additions=21,actual_native_survey_faces=actual,actual_native_survey_pending=sum(not a['face_bears'] for a in actual),retired_historical_bearings=retired,actual_region_sha256=region_pins,controller_count=len(controllers),source_inputs=inputs,pending=['Root final new three-seal gate/tables/support manifest and native construction are not frozen; this receipt does not replace them.'])
    (OUT/'DELIVERY_METADATA_CHECKS.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ('checks_passed','controller_count','actual_native_survey_pending','fixture_only','world_written')}))
if __name__=='__main__':main()
