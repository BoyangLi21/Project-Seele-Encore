"""Explicit immutable Root world/design authority for read-only bundle builders."""
from pathlib import Path
import hashlib,json,re

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def arguments(parser,required=True):
 for key in ('world','baseline','root-plan'):parser.add_argument('--'+key,type=Path,required=required)
 for key in ('baseline-sha256','root-plan-sha256'):parser.add_argument('--'+key,required=required)
def validate(args,epoch=None,directory=None):
 world=args.world.resolve();baseline=args.baseline.resolve();plan_path=args.root_plan.resolve()
 for file,expected in ((baseline,args.baseline_sha256),(plan_path,args.root_plan_sha256)):
  if not re.fullmatch(r'[0-9a-f]{64}',expected) or sha(file)!=expected:raise ValueError('Exact declared Root authority SHA differs: '+str(file))
 origin=read(baseline);plan=read(plan_path)
 if Path(origin.get('world','')).resolve()!=world or origin.get('world_writer')!='root' or origin.get('failed_R52_imported') is not False or not origin.get('files') or not re.fullmatch(r'[0-9a-f]{64}',origin.get('source_archive_sha256','')):raise ValueError('Explicit original baseline/actual World identity required; no retired QA selection')
 if not (world/'level.dat').is_file() or not (world/'dimensions/projectseele/geofront/region').is_dir():raise ValueError('Actual declared native World/geofront regions absent')
 if plan.get('schema')!='projectseele.complete-root-spatial-plan.v1' or plan.get('map_author')!='root' or not isinstance(plan.get('epoch'),int) or plan['epoch']<=0:raise ValueError('Explicit Root spatial declaration required')
 if epoch is not None and epoch!=plan['epoch']:raise ValueError('Selected directory and declared Root epoch differ')
 if directory is not None:
  if directory.get('epoch')!=plan['epoch']:raise ValueError('Ground epoch differs from current Root plan')
  bays=[n for n in directory['nodes'] if n['role']=='BAY'];banks=[n for n in directory['nodes'] if n['role']=='BANK']
  if len(bays)!=3 or len(banks)!=9 or any(n['foot_frame']['translation'][1]!=plan['bay_foot_y'] for n in bays) or any(n['foot_frame']['translation'][1]!=plan['bank_foot_y'] for n in banks):raise ValueError('Actual bay/bank depths differ from current declared Root frame')
  if set(n['foot_frame']['translation'][0] for n in bays)!=set(plan['lane_centres_x']):raise ValueError('Actual original lanes differ from current Root declaration')
  expected_roles={r['bank']:r['intent'] for r in plan['bank_roles']}
  if {r['bank']:r['intent'] for r in directory['bank_roles']}!=expected_roles:raise ValueError('Actual bank exit roles differ from current Root declaration')
  if any({n['foot_frame']['translation'][0] for n in banks if n['bank']==bank}!=set(plan['lane_centres_x']) for bank in expected_roles):raise ValueError('Every declared bank must retain all three original lanes')
 return {'world':world.as_posix(),'baseline_file':baseline.as_posix(),'baseline_sha256':args.baseline_sha256,'root_plan_file':plan_path.as_posix(),'root_plan_sha256':args.root_plan_sha256,'source_archive_sha256':origin['source_archive_sha256'],'epoch':plan['epoch']}

def validate_record(record,directory=None):
 from types import SimpleNamespace
 args=SimpleNamespace(world=Path(record['world']),baseline=Path(record['baseline_file']),root_plan=Path(record['root_plan_file']),baseline_sha256=record['baseline_sha256'],root_plan_sha256=record['root_plan_sha256'])
 actual=validate(args,epoch=record['epoch'],directory=directory)
 if actual!=record:raise ValueError('Recorded current Root authority differs from its exact source')
 return actual

def original_identities(path,expected_sha256,world):
 import uuid
 path=Path(path).resolve()
 if not re.fullmatch(r'[0-9a-f]{64}',expected_sha256 or '') or sha(path)!=expected_sha256:raise ValueError('Explicit original-identity baseline SHA differs')
 document=read(path);rows=document.get('managed_geofront')
 if 'world' in document and Path(document['world']).resolve()!=Path(world).resolve():raise ValueError('Original identities belong to another World')
 if not isinstance(rows,dict) or not rows:raise ValueError('Complete explicit original-identity table required')
 for identity,row in rows.items():
  if str(uuid.UUID(identity))!=identity or set(row)!={'type','dimension'} or not isinstance(row['type'],str) or not row['type'] or row['dimension']!='dimensions/projectseele/geofront':raise ValueError('Exact original UUID/type/dimension required')
 return rows
def candidate(path,world,require_fresh=False):
 path=Path(path).resolve();world=Path(world).resolve()
 if path==world or path.is_relative_to(world):raise ValueError('Candidate output must stay outside the actual World')
 for parent in (path,*path.parents):
  if (parent/'level.dat').exists() or (parent/'session.lock').exists():raise ValueError('Candidate output cannot lie inside any native World')
 if require_fresh and path.exists() and any(path.iterdir()):raise ValueError('Fresh candidate output required; preserve earlier receipts')
 return path
