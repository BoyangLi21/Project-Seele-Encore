"""One read-only current scope124 source/report/bundle entry. Never starts Minecraft.

Inputs are Root's explicit CURRENT_SCOPE124_INSTALL_INPUTS.json; no newest-file
selection, old World fallback, historical PASS import or construction mutation.
"""
import argparse,copy,hashlib,json,math,subprocess,sys,zipfile
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from root_bundle_authority_r53 import validate as authority, candidate
from build_immutable_r52_candidate import frozen_build_class_pins
from prepare_ground_space_r52 import leg_intervals
from wet_front_seal_manifest_r52 import phase_rows,sealed_front_specs
from query_blocks import iter_selected_sections
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'.Codex/map_complete_20261013/route_audit'
DEFAULTS={
 'ascent_hulls':('launch_hulls_v2_seated_plug/final_68cc/CURRENT_COMPLETE_NINE_ASCENT_HEIGHT_HULLS.json','3984d617ec4ea86765fb0a9fbf6b4acdd05552c2b504756c5eb42d4401b3c07b'),
 'prelaunch_envelopes':('prelaunch_world_current/CURRENT_PRELAUNCH_PART_ENVELOPES.json','b5f8fb21748bfc0066e9ad7aba558ee79a2e8f8e8638af63d84316894cb0ddb6'),
 'seated_plug_envelopes':('seated_plug_prelaunch/TRUE_PLUG_ENVELOPES.json','ed080c0b8c484c8b6bff70194cf9b3d7c2d3b9af7bd1053c97c4eea0f0a0e6f1'),
 'gate_interface':('wet_floor_expansion_v2/full_throat/CURRENT_TYPED_GATE_INTERFACE.json','bc521d1dbddb9e1075a0b5a7bedf2da26f509312b9b6839d9835f8296fc9192c'),
 'gate_peer':('wet_floor_expansion_v2/full_throat/CURRENT_GATE_PEER_CYCLE.json','fd012ca0309ffef5515e8a84ad958ad026dd8c1d1250f4c85b941e711b4245d6'),
 'bank_head_envelopes':('bank_world_current/CURRENT_ALL48_PART_ENVELOPES.json','41eb2e27521317855d7ae020c41073fb4bea2bc2030be2cfecea2a9427b5dd83'),
 'air_space_additions':('../requirements_audit/flight124/root_frame_candidate_v4_terminal84/GROUND_ADDITIONAL_SPACE.json','4c22fcc65532bff7eee0e3f736d53c2dc20bc323649c74f8aa4d7971cf5bd0ec'),
}
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf8');return p
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def selected(row):
 need(isinstance(row,dict) and {'path','sha256'}<=row.keys(),'Explicit path/SHA input required')
 p=Path(row['path']).resolve();need(p.is_file() and sha(p)==row['sha256'],'Current input missing or SHA changed: '+str(p));return p
def run(name,cmd,out):
 with (out/(name+'.log')).open('wb') as f:r=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 need(r.returncode==0,name+' failed; see '+str(out/(name+'.log')))
def java_args(p,values):p.write_text('\n'.join('"'+str(x).replace('\\','/').replace('"','\\"')+'"' for x in values)+'\n','utf8');return '@'+str(p)
def union(boxes):
 need(boxes,'Actual nonempty geometry required');return [min(b[i] for b in boxes)for i in range(3)]+[max(b[i+3] for b in boxes)for i in range(3)]
