"""Thin-floor regression against the actual distributable and nested libraries."""
from pathlib import Path
import json,subprocess,zipfile,hashlib,os
from build_server_ready_pack import newest_project_jar
from launch_rendered_client_r17 import java_environment
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/combat_direction_r36/packaged_physics'
def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--source-override',action='store_true');args=parser.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);jar=newest_project_jar();libraries=[]
 with zipfile.ZipFile(jar) as z:
  metadata=json.loads(z.read('META-INF/jarjar/metadata.json'))
  if len(metadata['jars'])!=3:raise ValueError('Unexpected physics dependency set')
  for dependency in metadata['jars']:
   p=OUT/Path(dependency['path']).name;p.write_bytes(z.read(dependency['path']));libraries.append(p)
 cache=Path.home()/'.gradle/caches/modules-2/files-2.1'
 for module in ['com.google.code.gson/gson/2.10.1','org.joml/joml/1.10.5']:
  items=[p for p in (cache/module).rglob('*.jar') if not p.name.endswith('-sources.jar')]
  if len(items)!=1:raise ValueError('Ambiguous runtime library')
  libraries+=items
 java,env=java_environment();cp=os.pathsep.join(map(str,[jar,*libraries]))
 if args.source_override:
  override=OUT/'source_override';override.mkdir(exist_ok=True)
  sources=[ROOT/'src/main/java/com/projectseele/physics'/name for name in ['ArticulatedBody.java','ArticulatedInputTraceR45.java','AngularConeConstraintR45.java']]
  subprocess.run([str(java/'bin/javac.exe'),'-cp',cp,'-d',str(override),*map(str,sources)],check=True,env=env)
  cp=str(override)+os.pathsep+cp
 subprocess.run([str(java/'bin/javac.exe'),'-cp',cp,'-d',str(OUT),str(ROOT/'tools/java/PackagedPhysicsR36Smoke.java')],check=True,env=env)
 result=OUT/('thin_floor_source.json' if args.source_override else 'thin_floor.json')
 subprocess.run([str(java/'bin/java.exe'),'-Xmx192m','-cp',str(OUT)+os.pathsep+cp,'PackagedPhysicsR36Smoke',str(ROOT/'artifacts/combat_rebuild_r35/jbullet/articulated_bodies_r35.json'),str(result)],check=True,env=env)
 data=json.loads(result.read_text());data['mod_sha256']=None if args.source_override else hashlib.sha256(jar.read_bytes()).hexdigest();data['scope']='Source-only physics experiment' if args.source_override else 'One-block floor, three actual body profiles and captured crouched contact, shipped reobfuscated classes and exact nested libraries; no multiplayer claim.';result.write_text(json.dumps(data,indent=2))
if __name__=='__main__':main()
