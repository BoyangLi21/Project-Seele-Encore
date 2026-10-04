"""Synthetic-only boundary tests. No production stage/ZIP, Java or MC execution."""
from pathlib import Path
import io,json,struct,unittest,uuid
from release_r45_contract import *
from package_r45 import Pipeline,copy_exact
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'artifacts/rebuild_r45/release_pipeline_sol_v13'/('synthetic_fixtures_'+uuid.uuid4().hex[:8])

def synthetic_class(protocol,unrelated='51'):
 entries=[b'\x01'+struct.pack('>H',len(x))+x.encode() for x in ['PROTOCOL_VERSION','Ljava/lang/String;','ConstantValue',protocol,unrelated]]
 entries.append(b'\x08\x00\x04')
 return b'\xca\xfe\xba\xbe\x00\x00\x00\x3d'+struct.pack('>H',7)+b''.join(entries)+b'\x00\x21\x00\x00\x00\x00\x00\x00\x00\x01'+struct.pack('>HHHHHIH',0x001a,1,2,1,3,2,6)+b'\x00\x00\x00\x00'

class Boundaries(unittest.TestCase):
 @classmethod
 def setUpClass(cls):FIX.mkdir(parents=True,exist_ok=False)
 def test_relative_path_escape_and_devices(self):
  for value in ['../level.dat','C:/eva/source','/tmp/save','x\\y','x//y','NUL.dat','folder/../x','COM1','x.']:
   with self.subTest(value=value),self.assertRaises(ContractError):relative(value)
  self.assertEqual(relative('dimensions/projectseele/geofront/entities/r.0.0.mca'),'dimensions/projectseele/geofront/entities/r.0.0.mca')
 def test_output_cannot_target_repo_or_source(self):
  for value in [str(ROOT),str(ROOT/'run/saves/world'),str(ROOT/'artifacts/server-ready-r44-stage')]:
   with self.subTest(value=value),self.assertRaises(ContractError):output_path(ROOT,value)
 def test_memory_16g_and_smoke_and_duplicates_rejected(self):
  for args in [['-Xms2G','-Xmx16G','-Dfile.encoding=UTF-8'],['-Xms1G','-Xmx4G','-Dfile.encoding=UTF-8'],['-Xms2G','-Xmx20G','-Xmx16G','-Dfile.encoding=UTF-8']]:
   with self.assertRaises(ContractError):check_memory(args)
  self.assertEqual(check_memory(['-Xms2G','-Xmx20G','-Dfile.encoding=UTF-8']),['-Xms2G','-Xmx20G','-Dfile.encoding=UTF-8'])
 def test_actual_constant_not_unrelated_protocol_literal(self):
  self.assertEqual(class_protocol(synthetic_class('49','51')),'49')
  self.assertEqual(class_protocol(synthetic_class('52','51')),'52')
  (FIX/'SYNTHETIC_PROTOCOL49.class.fixture').write_bytes(synthetic_class('49','51'))
 def test_no_development_paths_or_qa_lease(self):
  for raw in [b'{"directory":"D:/eva/artifacts/qa"}',b'{"role":"QA_ONLY"}',b'{"qa_lease":"one-shot"}',b'-Dprojectseele.r45CampaignAcceptancePlan=plan.json']:
   with self.assertRaises(ContractError):portable_text(raw,'fixture.json' if raw.startswith(b'{') else 'args.txt')
  portable_text(b'{"official_source":"https://www.complementary.dev/"}','credits.json')
 def test_dependency_side_and_version_closure(self):
  create={'mods':{'create':'6.0.8','ponder':'1.0.91'},'dependencies':[{'modId':'flywheel','mandatory':True,'side':'CLIENT','versionRange':'[1.0.0,2.0)'}]}
  check_dependencies([create],'SERVER')
  with self.assertRaises(ContractError):check_dependencies([create],'CLIENT')
  flywheel={'mods':{'flywheel':'1.0.5'},'dependencies':[]};check_dependencies([create,flywheel],'CLIENT')
  self.assertFalse(range_contains('0.9.0','[1.0.0,2.0)'))
  self.assertFalse(range_contains('2.0.0','[1.0.0,2.0)'))
 def test_world_progress_not_omittable(self):
  for name in ['level.dat','playerdata/UUID.dat','dimensions/projectseele/geofront/entities/r.0.0.mca','data/projectseele_tv_campaign.dat','mtr/UUID.dat','nerv_routes_r24.json.gz']:
   self.assertTrue(protected_world_file(name),name)
  self.assertFalse(protected_world_file('session.lock'))
 def test_copy_original_bytes_and_no_overwrite(self):
  source=FIX/'SYNTHETIC_state.bin';source.write_bytes(b'SYNTHETIC_ONLY\0uuid=fixture-original\0ledger=BORROWED\xff\0')
  h=sha(source);destination=FIX/'copy/unchanged.bin';copy_exact(source,destination,h)
  self.assertEqual(source.read_bytes(),destination.read_bytes())
  with self.assertRaises(FileExistsError):copy_exact(source,destination,h)
  with self.assertRaises(ContractError):copy_exact(source,FIX/'wrong.bin','0'*64)
 def test_old_manifest_reports_specific_failures(self):
  result=Validator(ROOT,{'schema':'R44','protocol':'49','server_jvm_args':['-Xms2G','-Xmx16G'],'world':{'role':'QA_ONLY'}}).validate()
  codes={row['code'] for row in result['issues']}
  self.assertTrue({'SCHEMA','PROTOCOL','SERVER_MEMORY','WORLD_ROLE','TEXTURE_UNSELECTED','ROOT_SOURCE_REVIEW'}<=codes)
  self.assertFalse(result['can_freeze']);self.assertFalse(result['released'])
 def test_slim_duplicate_unknown_mod_not_accepted(self):
  m={'common_mods':[{'filename':'create-1.20.1-6.0.8-slim.jar'},{'filename':'Ponder-Forge-1.20.1-1.0.91.jar'}]}
  v=Validator(ROOT,m);v.catalog('common_mods',COMMON,('server',));codes={row['code'] for row in v.issues}
  self.assertIn('MOD_UNKNOWN',codes);self.assertIn('MOD_MISSING',codes)
 def test_synthetic_acceptance_never_native_pass(self):
  pipeline=object.__new__(Pipeline);pipeline.m={'build':{'project_jar':{'sha256':'a'*64}}};pipeline.check_stage=lambda:{'stage_digest':'b'*64}
  p=FIX/'SYNTHETIC_acceptance.json'
  p.write_text(json.dumps({'schema':'projectseele.r45.stage-acceptance.v1','native_executed':True,'stage_digest':'b'*64,'tested_origin':'INSTALLED_STAGE_COPY','tested_payload_digest':'b'*64,'project_mod_sha256':'a'*64,'protocol':'52','scope':'SYNTHETIC','synthetic_fixture':True}),'utf-8')
  with self.assertRaisesRegex(ContractError,'Synthetic'):pipeline.acceptance(p)

def main():
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 report={'schema':'projectseele.r45.synthetic-input-checks.v13','scope':'SYNTHETIC_BOUNDARY_ONLY_NOT_REAL_PACKAGE_ACCEPTANCE',
 'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),
 'fixtures':str(FIX),'production_stage_executed':False,'production_zip_built':False,'java_started':False,'mc_started':False,'native_pass':False}
 (FIX/'synthetic_checks.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report))
 return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