def merge_air_spaces(ground,additions,air,ground_sha):
 need(additions['source_sha256']==ground_sha,'Air SPACE additions refer to different ground geometry')
 resources={r['id']:r for r in ground['resources']};bindings={r['resource']:r for r in ground['runtime']['bindings']}
 for row in additions['new_spaces']:
  r,b=row['resource'],row['binding'];key=r['id'];need(r==dict(id=key,kind='SPACE',component=key) and key.startswith('space/c'),'Only explicit canonical air SPACE additions admitted')
  coordinates=[int(v) for v in key.removeprefix('space/c').split('_')];need(len(coordinates)==3 and key=='space/c'+'_'.join(str(v)for v in coordinates),'Exact canonical shared-space identity required')
  expected=dict(resource=key,component=key,spaces=[[v*32 for v in coordinates]+[(v+1)*32 for v in coordinates]])
  need(b==expected and (key not in resources or resources[key]==r) and (key not in bindings or bindings[key]==b),'Air/static SPACE conflicts')
  resources[key]=copy.deepcopy(r);bindings[key]=copy.deepcopy(b)
 required=set()
 def walk(value):
  if isinstance(value,dict):
   if 'occupancy' in value:required.update(value['occupancy'])
   for child in value.values():walk(child)
  elif isinstance(value,list):
   for child in value:walk(child)
 walk(air)
 need(required and all(k in resources and resources[k]['kind']=='SPACE' and k in bindings for k in required),'Current air references undeclared shared SPACE')
 ground['resources']=list(resources.values());ground['runtime']['bindings']=list(bindings.values())
 return dict(actual_air_space_references=len(required),explicit_additions=len(additions['new_spaces']),total_space_resources=sum(r['kind']=='SPACE'for r in resources.values()))
def asset_pins(jar):
 with zipfile.ZipFile(jar)as z:return {n.removeprefix('assets/projectseele/'):hashlib.sha256(z.read(n)).hexdigest()for n in z.namelist()if n.startswith('assets/projectseele/') and n.endswith('.json')}
def export_sources(f,out,java):
 build=read(f['selected_build_receipt']);frozen_build_class_pins(f['selected_build_receipt'],f['selected_jar'])
 named=Path(build['named_class_directory']);manifest=selected(dict(path=build['named_class_manifest'],sha256=build['named_class_manifest_sha256']))
 pins=read(manifest);need(pins and all((named/n).is_file() and sha(named/n)==h for n,h in pins.items()),'Same-build named production class bytes changed')
 state=read(f['compile_state']);need(Path(state['destination']).resolve()==named.resolve(),'Compile-state/named production directory differs')
 cp=[str(named),str(f['selected_jar'])]+state['classpath'];need(all(Path(p).exists()for p in cp),'Actual current dependency absent')
 classes=out/'report_classes';classes.mkdir(exist_ok=True)
 sources=[ROOT/'tools/java/ExportCurrentRuntimeSourcesR53.java',ROOT/'tools/java/R52DirectoryFingerprint.java']
 run('compile_report_entry',[java.with_name('javac.exe'),java_args(out/'compile_report_entry.args',['-J-Xmx768m','-proc:none','--release','17','-encoding','UTF-8','-sourcepath',out/'empty','-cp',';'.join(cp),'-d',classes,*sources])],out)
 cp=[str(classes)]+cp
 run('production_source_export',[java,java_args(out/'production_source_export.args',['-Xmx1800m','-cp',';'.join(cp),'com.projectseele.world.ExportCurrentRuntimeSourcesR53',f['ground'],f['guide_source'],f['units'],f['gates'],ROOT,out])],out)
 return out/'production_source_export.args'
