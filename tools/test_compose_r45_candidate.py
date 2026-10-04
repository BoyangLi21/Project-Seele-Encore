"""Tiny real Anvil fixtures for offline composer safety; no Minecraft/Java."""
import copy,gzip,hashlib,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import nbtlib,numpy as np
import compose_r45_candidate as compose
from transplant_s22_authority import build_region,chunk_blob,flush_decoded,read_region,parse_chunk
from apply_s20_approved_semantic_repairs import parse_state
from query_blocks import read_box,iter_block_entities
from install_city_rigid_metadata_r45 import same_tag

ROOT=Path(__file__).resolve().parents[1]
STATE='minecraft:oak_sign[rotation=0,waterlogged=false]'
UUID='50ba377e-9053-5dfa-93be-9601e623037c'
def js(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf8')
def pin(p,root):return dict(path=p.relative_to(root).as_posix(),sha256=compose.sha(p))
def save_catalog(p,v):js(p,v);p.with_suffix('.json.sha256').write_text(compose.sha(p)+'\n','ascii')
class ComposerFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.policy=compose.Policy(self.root);self.source=self.policy.source
        data=self.source/'dimensions/projectseele/geofront';region=data/'region/r.0.0.mca';region.parent.mkdir(parents=True)
        tag=nbtlib.Compound(dict(id=nbtlib.String('minecraft:sign'),x=nbtlib.Int(1),y=nbtlib.Int(0),z=nbtlib.Int(0),keepPacked=nbtlib.Byte(0),Unknown=nbtlib.Compound(dict(TypedFlag=nbtlib.Byte(1),Inventory=nbtlib.List[nbtlib.Compound]([nbtlib.Compound(dict(Slot=nbtlib.Byte(0),id=nbtlib.String('minecraft:diamond'),Count=nbtlib.Byte(3)))]),Longs=nbtlib.LongArray([7,99]))),Text=nbtlib.String('original')))
        section=nbtlib.Compound(dict(Y=nbtlib.Byte(0),biomes=nbtlib.Compound(dict(palette=nbtlib.List[nbtlib.String](['minecraft:plains'])))))
        chunk=nbtlib.Compound(dict(DataVersion=nbtlib.Int(3465),xPos=nbtlib.Int(0),zPos=nbtlib.Int(0),Status=nbtlib.String('minecraft:full'),sections=nbtlib.List[nbtlib.Compound]([section]),block_entities=nbtlib.List[nbtlib.Compound]([tag]),UnknownChunk=nbtlib.Compound(dict(Owner=nbtlib.String('human'),Bytes=nbtlib.ByteArray([1,2,3])))))
        ids=np.zeros(4096,np.int32);ids[1]=1;palette=[parse_state('minecraft:air'),parse_state(STATE)];flush_decoded(chunk,{0:(palette,ids,{'minecraft:air':0,STATE:1})});blobs=[None]*1024;blobs[0]=chunk_blob(nbtlib.File(chunk));region.write_bytes(build_region(bytes(4096),blobs))
        nbtlib.File({'Data':nbtlib.Compound(dict(LevelName=nbtlib.String('fixture'),WorldGenSettings=nbtlib.Compound(dict(seed=nbtlib.Long(-3816295015381828007)))))},gzipped=True).save(self.source/'level.dat')
        owner=data/'data/projectseele_tokyo3_building_world_id_r44.dat';owner.parent.mkdir();nbtlib.File({'data':nbtlib.Compound(dict(WorldUUID=nbtlib.String(UUID)))},gzipped=True).save(owner)
        player=self.source/'playerdata/original.dat';player.parent.mkdir();player.write_bytes(b'original-player-inventory-full-bytes')
        entities=data/'entities/r.0.0.mca';entities.parent.mkdir();entities.write_bytes(b'original-UUID-entity-file-full-bytes')
        source_files={p.relative_to(self.source).as_posix():compose.sha(p) for p in self.source.rglob('*') if p.is_file()};self.original=source_files
        baseline=self.policy.art/'baseline.json';js(baseline,dict(backup=str(self.source),files=source_files))
        tools=self.root/'tools';tools.mkdir();shutil.copyfile(ROOT/'tools/compose_r45_candidate.py',tools/'compose_r45_candidate.py')
        codec=self.root/compose.CODEC_REL;codec.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/compose.CODEC_REL,codec)
        traits=self.policy.art/'fixture_traits.json';js(traits,{'minecraft:air':{'has_block_entity':False},'minecraft:white_concrete':{'has_block_entity':False},STATE:{'has_block_entity':True}})
        self.after_tag=copy.deepcopy(tag);self.after_tag['Text']=nbtlib.String('edited');self.rows=[dict(pos=[0,0,0],before='minecraft:air',after='minecraft:white_concrete',before_nbt=None,after_nbt=None,owner='r45/fixture/whole'),dict(pos=[1,0,0],before=STATE,after=STATE,before_nbt=tag.snbt(),after_nbt=self.after_tag.snbt(),owner='r45/fixture/whole')]
        self.folder=self.policy.art/'fixture_inputs';self.folder.mkdir();self.forward=self.folder/'forward.jsonl.gz';self.inverse=self.folder/'inverse.jsonl.gz';self.write_pairs()
        self.catalog=dict(schema=compose.SCHEMA,source='artifacts/rebuild_r45/source_world_backup',baseline=pin(baseline,self.root),codec=pin(codec,self.root),native_state_contract=pin(traits,self.root),identity_file=owner.relative_to(self.source).as_posix(),seed=-3816295015381828007,world_uuid=UUID,dimension='projectseele:geofront',epochs=[],allowed_file_targets=[],default_components=['tv_shells_v1'],components=[dict(id='tv_shells_v1',classification='CLASSIFIED_CANDIDATE_NOT_NATIVE',owner_prefixes=['r45/fixture/'],patches=[dict(forward=pin(self.forward,self.root),inverse=pin(self.inverse,self.root),rows=2)],files=[],depends_on=[])])
        self.catalog_path=self.policy.art/'fixture_catalog.json';self.seal()
    def write_pairs(self):
        for path,inverse in [(self.forward,False),(self.inverse,True)]:
            with gzip.open(path,'wt',encoding='utf8') as f:
                for r in self.rows:
                    v=copy.deepcopy(r)
                    if inverse:v['before'],v['after'],v['before_nbt'],v['after_nbt']=r['after'],r['before'],r['after_nbt'],r['before_nbt']
                    f.write(json.dumps(v)+'\n')
    def seal(self):save_catalog(self.catalog_path,self.catalog)
    def source_same(self):self.assertEqual(self.original,{p.relative_to(self.source).as_posix():compose.sha(p) for p in self.source.rglob('*') if p.is_file()})
    def run_case(self,name='test',apply=False):return compose.run(self.catalog_path,self.policy,self.policy.reports/name,destination=self.policy.candidates/name if apply else None)
    def test_dry_run_then_apply_full_nbt_and_inverse(self):
        result=self.run_case('dry');self.assertEqual(result['status'],'DRY_RUN_EXACT_BEFORE_CANDIDATE_ONLY');self.assertFalse(self.policy.candidates.exists());self.source_same()
        result=self.run_case('apply',True);world=self.policy.candidates/'apply/world';self.assertFalse(result['native_pass']);self.assertEqual(read_box(world,'projectseele:geofront',(0,0,0),(1,0,0))[(0,0,0)],'minecraft:white_concrete')
        actual=dict(iter_block_entities(world,'projectseele:geofront',(0,0,0),(1,0,0)))[(1,0,0)];self.assertTrue(same_tag(actual,self.after_tag));self.source_same()
        original_region=self.source/'dimensions/projectseele/geofront/region/r.0.0.mca';inverse=self.policy.candidates/'apply/inverse/dimensions/projectseele/geofront/region/r.0.0.mca';self.assertEqual(inverse.read_bytes(),original_region.read_bytes())
        for path in ['playerdata/original.dat','dimensions/projectseele/geofront/entities/r.0.0.mca','level.dat']:self.assertEqual((world/path).read_bytes(),(self.source/path).read_bytes())
    def test_reject_protected_existing_and_traversal_targets(self):
        for p in [self.source,self.root/'run/saves/real',self.policy.candidates.parent,self.policy.candidates/'../source_world_backup']:
            with self.assertRaises(compose.Hold):self.policy.new_candidate(p)
        existing=self.policy.candidates/'existing';existing.mkdir(parents=True)
        with self.assertRaises(compose.Hold):self.policy.new_candidate(existing)
        for p in ['../playerdata/x','playerdata/x','dimensions/projectseele/geofront/entities/x','level.dat']:
            with self.assertRaises(compose.Hold):self.policy.relative(p)
        self.source_same()
    def test_frozen_input_and_catalog_tamper(self):
        self.forward.write_bytes(self.forward.read_bytes()+b'x')
        with self.assertRaises(compose.Hold):self.run_case('sha',True)
        self.assertFalse(self.policy.candidates.exists());self.source_same();self.write_pairs();self.catalog['components'][0]['patches'][0]['forward']=pin(self.forward,self.root);self.seal();self.catalog_path.write_text(self.catalog_path.read_text()+' ')
        with self.assertRaises(compose.Hold):self.run_case('seal',True)
        self.assertFalse((self.policy.candidates/'seal').exists())
    def test_foreign_typed_nbt_whole_component_hold(self):
        tag=nbtlib.parse_nbt(self.rows[1]['before_nbt']);tag['Unknown']['TypedFlag']=nbtlib.Int(1);self.rows[1]['before_nbt']=tag.snbt();self.write_pairs();p=self.catalog['components'][0]['patches'][0];p['forward']=pin(self.forward,self.root);p['inverse']=pin(self.inverse,self.root);self.seal()
        with self.assertRaises(compose.Hold):self.run_case('nbt',True)
        self.assertFalse(self.policy.candidates.exists());self.source_same();self.assertTrue(compose.read(self.policy.reports/'nbt/conflicts.json')['all_whole_components_held'])
    def test_noncontiguous_chain_and_missing_native_state(self):
        second=copy.deepcopy(self.catalog['components'][0]);second['id']='ordinary_metal_doors_v1';second['depends_on']=['tv_shells_v1'];self.catalog['components'].append(second);self.catalog['default_components'].append(second['id']);self.seal()
        with self.assertRaises(compose.Hold):self.run_case('chain',True)
        self.assertFalse(self.policy.candidates.exists());self.source_same()
        self.catalog['components']=self.catalog['components'][:1];self.catalog['default_components']=['tv_shells_v1'];self.rows[0]['after']='minecraft:unverified';self.write_pairs();p=self.catalog['components'][0]['patches'][0];p['forward']=pin(self.forward,self.root);p['inverse']=pin(self.inverse,self.root);self.seal()
        with self.assertRaises(compose.Hold):self.run_case('state',True)
        self.assertFalse(self.policy.candidates.exists());self.source_same()
    def test_original_progress_sha_drift_and_copy_failure_receipt(self):
        original=self.source/'playerdata/original.dat';saved=original.read_bytes();original.write_bytes(b'foreign')
        with self.assertRaises(compose.Hold):self.run_case('progress',True)
        self.assertFalse(self.policy.candidates.exists());original.write_bytes(saved)
        actual_loader=compose.load_codec
        def broken(policy,catalog):
            codec=actual_loader(policy,catalog)
            def fail(*args,**kwargs):raise OSError('fixture injected region prepare failure')
            codec.mutate_chunk=fail;return codec
        with patch.object(compose,'load_codec',broken):
            with self.assertRaises(OSError):self.run_case('failure',True)
        self.source_same();receipt=compose.read(self.policy.candidates/'failure/composition.json');self.assertEqual(receipt['status'],'FAILED_CANDIDATE_PRESERVED_NOT_RELEASE');self.assertFalse(receipt['runtime_promoted'])
    def test_exact_derived_chain_and_absent_owner_marker_inverse(self):
        before=self.source/'quality_walk_cases.json';js(before,[dict(id='original',UnknownHuman='keep')]);self.original['quality_walk_cases.json']=compose.sha(before)
        baseline=self.policy.art/'baseline.json';js(baseline,dict(backup=str(self.source),files=self.original));self.catalog['baseline']=pin(baseline,self.root)
        middle=self.folder/'middle.json';final=self.folder/'final.json';marker=self.folder/'new_owner.dat';js(middle,[dict(id='original',UnknownHuman='keep'),dict(id='new',path=[1])]);js(final,[dict(id='original',UnknownHuman='keep'),dict(id='new',path=[2])]);marker.write_bytes(b'fixed-original-owner-marker-runtime-disabled')
        target='dimensions/projectseele/geofront/data/projectseele_dead_sea_chamber_r45.dat';self.catalog['allowed_file_targets']=['quality_walk_cases.json',target];self.catalog['components'][0]['files']=[dict(target='quality_walk_cases.json',before_sha256=compose.sha(before),after=pin(middle,self.root),kind='DERIVED_STATIC_FILE'),dict(target='quality_walk_cases.json',before_sha256=compose.sha(middle),after=pin(final,self.root),kind='DERIVED_STATIC_FILE'),dict(target=target,before_sha256=None,after=pin(marker,self.root),kind='NEW_OWNER_MARKER')];self.seal()
        result=self.run_case('derived',True);world=self.policy.candidates/'derived/world';self.assertEqual((world/'quality_walk_cases.json').read_bytes(),final.read_bytes());self.assertEqual((self.policy.candidates/'derived/inverse/quality_walk_cases.json').read_bytes(),before.read_bytes());self.assertEqual(len(result['files']),2);self.assertTrue(next(r for r in result['files'] if r['target']==target)['inverse_remove_only_new_hash']);self.source_same()
    def test_existing_saved_data_not_relabelled_new_owner(self):
        relative='dimensions/projectseele/geofront/data/projectseele_dead_sea_chamber_r45.dat';source=self.source/relative;source.write_bytes(b'original-active-owner-full-fields');self.original[relative]=compose.sha(source)
        baseline=self.policy.art/'baseline.json';js(baseline,dict(backup=str(self.source),files=self.original));self.catalog['baseline']=pin(baseline,self.root)
        payload=self.folder/'foreign_owner.dat';payload.write_bytes(b'foreign-runtime-owner')
        self.catalog['allowed_file_targets']=[relative];self.catalog['components'][0]['files']=[dict(target=relative,before_sha256=compose.sha(source),after=pin(payload,self.root),kind='NEW_OWNER_MARKER')];self.seal()
        with self.assertRaises(compose.Hold):self.run_case('saveddata',True)
        self.assertFalse(self.policy.candidates.exists());self.source_same()
if __name__=='__main__':unittest.main(verbosity=2)



