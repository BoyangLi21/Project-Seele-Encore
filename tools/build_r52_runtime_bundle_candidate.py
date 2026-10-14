"""Assemble actual Root continuous-upright inputs into a candidate bundle only.

No World, actor, rail, terrain or gameplay mutation. Missing real source/owner
proofs remain pending; installation intent does not manufacture native PASS.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil,uuid,subprocess,re,sys,math,zipfile,io
from prepare_r52_runtime_deployment_candidate import expected_controllers
from root_bundle_authority_r53 import arguments as authority_arguments, validate as world_authority, candidate as candidate_path
from wet_front_seal_manifest_r52 import validate_seal_phase_tables, phase_rows, sealed_front_specs

REPO=Path(__file__).resolve().parents[1]
OUT=None
ASSET=REPO/'src/main/resources/assets/projectseele'
SCHEMA_DEPS=REPO/f'.codex/r52_continuous_delivery_tools/schema_py{sys.version_info.major}{sys.version_info.minor}'
if SCHEMA_DEPS.exists():sys.path.insert(0,str(SCHEMA_DEPS))
GUIDE_PATH='facility/r52_upright_guideway_paths.json'
GUIDE_MODEL='mesh/upright_outer_captured_r52.json'
PROFILE='projectseele.r52.upright-captured-guideway.v1'
SELECTED_JAR=None
SELECTED_ASSET_SHA={}

def sha(path):
    path=Path(path).resolve()
    if SELECTED_JAR is not None and path.is_relative_to(ASSET.resolve()):
        member='assets/projectseele/'+path.relative_to(ASSET).as_posix()
        if member not in SELECTED_ASSET_SHA:
            with zipfile.ZipFile(SELECTED_JAR) as archive,archive.open(member) as stream:SELECTED_ASSET_SHA[member]=hashlib.file_digest(stream,'sha256').hexdigest()
        return SELECTED_ASSET_SHA[member]
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):
    path=Path(path).resolve()
    if SELECTED_JAR is not None and path.is_relative_to(ASSET.resolve()):
        member='assets/projectseele/'+path.relative_to(ASSET).as_posix()
        with zipfile.ZipFile(SELECTED_JAR) as archive,archive.open(member) as raw,io.TextIOWrapper(raw,encoding='utf-8') as stream:return json.load(stream)
    return json.loads(path.read_text(encoding='utf-8'))
def write(name, document):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
def records(document, key): return document[key] if isinstance(document, dict) else document
def identity(epoch, eva):
    raw = bytearray(hashlib.md5(f"projectseele:r52:original-carrier:{epoch}:{eva}".encode()).digest())
    raw[6] = (raw[6] & 15) | 48; raw[8] = (raw[8] & 63) | 128
    return str(uuid.UUID(bytes=bytes(raw)))
def production_identity(path, java, args_file):
    lines = args_file.read_text(encoding='utf-8').splitlines()
    switches = [i for i, line in enumerate(lines) if line.strip('"') in ('-classpath', '-cp')]
    if len(switches) != 1 or switches[0]+1 >= len(lines): raise ValueError('One explicit selected-node classpath required')
    cp = lines[switches[0]+1].strip('"')
    # Windows CreateProcess has a32K command-line bound. The actual game
    # dependency classpath exceeds it; Java reads the same arguments from file.
    arguments=OUT/'FINGERPRINT_JAVA.args'
    values=['-Xmx512M','-cp',cp,'com.projectseele.world.R52DirectoryFingerprint',path.as_posix()]
    arguments.write_text('\n'.join('"'+x.replace('\\','/').replace('"','\\"')+'"' for x in values)+'\n',encoding='utf-8')
    checked = subprocess.run([str(java),'@'+str(arguments)],capture_output=True,text=True,encoding='utf-8',errors='replace')
    match = re.search(r'^R52_DIRECTORY_FINGERPRINT=([0-9a-f]{64})$',checked.stdout,re.M)
    if checked.returncode or not match: raise ValueError('Production Directory parser failed: '+checked.stderr[-1500:]+checked.stdout[-1500:])
    return match.group(1)
def copy_table(reference, source_parent, prefix):
    relative = Path(reference["cells_file"])
    if relative.is_absolute() or ".." in relative.parts or ":" in str(relative): raise ValueError("Unsafe table reference")
    source = (source_parent / relative).resolve()
    if not source.is_relative_to(source_parent.resolve()) or sha(source) != reference["sha256"]: raise ValueError(f"Table SHA differs: {source}")
    target_relative = Path(prefix) / relative
    target = OUT / target_relative
    target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    return {"cells_file": target_relative.as_posix(), "sha256": sha(target)}
def unchanged_topology(original, candidate):
    for key in ("units", "nodes", "ports"):
        if candidate[key] != original[key]: raise ValueError(f"Root topology changed: {key}")
    # Root may append SPACE resources/occupancy and real native bindings.
    for key in ("legs", "routes"):
        aliases={f'bank_{bank}_rear_lane_{lane}':f'bank{bank}_rear_{lane}' for bank in (1,2) for lane in range(3)}
        def invariant(rows):
            result=[]
            for row in rows:
                value={k:v for k,v in row.items() if k!='occupancy'}
                if 'doors' in value: value['doors']=[aliases.get(x,x) for x in value['doors']]
                result.append(value)
            return result
        if invariant(candidate[key]) != invariant(original[key]): raise ValueError(f"Root path changed: {key}")

def bind_root_space_grid(directory, additions):
    if additions['grid_metres']!=32: raise ValueError('Root shared32m grid required')
    declared={x['id']:x for x in directory['resources']}
    pending={x['id']:x for x in additions['resources']}
    bindings={x['resource']:x for x in directory['runtime']['bindings']}
    for key,box in additions['space_boxes'].items():
        resource=declared.get(key)
        if resource is None or resource['kind']!='SPACE' or resource!=pending.get(key): raise ValueError('Explicit Root SPACE declaration differs: '+key)
        if len(box)!=6 or any(box[i+3]-box[i]!=32 or box[i]%32 for i in range(3)): raise ValueError('Exact Root shared grid box required')
        expected={'resource':key,'component':resource['component'],'spaces':[box]}
        if key in bindings and bindings[key]!=expected: raise ValueError('Existing Root SPACE grid binding differs')
        bindings[key]=expected
    directory['runtime']['bindings']=list(bindings.values())

def bind_original_hangar_doors(directory,gates):
    actual={g['resource']:g for g in gates};rows=[]
    for variant in range(3):
        gate=actual[f'bay_{variant}_front']
        if gate['kind']!='HANGAR' or gate['variant']!=variant: raise ValueError('Original bay seal geometry/variant differs')
        rows.append({'variant':variant,'entity_uuid':gate['visual'],'width':gate['width'],'height':gate['height']})
    if len({x['entity_uuid'] for x in rows})!=3: raise ValueError('Original wet-cage gate identities must be distinct')
    existing=directory['runtime'].get('hangar_doors')
    if existing is not None and existing!=rows: raise ValueError('Runtime original bay gates differ from actual ROOT_GATES')
    directory['runtime']['hangar_doors']=rows

def validate_runtime_declarations(directory):
    actual=directory['runtime'];routes={r['id']:r for r in directory['routes']}
    if directory['schema']=='projectseele.r52.route-directory.v2':
        if directory.get('bank_roles_version')!=1:raise ValueError('Explicit bank role version1 required')
        role_rows=directory.get('bank_roles',[])
        if len(role_rows)!=3 or {r['bank']for r in role_rows}!={1,2,3} or {r['intent']for r in role_rows}!={'surface','geofront','hakone'}:raise ValueError('Complete explicit bijective bank roles required')
        banks={r['intent']:r['bank']for r in role_rows}
        if banks!={'geofront':1,'surface':2,'hakone':3}:raise ValueError('Current compact bank roles differ from Root contract')
    elif directory['schema']=='projectseele.r52.route-directory.v1':banks={'surface':1,'geofront':2,'hakone':3}
    else:raise ValueError('Unknown explicit route-directory version')
    rows=actual.get('departure_defaults',[])
    if len(rows)!=3 or {r['variant'] for r in rows}!={0,1,2}: raise ValueError('All three original runtime departure defaults required')
    for row in rows:
        for intent,bank in banks.items():
            route=routes.get(row.get(intent))
            if route is None or route.get('reverse_of') or route['variant']!=row['variant'] or route['bank']!=bank: raise ValueError('Actual runtime departure default/variant/bank differs')
    if len(actual.get('hangar_doors',[]))!=3: raise ValueError('Actual runtime wet-cage gate declarations required')

def continuous_ground(ground):
    if not ground.get('routes') or any(not isinstance(r.get('motion_profile'),dict) or r['motion_profile'].get('type')!='continuous_upright' for r in ground['routes']):raise ValueError('Actual continuous_upright route declarations required')
    if any(row['motion']=='FOOT_BEARING_TURN' for row in ground['legs']):raise ValueError('Retired stationary turns cannot enter the new bundle')
    for key in ('legs','routes','resources','nodes'):
        if len({row['id'] for row in ground[key]})!=len(ground[key]):raise ValueError('Duplicate actual Root declaration: '+key)

def canonical_curve(document):
    result=[]
    for row in document['segments']:
        points=row['controls'];kind='LINE' if len(points)==2 else 'QUINTIC_BEZIER' if len(points)==6 else None
        if kind is None or set(row)-{'controls','type','kind'} or row.get('type',row.get('kind',kind))!=kind or any(len(p)!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in p) for p in points):raise ValueError('Actual explicit finite LINE/QUINTIC_BEZIER controls required')
        result.append({'type':kind,'controls':points})
    if not result:raise ValueError('Actual nonempty source centre_curve required')
    return {'segments':result}

def validate_upright_gate_ports(owner):
    for gate in owner['gates']:
        if gate['kind']!='SILO':continue
        spec=gate['silo_hatch'];expected=spec['opening_x']==31 and spec['opening_z']==31 and spec.get('separation_sign',1)==1
        if spec.get('upright_guide_ports',False) is not expected:raise ValueError('Actual31x31up gate requires explicit upright guide slots; service/pit gates must remain false: '+gate['resource'])

def validate_rear_hangar_depth(owner,ground):
    aliases={} if ground.get('schema')=='projectseele.r52.route-directory.v2' else {f'bank_{b}_rear_lane_{i}':f'bank{b}_rear_{i}' for b in (1,2) for i in range(3)}
    rear={aliases.get(door,door) for leg in ground['legs'] if leg['motion']=='TRACKED_BANK_TRANSFER' for door in leg['doors']}
    gates={g['resource']:g for g in owner['gates']}
    if len(rear)!=6 or any(key not in gates or gates[key]['kind']!='HANGAR' or gates[key]['hangar_stack'].get('depth_direction',1)!=-1 for key in rear):raise ValueError('Exact six actual tracked-transfer rear HANGAR gates require explicit depth_direction=-1')
    for key,gate in gates.items():
        if gate['kind']=='HANGAR' and key not in rear and gate['hangar_stack'].get('depth_direction',1)!=1:raise ValueError('Original nonrear HANGAR depth direction must retain compatible1: '+key)

def validate_guideway(report,ground,ground_sha):
    if report.get('profile')!=PROFILE or report.get('directory_geometry_sha256')!=ground_sha:raise ValueError('Fresh actual guideway/Root geometry report required')
    if report.get('model_source_sha256')!=sha(ASSET/GUIDE_MODEL) or report.get('path_source_sha256')!=sha(ASSET/GUIDE_PATH):raise ValueError('Actual selected guideway model/path bytes differ')
    actual=read(ASSET/GUIDE_PATH)
    if actual.get('schema')!='projectseele.r52.upright-captured-paths.v1' or actual.get('model_source_sha256')!=report['model_source_sha256']:raise ValueError('Actual new guideway source schema/model differs')
    legs={row['id']:row for row in ground['legs']};nodes={row['id']:row for row in ground['nodes']};rows=actual.get('paths',[]);ids=set()
    for row in rows:
        leg=legs.get(row['leg']);reverse=legs.get(row['reverse_leg'])
        if leg is None or reverse is None or row['leg'] in ids or row['reverse_leg'] in ids or leg['from']!=reverse['to'] or leg['to']!=reverse['from']:raise ValueError('Actual guideway path/complete reverse declarations differ')
        if canonical_curve(row['centre_curve'])!=canonical_curve(leg['centre_curve']):raise ValueError('Actual guideway source controls differ from Root directory')
        if row.get('from')!=nodes[leg['from']]['foot_frame'] or row.get('to')!=nodes[leg['to']]['foot_frame']:raise ValueError('Actual guideway source endpoint frames differ from Root directory')
        variants={r['variant'] for r in ground['routes'] if leg['id'] in r['legs']}
        if variants!={row.get('variant')}:raise ValueError('Actual guideway source variant differs from Root route membership')
        ids.update((row['leg'],row['reverse_leg']))
    wanted={row['id'] for row in ground['legs'] if 'centre_curve' in row}
    if ids!=wanted:raise ValueError('Guideway source does not cover exact new curve/reverse leg set')
    if actual.get('head_transfer_source_sha256')!=sha(ASSET/'mesh/outer_head_transfer_r53.json'):raise ValueError('Actual selected head slide/socket source differs')
    if not actual.get('pieces') or not actual.get('anchors'):raise ValueError('Actual steel and finite native bearing declarations required; no empty ready guideway')
    for piece in actual['pieces']:
        triangles=piece['triangles_rgb'];frame=piece['frame']
        if piece['leg'] not in {row['leg'] for row in rows} or piece['component'] not in {'head','web','bracket','native_seat'} or len(triangles)<18 or len(triangles)%18 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in triangles) or len(frame['translation'])!=3 or len(frame['quaternion_xyzw'])!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in frame['translation']+frame['quaternion_xyzw']):raise ValueError('Actual finite selected steel triangles/frame required')
    names={p['name']:p for p in actual['pieces']}
    if len(names)!=len(actual['pieces']):raise ValueError('Actual steel source piece identities aliased')
    covered=set()
    for anchor in actual['anchors']:
        seat=names.get(anchor['seat_piece'])
        if anchor['leg'] not in {row['leg'] for row in rows} or seat is None or seat['leg']!=anchor['leg'] or seat['component']!='native_seat' or len(anchor['at'])!=3 or len(anchor['bearing'])!=3 or len(anchor['normal'])!=3 or anchor['state'].split('[')[0] in ('minecraft:air','minecraft:cave_air','minecraft:void_air'):
            raise ValueError('Actual finite steel seat/World bearing declaration differs')
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in anchor['bearing']+anchor['normal']) or any(type(v) is not int for v in anchor['at']) or sum(v*v for v in anchor['normal'])<1e-12:raise ValueError('Actual finite native face normal/bearing/block cell required')
        covered.add(anchor['leg'])
    if covered!={row['leg'] for row in rows}:raise ValueError('Every actual new guideway path needs complete real steel/World bearing declaration')
    return actual

def validate_source_envelopes(envelope,ground,ground_sha):
    if envelope.get('full_source_sha256')!=sha(ASSET/'eva/full_assembly_geometry_r52_sources.json'):raise ValueError('Whole assembly source report must match selected source')
    if envelope.get('legacy_floor_overlay_sha256')!=sha(ASSET/'mesh/legacy_floor_recesses_r52.json'):raise ValueError('Fresh independent selected Legacy floor overlay envelope binding required')
    for field,source in [('service_overlay_sha256','mesh/legacy_service_bypass_r52.json'),('level_overlay_sha256','mesh/legacy_compact_level_r52.json'),('deep_frame_sha256','mesh/legacy_deep_frame_r53.json'),('head_transfer_source_sha256','mesh/outer_head_transfer_r53.json')]:
        if envelope.get(field)!=sha(ASSET/source):raise ValueError('Complete envelope must bind current selected '+field)
    if envelope.get('model_source_sha256')!=sha(ASSET/GUIDE_MODEL) or envelope.get('path_source_sha256')!=sha(ASSET/GUIDE_PATH) or envelope.get('directory_geometry_sha256')!=ground_sha:raise ValueError('Fresh actual upright guideway/geometry envelope proof required')
    rows=envelope.get('root_legs',[]);wanted={row['id'] for row in ground['legs']}
    if not envelope.get('directory_matches') or len(rows)!=len(wanted) or {row['leg'] for row in rows}!=wanted:raise ValueError('Whole source envelope must cover each actual Root leg once')
    for row in rows:
        interval=row['maximum_foot_interval_m']
        if not isinstance(interval,(int,float)) or not 0<=interval<=16 or not row.get('reservation_boxes'):raise ValueError('Finite actual complete assembly intervals at most16m required')

def validate_physical_receipt(doc,ground_sha,guide_report,owner,world):
    if doc.get('schema')!='projectseele.r52.actual-continuous-physical-readback.v1' or doc.get('map_author')!='root' or not isinstance(doc.get('world'),str) or Path(doc['world']).resolve()!=Path(world).resolve() or doc.get('verified') is not True:raise ValueError('Root actual World physical readback receipt required')
    wanted={'ground_sha256':ground_sha,'guide_source_sha256':sha(ASSET/GUIDE_PATH),'model_source_sha256':sha(ASSET/GUIDE_MODEL),'floor_overlay_sha256':sha(ASSET/'mesh/legacy_floor_recesses_r52.json')}
    wanted.update({field:sha(ASSET/source) for field,source in [('service_overlay_sha256','mesh/legacy_service_bypass_r52.json'),('level_overlay_sha256','mesh/legacy_compact_level_r52.json'),('deep_frame_sha256','mesh/legacy_deep_frame_r53.json'),('head_transfer_source_sha256','mesh/outer_head_transfer_r53.json')]})
    for key,value in wanted.items():
        if doc.get(key)!=value:raise ValueError('Physical readback selected source differs: '+key)
    if 'gate_source_sha256' in guide_report and doc.get('gate_source_sha256')!=guide_report['gate_source_sha256']:raise ValueError('Physical readback/final guide report must bind same actual selected gate bytes')
    if not isinstance(doc.get('gate_source_sha256'),str) or not re.fullmatch('[0-9a-f]{64}',doc['gate_source_sha256']):raise ValueError('Actual final gate source SHA required')
    interlocks=doc.get('interlocks',{})
    actual={name:len(s['cells']) for name,s in sealed_front_specs(owner['gates']).items()}
    recorded=interlocks.get('peer_proxy_cells_by_bay')
    if recorded is None and set(actual.values())=={14}:recorded={name:interlocks.get('peer_proxy_cells_per_bay') for name in actual}
    if interlocks.get('front_motion_requires_pit_open') is not True or recorded!=actual or interlocks.get('return_front_seal_before_pit') is not True:raise ValueError('Actual exact PIT/front phase contract must be recorded; not unconditional pair0 or stale14cell proxy')
    evidence=doc.get('evidence');
    if not isinstance(evidence,dict) or not evidence:raise ValueError('Actual Root construction/readback/scope evidence files required')
    if doc['gate_source_sha256'] not in evidence.values():raise ValueError('Physical evidence must include actual selected gate file bytes')
    for name,digest in evidence.items():
        path=Path(name)
        if not path.is_absolute() or not path.is_file() or sha(path)!=digest:raise ValueError('Actual physical evidence bytes differ: '+name)

def bind_mechanical_sources(directory,owner,requirements,ground_sha,selected_guide=None):
    if requirements.get('directory_geometry_sha256')!=ground_sha:raise ValueError('Mechanical rail requirements refer to another actual Root geometry')
    raw=requirements['mechanical_rail_requirements'];declared={row['resource']:row for row in raw};resources=owner['resources'];by_leg={row['id']:row for row in directory['legs']};by_resource={row['id']:row for row in directory['resources']};rails={row['id'] for row in directory['resources'] if row['kind']=='RAIL'}
    if len(declared)!=len(raw) or set(declared)!=rails:raise ValueError('Exact actual Root rail resource requirement set required')
    bindings={row['resource']:copy.deepcopy(row) for row in directory['runtime']['bindings']};units={u['variant']:u for u in owner['units']};gates={g['resource']:g for g in owner['gates']}
    for key,row in declared.items():
        spec=copy.deepcopy(row['mechanical_rail']);kind=spec['kind'];leg=by_leg.get(spec['leg'])
        if leg is None or key not in leg['rails']:raise ValueError('Actual mechanical rail/leg mismatch')
        if kind=='UPRIGHT_CAPTURED_GUIDEWAY':
            if 'centre_curve' not in leg or spec.get('controller_uuid','missing') is not None or spec.get('foundation_top_m','missing') is not None:raise ValueError('Static actual upright guideway requires explicit null controller/foundation')
            if spec['source_sha256']!=sha(ASSET/GUIDE_PATH) or spec['guide_source_sha256']!=sha(ASSET/GUIDE_MODEL):raise ValueError('Upright rail source/model SHA differs')
            cells=copy.deepcopy(row.get('cells'))
            if not cells:raise ValueError('Actual Root guideway bearing cells/states missing')
        elif kind=='LEGACY_RUNNING_HEAD':
            if 'centre_curve' in leg or spec['source_sha256']!=sha(ASSET/'mesh/legacy_running_heads_r52.json') or spec['guide_source_sha256']!=sha(ASSET/'mesh/foot_guide_rig_r52.json'):raise ValueError('Original lead/source declaration differs')
            if spec.get('floor_overlay_sha256')!=sha(ASSET/'mesh/legacy_floor_recesses_r52.json'):raise ValueError('Independent actual Legacy floor overlay source differs')
            if spec.get('service_overlay_sha256')!=sha(ASSET/'mesh/legacy_service_bypass_r52.json'):raise ValueError('Independent actual service-pipe overlay source differs')
            if spec.get('deep_frame_sha256')!=sha(ASSET/'mesh/legacy_deep_frame_r53.json'):raise ValueError('Exact approved rigid deep frame source differs')
            if spec.get('level_overlay_sha256')!=sha(ASSET/'mesh/legacy_compact_level_r52.json'):raise ValueError('Independent finite compact level overlay source differs')
            candidates=[u for u in owner['units'] if u['gantry']['id']==spec.get('controller_uuid')]
            if len(candidates)!=1 or spec.get('foundation_top_m') is not None:raise ValueError('Actual original gantry controller required for lead rail')
            u=candidates[0];cells=list({tuple(c['position']):copy.deepcopy(c) for c in u['gantry']['supports']+u['carrier_support']}.values())
        else:raise ValueError('Old Dock/station/fixed-turn rail family forbidden in the new mode: '+kind)
        if any(c['state'].split('[')[0] in ('minecraft:air','minecraft:cave_air','minecraft:void_air') for c in cells):raise ValueError('Air cannot stand in for actual finite rail support')
        if kind=='UPRIGHT_CAPTURED_GUIDEWAY':
            actual=selected_guide if selected_guide is not None else read(ASSET/GUIDE_PATH);anchors=[a for a in actual['anchors'] if a['leg']==spec['leg']]
            wanted={tuple(a['at']):a['state'] for a in anchors};observed={tuple(c['position']):c['state'] for c in cells}
            if not anchors or observed!=wanted:raise ValueError('Typed null controller cannot waive the exact actual guideway World support cells')
        resources[key]=copy.deepcopy(cells);bindings[key]={'resource':key,'component':by_resource[key]['component'],'mechanical_rail':spec,'cells':cells}
    for key,row in by_resource.items():
        if row['kind']=='DOOR':
            g=gates.get(key)
            if g is None:raise ValueError('Actual Root gate missing: '+key)
            bindings[key]={'resource':key,'component':row['component'],'entity_uuid':g['visual'],'expected_type':'projectseele:nerv_hangar_door' if g['kind']=='HANGAR' else 'projectseele:nerv_silo_door','required_open':1}
        elif row['kind']=='SUPPORT':
            cells=resources.get(key)
            if not cells:raise ValueError('Actual Root support cells missing: '+key)
            bindings[key]={'resource':key,'component':row['component'],'cells':copy.deepcopy(cells)}
    directory['runtime']['bindings']=list(bindings.values())

def copy_owner_tables(value,parent):
    if isinstance(value,dict):
        if 'cells_file' in value:return copy_table(value,parent,'tables/owner')
        return {key:copy_owner_tables(row,parent) for key,row in value.items()}
    if isinstance(value,list):return [copy_owner_tables(row,parent) for row in value]
    return value

def main():
    global OUT,SELECTED_JAR
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ground',type=Path,required=True);ap.add_argument('--ground-sha256',required=True)
    ap.add_argument('--native-directory',type=Path,required=True);ap.add_argument('--owner-manifest',type=Path,required=True)
    ap.add_argument('--guideway-report',type=Path,required=True);ap.add_argument('--mechanical-rails',type=Path,required=True)
    ap.add_argument('--envelopes',type=Path,required=True);ap.add_argument('--lead-report',type=Path,required=True)
    ap.add_argument('--shared-space-additions',type=Path);ap.add_argument('--air-transport',type=Path,required=True);ap.add_argument('--personnel-lifts',type=Path,required=True);ap.add_argument('--fixed-cannon',type=Path,help='Optional explicitly selected cannon; omit for scope124')
    ap.add_argument('--installed-intent',action='store_true');ap.add_argument('--physical-receipt',type=Path)
    ap.add_argument('--java',type=Path,default=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe'));ap.add_argument('--parser-classpath-args',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True,help='Fresh candidate subdirectory; preserve previous generated receipts')
    ap.add_argument('--selected-jar',type=Path,help='Actual immutable final Jar resource authority')
    ap.add_argument('--selected-build-receipt',type=Path,help='Matching successful immutable build receipt')
    authority_arguments(ap)
    args=ap.parse_args()
    authority=world_authority(args)
    if bool(args.selected_jar)!=bool(args.selected_build_receipt):raise ValueError('Selected final Jar and actual build receipt must be supplied together')
    if args.selected_jar:
        from build_immutable_r52_candidate import frozen_build_class_pins
        frozen_build_class_pins(args.selected_build_receipt,args.selected_jar);SELECTED_JAR=args.selected_jar.resolve()
    OUT=candidate_path(args.out,args.world,True)
    OUT.mkdir(parents=True,exist_ok=True)
    if sha(args.ground)!=args.ground_sha256:raise ValueError('Explicit actual Root ground SHA differs')
    ground=read(args.ground);world_authority(args,directory=ground);continuous_ground(ground);directory=read(args.native_directory);unchanged_topology(ground,directory);continuous_ground(directory)
    owner=copy.deepcopy(read(args.owner_manifest));validate_upright_gate_ports(owner);validate_rear_hangar_depth(owner,ground);cannon=read(args.fixed_cannon) if args.fixed_cannon else None;expected_controllers({'epoch':ground['epoch']},owner,ground,cannon)
    if SELECTED_JAR:
        for name,digest in owner['mechanism_sources'].items():
            if sha(ASSET/name)!=digest:raise ValueError('Owner mechanism source differs from actual selected Jar: '+name)
    validate_seal_phase_tables(owner['gates'],lambda g:phase_rows(g,args.owner_manifest.parent))
    if owner.get('schema')!='projectseele.r52.mechanical-owner.v1' or owner.get('map_author')!='root' or owner.get('epoch')!=ground['epoch']:raise ValueError('Actual Root owner manifest/epoch required')
    if owner.get('ground_guides',{}).get('mode')!='continuous_upright' or owner['ground_guides'].get('dock_foundations') or 'dock_source_sha256' in owner['ground_guides']:raise ValueError('Actual new captured guideway owner declaration required; old Dock data forbidden')
    report=read(args.guideway_report);selected_guide=validate_guideway(report,ground,args.ground_sha256);validate_source_envelopes(read(args.envelopes),ground,args.ground_sha256)
    if owner['ground_guides']['source_sha256']!=sha(ASSET/GUIDE_MODEL) or owner['ground_guides']['paths_sha256']!=sha(ASSET/GUIDE_PATH):raise ValueError('Owner model/path source differs from actual guideway')
    lead=read(args.lead_report)
    if lead.get('source')!=sha(ASSET/'mesh/legacy_running_heads_r52.json') or lead.get('full_source')!=sha(ASSET/'eva/full_assembly_geometry_r52_sources.json') or lead.get('legacy_helper_java_sha256')!=sha(REPO/'src/main/java/com/projectseele/world/NervLegacyCarrierRideR52.java'):raise ValueError('Fresh actual original lead/full-source/helper proof required')
    if lead.get('floor_overlay_sha256')!=sha(ASSET/'mesh/legacy_floor_recesses_r52.json') or lead.get('actual_floor_overlay_bytes_sha256')!=lead['floor_overlay_sha256'] or owner['mechanism_sources'].get('mesh/legacy_floor_recesses_r52.json')!=lead['floor_overlay_sha256']:raise ValueError('Fresh selected original provider/owner must lock actual independent floor overlay')
    if args.shared_space_additions:bind_root_space_grid(directory,read(args.shared_space_additions))
    bind_original_hangar_doors(directory,owner['gates']);validate_runtime_declarations(directory);bind_mechanical_sources(directory,owner,read(args.mechanical_rails),args.ground_sha256,selected_guide)
    bound={row['resource'] for row in directory['runtime']['bindings']};wanted={row['id'] for row in directory['resources']}
    if bound!=wanted:raise ValueError('Actual native binding/resource set differs')
    if {row['port'] for row in owner['receivers']}!={row['id'] for row in directory['ports']}:raise ValueError('Actual complete receiver/port declarations differ')
    pending=[]
    if args.installed_intent and not args.physical_receipt:pending.append('Root actual guideway/whole assembly physical readback receipt is still required')
    if args.physical_receipt:validate_physical_receipt(read(args.physical_receipt),args.ground_sha256,report,owner,args.world)
    provenance={str(path):sha(path) for path in [args.ground,args.native_directory,args.owner_manifest,args.guideway_report,args.mechanical_rails,args.envelopes,args.lead_report,args.air_transport,args.personnel_lifts,args.baseline,args.root_plan]}
    if args.fixed_cannon:provenance[str(args.fixed_cannon)]=sha(args.fixed_cannon)
    for path in (args.physical_receipt,args.shared_space_additions):
        if path:provenance[str(path)]=sha(path)
    for path in (args.selected_jar,args.selected_build_receipt):
        if path:provenance[str(path)]=sha(path)
    receipt={'schema':'projectseele.r52.candidate-bundle-assembly-receipt.v1','map_author':'root','root_world_authority':authority,'feature_scope':'124+explicit_fixed_cannon' if cannon is not None else '124','world_written':False,'native_commissioned':False,'native_cycle_passed':False,'installation_intent':args.installed_intent,'pending':pending,'inputs':provenance}
    receipt_file=write('ASSEMBLY_CANDIDATE_RECEIPT.json',receipt)
    if pending:print(json.dumps({'ready':False,'pending':pending,'receipt':str(receipt_file)}));return
    status='installed' if args.installed_intent else 'design';directory['status']=status
    if args.installed_intent:directory['installation_receipt_sha256']=sha(args.physical_receipt)
    directory_file=write('ROOT_RUNTIME_DIRECTORY.json',directory);fingerprint=production_identity(directory_file,args.java,args.parser_classpath_args)
    owner=copy_owner_tables(owner,args.owner_manifest.parent);owner.update(status=status,directory_fingerprint=fingerprint,commissioning_receipt_sha256=sha(args.physical_receipt) if args.physical_receipt else sha(receipt_file));owner_file=write('ROOT_MECHANICAL_OWNER.json',owner)
    guide_file=OUT/'UPRIGHT_GUIDEWAY_SOURCE.json'
    if SELECTED_JAR:
        with zipfile.ZipFile(SELECTED_JAR) as archive,archive.open('assets/projectseele/'+GUIDE_PATH) as source,guide_file.open('xb') as destination:shutil.copyfileobj(source,destination,1024*1024)
    else:guide_file.write_bytes((ASSET/GUIDE_PATH).read_bytes())
    if sha(guide_file)!=owner['ground_guides']['paths_sha256']:raise ValueError('Copied exact guideway source bytes differ')
    bundle={'schema':'projectseele.r52.assembly-installation.v1','map_author':'root','status':status,'dimension':directory['nodes'][0]['dimension'],'epoch':directory['epoch'],'directory_fingerprint':fingerprint,'directory':{'file':directory_file.name,'sha256':sha(directory_file)},'mechanical_owner':{'file':owner_file.name,'sha256':sha(owner_file)},'upright_guideway':{'file':guide_file.name,'sha256':sha(guide_file)}}
    lifts=read(args.personnel_lifts)
    if lifts['epoch']!=directory['epoch']:raise ValueError('Original lift epoch differs; no identity reset admitted')
    lifts['directory_fingerprint']=fingerprint;lifts_file=write('personnel_lifts_r52.json',lifts);bundle['personnel_lifts']={'file':lifts_file.name,'sha256':sha(lifts_file)}
    if cannon is not None:
        cannon['installed']=args.installed_intent;cannon_file=write('yashima_cannon_station_r52.json',cannon);bundle['fixed_cannon']={'file':cannon_file.name,'sha256':sha(cannon_file)}
    air=read(args.air_transport);air.update(directory_fingerprint=fingerprint,status=status);air_file=write('ROOT_AIR_TRANSPORT.json',air);bundle['air_transport']={'file':air_file.name,'sha256':sha(air_file)}
    bundle_file=write('ROOT_ASSEMBLY_BUNDLE.json',bundle)
    import jsonschema
    for name,document in [('mechanical-owner.schema.json',owner),('assembly-installation.schema.json',bundle),('native-bindings.schema.json',directory['runtime']['bindings'])]:jsonschema.Draft202012Validator(read(REPO/'docs/r52'/name)).validate(document)
    controllers=expected_controllers(bundle,owner,directory,cannon);receipt.update(pending=[],schema_valid=True,production_parser_valid=False,directory_fingerprint=fingerprint,bundle=str(bundle_file),expected_controllers=controllers,expected_controller_count=len(controllers),native_entry='/nerv r52 install <Root-copied exact ROOT_ASSEMBLY_BUNDLE.json>')
    write('ASSEMBLY_CANDIDATE_RECEIPT.json',receipt);print(json.dumps({'ready':True,'status':status,'controllers':len(controllers),'bundle':str(bundle_file),'production_parser_pending':True,'native_commissioned':False}))
if __name__=='__main__':main()