def source_spaces(f,out,pins,domains):
 ground=read(f['ground']);hulls=read(f['ascent_hulls']);lead=read(out/'CURRENT_LEGACY_LEAD_REPORT.json')
 air_merge=merge_air_spaces(ground,read(f['air_space_additions']),read(f['air_transport']),sha(f['ground']))
 need(hulls['root_design_sha256']==sha(f['ground']) and hulls['head_source_sha256']==pins['mesh/outer_head_transfer_r53.json'] and hulls['current_head_continuous_coverage'],'Current complete inserted-plug hull/whole launch tangent source differs')
 for p,h in hulls['source_sha256'].items():need(sha(p)==h,'Actual hull producer/source changed: '+p)
 pre=read(f['prelaunch_envelopes']);plug=read(f['seated_plug_envelopes']);bank=read(f['bank_head_envelopes'])
 seated=read(plug['binding_receipt']);need(seated['full_assembly_source_sha256']==pins['eva/full_assembly_geometry_r52_sources.json'],'Actual seated plug/full source differs from selected Jar')
 for key in ('body_pose','dorsal_profile'):need(sha(seated[key+'_source'])==seated[key+'_sha256'],'Actual seated-plug pose profile changed: '+key)
 need(bank['head_source_sha256']==pins['mesh/outer_head_transfer_r53.json'],'Actual complete bank-head source differs')
 rebind=read(plug['prelaunch_geometry_rebind']);need(rebind['directory_sha256']==sha(f['ground']) and rebind['fixed_component_bytes_unchanged'],'Explicit unchanged current prelaunch geometry rebind required')
 locals_={}
 for v in hulls['variants']:
  boxes=[]
  for s in v['height_slices_1m']:
   y=s['height_band_m'];p=s['actual_clipped_XZ_convex_hull_m'];boxes.append([min(x[0]for x in p),y[0],min(x[1]for x in p),max(x[0]for x in p),y[1],max(x[1]for x in p)])
  locals_[v['variant']]=union(boxes)
 resources={r['id']:r for r in ground['resources']};bindings={r['resource']:r for r in ground['runtime']['bindings']};nodes={n['id']:n for n in ground['nodes']};tickets=set();rows=[];source_planes=[]
 def reserve(leg,b):
  need(len(b)==6 and all(math.isfinite(x)for x in b) and all(b[i]<=b[i+3]for i in range(3)) and sum(b[i]<b[i+3]for i in range(3))>=2,'Finite physical surface reservation extent required')
  collapsed=[i for i in range(3)if b[i]==b[i+3]]
  if collapsed:
   original=list(b)
   for i in collapsed:b[i]-=.005;b[i+3]+=.005
   source_planes.append(dict(leg=leg['id'],actual_source_bounds=original,reservation_bounds=list(b),purpose='5mm each side of the measured finite source plane; occupancy only, no source geometry or World edit'))
  ids=[]
  for x in range(math.floor((b[0]-.005)/32),math.floor((b[3]+.005)/32)+1):
   for y in range(math.floor((b[1]-.005)/32),math.floor((b[4]+.005)/32)+1):
    for z in range(math.floor((b[2]-.005)/32),math.floor((b[5]+.005)/32)+1):
     key=f'space/c{x}_{y}_{z}';r=dict(id=key,kind='SPACE',component=key);binding=dict(resource=key,component=key,spaces=[[x*32,y*32,z*32,(x+1)*32,(y+1)*32,(z+1)*32]])
     need(key not in resources or resources[key]==r,'Existing SPACE declaration differs');need(key not in bindings or bindings[key]==binding,'Existing SPACE binding differs');resources[key]=r;bindings[key]=binding;ids.append(key)
  leg['occupancy']=sorted(set(leg['occupancy'])|set(ids))
  for x in range(math.floor(b[0]/16),math.floor(b[3]/16)+1):
   for z in range(math.floor(b[2]/16),math.floor(b[5]/16)+1):tickets.add((x,z))
 actual={r['leg']:[p['bounds']for p in r['parts']if p['family']!='PLUG']for r in pre['legs']}
 for r in plug['legs']:need(r['leg'] in actual,'Seated plug/retained leg mismatch');actual[r['leg']]+=[p['bounds']for p in r['parts']]
 head={r['bank']:[p['bounds']for p in r['parts']]for r in bank['banks']}
 for leg in ground['legs']:
  variants={r['variant']for r in ground['routes']if leg['id']in r['legs']};need(len(variants)==1,'Original variant per leg required');v=next(iter(variants));local=locals_[v];intervals=leg_intervals(leg,nodes);boxes=[]
  for controls,_ in intervals:boxes.append([min(p[i]for p in controls)+local[i]-.025 for i in range(3)]+[max(p[i]for p in controls)+local[i+3]+.025 for i in range(3)])
  forward=leg['id'].removesuffix('/reverse');boxes+=actual.get(forward,[])
  for r in ground['routes']:
   if not r.get('reverse_of') and forward in r['legs'] and r['id']in head:boxes+=head[r['id']]
  if forward==f'unit{v}/original_incline':
   row=next(x for x in lead['rows']if x['variant']==v);boxes += [row['source_bounds'],row['actual_carrier_reservation_bounds']]
   bay=nodes[f'unit{v}/bay']['foot_frame']['translation'];boxes.append([bay[i]+local[i]-(64 if i==1 else 0)for i in range(3)]+[bay[i]+local[i+3]+(64 if i==1 else 0)for i in range(3)])
  for b in boxes:reserve(leg,b)
  rows.append(dict(leg=leg['id'],variant=v,maximum_foot_interval_m=max(b for _,b in intervals),reservation_boxes=boxes))
 need(isinstance(domains,list) and domains,'Explicit Root current dynamic airspace domains required')
 ground['resources']=list(resources.values());ground['runtime']['bindings']=list(bindings.values());ground['space_domains']=copy.deepcopy(domains)
 env=dict(schema='projectseele.r52.continuous-source-reservation-envelopes.v1',directory_geometry_sha256=sha(f['ground']),directory_matches=True,full_source_sha256=pins['eva/full_assembly_geometry_r52_sources.json'],model_source_sha256=pins['mesh/upright_outer_captured_r52.json'],path_source_sha256=sha(f['guide_source']),root_legs=rows,preload_chunks=sorted(tickets),finite_source_plane_reservations=source_planes,world_written=False,native_acceptance=False,scope='Reservation only: current seated-plug ascent hull; complete retained parts plus corrected plug; full head transfer; current production64m carrier/lead bounds')
 for key,name in [('legacy_floor_overlay_sha256','legacy_floor_recesses_r52'),('service_overlay_sha256','legacy_service_bypass_r52'),('level_overlay_sha256','legacy_compact_level_r52'),('deep_frame_sha256','legacy_deep_frame_r53'),('head_transfer_source_sha256','outer_head_transfer_r53')]:env[key]=pins['mesh/'+name+'.json']
 write(out/'CURRENT_SOURCE_ENVELOPES.json',env);write(out/'CURRENT_SPACE_DIRECTORY.json',ground);write(out/'CURRENT_AIR_SPACE_MERGE.json',dict(air_merge,source_geometry_sha256=sha(f['ground']),air_source_sha256=sha(f['air_transport']),additions_sha256=sha(f['air_space_additions']),world_written=False,native_admission=False))
