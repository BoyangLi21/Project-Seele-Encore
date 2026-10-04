"""Prepare the pinned original Create libraries for ForgeGradle userdev remapping.

Production keeps the verified unmodified universal jar. Only the development
copy removes embedded MC-bearing libraries so ForgeGradle remaps each one.
"""
from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'artifacts/rebuild_r45/city_motion/create-1.20.1-6.0.8.jar';OUT=ROOT/'.Codex/local-mods';OUT.mkdir(exist_ok=True)
meta=json.loads((SOURCE.parent/'create_version_metadata.json').read_text('utf8'));expected=next(f for f in meta['files']if f.get('primary'))['hashes']['sha512'];assert hashlib.sha512(SOURCE.read_bytes()).hexdigest()==expected
rows=[]
with zipfile.ZipFile(SOURCE)as z:
 tags=json.loads(z.read('META-INF/jarjar/metadata.json'));retained=[];removed=[]
 for info in tags['jars']:
  if info['identifier']['artifact']=='mixinextras-forge':retained.append(info);continue
  p=OUT/Path(info['path']).name;data=z.read(info['path']);p.write_bytes(data);removed.append(info['path']);rows.append(dict(file=str(p),source_entry=info['path'],sha256=hashlib.sha256(data).hexdigest()))
 target=OUT/'create-1.20.1-6.0.8-slim.jar'
 with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED)as out:
  for name in z.namelist():
   if name in removed or name=='META-INF/jarjar/metadata.json':continue
   out.writestr(name,z.read(name))
  out.writestr('META-INF/jarjar/metadata.json',json.dumps(dict(jars=retained)))
 rows.append(dict(file=str(target),production_jar_unchanged=True,scope='Development only; three MC-dependent embedded libraries supplied independently to fg.deobf',sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
(SOURCE.parent/'userdev_library_receipt.json').write_text(json.dumps(rows,indent=2),'utf8');print('Pinned Create userdev copies',len(rows))
