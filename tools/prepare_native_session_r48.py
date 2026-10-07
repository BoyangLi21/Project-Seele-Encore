"""One retained Forge R47 headless launch, bounded original NPC session; Root alone runs it."""
from pathlib import Path
import argparse,json,os,queue,re,subprocess,threading,time,zipfile
from launch_rendered_client_r17 import java_environment
ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'artifacts/rebuild_r47/lifts_navigation/native_launch_prepare/server-dedicated.json'
CRITICAL=['assets/projectseele/mesh/tv_shoulder_shells_r44.json','assets/projectseele/blockstates/entry_plug_bridge_deck.json','assets/projectseele/blockstates/entry_plug_bridge_guard.json']
def same(a,b):
 if a.stat().st_size!=b.stat().st_size:return False
 with a.open('rb')as x,b.open('rb')as y:
  while True:
   ax,by=x.read(1048576),y.read(1048576)
   if ax!=by:return False
   if not ax:return True
def main():
 p=argparse.ArgumentParser();p.add_argument('--jar',type=Path,required=True);p.add_argument('--overlay',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True)
 p.add_argument('--source-world',type=Path,required=True);p.add_argument('--qa-world',type=Path,required=True);p.add_argument('--server-root',type=Path,required=True)
 p.add_argument('--copy-receipt',type=Path,required=True);p.add_argument('--launch-template',type=Path,default=DEFAULT);p.add_argument('--out',type=Path,required=True);p.add_argument('--run',action='store_true');p.add_argument('--hold-open',action='store_true');p.add_argument('--timeout',type=int,default=1200)
 p.add_argument('--revision',type=int,choices=(48,49),default=48);a=p.parse_args()
 for k in('jar','overlay','runtime','source_world','qa_world','server_root','copy_receipt','out'):setattr(a,k,getattr(a,k).resolve())
 base=ROOT/f'artifacts/rebuild_r{a.revision}'
 assert a.source_world==(base/f'construction/SEELE_R{a.revision}_WORLD').resolve(),'Only the confirmed construction source is allowed'
 assert a.qa_world.is_relative_to((base/'native_qa').resolve())and a.server_root.is_relative_to((base/'native_qa').resolve()),'Root QA server and world must stay in the named native_qa workspace'
 assert a.source_world!=a.qa_world and not a.qa_world.is_relative_to(a.source_world)and not a.source_world.is_relative_to(a.qa_world),'QA must be a distinct Root-only once-copied directory'
 assert(a.source_world/'level.dat').is_file()and a.jar.is_file()and a.overlay.is_dir()and a.runtime.is_dir()
 if a.revision==49:
  from r49_selected_payload import validate_selected_payload,validate_identity_coverage
 else:
  from r48_selected_payload import validate_selected_payload,validate_identity_coverage
 identity_coverage=validate_identity_coverage(a.overlay,a.runtime)
 selected_payload=validate_selected_payload(a.jar,a.overlay)
 with zipfile.ZipFile(a.jar)as z:
  for name in CRITICAL:
   f=a.overlay/name;assert f.is_file()and z.read(name)==f.read_bytes(),('Final Jar differs from selected R48 overlay',name)
  for name in('UndergroundSortieR48','EntryPlugBridgeLayoutR48','EntryPlugBridgeDeckR48'):
   assert 'com/projectseele/world/'+name+'.class'in z.namelist(),('Final class missing',name)
 rooms=json.loads((a.source_world/'r47_pilot_restrooms.json').read_text('utf8'))['slots'];assert len(rooms)==3
 a.out.mkdir(parents=True,exist_ok=True);spec=json.loads(a.launch_template.read_text('utf8'))
 admissions=('projectseele.nativeCandidateBindingR45','projectseele.nativeCandidateBindingR45SHA256','projectseele.nativeCandidateAdmissionR45','projectseele.nativeFacilityBindingR45','projectseele.nativeFacilityBindingR45SHA256','projectseele.nativeFacilityAdmissionR45')
 assert not any(s.startswith('-D'+key+'=')for s in spec['command']for key in admissions),'Old candidate admission is a different exact world/progress scope; supply a clean production launch template, never silently disable an admission gate'
 old_probes=('-Dprojectseele.r47CityUnionServerProbe=','-Dprojectseele.r47CityUnionProbeCentre=')
 portable='-Dprojectseele.combatBundleDirectory=projectseele-local-maps'
 assert not any(s.startswith('-Dprojectseele.')and s!=portable and not s.startswith(old_probes)for s in spec['command']),'Review/resource override in launch template; normal R48 production must resolve the selected runtime owners'
 cmd=[s for s in spec['command']if not s.startswith(old_probes+('-Xms','-Xmx'))]
 for flag in('--world','--universe'):
  if flag in cmd:i=cmd.index(flag);del cmd[i:i+2]
 cmd[1:1]=['-Xms1G','-Xmx6G'];cmd+=['--universe',a.qa_world.parent.as_posix(),'--world',a.qa_world.name]
 spec=dict(command=cmd,workingDirectory=str(a.server_root),environment={k:v for k,v in spec.get('environment',{}).items()if k!='MOD_CLASSES'},prepared_only=not a.run)
 def quote(s):assert not any(c in s for c in '\r\n\0');return'"'+s.replace('\\','\\\\').replace('"','\\"')+'"'
 arg=a.out/'launch.args';arg.write_text('\n'.join(quote(x)for x in cmd[1:])+'\n','utf8');(a.out/'launch.json').write_text(json.dumps(spec,indent=2),'utf8')
 contract={'final_jar':str(a.jar),'selected_overlay':str(a.overlay),'selected_runtime':str(a.runtime),'source_authority':str(a.source_world),'qa_world':str(a.qa_world),'copy_receipt':str(a.copy_receipt),'critical_selected_jar_bytes_match':True,'NPCs':[{'variant':r['variant'],'pilot_uuid':r['pilot_uuid'],'goal':r['goal'],'stand':r['stand'],'door':r['door_lower']}for r in rooms],'no_world_copy_by_this_tool':True,'headless_only':'Original NPC start/stop and server observations; not human/client inputs, V, UI, or art','function_pass_claimed':False}
 contract.update(selected_payload=selected_payload,identity_coverage=identity_coverage,admission_scope='NORMAL_R48_PRODUCTION_INPUTS; no R45 City/facility candidate admission pass claimed')
 (a.out/'inputs.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8')
 if not a.run:print('Prepared only:',a.out);return
 assert(a.qa_world/'level.dat').is_file()and a.copy_receipt.is_file(),'Root must make exactly one QA copy and record it before --run'
 receipt=json.loads(a.copy_receipt.read_text('utf-8-sig'));assert Path(receipt['source_world']).resolve()==a.source_world and Path(receipt['qa_world']).resolve()==a.qa_world and receipt['copied_once']is True
 staged=list((a.server_root/'mods').glob('projectseele-*.jar'));assert len(staged)==1 and same(staged[0],a.jar),'Root must stage exactly the selected final Jar'
 for selected in sorted(a.runtime.rglob('*')):
  if selected.is_file():
   rel=selected.relative_to(a.runtime);assert(a.server_root/rel).is_file()and same(selected,a.server_root/rel),('Selected runtime differs',str(rel))
 assert(a.server_root/'projectseele-local-maps').is_dir()and(a.server_root/'eula.txt').is_file()
 assert 'eula=true'in(a.server_root/'eula.txt').read_text('utf8'),'Use the existing Root local EULA agreement; do not auto-accept'
 props=dict(line.split('=',1)for line in(a.server_root/'server.properties').read_text('utf8').splitlines()if'='in line and not line.startswith('#'))
 assert props.get('server-ip')=='127.0.0.1','Native QA is local loopback only'
 assert not(a.out/'server.log').exists(),'Preserve earlier observations; use a new attempt out while reusing the one QA copy'
 assert all((a.qa_world/f).is_file()for f in('r48_entry_plug_bridge.json','r48_underground_sortie.json','r47_pilot_restrooms.json'))
 env=java_environment()[1];env.update(spec['environment']);env.pop('MOD_CLASSES',None)
 assert not any('-Dprojectseele.'in env.get(key,'')for key in('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS')),'Inherited Java options contain a review/admission/resource override; use clean production options without silently disabling a gate'
 lines=[];q=queue.Queue();started=time.monotonic();proc=None;failure=None
 with(a.out/'server.log').open('x',encoding='utf8')as log:
  proc=subprocess.Popen([cmd[0],'@'+str(arg)],cwd=a.server_root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
  def read():
   for line in proc.stdout:log.write(line);log.flush();lines.append(line);q.put(line)
  reader=threading.Thread(target=read,daemon=True);reader.start()
  def send(command):
   assert '\n'not in command and '\r'not in command
   (a.out/'commands.jsonl').open('a',encoding='utf8').write(json.dumps({'elapsed':time.monotonic()-started,'command':command,'submitted_not_function_pass':True},ensure_ascii=False)+'\n');proc.stdin.write(command+'\n');proc.stdin.flush()
  def native_route_fault(v,uid,index,phase):
   fresh=lines[index:]
   marker=r'NERV original pilot (?:full boarding path (?:failed|unsafe node)|route held in place): eva='+str(v)+r'\b'
   rejected=('登机通道还不能通过，驾驶员先在原地待命。','boarding route has an unsupported anchor.',
    '原驾驶员待命室元数据未接通','机体尚未在机库停稳','还没有确认驾驶员的位置','驾驶员正在返回待命，请等待',
    '待命室离座干点暂不可用','驾驶员还在另一台设备内','驾驶员尚未到达登机通道起点',
    '原待命室门框状态不完整',f'EVA-0{v} is not loaded.',f'EVA-0{v} already has an entry-plug occupant.',
    f'EVA-0{v} external entry plug is unavailable.')if phase=='boarding'else('未执行离栓：',)
   first=next((line for line in fresh if re.search(marker,line)or any(text in line for text in rejected)
    or phase=='boarding'and re.search(r'\[minecraft/MinecraftServer\]: [A-Z][A-Z0-9_]+: ',line)),None)
   if first is None:return
   detail=next((line for line in reversed(fresh)if('DUMMY LAST NATIVE PATH'in line or'full boarding path failed:'in line)and uid in line),None)
   (a.out/('npc_'+str(v)+'_first_fault.json')).write_text(json.dumps({'variant':v,'original_pilot_uuid':uid,'phase':phase,'first_native_fault_line':first,'single_latest_native_path':detail,'fresh_input_log_start':index,'preserved_game_result':True,'normal_stop_requested':True,'function_pass_claimed':False},ensure_ascii=False,indent=2),'utf8')
   raise RuntimeError('Original NPC '+phase+' explicitly failed; preserved first native fault for unit0'+str(v))
  def waitfor(pattern,index=0,seconds=180,fault=None):
   deadline=time.monotonic()+seconds
   while time.monotonic()<deadline:
    if fault is not None:fault()
    for line in lines[index:]:
     if re.search(pattern,line):return line
    index=len(lines)
    if proc.poll()is not None:raise RuntimeError('Native server exited before observation')
    if time.monotonic()-started>a.timeout:raise TimeoutError('Bounded session time exhausted')
    try:q.get(timeout=1)
    except queue.Empty:pass
   raise TimeoutError('No native observation: '+pattern)
  try:
   waitfor(r'Done \(',seconds=300);send('seele eva status');send('execute in projectseele:geofront run forceload query')
   for _ in range(30):
    mark=len(lines);send('seele eva status');send('seele eva dummy status');time.sleep(2)
    ready=''.join(lines[mark:])
    if all('DUMMY EVA-0'+str(v)+' stage=STANDBY 'in ready and 'EVA-0'+str(v)+' phase=PARKED loaded=true canonical='in ready for v in range(3)):break
   else:raise RuntimeError('Three original NPCs/EVA were not initially STANDBY/PARKED loaded; preserve state, do not reset/replace')
   for room in sorted(rooms,key=lambda r:r['variant']):
    v=room['variant'];uid=room['pilot_uuid'];unit='unit0'+str(v)
    send('execute in projectseele:geofront run data get entity '+uid+' UUID');send('execute in projectseele:geofront run data get entity '+uid+' Pos')
    index=len(lines);send('seele eva dummy start '+unit);boarded=None
    for _ in range(90):
     native_route_fault(v,uid,index,'boarding');time.sleep(2);native_route_fault(v,uid,index,'boarding');mark=len(lines);send('seele eva dummy status')
     try:boarded=waitfor('DUMMY EVA-0'+str(v)+r' stage=IN_PLUG ',mark,seconds=2,fault=lambda:native_route_fault(v,uid,index,'boarding'));break
     except TimeoutError:continue
    if boarded is None:raise TimeoutError('Original NPC did not complete native boarding: '+unit)
    send('execute in projectseele:geofront run data get entity '+uid+' UUID');send('execute in projectseele:geofront run data get entity '+uid+' Pos');index=len(lines);send('seele eva dummy stop '+unit);returned=None
    for _ in range(90):
     native_route_fault(v,uid,index,'return');time.sleep(2);native_route_fault(v,uid,index,'return');mark=len(lines);send('seele eva dummy status')
     try:returned=waitfor('DUMMY EVA-0'+str(v)+r' stage=STANDBY ',mark,seconds=2,fault=lambda:native_route_fault(v,uid,index,'return'));break
     except TimeoutError:continue
    if returned is None:raise TimeoutError('Original NPC did not return STANDBY: '+unit)
    send('execute in projectseele:geofront run data get entity '+uid+' Pos');send('execute in projectseele:geofront run data get entity '+uid+' UUID');send('execute in projectseele:geofront run data get block '+' '.join(map(str,room['door_lower'])))
    (a.out/('npc_'+str(v)+'_observations.json')).write_text(json.dumps({'pilot_uuid':uid,'native_boarded_line':boarded,'native_returned_line':returned,'full_success_not_claimed':'Inspect same UUID, original capsule/seat vehicle and exact stand/chair/door readback; STANDBY alone does not assert atOriginalStandbyR47'},ensure_ascii=False,indent=2),'utf8')
   send('seele eva status');send('seele eva dummy status');send('execute in projectseele:geofront run forceload query');time.sleep(3)
   if a.hold_open:
    print('R48_NPC_OBSERVATIONS_READY. Native server remains in this one QA copy. Real client/manual cases may follow; enter END_NORMAL to save/stop.',flush=True)
    while True:
     command=input()
     if command.strip()=='END_NORMAL':break
     if command.strip():send(command.strip())
  except Exception as e:failure=repr(e)
  finally:
   if proc.poll()is None:send('save-all flush');send('stop')
   try:proc.wait(timeout=60)
   except subprocess.TimeoutExpired:
    failure=(failure or'')+'; normal stop exceeded 60 seconds; Root must inspect this live process, no automatic kill'
    print('Normal stop is incomplete. Keeping this server log/stdout attached; Root must inspect the same process. No automatic kill or second launch.',flush=True)
    while proc.poll()is None:
     try:proc.wait(timeout=60)
     except subprocess.TimeoutExpired:print('Still awaiting the same native process normal exit; log remains attached.',flush=True)
   reader.join(timeout=2)
 (a.out/'session.json').write_text(json.dumps({'exit_code':proc.poll(),'failure':failure,'NPC_headless_observations_only':True,'world_is_QA_copy':True,'no_reset_force_fakeplayer_teleport_or_external_client':True,'whole_R48_function_pass_claimed':False,'human_cases_pending':['bridge occupied pause','actual rear/underground door inputs and rightful/other caller lifecycle','underground drive back pad/recovery','V key original UUID/support'],'all_dimensions_saved_log_seen':any('All dimensions are saved'in x for x in lines)},ensure_ascii=False,indent=2),'utf8')
 if failure:raise RuntimeError(failure)
 print('Native NPC observations saved; remaining cases require real inputs:',a.out)
if __name__=='__main__':main()