def physical_readback(f,out,mechanical,world,pins,evidence):
 mech=read(mechanical/'ACTUAL_MECHANICAL_BINDINGS_READBACK.json');need(not mech['pending'],'Current physical supports pending: '+str(mech['pending'][:3]))
 owner=read(mechanical/'ROOT_CONTINUOUS_OWNER_DESIGN.json');interface=read(f['gate_interface']);peer=read(f['gate_peer'])
 need(peer.get('passed')is True and not peer['hits'] and peer['source_interface_sha256']==sha(f['gate_interface']),'Actual current pit/front sequence proof absent')
 need(interface['root_gate_candidate']['sha256']==sha(f['gates']) and interface['directory_sha256']==sha(f['ground']),'Current exact gate geometry/Root source differs')
 wanted={};roles=defaultdict(set)
 for g in owner['gates']:
  for step in phase_rows(g,mechanical):
   for c in step:
    p=tuple(c['position']);need(p not in wanted or wanted[p]==c['closed'],'Conflicting exact closed-gate owner');wanted[p]=c['closed'];roles[p].add(g['resource'])
 selected_chunks=defaultdict(set);cells=defaultdict(set)
 for x,y,z in wanted:selected_chunks[x//16,z//16].add(y//16);cells[x//16,z//16,y//16].add((x,y,z))
 actual={}
 for cx,cz,sy,palette,ix in iter_selected_sections(world,'projectseele:geofront',selected_chunks):
  a=ix.reshape(16,16,16)
  for x,y,z in cells[cx,cz,sy]:actual[x,y,z]=palette[int(a[y%16,z%16,x%16])]
 pending=[dict(position=p,expected=s,actual=actual.get(p),gates=sorted(roles[p]))for p,s in wanted.items()if actual.get(p)!=s]
 write(out/'CURRENT_CLOSED_GATE_READBACK.json',dict(world=str(world),checked_cells=len(wanted),pending=pending,world_written=False,native_cycle_passed=False))
 need(not pending,'Current closed-gate physical cells differ; see CURRENT_CLOSED_GATE_READBACK.json')
 ev={str(p.resolve()):sha(p)for p in evidence+[f['gates'],f['gate_interface'],f['gate_peer'],mechanical/'ACTUAL_MECHANICAL_BINDINGS_READBACK.json',out/'CURRENT_CLOSED_GATE_READBACK.json']}
 seals=sealed_front_specs(owner['gates']);report=dict(schema='projectseele.r52.actual-continuous-physical-readback.v1',map_author='root',world=str(world),verified=True,ground_sha256=sha(f['ground']),guide_source_sha256=sha(f['guide_source']),model_source_sha256=pins['mesh/upright_outer_captured_r52.json'],gate_source_sha256=sha(f['gates']),interlocks=dict(front_motion_requires_pit_open=True,return_front_seal_before_pit=True,peer_proxy_cells_by_bay={k:len(v['cells'])for k,v in seals.items()}),evidence=ev,world_written=False,native_cycle_passed=False,scope='Current saved closed gate states and actual finite native support faces, current source/peer sequence; full live motion remains guarded and requires native run')
 for key,name in [('floor_overlay_sha256','legacy_floor_recesses_r52'),('service_overlay_sha256','legacy_service_bypass_r52'),('level_overlay_sha256','legacy_compact_level_r52'),('deep_frame_sha256','legacy_deep_frame_r53'),('head_transfer_source_sha256','outer_head_transfer_r53')]:report[key]=pins['mesh/'+name+'.json']
 write(out/'CURRENT_PHYSICAL_READBACK.json',report)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--java',type=Path,default=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe'));ap.add_argument('--resume',action='store_true');a=ap.parse_args()
 doc=read(a.inputs);world=Path(doc['world']).resolve();out=candidate(a.out,world,not a.resume);out.mkdir(parents=True,exist_ok=True)
 lock=out/'INPUT_LOCK.json'
 if lock.exists():need(read(lock)==ref(a.inputs),'Resume requires the identical selected inputs')
 else:write(lock,ref(a.inputs))
 files=copy.deepcopy(doc['files'])
 for key,(name,digest)in DEFAULTS.items():files.setdefault(key,dict(path=str(AUDIT/name),sha256=digest))
 f={k:selected(v)for k,v in files.items()};evidence=[selected(r)for r in doc['construction_evidence']];need(evidence,'Current Root construction/readback evidence required')
 auth=SimpleNamespace(world=world,baseline=f['baseline'],baseline_sha256=sha(f['baseline']),root_plan=f['root_plan'],root_plan_sha256=sha(f['root_plan']))
 authority(auth,directory=read(f['ground']));auth_cli=['--world',world,'--baseline',f['baseline'],'--baseline-sha256',sha(f['baseline']),'--root-plan',f['root_plan'],'--root-plan-sha256',sha(f['root_plan'])]
 parser_args=export_sources(f,out,a.java);pins=asset_pins(f['selected_jar']);source_spaces(f,out,pins,doc.get('space_domains'))
 attempt=1
 while(out/f'mechanical_{attempt}').exists():attempt+=1
 mechanical=out/f'mechanical_{attempt}'
 run('mechanical_readback',[sys.executable,ROOT/'tools/prepare_mechanical_native_bindings_r52.py','--ground',out/'CURRENT_SPACE_DIRECTORY.json','--design',f['ground'],'--design-sha256',sha(f['ground']),'--guide-source',f['guide_source'],'--guide-source-sha256',sha(f['guide_source']),'--units',f['units'],'--gates',f['gates'],'--staff',f['staff'],'--selected-jar',f['selected_jar'],'--selected-build-receipt',f['selected_build_receipt'],'--out',mechanical,*auth_cli],out)
 physical_readback(f,out,mechanical,world,pins,evidence)
 bundle=out/f'bundle_{attempt}'
 run('bundle',[sys.executable,ROOT/'tools/build_r52_runtime_bundle_candidate.py','--ground',f['ground'],'--ground-sha256',sha(f['ground']),'--native-directory',mechanical/'NATIVE_CONTINUOUS_DIRECTORY_DESIGN.json','--owner-manifest',mechanical/'ROOT_CONTINUOUS_OWNER_DESIGN.json','--guideway-report',out/'CURRENT_GUIDEWAY_REPORT.json','--mechanical-rails',mechanical/'MECHANICAL_RAIL_REQUIREMENTS.json','--envelopes',out/'CURRENT_SOURCE_ENVELOPES.json','--lead-report',out/'CURRENT_LEGACY_LEAD_REPORT.json','--air-transport',f['air_transport'],'--personnel-lifts',f['personnel_lifts'],'--installed-intent','--physical-receipt',out/'CURRENT_PHYSICAL_READBACK.json','--java',a.java,'--parser-classpath-args',parser_args,'--selected-jar',f['selected_jar'],'--selected-build-receipt',f['selected_build_receipt'],'--out',bundle,*auth_cli],out)
 deployment=out/f'deployment_{attempt}'
 run('deployment_candidate',[sys.executable,ROOT/'tools/prepare_r52_runtime_deployment_candidate.py','--bundle',bundle/'ROOT_ASSEMBLY_BUNDLE.json','--out',deployment,*auth_cli],out)
 deployed=deployment/'DEPLOYMENT_PREPARATION.json';need(read(deployed)['ready'],'Actual current deployment candidate is not ready')
 native_command=None
 if 'native' in doc:
  n=doc['native'];identities=selected(n['original_identities']);server_release=selected(n['server_release'])
  native_command=[sys.executable,str(ROOT/'tools/run_r52_minimal_install_restart.py'),'--scope','124','--build-receipt',str(f['selected_build_receipt']),'--jar',str(f['selected_jar']),'--jar-sha256',sha(f['selected_jar']),'--deployment',str(deployed),'--deployment-sha256',sha(deployed),'--original-identities',str(identities),'--original-identities-sha256',sha(identities),'--server-release',str(server_release),'--server-release-sha256',sha(server_release),'--runtime',n['runtime'],'--observer-dir',n['observer_dir'],'--server-template',n['server_template'],'--launch-template',n['launch_template'],'--mtr',n['mtr'],'--out',str(out/f'native_{attempt}'),*[str(x)for x in auth_cli],'--run']
  write(out/'ROOT_NATIVE_COMMAND.json',dict(argv=native_command,requires_root_metadata_deployment_first=ref(deployed),executed=False))
 r=dict(world_written=False,game_started=False,native_verified=False,bundle=ref(bundle/'ROOT_ASSEMBLY_BUNDLE.json'),deployment=ref(deployed),source_inputs={k:ref(v)for k,v in f.items()},reports={p.name:sha(p)for p in out.glob('CURRENT_*.json')},native_install_command=native_command or 'execute in projectseele:geofront run nerv r52 install ROOT_ASSEMBLY_BUNDLE.json',next='Root deploys exact metadata manifest then runs current native installation/restart; no offline report replaces live movement')
 write(out/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json',r);print(json.dumps(r,ensure_ascii=False))
if __name__=='__main__':main()
